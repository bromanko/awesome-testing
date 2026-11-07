#!/usr/bin/env python3
"""Prepare trusted, bounded evidence and render a dry-run review. No GitHub writes."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import sys

import collect
import review

ACTIONS = {"opened", "synchronize", "reopened", "edited", "ready_for_review"}
MAX_PACKET = 512 * 1024


def request_from_event(event, repository):
    if repository not in {"bromanko/awesome-testing", collect.UPSTREAM}:
        raise ValueError("Unsupported repository")
    if event.get("repository", {}).get("full_name") != repository:
        raise ValueError("Event repository mismatch")
    if event.get("action") not in ACTIONS:
        raise ValueError("Unsupported PR event")
    pr = event["pull_request"]
    number = pr["number"]
    if isinstance(number, bool) or not isinstance(number, int) or number < 1 or event.get("number") != number:
        raise ValueError("Invalid PR number")
    if pr.get("state") != "open" or pr.get("draft"):
        raise ValueError("PR is closed or draft")
    if pr["base"]["repo"]["full_name"] != repository:
        raise ValueError("PR base repository mismatch")
    for sha in (pr["head"]["sha"], pr["base"]["sha"]):
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid PR commit SHA")
    return {"repository": repository, "number": number,
            "headSha": pr["head"]["sha"], "baseSha": pr["base"]["sha"]}


def fresh(request):
    if request["repository"] != collect.REPO:
        raise ValueError("Request repository mismatch")
    number = request["number"]
    if type(number) is not int or number < 1:
        raise ValueError("Invalid PR number")
    current = collect.github(f"repos/{collect.REPO}/pulls/{number}")
    return (current["state"] == "open" and not current.get("draft")
            and current["head"]["sha"] == request["headSha"]
            and current["base"]["sha"] == request["baseSha"]
            and current["base"]["repo"]["full_name"] == request["repository"])


def edit_warnings(readme, proposals):
    patch_text = readme.get("patch", "")
    added = [line[1:] for line in patch_text.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in patch_text.splitlines() if line.startswith("-") and not line.startswith("---")]
    warnings = []
    if "patch" not in readme or len(added) != readme.get("additions") or len(removed) != readme.get("deletions"):
        warnings.append("GitHub's README patch may be incomplete; manual review required.")
    represented = {entry["markdown"] for entry in proposals}
    if any(line.strip() and line not in represented and not line.startswith("#") for line in added):
        warnings.append("Added README prose or unsupported entry syntax requires human review.")
    updated = {collect.normalized(entry["url"]) for entry in proposals if entry.get("changeKind") == "update"}
    for line in removed:
        if not line.strip():
            continue
        entries = collect.entries(line)
        if not entries or collect.normalized(entries[0]["url"]) not in updated:
            warnings.append("README removals outside recognized entry updates require human review.")
            break
    return warnings


def prepare(event_file, output):
    request = request_from_event(json.loads(event_file.read_text()), collect.REPO)
    if not fresh(request):
        raise ValueError("Superseded PR event; no review is run")
    # Search the original project's history even when testing in Brian's fork.
    history = collect.pages(f"repos/{collect.UPSTREAM}/pulls?state=all")
    collect.collect(request["number"], history, request["headSha"], request["baseSha"])
    packet = json.loads((collect.EVIDENCE / f"cases/{request['number']}/packet.json").read_text())
    packet["collectionWarnings"] = []
    # A truncated/missing patch cannot prove that all additions were extracted.
    files = json.loads((collect.EVIDENCE / f"cases/{request['number']}/files.json").read_text())
    readme = next(f for f in files if f["filename"] == "README.md")
    packet["collectionWarnings"].extend(edit_warnings(readme, packet["proposals"]))
    packet["readmeDiff"] = readme.get("patch", "")
    if any(f["filename"] != "README.md" for f in files):
        packet["collectionWarnings"].append("Non-README changes require human review.")
    urls = sorted({url for item in packet["proposals"] for url in re.findall(r"\((https?://[^)]+)\)", item["markdown"])})
    if len(urls) > 20:
        raise ValueError("Too many submitted links; manual review required")
    checks = []
    for url in urls:
        result = collect.fetch_source(url, collect.EVIDENCE / f"checks/{len(checks)}.body")
        checks.append({"url": url, "status": result.get("status"),
                       "passed": result.get("status") is not None and 200 <= result["status"] < 300,
                       "error": result.get("error")})
    packet["linkCheck"] = {"implementation": "bounded public-IP-pinned HTTP(S) GET",
                           "scope": "HTTP(S) links in proposed entry lines only",
                           "results": checks, "passed": bool(checks) and all(c["passed"] for c in checks)}
    packet["allowedEvidenceUrls"] = sorted(review.evidence_urls(packet))
    encoded = json.dumps(packet, ensure_ascii=False, indent=2).encode()
    if len(encoded) > MAX_PACKET:
        raise ValueError("Evidence packet exceeds 512 KiB; manual review required")
    if not fresh(request):
        raise ValueError("PR changed during collection; no review is run")
    output.mkdir(parents=True, exist_ok=True)
    (output / "packet.json").write_bytes(encoded + b"\n")
    collect.write_json(output / "request.json", request)
    print(f"Prepared PR #{request['number']} at {request['headSha']}")


def render(packet, raw, current):
    # UM schema-validates the selected JSON export. Fail closed on malformed fixtures too.
    if raw.get("decision") not in {"approve", "request_changes", "reject"} or type(raw.get("humanReview")) is not bool:
        raise ValueError("Invalid decision export")
    decision = review.guard(packet, raw)
    if not current:
        decision["humanReview"] = True
        decision["guardReasons"].append("PR changed, closed, or became draft after collection; this preview is stale.")
    plan = review.action_plan(packet, decision, "open" if current else "stale")
    comment = html.escape(decision["contributorComment"])
    body = (f"# PR #{packet['pullRequest']['number']} dry-run preview\n\n"
            f"Head: `{packet['pullRequest']['headSha']}`\n\n"
            f"Decision: **{decision['decision']}**\n\n"
            f"Human review required: **{decision['humanReview']}**\n\n"
            "No comment, review, approval, closure, or merge was submitted.\n\n"
            f"{html.escape(decision.get('summary', ''))}\n\n"
            "## Proposed contributor comment (untrusted model output)\n\n"
            f"{comment}\n\n## Guard reasons\n\n"
            + "\n".join("- " + html.escape(reason) for reason in decision["guardReasons"]) + "\n")
    return decision, plan, body


def finish(input_dir, decision_file, output, offline=False):
    packet = json.loads((input_dir / "packet.json").read_text())
    request = json.loads((input_dir / "request.json").read_text())
    if (packet["repository"] != request["repository"] or packet["pullRequest"]["number"] != request["number"]
            or packet["pullRequest"]["headSha"] != request["headSha"]
            or packet["snapshot"]["baseSha"] != request["baseSha"]):
        raise ValueError("Evidence/request identity mismatch")
    if decision_file.stat().st_size > 65536:
        raise ValueError("Oversized decision export")
    current = False if offline else fresh(request)
    raw = json.loads(decision_file.read_text())
    decision, plan, body = render(packet, raw, current)
    output.mkdir(parents=True, exist_ok=True)
    for filename, value in (("request.json", request), ("decision.json", decision), ("action-plan.json", plan)):
        collect.write_json(output / filename, value)
    (output / "review.md").write_text(body)
    print(f"Dry-run report ready; humanReview={decision['humanReview']}; externalChangesPerformed=0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pre = commands.add_parser("prepare")
    pre.add_argument("--event-file", type=Path, required=True)
    pre.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check-current")
    check.add_argument("--input-dir", type=Path, required=True)
    post = commands.add_parser("finish")
    post.add_argument("--input-dir", type=Path, required=True)
    post.add_argument("--decision-file", type=Path, required=True)
    post.add_argument("--output", type=Path, required=True)
    post.add_argument("--offline", action="store_true", help="Always mark the report stale; test only")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.event_file, args.output)
    elif args.command == "check-current":
        if not fresh(json.loads((args.input_dir / "request.json").read_text())):
            raise ValueError("Superseded PR evidence; no model call is run")
    else:
        finish(args.input_dir, args.decision_file, args.output, args.offline)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError) as error:
        sys.exit(f"Review blocked: {error}")

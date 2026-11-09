#!/usr/bin/env python3
"""Prepare trusted, bounded evidence and render a dry-run review. No GitHub writes."""
import argparse
import html
import json
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


def current_pr(request):
    if request["repository"] != collect.REPO:
        raise ValueError("Request repository mismatch")
    number = request["number"]
    if type(number) is not int or number < 1:
        raise ValueError("Invalid PR number")
    current = collect.github(f"repos/{collect.REPO}/pulls/{number}")
    matches = (current["state"] == "open" and not current.get("draft")
            and current["head"]["sha"] == request["headSha"]
            and current["base"]["sha"] == request["baseSha"]
            and current["base"]["repo"]["full_name"] == request["repository"])
    return current if matches else None


def prepare(event_file, output):
    request = request_from_event(json.loads(event_file.read_text()), collect.REPO)
    pr = current_pr(request)
    if pr is None:
        raise ValueError("Superseded PR event; no review is run")
    packet = collect.collect(pr)
    encoded = json.dumps(packet, ensure_ascii=False, indent=2).encode()
    if len(encoded) > MAX_PACKET:
        raise ValueError("Evidence packet exceeds 512 KiB; manual review required")
    if current_pr(request) is None:
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
    labels = {"approve": "Approve", "request_changes": "Request changes", "reject": "Decline"}
    body = (f"# Review of PR #{packet['pullRequest']['number']}\n\n"
            f"**Recommendation: {labels[decision['decision']]}**\n\n"
            f"{html.escape(decision.get('summary', ''))}\n\n")
    research = decision["research"]
    questions = list(decision["guardReasons"])
    limitations = research.get("limitations", [])
    if limitations:
        questions = [q for q in questions if q != "The agent reports unresolved research limitations."]
        questions.extend(limitations)
    if decision["humanReview"] and not questions:
        questions.append("The reviewer flagged this recommendation for a closer look.")
    if questions:
        body += "## Needs your judgment\n\n" + "\n".join(
            "- " + html.escape(q) for q in dict.fromkeys(questions)) + "\n\n"
    body += "## Suggested response\n\n" + html.escape(decision["contributorComment"]) + "\n\n"
    investigation = [research.get("historySearch"), research.get("coverageComparison")]
    if any(investigation):
        body += "## Investigation\n\n" + "\n\n".join(
            html.escape(text) for text in investigation if text) + "\n"
    return decision, body


def finish(input_dir, decision_file, output, offline=False):
    packet = json.loads((input_dir / "packet.json").read_text())
    request = json.loads((input_dir / "request.json").read_text())
    if (packet["repository"] != request["repository"] or packet["pullRequest"]["number"] != request["number"]
            or packet["pullRequest"]["headSha"] != request["headSha"]
            or packet["snapshot"]["baseSha"] != request["baseSha"]):
        raise ValueError("Evidence/request identity mismatch")
    if decision_file.stat().st_size > 65536:
        raise ValueError("Oversized decision export")
    current = False if offline else current_pr(request) is not None
    raw = json.loads(decision_file.read_text())
    decision, body = render(packet, raw, current)
    output.mkdir(parents=True, exist_ok=True)
    collect.write_json(output / "decision.json", decision)
    (output / "review.md").write_text(body)
    print(f"Dry-run report ready; humanReview={decision['humanReview']}; externalChangesPerformed=0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pre = commands.add_parser("prepare")
    pre.add_argument("--event-file", type=Path, required=True)
    pre.add_argument("--output", type=Path, required=True)
    post = commands.add_parser("finish")
    post.add_argument("--input-dir", type=Path, required=True)
    post.add_argument("--decision-file", type=Path, required=True)
    post.add_argument("--output", type=Path, required=True)
    post.add_argument("--offline", action="store_true", help="Always mark the report stale; test only")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.event_file, args.output)
    else:
        finish(args.input_dir, args.decision_file, args.output, args.offline)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError) as error:
        sys.exit(f"Review blocked: {error}")

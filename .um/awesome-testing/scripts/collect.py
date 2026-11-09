#!/usr/bin/env python3
"""Retain public, read-only evidence for TheJambo/awesome-testing PRs."""

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit

from public_http import destination, fetch

UPSTREAM = "TheJambo/awesome-testing"
REPO = os.environ.get("GITHUB_REPOSITORY", "bromanko/awesome-testing")
if REPO not in {"bromanko/awesome-testing", UPSTREAM}:
    raise ValueError("Unsupported repository")
ROOT = Path(__file__).resolve().parents[1]
ENTRY = re.compile(r"^\s*[-*]\s+\[([^\]]+)\]\((https?://[^\s)]+)\)\s*-?\s*(.*)$")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def github(endpoint: str) -> object:
    # This collector never accepts an HTTP method or arbitrary executable.
    if not endpoint.startswith((f"repos/{REPO}/", f"repos/{UPSTREAM}/")):
        raise ValueError("GitHub API destination is outside the review repositories")
    result = subprocess.run(["gh", "api", "--hostname", "github.com", "--method", "GET", endpoint],
                            text=True, capture_output=True, timeout=60, check=True)
    return json.loads(result.stdout)


def pages(endpoint: str) -> list:
    rows = []
    for page in range(1, 30):
        separator = "&" if "?" in endpoint else "?"
        batch = github(f"{endpoint}{separator}per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError(f"Expected a paginated list: {endpoint}")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise ValueError(f"Pagination limit reached: {endpoint}")


def entries(markdown: str) -> list[dict]:
    section = ""
    result = []
    for number, line in enumerate(markdown.splitlines(), 1):
        if line.startswith("#"):
            section = line.lstrip("# ").strip()
        match = ENTRY.match(line)
        if match:
            result.append(dict(name=match[1], url=match[2], description=match[3],
                               category=section, line=number, markdown=line))
    return result


def normalized(url: str) -> str:
    parsed = urlsplit(url)
    return (parsed.hostname or "").lower().removeprefix("www.") + parsed.path.rstrip("/").lower()


def historical_matches(proposals: list[dict], history: list[dict], number: int, cutoff: str) -> list[dict]:
    candidates = []
    for entry in proposals:
        primary = normalized(entry["url"])
        name = re.sub(r"[^a-z0-9]", "", entry["name"].lower())
        name_pattern = re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(re.escape(char) for char in name) + r"(?![a-z0-9])")
        words = set(re.findall(r"[a-z0-9]+", entry["name"].lower())) - {
            "test", "testing", "tool", "tools", "app", "qa", "software", "free"}
        for other in history:
            if other["number"] == number or other["created_at"] >= cutoff:
                continue
            haystack = (other["title"] + " " + (other.get("body") or "")).lower()
            urls = re.findall(r"https?://[^\s)>]+", haystack)
            token_match = len(words.intersection(re.findall(r"[a-z0-9]+", haystack))) >= 2
            if (len(name) >= 4 and name_pattern.search(haystack)) or token_match or any(normalized(u) == primary for u in urls):
                candidates.append(dict(number=other["number"], title=other["title"],
                                       url=other["html_url"], createdAt=other["created_at"],
                                       excerpt=(other.get("body") or "")[:1600]))
    return list({item["number"]: item for item in candidates}.values())


def public_url(url: str) -> None:
    destination(url)


def fetch_source(url: str) -> dict:
    result = dict(url=url, fetchedAt=datetime.now(timezone.utc).isoformat())
    try:
        response = dict(fetch(url))
        content = response.pop("content")
        result.update(response)
        result.update(sha256=hashlib.sha256(content).hexdigest())
        text = content.decode("utf-8", errors="replace")
        text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        result["excerpt"] = re.sub(r"\s+", " ", text).strip()[:18000]
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        result.update(status=getattr(error, "code", None), error=str(error)[:300], excerpt="")
    return result


def readme_at(ref: str, filename: str = "README.md") -> str:
    blob = github(f"repos/{REPO}/contents/{quote(filename)}?ref={quote(ref)}")
    return base64.b64decode(blob["content"]).decode("utf-8")


def public_github_readme(repository: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid public repository")
    response = fetch(f"https://api.github.com/repos/{repository}/readme", limit=1024 * 1024)
    if response["status"] != 200 or response["truncated"]:
        raise ValueError("Public README unavailable or oversized")
    return json.loads(response["content"])


def prior_context(candidates: list[dict], history: list[dict], cutoff: str) -> list[dict]:
    indexed = {row["number"]: row for row in history}
    for candidate in candidates[:5]:
        number = candidate["number"]
        files = pages(f"repos/{UPSTREAM}/pulls/{number}/files")
        comments = pages(f"repos/{UPSTREAM}/issues/{number}/comments")
        changed = []
        for file in files:
            if file["filename"].lower() == "readme.md":
                added = "\n".join(line[1:] for line in file.get("patch", "").splitlines()
                                  if line.startswith("+") and not line.startswith("+++"))
                changed.extend(entries(added))
        candidate["proposedEntries"] = changed
        candidate["ownerComments"] = [dict(text=row["body"], url=row["html_url"], createdAt=row["created_at"])
                                      for row in comments
                                      if row.get("author_association") == "OWNER" and row["created_at"] < cutoff
                                      and row.get("updated_at", row["created_at"]) < cutoff]
        previous = indexed[number]
        candidate["statusAtCutoff"] = ("merged" if previous["merged_at"] else "closed") if previous.get("closed_at") and previous["closed_at"] < cutoff else "open"
        candidate["diffMayContainLaterEdits"] = previous["updated_at"] > cutoff
    return candidates


def collect(pr: dict, history: list[dict]) -> tuple[dict, list[dict]]:
    number = pr["number"]
    files = pages(f"repos/{REPO}/pulls/{number}/files")
    if len(files) > 50:
        raise ValueError("Too many changed files; manual review required")
    readme = next((f for f in files if f["filename"] == "README.md"), None)
    if readme is None:
        raise ValueError("No README change; manual review required")
    head_text = readme_at(pr["head"]["sha"], readme["filename"])
    base_ref = pr["base"]["sha"]
    base_text = readme_at(base_ref, readme.get("previous_filename", readme["filename"]))
    contribution_blob = github(f"repos/{REPO}/contents/CONTRIBUTING.md?ref={quote(base_ref)}")
    rules = base64.b64decode(contribution_blob["content"]).decode()
    added = [line[1:] for line in readme.get("patch", "").splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    proposals = [entry for entry in entries(head_text) if entry["markdown"] in added]
    if len(proposals) > 10 or len(head_text) > 1024 * 1024 or len(base_text) > 1024 * 1024:
        raise ValueError("Evidence size limit exceeded; manual review required")
    existing = entries(base_text)
    sources = []
    for entry in proposals:
        source = fetch_source(entry["url"])
        source["entryUrl"] = entry["url"]
        sources.append(source)
        parsed = urlsplit(entry["url"])
        parts = parsed.path.strip("/").split("/")
        if parsed.hostname == "github.com" and len(parts) >= 2:
            repo_name = "/".join(parts[:2])
            try:
                blob = public_github_readme(repo_name)
                content = base64.b64decode(blob["content"]).decode("utf-8", errors="replace")
                sources.append(dict(url=blob["html_url"], entryUrl=entry["url"], status=200,
                                    excerpt=content[:22000], sha256=hashlib.sha256(content.encode()).hexdigest()))
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError):
                pass
    cutoff = pr["closed_at"] or datetime.now(timezone.utc).isoformat()
    removed = [line[1:] for line in readme.get("patch", "").splitlines()
               if line.startswith("-") and not line.startswith("---")]
    for entry in proposals:
        primary = normalized(entry["url"])
        name = re.sub(r"[^a-z0-9]", "", entry["name"].lower())
        entry["changeKind"] = "update" if any(normalized(e["url"]) == primary and e["markdown"] in removed for e in existing) else "addition"
        entry["existingMatches"] = [e for e in existing if normalized(e["url"]) == primary
                                    or re.sub(r"[^a-z0-9]", "", e["name"].lower()) == name]
    candidates = prior_context(historical_matches(proposals, history, number if REPO == UPSTREAM else -1, cutoff), history, cutoff)
    precedent_path = ROOT / "evidence/maintainer-precedents.json"
    current_precedents = [p for p in json.loads(precedent_path.read_text())
                          if REPO != UPSTREAM or p["pullRequest"] != number] if precedent_path.exists() else []
    precedents = [p for p in current_precedents if p["createdAt"] < cutoff]
    findings = []
    additions = sum(item["changeKind"] == "addition" for item in proposals)
    if additions > 1:
        findings.append("More than one new suggestion; CONTRIBUTING requires one per PR.")
    for entry in proposals:
        if not entry["description"].rstrip().endswith("."):
            findings.append(f"{entry['name']}: description does not end with a period.")
    if any(line != line.rstrip() for line in added):
        findings.append("The changed README lines contain trailing whitespace.")
    if any(f["filename"].lower() != "readme.md" for f in files):
        findings.append("Non-README changes require human review; no submitted code is executed.")
    if not proposals or "patch" not in readme:
        findings.append("No complete proposed entry could be extracted; human review is required.")
    base_url = f"https://github.com/{REPO}/blob/{base_ref}"
    packet = dict(repository=REPO, pullRequest=dict(number=number, title=pr["title"],
                  body=pr.get("body") or "", url=pr["html_url"], headSha=pr["head"]["sha"]),
                  snapshot=dict(baseSha=base_ref, reviewCutoff=cutoff,
                                caveat="Final retained PR head; current official sources; target discussion/outcome withheld; earlier maintainer precedents may be included."),
                  rules=dict(text=rules, url=f"{base_url}/CONTRIBUTING.md",
                             foreword=base_text[:base_text.find("## Contents")] if "## Contents" in base_text else base_text[:3000],
                             readmeUrl=f"{base_url}/{readme['filename']}"),
                  categories=[line.lstrip("# ") for line in head_text.splitlines() if line.startswith("#")],
                  proposals=proposals, deterministicFindings=findings, priorSubmissions=candidates,
                  categoryEntries=[entry for entry in existing if entry["category"] in {p["category"] for p in proposals}],
                  maintainerPrecedents=precedents,
                  currentCuratorPolicyEvidence=current_precedents,
                  reviewPolicyVersion="2026-11-06-curator-calibration; current policy, not an as-of policy reconstruction",
                  historicalSearch=dict(pullRequestsScanned=len(history), matchingPriorSubmissions=len(candidates),
                                        cutoff=cutoff, targetOutcomeIncluded=False),
                  sources=sources)
    print(f"Collected PR #{number}: {len(proposals)} entries, {len(candidates)} prior submissions", flush=True)
    return packet, files

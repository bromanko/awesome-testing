#!/usr/bin/env python3
"""Retain public, read-only evidence for TheJambo/awesome-testing PRs."""

import base64
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote


UPSTREAM = "TheJambo/awesome-testing"
REPO = os.environ.get("GITHUB_REPOSITORY", "bromanko/awesome-testing")
if REPO not in {"bromanko/awesome-testing", UPSTREAM}:
    raise ValueError("Unsupported repository")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def github(endpoint: str) -> object:
    if not endpoint.startswith((f"repos/{REPO}/", f"repos/{UPSTREAM}/")):
        raise ValueError("GitHub API destination is outside the review repositories")
    request = Request("https://api.github.com/" + endpoint,
                      headers={"Accept": "application/vnd.github+json", "User-Agent": "awesome-testing-review"})
    token = os.environ.get("REVIEW_GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    with urlopen(request, timeout=60) as response:
        return json.load(response)


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


def readme_at(ref: str, filename: str = "README.md") -> str:
    blob = github(f"repos/{REPO}/contents/{quote(filename)}?ref={quote(ref)}")
    return base64.b64decode(blob["content"]).decode("utf-8")


def readme_entries(text):
    entries, headings = [], []
    fence = None
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), text, flags=re.S)
    link = re.compile(
        r'^ {0,3}[-+*]\s+\[(?P<name>(?:\\.|[^\]\\])+)\]'
        r'\((?:<(?P<angle>https?://[^<>\s]+)>|'
        r'(?P<url>https?://(?:[^()<>\s]|\([^()\s]*\))+))'
        r'(?:\s+"[^"\n]*")?\)')
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading[1])
            headings = [(depth, title) for depth, title in headings if depth < level]
            headings.append((level, re.sub(r"\s+#+$", "", heading[2])))
        match = link.match(line)
        if match:
            entries.append(dict(name=match["name"], url=match["angle"] or match["url"],
                                category=" > ".join(title for depth, title in headings if depth > 1),
                                line=number, text=line))
    return entries


def readme_changes(base, head, listed=None):
    """Compare the list's one-line inline HTTP(S) entries, preserving exact URLs."""
    before, after = readme_entries(base), readme_entries(head)
    existing = readme_entries(listed) if listed is not None else before
    remaining, changed = list(before), []
    for entry in after:
        same = next((old for old in remaining if all(old[k] == entry[k] for k in ("url", "text", "category"))), None)
        if same is not None:
            remaining.remove(same)
        else:
            changed.append(entry)
    changed.sort(key=lambda entry: not any(item["url"] == entry["url"] and item["category"] == entry["category"] for item in remaining))
    changes = []
    for entry in changed:
        candidates = [item for item in remaining if item["url"] == entry["url"]]
        old = next((item for item in candidates if item["category"] == entry["category"]), candidates[0] if candidates else None)
        if old is not None:
            remaining.remove(old)
            kind = "moved" if old["category"] != entry["category"] else "edited"
        else:
            kind = "added"
        changes.append(dict(kind=kind, before=old, after=entry,
                            existingMatches=[item for item in existing if item["url"] == entry["url"]] if old is None else []))
    changes.extend(dict(kind="removed", before=old, after=None, existingMatches=[]) for old in remaining)
    return changes


def assemble(pr, files, base_readme, head_readme, rules, base_sha=None, diff_base_readme=None, diff_base_sha=None):
    """Bind the full submitted edit to immutable repository context."""
    base_sha = base_sha or pr["base"]["sha"]
    warnings = []
    for item in files:
        patch = item.get("patch", "")
        additions = sum(line.startswith("+") and not line.startswith("+++") for line in patch.splitlines())
        deletions = sum(line.startswith("-") and not line.startswith("---") for line in patch.splitlines())
        if "patch" not in item or additions != item["additions"] or deletions != item["deletions"]:
            warnings.append(f"Incomplete patch for {item['filename']}; inspect the pinned file versions or request human review.")
    repo = pr["base"]["repo"]["full_name"]
    base_url = f"https://github.com/{repo}/blob/{base_sha}"
    return dict(repository=repo,
                pullRequest=dict(number=pr["number"], title=pr["title"], body=pr.get("body") or "",
                                 url=pr["html_url"], headSha=pr["head"]["sha"]),
                snapshot=dict(baseSha=base_sha, diffBaseSha=diff_base_sha or base_sha),
                rules=dict(text=rules, url=f"{base_url}/CONTRIBUTING.md", readmeUrl=f"{base_url}/README.md"),
                baseReadme=base_readme, headReadme=head_readme,
                readmeChanges=readme_changes(base_readme if diff_base_readme is None else diff_base_readme, head_readme, base_readme),
                changes=[{key: item[key] for key in ("filename", "previous_filename", "status", "additions", "deletions", "patch") if key in item}
                         for item in files], collectionWarnings=warnings)


def collect(pr):
    number = pr["number"]
    files = pages(f"repos/{REPO}/pulls/{number}/files")
    if len(files) > 50:
        raise ValueError("Too many changed files; manual review required")
    base_sha, head_sha = pr["base"]["sha"], pr["head"]["sha"]
    diff_base_sha = github(f"repos/{REPO}/compare/{base_sha}...{head_sha}")["merge_base_commit"]["sha"]
    base = readme_at(base_sha)
    diff_base = base if diff_base_sha == base_sha else readme_at(diff_base_sha)
    return assemble(pr, files, base, readme_at(head_sha), readme_at(base_sha, "CONTRIBUTING.md"),
                    diff_base_readme=diff_base, diff_base_sha=diff_base_sha)

#!/usr/bin/env python3
"""Retain public, read-only evidence for TheJambo/awesome-testing PRs."""

import base64
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote


UPSTREAM = "TheJambo/awesome-testing"
REPO = os.environ.get("GITHUB_REPOSITORY", "bromanko/awesome-testing")
if REPO not in {"bromanko/awesome-testing", UPSTREAM}:
    raise ValueError("Unsupported repository")


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


def readme_at(ref: str, filename: str = "README.md") -> str:
    blob = github(f"repos/{REPO}/contents/{quote(filename)}?ref={quote(ref)}")
    return base64.b64decode(blob["content"]).decode("utf-8")


def assemble(pr, files, base_readme, head_readme, rules, base_sha=None):
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
                snapshot=dict(baseSha=base_sha),
                rules=dict(text=rules, url=f"{base_url}/CONTRIBUTING.md", readmeUrl=f"{base_url}/README.md"),
                baseReadme=base_readme, headReadme=head_readme,
                changes=[{key: item[key] for key in ("filename", "previous_filename", "status", "additions", "deletions", "patch") if key in item}
                         for item in files], collectionWarnings=warnings)


def collect(pr):
    number = pr["number"]
    files = pages(f"repos/{REPO}/pulls/{number}/files")
    if len(files) > 50:
        raise ValueError("Too many changed files; manual review required")
    return assemble(pr, files, readme_at(pr["base"]["sha"]),
                    readme_at(pr["head"]["sha"]), readme_at(pr["base"]["sha"], "CONTRIBUTING.md"))

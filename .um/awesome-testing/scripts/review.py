"""Consistency checks on an agent's research report; these do not verify its claims."""
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit


def public_citation(url):
    try:
        parsed = urlsplit(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def guard(packet, raw):
    decision = deepcopy(raw)
    reasons = list(packet.get("collectionWarnings", []))
    for change in packet.get("readmeChanges", []):
        if change["kind"] == "added" and change["existingMatches"]:
            entry = change["after"]
            locations = "; ".join(f"{match['category'] or 'uncategorized'} (base README line {match['line']})"
                                  for match in change["existingMatches"])
            reasons.append(f"Added entry \"{entry['name']}\" uses a URL already listed under {locations}: {entry['url']}. Check whether another listing is intended.")
    research = decision.get("research", {})
    sources = research.get("sources", [])
    known = {packet["pullRequest"]["url"], packet["rules"]["url"], packet["rules"]["readmeUrl"]}
    known.update(re.findall(r'https?://[^\s"<>\\)]+', json.dumps(packet)))
    known.update(source["url"] for source in sources if source.get("status") == "accessed" and public_citation(source.get("url", "")))
    citations = {url for finding in decision["findings"] for url in finding["evidence"]}
    citations.update(re.findall(r"\]\((https?://[^)]+)\)", decision["contributorComment"]))
    if any(not public_citation(url) for url in citations) or citations - known:
        reasons.append("A decision citation has no accessed source in the research record or pinned context.")
    if not research.get("historySearch") or not research.get("coverageComparison"):
        reasons.append("The report does not explain the history search and coverage comparison.")
    if not any(source.get("status") == "accessed" for source in sources):
        reasons.append("The agent reports no accessed research sources.")
    if research.get("limitations"):
        reasons.append("The agent reports unresolved research limitations.")
    if decision["decision"] == "approve" and any(f["severity"] == "blocking" for f in decision["findings"]):
        reasons.append("Approval conflicts with a blocking finding.")
    if decision.get("confidence") != "high" and any(f.get("kind") == "duplicate" and f["severity"] == "blocking" for f in decision["findings"]):
        reasons.append("A blocking duplicate/coverage-overlap judgment needs a maintainer to resolve the uncertain comparison.")
    if reasons:
        decision["humanReview"] = True
    decision["guardReasons"] = reasons
    return decision

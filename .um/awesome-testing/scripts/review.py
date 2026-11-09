"""Pure decision guards. Never performs I/O."""
import json
import re

def evidence_urls(packet: dict) -> set[str]:
    known = {packet["pullRequest"]["url"], packet["rules"]["url"], packet["rules"]["readmeUrl"]}
    known.update(item["url"] for item in packet["priorSubmissions"])
    for item in packet["priorSubmissions"]:
        known.update(entry["url"] for entry in item.get("proposedEntries", []))
        known.update(comment["url"] for comment in item.get("ownerComments", []))
    known.update(item["url"] for item in packet.get("maintainerPrecedents", []))
    known.update(item["url"] for item in packet.get("currentCuratorPolicyEvidence", []))
    known.update(item["url"] for item in packet.get("categoryEntries", []))
    for item in packet["proposals"]:
        known.add(item["url"])
        known.update(match["url"] for match in item["existingMatches"])
    for source in packet["sources"]:
        known.update(source.get(key) for key in ("url", "finalUrl") if source.get(key))
    known.update(row["url"] for row in packet["linkCheck"].get("results", []))
    return known


def guard(packet: dict, decision: dict) -> dict:
    decision = json.loads(json.dumps(decision))
    known = evidence_urls(packet)
    citations = {url for finding in decision["findings"] for url in finding["evidence"]}
    citations.update(re.findall(r"\]\((https?://[^)]+)\)", decision["contributorComment"]))
    reasons = []
    if citations - known:
        reasons.append("The model cited a URL absent from the evidence packet.")
    if not packet["proposals"]:
        reasons.append("No complete proposed entry was extracted.")
    if packet.get("collectionWarnings"):
        reasons.extend(packet["collectionWarnings"])
    if not packet["linkCheck"].get("passed"):
        reasons.append("The existing link check did not pass completely.")
    for proposal in packet["proposals"]:
        if not any(source.get("entryUrl") == proposal["url"] and source.get("excerpt")
                   and source.get("status") == 200 for source in packet["sources"]):
            reasons.append(f"No usable official-source evidence for {proposal['name']}.")
    if decision["decision"] == "approve" and packet["deterministicFindings"]:
        reasons.append("Approval conflicts with a deterministic contribution-rule finding.")
    if decision["decision"] == "approve" and any(f["severity"] == "blocking" for f in decision["findings"]):
        reasons.append("Approval conflicts with a blocking model finding.")
    if decision.get("confidence") != "high" and any(
            finding.get("kind") == "duplicate" and finding.get("severity") == "blocking"
            for finding in decision["findings"]):
        reasons.append("A blocking duplicate/coverage-overlap judgment is not high confidence; "
                       "a maintainer must resolve the comparison before any action.")
    if reasons:
        decision["humanReview"] = True
    decision["guardReasons"] = reasons
    return decision

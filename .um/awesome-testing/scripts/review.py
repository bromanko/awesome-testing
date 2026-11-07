"""Pure decision guards and hypothetical action plans. Never performs I/O."""
import json
import re
from collect import REPO

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


def action_plan(packet: dict, decision: dict, current_state: str) -> dict:
    # Keep the action boundary safe even when a caller passes a raw model result.
    decision = guard(packet, decision)
    pr = packet["pullRequest"]
    marker = f"<!-- awesome-testing-review:{pr['headSha']} -->"
    body = decision["contributorComment"].strip() + "\n\n" + marker
    repository = packet.get("repository", REPO)
    prefix = f"https://api.github.com/repos/{repository}"
    requests = []
    if not decision["humanReview"]:
        if decision["decision"] in {"approve", "request_changes"}:
            requests.append(dict(method="POST", url=f"{prefix}/pulls/{pr['number']}/reviews",
                                 json=dict(commit_id=pr["headSha"], body=body,
                                           event="APPROVE" if decision["decision"] == "approve" else "REQUEST_CHANGES")))
        else:
            requests.extend([
                dict(method="POST", url=f"{prefix}/issues/{pr['number']}/comments", json=dict(body=body)),
                dict(method="PATCH", url=f"{prefix}/pulls/{pr['number']}", json=dict(state="closed")),
            ])
    return dict(mode="dry-run", repository=repository, pullRequest=pr["number"], headSha=pr["headSha"],
                decision=decision["decision"], humanReview=decision["humanReview"],
                currentState=current_state, externalChangesPerformed=0,
                hypotheticalRequests=requests,
                preflightReads=[f"{prefix}/pulls/{pr['number']}",
                                f"{prefix}/pulls/{pr['number']}/reviews",
                                f"{prefix}/issues/{pr['number']}/comments"],
                requiredPreconditions=["PR is open and not draft", "head SHA still matches this exact review",
                                       "No existing review/comment for this head SHA and marker",
                                       "Dedicated bot has repository write permission and is not PR author",
                                       "All relevant check results remain current for the same head"],
                wouldExecuteNow=False,
                executionBlockedBecause="Spike deliberately has no GitHub write executor; full-auto is design only.",
                mergePolicy="Approval submits an APPROVE review only; merging is outside this spike's design.")

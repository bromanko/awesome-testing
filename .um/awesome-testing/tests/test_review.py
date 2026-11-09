"""Offline regressions for the dry-run, stale-head, URL and credential boundaries."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci
import collect
import review


def packet():
    return dict(repository=collect.REPO, pullRequest=dict(number=7, url=f"https://github.com/{collect.REPO}/pull/7", headSha="a" * 40),
                snapshot=dict(baseSha="b" * 40), rules=dict(url="https://example.com/rules", readmeUrl="https://example.com/list"),
                baseReadme="# Tools", headReadme="# Tools\n- [Example](https://example.com/tool) - Tool.",
                changes=[], collectionWarnings=[])


def decision():
    return dict(decision="approve", humanReview=False, confidence="high", summary="Relevant tool.",
                category="Tools", proposedEntry=None, findings=[], contributorComment="Looks relevant.",
                research=dict(sources=[dict(url="https://example.com/tool",status="accessed",observation="Official documentation describes the testing use case.")],
                              historySearch="Searched the resource name and URL; no prior submission found.",
                              coverageComparison="Compared the closest listed tool; this adds a distinct capability.",limitations=[]))


def event():
    return dict(action="synchronize", number=7, repository=dict(full_name=collect.REPO),
                pull_request=dict(number=7, state="open", draft=False,
                                  head=dict(sha="a" * 40), base=dict(sha="b" * 40, repo=dict(full_name=collect.REPO))))


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.packet = packet()
        self.decision = decision()


    def test_agent_discovered_source_is_accepted(self):
        self.decision["findings"] = [dict(evidence=["https://example.com/tool"], severity="advisory")]
        self.assertFalse(review.guard(self.packet, self.decision)["humanReview"])

    def test_readme_link_can_be_cited_as_pinned_context(self):
        self.packet["baseReadme"] = "- [Existing](https://existing.example/tool) - Comparator."
        self.decision["findings"] = [dict(evidence=["https://existing.example/tool"], severity="advisory")]
        self.assertFalse(review.guard(self.packet, self.decision)["humanReview"])

    def test_unavailable_source_cannot_support_a_finding(self):
        self.decision["research"]["sources"][0]["status"] = "unavailable"
        self.decision["findings"] = [dict(evidence=["https://example.com/tool"], severity="advisory")]
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_research_limitations_require_human_review(self):
        self.decision["research"]["limitations"] = ["Could not establish the overlap."]
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_invented_citation_blocks(self):
        self.decision["findings"] = [dict(evidence=["https://invented.example/claim"], severity="advisory")]
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_invented_comment_link_blocks(self):
        self.decision["contributorComment"] = "See [fake](https://invented.example/claim)."
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])


    def duplicate_finding(self, severity="blocking"):
        return dict(kind="duplicate", severity=severity,
                    message="The primary testing need may already be covered.",
                    evidence=[self.packet["rules"]["readmeUrl"]])

    def test_uncertain_blocking_overlap_requires_maintainer_for_every_decision(self):
        for confidence in ("medium", "low", None, "missing"):
            for recommendation in ("approve", "request_changes", "reject"):
                with self.subTest(confidence=confidence, decision=recommendation):
                    raw = dict(self.decision, decision=recommendation, confidence=confidence,
                               findings=[self.duplicate_finding()])
                    if confidence == "missing":
                        raw.pop("confidence")
                    original = json.loads(json.dumps(raw))
                    guarded = review.guard(self.packet, raw)
                    self.assertTrue(guarded["humanReview"])
                    self.assertEqual(guarded["decision"], recommendation)
                    self.assertTrue(any("coverage-overlap" in reason for reason in guarded["guardReasons"]))
                    self.assertEqual(raw, original)


    def test_high_confidence_duplicate_keeps_existing_rejection_preview(self):
        raw = dict(self.decision, decision="reject", findings=[self.duplicate_finding()])
        guarded = review.guard(self.packet, raw)
        self.assertFalse(guarded["humanReview"])
        self.assertEqual(guarded["guardReasons"], [])

    def test_nonblocking_duplicate_and_unrelated_fixes_are_not_newly_blocked(self):
        for finding in (self.duplicate_finding("advisory"),
                        dict(kind="rule", severity="blocking", message="Add a period.",
                             evidence=[self.packet["rules"]["url"]])):
            with self.subTest(finding=finding):
                raw = dict(self.decision, decision="request_changes", confidence="medium", findings=[finding])
                guarded = review.guard(self.packet, raw)
                self.assertFalse(guarded["humanReview"])

    def test_guard_is_idempotent_and_preserves_model_human_review(self):
        raw = dict(self.decision, decision="reject", humanReview=True, confidence="medium", findings=[self.duplicate_finding()])
        guarded = review.guard(self.packet, raw)
        self.assertTrue(guarded["humanReview"])
        self.assertEqual(review.guard(self.packet, guarded), guarded)
        self.assertEqual(len(guarded["guardReasons"]), 1)

    def test_ci_report_routes_uncertain_overlap_to_maintainer(self):
        for recommendation in ("approve", "request_changes", "reject"):
            with self.subTest(decision=recommendation):
                raw = dict(self.decision, decision=recommendation, confidence="medium",
                           findings=[self.duplicate_finding()])
                original = copy.deepcopy(raw)
                guarded, report = ci.render(self.packet, raw, True)
                self.assertTrue(guarded["humanReview"])
                self.assertEqual(guarded["decision"], recommendation)
                self.assertIn("## Needs your judgment", report)
                self.assertIn("coverage-overlap", report)
                self.assertEqual(raw, original)

    def test_report_applies_existing_evidence_guards(self):
        cases = [
            (dict(self.packet, collectionWarnings=["Incomplete patch"]), self.decision),
            (self.packet, dict(self.decision, contributorComment="See [fake](https://invented.example/claim).")),
            (self.packet, dict(self.decision, findings=[self.duplicate_finding()])),
            (self.packet, dict(self.decision, research={})),
        ]
        for evidence, raw in cases:
            with self.subTest(packet=evidence, decision=raw):
                guarded, report = ci.render(evidence, raw, True)
                self.assertTrue(guarded["humanReview"])

    def test_partial_patch_blocks_every_decision(self):
        self.packet["collectionWarnings"] = ["Incomplete patch"]
        for value in ("approve", "request_changes", "reject"):
            self.assertTrue(review.guard(self.packet, dict(self.decision, decision=value))["humanReview"])

    def test_stale_report_requires_human_review(self):
        guarded, report = ci.render(self.packet, self.decision, False)
        self.assertTrue(guarded["humanReview"])
        self.assertIn("stale", report)

    def test_render_does_not_mutate_model_output(self):
        before = copy.deepcopy(self.decision)
        ci.render(self.packet, self.decision, False)
        self.assertEqual(before, self.decision)

    def test_html_is_escaped_in_report(self):
        self.decision["contributorComment"] = "<img src=x>"
        self.assertIn("&lt;img", ci.render(self.packet, self.decision, True)[1])

    def test_invalid_decision_rejected(self):
        with self.assertRaises(ValueError):
            ci.render(self.packet, dict(self.decision, humanReview="false"), True)

    def test_full_auto_is_not_a_command(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/ci.py"), "full-auto"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


class EventTests(unittest.TestCase):
    def test_exact_repository_head_and_base(self):
        self.assertEqual(ci.request_from_event(event(), collect.REPO),
                         dict(repository=collect.REPO, number=7, headSha="a" * 40, baseSha="b" * 40))

    def test_wrong_repository_rejected(self):
        value = event(); value["repository"]["full_name"] = "other/repo"
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_base_repository_rejected(self):
        value = event(); value["pull_request"]["base"]["repo"]["full_name"] = "other/repo"
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_unexpected_action_rejected(self):
        value = event(); value["action"] = "closed"
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_draft_rejected(self):
        value = event(); value["pull_request"]["draft"] = True
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_closed_rejected(self):
        value = event(); value["pull_request"]["state"] = "closed"
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_injection_sha_rejected(self):
        value = event(); value["pull_request"]["head"]["sha"] = "$(touch /tmp/no)"
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_bool_number_rejected(self):
        value = event(); value["pull_request"]["number"] = True
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_mismatched_number_rejected(self):
        value = event(); value["number"] = 8
        with self.assertRaises(ValueError): ci.request_from_event(value, collect.REPO)

    def test_changed_head_fails_freshness(self):
        current = event()["pull_request"]; current["head"]["sha"] = "c" * 40
        with patch.object(collect, "github", return_value=current):
            self.assertFalse(ci.current_pr(ci.request_from_event(event(), collect.REPO)))

    def test_changed_base_fails_freshness(self):
        current = event()["pull_request"]; current["base"]["sha"] = "c" * 40
        with patch.object(collect, "github", return_value=current):
            self.assertFalse(ci.current_pr(ci.request_from_event(event(), collect.REPO)))

    def test_stale_prepare_does_not_collect(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "event.json"; file.write_text(json.dumps(event()))
            with patch.object(ci, "current_pr", return_value=None), patch.object(collect, "collect") as gather:
                with self.assertRaisesRegex(ValueError, "Superseded"):
                    ci.prepare(file, Path(directory) / "input")
                gather.assert_not_called()

    def test_changed_pr_during_collection_does_not_publish_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "event.json").write_text(json.dumps(event()))
            with patch.object(ci, "current_pr", side_effect=[event()["pull_request"], None]), \
                 patch.object(collect, "collect", return_value=packet()):
                with self.assertRaisesRegex(ValueError, "changed during collection"):
                    ci.prepare(root / "event.json", root / "input")
            self.assertFalse((root / "input").exists())

    def test_changed_pr_after_model_is_reported_as_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packet.json").write_text(json.dumps(packet()))
            (root / "request.json").write_text(json.dumps(ci.request_from_event(event(), collect.REPO)))
            (root / "decision.json").write_text(json.dumps(decision()))
            with patch.object(ci, "current_pr", return_value=None):
                ci.finish(root, root / "decision.json", root / "report")
            result = json.loads((root / "report/decision.json").read_text())
            self.assertTrue(result["humanReview"])
            self.assertIn("stale", (root / "report/review.md").read_text())

    def test_mismatched_packet_identity_rejected_before_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); p = packet(); p["pullRequest"]["headSha"] = "c" * 40
            (root / "packet.json").write_text(json.dumps(p))
            (root / "request.json").write_text(json.dumps(ci.request_from_event(event(), collect.REPO)))
            with patch.object(ci, "current_pr") as api:
                with self.assertRaisesRegex(ValueError, "identity"):
                    ci.finish(root, root / "decision.json", root / "out")
                api.assert_not_called()

    def test_no_authenticated_arbitrary_api(self):
        with patch.object(collect.subprocess, "run") as run:
            with self.assertRaises(ValueError): collect.github("repos/other/private/readme")
            run.assert_not_called()


class ContextTests(unittest.TestCase):
    def context(self, changes):
        pr = event()["pull_request"]
        pr.update(title="Edit", body="Text", html_url="https://github.com/example/repo/pull/7")
        return collect.assemble(pr, changes, "old README", "new README", "rules")

    def test_preserves_removals_prose_and_non_readme_changes(self):
        changes = [dict(filename="README.md", patch="-old entry\n+new prose", additions=1, deletions=1),
                   dict(filename="other.txt", patch="+extra", additions=1, deletions=0)]
        context = self.context(changes)
        self.assertEqual(context["changes"], changes)
        self.assertEqual(context["baseReadme"], "old README")
        self.assertEqual(context["headReadme"], "new README")
        self.assertEqual(context["collectionWarnings"], [])

    def test_incomplete_patch_requires_review(self):
        context = self.context([dict(filename="README.md", patch="+one", additions=2, deletions=0)])
        self.assertTrue(review.guard(context, decision())["humanReview"])

    def test_missing_patch_requires_review(self):
        context = self.context([dict(filename="README.md", additions=1, deletions=0)])
        self.assertTrue(context["collectionWarnings"])


class PipelineTests(unittest.TestCase):
    def test_prepare_and_finish_without_network_or_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = event()
            payload["pull_request"].update(title="Example", body="$(not executed)", closed_at=None,
                                         html_url=f"https://github.com/{collect.REPO}/pull/7")
            base = "# List\n## Tools\n"
            addition = "- [Example](https://example.com/tool) - Tool."
            change = dict(filename="README.md", patch="@@ -1 +1,2 @@\n+" + addition, additions=1, deletions=0)
            def github(endpoint):
                if endpoint == f"repos/{collect.REPO}/pulls/7":
                    return copy.deepcopy(payload["pull_request"])
                if "/pulls/7/files?" in endpoint:
                    return [change]
                if "/pulls?" in endpoint:
                    return []
                if "/contents/README.md?" in endpoint:
                    text = base + addition + "\n" if "a" * 40 in endpoint else base
                    return dict(content=base64.b64encode(text.encode()).decode())
                if "/contents/CONTRIBUTING.md?" in endpoint:
                    return dict(content=base64.b64encode(b"One suggestion per PR.").decode())
                raise AssertionError(f"Unexpected API call: {endpoint}")
            (root / "event.json").write_text(json.dumps(payload))
            with patch.object(collect, "github", side_effect=github) as api:
                ci.prepare(root / "event.json", root / "input")
                data = json.loads((root / "input/packet.json").read_text())
                self.assertEqual(data["repository"], collect.REPO)
                self.assertEqual(data["baseReadme"], base)
                self.assertEqual(data["headReadme"], base + addition + "\n")
                self.assertEqual(data["collectionWarnings"], [])
                self.assertEqual(data["changes"][0]["patch"], change["patch"])
                (root / "decision.json").write_text(json.dumps(decision()))
                ci.finish(root / "input", root / "decision.json", root / "report")
                report = (root / "report/review.md").read_text()
                self.assertIn("**Recommendation: Approve**", report)
                self.assertNotIn("## Needs your judgment", report)
                self.assertEqual(sum(call.args[0] == f"repos/{collect.REPO}/pulls/7" for call in api.call_args_list), 3)
                self.assertEqual(sorted(p.name for p in root.iterdir()), ["decision.json", "event.json", "input", "report"])
                self.assertEqual(sorted(p.name for p in (root / "report").iterdir()),
                                 ["decision.json", "review.md"])


if __name__ == "__main__":
    unittest.main()

"""Offline regressions for the dry-run, stale-head, URL and credential boundaries."""
import base64
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci
import collect
import public_http
import review


def packet():
    return dict(repository=collect.REPO, pullRequest=dict(number=7, url=f"https://github.com/{collect.REPO}/pull/7", headSha="a" * 40),
                snapshot=dict(baseSha="b" * 40), rules=dict(url="https://example.com/rules", readmeUrl="https://example.com/list"),
                priorSubmissions=[], categoryEntries=[], maintainerPrecedents=[], deterministicFindings=[],
                proposals=[dict(name="Example", url="https://example.com/tool", markdown="- [Example](https://example.com/tool) - Tool.", existingMatches=[])],
                sources=[dict(url="https://example.com/tool", entryUrl="https://example.com/tool", status=200, excerpt="Official description")],
                linkCheck=dict(passed=True, results=[]))


def decision():
    return dict(decision="approve", humanReview=False, confidence="high", summary="Relevant tool.",
                category="Tools", proposedEntry=None, findings=[], contributorComment="Looks relevant.")


def event():
    return dict(action="synchronize", number=7, repository=dict(full_name=collect.REPO),
                pull_request=dict(number=7, state="open", draft=False,
                                  head=dict(sha="a" * 40), base=dict(sha="b" * 40, repo=dict(full_name=collect.REPO))))


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.packet = packet()
        self.decision = decision()

    def test_approval_is_a_preview_for_the_fork_and_exact_head(self):
        plan = review.action_plan(self.packet, self.decision, "open")
        self.assertFalse(plan["wouldExecuteNow"])
        self.assertEqual(plan["externalChangesPerformed"], 0)
        self.assertEqual(plan["hypotheticalRequests"][0]["json"]["commit_id"], "a" * 40)
        self.assertIn(collect.REPO, plan["hypotheticalRequests"][0]["url"])
        self.assertTrue(all("/merge" not in item["url"] for item in plan["hypotheticalRequests"]))

    def test_human_review_has_no_action_requests(self):
        for value in ("approve", "request_changes", "reject"):
            d = dict(self.decision, decision=value, humanReview=True)
            self.assertEqual(review.action_plan(self.packet, d, "open")["hypotheticalRequests"], [])

    def test_rejection_plan_retains_comment_before_close(self):
        rows = review.action_plan(self.packet, dict(self.decision, decision="reject"), "open")["hypotheticalRequests"]
        self.assertEqual([row["method"] for row in rows], ["POST", "PATCH"])

    def test_missing_official_source_blocks(self):
        self.packet["sources"] = []
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_failed_check_blocks(self):
        self.packet["linkCheck"]["passed"] = False
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_invented_citation_blocks(self):
        self.decision["findings"] = [dict(evidence=["https://invented.example/claim"], severity="advisory")]
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_invented_comment_link_blocks(self):
        self.decision["contributorComment"] = "See [fake](https://invented.example/claim)."
        self.assertTrue(review.guard(self.packet, self.decision)["humanReview"])

    def test_rule_failure_blocks_approval(self):
        self.packet["deterministicFindings"] = ["Two suggestions in one PR"]
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
                    self.assertEqual(review.action_plan(self.packet, guarded, "open")["hypotheticalRequests"], [])
                    self.assertEqual(raw, original)

    def test_action_plan_guards_raw_uncertain_overlap(self):
        raw = dict(self.decision, decision="reject", confidence="medium",
                   findings=[self.duplicate_finding()])
        plan = review.action_plan(self.packet, raw, "open")
        self.assertTrue(plan["humanReview"])
        self.assertEqual(plan["hypotheticalRequests"], [])
        self.assertFalse(plan["wouldExecuteNow"])
        self.assertEqual(plan["externalChangesPerformed"], 0)

    def test_high_confidence_duplicate_keeps_existing_rejection_preview(self):
        raw = dict(self.decision, decision="reject", findings=[self.duplicate_finding()])
        guarded = review.guard(self.packet, raw)
        self.assertFalse(guarded["humanReview"])
        self.assertEqual(guarded["guardReasons"], [])
        self.assertEqual([row["method"] for row in review.action_plan(self.packet, raw, "open")["hypotheticalRequests"]],
                         ["POST", "PATCH"])

    def test_nonblocking_duplicate_and_unrelated_fixes_are_not_newly_blocked(self):
        for finding in (self.duplicate_finding("advisory"),
                        dict(kind="rule", severity="blocking", message="Add a period.",
                             evidence=[self.packet["rules"]["url"]])):
            with self.subTest(finding=finding):
                raw = dict(self.decision, decision="request_changes", confidence="medium", findings=[finding])
                guarded = review.guard(self.packet, raw)
                self.assertFalse(guarded["humanReview"])
                self.assertEqual(len(review.action_plan(self.packet, raw, "open")["hypotheticalRequests"]), 1)

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
                guarded, plan, report = ci.render(self.packet, raw, True)
                self.assertTrue(guarded["humanReview"])
                self.assertEqual(guarded["decision"], recommendation)
                self.assertTrue(plan["humanReview"])
                self.assertEqual(plan["hypotheticalRequests"], [])
                self.assertIn("Human review required: **True**", report)
                self.assertIn("coverage-overlap", report)
                self.assertEqual(raw, original)

    def test_raw_action_plan_applies_existing_evidence_guards(self):
        cases = [
            (dict(self.packet, proposals=[]), self.decision),
            (dict(self.packet, sources=[]), self.decision),
            (dict(self.packet, linkCheck=dict(passed=False, results=[])), self.decision),
            (dict(self.packet, collectionWarnings=["Incomplete patch"]), self.decision),
            (dict(self.packet, deterministicFindings=["Two suggestions"]), self.decision),
            (self.packet, dict(self.decision, contributorComment="See [fake](https://invented.example/claim).")),
            (self.packet, dict(self.decision, findings=[self.duplicate_finding()])),
        ]
        for evidence, raw in cases:
            with self.subTest(packet=evidence, decision=raw):
                plan = review.action_plan(evidence, raw, "open")
                self.assertTrue(plan["humanReview"])
                self.assertEqual(plan["hypotheticalRequests"], [])

    def test_partial_patch_blocks_every_decision(self):
        self.packet["collectionWarnings"] = ["Incomplete patch"]
        for value in ("approve", "request_changes", "reject"):
            self.assertTrue(review.guard(self.packet, dict(self.decision, decision=value))["humanReview"])

    def test_stale_report_has_no_proposed_actions(self):
        guarded, plan, report = ci.render(self.packet, self.decision, False)
        self.assertTrue(guarded["humanReview"])
        self.assertEqual(plan["hypotheticalRequests"], [])
        self.assertIn("stale", report)

    def test_render_does_not_mutate_model_output(self):
        before = copy.deepcopy(self.decision)
        ci.render(self.packet, self.decision, False)
        self.assertEqual(before, self.decision)

    def test_html_is_escaped_in_report(self):
        self.decision["contributorComment"] = "<img src=x>"
        self.assertIn("&lt;img", ci.render(self.packet, self.decision, True)[2])

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
            self.assertFalse(ci.fresh(ci.request_from_event(event(), collect.REPO)))

    def test_changed_base_fails_freshness(self):
        current = event()["pull_request"]; current["base"]["sha"] = "c" * 40
        with patch.object(collect, "github", return_value=current):
            self.assertFalse(ci.fresh(ci.request_from_event(event(), collect.REPO)))

    def test_stale_prepare_does_not_collect(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "event.json"; file.write_text(json.dumps(event()))
            with patch.object(ci, "fresh", return_value=False), patch.object(collect, "collect") as gather:
                with self.assertRaisesRegex(ValueError, "Superseded"):
                    ci.prepare(file, Path(directory) / "input")
                gather.assert_not_called()

    def test_mismatched_artifact_identity_rejected_before_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); p = packet(); p["pullRequest"]["headSha"] = "c" * 40
            (root / "packet.json").write_text(json.dumps(p))
            (root / "request.json").write_text(json.dumps(ci.request_from_event(event(), collect.REPO)))
            with patch.object(ci, "fresh") as api:
                with self.assertRaisesRegex(ValueError, "identity"):
                    ci.finish(root, root / "decision.json", root / "out")
                api.assert_not_called()

    def test_no_authenticated_arbitrary_api(self):
        with patch.object(collect.subprocess, "run") as run:
            with self.assertRaises(ValueError): collect.github("repos/other/private/readme")
            run.assert_not_called()

    def test_submitted_repo_fetch_never_uses_operator_auth(self):
        with patch.object(collect, "fetch", return_value=dict(status=404, truncated=False)), patch.object(collect, "github") as authenticated:
            with self.assertRaises(ValueError): collect.public_github_readme("owner/private")
            authenticated.assert_not_called()


class NetworkTests(unittest.TestCase):
    def addresses(self, ip):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    def test_non_public_addresses_rejected(self):
        for ip in ("127.0.0.1", "10.1.1.1", "169.254.169.254", "100.64.0.1", "224.0.0.1", "::1", "fc00::1", "::ffff:127.0.0.1"):
            with self.subTest(ip=ip), patch.object(public_http.socket, "getaddrinfo", return_value=self.addresses(ip)):
                with self.assertRaisesRegex(ValueError, "Non-public"):
                    public_http.destination("https://example.com")

    def test_mixed_public_private_dns_rejected(self):
        with patch.object(public_http.socket, "getaddrinfo", return_value=self.addresses("8.8.8.8") + self.addresses("127.0.0.1")):
            with self.assertRaises(ValueError): public_http.destination("https://example.com")

    def test_bad_urls_rejected_before_dns(self):
        for url in ("file:///tmp/no", "http://user:pass@example.com", "https://example.com:8080", "https://example.com/\r\ninject", "https://example.com\\@localhost/"):
            with self.subTest(url=url), patch.object(public_http.socket, "getaddrinfo") as dns:
                with self.assertRaises(ValueError): public_http.destination(url)
                dns.assert_not_called()

    def test_fetch_connects_to_the_validated_address(self):
        sock = MagicMock()
        response = MagicMock(status=200)
        response.getheader.return_value = None
        response.read1.side_effect = [b"safe", b""]
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(public_http.socket, "getaddrinfo", return_value=self.addresses("8.8.8.8")) as dns, \
             patch.object(public_http.socket, "socket", return_value=sock), \
             patch.object(public_http.http.client, "HTTPConnection", return_value=connection):
            result = public_http._fetch("http://example.com/")
            self.assertEqual(result["content"], b"safe")
            self.assertEqual(dns.call_count, 1)
            sock.connect.assert_called_once_with(("8.8.8.8", 443))
            self.assertIs(connection.sock, sock)
            self.assertNotIn("Authorization", connection.request.call_args.kwargs["headers"])

    def test_redirect_private_destination_is_rejected(self):
        response = MagicMock(status=302); response.getheader.return_value = "http://127.0.0.1/"
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(public_http.socket, "getaddrinfo", side_effect=[self.addresses("8.8.8.8"), self.addresses("127.0.0.1")]), \
             patch.object(public_http, "_connect"), patch.object(public_http.http.client, "HTTPConnection", return_value=connection):
            with self.assertRaisesRegex(ValueError, "Non-public"):
                public_http._fetch("http://example.com")

    def test_size_limit_is_retained(self):
        response = MagicMock(status=200); response.getheader.return_value = None; response.read1.return_value = b"12345"
        connection = MagicMock(); connection.getresponse.return_value = response
        with patch.object(public_http.socket, "getaddrinfo", return_value=self.addresses("8.8.8.8")), \
             patch.object(public_http, "_connect"), patch.object(public_http.http.client, "HTTPConnection", return_value=connection):
            result = public_http._fetch("http://example.com", limit=4)
            self.assertEqual(result["content"], b"1234")
            self.assertTrue(result["truncated"])

    def test_process_deadline_bounds_dns_and_headers(self):
        with patch.object(public_http.subprocess, "run", side_effect=subprocess.TimeoutExpired("fetch", 35)) as run:
            with self.assertRaisesRegex(TimeoutError, "process deadline"):
                public_http.fetch("https://example.com")
            self.assertEqual(run.call_args.kwargs["timeout"], 35)

    def test_fetch_process_does_not_inherit_credentials(self):
        result = MagicMock(stdout=json.dumps(dict(status=200, contentBase64="", truncated=False)))
        with patch.dict(public_http.os.environ, {"GH_TOKEN": "must-not-pass", "ANTHROPIC_API_KEY": "must-not-pass"}), patch.object(public_http.subprocess, "run", return_value=result) as run:
            public_http.fetch("https://example.com")
            env = run.call_args.kwargs["env"]
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("ANTHROPIC_API_KEY", env)


class EditCoverageTests(unittest.TestCase):
    def test_valid_addition_needs_no_warning(self):
        p = packet()["proposals"]
        change = dict(patch="+" + p[0]["markdown"], additions=1, deletions=0)
        self.assertEqual(ci.edit_warnings(change, p), [])

    def test_extra_prose_is_not_silently_approved(self):
        p = packet()["proposals"]
        change = dict(patch="+" + p[0]["markdown"] + "\n+New rules", additions=2, deletions=0)
        self.assertTrue(ci.edit_warnings(change, p))

    def test_removal_is_not_silently_approved(self):
        p = packet()["proposals"]
        change = dict(patch="+" + p[0]["markdown"] + "\n-## Existing category", additions=1, deletions=1)
        self.assertTrue(ci.edit_warnings(change, p))

    def test_recognized_description_update_needs_no_warning(self):
        p = packet()["proposals"]; p[0]["changeKind"] = "update"
        change = dict(patch="+" + p[0]["markdown"] + "\n-" + p[0]["markdown"].replace("Tool.", "Old."), additions=1, deletions=1)
        self.assertEqual(ci.edit_warnings(change, p), [])

    def test_new_category_is_allowed(self):
        p = packet()["proposals"]
        change = dict(patch="+## New category\n+" + p[0]["markdown"], additions=2, deletions=0)
        self.assertEqual(ci.edit_warnings(change, p), [])

    def test_truncated_removals_require_human_review(self):
        self.assertTrue(ci.edit_warnings(dict(patch="", additions=0, deletions=1), []))


class PipelineTests(unittest.TestCase):
    def test_prepare_and_finish_without_network_or_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = event()
            payload["pull_request"].update(title="Example", body="$(not executed)", closed_at=None,
                                         html_url=f"https://github.com/{collect.REPO}/pull/7")
            base = "# List\n## Tools\n"
            addition = packet()["proposals"][0]["markdown"]
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
            with patch.object(collect, "EVIDENCE", root / "evidence"), patch.object(collect, "github", side_effect=github), \
                 patch.object(collect, "fetch", return_value=dict(status=200, finalUrl="https://example.com/tool", contentType="text/plain", truncated=False, content=b"Official description")):
                ci.prepare(root / "event.json", root / "input")
                data = json.loads((root / "input/packet.json").read_text())
                self.assertEqual(data["repository"], collect.REPO)
                self.assertTrue(data["linkCheck"]["passed"])
                self.assertEqual(data["collectionWarnings"], [])
                self.assertIn("readmeDiff", data)
                (root / "decision.json").write_text(json.dumps(decision()))
                ci.finish(root / "input", root / "decision.json", root / "report")
                plan = json.loads((root / "report/action-plan.json").read_text())
                self.assertEqual(plan["externalChangesPerformed"], 0)
                self.assertFalse(plan["wouldExecuteNow"])
                self.assertEqual(sorted(p.name for p in (root / "report").iterdir()),
                                 ["action-plan.json", "decision.json", "request.json", "review.md"])



class HistoryTests(unittest.TestCase):
    def test_name_variants_exclude_future_history(self):
        proposals = [dict(name="BestJSON JSON Diff", url="https://bestjson.com/json-diff")]
        history = [dict(number=1, title="Add JSON Diff", body="", created_at="2020-01-01", html_url="https://github.com/example/1"),
                   dict(number=2, title="Add JSON Diff", body="", created_at="2022-01-01", html_url="https://github.com/example/2")]
        self.assertEqual([item["number"] for item in collect.historical_matches(proposals, history, 7, "2021-01-01")], [1])

    def test_name_does_not_match_inside_frontend_testing(self):
        proposals = [dict(name="Endtest", url="https://endtest.io")]
        history = [dict(number=1, title="Frontend testing", body="End testing problems.", created_at="2020-01-01", html_url="https://github.com/example/1")]
        self.assertEqual(collect.historical_matches(proposals, history, 7, "2021-01-01"), [])

    def test_prior_context_uses_upstream_not_fork_numbers(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(collect, "EVIDENCE", Path(directory)), patch.object(collect, "pages", return_value=[]) as pages:
            collect.prior_context([dict(number=1)], [dict(number=1, closed_at=None, merged_at=None, updated_at="2020-01-01")], "2021-01-01")
            self.assertTrue(all("repos/TheJambo/awesome-testing/" in args.args[0] for args in pages.call_args_list))


if __name__ == "__main__":
    unittest.main()

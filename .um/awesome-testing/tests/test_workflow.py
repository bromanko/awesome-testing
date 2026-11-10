"""Command-step input handling and read-only API authentication."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci
import collect
from test_review import event, packet, decision


class WorkflowTests(unittest.TestCase):
    def test_collect_reads_materialized_event(self):
        with patch.dict(os.environ, {"UM_STEP_INPUTS": "/tmp/step inputs"}), \
             patch.object(sys, "argv", ["ci.py", "prepare"]), patch.object(ci, "prepare") as prepare:
            ci.main()
        prepare.assert_called_once_with(Path("/tmp/step inputs/values/event"), Path("work/input"))

    def test_report_reads_all_materialized_outputs(self):
        with patch.dict(os.environ, {"UM_STEP_INPUTS": "/tmp/step inputs"}), \
             patch.object(sys, "argv", ["ci.py", "finish"]), patch.object(ci, "finish") as finish:
            ci.main()
        finish.assert_called_once_with(Path("/tmp/step inputs/values/packet"),
                                       Path("/tmp/step inputs/values/request"),
                                       Path("/tmp/step inputs/values/decision"), Path("work/report"))

    def test_upstream_repository_comes_from_validated_event(self):
        value = event()
        value["repository"]["full_name"] = collect.UPSTREAM
        value["pull_request"]["base"]["repo"]["full_name"] = collect.UPSTREAM
        with tempfile.TemporaryDirectory() as directory, patch.object(collect, "REPO", collect.REPO):
            root = Path(directory); (root / "event.json").write_text(json.dumps(value))
            with patch.object(ci, "current_pr", return_value=value["pull_request"]) as current, \
                 patch.object(collect, "collect", return_value=packet()):
                ci.prepare(root / "event.json", root / "out")
            self.assertEqual(collect.REPO, collect.UPSTREAM)
            self.assertEqual(current.call_args.args[0]["repository"], collect.UPSTREAM)

    def test_report_restores_repository_from_bound_request(self):
        p = packet(); p["repository"] = collect.UPSTREAM
        request = dict(repository=collect.UPSTREAM, number=7, headSha="a" * 40, baseSha="b" * 40)
        with tempfile.TemporaryDirectory() as directory, patch.object(collect, "REPO", collect.REPO):
            root = Path(directory)
            for name, data in [("packet", p), ("request", request), ("decision", decision())]:
                (root / name).write_text(json.dumps(data))
            with patch.object(ci, "current_pr", return_value={}) as current:
                ci.finish(root / "packet", root / "request", root / "decision", root / "out")
            self.assertEqual(collect.REPO, collect.UPSTREAM)
            current.assert_called_once_with(request)

    def test_http_reads_use_scoped_token_without_command_interpolation(self):
        with patch.dict(os.environ, {"REVIEW_GITHUB_TOKEN": "test-placeholder"}), \
             patch.object(collect, "urlopen", return_value=io.BytesIO(b'{"number": 7}')) as fetch:
            self.assertEqual(collect.github(f"repos/{collect.REPO}/pulls/7"), {"number": 7})
        request = fetch.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-placeholder")
        self.assertEqual(request.full_url, f"https://api.github.com/repos/{collect.REPO}/pulls/7")

    def test_public_reads_work_without_token(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(collect, "urlopen", return_value=io.BytesIO(b'{}')) as fetch:
            collect.github(f"repos/{collect.REPO}/pulls/7")
        self.assertIsNone(fetch.call_args.args[0].get_header("Authorization"))

    def test_unrecognized_event_repository_stops_before_collection(self):
        value = event(); value["repository"]["full_name"] = "other/private"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "event.json").write_text(json.dumps(value))
            with patch.object(collect, "collect") as gather:
                with self.assertRaisesRegex(ValueError, "Unsupported repository"):
                    ci.prepare(root / "event.json", root / "out")
                gather.assert_not_called()


if __name__ == "__main__":
    unittest.main()

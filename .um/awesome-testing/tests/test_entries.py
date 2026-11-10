"""Pinned README facts: additions, moves, edits, and exact existing URL matches."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect
import ci
from test_review import packet, decision, event


class EntryTests(unittest.TestCase):
    entry = "- [Tool](https://example.com/tool) - Useful."
    base = "# List\n## Software\n### API\n" + entry + "\n"

    def test_primary_url_heading_and_pinned_line(self):
        head = self.base + "- [New](https://example.com/new) - Uses [docs](https://example.com/docs).\n"
        change, = collect.readme_changes(self.base, head)
        self.assertEqual(change["kind"], "added")
        self.assertEqual(change["after"]["url"], "https://example.com/new")
        self.assertEqual(change["after"]["category"], "Software > API")
        self.assertEqual(change["after"]["line"], 5)
        self.assertEqual(change["existingMatches"], [])

    def test_exact_duplicate_carries_original_location(self):
        changes = collect.readme_changes(self.base, self.base + "### Other\n" + self.entry)
        change, = changes
        self.assertEqual(change["kind"], "added")
        self.assertEqual(change["after"]["category"], "Software > Other")
        self.assertEqual([(m["category"], m["line"]) for m in change["existingMatches"]], [("Software > API", 4)])

    def test_move_and_description_edit_are_not_new_duplicate(self):
        head = "# List\n## Software\n### Other\n" + self.entry.replace("Useful.", "New description.")
        change, = collect.readme_changes(self.base, head)
        self.assertEqual(change["kind"], "moved")
        self.assertEqual(change["before"]["category"], "Software > API")
        self.assertEqual(change["after"]["category"], "Software > Other")
        self.assertEqual(change["existingMatches"], [])

    def test_name_and_description_edit_are_not_new_duplicate(self):
        change, = collect.readme_changes(self.base, self.base.replace("[Tool]", "[Renamed]").replace("Useful.", "Revised."))
        self.assertEqual(change["kind"], "edited")
        self.assertEqual(change["existingMatches"], [])

    def test_preexisting_duplicate_and_line_shifts_do_not_create_findings(self):
        base = self.base + "### Other\n" + self.entry
        self.assertEqual(collect.readme_changes(base, "Extra prose.\n\n" + base), [])

    def test_move_of_preexisting_duplicate_does_not_add_occurrence(self):
        base = self.base + "### Other\n" + self.entry
        change, = collect.readme_changes(base, base.replace("### Other", "### Changed"))
        self.assertEqual(change["kind"], "moved")
        self.assertEqual(change["existingMatches"], [])

    def test_removed_and_replaced_urls_are_preserved(self):
        changes = collect.readme_changes(self.base, self.base.replace("example.com/tool", "example.com/new"))
        self.assertEqual([c["kind"] for c in changes], ["added", "removed"])
        self.assertEqual(changes[1]["before"]["url"], "https://example.com/tool")
        self.assertIsNone(changes[1]["after"])

    def test_matching_does_not_collapse_path_case_query_fragment_or_slash(self):
        for url in ("https://example.com/Tool", "https://example.com/tool/", "https://example.com/tool?x=1", "https://example.com/tool#guide"):
            with self.subTest(url=url):
                change, = collect.readme_changes(self.base, self.base + f"- [Other]({url}) - Useful.")
                self.assertEqual(change["existingMatches"], [])

    def test_inline_url_variants_and_excluding_nonentries(self):
        text = ('# List\n## Software\n### API ###\n'
                '- [TOC](#api)\n![Image](https://example.com/image)\n'
                '```md\n### Fake\n- [Fake](https://example.com/fake)\n```\n'
                '<!--\n### Hidden\n- [Hidden](https://example.com/hidden)\n-->\n'
                '* [Parentheses](https://example.com/tool_(testing)) - Tool.\n'
                '+ [Angle](<https://example.com/angle> "Title") - Tool.\n')
        entries = collect.readme_entries(text)
        self.assertEqual([e["url"] for e in entries], ["https://example.com/tool_(testing)", "https://example.com/angle"])
        self.assertEqual([e["line"] for e in entries], [14, 15])
        self.assertTrue(all(e["category"] == "Software > API" for e in entries))

    def test_collector_and_report_surface_duplicate_without_changing_recommendation(self):
        pr = event()["pull_request"]
        pr.update(title="Add tool", body="", html_url="https://github.com/example/repo/pull/7")
        head = self.base + self.entry
        context = collect.assemble(pr, [], self.base, head, "Rules")
        raw = decision()
        original = copy.deepcopy(raw)
        guarded, report = ci.render(context, raw, True)
        self.assertEqual(guarded["decision"], "approve")
        self.assertTrue(guarded["humanReview"])
        self.assertIn("already listed under Software &gt; API (base README line 4)", report)
        self.assertIn("Check whether another listing is intended", report)
        self.assertEqual(raw, original)

    def test_move_does_not_add_report_hold(self):
        context = packet()
        context["readmeChanges"] = collect.readme_changes(self.base, self.base.replace("### API", "### Other"))
        guarded, report = ci.render(context, decision(), True)
        self.assertFalse(guarded["humanReview"])
        self.assertNotIn("already listed", report)

    def test_edit_and_addition_of_same_url_keep_the_original_category(self):
        head = "# List\n## Software\n### Other\n" + self.entry + "\n### API\n" + self.entry.replace("Useful.", "Revised.")
        changes = collect.readme_changes(self.base, head)
        self.assertEqual([(c["kind"], c["after"]["category"]) for c in changes],
                         [("edited", "Software > API"), ("added", "Software > Other")])
        self.assertEqual(len(changes[1]["existingMatches"]), 1)

    def test_behind_target_branch_does_not_invent_pr_removals(self):
        ancestor = "# List\n## Software\n### API\n"
        target = self.base + "- [Target only](https://example.com/target-only) - Tool.\n"
        head = ancestor + self.entry
        changes = collect.readme_changes(ancestor, head, target)
        change, = changes
        self.assertEqual(change["kind"], "added")
        self.assertEqual(change["after"]["url"], "https://example.com/tool")
        self.assertEqual(change["existingMatches"][0]["line"], 4)
        self.assertNotIn("target-only", str(changes))

    def test_target_removal_does_not_turn_pr_edit_into_new_duplicate(self):
        head = self.base.replace("Useful.", "Revised.")
        change, = collect.readme_changes(self.base, head, "# List\n## Software\n")
        self.assertEqual(change["kind"], "edited")
        self.assertEqual(change["existingMatches"], [])

    def test_collector_uses_common_ancestor_but_matches_current_target(self):
        pr = event()["pull_request"]
        pr.update(title="Add tool", body="", html_url="https://github.com/example/repo/pull/7")
        ancestor = "# List\n## Software\n### API\n"
        snapshots = {"b" * 40: self.base, "a" * 40: ancestor + self.entry, "c" * 40: ancestor}
        with patch.object(collect, "pages", return_value=[]), \
             patch.object(collect, "github", return_value={"merge_base_commit": {"sha": "c" * 40}}) as api, \
             patch.object(collect, "readme_at", side_effect=lambda ref, filename="README.md": snapshots[ref] if filename == "README.md" else "Rules"):
            context = collect.collect(pr)
        api.assert_called_once_with(f"repos/{collect.REPO}/compare/{'b' * 40}...{'a' * 40}")
        self.assertEqual(context["snapshot"]["diffBaseSha"], "c" * 40)
        change, = context["readmeChanges"]
        self.assertEqual(change["kind"], "added")
        self.assertEqual(len(change["existingMatches"]), 1)


if __name__ == "__main__":
    unittest.main()

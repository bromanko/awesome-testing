# Fresh-case rubric evaluation — 2026-11-09

The stronger rubric improved calibration but did not establish better accuracy on fresh cases. It became more decisive and rejected four resources the maintainer accepted. Do not promote it to the production workflow.

## Primary holdout result

Sixteen cases were selected before reading their discussions or developing case-specific changes. Fifteen have usable inclusion labels: nine accepted, six rejected. One has no documented inclusion decision and remains unscored. A closed-unmerged PR that was applied manually is correctly labeled accepted.

A human-review flag counts as abstention even when a model also gives a tentative recommendation. Holds earn no correct-decision credit.

| Variant, same Opus model | Correct / all 15 | False approvals | False rejections | Abstentions | Accuracy when decisive | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| Prior detailed agent prompt | 3/15 | 3 | 0 | 9 | 50.0% | 40.0% |
| Proposed curator rubric | 8/15 | 2 | 4 | 1 | 57.1% | 93.3% |

Always including would match **9/15**; always excluding would match **6/15**. The rubric does not beat the stronger trivial baseline. Its greater decision coverage is not evidence of adequate accuracy.

For completeness, ignoring human-review holds, raw inclusion recommendations matched **9/15 for the prior prompt** and **8/15 for the rubric**. Exact raw approve/reject action agreement was **8/15** and **7/15**, respectively. These raw matches are not counted as correct actionable decisions in the primary table.

## What went wrong

The rubric generalized the rejection examples into too strict a novelty requirement. It excluded accepted entries because their value lay in workflow, deployment or convenience:

- **#218 Waterfall AI Test:** excluded as another way to generate and maintain Playwright tests; the maintainer merged it.
- **#276 8½ Minute Mail:** excluded as another manual temporary inbox; the maintainer merged it. Both prompts recommended exclusion here, so this is not only a new-rubric failure.
- **#284 Locust Kubernetes Operator:** excluded because k6 already provides distributed load testing, treating the Locust/Kubernetes workflow as implementation detail. The maintainer merged it.
- **#300 CurlShot:** excluded as a screenshot/PDF capture service overlapping fuller visual-testing tools. The maintainer merged it.

The rubric also approved rejected **#216 Testudos** (maintainer called it too niche) and **#267 APIFae** (maintainer said it was unreleased; the author disputed that). Current source snapshots cannot reconstruct historical release availability.

Correct labels do not prove correct reasoning: #217 and #256 were rejected historically on maturity/adoption grounds, while the rubric rejected them for coverage. Those maintainer reasons were not in the published rules or the frozen proposed rubric. Adding a popularity rule now to fit these cases would be another calibration step, not validation.

## Calibration and selection

Ten already-seen cases were used only for calibration. Eight had inclusion labels. The same frozen rubric produced:

| Model | Correct / 8 | False approvals | False rejections | Abstentions | Output failures |
| --- | --- | --- | --- | --- | --- |
| Sonnet | 5/8 | 2 | 0 | 0 | 1 |
| Opus | 6/8 | 2 | 0 | 0 | 0 |

Opus was selected by the preregistered rule: most correct non-abstaining inclusion decisions, then fewer false approvals, then lower cost. Sonnet and Opus agreed on every calibration case where both returned a valid report; the selection advantage was one Sonnet structured-output failure, not demonstrated superior judgment. Opus still approved the known Email Blackhole and RequestFox rejection cases.

The original experiment did not establish a high, unbiased accuracy target. Its reports mixed known-case tuning, current policy derived from later closures, additional cases and human-review holds. This study does not reinterpret those holds as correct decisions. Separating inclusion from a correctable factual defect is an explicit measurement change shared by both new holdout arms; the earlier 2/8–3/8 figures are not directly interchangeable with inclusion scores.

## Evidence-only correction, separately reported

Before opening closure reasons, an abstention exposed a collection bug: a specific GitHub document link was replaced with the repository README. A mechanical audit of every selected source identified only **#289** as affected. The original corpus and all primary results remain unchanged. The collector now preserves exact blob documents. Both frozen prompts were run once on a separate corrected copy of that case, with no model or prompt tuning.

Both then recommended exclusion. The prior prompt still requested human review; the rubric did not. Substituting only that diagnostic rerun gives the rubric **9 correct, 2 false approvals, 4 false rejections, no abstentions out of 15**, tying always-include. The prior prompt remains **3 correct, 3 false approvals and 9 holds**; its raw tentative inclusion agreement becomes 10/15. This is a sensitivity check after observing an evidence failure, not a second untouched holdout and not proof of an accuracy gain.

## Per-case primary results

`include + fix` means the resource merits inclusion after a specific correction. `hold` means human review is required; even a matching tentative recommendation receives no correct-decision credit.

| PR | Historical inclusion | Prior prompt | Rubric |
| --- | --- | --- | --- |
| [#203 Add Bats](https://github.com/TheJambo/awesome-testing/pull/203) | [include](https://github.com/TheJambo/awesome-testing/pull/203) | include + fix (hold) | include + fix |
| [#216 Add Testudos](https://github.com/TheJambo/awesome-testing/pull/216) | [exclude](https://github.com/TheJambo/awesome-testing/pull/216#issuecomment-5457048464) | include | include |
| [#217 Add AI API Test Generator](https://github.com/TheJambo/awesome-testing/pull/217) | [exclude](https://github.com/TheJambo/awesome-testing/pull/217#issuecomment-5457064423) | exclude (hold) | exclude |
| [#218 Add Waterfall AI Test](https://github.com/TheJambo/awesome-testing/pull/218) | [include](https://github.com/TheJambo/awesome-testing/pull/218) | include (hold) | exclude |
| [#245 Add aiexpect to AI & LLM Testing](https://github.com/TheJambo/awesome-testing/pull/245) | [include](https://github.com/TheJambo/awesome-testing/pull/245) | include | include |
| [#256 Add jevnav to UI & End-to-End Testing](https://github.com/TheJambo/awesome-testing/pull/256) | [exclude](https://github.com/TheJambo/awesome-testing/pull/256#issuecomment-5855368475) | include | exclude |
| [#267 Add APIFae to Service Virtualization](https://github.com/TheJambo/awesome-testing/pull/267) | [exclude](https://github.com/TheJambo/awesome-testing/pull/267#issuecomment-5920144525) | include | include |
| [#276 Add 8½ Minute Mail to Test Data Management](https://github.com/TheJambo/awesome-testing/pull/276) | [include](https://github.com/TheJambo/awesome-testing/pull/276) | exclude (hold) | exclude |
| [#284 Add Locust Kubernetes Operator to Performance & Load Testing](https://github.com/TheJambo/awesome-testing/pull/284) | [include](https://github.com/TheJambo/awesome-testing/pull/284) | include (hold) | exclude |
| [#289 Add browser outcome-verification field notes to Training](https://github.com/TheJambo/awesome-testing/pull/289) | [exclude](https://github.com/TheJambo/awesome-testing/pull/289#issuecomment-6275633471) | abstain | abstain |
| [#300 Add CurlShot to Visual Testing](https://github.com/TheJambo/awesome-testing/pull/300) | [include](https://github.com/TheJambo/awesome-testing/pull/300) | abstain | exclude |
| [#322 Add OverlayQA MCP to Accessibility & Usability Testing](https://github.com/TheJambo/awesome-testing/pull/322) | [unknown](https://github.com/TheJambo/awesome-testing/pull/322) | include + fix (hold) | exclude |
| [#323 Add Site Spell Checker to Accessibility & Usability Testing](https://github.com/TheJambo/awesome-testing/pull/323) | [include](https://github.com/TheJambo/awesome-testing/pull/323) | include (hold) | include |
| [#340 Add OpenAPI Breaking Change Checker to API Testing](https://github.com/TheJambo/awesome-testing/pull/340) | [include](https://github.com/TheJambo/awesome-testing/pull/340) | include | include |
| [#343 Add telegym to Performance & Load Testing](https://github.com/TheJambo/awesome-testing/pull/343) | [include](https://github.com/TheJambo/awesome-testing/pull/343#issuecomment-6476321561) | include | include |
| [#346 Add GetTemp.Email testing connector](https://github.com/TheJambo/awesome-testing/pull/346) | [exclude](https://github.com/TheJambo/awesome-testing/pull/346#issuecomment-6511275610) | exclude (hold) | exclude |

**Label checks:** #343 was accepted by direct commit [`3fd3aa596cec03d199fd963a2fbc0ad5c9cec8a5`](https://github.com/TheJambo/awesome-testing/commit/3fd3aa596cec03d199fd963a2fbc0ad5c9cec8a5), verified against the maintainer comment and commit diff. #322 has no documented acceptance/rejection reason and is unscored; it was not replaced.

## Controls and limits

- Fixed hash selection of eight merged and eight closed-unmerged PRs numbered at least 200; previously collected target/prior cases and known target resource families were excluded. No replacements after results. The sixteen targets have distinct URLs and cover ten categories.
- One proposed rubric, with representative calibration patterns, was frozen before fresh PR content and outcome reasons were inspected. The model was selected on calibration only. No prompt tuning followed holdout results.
- Both holdout arms used `claude-opus-5-5`, medium effort, the same native structured schema, source documents and Read/Glob/Grep tools. Baseline transport instructions were adapted identically to the new inclusion/abstention fields.
- Separate restricted working directories, safe mode, strict empty MCP configuration, no session persistence, no GitHub token passed to model processes. Outcomes and other runs were inaccessible to model file tools. No unexpected tools or inconsistent inclusion/action pairs were observed.
- Prompt and corpus hashes were verified after execution. Before holdout execution, parent-ref notation for merged cases was resolved to plain commit SHAs, removing an outcome-correlated metadata signal. All holdout IDs were excluded from submission-history indexes. Mutable target PR bodies were omitted.
- Pinned merge-parent baselines for merged PRs and merge-base snapshots for unmerged PRs; final PR heads and current official sources. This is not a historical reconstruction. Sixty-four of 65 public source fetches succeeded; the access failure was retained. Alternatives were selected by a generic same-category lexical rule, which can miss the best comparison.
- The calibration cases are already familiar, and the holdout is small and deliberately stratified. Models may have encountered public repositories in training. Historical maintainer policy and product availability can change; notably, some older closure reasons use maturity/popularity while later calibration emphasized breadth. Historical agreement is not an objective oracle for review quality.
- Production workflow, model and PR body remain unchanged. The new rubric is retained as an evaluated candidate, not silently adopted.

## Recommendation

Do not tighten the prompt further against these same holdout failures. This holdout is now spent. The evidence does not justify a production model upgrade or a blanket requirement that every entry enable a unique testing task. The next valid evaluation needs a fresh set and a clearer, current maintainer standard for when workflow/convenience improvements are valuable, ideally with judgments made on the same current evidence. Otherwise matching inconsistent historical decisions invites further overfitting.

The research summary may still be useful, but its usefulness has not been measured independently of recommendation agreement. Keep recommendations advisory.

## Retained evidence and cost

Completed **54 attempts**: 20 calibration, 32 primary holdout and 2 evidence-correction runs. All 34 holdout/correction runs returned valid structured reports; one calibration Sonnet run failed after native output retries. Total CLI-reported list-price estimate: **$17.31**, not necessarily billed cost.

The acquisition workspace retains the protocol, split, prompt/model locks, source files and hashes, independent labels, all native transcripts, receipts, audits and both primary/sensitivity summaries under `targets/awesome-testing/agent-review/holdout-study/`.

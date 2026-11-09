# Agent-led review backtest — 2026-11-09

Claude now investigates with normal tools instead of classifying a preselected
evidence packet. These runs demonstrate that the integration works and produces
more extensive research traces. They do **not** establish better curation judgment than the old
reviewer or support automatic approval/rejection.

The final Sonnet pass completed all 11 cases. Raw recommendations agreed with
2/8 historical approve/reject labels; 9/11 reports required a maintainer.
2 final runs have outcome-exposure/audit flags. Excluding flagged runs,
raw agreement was 1/6 labeled cases. These are descriptive counts, not an accuracy
estimate: all cases had been examined previously, and current sources can differ
from the historical products. Author withdrawals and the category-correction case
are not counted as binary rejection labels. A held recommendation is an abstention,
not a correct decision. Absence of an audit flag does not prove absence of leakage.

## Final pass

| PR | Historical result | Recommendation | Human review | Audit flag | Report |
| --- | --- | --- | --- | --- | --- |
| [#34](https://github.com/TheJambo/awesome-testing/pull/34) | category correction | approve | no | none detected | [read](backtests/pr-34.md) |
| [#35](https://github.com/TheJambo/awesome-testing/pull/35) | merged | approve | yes | none detected | [read](backtests/pr-35.md) |
| [#81](https://github.com/TheJambo/awesome-testing/pull/81) | author withdrew | approve | no | none detected | [read](backtests/pr-81.md) |
| [#107](https://github.com/TheJambo/awesome-testing/pull/107) | maintainer rejected | approve | yes | yes | [read](backtests/pr-107.md) |
| [#297](https://github.com/TheJambo/awesome-testing/pull/297) | maintainer rejected | approve | yes | none detected | [read](backtests/pr-297.md) |
| [#333](https://github.com/TheJambo/awesome-testing/pull/333) | merged | approve | yes | yes | [read](backtests/pr-333.md) |
| [#347](https://github.com/TheJambo/awesome-testing/pull/347) | maintainer rejected | approve | yes | none detected | [read](backtests/pr-347.md) |
| [#354](https://github.com/TheJambo/awesome-testing/pull/354) | merged | request_changes | yes | none detected | [read](backtests/pr-354.md) |
| [#360](https://github.com/TheJambo/awesome-testing/pull/360) | author withdrew | approve | yes | none detected | [read](backtests/pr-360.md) |
| [#362](https://github.com/TheJambo/awesome-testing/pull/362) | maintainer rejected | approve | yes | none detected | [read](backtests/pr-362.md) |
| [#370](https://github.com/TheJambo/awesome-testing/pull/370) | maintainer rejected | approve | yes | none detected | [read](backtests/pr-370.md) |

## What changed during tuning

- Replaced chosen excerpts and keyword-matched prior PRs with exact PR changes,
  complete base/head README, and contribution rules. Claude owns source research,
  history search, use-case comparisons, and follow-up questions.
- Added a research record to the summary. Newly discovered citations are accepted;
  report checks test consistency, not the truth of the agent's claims.
- Replaced broad repository web searches with API searches that should filter the
  target and later records before display. The final replay sets `historyBefore`
  to target submission time. The pinned README determines what was already listed.
- Clarified that implementation/pricing/vendor differences are not necessarily a
  new testing need. Asked for concrete unresolved questions, not generic caveats.
- Retained every earlier attempt. Some earlier runs saw target outcomes or treated
  a later merged sibling as already listed. Those are evaluation failures, not wins.

## Findings that matter

The final run on #34 approved a mock-server tool under Security despite describing
it as an API-mocking utility. That is a judgment/category miss. The final #81 run
also approved a unit-testing resource despite the foreword scope restriction; this
is a scope concern, not a scored maintainer-rejection label because the author withdrew it. On overlap cases,
inspect whether the agent establishes a missing testing task rather than merely
naming a product difference. Several approvals remain discretionary or conflict
with the maintainer's historical rejection. More research did not eliminate that
problem, and the human-review flags should not conceal it. On #360 it also raised
stars/project-age concerns despite being told not to invent those requirements.

The agent can also fail the evaluation procedure itself: a raw API search or later
comment can reveal the target outcome. #333 disclosed such exposure in the final
pass. Prompt instructions alone are not a guarantee of blinded evaluation. Reported
source access is self-reported; raw tool traces are retained locally for audit.

A useful next experiment is Opus both with this fixed prompt and with a separate,
shorter maintainer brief tuned for that model. No Opus runs were performed in this
iteration; Sonnet's prompt is not assumed to be optimal for Opus.

## Reproducibility and limits

- UM 0.72.1; official Claude Code 2.1.284; claude-sonnet-5, medium effort.
- Final prompt SHA-256: `cc9ab3341cca32a8067c70339c08dfe78b7d2e9ef3f2b36e7977ab3c8d02986b`.
- Final-pass provider-reported cost: **$3.28**; median runtime **46s**.
- All 30 retained attempts: **$9.06** recorded cost. One UM 0.57.0
  protocol failure has no cost receipt, so that total is incomplete. Costs are
  provider estimates, not billing invoices.
- The old Action's UM 0.57.0 rejected a normal Claude ToolSearch response. The Action
  now pins a published revision supporting `um-version`, explicitly set to 0.72.1.
- Exact historical final-head diffs were reused; current web research was allowed.
  History cutoff is submission time, which can precede later edits in the retained
  final head. This is not a reconstruction of the historical web or decision state.
- Local Claude/GitHub configuration was available during replay. The hosted agent
  receives no GitHub token and must fall back to public API/web access. Passing the
  workflow token to the agent was rejected by automatic approval review and was
  not implemented. Hosted authentication/rate-limit behavior remains unverified.
- No PR review, comment, approval, closure, or merge was submitted. The report-only
  integration remains opt-in; the GitHub-hosted end-to-end trial has not run.

The final case reports and `backtests/results.json` retain the guarded decisions,
research records, and comparison metrics. Raw decisions, tool requests, full native
transcripts, and every prior prompt/input snapshot remain in the local acquisition
experiment.

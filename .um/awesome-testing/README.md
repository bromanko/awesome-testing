# Agent-led contribution review

This opt-in GitHub workflow asks Claude to investigate a contribution to
awesome-testing and recommends approve, request changes, or reject. The report
appears in the Actions run summary. It does not submit a review or comment, close
PRs, or merge changes.

## How it works

1. Python reads the exact PR head/base, changed-file patches, both README versions,
   and contribution rules from GitHub. It checks that the PR remains current.
2. UM runs the official Claude Code agent with normal tools. Claude investigates
   the proposed resource, searches submission history, compares listed alternatives,
   and returns a structured decision with sources and unresolved questions.
3. Python checks the report for internal inconsistencies, checks the PR again,
   and renders the summary. Changes during research mark the report stale.

Newly discovered sources are welcome. The source record is the agent's account
of its investigation, not independent verification. Missing research, unsupported
citations, incomplete patches, and uncertain blocking overlap require a maintainer.
Research failures are not automatically evidence that a product is broken.

The collector does not parse entries, choose historical candidates, fetch product
pages, or decide which alternatives Claude should consider. All submitted changes,
including removals and non-README files, are visible to the agent. Only the model
packet and exact request identity cross steps; there are no evidence archives,
replay caches, or hypothetical API action plans.

## Runtime

The workflow uses `useful-machinery/run-action` at
`3b5d29379bc349df8d95b29b599e71701aa1d017` with explicit `um-version: 0.72.1`,
Claude Code `2.1.284`, model `claude-sonnet-5`, and medium effort.
UM 0.57.0 rejected Claude's ToolSearch response during the live pilot; 0.72.1
supports the tool interaction observed in the backtests.

Claude is installed with its official native installer. There is no executable
wrapper, custom tool restriction, or per-invocation dollar cap. The GitHub job has
a 30-minute timeout, and newer events cancel an older run for the same PR.

The model receives the Anthropic key. The collection/report steps receive the
read-only GitHub token. Claude can use public web tools and unauthenticated public
API requests; it should report access/rate-limit failures honestly. The prompt
forbids external changes and execution of submitted code. Normal agent tools are
available; the prompt is not an execution sandbox.

## Enable a fork trial

- Create the `awesome-testing-review` environment with required reviewers.
- Add `ANTHROPIC_API_KEY` as an environment secret.
- Set repository variable `UM_PR_REVIEW_ENABLED=true`.
- Put the workflow on the fork's base branch, then open a non-draft test PR.
- Approve the environment job and read the report in the Actions run summary.

Keep the token's `contents` and `pull-requests` permissions read-only. Set the
opt-in variable to false to stop new runs; cancel running/pending jobs separately.
The code accepts this fork and `TheJambo/awesome-testing`.

## Files

- `workflow.yaml`: UM agent step and structured decision export.
- `prompts/reviewer.md`: investigation task and reporting instructions.
- `schemas/decision.json`: decision and research record format.
- `scripts/collect.py`: exact repository context, without research heuristics.
- `scripts/ci.py`: event identity, freshness checks, preparation, and rendering.
- `scripts/review.py`: consistency checks on the agent's report.

## Validation

```sh
python3 -m unittest discover -s .um/awesome-testing/tests -v
um workflow validate --source-root .um/awesome-testing --json .um/awesome-testing/workflow.yaml
actionlint .github/workflows/um-pr-review.yml .github/workflows/um-pr-review-checks.yml
```

The historical replay uses retained final-head diffs and live research. Target
outcomes and discussions are withheld from the packet and forbidden by the prompt,
but a live search can still reveal later information. Results must be audited and
reported as retrospective comparisons, not blinded or historically frozen accuracy.
The end-to-end GitHub-hosted trial remains separate from local UM backtesting.

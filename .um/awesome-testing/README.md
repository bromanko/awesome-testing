# Contribution review

This UM workflow collects pinned PR evidence, uses Claude to research the
contribution and compare existing entries, then checks and renders an advisory
report. The opt-in GitHub Action runs the workflow and displays its report in the
Actions summary. Inclusion decisions stay with the maintainer; the workflow does
not post comments or reviews, close PRs, or merge changes.

## Setup

1. Add this workflow to the repository's base branch.
2. Create a GitHub environment named `awesome-testing-review` with required reviewers.
3. Add `ANTHROPIC_API_KEY` as an environment secret.
4. Set the repository variable `UM_PR_REVIEW_ENABLED` to `true`.
5. Open or update a non-draft PR, approve the environment job, and open its Actions
   run to read the summary.

Set `UM_PR_REVIEW_ENABLED` to `false` to stop new runs. Cancel any running or pending
jobs separately. Each run uses your Anthropic account, has a 30-minute timeout,
and is cancelled when a newer review starts for the same PR.

## What to expect

The report includes a recommendation, suggested response, and investigation of
submission history and similar entries. Research gaps or inconsistent findings
appear under “Needs your judgment.” The collector also extracts changed resource
URLs and headings from the PR's pinned common ancestor and head README, then checks
those additions against the current pinned target README. Additional occurrences of an
exact existing URL are flagged; moves and description edits are not treated as
new duplicates. Matching does not follow redirects or infer equivalent products,
and extraction covers the list's one-line inline Markdown links.

Recommendations can be wrong, and sources are
reported by the agent rather than independently verified. Check the evidence
before acting. A report is marked stale if the PR changes during the review.

The workflow runs trusted code from the base branch with read-only GitHub
permissions. UM runs collection, Claude review, and final freshness/report checks as
three dependent steps. Actions only installs the tools, supplies the event and
credentials, invokes UM, and displays the exported report.

The job's repository-scoped read-only GitHub token is passed as REVIEW_GITHUB_TOKEN
for authenticated API reads. UM forwards declared credentials to all steps,
including Claude; the job grants no comment, review, or merge permissions. Claude
also receives the Anthropic key and uses its normal research tools. Its instructions
prohibit external changes and running submitted code, but are not an execution
sandbox. Without a GitHub token, public API reads may fail due to rate limits.

## Maintenance

The agent configuration is in `workflow.yaml`, its instructions in
`prompts/reviewer.md`, and its output format in `schemas/decision.json`.
The Python scripts implement the workflow's collection and report command steps.
The workflow accepts a saved GitHub pull-request event as its `event` text input and
exports the final Markdown as `report`. It can run without the Actions wrapper:

```sh
um workflow run --source-root .um/awesome-testing \
  --execution-root .um/awesome-testing \
  --input-text-file event /path/to/event.json .um/awesome-testing/workflow.yaml
```

Use a trusted checkout, Python 3, Claude, and UM 0.72.1. Set ANTHROPIC_API_KEY and
REVIEW_GITHUB_TOKEN (a token limited to read-only access to the target repository).
The event must identify an open, non-draft PR with matching current base/head commits.
Working files stay under the ignored `work/` directory. Do not run two reviews in
the same execution directory concurrently.

Run the offline tests without an API key:

```sh
python3 -m unittest discover -s .um/awesome-testing/tests
```

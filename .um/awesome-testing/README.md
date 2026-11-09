# Contribution review

This opt-in GitHub Action uses Claude to research a contribution, compare it with
existing entries, and suggest a response. Read the report in the Actions run
summary. Inclusion decisions stay with the maintainer; the workflow does not post
comments or reviews, close PRs, or merge changes.

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
appear under “Needs your judgment.” Recommendations can be wrong, and sources are
reported by the agent rather than independently verified. Check the evidence
before acting. A report is marked stale if the PR changes during the review.

The workflow runs trusted code from the base branch with read-only GitHub
permissions. Claude receives the Anthropic key and uses its normal research tools;
it does not receive the GitHub token. Its instructions prohibit external changes
and running submitted code, but those instructions are not an execution sandbox.

## Maintenance

The agent configuration is in `workflow.yaml`, its instructions in
`prompts/reviewer.md`, and its output format in `schemas/decision.json`.
The Python scripts collect PR context, check the report, and render the summary.

Run the offline tests without an API key:

```sh
python3 -m unittest discover -s .um/awesome-testing/tests
```

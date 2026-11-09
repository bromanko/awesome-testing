# awesome-testing PR review with Useful Machinery

A dry-run port of the contribution-review experiment. The GitHub workflow collects
public evidence, runs the existing Sonnet review through the **UM run action**,
and retains a proposed decision/comment. It does not post comments, submit reviews,
approve, close, or merge PRs. There is no GitHub write executor.

## Current status

The integration is prepared for `bromanko/awesome-testing`. Model runs are disabled
unless `UM_PR_REVIEW_ENABLED` is exactly `true`. Creating the fork or publishing
these files does not set that variable, create an environment, or add credentials.
A hosted GitHub run and live model trial remain unverified.

- Trigger: `pull_request_target` on opened, synchronize, reopened, edited, and
  ready-for-review events. Drafts are skipped.
- Trust boundary: code, prompt, schema, and workflow always come from the **base
  commit**, never the PR head. The PR README/diff/body are API-fetched data only.
- Model: `claude-sonnet-5`, effort `low`, maximum API budget $1 per invocation.
  Repeated PR events can incur repeated charges after enablement. Workflow
  concurrency cancels an older run for the same PR; it is not a global spend cap.
- Reports: `review.md`, `decision.json`, `action-plan.json`, and the exact PR
  identity. The action plan is explicitly hypothetical. Artifact retention is
  seven days. The evidence packet stays on the runner and is passed between steps as a local file.

## Files and responsibilities

- [GitHub workflow](../../.github/workflows/um-pr-review.yml): trusted checkout,
  one protected job for collection and review, followed by report upload.
- [Offline CI checks](../../.github/workflows/um-pr-review-checks.yml): tests on
  ordinary PRs without provider secrets or a privileged PR context.
- [UM workflow](workflow.yaml): the existing evidence-only agent review and
  schema-validated `decision` JSON export.
- `scripts/collect.py`: fork-specific PR evidence plus upstream submission history.
- `scripts/public_http.py`: unauthenticated, public-IP-pinned HTTP(S) requests.
- `scripts/ci.py`: event validation, freshness checks, preparation, report rendering.
- `scripts/review.py`: pure evidence guards and hypothetical request descriptions.
- `bin/claude`: no tools, skills, hooks, plugins, ambient settings, or MCP servers.
  It preserves UM's native stream/result protocol and permission-mode argument.

## Version contract

The run action is pinned to the verified public revision
[`0572ca6153d1d030a1490d2f46298264aebd1cb3`](https://github.com/useful-machinery/run-action/tree/0572ca6153d1d030a1490d2f46298264aebd1cb3).
That revision installs checksum-verified **UM 0.57.0**, not the local experiment's
0.72.1. The workflow validates with 0.57.0. Claude Code is pinned to **2.1.284**,
installed with the official native installer; no Node.js setup is needed.
Other GitHub Actions are pinned to full commit SHAs.

The [upstream action's native checks passed for this exact revision](https://github.com/useful-machinery/run-action/actions/runs/37415128498).
The action's named Text input carries the prepared packet by file path, and its
selected JSON export hands the result to the report step. No alternate direct UM
CLI launcher is used by the GitHub workflow.

## Enable deliberately, after reviewing the code

These are future setup steps, not actions already performed:

1. Review and land these files in the fork's default branch, `master`.
   `pull_request_target` uses base-branch code, so a PR adding this integration
   cannot exercise its own new review workflow. Do not switch checkout to the PR
   head to work around this.
2. In the fork, create an environment named `awesome-testing-review`. Configure
   **required reviewers**, prevent self-review if appropriate, and restrict which
   branches can use it. Merely naming an environment in YAML does not enforce
   approval. Confirm the protection works before enabling the workflow.
3. Add `ANTHROPIC_API_KEY` to that protected environment, not as a repository-wide
   secret. This transmits public PR/repository evidence to Anthropic and permits
   provider usage. Use a purpose-specific budget-limited key. No GitHub PAT or
   write token is needed. Credential creation/configuration needs separate approval.
4. Set repository variable `UM_PR_REVIEW_ENABLED=true`. Keep GitHub token
   permissions read-only. The job requests only `contents: read` and
   `pull-requests: read`; allow ordinary required artifact actions if your
   organization has an action allowlist.
5. Open a small README-only test PR **against Brian's fork**. Approve the protected
   environment job, inspect the Actions run, and download the report. Verify the
   report's exact head SHA. No contributor-facing message will be sent.
6. Set `UM_PR_REVIEW_ENABLED=false` to stop new model jobs. Cancel any already
   running or pending job separately. Do not add auto-approval/publication until
   that behavior and its permissions have been explicitly reviewed.

## Evidence and safety

The collector checks repository, PR number, open/non-draft state, **head and base
SHA** before collecting, after collecting, immediately before the model, and after the model. Environment approval happens
before the combined job starts. Stale reports require human
review and contain no hypothetical requests. PR content is never interpolated
into shell commands or GitHub file-command outputs.

It searches the upstream list's fully paginated PR history rather than confusing
fork PR numbers with upstream PR numbers. It keeps the existing prompt, JSON
schema, current curator calibration, and URL citation allowlist. The public
maintainer statements retained in `evidence/maintainer-precedents.json` carry
source links and dates; they are a policy snapshot, not a live subscription.
The target PR's own comments/reviews/outcome are not model inputs.

The old experiment's `restqa/404-links` checker is **not run against arbitrary PR
URLs** in this job. That checker did not enforce the network boundary needed for
hostile PRs. This port replaces that check with bounded HTTP(S) GETs of every link
in proposed entry lines, checks each DNS answer/redirect, and connects directly
to an inspected public IP with normal TLS hostname verification. It rejects
private, loopback, link-local, multicast, shared-address, and IPv6 transition
destinations. Each request has a 35-second process deadline, five redirects, and
a 512 KiB response cap (1 MiB for public GitHub README JSON). The network process
receives no GitHub or provider credentials and ignores ambient proxies.

This is **not identical to the old link-checker result**, and it does not establish
that every existing README link works. The upstream `404-links.yml` is unchanged.
Limits are ten proposed entries, twenty checked URLs, fifty changed files, and a
512 KiB model packet. Missing or partial patches, extra prose, non-README changes,
unrecognized removals, unavailable sources, failed checks, and unsupported
citations require human review or stop preparation. New category headings and
recognized entry updates remain supported. A model judgment is not a security
boundary or a guarantee of curation quality.

A blocking duplicate or coverage-overlap finding below high confidence always
requires a maintainer, even if the model sets `humanReview=false`. Missing
confidence also fails closed. The guard preserves the tentative recommendation
and records why the comparison needs review. It runs again when building the
action plan, so callers cannot bypass it by passing a raw model result. Such
reports contain no hypothetical comment, review, or close requests.

The prompt requires decision-driving overlap concerns to be blocking `duplicate`
findings, with a tentative comment and a clear maintainer question when uncertain.
Advisory observations and high-confidence decisions retain their existing routing;
all evidence, citation, link, and stale-PR checks remain in place. This conservative
routing fix is ported from the contribution-review experiment's commit `c869d0f`.
It is not evidence that model confidence is calibrated or that overlap accuracy
has improved. The revised prompt still needs a controlled live evaluation.

No raw Claude sessions, configuration directories, execution directories, API
keys, or local experiment result archives are uploaded. The only model artifact
is the guarded report. GitHub Actions artifacts in a public repository may be
accessible to people who can read the repository; submit public data only.

## Local verification

From the fork checkout:

```sh
python3 -m unittest discover -s .um/awesome-testing/tests -v
python3 -m py_compile .um/awesome-testing/scripts/*.py
um workflow validate --source-root .um/awesome-testing --json \
  .um/awesome-testing/workflow.yaml
actionlint .github/workflows/um-pr-review.yml \
  .github/workflows/um-pr-review-checks.yml
```

Use UM **0.57.0** for the compatibility check. Offline tests need only Python 3.12+
and never call GitHub or a model. The live workflow also needs GitHub CLI, Python,
and the pinned Claude harness; GitHub-hosted Ubuntu supplies `gh`.

Verification completed locally on macOS ARM64:

- 55 offline regression tests, including a mocked prepare-to-report pipeline and
  uncertain-overlap guards at the decision, raw action-plan, and CI report boundaries.
- Offline replay of all 32 retained experiment cases through the ported guard:
  maintainer routes increased from 18 to 21. Endtest (Opus low) and Persqo (Opus low
  and high) now emit zero hypothetical requests; the other 29 routes and request
  counts are unchanged. No model calls, source refreshes, or archive edits occurred.
- Python compilation, actionlint 1.7.12 with shellcheck, and UM 0.57.0 validation.
- Exact pinned run-action execution with a synthetic command-only workflow,
  named Text packet, schema-validated JSON decision, and available export path.
- Claude 2.1.284 installation/version and wrapper flag parsing, without authentication
  or provider requests.
- Hardened HTTP fetch of the public upstream GitHub repository.

The command-only smoke test proves action input/export plumbing, **not** Claude's
live structured-result behavior or GitHub-hosted event/environment/artifact wiring.
Those remain the first controlled fork trial after publication and explicit setup.

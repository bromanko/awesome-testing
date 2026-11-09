# Preregistered fresh-case evaluation

Frozen before fresh PR content/outcome reasons are inspected, 2026-11-09.

The original spike did not establish a high unbiased accuracy figure. It mixed
known-case calibration, new cases, current policy derived from later closures,
and abstentions. Recover useful review quality, not an unsupported target number.

## Split and stopping rule

`split.json` fixes ten already-seen calibration cases and sixteen new holdout
cases. Eight merged and eight closed-unmerged PRs are sampled by a fixed hash from
cached PRs numbered at least 200. All previously collected cases/prior evidence
and known resource-family title matches are excluded. This is a balanced diagnostic
sample, not a natural-prevalence sample. A closed-unmerged PR is not automatically
a maintainer rejection; evaluator-only discussions/events establish the label.
Unknown, withdrawn or ambiguous outcomes remain visible and unscored. Do not
replace a case because evidence is difficult or its result is unfavorable.

Use one proposed rubric, frozen before seeing holdout content, with Sonnet and
Opus at medium effort. Evaluate both on calibration. Choose the model by the
number of correct non-abstaining inclusion decisions on the eight labeled
calibration cases; break ties by fewer false approvals, then lower reported cost.
Abstentions earn no correct-decision credit. The selected model and rubric are
locked before holdout predictions. No further tuning after holdout results.

Run the selected model with both the rubric and the prior detailed agent prompt
on all sixteen holdout cases. The same schema, tool restrictions and per-case
evidence apply. No calibration-result comparison is presented as validation.

## Evidence and isolation

Reuse native Claude restricted mode, safe mode, explicit Read/Glob/Grep tools,
empty MCP config, no session persistence, and one case-specific working directory.
No GitHub credential is passed to model processes. Evaluation labels, other model
outputs, and target discussion remain outside the accessible directory. Original
prompt transport instructions are adapted to native schema output for both arms.

Both arms receive the exact PR changes, pinned README/rules and official sources.
Additional alternative sources are selected by a generic category/lexical rule,
not target outcomes. Provide the category entries even when documentation cannot
be fetched. Exclude all holdout outcomes from every corpus, including cross-case
history. Prior history titles can be searched but are not proof of contents.
Evidence collection failures are retained. Current websites and final-head diffs
are not historically frozen evidence; report this limitation.

## Measurements

`inclusion` is include/exclude/abstain. `decision` separately records approve,
request_changes, reject or abstain. This permits a correctable factual defect in
an otherwise includable tool without relabeling it as exclusion. The previous
prompt receives the same schema and output definitions. This is an explicit
measurement change, not a retroactive improvement to earlier 2/8 scores.

Report both exact action agreement and inclusion agreement. For inclusion report
correct decisions / all labeled cases, false approvals, false rejections,
abstentions, coverage and accuracy among non-abstentions. Publish always-include
and always-exclude baselines. Do not count a hold as a correct rejection or inflate
headline accuracy by dropping held cases. Keep costs and malformed-output retries.

The rubric operationalizes calibration patterns; it is a proposed maintainer
policy, not a claim that the maintainer has endorsed every sentence. Fresh-case
results determine whether it generalizes. One trial per arm/case remains a small
diagnostic study, not a production guarantee. Production workflow stays unchanged
until results justify a concrete change.

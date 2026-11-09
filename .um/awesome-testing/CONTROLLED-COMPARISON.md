# Controlled Sonnet / Opus comparison — 2026-11-09

Opus with the detailed prompt improved historical agreement by one case. Removing research tools did not improve agreement; shortening the prompt lost that improvement. This does not justify a production model change yet.

## Results

All 44 reviews completed successfully. Each arm reviewed the same 11 cases at medium effort using Claude Code 2.1.284. Eight cases have historical approve/reject labels; three are qualitative checks. Agreement is not an accuracy estimate, and a human-review hold is not counted as a correct rejection.

| Variant | Agreement | Model asks for human review | After existing guard | Reported cost | Mean seconds |
| --- | --- | --- | --- | --- | --- |
| Sonnet, detailed agent | 2/8 | 6/11 | 11/11 | $4.82 | 112.2 |
| Opus, detailed agent | 3/8 | 8/11 | 9/11 | $5.63 | 55.3 |
| Opus, short brief | 2/8 | 6/11 | 11/11 | $6.56 | 81.7 |
| Opus, fixed packet | 3/8 | 9/11 | 10/11 | $7.24 | 36.1 |

Total CLI-reported list-price estimate: $24.26, plus $0.021 for the isolation probe. These are not necessarily billed amounts.

## Paired recommendations

`A` = approve, `C` = request changes, `R` = reject. `*` means the existing guard requires human review.

| PR | Historical reference | Sonnet detailed | Opus detailed | Opus brief | Opus fixed |
| --- | --- | --- | --- | --- | --- |
| [#34](https://github.com/TheJambo/awesome-testing/pull/34) | category objection | C* | C | C* | C |
| [#35](https://github.com/TheJambo/awesome-testing/pull/35) | approve | A* | A* | A* | A* |
| [#81](https://github.com/TheJambo/awesome-testing/pull/81) | author withdrew | R* | R* | R* | R* |
| [#107](https://github.com/TheJambo/awesome-testing/pull/107) | reject | A* | A* | A* | A* |
| [#297](https://github.com/TheJambo/awesome-testing/pull/297) | reject | A* | A* | A* | A* |
| [#333](https://github.com/TheJambo/awesome-testing/pull/333) | approve | A* | A* | A* | A* |
| [#347](https://github.com/TheJambo/awesome-testing/pull/347) | reject | A* | R* | A* | R* |
| [#354](https://github.com/TheJambo/awesome-testing/pull/354) | approve | C* | C* | C* | R* |
| [#360](https://github.com/TheJambo/awesome-testing/pull/360) | author withdrew | A* | A* | A* | A* |
| [#362](https://github.com/TheJambo/awesome-testing/pull/362) | reject | A* | A* | A* | A* |
| [#370](https://github.com/TheJambo/awesome-testing/pull/370) | reject | A* | A | A* | A* |

## What the comparison shows

- **Model:** the matched Sonnet and detailed Opus arms differed on #347. Opus rejected the disposable-email API because keyless access did not add a new testing task. Sonnet approved it. The other ten raw recommendations matched.
- **Prompt:** the short Opus brief also approved #347, treating keyless access as meaningful value. It did not improve historical agreement and generated generic limitations in every report, which the existing guard turned into holds. This is one short brief, not evidence that every concise prompt is worse.
- **Agency:** detailed Opus with research tools and fixed-packet Opus had the same historical agreement. Their only raw recommendation difference was #354: the agent asked for a factual correction; the fixed packet rejected over overlap. Removing research tools did not resolve the curation disagreements.
- **Basic review quality:** every arm caught the misplaced Security entry in #34 and the explicit unit-testing scope conflict in #81. The earlier live Sonnet pass missed both. Because the environment and evidence changed, the improvement cannot be attributed to Opus.
- **Remaining curation gap:** every arm approved #107, #297, #362 and #370 despite historical rejections. Several reviews clearly described overlap but still chose tentative approval with a maintainer question. SMTP capture in #362 and passive browser monitoring in #370 were treated as possible distinct needs. Whether those distinctions warrant another entry is the policy question.
- **Historical labels have limits:** #354 was merged, but current Persqo pricing says $49 while the submitted description says $59. Requesting a correction is defensible given the current evidence, even though it disagrees with the historical acceptance.
- **Grounding has limits:** #370 comparisons rely partly on the base README description of Keploy API Test Recorder; its full documentation was not in the frozen corpus. Claims that no alternative offers a feature are therefore stronger than the available evidence supports.

## Method and limits

The fourth arm is a matched Sonnet control. Its earlier live-web run was not used as the control because tools, sources and outcome exposure differed. Models were `claude-sonnet-5` and `claude-opus-5-5`, all at medium effort.

All arms had the same frozen per-case corpus: exact submitted edits, pinned README/rules, current official-source excerpts, nearby alternatives, and time-filtered prior-submission evidence. Agent arms could choose documents with Read/Glob/Grep; the fixed arm received every document inline. The common execution instructions replaced live-web research and UM transport with offline research and native structured output. This measures evidence selection and judgment within a finite corpus, not unrestricted web agency.

Native restricted mode confined each model to its own case folder. A canary verified that an outside-file read was denied. Safe mode, an explicit tool list and strict empty MCP configuration removed external research and command tools. Tool inventories and traces were audited. Target discussion/outcome files and scoring labels stayed outside the accessible folders. No unexpected tools were used, and claimed product-source URLs matched the supplied corpus. This does not rule out information in model pretraining.

All 161 corpus documents were hash-checked after execution. History indexes excluded the target and submissions at/after its creation; comments had to be both created and last updated before that cutoff. Prior diffs/titles may reflect later edits. Current source pages do not reconstruct the historical web. Source excerpts and manually selected alternatives can omit useful evidence.

One run per arm per case, with cases already used for prior prompt tuning: these are diagnostic paired observations, not a fresh holdout or statistical model ranking. Prompts and corpus stayed unchanged throughout the scored runs. Four schema-dialect startup failures were preserved separately; removing the unsupported dialect URI let the unchanged schema constraints run. Native structured-output retries and file-read size limits affected cost and duration, so these timing numbers are specific to this harness.

## Next decision

Keep the production model and agent workflow unchanged for now. Define the curator’s inclusion threshold more clearly—especially when overlap is sufficient to exclude an otherwise useful tool—and separate that discretionary judgment from factual corrections. Then compare on fresh cases with needed alternative documentation available. The evidence supports keeping deterministic collection, outcome isolation and output validation; it does not support replacing substantive review with a classifier or assuming Opus alone solves the problem.

Full prompts, frozen evidence, transcripts, final decisions, guard results and receipts are retained in the acquisition workspace under `targets/awesome-testing/agent-review/comparison/`. The production workflow and draft PR body are unchanged.

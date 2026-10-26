# Qualified generation experiment, 2026-10-26

**Historical protocol:** the seven-sentence screens below were superseded by the [200-word axis-matched protocol](AXIS_MATRIX_AND_OA_VALIDATION.md), whose current operational threshold is 7/10 per ten-paper cohort. Do not use these historical 5/6 results as current evaluator eligibility.

## Basis and frozen order

Research basis: [Wang et al. (2025)](https://aclanthology.org/2025.findings-emnlp.532/), plus its direct reference [Bhandarkar et al. (2024)](https://aclanthology.org/2024.personalize-1.6/) for the author-prefix setting. The older card pilot is auxiliary. Gate human text first; then prepare all conditions; then score independent generations and semantics. No prompt or feature is selected from the new generation results.

Wang et al.'s Table 6 compares five-shot and five-shot-plus-snippet, where the snippet is the **first min(50 words, 20%) of the target test text**, not the beginning of a different paper. Only the model's continuation is scored. The clearest +Snippet gain is the AI detector's human classification; authorship and stylistic measures have mixed changes across genres. The paper's Table 5 uses SBERT as a semantic sanity check. Neither the detector result nor its SBERT values transfer as an acceptance threshold to life-science manuscripts.

## 1. Human evaluator eligibility

`pentwin qualify-eval COHORT_A.json COHORT_B.json` rejects reused papers and screens each frozen feature independently: at least 5/6 with at least 2/3 per writer in **both** cohorts. This is an operational filter, not a significance test. The cohorts were previously inspected; fresh disjoint human texts are still needed for external confirmation.

| Feature | Cohort A | Cohort B | Decision |
| --- | ---: | ---: | --- |
| Fixed function-word rates | 5/6 | 5/6 | Descriptive primary candidate |
| Sentence length + punctuation | 5/6 | 2/6 | Exclude from primary |

In cohort B, sentence length alone recognized 2/6 and the three punctuation rates together recognized 2/6. With a first-five-sentence window, the combined score was 3/6; with seven it was 2/6; with ten it was 3/6. Punctuation alone stayed at 2/6 throughout. In seven-sentence windows many semicolon, parenthesis and question rates were zero, and a single event changed a rate by roughly one seventh. This supports **sparse/unstable surface markers plus variable sentence length** as the observed bottleneck. There is no syntactic parser in this feature set, and no domain vocabulary term, so parser mismatch and direct topic-word noise cannot be the immediate mechanism. Editorial/topic differences may still alter length and punctuation indirectly. The six texts do not identify a unique causal source. Window length was **not** tuned to improve the result.

The function-word set is a limited primary candidate: it may miss lexical choices and explanation order altogether. It is not a complete author-voice evaluator. These cohorts contain short editorials, not life-sciences research manuscripts; drafting roles and topic/time controls are incomplete. The previous `paper-eval` single-cohort generated score is marked unqualified; new comparisons use both cohorts via `factorial-eval`. The 5/6 screen can occur by chance in six trials and does not validate a general model.

## 2. Factorial ablation

MCP `generation_protocol(section)` emits a generic baseline and all seven nonempty combinations of three axes: A, wording/lexical preference; B, qualified versus direct assertions in the **last ten words** of sentences; C, visible explanation-cue order. The ending axis uses fixed generic patterns in two development papers and abstains if absent. Every condition records its available axes. Match the user-supplied brief, word count, model and settings. `pentwin factorial-eval COHORT_A.json COHORT_B.json CASES.json --sbert-model-dir LOCAL_MODEL` accepts paired cases for two writers and at least two briefs, with seven conditions each. An eighth, `all_snippet`, is optional. It records per-condition change from the same generic baseline, without pooling failed structure into the primary score.

The **older**, deterministic 16-draft probe contains wording, cue order, broad stance and their combination across two briefs and two writers. Rescored against the new frozen reference profiles, function-word improvement was 0/4 for wording, 0/4 for cue order, 2/4 for broad stance and 2/4 for combined. The surface-structure metric improved 0/4 for all four. The wording and order edits left the measured function words unchanged, so those 0/4 values are **lack of metric sensitivity**, not proof that the edits failed. The broad stance edits are not the new sentence-ending intervention. The probe has neither the three pairwise combinations nor independent host-model generations, so it cannot identify factorial interactions or a causal trade-off. The new CLI rejects an incomplete seven-condition set rather than filling combinations with invented drafts.

## 3. +Snippet condition

`generation_protocol(section, target_text, confirmed_author_written=true)` takes a **separately supplied human-authored target** and appends `all_snippet` to the eight conditions. It returns at most 50 words or one fifth of the target, whichever is shorter; it rejects a prefix drawn from the sealed calibration corpus. The original full target and its author are not published. The client must output a continuation only; `factorial-eval` rejects a continuation that starts by repeating its private anchor. Comparison is `all` versus `all_snippet` under the same brief/model/length. A prefix from a different author paper does not reproduce Wang et al.'s intervention.

## 4. Semantic screen

The optional `semantic` dependency loads an explicitly provided **local** SentenceTransformer model with offline loading and remote code disabled. Cosine similarity compares every **continuation alone** with the same content brief. The generic baseline must reach 0.70; a condition must not fall more than 0.05 below that baseline. These are provisional engineering cutoffs for a paired sanity check, **not** the paper's SBERT scores and not factual verification. If a model is missing, the report says `semantic_unavailable` and makes no pass decision. If the baseline itself fails, no condition passes. Scientific claim checking remains a separate task.

## Verification and outstanding evidence

The two previously assembled six-paper cohorts gave the gate values above. MCP stdio tests check the eight conditions and an independently provided target prefix. Synthetic tests check duplicate-cohort rejection, incomplete factorial rejection, continuation-only handling, semantic pass/fail arithmetic, and offline failure. No local SBERT model or OpenAI/Claude API credentials were available during this run, and the old drafts have no seven-condition factorial or new author target prefixes. Therefore **no real GPT/Claude factorial or +Snippet effect, nor a real SBERT score, is reported**. The code fails closed on these missing inputs. Before claiming a generator advantage, obtain fresh human calibration cohorts and independently generated complete paired outputs, then run the frozen protocol without retuning thresholds.

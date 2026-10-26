# Axis-matched evaluation and OA validation, updated 2026-10-27

## Decision order

This is the current protocol. The earlier six-paper and seven-sentence results are historical. Require at least 200 measurable English words, then screen each metric on two disjoint **ten-paper** cohorts: two authors × five papers each, with four independent reference papers per withheld article on each side. Each axis needs at least **7/10**, at least **3/5 per author**, and all ten cases measurable in **each** cohort. A failed axis cannot contribute a positive generator judgment. A fair two-choice guess reaches at least seven in 176/1024 independent trials; these overlapping leave-one-out decisions are not independent. This is an operational exploration threshold, not a significance test or estimated deployment accuracy. The authors, papers and metric refinement were inspected during development, so passing these cohorts is not an independent replication.

| Generation axis | Matching metric | Possible distortion |
| --- | --- | --- |
| A: lexical wording | Jaccard over the pre-existing, fixed generation-card vocabulary of generic connectors and reporting verbs; raw English content-word Jaccard must independently pass 7/10 and is also reported. Reviewed technical-term coverage is separate. | Raw content overlap includes subject matter, citation artifacts and recurring technical terms. The fixed card vocabulary better matches what the generator actually requests, but journals and coauthors can still confound it. |
| B: sentence ending / claim strength | Equal-weight distance of fixed function-word rates and qualified/direct expressions in the last ten words of sentences | Fixed surface patterns do not parse English morphology, rhetorical force or grammatical endings. |
| C: explanation order | Relative frequencies of successive, visible discourse-cue labels | Fewer than two cue transitions in a passage or reference cause abstention. Marker order is not a full argument structure. |

`pentwin qualify-eval FIRST.json SECOND.json` checks the mapping **per axis**. `factorial-eval` scores each variant only against its own matching metric; unavailable metrics remain `null`. It also reports coverage and semantic scores without pooling unlike quantities. The cohorts and generated texts are never returned.

Each human cohort report includes descriptive passive-voice and fixed academic-phrase rates to expose domain-specific surface shifts. The passive expression is a regular-expression approximation, not a syntactic parse. These diagnostic rates do not enter any axis acceptance score.

## Minimum length and observed gate

The source window ends at the first complete sentence reaching **at least 200 English words**. Every generic draft and every variant or +Snippet continuation also needs 200 measurable words. A shorter passage is rejected, not treated as zero markers. The prior two private six-paper editorial cohorts had the following **historical** values at 200 words; they are not valid inputs to the 7/10 gate:

| Historical axis | Cohort 1 | Cohort 2 | Availability | Current eligibility |
| --- | ---: | ---: | --- | --- |
| Content Jaccard | 4/6 | 4/6 | 6/6 in each | Ineligible: six papers |
| Function words + ending patterns | 5/6 | 4/6 | 6/6 in each | Ineligible: six papers |
| Discourse-cue transitions | 0/6 | 0/6 | 0/6, then 1/6 | Ineligible: six papers |

Their earlier 4/6 permission was a retrospective exploration rule and has been superseded. The old function-word-only 5/6 and 5/6 at seven sentences became 5/6 and 4/6 at 200 words. Neither set establishes life-science performance or author voice.

## Local input injection

`factorial-eval FIRST.json SECOND.json CASES.json --semantic-scores SCORES.json` and MCP `offline_evaluate(first_manifest, second_manifest, cases_file, semantic_scores_file)` read files from absolute, private paths. No GPT/Claude API or local SBERT model is required. A case has anonymous IDs, `model`, `section="discussion"`, `content_brief`, `baseline`, and `variants`. The original full design still accepts all seven card conditions: `lexical`, `ending`, `order`, `lexical_ending`, `lexical_order`, `ending_order`, `all`. The reduced design accepts **every nonempty combination of the axes that passed the gate**. For the OA life-science cohorts here, that is just `lexical`; `lexical_snippet` may be added with `snippet_anchor` to compare the original card against +Snippet. Use at least two briefs and both writers for each, with identical variant labels in every case. Every snippet variant is the **continuation only**, excluding the human opening. Identical briefs, baseline, section and model are required across the paired writers. The report's `improved_and_semantic_pass` count is available only for eligible axes with semantic scores; it is still descriptive, not a voice-authenticity verdict.

The optional score JSON has `model`, `metric="cosine"` and a `cases` list. Each case needs its `case_id`, SHA-256 of the exact UTF-8 content brief as `reference_sha256`, and a `scores` object containing `none` and exactly the variant labels. Each score entry needs `sha256` of its exact UTF-8 generated text and a finite cosine `similarity` in [-1, 1]. A missing/mismatched hash or case rejects the entire report. Imported scores are **asserted by the supplier**; hashes bind them to texts but cannot prove that SBERT actually produced them. The provisional generic floor 0.70 and maximum relative decline 0.05 still apply. With neither imported scores nor a local model, semantic assessment is unavailable. MCP never publishes raw drafts or source passages in its result.

`pentwin semantic-template CASES.json PRIVATE_SCORES.json` creates the exact IDs and hashes with blank similarities. Score the same brief, baseline and each continuation using one fixed SBERT model, then fill every similarity and the model identifier before importing. The template contains no prose.

## OA life-science corpus check

The current corpus uses four credited original drafters × five distinct CC BY open-access biomedical research papers. `pentwin fetch-pmc PMCID PRIVATE.xml` uses the official Europe PMC OA fullTextXML endpoint. After review, a private ten-entry specification lists XML paths, anonymous writer/paper IDs, PMCID, one stratum and `primary_drafter_verified=true`. `pentwin prepare-pmc PRIVATE_SPEC.json PRIVATE_OUTPUT` checks unique IDs, CC BY license, research-article type, matching PMCID, one top-level Discussion section, and at least 200 words; it writes a private diagnostic manifest. The six-entry format remains available for historical diagnostic replays, but `qualify-eval` rejects it. Review XML paragraph boundaries, drafting contributions and topic/journal/time matching before interpreting scores.

Twenty distinct CC BY research articles were retrieved into a **private** corpus: four credited original drafters, five papers each, with Discussion sections and a broad biomedical Mendelian randomization topic. Contributor groups do not cross the paired writers. One writer has a paper on which several contributors share original-draft credit; many papers in another group also credit multiple drafters. Publication periods overlap within each cohort, but journals and specific biomedical questions differ. The initial twelve papers were previously inspected, eight were subsequently added, and the choice of the fixed card-vocabulary metric was made after seeing raw content-word results. **This is an exploratory development set, not an untouched external confirmation.** IDs, names, passages, and attribution stay private.

| OA cohort | Card-vocabulary Jaccard | Raw content Jaccard | Function words + ending | Discourse order |
| --- | ---: | ---: | ---: | ---: |
| Cohort 1, 10 papers | 9/10 (4/5, 5/5) | 10/10 | 5/10 (1/5, 4/5) | 1/4 measurable |
| Cohort 2, 10 papers | 9/10 (5/5, 4/5) | 10/10 | 8/10 (3/5, 5/5) | 2/5 measurable |

Under the **7/10 operational gate**, only the lexical axis passes both cohorts, including the separate raw-content check. Ending fails in cohort 1 despite reaching 8/10 in cohort 2; order has insufficient measurable cases. A journal-only comparator abstains on 9/10 in cohort 1, but correctly classifies all **9/9 available** cases in cohort 2, matching the card-vocabulary score of 9/10. Shifting every 200-word window past the first sentence yields 10/10 in cohort 1 but only 6/10 in cohort 2. These additional checks were performed after seeing the main results and are sensitivity diagnostics, not a tuned replacement gate. The lexical score in cohort 2 cannot be separated from journal or opening-specific effects. Passive-voice and formulaic-expression rates remain descriptive domain diagnostics. There is still **no independently verified author-voice or generated-text improvement claim**.

Two private five-paper sealed runs were also prepared for the first cohort, with four development papers and one holdout per writer. Their structured JATS Discussion text survived an exact DOCX round trip; 31 and 47 extracted paragraphs were reviewed and sealed. Real stdio MCP calls returned available lexical instructions for both writers. The order and ending plans may also be mechanically available from the card, but their human evaluator axes failed and must not be promoted to positive outcomes. No independently sampled GPT/Claude continuations or verified SBERT scores were available for a generation result.

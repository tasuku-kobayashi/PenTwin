# Axis-matched evaluation and OA validation, updated 2026-10-27

## Decision order

This is the current protocol. The earlier seven-sentence 5/6 and 2/6 results were exploratory and are **not** carried forward after changing passage length. Select metrics, require 200 measurable English words, test withheld human papers, and only then inspect generated drafts. For two disjoint six-paper cohorts, each axis now needs at least **4/6** correct, at least **1/3 per author**, and six measurable cases in **each** cohort. A 1/3 versus 3/3 split is flagged as writer imbalance. A failed axis cannot contribute a positive generator judgment. The threshold was lowered after observing these cohorts, so passing them is a **retrospective exploration permission**, not an independent validation result. Even for six independent fair two-choice guesses, 4/6 or better occurs 22/64 times; these overlapping leave-one-out trials do not satisfy that independence assumption.

| Generation axis | Matching metric | Possible distortion |
| --- | --- | --- |
| A: lexical wording | Jaccard of English content-word types (fixed function-word exclusion); optional coverage of a separately reviewed technical-term list | Subject matter and recurring technical terms can masquerade as personal style. Term coverage is reported separately, not treated as a style score. |
| B: sentence ending / claim strength | Equal-weight distance of fixed function-word rates and qualified/direct expressions in the last ten words of sentences | Fixed surface patterns do not parse English morphology, rhetorical force or grammatical endings. |
| C: explanation order | Relative frequencies of successive, visible discourse-cue labels | Fewer than two cue transitions in a passage or reference cause abstention. Marker order is not a full argument structure. |

`pentwin qualify-eval FIRST.json SECOND.json` checks the mapping **per axis**. `factorial-eval` scores each variant only against its own matching metric; unavailable metrics remain `null`. It also reports coverage and semantic scores without pooling unlike quantities. The cohorts and generated texts are never returned.

Each human cohort report includes descriptive passive-voice and fixed academic-phrase rates to expose domain-specific surface shifts. The passive expression is a regular-expression approximation, not a syntactic parse. These diagnostic rates do not enter any axis acceptance score.

## Minimum length and observed gate

The source window now ends at the first complete sentence reaching **at least 200 English words**. Every generic draft and every variant or +Snippet continuation also needs 200 measurable words. A shorter passage is rejected, not treated as zero markers. The existing two private six-paper editorial cohorts were previously measured at 200 words. The new rule changes eligibility, not those measurements:

| Axis | Cohort 1 | Cohort 2 | Availability | Eligible? |
| --- | ---: | ---: | --- | --- |
| Content Jaccard | 4/6 | 4/6 | 6/6 in each | Yes, exploratory |
| Function words + ending patterns | 5/6 | 4/6 | 6/6 in each | Yes, exploratory |
| Discourse-cue transitions | 0/6 | 0/6 | 0/6, then 1/6 | No |

Even the former function-word-only score becomes 5/6 and 4/6 at the new passage length; the old 5/6 and 5/6 does not survive. Lexical and ending axes now pass only the weak operational gate. The explanation-order scorer mostly abstains because the required transitions are absent; lowering the correct-count threshold does not fix its availability. These are editorials with topic, publication-period and original-drafter confounds; they do not establish performance on life-science manuscripts. There is no independent generated-style success claim. If generating drafts now, report only lexical and ending margin changes against paired generic drafts, separately for each writer, and score +Snippet as a distinct intervention. Report order descriptively or as unavailable, never as a pass. Semantic scores must pass their own guard before interpreting a style gain.

## Local input injection

`factorial-eval FIRST.json SECOND.json CASES.json --semantic-scores SCORES.json` and MCP `offline_evaluate(first_manifest, second_manifest, cases_file, semantic_scores_file)` read files from absolute, private paths. No GPT/Claude API or local SBERT model is required. A case has anonymous IDs, `model`, `section="discussion"`, `content_brief`, `baseline`, and `variants`. The original full design still accepts all seven card conditions: `lexical`, `ending`, `order`, `lexical_ending`, `lexical_order`, `ending_order`, `all`. The reduced design accepts **every nonempty combination of the axes that passed the gate**. For the OA life-science cohorts here, that is just `lexical`; `lexical_snippet` may be added with `snippet_anchor` to compare the original card against +Snippet. Use at least two briefs and both writers for each, with identical variant labels in every case. Every snippet variant is the **continuation only**, excluding the human opening. Identical briefs, baseline, section and model are required across the paired writers. The report's `improved_and_semantic_pass` count is available only for eligible axes with semantic scores; it is still descriptive, not a voice-authenticity verdict.

The optional score JSON has `model`, `metric="cosine"` and a `cases` list. Each case needs its `case_id`, SHA-256 of the exact UTF-8 content brief as `reference_sha256`, and a `scores` object containing `none` and exactly the variant labels. Each score entry needs `sha256` of its exact UTF-8 generated text and a finite cosine `similarity` in [-1, 1]. A missing/mismatched hash or case rejects the entire report. Imported scores are **asserted by the supplier**; hashes bind them to texts but cannot prove that SBERT actually produced them. The provisional generic floor 0.70 and maximum relative decline 0.05 still apply. With neither imported scores nor a local model, semantic assessment is unavailable. MCP never publishes raw drafts or source passages in its result.

`pentwin semantic-template CASES.json PRIVATE_SCORES.json` creates the exact IDs and hashes with blank similarities. Score the same brief, baseline and each continuation using one fixed SBERT model, then fill every similarity and the model identifier before importing. The template contains no prose.

## OA life-science corpus check

The intended independent cohort is two confirmed original drafters × three distinct CC BY open-access life-science research papers with the same section and matched topic/journal/time where possible. `pentwin fetch-pmc PMCID PRIVATE.xml` uses the official Europe PMC OA fullTextXML endpoint when network access permits. After visual review, a private six-entry specification names local XML paths, anonymous writer/paper IDs, PMCID, one stratum and `primary_drafter_verified=true`. `pentwin prepare-pmc PRIVATE_SPEC.json PRIVATE_OUTPUT` checks unique IDs, CC BY license, matching PMCID, one top-level Discussion section, and at least 200 words; it writes a private diagnostic manifest. Verify the XML paragraph boundaries and drafting role against the article before using `qualify-eval`.

After the threshold decision, the OA endpoint became reachable. Twelve distinct CC BY research articles were retrieved into a **private** corpus: four original drafters, three papers each, with the same Discussion section and a broad biomedical Mendelian randomization topic. Author-contribution statements and disjoint contributor groups were checked. Within each cohort the publication **year** was matched, but journals and specific biomedical questions were not; multiple credited original drafters on a paper may also influence the style. The two cohorts were regrouped by year after seeing an initial pairing's scores, so this is exploratory and **not** an untouched external test. IDs, names, passages, roles, and exact source attribution are retained privately, never in Git.

| Current year-matched OA cohort | Content Jaccard | Function words + ending | Discourse order (measurable) |
| --- | ---: | ---: | ---: |
| Cohort 1 | 6/6 (3/3, 3/3) | 2/6 (0/3, 2/3) | 0/1 |
| Cohort 2 | 4/6 (2/3, 2/3) | 2/6 (0/3, 2/3) | 1/3 |

Under the **4/6 operational gate**, only the lexical axis passes both cohorts. The ending axis does not retain discrimination in these life-science papers, and order has too little measurable evidence. Passive-sentence proxy rates by writer were 0.208, 0.233, 0.229 and 0.162; fixed academic-phrase rates were 0.167, 0.048, 0.100 and 0.162. Those are diagnostics, not additional style scores. Topic, journal and editorial effects remain plausible causes of the lexical result. There is still **no independently verified author-voice or generated-text improvement claim**.

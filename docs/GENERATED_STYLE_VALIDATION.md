# Automated style pilot, 2026-10-26

## Design

Two anonymous writers contributed three articles each in the same medical editorial column. The first two per writer provided aggregate reference profiles; a third per writer was reserved for the whole-paper diagnostic. Three short content briefs about laboratory observations each received one shared generic baseline and two target-guided English drafts (six guided cases). The assistant wrote the drafts within this session after viewing aggregate profiles and guidance. All source bodies, case texts, paths and writer identities remain private. The experiment made no independent GPT or Claude API calls and did not send source passages to a model.

The command `pentwin auto-eval PRIVATE_MANIFEST.json PRIVATE_CASES.json` checks two independent reference files per writer, distinct paper bodies, two matching writer arms for each content item, exact shared baselines, and at least 50 measurable words per draft. It reports margins between distance to the target and rival author profiles. Larger positive margin means closer to the assigned target under the selected features; it is not a probability or human similarity judgment.

## Observations

| Measure | Guided closer to target | Guided margin improved over baseline | Writer A / Writer B improved |
| --- | ---: | ---: | ---: |
| Sentence and paragraph length | 3/6 | 3/6 | 0/3 · 3/3 |
| Seven-feature distance | 3/6 | 3/6 | 0/3 · 3/3 |
| Rhetorical extension | 3/6 | 3/6 | 0/3 · 3/3 |
| Function words | 2/6 | 2/6 | 0/3 · 2/3 |
| Sentence length alone | 6/6 | 3/6 | 3/3 · 0/3 |
| Short-passage profile, without paragraph length | 6/6 | 6/6 | 3/3 · 3/3 |

The original whole-paper diagnostic on these six source articles gave 5/6 for both seven features and length alone, and 3/6 for function words. The same-column cohort has **nonoverlapping writer publication periods, no reported shared topics and unverified primary drafting roles**. Its genre is editorial, not a research manuscript.

## Interpretation and failure analysis

The raw score assigned every Writer A guided draft to the rival profile. The source profile's paragraph length is based on long whole articles; a short draft has too few sentences to reproduce it. Even though Writer A's sentence rhythm moved toward its target, the paragraph component dominated the distance. The tool now shows both raw and short-passage diagnostics so this mismatch is visible.

Before the change, both profiles gave almost the same top-line advice on a common draft. The revised plan now states stable numeric soft targets: median sentence length around 29 versus 19 words, first-person use around 27% versus 39%, and passive-like construction rates around 26% versus 14%. These numbers distinguish the plans, but their usefulness in an independently run host LLM remains untested.

The short-passage metric was defined **after** examining this failure. Its 6/6 result is exploratory and cannot be treated as a fresh success rate. The drafts were deliberately written with knowledge of the target aggregate values, and the score measures related features; matching its numbers could produce a high score without a distinctive voice. Writer B already had the closer profile for all three generic baselines. Sentence length alone classified all six guided drafts, while the additional features provided no demonstrated advantage. No independent judge assessed whether a reader would recognize either writer.

For a stronger automated follow-up, freeze the short-passage scoring rule before collecting new writers and research-manuscript sections. Compare multiple writers who overlap in publication period and topic, use independently sampled GPT and Claude generations from identical briefs, retain generic academic controls, and report failures by writer. A new study must also establish that a gain beyond sentence rhythm survives this control. The current evidence supports the ability to alter measured rhythm in a contrived pilot; it does not establish author-specific wording or product-level fidelity.

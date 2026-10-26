# What a 5/6 attribution result can establish

Status: theoretical decision record, 2026-10-26. This document defines the next experiment **before** another implementation or validation cycle. It contains no participant identity or source passage.

## The observation and its limits

In a third exploratory set of two writers with three sole-authored articles each, all six items came from the same named medical-journal editorial column. Whole-article leave-one-out comparison, using the two remaining papers per writer as references, gave 5/6 correct for the seven-feature profile, 5/6 for its rhetorical extension, 5/6 for the two-feature sentence/paragraph-length comparator, and 3/6 for fixed function words. The length comparator measures median **sentence** words and sentences per paragraph, not total article length. The seven-feature and length-only systems made the same correct/incorrect decisions on all six items. These are meaningful signs that the texts differ predictably in this closed pair, but provide zero observed incremental classification wins over length.

Five successes out of six equal 83.3% observed accuracy. Under a *hypothetical* six independent, prospectively sampled Bernoulli trials with a genuine 50% null success probability, the probability of at least five is 7/64 = 0.109375; a two-sided exact 95% binomial interval for the success probability is approximately 0.359–0.996. Those assumptions do not hold here: leave-one-out reference sets overlap, the same two authors recur, the source and feature choices were explored during development, and article period and subject matter correlate with the writer. Thus neither that probability nor that interval is a valid significance result for PenTwin. A two-author closed-set 50% comparator also does not represent an unknown-author or many-author deployment setting.

Matching the column removed one visible confound from the previous corpus, but the two writers occupy different publication periods, including an editorial handover. An observed feature difference can still be an era, topic, or editor effect. Citation and quotation contamination, short articles, and imperfect extraction create further uncertainty. The current sample is an editorial column, whereas the intended product handles life-sciences research manuscripts. A result for one cannot be transferred to the other without a new test.

## A causal account of the problem

For a source passage, write its observable text as a mixture of author contribution, genre, rhetorical section, topic, time, journal/editorial intervention, coauthors, and extraction noise. The profile is a function of the text. A generated passage additionally depends on the fact sheet, the model/version, its instructions, and stochastic output. Attribution asks whether a profile helps choose between *existing* texts. The product asks whether guidance built from that profile improves *new text on fixed facts*, while preserving scientific meaning.

There are four distinct claims:

1. **Feasibility:** A fixed profile recognizes some held-out texts in a specified two-author setting.
2. **Author signal:** The profile distinguishes writers beyond simple length and matched topic, time, journal, genre, section, and editing effects.
3. **Transfer:** A model uses the profile to produce more author-like prose on the same facts than a no-profile or generic-academic instruction.
4. **Usability:** The transfer does not increase material scientific errors or reduce readability and naturalness.

The present 5/6 supports further investigation of claim 1. It does not establish claims 2–4. If writer and period are perfectly paired, the contribution of each is unidentifiable from this corpus, however high the attribution accuracy. If seven features and length make identical decisions, the data provide no evidence that the additional features improved the chosen decision rule. This does not prove that they are useless on future writers or for generation.

The simple comparator is not a meaningless straw man. Sentence rhythm and paragraph structure can themselves be aspects of style. Therefore 5/6 for length-only is compatible with a useful, compact profile. The competing explanations require different tests:

| Explanation | Prediction on a new controlled corpus | Design consequence |
| --- | --- | --- |
| H-A: stable personal rhythm | Sentence/paragraph measurements remain predictive when topic, time, journal and section are matched and independently varied. | Test length-only first, across more writers and whole-paper holdouts. |
| H-B: time/topic/editor proxy | Predictive advantage fades or changes sign when writers overlap in time and topic; a time/topic-only control performs similarly. | Counterbalance period and topic; log editorial and contribution roles. |
| H-C: two length dimensions suffice within this genre | Seven features keep agreeing with length-only even on new writers; extra features show little stable incremental gain. | Favor a smaller, interpretable profile unless a new feature helps on untouched data. |
| H-D: identification does not turn into useful instructions | Existing papers remain distinguishable but guided generations receive no masked likeness preference over both controls. | Test prompt usability on fixed facts before expanding the attribution model. |
| H-E: small-sample or selection effect | New, prospectively enrolled writers fall toward the relevant baseline and results vary greatly by group. | Widen the corpus and report clustered uncertainty without recycling inspected papers. |

These hypotheses can coexist. For instance a real personal rhythm might be measurable but hard for a particular LLM to apply without changing factual meaning.

## Why the new literature changes our design

- Patel et al. (2025), [StyleDistance](https://aclanthology.org/2025.naacl-long.436/), explicitly controls content with synthetic near-parallel examples when learning style representations. It suggests a future content-matched contrast, but its reported gains do not establish performance for PenTwin's fixed aggregate profile or biomedical manuscripts.
- Kim and Jurgens (2026), [style-eliciting prompts](https://aclanthology.org/2026.findings-acl.2039.pdf), evaluate not just extracting a style representation but whether its natural-language prompt can steer generated text. This supports treating profile discovery and usable rewrite instructions as separate links to test. Their learned decoder and study domain are not PenTwin's implementation.
- Cho et al. (2025), [TICL](https://aclanthology.org/2025.findings-naacl.326.pdf), report that explicit prose analysis of few-shot examples did not consistently improve personalization; trial/error and explanations helped in their tested settings. This is a concrete warning that even a discriminating profile need not yield a useful generic instruction. Its examples and privacy/compute requirements cannot simply be assumed here.
- Mir et al. (2019), [style-transfer evaluation](https://aclanthology.org/N19-1049/), distinguish style change, preserved content, and naturalness. The review by Briakou et al. (2021), [human evaluation survey](https://aclanthology.org/2021.gem-1.6/), finds that such protocols are often insufficiently specified. PenTwin therefore needs separate blinded scores and a scientific-fidelity gate rather than an aggregate style distance.
- Sawatphol et al. (2024), [topic leakage](https://aclanthology.org/2024.tacl-1.75/), show that even nominal cross-topic splits can retain topic shortcuts. A future corpus must record topic and enforce the split, then compare with topic and length controls.
- Manzo (2026), [academic genealogy and writing style](https://arxiv.org/abs/2608.14843), is a preprint reporting that advisor-student and academic-sibling texts can be stylistically closer than same-field controls. It strengthens the reason to include difficult comparison writers from the same research community, while its mathematical solo-author corpus does not quantify the effect for life sciences.
- Academic text can be changed by editors: Daudaravicius (2014), [language-edited academic texts](https://aclanthology.org/L14-1560.pdf), describes before/after professional editing data. For research papers, collect confirmed original-draft contributions and account for editing and coauthors. A published byline alone is not evidence that one person supplied its wording.

## Thresholds, declared before more testing

**Exploration threshold:** 5/6 in a fixed closed pair is enough to justify collecting a new corpus. It is not a product accuracy estimate and is not a threshold on a similarity score. We must not fit a cutoff to these six articles and retest it on them.

**Evidence for a distinctive profile:** On newly enrolled research-manuscript sections, predefine exactly one main feature set and distance rule; keep sentence/paragraph length as the primary simple comparator and a generic-academic profile as another control. Select writers who overlap in publication period and topic, use the same journal/genre/section when possible, verify writing roles, and include difficult same-community rivals. Keep entire papers, near-duplicate versions, and all coauthors out of both reference and held-out sets where leakage would occur. Report writer-level results, paired disagreements with each comparator, per-stratum margins, and failures. A positive claim requires a prospectively estimated *increment over the length comparator* whose author-cluster uncertainty interval excludes zero in more than one independent writer group; it cannot rest on a pooled 5/6 alone. The exact sample size must follow a feasibility/power assessment, not an invented universal 85% cutoff.

**Evidence for transfer:** Freeze fact sheets and model/version, then randomize no-profile, generic-academic, and PenTwin-guided outputs on the same facts, by model (GPT and Claude) and section. A reader familiar with the writer rates masked pairs for likeness and naturalness; a separate qualified reviewer checks numbers, units, populations, comparisons, uncertainty, citations, and scientific meaning. Keep prompt logs and exact hashes. Compare paired outcomes across writer clusters rather than treating repeated passages from one writer as independent. The guided arm must beat both controls on blinded likeness in new writers/sections, without an increase in material errors or a material naturalness loss. Predefine treatment of ties, unresolved errors, and missing judgments. A score from `assess_revision` cannot substitute for that judgment.

**Product gate:** Until the transfer and fidelity conditions hold, display an aggregate style description and a reviewable rewrite plan as experimental guidance only. Do not label a generated passage as author-faithful or automatically approve it. Even a successful attribution threshold would not establish a safe automatic manuscript rewrite.

## Immediate next experiment, after this theory is accepted as the frozen protocol

Recruit a new set of confirmed primary-draft writers of English life-sciences research papers, aiming initially for at least two matched writer groups and four independent papers per writer: two reference papers, one development paper for choosing any threshold, and one untouched test paper. Match section and genre first, record topic/time/editor/coauthor metadata, and vary topic within each writer where possible. This is a feasibility target, not a powered sample size; expand writer groups based on the observed cluster variation before making an efficacy claim. Fix extraction and exclusion rules before opening the test texts. The six editorial articles already inspected are development evidence and can never become an untouched confirmation set.

If research papers cannot be paired so that writer and topic/time vary separately, report the design as non-identifying and run the same-facts blinded generation test without claiming an author-specific statistical fingerprint. If the length baseline again matches all seven-feature decisions, spend effort on controllable, scientifically grounded style guidance and human ratings before adding more stylometric features.

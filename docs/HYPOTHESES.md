# Author-style hypotheses and decision record (2026-10-26)

The product objective is a more author-like **generated English life-sciences passage** with unchanged scientific meaning. Identifying the author of an existing article is a useful intermediate check, not the objective itself. The six-article exploratory corpus has already influenced design decisions and must not be used for an independent release claim. No participant identity, source passage, or private corpus belongs in this repository.

| Hypothesis | Current evidence | Next discriminating experiment | Current confidence |
| --- | --- | --- | --- |
| H1: seven surface features omit useful author signals | Seven features and length-only both 4/6; fixed function-word rates 6/6 on the *same inspected cases*. Dropping `the` lowers this to 5/6. | Freeze the feature sets and normalizers, then evaluate entirely new confirmed authors and papers. Compare length-only, seven features, function words, rhetoric, and combined with whole-paper holdouts. | Plausible, unconfirmed outside inspected cases. |
| H2: genre, journal, section and topic shifts masquerade as author differences | Five articles share one journal; one article differs. Same-journal test leaves only one reference article per author. | Enroll enough independent articles for at least two reference families and one held-out family in *each* matched genre/section stratum. Cross topic and journal in a separate test; report every stratum. | Strong methodological concern; effect size unknown. |
| H3: profile-to-instruction conversion is too generic | Same draft yields 3/4 shared prioritized instructions for two authors even with new rhetorical cues. No LLM output was produced. | Hold source facts, model/version and section fixed. Randomize ordinary vs guided outputs; keep tool logs and hashes; blind rate author likeness. Include a no-profile generic-academic guidance control. | Plausible; generated-text effect unknown. |
| H4: proxy scores fail to track likeness or factual correctness | No generated output has been rated. Style distance only measures the chosen features. | Rate author likeness, naturalness and factual fidelity independently. Report paired wins and material-error cases. Test agreement of each automated metric with blinded ratings without selecting the metric on the evaluation set. | The measurement gap is certain; the direction of bias is unknown. |

## Iteration outcomes

1. Added fixed function-word and discourse-cue aggregate features to the local engine, with no source text or rare lexical sequences in MCP output. They are exploratory diagnostic features, and the host LLM receives only aggregates.
2. Re-ran whole-paper leave-one-out comparisons on the already inspected six-article corpus. The function-word result improved from the old 4/6 to 6/6, but a single high-frequency word contributes materially and no independent replication exists. Rhetorical cues alone gave no improvement. The new plan still shared 3/4 instructions across the two profiles.
3. Extended the private blind-rating workflow with separate paired dimensions and a material-error gate. Synthetic tests exercise the gate. This is an implementation check, not human or model-generated quality evidence.
4. Added an optional human-reviewed rhetorical-move filter and stopped automatic all-section fallback when a requested section or move lacks two independent development families. Synthetic tests and the MCP SDK integration pass. This reduces a known genre/section mismatch risk, but does not establish a likeness gain.

## Pre-registered next-stage decision rule

Before collecting new articles, freeze code and extraction rules; keep at least three independent papers per author, with two for development and a whole paper held out. Require enough papers per matched stratum before making section/genre claims. Compare against length-only and generic-academic controls, and report per-author outcomes rather than one pooled score. For actual same-content drafts, require a blinded improvement in likeness across authors and sections without increased material factual errors or naturalness regressions. A small pilot yields descriptive evidence, not a universal accuracy rate. If matched-stratum recognition improves but blinded drafts do not, prioritize H3; if recognition fails under controls, revisit H1/H2 before editing prompts.

## Research basis

- Altakrori et al., [Topic Confusion Task](https://aclanthology.org/2021.findings-emnlp.359/): topic shifts can confound author attribution; POS-based stylometry was relatively robust in their evaluation.
- Sundararajan and Woodard, [What represents style?](https://aclanthology.org/C18-1238/): syntactic and lexical evidence behave differently across topic and genre.
- Sawatphol et al., [Topic Leakage](https://aclanthology.org/2024.tacl-1.75/): apparent cross-topic evaluation can still leak topic shortcuts.
- Alliheedi et al., [Rhetorical Moves in Biochemistry Articles](https://aclanthology.org/W19-4514/): scientific argument structure is a meaningful annotation target.
- Horvitz et al., [TinyStyler](https://aclanthology.org/2024.findings-emnlp.781/): few-shot author style transfer is possible in their evaluated domains, without establishing performance on this product's life-sciences papers.
- Pauli et al., [Mind the Style Gap](https://aclanthology.org/2025.findings-emnlp.1175/): content-preservation metrics can appear better than they are when evaluation sets are too easy.

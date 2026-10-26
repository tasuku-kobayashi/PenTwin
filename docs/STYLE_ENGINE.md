# Local style engine (v0.3)

## What is implemented

The input is a sealed, human-reviewed set of English paragraphs from at least three independent papers, with one family reserved as holdout. Only development families contribute to the style profile. The server reads the private text on the user's computer, computes measurements, and returns aggregate values. It does not fine-tune, train, embed, or send the source paragraphs to an LLM. No paper excerpt permission is needed for this aggregate-only workflow; there is no raw-example MCP tool.

For a section, each paper first produces a vector: median sentence words; sentences per paragraph; fractions of sentences with hedges, first-person pronouns, passive-like verbs, citation-like markers, semicolons, or parentheses; and usage of a small fixed vocabulary of connectors and stance verbs. The component-wise median across independent paper families is the target. A component with large disagreement across papers does not yield a rewrite instruction. A section with fewer than two usable families falls back to the whole development set and reports that fallback. This does not infer individual phrasing, rare word choices, or the writer's scientific reasoning.

`rewrite_plan` compares those targets with the input draft and orders at most four changes by normalized size. Its contract tells the host LLM to preserve assertions, comparisons, groups, directions, numbers, units, citations, negation and calibrated uncertainty, and to avoid copying source material. `assess_revision` reports a diagnostic difference before and after, text hashes, and lexical alarms. It always returns `needs_human_review`; it never certifies meaning or author likeness. The host application must explicitly invoke the tools, and the final displayed text must be checked against the returned revision hash for the assessment to apply to it.

## Verification and limits

- Synthetic tests check that local aggregation works when `model_excerpt_permission=no`, holdout text has no effect, no original passage appears in an MCP response, the rewrite plan responds to engineered stylistic differences, numeric mutations are flagged, and the official SDK can call the tools over stdio.
- The private four-PDF extraction smoke test produced enough provisional all-section candidates for the algorithm to run but too few independently supported candidates in individual sections. The rows have **not** been visually reviewed or confirmed as primarily written by the target author, so these measurements are not a valid style profile and are not served through MCP.
- Heuristics such as passive-voice detection and sentence splitting can misread scientific notation, abbreviations, tables, and OCR. Family-balanced averages can still track journal and topic differences. A lower diagnostic distance is not proof of human-recognizable authorship.
- Validate with confirmed writing contributions and blinded, same-content author ratings across sections, alongside independent fact checks. Keep evaluation papers untouched while iterating. See [evaluation protocol](EVALUATION.md).

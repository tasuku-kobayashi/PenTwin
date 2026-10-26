# Weak-card axis probe, 2026-10-26

## Why

The first role-conditioned card abstained for all four anonymous profiles in two private editorial cohorts. Its minimum counts demanded recurring exact vocabulary and confirmed paragraph move labels. An abstention did not answer whether weaker evidence could still improve a draft. Version 0.9 adds a graded exploratory card rather than labeling every small or inconsistent signal as a failed style.

The new card keeps a fixed vocabulary's term if it appears in either of two development papers, recording **support 1/2 and low confidence** when it appears in only one. It also records soft first-person, hedge and passive-like rates and approximate sequences of visible rhetorical cues. Surface cue order is explicitly distinct from a verified explanation plan. The stricter card remains available for comparison.

## Controlled probe

One previously inspected anonymous same-column cohort supplied two reference articles and a third scoring article for each of two writers. The exploratory cards produced candidates for both writers; the strict cards produced none. Two synthetic scientific content briefs each had one identical generic baseline for both writers. Deterministic, short edits changed only one axis at a time or all three, creating **16 target variants**: 2 briefs × 2 writers × 4 conditions. Each text had seven sentences and 82–98 words. Wording and cue-order interventions left median sentence length unchanged; stance edits changed it by at most one word. Source texts, identities and draft texts remain private.

The experimental command `pentwin heldout-axes PRIVATE_MANIFEST.json PRIVATE_CASES.json` measures whether a variant moves closer to its assigned writer's **third article** than to the rival's third article, relative to the same generic baseline. It uses fixed connector/verb rates, first-person/hedge/passive rates, or distributions of visible cue transitions. Empty cue transitions count as a zero rate. Scores are descriptive distances to whole articles, not a reader's author-likeness judgment.

| Changed axis | Improvement over generic baseline | Writer A / Writer B |
| --- | ---: | ---: |
| Wording | 0/4 | 0/2 · 0/2 |
| Visible cue order | 2/4 | 2/2 · 0/2 |
| Stance | 2/4 | 0/2 · 2/2 |
| Combined | 2/4 | 0/2 · 2/2 |

**Interpretation:** Lowering the threshold revealed clues, but the weak wording candidates did not transfer to the held-out papers. One target's candidate reporting verb was absent from its held-out article. Cue order and stance moved in opposite directions for the two writers; combining them did not improve on the better individual result. No axis showed a consistent gain across writers. It would be incorrect to select the winning axis from this tiny inspected cohort and claim independent confirmation.

## What this does not prove

- Edits were deterministic probes prepared in this assistant session, not independently sampled GPT or Claude generations from the MCP prompts. They establish that the experimental path can isolate a change, not that a host model will use the clue well.
- Both writer and publication period/topic may be confounded; the articles are editorials with unverified original drafting roles, not life-sciences research manuscripts. The third articles were previously inspected during development, so they are not untouched confirmation data.
- The evaluator measures variants of the same visible cues offered in the exploratory cards. It may reward a marker without measuring recognizable personal voice. Its combined distance has no calibrated cross-axis weights. A zero cue rate and a single observed transition are both fragile in short texts.
- The cue-distance treatment of zero observed transitions was changed after the first run, which initially abstained on all four cue-order cases. The 2/4 result is therefore explicitly post-inspection. Scientific meaning is outside this experiment.

The next informative test freezes the current scorer and weak-card rules, then uses independently generated GPT and Claude drafts for new authors with matched paper section, topic and time. Compare generic, individual axes, strict card and combined weak card on the same briefs. Report all writers and failures. No human blinded review is required for that protocol.

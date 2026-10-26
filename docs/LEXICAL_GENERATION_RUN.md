# Lexical-only generation run

This is an operational protocol, not a claim that generated prose resembles a writer. The only axis cleared for exploratory scoring in the inspected OA life-science cohorts is lexical wording. Its 9/10 and 9/10 human scores are confounded by journal and opening position. Keep the existing 7/10 two-cohort gate and its warnings in the result; do not use ending or discourse-order scores as positive evidence.

## Inputs and separation

Use two sealed private writer runs and the two private ten-paper calibration manifests. Do not put writer names, article IDs, passages, prompts containing excerpts, outputs, or manifests in the public repository. Use at least two identical content briefs for both writers. Run GPT and Claude separately: each `cases_json` payload covers **one model** because the pairwise evaluator requires the same model for both writers of a brief. Record the exact model ID and generation settings outside Git. Keep one generic baseline per brief byte-for-byte identical in both writer cases. Generate the target writer's lexical output without seeing the other writer's output.

For each sealed writer MCP connection, call `generation_protocol(section="discussion", lexical_only=true)`. This returns `none` and `lexical`. The wording clues come from that writer's four development paper families. For a snippet condition, first obtain a separately confirmed writer-authored target that is absent from **both** calibration cohorts and from both sealed writer runs; call with `target_text=...` and `confirmed_author_written=true`. The resulting `lexical_snippet` instruction asks the model to continue a short opening. Store and score **only the new continuation**, never the human anchor. The offline evaluator checks 10–50 anchor words and rejects an exact normalized anchor found in either calibration cohort. An original-draft credit for a whole paper does not by itself prove that a particular opening was written by one contributor.

Use the same brief, target length (at least 200 measurable English words), model, and settings for the generic and lexical conditions. The lexical condition adds only the lexical instructions. The optional snippet condition adds the human anchor as a third condition; do not silently substitute an opening from another paper. Replicate and randomize condition order when a host supports it; record any failures without rewriting the prompt after seeing scores.

## Direct MCP submission

On either sealed MCP server call `evaluate_generated_drafts(first_manifest, second_manifest, cases_json, semantic_scores_json="")`. The JSON **string** `cases_json` has the shape below. Fill every prose field with the model's exact UTF-8 output; the placeholder strings are not evaluable. Repeat the two-brief/two-writer payload for each model. `content_id` groups paired writer cases, and `case_id` is globally unique within one payload.

```json
{
  "cases": [
    {
      "case_id": "brief1_writerA",
      "content_id": "brief1",
      "author_id": "A",
      "model": "exact-model-id",
      "section": "discussion",
      "content_brief": "identical factual brief for both writer cases",
      "baseline": "same complete generic passage for both writer cases",
      "variants": {"lexical": "complete target lexical passage"}
    },
    {
      "case_id": "brief1_writerB",
      "content_id": "brief1",
      "author_id": "B",
      "model": "exact-model-id",
      "section": "discussion",
      "content_brief": "identical factual brief for both writer cases",
      "baseline": "same complete generic passage for both writer cases",
      "variants": {"lexical": "complete rival lexical passage"}
    }
  ]
}
```

Add another pair with `content_id="brief2"`. Use the **actual anonymous IDs** from the first calibration cohort; `A`/`B` above are placeholders. If a separate target is confirmed for each writer, add `lexical_snippet` to each `variants` and the corresponding `snippet_anchor` to each case. The snippet continuation must be at least 200 words on its own. All four cases must use the same variant labels.

The MCP result contains case-level score changes, SHA-256 hashes of exact outputs, eligibility flags and diagnostic warnings, but no drafts. The direct input exists only during the call. Save your input privately to reproduce the result. `offline_evaluate(first_manifest, second_manifest, cases_file, semantic_scores_file="")` reads that saved payload through the same evaluator and should yield the same scores. Pass verified SBERT cosine scores for **the same hashes**, or use one fixed local encoder. Without them, `semantic_unavailable` is expected and there is no passing generation-quality decision. Imported scores are asserted by the supplier and cannot prove the encoder identity.

## Interpretation

Report each writer, each brief, each model and each condition. Count improvement over the shared generic baseline only on the lexical axis and only if the semantic screen passes. Also report zero or negative changes, the journal-only control and the first-sentence-shift diagnostic. The current 20 papers were inspected while designing the metric. A fresh, independently selected two-writer/five-paper-per-writer same-journal cohort with confirmed original drafting is still required to distinguish writer wording from journal, topic, period and coauthor effects. The retrospective five same-journal pairs represent only seven unique held papers and cannot replace that cohort.

As of this protocol revision, two sealed writer runs produced available lexical MCP plans, and direct MCP evaluation passed a four-case integration check using **byte-identical synthetic passages**. The zero style improvements in that check are expected and are not a GPT or Claude result. No independent GPT/Claude text, independent confirmed human snippet, or verified SBERT score has been collected in this environment.

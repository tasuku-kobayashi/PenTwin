# PenTwin — reviewed corpus and local MCP pilot

PenTwin is an English life sciences writing-style project. It prepares a manually reviewed corpus and serves limited style observations through a read-only local MCP server. It does not generate prose, call an LLM, publish a manuscript, or certify authorship, meaning, or style fidelity. **The three-paper minimum is an ingestion threshold, not evidence of reliable style imitation.**

## Prerequisites

- Python 3.11 or newer; install with `python -m pip install -e .` inside this directory. For tests, use `python -m pip install -e '.[test]'`.
- `pandoc` on PATH for `.tex` input. Source must be a self-contained file; included files and custom macros must be inspected in the output.
- At least three independent paper families. Two versions of the same paper **must** share a `family_id`.

Create a private manifest based on `manifest.example.json`. A paper is eligible for the final corpus only when its primary writing contribution is confirmed. The legacy `model_excerpt_permission` field is optional and defaults to `no`; the current MCP server never returns paper excerpts. The manifest makes no network calls. Keep all source papers, review sheets, and output directories outside Git. The CLI rejects an output directory anywhere inside a Git working tree.

```
pentwin prepare /private/pentwin/manifest.json /private/pentwin/run-001
```

`review.csv` contains candidates, **not approved training data**. Compare each candidate with its source; check column order, page layout, equations, references, tables, captions, and English text. Set `include` to `yes` or `no` for **every** row. For accepted rows, set `source_verified=yes` only after visual comparison, then choose a checked `section` and `move` from the allowed values below. Rejected rows need no labels. Explain any accepted `other` section in `review_note`. Do not edit the candidate text or provenance columns; correct the source and run a new preparation if necessary.

```
pentwin seal /private/pentwin/run-001
```

The sealed `corpus.jsonl` contains full local text and a deterministic `development` / `holdout` split by `family_id`. The holdout family is never used for tuning. A sealed run cannot be overwritten. **Do not give a model the holdout text or send it as a tool exemplar.** A one-paper holdout is a pilot and cannot establish broad generalization. With only three papers, record confidence limits and collect more independent papers as they become available. The companion `corpus.sha256` detects accidental changes after sealing; it is not an authenticity signature.

## MCP path

Run only after `seal`, on a computer with access to the private run:

```powershell
python -m pip install -e .
python -m pentwin.cli serve C:\private\pentwin\run-001
```

The process reads JSON-RPC from stdin and writes MCP responses to stdout. Configure the client to launch `python` with arguments `-m`, `pentwin.cli`, `serve`, and an **absolute** private run path. An unsealed run or changed corpus fails before tools are advertised.

### Author-style rewrite logic

`style_profile` measures English writing from visually reviewed **development** papers locally, with one vote per independent paper family. It measures sentence and paragraph length, hedging, first person, passive constructions, citation and punctuation use, and a fixed list of generic academic connectors and stance verbs. It returns only bounded aggregate numbers and generic vocabulary from that fixed list. Published or unpublished source text, names, and phrases do not enter this response. `model_excerpt_permission=no` permits this local calculation. No MCP tool serves raw paper examples.

`rewrite_plan(draft, section)` compares the user's draft with those aggregate targets. It returns up to four prioritized edits and a meaning-preservation contract for the host LLM. A requested section or move with fewer than two reviewed paper families returns `insufficient_evidence` rather than broadening the scope. It does **not** train a model or return paper passages. The LLM in ChatGPT or Claude writes the revised text using this plan. `assess_revision(original, revised, section)` then measures whether the diagnostic style distance moved, reports exact text hashes, and flags numeric tokens, negation, uncertainty, and changed citation tokens for human review. The distance is not an author-likeness score and equal token counts cannot prove meaning is preserved. MCP cannot force a model to call either tool or prevent changes after assessment.

Both `rewrite_plan` and `assess_revision` accept an optional `protected_spans` array of exact phrases from the original draft, for example `["12.5 mg/mL", "not superior to", "[12]"]`. The plan asks the host to keep these unchanged; assessment reports a count change for each protected span. Use the same list in both calls. Exact phrase checks can miss changed context, scope, causality, and meaning, so they never approve a draft. The choice follows a [comparison of writing services](docs/SERVICE_RESEARCH.md), without relying on their marketing performance claims.

`corpus_status` reports anonymous counts. Unpublished papers can be ingested and locally measured, but their text is never returned by this server. `review_draft` flags changed numeric tokens between a supplied fact sheet and draft; it cannot detect all altered claims. See [style logic and validation](docs/STYLE_ENGINE.md) and [hypothesis tests](docs/HYPOTHESES.md). Function-word recognition on the first tiny sample did not replicate; generated author likeness is still unvalidated.

**Current evidence:** three small attribution pilots gave mixed results. In a same-column six-paper cohort, seven features and length-only both matched 5/6 withheld articles. None of these pilots supports a claim that generated prose resembles its intended author. Details and limitations are in the [hypothesis record](docs/HYPOTHESES.md).

For an offline matched-stratum check, keep a private JSON manifest outside Git with six reviewed body-text files. Use anonymous identifiers, exactly two authors with three independent papers each, and the same `stratum` value for all six:

```json
{"papers": [{"author_id": "A", "paper_id": "A1", "stratum": "same genre and section", "path": "A1.txt"}]}
```

The example shows one entry; add five more. Run `pentwin diagnose C:\private\pentwin\six-papers.json` and retain its JSON report privately. It compares whole-paper leave-one-out attribution against a length-only baseline, with per-author counts. An article in a different genre, topic, or time can still confound the result. The current same-column six-paper pilot scored 5/6 on both the seven features and length-only, and 3/6 on function words. This does not measure whether an LLM's prose resembles an author.

To audit visible confounds, each private diagnostic entry may additionally include `publication_month` (`YYYY-MM`), `topic_id`, `journal`, `genre`, `section` and `primary_drafter_verified` (Boolean). The report shows missing fields and risk codes without returning these metadata values. It also counts which individual papers each feature set gains or loses against the length comparator. Metadata can identify a design problem; their presence cannot prove an author-specific effect.

The MCP path was exercised with the official Python SDK client over a real stdio subprocess using synthetic documents. **A Windows installation of ChatGPT or Claude has not been exercised here.** Claude Code can register a local stdio command (`claude mcp add --transport stdio pentwin -- python -m pentwin.cli serve C:\private\pentwin\run-001`) and verify it with `/mcp`. Claude Desktop supports local MCP extensions, but packaging and an actual desktop check remain. ChatGPT Desktop's local plugin submission is restricted to approved partners. An alternative private ChatGPT test can use OpenAI's Secure MCP Tunnel, which requires its own Platform key, tunnel and workspace permissions, and outbound communication. GitHub access does not grant those permissions. See [connection checklist](docs/CONNECTION.md) and the linked official sources there.

Do not assume a local corpus means a local-only model: tool responses and fact sheets supplied in the conversation can reach the model provider. Obtain permission for every model-facing passage, and do not publish private run paths or files.

## Blinded writing quality experiment

Use the same fact sheet to create baseline and PenTwin-guided drafts separately for each model and section. Store a **private** JSON file with `cases` containing `case_id`, `model`, `section`, `baseline`, and `guided` text. Do not put this file or model outputs in Git. Then:

```powershell
python -m pentwin.cli blind C:\private\pentwin\cases.json C:\private\pentwin\blind-001 --seed secret-experiment-seed
```

Give `rating.csv` to the author without `private_key.json`. For each row, fill `preferred` with `A`, `B`, or `tie` and rate `likeness_a/b`, `naturalness_a/b`, and `facts_a/b` from 1 to 5. A qualified reviewer marks `material_error_a/b` as `yes`, `no`, or `uncertain`; enter comments. Keep the key separate until ratings are complete. Run `python -m pentwin.cli ratings C:\private\pentwin\blind-001` to see paired preferences and each rating dimension by GPT and Claude. Collect independent content checks and multiple papers/sections; this descriptive count alone does not establish reliable author style. Do not inspect or use holdout text for prompt design, debugging, or tuning. See [evaluation protocol](docs/EVALUATION.md).

### Labels

Sections: `abstract`, `introduction`, `methods`, `results`, `discussion`, `conclusion`, `other`.

Moves: `background`, `gap`, `objective`, `method`, `finding`, `comparison`, `interpretation`, `limitation`, `implication`, `future_work`, `other`.

## Limits and privacy

- PDF line/column order and paragraph boundaries may be wrong; scanned PDFs may yield no text. DOCX inline objects and LaTeX macros/included files may be lost. Every candidate needs source checking. No parser output is considered authoritative.
- The manifest's `model_excerpt_permission` field is retained for compatibility. The current server never returns source passages regardless of this field.
- The public repository must contain code and synthetic tests only. The manifest with real paths, paper files, extracted text, and review outputs must remain private.
- For a future ChatGPT desktop connection on Windows, validate the actual local plugin/transport setup and model-facing data flow before exposing any unpublished text. A local corpus does not imply a local-only LLM.

## Evaluation order

After review, build a same-content baseline using ordinary GPT and Claude drafts. Then compare style-guided output in blinded, author-rated trials, with separate fidelity and fluency checks. Do not use the holdout paper for feature selection, prompts, examples, or debugging. See `REVIEW.md` for the adversarial analysis and experimental plan.

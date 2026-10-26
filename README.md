# PenTwin — stage 1 corpus preparation

PenTwin is an English life sciences writing-style project. This package implements only **paper ingestion, manual audit, and paper-family evaluation separation**. It does not generate prose, call an LLM, publish a manuscript, or claim that a passage is faithful to its source. The MCP server comes after the corpus and evaluation baseline are validated.

## Prerequisites

- Python 3.11 or newer; install with `python -m pip install -e .` inside this directory. For tests, use `python -m pip install -e '.[test]'`.
- `pandoc` on PATH for `.tex` input. Source must be a self-contained file; included files and custom macros must be inspected in the output.
- At least three independent paper families. Two versions of the same paper **must** share a `family_id`.

Create a private manifest based on `manifest.example.json`. A paper is eligible for the final corpus only when the author confirms they primarily wrote its text. `model_excerpt_permission` is independent of ingestion: `no` still permits local preparation but forbids later model-facing exemplars. The manifest makes no network calls. Keep all source papers, review sheets, and output directories outside Git. The CLI rejects an output directory anywhere inside a Git working tree.

```
pentwin prepare /private/pentwin/manifest.json /private/pentwin/run-001
```

`review.csv` contains candidates, **not approved training data**. Compare each candidate with its source; check column order, page layout, equations, references, tables, captions, and English text. Set `include` to `yes` or `no` for **every** row. For accepted rows, set `source_verified=yes` only after visual comparison, then choose a checked `section` and `move` from the allowed values below. Rejected rows need no labels. Explain any accepted `other` section in `review_note`. Do not edit the candidate text or provenance columns; correct the source and run a new preparation if necessary.

```
pentwin seal /private/pentwin/run-001
```

The sealed `corpus.jsonl` contains full local text and a deterministic `development` / `holdout` split by `family_id`. The holdout family is never used for tuning. A sealed run cannot be overwritten. **Do not give a model the holdout text or send it as a tool exemplar.** A one-paper holdout is a pilot and cannot establish broad generalization. With only three papers, record confidence limits and collect more independent papers as they become available.

### Labels

Sections: `abstract`, `introduction`, `methods`, `results`, `discussion`, `conclusion`, `other`.

Moves: `background`, `gap`, `objective`, `method`, `finding`, `comparison`, `interpretation`, `limitation`, `implication`, `future_work`, `other`.

## Limits and privacy

- PDF line/column order and paragraph boundaries may be wrong; scanned PDFs may yield no text. DOCX inline objects and LaTeX macros/included files may be lost. Every candidate needs source checking. No parser output is considered authoritative.
- `model_excerpt_permission=yes` records the author's approval to offer that paper's reviewed passages later. It does **not** send anything during stage 1, nor does it override coauthor, patient-data, or journal restrictions.
- The public repository must contain code and synthetic tests only. The manifest with real paths, paper files, extracted text, and review outputs must remain private.
- For a future ChatGPT desktop connection on Windows, validate the actual local plugin/transport setup and model-facing data flow before exposing any unpublished text. A local corpus does not imply a local-only LLM.

## Evaluation order

After review, build a same-content baseline using ordinary GPT and Claude drafts. Then compare style-guided output in blinded, author-rated trials, with separate fidelity and fluency checks. Do not use the holdout paper for feature selection, prompts, examples, or debugging. See `REVIEW.md` for the adversarial analysis and experimental plan.

# PenTwin — reviewed corpus and local MCP pilot

**Current research basis:** [Wang et al. (2025) and its directly cited work](docs/PAPER_GROUNDED_LOGIC.md). The new `paper-eval` command calibrates independent short-passage diagnostics on held-out human papers before it interprets matched generated drafts. The initial private pilot identifies 5/6 human windows on each metric but improves only 3/6 guided drafts on each, with opposite writers benefiting. This is exploratory evidence of a remaining generation gap, not author likeness. Earlier style cards and proxy results remain historical aids.

The MCP `generation_protocol(section)` tool provides comparable generic, card-guided and card-plus-critique conditions without returning paper excerpts. It prepares an experiment; it does not run the host model or establish that any condition works.

PenTwin is an English life sciences author-style project. It prepares a manually reviewed corpus and serves style observations through a read-only local MCP server. The host LLM writes prose; PenTwin does not generate prose, call an LLM, publish a manuscript, or certify authorship or author likeness. Scientific meaning and citation checks are outside this project and belong to an independent service. **The three-paper minimum is an ingestion threshold, not evidence of reliable style imitation.**

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

The strict role card examines reviewed rhetorical moves in at least two development families. It selects repeated generic wording within each move, move-specific stance differences, and recurring move transitions in source order. `rewrite_plan` includes supported instructions to plan explanation order, choose wording and stance, then critique generic substitutions. If reviewed role evidence is absent, the strict card abstains; a numerical profile remains available. See [style card design](docs/STYLE_CARD.md). `pentwin contrast-card` can compare two privately sealed writer runs without returning source text.

The default `author_style_card` now returns **graded exploratory clues** even when the strict move card abstains; pass `evidence_mode="strict"` for the original threshold. `rewrite_plan` includes both, with low-confidence clues labeled. `axis_plan(draft, section, axis)` isolates `wording`, `cue_order`, `stance`, `combined` or `none` without leaking the other axes into its instructions. A private `heldout-axes` command compares same-content variants against the third article per writer. In the initial deterministic probe, weak wording failed to improve in 0/4 cases; cue order, stance and combined each improved in 2/4. See the [probe record](docs/WEAK_CARD_ABLATION.md). These are surface-feature outcomes, not proof of author likeness.

`rewrite_plan(draft, section)` compares a draft with aggregate style targets and returns up to four prioritized edits about rhythm, stance, wording, and argument flow. A requested section or move with fewer than two reviewed paper families returns `insufficient_evidence`. It does not train a model or return paper passages. The host LLM in ChatGPT or Claude writes the revision. `assess_revision(original, revised, section)` then reports text hashes, a whole-paper style distance and a short-passage diagnostic that omits paragraph length. A lower distance does not demonstrate recognizable author likeness; evaluate with the automated same-content proxy and report its limits. Scientific claims, citations, and meaning require an independent verifier outside PenTwin. MCP cannot force a model to call the tools or prevent subsequent changes.

`corpus_status` reports anonymous counts. Unpublished papers can be ingested and locally measured, but their text is never returned. See [style logic and validation](docs/STYLE_ENGINE.md), [hypothesis tests](docs/HYPOTHESES.md), and [service research](docs/SERVICE_RESEARCH.md). Function-word recognition on the first tiny sample did not replicate; generated author likeness remains unvalidated.

**Current evidence:** three small attribution pilots gave mixed results. In a same-column six-paper cohort, seven features and length-only both matched 5/6 withheld articles. None of these pilots supports a claim that generated prose resembles its intended author. Details and limitations are in the [hypothesis record](docs/HYPOTHESES.md).

For an offline matched-stratum check, keep a private JSON manifest outside Git with six reviewed body-text files. Use anonymous identifiers, exactly two authors with three independent papers each, and the same `stratum` value for all six:

```json
{"papers": [{"author_id": "A", "paper_id": "A1", "stratum": "same genre and section", "path": "A1.txt"}]}
```

The example shows one entry; add five more. Run `pentwin diagnose C:\private\pentwin\six-papers.json` and retain its JSON report privately. It compares whole-paper leave-one-out attribution against a length-only baseline, with per-author counts. An article in a different genre, topic, or time can still confound the result. The current same-column six-paper pilot scored 5/6 on both the seven features and length-only, and 3/6 on function words. This does not measure whether an LLM's prose resembles an author.

To audit visible confounds, each private diagnostic entry may additionally include `publication_month` (`YYYY-MM`), `topic_id`, `journal`, `genre`, `section` and `primary_drafter_verified` (Boolean). The report shows missing fields and risk codes without returning these metadata values. It also counts which individual papers each feature set gains or loses against the length comparator. Metadata can identify a design problem; their presence cannot prove an author-specific effect.

The MCP path was exercised with the official Python SDK client over a real stdio subprocess using synthetic documents. **A Windows installation of ChatGPT or Claude has not been exercised here.** Claude Code can register a local stdio command (`claude mcp add --transport stdio pentwin -- python -m pentwin.cli serve C:\private\pentwin\run-001`) and verify it with `/mcp`. Claude Desktop supports local MCP extensions, but packaging and an actual desktop check remain. ChatGPT Desktop's local plugin submission is restricted to approved partners. An alternative private ChatGPT test can use OpenAI's Secure MCP Tunnel, which requires its own Platform key, tunnel and workspace permissions, and outbound communication. GitHub access does not grant those permissions. See [connection checklist](docs/CONNECTION.md) and the linked official sources there.

Do not assume a local corpus means a local-only model: tool responses and fact sheets supplied in the conversation can reach the model provider. Obtain permission for every model-facing passage, and do not publish private run paths or files.

## Automated style proxy experiment

Human blinded ratings are not required in the current validation path. Run the private `auto-eval` command with an anonymous six-paper manifest (two writers, three papers each) and a private JSON containing at least two content briefs, each with the same baseline and a guided draft for both writers. Each case requires `case_id`, `content_id`, anonymous `author_id`, `model`, `section="discussion"`, `baseline`, and `guided`. The reference profile uses the first two manifest papers per writer; the third is reserved for the whole-paper diagnostic. Order the manifest intentionally and do not reuse a version of the same paper as a separate family.

```powershell
python -m pentwin.cli auto-eval C:\private\pentwin\six-papers.json C:\private\pentwin\generated-cases.json
```

The command checks source independence and paired content, then reports whether guided prose moves closer to the target than the rival profile. It includes raw length and seven-feature scores, a sentence-only comparator, and a short-passage score that omits paragraph length. No text or source paths are returned. This is an **automated proxy**, not a recognition test by a reader. It reuses features from the rewrite guidance and may be gamed by rhythm alone. Preserve case texts privately and report each writer separately. The [automated pilot report](docs/GENERATED_STYLE_VALIDATION.md) records both successes and failures.

The older `blind` and `ratings` commands remain available for legacy experiments; they are not part of this validation path.

### Labels

Sections: `abstract`, `introduction`, `methods`, `results`, `discussion`, `conclusion`, `other`.

Moves: `background`, `gap`, `objective`, `method`, `finding`, `comparison`, `interpretation`, `limitation`, `implication`, `future_work`, `other`.

## Limits and privacy

- PDF line/column order and paragraph boundaries may be wrong; scanned PDFs may yield no text. DOCX inline objects and LaTeX macros/included files may be lost. Every candidate needs source checking. No parser output is considered authoritative.
- The manifest's `model_excerpt_permission` field is retained for compatibility. The current server never returns source passages regardless of this field.
- The public repository must contain code and synthetic tests only. The manifest with real paths, paper files, extracted text, and review outputs must remain private.
- For a future ChatGPT desktop connection on Windows, validate the actual local plugin/transport setup and model-facing data flow before exposing any unpublished text. A local corpus does not imply a local-only LLM.

## Evaluation order

After source review, prepare matched content briefs and generate ordinary and PenTwin-guided drafts. Use the automated proxy across multiple writers and sections, while preserving the distinction between metric movement and recognizable author voice. Keep holdout papers untouched during prompt and feature development. Treat the prior 5/6 attribution pilot as exploratory; it does not measure the likeness of generated text.

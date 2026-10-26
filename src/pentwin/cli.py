"""Stage 1 corpus preparation. No model calls and no MCP generation tools."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


SECTIONS = {"abstract", "introduction", "methods", "results", "discussion", "conclusion", "other"}
MOVES = {
    "background", "gap", "objective", "method", "finding", "comparison",
    "interpretation", "limitation", "implication", "future_work", "other",
}
HEADINGS = {
    "abstract": "abstract", "summary": "abstract",
    "introduction": "introduction", "background": "introduction",
    "methods": "methods", "materials and methods": "methods", "methodology": "methods",
    "results": "results", "findings": "results", "results and discussion": "results",
    "discussion": "discussion", "conclusions": "conclusion", "conclusion": "conclusion",
}
STOP_HEADINGS = {"references", "bibliography", "acknowledgments", "acknowledgements", "supplementary material", "appendix"}
FIELDS = ["candidate_id", "paper_id", "family_id", "split", "source_location", "source_sha256", "section_suggested", "text", "extraction_warning", "include", "source_verified", "section", "move", "review_note"]
LOCKED_FIELDS = FIELDS[:9]


class CorpusError(ValueError):
    pass


def canonical_heading(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^\d+(?:\.\d+)*[.\s]+", "", text.strip().lower())).strip(" .:")


def clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\u00a0", " ")).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("papers"), list):
        raise CorpusError("Manifest must contain a papers list")
    papers = data["papers"]
    if len(papers) < 3:
        raise CorpusError("At least three papers are required for this pilot")
    ids, groups = set(), set()
    for paper in papers:
        if not isinstance(paper, dict):
            raise CorpusError("Every paper must be an object")
        for key in ("paper_id", "family_id", "file", "authorship", "status"):
            if not isinstance(paper.get(key), str) or not paper[key].strip():
                raise CorpusError(f"Each paper requires a nonempty {key}")
        paper.setdefault("model_excerpt_permission", "no")
        if paper["paper_id"] in ids:
            raise CorpusError("Duplicate paper_id")
        ids.add(paper["paper_id"])
        groups.add(paper["family_id"])
        if paper["authorship"] not in {"primary_confirmed", "uncertain", "not_primary"}:
            raise CorpusError("Invalid authorship value")
        if paper["status"] not in {"published", "unpublished"}:
            raise CorpusError("Invalid status value")
        if paper["model_excerpt_permission"] not in {"yes", "no"}:
            raise CorpusError("model_excerpt_permission must explicitly be yes or no")
        source = (path.parent / paper["file"]).resolve()
        if not source.is_file() or source.suffix.lower() not in {".pdf", ".docx", ".tex"}:
            raise CorpusError(f"Unsupported or missing file for {paper['paper_id']}: {source}")
        paper["_source"] = source
    if len(groups) < 3:
        raise CorpusError("At least three independent paper families are required; versions share a family_id")
    return papers


def assign_splits(papers: list[dict], seed: str) -> dict[str, str]:
    families = sorted({p["family_id"] for p in papers})
    held_out = min(families, key=lambda family: hashlib.sha256(f"{seed}:{family}".encode()).hexdigest())
    return {family: "holdout" if family == held_out else "development" for family in families}


def _docx_candidates(source: Path):
    from docx import Document
    from docx.table import Table

    doc = Document(source)
    section, stop = "other", False
    for index, block in enumerate(doc.iter_inner_content(), 1):
        if isinstance(block, Table):
            continue
        text = clean(block.text)
        if not text:
            continue
        style = (block.style.name if block.style else "").lower()
        if style.startswith("heading"):
            key = canonical_heading(text)
            if key in STOP_HEADINGS:
                stop = True
            if key in HEADINGS:
                section, stop = HEADINGS[key], False
            continue
        if stop or style.startswith(("caption", "title", "subtitle")):
            continue
        yield f"paragraph:{index}", section, text, "review_heading_and_inline_objects"


def _pdf_candidates(source: Path):
    import pdfplumber

    section, stop = "other", False
    with pdfplumber.open(source) as doc:
        for page_number, page in enumerate(doc.pages, 1):
            if stop:
                break
            lines = page.extract_text_lines(return_chars=False)
            if not lines:
                continue
            parts, first, prev = [], 0, None

            def candidate(last):
                if not parts or stop:
                    return None
                text = clean(" ".join(parts))
                return (f"page:{page_number}:lines:{first}-{last}", section, text,
                        "pdf_order_columns_headers_tables_and_ocr_must_be_checked")

            for index, line in enumerate(lines, 1):
                text = clean(line["text"])
                if not text:
                    continue
                key = canonical_heading(text)
                if key in STOP_HEADINGS or key in HEADINGS:
                    result = candidate(index - 1)
                    if result:
                        yield result
                    parts, prev = [], None
                    if key in STOP_HEADINGS:
                        stop = True
                    elif not stop:
                        section, stop = HEADINGS[key], False
                    continue
                if stop:
                    continue
                if prev is not None:
                    line_height = max(prev["bottom"] - prev["top"], 1)
                    gap = line["top"] - prev["bottom"]
                    column_jump = abs(line["x0"] - prev["x0"]) > page.width * 0.25
                    paragraph_indent = (line["x0"] - prev["x0"] > max(12, line_height)) and parts[-1].endswith((".", ";", ":"))
                    if gap > line_height * 0.8 or column_jump or paragraph_indent:
                        result = candidate(index - 1)
                        if result:
                            yield result
                        parts = []
                if not parts:
                    first = index
                parts.append(text)
                prev = line
            result = candidate(len(lines))
            if result:
                yield result


def _tex_candidates(source: Path):
    if shutil.which("pandoc") is None:
        raise CorpusError("LaTeX extraction requires pandoc installed locally")
    proc = subprocess.run(
        ["pandoc", "--from=latex", "--to=markdown", "--wrap=none", str(source)],
        cwd=source.parent, capture_output=True, text=True, timeout=90, check=False,
    )
    if proc.returncode:
        raise CorpusError(f"pandoc failed for {source.name}: {proc.stderr[:300]}")
    section, stop, parts, start = "other", False, [], 1
    for lineno, line in enumerate(proc.stdout.splitlines(), 1):
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            if parts and not stop:
                yield f"markdown_lines:{start}-{lineno - 1}", section, clean(" ".join(parts)), "latex_conversion_and_includes_must_be_checked"
            parts = []
            key = canonical_heading(heading.group(1))
            if key in STOP_HEADINGS:
                stop = True
            elif key in HEADINGS:
                section, stop = HEADINGS[key], False
            continue
        if not line.strip():
            if parts and not stop:
                yield f"markdown_lines:{start}-{lineno - 1}", section, clean(" ".join(parts)), "latex_conversion_and_includes_must_be_checked"
            parts = []
        elif not parts:
            parts, start = [line.strip()], lineno
        else:
            parts.append(line.strip())
    if parts and not stop:
        yield f"markdown_lines:{start}-{lineno}", section, clean(" ".join(parts)), "latex_conversion_and_includes_must_be_checked"


def extract(source: Path):
    return {".pdf": _pdf_candidates, ".docx": _docx_candidates, ".tex": _tex_candidates}[source.suffix.lower()](source)


def prepare(manifest: Path, out: Path, seed: str) -> dict:
    papers = load_manifest(manifest)
    content_families = {}
    for paper in papers:
        digest = sha256(paper["_source"])
        prior_family = content_families.setdefault(digest, paper["family_id"])
        if prior_family != paper["family_id"]:
            raise CorpusError("Identical source bytes cannot belong to different paper families")
    resolved_output = out.resolve()
    if any((parent / ".git").exists() for parent in (resolved_output, *resolved_output.parents)):
        raise CorpusError("Private corpus output must be outside every Git working tree")
    if out.exists() and any(out.iterdir()):
        raise CorpusError("Output directory must be empty; keep prior reviews and runs immutable")
    out.mkdir(parents=True, exist_ok=True)
    splits = assign_splits(papers, seed)
    rows, metadata, discarded_corrupt = [], [], 0
    for paper in papers:
        source = paper["_source"]
        source_digest = sha256(source)
        metadata.append({k: v for k, v in paper.items() if not k.startswith("_")} | {"source_path": str(source), "sha256": source_digest, "split": splits[paper["family_id"]]})
        for location, section, text, warning in extract(source):
            if "\x00" in text or "\ufffd" in text:
                discarded_corrupt += 1
                continue
            if len(text.split()) < 5:
                continue
            cid = hashlib.sha256(f"{paper['paper_id']}:{source_digest}:{location}:{text}".encode()).hexdigest()[:20]
            rows.append({"candidate_id": cid, "paper_id": paper["paper_id"], "family_id": paper["family_id"],
                         "split": splits[paper["family_id"]], "source_location": location, "source_sha256": source_digest,
                         "section_suggested": section, "text": text, "extraction_warning": warning,
                         "include": "", "source_verified": "", "section": "", "move": "", "review_note": ""})
    if not rows:
        raise CorpusError("No candidate text extracted; inspect the input files")
    with (out / "review.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out / "candidates.lock.json").write_text(json.dumps({r["candidate_id"]: hashlib.sha256(
        json.dumps({k: r[k] for k in LOCKED_FIELDS}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        for r in rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "manifest.lock.json").write_text(json.dumps({"schema": 1, "seed": seed, "papers": metadata}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"papers": len(papers), "families": len(splits), "candidates": len(rows), "discarded_corrupt": discarded_corrupt,
            "holdout_families": sum(v == "holdout" for v in splits.values())}


def seal(out: Path) -> dict:
    lock = json.loads((out / "manifest.lock.json").read_text(encoding="utf-8"))
    candidates = json.loads((out / "candidates.lock.json").read_text(encoding="utf-8"))
    by_id = {p["paper_id"]: p for p in lock["papers"]}
    for p in by_id.values():
        source = Path(p["source_path"])
        if not source.is_file() or sha256(source) != p["sha256"]:
            raise CorpusError(f"Source missing or changed since preparation: {p['paper_id']}")
    with (out / "review.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != FIELDS:
            raise CorpusError("review.csv columns were changed")
        rows = list(reader)
    accepted, seen = [], set()
    for row in rows:
        cid = row["candidate_id"]
        if cid in seen or row["paper_id"] not in by_id or cid not in candidates:
            raise CorpusError("Duplicated or unknown candidate in review.csv")
        seen.add(cid)
        fingerprint = hashlib.sha256(json.dumps({k: row[k] for k in LOCKED_FIELDS}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if fingerprint != candidates[cid]:
            raise CorpusError(f"Extracted text or provenance changed for {cid}; rerun prepare")
        paper = by_id[row["paper_id"]]
        if row["family_id"] != paper["family_id"] or row["split"] != paper["split"] or row["source_sha256"] != paper["sha256"]:
            raise CorpusError(f"Provenance/split changed for {cid}")
        if row["include"] not in {"yes", "no"}:
            raise CorpusError(f"Every row requires include=yes/no: {cid}")
        if row["include"] == "no":
            continue
        if row["source_verified"] != "yes":
            raise CorpusError(f"Accepted row requires source_verified=yes after visual comparison: {cid}")
        if paper["authorship"] != "primary_confirmed":
            raise CorpusError(f"Cannot accept unconfirmed primary authorship: {cid}")
        if row["section"] not in SECTIONS or row["move"] not in MOVES:
            raise CorpusError(f"Accepted row needs a valid human-checked section and move: {cid}")
        if row["section"] == "other" and not row["review_note"].strip():
            raise CorpusError(f"Explain other section before acceptance: {cid}")
        accepted.append({k: row[k] for k in ("candidate_id", "paper_id", "family_id", "split", "source_location", "source_sha256", "section", "move", "text")}
                        | {"model_excerpt_permission": paper["model_excerpt_permission"], "status": paper["status"]})
    if seen != set(candidates):
        raise CorpusError("Review rows were removed; review every candidate explicitly")
    dev_families = {r["family_id"] for r in accepted if r["split"] == "development"}
    test_families = {r["family_id"] for r in accepted if r["split"] == "holdout"}
    if len(dev_families) < 2 or len(test_families) < 1:
        raise CorpusError("Accepted data must cover at least two development and one holdout paper family")
    target = out / "corpus.jsonl"
    if target.exists():
        raise CorpusError("Sealed corpus exists; create a new run to change reviewed data")
    with target.open("w", encoding="utf-8") as fh:
        for row in accepted:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "corpus.sha256").write_text(sha256(target) + "\n", encoding="ascii")
    return {"accepted": len(accepted), "development": sum(r["split"] == "development" for r in accepted),
            "holdout": sum(r["split"] == "holdout" for r in accepted)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and review a local PenTwin research corpus")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Extract review candidates; never sends source data to a model")
    prep.add_argument("manifest", type=Path)
    prep.add_argument("output", type=Path)
    prep.add_argument("--seed", default="pentwin-pilot-v1")
    final = sub.add_parser("seal", help="Seal explicitly reviewed candidates into a split corpus")
    final.add_argument("output", type=Path)
    server = sub.add_parser("serve", help="Run the local read-only MCP server over stdio")
    server.add_argument("output", type=Path, help="Absolute path to a sealed private run")
    blind = sub.add_parser("blind", help="Prepare a private, same-content blinded rating sheet")
    blind.add_argument("cases", type=Path)
    blind.add_argument("output", type=Path)
    blind.add_argument("--seed", required=True)
    report = sub.add_parser("ratings", help="Summarize a completed blinded rating sheet")
    report.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from pentwin.server import serve
            serve(args.output)
            return 0
        if args.command in {"blind", "ratings"}:
            from pentwin.evaluation import make_blind_pairs, summarize
            result = make_blind_pairs(args.cases, args.output, args.seed) if args.command == "blind" else summarize(args.output)
        else:
            result = prepare(args.manifest, args.output, args.seed) if args.command == "prepare" else seal(args.output)
    except (CorpusError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(f"PenTwin stopped: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

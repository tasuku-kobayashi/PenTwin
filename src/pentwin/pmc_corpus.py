"""Private, reviewed JATS Discussion extractor for open-access life-science pilots.

The user supplies the six article XML files and verifies original drafting.
No author name, identifier, or extracted passage is returned in the report.
"""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.style_engine import WORD


PMC_ID = re.compile(r"PMC[0-9]{4,12}$")
EXCLUDED = {"xref", "table-wrap", "fig", "disp-formula", "fn", "supplementary-material"}


def _cc_by_license(license_node: ET.Element) -> bool:
    """Accept URL or explicit CC BY prose, but never NC/ND/SA variants."""
    value = str(license_node.attrib) + " " + " ".join(license_node.itertext())
    normalized = re.sub(r"\s+", " ", value).lower()
    return ("creativecommons.org/licenses/by/" in normalized or
            ("creative commons attribution license" in normalized and
             re.search(r"\bcc\s?by\b", normalized) is not None)) and not re.search(
                 r"\bcc\s?by\s?[-–]\s?(?:nc|nd|sa)\b|creativecommons\.org/licenses/by-(?:nc|nd|sa)/",
                 normalized)


def fetch_open_access_xml(pmcid: str, destination: Path) -> None:
    """Opt-in download from Europe PMC's OA fullTextXML endpoint."""
    if not PMC_ID.fullmatch(pmcid) or destination.exists() or any(
            (parent / ".git").exists() for parent in (destination.resolve(), *destination.resolve().parents)):
        raise CorpusError("Provide a valid PMCID and a new destination")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    with urllib.request.urlopen(url, timeout=20) as response:
        body = response.read(5_000_001)
    if len(body) > 5_000_000:
        raise CorpusError("OA XML exceeds the local 5 MB limit")
    ET.fromstring(body)  # reject HTML error pages
    destination.write_bytes(body)


def _visible(node: ET.Element) -> str:
    parts = [node.text or ""]
    for child in node:
        if child.tag.split("}")[-1] not in EXCLUDED:
            parts.append(_visible(child))
        parts.append(child.tail or "")
    return "".join(parts)


def build_manifest(private_spec: Path, output: Path) -> dict:
    if any((parent / ".git").exists() for path in (private_spec, output)
           for parent in (path.resolve(), *path.resolve().parents)):
        raise CorpusError("PMC source data and output must stay outside Git working trees")
    payload = json.loads(private_spec.read_text(encoding="utf-8"))
    items = payload.get("papers") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) != 6 or output.exists():
        raise CorpusError("Use six private article specifications and a new output directory")
    authors, used_ids, used_paper_ids, papers = {}, set(), set(), []
    staging = []
    for item in items:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip()
                                               for k in ("author_id", "paper_id", "pmcid", "xml", "stratum")):
            raise CorpusError("Every paper needs author_id, paper_id, PMCID, XML path and stratum")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", item["paper_id"]) or item["paper_id"] in used_paper_ids:
            raise CorpusError("Paper IDs must be unique safe identifiers")
        used_paper_ids.add(item["paper_id"])
        if not PMC_ID.fullmatch(item["pmcid"]) or item["pmcid"] in used_ids or item.get("primary_drafter_verified") is not True:
            raise CorpusError("Require six unique PMCIDs and verified original drafting for each assigned author")
        used_ids.add(item["pmcid"])
        authors[item["author_id"]] = authors.get(item["author_id"], 0) + 1
        root = ET.parse((private_spec.parent / item["xml"]).resolve()).getroot()
        if root.attrib.get("article-type") != "research-article":
            raise CorpusError("Only JATS research articles are accepted in this pilot")
        recorded = {n.text.strip() for n in root.findall(".//article-id") if n.text}
        if item["pmcid"] not in recorded:
            raise CorpusError("PMCID does not match the local OA XML")
        if not any(_cc_by_license(node) for node in root.findall(".//license")):
            raise CorpusError("Only verified CC BY OA XML is accepted in this pilot")
        target_title = item.get("section_title", "discussion").lower().strip()
        body = root.find(".//body")
        sections = [] if body is None else [s for s in body.findall("sec")
                                            if (s.findtext("title") or "").lower().strip() == target_title]
        if len(sections) != 1:
            raise CorpusError("Exactly one matching top-level Discussion section is required")
        paragraphs = [re.sub(r"\s+", " ", _visible(p)).strip() for p in sections[0].findall(".//p")]
        text = "\n\n".join(p for p in paragraphs if p)
        if len(WORD.findall(text)) < 200:
            raise CorpusError("Each reviewed Discussion needs at least 200 English words")
        staging.append((item["paper_id"], text))
        metadata = {"author_id": item["author_id"], "paper_id": item["paper_id"],
                    "stratum": item["stratum"], "path": item["paper_id"] + ".txt",
                    "genre": "original_research", "section": "discussion",
                    "primary_drafter_verified": True}
        journal = root.findtext(".//journal-meta/journal-title-group/journal-title") or root.findtext(".//journal-meta/journal-title")
        if journal:
            metadata["journal"] = journal.strip()
        for date in root.findall(".//article-meta/pub-date"):
            year, month = date.findtext("year"), date.findtext("month")
            if year and month and re.fullmatch(r"\d{4}", year) and re.fullmatch(r"\d{1,2}", month) and 1 <= int(month) <= 12:
                metadata["publication_month"] = f"{year}-{int(month):02d}"
                break
        if isinstance(item.get("topic_id"), str) and item["topic_id"].strip():
            metadata["topic_id"] = item["topic_id"].strip()
        papers.append(metadata)
    if len(authors) != 2 or sorted(authors.values()) != [3, 3] or len({p["stratum"] for p in papers}) != 1:
        raise CorpusError("Use two independently verified original drafters, three papers each, in one matched stratum")
    output.mkdir(parents=True)
    for paper_id, text in staging:
        (output / (paper_id + ".txt")).write_text(text, encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps({"papers": papers}, indent=2), encoding="utf-8")
    return {"status": "private_oa_discussions_prepared", "papers": 6, "authors": 2,
            "limitations": "Authorship and section review are asserted by the private spec; OA status alone does not verify a unique drafter. Inspect XML paragraph extraction and topic/journal/time matching before interpreting scores."}

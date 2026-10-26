import asyncio
import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from docx import Document
from mcp import Client, StdioServerParameters

from pentwin.cli import CorpusError, prepare, seal
from pentwin.server import build_server, load_corpus
from pentwin.style_engine import aggregate


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        papers = []
        for i in range(4):
            doc = Document()
            doc.add_heading("Introduction", 1)
            doc.add_paragraph(f"A synthetic pathway in set {i} may alter expression. This preliminary finding requires an independent assay to assess the response.")
            doc.add_paragraph(f"In set {i}, the control and treatment samples were assayed separately. The observations are limited to these artificial measurements.")
            doc.add_paragraph(f"We observed a further artificial pattern in set {i} during this synthetic trial.")
            source = self.root / f"sample{i}.docx"
            doc.save(source)
            papers.append({"paper_id": f"p{i}", "family_id": f"f{i}", "file": source.name,
                           "authorship": "primary_confirmed", "status": "published", "model_excerpt_permission": "yes"})
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"papers": papers}))
        self.run = self.root / "run"
        prepare(self.manifest, self.run, "synthetic")
        with (self.run / "review.csv").open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            row.update(include="yes", source_verified="yes", section="introduction", move="background")
        with (self.run / "review.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        seal(self.run)

    def tearDown(self):
        self.temp.cleanup()

    def test_permission_no_still_allows_aggregate_but_no_source_text_leaves(self):
        rows = load_corpus(self.run)
        held = [r for r in rows if r["split"] == "holdout"]
        denied = next(r for r in rows if r["split"] == "development")
        unpublished = next(r for r in rows if r["split"] == "development" and r["family_id"] != denied["family_id"])
        for row in rows:
            if row["family_id"] == denied["family_id"]:
                row["model_excerpt_permission"] = "no"
            if row["family_id"] == unpublished["family_id"]:
                row["status"] = "unpublished"
        response = json.dumps(aggregate(rows))
        self.assertNotIn(held[0]["text"], response)
        self.assertNotIn(denied["text"], response)
        self.assertNotIn(unpublished["text"], response)
        self.assertEqual(aggregate(rows)["status"], "provisional")

    def test_tampered_corpus_and_unsealed_run_fail_closed(self):
        (self.run / "corpus.jsonl").write_text("{}\n")
        with self.assertRaisesRegex(CorpusError, "changed"):
            load_corpus(self.run)
        with self.assertRaises(CorpusError):
            build_server(self.root)

    def test_stdio_sdk_handshake_discovery_and_tool_call(self):
        async def exercise():
            import sys
            server = StdioServerParameters(command=sys.executable, args=["-m", "pentwin.cli", "serve", str(self.run)],
                                           env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
            async with Client(server) as client:
                tools = await client.list_tools()
                self.assertEqual({t.name for t in tools.tools}, {"corpus_status", "style_profile", "author_style_card", "axis_plan", "generation_protocol", "offline_evaluate", "rewrite_plan", "assess_revision"})
                status = await client.call_tool("corpus_status", {})
                self.assertFalse(status.is_error)
                self.assertTrue(json.loads(status.content[0].text)["sealed"])
                profile = await client.call_tool("style_profile", {})
                self.assertFalse(profile.is_error)
                response = json.loads(profile.content[0].text)
                self.assertEqual(response["status"], "provisional")
                self.assertFalse(any(k.startswith("function:") for k in response["target"]))
                held = [r["text"] for r in load_corpus(self.run) if r["split"] == "holdout"]
                self.assertTrue(all(t not in json.dumps(response) for t in held))
                self.assertTrue(all(r["text"] not in json.dumps(response) for r in load_corpus(self.run)))
                card = await client.call_tool("author_style_card", {"section": "introduction"})
                self.assertFalse(card.is_error)
                self.assertNotIn("synthetic pathway", json.dumps(json.loads(card.content[0].text)))
                isolated = await client.call_tool("axis_plan", {
                    "draft": "The synthetic pathway produced a measured response in this assay.",
                    "section": "introduction", "axis": "none"})
                self.assertFalse(isolated.is_error)
                self.assertEqual(json.loads(isolated.content[0].text)["instructions"], [])
                stance = await client.call_tool("axis_plan", {
                    "draft": "The synthetic pathway produced a measured response in this assay.",
                    "section": "introduction", "axis": "stance"})
                self.assertFalse(stance.is_error)
                stance_payload = json.loads(stance.content[0].text)
                self.assertEqual(stance_payload["status"], "experimental_plan")
                protocol = await client.call_tool("generation_protocol", {"section": "introduction"})
                self.assertFalse(protocol.is_error)
                protocol_payload = json.loads(protocol.content[0].text)
                self.assertEqual(set(protocol_payload["conditions"]),
                                 {"none", "lexical", "ending", "order", "lexical_ending", "lexical_order", "ending_order", "all"})
                self.assertTrue(all(r["text"] not in json.dumps(protocol_payload) for r in load_corpus(self.run)))
                target = "A human authored target passage provides the opening of a synthetic experiment. " * 12
                anchored = await client.call_tool("generation_protocol", {"section": "introduction",
                    "target_text": target, "confirmed_author_written": True})
                self.assertFalse(anchored.is_error)
                anchor = json.loads(anchored.content[0].text)["conditions"]["all_snippet"]
                self.assertEqual(anchor["anchor_words"], min(50, len(target.split()) // 5))
                self.assertNotIn(target, json.dumps(anchor))
                from pentwin.ablation_protocol import CONDITIONS
                manifests = []
                for cohort in ("c1", "c2"):
                    folder = self.root / cohort
                    folder.mkdir()
                    entries = []
                    for author in "AB":
                        for index in range(5):
                            name = f"{author}{index}"
                            body = ("We suggest the artificial molecular pattern may be limited. " if author == "A"
                                    else "The observed synthetic assay demonstrates a direct pattern here. ") * 30
                            (folder / (name + ".txt")).write_text(body + f" Independent marker {cohort} {name} appears here.")
                            entries.append({"author_id": author, "paper_id": name, "stratum": "synthetic",
                                            "path": name + ".txt"})
                    manifest = folder / "manifest.json"
                    manifest.write_text(json.dumps({"papers": entries}))
                    manifests.append(manifest)
                baseline = "The synthetic assay produced an artificial molecular observation in this sample. " * 22
                cases, scores = [], []
                for content in ("one", "two"):
                    for author in "AB":
                        case_id = content + author
                        brief = "The assay found an artificial observation."
                        variants = {label: baseline for label in CONDITIONS if label != "none"}
                        cases.append({"case_id": case_id, "author_id": author, "content_id": content,
                                      "model": "injected-test", "section": "discussion",
                                      "content_brief": brief, "baseline": baseline, "variants": variants})
                        scores.append({"case_id": case_id,
                                       "reference_sha256": hashlib.sha256(brief.encode()).hexdigest(),
                                       "scores": {label: {"sha256": hashlib.sha256(baseline.encode()).hexdigest(),
                                                          "similarity": 0.9} for label in ["none", *variants]}})
                cases_file, scores_file = self.root / "offline-cases.json", self.root / "offline-scores.json"
                cases_file.write_text(json.dumps({"cases": cases}))
                scores_file.write_text(json.dumps({"model": "injected-sbert-test", "metric": "cosine", "cases": scores}))
                offline = await client.call_tool("offline_evaluate", {"first_manifest": str(manifests[0]),
                    "second_manifest": str(manifests[1]), "cases_file": str(cases_file),
                    "semantic_scores_file": str(scores_file)})
                self.assertFalse(offline.is_error)
                offline_report = json.loads(offline.content[0].text)
                self.assertEqual(offline_report["cases"], 4)
                self.assertEqual(offline_report["summary"]["all"]["semantic_pass"], 4)
                self.assertNotIn("artificial molecular observation", json.dumps(offline_report))
                self.assertTrue(all("stance" not in instruction or "soft" in instruction
                                    for instruction in stance_payload["instructions"]))
                plan = await client.call_tool("rewrite_plan", {"draft": "The synthetic response was 12.5 mg/mL in the assay.",
                                                               "section": "introduction"})
                self.assertFalse(plan.is_error)
                plan_response = json.loads(plan.content[0].text)
                self.assertEqual(plan_response["status"], "rewrite_guidance")
                self.assertFalse(any(k.startswith("function:") for k in plan_response["target"]))
                self.assertIn("Authorial style only", plan_response["scope"])
                checked = await client.call_tool("assess_revision", {
                    "original": "The synthetic response was 12.5 mg/mL in the assay.",
                    "revised": "The synthetic response was 15 mg/mL in the assay.",
                    "section": "introduction"})
                self.assertFalse(checked.is_error)
                self.assertEqual(json.loads(checked.content[0].text)["status"], "style_diagnostic_only")
        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()

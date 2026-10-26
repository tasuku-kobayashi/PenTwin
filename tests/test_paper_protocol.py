import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pentwin.ablation_protocol import CONDITIONS, snippet_from_target, conditions
from pentwin.cli import CorpusError
from pentwin.qualified_eval import qualify_evaluators, evaluate_factorial
from pentwin.semantic_guard import semantic_guard, load_local_encoder, make_semantic_template
from pentwin.axis_metrics import measure, technical_term_coverage


class FixedEncoder:
    def encode(self, texts, convert_to_numpy=True):
        # A deterministic fake that tests the pass/fail arithmetic, not SBERT.
        mapping = {"reference": [1.0, 0.0], "baseline": [0.9, 0.43589],
                   "safe": [0.88, 0.47497], "drift": [0.5, 0.86603]}
        return [mapping[t] for t in texts]


class ProtocolTests(unittest.TestCase):
    def test_four_of_six_is_an_axis_specific_exploration_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = []
            for cohort in ("one", "two"):
                folder = root / cohort
                folder.mkdir()
                (folder / "paper.txt").write_text(cohort)
                manifest = folder / "manifest.json"
                manifest.write_text(json.dumps({"papers": [{"path": "paper.txt"}]}))
                manifests.append(manifest)
            def counts(a, b, available=3):
                return {"A": {"correct": a, "available": available},
                        "B": {"correct": b, "available": available}}
            def report(lexical, ending, order):
                return {"per_author": {"lexical": counts(*lexical),
                                       "ending": counts(*ending),
                                       "order": counts(*order, available=0)},
                        "confounds": [], "domain_diagnostics": {}}
            with patch("pentwin.qualified_eval.calibrate", side_effect=[
                    report((1, 3), (2, 3), (0, 0)),
                    report((2, 2), (1, 3), (0, 0))]):
                gate = qualify_evaluators(*manifests)
            self.assertEqual(gate["threshold"]["per_cohort"], "at least 4/6")
            self.assertEqual(gate["status"], "partial_exploratory_eligible")
            self.assertTrue(gate["axes"]["lexical"]["eligible_for_exploratory_scoring"])
            self.assertTrue(gate["axes"]["ending"]["eligible_for_exploratory_scoring"])
            self.assertFalse(gate["axes"]["order"]["eligible_for_exploratory_scoring"])
            self.assertEqual(gate["axes"]["lexical"]["writer_imbalance"], [True, False])
            self.assertEqual(gate["axes"]["order"]["available"], [0, 0])

    def test_axis_matrix_requires_200_measurable_words(self):
        sentence = "However, we suggest the synthetic molecular assay indicates a limited effect here. "
        with self.assertRaisesRegex(CorpusError, "at least 200"):
            measure(sentence * 10)
        measured = measure(sentence * 20)
        self.assertGreaterEqual(measured["words"], 200)
        self.assertEqual(technical_term_coverage(measured, ["molecular", "assay"]), 1.0)
        self.assertEqual(technical_term_coverage(measured, ["molecular assay", "RNA-seq"]), 0.5)
        self.assertIsNone(technical_term_coverage(measured, []))

    def test_semantic_guard_compares_each_candidate_to_the_same_reference(self):
        r = semantic_guard("reference", "baseline", {"safe": "safe", "bad": "drift"}, FixedEncoder())
        self.assertEqual(r["status"], "scored")
        self.assertTrue(r["candidates"]["safe"]["pass"])
        self.assertFalse(r["candidates"]["bad"]["pass"])
        with self.assertRaisesRegex(CorpusError, "existing local"):
            load_local_encoder(Path("/does/not/exist"))

    def test_snippet_is_short_and_never_taken_from_sealed_paper(self):
        target = "A uniquely authored target opening belongs only to the separate human target. " * 12
        anchor = snippet_from_target(target)
        self.assertEqual(len(anchor.split()), min(50, len(target.split()) // 5))
        rows = [{"family_id": str(i), "candidate_id": str(i), "source_sha256": str(i),
                 "section": "discussion", "move": "finding", "split": "development",
                 "text": ("We may report this artificial result, which suggests a pattern. " * 9)}
                for i in range(2)]
        with self.assertRaisesRegex(CorpusError, "Confirm"):
            conditions(rows, "discussion", target_text=target)
        out = conditions(rows, "discussion", target_text=target, confirmed_author_written=True)
        self.assertEqual(len(out["conditions"]), 9)
        self.assertNotIn(target, json.dumps(out))
        with self.assertRaisesRegex(CorpusError, "separate"):
            conditions(rows, "discussion", target_text=rows[0]["text"], confirmed_author_written=True)

    def test_two_cohorts_gate_rejects_reused_papers_and_incomplete_ablation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = []
            for cohort in ("one", "two"):
                folder = root / cohort
                folder.mkdir()
                papers = []
                for author in "AB":
                    for index in range(3):
                        name = f"{author}{index}"
                        phrase = ("We could suggest a pattern in these artificial observations. "
                                  if author == "A" else
                                  "The artificial observations demonstrate a clear pattern here. ")
                        (folder / f"{name}.txt").write_text((phrase * 30) + cohort + name)
                        papers.append({"author_id": author, "paper_id": name,
                                       "stratum": "synthetic", "path": f"{name}.txt"})
                manifest = folder / "manifest.json"
                manifest.write_text(json.dumps({"papers": papers}))
                manifests.append(manifest)
            with self.assertRaisesRegex(CorpusError, "reuse"):
                qualify_evaluators(manifests[0], manifests[0])
            gate = qualify_evaluators(*manifests)
            self.assertEqual(set(gate["matrix"]), {"lexical", "ending", "order"})
            cases = []
            baseline = "The synthetic assay produced artificial observations in this sample. " * 24
            for content in ("c1", "c2"):
                for author in "AB":
                    cases.append({"case_id": content + author, "content_id": content,
                                  "author_id": author, "model": "test", "section": "discussion",
                                  "content_brief": "An artificial observation was recorded in an assay.",
                                  "baseline": baseline, "variants": {"lexical": baseline}})
            file = root / "cases.json"
            file.write_text(json.dumps({"cases": cases}))
            with self.assertRaisesRegex(CorpusError, "seven card"):
                evaluate_factorial(*manifests, file)
            for case in cases:
                case["variants"] = {label: baseline for label in CONDITIONS if label != "none"}
            file.write_text(json.dumps({"cases": cases}))
            template_file = root / "template.json"
            self.assertEqual(make_semantic_template(file, template_file)["cases"], 4)
            self.assertNotIn(baseline, template_file.read_text())
            report = evaluate_factorial(*manifests, file)
            self.assertEqual(report["status"], "semantic_unavailable")
            self.assertEqual(report["eligible_axes"], ["lexical", "ending"])
            self.assertEqual(report["excluded_axes"], ["order"])
            self.assertEqual(report["condition_set"], "full_factorial")
            self.assertEqual(report["summary"]["all"]["lexical"]["improved"], 0)
            self.assertIsNone(report["summary"]["all"]["semantic_pass"])
            self.assertNotIn("artificial observations demonstrate", json.dumps(report))
            class IdenticalEncoder:
                def encode(self, texts, convert_to_numpy=True):
                    return [[1.0, 0.0] for _ in texts]
            scored = evaluate_factorial(*manifests, file, IdenticalEncoder())
            self.assertEqual(scored["summary"]["all"]["semantic_pass"], 4)
            self.assertEqual(scored["summary"]["all"]["lexical"]["improved_and_semantic_pass"], 0)
            reduced = json.loads(json.dumps(cases))
            for case in reduced:
                case["variants"] = {label: baseline for label in ("lexical", "ending", "lexical_ending")}
                case["variants"]["lexical_ending_snippet"] = baseline
                case["snippet_anchor"] = "A separate human-written opening."
            file.write_text(json.dumps({"cases": reduced}))
            smaller = evaluate_factorial(*manifests, file, IdenticalEncoder())
            self.assertEqual(smaller["condition_set"], "eligible_axes_only")
            self.assertEqual(set(smaller["summary"]), set(reduced[0]["variants"]))
            file.write_text(json.dumps({"cases": cases}))
            imported = {"model": "locally-asserted-sbert-v1", "metric": "cosine", "cases": []}
            for case in cases:
                drafts = {"none": case["baseline"], **case["variants"]}
                imported["cases"].append({"case_id": case["case_id"],
                    "reference_sha256": hashlib.sha256(case["content_brief"].encode()).hexdigest(),
                    "scores": {label: {"sha256": hashlib.sha256(body.encode()).hexdigest(),
                                       "similarity": 0.80 if label == "all" and case["case_id"] == "c1A" else 0.90}
                               for label, body in drafts.items()}})
            score_file = root / "scores.json"
            score_file.write_text(json.dumps(imported))
            injected = evaluate_factorial(*manifests, file, semantic_scores_path=score_file)
            self.assertEqual(injected["summary"]["all"]["semantic_pass"], 3)
            imported["cases"][0]["scores"]["all"]["sha256"] = "0" * 64
            score_file.write_text(json.dumps(imported))
            with self.assertRaisesRegex(CorpusError, "hash mismatch"):
                evaluate_factorial(*manifests, file, semantic_scores_path=score_file)
            cases[0]["variants"]["all_snippet"] = baseline
            cases[0]["snippet_anchor"] = baseline
            cases[1]["variants"]["all_snippet"] = baseline
            cases[1]["snippet_anchor"] = baseline
            file.write_text(json.dumps({"cases": cases}))
            with self.assertRaisesRegex(CorpusError, "continuation"):
                evaluate_factorial(*manifests, file, IdenticalEncoder())


if __name__ == "__main__":
    unittest.main()

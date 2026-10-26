import json
import tempfile
import unittest
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.validation import diagnose
from pentwin.automatic_eval import evaluate_generations
from pentwin.heldout_eval import evaluate_heldout_axes
from pentwin.paper_grounded_eval import evaluate_paper_grounded


class ValidationTests(unittest.TestCase):
    def test_paper_grounded_calibration_abstains_on_undistinguishable_writers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            papers = []
            for author in ("A", "B"):
                for index in range(3):
                    paper_id = f"{author}{index}"
                    # Distinct documents but the same short-window style.
                    body = ("The artificial assay was repeated with a control sample. " * 16 +
                            f"Unique synthetic body marker {paper_id} was checked after the experiment. " * 16)
                    (root / f"{paper_id}.txt").write_text(body, encoding="utf-8")
                    papers.append({"author_id": author, "paper_id": paper_id,
                                   "stratum": "synthetic", "path": f"{paper_id}.txt"})
            manifest = root / "papers.json"
            manifest.write_text(json.dumps({"papers": papers}), encoding="utf-8")
            baseline = "The artificial assay was repeated with a control sample. " * 24
            cases = [{"case_id": f"{author}{index}", "content_id": f"c{index}",
                      "author_id": author, "model": "synthetic", "section": "discussion",
                      "baseline": baseline, "guided": baseline}
                     for index in range(2) for author in ("A", "B")]
            drafts = root / "drafts.json"
            drafts.write_text(json.dumps({"cases": cases}), encoding="utf-8")
            report = evaluate_paper_grounded(manifest, drafts)
            self.assertEqual(report["status"], "calibration_inadequate")
            self.assertEqual(report["calibration"]["correct_by_author"]["function_words"],
                             {"A": 0, "B": 0})
            self.assertEqual(report["generated"]["summary"]["function_words"]["improved"], 0)
            self.assertNotIn("Unique synthetic body marker", json.dumps(report))
            cases[1]["baseline"] += "An extra sentence was added here."
            drafts.write_text(json.dumps({"cases": cases}), encoding="utf-8")
            with self.assertRaisesRegex(CorpusError, "exact same model"):
                evaluate_paper_grounded(manifest, drafts)

    def test_heldout_axis_evaluation_keeps_text_private_and_checks_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            papers = []
            for author in ("A", "B"):
                for index in range(3):
                    paper_id = f"{author}{index}"
                    sentence = ("We suggest the synthetic finding could be relevant here. " if author == "A"
                                else "We report the synthetic finding in the artificial samples. ")
                    (root / f"{paper_id}.txt").write_text(sentence * (12 + index), encoding="utf-8")
                    papers.append({"author_id": author, "paper_id": paper_id,
                                   "stratum": "synthetic", "path": f"{paper_id}.txt"})
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"papers": papers}))
            baseline = "The synthetic result was recorded in an artificial assay. " * 7
            cases = [{"case_id": f"{content}-{author}", "content_id": content, "author_id": author,
                      "axis": "wording", "model": "synthetic", "baseline": baseline,
                      "guided": ("We suggest the synthetic finding in this artificial assay. " if author == "A"
                                 else "We report the synthetic finding in this artificial assay. ") * 7}
                     for content in ("c1", "c2") for author in ("A", "B")]
            path = root / "cases.json"
            path.write_text(json.dumps({"cases": cases}))
            result = evaluate_heldout_axes(manifest, path)
            self.assertEqual(result["cases"], 4)
            self.assertEqual(result["summary"]["wording"]["cases"], 4)
            self.assertNotIn("synthetic result was recorded", json.dumps(result))
            cases[1]["baseline"] += "Altered baseline."
            path.write_text(json.dumps({"cases": cases}))
            with self.assertRaisesRegex(CorpusError, "same baseline"):
                evaluate_heldout_axes(manifest, path)

    def test_automated_proxy_requires_same_content_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            papers = []
            for author in ("A", "B"):
                for index in range(3):
                    paper_id = f"{author}{index}"
                    sentence = (f"The artificial finding {index} was observed across several samples. " if author == "A"
                                else f"We observed an artificial finding {index} across multiple samples. ")
                    (root / f"{paper_id}.txt").write_text(sentence * 16, encoding="utf-8")
                    papers.append({"author_id": author, "paper_id": paper_id,
                                   "stratum": "synthetic", "path": f"{paper_id}.txt"})
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"papers": papers}))
            baseline = "The artificial method produced a consistent measurement in the samples. " * 7
            cases = [{"case_id": f"{author}{index}", "content_id": f"c{index}", "author_id": author,
                      "model": "synthetic", "section": "discussion", "baseline": baseline,
                      "guided": ("We observed a consistent measurement in the artificial samples. " if author == "B"
                                 else "The consistent measurement was observed in the artificial samples. ") * 7}
                     for index in range(2) for author in ("A", "B")]
            drafts = root / "drafts.json"
            drafts.write_text(json.dumps({"cases": cases}))
            result = evaluate_generations(manifest, drafts)
            self.assertEqual(result["cases"], 4)
            self.assertEqual(result["status"], "automated_proxy_only")
            self.assertNotIn("artificial method", json.dumps(result))
            self.assertEqual(set(result["by_author"]), {"A", "B"})
            self.assertNotIn("paragraph_sentences", result["features"]["short_passage"])
            self.assertIn("paragraph_sentences", result["features"]["length"])
            cases[1]["baseline"] += "Extra sentence unrelated to the shared baseline."
            drafts.write_text(json.dumps({"cases": cases}))
            with self.assertRaisesRegex(CorpusError, "same model, section and exact baseline"):
                evaluate_generations(manifest, drafts)

    def test_whole_paper_diagnostic_and_independence_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            papers = []
            for author in ("A", "B"):
                for index in range(3):
                    paper_id = f"{author}{index}"
                    sentence = (f"The synthetic observation {index} suggests a limited effect in this sample. "
                                if author == "A" else
                                f"We studied this synthetic sample {index} in detail, and we report an effect; the evidence is preliminary. ")
                    (root / f"{paper_id}.txt").write_text(sentence * (12 + index), encoding="utf-8")
                    papers.append({"author_id": author, "paper_id": paper_id,
                                   "stratum": "synthetic discussion", "path": f"{paper_id}.txt"})
            manifest = root / "papers.json"
            manifest.write_text(json.dumps({"papers": papers}), encoding="utf-8")
            report = diagnose(manifest)
            self.assertEqual(report["status"], "diagnostic_only")
            self.assertEqual(len(report["cases"]), 6)
            self.assertEqual(set(report["total_correct"]), {"length", "seven", "rhetoric", "function"})
            self.assertNotIn("synthetic observation", json.dumps(report))
            self.assertEqual(report["confounds"]["reported_risks"], ["missing_confound_metadata"])
            self.assertEqual(report["paired_vs_length"]["seven"]["gain_over_length"] -
                             report["paired_vs_length"]["seven"]["loss_to_length"],
                             report["increment_over_length"]["seven"])
            for item in papers:
                item.update({"publication_month": f"2024-0{int(item['paper_id'][-1]) + (1 if item['author_id'] == 'A' else 5)}",
                             "topic_id": "same_topic", "journal": "synthetic_journal", "genre": "research",
                             "section": "discussion", "primary_drafter_verified": True})
            manifest.write_text(json.dumps({"papers": papers}), encoding="utf-8")
            self.assertEqual(diagnose(manifest)["confounds"]["reported_risks"],
                             ["nonoverlapping_author_publication_periods"])
            papers[1]["path"] = papers[0]["path"]
            manifest.write_text(json.dumps({"papers": papers}), encoding="utf-8")
            with self.assertRaisesRegex(CorpusError, "independent"):
                diagnose(manifest)


if __name__ == "__main__":
    unittest.main()

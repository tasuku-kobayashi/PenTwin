import csv
import json
import tempfile
import unittest
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.evaluation import make_blind_pairs, summarize


class BlindEvaluationTests(unittest.TestCase):
    def test_randomized_key_is_separate_from_rating_and_summary_decodes_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases = root / "cases.json"
            cases.write_text(json.dumps({"cases": [
                {"case_id": "synthetic-1", "author_id": "A", "model": "GPT", "section": "results",
                 "baseline": "Baseline artificial wording.", "guided": "Guided artificial wording."},
                {"case_id": "synthetic-2", "author_id": "B", "model": "Claude", "section": "discussion",
                 "baseline": "Another baseline sentence.", "guided": "Another guided sentence."}]}))
            run = root / "blind"
            make_blind_pairs(cases, run, "private-seed")
            key = json.loads((run / "private_key.json").read_text())["guided_at"]
            with (run / "rating.csv").open(newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fields = reader.fieldnames
            self.assertNotIn("guided_at", (run / "rating.csv").read_text())
            for row in rows:
                row.update(preferred=key[row["case_id"]], likeness_a="3", likeness_b="3",
                           distinctiveness_a="2", distinctiveness_b="2",
                           naturalness_a="4", naturalness_b="4")
            with (run / "rating.csv").open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            summary = summarize(run)
            self.assertEqual(summary["preference"]["guided"], 2)
            self.assertEqual(summary["paired_dimensions"]["likeness"]["tie"], 2)
            self.assertEqual(summary["by_author"]["A"]["guided"], 1)
            self.assertNotIn("quality_gate", summary)
            rows[0]["author_id"] = "wrong"
            with (run / "rating.csv").open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(CorpusError, "provenance"):
                summarize(run)
            rows[0]["author_id"] = "A"
            rows[0]["distinctiveness_a"] = ""
            with (run / "rating.csv").open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(CorpusError):
                summarize(run)

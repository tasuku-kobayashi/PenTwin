import json
import tempfile
import unittest
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.validation import diagnose


class ValidationTests(unittest.TestCase):
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
            papers[1]["path"] = papers[0]["path"]
            manifest.write_text(json.dumps({"papers": papers}), encoding="utf-8")
            with self.assertRaisesRegex(CorpusError, "independent"):
                diagnose(manifest)


if __name__ == "__main__":
    unittest.main()

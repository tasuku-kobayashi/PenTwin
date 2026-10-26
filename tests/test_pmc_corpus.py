import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from pentwin.cli import CorpusError
from pentwin.pmc_corpus import build_manifest, _cc_by_license
from pentwin.axis_metrics import calibrate


class PMCCorpusTests(unittest.TestCase):
    def test_plain_text_cc_by_is_allowed_but_nc_is_not(self):
        by = ET.fromstring("<license>Creative Commons Attribution License 4.0 (CCBY)</license>")
        nc = ET.fromstring("<license>Creative Commons Attribution-Non Commercial License 4.0 (CCBY-NC)</license>")
        self.assertTrue(_cc_by_license(by))
        self.assertFalse(_cc_by_license(nc))

    def test_private_jats_extraction_and_length_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            papers = []
            for author in "AB":
                for i in range(3):
                    pmcid = f"PMC1000{int(author == 'B')}{i}00"
                    phrase = ("We observed an artificial biological result in this assay. " if author == "A"
                              else "The synthetic molecular finding was measured in this sample. ")
                    xml = (f'<article article-type="research-article" xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
                           f'<article-id pub-id-type="pmc">{pmcid}</article-id>'
                           f'<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
                           f'</article-meta></front><body><sec><title>Discussion</title><p>'
                           f'{phrase * 25} Trial number {i} ended with an additional synthetic observation.'
                           f'<xref ref-type="bibr">99</xref></p></sec></body></article>')
                    name = f"{author}{i}"
                    (root / f"{name}.xml").write_text(xml)
                    papers.append({"author_id": author, "paper_id": name, "pmcid": pmcid,
                                   "xml": f"{name}.xml", "stratum": "synthetic molecular study",
                                   "primary_drafter_verified": True})
            spec = root / "spec.json"
            spec.write_text(json.dumps({"papers": papers}))
            out = root / "prepared"
            result = build_manifest(spec, out)
            self.assertEqual(result["papers"], 6)
            self.assertNotIn("artificial biological", json.dumps(result))
            self.assertNotIn("99", (out / "A0.txt").read_text())
            self.assertEqual(len(calibrate(out / "manifest.json")["cases"]), 6)
            papers[0]["primary_drafter_verified"] = False
            spec.write_text(json.dumps({"papers": papers}))
            with self.assertRaisesRegex(CorpusError, "verified original drafting"):
                build_manifest(spec, root / "rejected")
            papers[0]["primary_drafter_verified"] = True
            spec.write_text(json.dumps({"papers": papers}))
            source = root / "A0.xml"
            source.write_text(source.read_text().replace('article-type="research-article"',
                                                         'article-type="review-article"', 1))
            with self.assertRaisesRegex(CorpusError, "research articles"):
                build_manifest(spec, root / "review-rejected")


if __name__ == "__main__":
    unittest.main()

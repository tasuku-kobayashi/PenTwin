import json
import unittest

from pentwin.style_engine import aggregate, assess, guidance


def row(family, text, split="development", section="results", permission="no"):
    return {"candidate_id": f"candidate-{family}", "source_sha256": f"hash-{family}",
            "family_id": family, "split": split, "section": section, "text": text,
            "model_excerpt_permission": permission, "status": "unpublished"}


class StyleLogicTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            row("a", "We observed a 12% response in the synthetic assay. We suggest that this result may reflect a limited effect. PRIVATE FAMILY A marker appears only here."),
            row("b", "We observed a 9% response in the synthetic assay. We suggest that the finding may reflect a limited effect. PRIVATE FAMILY B marker appears only here."),
            row("h", "The result demonstrates a large effect. The data demonstrate a large effect. PRIVATE HOLDOUT marker appears only here.", "holdout"),
        ]

    def test_local_profile_uses_permission_no_but_never_returns_original_text(self):
        result = aggregate(self.rows, "results")
        self.assertEqual(result["status"], "provisional")
        self.assertEqual(result["families"], 2)
        self.assertGreater(result["target"]["hedge_rate"], 0)
        self.assertIn("function:the", result["target"])
        self.assertIn("rhetoric:contrast", result["target"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        changed = [*self.rows, row("other-holdout", "May may may. We we we.", "holdout")]
        self.assertEqual(result, aggregate(changed, "results"))

    def test_rewrite_plan_prioritizes_authors_tendencies_and_falls_back(self):
        draft = "The synthetic response was 12% in the assay. The result demonstrates an effect."
        result = guidance(self.rows, draft, "results")
        self.assertEqual(result["status"], "rewrite_guidance")
        self.assertIn("use calibrated uncertainty only where the evidence supports it", result["prioritized_edits"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertTrue(guidance(self.rows, draft, "discussion")["section_fallback"])
        self.assertIn("function:the", result["target"])

    def test_revision_style_diagnostic_and_fidelity_alarms_are_separate(self):
        original = "The synthetic response was 12% in the assay. The result demonstrates an effect."
        revision = "We observed a synthetic response of 12% in the assay. We suggest that this result may reflect an effect."
        result = assess(self.rows, original, revision, "results")
        self.assertLess(result["style_distance_diagnostic"]["after"], result["style_distance_diagnostic"]["before"])
        self.assertEqual(result["status"], "needs_human_review")
        self.assertIn("uncertainty", result["count_changes"])
        altered = assess(self.rows, original, revision.replace("12%", "21%"), "results")
        self.assertIn("21%", altered["lexical_alarms"]["new_numeric_tokens"])
        changed_citation = assess(self.rows, original + " [12]", revision + " [13]", "results")
        self.assertEqual(changed_citation["citation_token_changes"], {"added": ["[13]"], "removed": ["[12]"]})


if __name__ == "__main__":
    unittest.main()

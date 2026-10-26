import json
import unittest

from pentwin.cli import CorpusError
from pentwin.style_engine import aggregate, assess, guidance


def row(family, text, split="development", section="results", permission="no"):
    return {"candidate_id": f"candidate-{family}", "source_sha256": f"hash-{family}",
            "family_id": family, "split": split, "section": section, "text": text,
            "move": "finding", "model_excerpt_permission": permission, "status": "unpublished"}


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

    def test_wording_preference_requires_two_paper_families(self):
        rows = [
            row("a", "However, we observed the synthetic response. However, we reported another observation."),
            row("b", "We observed the synthetic response today. We reported another synthetic observation today."),
        ]
        self.assertNotIn("however", aggregate(rows, "results")["common_connectors"])

    def test_rewrite_plan_prioritizes_tendencies_only_with_scoped_evidence(self):
        draft = "The synthetic response was 12% in the assay. The result demonstrates an effect."
        result = guidance(self.rows, draft, "results")
        self.assertEqual(result["status"], "rewrite_guidance")
        self.assertTrue(any("use more hedging expressions in the author's typical phrasing" in edit
                            for edit in result["prioritized_edits"]))
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(guidance(self.rows, draft, "discussion")["status"], "insufficient_evidence")
        self.assertEqual(guidance(self.rows, draft, "results", "limitation")["status"], "insufficient_evidence")
        self.assertEqual(guidance(self.rows, draft, "results", "finding")["status"], "rewrite_guidance")
        self.assertNotIn("function:the", result["target"])
        self.assertEqual(result["diagnostic_features_excluded_from_rewrite"], ["function_word_rates"])
        self.assertIn("sentence_words", result["stable_style_signature"])
        self.assertTrue(any("author median about" in edit for edit in result["prioritized_edits"]))

    def test_revision_style_diagnostic_does_not_claim_author_likeness(self):
        original = "The synthetic response was 12% in the assay. The result demonstrates an effect."
        revision = "We observed a synthetic response of 12% in the assay. We suggest that this result may reflect an effect."
        result = assess(self.rows, original, revision, "results")
        self.assertLess(result["style_distance_diagnostic"]["after"], result["style_distance_diagnostic"]["before"])
        self.assertEqual(result["status"], "style_diagnostic_only")
        self.assertIn("short_passage_style_distance_diagnostic", result)
        self.assertNotIn("lexical_alarms", result)
        self.assertNotIn("protected_spans", guidance(self.rows, original, "results"))
        self.assertIn("independent verifier", guidance(self.rows, original, "results")["scope"])


if __name__ == "__main__":
    unittest.main()

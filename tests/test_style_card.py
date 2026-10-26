import json
import unittest

from pentwin.style_card import build_style_card, card_instructions, contrast_style_cards
from pentwin.style_engine import guidance


def paragraph(role: str) -> str:
    if role == "finding":
        return ("We observed a synthetic pattern in the samples. "
                "However, we observed another pattern in the controls. "
                "The measured response was recorded in every trial. "
                "We observed a third pattern in the assay. "
                "However, the synthetic pattern appeared again today. "
                "The data were reported in a final comparison.")
    return ("We suggest an interpretation of the artificial result. "
            "The difference suggests a possible explanation here. "
            "We suggest that the contrast has a role. "
            "The finding may indicate a second explanation. "
            "We suggest another interpretation for the pattern. "
            "The result may reflect the measured variation.")


class StyleCardTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        for family in ("A", "B"):
            for index, role in enumerate(("finding", "interpretation")):
                self.rows.append({
                    "candidate_id": f"{family}{index}", "source_sha256": f"{family}{index}",
                    "family_id": family, "split": "development", "section": "discussion",
                    "move": role, "text": paragraph(role),
                })
        self.rows.append({
            "candidate_id": "H", "source_sha256": "H", "family_id": "H",
            "split": "holdout", "section": "discussion", "move": "finding",
            "text": "PRIVATE HOLDOUT material must never appear in the style card. " * 6,
        })

    def test_supported_wording_stance_flow_and_private_holdout(self):
        card = build_style_card(self.rows, "discussion")
        self.assertEqual(card["status"], "provisional")
        self.assertEqual(card["flow"], [{"from": "finding", "to": "interpretation", "families": 2}])
        self.assertEqual(card["roles"]["finding"]["wording"]["connectors"][0]["term"], "however")
        self.assertEqual(card["roles"]["interpretation"]["wording"]["stance_verbs"][0]["term"], "suggest")
        self.assertIn("hedge_rate", card["roles"]["interpretation"]["stance"])
        self.assertNotIn("first_person_rate", card["roles"]["finding"]["stance"])
        self.assertNotIn("PRIVATE", json.dumps(card))
        self.assertTrue(any("finding → interpretation" in instruction for instruction in card_instructions(card)))
        plan = guidance(self.rows, "The synthetic pattern was seen. The result has several possible interpretations.",
                        "discussion")
        self.assertIn("finding", plan["conditional_style_card"]["roles"])
        self.assertIn("revise once", plan["revision_critique_prompt"])
        self.assertIn("However", json.dumps(self.rows))
        self.assertNotIn("We observed a synthetic pattern", json.dumps(plan))

    def test_role_without_two_families_abstains(self):
        only_one = [row for row in self.rows if row["family_id"] != "B"]
        self.assertEqual(build_style_card(only_one, "discussion")["status"], "insufficient_role_evidence")
        self.assertEqual(build_style_card(self.rows, "discussion", "limitation")["roles"], {})
        self.assertEqual(build_style_card(self.rows, "discussion", "finding")["flow"], [])

    def test_two_writers_get_different_executable_cards_on_same_roles(self):
        rival = []
        for family in ("C", "D"):
            for index, role in enumerate(("interpretation", "finding")):
                text = ("We report an artificial observation in this trial. "
                        "Therefore, we report the new measured pattern. "
                        "The samples were collected for this assay. "
                        "We report a second artificial observation. "
                        "Therefore, another synthetic pattern was found. "
                        "The final difference was reported to the group.")
                rival.append({"candidate_id": f"{family}{index}", "source_sha256": f"{family}{index}",
                              "family_id": family, "split": "development", "section": "discussion",
                              "move": role, "text": text})
        first = build_style_card(self.rows, "discussion")
        second = build_style_card(rival, "discussion")
        self.assertEqual(second["flow"], [{"from": "interpretation", "to": "finding", "families": 2}])
        self.assertEqual(second["roles"]["finding"]["wording"]["connectors"][0]["term"], "therefore")
        self.assertNotEqual(card_instructions(first), card_instructions(second))
        distinctive = contrast_style_cards(first, second)
        self.assertEqual(distinctive["status"], "candidate_distinctions")
        self.assertEqual(distinctive["flow"][0]["from"], "finding")
        self.assertEqual(distinctive["roles"]["finding"]["wording"]["connectors"][0]["term"], "however")
        self.assertEqual(contrast_style_cards(first, first)["status"], "insufficient_distinctive_evidence")


if __name__ == "__main__":
    unittest.main()

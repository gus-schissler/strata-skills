import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "find-in-stratagraph" / "SKILL.md"


class FindInStratagraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_PATH.read_text(encoding="utf-8")
        cls.lower = cls.skill.lower()

    def test_search_results_are_candidates_not_authority(self):
        self.assertIn("semantic_similarity", self.skill)
        self.assertRegex(
            self.lower,
            r"relative proximity, not truth, confidence, relevance, or currentness",
        )
        self.assertRegex(
            self.lower,
            r"existence in the graph does not establish that it is relevant, true, or current",
        )
        self.assertIn("graph grounding", self.lower)
        self.assertIn("externally verified truth", self.lower)

    def test_current_state_checks_each_dimension(self):
        for field in ("occurred_at", "occurred_at_basis", "review"):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", self.skill)
        self.assertRegex(self.lower, r"incoming `replaces` and `resolves`")
        self.assertRegex(self.lower, r"`counters` relationships in both directions")
        self.assertRegex(self.lower, r"counters and age alone do not")

    def test_replacement_chain_reaches_the_terminal_successor(self):
        self.assertRegex(
            self.lower,
            re.compile(
                r"follow its inbound `replaces` relationships:.*repeat until the endpoint has no further inbound `replaces`",
                re.DOTALL,
            ),
        )
        self.assertIn("terminal successor", self.lower)


if __name__ == "__main__":
    unittest.main()

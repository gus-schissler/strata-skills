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
        self.assertIn(
            "treat `semantic_similarity` when supplied as relative proximity, not truth, confidence, relevance, or currentness.",
            self.lower,
        )
        self.assertIn(
            "a node's existence in the graph does not establish that it is relevant, true, or current.",
            self.lower,
        )
        self.assertIn(
            "describe conclusions as graph grounding — what the project records and currently treats as canonical — rather than externally verified truth unless separate evidence verifies them.",
            self.lower,
        )

    def test_current_state_checks_each_dimension(self):
        for field in ("occurred_at", "occurred_at_basis", "review"):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", self.skill)
        self.assertIn(
            "incoming `replaces` and `resolves` relationships, and `counters` relationships in both directions.",
            self.lower,
        )
        self.assertIn(
            "an inbound `replaces` edge retires a claim; counters and age alone do not.",
            self.lower,
        )

    def test_replacement_chain_is_bounded_and_cycle_safe(self):
        self.assertIn(
            "start with `superseded_by` when search supplies it, then use `strata_list_edges` for each next inbound `replaces` hop.",
            self.lower,
        )
        self.assertIn("track every visited node key.", self.lower)
        self.assertIn(
            "stop if a key repeats; report a replacement cycle and that no live head was found.",
            self.lower,
        )
        self.assertIn(
            "stop after 20 hops; report the unresolved cap rather than guessing.",
            self.lower,
        )
        self.assertIn(
            "if the walk ends at a node with no inbound `replaces`, cite that terminal successor",
            self.lower,
        )


if __name__ == "__main__":
    unittest.main()

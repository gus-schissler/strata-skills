import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "find-in-stratagraph"
SKILL_PATH = SKILL_DIR / "SKILL.md"


class FindSkillPackagingTests(unittest.TestCase):
    def test_marketplace_uses_the_canonical_skill_tree(self):
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text()
        )
        plugin = marketplace["plugins"][0]
        self.assertEqual(plugin["source"], "./")
        self.assertFalse(plugin["strict"])
        self.assertEqual(
            plugin["skills"],
            [
                "./skills/find-in-stratagraph",
                "./skills/import",
                "./skills/gather",
            ],
        )

    def test_gather_routine_adapter_is_a_symlink_to_the_canonical_skill(self):
        adapter = ROOT / ".claude" / "skills" / "gather"
        self.assertTrue(adapter.is_symlink())
        self.assertEqual(adapter.resolve(), (ROOT / "skills" / "gather").resolve())

    def test_frontmatter_names_the_skill_and_describes_activation(self):
        content = SKILL_PATH.read_text()
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)
        self.assertIsNotNone(frontmatter)
        metadata = frontmatter.group(1)
        self.assertIn("name: find-in-stratagraph", metadata)
        self.assertIn("Find and verify specific information", metadata)
        self.assertIn("Do not use it for broad", metadata)

    def test_workflow_enforces_verified_read_only_retrieval(self):
        content = SKILL_PATH.read_text()
        required_contract = (
            "Use `strata_search_nodes` to locate candidates",
            "strata_get_node",
            "strata_get_nodes",
            "strata_list_documents",
            "strata_get_document",
            "strata_list_edges",
            "strata_traverse",
            "Start with `max_depth: 1`",
            "Use only read tools",
            "Link every displayed node key",
            "Never display a bare node key",
            "/projects/{project_key}/nodes/{node_key}",
        )
        for phrase in required_contract:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_openai_metadata_has_explicit_invocation_prompt(self):
        metadata_path = SKILL_DIR / "agents" / "openai.yaml"
        metadata = metadata_path.read_text()
        self.assertIn('display_name: "Find in Stratagraph"', metadata)
        self.assertIn("$find-in-stratagraph", metadata)


if __name__ == "__main__":
    unittest.main()

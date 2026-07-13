import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = (
    ROOT / "plugins/stratagraph/skills/find-in-stratagraph",
    ROOT / ".agents/skills/find-in-stratagraph",
    ROOT / ".claude/skills/find-in-stratagraph",
)
SKILL_PATHS = tuple(skill_dir / "SKILL.md" for skill_dir in SKILL_DIRS)


class FindSkillPackagingTests(unittest.TestCase):
    def test_distributed_skill_copies_match(self):
        def files(skill_dir):
            return {
                path.relative_to(skill_dir): path.read_bytes()
                for path in skill_dir.rglob("*")
                if path.is_file()
            }

        copies = [files(skill_dir) for skill_dir in SKILL_DIRS]
        self.assertTrue(all(copy == copies[0] for copy in copies[1:]))

    def test_frontmatter_names_the_skill_and_describes_activation(self):
        content = SKILL_PATHS[0].read_text()
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)
        self.assertIsNotNone(frontmatter)
        metadata = frontmatter.group(1)
        self.assertIn("name: find-in-stratagraph", metadata)
        self.assertIn("Find and verify specific information", metadata)
        self.assertIn("Do not use it for broad", metadata)

    def test_workflow_enforces_verified_read_only_retrieval(self):
        content = SKILL_PATHS[0].read_text()
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
        metadata_path = (
            ROOT
            / "plugins/stratagraph/skills/find-in-stratagraph/agents/openai.yaml"
        )
        metadata = metadata_path.read_text()
        self.assertIn('display_name: "Find in Stratagraph"', metadata)
        self.assertIn("$find-in-stratagraph", metadata)


if __name__ == "__main__":
    unittest.main()

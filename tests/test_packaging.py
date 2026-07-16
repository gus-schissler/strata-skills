import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
MARKETPLACE_PATH = ROOT / ".claude-plugin" / "marketplace.json"


def canonical_skills():
    return {
        path.parent.relative_to(ROOT).as_posix()
        for path in SKILLS_DIR.glob("*/SKILL.md")
    }


class PackagingTests(unittest.TestCase):
    def test_marketplace_points_to_each_canonical_skill(self):
        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(marketplace["plugins"]), 1)

        plugin = marketplace["plugins"][0]
        self.assertEqual(plugin["source"], "./")
        self.assertFalse(plugin["strict"])

        registered = [Path(path).as_posix().removeprefix("./") for path in plugin["skills"]]
        self.assertEqual(len(registered), len(set(registered)))
        self.assertEqual(set(registered), canonical_skills())

        for relative_path in registered:
            with self.subTest(skill=relative_path):
                self.assertTrue((ROOT / relative_path / "SKILL.md").is_file())

    def test_skill_names_match_their_canonical_folders(self):
        for skill_path in SKILLS_DIR.glob("*/SKILL.md"):
            with self.subTest(skill=skill_path.parent.name):
                content = skill_path.read_text(encoding="utf-8")
                frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.DOTALL)
                self.assertIsNotNone(frontmatter)
                self.assertRegex(
                    frontmatter.group(1),
                    rf"(?m)^name:\s*{re.escape(skill_path.parent.name)}\s*$",
                )

    def test_gather_adapter_points_to_the_canonical_skill(self):
        adapter = ROOT / ".claude" / "skills" / "gather"
        self.assertTrue(adapter.is_symlink())
        self.assertEqual(adapter.resolve(), (SKILLS_DIR / "gather").resolve())


if __name__ == "__main__":
    unittest.main()

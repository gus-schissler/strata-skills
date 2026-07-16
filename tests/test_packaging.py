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

    def test_marketplace_brand_assets_exist(self):
        marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        plugin = marketplace["plugins"][0]
        interface = plugin["interface"]

        self.assertEqual(plugin["displayName"], "Stratagraph")
        self.assertRegex(interface["brandColor"], r"\A#[0-9A-Fa-f]{6}\Z")
        for field in ("composerIcon", "logo"):
            with self.subTest(field=field):
                relative_path = interface[field].removeprefix("./")
                self.assertTrue((ROOT / relative_path).is_file())

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

    def test_each_skill_has_resolvable_openai_brand_assets(self):
        for skill_path in SKILLS_DIR.glob("*/SKILL.md"):
            skill_dir = skill_path.parent
            metadata_path = skill_dir / "agents" / "openai.yaml"
            with self.subTest(skill=skill_dir.name):
                self.assertTrue(metadata_path.is_file())
                metadata = metadata_path.read_text(encoding="utf-8")
                for field in ("icon_small", "icon_large"):
                    match = re.search(
                        rf'(?m)^\s*{field}:\s*"([^"]+)"\s*$',
                        metadata,
                    )
                    self.assertIsNotNone(match)
                    relative_path = match.group(1).removeprefix("./")
                    self.assertTrue((skill_dir / relative_path).is_file())
                self.assertRegex(
                    metadata,
                    r'(?m)^\s*brand_color:\s*"#[0-9A-Fa-f]{6}"\s*$',
                )

    def test_gather_adapter_points_to_the_canonical_skill(self):
        adapter = ROOT / ".claude" / "skills" / "gather"
        self.assertTrue(adapter.is_symlink())
        self.assertEqual(adapter.resolve(), (SKILLS_DIR / "gather").resolve())


if __name__ == "__main__":
    unittest.main()

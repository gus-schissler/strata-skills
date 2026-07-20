"""Version discipline checks.

1. The two plugin manifests must always agree on the version.
2. On a pull request, a change to shipped plugin content (skills/ or either
   manifest) must come with a version bump. This check runs only when CI
   provides a base ref to compare against (GITHUB_BASE_REF); local runs and
   push builds skip it rather than guessing at a baseline.
"""

import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_MANIFEST = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
CODEX_MANIFEST = os.path.join(ROOT, ".codex-plugin", "plugin.json")


def claude_version(text: str) -> str:
    return json.loads(text)["plugins"][0]["version"]


def codex_version(text: str) -> str:
    return json.loads(text)["version"]


class TestVersion(unittest.TestCase):
    def test_manifests_agree(self):
        with open(CLAUDE_MANIFEST) as f:
            claude = claude_version(f.read())
        with open(CODEX_MANIFEST) as f:
            codex = codex_version(f.read())
        self.assertEqual(
            claude,
            codex,
            "marketplace.json and plugin.json carry different versions",
        )

    def test_content_changes_bump_the_version(self):
        base_ref = os.environ.get("GITHUB_BASE_REF")
        if not base_ref:
            self.skipTest("no PR base ref; version-bump check runs on PRs only")
        base = f"origin/{base_ref}"

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout

        git("fetch", "--depth=1", "origin", base_ref)
        changed = git(
            "diff", "--name-only", base, "HEAD", "--",
            "skills", ".claude-plugin", ".codex-plugin",
        ).strip()
        if not changed:
            self.skipTest("no shipped plugin content changed")

        base_manifest = git("show", f"{base}:.claude-plugin/marketplace.json")
        self.assertNotEqual(
            claude_version(base_manifest),
            claude_version(open(CLAUDE_MANIFEST).read()),
            "skills/ or manifest content changed without a version bump; "
            "bump the version in BOTH .claude-plugin/marketplace.json and "
            ".codex-plugin/plugin.json",
        )


if __name__ == "__main__":
    unittest.main()

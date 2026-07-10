import contextlib
import importlib.util
import io
import json
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "import" / "import.py"
SPEC = importlib.util.spec_from_file_location("stratagraph_import", SCRIPT)
IMPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORT)


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def entry(external_id, occurred_at, content="A decision", span="source text"):
    return {
        "document": {
            "externalId": external_id,
            "name": external_id,
            "occurredAt": occurred_at,
            "source": "test",
            "text": "source text",
        },
        "atoms": [{"type": "decision", "content": content, "spans": [span]}],
    }


class ImportHelperTests(unittest.TestCase):
    def quiet(self, function, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return function(args)

    def test_validation_requires_type_and_one_to_five_exact_spans(self):
        allowed = {"decision"}
        valid = [{"type": "decision", "content": "A", "spans": ["source"]}]
        self.assertTrue(IMPORT.validate_atoms(valid, "source text", allowed)["ok"])

        no_spans = [{"type": "decision", "content": "A", "spans": []}]
        self.assertFalse(IMPORT.validate_atoms(no_spans, "source text", allowed)["ok"])

        too_many = [{"type": "decision", "content": "A", "spans": ["source"] * 6}]
        self.assertFalse(IMPORT.validate_atoms(too_many, "source text", allowed)["ok"])

        wrong_type = [{"type": "risk", "content": "A", "spans": ["source"]}]
        self.assertFalse(IMPORT.validate_atoms(wrong_type, "source text", allowed)["ok"])

        inexact = [{"type": "decision", "content": "A", "spans": ["missing"]}]
        self.assertFalse(IMPORT.validate_atoms(inexact, "source text", allowed)["ok"])

    def test_bundle_replaces_only_with_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            first = write_json(root / "first.json", entry("doc", "2025-01-01", "First"))
            second = write_json(root / "second.json", entry("doc", "2025-01-01", "Second"))

            args = types.SimpleNamespace(output_dir=str(out), entries=[first], replace=False)
            self.assertEqual(self.quiet(IMPORT.cmd_bundle, args), 0)

            args = types.SimpleNamespace(output_dir=str(out), entries=[second], replace=False)
            self.assertEqual(self.quiet(IMPORT.cmd_bundle, args), 0)
            bundle = json.loads((out / "import-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["documents"][0]["atoms"][0]["content"], "First")

            args = types.SimpleNamespace(output_dir=str(out), entries=[second], replace=True)
            self.assertEqual(self.quiet(IMPORT.cmd_bundle, args), 0)
            bundle = json.loads((out / "import-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["documents"][0]["atoms"][0]["content"], "Second")

    def test_combine_sorts_and_writes_hash_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            newer = write_json(root / "newer.json", {"version": 1, "documents": [entry("newer", "2025-02-01")]})
            older = write_json(root / "older.json", {"version": 1, "documents": [entry("older", "2025-01-01")]})
            out = root / "combined"
            args = types.SimpleNamespace(output_dir=str(out), types="decision", bundles=[newer, older])

            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 0)
            bundle = json.loads((out / "import-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual([d["document"]["externalId"] for d in bundle["documents"]], ["older", "newer"])

            manifest = json.loads((out / "combined-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["parents"]), 2)
            self.assertEqual(len(manifest["combined"]["sha256"]), 64)

    def test_combine_rejects_duplicates_and_unresolved_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_json(root / "first.json", {"version": 1, "documents": [entry("same", "2025-01-01")]})
            duplicate = write_json(root / "duplicate.json", {"version": 1, "documents": [entry("same", "2025-02-01")]})
            args = types.SimpleNamespace(output_dir=str(root / "duplicates"), types="decision", bundles=[first, duplicate])
            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 1)

            unresolved = write_json(root / "unresolved.json", {"version": 1, "documents": [entry("undated", "")]})
            args = types.SimpleNamespace(output_dir=str(root / "unresolved"), types="decision", bundles=[unresolved])
            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 1)


if __name__ == "__main__":
    unittest.main()

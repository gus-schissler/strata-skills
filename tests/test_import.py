import contextlib
import importlib.util
import io
import json
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "import" / "scripts" / "import.py"
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
        "nodes": [{"type": "decision", "content": content, "spans": [span]}],
    }


class ImportHelperTests(unittest.TestCase):
    def quiet(self, function, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return function(args)

    def test_validation_requires_type_and_one_to_five_exact_spans(self):
        allowed = {"decision"}
        valid = [{"type": "decision", "content": "A", "spans": ["source"]}]
        report = IMPORT.validate_nodes(valid, "source text", allowed)
        self.assertTrue(report["ok"])
        self.assertEqual(report["nodeCount"], 1)
        self.assertEqual(len(report["nodes"]), 1)

        no_spans = [{"type": "decision", "content": "A", "spans": []}]
        self.assertFalse(IMPORT.validate_nodes(no_spans, "source text", allowed)["ok"])

        too_many = [{"type": "decision", "content": "A", "spans": ["source"] * 6}]
        self.assertFalse(IMPORT.validate_nodes(too_many, "source text", allowed)["ok"])

        wrong_type = [{"type": "risk", "content": "A", "spans": ["source"]}]
        self.assertFalse(IMPORT.validate_nodes(wrong_type, "source text", allowed)["ok"])

        inexact = [{"type": "decision", "content": "A", "spans": ["missing"]}]
        self.assertFalse(IMPORT.validate_nodes(inexact, "source text", allowed)["ok"])

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
            self.assertEqual(bundle["documents"][0]["nodes"][0]["content"], "First")

            args = types.SimpleNamespace(output_dir=str(out), entries=[second], replace=True)
            self.assertEqual(self.quiet(IMPORT.cmd_bundle, args), 0)
            bundle = json.loads((out / "import-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["documents"][0]["nodes"][0]["content"], "Second")

    def test_bundle_rejects_legacy_atoms_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            legacy = entry("doc", "2025-01-01")
            legacy["atoms"] = legacy.pop("nodes")
            legacy_path = write_json(root / "legacy.json", legacy)
            args = types.SimpleNamespace(output_dir=str(out), entries=[legacy_path], replace=False)

            self.assertEqual(self.quiet(IMPORT.cmd_bundle, args), 1)
            bundle = json.loads((out / "import-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["version"], 2)
            self.assertEqual(bundle["documents"], [])

    def test_bundle_rejects_stale_existing_contract_without_mutation(self):
        cases = (
            (
                "same externalId with version 1",
                {"version": 1, "documents": [entry("doc", "2025-01-01")]},
                "doc",
            ),
            (
                "different externalId with legacy key",
                {
                    "version": 2,
                    "documents": [
                        {
                            "document": entry("old", "2025-01-01")["document"],
                            "atoms": entry("old", "2025-01-01")["nodes"],
                        }
                    ],
                },
                "new",
            ),
        )
        for label, existing, incoming_external_id in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                out = root / "out"
                out.mkdir()
                bundle_path = Path(write_json(out / "import-bundle.json", existing))
                worklist_path = Path(write_json(out / "worklist.json", {"sentinel": label}))
                incoming = write_json(
                    root / "incoming.json",
                    entry(incoming_external_id, "2025-02-01"),
                )
                bundle_before = bundle_path.read_bytes()
                worklist_before = worklist_path.read_bytes()
                args = types.SimpleNamespace(output_dir=str(out), entries=[incoming], replace=False)
                stderr = io.StringIO()

                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                    result = IMPORT.cmd_bundle(args)

                self.assertEqual(result, 2)
                self.assertIn("regenerate", stderr.getvalue())
                self.assertEqual(bundle_path.read_bytes(), bundle_before)
                self.assertEqual(worklist_path.read_bytes(), worklist_before)

    def test_combine_rejects_legacy_atoms_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_entry = entry("doc", "2025-01-01")
            legacy_entry["atoms"] = legacy_entry.pop("nodes")
            legacy = write_json(root / "legacy.json", {"version": 2, "documents": [legacy_entry]})
            args = types.SimpleNamespace(output_dir=str(root / "combined"), types="decision", bundles=[legacy])

            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 1)

    def test_combine_sorts_and_writes_hash_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            newer = write_json(root / "newer.json", {"version": 2, "documents": [entry("newer", "2025-02-01")]})
            older = write_json(root / "older.json", {"version": 2, "documents": [entry("older", "2025-01-01")]})
            out = root / "combined"
            args = types.SimpleNamespace(output_dir=str(out), types="decision", bundles=[newer, older])

            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 0)
            bundle = json.loads((out / "import-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["version"], 2)
            self.assertEqual([d["document"]["externalId"] for d in bundle["documents"]], ["older", "newer"])

            manifest = json.loads((out / "combined-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], 2)
            self.assertEqual(len(manifest["parents"]), 2)
            self.assertEqual(len(manifest["combined"]["sha256"]), 64)

    def test_combine_rejects_duplicates_and_unresolved_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_json(root / "first.json", {"version": 2, "documents": [entry("same", "2025-01-01")]})
            duplicate = write_json(root / "duplicate.json", {"version": 2, "documents": [entry("same", "2025-02-01")]})
            args = types.SimpleNamespace(output_dir=str(root / "duplicates"), types="decision", bundles=[first, duplicate])
            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 1)

            unresolved = write_json(root / "unresolved.json", {"version": 2, "documents": [entry("undated", "")]})
            args = types.SimpleNamespace(output_dir=str(root / "unresolved"), types="decision", bundles=[unresolved])
            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 1)

    def test_combine_rejects_version_1_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = write_json(root / "stale.json", {"version": 1, "documents": [entry("doc", "2025-01-01")]})
            args = types.SimpleNamespace(output_dir=str(root / "combined"), types="decision", bundles=[stale])

            self.assertEqual(self.quiet(IMPORT.cmd_combine, args), 1)
            self.assertFalse((root / "combined" / "import-bundle.json").exists())


if __name__ == "__main__":
    unittest.main()

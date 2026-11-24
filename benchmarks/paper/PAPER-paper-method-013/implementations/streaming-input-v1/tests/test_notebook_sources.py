"""Source authentication/redaction controls; no author cells or model are run."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("notebook_sources", ROOT / "notebook_sources.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def fixture(name="test", code="raise RuntimeError('must never execute')"):
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["PRIVATE_MARKDOWN_DO_NOT_EXPORT"]},
        {"cell_type": "code", "source": [code], "outputs": [{"data": {"text/plain": ["PRIVATE_OUTPUT_DO_NOT_EXPORT"]}}], "execution_count": 999},
    ]}
    raw = json.dumps(notebook).encode()
    exported = ("# Original code cell 1\n" + code + "\n").encode()
    expected = {"name": name, "path": name + ".ipynb", "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "git_blob_sha1": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                "export_sha256": hashlib.sha256(exported).hexdigest()}
    return raw, exported, expected


class NotebookSourceControls(unittest.TestCase):
    def test_raw_identity_rejected_before_json_parsing(self):
        raw, _, expected = fixture()
        for field in ("sha256", "git_blob_sha1", "bytes"):
            changed = dict(expected)
            changed[field] = 0 if field == "bytes" else "0" * len(expected[field])
            with patch.object(source.json, "loads", side_effect=AssertionError("unverified JSON parsed")):
                with self.assertRaisesRegex(ValueError, "source identity"):
                    source.extract(raw, changed)

    def test_only_literal_code_is_exported_without_execution(self):
        raw, exported, expected = fixture()
        actual, receipt = source.extract(raw, expected)
        self.assertEqual(actual, exported)
        self.assertNotIn(b"PRIVATE_OUTPUT", actual)
        self.assertNotIn(b"PRIVATE_MARKDOWN", actual)
        self.assertTrue(receipt["code_cells"][0]["ast_parseable"])
        self.assertEqual(receipt["code_cells"][0]["notebook_cell_index"], 1)

    def test_upstream_syntax_failure_is_preserved(self):
        raw, exported, expected = fixture(code="seg = Dense(self.128, 'relu')(seg)")
        actual, receipt = source.extract(raw, expected)
        self.assertEqual(actual, exported)
        self.assertFalse(receipt["code_cells"][0]["ast_parseable"])
        self.assertEqual(receipt["code_cells"][0]["error_type"], "SyntaxError")

    def test_wrong_derived_identity_is_rejected(self):
        raw, _, expected = fixture()
        expected["export_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "export identity"):
            source.extract(raw, expected)

    def test_complete_authentication_precedes_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = []
            for name in ("testing", "training", "preprocessing"):
                raw, _, expected = fixture(name)
                (root / (name + ".ipynb")).write_bytes(raw if name != "preprocessing" else raw + b"x")
                records.append(expected)
            with patch.object(source, "SOURCES", records):
                with self.assertRaisesRegex(ValueError, "source identity"):
                    source.export_all(root, root / "output")
            self.assertFalse((root / "output").exists())

    def test_export_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, _, expected = fixture("testing")
            (root / "testing.ipynb").write_bytes(raw)
            output = root / "output"
            output.mkdir()
            (output / "marker").write_text("keep")
            with patch.object(source, "SOURCES", (expected,)):
                with self.assertRaises(FileExistsError):
                    source.export_all(root, output)
            self.assertEqual((output / "marker").read_text(), "keep")
            self.assertEqual(list(output.iterdir()), [output / "marker"])

    def test_committed_sources_match_authenticated_exports(self):
        manifest = json.loads((ROOT / "author-code" / "MANIFEST.json").read_text())
        self.assertEqual(len(manifest["notebooks"]), 3)
        failures = []
        for receipt, expected in zip(manifest["notebooks"], source.SOURCES):
            self.assertEqual(receipt["name"], expected["name"])
            self.assertEqual(receipt["source_git_blob_sha1"], expected["git_blob_sha1"])
            self.assertEqual(receipt["source_sha256"], expected["sha256"])
            data = (ROOT / "author-code" / receipt["export_file"]).read_bytes()
            self.assertEqual(len(data), receipt["export_bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected["export_sha256"])
            failures.extend((receipt["name"], cell["notebook_cell_index"])
                            for cell in receipt["code_cells"] if not cell["ast_parseable"])
        self.assertEqual(failures, [("training", 3)])
        self.assertFalse(manifest["notebook_outputs_included"])
        self.assertFalse(manifest["notebook_code_executed"])
        self.assertFalse(manifest["paper_checkpoint_equivalence"])


if __name__ == "__main__":
    unittest.main()

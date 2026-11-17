"""Portable independent controls for the OpenMIIR source-support calculation.

Only published stimulus metadata and generated XML/files are used. These are
not EEG/model experiments and do not require any cached personal source path.
"""
from __future__ import annotations

import contextlib
import copy
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape
import zipfile


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("_openmiir_support_review", HERE / "support.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)


def rows(version):
    report = json.loads((HERE / "support_report.json").read_text())
    return copy.deepcopy(next(v["source_rows"] for v in report["versions"] if v["version"] == version))


def pair_ids(result, key="meter_tempo_pairs"):
    return [tuple(pair["stimulus_ids"]) for pair in result[key]]


def generated_workbook(values):
    """Build simple OOXML with cached formulas; no spreadsheet engine needed."""
    strings, sheet = [], []
    for number, row in enumerate(values, 2):
        cells = []
        # Reverse physical cell order to check that coordinates, not insertion
        # order, select the source column.
        for column, key in reversed(list(SUPPORT.COLUMNS.items())):
            value = row[key]
            if key in ("label", "audio_file"):
                index = len(strings)
                strings.append("<si><t>" + escape(value) + "</t></si>")
                cells.append(f'<c r="{column}{number}" t="s"><v>{index}</v></c>')
            else:
                formula = "<f>1/0</f>" if column == "F" else ""
                cells.append(f'<c r="{column}{number}">{formula}<v>{escape(str(value))}</v></c>')
        sheet.append(f'<row r="{number}">' + "".join(cells) + "</row>")
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}">' + "".join(strings) + "</sst>")
        archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>' +
                         "".join(sheet) + "</sheetData></worksheet>")
    return buffer.getvalue()


def blob_record(path, data):
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


@contextlib.contextmanager
def generated_source():
    """A clearly generated source contract for exercising byte-admission paths."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        payloads = {f"meta/Stimuli_Meta.v{v}.xlsx": generated_workbook(rows(v)) for v in (1, 2)}
        payloads["meta/README.md"] = b"generated metadata context\n"
        records = []
        for relative, content in payloads.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            records.append(blob_record(relative, content))
        loader = root / "metadata.py"
        # Correct behavior is to hash these bytes, never import this module.
        loader.write_bytes(b"raise RuntimeError('the metadata loader must never execute')\n")
        manifest = {"repository": "generated-control", "commit": SUPPORT.COMMIT,
                    "files": records,
                    "author_metadata_loader": {"bytes": loader.stat().st_size,
                                               "sha256": hashlib.sha256(loader.read_bytes()).hexdigest()}}
        (root / "source_manifest.json").write_text(json.dumps(manifest))
        with patch.object(SUPPORT, "HERE", root):
            yield root, source, loader, manifest


class SupportControls(unittest.TestCase):
    def test_original_pair_sets_and_zero_joint_support(self):
        expected = [(1, 11), (2, 12), (3, 13), (4, 14)]
        for version in (1, 2):
            with self.subTest(version=version):
                actual = SUPPORT.audit_version(rows(version), version)
                self.assertEqual(actual["complete_stimulus_count"], 12)
                self.assertEqual(actual["enumerated_unordered_pairs"], 66)
                self.assertTrue(actual["original_duration_values_unique"])
                self.assertEqual(pair_ids(actual["comparisons"]["cue_tempo"]), expected)
                for comparison in actual["comparisons"].values():
                    self.assertEqual(comparison["meter_tempo_duration_pairs"], [])
                    self.assertEqual(comparison["different_composition_meter_tempo_pairs"], [])
                    self.assertTrue(all(pair["same_composition"] for pair in comparison["meter_tempo_pairs"]))

    def test_author_tempo_semantics_are_version_specific(self):
        first = SUPPORT.audit_version(rows(1), 1)["comparisons"]["author_effective_tempo"]
        second = SUPPORT.audit_version(rows(2), 2)["comparisons"]["author_effective_tempo"]
        self.assertEqual(first["tempo_field"], "measured_bpm")
        self.assertEqual(pair_ids(first), [(3, 13), (4, 14)])
        self.assertEqual(second["tempo_field"], "cue_bpm")
        self.assertEqual(pair_ids(second), [(1, 11), (2, 12), (3, 13), (4, 14)])

    def test_published_duration_rounding_cannot_create_support(self):
        values = {row["id"]: row for row in rows(2)}
        a = Decimal(values[2]["song_seconds"])
        b = Decimal(values[12]["song_seconds"])
        self.assertEqual(a, Decimal("7.6700999999999997"))
        self.assertEqual(b, Decimal("7.7736999999999998"))
        self.assertNotEqual(a, b)
        # A coarse table may list both as 7.7 s; that cannot replace these cells.
        self.assertEqual(b - a, Decimal("0.1036000000000001"))
        self.assertNotIn((2, 12), pair_ids(SUPPORT.audit_version(list(values.values()), 2)
                                         ["comparisons"]["cue_tempo"], "meter_tempo_duration_pairs"))

    def test_generated_positive_cross_composition_match_is_detected(self):
        values = rows(2)
        by_id = {row["id"]: row for row in values}
        for field in ("cue_bpm", "measured_bpm", "beats_per_bar", "song_seconds"):
            by_id[21][field] = by_id[1][field]
        result = SUPPORT.audit_version(values, 2)["comparisons"]["author_effective_tempo"]
        self.assertIn({"stimulus_ids": [1, 21], "same_composition": False},
                      result["different_composition_joint_pairs"])

    def test_decimal_equality_has_no_hidden_float_rounding_or_tolerance(self):
        values = rows(2)
        by_id = {row["id"]: row for row in values}
        by_id[21].update(cue_bpm="212.000", beats_per_bar="3.0", song_seconds="13.316100")
        pair = {"stimulus_ids": [1, 21], "same_composition": False}
        actual = SUPPORT.audit_version(values, 2)["comparisons"]["cue_tempo"]
        self.assertIn(pair, actual["meter_tempo_duration_pairs"])
        by_id[21]["song_seconds"] = "13.316100000000000000000000000000000001"
        actual = SUPPORT.audit_version(values, 2)["comparisons"]["cue_tempo"]
        self.assertNotIn(pair, actual["meter_tempo_duration_pairs"])

    def test_input_order_does_not_change_pair_enumeration(self):
        original = SUPPORT.audit_version(rows(2), 2)
        shuffled = SUPPORT.audit_version(list(reversed(rows(2))), 2)
        self.assertEqual(original, shuffled)

    def test_complete_roster_and_explicit_version_are_required(self):
        for kind in ("missing", "duplicate", "wrong", "boolean"):
            values = rows(1)
            if kind == "missing":
                values.pop()
            elif kind == "duplicate":
                values[-1]["id"] = 1
            elif kind == "wrong":
                values[-1]["id"] = 999
            else:
                values[0]["id"] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                SUPPORT.audit_version(values, 1)
        for version in (None, True, 0, 3, "1", 1.0):
            with self.subTest(version=version), self.assertRaises(ValueError):
                SUPPORT.audit_version(rows(1), version)

    def test_nonfinite_or_coerced_metadata_numbers_are_rejected(self):
        for bad in ("NaN", "Infinity", "-Infinity", "0", "-1", "nonsense", 212.0, True):
            values = rows(2)
            values[0]["cue_bpm"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                SUPPORT.audit_version(values, 2)

    def test_workbook_parser_uses_cell_coordinates_and_cached_decimal_text(self):
        expected = rows(2)
        observed = SUPPORT.workbook_rows(generated_workbook(expected))
        self.assertEqual(observed, expected)
        self.assertEqual(observed[1]["song_seconds"], "7.6700999999999997")

    def test_generated_source_hashes_admit_without_executing_loader(self):
        with generated_source() as (_, source, loader, _):
            report = SUPPORT.audit(source, loader)
            self.assertEqual(len(report["versions"]), 2)
            self.assertIsNone(report["neural_performance"])

    def test_bad_loader_or_source_hash_refuses_before_workbook_parsing(self):
        with generated_source() as (_, source, loader, _):
            original = loader.read_bytes()
            loader.write_bytes(original + b"changed")
            with patch.object(SUPPORT, "workbook_rows", side_effect=AssertionError("must not parse")):
                with self.assertRaisesRegex(ValueError, "metadata loader differs"):
                    SUPPORT.audit(source, loader)
            loader.write_bytes(original)
            path = source / "meta/Stimuli_Meta.v1.xlsx"
            blob = path.read_bytes()
            path.write_bytes(bytes([blob[0] ^ 1]) + blob[1:])
            with patch.object(SUPPORT, "workbook_rows", side_effect=AssertionError("must not parse")):
                with self.assertRaisesRegex(ValueError, "source bytes differ"):
                    SUPPORT.audit(source, loader)

    def test_wrong_git_blob_refuses_even_when_sha256_matches(self):
        with generated_source() as (root, source, loader, manifest):
            manifest["files"][0]["git_blob_sha1"] = "0" * 40
            (root / "source_manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "source Git blob differs"):
                SUPPORT.audit(source, loader)

    def test_cli_preserves_existing_output_and_emits_no_score(self):
        with generated_source() as (root, source, loader, _):
            output = root / "result.json"
            args = ["--source-root", str(source), "--metadata-loader", str(loader), "--output", str(output)]
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                SUPPORT.main(args)
            summary = json.loads(capture.getvalue())
            self.assertEqual(summary["distinct_composition_match_count"], 0)
            self.assertIsNone(summary["neural_performance"])
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                SUPPORT.main(args)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

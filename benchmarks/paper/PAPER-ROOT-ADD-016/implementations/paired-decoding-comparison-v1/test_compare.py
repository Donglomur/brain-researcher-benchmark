"""Generated complete panels only: no authentic score or recording execution."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("tested_cardiac_compare", HERE / "compare.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def generated():
    published = [{"subject_id": s, "device": d, "condition": c,
                  "r": .1 + int(s)/1000 + C.P.CONDITIONS.index(c)/100}
                 for s, d, c in C.KEYS]
    exports = {}
    for index, role in enumerate(C.ROLES):
        rows = deepcopy(published)
        for row in rows:
            # Vary within participant and condition to distinguish true pairing
            # from subtraction of summary means or unpaired SD arithmetic.
            row["r"] += (index + 1) * (int(row["subject_id"]) - 9.5)/1000
            row["r"] += (index + 1)/100
        exports[role] = {"schema": C.SCHEMA, "task_id": C.TASK_ID, "role": role,
                         "declared_support_sha256": "a"*64,
                         "producer_sha256": str(index + 1)*64, "scores": rows}
    return published, exports


class CompleteComparisonTests(unittest.TestCase):
    def test_all_coordinates_and_paired_arithmetic(self):
        published, exports = generated()
        report = C.compare(published, exports)
        self.assertEqual(len(report["cells"]), 6)
        self.assertEqual(sum(len(c["participants"]) for c in report["cells"]), 120)
        for cell in report["cells"]:
            self.assertEqual([r["subject_id"] for r in cell["participants"]], list(map(str, range(20))))
            for name, multiplier in (("author_minus_published", 1),
                                     ("paper_data_minus_published", 2),
                                     ("paper_data_author_code_minus_published", 3),
                                     ("paper_data_author_code_minus_paper_data", 1)):
                summary = cell["descriptive_paired_summaries"][name]
                self.assertAlmostEqual(summary["mean_paired_delta_r"], multiplier/100)
                self.assertAlmostEqual(summary["sample_sd_paired_delta_r"], multiplier*math.sqrt(35)/1000)
        self.assertIsNone(report["reproduction"])
        self.assertIsNone(report["improvement"])
        self.assertIsNone(report["assistance_effect"])
        self.assertEqual(report["published_input_authentication"], "not_established_by_arithmetic_api")
        self.assertEqual(report["scalar_aggregation"], "none")

    def test_row_order_cannot_change_pairing(self):
        published, exports = generated()
        expected = C.compare(published, exports)
        for export in exports.values():
            export["scores"] = export["scores"][39:] + export["scores"][:39]
        self.assertEqual(expected, C.compare(list(reversed(published)), exports))

    def test_condition_tradeoff_is_not_pooled_away(self):
        published, exports = generated()
        for row in exports["paper_data_author_code"]["scores"]:
            if row["device"] == "meg" and row["condition"] == "ECG_rejected":
                row["r"] = -.5
        report = C.compare(published, exports)
        self.assertLess(report["cells"][-1]["descriptive_paired_summaries"]
                        ["paper_data_author_code_minus_author"]["mean_paired_delta_r"], 0)
        self.assertGreater(report["cells"][0]["descriptive_paired_summaries"]
                           ["paper_data_author_code_minus_author"]["mean_paired_delta_r"], 0)
        self.assertNotIn("score", report)

    def test_each_panel_must_be_complete_unique_original_support(self):
        for role in ("published", *C.ROLES):
            for mutation in ("missing", "duplicate", "replacement", "unknown_condition"):
                with self.subTest(role=role, mutation=mutation):
                    published, exports = generated()
                    rows = published if role == "published" else exports[role]["scores"]
                    if mutation == "missing":
                        rows.pop()
                    elif mutation == "duplicate":
                        rows[-1] = deepcopy(rows[0])
                    elif mutation == "replacement":
                        rows[-1]["subject_id"] = "20"
                    else:
                        rows[-1]["condition"] = "pooled"
                    with self.assertRaises(C.ComparisonError):
                        C.compare(published, exports)

    def test_roles_and_declared_support_cannot_be_interchanged(self):
        for mutation in ("role", "support", "missing_arm"):
            published, exports = generated()
            if mutation == "role":
                exports["paper_data"]["role"] = "paper_data_author_code"
            elif mutation == "support":
                exports["paper_data"]["declared_support_sha256"] = "b"*64
            else:
                exports.pop("paper_data")
            with self.assertRaises(C.ComparisonError):
                C.compare(published, exports)

    def test_undefined_or_nonmetric_scores_rejected(self):
        for value in (True, "0.5", None, float("nan"), float("inf"), -1.01, 1.01):
            published, exports = generated()
            exports["paper_data"]["scores"][0]["r"] = value
            with self.subTest(value=value), self.assertRaises(C.ComparisonError):
                C.compare(published, exports)

    def test_export_bytes_receipt_and_duplicate_json_fields(self):
        _, exports = generated()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "export.json"
            data = json.dumps(exports["paper_data"]).encode()
            path.write_bytes(data)
            document, receipt = C.load_export(path, "paper_data")
            self.assertEqual(document, exports["paper_data"])
            self.assertEqual(receipt["bytes"], len(data))
            path.write_text('{"schema":"a","schema":"b"}')
            with self.assertRaisesRegex(C.ComparisonError, "Duplicate"):
                C.load_export(path, "paper_data")
            path.write_bytes(b"x" * (C.MAX_EXPORT_BYTES + 1))
            with self.assertRaisesRegex(C.ComparisonError, "64 KiB"):
                C.load_export(path, "paper_data")

    def test_cli_rejects_changed_published_source_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"fake.csv", Path(folder)/"report.json"
            source.write_bytes(b"x" * C.P.SOURCE_BYTES)
            args = ["--published", str(source), "--out", str(output)]
            for role in C.ROLES:
                args.extend(["--" + role.replace("_", "-"), str(source)])
            with self.assertRaises(C.P.SourceError):
                C.main(args)
            self.assertFalse(output.exists())

    def test_cli_routes_all_exports_and_does_not_overwrite(self):
        published, exports = generated()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"report.json"
            args = ["--published", str(Path(folder)/"unused.csv"), "--out", str(output)]
            for role in C.ROLES:
                path = Path(folder)/(role + ".json")
                path.write_text(json.dumps(exports[role]))
                args.extend(["--" + role.replace("_", "-"), str(path)])
            # Generated routing control replaces only source authentication;
            # its synthetic report is never an authentic source result.
            with patch.object(C.P, "load_published", return_value=published):
                C.main(args)
                result = json.loads(output.read_text())
                self.assertEqual(set(result["inputs"]), {"published", *C.ROLES})
                original = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    C.main(args)
                self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

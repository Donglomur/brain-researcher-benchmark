"""Generated header metadata controls only; no actual EEG or predictions."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n012_montage_diagnostics", ROOT / "montage_diagnostics.py")
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
RUNTIME = Path(os.environ.get("NEURAL012_TEST_RUNTIME_ROOT", diagnostic.RUNTIME))
contract = diagnostic.load_contract(RUNTIME)
ELECTRODES = sorted({x for edge in contract.EDGES for x in edge.split("-")})


def record(cohort="CHB", index=1, patient=1001):
    return {"recording_id": format(index, "024x"), "patient_id": format(patient, "024x"),
            "cohort": cohort,
            "channel_labels": list(contract.EDGES) if cohort == "CHB" else ["EEG " + x for x in ELECTRODES],
            "release_eeg_labels": [] if cohort == "CHB" else list(ELECTRODES),
            "header_sha256": "1" * 64, "original_source_sha256": "2" * 64}


def panel():
    rows = [record("CHB", i + 1, 1000 + i % 23) for i in range(686)]
    rows += [record("Siena", i + 687, 2000 + i % 14) for i in range(41)]
    return {"schema": "neural012_declared_header_labels_v1", "task_id": "NEURAL-012", "records": rows}


def invented_edf_header(labels, cohort):
    """In-memory EDF header/declared extent; the signal body does not exist."""
    n = len(labels)
    hb = 256 * (n + 1)
    rate = 256 if cohort == "CHB" else 512
    def field(value, width):
        return str(value).encode("ascii").ljust(width, b" ")
    fixed = b"".join(field(value, width) for value, width in (
        ("0", 8), ("invented", 80), ("invented", 80), ("01.01.00", 8),
        ("00.00.00", 8), (hb, 8), ("", 44), (1, 8), (1, 8), (n, 4)))
    signal = b"".join(field(value, width) for values, width in (
        (labels, 16), ([""] * n, 80), (["uV"] * n, 8), ([-100] * n, 8),
        ([100] * n, 8), ([-32768] * n, 8), ([32767] * n, 8),
        ([""] * n, 80), ([rate] * n, 8), ([""] * n, 32)) for value in values)
    return fixed + signal, hb + 2 * rate * n


class MontageDiagnosticsTests(unittest.TestCase):
    def test_full_panel_retained_and_no_qualification(self):
        result = diagnostic.diagnose_panel(panel(), contract)
        self.assertEqual(len(result["records"]), 727)
        self.assertEqual(result["record_counts"], {"CHB": 686, "Siena": 41})
        self.assertEqual(result["declared_patient_counts"], {"CHB": 23, "Siena": 14})
        self.assertTrue(result["complete_panel_structural_label_support"])
        self.assertFalse(result["runnable"])
        self.assertFalse(result["scientifically_qualified"])
        self.assertIn("Siena_common_reference_physics", result["unresolved"])

    def test_all_missing_and_forward_reverse_ambiguities_retained(self):
        row = record()
        row["channel_labels"].remove("FP1-F7")
        row["channel_labels"].remove("CZ-PZ")
        row["channel_labels"] += ["T7-F7", "F7-T7", "EKG"]
        result = diagnostic.diagnose_record(row, contract)
        edges = {r["edge"]: r for r in result["edges"]}
        self.assertEqual(edges["FP1-F7"]["status"], "missing")
        self.assertEqual(edges["CZ-PZ"]["status"], "missing")
        self.assertEqual(edges["F7-T7"]["status"], "ambiguous")
        self.assertEqual([x["sign"] for x in edges["F7-T7"]["measured_candidates"]], [1, -1, 1])
        self.assertEqual(len(result["edges"]), 18)
        self.assertFalse(result["structural_label_support"])
        self.assertEqual(result["excluded_channels"][-1]["label"], "EKG")

    def test_reverse_and_old_electrode_aliases_preserve_sign_and_indices(self):
        row = record()
        row["channel_labels"][1] = "T3-F7"
        row["channel_labels"].insert(0, "-")
        result = diagnostic.diagnose_record(row, contract)
        edge = next(x for x in result["edges"] if x["edge"] == "F7-T7")
        self.assertEqual(edge["measured_candidates"], [{"source_index": 2, "sign": -1}])
        self.assertTrue(result["structural_label_support"])

    def test_siena_duplicate_alias_and_missing_nonedge_whitelist_channel(self):
        row = record("Siena")
        row["release_eeg_labels"] += ["T3", "AF7"]
        row["channel_labels"] += ["EEG T3", "ECG"]
        result = diagnostic.diagnose_record(row, contract)
        self.assertEqual(result["missing_release_labels"], ["AF7"])
        self.assertEqual(next(x for x in result["edges"] if x["edge"] == "F7-T7")["status"], "ambiguous")
        self.assertFalse(result["structural_label_support"])

    def test_duplicate_siena_label_outside_edge_set_still_fails(self):
        row = record("Siena")
        row["release_eeg_labels"].append("AF7")
        row["channel_labels"] += ["EEG AF7", "EEG AF7"]
        result = diagnostic.diagnose_record(row, contract)
        self.assertTrue(all(e["status"] == "unique" for e in result["edges"]))
        self.assertEqual(result["duplicate_release_labels"], ["AF7"])
        self.assertFalse(result["structural_label_support"])

    def test_selector_matches_preserved_header_on_generated_valid_headers(self):
        raw = (RUNTIME / "source_header.py").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), diagnostic.HEADER_SHA256)
        module = types.ModuleType("n012_preserved_header")
        previous = sys.modules.get("scientific_contract")
        try:
            sys.modules["scientific_contract"] = contract
            exec(compile(raw, str(RUNTIME / "source_header.py"), "exec"), module.__dict__)
        finally:
            if previous is None:
                sys.modules.pop("scientific_contract", None)
            else:
                sys.modules["scientific_contract"] = previous
        for cohort in ("CHB", "Siena"):
            row = record(cohort)
            row["channel_labels"] += ["EKG", "-", "Status"]
            body, extent = invented_edf_header(row["channel_labels"], cohort)
            actual = module.inspect_header(body, extent, cohort, row["release_eeg_labels"])
            result = diagnostic.diagnose_record(row, contract)
            self.assertEqual([(x["source_index"], x["label"]) for x in actual["selected_channels"]],
                             [(x["source_index"], x["label"]) for x in result["selected_channels"]])

    def test_partial_panel_duplicate_records_and_cross_cohort_people_refused(self):
        cases = []
        value = panel(); value["records"].pop(); cases.append(value)
        value = panel(); value["records"][1]["recording_id"] = value["records"][0]["recording_id"]; cases.append(value)
        value = panel(); value["records"][686]["patient_id"] = value["records"][0]["patient_id"]; cases.append(value)
        for value in cases:
            with self.assertRaises(ValueError):
                diagnostic.diagnose_panel(value, contract)

    def test_padded_labels_match_preserved_header_for_both_cohorts(self):
        raw = (RUNTIME / "source_header.py").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), diagnostic.HEADER_SHA256)
        module = types.ModuleType("n012_preserved_padded_header")
        previous = sys.modules.get("scientific_contract")
        try:
            sys.modules["scientific_contract"] = contract
            exec(compile(raw, str(RUNTIME / "source_header.py"), "exec"), module.__dict__)
        finally:
            if previous is None:
                sys.modules.pop("scientific_contract", None)
            else:
                sys.modules["scientific_contract"] = previous
        for cohort in ("CHB", "Siena"):
            row = record(cohort)
            row["channel_labels"] = [" " + x + " " for x in row["channel_labels"]] + [" EKG "]
            body, extent = invented_edf_header(row["channel_labels"], cohort)
            expected = module.inspect_header(body, extent, cohort, row["release_eeg_labels"])
            result = diagnostic.diagnose_record(row, contract)
            self.assertTrue(result["structural_label_support"])
            self.assertEqual([(x["source_index"], x["label"]) for x in expected["selected_channels"]],
                             [(x["source_index"], x["label"]) for x in result["selected_channels"]])
            self.assertEqual(result["selected_channels"][0]["declared_label"], row["channel_labels"][0])
            self.assertEqual(result["excluded_channels"], [{"source_index": len(row["channel_labels"]) - 1,
                                                            "label": "EKG", "declared_label": " EKG "}])

    def test_changed_frozen_source_and_malformed_json_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "scientific_contract.py").write_bytes(b"raise RuntimeError('must not execute')\n")
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                diagnostic.load_contract(directory)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            diagnostic.strict(b'{"records":[],"records":[]}')
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            diagnostic.strict(b'{"x":NaN}')


if __name__ == "__main__":
    unittest.main(verbosity=2)

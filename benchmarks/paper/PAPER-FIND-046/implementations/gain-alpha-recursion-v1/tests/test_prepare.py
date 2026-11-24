import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("find046_prepare", ROOT / "prepare.py")
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)
model = prepare.model


def raw():
    return {"schema_version": 1, "input_kind": "generated_engineering_control",
            "preprocessing": "author_figure3_raw_ratTrial",
            "rat_trial": {"trial_ids": [f"trial-{i}" for i in range(11)],
                          "reward": [4, 8, 16, 32, 64, 0, 5, 10, 20, 40, 80],
                          "iti": [900, 1, 2, None, 30, 100, 800, 4, 5, 20, 21],
                          "ntrials": [0, 6, 5]}}


def receipt(payload, threshold=21):
    # Deliberately chosen branch-control value, NOT a computed native percentile.
    request = prepare.statistic_request(payload)
    return {"schema_version": 1, "input_kind": payload["input_kind"],
            "request_sha256": model.canonical_hash(request),
            "producer": "generated branch control; not MATLAB percentile parity",
            "values": {"iti_p99": threshold}}


class SourcePreparationTests(unittest.TestCase):
    def test_percentile_operand_uses_session_mask_and_retains_missing_rows(self):
        result = prepare.statistic_request(raw())
        self.assertEqual(result["source_first_iti_assignment_rows_zero_based"], [0, 0, 6])
        self.assertEqual(result["statistic_operands"], [{"key": "iti_p99", "function": "prctile",
            "percentile": 99, "values": [None, 1, 2, None, 30, 100, None, 4, 5, 20, 21]}])

    def test_source_conversion_strict_threshold_and_complete_row_ledger(self):
        payload = raw()
        before = copy.deepcopy(payload)
        result, audit = prepare.prepare(payload, receipt(payload))
        self.assertEqual(payload, before)
        self.assertEqual(result["rat_trial"]["reward"], [5, 10, 20, 40, 80, 0, 5, 10, 20, 40, 80])
        self.assertEqual(result["rat_trial"]["iti"], [None, 1, 2, None, None, None, None, 4, 5, 20, 21])
        self.assertEqual(result["rat_trial"]["trial_ids"], payload["rat_trial"]["trial_ids"])
        self.assertEqual(result["rat_trial"]["ntrials"], [0, 6, 5])
        self.assertEqual(audit["outlier_rows_zero_based"], [4, 5])
        self.assertEqual(len(audit["row_ledger"]), 11)
        self.assertTrue(audit["row_ledger"][10]["retained_by_recurrence_iti_mask"])
        self.assertFalse(audit["row_ledger"][3]["source_p99_outlier"])
        self.assertFalse(audit["reproduction_qualified"])
        self.assertFalse(audit["improvement_eligible"])
        self.assertEqual(audit["prepared_sha256"], model.canonical_hash(result))

    def test_convertreward_preserves_source_unlisted_and_level_values(self):
        # Source accepts unlisted numeric inputs and maps surviving levels too.
        self.assertEqual([prepare.standard_reward(x) for x in [None, -2, 0, 1, 2, 3, 4, 5, 6, 7.5]],
                         [None, -2, 0, 5, 10, 20, 5, 5, 6, 7.5])

    def test_output_runs_through_existing_recurrence_interface(self):
        payload = raw()
        prepared, _ = prepare.prepare(payload, receipt(payload))
        request = model.statistic_requests(prepared)
        native_control = {"schema_version": 1, "input_kind": prepared["input_kind"],
                          "request_sha256": model.canonical_hash(request),
                          "producer": "generated branch control, no native percentile assertion",
                          "values": {x["key"]: max(v for v in x["values"] if v is not None)
                                     for x in request["statistic_operands"]}}
        result = model.reconstruct(prepared, native_control)
        self.assertEqual(result["trial_ids"], payload["rat_trial"]["trial_ids"])
        self.assertEqual(result["retained_indices_zero_based"], [1, 2, 7, 8, 9, 10])
        self.assertEqual(result["retained_session_start_positions_zero_based"], [0, 2])
        self.assertEqual(len(result["conditions"]), 5)
        self.assertTrue(all(len(c["Kappa"]) == 11 for c in result["conditions"]))
        self.assertFalse(result["reproduction_qualified"])

    def test_mismatched_operand_receipt_and_kind_are_rejected(self):
        payload = raw()
        original = receipt(payload)
        payload["rat_trial"]["iti"][2] = 3
        with self.assertRaisesRegex(prepare.ContractError, "exact operands"):
            prepare.prepare(payload, original)
        payload = raw()
        other = receipt(payload)
        other["input_kind"] = "authorized_native_export"
        with self.assertRaisesRegex(prepare.ContractError, "kind mismatch"):
            prepare.prepare(payload, other)
        other = receipt(payload, 200)
        with self.assertRaisesRegex(prepare.ContractError, "outside operand support"):
            prepare.prepare(payload, other)

    def test_undefined_source_and_incomplete_alignment_rejected_without_subsetting(self):
        payload = raw()
        payload["rat_trial"]["ntrials"].append(0)
        with self.assertRaisesRegex(prepare.ContractError, "extend ITI"):
            prepare.statistic_request(payload)
        payload = raw()
        payload["rat_trial"]["trial_ids"].pop()
        with self.assertRaisesRegex(prepare.ContractError, "row alignment"):
            prepare.statistic_request(payload)
        payload = raw()
        payload["preprocessing"] = "author_figure3_preprocessed_ratTrial"
        with self.assertRaisesRegex(prepare.ContractError, "processed twice"):
            prepare.statistic_request(payload)

    def test_missing_reward_depends_on_retained_source_rows(self):
        payload = raw()
        payload["rat_trial"]["reward"][0] = None
        result, _ = prepare.prepare(payload, receipt(payload))
        self.assertIsNone(result["rat_trial"]["reward"][0])
        payload["rat_trial"]["reward"][1] = None
        with self.assertRaisesRegex(prepare.ContractError, "missing reward"):
            prepare.prepare(payload, receipt(payload))
        payload = raw()
        with self.assertRaisesRegex(prepare.ContractError, "fewer than two"):
            prepare.prepare(payload, receipt(payload, 1))

    def test_cli_preparation_and_existing_requests_command(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            input_path, receipt_path = folder / "raw.json", folder / "receipt.json"
            output, audit = folder / "prepared.json", folder / "audit.json"
            input_path.write_text(json.dumps(raw()))
            receipt_path.write_text(json.dumps(receipt(raw())))
            command = [sys.executable, "-B", str(ROOT / "prepare.py"), "prepare", str(input_path),
                       "--receipt", str(receipt_path), "--output", str(output), "--audit-output", str(audit)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(len(json.loads(audit.read_text())["row_ledger"]), 11)
            model_command = [sys.executable, "-B", str(ROOT / "model.py"), "requests", str(output),
                             "--output", str(folder / "model-request.json")]
            completed = subprocess.run(model_command, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("output already exists", completed.stderr)


if __name__ == "__main__":
    unittest.main()

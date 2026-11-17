"""Small generated controls; these are not authentic ERP data or model fits."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("prepare.py")
SPEC = importlib.util.spec_from_file_location("erp_input_preparer", MODULE_PATH)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "prepared"
        self.contract = json.loads(prepare.CONTRACT_PATH.read_text())
        self.contract_path = self.root / "fixture-contract.json"
        self.tables = {}
        for spec in self.contract["public_input_files"]:
            name = Path(spec["path"]).name
            rows = [{column: f"{index + 1}.2300" for column in spec["columns"]} for index in range(8)]
            self.tables[name] = rows
        behavior = self.tables["BEH_ug.csv"]
        for index, row in enumerate(behavior):
            row["sub"] = "participant-a" if index < 4 else "participant-b"
            row["trialGlobal"] = str(index % 4 + 1)
            row["epe_valence_s"] = "-1.5000"
        behavior[1]["epe_valence_s"] = "NA"
        self.tables["df_FRN_N2_offer.csv"][2]["FRN_N2_offer_s"] = "NA"
        self.tables["df_P3a_base.csv"][3]["P3a_base_offer_s"] = "NaN"
        self.tables["df_P3b_offer.csv"][4]["P3b_offer_s"] = ""
        for spec in self.contract["public_input_files"]:
            spec["rows"] = 8
        for spec in self.contract["models"].values():
            spec["required_participants"] = 2
            spec["required_rows"] = 6
        self.save_fixture()
        self.contract_patch = patch.object(prepare, "CONTRACT_PATH", self.contract_path)
        self.contract_patch.start()
        self.addCleanup(self.contract_patch.stop)

    def save_fixture(self):
        for spec in self.contract["public_input_files"]:
            name = Path(spec["path"]).name
            text = io.StringIO(newline="")
            writer = csv.DictWriter(text, fieldnames=spec["columns"], lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.tables[name])
            payload = text.getvalue().encode()
            (self.source / name).write_bytes(payload)
            spec["bytes"], spec["sha256"] = len(payload), prepare.digest(payload)
        self.contract_path.write_text(json.dumps(self.contract))

    def run_preparation(self):
        return prepare.prepare(self.source, self.output)

    def assert_rejected(self, message):
        with self.assertRaisesRegex(prepare.PreparationError, message):
            self.run_preparation()
        self.assertFalse(self.output.exists())

    def test_original_positions_and_model_specific_masks_survive(self):
        report = self.run_preparation()
        expected = {"FRN": [1, 4, 5, 6, 7, 8], "P3a": [1, 3, 5, 6, 7, 8], "P3b": [1, 3, 4, 6, 7, 8]}
        for model, indices in expected.items():
            with (self.output / f"{model}.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([int(row["source_row"]) for row in rows], indices)
            self.assertEqual(rows[0]["abs_rpe_s"], "1.2300")
            self.assertEqual(rows[-1]["trialGlobal"], "4")
            self.assertEqual(report["models"][model]["excluded_missing_valence_pe"], 1)
            self.assertEqual(report["models"][model]["excluded_model_complete_cases"], 1)
            self.assertEqual(report["models"][model]["participants"], 2)
            self.assertEqual(report["models"][model]["output"]["sha256"], prepare.digest((self.output / f"{model}.csv").read_bytes()))
        self.assertEqual(len({report["models"][model]["ordered_identity_sha256"] for model in expected}), 3)
        self.assertIn("no independently verified", report["alignment"])
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertEqual(json.loads((self.output / "receipt.json").read_text()), report)

    def test_one_reordered_erp_table_fails_before_positional_join(self):
        path = self.source / "df_P3b_offer.csv"
        lines = path.read_bytes().splitlines(keepends=True)
        lines[1], lines[2] = lines[2], lines[1]
        path.write_bytes(b"".join(lines))
        self.assert_rejected("Source identity mismatch")

    def test_duplicate_behavior_identity_is_not_silently_deduplicated(self):
        self.tables["BEH_ug.csv"][2]["trialGlobal"] = "1.0"
        self.save_fixture()
        self.assert_rejected("Duplicate behavior trial identity")

    def test_missing_identity_is_not_just_a_complete_case_exclusion(self):
        self.tables["BEH_ug.csv"][1]["sub"] = "NA"
        self.save_fixture()
        self.assert_rejected("Missing trial identity")

    def test_inf_in_retained_covariate_is_rejected(self):
        self.tables["df_P3b_base.csv"][0]["P3b_base_offer_s"] = "Inf"
        self.save_fixture()
        self.assert_rejected("Nonfinite P3b_base_offer_s")

    def test_first_filter_happens_before_numeric_validation(self):
        self.tables["df_P3b_base.csv"][1]["P3b_base_offer_s"] = "Inf"
        self.save_fixture()
        self.assertEqual(self.run_preparation()["models"]["P3b"]["retained_rows"], 6)

    def test_model_specific_missing_covariate_changes_eligible_rows(self):
        self.tables["df_P3b_base.csv"][0]["P3b_base_offer_s"] = "NA"
        self.save_fixture()
        self.assert_rejected("Registered retained cohort mismatch: P3b")

    def test_short_source_table_is_not_zipped_and_truncated(self):
        self.tables["df_P2_offer.csv"].pop()
        self.save_fixture()
        self.assert_rejected("Source row-count mismatch")

    def test_ragged_row_rejected_even_with_matching_fixture_hash(self):
        spec = self.contract["public_input_files"][1]
        path = self.source / Path(spec["path"]).name
        payload = path.read_bytes().replace(b"1.2300,1.2300", b"1.2300,1.2300,7", 1)
        path.write_bytes(payload)
        spec["bytes"], spec["sha256"] = len(payload), prepare.digest(payload)
        self.contract_path.write_text(json.dumps(self.contract))
        self.assert_rejected("Ragged source CSV")

    def test_source_panel_loss_rejected(self):
        for index, row in enumerate(self.tables["BEH_ug.csv"], 1):
            row["sub"] = "one-participant"
            row["trialGlobal"] = str(index)
        self.save_fixture()
        self.assert_rejected("Source participant panel")

    def test_formula_change_cannot_use_stale_complete_case_columns(self):
        self.contract["models"]["P3b"]["formula"] += " + partnerID"
        self.save_fixture()
        self.assert_rejected("Formula variables changed")

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        marker = self.output / "marker"
        marker.write_text("unchanged")
        with self.assertRaisesRegex(prepare.PreparationError, "must be fresh"):
            self.run_preparation()
        self.assertEqual(marker.read_text(), "unchanged")

    def test_source_directory_cannot_receive_outputs(self):
        self.output = self.source / "derived"
        self.assert_rejected("outside the repository and source")


if __name__ == "__main__":
    unittest.main(verbosity=2)

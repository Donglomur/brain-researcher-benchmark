"""Generated metadata controls; no authentic HDF5, labels or signals are read."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest

COMPONENT = Path(__file__).resolve().parents[1]
TASK = COMPONENT.parent.parent / "task.json"
SOURCE = COMPONENT / "reconcile.py"
spec = importlib.util.spec_from_file_location("n014_source_count_reconciliation", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture(coverage="all_source_members"):
    task = TASK.read_bytes()
    members = mod.source_members(task)
    lines = io.StringIO(newline="")
    writer = csv.writer(lines)
    writer.writerow(mod.CSV_FIELDS)
    documents = []
    dates = {}
    for name, row in sorted(members.items()):
        dates.setdefault(row["date"], set()).add(row["split"])
        if coverage == "labeled_train_val" and row["split"] == "test":
            continue
        block = 1 if row["split"] == "train" else 2
        trial_num = {"train": 1, "val": 2, "test": 3}[row["split"]]
        documents.append({"name": name, "bytes": row["bytes"],
            "sha256": hashlib.sha256(("GENERATED:" + name).encode()).hexdigest(),
            "trials": [{"group": "trial_0000", "session": row["session"],
                        "block_num": block, "trial_num": trial_num}]})
    for day, splits in sorted(dates.items()):
        writer.writerow([day, 1, 1, 1, "GENERATED", "Train"])
        if splits - {"train"}:
            writer.writerow([day, 1, 2, len(splits - {"train"}), "GENERATED", "Val/Test"])
    headers = {"schema": "neural014-trial-header-census-v1", "coverage": coverage,
               "archive_sha256": mod.ARCHIVE_SHA256, "members": documents}
    return task, lines.getvalue().encode(), headers


class SourceCountReconciliationTests(unittest.TestCase):
    def call(self, values):
        task, csv_body, headers = values
        return mod.reconcile(task, csv_body, mod.canonical(headers))

    def test_full_metadata_comparison_is_not_authentication_or_readiness(self):
        out = self.call(fixture())
        self.assertEqual((out["source_member_count"], out["observed_trial_count"]), (127, 127))
        self.assertTrue(out["all_source_blocks_match"])
        self.assertFalse(out["source_payload_authentication_established"])
        self.assertFalse(out["scientific_qualified"])
        self.assertEqual(out["observed_minus_readme"], 127 - 10948)

    def test_labeled_only_does_not_treat_combined_val_test_as_exact(self):
        out = self.call(fixture("labeled_train_val"))
        self.assertEqual(out["source_member_count"], 86)
        self.assertIsNone(out["all_source_blocks_match"])
        self.assertIsNone(out["observed_minus_readme"])
        partial = [r for r in out["blocks"] if r["source_split"] == "Val/Test"]
        self.assertTrue(partial)
        self.assertTrue(all(r["matches"] is None and r["observed_minus_declared"] is None for r in partial))
        self.assertTrue(all(r["unobserved_or_discrepant_count"] == 1 for r in partial))

    def test_missing_train_trials_are_retained_as_count_differences(self):
        values = fixture()
        member = next(r for r in values[2]["members"] if r["name"].endswith("data_train.hdf5"))
        member["trials"] = []
        out = self.call(values)
        self.assertFalse(out["all_exact_blocks_match"])
        self.assertEqual(sum(r["observed_minus_declared"] for r in out["blocks"]), -1)
        self.assertFalse(out["source_exclusions_inferred"])

    def test_extra_labeled_trials_invalidate_the_lower_bound(self):
        values = fixture("labeled_train_val")
        member = next(r for r in values[2]["members"] if r["name"].endswith("data_val.hdf5"))
        for i in (5, 6):
            extra = dict(member["trials"][0], group=f"trial_{i:04}", trial_num=i)
            member["trials"].append(extra)
        out = self.call(values)
        self.assertFalse(out["all_lower_bounds_valid"])
        self.assertTrue(any(r["unobserved_or_discrepant_count"] == -1 for r in out["blocks"]))

    def test_missing_member_refuses_comparison(self):
        values = fixture()
        values[2]["members"].pop()
        with self.assertRaisesRegex(ValueError, "every selected"):
            self.call(values)

    def test_duplicate_native_trial_across_val_test_refuses(self):
        values = fixture()
        val = next(r for r in values[2]["members"] if r["name"].endswith("data_val.hdf5"))
        test = next(r for r in values[2]["members"] if r["name"] == val["name"].replace("data_val", "data_test"))
        test["trials"][0]["trial_num"] = val["trials"][0]["trial_num"]
        with self.assertRaisesRegex(ValueError, "duplicate native trial"):
            self.call(values)

    def test_unknown_block_and_split_confusion_refuse(self):
        for new_block in (0, 2):
            values = fixture()
            row = next(r for r in values[2]["members"] if r["name"].endswith("data_train.hdf5") and "2023.08.13" in r["name"])
            row["trials"][0]["block_num"] = new_block
            with self.assertRaises(ValueError):
                self.call(values)

    def test_unknown_signal_or_target_fields_refuse(self):
        for key in ("input_features", "tokens", "transcription"):
            values = fixture()
            values[2]["members"][0]["trials"][0][key] = []
            with self.assertRaisesRegex(ValueError, "only native identity"):
                self.call(values)

    def test_frozen_source_roster_change_refuses(self):
        task, csv_body, headers = fixture()
        changed = json.loads(task)
        changed["input_assets"]["readiness_records"][0]["data_manifest"]["neural_archive_members"][0]["size"] += 1
        with self.assertRaisesRegex(ValueError, "unchanged frozen"):
            mod.reconcile(mod.canonical(changed), csv_body, mod.canonical(headers))

    def test_duplicate_csv_block_and_json_keys_refuse(self):
        task, csv_body, headers = fixture()
        with self.assertRaisesRegex(ValueError, "duplicate author date/block"):
            mod.reconcile(task, csv_body + csv_body.splitlines(keepends=True)[1], mod.canonical(headers))
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            mod.reconcile(task, csv_body, b'{"schema":"x","schema":"y"}')

    def test_boolean_trial_identity_refuses(self):
        values = fixture()
        values[2]["members"][0]["trials"][0]["trial_num"] = True
        with self.assertRaisesRegex(ValueError, "native integer"):
            self.call(values)


if __name__ == "__main__":
    unittest.main()

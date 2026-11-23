"""Small generated index-alignment controls; no native curation execution."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e
from example_control import control
from prepare_exports import prepare_curation_exports, write_curation_exports


def native_results(exports):
    results = {}
    for sorter, exported in exports["sorters"].items():
        rows = exported["unit_rows"]
        results[sorter] = {
            "native_unit_ids": [r["unit_id"] for r in rows],
            "bombcell_labels": [(r["unit_id"], r["bombcell_label"]) for r in reversed(rows)],
            "unitrefine_labels": [(r["unit_id"], r["unitrefine_label"]) for r in rows[2:] + rows[:2]],
            "slay_merge_groups": copy.deepcopy(exported["slay_merge_groups"]),
            "native_artifact_sha256": exported["native_artifact_sha256"],
        }
    return results


class PreparationControls(unittest.TestCase):
    def setUp(self):
        self.manifest, self.expected, self.digest, self.raster = control()
        self.native = native_results(self.expected)

    def prepare(self):
        return prepare_curation_exports(self.manifest, self.native, self.digest)

    def test_shuffled_curators_join_by_id_and_keep_exact_good_raster(self):
        actual = self.prepare()
        self.assertEqual(actual, self.expected)
        destination = io.StringIO()
        summary = e.export_good_unit_raster(self.manifest, actual, self.digest,
                                            io.StringIO(self.raster), destination)
        self.assertEqual(summary["retained_spikes"], 1)
        self.assertEqual([r["unit_id"] for r in csv.DictReader(io.StringIO(destination.getvalue()))], ["u1"])

    def test_index_omissions_duplicates_and_foreign_ids_fail(self):
        original = copy.deepcopy(self.native)
        for name in ("bombcell_labels", "unitrefine_labels"):
            for mutation in ("missing", "duplicate", "foreign", "bad_label"):
                with self.subTest(column=name, mutation=mutation):
                    self.native = copy.deepcopy(original)
                    pairs = self.native["lupin"][name]
                    if mutation == "missing": pairs.pop()
                    if mutation == "duplicate": pairs[-1] = pairs[0]
                    if mutation == "foreign": pairs[-1] = ("foreign", pairs[-1][1])
                    if mutation == "bad_label": pairs[-1] = (pairs[-1][0], None)
                    with self.assertRaises(e.ContractError): self.prepare()

    def test_native_inventory_and_all_sorters_required(self):
        self.native["lupin"]["native_unit_ids"].pop()
        with self.assertRaises(e.ContractError): self.prepare()
        self.native = native_results(self.expected)
        del self.native["lupin"]
        with self.assertRaises(e.ContractError): self.prepare()

    def test_integer_ids_and_generators_preserve_identity(self):
        for sorter in e.SORTERS:
            self.manifest["runs"][sorter]["unit_spike_counts"] = {str(i): 1 for i in range(1, 6)}
            item = self.native[sorter]
            item["native_unit_ids"] = iter(range(1, 6))
            for column in ("bombcell_labels", "unitrefine_labels"):
                item[column] = iter([(int(uid[1:]), label) for uid, label in item[column]])
            item["slay_merge_groups"] = [[int(uid[1:]) for uid in group] for group in item["slay_merge_groups"]]
        self.digest = e.canonical_digest(self.manifest)
        result = self.prepare()["sorters"]["kilosort4"]
        self.assertEqual([r["unit_id"] for r in result["unit_rows"]], ["1", "2", "3", "4", "5"])
        self.assertEqual(result["unit_rows"][0]["bombcell_label"], "good")
        self.assertEqual(result["slay_merge_groups"], [["1", "2", "3"], ["4", "5"]])

    def test_lossy_or_type_changed_ids_rejected(self):
        for bad_id in (True, 1.0, None):
            with self.subTest(bad_id=bad_id):
                self.native = native_results(self.expected)
                self.native["lupin"]["native_unit_ids"][0] = bad_id
                with self.assertRaises(e.ContractError): self.prepare()
        self.native = native_results(self.expected)
        self.native["lupin"]["native_unit_ids"] = [1, "1", "u3", "u4", "u5"]
        with self.assertRaisesRegex(e.ContractError, "colliding"): self.prepare()
        self.native = native_results(self.expected)
        self.native["lupin"]["native_unit_ids"][0] = 1
        self.manifest["runs"]["lupin"]["unit_spike_counts"] = {"1": 1, **{f"u{i}": 1 for i in range(2, 6)}}
        self.digest = e.canonical_digest(self.manifest)
        self.native["lupin"]["bombcell_labels"][-1] = ("1", "good")
        with self.assertRaisesRegex(e.ContractError, "foreign native"): self.prepare()

    def test_zero_unit_sorter_retained_and_holds_unchanged(self):
        self.manifest["runs"]["lupin"]["unit_spike_counts"] = {}
        self.digest = e.canonical_digest(self.manifest)
        self.native["lupin"].update(native_unit_ids=[], bombcell_labels=[], unitrefine_labels=[], slay_merge_groups=[])
        report = e.evaluate_curation(self.manifest, self.prepare(), self.digest)
        self.assertEqual(report["sorters"]["lupin"]["source_table"]["total units"], 0)
        self.assertEqual(report["holds"], list(e.HOLDS))
        self.assertFalse(report["scientific_qualified"])

    def test_merge_groups_and_native_hash_use_existing_policy(self):
        for field, value in (("slay_merge_groups", [["u1", "u2"], ["u2", "u3"]]),
                             ("slay_merge_groups", [["u1", "foreign"]]),
                             ("native_artifact_sha256", "0" * 64)):
            self.native = native_results(self.expected)
            self.native["lupin"][field] = value
            with self.subTest(field=field), self.assertRaises(e.ContractError): self.prepare()

    def test_write_is_consumable_and_rejects_existing_or_invalid_output(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "curation.json"
            digest = write_curation_exports(self.manifest, self.native, self.digest, destination)
            actual = e._load(destination)
            self.assertEqual(actual, self.expected)
            self.assertEqual(digest, e.canonical_digest(actual))
            with self.assertRaises(FileExistsError):
                write_curation_exports(self.manifest, self.native, self.digest, destination)
            self.native["lupin"]["unitrefine_labels"].pop()
            invalid = Path(directory) / "invalid.json"
            with self.assertRaises(e.ContractError):
                write_curation_exports(self.manifest, self.native, self.digest, invalid)
            self.assertFalse(invalid.exists())
            self.assertEqual(json.loads(destination.read_text()), self.expected)

    def test_independent_owner_digest_required(self):
        self.manifest["recording"]["num_frames"] += 1
        with self.assertRaises(e.ContractError): self.prepare()


if __name__ == "__main__":
    unittest.main()

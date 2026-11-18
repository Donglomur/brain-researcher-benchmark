import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e
from example_control import control


class CurationTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.exports, self.digest, self.raster = control()

    def score(self):
        return e.evaluate_curation(self.manifest, self.exports, self.digest)

    def refreeze(self):
        self.digest = e.canonical_digest(self.manifest)
        self.exports["owner_manifest_sha256"] = self.digest

    def test_independent_five_label_count_oracle(self):
        # Independently derived source-review control: include non-somatic good/MUA.
        table = self.score()["sorters"]["kilosort4"]
        self.assertEqual(table["source_table"], {
            "total units": 5, "bombcell good": 2, "unitrefine sua": 2,
            "bombcell mua": 2, "unitrefine mua": 2, "# slay merges": 2,
            "bombcell noise": 1, "unitrefine noise": 1})
        self.assertEqual(table["slay_units_in_proposed_groups"], 5)
        self.assertEqual(table["fractions_of_all_units"]["bombcell good"], 0.4)
        cross = table["curation_label_cross_tab"]
        self.assertEqual(cross["good"], {"sua": 1, "mua": 0, "noise": 0})
        self.assertEqual(cross["non_soma_good"], {"sua": 0, "mua": 1, "noise": 0})
        self.assertEqual(cross["noise"]["sua"], 1)

    def test_paired_differences_keep_fixed_four_comparators(self):
        self.exports["sorters"]["lupin"]["unit_rows"][0]["bombcell_label"] = "noise"
        differences = self.score()["paired_descriptive_count_differences"]
        self.assertEqual(len(differences), 6)
        pair = next(p for p in differences if p["left"] == "kilosort4" and p["right"] == "lupin")
        self.assertEqual(pair["left_minus_right"]["bombcell good"], 1)
        self.assertEqual(pair["left_minus_right"]["bombcell noise"], -1)

    def test_missing_comparator_rejected(self):
        del self.exports["sorters"]["lupin"]
        with self.assertRaises(e.ContractError): self.score()

    def test_missing_unit_rejected(self):
        self.exports["sorters"]["kilosort4"]["unit_rows"].pop()
        with self.assertRaises(e.ContractError): self.score()

    def test_duplicate_unit_rejected(self):
        self.exports["sorters"]["lupin"]["unit_rows"].append(copy.deepcopy(self.exports["sorters"]["lupin"]["unit_rows"][0]))
        with self.assertRaises(e.ContractError): self.score()

    def test_unknown_label_rejected(self):
        self.exports["sorters"]["lupin"]["unit_rows"][0]["bombcell_label"] = "best"
        with self.assertRaises(e.ContractError): self.score()

    def test_overlapping_merge_groups_rejected(self):
        self.exports["sorters"]["lupin"]["slay_merge_groups"] = [["u1", "u2"], ["u2", "u3"]]
        with self.assertRaises(e.ContractError): self.score()

    def test_zero_units_retained_with_undefined_fractions(self):
        self.manifest["runs"]["lupin"]["unit_spike_counts"] = {}
        self.exports["sorters"]["lupin"].update(unit_rows=[], slay_merge_groups=[])
        self.refreeze()
        table = self.score()["sorters"]["lupin"]
        self.assertEqual(table["source_table"]["total units"], 0)
        self.assertTrue(all(v is None for v in table["fractions_of_all_units"].values()))

    def test_owner_manifest_mutation_rejected(self):
        self.manifest["recording"]["num_frames"] += 1
        with self.assertRaises(e.ContractError): self.score()

    def test_other_asset_not_silently_substituted(self):
        self.manifest["recording"]["asset_path"] = "some-other-recording.nwb"
        self.refreeze()
        with self.assertRaises(e.ContractError): self.score()

    def test_source_analyzer_order_preserved_as_unresolved_comparability(self):
        self.manifest["runs"]["kilosort4"]["analyzer_preprocessing_order"].reverse()
        self.refreeze()
        with self.assertRaises(e.ContractError): self.score()

    def test_native_artifact_identity_bound(self):
        self.exports["sorters"]["lupin"]["native_artifact_sha256"] = "0" * 64
        with self.assertRaises(e.ContractError): self.score()

    def test_resource_claims_must_be_finite(self):
        self.manifest["runs"]["lupin"]["runtime_seconds"] = -1
        self.refreeze()
        with self.assertRaises(e.ContractError): self.score()

    def test_native_label_does_not_promote_qualification(self):
        self.manifest["evidence_kind"] = "owner_native_exports"
        self.manifest["runs"]["kilosort4"]["sorter_version"] = "4.1.2"
        self.refreeze()
        report = self.score()
        for key in ("scientific_qualified", "full_contract_complete", "native_reference_verified", "spike_accuracy_estimated"):
            self.assertFalse(report[key])
        self.assertIn("quality_labels_and_yield_are_not_spike_accuracy", report["holds"])

    def test_native_kilosort_version_must_match_pinned_source(self):
        self.manifest["evidence_kind"] = "owner_native_exports"
        self.manifest["runs"]["kilosort4"]["sorter_version"] = "4.0.0"
        self.refreeze()
        with self.assertRaises(e.ContractError): self.score()

    def test_finite_sampling_rate_with_infinite_derived_duration_rejected(self):
        self.manifest["recording"]["sampling_frequency_hz"] = 5e-324
        self.refreeze()
        with self.assertRaises(e.ContractError): self.score()

    def raster_export(self, raster=None):
        output = io.StringIO()
        summary = e.export_good_unit_raster(self.manifest, self.exports, self.digest,
                                           io.StringIO(self.raster if raster is None else raster), output)
        return summary, list(csv.DictReader(io.StringIO(output.getvalue())))

    def test_drift_filter_exactly_good_not_non_somatic_good(self):
        summary, rows = self.raster_export()
        self.assertEqual(summary["input_spikes"], 5)
        self.assertEqual(summary["retained_spikes"], 1)
        self.assertEqual([r["unit_id"] for r in rows], ["u1"])
        self.assertEqual(float(rows[0]["time_seconds"]), .01)
        self.assertFalse(summary["numeric_drift_robustness_computed"])

    def test_drift_missing_nonretained_spike_still_rejected(self):
        with self.assertRaises(e.ContractError): self.raster_export(self.raster.rsplit("u5", 1)[0])

    def test_drift_nonfinite_coordinate_rejected(self):
        with self.assertRaises(e.ContractError): self.raster_export(self.raster.replace("20,-100", "NaN,-100", 1))

    def test_drift_duplicate_frame_rejected(self):
        with self.assertRaises(e.ContractError): self.raster_export(self.raster + "u5,50,100,-100\n")

    def test_drift_out_of_recording_rejected(self):
        with self.assertRaises(e.ContractError): self.raster_export(self.raster.replace("u5,50", "u5,100"))

    def test_cli_complete_outputs_and_failure_is_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "manifest.json").write_text(json.dumps(self.manifest))
            (root / "curation.json").write_text(json.dumps(self.exports))
            (root / "spikes.csv").write_text(self.raster)
            args = ["--owner-manifest", str(root / "manifest.json"), "--expected-manifest-sha256", self.digest,
                    "--curation-json", str(root / "curation.json"), "--drift-spikes-csv", str(root / "spikes.csv"),
                    "--output-directory", str(root / "report")]
            self.assertEqual(e.main(args), 0)
            self.assertEqual({p.name for p in (root / "report").iterdir()},
                             {"report.json", "source_curation_table.csv", "good_unit_raster.csv"})
            report = json.loads((root / "report/report.json").read_text())
            self.assertEqual(report["drift_raster"]["retained_spikes"], 1)
            self.assertEqual(report["input_raster_sha256"], hashlib.sha256(self.raster.encode()).hexdigest())
            for name, digest in report["output_artifacts_sha256"].items():
                self.assertEqual(digest, hashlib.sha256((root / "report" / name).read_bytes()).hexdigest())
            args[-1] = str(root / "failed")
            (root / "spikes.csv").write_text(self.raster.rsplit("u5", 1)[0])
            with self.assertRaises(e.ContractError): e.main(args)
            self.assertFalse((root / "failed").exists())
            self.assertEqual(list(root.glob(".curation-stage-*")), [])

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text('{"sorters": {}, "sorters": {}}')
            with self.assertRaises(e.ContractError): e._load(path)


class RetainedContractBindingTests(unittest.TestCase):
    def test_declared_contract_file_matches_the_executable_policy(self):
        # An old digest must resolve to the retained contract, not a later task.
        implementation = Path(__file__).resolve().parents[1]
        repository = Path(__file__).resolve().parents[6]
        provenance = json.loads((implementation / "source-provenance.json").read_text(encoding="utf-8"))
        declaration = provenance["contract"]
        relative = Path(declaration["path"])
        self.assertFalse(relative.is_absolute())
        self.assertNotIn("..", relative.parts)
        payload = (repository / relative).read_bytes()
        actual_digest = hashlib.sha256(payload).hexdigest()
        self.assertEqual(actual_digest, declaration["sha256"],
                         "declared contract path must resolve to the pinned bytes")
        self.assertEqual(actual_digest, e.CONTRACT_SHA256)
        self.assertEqual(json.loads(payload)["id"], e.TASK_ID)
        self.assertEqual(provenance["task_id"], e.TASK_ID)


if __name__ == "__main__":
    unittest.main()

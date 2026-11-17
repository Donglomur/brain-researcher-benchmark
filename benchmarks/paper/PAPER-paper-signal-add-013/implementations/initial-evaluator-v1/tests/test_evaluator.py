"""Generated engineering controls; no empirical observations or benchmark targets."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("hemodynamics_evaluator", MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def generated_packet():
    """Fictitious receipts, visibly generated; valid only for parser/algorithm controls."""
    indices = np.arange(6, dtype=np.int64)
    arrays = {
        "voxel_indices": indices,
        "positive_mask": np.array([True, True, True, False, False, False]),
        "negative_mask": np.array([False, False, False, True, True, True]),
        "bold_percent_change": np.tile([1., 2., 3., -1., -2., -3.], (40, 1)),
        "cmro2_control_orig": np.full((40, 6), 100.),
        "cmro2_calc_cbv": np.tile([110., 120., 130., 110., 120., 130.], (40, 1)),
        "cmro2_calc_source_original": np.full((40, 6), 105.),
    }
    arrays["cmro2_calc_source_original"][30:] = arrays["cmro2_calc_cbv"][30:]
    fake = hashlib.sha256(b"GENERATED ENGINEERING RECEIPT; NOT AUTHENTIC DATA").hexdigest()
    manifest = {
        "schema_version": 1, "task_id": e.TASK_ID, "contract_sha256": e.CONTRACT_SHA256,
        "dataset": "ds004873", "dataset_version": "2.0.6", "dataset_git_revision": e.DATA_REVISION,
        "official_code_revision": e.CODE_REVISION, "contrast": "calc-control",
        "primary_lineage": "calc_desc-CBV_vs_control_desc-orig",
        "original_sensitivity_lineage": "calc_desc-orig_first30_desc-CBV_last10_vs_control_desc-orig",
        "mask_policy": "frozen_source_PLS_BOLD_reproduction_only",
        "spatial_null_policy": "withheld_pending_geometry_preserving_null_qualification",
        "bold_units": "already_percent_change", "cmro2_units": "umol/100g/min",
        "subject_ids": list(e.SUBJECTS),
        "grid": {"space": "MNI152", "shape": [91, 109, 91], "voxel_size_mm": [2, 2, 2],
                 "index_order": "C_flat_sorted", "affine_sha256": fake,
                 "voxel_indices_sha256": hashlib.sha256(indices.astype("<i8").tobytes()).hexdigest()},
        "data_file": "maps.npz", "data_sha256": fake,
        "source_receipt_status": "operator_attested_not_independently_authenticated",
        "preassessment_freeze_receipt_sha256": fake,
        "physiology_and_cbv_lineage_receipt_sha256": fake,
        "map_receipts": [{"subject_id": subject, "map_key": key,
                          "path": e.source_map_path(subject, key), "sha256": fake,
                          "bytes": 1, "affine_sha256": fake}
                         for subject in e.SUBJECTS for key in e.MAP_KEYS],
        "mask_receipts": {key: {"path": path, "sha256": fake, "affine_sha256": fake}
                          for key, path in e.MASK_PATHS.items()},
    }
    return manifest, arrays


class ContrastControls(unittest.TestCase):
    def test_fixed_source_cohort_and_lineage(self):
        self.assertEqual(len(e.SUBJECTS), 40)
        self.assertNotIn("sub-p053", e.SUBJECTS)
        self.assertTrue(e.source_map_path("sub-p019", "cmro2_calc_source_original").endswith("desc-orig_cmro2.nii.gz"))
        self.assertTrue(e.source_map_path("sub-p068", "cmro2_calc_source_original").endswith("desc-CBV_cmro2.nii.gz"))
        manifest, arrays = generated_packet()
        e.validate_manifest(manifest)
        e.validate_arrays(arrays, manifest)

    def test_known_opposition_and_agreement_without_bold_rescaling(self):
        manifest, arrays = generated_packet()
        result = e.evaluate_packet(manifest, arrays, bootstrap_replicates=7)
        positive = result["outputs"]["primary_cbv"]["positive"]
        negative = result["outputs"]["primary_cbv"]["negative"]
        self.assertEqual(positive["source_spatial_median_of_voxelwise_subject_medians"],
                         {"bold_percent": 2., "cmro2_percent": 20.})
        self.assertEqual(negative["group_voxel_signs"]["opposed_fraction_nonzero"], 1.)
        self.assertEqual(positive["group_voxel_signs"]["opposed_fraction_nonzero"], 0.)
        self.assertAlmostEqual(positive["spatial_pearson_descriptive"], 1.)
        self.assertAlmostEqual(negative["spatial_pearson_descriptive"], -1.)
        self.assertEqual(positive["prospective_paired_subject_bootstrap_percentile_95"]["cmro2_percent"], [20., 20.])
        self.assertIsNone(result["reward"])
        self.assertIsNone(result["spatial_null_pvalue"])
        self.assertFalse(result["research_qualified"])

    def test_independently_derived_noncommuting_medians(self):
        # Source/reference worker derived this exact40 fixture independently.
        rows = np.array([[0., 0., 100.]] * 14 + [[0., 100., 0.]] * 13
                        + [[100., 100., 100.]] * 13)
        result = e._region_summary(rows, e.percent_change(100. + rows, np.full_like(rows, 100.)))
        self.assertEqual(result["source_spatial_median_of_voxelwise_subject_medians"]["cmro2_percent"], 100.)
        self.assertEqual(result["median_of_participant_spatial_medians"]["cmro2_percent"], 0.)

    def test_subject_percentages_precede_group_reduction(self):
        changes = e.percent_change(np.array([20., 90.]), np.array([10., 100.]))
        np.testing.assert_allclose(changes, [100., -10.])
        self.assertEqual(float(np.median(changes)), 45.)
        self.assertNotEqual(float(np.median(changes)), float(e.percent_change(np.median([20.,90.]), np.median([10.,100.]))))

    def test_paired_bootstrap_exact_independent_reference(self):
        bold = np.arange(24, dtype=float).reshape(4, 6)
        metabolism = 3. * bold + 1.
        samples = np.array([[0, 0, 2, 3], [1, 1, 1, 3], [0, 1, 2, 3]])
        reference_b, reference_m = [], []
        # Pure-Python statistics independently computes the nested medians.
        from statistics import median
        for row in samples:
            reference_b.append(median([median([float(bold[i,j]) for i in row]) for j in range(6)]))
            reference_m.append(median([median([float(metabolism[i,j]) for i in row]) for j in range(6)]))
        observed = e._bootstrap(bold, metabolism, samples)
        np.testing.assert_allclose(observed["bold_percent"], np.quantile(reference_b, [.025,.975]))
        np.testing.assert_allclose(observed["cmro2_percent"], np.quantile(reference_m, [.025,.975]))
        np.testing.assert_allclose(observed["cmro2_percent"], 3 * np.array(observed["bold_percent"]) + 1)

    def test_constant_and_zero_signs_are_explicit(self):
        s = e._region_summary(np.array([[0., 1., -1.]]), np.array([[0., 2., 2.]]))
        self.assertEqual(s["group_voxel_signs"], {"nonzero_pair_count": 2, "zero_pair_count": 1,
                                                 "opposed_count": 1, "opposed_fraction_nonzero": .5})
        self.assertIsNone(e.pearson([1., 1.], [0., 2.]))
        all_zero = e._region_summary(np.zeros((40,3)), np.zeros((40,3)))
        self.assertIsNone(all_zero["group_voxel_signs"]["opposed_fraction_nonzero"])

    def test_rejects_population_and_policy_mutations(self):
        manifest, arrays = generated_packet()
        mutations = [lambda m: m["subject_ids"].pop(),
                     lambda m: m["subject_ids"].__setitem__(0, "sub-p053"),
                     lambda m: m.__setitem__("dataset_version", "1.0.4"),
                     lambda m: m.__setitem__("bold_units", "raw_intensity"),
                     lambda m: m.__setitem__("mask_policy", "selected_for_largest_opposition"),
                     lambda m: m["map_receipts"].pop(),
                     lambda m: m["map_receipts"][0].__setitem__("path", "other.nii.gz"),
                     lambda m: m["mask_receipts"]["positive"].__setitem__("affine_sha256", "a"*64)]
        for change in mutations:
            with self.subTest(change=change):
                bad = copy.deepcopy(manifest); change(bad)
                with self.assertRaises(e.ContractError): e.validate_manifest(bad)

    def test_rejects_invalid_arrays_without_dropping_units(self):
        manifest, arrays = generated_packet()
        mutations = [lambda a: a.__setitem__("bold_percent_change", a["bold_percent_change"][:30]),
                     lambda a: a["cmro2_control_orig"].__setitem__((0,0), 0.),
                     lambda a: a["bold_percent_change"].__setitem__((0,0), np.nan),
                     lambda a: a["positive_mask"].__setitem__(3, True),
                     lambda a: a["positive_mask"].fill(False),
                     lambda a: a["voxel_indices"].__setitem__(0, 5),
                     lambda a: a["cmro2_calc_source_original"].__setitem__((39,0), 100.)]
        for change in mutations:
            with self.subTest(change=change):
                bad = copy.deepcopy(arrays); change(bad)
                with self.assertRaises(e.ContractError): e.validate_arrays(bad, manifest)

    def test_digest_bound_packet_and_cli(self):
        manifest, arrays = generated_packet()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = root / "maps.npz"; path = root / "manifest.json"
            np.savez_compressed(data, **arrays)
            manifest["data_sha256"] = e.sha256_file(data)
            path.write_text(json.dumps(manifest)); pin = e.sha256_file(path)
            e.load_packet(path, pin)
            output = root / "result.json"
            e.main([str(path), "--expected-manifest-sha256", pin, "--output", str(output),
                    "--bootstrap-replicates", "3"])
            self.assertEqual(json.loads(output.read_text())["n_primary"], 40)
            with self.assertRaises(e.ContractError): e.load_packet(path, "0"*64)
            data.write_bytes(data.read_bytes() + b"tampered")
            with self.assertRaises(e.ContractError): e.load_packet(path, pin)


if __name__ == "__main__":
    unittest.main()

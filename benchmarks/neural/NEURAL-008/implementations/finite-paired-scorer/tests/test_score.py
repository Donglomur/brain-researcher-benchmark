"""Generated controls only. No original targets, recordings or predictions read."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import score
from neural008_vendor import candidate_adapter as adapter
from neural008_vendor import paired_core


class PairedScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.submission = self.root / "submission"
        self.submission.mkdir()
        self.targets = {}
        for case in score.CASES:
            stage = np.arange(case.epochs, dtype=np.int16) % 5
            self.targets[case.case_id] = {"epoch_id": adapter.expected_ids(case),
                                          "stage": stage, "score_mask": stage >= 0}
        self.calls = 0
        self.write_panel("EEG_clock")
        self.write_panel("EEG_EOG_clock")
        self.claims = {"schema_version": 1, "candidate_id": "NEURAL-008", "reported_contrast": None}
        self.write_claims()

    def loader(self):
        self.calls += 1
        return self.targets

    def write_claims(self):
        (self.submission / "claims.json").write_text(json.dumps(self.claims), encoding="utf-8")

    def panel(self, fixed=None):
        arrays = {"class_order": np.asarray(adapter.CLASS_ORDER)}
        for case in score.CASES:
            labels = self.targets[case.case_id]["stage"]
            chosen = np.maximum(labels, 0) if fixed is None else np.full(case.epochs, fixed)
            arrays[case.case_id + "__epoch_id"] = adapter.expected_ids(case)
            arrays[case.case_id + "__probabilities"] = np.eye(5, dtype=np.float64)[chosen]
        return arrays

    def write_panel(self, arm, arrays=None):
        np.savez(self.submission / (arm + ".npz"), **(self.panel() if arrays is None else arrays))

    def refuse_before_targets(self):
        with self.assertRaises((ValueError, zipfile.BadZipFile, OSError)):
            score.assess(self.submission, self.loader)
        self.assertEqual(self.calls, 0)

    def test_equal_person_contrast_not_epoch_pooling(self):
        eeg = self.panel()
        eog = self.panel()
        eeg["development-001__probabilities"][:] = [1, 0, 0, 0, 0]
        eog["development-002__probabilities"][:] = [1, 0, 0, 0, 0]
        self.write_panel("EEG_clock", eeg)
        self.write_panel("EEG_EOG_clock", eog)
        report = score.assess(self.submission, self.loader)
        self.assertEqual(self.calls, 1)
        result = report["result"]
        contrast = result["paired_contrast"]
        # Each person's true classes are balanced. Always W gives F1_W=1/3,
        # then fixed-five-class macro-F1=1/15, independent of night length.
        self.assertAlmostEqual(contrast["per_person"][0]["macro_f1_delta"], 14 / 15)
        self.assertAlmostEqual(contrast["per_person"][1]["macro_f1_delta"], -14 / 15)
        self.assertAlmostEqual(contrast["person_mean_macro_f1_delta"], 0)
        self.assertEqual(contrast["person_mean_rem_recall_delta"], 0)
        self.assertEqual(set(result["absolute_performance"]), set(paired_core.ARMS))
        self.assertIsNone(report["score"])
        self.assertFalse(result["scientific_improvement_verified"])

    def test_negative_contribution_is_valid_and_absolute_scores_retained(self):
        self.write_panel("EEG_EOG_clock", self.panel(fixed=0))
        result = score.assess(self.submission, self.loader)["result"]
        self.assertAlmostEqual(result["paired_contrast"]["person_mean_macro_f1_delta"], -14 / 15)
        self.assertEqual(result["paired_contrast"]["person_mean_rem_recall_delta"], -1)
        self.assertIsNone(result["scalar_optimization_reward"])
        self.assertEqual(result["absolute_performance"]["EEG_clock"]["person_mean_macro_f1"], 1)

    def test_undefined_rem_is_not_silently_averaged_over_one_person(self):
        self.targets["development-002"]["stage"][:] = 0
        self.write_panel("EEG_clock")
        self.write_panel("EEG_EOG_clock")
        result = score.assess(self.submission, self.loader)["result"]
        contrast = result["paired_contrast"]
        self.assertEqual(len(contrast["per_person"]), 2)
        self.assertIsNone(contrast["per_person"][1]["rem_recall_delta"])
        self.assertIsNone(contrast["person_mean_rem_recall_delta"])
        person = result["absolute_performance"]["EEG_clock"]["per_person"][1]
        self.assertEqual(person["f1_by_stage"], [1, 0, 0, 0, 0])
        self.assertEqual(person["macro_f1_fixed_five"], .2)
        self.assertFalse(result["population_inference"])
        self.assertIsNone(result["confidence_interval"])

    def test_ties_fixed_class_and_mask_only_affects_scoring(self):
        for case in score.CASES:
            row = self.targets[case.case_id]
            row["stage"][:5] = -1
            row["score_mask"][:5] = False
        arrays = self.panel()
        for case in score.CASES:
            arrays[case.case_id + "__probabilities"][:] = .2
        self.write_panel("EEG_clock", arrays)
        result = score.assess(self.submission, self.loader)["result"]
        for row, case in zip(result["absolute_performance"]["EEG_clock"]["per_person"], score.CASES):
            self.assertEqual(row["full_epochs"], case.epochs)
            self.assertEqual(row["scored_epochs"], case.epochs - 5)
            self.assertEqual(row["predicted_support"], [case.epochs - 5, 0, 0, 0, 0])

    def test_bad_second_arm_never_loads_targets(self):
        arrays = self.panel()
        arrays["development-002__epoch_id"] = arrays["development-002__epoch_id"][::-1]
        self.write_panel("EEG_EOG_clock", arrays)
        self.refuse_before_targets()

    def test_invalid_probabilities_and_incomplete_panel_never_load_targets(self):
        for kind in ("nan", "sum", "negative", "missing", "object", "cropped"):
            with self.subTest(kind=kind):
                arrays = self.panel()
                key = "development-002__probabilities"
                if kind == "nan": arrays[key][0, 0] = np.nan
                elif kind == "sum": arrays[key][0] = .3
                elif kind == "negative": arrays[key][0] = [-1, 2, 0, 0, 0]
                elif kind == "missing": arrays.pop(key)
                elif kind == "object": arrays[key] = arrays[key].astype(object)
                elif kind == "cropped": arrays[key] = arrays[key][1:]
                self.write_panel("EEG_EOG_clock", arrays)
                self.refuse_before_targets()

    def test_duplicate_zip_member_and_compressed_npz_refused(self):
        path = self.submission / "EEG_EOG_clock.npz"
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("class_order.npy", b"duplicate")
        self.refuse_before_targets()
        np.savez_compressed(path, **self.panel())
        self.refuse_before_targets()

    def test_claim_schema_and_duplicate_json_keys_refused_before_targets(self):
        path = self.submission / "claims.json"
        for body in ('{"schema_version":1,"schema_version":1,"candidate_id":"NEURAL-008","reported_contrast":null}',
                     '{"schema_version":true,"candidate_id":"NEURAL-008","reported_contrast":null}',
                     '{"schema_version":1,"candidate_id":"NEURAL-008","reported_contrast":NaN}'):
            path.write_text(body)
            self.refuse_before_targets()

    def test_claim_agreement_is_separate_from_scientific_validity(self):
        zero = {"person_mean_macro_f1_delta": 0, "person_mean_rem_recall_delta": 0,
                "per_person": [{"person_id": c.case_id, "macro_f1_delta": 0, "rem_recall_delta": 0}
                               for c in score.CASES]}
        self.claims["reported_contrast"] = zero
        self.write_claims()
        result = score.assess(self.submission, self.loader)["result"]
        self.assertEqual(result["claim_consistency"]["status"], "consistent")
        self.assertEqual(result["claim_consistency"]["scientific_claim_validity"], "not_assessed")
        zero["person_mean_macro_f1_delta"] = .5
        self.write_claims()
        result = score.assess(self.submission, self.loader)["result"]
        self.assertEqual(result["claim_consistency"]["status"], "inconsistent")
        self.assertEqual(result["claim_consistency"]["max_absolute_numeric_error"], .5)

    def test_frozen_panel_mutation_and_link_rejected(self):
        locks = score.freeze_submission(self.submission)
        path = self.submission / "EEG_EOG_clock.npz"
        self.write_panel("EEG_EOG_clock", self.panel(fixed=0))
        arms = {a: (self.submission / (a + ".npz"), locks[a + ".npz"]) for a in paired_core.ARMS}
        with self.assertRaises(ValueError):
            paired_core.evaluate(arms, self.claims, score.SPEC, self.loader)
        self.assertEqual(self.calls, 0)
        moved = self.root / "elsewhere.npz"
        path.rename(moved)
        path.symlink_to(moved)
        self.refuse_before_targets()

    def test_cli_validation_and_fresh_output(self):
        output = self.root / "report.json"
        argv = ["--submission", str(self.submission), "--validate-only", "--output", str(output)]
        self.assertEqual(score.main(argv), 0)
        report = json.loads(output.read_text())
        self.assertEqual(report["epochs_per_arm"], 5450)
        self.assertEqual(report["private_loader_calls"], 0)
        with self.assertRaises(ValueError):
            score.main(argv)

    def test_target_loader_checks_hash_lineage_and_schema(self):
        root = self.root / "generated-targets"
        root.mkdir()
        expected_manifest = {"generated_software_control": True}
        (root / "manifest.json").write_text(json.dumps(expected_manifest))
        for case in score.CASES:
            np.savez(root / (case.case_id + "_labels.npz"), **self.targets[case.case_id])
        pins = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in root.iterdir()}
        plan = {"private_files": pins, "private_manifest_expected": expected_manifest}
        result = score._load_targets(root, plan)
        self.assertEqual(set(result), set(self.targets))
        plan["private_manifest_expected"] = {"different": True}
        with self.assertRaisesRegex(ValueError, "lineage"):
            score._load_targets(root, plan)
        plan["private_manifest_expected"] = expected_manifest
        (root / "manifest.json").write_text("{}")
        with self.assertRaises(ValueError):
            score._load_targets(root, plan)
        # Production never accepts these fixture pins or the generated target values.
        with self.assertRaises(ValueError):
            score.historical_targets(root)

    def test_target_header_rejects_object_arrays(self):
        stream = io.BytesIO()
        row = dict(self.targets[score.CASES[0].case_id])
        row["stage"] = row["stage"].astype(object)
        np.savez(stream, **row)
        with self.assertRaises(ValueError):
            score.target_headers(stream.getvalue(), score.CASES[0])

    def test_original_source_pins(self):
        adapter_bytes = (ROOT / "neural008_vendor/candidate_adapter.py").read_bytes()
        self.assertEqual(hashlib.sha256(adapter_bytes).hexdigest(),
                         "fc8363b28a86cd1f5083b4cc5d24fb1a5a4abd1d490d9163a305f85f1fbe4d23")
        core = (ROOT / "neural008_vendor/paired_core.py").read_bytes()
        original = core.replace(b"from . import candidate_adapter as adapter", b"import candidate_adapter as adapter")
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         "9f3f738f1cfb1295d290a3c69e9f12583ec2329db28f64f6d8d450229cc40dfe")


if __name__ == "__main__":
    print("Generated software controls: Python", sys.version.split()[0], "NumPy", np.__version__, flush=True)
    unittest.main(verbosity=2)

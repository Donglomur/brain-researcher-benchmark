"""Generated complete-panel controls; no authentic observations or model fitting."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural026_compare", HERE / "compare.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

WRITTEN = 0


def write(path, body):
    global WRITTEN
    path.write_bytes(body)
    WRITTEN += len(body)


def json_body(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def npz_body(**values):
    out = io.BytesIO()
    np.savez_compressed(out, **values)
    return out.getvalue()


class PairedControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        cls.scorer = c.load_scorer()
        cls.api = cls.scorer.backend()
        cls.folders = {mode: cls.root / mode for mode in c.MODES}
        for folder in cls.folders.values():
            folder.mkdir()
        cls.design = {"schema": "neural026_design_v1", "cases": []}
        manifests = {mode: {"schema": cls.scorer.NEW_SCHEMA, "cases": []} for mode in c.MODES}
        cls.targets, cls.references = {}, {}
        for mouse in cls.api.p.MICE:
            for area in cls.api.p.AREAS:
                for fold in range(5):
                    cid = f"{mouse}_{area}_fold{fold}"
                    ids = [i for i in range(1, 21) if (i - 1) % 5 == fold]
                    cls.design["cases"].append({"case_id": cid, "mouse": mouse, "area": area,
                        "fold": fold, "query_id": ids,
                        "train_id": [i for i in range(1, 21) if i not in ids],
                        "matched_counts": {"1": 10, "2": 10}})
                    ids = np.asarray(ids, dtype=np.int64)
                    y = np.broadcast_to(ids[:, None, None], (4, 51, 24)).astype(np.float64)
                    cls.targets[cid] = {"trial_id": ids, "y": y}
                    cls.references[cid] = {"trial_id": ids, "nuisance": y + 3.,
                                           "neural": y + 1., "shifted": y + 2.}
                    for mode, offset in zip(c.MODES, (.5, 1.5, 2.5), strict=True):
                        path = cls.folders[mode] / (cid + ".npz")
                        body = npz_body(trial_id=ids, neural=y + offset)
                        write(path, body)
                        manifests[mode]["cases"].append({"case_id": cid, "file": path.name,
                            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
        for mode, manifest in manifests.items():
            write(cls.folders[mode] / "submission.json", json_body(manifest))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        print("generated_fixture_bytes_written=" + str(WRITTEN))

    def loader(self, cid):
        return self.targets[cid], self.references[cid]

    def replace_first(self, mode):
        folder = self.folders[mode]
        manifest_path = folder / "submission.json"
        manifest_original = manifest_path.read_bytes()
        manifest = json.loads(manifest_original)
        row = manifest["cases"][0]
        path = folder / row["file"]
        original = path.read_bytes()
        target = self.targets[row["case_id"]]
        changed = npz_body(trial_id=target["trial_id"], neural=target["y"] + 7.)
        write(path, changed)
        row.update(bytes=len(changed), sha256=hashlib.sha256(changed).hexdigest())
        write(manifest_path, json_body(manifest))
        def restore():
            write(path, original)
            write(manifest_path, manifest_original)
        return restore

    def test_complete_pairing_and_independent_arithmetic_oracle(self):
        result = c.evaluate(self.folders, self.design, self.loader)
        # Each joint contains each integer1..20 equally often: variance33.25.
        self.assertAlmostEqual(result["grades"]["full"]["primary_value"], 8.75 / 33.25)
        for mode, numerator in (("context_only", 2.), ("training_trial_shift", 6.)):
            contrast = result["full_minus_control"][mode]
            self.assertAlmostEqual(contrast["value"], numerator / 33.25)
            self.assertEqual(len(contrast["biological_effects"]), 10)
            self.assertEqual(len(contrast["per_mouse"]), 5)
            self.assertTrue(all(len(row["full_minus_control_joint_incremental_ev"]) == 24
                                for row in contrast["biological_effects"]))
        self.assertFalse(result["neural_dependence_established"])
        self.assertFalse(result["scientific_qualification"])
        self.assertIsNone(result["binary_pass"])

    def test_default_single_panel_api_remains_identical(self):
        single = self.scorer.evaluate(self.folders["full"], self.design, self.loader)
        paired = c.evaluate(self.folders, self.design, self.loader)
        self.assertEqual(single, paired["grades"]["full"])

    def test_active_preparation_loader_accepts_updated_scorer(self):
        path = HERE.parent / "paired-preparation-v2/prepare.py"
        spec = importlib.util.spec_from_file_location("neural026_paired_prepare", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        api = module.backend()
        self.assertEqual(api.p.case_ids(), self.api.p.case_ids())
        self.assertEqual(len(api.inventory), 10)

    def test_invalid_last_mode_before_any_protected_read(self):
        path = self.folders["training_trial_shift"] / (self.design["cases"][-1]["case_id"] + ".npz")
        saved = path.read_bytes()
        calls = []
        path.unlink()
        try:
            with self.assertRaises(ValueError):
                c.evaluate(self.folders, self.design, lambda cid: calls.append(cid))
            self.assertEqual(calls, [])
        finally:
            write(path, saved)

    def test_expected_commitment_refuses_coherent_replacement(self):
        admitted = self.scorer.admit_submission(self.folders["full"], self.design, self.api)
        restore = self.replace_first("full")
        calls = []
        try:
            with self.assertRaisesRegex(ValueError, "paired complete admission"):
                self.scorer.evaluate(self.folders["full"], self.design, lambda cid: calls.append(cid),
                                     expected_admission=admitted)
            self.assertEqual(calls, [])
        finally:
            restore()

    def test_wrapper_uses_initial_admission_after_all_modes_validate(self):
        original = self.scorer.evaluate
        restores = []
        calls = []
        def replace_then_grade(*args, **kwargs):
            restores.append(self.replace_first("full"))
            return original(*args, **kwargs)
        try:
            with mock.patch.object(c, "load_scorer", return_value=self.scorer), \
                 mock.patch.object(self.scorer, "evaluate", side_effect=replace_then_grade):
                with self.assertRaisesRegex(ValueError, "paired complete admission"):
                    c.evaluate(self.folders, self.design, lambda cid: calls.append(cid))
            self.assertEqual(calls, [])
        finally:
            for restore in reversed(restores):
                restore()

    def test_negative_and_zero_contrasts_are_retained(self):
        folders = {"full": self.folders["training_trial_shift"],
                   "context_only": self.folders["full"],
                   "training_trial_shift": self.folders["training_trial_shift"]}
        result = c.evaluate(folders, self.design, self.loader)
        self.assertAlmostEqual(result["full_minus_control"]["context_only"]["value"], -6. / 33.25)
        self.assertEqual(result["full_minus_control"]["training_trial_shift"]["value"], 0.)

    def test_large_shared_nuisance_error_does_not_erase_paired_difference(self):
        originals = {cid: values["nuisance"] for cid, values in self.references.items()}
        try:
            for cid in self.references:
                self.references[cid]["nuisance"] = self.targets[cid]["y"] + 1e10
            result = c.evaluate(self.folders, self.design, self.loader)
            self.assertEqual(result["grades"]["full"]["primary_value"],
                             result["grades"]["context_only"]["primary_value"])
            self.assertAlmostEqual(result["full_minus_control"]["context_only"]["value"], 2. / 33.25)
        finally:
            for cid, original in originals.items():
                self.references[cid]["nuisance"] = original

    def test_missing_or_extra_condition_refused_without_private_read(self):
        for folders in ({"full": self.folders["full"]}, {**self.folders, "other": self.folders["full"]}):
            calls = []
            with self.assertRaises(ValueError):
                c.evaluate(folders, self.design, lambda cid: calls.append(cid))
            self.assertEqual(calls, [])

    def test_cli_binds_same_private_arrays_and_refuses_changed_target(self):
        global WRITTEN
        private = self.root / "private"
        private.mkdir()
        binding = {"schema": "neural026_private_binding_v1", "cases": {}}
        for cid in self.targets:
            binding["cases"][cid] = {}
            for role, values in (("target", self.targets[cid]), ("reference", self.references[cid])):
                path = private / (cid + "_" + role + ".npz")
                body = npz_body(**values)
                write(path, body)
                binding["cases"][cid][role] = {"file": path.name, "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()}
        design_path, binding_path = self.root / "design.json", self.root / "binding.json"
        write(design_path, json_body(self.design))
        write(binding_path, json_body(binding))
        argv = ["--design", str(design_path), "--design-sha256", hashlib.sha256(design_path.read_bytes()).hexdigest(),
                "--private-root", str(private), "--binding", str(binding_path), "--binding-sha256",
                hashlib.sha256(binding_path.read_bytes()).hexdigest()]
        for mode in c.MODES:
            argv += ["--" + mode.replace("_", "-"), str(self.folders[mode])]
        output = self.root / "grade.json"
        self.assertEqual(c.main([*argv, "--output", str(output)]), 0)
        WRITTEN += output.stat().st_size
        report = json.loads(output.read_text())
        self.assertEqual(report["operator_binding_sha256"], hashlib.sha256(binding_path.read_bytes()).hexdigest())
        path = private / binding["cases"][self.design["cases"][0]["case_id"]]["target"]["file"]
        write(path, path.read_bytes() + b"changed")
        failed = self.root / "refused.json"
        with self.assertRaisesRegex(ValueError, "Same pinned private bytes"):
            c.main([*argv, "--output", str(failed)])
        self.assertFalse(failed.exists())


if __name__ == "__main__":
    unittest.main()

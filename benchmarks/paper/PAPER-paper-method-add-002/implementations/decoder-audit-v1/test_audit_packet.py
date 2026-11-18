"""Generated audit transport/verification controls, never authentic data.

The original scoring packet parser is unchanged and separately tested. Its
already-decoded interface is represented here by a generated in-memory object.
Only the test temporarily lowers the audit feature dimension to three; all511
trials,20x5 folds,eight model slots and20x2 half schedules remain complete.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("slice_audit_packet_test", HERE / "audit_packet.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class GeneratedCore:
    def __init__(self, family, recipe):
        self.manifest_sha256 = "d" * 64
        self.plan = {"task_id": m.b.TASK, "bank_manifest_sha256": "b" * 64,
                     "evaluation_profile_sha256": "e" * 64, "recipe": recipe,
                     "component_routes": {"region_map": "paper_counts_unbound", "target_projection_route": "source_raw_factor",
                                          "subspace_route": "source_default_axes", "preparatory_time_indices": None},
                     "reconstruction_cells": [], "reconstruction_roster_identity": None}
        self.manifest = {"angle_counts": {"straight": 4, "curved": 4}}
        self.arrays = {}
        for model, result in family["single_trial_decoding"].items():
            for reach, row in result["conditions"].items():
                for field in ("prediction", "test_indices"):
                    self.arrays[f"decoding/{model}/{reach}/{field}"] = row[field]
        for reach, result in family["raw_condition_average_control"]["conditions"].items():
            rows = result["rows"]
            self.arrays[f"averaged/{reach}/labels"] = rows[0][0]["condition_labels"]
            for field in ("prediction", "train_indices", "test_indices"):
                self.arrays[f"averaged/{reach}/{field}"] = np.stack([np.stack([row[field] for row in pair]) for pair in rows])

    def get(self, key):
        return self.arrays[key]


def generated_fixture():
    t = np.arange(150, dtype=np.float64)
    x = np.broadcast_to(np.stack((t, t * t, np.ones_like(t)), axis=-1)[:, None, :], (150, 511, 3))
    ids = np.arange(511, dtype=np.float64)
    movement = np.stack((t[:, None] + ids[None, :] / 4, 2 * t[:, None] + ids[None, :] / 8), axis=-1)
    angles = np.resize(np.arange(4, dtype=np.float64), 511)
    recipe = "source_code_ridge1"
    single = m.a._repeated_windowed(x[55:-15], movement[65:-5], movement, recipe=recipe)
    averaged = m.a._condition_average_windowed(x[55:-15], movement[65:-5], angles, recipe=recipe)
    family = {"single_trial_decoding": {model: single for model in m.b.MODELS},
              "raw_condition_average_control": averaged}
    core = GeneratedCore(family, recipe)
    bank = {"manifest_sha256": "b" * 64, "neural": x.transpose(1, 2, 0), "movement": movement, "target_angle": angles}
    representations = {model: x for model in m.b.MODELS}
    pins = {model: m.a.array_digest(value) for model, value in representations.items()}
    return family, core, bank, representations, pins


class AuditTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dimension = mock.patch.object(m, "FEATURES", 3)
        cls.dimension.start()
        cls.family, cls.core, cls.bank, cls.representations, cls.pins = generated_fixture()
        cls.tmp = tempfile.TemporaryDirectory(prefix=".audit-generated-", dir=HERE)
        cls.root = Path(cls.tmp.name)
        cls.receipt = m.write_packet(cls.family, cls.root / "audit", cls.core, cls.pins, maximum_bytes=12 * 1024**2)

    @classmethod
    def tearDownClass(cls):
        print("GENERATED_AUDIT_WRITE_BYTES", cls.receipt["charged_output_bytes"])
        cls.tmp.cleanup()
        cls.dimension.stop()

    def packet(self):
        return m.AuditPacket(self.root / "audit", self.receipt["manifest_sha256"], self.core)

    def overlay(self, key, mutate):
        packet = self.packet()
        original = packet.get
        def replacement(name):
            value = original(name)
            if name == key:
                value = value.copy()
                mutate(value)
            return value
        packet.get = replacement
        return packet

    def test_complete_generated_roundtrip_verifies_all1680_records_without_refitting(self):
        with mock.patch.object(m.a.p, "fit_velocity", side_effect=AssertionError("verification must not fit")):
            result = m.verify_original_linear_readout(self.packet(), self.bank, self.representations)
        self.assertEqual(result["counts"], {"single_fits": 1600, "half_fits": 80, "single_test_occurrences": 81600})
        self.assertFalse(result["fit_execution_authenticated"])
        self.assertFalse(result["scientific_admission"])
        self.assertFalse(result["fitting_reexecuted"])

    def test_core_manifest_and_plan_must_match(self):
        core = copy.copy(self.core)
        core.manifest_sha256 = "c" * 64
        with self.assertRaisesRegex(ValueError, "identity/scope"):
            m.AuditPacket(self.root / "audit", self.receipt["manifest_sha256"], core)
        core.manifest_sha256 = self.core.manifest_sha256
        core.plan = copy.deepcopy(self.core.plan)
        core.plan["recipe"] = "paper_ols0"
        with self.assertRaisesRegex(ValueError, "identity/scope"):
            m.AuditPacket(self.root / "audit", self.receipt["manifest_sha256"], core)

    def test_representation_identity_precedes_equations(self):
        values = dict(self.representations)
        values["raw"] = values["raw"].copy()
        values["raw"][0, 0, 0] += 1
        with self.assertRaisesRegex(ValueError, "representation identity"):
            m.verify_original_linear_readout(self.packet(), self.bank, values)

    def test_changed_coefficient_rejected_by_fit_record(self):
        packet = self.overlay("single/raw/straight/weight", lambda value: value.__setitem__((0, 0, 0, 0), value[0, 0, 0, 0] + .1))
        with self.assertRaisesRegex(ValueError, "fit input/output"):
            m.verify_original_linear_readout(packet, self.bank, self.representations)

    def test_changed_displacement_rejected_without_using_submitted_scalar_scores(self):
        packet = self.overlay("single/raw/straight/displacement", lambda value: value.__setitem__((0, 0, 0, 0, 0), value[0, 0, 0, 0, 0] + .1))
        with self.assertRaisesRegex(ValueError, "single displacement"):
            m.verify_original_linear_readout(packet, self.bank, self.representations)

    def test_changed_neural_half_mean_rejected(self):
        packet = self.overlay("averaged/straight/neural_test_mean", lambda value: value.__setitem__((0, 0, 0, 0, 0), value[0, 0, 0, 0, 0] + .1))
        with self.assertRaisesRegex(ValueError, "neural_test_mean"):
            m.verify_original_linear_readout(packet, self.bank, self.representations)

    def test_held_target_mean_is_not_exported_or_required(self):
        packet = self.packet()
        self.assertFalse(any("movement_test" in key or key.endswith("/target") for key in packet.manifest["files"]))
        family = copy.deepcopy(self.family)
        for result in family["raw_condition_average_control"]["conditions"].values():
            for pair in result["rows"]:
                for row in pair:
                    row.pop("movement_test_mean")
                    row.pop("target")
        arrays, records = m.collect(family, self.core)
        self.assertEqual(set(arrays), set(packet.manifest["files"]))

    def test_payload_replacement_after_admission_rejected(self):
        packet = self.packet()
        key = "single/raw/straight/bias"
        path = packet.root / packet.manifest["files"][key]["file"]
        original = path.read_bytes()
        self.assertLess(len(original), 4096)
        changed = bytearray(original)
        changed[-1] ^= 1
        try:
            path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "content changed"):
                packet.get(key)
        finally:
            path.write_bytes(original)

    def test_total_output_budget_refuses_without_retry(self):
        root = self.root / "budget-refused"
        with self.assertRaisesRegex(ValueError, "output budget"):
            m.write_packet(self.family, root, self.core, self.pins, maximum_bytes=1)
        self.assertTrue(root.is_dir())
        self.assertFalse((root / "MANIFEST.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

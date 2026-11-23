"""Generated factor/readout linkage controls; no real inputs, fitting or files."""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("slice_representation_test", HERE / "representation_audit.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Isolated candidate checks can locate unchanged dependencies in the read-only
# source tree. Installed/repository tests need no environment override.
if "SLICETCA_TEST_AUDIT_PATH" in os.environ:
    m.AUDIT_PATH = Path(os.environ["SLICETCA_TEST_AUDIT_PATH"])


def fixture(q):
    rng = np.random.RandomState(74)
    factors = {"trial_weights": rng.uniform(.1, .4, (12, 511)),
               "trial_slices": rng.uniform(.2, .5, (12, 3, 150)),
               "time_vector": rng.uniform(.1, .6, (1, 150)),
               "preparatory_trial_neuron_slice": rng.uniform(.2, .7, (511, 3))}
    trial = np.einsum("rk,rnt->tkn", factors["trial_weights"], factors["trial_slices"])
    time = np.einsum("t,kn->tkn", factors["time_vector"][0], factors["preparatory_trial_neuron_slice"])
    representations = dict(zip(m.MIXED, (trial, time, trial + time)))
    arrays = {"components/" + key: value for key, value in factors.items()}
    core = SimpleNamespace(manifest_sha256="c" * 64, plan={"generated": True}, get=arrays.__getitem__)
    manifest = {"core_manifest_sha256": core.manifest_sha256, "plan_sha256": q.b.digest(core.plan),
                "representation_pins": {key: q.a.array_digest(value) for key, value in representations.items()}}
    return SimpleNamespace(core=core, manifest=manifest, manifest_sha256="a" * 64), factors, representations


class RepresentationLinkage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = m.original_audit()

    def setUp(self):
        self.patch = mock.patch.object(m, "FEATURES", 3)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.loader = mock.patch.object(m, "original_audit", return_value=self.q)
        self.loader.start()
        self.addCleanup(self.loader.stop)
        self.packet, self.factors, self.representations = fixture(self.q)

    def repin(self, name):
        self.packet.manifest["representation_pins"][name] = self.q.a.array_digest(self.representations[name])

    def test_full_support_and_rank_linkage_preserves_no_admission(self):
        result = m.verify_mixed_representations(self.packet, self.representations)
        self.assertEqual(result["checked_shape"], [150, 511, 3])
        self.assertEqual((result["trial_components"], result["time_components"]), (12, 1))
        self.assertEqual(result["core_manifest_sha256"], self.packet.core.manifest_sha256)
        self.assertEqual(result["audit_manifest_sha256"], self.packet.manifest_sha256)
        for name, factor in self.factors.items():
            self.assertEqual(result["factor_pins"][name], self.q.a.array_digest(factor))
        for flag in ("fitting_reexecuted", "representation_fitting_authenticated",
                     "historical_component_identity_authenticated", "scientific_admission"):
            self.assertIs(result[flag], False)

    def test_public_182_feature_requirement_refuses_reduced_fixture(self):
        with mock.patch.object(m, "FEATURES", 182):
            with self.assertRaisesRegex(ValueError, "shape mismatch: trial_slices"):
                m.verify_mixed_representations(self.packet, self.representations)

    def test_float32_factor_products_match_preserved_producer(self):
        factors = {key: value.astype(np.float32) for key, value in self.factors.items()}
        arrays = {"components/" + key: value for key, value in factors.items()}
        self.packet.core.get = arrays.__getitem__
        native = {"trial": (factors["trial_weights"], factors["trial_slices"]),
                  "neuron": (np.empty((0, 3), np.float32), np.empty((0, 511, 150), np.float32)),
                  "time": (factors["time_vector"], factors["preparatory_trial_neuron_slice"][None])}
        for name, modes in zip(m.MIXED, (("trial",), ("time",), ("trial", "time"))):
            self.representations[name] = self.q.a.p.slice_reconstruction(native, (511, 3, 150), modes=modes).transpose(2, 0, 1)
            self.repin(name)
        result = m.verify_mixed_representations(self.packet, self.representations)
        self.assertEqual(result["factor_pins"]["trial_weights"]["dtype"], "<f4")
        self.assertEqual(result["status"], "consistent_with_supplied_factors")

    def test_full_tensor_cannot_be_substituted_for_trial_only_readout(self):
        self.representations["mixed_trial_only"] = self.representations["mixed_slice12_1"]
        self.repin("mixed_trial_only")
        with self.assertRaisesRegex(ValueError, "reconstruction differs: mixed_trial_only"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_self_consistent_bundle_must_still_follow_supplied_factors(self):
        self.representations["mixed_time_only"] += .5
        self.representations["mixed_slice12_1"] += .5
        for name in ("mixed_time_only", "mixed_slice12_1"):
            self.repin(name)
        np.testing.assert_allclose(self.representations["mixed_slice12_1"],
                                   self.representations["mixed_trial_only"] + self.representations["mixed_time_only"])
        with self.assertRaisesRegex(ValueError, "reconstruction differs: mixed_time_only"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_last_bin_and_trial_outside_decoder_support_are_checked(self):
        self.representations["mixed_slice12_1"][149, 510, 2] += .1
        self.repin("mixed_slice12_1")
        with self.assertRaisesRegex(ValueError, "reconstruction differs: mixed_slice12_1"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_representation_content_pin_precedes_factor_equations(self):
        self.representations["mixed_time_only"][0, 0, 0] += .1
        with self.assertRaisesRegex(ValueError, "representation identity differs"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_exact_factor_rank_and_nonnegative_export_are_required(self):
        original_get = self.packet.core.get
        with mock.patch.object(self.packet.core, "get", side_effect=lambda key: original_get(key)[:11]
                               if key == "components/trial_weights" else original_get(key)):
            with self.assertRaisesRegex(ValueError, "shape mismatch: trial_weights"):
                m.verify_mixed_representations(self.packet, self.representations)
        self.factors["time_vector"][0, 0] = -.1
        with self.assertRaisesRegex(ValueError, "nonnegative exported factors"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_finite_factors_with_unrepresentable_product_fail(self):
        self.factors["time_vector"][:] = 1e308
        self.factors["preparatory_trial_neuron_slice"][:] = 2
        with self.assertRaisesRegex(ValueError, "unrepresentable mixed reconstruction"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_core_plan_and_tensor_roster_cannot_change(self):
        self.packet.core.plan["generated"] = False
        with self.assertRaisesRegex(ValueError, "binding differs"):
            m.verify_mixed_representations(self.packet, self.representations)
        self.packet.core.plan["generated"] = True
        self.representations.pop("mixed_time_only")
        with self.assertRaisesRegex(ValueError, "all three mixed"):
            m.verify_mixed_representations(self.packet, self.representations)

    def test_combined_entrypoint_checks_linkage_before_original_readout(self):
        bank = {"generated": True}
        linear = {"scientific_admission": False, "counts": {"single_fits": 1600, "half_fits": 80}}
        with mock.patch.object(self.q, "verify_original_linear_readout", return_value=linear) as reader:
            result = m.verify_original_linear_result(self.packet, bank, self.representations)
            reader.assert_called_once_with(self.packet, bank, self.representations)
            self.assertEqual(result["linear_readout"], linear)
            self.assertFalse(result["scientific_admission"])
        self.representations["mixed_trial_only"][0, 0, 0] += 1
        self.repin("mixed_trial_only")
        with mock.patch.object(self.q, "verify_original_linear_readout") as reader:
            with self.assertRaisesRegex(ValueError, "reconstruction differs"):
                m.verify_original_linear_result(self.packet, bank, self.representations)
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()

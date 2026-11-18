"""Generated controls for the metadata view, never authentic neural observations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("latent_scope_view", HERE / "scope_view.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def fixtures():
    index = {}
    for animal in M.ANIMALS:
        index[animal] = {
            M.PROFILE: {
                "validation_calibration": {
                    "fit_scope": "training_only",
                    "mean": {"array": {"path": "/must/not/be/read.npy", "sha256": "a" * 64}},
                },
                "valid_for_protected_prediction": False,
            },
            "I_locked_traincal_two_way": {
                "all_calibration_from_development": True,
                "outer_used_for_selection": False,
                "validation_preprocessed": {"array": {"path": "/also/inert.npy"}},
            },
            "common": {
                "training_calibration": {"fit_scope": "training_only"},
                "training_pca_parameters": {"fit_scope": "training_only"},
                "error_common_training_preprocessed": {"array": {"path": "/inert/error.npy"}},
            },
        }
    correction = {
        "schema": "latent_response_additive_effective_calibration_scope/v1",
        "applies_to_exact_population_index": {},
        "corrections": [{
            "field_path": f"{animal}.{M.PROFILE}.validation_calibration.fit_scope",
            "original_value": "training_only",
            "effective_value": M.EFFECTIVE_SCOPE,
            "original_value_is_correct": False,
            "protected_prediction_eligible": False,
        } for animal in M.ANIMALS],
    }
    return index, correction


class ScopeTests(unittest.TestCase):
    def bound(self, index=None, correction=None):
        original, record = fixtures()
        index = original if index is None else index
        correction = record if correction is None else correction
        raw = encoded(index)
        correction["applies_to_exact_population_index"] = {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()
        }
        corr = encoded(correction)
        # Fixture pins only: production has fixed constants and no caller override.
        patcher = mock.patch.multiple(M, INDEX_BYTES=len(raw),
            INDEX_SHA256=hashlib.sha256(raw).hexdigest(), CORRECTION_BYTES=len(corr),
            CORRECTION_SHA256=hashlib.sha256(corr).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)
        return raw, corr

    def test_two_repairs_preserve_every_other_field_and_input(self):
        raw, corr = self.bound()
        old = json.loads(raw)
        result = M.effective_index(raw, corr)
        expected = copy.deepcopy(old)
        for animal in M.ANIMALS:
            expected[animal][M.PROFILE]["validation_calibration"]["fit_scope"] = M.EFFECTIVE_SCOPE
        self.assertEqual(result, expected)
        self.assertEqual(json.loads(raw), old)
        result["ar"]["common"]["training_calibration"]["fit_scope"] = "changed"
        self.assertEqual(json.loads(raw), old)

    def test_bad_index_identity_refused_before_json_decoding(self):
        raw, corr = self.bound()
        with mock.patch.object(M, "_json", side_effect=AssertionError("must not decode")):
            with self.assertRaises(M.ScopeRefusal): M.effective_index(raw[:-1] + b" ", corr)

    def test_bad_correction_identity_refused_before_json_decoding(self):
        raw, corr = self.bound()
        with mock.patch.object(M, "_json", side_effect=AssertionError("must not decode")):
            with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr[:-1] + b" ")

    def test_pins_cannot_be_overridden_by_api(self):
        with self.assertRaises(TypeError):
            M.effective_index(b"{}", b"{}", expected_index_sha256="0" * 64)

    def test_missing_animal_or_duplicate_scope_path_is_refused(self):
        index, correction = fixtures()
        correction["corrections"][1] = copy.deepcopy(correction["corrections"][0])
        raw, corr = self.bound(index, correction)
        with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr)

    def test_unrelated_correction_path_is_refused(self):
        index, correction = fixtures()
        correction["corrections"][0]["field_path"] = "ar.common.training_calibration.fit_scope"
        raw, corr = self.bound(index, correction)
        with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr)

    def test_wrong_old_scope_is_refused(self):
        index, correction = fixtures()
        index["fe"][M.PROFILE]["validation_calibration"]["fit_scope"] = M.EFFECTIVE_SCOPE
        raw, corr = self.bound(index, correction)
        with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr)

    def test_reconstruction_cannot_claim_protected_eligibility(self):
        index, correction = fixtures()
        index["ar"][M.PROFILE]["valid_for_protected_prediction"] = True
        raw, corr = self.bound(index, correction)
        with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr)

    def test_unchanged_I_profile_and_training_scopes_are_checked(self):
        for field in ("I", "training", "pca"):
            with self.subTest(field=field):
                index, correction = fixtures()
                if field == "I": index["ar"]["I_locked_traincal_two_way"]["outer_used_for_selection"] = True
                elif field == "training": index["ar"]["common"]["training_calibration"]["fit_scope"] = "validation"
                else: index["ar"]["common"]["training_pca_parameters"]["fit_scope"] = "validation"
                raw, corr = self.bound(index, correction)
                with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr)

    def test_metadata_paths_are_never_followed(self):
        raw, corr = self.bound()
        with mock.patch.object(Path, "open", side_effect=AssertionError("no file access")):
            out = M.summary(raw, corr)
        self.assertEqual(out["array_payloads_read"], 0)
        self.assertFalse(out["readiness_promoted"])
        self.assertNotIn("/must/", json.dumps(out))

    def test_strict_json_refuses_duplicates_and_nonfinite(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw):
                with self.assertRaises(M.ScopeRefusal): M._json(raw)

    def test_correction_flags_require_boolean_false(self):
        index, correction = fixtures()
        correction["corrections"][0]["protected_prediction_eligible"] = 0
        raw, corr = self.bound(index, correction)
        with self.assertRaises(M.ScopeRefusal): M.effective_index(raw, corr)


if __name__ == "__main__":
    unittest.main()

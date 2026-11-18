"""Generated controls for temporal support; no real Brain Treebank observations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scorer = load("feature_availability_neural016", PACKAGE / "evaluator.py")
fixture = load("bound_nuisance_fixture", PACKAGE.parent / "bound-nuisance-v1" / "test_evaluator.py")


def manifest(protocol):
    rows = []
    for role, names in protocol["recipe"]["nuisance_features"].items():
        rows.extend({"name": name, "role": role, "support_seconds": [0, 0],
                     "available_after_seconds": 0, "definition": "generated available feature",
                     "extractor_sha256": "3" * 64} for name in names)
    rows.extend({"name": name, "role": "linguistic", "support_seconds": [0, 0],
                 "available_after_seconds": 0, "definition": "generated available feature",
                 "extractor_sha256": "4" * 64} for name in protocol["recipe"]["linguistic_features"])
    return {"schema_version": 1, "task_id": "NEURAL-016",
            "protocol_sha256": scorer.bound.base.canonical_hash(protocol),
            "policy": "available_at_row_time", "coverage": "all_declared_fit_and_evaluation_rows",
            "features": rows}


def encoded(value):
    raw = json.dumps(value, allow_nan=False).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def check(protocol, value):
    raw, pin = encoded(value)
    return scorer.validate_availability(protocol, raw, pin)


class FeatureAvailabilityTests(unittest.TestCase):
    def test_available_features_preserve_existing_estimand_and_comparator(self):
        p, t, c, n, npin = fixture.packets()
        raw, pin = encoded(manifest(p))
        old = scorer.bound.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin)
        new = scorer.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin,
                              feature_manifest_bytes=raw, expected_feature_manifest_sha256=pin)
        for key in ("primary_estimate", "summary", "absolute_summary", "claim_score", "operator_nuisance_file_sha256"):
            self.assertEqual(new[key], old[key])
        self.assertFalse(new["admission"]["research_qualified"])

    def test_zero_nominal_lag_does_not_allow_future_word_or_post_onset_feature(self):
        p = fixture.packets()[0]
        # The predecessor accepts the frozen protocol's nonpositive nominal lags.
        scorer.bound.base.validate_protocol(p)
        for upper in (0.18, 0.5):
            m = manifest(p)
            m["features"][0].update(support_seconds=[0, upper], available_after_seconds=upper)
            with self.subTest(upper=upper), self.assertRaisesRegex(scorer.ContractError, "unavailable"):
                check(p, m)

    def test_processing_latency_is_not_ignored(self):
        p = fixture.packets()[0]
        m = manifest(p)
        m["features"][0]["available_after_seconds"] = 0.001
        with self.assertRaisesRegex(scorer.ContractError, "unavailable"):
            check(p, m)

    def test_available_before_latest_input_is_impossible(self):
        p = fixture.packets()[0]
        m = manifest(p)
        m["features"][0].update(support_seconds=[0, 0.5], available_after_seconds=0)
        with self.assertRaisesRegex(scorer.ContractError, "before its latest input"):
            check(p, m)

    def test_explicit_lag_can_make_post_anchor_feature_available(self):
        p = fixture.packets()[0]
        p["recipe"]["feature_lags_seconds"] = [-0.5]
        p["recipe"]["guard_seconds"] = 1
        m = manifest(p)
        for row in m["features"]:
            row.update(support_seconds=[0, 0.5], available_after_seconds=0.5)
        result = check(p, m)
        self.assertEqual(result["effective_support_seconds"], [-0.5, 0.0])
        self.assertEqual(result["latest_availability_relative_to_row_seconds"], 0.0)

    def test_temporal_guard_covers_combined_support_and_lag(self):
        p = fixture.packets()[0]
        p["recipe"]["feature_lags_seconds"] = [-0.5]
        p["recipe"]["guard_seconds"] = 0.5
        m = manifest(p)
        m["features"][0]["support_seconds"] = [-0.2, 0]
        with self.assertRaisesRegex(scorer.ContractError, "temporal guard misses"):
            check(p, m)

    def test_complete_features_roles_and_coverage_required(self):
        p = fixture.packets()[0]
        for change in ("missing", "extra", "duplicate", "role", "coverage"):
            m = manifest(p)
            if change == "missing": m["features"].pop()
            elif change == "extra":
                extra = copy.deepcopy(m["features"][0]); extra["name"] = "undeclared"; m["features"].append(extra)
            elif change == "duplicate": m["features"].append(copy.deepcopy(m["features"][0]))
            elif change == "role": m["features"][0]["role"] = "linguistic"
            else: m["coverage"] = "evaluation_rows_only"
            with self.subTest(change=change), self.assertRaises(scorer.ContractError):
                check(p, m)

    def test_bad_numbers_and_reversed_support_rejected(self):
        p = fixture.packets()[0]
        for support, available in (([1, 0], 0), ([False, 0], 0), ([0, 0], True), ([0, 0], "0"), ([0, 10**1000], 10**1000)):
            m = manifest(p); m["features"][0].update(support_seconds=support, available_after_seconds=available)
            with self.subTest(support=support, available=available), self.assertRaises(scorer.ContractError):
                check(p, m)

    def test_operator_byte_binding_and_protocol_binding(self):
        p = fixture.packets()[0]
        m = manifest(p); raw, pin = encoded(m)
        with self.assertRaisesRegex(scorer.ContractError, "file hash mismatch"):
            scorer.validate_availability(p, raw + b"\n", pin)
        m["protocol_sha256"] = "0" * 64
        with self.assertRaisesRegex(scorer.ContractError, "protocol hash mismatch"):
            check(p, m)

    def test_order_independence_no_mutation(self):
        p = fixture.packets()[0]; m = manifest(p); before = copy.deepcopy((p, m))
        expected = check(p, m)
        self.assertEqual((p, m), before)
        m["features"].reverse()
        actual = check(p, m)
        # Raw-byte pin intentionally changes with serialization order.
        actual.pop("operator_feature_manifest_file_sha256")
        expected.pop("operator_feature_manifest_file_sha256")
        self.assertEqual(actual, expected)

    def test_cli_future_support_rejected_before_private_inputs_and_preserves_output(self):
        p = fixture.packets()[0]; m = manifest(p)
        m["features"][0].update(support_seconds=[0, 0.5], available_after_seconds=0.5)
        raw, pin = encoded(m)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "protocol.json").write_text(json.dumps(p))
            (root / "features.json").write_bytes(raw)
            (root / "score.json").write_text("preserved")
            command = [sys.executable, "-B", str(PACKAGE / "evaluator.py"),
                       "--protocol", str(root / "protocol.json"),
                       "--operator-feature-manifest", str(root / "features.json"),
                       "--expected-feature-manifest-sha256", pin,
                       "--operator-nuisance", str(root / "absent-nuisance.json"),
                       "--expected-nuisance-sha256", "0" * 64,
                       "--candidate", str(root / "absent-candidate.json"),
                       "--private-targets", str(root / "absent-targets.json"),
                       "--output", str(root / "score.json")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unavailable", result.stderr)
            self.assertNotIn("No such file", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual((root / "score.json").read_text(), "preserved")


if __name__ == "__main__":
    unittest.main()

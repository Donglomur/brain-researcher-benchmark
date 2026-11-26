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
from unittest import mock

PACKAGE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scorer = load("feature_availability_neural016", PACKAGE / "evaluator.py")
fixture = load("bound_nuisance_fixture", PACKAGE.parent / "bound-nuisance-v1" / "test_evaluator.py")


def complete_packets():
    """Extend the preserved generated fixture with its missing held-out person.

    The old fixture intentionally remains unchanged: person 3 appears only in
    fit rows there. This current-route fixture evaluates all three declared
    recordings, with person/movie-independent fits and the same numerical oracle.
    """
    protocol, targets, candidate, nuisance_raw, _ = fixture.packets()
    nuisance = json.loads(nuisance_raw)
    evaluation = [row["row_id"] for row in protocol["rows"] if row["participant_id"] == "3"]
    fitting = [row["row_id"] for row in protocol["rows"] if row["participant_id"] == "1"]
    protocol["folds"].append({"fold_id": "fold-3", "fit_row_ids": fitting,
                              "evaluation_row_ids": evaluation})
    for row_id, value, control in zip(evaluation, [-3.0, -1.0, 1.0, 3.0], [-2.0, -2.0, 2.0, 2.0]):
        targets["values"].append({"row_id": row_id, "value": value})
        candidate["predictions"].append({"row_id": row_id, "full": value})
        nuisance["predictions"].append({"row_id": row_id, "nuisance": control})
    common = {"fold_id": "fold-3", "fit_row_ids": fitting,
              "recipe_sha256": scorer.bound.base.canonical_hash(protocol["recipe"])}
    candidate["fit_provenance"].append(dict(common, full_artifact_sha256="2" * 64))
    nuisance["fit_provenance"].append(dict(common, nuisance_artifact_sha256="1" * 64))
    digest = scorer.bound.base.canonical_hash(protocol)
    for packet in (targets, candidate, nuisance):
        packet["protocol_sha256"] = digest
    raw, pin = encoded(nuisance)
    return protocol, targets, candidate, raw, pin


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
        p, t, c, n, npin = complete_packets()
        raw, pin = encoded(manifest(p))
        old = scorer.bound.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin)
        new = scorer.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin,
                              feature_manifest_bytes=raw, expected_feature_manifest_sha256=pin)
        for key in ("primary_estimate", "summary", "absolute_summary", "claim_score", "operator_nuisance_file_sha256"):
            self.assertEqual(new[key], old[key])
        self.assertFalse(new["admission"]["research_qualified"])
        self.assertEqual(new["summary"]["n_participants"], 3)
        self.assertEqual(new["population_accounting"]["included_recordings"], 3)
        self.assertEqual(new["population_accounting"]["evaluation_rows"], len(p["rows"]))
        self.assertAlmostEqual(new["primary_estimate"], 0.2)

    def test_zero_nominal_lag_does_not_allow_future_word_or_post_onset_feature(self):
        p = complete_packets()[0]
        # The predecessor accepts the frozen protocol's nonpositive nominal lags.
        scorer.bound.base.validate_protocol(p)
        for upper in (0.18, 0.5):
            m = manifest(p)
            m["features"][0].update(support_seconds=[0, upper], available_after_seconds=upper)
            with self.subTest(upper=upper), self.assertRaisesRegex(scorer.ContractError, "unavailable"):
                check(p, m)

    def test_processing_latency_is_not_ignored(self):
        p = complete_packets()[0]
        m = manifest(p)
        m["features"][0]["available_after_seconds"] = 0.001
        with self.assertRaisesRegex(scorer.ContractError, "unavailable"):
            check(p, m)

    def test_available_before_latest_input_is_impossible(self):
        p = complete_packets()[0]
        m = manifest(p)
        m["features"][0].update(support_seconds=[0, 0.5], available_after_seconds=0)
        with self.assertRaisesRegex(scorer.ContractError, "before its latest input"):
            check(p, m)

    def test_explicit_lag_can_make_post_anchor_feature_available(self):
        p = complete_packets()[0]
        p["recipe"]["feature_lags_seconds"] = [-0.5]
        p["recipe"]["guard_seconds"] = 1
        m = manifest(p)
        for row in m["features"]:
            row.update(support_seconds=[0, 0.5], available_after_seconds=0.5)
        result = check(p, m)
        self.assertEqual(result["effective_support_seconds"], [-0.5, 0.0])
        self.assertEqual(result["latest_availability_relative_to_row_seconds"], 0.0)

    def test_temporal_guard_covers_combined_support_and_lag(self):
        p = complete_packets()[0]
        p["recipe"]["feature_lags_seconds"] = [-0.5]
        p["recipe"]["guard_seconds"] = 0.5
        m = manifest(p)
        m["features"][0]["support_seconds"] = [-0.2, 0]
        with self.assertRaisesRegex(scorer.ContractError, "temporal guard misses"):
            check(p, m)

    def test_complete_features_roles_and_coverage_required(self):
        p = complete_packets()[0]
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
        p = complete_packets()[0]
        for support, available in (([1, 0], 0), ([False, 0], 0), ([0, 0], True), ([0, 0], "0"), ([0, 10**1000], 10**1000)):
            m = manifest(p); m["features"][0].update(support_seconds=support, available_after_seconds=available)
            with self.subTest(support=support, available=available), self.assertRaises(scorer.ContractError):
                check(p, m)

    def test_operator_byte_binding_and_protocol_binding(self):
        p = complete_packets()[0]
        m = manifest(p); raw, pin = encoded(m)
        with self.assertRaisesRegex(scorer.ContractError, "file hash mismatch"):
            scorer.validate_availability(p, raw + b"\n", pin)
        m["protocol_sha256"] = "0" * 64
        with self.assertRaisesRegex(scorer.ContractError, "protocol hash mismatch"):
            check(p, m)

    def test_order_independence_no_mutation(self):
        p = complete_packets()[0]; m = manifest(p); before = copy.deepcopy((p, m))
        expected = check(p, m)
        self.assertEqual((p, m), before)
        m["features"].reverse()
        actual = check(p, m)
        # Raw-byte pin intentionally changes with serialization order.
        actual.pop("operator_feature_manifest_file_sha256")
        expected.pop("operator_feature_manifest_file_sha256")
        self.assertEqual(actual, expected)

    def test_cli_future_support_rejected_before_private_inputs_and_preserves_output(self):
        p = complete_packets()[0]; m = manifest(p)
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

    def test_fit_only_included_recording_rejected_before_scoring(self):
        p, t, c, n, npin = fixture.packets()
        old = scorer.bound.base.validate_protocol(p)
        self.assertLess(len(old["evaluation_ids"]), len(old["rows"]))
        raw, pin = encoded(manifest(p))
        with mock.patch.object(scorer.bound, "evaluate", side_effect=AssertionError("scoring reached")) as score:
            with self.assertRaisesRegex(scorer.ContractError, "fit-only inclusion"):
                scorer.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin,
                                feature_manifest_bytes=raw, expected_feature_manifest_sha256=pin)
            score.assert_not_called()

    def test_omitted_declared_block_rejected_even_when_used_for_fit(self):
        p = complete_packets()[0]
        original = [row for row in p["rows"] if row["participant_id"] == "3"]
        block = {"block_id": "extra-declared-block", "recording_id": original[0]["recording_id"],
                 "start_seconds": 20.0, "end_seconds": 40.0}
        p["blocks"].append(block)
        extra = [dict(row, row_id=row["row_id"] + "-extra", block_id=block["block_id"],
                      time_seconds=row["time_seconds"] + 20) for row in original]
        p["rows"].extend(extra)
        p["folds"][0]["fit_row_ids"].extend(row["row_id"] for row in extra)
        scorer.bound.base.validate_protocol(p)  # The prior gate accepts fit-only blocks.
        with self.assertRaisesRegex(scorer.ContractError, "fit-only inclusion"):
            check(p, manifest(p))

    def test_omitted_declared_electrode_remains_rejected(self):
        p = complete_packets()[0]
        original = [row for row in p["rows"] if row["participant_id"] == "3"]
        extra = [dict(row, row_id=row["row_id"] + "-electrode", electrode_id="generated_electrode_2")
                 for row in original]
        p["rows"].extend(extra)
        p["folds"][0]["fit_row_ids"].extend(row["row_id"] for row in extra)
        with self.assertRaisesRegex(scorer.ContractError, "every declared row of each held-out block"):
            check(p, manifest(p))

    def test_complete_coverage_preserves_split_and_exactly_once_rejections(self):
        for defect in ("duplicate_evaluation", "fit_overlap"):
            p = complete_packets()[0]
            if defect == "duplicate_evaluation":
                p["folds"].append(dict(p["folds"][0], fold_id="duplicate-held-out-fold"))
                message = "evaluation row appears in multiple folds"
            else:
                p["folds"][0]["fit_row_ids"].extend(p["folds"][0]["evaluation_row_ids"])
                message = "fit/evaluation row overlap"
            with self.subTest(defect=defect), self.assertRaisesRegex(scorer.ContractError, message):
                check(p, manifest(p))

    def test_signed_sse_and_ev_unchanged_on_identical_complete_support(self):
        for value_mode, expected_r2, expected_ev in (("constant", -0.8, -0.8), ("biased", -19.8, 0.2)):
            p, t, c, n, npin = complete_packets()
            for row in c["predictions"]:
                row["full"] = 0 if value_mode == "constant" else row["full"] + 10
            c["claimed_delta_r2"] = expected_r2
            raw, pin = encoded(manifest(p))
            old = scorer.bound.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin)
            new = scorer.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin,
                                  feature_manifest_bytes=raw, expected_feature_manifest_sha256=pin)
            with self.subTest(value_mode=value_mode):
                for key in ("primary_estimate", "blocks", "summary", "absolute_summary", "claim_score",
                            "operator_nuisance_file_sha256", "admission", "full_prediction_statistic"):
                    self.assertEqual(new[key], old[key])
                self.assertAlmostEqual(new["primary_estimate"], expected_r2)
                self.assertAlmostEqual(new["summary"]["estimate"]["delta_explained_variance"], expected_ev)
                self.assertAlmostEqual(new["claim_score"]["absolute_error"], 0)
                self.assertTrue(all(value is False for value in new["admission"].values()))

    def test_cli_fit_only_recording_rejected_before_all_prediction_and_target_reads(self):
        p = fixture.packets()[0]
        raw, pin = encoded(manifest(p))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "protocol.json").write_text(json.dumps(p))
            (root / "features.json").write_bytes(raw)
            (root / "score.json").write_text("preserved")
            command = [sys.executable, "-I", "-B", str(PACKAGE / "evaluator.py"),
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
            self.assertIn("fit-only inclusion", result.stderr)
            self.assertNotIn("No such file", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual((root / "score.json").read_text(), "preserved")

    def test_cli_complete_coverage_scores_all_declared_rows(self):
        p, t, c, n, npin = complete_packets()
        raw, pin = encoded(manifest(p))
        expected = scorer.bound.evaluate(p, t, c, nuisance_bytes=n, expected_nuisance_sha256=npin)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("protocol", p), ("private-targets", t), ("candidate", c)):
                (root / (name + ".json")).write_text(json.dumps(value))
            (root / "features.json").write_bytes(raw)
            (root / "nuisance.json").write_bytes(n)
            command = [sys.executable, "-I", "-B", str(PACKAGE / "evaluator.py"),
                       "--protocol", str(root / "protocol.json"),
                       "--private-targets", str(root / "private-targets.json"),
                       "--candidate", str(root / "candidate.json"),
                       "--operator-nuisance", str(root / "nuisance.json"),
                       "--expected-nuisance-sha256", npin,
                       "--operator-feature-manifest", str(root / "features.json"),
                       "--expected-feature-manifest-sha256", pin,
                       "--output", str(root / "score.json")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            actual = json.loads((root / "score.json").read_text())
            for key in ("primary_estimate", "blocks", "summary", "absolute_summary", "claim_score", "admission"):
                self.assertEqual(actual[key], expected[key])
            self.assertEqual(actual["population_accounting"]["evaluation_rows"], 12)
            self.assertEqual(actual["summary"]["n_participants"], 3)


if __name__ == "__main__":
    unittest.main()

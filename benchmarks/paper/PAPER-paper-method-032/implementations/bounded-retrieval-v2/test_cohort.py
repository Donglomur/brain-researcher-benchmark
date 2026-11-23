"""Generated decision records only; no images, feature arrays, models or labels."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
from statistics import NormalDist, fmean
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cohort_under_test", ROOT / "cohort.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
WRITTEN = 0


def summary(values):
    # Independently express the literal published-scorer population SEM rule.
    mean = sum(values) / len(values)
    sem = (sum((x - mean) ** 2 for x in values) / len(values)) ** .5 / len(values) ** .5
    radius = NormalDist().inv_cdf(.975) * sem
    return {"mean": mean, "draw_values": values, "draw_sem": sem,
            "draw_normal_95_interval": [mean - radius, mean + radius],
            "uncertainty_unit": "repeated retrieval subset; not independent subjects/images"}


def record(subject, hits=150):
    population = [f"generated-{i}" for i in range(1000)]
    # Deliberately cover only300of1000unique identities: source admissibility
    # requires30valid frozen pools, not an invented full-union coverage rule.
    pool = population[:300]
    pools = [pool.copy() for _ in range(30)]
    ref = {"task_id": c.TASK, "contract_sha256": c.CONTRACT_SHA256,
           "code_revision": c.CODE_REVISION, "dataset_revision": c.DATA_REVISION,
           "feature_space": c.FEATURE_SPACE, "subject": subject,
           "image_ids": population, "retrieval_pools": pools,
           "image_features_sha256": "a" * 64, "population_manifest_sha256": "b" * 64,
           "feature_extraction_receipt_sha256": "c" * 64}
    draws = []
    metric_values = {name: [] for name in c.DIRECTIONS}
    for draw_index in range(30):
        directions = {}
        for name, count in (("image_retrieval", hits), ("brain_retrieval", 300 - hits)):
            decisions = [{"query_id": key,
                          "predicted_id": key if i < count else pool[(i + 1) % 300],
                          "correct": i < count} for i, key in enumerate(pool)]
            directions[name] = decisions
            metric_values[name].append(count / 300)
        draws.append({"draw_index_zero_based": draw_index, "candidate_ids": pool.copy(),
                      "directions": directions})
    evidence = {"schema": "mindeye2-retrieval-query-evidence/v1", "image_ids": population.copy(),
                "pool_digest": c.digest(pools), "draws": draws,
                "tie_policy": "reject_maximal_ties", "direction_semantics": dict(c.SEMANTICS),
                "scope": "protected_operator_feature_decisions_not_native_execution_attestation"}
    result = {"task_id": c.TASK, "scope": "bounded_original_population_feature_retrieval",
              "reference_manifest_digest": c.digest(ref), "candidate_manifest_digest": "d" * 64,
              "population_manifest_sha256": ref["population_manifest_sha256"],
              "subject": subject, "n_images": 1000, "pool_digest": c.digest(pools),
              "metrics": {name: summary(values) for name, values in metric_values.items()},
              "scientific_qualification": False, "full_contract_complete": False,
              "native_parity_verified": False, "decision_evidence": evidence,
              "decision_evidence_digest": c.digest(evidence)}
    return {"reference": ref, "result": result}


def repin(row):
    ref, result = row["reference"], row["result"]
    result["reference_manifest_digest"] = c.digest(ref)
    result["decision_evidence_digest"] = c.digest(result["decision_evidence"])


class CohortControls(unittest.TestCase):
    def test_complete_four_subject_macro_and_paired_changes(self):
        baseline = [record(s, k) for s, k in zip(c.SUBJECTS, (0, 75, 150, 300))]
        candidate = [record(s, k) for s, k in zip(c.SUBJECTS, (150, 75, 225, 300))]
        result = c.compare(candidate[::-1], baseline)
        self.assertEqual([r["subject"] for r in result["candidate"]["subjects"]], list(c.SUBJECTS))
        self.assertEqual(result["baseline"]["metrics"]["image_retrieval"]["mean"], .4375)
        self.assertEqual(result["candidate"]["metrics"]["image_retrieval"]["mean"], .625)
        self.assertEqual(result["candidate_minus_baseline"]["image_retrieval"]["mean_difference"], .1875)
        self.assertEqual(result["candidate_minus_baseline"]["brain_retrieval"]["mean_difference"], -.1875)
        self.assertEqual(result["candidate_minus_baseline"]["image_retrieval"]["subject_differences"], [.5, 0., .25, 0.])
        self.assertFalse(result["scientific_improvement_claim_supported"])
        self.assertFalse(result["matched_exposure_or_compute_verified"])
        self.assertFalse(result["candidate"]["native_parity_verified"])
        self.assertFalse(result["candidate"]["full_contract_complete"])
        self.assertNotIn("confidence_interval", result["candidate"]["metrics"]["image_retrieval"])
        self.assertNotIn("decision_evidence", result["candidate"]["subjects"][0])

    def test_paired_reference_mismatch_is_not_hidden_by_same_image_set(self):
        baseline = [record(s) for s in c.SUBJECTS]
        candidate = [record(s) for s in c.SUBJECTS]
        candidate[0]["reference"]["feature_extraction_receipt_sha256"] = "e" * 64
        repin(candidate[0])
        with self.assertRaisesRegex(ValueError, "identical subject-specific references"):
            c.compare(candidate, baseline)

    def test_missing_duplicate_or_changed_subject_population_refused(self):
        rows = [record(s) for s in c.SUBJECTS]
        with self.assertRaisesRegex(ValueError, "all four"):
            c.aggregate(rows[:-1])
        with self.assertRaisesRegex(ValueError, "exactly once"):
            c.aggregate(rows[:-1] + [rows[0]])
        rows[0]["reference"]["image_ids"][-1] = "foreign-unqueried-image"
        rows[0]["result"]["decision_evidence"]["image_ids"][-1] = "foreign-unqueried-image"
        repin(rows[0])
        with self.assertRaisesRegex(ValueError, "same shared1000"):
            c.aggregate(rows)

    def test_correctness_recomputed_even_if_modified_evidence_is_rehashed(self):
        row = record(1)
        decision = row["result"]["decision_evidence"]["draws"][0]["directions"]["image_retrieval"][0]
        decision["correct"] = False
        repin(row)
        with self.assertRaisesRegex(ValueError, "correctness flag"):
            c._subject(row)

    def test_query_order_and_candidate_membership_checked(self):
        row = record(1)
        decisions = row["result"]["decision_evidence"]["draws"][0]["directions"]["image_retrieval"]
        original = dict(decisions[0])
        for change in ({"predicted_id": "generated-999", "correct": False},
                       {"query_id": "generated-1"}, {"correct": 1}):
            decisions[0] = dict(original, **change)
            repin(row)
            with self.assertRaises(ValueError):
                c._subject(row)

    def test_all_draws_both_directions_and_full_query_support_required(self):
        row = record(1)
        evidence = row["result"]["decision_evidence"]
        removed = evidence["draws"].pop(); repin(row)
        with self.assertRaisesRegex(ValueError, "30 query"):
            c._subject(row)
        evidence["draws"].append(removed)
        removed_direction = evidence["draws"][0]["directions"].pop("brain_retrieval"); repin(row)
        with self.assertRaisesRegex(ValueError, "both physical"):
            c._subject(row)
        evidence["draws"][0]["directions"]["brain_retrieval"] = removed_direction[:-1]; repin(row)
        with self.assertRaisesRegex(ValueError, "300 query"):
            c._subject(row)

    def test_source_pins_evidence_digest_and_scope_flags_checked(self):
        row = record(1)
        for key, invalid in (("reference_manifest_digest", "0" * 64),
                             ("decision_evidence_digest", "0" * 64),
                             ("pool_digest", "0" * 64), ("scientific_qualification", True),
                             ("native_parity_verified", True), ("full_contract_complete", True),
                             ("subject", True), ("n_images", 999)):
            original = row["result"][key]; row["result"][key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                c._subject(row)
            row["result"][key] = original

    def test_summary_corruption_refused_with_only_roundoff_tolerance(self):
        row = record(1, 1)
        metric = row["result"]["metrics"]["image_retrieval"]
        original = metric["mean"]
        metric["mean"] = math.nextafter(original, math.inf)
        c._subject(row)
        metric["mean"] = original + 1e-8
        with self.assertRaisesRegex(ValueError, "numerical summary"):
            c._subject(row)
        metric["mean"] = original
        metric["draw_values"][0] = 2 / 300
        with self.assertRaisesRegex(ValueError, "draw score"):
            c._subject(row)
        metric["draw_values"][0] = 1 / 300
        metric["draw_sem"] = .01
        with self.assertRaisesRegex(ValueError, "draw SEM"):
            c._subject(row)

    def test_retrieval_direction_correction_and_tie_semantics_cannot_be_relabeled(self):
        row = record(1)
        evidence = row["result"]["decision_evidence"]
        for key, value in (("direction_semantics", {"image_retrieval": "image_query_to_brain_candidates",
                                                   "brain_retrieval": "brain_query_to_image_candidates"}),
                           ("tie_policy", "first_max")):
            old = evidence[key]; evidence[key] = value; repin(row)
            with self.assertRaisesRegex(ValueError, "direction, tie or scope"):
                c._subject(row)
            evidence[key] = old; repin(row)

    def write(self, path, raw):
        global WRITTEN
        path.write_bytes(raw); WRITTEN += len(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_cli_pins_shared_input_budget_and_complete_pair_options(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-cohort-") as temp:
            path = Path(temp) / "empty.json"
            raw = json.dumps({"schema": c.INPUT_SCHEMA, "subjects": []}).encode()
            pin = self.write(path, raw)
            common = ["--candidate", str(path), "--candidate-sha256", pin,
                      "--max-input-bytes", str(2 * len(raw) - 1)]
            with mock.patch.object(c, "compare", side_effect=AssertionError("must refuse before comparing")):
                with self.assertRaisesRegex(ValueError, "byte allowance"):
                    c.main(common + ["--baseline", str(path), "--baseline-sha256", pin])
            with self.assertRaisesRegex(ValueError, "supplied together"):
                c.main(common + ["--baseline", str(path)])
            with self.assertRaisesRegex(ValueError, "SHA256/size mismatch"):
                c.load(path, "0" * 64, len(raw))
            capture = io.StringIO()
            with mock.patch.object(c, "aggregate", return_value={"scientific_qualification": False}), contextlib.redirect_stdout(capture):
                c.main(common)
            output = json.loads(capture.getvalue())
            self.assertEqual(output["input_read_bytes"], len(raw))
            self.assertEqual(output["candidate_input_sha256"], pin)

    def test_json_duplicate_and_nonfinite_values_refused(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-cohort-") as temp:
            path = Path(temp) / "bad.json"
            for raw in (b'{"schema":"a","schema":"b","subjects":[]}',
                        b'{"schema":"a","subjects":NaN}'):
                pin = self.write(path, raw)
                with self.assertRaises(ValueError):
                    c.load(path, pin, len(raw))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(CohortControls))
    print(json.dumps({"generated_only": True, "tests": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "generated_file_write_bytes": WRITTEN}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)

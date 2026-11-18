"""Generated receipt controls, not original biological observations or runs."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


support = load("split_support", PACKAGE / "support.py")
old = load("existing_score_fixture", PACKAGE.parent / "figure5i-score-v1" / "tests" / "test_score.py")


def fixture():
    reference, _ = old.fixture()
    receipt = {
        "schema": "figure5i-original-split-support/v1", "task_id": support.TASK_ID,
        "source_revision": support.SOURCE_REVISION, "realization": "historical_original",
        "cohort_receipt_sha256": reference["cohort_receipt_sha256"],
        "preprocessing_receipt_sha256": reference["preprocessing_receipt_sha256"],
        "realization_evidence": {role: "a" * 64 for role in support.EVIDENCE_ROLES},
        "sessions": [],
    }
    for session in reference["sessions"]:
        row = copy.deepcopy(session)
        row["folds"] = [
            {"repeat": f["repeat"], "test_observation_ids": list(f["test_observation_ids"]),
             "real_train_observation_ids": list(f["train_observation_ids"]),
             "spike_shuffle_train_observation_ids": list(reversed(f["train_observation_ids"]))}
            for f in session["folds"]
        ]
        receipt["sessions"].append(row)
    return reference, receipt


def bind(reference, receipt):
    digest = support.support_digest(receipt)
    reference["split_receipt_sha256"] = digest
    return digest


class SupportTests(unittest.TestCase):
    def test_complete_panel_and_honest_scope(self):
        reference, receipt = fixture()
        result = support.audit_support(reference, receipt, bind(reference, receipt))
        self.assertEqual(result["sessions"], 61)
        self.assertEqual(result["folds"], 610)
        self.assertEqual(result["test_rows"], 61 * 21)
        self.assertEqual(result["spike_shuffle_training_rows"], 61 * 10 * 18)
        self.assertEqual(result["folds_with_different_training_order_or_membership"], 610)
        self.assertFalse(result["scientific_admission"])
        self.assertEqual(result["paper_improvement"], "not_assessed")

    def test_independent_shuffle_draws_may_coincide(self):
        reference, receipt = fixture()
        for session in receipt["sessions"]:
            for fold in session["folds"]:
                fold["spike_shuffle_train_observation_ids"] = fold["real_train_observation_ids"].copy()
        result = support.audit_support(reference, receipt, bind(reference, receipt))
        self.assertEqual(result["folds_with_different_training_order_or_membership"], 0)

    def test_external_admission_and_reference_commitment_both_required(self):
        reference, receipt = fixture()
        admitted = bind(reference, receipt)
        with self.assertRaisesRegex(ValueError, "externally admitted"):
            support.audit_support(reference, receipt, "0" * 64)
        reference["split_receipt_sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "does not bind"):
            support.audit_support(reference, receipt, admitted)

    def test_changed_receipt_cannot_reuse_commitment(self):
        reference, receipt = fixture()
        admitted = bind(reference, receipt)
        receipt["sessions"][0]["folds"][0]["spike_shuffle_train_observation_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "externally admitted"):
            support.audit_support(reference, receipt, admitted)

    def test_real_membership_and_order_are_bound(self):
        for field in ("real_train_observation_ids", "test_observation_ids"):
            reference, receipt = fixture()
            receipt["sessions"][0]["folds"][0][field].reverse()
            with self.subTest(field=field), self.assertRaises(ValueError):
                support.audit_support(reference, receipt, bind(reference, receipt))

    def test_shuffle_leakage_unknown_duplicate_and_size_rejected(self):
        mutations = [
            lambda f: f["spike_shuffle_train_observation_ids"].__setitem__(0, f["test_observation_ids"][0]),
            lambda f: f["spike_shuffle_train_observation_ids"].__setitem__(0, "unknown"),
            lambda f: f["spike_shuffle_train_observation_ids"].__setitem__(0, f["spike_shuffle_train_observation_ids"][1]),
            lambda f: f["spike_shuffle_train_observation_ids"].pop(),
        ]
        for mutate in mutations:
            reference, receipt = fixture()
            mutate(receipt["sessions"][0]["folds"][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                support.audit_support(reference, receipt, bind(reference, receipt))

    def test_complete_sessions_and_folds(self):
        mutations = [
            lambda r: r["sessions"].pop(),
            lambda r: r["sessions"].__setitem__(1, copy.deepcopy(r["sessions"][0])),
            lambda r: r["sessions"][0]["folds"].pop(),
            lambda r: r["sessions"][0]["folds"][0].update(repeat=True),
            lambda r: r["sessions"][0]["folds"][1].update(repeat=0),
            lambda r: r["sessions"][0].update(mouse_id="invented"),
        ]
        for mutate in mutations:
            reference, receipt = fixture()
            mutate(receipt)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                support.audit_support(reference, receipt, bind(reference, receipt))

    def test_source_cells_order_downsampling_and_age_remain_exact(self):
        mutations = [
            lambda s: s["spatial_cell_ids"].reverse(),
            lambda s: s["downsampled_observation_ids"].reverse(),
            lambda s: s.update(age_group="aged"),
            lambda s: s.update(optimal_k=2.0),
            lambda s: s.update(source_onemap=0),
        ]
        for mutate in mutations:
            reference, receipt = fixture()
            mutate(receipt["sessions"][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                support.audit_support(reference, receipt, bind(reference, receipt))

    def test_missing_realization_evidence_and_rerun_kind_rejected(self):
        mutations = [
            lambda r: r["realization_evidence"].pop("original_spike_shuffle_training"),
            lambda r: r["realization_evidence"].update(original_downsampling="not_a_digest"),
            lambda r: r.update(realization="new_seed_rerun"),
            lambda r: r.update(source_revision="unversioned"),
            lambda r: r.update(task_id="another-task"),
            lambda r: r.update(cohort_receipt_sha256="b" * 64),
        ]
        for mutate in mutations:
            reference, receipt = fixture()
            mutate(receipt)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                support.audit_support(reference, receipt, bind(reference, receipt))

    def test_unknown_target_field_not_silently_ignored(self):
        reference, receipt = fixture()
        receipt["sessions"][0]["folds"][0]["target_radians"] = [0.0, 0.0, 0.0]
        with self.assertRaisesRegex(ValueError, "exact declared fields"):
            support.audit_support(reference, receipt, bind(reference, receipt))

    def test_session_and_fold_list_order_is_not_identity(self):
        reference, receipt = fixture()
        receipt["sessions"].reverse()
        for session in receipt["sessions"]:
            session["folds"].reverse()
        result = support.audit_support(reference, receipt, bind(reference, receipt))
        self.assertEqual(result["folds"], 610)

    def test_modified_scorer_is_rejected_before_execution(self):
        reference, receipt = fixture()
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "score.py"
            marker = Path(temp) / "executed"
            fake.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n")
            with self.assertRaisesRegex(ValueError, "dependency differs"):
                support.audit_support(reference, receipt, bind(reference, receipt), scorer_path=fake)
            self.assertFalse(marker.exists())

    def test_canonical_digest_rejects_non_json_or_nonfinite(self):
        for value in ({1: "bad key"}, {"a": (1, 2)}, {"a": float("nan")}, {"a": {1, 2}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                support.support_digest(value)


if __name__ == "__main__":
    unittest.main()

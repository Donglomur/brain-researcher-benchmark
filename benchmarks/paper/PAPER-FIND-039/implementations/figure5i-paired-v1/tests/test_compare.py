"""Generated complete-panel controls; no empirical data or model execution."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("FIGURE5I_COMPONENTS_ROOT", str(PACKAGE.parent)))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paired = load("paired_comparison", PACKAGE / "compare.py")
old = load("support_fixture", ROOT / "figure5i-support-v1/tests/test_support.py")


def fixture():
    reference, support = old.fixture()
    admitted = old.bind(reference, support)
    _, author = old.old.fixture()
    author["reference_sha256"] = old.old.score.reference_digest(reference)
    candidates = {condition: {outcome: copy.deepcopy(author) for outcome in paired.OUTCOMES}
                  for condition in paired.CONDITIONS}
    return reference, support, admitted, candidates, author, copy.deepcopy(author)


def run(values):
    return paired.compare_conditions(*values, components_root=ROOT)


def angles(packet, value, age=None, first_fold_only=False):
    for session in packet["sessions"]:
        if age is not None and not session["mouse_id"].startswith(age):
            continue
        for fold in session["folds"][:1] if first_fold_only else session["folds"]:
            fold["predicted_radians"] = [value] * len(fold["predicted_radians"])


class ComparisonTests(unittest.TestCase):
    def test_all_four_packets_have_full_session_fold_and_companion_results(self):
        result = run(fixture())
        for condition in paired.CONDITIONS:
            for outcome in paired.OUTCOMES:
                report = result["condition_reports"][condition][outcome]
                self.assertEqual(len(report["sessions"]), 61)
                self.assertEqual(report["age_strata"]["young"]["n_sessions"], 34)
                self.assertEqual(report["age_strata"]["aged"]["n_sessions"], 27)
                for row in report["sessions"]:
                    self.assertEqual(set(row["arms"]), {"candidate", "author", "shuffle"})
                    self.assertTrue(all(len(arm["fold_scores"]) == 10 for arm in row["arms"].values()))
        self.assertEqual(result["support_audit"]["folds"], 610)
        self.assertFalse(result["interpretation"]["scientific_admission"])
        self.assertEqual(result["interpretation"]["paper_reproduction"], "not_assessed")
        self.assertEqual(result["interpretation"]["paper_improvement"], "not_assessed")

    def test_independent_outcomes_and_ages_preserve_opposite_effects(self):
        values = fixture()
        candidates = values[3]
        angles(candidates["paper_data"]["reproduction"], math.pi, "young")
        angles(candidates["paper_data_author_code"]["reproduction"], math.pi, "aged")
        angles(candidates["paper_data_author_code"]["improvement"], math.pi, "young")
        result = run(values)["author_code_minus_paper_data"]
        self.assertEqual(result["reproduction"]["age_strata"]["young"]["mean_session_difference"], 2)
        self.assertEqual(result["reproduction"]["age_strata"]["aged"]["mean_session_difference"], -2)
        self.assertEqual(result["improvement"]["age_strata"]["young"]["mean_session_difference"], -2)
        self.assertEqual(result["improvement"]["age_strata"]["aged"]["mean_session_difference"], 0)
        self.assertNotIn("pooled", result["reproduction"])

    def test_unequal_folds_keep_source_weighting_in_paired_contrast(self):
        values = fixture()
        angles(values[3]["paper_data_author_code"]["improvement"], math.pi, first_fold_only=True)
        report = run(values)["author_code_minus_paper_data"]["improvement"]
        self.assertAlmostEqual(report["age_strata"]["young"]["mean_session_difference"], -.2)
        self.assertEqual(report["sessions"][0]["fold_differences"], [-2] + [0] * 9)
        self.assertNotAlmostEqual(report["sessions"][0]["session_difference"], -6 / 21)

    def test_each_condition_outcome_must_be_complete(self):
        for condition in paired.CONDITIONS:
            for outcome in paired.OUTCOMES:
                values = fixture()
                values[3][condition][outcome]["sessions"].pop()
                with self.subTest(condition=condition, outcome=outcome), self.assertRaises(ValueError):
                    run(values)

    def test_missing_extra_or_aliased_slots_cannot_be_silently_substituted(self):
        for level, key in (("condition", "paper_data"), ("outcome", "reproduction")):
            values = fixture()
            mapping = values[3] if level == "condition" else values[3]["paper_data"]
            mapping["unexpected"] = mapping.pop(key)
            with self.subTest(level=level), self.assertRaisesRegex(ValueError, "exact declared"):
                run(values)

    def test_same_reference_is_required_in_every_slot(self):
        for condition in paired.CONDITIONS:
            for outcome in paired.OUTCOMES:
                values = fixture()
                values[3][condition][outcome]["reference_sha256"] = "0" * 64
                with self.subTest(condition=condition, outcome=outcome), self.assertRaisesRegex(ValueError, "digest"):
                    run(values)

    def test_admission_cannot_be_replaced_by_bundle_support_hash(self):
        values = list(fixture())
        values[2] = "0" * 64
        with self.assertRaisesRegex(ValueError, "externally admitted"):
            run(values)
        values = fixture()
        values[1]["sessions"][0]["folds"][0]["spike_shuffle_train_observation_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "externally admitted"):
            run(values)

    def test_even_recommitted_shuffle_leakage_is_rejected(self):
        values = list(fixture())
        fold = values[1]["sessions"][0]["folds"][0]
        fold["spike_shuffle_train_observation_ids"][0] = fold["test_observation_ids"][0]
        values[2] = old.bind(values[0], values[1])
        with self.assertRaisesRegex(ValueError, "held-out"):
            run(values)

    def test_both_shared_companions_are_mandatory(self):
        for index in (4, 5):
            values = fixture()
            values[index]["sessions"].pop()
            with self.subTest(index=index), self.assertRaises(ValueError):
                run(values)

    def test_shuffle_never_changes_real_label_condition_contrast(self):
        values = fixture()
        before = run(values)
        angles(values[5], math.pi)
        after = run(values)
        self.assertEqual(before["author_code_minus_paper_data"], after["author_code_minus_paper_data"])
        self.assertNotEqual(before["shuffle_packet_sha256"], after["shuffle_packet_sha256"])
        self.assertEqual(after["condition_reports"]["paper_data"]["improvement"]["age_strata"]["young"]["session_mean"]["shuffle"], -1)

    def test_input_order_does_not_change_numeric_pairing(self):
        values = fixture()
        angles(values[3]["paper_data_author_code"]["reproduction"], math.pi, "young")
        expected = run(values)
        packet = values[3]["paper_data_author_code"]["reproduction"]
        packet["sessions"].reverse()
        for session in packet["sessions"]:
            session["folds"].reverse()
        actual = run(values)
        self.assertEqual(expected["author_code_minus_paper_data"], actual["author_code_minus_paper_data"])
        self.assertEqual(expected["condition_reports"], actual["condition_reports"])

    def test_changed_component_is_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "figure5i-score-v1/score.py"
            target.parent.mkdir()
            marker = root / "executed"
            target.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n")
            with self.assertRaisesRegex(ValueError, "pinned component differs"):
                paired.compare_conditions(*fixture(), components_root=root)
            self.assertFalse(marker.exists())

    def test_operator_cli_uses_external_commitment_and_writes_complete_report(self):
        reference, support, admitted, candidates, author, shuffle = fixture()
        bundle = {"schema": "figure5i-paired-input/v1", "task_id": paired.TASK,
                  "reference": reference, "support": support, "candidates": candidates,
                  "author": author, "shuffle": shuffle}
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "bundle.json", Path(temp) / "report.json"
            input_bytes = source.write_text(json.dumps(bundle))
            paired.main([str(source), str(output), "--admitted-support-sha256", admitted,
                         "--components-root", str(ROOT)])
            report = json.loads(output.read_text())
            self.assertEqual(set(report["condition_reports"]), set(paired.CONDITIONS))
            self.assertEqual(report["support_audit"]["support_sha256"], admitted)
            # Expose generated disk writes for the enclosing wave's cost ledger.
            print(f"generated_cli_bytes_written={input_bytes + output.stat().st_size}")
            source.write_text('{"schema": 1, "schema": 2}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON"):
                paired.main([str(source), str(output), "--admitted-support-sha256", admitted])


if __name__ == "__main__":
    unittest.main()

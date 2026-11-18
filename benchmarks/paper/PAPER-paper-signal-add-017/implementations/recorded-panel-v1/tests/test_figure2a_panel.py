"""Generated complete-support engineering checks; no biological data or fitting."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "figure2a_panel.py"
spec = importlib.util.spec_from_file_location("figure2a_panel", path)
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


def fixture(condition="MI"):
    # Independent complete21-person x2condition x8run x10-per-class layout.
    manifest = {"schema": "finger017-recorded-panel-assessment/v1", "condition": condition,
                "source_receipt_sha256": "a" * 64,
                "recorded_control_receipt_sha256": "b" * 64, "runs": []}
    outputs, recorded = {}, {}
    for person in range(1, 22):
        subject = f"S{person:02d}"
        for nc, labels in ((2, (1, 4)), (3, (1, 2, 4))):
            for number in range(1, 9):
                kind = {"MI": "Imagery", "ME": "Movement"}[condition]
                folder = f"Online{kind}_Sess02_{nc}class_Finetune"
                member = f"{subject}/{folder}/{subject}_{folder}_R{number:02d}.mat"
                run = {"subject": subject, "nclass": nc, "run": number, "member": member,
                       "source_sha256": hashlib.sha256(member.encode()).hexdigest(), "trials": []}
                for index, label in enumerate(labels * 10):
                    tid = f"{member}#trial{index:04d}"
                    run["trials"].append({"id": tid, "target": label,
                                          "start_sample_zero_based": index * 3072,
                                          "length_samples": 1024, "recorded_prediction": label})
                    outputs[tid + "#sample00000"] = label
                    recorded[tid] = label
                manifest["runs"].append(run)
    predictions = {"schema": "finger017-recorded-panel-predictions/v1",
                   "assessment_sha256": panel.digest(manifest), "models": {}}
    for number, model in enumerate(("S1-B", "S1-F", "S2-B"), 1):
        predictions["models"][model] = {"role": "replayed_decoder",
                                         "model_artifact_sha256": str(number) * 64,
                                         "window_predictions": dict(outputs)}
    predictions["models"]["S2-F"] = {"role": "recorded_online_control",
                                       "recorded_control_receipt_sha256": "b" * 64,
                                       "trial_predictions": recorded}
    return manifest, predictions


class CompletePanelTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.predictions = fixture()
        self.frozen = panel.digest(self.manifest)

    def evaluate(self):
        return panel.evaluate_panel(self.manifest, self.predictions,
                                    expected_assessment_sha256=self.frozen)

    def test_all_model_cells_and_trial_denominators(self):
        result = self.evaluate()
        self.assertEqual(result["source_trial_count"], 8400)
        self.assertEqual(len(result["cells"]), 168)
        self.assertEqual(len(result["summaries"]), 8)
        self.assertEqual({c["trials"] for c in result["cells"] if c["nclass"] == 2}, {160})
        self.assertEqual({c["trials"] for c in result["cells"] if c["nclass"] == 3}, {240})
        self.assertTrue(all(c["accuracy"] == 1 for c in result["cells"]))
        self.assertIsNone(result["paper_win"])
        self.assertFalse(result["readiness_promoted"])

    def test_paired_single_error_retains_every_cell_without_victory(self):
        candidate = copy.deepcopy(self.predictions)
        wid = next(iter(self.predictions["models"]["S1-B"]["window_predictions"]))
        self.predictions["models"]["S1-B"]["window_predictions"][wid] = 4
        result = panel.compare_complete_panels(self.manifest, self.predictions, candidate,
                                               expected_assessment_sha256=self.frozen)
        changed = [c for c in result["paired_replay_cells"] if c["candidate_minus_author"] != 0]
        self.assertEqual(len(result["paired_replay_cells"]), 126)
        self.assertEqual(len(changed), 1)
        self.assertAlmostEqual(changed[0]["candidate_minus_author"], 1 / 160)
        self.assertEqual((changed[0]["subject"], changed[0]["nclass"], changed[0]["model"]),
                         ("S01", 2, "S1-B"))
        self.assertIsNone(result["paper_win"])

    def test_missing_original_run_is_not_subset_scored(self):
        self.manifest["runs"].pop()
        self.frozen = panel.digest(self.manifest)
        with self.assertRaisesRegex(ValueError, "all21"):
            self.evaluate()

    def test_changed_frozen_target_rejected_before_scoring(self):
        self.manifest["runs"][0]["trials"][0]["target"] = 4
        with self.assertRaisesRegex(ValueError, "frozen pin"):
            self.evaluate()

    def test_repeated_source_file_cannot_fill_missing_run_role(self):
        self.manifest["runs"][1]["source_sha256"] = self.manifest["runs"][0]["source_sha256"]
        self.frozen = panel.digest(self.manifest)
        with self.assertRaisesRegex(ValueError, "source bytes reused"):
            self.evaluate()

    def test_same_subject_changed_window_support_is_rejected(self):
        windows = self.predictions["models"]["S1-F"]["window_predictions"]
        old = next(iter(windows))
        windows[old + "-changed"] = windows.pop(old)
        with self.assertRaisesRegex(ValueError, "exact common assessment windows"):
            self.evaluate()

    def test_recorded_control_cannot_be_candidate_replay(self):
        self.predictions["models"]["S2-F"]["role"] = "replayed_decoder"
        with self.assertRaisesRegex(ValueError, "recorded control"):
            self.evaluate()

    def test_recorded_control_prediction_cannot_change(self):
        labels = self.predictions["models"]["S2-F"]["trial_predictions"]
        labels[next(iter(labels))] = 4
        with self.assertRaisesRegex(ValueError, "recorded online output changed"):
            self.evaluate()

    def extend_first_trial(self, length, labels):
        trial = self.manifest["runs"][0]["trials"][0]
        trial["length_samples"] = length
        for model in ("S1-B", "S1-F", "S2-B"):
            for offset, label in zip(range(0, length - 1024 + 1, 128), labels):
                self.predictions["models"][model]["window_predictions"][
                    trial["id"] + f"#sample{offset:05d}"] = label
        self.frozen = panel.digest(self.manifest)
        self.predictions["assessment_sha256"] = self.frozen

    def test_unresolved_trial_vote_tie_fails_instead_of_lowest_class(self):
        self.extend_first_trial(1152, [1, 4])
        with self.assertRaisesRegex(ValueError, "unresolved source trial-vote tie"):
            self.evaluate()

    def test_majority_uses_every_window_not_first_prediction(self):
        self.extend_first_trial(1280, [1, 4, 4])
        result = self.evaluate()
        cell = next(c for c in result["cells"] if (c["subject"], c["nclass"], c["model"])
                    == ("S01", 2, "S1-B"))
        self.assertEqual(cell["correct_trials"], 159)
        self.assertEqual(cell["trials"], 160)

    def test_condition_cannot_change_under_implicit_mi_route(self):
        self.manifest["condition"] = "ME"
        self.frozen = panel.digest(self.manifest)
        with self.assertRaisesRegex(ValueError, "condition/source route mismatch"):
            self.evaluate()

    def test_missing_model_and_boolean_class_are_rejected(self):
        self.predictions["models"].pop("S2-B")
        with self.assertRaisesRegex(ValueError, "complete source model panel"):
            self.evaluate()
        self.manifest, self.predictions = fixture()
        windows = self.predictions["models"]["S1-B"]["window_predictions"]
        windows[next(iter(windows))] = True
        with self.assertRaisesRegex(ValueError, "invalid hard-window class"):
            self.evaluate()


    def test_explicit_me_s7a_preserves_complete_own_source_support(self):
        manifest, predictions = fixture("ME")
        result = panel.evaluate_panel(manifest, predictions,
                                      expected_assessment_sha256=panel.digest(manifest),
                                      expected_condition="ME")
        self.assertEqual((result["condition"], result["panel"]), ("ME", "S7A"))
        self.assertEqual(result["source_trial_count"], 8400)
        self.assertEqual(len(result["cells"]), 168)

    def test_two_condition_wrapper_does_not_pool_or_omit_me(self):
        me, me_predictions = fixture("ME")
        result = panel.compare_mi_me(
            {"MI": self.manifest, "ME": me},
            {"MI": self.predictions, "ME": me_predictions},
            {"MI": self.predictions, "ME": me_predictions},
            expected_assessment_sha256s={"MI": self.frozen, "ME": panel.digest(me)})
        self.assertEqual(set(result["panels"]), {"MI", "ME"})
        self.assertEqual([len(result["panels"][c]["paired_replay_cells"]) for c in ("MI", "ME")],
                         [126, 126])
        self.assertIsNone(result["paper_win"])
        with self.assertRaisesRegex(ValueError, "exact fields"):
            panel.compare_mi_me({"MI": self.manifest}, {}, {}, expected_assessment_sha256s={})

    def test_me_manifest_cannot_relabel_imagery_source_members(self):
        self.manifest["condition"] = "ME"
        with self.assertRaisesRegex(ValueError, "wrong source assessment member"):
            panel.validate_assessment(self.manifest, expected_sha256=panel.digest(self.manifest),
                                      expected_condition="ME")

    def test_accuracy_units_and_canonical_percent_boundary(self):
        me, me_predictions = fixture("ME")
        author = copy.deepcopy(self.predictions)
        wid = next(iter(author["models"]["S1-B"]["window_predictions"]))
        author["models"]["S1-B"]["window_predictions"][wid] = 4
        report = panel.compare_mi_me(
            {"MI": self.manifest, "ME": me},
            {"MI": author, "ME": me_predictions},
            {"MI": self.predictions, "ME": me_predictions},
            expected_assessment_sha256s={"MI": self.frozen, "ME": panel.digest(me)})
        comparison = report["panels"]["MI"]
        for obj in (report, comparison, comparison["author"], comparison["candidate"]):
            self.assertEqual(obj["units"]["accuracy"], "fraction_correct_trials")
            self.assertFalse(obj["units"]["conversion_applied_to_output"])
            self.assertEqual(obj["units"]["canonical_accuracy_binding"]["units"], "percent correct trials")
            self.assertEqual(obj["units"]["canonical_difference_binding"]["units"], "percentage_points")
        first_cell = comparison["author"]["cells"][0]
        self.assertEqual(first_cell["accuracy"], 159 / 160)
        self.assertEqual(first_cell["accuracy"] * report["units"]["canonical_accuracy_binding"]["multiply_by"],
                         99.375)
        delta = comparison["paired_replay_cells"][0]["candidate_minus_author"]
        self.assertAlmostEqual(delta * report["units"]["canonical_difference_binding"]["multiply_by"], .625)



if __name__ == "__main__":
    unittest.main()

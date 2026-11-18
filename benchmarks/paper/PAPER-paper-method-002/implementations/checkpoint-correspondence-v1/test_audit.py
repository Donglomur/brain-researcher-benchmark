"""Generated metadata controls; no scientific data, simulation or fit."""
import copy
import importlib.util
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location("checkpoint_audit", Path(__file__).with_name("audit.py"))
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)
audit = module.audit
Error = module.CorrespondenceError


def fixture():
    # Two complete epochs, three batches each. Validation runs after batch1
    # and after epoch-end: optimizer steps2,3,5,6.
    return {
        "schema": module.SCHEMA,
        "source_commit": "5e7a86282adb9d4603b5546ac5d8dad59aec7cc0",
        "observation_manifest_sha256": "f" * 64,
        "epochs": 2, "batches_per_epoch": 3, "evaluate_every_nth_batch": 2,
        "events": [
            {"epoch": 0, "after_batch": 1, "validation_mean_pearson": .8,
             "parameter_state_sha256": "a" * 64},
            {"epoch": 0, "after_batch": "epoch_end", "validation_mean_pearson": .4,
             "parameter_state_sha256": "b" * 64},
            {"epoch": 1, "after_batch": 1, "validation_mean_pearson": .3,
             "parameter_state_sha256": "c" * 64},
            {"epoch": 1, "after_batch": "epoch_end", "validation_mean_pearson": .2,
             "parameter_state_sha256": "d" * 64},
        ],
        "checkpoints": [
            {"epoch_boundary": 0, "parameter_state_sha256": "0" * 64},
            {"epoch_boundary": 1, "parameter_state_sha256": "b" * 64},
            {"epoch_boundary": 2, "parameter_state_sha256": "d" * 64},
        ],
    }


class AuditTests(unittest.TestCase):
    def test_mid_epoch_winner_is_not_epoch_checkpoint(self):
        result = audit(fixture())
        self.assertEqual(result["selected_event"]["optimizer_step"], 2)
        self.assertEqual(result["checkpoint_correspondence"],
                         "winner_is_between_source_checkpoint_boundaries")
        self.assertEqual(result["matching_same_step_boundaries"], [])

    def test_epoch_only_schedule_binds_matching_boundary(self):
        data = fixture()
        data["batches_per_epoch"] = 48
        data["evaluate_every_nth_batch"] = 100
        data["events"] = [data["events"][1], data["events"][3]]
        result = audit(data)
        self.assertEqual(result["selected_event"]["optimizer_step"], 48)
        self.assertEqual(result["matching_same_step_boundaries"], [1])
        self.assertFalse(result["checkpoint_bytes_verified"])
        self.assertEqual(result["historical_authenticity"], "not_established")
        self.assertIsNone(result["paper_win"])

    def test_first_strict_maximum_wins_ties(self):
        data = fixture()
        data["events"][1]["validation_mean_pearson"] = .8
        data["events"][3]["validation_mean_pearson"] = .8
        self.assertEqual(audit(data)["selected_event"]["event_index"], 0)

    def test_missing_parameter_identity_stays_unresolved(self):
        data = fixture()
        data["events"][0]["parameter_state_sha256"] = None
        self.assertEqual(audit(data)["checkpoint_correspondence"],
                         "winner_parameter_identity_unrecorded")

    def test_undefined_and_minus_one_do_not_invent_winner(self):
        data = fixture()
        for event, score in zip(data["events"], [None, -1, None, -1]):
            event["validation_mean_pearson"] = score
        result = audit(data)
        self.assertIsNone(result["selected_event"])
        self.assertEqual(result["undefined_validation_event_count"], 2)
        self.assertEqual(result["checkpoint_correspondence"],
                         "no_validation_winner_above_source_initial_minus_one")

    def test_incomplete_or_reordered_history_refused(self):
        data = fixture()
        data["events"].pop()
        with self.assertRaises(Error):
            audit(data)
        data = fixture()
        data["events"][0], data["events"][1] = data["events"][1], data["events"][0]
        with self.assertRaises(Error):
            audit(data)

    def test_epoch_end_duplicate_event_is_retained_and_state_consistent(self):
        data = fixture()
        data["epochs"] = 1
        data["batches_per_epoch"] = 2
        data["events"] = data["events"][:2]
        data["events"][1]["parameter_state_sha256"] = "a" * 64
        data["events"][1]["validation_mean_pearson"] = .8
        data["checkpoints"] = [
            {"epoch_boundary": 1, "parameter_state_sha256": "a" * 64}]
        result = audit(data)
        self.assertEqual(result["complete_declared_event_count"], 2)
        self.assertEqual(result["matching_same_step_boundaries"], [1])
        data["events"][1]["parameter_state_sha256"] = "e" * 64
        with self.assertRaises(Error):
            audit(data)

    def test_missing_and_wrong_boundary_states_are_distinct(self):
        data = fixture()
        data["events"][1]["validation_mean_pearson"] = .9
        data["checkpoints"] = []
        self.assertEqual(audit(data)["checkpoint_correspondence"],
                         "winner_boundary_checkpoint_not_in_inventory")
        data["checkpoints"] = [
            {"epoch_boundary": 1, "parameter_state_sha256": "e" * 64}]
        self.assertEqual(audit(data)["checkpoint_correspondence"],
                         "winner_and_boundary_checkpoint_digests_differ")

    def test_same_digest_elsewhere_does_not_assert_same_step(self):
        data = fixture()
        data["checkpoints"][2]["parameter_state_sha256"] = "a" * 64
        result = audit(data)
        self.assertEqual(result["identical_digest_at_other_boundaries"], [2])
        self.assertEqual(result["matching_same_step_boundaries"], [])

    def test_malformed_values_and_selection_on_test_are_refused(self):
        for score in [True, float("nan"), float("inf"), 1.001, "0.8"]:
            with self.subTest(score=score):
                data = fixture()
                data["events"][0]["validation_mean_pearson"] = score
                with self.assertRaises(Error):
                    audit(data)
        data = fixture()
        data["events"][0]["test_mean_pearson"] = 1
        with self.assertRaises(Error):
            audit(data)
        data = fixture()
        data["epochs"] = True
        with self.assertRaises(Error):
            audit(data)

    def test_duplicate_and_out_of_range_checkpoints_are_refused(self):
        data = fixture()
        data["checkpoints"][1] = copy.deepcopy(data["checkpoints"][0])
        with self.assertRaises(Error):
            audit(data)
        data = fixture()
        data["checkpoints"][0]["epoch_boundary"] = 3
        with self.assertRaises(Error):
            audit(data)

    def test_input_not_mutated_and_binding_changes_digest(self):
        data = fixture()
        before = copy.deepcopy(data)
        first = audit(data)
        self.assertEqual(data, before)
        data["observation_manifest_sha256"] = "e" * 64
        second = audit(data)
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])
        self.assertEqual(first["selected_event"], second["selected_event"])


if __name__ == "__main__":
    unittest.main()

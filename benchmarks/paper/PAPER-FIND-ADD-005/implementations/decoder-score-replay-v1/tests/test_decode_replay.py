"""Generated engineering controls only; no authentic data or source fitting."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("dentate_decode_replay", Path(__file__).parents[1] / "decode_replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def fixture():
    targets = [0] * 8 + [1] * 2
    weights = [1 / 16] * 8 + [1 / 4] * 2
    predictions = [[0, 1, target] for target in targets]
    # Independent enumeration: constant0/constant1 each receives half category mass.
    accuracy = [[0.5] + [0.4] * 50, [0.5] + [0.4] * 50, [1.0] + [0.4] * 50]
    group = {"variable": "gap_direction", "subgroup_index": 1, "values": [0, 1],
             "selected_experiment_trial_indices": list(range(1, 11)), "target": targets,
             "trial_weights": weights, "status": "fitted",
             "models": [{"alignment": "cue_start", "aligned_time_ms": [-200, 0, 200],
                         "first_experiment_prediction": predictions, "retained_accuracy": accuracy}]}
    cell = {"monkey": "Mi", "cell_id": "generated_cell", "status": "fitted",
            "selected_prefiltered_trial_indices": list(range(2, 22, 2)),
            "source_trial_numbers": list(range(101, 111)), "groups": [group]}
    return {"schema": "dentate-decoder-score-export-v1", "source_commit": replay.SOURCE_COMMIT,
            "source_decoder_sha256": replay.SOURCE_DECODER_SHA256,
            "configuration": {"n_cv_folds": 3, "requested_n_shuffles": 50,
                              "time_bin_ms": 200, "minimum_trials": 10,
                              "behavior_variables": ["gap_direction"], "behavior_events": ["cue_start"]},
            "cells": [cell]}


def candidate(source):
    report = replay.replay(source)["models"][0]
    cell = source["cells"][0]
    group = cell["groups"][0]
    model = {name: report[name] for name in ("monkey", "cell_id", "variable", "values", "alignment",
                                            "aligned_time_ms", "support_sha256")}
    model["source_trial_numbers"] = cell["source_trial_numbers"][:]
    model["prediction"] = [[target] * 3 for target in group["target"]]
    return {"schema": "dentate-decoder-predictions-v1", "models": [model]}


class DecoderReplayTests(unittest.TestCase):
    def test_weighted_not_unweighted_accuracy(self):
        result = replay.replay(fixture())
        self.assertEqual(result["models"][0]["first_experiment_accuracy"], [0.5, 0.5, 1.0])
        self.assertNotEqual(result["models"][0]["first_experiment_accuracy"][0], 0.8)
        self.assertFalse(result["permutation_scores_replayed"])
        self.assertFalse(result["first_experiment_is_unshuffled_verified"])
        self.assertFalse(result["paper_figure4_mapping_verified"])
        self.assertIsNone(result["population_significance_fraction"])

    def test_retained_null_scores_are_not_fabricated_replays(self):
        document = fixture()
        document["cells"][0]["groups"][0]["models"][0]["retained_accuracy"][0][1] = 0.97
        result = replay.replay(document)
        self.assertFalse(result["models"][0]["remaining_accuracy_columns_replayed"])
        self.assertEqual(result["models"][0]["retained_accuracy_column_count"], 51)

    def test_request_count_does_not_invent_permutation_helper_shape(self):
        document = fixture()
        model = document["cells"][0]["groups"][0]["models"][0]
        model["retained_accuracy"] = [row[:-1] for row in model["retained_accuracy"]]
        self.assertEqual(replay.replay(document)["models"][0]["retained_accuracy_column_count"], 50)

    def test_changed_observed_score_rejected(self):
        document = fixture()
        document["cells"][0]["groups"][0]["models"][0]["retained_accuracy"][0][0] = 0.8
        with self.assertRaisesRegex(replay.ReplayError, "does not replay"):
            replay.replay(document)

    def test_weights_not_silently_renormalized(self):
        document = fixture()
        document["cells"][0]["groups"][0]["trial_weights"][0] *= 2
        with self.assertRaisesRegex(replay.ReplayError, "sum to one"):
            replay.replay(document)

    def test_candidate_complete_pair_and_delta(self):
        document = fixture()
        result = replay.replay(document, candidate(document))
        self.assertEqual(result["models"][0]["candidate_minus_retained_first_experiment"], [0.5, 0.5, 0.0])
        self.assertFalse(result["paper_improvement_established"])

    def test_candidate_missing_support_rejected(self):
        with self.assertRaisesRegex(replay.ReplayError, "incomplete"):
            replay.replay(fixture(), {"schema": "dentate-decoder-predictions-v1", "models": []})

    def test_candidate_trial_time_and_label_corruption_rejected(self):
        document = fixture()
        for field, value in (("source_trial_numbers", list(range(110, 100, -1))),
                             ("aligned_time_ms", [-100, 100, 300]),
                             ("support_sha256", "0" * 64)):
            with self.subTest(field=field):
                submission = candidate(document)
                submission["models"][0][field] = value
                with self.assertRaises(replay.ReplayError):
                    replay.replay(document, submission)
        submission = candidate(document)
        submission["models"][0]["prediction"][0][0] = 9
        with self.assertRaisesRegex(replay.ReplayError, "unknown label"):
            replay.replay(document, submission)

    def test_empty_source_exclusions_preserved(self):
        document = fixture()
        document["cells"].append({"monkey": "Mo", "cell_id": "generated_excluded", "status": "insufficient_cell_trials",
                                  "selected_prefiltered_trial_indices": [], "source_trial_numbers": []})
        document["configuration"]["behavior_variables"].append("past_gap")
        document["cells"][0]["groups"].append({"variable": "past_gap", "subgroup_index": 1, "values": [],
            "status": "insufficient_group_trials", "selected_experiment_trial_indices": [],
            "target": [], "trial_weights": [], "models": []})
        result = replay.replay(document)
        self.assertEqual(len(result["source_exclusions"]), 2)
        self.assertTrue(all(row["n_trials"] == 0 for row in result["source_exclusions"]))

    def test_missing_duplicate_or_overlapping_groups_rejected(self):
        document = fixture()
        for mode in ("duplicate_cell", "duplicate_event", "missing_variable", "overlap_group"):
            source = copy.deepcopy(document)
            if mode == "duplicate_cell": source["cells"].append(copy.deepcopy(source["cells"][0]))
            elif mode == "duplicate_event": source["cells"][0]["groups"][0]["models"].append(copy.deepcopy(source["cells"][0]["groups"][0]["models"][0]))
            elif mode == "missing_variable": source["configuration"]["behavior_variables"].append("past_gap")
            else:
                group = copy.deepcopy(source["cells"][0]["groups"][0]); group["subgroup_index"] = 2
                source["cells"][0]["groups"].append(group)
            with self.subTest(mode=mode), self.assertRaises(replay.ReplayError): replay.replay(source)

    def test_pinned_variant_and_axis_rejected(self):
        for field, value in (("n_cv_folds", 5), ("time_bin_ms", 150), ("requested_n_shuffles", True)):
            source = fixture(); source["configuration"][field] = value
            with self.subTest(field=field), self.assertRaises(replay.ReplayError): replay.replay(source)
        source = fixture(); source["configuration"]["behavior_variables"] = ["condition_code"]
        with self.assertRaises(replay.ReplayError): replay.replay(source)
        source = fixture(); source["cells"][0]["groups"][0]["models"][0]["aligned_time_ms"] = [-200, 0, 199]
        with self.assertRaises(replay.ReplayError): replay.replay(source)

    def test_cli_hashes_exact_scored_input_snapshots(self):
        for mode in ("author", "candidate", "paired"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                source = fixture()
                proposal = candidate(source)
                documents = {"author_export": source}
                if mode == "candidate":
                    documents["candidate"] = proposal
                elif mode == "paired":
                    documents.update(paper_data=proposal, paper_data_author_code=proposal)
                paths = {name: Path(folder) / (name + ".json") for name in documents}
                original_bytes = {name: json.dumps(document).encode("utf-8")
                                  for name, document in documents.items()}
                for name, path in paths.items():
                    path.write_bytes(original_bytes[name])
                operation = "compare_conditions" if mode == "paired" else "replay"
                original_operation = getattr(replay, operation)
                args = (source, proposal, proposal) if mode == "paired" else (source, proposal if mode == "candidate" else None)
                expected = original_operation(*args)
                def replace_after_replay(*args):
                    result = original_operation(*args)
                    for path in paths.values():
                        replacement = path.with_suffix(".replacement")
                        replacement.write_bytes(b'{"replaced_after_scoring": true}')
                        replacement.replace(path)
                    return result
                output = Path(folder) / "report.json"
                argv = ["decode_replay.py", "--output", str(output)]
                for name, path in paths.items():
                    argv += ["--" + name.replace("_", "-"), str(path)]
                with patch.object(sys, "argv", argv), patch.object(replay, operation, replace_after_replay):
                    replay.main()
                report = json.loads(output.read_text())
                for name, raw in original_bytes.items():
                    self.assertEqual(report.pop(name + "_sha256"), hashlib.sha256(raw).hexdigest())
                self.assertEqual(report, expected)

    def test_duplicate_json_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            for text in ('{"schema": 1, "schema": 2}', '{"x": NaN}'):
                path.write_text(text)
                with self.assertRaises(replay.ReplayError): replay.read_json(path)


if __name__ == "__main__":
    unittest.main()

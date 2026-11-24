"""Generated paired-arm controls; no authentic observations or fits."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_decode_replay import fixture, replay


def paired_fixture():
    source = fixture()
    second = copy.deepcopy(source["cells"][0])
    second.update(monkey="Mo", cell_id="generated_second",
                  source_trial_numbers=list(range(201, 211)))
    source["cells"].append(second)
    source["configuration"]["behavior_variables"].append("past_gap")
    source["configuration"]["behavior_events"].append("reward_start")
    for cell in source["cells"]:
        past = copy.deepcopy(cell["groups"][0])
        past["variable"] = "past_gap"
        cell["groups"].append(past)
        for group in cell["groups"]:
            event = copy.deepcopy(group["models"][0])
            event.update(alignment="reward_start", aligned_time_ms=[-400, -200, 0])
            group["models"].append(event)
    source["cells"].append({"monkey": "Mo", "cell_id": "generated_excluded",
                            "status": "insufficient_cell_trials",
                            "selected_prefiltered_trial_indices": [], "source_trial_numbers": []})
    data, code = [], []
    for i, report in enumerate(replay.replay(source)["models"]):
        cell = next(cell for cell in source["cells"]
                    if (cell["monkey"], cell["cell_id"]) == (report["monkey"], report["cell_id"]))
        group = next(group for group in cell["groups"] if group["variable"] == report["variable"])
        model = {name: report[name] for name in ("monkey", "cell_id", "variable", "values", "alignment",
                                                "aligned_time_ms", "support_sha256")}
        model["source_trial_numbers"] = cell["source_trial_numbers"][:]
        data.append({**copy.deepcopy(model), "prediction": [[0, 0, 0] for _ in group["target"]]})
        code.append({**copy.deepcopy(model), "prediction": [[y, 1 - y, 0] if i % 2 == 0 else [1 - y, y, 0]
                                              for y in group["target"]]})
    return (source, {"schema": "dentate-decoder-predictions-v1", "models": data},
            {"schema": "dentate-decoder-predictions-v1", "models": list(reversed(code))})


class PairedConditionsTests(unittest.TestCase):
    def test_complete_family_aligns_reordered_arms_and_preserves_axes(self):
        source, data, code = paired_fixture()
        before = copy.deepcopy((source, data, code))
        report = replay.compare_conditions(source, data, code)
        self.assertEqual(len(report["models"]), 8)
        self.assertEqual({row["monkey"] for row in report["models"]}, {"Mi", "Mo"})
        for i, row in enumerate(report["models"]):
            self.assertEqual(row["first_experiment_accuracy"], [0.5, 0.5, 1.0])
            self.assertEqual(row["condition_scores"]["paper_data"]["accuracy"], [0.5] * 3)
            self.assertEqual(row["condition_scores"]["paper_data"]["minus_retained_first_experiment"],
                             [0.0, 0.0, -0.5])
            expected = [0.5, -0.5, 0.0] if i % 2 == 0 else [-0.5, 0.5, 0.0]
            self.assertEqual(row["paper_data_author_code_minus_paper_data"], expected)
            self.assertEqual(row["condition_scores"]["paper_data_author_code"]
                             ["minus_retained_first_experiment"], expected[:2] + [-0.5])
        self.assertEqual((source, data, code), before)
        self.assertEqual(report["source_exclusions"][0]["cell_id"], "generated_excluded")
        for field in ("complete_original_cohort_verified", "original_folds_verified",
                      "paper_figure4_mapping_verified", "paper_reproduction_established",
                      "paper_improvement_established", "information_condition_assignment_verified",
                      "condition_resource_exposure_comparability_verified"):
            self.assertFalse(report[field])
        self.assertIsNone(report["population_significance_fraction"])

    def test_each_arm_must_supply_every_model_and_original_support(self):
        for arm in (1, 2):
            for corruption in ("missing_model", "support_hash", "trial_order", "time_axis"):
                values = list(paired_fixture())
                row = values[arm]["models"][0]
                if corruption == "missing_model":
                    values[arm]["models"].pop()
                elif corruption == "support_hash":
                    row["support_sha256"] = "0" * 64
                elif corruption == "trial_order":
                    row["source_trial_numbers"].reverse()
                else:
                    row["aligned_time_ms"] = [-100, 100, 300]
                with self.subTest(arm=arm, corruption=corruption), self.assertRaises(replay.ReplayError):
                    replay.compare_conditions(*values)

    def test_paired_api_requires_both_arms(self):
        source, data, code = paired_fixture()
        for args in ((source, None, code), (source, data, None)):
            with self.assertRaisesRegex(replay.ReplayError, "both information-condition"):
                replay.compare_conditions(*args)

    def test_cli_preserves_three_input_receipts_and_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, data, code = [root / name for name in ("source.json", "data.json", "code.json")]
            for path, value in zip((source, data, code), paired_fixture()):
                path.write_text(json.dumps(value))
            output = root / "paired.json"
            args = ["decode_replay.py", "--author-export", str(source), "--paper-data", str(data),
                    "--paper-data-author-code", str(code), "--output", str(output)]
            with patch.object(sys, "argv", args):
                replay.main()
            report = json.loads(output.read_text())
            self.assertEqual(report["schema"], "dentate-decoder-paired-conditions-report-v1")
            for name, path in (("author_export", source), ("paper_data", data),
                               ("paper_data_author_code", code)):
                self.assertEqual(report[name + "_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            previous = output.read_bytes()
            with patch.object(sys, "argv", args), self.assertRaises(FileExistsError):
                replay.main()
            self.assertEqual(output.read_bytes(), previous)
            args[-1] = str(data)
            with patch.object(sys, "argv", args), self.assertRaisesRegex(replay.ReplayError, "overwrite"):
                replay.main()

    def test_cli_rejects_partial_pair_or_mixed_mode_before_reading_inputs(self):
        base = ["decode_replay.py", "--author-export", "absent.json", "--output", "absent-output.json"]
        for extra in (["--paper-data", "data.json"], ["--paper-data-author-code", "code.json"],
                      ["--candidate", "candidate.json", "--paper-data", "data.json",
                       "--paper-data-author-code", "code.json"]):
            with self.subTest(extra=extra), patch.object(sys, "argv", base + extra), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                replay.main()
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

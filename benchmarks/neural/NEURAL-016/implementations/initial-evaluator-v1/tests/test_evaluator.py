"""Generated engineering controls only; no authentic neural measurements."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import unittest
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from evaluator import ContractError, canonical_hash, contrast, evaluate, summarize, validate_protocol
from controls import joint_linguistic_circular_shift


def packets():
    """A complete synthetic protocol, with every canonical recording accounted for."""
    roster = json.loads((PACKAGE / "source_manifest.json").read_text())["recordings"]
    chosen = {"sub_1_trial000", "sub_2_trial000", "sub_3_trial000"}
    recipe = {
        "primary_metric": "delta_explained_variance", "constant_prediction_policy": "report",
        "response_definition": "GENERATED CONTROL ONLY: scalar, no neural signal",
        "response_window_seconds": [0.0, 0.5], "feature_lags_seconds": [-1.0, 0.0],
        "guard_seconds": 1.0, "anatomy_selection": "training_only", "preprocessing": "training_only",
        "split_policy": "outer_person_and_whole_movie", "bootstrap_repetitions": 200, "bootstrap_seed": 19,
        "nuisance_features": {"speaker": ["speaker_id"], "acoustic": ["rms"],
                              "visual_motion": ["max_global_magnitude"], "word_timing": ["word_length", "word_diff"]},
        "linguistic_features": ["gpt2_surprisal"],
    }
    protocol = {"schema_version": 1, "task_id": "NEURAL-016", "protocol_id": "generated-control",
                "frozen_before_outcomes": True, "data_scope": "public_development_only", "recipe": recipe,
                "source_files": [{"role": r, "identity": "generated-control-not-real-source", "sha256": "0" * 64, "bytes": 1}
                                 for r in ("neural", "timing", "transcripts", "electrodes")],
                "population": [{"recording_id": r["recording_id"], "disposition": "included" if r["recording_id"] in chosen else "excluded",
                                "reason": "generated engineering fixture only; no scientific population selection"} for r in roster],
                "blocks": [], "rows": [], "folds": []}
    for recording in sorted(chosen):
        source = next(r for r in roster if r["recording_id"] == recording)
        protocol["blocks"].append({"block_id": recording + "-block", "recording_id": recording,
                                    "start_seconds": 0.0, "end_seconds": 20.0})
        for i in range(4):
            protocol["rows"].append(dict(source, row_id=recording + "-" + str(i), electrode_id="generated_electrode_1",
                                         block_id=recording + "-block", time_seconds=3.0 + i))
    fit = [r["row_id"] for r in protocol["rows"] if r["participant_id"] == "3"]
    for participant in ("1", "2"):
        test = [r["row_id"] for r in protocol["rows"] if r["participant_id"] == participant]
        protocol["folds"].append({"fold_id": "fold-" + participant, "fit_row_ids": fit, "evaluation_row_ids": test})
    digest = canonical_hash(protocol)
    values, predictions = [], []
    for fold in protocol["folds"]:
        for row_id, y, n in zip(fold["evaluation_row_ids"], [-3.0, -1.0, 1.0, 3.0], [-2.0, -2.0, 2.0, 2.0]):
            values.append({"row_id": row_id, "value": y})
            predictions.append({"row_id": row_id, "nuisance": n, "full": y})
    target = {"protocol_sha256": digest, "values": values}
    submission = {"protocol_sha256": digest, "predictions": predictions, "fit_provenance": [
        {"fold_id": f["fold_id"], "fit_row_ids": f["fit_row_ids"], "recipe_sha256": canonical_hash(recipe),
         "nuisance_artifact_sha256": "1" * 64, "full_artifact_sha256": "2" * 64} for f in protocol["folds"]]}
    return protocol, target, submission


def test_independent_sse_oracle_and_negative_contrast():
    y, nuisance = [-3, -1, 1, 3], [-2, -2, 2, 2]
    answer = contrast(y, nuisance, y)
    assert answer["target_sst"] == 20
    assert answer["nuisance_sse"] == 4
    unittest.TestCase().assertAlmostEqual(answer["delta_r2"], 0.2)
    unittest.TestCase().assertAlmostEqual(contrast(y, nuisance, [0] * 4)["delta_r2"], -0.8)
    biased = contrast(y, nuisance, np.array(y) + 10)
    unittest.TestCase().assertAlmostEqual(biased["delta_r2"], -19.8)
    unittest.TestCase().assertAlmostEqual(biased["delta_explained_variance"], 0.2)


def test_independent_bias_distinguishes_ev_and_r2():
    result = contrast([1, 2, 3, 4], [2.5] * 4, [11, 12, 13, 14])
    unittest.TestCase().assertAlmostEqual(result["delta_explained_variance"], 1)
    unittest.TestCase().assertAlmostEqual(result["delta_r2"], -79)
    assert result["nuisance_constant"] is True


def test_review_numeric_regressions():
    with unittest.TestCase().assertRaisesRegex(ContractError, "nonfinite metric"):
        contrast([0, 1e-160], [1, 1], [0, 1e-160])
    result = contrast([0, 1e-100], [1, 1], [0, 1e-100])
    unittest.TestCase().assertAlmostEqual(result["nuisance_explained_variance"], 0)
    unittest.TestCase().assertAlmostEqual(result["delta_explained_variance"], 1)
    blocks = [{"participant_id": p, "electrode_id": "a", "delta_r2": -1e308, "delta_explained_variance": -1e308}
              for p in ["1", "1", "2", "2"]]
    with unittest.TestCase().assertRaisesRegex(ContractError, "nonfinite aggregate"):
        summarize(blocks, 100, 5)


def test_independent_nested_macro_oracle():
    blocks = [{"participant_id": p, "electrode_id": e, "delta_r2": v, "delta_explained_variance": v}
              for p, e, v in [("1", "a", 1), ("1", "a", -1), ("1", "b", 1), ("2", "a", -1)]]
    summary = summarize(blocks, 1000, 27)
    unittest.TestCase().assertAlmostEqual(summary["estimate"]["delta_r2"], -0.25)
    assert [p["delta_r2"] for p in summary["participants"]] == [0.5, -1]
    assert summary == summarize(blocks, 1000, 27)
    assert summarize(blocks[:1], 100, 27)["participant_paired_bootstrap_95_percentile"] is None


def test_complete_scoring_and_order_independence():
    p, t, s = packets()
    result = evaluate(p, t, s)
    unittest.TestCase().assertAlmostEqual(result["primary_estimate"], 0.2)
    assert result["summary"]["n_participants"] == 2
    assert result["population_accounting"]["canonical_recordings"] == 26
    assert result["admission"]["research_qualified"] is False
    t["values"].reverse()
    s["predictions"].reverse()
    assert evaluate(p, t, s)["summary"] == result["summary"]


PROTOCOL_MUTATIONS = [
    (lambda p: p["population"].pop(), "all 26"),
    (lambda p: p["rows"][0].update(participant_id="999"), "canonical roster"),
    (lambda p: p["rows"][0].update(time_seconds=0.25), "guard"),
    (lambda p: p["recipe"].update(feature_lags_seconds=[0, 0.1]), "future"),
    (lambda p: p["recipe"].update(guard_seconds=0.1), "every lag"),
    (lambda p: p["recipe"]["nuisance_features"].pop("speaker"), "speaker"),
    (lambda p: p["recipe"].update(anatomy_selection="heldout"), "training only"),
    (lambda p: p["folds"][0]["fit_row_ids"].extend(p["folds"][0]["evaluation_row_ids"]), "row overlap"),
    (lambda p: p["rows"].append(dict(p["rows"][0], row_id="alias")), "duplicate biological"),
]
def check_protocol_adversary(mutation, match):
    p, _, _ = packets()
    mutation(p)
    with unittest.TestCase().assertRaisesRegex(ContractError, match):
        validate_protocol(p)


def test_same_movie_across_people_is_not_unseen_stimulus():
    p, _, _ = packets()
    # Participant 3 and 10 both watched cars-2. Replace evaluation participant 1
    # with canonical participant 10, preserving different people but same movie.
    old, new = "sub_1_trial000", "sub_10_trial000"
    for row in p["rows"]:
        if row["recording_id"] == old:
            row.update(recording_id=new, participant_id="10", movie_id="cars-2")
    for block in p["blocks"]:
        if block["recording_id"] == old:
            block["recording_id"] = new
    for item in p["population"]:
        if item["recording_id"] in {old, new}:
            item["disposition"] = "included" if item["recording_id"] == new else "excluded"
    with unittest.TestCase().assertRaisesRegex(ContractError, "movie_id leakage"):
        validate_protocol(p)


def test_review_schema_and_block_atomicity_regressions():
    p, t, s = packets()
    p["recipe"] = None
    with unittest.TestCase().assertRaisesRegex(ContractError, "recipe must be an object"):
        validate_protocol(p)
    p, t, s = packets()
    p["rows"][0]["held_out_target"] = 3.0
    with unittest.TestCase().assertRaisesRegex(ContractError, "unknown fields"):
        validate_protocol(p)
    p, t, s = packets()
    first = p["folds"][0]
    extra = dict(first, fold_id="illegal-extra", evaluation_row_ids=first["evaluation_row_ids"][2:])
    first["evaluation_row_ids"] = first["evaluation_row_ids"][:2]
    p["folds"].append(extra)
    with unittest.TestCase().assertRaisesRegex(ContractError, "every declared row"):
        validate_protocol(p)
    p, t, s = packets()
    s["null_predictions"] = [None]
    with unittest.TestCase().assertRaisesRegex(ContractError, "null control must be an object"):
        evaluate(p, t, s)


def check_packet_adversary(kind):
    p, t, s = packets()
    if kind == "missing": s["predictions"].pop()
    if kind == "extra": s["predictions"].append({"row_id": "unknown", "nuisance": 0, "full": 1})
    if kind == "duplicate": s["predictions"].append(copy.deepcopy(s["predictions"][0]))
    if kind == "nan": s["predictions"][0]["full"] = float("nan")
    if kind == "boolean": s["predictions"][0]["full"] = True
    if kind == "hash": t["protocol_sha256"] = "0" * 64
    if kind == "fit": s["fit_provenance"][0]["fit_row_ids"] = [s["predictions"][0]["row_id"]]
    if kind == "recipe": s["fit_provenance"][0]["recipe_sha256"] = "0" * 64
    with unittest.TestCase().assertRaises(ContractError): evaluate(p, t, s)


def test_constant_outputs_explicit_and_constant_targets_rejected():
    p, t, s = packets()
    for row in s["predictions"]: row["full"] = 0
    result = evaluate(p, t, s)
    assert all(b["full_constant"] for b in result["blocks"])
    p["recipe"]["constant_prediction_policy"] = "reject_full"
    digest = canonical_hash(p)
    t["protocol_sha256"] = s["protocol_sha256"] = digest
    for f in s["fit_provenance"]: f["recipe_sha256"] = canonical_hash(p["recipe"])
    with unittest.TestCase().assertRaisesRegex(ContractError, "constant full"): evaluate(p, t, s)
    for row in t["values"]: row["value"] = 1
    with unittest.TestCase().assertRaisesRegex(ContractError, "constant.*target"): evaluate(p, t, s)


def test_null_circular_correlation_and_joint_structure():
    times = np.arange(12) * 0.5
    a = np.array([0, 1, 3, 7, 2, 5, 1, 6, 2, 3, 8, 1.0])
    original = np.column_stack([a, a**2])
    shifted = joint_linguistic_circular_shift(times, original, 4, 1.0)
    assert np.array_equal(shifted[:, 1], shifted[:, 0]**2)
    for lag in range(len(a)):
        unittest.TestCase().assertAlmostEqual(np.dot(a, np.roll(a, lag)), np.dot(shifted[:, 0], np.roll(shifted[:, 0], lag)))
    assert np.array_equal(original[:, 0], a)  # No mutation.
    with unittest.TestCase().assertRaisesRegex(ContractError, "irregular"):
        joint_linguistic_circular_shift(times**2, original, 4, 1.0)
    with unittest.TestCase().assertRaisesRegex(ContractError, "guard"):
        joint_linguistic_circular_shift(times, original, 1, 1.0)
    with unittest.TestCase().assertRaisesRegex(ContractError, "degenerate"):
        joint_linguistic_circular_shift(times, np.ones((12, 2)), 4, 1.0)


def test_null_recomputed_but_never_claims_calibrated_p_value():
    p, t, s = packets()
    null_predictions = copy.deepcopy(s["predictions"])
    for prediction in null_predictions: prediction["full"] = prediction["nuisance"]
    s["null_predictions"] = [{"permutation_id": "control-1", "control": "joint_linguistic_circular_shift_uniform_time",
                              "refitted_recipe_sha256": canonical_hash(p["recipe"]), "predictions": null_predictions,
                              "shift_manifest_sha256": "3" * 64, "fit_provenance": copy.deepcopy(s["fit_provenance"])}]
    result = evaluate(p, t, s)
    assert result["null_control"]["descriptive_upper_tail_rank"] == 0.5
    assert result["null_control"]["replicates"][0]["estimate"]["delta_r2"] == 0
    assert result["null_control"]["status"] == "supplied_unverified_exchangeability"
    s["null_predictions"][0]["shift_manifest_sha256"] = "invalid"
    with unittest.TestCase().assertRaisesRegex(ContractError, "shift manifest"): evaluate(p, t, s)
    s["null_predictions"][0]["shift_manifest_sha256"] = "3" * 64
    s["null_predictions"][0]["fit_provenance"][0]["fit_row_ids"] = ["heldout"]
    with unittest.TestCase().assertRaisesRegex(ContractError, "declared fit rows"): evaluate(p, t, s)
    s["null_predictions"][0]["fit_provenance"] = copy.deepcopy(s["fit_provenance"])
    null_predictions[0]["nuisance"] += 1
    with unittest.TestCase().assertRaisesRegex(ContractError, "nuisance comparator"): evaluate(p, t, s)


def check_cli_round_trip(tmp_path):
    p, t, s = packets()
    names = ["protocol", "private-targets", "submission"]
    command = [sys.executable, str(PACKAGE / "evaluator.py")]
    for name, value in zip(names, (p, t, s)):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        command.extend(["--" + name, str(path)])
    output = tmp_path / "score.json"
    command.extend(["--output", str(output)])
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text())
    unittest.TestCase().assertAlmostEqual(result["primary_estimate"], 0.2)
    assert len(result["input_file_sha256"]["private_targets"]) == 64
    # Invalid metadata cannot produce a traceback or overwrite a successful score.
    s["unexpected_metadata"] = float("nan")
    (tmp_path / "submission.json").write_text(json.dumps(s))
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 2
    assert "Traceback" not in completed.stderr
    assert json.loads(output.read_text())["primary_estimate"] == result["primary_estimate"]


class GeneratedEngineeringTests(unittest.TestCase):
    def test_protocol_adversaries(self):
        for mutation, match in PROTOCOL_MUTATIONS:
            with self.subTest(match=match):
                check_protocol_adversary(mutation, match)

    def test_packet_adversaries(self):
        for kind in ["missing", "extra", "duplicate", "nan", "boolean", "hash", "fit", "recipe"]:
            with self.subTest(kind=kind):
                check_packet_adversary(kind)

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            check_cli_round_trip(Path(directory))


# Standalone numerical controls remain independently callable by reviewers.
for _name, _function in list(globals().items()):
    if _name.startswith("test_") and callable(_function):
        setattr(GeneratedEngineeringTests, _name, staticmethod(_function))
del _name, _function

if __name__ == "__main__":
    unittest.main()

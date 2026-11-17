"""Generated-only endpoint controls; no authentic observations are opened."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("paired_mae", HERE / "paired_mae.py")
mae = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mae)
PIN = "0" * 64


def row(member, index, mouse, compartment, **changes):
    value = dict(row_id=f"m{member:02d}r{index:04d}", mouse_id=mouse,
                 compartment=compartment, member_index0=member, source_row0=index,
                 baseline_flag={"kind": "str", "value": ""},
                 followup_flag={"kind": "tuple", "value": [""]},
                 baseline_volume=1.0, followup_volume=2.0, event_rate=None,
                 movement_amplitude=0.2, local=0.3, coincident=0.4, movement_spine=False)
    value.update(changes)
    return value


def fixture():
    # Mouse A spans two members and both compartments; mouse B has fewer rows.
    return [row(0, 0, "A", "apical"), row(0, 1, "A", "apical"),
            row(1, 0, "A", "basal", baseline_volume=2, followup_volume=4),
            row(2, 0, "B", "basal", followup_volume=3)]


def submission(rows):
    selected, _ = mae.select_support(rows)
    folds = []
    for spec in mae.folds_for(selected):
        mouse = spec["heldout_mouse"]
        predictions = []
        for r in selected:
            if r["mouse_id"] == mouse:
                baseline_error, neural_error = (2, 1) if mouse == "A" else (0, 3)
                predictions.append(dict(row_id=r["row_id"], baseline=r["target"] + baseline_error,
                                        neural=r["target"] + neural_error))
        folds.append(dict(heldout_mouse=mouse, training_mice=spec["training_mice"], predictions=predictions))
    return dict(schema_version=1, task_id="NEURAL-032", protocol=mae.PROTOCOL,
                input_sha256=PIN, folds=folds)


class EndpointControls(unittest.TestCase):
    def test_equal_mouse_mae_and_signed_loss_contrast(self):
        rows = fixture()
        result = mae.score_rows(rows, submission(rows), PIN)
        # Hand calculation: A has MAE (2,1), B (0,3). Macro=(1,2), gain=-1.
        # Pooling four spine rows instead would give (1.5,1.5), gain=0.
        self.assertEqual(result["equal_mouse"], dict(baseline_mae=1, neural_mae=2,
                                                    baseline_minus_neural_mae=-1))
        self.assertEqual([r["n"] for r in result["per_mouse"]], [3, 1])
        self.assertEqual(result["units"], "dimensionless volume ratio")

    def test_whole_mouse_fold_includes_both_compartments(self):
        selected, support = mae.select_support(fixture())
        folds = mae.folds_for(selected)
        self.assertEqual(folds[0]["query_row_ids"], ["m00r0000", "m00r0001", "m01r0000"])
        self.assertEqual(folds[0]["train_row_ids"], ["m02r0000"])
        self.assertEqual(len(support["by_mouse_compartment"]), 3)

    def test_support_partition_and_baseline_new_retained(self):
        rows = fixture()
        rows[0]["baseline_flag"] = {"kind": "str", "value": "New Spine"}
        extra = [
            {"baseline_flag": {"kind": "list", "value": ["Absent"]}},
            {"baseline_flag": {"kind": "tuple", "value": ["unknown"]}},
            {"followup_flag": {"kind": "str", "value": "New Spine"}},
            {"followup_volume": None}, {"followup_volume": 0},
            {"baseline_volume": 1e-308, "followup_volume": 1e308},
            {"baseline_volume": 1e308, "followup_volume": 1e-308},
            {"baseline_flag": {"kind": "list", "value": ["New Spine", "Eliminated Spine"]}},
        ]
        rows.extend(row(0, i + 2, "A", "apical", **change) for i, change in enumerate(extra))
        selected, support = mae.select_support(rows)
        self.assertEqual(len(selected), 4)
        self.assertEqual([support[k] for k in ("all_rows", "baseline_excluded", "followup_unavailable", "observed_rows")],
                         [12, 3, 5, 4])
        self.assertEqual(selected[0]["target"], 2)

    def test_mouse_with_no_observed_outcome_is_not_dropped(self):
        rows = fixture()
        rows[-1]["followup_volume"] = None
        with self.assertRaisesRegex(mae.Invalid, "every source mouse"):
            mae.select_support(rows)

    def test_predictions_join_by_id_not_order(self):
        rows = fixture()
        value = submission(rows)
        expected = mae.score_rows(rows, value, PIN)
        value["folds"].reverse()
        value["folds"][1]["predictions"].reverse()
        self.assertEqual(mae.score_rows(rows, value, PIN), expected)

    def test_missing_duplicate_wrong_and_extra_query_rows_rejected(self):
        rows = fixture()
        for mutation in ("missing", "duplicate", "wrong", "extra"):
            with self.subTest(mutation=mutation):
                value = submission(rows)
                predictions = value["folds"][0]["predictions"]
                if mutation == "missing":
                    predictions.pop()
                elif mutation == "duplicate":
                    predictions[1]["row_id"] = predictions[0]["row_id"]
                elif mutation == "wrong":
                    predictions[0]["row_id"] = "m02r0000"
                else:
                    predictions.append(copy.deepcopy(predictions[0]))
                with self.assertRaises(mae.Invalid):
                    mae.score_rows(rows, value, PIN)

    def test_malformed_pair_and_false_fold_declaration_rejected(self):
        rows = fixture()
        for mutation in ("bool", "nan", "missing_arm", "extra", "training_mouse", "duplicate_fold", "pin", "schema_bool"):
            with self.subTest(mutation=mutation):
                value = submission(rows)
                prediction = value["folds"][0]["predictions"][0]
                if mutation == "bool": prediction["neural"] = True
                elif mutation == "nan": prediction["baseline"] = float("nan")
                elif mutation == "missing_arm": del prediction["neural"]
                elif mutation == "extra": prediction["target"] = 2
                elif mutation == "training_mouse": value["folds"][0]["training_mice"] = ["A", "B"]
                elif mutation == "duplicate_fold": value["folds"][1]["heldout_mouse"] = "A"
                elif mutation == "pin": value["input_sha256"] = "1" * 64
                else: value["schema_version"] = True
                with self.assertRaises(mae.Invalid):
                    mae.score_rows(rows, value, PIN)

    def test_constants_negative_predictions_and_null_gain_are_valid(self):
        rows = fixture()
        value = submission(rows)
        for fold in value["folds"]:
            for prediction in fold["predictions"]:
                prediction["baseline"] = prediction["neural"] = -1
        result = mae.score_rows(rows, value, PIN)
        self.assertEqual(result["equal_mouse"]["baseline_minus_neural_mae"], 0)
        self.assertEqual(result["equal_mouse"]["baseline_mae"], 3.5)

    def test_invalid_source_identity_or_numeric_type_rejected(self):
        for mutation in ("duplicate", "member", "gap", "bool", "flag"):
            with self.subTest(mutation=mutation):
                rows = fixture()
                if mutation == "duplicate": rows[1] = copy.deepcopy(rows[0])
                elif mutation == "member": rows[1]["mouse_id"] = "B"
                elif mutation == "gap": rows[1]["source_row0"], rows[1]["row_id"] = 2, "m00r0002"
                elif mutation == "bool": rows[0]["baseline_volume"] = True
                else: rows[0]["baseline_flag"]["value"] = []
                with self.assertRaises(mae.Invalid): mae.select_support(rows)

    def test_strict_json_and_wrong_export_fail_before_scoring(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'{"a":1e-999}'):
            with self.subTest(body=body), self.assertRaises(mae.Invalid): mae.parse_json(body)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.json"
            path.write_text(json.dumps({"rows": fixture()}))
            with self.assertRaisesRegex(mae.Invalid, "exact complete20"):
                mae.load_observations(path)

    def test_mae_is_not_mse(self):
        rows = fixture()
        value = submission(rows)
        # Absolute losses for A: 0,0,9 => MAE 3, MSE 27; B:0 => macro MAE1.5.
        for fold in value["folds"]:
            for prediction in fold["predictions"]:
                prediction["baseline"] = 3 if fold["heldout_mouse"] == "B" else 2
                prediction["neural"] = prediction["baseline"]
        value["folds"][0]["predictions"][2]["baseline"] = 11
        result = mae.score_rows(rows, value, PIN)
        self.assertEqual(result["equal_mouse"]["baseline_mae"], 1.5)
        self.assertEqual(result["equal_mouse"]["baseline_minus_neural_mae"], 1.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

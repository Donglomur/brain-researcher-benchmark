"""Generated binary64 mean regressions; no original observations or files."""
import importlib.util
import math
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("neural032_mean_under_test", Path(__file__).with_name("paired_mae.py"))
mae = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mae)
TINY = float.fromhex("0x0.0000000000001p-1022")


def generated_case(rows_per_mouse, target=TINY, baseline=0.0, neural=None):
    rows, folds = [], []
    mice = list(mae.MICE)
    for member, mouse in enumerate(mice):
        predictions = []
        for index in range(rows_per_mouse):
            row_id = f"m{member:02d}r{index:04d}"
            rows.append(dict(row_id=row_id, mouse_id=mouse, compartment="apical",
                member_index0=member, source_row0=index,
                baseline_flag={"kind": "str", "value": ""},
                followup_flag={"kind": "list", "value": []},
                baseline_volume=1.0, followup_volume=target, event_rate=None,
                movement_amplitude=None, local=None, coincident=None, movement_spine=False))
            predictions.append(dict(row_id=row_id, baseline=baseline, neural=target if neural is None else neural))
        folds.append(dict(heldout_mouse=mouse, training_mice=[m for m in mice if m != mouse], predictions=predictions))
    packet = dict(schema_version=1, task_id="NEURAL-032", protocol=mae.PROTOCOL,
                  input_sha256="0" * 64, folds=folds)
    return rows, packet


class MeanPrecisionControls(unittest.TestCase):
    def score(self, count, **kwargs):
        rows, packet = generated_case(count, **kwargs)
        result = mae.score_rows(rows, packet, "0" * 64)
        self.assertEqual(len(result["per_mouse"]), 20)
        self.assertEqual(result["support"]["observed_rows"], 20 * count)
        return result

    def test_within_mouse_positive_error_cannot_become_perfect(self):
        result = self.score(2)
        # Mean of identical representable values is that value, at both levels.
        self.assertTrue(all(r["baseline_mae"] == TINY for r in result["per_mouse"]))
        self.assertEqual(result["equal_mouse"]["baseline_mae"], TINY)
        self.assertEqual(result["equal_mouse"]["baseline_minus_neural_mae"], TINY)
        self.assertEqual(result["equal_mouse"]["neural_mae"], 0.0)

    def test_equal_mouse_positive_error_cannot_become_perfect(self):
        result = self.score(1)
        self.assertTrue(all(r["baseline_mae"] == TINY for r in result["per_mouse"]))
        self.assertEqual(result["equal_mouse"]["baseline_mae"], TINY)
        self.assertEqual(result["equal_mouse"]["baseline_minus_neural_mae"], TINY)

    def test_near_maximum_finite_losses_do_not_overflow(self):
        maximum = float.fromhex("0x1.fffffffffffffp+1023")
        result = self.score(2, target=1.0, baseline=maximum)
        self.assertEqual(result["equal_mouse"]["baseline_mae"], maximum)
        self.assertTrue(math.isfinite(result["equal_mouse"]["baseline_mae"]))

    def test_signed_gains_cancel_without_positive_floor(self):
        rows, packet = generated_case(2)
        for fold in packet["folds"][10:]:
            for row in fold["predictions"]:
                row["baseline"], row["neural"] = row["neural"], row["baseline"]
        result = mae.score_rows(rows, packet, "0" * 64)
        self.assertEqual(result["equal_mouse"]["baseline_minus_neural_mae"], 0.0)
        self.assertEqual(sum(r["baseline_minus_neural_mae"] > 0 for r in result["per_mouse"]), 10)
        self.assertEqual(sum(r["baseline_minus_neural_mae"] < 0 for r in result["per_mouse"]), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)

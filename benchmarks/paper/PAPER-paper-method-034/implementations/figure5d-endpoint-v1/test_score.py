"""Generated controls only; no authentic targets, neural data or model fitting."""
import contextlib
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("figure5d_score", HERE / "score.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    # Nearest 36 training rows have position 2; one distant row is position 100.
    # Uniform 36-neighbor decoding must return 2 for all 2000 query rows.
    basis = [1.0] + [0.0] * 31
    other = [-1.0] + [0.0] * 31
    support = {"schema": "marble_figure5d_support_v1", "task_id": m.TASK_ID,
               "panel": "Figure 5d", "animal": "rat1", "unit": "m",
               "source_sha256": "a" * 64,
               "training_row_ids": [f"generated/train/{i}" for i in range(37)],
               "query_row_ids": [f"generated/query/{i}" for i in range(2000)]}
    train = {"row_ids": support["training_row_ids"].copy(),
             "embedding": [basis.copy() for _ in range(36)] + [other],
             "position_m": [2.0] * 36 + [100.0]}
    query = {"row_ids": support["query_row_ids"].copy(),
             "embedding": [basis.copy() for _ in range(2000)]}
    # One last-row error of 2000 makes mean=1 and median=0. Omitting that row
    # silently creates a perfect score, exercising the exact historical mismatch.
    targets = {"row_ids": support["query_row_ids"].copy(),
               "position_m": [2.0] * 1999 + [2002.0]}
    return support, train, query, targets


class EndpointTests(unittest.TestCase):
    def test_independent_closed_form_and_last_row(self):
        support, train, query, targets = fixture()
        result = m.score(support, train, query, targets)
        self.assertEqual(result["score"]["samples"], 2000)
        self.assertEqual(result["score"]["mean_absolute_error_m"], 1.0)
        self.assertEqual(result["score"]["absolute_error_sd_population_m"], math.sqrt(1999))
        self.assertEqual(result["score"]["absolute_error_sd_sample_m"], math.sqrt(2000))
        self.assertFalse(result["historical_source_support_verified"])
        self.assertIsNone(result["scientific_improvement_awarded"])

    def test_query_targets_cannot_enter_decoder(self):
        support, train, query, targets = fixture()
        query["position_m"] = targets["position_m"]
        with self.assertRaisesRegex(ValueError, "query input"):
            m.decode(support, train, query)

    def test_wrong_support_and_order_rejected(self):
        for mutation in ("1999", "reordered", "overlap", "duplicate", "unit", "animal"):
            support, train, query, targets = fixture()
            if mutation == "1999":
                support["query_row_ids"].pop()
            elif mutation == "reordered":
                targets["row_ids"][0], targets["row_ids"][1] = targets["row_ids"][1], targets["row_ids"][0]
            elif mutation == "overlap":
                support["query_row_ids"][0] = support["training_row_ids"][0]
            elif mutation == "duplicate":
                support["query_row_ids"][0] = support["query_row_ids"][1]
            elif mutation == "unit":
                support["unit"] = "cm"
            else:
                support["animal"] = "all-four-rats"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                m.error_summary(support, [2.0] * 2000, targets)

    def test_invalid_embedding_shapes_values_and_order(self):
        for mutation in ("3d", "nan", "bool", "reordered"):
            support, train, query, targets = fixture()
            if mutation == "3d":
                query["embedding"][0] = [0, 1, 2]
            elif mutation == "nan":
                query["embedding"][0][0] = float("nan")
            elif mutation == "bool":
                train["position_m"][0] = True
            else:
                query["row_ids"][0], query["row_ids"][1] = query["row_ids"][1], query["row_ids"][0]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                m.decode(support, train, query)

    def test_decoder_uses_cosine_not_euclidean_or_all_points(self):
        support, train, query, _ = fixture()
        # Huge collinear vectors remain the nearest in cosine distance.
        for row in train["embedding"][:36]:
            row[0] = 1000.0
        self.assertEqual(m.decode(support, train, query), [2.0] * 2000)

    def test_json_cli_pins_inputs_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            args = []
            for name, value in zip(("support", "training", "query", "targets"), fixture()):
                path = Path(directory) / (name + ".json")
                path.write_text(json.dumps(value))
                args += ["--" + name, str(path)]
            pin = m.sha256((Path(directory) / "support.json").read_bytes())
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(m.main(args + ["--support-sha256", pin]), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["score"]["mean_absolute_error_m"], 1)
            self.assertEqual(set(result["input_pins"]), {"support", "training", "query", "targets"})
            self.assertNotIn("position_m", result)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(args + ["--support-sha256", "b" * 64]), 1)

    def test_json_duplicate_keys_and_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"x": 1, "x": 2}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                m.read_json(path, 1024)
            with self.assertRaisesRegex(ValueError, "byte bound"):
                m.read_json(path, 1)


if __name__ == "__main__":
    unittest.main()

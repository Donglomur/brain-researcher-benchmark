"""Bounded generated controls. No authentic observations or imputation model calls."""
import ast
import contextlib
import copy
import importlib.util
import io
import logging
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("endpoint", ROOT / "endpoint.py")
endpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(endpoint)


def generated_data():
    rng = np.random.default_rng(817)
    train = rng.normal(size=(14, 6, 8)).astype(np.float32)
    test = rng.normal(size=(8, 6, 8)).astype(np.float32)
    labels = np.array([0, 1] * 7)
    test_labels = np.array([0, 1] * 4)
    train[:, :, 0] += labels[:, None] * 3
    test[:, :, 0] += test_labels[:, None] * 3
    return {
        "train_z": train, "test_z": test, "train_labels": labels, "test_labels": test_labels,
        "train_row_ids": np.array([f"train{i}" for i in range(14)]),
        "test_row_ids": np.array([f"test{i}" for i in range(8)]),
        "native_row_ids": np.array([f"train{i}" for i in range(14)] + [f"test{i}" for i in range(8)]),
        "native_days": np.array([1] * 7 + [2] * 7 + [7] * 8),
        "train_mean": np.linspace(-1, 1, 6), "train_scale": np.linspace(0.5, 2, 6),
        "author_ddpm": rng.normal(size=test.shape).astype(np.float32),
        "deterministic_nn": test * 0.5, "candidate": test.copy(),
        "source_sha256": np.array("a" * 64),
    }


def generated_receipts():
    records = []
    for participant in endpoint.PARTICIPANTS:
        for dropout in endpoint.DROPOUTS:
            for repeat in endpoint.REPEATS:
                _, chosen = endpoint.observed_channels(10, dropout, repeat)
                records.append({
                    "schema": endpoint.SCHEMA, "source_revision": endpoint.SOURCE_REVISION,
                    "kind": "generated_control", "participant": participant, "dropout": dropout, "repeat": repeat,
                    "source_sha256": "a" * 64, "input_sha256": "b" * 64,
                    "preparation_sha256": "b" * 64,
                    "train_row_order_sha256": "c" * 64, "test_row_order_sha256": "d" * 64,
                    "native_day_order_sha256": "e" * 64, "train_days": [1, 2], "test_day": 7,
                    "channels": 10, "samples_per_event": 8, "test_events": 10,
                    "software": {"numpy": "generated", "scikit_learn": "generated"},
                    "observed_channels_choice_order": chosen.tolist(),
                    "folds": [{"fold": fold, "rf_seed": fold, "test_events": 10, "train_events": 8,
                               "train_row_order_sha256": endpoint.digest_json([participant, repeat, fold]),
                               "correct": {"fully_observed": 9, "mean_imputation": 1 + repeat,
                                           "author_ddpm": 5 + repeat, "deterministic_nn": 7, "candidate": 8}}
                              for fold in range(3)],
                })
    return records


class SourceEndpointTests(unittest.TestCase):
    def test_source_day_order_and_remainder_rows(self):
        train, test = endpoint.source_day_indices([3, 1, 2, 1, 3, 2, 7, 7])
        self.assertEqual(train.tolist(), [1, 3, 2, 5, 0, 4])
        self.assertEqual(test.tolist(), [6, 7])
        permutation = np.random.default_rng(2).permutation(8)
        folds = endpoint.training_partitions(8, 2)
        for index, retained in enumerate(folds):
            expected = sorted(set(range(8)) - set(permutation[index * 2:index * 2 + 2]))
            self.assertEqual(retained.tolist(), expected)
        self.assertEqual(set.intersection(*(set(x) for x in folds)), set(permutation[6:]))
        for length in (0, 1, 2):
            with self.assertRaises(ValueError):
                endpoint.training_partitions(length, 0)

    def test_inverse_transform_flatten_and_observed_invariance(self):
        observed = np.array([True, False])
        test = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.float32)
        imputers = {arm: np.full_like(test, 8) for arm in endpoint.IMPUTERS}
        result = endpoint.decoder_inputs(test, [10, 20], [2, 3], imputers, observed)
        np.testing.assert_array_equal(result["fully_observed"], [[12, 14, 16, 32, 35, 38]])
        np.testing.assert_array_equal(result["mean_imputation"], [[12, 14, 16, 20, 20, 20]])
        np.testing.assert_array_equal(result["candidate"], [[12, 14, 16, 44, 44, 44]])
        self.assertEqual(result["candidate"].dtype, np.float32)
        imputers["candidate"][:, 0] = -10000
        np.testing.assert_array_equal(endpoint.decoder_inputs(test, [10, 20], [2, 3], imputers, observed)["candidate"], result["candidate"])
        del imputers["deterministic_nn"]
        with self.assertRaises(ValueError):
            endpoint.decoder_inputs(test, [10, 20], [2, 3], imputers, observed)

    def test_source_function_numerical_parity(self):
        """Run unchanged pinned author function with supplied generated imputations.

        The sampling callback returns an array; it never invokes a diffusion model.
        RF implementation/parameters and float32 tensor arithmetic are real.
        """
        import torch
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        torch.set_num_threads(1)
        data = generated_data()
        source_path = ROOT / "source" / "ajile_imputation_experiment.py"
        self.assertEqual(endpoint.digest_file(source_path), "17280ce42d3c39172bba568bf9fe5fc6e4126e88333d819f2446187a9f8915fa")
        module = ast.parse(source_path.read_text())
        function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "conditional_ajile_imputation_experiment")
        calls = []

        def samples(**kwargs):
            calls.append(kwargs["cond"].clone())
            return torch.from_numpy(data["author_ddpm"])

        scope = {"np": np, "torch": torch, "RandomForestClassifier": RandomForestClassifier,
                 "accuracy_score": accuracy_score, "generate_samples": samples,
                 "repeat": lambda tensor, pattern, b: tensor.unsqueeze(0).repeat(b, 1, 1),
                 "log": logging.getLogger("source_oracle")}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec"), scope)

        class Dataset:
            dataset = None

            def __init__(self, part):
                self.part = part
                self.dataset = self

            def __iter__(self):
                return iter({"signal": torch.from_numpy(x), "label": torch.tensor([y], dtype=torch.float32)}
                            for x, y in zip(data[self.part + "_z"], data[self.part + "_labels"]))

            def get_train_mean_and_std(self):
                return (torch.tensor(data["train_mean"], dtype=torch.float32)[None, :, None],
                        torch.tensor(data["train_scale"], dtype=torch.float32)[None, :, None])

        with contextlib.redirect_stdout(io.StringIO()):
            expected = scope["conditional_ajile_imputation_experiment"](None, Dataset("train"), Dataset("test"), mask_seed=2, percent_dropout_channels=0.7)
        actual = endpoint.evaluate_case(data, participant="EC01", dropout=0.7, repeat=2, input_digest="b" * 64, kind="generated_control")
        for arm, value in zip(("fully_observed", "mean_imputation", "author_ddpm"), expected):
            self.assertEqual(np.mean([fold["correct"][arm] / 8 for fold in actual["folds"]]), value)
        self.assertEqual(len(calls), 1)
        mask, _ = endpoint.observed_channels(6, 0.7, 2)
        np.testing.assert_array_equal(calls[0][:, :6].numpy(), np.broadcast_to(mask[None, :, None], (8, 6, 8)))
        self.assertEqual(actual["test_events"], 8)

    def test_input_mismatches_fail_before_fitting(self):
        args = dict(participant="EC01", dropout=0.5, repeat=0, input_digest="b" * 64, kind="generated_control")
        bad = generated_data()
        bad["test_labels"][0] = 2
        with self.assertRaisesRegex(ValueError, "binary"):
            endpoint.evaluate_case(bad, **args)
        bad = generated_data()
        bad["train_row_ids"] = bad["train_row_ids"][::-1]
        with self.assertRaisesRegex(ValueError, "source day-sorted"):
            endpoint.evaluate_case(bad, **args)
        with self.assertRaisesRegex(ValueError, "1001"):
            endpoint.evaluate_case(generated_data(), **{**args, "kind": "authentic_input"})
        bad = generated_data()
        bad["candidate"][0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            endpoint.evaluate_case(bad, **args)

    def test_full_panel_and_original_paired_errorbar(self):
        result = endpoint.aggregate_panel(generated_receipts())
        self.assertEqual(len(result["participant_dropout_cells"]), 36)
        self.assertEqual(result["fold_count"], 540)
        first = result["participant_dropout_cells"][0]
        self.assertAlmostEqual(first["mean_accuracy"]["candidate"], 0.8)
        self.assertAlmostEqual(first["accuracy_sd_over_repeats"]["candidate"], 0)
        self.assertAlmostEqual(first["source_figure_errorbar_paired_gain_sd"]["candidate"], np.sqrt(0.02))
        self.assertAlmostEqual(first["source_figure_errorbar_paired_gain_sd"]["author_ddpm"], 0)
        self.assertNotIn("overall", result)

    def test_panel_rejects_omissions_misalignment_and_bad_denominators(self):
        records = generated_receipts()
        for bad in (records[:-1], records[:-1] + [records[0]]):
            with self.assertRaises(ValueError):
                endpoint.aggregate_panel(bad)
        for field, value in (("test_row_order_sha256", "f" * 64), ("preparation_sha256", "f" * 64), ("kind", "authentic_input"), ("observed_channels_choice_order", [0]), ("test_events", 0)):
            bad = copy.deepcopy(records)
            bad[8][field] = value
            with self.assertRaises(ValueError):
                endpoint.aggregate_panel(bad)
        for field, value in (("train_row_order_sha256", "f" * 64), ("test_events", 9), ("rf_seed", 8)):
            bad = copy.deepcopy(records)
            bad[8]["folds"][0][field] = value
            with self.assertRaises(ValueError):
                endpoint.aggregate_panel(bad)
        for arm, count in (("candidate", 11), ("fully_observed", 8), ("candidate", True)):
            bad = copy.deepcopy(records)
            bad[8]["folds"][0]["correct"][arm] = count
            with self.assertRaises(ValueError):
                endpoint.aggregate_panel(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Generated-only MegNIST method/transport controls.

Run only through the approved generated-control runner. These controls never open authentic
input/reference/target payloads, instantiate a full MegNIST model, or establish
scientific performance or actual runtime isolation. Tiny fixtures are retained
under a fresh external temporary root, printed below, with an accounting receipt.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import weakref

import h5py
import numpy as np
import torch

C = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(C))

import author_route
import evaluate_private
import prediction_interface
import preflight
import summarize_reference

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"
# Retain failures without modifying the source checkout or counting older runs.
FIXTURE_ROOT = Path(tempfile.mkdtemp(prefix="megnist-generated-")).resolve()
RUN_DIR = FIXTURE_ROOT / f"generated-fixtures-{RUN_ID}"
FIXTURE_CAP = 3 * 1024 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_ids(rows):
    # Leading NULs deliberately expose accidental string conversion/truncation.
    values = np.zeros((rows, 16), dtype=np.uint8)
    values[:, -1] = np.arange(1, rows + 1, dtype=np.uint8)
    return values


def features(rows=8):
    if rows != 8:
        return (np.arange(rows * 6, dtype=np.float32).reshape(rows, 2, 3) / 7).astype(np.float32)
    values = np.arange(48, dtype=np.float32).reshape(8, 6)
    values[:, 0] = 7  # Exact constant column: source std becomes 1.
    values[:, 1] = np.arange(8, dtype=np.float32)  # Population variance 5.25.
    values[:, 2] = np.asarray([1e8, 1, -1e8, 3, 1e-5, -3, 2e8, -2e8], dtype=np.float32)
    return values.reshape(8, 2, 3)


def write_h5(path, *, data=None, ids=None, labels=None, original_row=None, attributes=None):
    with h5py.File(path, "x") as handle:
        for name, value in (("data", data), ("case_ids", ids), ("labels", labels), ("original_row", original_row)):
            if value is not None:
                handle.create_dataset(name, data=value)
        for name, value in (attributes or {}).items():
            handle.attrs[name] = value
    return Path(path)


def no_values_equal(case, left, right, message):
    case.assertTrue(np.array_equal(left, right), message)


def setUpModule():
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    print(json.dumps({"retained_generated_fixture_root": str(FIXTURE_ROOT)}), flush=True)
    torch.set_default_dtype(torch.float32)
    torch.set_default_device("cpu")


def tearDownModule():
    files = []
    for path in sorted(RUN_DIR.rglob("*")):
        if path.is_file():
            info = path.stat()
            files.append({"path": str(path.relative_to(RUN_DIR)), "bytes": info.st_size,
                          "allocated_bytes": info.st_blocks * 512, "sha256": sha(path)})
    receipt = {
        "scope": "Retained deterministic generated fixtures only; no authentic input/target/model artifacts",
        "run_id": RUN_ID,
        "accounting_scope": "This invocation's fresh retained fixture root only",
        "files_before_receipt": files,
        "logical_bytes_before_receipt": sum(item["bytes"] for item in files),
        "conservative_allocated_charge_before_receipt": sum(max(item["bytes"], item["allocated_bytes"]) for item in files),
        "receipt_allowance_bytes": 65536,
        "failure_preservation": "Fixtures and pool results are retained even if assertions fail; no fixture deletion is performed.",
        "scientific_qualification": False,
        "actual_runtime_isolation_qualified": False,
    }
    destination = RUN_DIR / "FIXTURE_ACCOUNTING.json"
    destination.write_text(json.dumps(receipt, indent=2) + "\n")
    cumulative = 0
    for directory in FIXTURE_ROOT.glob("generated-fixtures-*"):
        for path in directory.rglob("*"):
            if path.is_file():
                info = path.stat()
                cumulative += max(info.st_size, info.st_blocks * 512)
    if cumulative > FIXTURE_CAP:
        raise AssertionError("Generated fixture accounting exceeded the 3 MiB invocation cap")


class GeneratedCase(unittest.TestCase):
    def setUp(self):
        self.root = RUN_DIR / self._testMethodName
        self.root.mkdir()

    def labeled(self, filename="train.h5", data=None, labels=None):
        data = features() if data is None else data
        labels = np.zeros(len(data), dtype=np.int32) if labels is None else labels
        return write_h5(self.root / filename, data=data, ids=case_ids(len(data)), labels=labels)

    def tiny_fit_inputs(self):
        source = author_route.load_author_source()
        train_data = features()
        val_data = (features(4) + np.float32(0.125)).astype(np.float32)
        stats_input = write_h5(self.root / "generated-statistics-input.h5", data=train_data)
        mean, std = source.compute_dataset_statistics(stats_input)
        source.set_all_seeds(47)
        initial = source.SimpleMLP(6, 2, num_classes=10)
        initial.eval()
        with torch.no_grad():
            train_labels = initial(torch.FloatTensor((train_data.reshape(8, -1) - mean) / std)).argmax(1).numpy().astype(np.int32)
            val_labels = initial(torch.FloatTensor((val_data.reshape(4, -1) - mean) / std)).argmax(1).numpy().astype(np.int32)
        train = self.labeled(data=train_data, labels=train_labels)
        val = self.labeled("val.h5", data=val_data, labels=val_labels)
        norm = author_route.normalization_for_training(train, expected_train_sha256=sha(train))
        return source, train, val, norm

    def tiny_fit(self, train, val, norm):
        with contextlib.redirect_stdout(io.StringIO()):
            return author_route.fit_reference_run(
                train, val, expected_train_sha256=sha(train), expected_val_sha256=sha(val),
                normalization=norm, hidden_size=2, seed=47, device="cpu", batch_size=2,
                max_epochs=3, learning_rate=0.001, patience=2, num_workers=0)


class NormalizationAndFitControls(GeneratedCase):
    def test_exact_ordered_welford_population_variance_and_cast(self):
        train = self.labeled()
        source = author_route.load_author_source()
        expected_mean, expected_std = source.compute_dataset_statistics(train, batch_size=1000)
        actual = author_route.normalization_for_training(train, expected_train_sha256=sha(train))
        no_values_equal(self, actual["mean"], expected_mean, "Mean differs from exact ordered source arithmetic")
        no_values_equal(self, actual["std"], expected_std, "Std differs from exact ordered source arithmetic")
        self.assertEqual(actual["mean"].dtype, np.dtype("float64"))
        self.assertEqual(actual["mean"][0], 7)
        self.assertEqual(actual["std"][0], 1)
        self.assertEqual(actual["mean"][1], 3.5)
        self.assertEqual(actual["std"][1], np.sqrt(5.25))
        self.assertFalse(actual["mean"].flags.writeable)
        self.assertFalse(actual["std"].flags.writeable)
        source_dataset = source.HDF5Dataset(train, actual["mean"], actual["std"])
        tensor, _ = source_dataset[3]
        independent = torch.FloatTensor((features()[3].flatten() - expected_mean) / expected_std)
        self.assertEqual(tensor.dtype, torch.float32)
        self.assertTrue(torch.equal(tensor, independent), "Source row normalization/cast changed")

    def test_cache_pin_reuse_and_changed_training_refusal(self):
        train = self.labeled()
        cache = self.root / "normalization.npz"
        result = author_route.normalization_for_training(train, expected_train_sha256=sha(train), cache_path=cache)
        pin = result["cache"]["provenance_sha256"]
        with self.assertRaises(ValueError):
            author_route.normalization_for_training(train, expected_train_sha256=sha(train), cache_path=cache)
        reused = author_route.normalization_for_training(
            train, expected_train_sha256=sha(train), cache_path=cache, expected_cache_provenance_sha256=pin)
        no_values_equal(self, result["mean"], reused["mean"], "Pinned cache changed normalization")
        check = preflight.validate_normalization_cache(
            cache, expected_provenance_sha256=pin, expected_train_sha256=sha(train))
        self.assertFalse(check["training_arrays_read"])
        self.assertFalse(check["numeric_vectors_verified"])
        changed = self.labeled("changed-train.h5", data=features() + np.float32(1))
        with self.assertRaises(ValueError):
            author_route.normalization_for_training(changed, expected_train_sha256=sha(train))
        # Even the correct new input hash cannot authorize reuse of old stats.
        with self.assertRaises(ValueError):
            author_route.normalization_for_training(
                changed, expected_train_sha256=sha(changed), cache_path=cache,
                expected_cache_provenance_sha256=pin)

    def test_cache_array_and_in_memory_provenance_tamper_refusal(self):
        train = self.labeled()
        val = self.labeled("val.h5", data=features(4))
        cache = self.root / "normalization.npz"
        result = author_route.normalization_for_training(train, expected_train_sha256=sha(train), cache_path=cache)
        damaged = self.root / "damaged-cache.npz"
        np.savez_compressed(damaged, mean=result["mean"] + 1, std=result["std"])
        Path(str(damaged) + ".json").write_bytes(Path(str(cache) + ".json").read_bytes())
        with self.assertRaises(ValueError):
            author_route.normalization_for_training(
                train, expected_train_sha256=sha(train), cache_path=damaged,
                expected_cache_provenance_sha256=result["cache"]["provenance_sha256"])
        bad = dict(result)
        bad["mean"] = result["mean"] + 1
        with self.assertRaises(ValueError):
            self.tiny_fit(train, val, bad)

    def test_tiny_fit_matches_actual_author_loader_and_training_route(self):
        source, train, val, norm = self.tiny_fit_inputs()
        actual = self.tiny_fit(train, val, norm)
        # Actual source make_loaders is the oracle. Its tiny test loader is
        # constructed but never iterated, preserving the source fit prefix.
        train_loader, val_loader, _, input_size = source.make_loaders(
            {"train": train, "val": val, "test": val}, norm["mean"], norm["std"],
            batch_size=2, seed=47, num_workers=0)
        source.set_all_seeds(47)
        expected_model = source.SimpleMLP(input_size, 2, num_classes=10).to(torch.device("cpu"))
        with contextlib.redirect_stdout(io.StringIO()):
            expected = source.train_model(expected_model, train_loader, val_loader, torch.device("cpu"),
                                          max_epochs=3, learning_rate=0.001, patience=2)
        for name, value in expected["model"].state_dict().items():
            self.assertTrue(torch.equal(value, actual["model"].state_dict()[name]), f"Source state tensor differs: {name}")
        for key in ("best_val_acc", "best_epoch", "train_accs", "val_accs"):
            self.assertEqual(actual["metadata"][key], expected[key], f"Source fit metadata differs: {key}")
        self.assertFalse(actual["model"].training)
        self.assertTrue(all(not parameter.requires_grad for parameter in actual["model"].parameters()))
        self.assertFalse(actual["metadata"]["scientific_qualification"])
        self.assertTrue(actual["metadata"]["no_test_evaluation_path_executed"])
        self.assertTrue(actual["metadata"]["input_roles_require_preflight"])
        self.assertFalse(actual["metadata"]["test_result_emitted"])
        self.assertFalse(actual["metadata"]["complete_reference_scope_validated"])

    def test_strict_validation_improvement_restores_first_best_state(self):
        source, train, val, norm = self.tiny_fit_inputs()
        train_loader, val_loader, _, n_features = source.make_loaders(
            {"train": train, "val": val, "test": val}, norm["mean"], norm["std"],
            batch_size=2, seed=47, num_workers=0)
        source.set_all_seeds(47)
        model = source.SimpleMLP(n_features, 2, num_classes=10)
        snapshots = []
        schedule = [50.0, 50.0, 25.0]

        def controlled_validation(current, loader, device):
            snapshots.append({name: value.detach().clone() for name, value in current.state_dict().items()})
            return schedule[len(snapshots) - 1]

        with mock.patch.object(source, "accuracy", side_effect=controlled_validation), contextlib.redirect_stdout(io.StringIO()):
            result = source.train_model(model, train_loader, val_loader, torch.device("cpu"),
                                        max_epochs=3, learning_rate=0.001, patience=10)
        self.assertEqual(result["best_epoch"], 0)
        self.assertEqual(result["best_val_acc"], 50)
        self.assertEqual(result["val_accs"], schedule)
        self.assertEqual(len(snapshots), 3)
        for name, value in snapshots[0].items():
            self.assertTrue(torch.equal(value, result["model"].state_dict()[name]), "Best state was not restored")

    def test_source_zero_validation_failure_is_not_silently_repaired(self):
        source, train, val, norm = self.tiny_fit_inputs()
        with mock.patch.object(source, "accuracy", return_value=0.0), self.assertRaises(RuntimeError):
            self.tiny_fit(train, val, norm)


class ReferenceSelectionControls(GeneratedCase):
    @staticmethod
    def records():
        rows = []
        widths = [32, 64, 128, 256, 512, 1024, 2048]
        for width in widths:
            for index, seed in enumerate(range(42, 52)):
                validation = float(70 + 2 * index) if width == 128 else float(10 + index)
                tests = [40, 41, 42, 43, 50, 10, 44, 45, 46, 47]
                rows.append({"hidden_size": width, "seed": seed, "val_acc": validation,
                             "test_acc": float(tests[index]) if width == 128 else float(99 - index)})
        return rows

    def test_complete_reference_mean_validation_and_posthoc_source_parity(self):
        records = self.records()
        actual = summarize_reference.summarize_reference(list(reversed(records)))
        source = author_route.load_author_source()
        grid = {width: [row for row in records if row["hidden_size"] == width]
                for width in [32, 64, 128, 256, 512, 1024, 2048]}
        selected_width, selected_seed, seed_index = source.choose_representative(grid, list(range(42, 52)))
        self.assertEqual(actual["selected_width"], selected_width)
        self.assertEqual(selected_width, 128)
        representative = actual["posthoc_representative"]
        self.assertEqual(representative["seed"], selected_seed)
        self.assertEqual(representative["seed_index"], seed_index)
        self.assertTrue(representative["used_test_tiebreak"])
        self.assertFalse(representative["eligible_candidate_selection"])
        self.assertFalse(actual["candidate_grid_required"])
        self.assertFalse(actual["scientific_qualification"])
        self.assertFalse(actual["runtime_isolation_qualified"])
        self.assertEqual(actual["reproduction_status"], "unknown")
        self.assertEqual(actual["improvement_status"], "unknown")
        self.assertEqual(len(actual["records"]), 70)

    def test_test_tiebreak_does_not_select_width_and_width_tie_uses_source_order(self):
        records = self.records()
        original = summarize_reference.summarize_reference(records)
        changed = [dict(row) for row in records]
        for row in changed:
            if row["hidden_size"] == 128 and row["seed"] in (46, 47):
                row["test_acc"] = 10.0 if row["seed"] == 46 else 50.0
        updated = summarize_reference.summarize_reference(changed)
        self.assertEqual(original["selected_width"], updated["selected_width"])
        self.assertNotEqual(original["posthoc_representative"]["seed"], updated["posthoc_representative"]["seed"])
        tied = [dict(row, val_acc=50.0, test_acc=99.0 if row["hidden_size"] == 2048 else 1.0)
                for row in records]
        self.assertEqual(summarize_reference.summarize_reference(list(reversed(tied)))["selected_width"], 32)

    def test_reference_scope_and_numeric_refusals(self):
        records = self.records()
        mutations = [records[:-1], records + [dict(records[0])]]
        extra = [dict(row) for row in records]
        extra[-1]["hidden_size"] = 4096
        mutations.append(extra)
        for key, value in (("seed", True), ("val_acc", float("nan")), ("test_acc", 101.0), ("test_acc", float("inf"))):
            changed = [dict(row) for row in records]
            changed[0][key] = value
            mutations.append(changed)
        for index, changed in enumerate(mutations):
            with self.subTest(case=index), self.assertRaises(ValueError):
                summarize_reference.summarize_reference(changed)


class PredictionAndPrivateScoreControls(GeneratedCase):
    @staticmethod
    def logits():
        values = np.zeros((5, 10), dtype=np.float32)
        values[np.arange(5), np.arange(5)] = 3
        values[0, 1] = 3  # Native argmax tie must choose class0.
        return values

    def prediction_payload(self):
        scores = self.logits()
        return {"case_ids": case_ids(5), "logits": scores,
                "predictions": scores.argmax(1).astype(np.int64), "model_state_sha256": "0" * 64}

    def test_source_cast_and_all_case_prediction_transport(self):
        source = author_route.load_author_source()
        values = features(5)
        ids = case_ids(5)
        feature_path = write_h5(self.root / "test.h5", data=values, ids=ids)
        labeled_path = write_h5(self.root / "source-labeled-generated.h5", data=values, ids=ids,
                                labels=np.zeros(5, dtype=np.int32))
        mean = np.linspace(-0.2, 0.3, 6, dtype=np.float64)
        std = np.linspace(0.75, 1.75, 6, dtype=np.float64)
        source.set_all_seeds(49)
        model = source.SimpleMLP(6, 2, num_classes=10).eval()
        model.requires_grad_(False)
        frozen_hash = author_route.model_state_sha256(model)
        actual = prediction_interface.predict_h5(
            model, feature_path, mean, std, expected_model_state_sha256=frozen_hash,
            batch_size=2, device="cpu", expected_rows=5, expected_shape=(2, 3))
        source_dataset = source.HDF5Dataset(labeled_path, mean, std)
        expected_loader = source.DataLoader(
            source_dataset, batch_size=2, shuffle=False, num_workers=0,
            pin_memory=torch.cuda.is_available())
        with torch.no_grad():
            expected = np.concatenate([model(inputs).numpy() for inputs, _ in expected_loader])
        no_values_equal(self, actual["logits"], expected, "Feature-only export differs from source normalization/cast")
        no_values_equal(self, actual["case_ids"], ids, "Opaque IDs changed during export")
        self.assertEqual(actual["model_state_sha256"], frozen_hash)
        path = self.root / "predictions.h5"
        prediction_interface.write_predictions(path, actual)
        with h5py.File(path, "r") as handle:
            self.assertEqual(set(handle.keys()), {"case_ids", "logits", "predictions"})
            self.assertNotIn("labels", handle)
        restored = prediction_interface.read_predictions(path, expected_rows=5)
        no_values_equal(self, restored["logits"], actual["logits"], "Prediction bytes changed on transport")
        with self.assertRaises(FileExistsError):
            prediction_interface.write_predictions(path, actual)

    def test_fit_state_digest_handoff_and_pre_inference_mutation_refusal(self):
        _, train, val, norm = self.tiny_fit_inputs()
        fitted = self.tiny_fit(train, val, norm)
        feature_path = write_h5(self.root / "test.h5", data=features(4), ids=case_ids(4))
        digest = fitted["metadata"]["model_state_sha256"]
        self.assertEqual(digest, prediction_interface.model_state_sha256(fitted["model"]))
        accepted = prediction_interface.predict_h5(
            fitted["model"], feature_path, norm["mean"], norm["std"],
            expected_model_state_sha256=digest, expected_rows=4, expected_shape=(2, 3), batch_size=2)
        self.assertEqual(accepted["model_state_sha256"], digest)
        with torch.no_grad():
            next(fitted["model"].parameters()).add_(1)
        with mock.patch.object(fitted["model"], "forward", wraps=fitted["model"].forward) as call:
            with self.assertRaises(ValueError):
                prediction_interface.predict_h5(
                    fitted["model"], feature_path, norm["mean"], norm["std"],
                    expected_model_state_sha256=digest, expected_rows=4, expected_shape=(2, 3))
            call.assert_not_called()

    def test_private_id_join_argmax_tie_and_single_candidate_scope(self):
        payload = self.prediction_payload()
        labels = np.asarray([0, 1, 8, 3, 4], dtype=np.int32)
        order = np.asarray([4, 1, 3, 0, 2])
        result = evaluate_private.score_predictions(
            payload["case_ids"], payload["logits"], payload["case_ids"][order], labels[order], expected_rows=5)
        self.assertEqual(result["num_cases"], 5)
        self.assertEqual(result["correct_count"], 4)
        self.assertEqual(result["accuracy_percent"], 80.0)
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["runtime_isolation_qualified"])
        no_values_equal(self, result["predictions"], payload["predictions"][order], "Join used row position instead of raw ID")
        predictions = self.root / "predictions.h5"
        prediction_interface.write_predictions(predictions, payload)
        private = write_h5(self.root / "private.h5", ids=payload["case_ids"][order], labels=labels[order],
                           original_row=order.astype(np.uint32))
        alternate = write_h5(self.root / "private-other-rowmap.h5", ids=payload["case_ids"][order], labels=labels[order],
                             original_row=np.roll(order, 1).astype(np.uint32))
        first = evaluate_private.evaluate_files(predictions, private, expected_rows=5)
        second = evaluate_private.evaluate_files(predictions, alternate, expected_rows=5)
        self.assertEqual(first["accuracy_percent"], second["accuracy_percent"])
        no_values_equal(self, first["predictions"], second["predictions"], "original_row incorrectly determined case join")

    def test_case_membership_shape_dtype_and_logit_refusals(self):
        ids, scores = case_ids(5), self.logits()
        labels = np.arange(5, dtype=np.int32)
        duplicate = ids.copy()
        duplicate[1] = duplicate[0]
        extra = ids.copy()
        extra[-1, -1] = 99
        bad_ids = [ids.reshape(-1), ids[:, :15], ids.astype(np.uint16), duplicate]
        for index, value in enumerate(bad_ids):
            with self.subTest(ids=index), self.assertRaises(ValueError):
                prediction_interface.normalize_case_ids(value)
        no_values_equal(self, prediction_interface.normalize_case_ids(ids), ids, "Raw zero-containing identifiers changed")
        for target in (ids[:-1], duplicate, extra):
            with self.subTest(target_shape=target.shape), self.assertRaises(ValueError):
                evaluate_private.score_predictions(ids, scores, target, labels[:len(target)], expected_rows=5)
        nan = scores.copy()
        nan[0, 0] = np.nan
        infinite = scores.copy()
        infinite[0, 0] = np.inf
        for index, value in enumerate((scores[:, :9], scores[:-1], scores.astype(np.int32), nan, infinite)):
            with self.subTest(logits=index), self.assertRaises(ValueError):
                evaluate_private.score_predictions(ids, value, ids, labels, expected_rows=5)
        for invalid in (labels.astype(float), np.asarray([-1, 1, 2, 3, 4], dtype=np.int32), np.asarray([0, 1, 2, 3, 10], dtype=np.int32)):
            with self.subTest(labels_dtype=str(invalid.dtype)), self.assertRaises(ValueError):
                evaluate_private.score_predictions(ids, scores, ids, invalid, expected_rows=5)

    def test_prediction_artifact_rejects_labels_and_inconsistent_predictions(self):
        payload = self.prediction_payload()
        damaged = dict(payload, predictions=np.full(5, 9, dtype=np.int64))
        with self.assertRaises(ValueError):
            prediction_interface.write_predictions(self.root / "inconsistent.h5", damaged)
        path = self.root / "label-bearing-predictions.h5"
        prediction_interface.write_predictions(path, payload)
        with h5py.File(path, "r+") as handle:
            handle.create_dataset("labels", data=np.zeros(5, dtype=np.int32))
        with self.assertRaises(ValueError):
            prediction_interface.read_predictions(path, expected_rows=5)


class PreflightControls(GeneratedCase):
    def generated_manifest(self):
        records = {}
        for split, count in (("train", 8), ("val", 4), ("test", 5)):
            labels = None if split == "test" else np.zeros(count, dtype=np.int32)
            path = write_h5(self.root / f"{split}.h5", data=features(count), ids=case_ids(count), labels=labels)
            keys = ["data", "case_ids"] + ([] if split == "test" else ["labels"])
            records[split] = {"file": path.name, "rows": count, "datasets": keys,
                              "size": path.stat().st_size, "sha256": sha(path)}
        document = {"schema": "standalone_features_static_axes_v2", "generated_fixture": True,
                    "feature_shape": [2, 3], "splits": records}
        path = self.root / "manifest.json"
        path.write_text(json.dumps(document, sort_keys=True) + "\n")
        return path

    def test_generated_metadata_and_headers_do_not_qualify_reference_or_isolation(self):
        path = self.generated_manifest()
        result = preflight.validate_input_manifest(
            path, profile="generated", expected_sha256=sha(path), root=self.root, inspect_files=True)
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["actual_isolation_qualified"])
        self.assertFalse(result["runtime_isolation_qualified"])
        self.assertFalse(result["authentic_reference_data_read"])
        self.assertTrue(result["file_identities_verified"])
        for split in result["splits"].values():
            self.assertFalse(split["header_check"]["array_values_read"])
            self.assertFalse(split["header_check"]["case_id_uniqueness_verified"])
        with self.assertRaises(ValueError):
            preflight.validate_input_manifest(path, profile="reference", inspect_files=False)
        with self.assertRaises(ValueError):
            preflight.validate_input_manifest(path, profile="generated", expected_sha256="0" * 64)
        separation = preflight.check_path_separation(self.root / "candidate", self.root / "private")
        self.assertTrue(separation["declared_roots_disjoint"])
        self.assertFalse(separation["actual_isolation_qualified"])
        with self.assertRaises(ValueError):
            preflight.check_path_separation(self.root, self.root / "private")

    def test_candidate_test_header_refusals_and_source_identity(self):
        valid = write_h5(self.root / "valid.h5", data=features(5), ids=case_ids(5))
        good = preflight.inspect_candidate_h5(valid, split="test", expected_rows=5, feature_shape=(2, 3))
        self.assertFalse(good["actual_isolation_qualified"])
        for name, kwargs in (
            ("labels", {"labels": np.zeros(5, dtype=np.int32)}),
            ("attrs", {"attributes": {"private_provenance": "generated-only"}}),
            ("shape", {"ids": case_ids(5)[:, :15]}),
            ("dtype", {"ids": case_ids(5).astype(np.uint16)}),
            ("feature-dtype", {"data": features(5).astype(np.float64)}),
        ):
            values = {"data": features(5), "ids": case_ids(5)}
            values.update(kwargs)
            path = write_h5(self.root / f"invalid-{name}.h5", **values)
            with self.subTest(case=name), self.assertRaises(ValueError):
                preflight.inspect_candidate_h5(path, split="test", expected_rows=5, feature_shape=(2, 3))
        linked = self.root / "soft-linked.h5"
        with h5py.File(linked, "x") as handle:
            handle.create_dataset("data", data=features(5))
            handle["case_ids"] = h5py.SoftLink("/data")
        with self.assertRaises(ValueError):
            preflight.inspect_candidate_h5(linked, split="test", expected_rows=5, feature_shape=(2, 3))
        source = self.root / "generated-source.txt"
        source.write_text("Generated non-executable source identity fixture.\n")
        self.assertFalse(preflight.verify_source_identity(source, sha(source))["scientific_qualification"])
        with self.assertRaises(ValueError):
            preflight.verify_source_identity(source, "0" * 64)


class MockedPanelRoutingControls(GeneratedCase):
    """Control flow only: every scientific/input dependency is replaced.

    Metadata uses the declared full-reference cardinality, but no such array
    exists. Each fake model is a plain Python object, never a Torch model.
    All file operations are restricted to this generated test directory.
    """

    def mocked_panel(self, fail_at=None):
        accepted_manifest = "ec53db9a60779e01ee05496833418355151781afff7b02f9db20a879029ace02"
        accepted_join = "98b85d94724611df9e79b821bf0fadc1a8af54b239c4db70de180307a5bddf36"
        candidate = self.root / "generated-candidate"
        private = self.root / "generated-private"
        candidate.mkdir()
        private.mkdir()
        manifest = candidate / "manifest.json"
        manifest.write_text('{"generated_mock_orchestration_only": true}\n')
        split_paths = {}
        for split in ("train", "val", "test"):
            path = candidate / f"{split}.h5"
            path.write_text(f"Generated MOCK {split} placeholder; not an HDF5 payload.\n")
            split_paths[split] = path
        join = private / "mock-private-join.h5"
        join.write_text("Generated MOCK private-join placeholder; contains no targets.\n")
        output = private / "mocked-reference-output"
        events, fit_calls, model_refs, normalization_calls, summary_calls = [], [], [], [], []
        predictions_by_path = {}
        tokens_by_digest = {}
        verified_inputs = {
            "manifest_sha256": accepted_manifest, "feature_shape": [306, 250],
            "file_identities_verified": True, "header_shapes_verified": True,
            "generated_mock_orchestration_only": True,
            "splits": {split: {"path": str(path), "rows": 10000 if split == "train" else 1000,
                               "sha256": sha(path)} for split, path in split_paths.items()},
        }

        def confined(path):
            value = Path(path).resolve()
            if value != self.root and self.root not in value.parents:
                raise AssertionError("Mocked orchestration tried a path outside generated fixtures")
            return value

        def safe_hash(path):
            return sha(confined(path))

        def fake_verified(path, expected, name):
            value = confined(path)
            if value == join:
                self.assertEqual(expected, accepted_join)
            else:
                self.assertEqual(safe_hash(value), expected, "Generated artifact identity mismatch")
            return value

        def fake_source(path, expected):
            self.assertEqual(Path(path), author_route.AUTHOR_PATH)
            self.assertEqual(expected, author_route.AUTHOR_SHA256)
            return {"generated_mock_source_check_only": True, "scientific_qualification": False}

        def fake_separation(left, right):
            self.assertEqual(confined(left), candidate)
            self.assertIn(confined(right), (private, output))
            return {"actual_isolation_qualified": False, "generated_mock_only": True}

        def fake_preflight(path, **kwargs):
            self.assertEqual(confined(path), manifest)
            self.assertEqual(kwargs, {"profile": "reference", "expected_sha256": accepted_manifest,
                                      "root": candidate, "inspect_files": True, "feature_shape": (306, 250)})
            return verified_inputs

        def fake_normalization(path, **kwargs):
            self.assertEqual(confined(path), split_paths["train"])
            self.assertEqual(kwargs["expected_train_sha256"], verified_inputs["splits"]["train"]["sha256"])
            self.assertIsNone(kwargs["expected_cache_provenance_sha256"])
            cache = confined(kwargs["cache_path"])
            self.assertEqual(cache, output / "training_standardisation.npz")
            cache.write_text("Generated MOCK normalization cache; no numeric training statistics.\n")
            sidecar = Path(str(cache) + ".json")
            sidecar.write_text('{"generated_mock_orchestration_only": true}\n')
            normalization_calls.append(path)
            events.append(("normalize",))
            return {"mean": np.zeros(1, dtype=np.float64), "std": np.ones(1, dtype=np.float64),
                    "provenance": {"generated_mock_orchestration_only": True},
                    "cache": {"data_path": str(cache), "provenance_path": str(sidecar),
                              "data_sha256": safe_hash(cache), "provenance_sha256": safe_hash(sidecar)}}

        class FakeFrozenModel:
            def __init__(model, token):
                model.token = token
                model.digest = hashlib.sha256(f"generated-mock-model:{token}".encode()).hexdigest()

            def __del__(model):
                metadata = output / f"width_{model.token[0]}_seed_{model.token[1]}" / "fit_and_private_score.json"
                events.append(("dispose", model.token, metadata.is_file()))

        def fake_fit(train, val, **kwargs):
            if model_refs:
                self.assertIsNone(model_refs[-1](), "Previous fake model was retained into the next fit")
            self.assertEqual(confined(train), split_paths["train"])
            self.assertEqual(confined(val), split_paths["val"])
            token = (kwargs["hidden_size"], kwargs["seed"])
            events.append(("fit", token))
            fit_calls.append(dict(kwargs))
            if fail_at is not None and len(fit_calls) - 1 == fail_at:
                raise RuntimeError("Generated deliberate mocked fit failure")
            model = FakeFrozenModel(token)
            model_refs.append(weakref.ref(model))
            tokens_by_digest[model.digest] = token
            metadata = {"hidden_size": token[0], "seed": token[1],
                        "source_sha256": author_route.AUTHOR_SHA256,
                        "train_sha256": verified_inputs["splits"]["train"]["sha256"],
                        "val_sha256": verified_inputs["splits"]["val"]["sha256"],
                        "model_state_sha256": model.digest, "best_val_acc": float(40 + token[1] - 42),
                        "best_epoch": 0, "generated_mock_orchestration_only": True}
            return {"model": model, "metadata": metadata, "normalization": kwargs["normalization"]}

        def fake_model_hash(model):
            self.assertIsInstance(model, FakeFrozenModel, "A real model reached mocked orchestration")
            return model.digest

        def fake_predict(model, path, mean, std, **kwargs):
            self.assertIsInstance(model, FakeFrozenModel)
            self.assertEqual(confined(path), split_paths["test"])
            self.assertEqual(kwargs, {"expected_model_state_sha256": model.digest, "batch_size": 32,
                                      "device": "cpu", "expected_rows": 1000, "expected_shape": (306, 250)})
            self.assertEqual(mean.shape, (1,))  # No authentic/full-feature array was created.
            self.assertEqual(std.shape, (1,))
            events.append(("predict", model.token))
            return {"model_state_sha256": model.digest, "generated_mock_orchestration_only": True}

        def fake_write(path, payload):
            value = confined(path)
            token = tokens_by_digest[payload["model_state_sha256"]]
            value.write_text("Generated MOCK prediction artifact; no model predictions.\n")
            predictions_by_path[value] = token
            events.append(("export", token))

        def fake_score(path, private_path, **kwargs):
            token = predictions_by_path[confined(path)]
            self.assertEqual(confined(private_path), join)
            self.assertEqual(kwargs, {"expected_rows": 1000})
            events.append(("score", token))
            count = 200 + token[1] - 42
            return {"num_cases": 1000, "correct_count": count, "accuracy_percent": 100.0 * count / 1000,
                    "generated_mock_orchestration_only": True}

        real_summary = summarize_reference.summarize_reference

        def fake_summary(records):
            self.assertEqual(len(records), 70, "Partial panel reached complete-summary construction")
            summary_calls.append(len(records))
            events.append(("summary",))
            return real_summary(records)  # Pure synthetic numeric metadata; no source/input access.

        fake_author = SimpleNamespace(torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
        patches = [
            (preflight, "verify_source_identity", fake_source),
            (preflight, "check_path_separation", fake_separation),
            (preflight, "validate_input_manifest", fake_preflight),
            (author_route, "_verified_file", fake_verified),
            (author_route, "file_sha256", safe_hash),
            (author_route, "load_author_source", lambda: fake_author),
            (author_route, "normalization_for_training", fake_normalization),
            (author_route, "fit_reference_run", fake_fit),
            (author_route, "model_state_sha256", fake_model_hash),
            (prediction_interface, "predict_h5", fake_predict),
            (prediction_interface, "write_predictions", fake_write),
            (evaluate_private, "evaluate_files", fake_score),
            (summarize_reference, "summarize_reference", fake_summary),
        ]
        result = None
        error = None
        with contextlib.ExitStack() as stack:
            for module, name, replacement in patches:
                stack.enter_context(mock.patch.object(module, name, new=replacement))
            try:
                result = author_route.run_reference_panel(
                    manifest, candidate_root=candidate, private_join_path=join,
                    expected_private_join_sha256=accepted_join, output_root=output)
            except RuntimeError as exc:
                if fail_at is None:
                    raise
                error = exc
        return {"result": result, "error": error, "output": output, "events": events,
                "fits": fit_calls, "models": model_refs, "normalizations": normalization_calls,
                "summaries": summary_calls}

    def test_mocked_complete70_orchestration_preserves_source_profile_and_disposal_order(self):
        observed = self.mocked_panel()
        expected = [(width, seed) for width in (32, 64, 128, 256, 512, 1024, 2048) for seed in range(42, 52)]
        self.assertEqual([(call["hidden_size"], call["seed"]) for call in observed["fits"]], expected)
        self.assertEqual(len(observed["normalizations"]), 1)
        self.assertEqual(observed["summaries"], [70])
        for call in observed["fits"]:
            self.assertEqual({key: call[key] for key in ("batch_size", "max_epochs", "learning_rate", "patience", "num_workers", "device")},
                             {"batch_size": 32, "max_epochs": 200, "learning_rate": 0.001,
                              "patience": 20, "num_workers": 0, "device": "cpu"})
        for token in expected:
            events = [entry for entry in observed["events"] if len(entry) > 1 and entry[1] == token]
            self.assertEqual([entry[0] for entry in events], ["fit", "predict", "export", "score", "dispose"])
            self.assertTrue(events[-1][2], "Fake model disposed before its private metadata was retained")
        self.assertTrue(all(reference() is None for reference in observed["models"]))
        result = observed["result"]
        self.assertEqual(result["execution_completed_cells"], 70)
        self.assertEqual(len(result["records"]), 70)
        self.assertFalse(result["optional_71st_checkpoint_refit_performed"])
        self.assertFalse(result["candidate_grid_required"])
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["runtime_isolation_qualified"])
        self.assertEqual(result["reproduction_status"], "unknown")
        self.assertTrue((observed["output"] / "COMPLETE_REFERENCE_PANEL.json").is_file())
        self.assertFalse((observed["output"] / "RUN_FAILED.json").exists())

    def test_mocked_partial_failure_retains_failure_without_complete_panel(self):
        observed = self.mocked_panel(fail_at=3)
        self.assertIsInstance(observed["error"], RuntimeError)
        self.assertIsNone(observed["result"])
        self.assertEqual(len(observed["fits"]), 4)
        self.assertEqual(len(observed["normalizations"]), 1)
        self.assertEqual(observed["summaries"], [])
        self.assertTrue(all(reference() is None for reference in observed["models"]))
        self.assertFalse((observed["output"] / "COMPLETE_REFERENCE_PANEL.json").exists())
        failure = json.loads((observed["output"] / "RUN_FAILED.json").read_text())
        self.assertEqual(failure["completed_cells"], 3)
        self.assertFalse(failure["complete_reference_panel"])
        self.assertFalse(failure["scientific_qualification"])
        self.assertEqual(failure["reproduction_status"], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)

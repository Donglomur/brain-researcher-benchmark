"""Generated endpoint controls; no authentic data or fitted model is used."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location("rat_oof_replay", Path(__file__).resolve().parents[1] / "replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def fixture(n=40):
    z = np.zeros((n + 1, 7))
    z[:, 2] = 5
    z[-1, 2] = 4  # Strict speed boundary, excluded before assigning folds.
    counts = np.column_stack([np.arange(n + 1) % 4, 1 + np.arange(n + 1) % 4,
                              np.zeros(n + 1), np.ones(n + 1)])
    counts[0, 2] = n * .05  # Exactly 0.1 Hz over moving rows, excluded.
    reference = {"latents": z, "counts": counts,
                 "bin_ids": np.array([f"bin:{i}" for i in range(n + 1)]),
                 "unit_ids": np.array(["ca1:a", "pfc:b", "rate:boundary", "other:c"]),
                 "locations": np.array(["CA1", "PFC", "CA1", "other"])}
    predictions = {"bin_ids": reference["bin_ids"][:n].copy(),
                   "unit_ids": reference["unit_ids"][:2].copy(),
                   "fold_ids": replay.source_fold_ids(n),
                   "predictions": np.full((n, 2), 2.0)}
    return reference, predictions


def save_manifest(directory, role, arrays):
    rows = []
    for animal in replay.source.ANIMALS:
        for session in range(8):
            path = directory / f"{role}-{animal}-{session}.npz"
            np.savez(path, **arrays)
            raw = path.read_bytes()
            rows.append({"animal": animal, "session_index": session, "epoch_id": f"native-epoch-{session}",
                         "path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return {"source_revision": replay.source.SOURCE_REVISION,
            "dandiset_version": "0.240511.0307", "sessions": rows}


class ReplayTests(unittest.TestCase):
    def test_original_ten_folds_match_independent_kfold(self):
        from sklearn.model_selection import KFold
        for n in (10, 11, 39, 40, 41, 109):
            actual = replay.source_fold_ids(n)
            for fold, (_, indices) in enumerate(KFold(10, shuffle=False).split(np.empty(n))):
                np.testing.assert_array_equal(np.flatnonzero(actual == fold), indices)
        for n in (0, 9, True, 10.0):
            with self.assertRaises(replay.ContractError):
                replay.source_fold_ids(n)

    def test_original_masks_units_and_no_geometry_subsampling(self):
        reference, predictions = fixture()
        result = replay.score_session(reference, predictions, predictions)
        self.assertEqual(result["retained_bin_count"], 40)
        self.assertEqual(result["source_row_indices"], list(range(40)))
        self.assertEqual(result["fold_bin_counts"], [4] * 10)
        self.assertEqual(set(result["regions"]), {"CA1", "PFC"})
        for region, identity in (("CA1", "ca1:a"), ("PFC", "pfc:b")):
            units = result["regions"][region]["units"]
            self.assertEqual(len(units), 1)  # Prediction endpoint has no PR minimum-19 requirement.
            self.assertEqual(units[0]["unit_id"], identity)
            self.assertEqual(units[0]["paired_fold_d2_difference"], [0.0] * 10)

    def test_byte_locations_preserve_exact_region_labels(self):
        reference, predictions = fixture()
        expected = replay.score_session(reference, predictions, predictions)
        reference["locations"] = reference["locations"].astype("S")
        self.assertEqual(replay.score_session(reference, predictions, predictions), expected)

    def test_fold_scores_match_sklearn_deviance_not_pooled_null(self):
        from sklearn.metrics import mean_poisson_deviance
        reference, author = fixture()
        # Different fold means make using the session null observably wrong.
        reference["counts"][:40, 0] += np.repeat(np.arange(10), 4)
        candidate = copy.deepcopy(author)
        candidate["predictions"] = np.maximum(reference["counts"][:40, :2], .25)
        result = replay.score_session(reference, author, candidate)
        for u, region in enumerate(("CA1", "PFC")):
            unit = result["regions"][region]["units"][0]
            for f in range(10):
                mask = author["fold_ids"] == f
                y = reference["counts"][:40, u][mask]
                null = mean_poisson_deviance(y, np.full(len(y), y.mean()))
                for role, packet in (("author", author), ("candidate", candidate)):
                    dev = mean_poisson_deviance(y, packet["predictions"][mask, u])
                    np.testing.assert_allclose(unit[role][f]["d2"], 1 - dev/null, rtol=1e-12, atol=2e-12)
        first = result["regions"]["CA1"]["units"][0]["author"][0]
        y = reference["counts"][:4, 0]
        wrong_null = mean_poisson_deviance(y, np.full(4, reference["counts"][:40, 0].mean()))
        self.assertNotAlmostEqual(first["d2"], 1 - first["model_deviance"]/wrong_null)

    def test_constant_fold_is_retained_as_nonfinite_not_replaced_or_dropped(self):
        reference, author = fixture()
        reference["counts"][:4, 0] = 2
        candidate = copy.deepcopy(author)
        candidate["predictions"][:4, 0] = 3
        unit = replay.score_session(reference, author, candidate)["regions"]["CA1"]["units"][0]
        self.assertEqual(unit["author"][0]["status"], "undefined_zero_over_zero")
        self.assertEqual(unit["candidate"][0]["status"], "negative_infinity")
        self.assertIsNone(unit["paired_fold_d2_difference"][0])
        self.assertEqual(unit["finite_paired_fold_count"], 9)
        reference["counts"][:4, 0] = 0
        unit = replay.score_session(reference, author, candidate)["regions"]["CA1"]["units"][0]
        self.assertEqual(unit["author"][0]["null_deviance"], 0.0)
        json.dumps(unit, allow_nan=False)

    def test_prediction_identity_population_folds_and_values_fail_closed(self):
        reference, prediction = fixture()
        changes = []
        for key in ("unit_ids", "bin_ids"):
            changed = copy.deepcopy(prediction)
            changed[key] = changed[key][::-1]
            changes.append(changed)
        changed = copy.deepcopy(prediction)
        changed["fold_ids"] = changed["fold_ids"][::-1]
        changes.append(changed)
        changed = copy.deepcopy(prediction)
        changed["predictions"] = changed["predictions"][:, :1]
        changes.append(changed)
        for value in (0, -1, np.nan, np.inf):
            changed = copy.deepcopy(prediction)
            changed["predictions"][0, 0] = value
            changes.append(changed)
        for index, changed in enumerate(changes):
            with self.subTest(change=index):
                with self.assertRaises(replay.ContractError):
                    replay.score_session(reference, prediction, changed)

    def test_nearly_perfect_deviance_is_nonnegative_and_overflow_is_rejected(self):
        y = np.array([[1.0, 3.0], [2.0, 7.0]])
        close = replay._mean_deviance(y, y * (1 + 1e-9))
        self.assertTrue(np.all(close >= 0))
        np.testing.assert_allclose(close, y.mean(axis=0) * 1e-18, rtol=1e-5)
        reference, prediction = fixture()
        prediction["predictions"][:] = 1e308
        with self.assertRaises(replay.ContractError):
            replay.score_session(reference, prediction, prediction)

    def test_full_paired_panel_cli_and_pins_without_fit_stubs(self):
        reference, predictions = fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            manifests = [save_manifest(directory, role, arrays) for role, arrays in
                         (("reference", reference), ("author", predictions), ("candidate", predictions))]
            paths = []
            for role, manifest in zip(("reference", "author", "candidate"), manifests):
                path = directory / f"{role}.json"
                path.write_text(json.dumps(manifest))
                paths.append(str(path))
            output = directory / "private-result.json"
            replay.main(paths + [str(output)])
            result = json.loads(output.read_text())
            self.assertEqual(len(result["sessions"]), 64)
            self.assertEqual(sum(len(r["regions"]) for r in result["sessions"]), 128)
            self.assertIsNone(result["population_d2"])
            self.assertFalse(any(result["qualification"].values()))
            with self.assertRaises(FileExistsError):
                replay.main(paths + [str(output)])
            missing = copy.deepcopy(manifests[2])
            missing["sessions"].pop()
            with self.assertRaises(replay.ContractError):
                replay.replay_panel(manifests[0], manifests[1], missing, [directory] * 3)
            changed = copy.deepcopy(manifests[2])
            changed["sessions"][0]["epoch_id"] = "different-epoch"
            with self.assertRaises(replay.ContractError):
                replay.replay_panel(manifests[0], manifests[1], changed, [directory] * 3)
            first = directory / manifests[2]["sessions"][0]["path"]
            first.write_bytes(first.read_bytes() + b"tamper")
            with self.assertRaises(replay.ContractError):
                replay.replay_panel(*manifests, [directory] * 3)


if __name__ == "__main__":
    unittest.main()

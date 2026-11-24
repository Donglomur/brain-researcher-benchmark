"""Generated full-panel controls only; no recordings, model fits or MATLAB."""

import copy
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("within_time_audit", Path(__file__).with_name("within_time_audit.py"))
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def partition(n, rotation):
    held = [list(range(i + 1, n + 1, 3)) for i in range(3)]
    held = held[rotation:] + held[:rotation]
    return [{"test_positions": row,
             "train_positions": [i for i in range(1, n + 1) if i not in row]} for row in held]


def fixture(n=5):
    sessions = {}
    for sid in audit.SESSIONS:
        sessions[sid] = {
            "n_trials": n, "class_order": list(range(1, 7)),
            "states": {
                state: {"unit_ids": ["unit_a", "unit_b"],
                        "trial_ids": [[f"{state}.class{label}.trial{i}" for i in range(1, n + 1)]
                                      for label in range(1, 7)],
                        "partitions": [[partition(n, (rep + window + state_index) % 3)
                                        for window in range(191)] for rep in range(5)]}
                for state_index, state in enumerate(audit.STATES)},
        }
    return {"schema": "horrocks-within-time-audit-manifest/v1", "task_id": audit.TASK,
            "source_commit": audit.SOURCE_COMMIT,
            "bindings": {name: "a" * 64 for name in (
                "observations_sha256", "eligibility_recipe_sha256", "source_class_mapping_sha256")},
            "sessions": sessions}


def header(manifest_sha="a" * 64):
    return {"schema": "horrocks-within-time-predictions/v1", "audit_manifest_sha256": manifest_sha,
            "method_sha256": "b" * 64, "condition": "paper_data"}


def records(manifest):
    # Independently derive held identities/counts instead of using audit's validator.
    for sid in audit.SESSIONS:
        for state in audit.STATES:
            item = manifest["sessions"][sid]["states"][state]
            for rep, windows in enumerate(item["partitions"], 1):
                for window, partition_folds in enumerate(windows, 1):
                    folds = []
                    for fold_index, fold in enumerate(partition_folds):
                        held = [[row[i - 1] for i in fold["test_positions"]] for row in item["trial_ids"]]
                        raw = json.dumps(held, sort_keys=True, separators=(",", ":")).encode()
                        # Different fold outcomes make equal-fold and pooled accuracy disagree.
                        predictions = [[label if fold_index == 0 else label % 6 + 1 for _ in row]
                                       for label, row in enumerate(held, 1)]
                        folds.append({"held_trial_order_sha256": hashlib.sha256(raw).hexdigest(),
                                      "predicted_classes": predictions})
                    yield {"session": sid, "state": state, "repeat": rep,
                           "time_index": window, "folds": folds}


class MemoryPath:
    def __init__(self, raw):
        self.raw = raw

    def open(self, mode):
        assert mode == "rb"
        return io.BytesIO(self.raw)


class WithinTimeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = fixture()

    def test_full_panel_equal_fold_mean_and_distinct_partitions(self):
        result = audit.reconstruct(self.manifest, "a" * 64, header(), records(self.manifest))
        self.assertEqual(result["record_count"], 9550)
        self.assertEqual(result["time_centers_ms"], list(range(-150, 1751, 10)))
        for sid in audit.SESSIONS:
            for state in audit.STATES:
                row = result["sessions"][sid][state]
                self.assertEqual(len(row["within_time"]), 5)
                self.assertTrue(all(len(x) == 191 for x in row["within_time"]))
                self.assertEqual(row["within_time"][0][0], 1 / 3)
        stat = result["sessions"][audit.SESSIONS[0]]["stat"]
        run = result["sessions"][audit.SESSIONS[0]]["run"]
        self.assertEqual(stat["trials_per_fold"][0][0], [12, 12, 6])
        self.assertEqual(stat["correct_counts"][0][0], [12, 0, 0])
        self.assertNotEqual(sum(stat["correct_counts"][0][0]) / sum(stat["trials_per_fold"][0][0]),
                            stat["within_time"][0][0])
        self.assertNotEqual(stat["trials_per_fold"][0][0], stat["trials_per_fold"][0][1])
        self.assertNotEqual(stat["trials_per_fold"][0][0], run["trials_per_fold"][0][0])
        self.assertIsNone(result["reproduction"])
        self.assertIsNone(result["improvement"])
        self.assertEqual(result["scientific_readiness"], "unqualified")

    def test_missing_and_duplicate_window(self):
        with self.assertRaisesRegex(ValueError, "incomplete full"):
            audit.reconstruct(self.manifest, "a" * 64, header(),
                              itertools.islice(records(self.manifest), audit.RECORDS - 1))
        first = next(records(self.manifest))
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            audit.reconstruct(self.manifest, "a" * 64, header(), [first, first])

    def test_complete_partition_not_individually_plausible_folds(self):
        folds = partition(5, 0)
        folds[1] = copy.deepcopy(folds[0])
        with self.assertRaisesRegex(ValueError, "partition every"):
            audit.validate_partition(folds, 5)
        with self.assertRaisesRegex(ValueError, "differ by at most"):
            audit.validate_partition([
                {"test_positions": [1, 2, 3], "train_positions": [4, 5]},
                {"test_positions": [4], "train_positions": [1, 2, 3, 5]},
                {"test_positions": [5], "train_positions": [1, 2, 3, 4]}], 5)

    def test_source_order_and_training_complement(self):
        folds = partition(5, 0)
        folds[0]["test_positions"].reverse()
        with self.assertRaisesRegex(ValueError, "unique and ordered"):
            audit.validate_partition(folds, 5)
        folds = partition(5, 0)
        folds[0]["train_positions"].reverse()
        with self.assertRaisesRegex(ValueError, "ordered exact"):
            audit.validate_partition(folds, 5)
        folds = partition(5, 0)
        folds[0]["test_positions"][0] = True
        with self.assertRaisesRegex(ValueError, "one-based integer"):
            audit.validate_partition(folds, 5)

    def test_three_trial_boundary_and_unsupported_smaller_route(self):
        audit.validate_partition(partition(3, 0), 3)
        manifest = copy.deepcopy(self.manifest)
        manifest["sessions"][audit.SESSIONS[0]]["n_trials"] = 2
        with self.assertRaisesRegex(ValueError, "selected threefold"):
            audit.validate_manifest(manifest)

    def test_manifest_full_support_and_identity(self):
        for mutate, error in (
            (lambda m: m["sessions"].pop(audit.SESSIONS[-1]), "all five"),
            (lambda m: m["sessions"][audit.SESSIONS[0]]["states"]["run"]["unit_ids"].reverse(), "same ordered"),
            (lambda m: m["sessions"][audit.SESSIONS[0]]["states"]["stat"]["partitions"][0].pop(), "191"),
            (lambda m: m["bindings"].pop("observations_sha256"), "source bindings"),
        ):
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest)
            with self.assertRaisesRegex(ValueError, error):
                audit.validate_manifest(manifest)
        manifest = copy.deepcopy(self.manifest)
        states = manifest["sessions"][audit.SESSIONS[0]]["states"]
        states["run"]["trial_ids"][0][0] = states["stat"]["trial_ids"][0][0]
        with self.assertRaisesRegex(ValueError, "trial repeated"):
            audit.validate_manifest(manifest)

    def test_prediction_fold_support_and_labels(self):
        for mutate, error in (
            (lambda r: r["folds"][0].update(held_trial_order_sha256="c" * 64), "source fold mismatch"),
            (lambda r: r["folds"][0]["predicted_classes"][0].pop(), "balanced held"),
            (lambda r: r["folds"][0]["predicted_classes"][0].__setitem__(0, True), "integer classes"),
            (lambda r: r.update(accuracy=1), "record fields"),
            (lambda r: r.update(time_index=192), "time index"),
        ):
            row = next(records(self.manifest))
            mutate(row)
            with self.assertRaisesRegex(ValueError, error):
                audit.reconstruct(self.manifest, "a" * 64, header(), [row])

    def test_information_condition_and_manifest_binding(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            audit.validate_header(header("c" * 64), "a" * 64)
        h = header()
        h["condition"] = "native"
        with self.assertRaisesRegex(ValueError, "information condition"):
            audit.validate_header(h, "a" * 64)

    def test_strict_json_and_stream_boundaries(self):
        for raw, error in ((b'{"x":1,"x":2}', "duplicate"), (b'NaN', "nonfinite")):
            with self.assertRaisesRegex(ValueError, error):
                audit.strict_json(raw)
        for raw in (b'{}', b'\n'):
            with self.assertRaisesRegex(ValueError, "newline"):
                audit.read_json_line(io.BytesIO(raw), hashlib.sha256(), [0])
        self.assertIsNone(audit.read_json_line(io.BytesIO(b'null\n'), hashlib.sha256(), [0]))
        self.assertIs(audit.read_json_line(io.BytesIO(b''), hashlib.sha256(), [0]), audit.END_OF_STREAM)

    def test_streamed_full_panel_digest_and_trailing_null(self):
        manifest_raw = json.dumps(self.manifest, separators=(",", ":")).encode()
        manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
        raw = b"\n".join(json.dumps(r, separators=(",", ":")).encode()
                          for r in itertools.chain([header(manifest_sha)], records(self.manifest))) + b"\n"
        result = audit.audit_files(MemoryPath(manifest_raw), manifest_sha,
                                   MemoryPath(raw), hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["record_count"], 9550)
        self.assertEqual(result["prediction_export_bytes"], len(raw))
        with self.assertRaisesRegex(ValueError, "prediction digest mismatch"):
            audit.audit_files(MemoryPath(manifest_raw), manifest_sha, MemoryPath(raw), "0" * 64)
        raw += b"null\n"
        with self.assertRaisesRegex(ValueError, "extra prediction record"):
            audit.audit_files(MemoryPath(manifest_raw), manifest_sha,
                              MemoryPath(raw), hashlib.sha256(raw).hexdigest())

    def test_cli_writes_only_after_audit_and_exclusively(self):
        args = ["within_time_audit.py", "--manifest", "manifest.json", "--manifest-sha256", "a" * 64,
                "--predictions", "predictions.jsonl", "--predictions-sha256", "b" * 64,
                "--output", "result.json"]
        output = mock.MagicMock()
        with mock.patch("sys.argv", args), mock.patch.object(audit, "audit_files", return_value={
                "qualification": "operator_prediction_arithmetic_and_support_only"}), \
                mock.patch.object(Path, "open", return_value=output) as opened, \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            audit.main()
            opened.assert_called_once_with("xb")
            output.__enter__().write.assert_called_once()
        with mock.patch("sys.argv", args), mock.patch.object(audit, "audit_files", side_effect=ValueError("bad input")), \
                mock.patch.object(Path, "open") as opened:
            with self.assertRaisesRegex(ValueError, "bad input"):
                audit.main()
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=1)

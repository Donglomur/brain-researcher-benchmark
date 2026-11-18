"""Generated in-memory controls; no recordings, MATLAB or model execution."""

import copy
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("cross_time_audit.py")
SPEC = importlib.util.spec_from_file_location("cross_time_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def fixture(n=5):
    sessions = {}
    for sid in audit.SESSIONS:
        sessions[sid] = {
            "n_trials": n, "class_order": list(range(1, 7)),
            "states": {
                state: {"unit_ids": ["unit_a", "unit_b"],
                        "trial_ids": [[f"{state}.class{label}.trial{i}" for i in range(1, n + 1)]
                                      for label in range(1, 7)]}
                for state in audit.STATES},
            "splits": [{"train_positions": list(range(n // 2 + 1, n + 1)),
                        "test_positions": list(range(1, n // 2 + 1))}
                       for _ in range(5)],
        }
    return {"schema": "horrocks-cross-time-audit-manifest/v1", "task_id": audit.TASK,
            "source_commit": audit.SOURCE_COMMIT,
            "bindings": {name: "a" * 64 for name in (
                "observations_sha256", "eligibility_recipe_sha256",
                "n_trials_assignment_sha256", "source_class_mapping_sha256")},
            "sessions": sessions}


def header(manifest_sha="a" * 64):
    return {"schema": "horrocks-cross-time-predictions/v1",
            "audit_manifest_sha256": manifest_sha, "method_sha256": "b" * 64,
            "condition": "paper_data"}


def records(manifest):
    supports = audit.validate_manifest(manifest)
    for sid in audit.SESSIONS:
        for state in audit.STATES:
            for repeat in range(1, 6):
                n_test, held_sha = supports[(sid, state, repeat)]
                for train in range(1, 21):
                    for test in range(1, 21):
                        correct = (train * 7 + test + repeat) % (6 * n_test + 1)
                        predictions = [[label if (label - 1) * n_test + i < correct else label % 6 + 1
                                        for i in range(n_test)] for label in range(1, 7)]
                        yield {"session": sid, "state": state, "repeat": repeat,
                               "train_time_index": train, "test_time_index": test,
                               "held_trial_order_sha256": held_sha, "predicted_classes": predictions}


class MemoryPath:
    """Exercise the exact streaming reader without creating generated disk data."""
    def __init__(self, raw):
        self.raw = raw

    def open(self, mode):
        assert mode == "rb"
        return io.BytesIO(self.raw)


class CrossTimeAuditTests(unittest.TestCase):
    def test_full_panel_and_asymmetric_axis_order(self):
        manifest = fixture()
        result = audit.reconstruct(manifest, "a" * 64, header(), records(manifest))
        self.assertEqual(result["record_count"], 20000)
        self.assertEqual(set(result["sessions"]), set(audit.SESSIONS))
        left = result["sessions"][audit.SESSIONS[0]]["stat"]
        self.assertEqual(left["trials_per_cell"], [12] * 5)
        self.assertEqual(left["correct_counts"][1][2][4], (3 * 7 + 5 + 2) % 13)
        self.assertEqual(left["cross_time"][1][2][4], ((3 * 7 + 5 + 2) % 13) / 12)
        self.assertNotEqual(left["cross_time"][1][2][4], left["cross_time"][1][4][2])
        self.assertIsNone(result["improvement"])
        self.assertIsNone(result["reproduction"])

    def test_missing_last_cell_is_not_partial_score(self):
        manifest = fixture()
        with self.assertRaisesRegex(ValueError, "incomplete full"):
            audit.reconstruct(manifest, "a" * 64, header(), itertools.islice(records(manifest), 19999))

    def test_duplicate_cell_cannot_replace_missing_cell(self):
        manifest = fixture()
        first = next(records(manifest))
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            audit.reconstruct(manifest, "a" * 64, header(), [first, first])

    def test_prediction_order_bound_to_held_roster(self):
        manifest = fixture()
        row = next(records(manifest))
        row["held_trial_order_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "held trial order"):
            audit.reconstruct(manifest, "a" * 64, header(), [row])

    def test_class_or_state_trial_reuse_rejected(self):
        manifest = fixture()
        first = manifest["sessions"][audit.SESSIONS[0]]["states"]
        first["run"]["trial_ids"][0][0] = first["stat"]["trial_ids"][0][0]
        with self.assertRaisesRegex(ValueError, "trial repeated"):
            audit.validate_manifest(manifest)

    def test_missing_mouse_and_units_rejected(self):
        manifest = fixture()
        del manifest["sessions"][audit.SESSIONS[-1]]
        with self.assertRaisesRegex(ValueError, "all five"):
            audit.validate_manifest(manifest)
        manifest = fixture()
        manifest["sessions"][audit.SESSIONS[0]]["states"]["run"]["unit_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "same ordered full"):
            audit.validate_manifest(manifest)

    def test_odd_split_preserves_source_floor_ceil_and_order(self):
        manifest = fixture(5)
        split = manifest["sessions"][audit.SESSIONS[0]]["splits"][0]
        split["train_positions"], split["test_positions"] = [5, 1, 3], [2, 4]
        support = audit.validate_manifest(manifest)
        self.assertEqual(support[(audit.SESSIONS[0], "stat", 1)][0], 2)
        split["test_positions"].reverse()
        with self.assertRaisesRegex(ValueError, "ordered exact"):
            audit.validate_manifest(manifest)

    def test_even_split_and_train_test_overlap(self):
        manifest = fixture(4)
        self.assertEqual(audit.validate_manifest(manifest)[(audit.SESSIONS[0], "run", 1)][0], 2)
        manifest["sessions"][audit.SESSIONS[0]]["splits"][0]["test_positions"] = [1, 3]
        with self.assertRaisesRegex(ValueError, "ordered exact"):
            audit.validate_manifest(manifest)

    def test_missing_source_assignment_and_wrong_commit(self):
        manifest = fixture()
        manifest["bindings"]["n_trials_assignment_sha256"] = None
        with self.assertRaisesRegex(ValueError, "SHA256"):
            audit.validate_manifest(manifest)
        manifest = fixture()
        manifest["source_commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            audit.validate_manifest(manifest)

    def test_bool_predictions_and_unbalanced_class_support(self):
        manifest = fixture()
        row = next(records(manifest))
        row["predicted_classes"][0][0] = True
        with self.assertRaisesRegex(ValueError, "integer classes"):
            audit.reconstruct(manifest, "a" * 64, header(), [row])
        row = next(records(manifest))
        row["predicted_classes"][0].pop()
        with self.assertRaisesRegex(ValueError, "complete balanced"):
            audit.reconstruct(manifest, "a" * 64, header(), [row])

    def test_claimed_accuracy_and_unknown_window_rejected(self):
        manifest = fixture()
        row = next(records(manifest))
        row["accuracy"] = 1
        with self.assertRaisesRegex(ValueError, "record fields"):
            audit.reconstruct(manifest, "a" * 64, header(), [row])
        del row["accuracy"]
        row["train_time_index"] = 0
        with self.assertRaisesRegex(ValueError, "time indices"):
            audit.reconstruct(manifest, "a" * 64, header(), [row])

    def test_manifest_header_identity_and_information_condition(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            audit.validate_header(header("c" * 64), "a" * 64)
        h = header()
        h["condition"] = "native"
        with self.assertRaisesRegex(ValueError, "information condition"):
            audit.validate_header(h, "a" * 64)

    def test_strict_json_and_null_is_not_eof(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit.strict_json('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            audit.strict_json('{"a":NaN}')
        stream = io.BytesIO(b"null\n")
        self.assertIsNone(audit.read_json_line(stream, hashlib.sha256(), [0]))
        self.assertIs(audit.read_json_line(stream, hashlib.sha256(), [0]), audit.END_OF_STREAM)
        with self.assertRaisesRegex(ValueError, "record fields"):
            audit.reconstruct(fixture(), "a" * 64, header(), [None])

    def test_streamed_full_panel_digest_and_trailing_null(self):
        manifest = fixture()
        manifest_raw = json.dumps(manifest, separators=(",", ":")).encode()
        manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
        lines = [json.dumps(header(manifest_sha), separators=(",", ":")).encode() + b"\n"]
        lines.extend(json.dumps(r, separators=(",", ":")).encode() + b"\n" for r in records(manifest))
        raw = b"".join(lines)
        result = audit.audit_files(MemoryPath(manifest_raw), manifest_sha,
                                   MemoryPath(raw), hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["prediction_export_bytes"], len(raw))
        with self.assertRaisesRegex(ValueError, "prediction digest mismatch"):
            audit.audit_files(MemoryPath(manifest_raw), manifest_sha, MemoryPath(raw), "0" * 64)
        raw += b"null\n"
        with self.assertRaisesRegex(ValueError, "extra prediction record"):
            audit.audit_files(MemoryPath(manifest_raw), manifest_sha,
                              MemoryPath(raw), hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=1)

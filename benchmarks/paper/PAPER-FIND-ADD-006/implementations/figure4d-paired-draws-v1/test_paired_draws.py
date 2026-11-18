"""Generated metadata/CSV controls; no recordings, classifiers or model calls."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("paired_draws", HERE / "paired_draws.py")
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)
SCORING = pd.scorer_module()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def fixture(animal="jc233", date="170220"):
    vectors = []
    train, test, train_draw, test_draw = [], [], [], []
    for group, (context, condition) in enumerate((("A", "left"), ("A", "right"),
                                               ("B", "left"), ("B", "right"))):
        keys = [f"pv-{group}-{i}" for i in range(5)]
        vectors.extend({"pv_id": key, "context": context, "condition": condition} for key in keys)
        count = 3 if group % 2 == 0 else 4
        train.extend(keys[:count]); test.extend(keys[count:])
        train_draw.extend([keys[0]] * count); test_draw.extend([keys[count]] * (5 - count))
    source = {"schema": "hierarchy-figure4d-pv-metadata/v1", "animal": animal, "date": date,
              "context_labels": ["A", "B"], "condition_labels": ["left", "right"],
              "preparation_receipt_sha256": "a" * 64, "vectors": vectors}
    source_hash = hashlib.sha256(encode(source)).hexdigest()
    ledger = {"schema": "hierarchy-figure4d-draw-ledger/v1", "source_sha256": source_hash,
              "generation": {"kind": "regenerated_original_protocol", "receipt_sha256": "b" * 64,
                             "sample_fraction": 1},
              "repeats": [{"repeat": rep, "train_partition": list(train), "test_partition": list(test),
                           "train_draw": list(train_draw), "test_draw": list(test_draw)}
                          for rep in range(pd.REPEATS)]}
    by_id = {v["pv_id"]: v for v in vectors}
    rows = [{"Boot_rep": str(rep), "Draw_occurrence": str(i), "PV_id": key,
             "Real_label": by_id[key]["context"], "Pred_label": by_id[key]["context"],
             "Condition": by_id[key]["condition"]}
            for rep in range(pd.REPEATS) for i, key in enumerate(test_draw)]
    exports = {method: {arm: deepcopy(rows) for arm in SCORING.ARMS} for method in pd.METHODS}
    return source, ledger, source_hash, exports


class DrawChecks(unittest.TestCase):
    def setUp(self):
        self.source, self.ledger, self.sha, self.exports = fixture()

    def validate(self):
        return pd.validate_session(self.source, self.ledger, self.sha, SCORING)

    def test_pairing_preserves_occurrences_and_accepts_arm_row_reordering(self):
        for method in pd.METHODS:
            for arm in SCORING.ARMS:
                self.exports[method][arm].reverse()
        for arm in SCORING.ARMS:
            self.exports["candidate"][arm][0]["Pred_label"] = "A"
        report = pd.score_session(self.source, self.ledger, self.sha, self.exports, SCORING)
        self.assertEqual(report["methods"]["author"]["global"]["selected_rows"], 600)
        self.assertEqual(report["methods"]["author"]["global"]["repeat_summary"]["exact_match_accuracy"], 1)
        self.assertEqual(report["methods"]["candidate"]["global"]["repetitions"][99]
                         ["pooled_observation_diagnostic"]["mismatches"], 1)
        self.assertIsNone(report["paper_win"])
        self.assertFalse(report["stratification_algorithm_verified"])
        self.assertFalse(report["training_execution_verified"])

    def test_source_partition_overlap_and_omission_rejected(self):
        self.ledger["repeats"][0]["train_partition"][0] = self.ledger["repeats"][0]["test_partition"][0]
        with self.assertRaisesRegex(pd.DrawError, "overlap or omit"):
            self.validate()

    def test_partition_before_bootstrap_is_checked(self):
        self.ledger["repeats"][0]["test_draw"][0] = self.ledger["repeats"][0]["train_partition"][0]
        with self.assertRaisesRegex(pd.DrawError, "unknown source PV"):
            self.validate()

    def test_all_repeats_and_original_split_sizes_required(self):
        self.ledger["repeats"][99]["repeat"] = 98
        with self.assertRaisesRegex(pd.DrawError, "duplicate repetition"):
            self.validate()
        self.ledger["repeats"][99]["repeat"] = 99
        row = self.ledger["repeats"][0]
        row["train_partition"].append(row["test_partition"].pop())
        with self.assertRaisesRegex(pd.DrawError, "70/30"):
            self.validate()

    def test_fraction_and_training_support_checked(self):
        self.ledger["generation"]["sample_fraction"] = True
        with self.assertRaisesRegex(pd.DrawError, "sample_fraction"):
            self.validate()
        self.ledger["generation"]["sample_fraction"] = 1
        draw = self.ledger["repeats"][0]["train_draw"]
        draw[:] = [draw[0]] * len(draw)
        with self.assertRaisesRegex(pd.DrawError, "omits source"):
            self.validate()

    def test_pv_substitution_with_same_label_histogram_rejected(self):
        row = self.exports["candidate"]["conditional"][0]
        row["PV_id"] = "pv-0-4"  # same context and condition, a different held PV.
        with self.assertRaisesRegex(pd.DrawError, "substituted another PV"):
            pd.score_session(self.source, self.ledger, self.sha, self.exports, SCORING)

    def test_duplicates_and_deduplicated_bootstraps_rejected(self):
        rows = self.exports["candidate"]["global"]
        rows[1] = dict(rows[0])
        with self.assertRaisesRegex(pd.DrawError, "duplicate prediction"):
            pd.score_session(self.source, self.ledger, self.sha, self.exports, SCORING)
        self.source, self.ledger, self.sha, self.exports = fixture()
        self.exports["candidate"]["global"].pop()
        with self.assertRaisesRegex(pd.DrawError, "omits shared draw"):
            pd.score_session(self.source, self.ledger, self.sha, self.exports, SCORING)

    def test_labels_are_operator_bound_for_shuffle_controls_too(self):
        self.exports["candidate"]["conditional_context_shuffle"][0]["Real_label"] = "B"
        with self.assertRaisesRegex(pd.DrawError, "operator metadata"):
            pd.score_session(self.source, self.ledger, self.sha, self.exports, SCORING)

    def test_all_methods_and_five_comparison_arms_required(self):
        del self.exports["author"]["global_context_shuffle"]
        with self.assertRaisesRegex(pd.DrawError, "comparison arms"):
            pd.score_session(self.source, self.ledger, self.sha, self.exports, SCORING)

    def test_source_hash_and_generation_kind_are_not_guessed(self):
        self.ledger["source_sha256"] = "c" * 64
        with self.assertRaisesRegex(pd.DrawError, "another source"):
            self.validate()
        self.ledger["source_sha256"] = self.sha
        self.ledger["generation"]["kind"] = "new_whole_animal_holdout"
        with self.assertRaisesRegex(pd.DrawError, "provenance"):
            self.validate()

    def test_hash_reader_json_and_csv_refuse_malformed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"; body = b'{"a":1}'
            path.write_bytes(body)
            desc = {"path": "x.json", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            self.assertEqual(pd.pinned_body(tmp, desc), body)
            path.write_bytes(b'{"a":2}')
            with self.assertRaisesRegex(pd.DrawError, "captured bytes/hash"):
                pd.pinned_body(tmp, desc)
        with self.assertRaisesRegex(pd.DrawError, "duplicate JSON"):
            pd.json_body(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(pd.DrawError, "six identity"):
            list(pd.csv_rows(b'Boot_rep,PV_id\n0,a\n'))
        with self.assertRaisesRegex(pd.DrawError, "nonfinite JSON"):
            pd.json_body(b'{"a":NaN}')

    def test_complete_panel_requires_all_25_sessions_and_uses_original_scorer(self):
        # All scientific arrays are invented in memory; no large fixture files.
        members, sessions = {}, []
        for animal, dates in SCORING.ROSTER.items():
            for date in dates:
                source, ledger, sha, exports = fixture(animal, date)
                prefix = f"{animal}-{date}"
                members[prefix + "-source"] = encode(source)
                members[prefix + "-ledger"] = encode(ledger)
                csv = (",".join(sorted(pd.FIELDS)) + "\n" + "\n".join(
                    ",".join(row[key] for key in sorted(pd.FIELDS))
                    for row in exports["author"]["global"]) + "\n").encode()
                for method in pd.METHODS:
                    for arm in SCORING.ARMS:
                        members[prefix + "-" + method + "-" + arm] = csv
                def ref(name):
                    return {"path": prefix + name, "bytes": len(members[prefix + name]),
                            "sha256": hashlib.sha256(members[prefix + name]).hexdigest()}
                sessions.append({"animal": animal, "date": date, "source": ref("-source"),
                                 "ledger": ref("-ledger"), "exports": {
                                     method: {arm: ref("-" + method + "-" + arm) for arm in SCORING.ARMS}
                                     for method in pd.METHODS}})
        panel = {"schema": "hierarchy-figure4d-paired-panel/v1", "sessions": sessions}
        with patch.object(pd, "pinned_body", side_effect=lambda base, desc: members[desc["path"]]):
            report = pd.score_panel(panel, ".")
        self.assertEqual(report["session_count"], 25)
        self.assertEqual(report["animal_count"], 5)
        self.assertIsNone(report["cross_session_aggregate"])
        self.assertEqual(report["reproduction_outcome"], "unknown")
        original = sessions[0]["exports"]["candidate"]["global"]
        sessions[0]["exports"]["candidate"]["global"] = sessions[0]["exports"]["author"]["global"]
        with patch.object(pd, "pinned_body", side_effect=lambda base, desc: members[desc["path"]]):
            with self.assertRaisesRegex(pd.DrawError, "same prediction export"):
                pd.score_panel(panel, ".")
        sessions[0]["exports"]["candidate"]["global"] = original
        panel["sessions"] = sessions[:-1]
        with self.assertRaisesRegex(pd.DrawError, "25-session"):
            pd.score_panel(panel, ".")


if __name__ == "__main__":
    unittest.main(verbosity=2)

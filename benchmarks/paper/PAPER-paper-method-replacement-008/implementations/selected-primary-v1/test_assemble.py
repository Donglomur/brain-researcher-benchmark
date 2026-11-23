"""Generated controls for full-panel assembly; no model execution or real data."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("barista_assemble", HERE / "assemble.py")
assemble = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assemble)
score = assemble.score
import numpy as np
from arrays import write_array
from io_contract import capture, parse
from protocol import canonical, digest


def panel():
    p = {"schema": "barista_selected_primary_panel_v1", "task_id": score.TASK_ID,
         "source_protocol_sha256": score.SOURCE_PROTOCOL_SHA,
         "scope_contract_sha256": score.SCOPE_SHA256, "generation_commitment": "a" * 64,
         "contexts": [dict(c, query_count=4, query_ids_sha256=digest(["q0", "q1", "q2", "q3"]))
                      for c in score.contexts()]}
    p["panel_id"] = digest(p)
    return p


def runs(public, values):
    return [{"schema": "barista_selected_primary_run_v1", "panel_id": public["panel_id"],
             **{k: row[k] for k in assemble.IDENTITY_KEYS},
             "query_ids": ["q0", "q1", "q2", "q3"], "values": values}
            for row in score.outputs(public)]


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.public = panel()
        self.descriptor = write_array(self.root / "p.npy", np.array([.2, .8, .4, .6]))
        self.receipts = runs(self.public, self.descriptor)

    def test_shuffled_full_panel_cli_writes_scorer_admissible_unchanged_values(self):
        output = self.root / "SUBMISSION.json"
        original = capture(self.root / "p.npy")
        # Full real file-loading/CLI path; one generated output manifest only.
        names = [f"run-{i}.json" for i in range(len(self.receipts))]
        receipt_bodies = [canonical(r) + b"\n" for r in self.receipts[::-1]]
        public_body = canonical(self.public) + b"\n"
        index_body = canonical({"schema": "barista_selected_primary_run_index_v1",
                                "panel_id": self.public["panel_id"], "runs": names}) + b"\n"
        self.assertLessEqual(sum(map(len, receipt_bodies)) + len(public_body) + len(index_body),
                             3_200_000)
        (self.root / "PUBLIC.json").write_bytes(public_body)
        (self.root / "RUNS.json").write_bytes(index_body)
        for name, body in zip(names, receipt_bodies):
            (self.root / name).write_bytes(body)
        completed = subprocess.run([
            sys.executable, "-I", "-B", str(HERE / "assemble.py"),
            "--public", str(self.root / "PUBLIC.json"),
            "--index", str(self.root / "RUNS.json"), "--out", str(output),
            "--max-output-bytes", "2900000",
        ], capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        body = capture(output, cap=score.JSON_CAP)
        result = parse(body)
        rows, expected = score.admit(self.public, body, self.root)
        self.assertEqual(len(rows), 5880)
        self.assertEqual([tuple(r[k] for k in assemble.IDENTITY_KEYS) for r in rows],
                         [tuple(r[k] for k in assemble.IDENTITY_KEYS) for r in expected])
        self.assertTrue(all(r["values"] == self.descriptor for r in rows))
        self.assertEqual(capture(self.root / "p.npy"), original)
        self.assertEqual(set(r["arm"] for r in rows), set(score.ARMS))
        self.assertEqual(len({r["id"] for r in rows}), 420)
        self.assertFalse(any(k in result for k in ("gold", "labels", "paper_win_established")))
        with self.assertRaisesRegex(ValueError, "Fresh output"):
            assemble.write_submission(self.public, self.receipts, self.root,
                                      output, max_output_bytes=3_000_000)

    def test_missing_duplicate_foreign_run_and_wrong_generation_refused(self):
        for mutation in (
            lambda rows: rows.pop(),
            lambda rows: rows.__setitem__(-1, copy.deepcopy(rows[0])),
            lambda rows: rows[0].update(model="barista_channels_parcels"),
            lambda rows: rows[0].update(arm="merged_arms"),
            lambda rows: rows[0].update(panel_id="f" * 64),
        ):
            changed = copy.deepcopy(self.receipts)
            mutation(changed)
            with self.assertRaises(ValueError):
                assemble.compile_submission(self.public, changed, self.root)

    def test_missing_repeated_or_reordered_query_support_refused(self):
        for ids in (["q1", "q0", "q2", "q3"], ["q0", "q1", "q2"],
                    ["q0", "q1", "q2", "q2"], ["q0", "q1", "q2", 3]):
            changed = copy.deepcopy(self.receipts)
            changed[-1]["query_ids"] = ids
            with self.assertRaisesRegex(ValueError, "query IDs"):
                assemble.compile_submission(self.public, changed, self.root)

    def test_last_artifact_and_output_budget_refused_before_output(self):
        out = self.root / "ABSENT.json"
        changed = copy.deepcopy(self.receipts)
        changed[-1]["values"] = dict(self.descriptor, path="missing.npy")
        with self.assertRaises(OSError):
            assemble.write_submission(self.public, changed, self.root,
                                      out, max_output_bytes=3_000_000)
        self.assertFalse(out.exists())
        with self.assertRaisesRegex(ValueError, "output allowance"):
            assemble.write_submission(self.public, self.receipts, self.root,
                                      out, max_output_bytes=100)
        self.assertFalse(out.exists())
        with self.assertRaisesRegex(ValueError, "share"):
            assemble.write_submission(self.public, self.receipts, self.root,
                                      self.root.parent / "WRONG.json", max_output_bytes=3_000_000)

    def test_invalid_probability_shape_range_and_hash_refused(self):
        bad = write_array(self.root / "outside.npy", np.array([.1, .2, .3, 1.1]))
        matrix = write_array(self.root / "matrix.npy", np.full((4, 2), .5))
        for desc in (bad, matrix, dict(self.descriptor, sha256="f" * 64)):
            changed = list(self.receipts)
            changed[0] = dict(changed[0], values=desc)
            with self.assertRaises(ValueError):
                assemble.compile_submission(self.public, changed, self.root)

    def test_index_identity_duplicates_and_traversal_refused(self):
        names = [f"run-{i}.json" for i in range(5880)]
        for changed in (names[:-1], names[:-1] + [names[0]], names[:-1] + ["../other.json"]):
            index = {"schema": "barista_selected_primary_run_index_v1",
                     "panel_id": self.public["panel_id"], "runs": changed}
            with self.assertRaises(ValueError):
                assemble._read_receipts(index, self.root, self.public)


if __name__ == "__main__":
    unittest.main(verbosity=2)

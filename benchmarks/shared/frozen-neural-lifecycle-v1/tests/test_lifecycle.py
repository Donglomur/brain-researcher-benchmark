"""Generated engineering controls; no biological input, solver, or scientific score."""
from pathlib import Path
import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frozen_neural_lifecycle", PACKAGE / "lifecycle.py")
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)

CANDIDATE = '''from pathlib import Path
import argparse, json, os
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
r=json.loads(Path(a.request).read_text()); ids=r['ids']
assert not list(Path.cwd().iterdir()), 'scratch must start empty'
assert set(Path(r['case_directory']).iterdir()) == {Path(r['case_directory'])/'public.json'}
assert 'private' not in r and 'target' not in r
probabilities=([0.2]*5 if r['task_id']=='NEURAL-007' else 0.5)
result={'ids':ids,'probabilities':[probabilities for _ in ids]}
Path(a.output).write_text(json.dumps(result))
print(json.dumps({'pid':os.getpid(),'case':r['case_id']}))
'''


def generated(root, task="NEURAL-077", authentic_mode=False):
    """Full-size generated panel, inaccessible from the public prepare CLI."""
    root.mkdir()
    (root / "events").mkdir()
    (root / "inputs" / "training").mkdir(parents=True)
    lc.write_json(root / "inputs" / "training" / "labels.json", {"generated": True})
    cases = {}
    for case, count in zip(lc.CASES, lc.COUNTS[task]):
        folder = root / "inputs" / "development" / case
        folder.mkdir(parents=True)
        lc.write_json(folder / "public.json", {"generated": True, "case": case})
        cases[case] = {"count": count, "ids": [f"{case}/{i:05d}" for i in range(count)]}
    p = {"schema": "frozen_neural_lifecycle_v1", "task_id": task,
         "evidence_kind": "authentic_public_inputs" if authentic_mode else "generated_engineering_control",
         "case_order": list(lc.CASES), "cases": cases, "inputs": lc.inventory(root / "inputs"),
         "scorer_memory_bytes": 4 * 1024**3}
    lc.write_json(root / "packet.json", p)
    lc.record(root, "prepared", packet=lc.pin(root / "packet.json"), generated=True)
    return p


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "run"
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "METHOD.md").write_text("Generated constant predictor; tests lifecycle only.\n")
        (self.source / "candidate.py").write_text(CANDIDATE)

    def tearDown(self):
        self.temp.cleanup()

    def ready(self, task="NEURAL-077"):
        generated(self.root, task)
        lc.commit(self.root, self.source)

    def frozen(self, task="NEURAL-077"):
        self.ready(task)
        lc.execute(self.root)
        lc.freeze(self.root)

    def failure(self, action, message=None):
        with self.assertRaises(lc.Rejected) as result:
            action()
        if message:
            self.assertIn(message, str(result.exception))
        self.assertEqual(lc.events(self.root)[-1]["event"], "operation_failed")

    def test_full_neural077_processes_freeze_before_private_action(self):
        self.frozen()
        rows = lc.events(self.root)
        starts = [r for r in rows if r["event"] == "case_started"]
        self.assertEqual(len({r["pid"] for r in starts}), 2)
        self.assertLess(next(r["sequence"] for r in rows if r["event"] == "method_committed"), starts[0]["sequence"])
        with zipfile.ZipFile(self.root / "submission.npz") as z:
            self.assertEqual(z.namelist(), ["trial_ids.npy", "target_probability.npy"])
        self.assertEqual(len(lc._unicode_array(self.root / "submission.npz", "trial_ids", 400)), 400)
        called = []
        def private_action(root, packet):
            self.assertEqual(lc.events(root)[-1]["event"], "grade_started")
            called.append(lc.pin(root / "submission.npz"))
        lc._grade_gate(self.root, private_action, 4 * 1024**3)
        self.assertEqual(called, [lc.pin(self.root / "submission.npz")])
        self.assertEqual(lc.events(self.root)[-1]["event"], "grade_finished")

    def test_full_sleep_native_clock_and_class_order(self):
        self.frozen("NEURAL-007")
        with zipfile.ZipFile(self.root / "submission.npz") as z:
            self.assertEqual(len(z.namelist()), 5)
            self.assertTrue(all(r.compress_type == zipfile.ZIP_STORED for r in z.infolist()))
        self.assertEqual(lc._unicode_array(self.root / "submission.npz", "class_order", 5), list(lc.CLASSES))
        for case, count in zip(lc.CASES, lc.COUNTS["NEURAL-007"]):
            self.assertEqual(len(lc._unicode_array(self.root / "submission.npz", case + "__epoch_id", count)), count)

    def test_execute_without_commit_is_terminal(self):
        generated(self.root)
        self.failure(lambda: lc.execute(self.root), "commitment")
        self.failure(lambda: lc.commit(self.root, self.source), "terminal")

    def test_freeze_before_any_execution_is_rejected(self):
        self.ready()
        self.failure(lambda: lc.freeze(self.root), "Finish both")

    def test_private_action_never_runs_before_freeze(self):
        self.ready()
        called = []
        self.failure(lambda: lc._grade_gate(self.root, lambda *args: called.append(True), 4 * 1024**3))
        self.assertEqual(called, [])

    def test_method_mutation_before_first_prediction_is_terminal(self):
        self.ready()
        (self.source / "candidate.py").write_text("raise RuntimeError('changed')")
        self.failure(lambda: lc.execute(self.root), "tree changed")
        self.assertFalse((self.root / "processes").exists())
        self.failure(lambda: lc.commit(self.root, self.source), "terminal")

    def test_candidate_cannot_change_committed_source_and_continue(self):
        (self.source / "candidate.py").write_text(CANDIDATE + "\nPath(__file__).write_text('modified')\n")
        self.ready()
        self.failure(lambda: lc.execute(self.root), "tree changed")
        self.assertFalse((self.root / "processes" / lc.CASES[1]).exists())

    def test_public_input_tamper_prevents_execution(self):
        self.ready()
        (self.root / "inputs" / "training" / "labels.json").write_text("{}")
        self.failure(lambda: lc.execute(self.root), "tree changed")
        self.assertFalse((self.root / "processes").exists())

    def test_missing_person_output_and_failures_are_retained(self):
        (self.source / "candidate.py").write_text("print('preserved failure'); raise SystemExit(9)\n")
        self.ready()
        self.failure(lambda: lc.execute(self.root), "Candidate failed")
        first = self.root / "processes" / lc.CASES[0]
        self.assertIn("preserved failure", (first / "stdout.log").read_text())
        self.assertFalse((self.root / "processes" / lc.CASES[1]).exists())
        self.failure(lambda: lc.execute(self.root), "terminal")

    def test_live_child_prevents_admission_and_is_killed(self):
        (self.source / "candidate.py").write_text(CANDIDATE + "\nimport subprocess,sys\nsubprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n")
        self.ready()
        self.failure(lambda: lc.execute(self.root), "live descendants")
        exited = [r for r in lc.events(self.root) if r["event"] == "case_exited"]
        self.assertTrue(exited[0]["remaining_group"])
        self.assertFalse((self.root / "submission.npz").exists())

    def test_receipt_failure_still_reaps_owned_process(self):
        (self.source / "candidate.py").write_text("import time; time.sleep(30)\n")
        self.ready()
        original_record = lc.record
        children = []
        def fail_receipt(root, kind, **details):
            if kind == "case_started":
                children.append(details["pid"])
                raise OSError("generated receipt write failure")
            return original_record(root, kind, **details)
        with mock.patch.object(lc, "record", fail_receipt):
            with self.assertRaises(OSError):
                lc.execute(self.root)
        self.assertEqual(len(children), 1)
        self.assertFalse(lc._group_alive(children[0]))
        self.assertEqual(lc.events(self.root)[-1]["event"], "operation_failed")

    def test_interruption_reaps_owned_process_and_records_terminal_failure(self):
        (self.source / "candidate.py").write_text("import time; time.sleep(30)\n")
        self.ready()
        original_record = lc.record
        children = []
        def interrupt(root, kind, **details):
            if kind == "case_started":
                children.append(details["pid"])
                raise KeyboardInterrupt("generated operator interrupt")
            return original_record(root, kind, **details)
        with mock.patch.object(lc, "record", interrupt):
            with self.assertRaises(KeyboardInterrupt):
                lc.execute(self.root)
        self.assertFalse(lc._group_alive(children[0]))
        self.assertEqual(lc.events(self.root)[-1]["error_type"], "KeyboardInterrupt")
        self.failure(lambda: lc.execute(self.root), "terminal")

    def test_missing_trial_not_admitted_or_graded(self):
        (self.source / "candidate.py").write_text(CANDIDATE.replace("ids=r['ids']", "ids=r['ids'][:-1]"))
        self.ready()
        self.failure(lambda: lc.execute(self.root), "complete person")
        self.assertFalse((self.root / "submission.npz").exists())

    def test_reexecution_after_success_is_rejected(self):
        self.ready()
        lc.execute(self.root)
        self.failure(lambda: lc.execute(self.root), "exactly once")

    def test_complete_output_tamper_before_freeze(self):
        self.ready()
        lc.execute(self.root)
        output = self.root / "processes" / lc.CASES[0] / "output" / "predictions.json"
        output.write_text(output.read_text().replace("0.5", "0.4"))
        self.failure(lambda: lc.freeze(self.root), "Pinned bytes changed")

    def test_frozen_submission_tamper_blocks_private_action(self):
        self.frozen()
        with (self.root / "submission.npz").open("ab") as f:
            f.write(b"tamper")
        called = []
        self.failure(lambda: lc._grade_gate(self.root, lambda *args: called.append(True), 4 * 1024**3), "Pinned bytes changed")
        self.assertEqual(called, [])

    def test_native_memory_budget_refusal_preserved(self):
        self.frozen()
        called = []
        self.failure(lambda: lc._grade_gate(self.root, lambda *args: called.append(True), 2 * 1024**3), "4 GiB")
        self.assertEqual(called, [])

    def test_response_rejects_duplicate_ids_boolean_nonfinite_extra_fields(self):
        path = self.base / "response.json"
        good = {"ids": ["a", "b"], "probabilities": [0.3, 0.8]}
        variants = [dict(good, ids=["a", "a"]), dict(good, probabilities=[True, 0.8]),
                    dict(good, probabilities=[float("nan"), 0.8]), dict(good, answer="extra")]
        for bad in variants:
            path.write_text(json.dumps(bad))
            with self.assertRaises(lc.Rejected):
                lc.response(path, ["a", "b"], "NEURAL-077")
        path.write_text('{"ids":["a","b"],"ids":["a","b"],"probabilities":[0.3,0.8]}')
        with self.assertRaises(lc.Rejected):
            lc.response(path, ["a", "b"], "NEURAL-077")

    def test_sleep_no_probability_normalization(self):
        path = self.base / "response.json"
        path.write_text(json.dumps({"ids": ["a"], "probabilities": [[0.3] * 5]}))
        with self.assertRaises(lc.Rejected):
            lc.response(path, ["a"], "NEURAL-007")

    @unittest.skipIf(sys.platform == "linux", "Linux has the declared hard-memory route")
    def test_unsupported_hard_memory_setup_records_failure_before_candidate(self):
        generated(self.root, authentic_mode=True)
        lc.commit(self.root, self.source)
        self.failure(lambda: lc.execute(self.root), "Candidate failed")
        first = self.root / "processes" / lc.CASES[0]
        self.assertEqual(lc.read_json(first / "resources.json")["status"], "resource_setup_failed")
        self.assertFalse((first / "output" / "predictions.json").exists())

    def test_chain_tamper_is_detected(self):
        self.ready()
        path = self.root / "events" / "0000.json"
        row = lc.read_json(path)
        row["generated"] = False
        path.write_text(json.dumps(row))
        with self.assertRaises(lc.Rejected):
            lc.events(self.root)


if __name__ == "__main__":
    unittest.main()

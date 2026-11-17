"""Generated controls; optional pinned author AST oracle stays outside Git."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_split", HERE / "source_split.py")
split = importlib.util.module_from_spec(spec)
spec.loader.exec_module(split)
ROSTER = json.loads((HERE.parent / "initial-evaluator-v1" / "cohort.json").read_text())
SOURCE_PATH = None


def event(n=90, index=0, spacing=3.0):
    return {"eid": ROSTER["heldout_eids"][index],
            "trial_ids": [f"generated-original-{i}" for i in range(n)],
            "stim_on_seconds": [i * spacing for i in range(n)]}


def request(events=None):
    return {"schema": "neds-source-split-request-v1", "source_commit": split.COMMIT,
            "evidence_kind": "generated_engineering",
            "rng_origin": {"kind": "source_process_seed", "seed": 42},
            "events": events or [event()]}


def bundle_sessions(report):
    return [{"eid": s["eid"], **{name: {"trial_ids": s["partitions"][name]["trial_ids"][:]}
                               for name in split.SPLITS}} for s in report["sessions"]]


class Controls(unittest.TestCase):
    def test_source_float_floor_not_rounded_proportions(self):
        # Literal source floating multiplication differs from rational 7*n//10 at n=90.
        report = split.replay(request())
        self.assertEqual([len(report["sessions"][0]["partitions"][s]["trial_ids"])
                          for s in split.SPLITS], [62, 10, 18])
        ids = [i for s in split.SPLITS for i in report["sessions"][0]["partitions"][s]["trial_ids"]]
        self.assertCountEqual(ids, event()["trial_ids"])
        small = split.replay(request([event(2)]))["sessions"][0]["partitions"]
        self.assertEqual([len(small[s]["trial_ids"]) for s in split.SPLITS], [1, 0, 1])

    def test_sequence_and_captured_state_not_per_session_reseed(self):
        first, second = event(19), event(31, 1)
        sequential = split.replay(request([first, second]))
        reset = split.replay(request([second]))
        self.assertNotEqual(sequential["sessions"][1]["partitions"], reset["sessions"][0]["partitions"])
        resumed = request([second])
        resumed["rng_origin"] = {"kind": "captured_pre_split_state",
                                 "state": split.replay(request([first]))["rng_state_after"]}
        self.assertEqual(sequential["sessions"][1], split.replay(resumed)["sessions"][0])

    def test_no_global_rng_or_input_mutation(self):
        original = request()
        saved = copy.deepcopy(original)
        np.random.seed(123)
        before = split.encode_state(np.random)
        split.replay(original)
        self.assertEqual(before, split.encode_state(np.random))
        self.assertEqual(original, saved)

    def test_identity_verification_rejects_reorder_swap_missing_duplicate(self):
        report = split.replay(request([event(20), event(20, 1)]))
        sessions = bundle_sessions(report)
        split.verify_partition_ids(report, sessions)
        bad = copy.deepcopy(sessions)
        bad[0]["train"]["trial_ids"].reverse()
        with self.assertRaises(split.ReplayError):
            split.verify_partition_ids(report, bad)
        bad = copy.deepcopy(sessions)
        bad[0]["train"], bad[0]["test"] = bad[0]["test"], bad[0]["train"]
        for example in (bad, sessions[:1], sessions + sessions[:1]):
            with self.assertRaises(split.ReplayError):
                split.verify_partition_ids(report, example)

    def test_physical_overlap_bruteforce_and_no_purging(self):
        original = request([event(90, spacing=0.125)])
        report = split.replay(original)
        partitions = report["sessions"][0]["partitions"]
        for pair, found in report["sessions"][0]["physical_overlap"].items():
            left, right = (partitions[n] for n in pair.split(":"))
            overlaps = [max(0, min(a[1], b[1]) - max(a[0], b[0]))
                        for a in left["windows_seconds"] for b in right["windows_seconds"]]
            self.assertEqual(found["overlapping_pair_count"], sum(x > 0 for x in overlaps))
            self.assertAlmostEqual(found["sum_pair_overlap_seconds"], sum(overlaps))
            self.assertLessEqual(len(found["examples"]), 10)
        separated = split.replay(request([event(90, spacing=2.0)]))
        self.assertTrue(all(v["overlapping_pair_count"] == 0
                            for v in separated["sessions"][0]["physical_overlap"].values()))
        self.assertEqual([partitions[s]["trial_ids"] for s in split.SPLITS],
                         [separated["sessions"][0]["partitions"][s]["trial_ids"] for s in split.SPLITS])

    def test_reject_malformed_identity_time_state_and_source(self):
        cases = []
        for name, value in (("trial_ids", ["same", "same"]),
                            ("stim_on_seconds", [0, float("inf")]),
                            ("stim_on_seconds", [0, 1e308]),
                            ("stim_on_seconds", [False, 1]),
                            ("eid", "not-in-source")):
            bad = request([event(2)])
            bad["events"][0][name] = value
            cases.append(bad)
        bad = request()
        bad["source_commit"] = "other-revision"
        cases.append(bad)
        bad = request()
        bad["rng_origin"]["seed"] = 0
        cases.append(bad)
        bad = request()
        state = split.encode_state(np.random.RandomState(42))
        state["keys"][0] = -1
        bad["rng_origin"] = {"kind": "captured_pre_split_state", "state": state}
        cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad["events"][0]["eid"]), self.assertRaises(split.ReplayError):
                split.replay(bad)

    def test_cli_checks_existing_evaluator_partition_ids(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source, bundle, output = (root / x for x in ("request.json", "bundle.json", "output.json"))
            source.write_text(json.dumps(request([event(20)])))
            bundle.write_text(json.dumps({"sessions": bundle_sessions(split.replay(request([event(20)])))}))
            result = subprocess.run([sys.executable, "-I", "-B", str(HERE / "source_split.py"),
                                     str(source), str(output), "--verify-bundle", str(bundle)],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["evaluator_trial_identity_check"],
                             "matched exact ordered partitions")


class PinnedSourceParity(unittest.TestCase):
    def check_actual_source_ast_against_sequence_and_checkpoint(self):
        self.assertIsNotNone(SOURCE_PATH, "invoke with --prepare-source to run source oracle")
        body = SOURCE_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),
                         "7583a5a2aea415506bf2294e34d84027fb1b7a652c18a1b711de69afb2a3f7fe")
        names = {"trial_idxs", "train_idxs", "val_idxs", "test_idxs"}
        assignments = [n for n in ast.walk(ast.parse(body)) if isinstance(n, ast.Assign)
                       and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                       and n.targets[0].id in names]
        assignments.sort(key=lambda n: n.lineno)
        self.assertEqual([n.targets[0].id for n in assignments],
                         ["trial_idxs", "train_idxs", "val_idxs", "test_idxs"])
        code = compile(ast.Module(body=assignments, type_ignores=[]), "pinned-author-split", "exec")
        events = [event(90), event(17, 1), event(100, 2)]
        saved = np.random.get_state()
        try:
            np.random.seed(42)
            reference = []
            for e in events:
                namespace = {"np": np, "num_trials": len(e["trial_ids"])}
                exec(code, namespace)
                reference.append([namespace[n].tolist() for n in ("train_idxs", "val_idxs", "test_idxs")])
            expected_final_state = split.encode_state(np.random)
        finally:
            np.random.set_state(saved)
        replayed = split.replay(request(events))
        for observed, expected in zip(replayed["sessions"], reference):
            self.assertEqual([observed["partitions"][s]["aligned_row_indices"] for s in split.SPLITS], expected)
        self.assertEqual(replayed["rng_state_after"], expected_final_state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-source", type=Path)
    args, remaining = parser.parse_known_args()
    SOURCE_PATH = args.prepare_source
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    if SOURCE_PATH is not None:
        suite.addTest(PinnedSourceParity("check_actual_source_ast_against_sequence_and_checkpoint"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"tests_run": result.testsRun, "pinned_source_oracle": SOURCE_PATH is not None,
                      "generated_controls_only": True, "numpy_version": np.__version__}))
    sys.exit(0 if result.wasSuccessful() else 1)

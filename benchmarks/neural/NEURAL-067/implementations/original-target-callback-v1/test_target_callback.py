"""Focused generated target-adapter controls; never read authentic target bodies."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PARSER = argparse.ArgumentParser(description=__doc__)
PARSER.add_argument("--workdir", type=Path, required=True)
PARSER.add_argument("--scorer-path", type=Path, default=HERE.parent / "session-evaluator-v1/scorer.py")
ARGS = PARSER.parse_args()
AUTHOR = ARGS.workdir.resolve()
ROOT = AUTHOR / "generated-fixtures-v1"
SCORER = ARGS.scorer_path
SPEC = importlib.util.spec_from_file_location("neural067_generated_target_callback", HERE / "target_callback.py")
CB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CB)
S = CB.load_scorer(SCORER)
NP = CB.load_reader().np
WRITTEN = 0
WRITE_LIMIT = 1572864
TRAIN = tuple(zip(("19250101T111740", "19250101T112404", "19250108T110520", "19250108T111022", "19250108T111455", "19250113T120811", "19250113T121303", "19250115T110633", "19250115T111328", "19250119T113543", "19250119T114045", "19250120T115044", "19250120T115537"), (10819, 6456, 12233, 6786, 6505, 11646, 11732, 10071, 12267, 11951, 12022, 12078, 11425)))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def write(path, raw):
    global WRITTEN
    if WRITTEN + len(raw) > WRITE_LIMIT:
        raise RuntimeError("prospective generated fixture write ceiling")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    WRITTEN += len(raw)


def fake_pin(label):
    return {"bytes": 100, "sha256": hashlib.sha256(label.encode()).hexdigest()}


def fixture(name, target_mutation=None, metadata_mutation=None, constant=False):
    """All bodies are synthetic; only expected whole-metadata pins are test-patched."""
    root = ROOT / name
    root.mkdir(parents=True)
    rows, assets, train, query, targets = [], [], [], [], {}
    for role, runs in (("train", TRAIN), ("query", [(r, n) for r, _, n in S.QUERY])):
        for i, (run, count) in enumerate(runs):
            asset = {"asset_id": "generated-" + run,
                     "path": f"sub-HumanPitt-held-{'in' if role == 'train' else 'out'}-calib/sub-HumanPitt-held-{'in' if role == 'train' else 'out'}-calib_ses-{run}.nwb",
                     "bytes": 100, "sha256": fake_pin("source-" + run)["sha256"],
                     "url": "https://invalid.example/generated/" + run}
            assets.append(asset)
            inp, target = fake_pin("input-" + run), fake_pin("target-" + run)
            masked = count
            if role == "query":
                velocity = NP.full((count, 7), 0.1, dtype=NP.float64) if constant else NP.tile((NP.arange(count) % 2).astype(NP.float64)[:, None], (1, 7))
                mask = NP.ones(count, dtype=NP.uint8)
                if target_mutation is not None and i == 0:
                    velocity, mask = target_mutation(velocity, mask)
                stream = io.BytesIO()
                NP.savez_compressed(stream, velocity=velocity, eval_mask=mask)
                raw = stream.getvalue()
                target = CB.pin(raw)
                write(root / run / "target.npz", raw)
            row = {**asset, "role": role, "run": run, "day": run[:8], "n_rows": count,
                   "n_masked_rows": masked, "n_trials": 3, "units": CB.UNITS,
                   "columns": list(S.COLUMNS),
                   "channel_ids": "0..175 source row slots, not tracked neuron identity",
                   "prepared": {"input.npz": inp, "target.npz": target}}
            rows.append(row)
            targets[run] = target
            declaration = {"run": run, "day": run[:8], "n_rows": count, "input": inp}
            if role == "train":
                declaration["target"] = target
                train.append(declaration)
            else:
                query.append(declaration)
    for i, (run, _) in enumerate(TRAIN):
        asset = {"asset_id": "generated-minival-" + str(i), "path": "minival/" + run + ".nwb",
                 "bytes": 100, "sha256": fake_pin("minival-" + run)["sha256"],
                 "url": "https://invalid.example/generated/minival/" + run}
        assets.append(asset)
        rows.append({**asset, "role": "duplicate_minival_not_projected"})
    design = {"schema": "neural067_design_v1", "task_id": "NEURAL-067", "person_count": 1,
              "query_label_access": False, "source_code_commit": CB.SOURCE_COMMIT,
              "columns": list(S.COLUMNS), "arms": list(S.ARMS), "train": train, "query": query}
    prep = {"schema": "falcon_h1_shared_preparation_v1", "full_raw_files": 40,
            "distinct_calibration_runs": 27, "minival_duplicates": 13,
            "rows": rows, "prepared_bytes": sum(sum(p["bytes"] for p in r["prepared"].values()) for r in rows if "prepared" in r)}
    if metadata_mutation:
        metadata_mutation(prep, design)
    bodies = {"asset_manifest": encoded({"files": assets}), "design": encoded(design), "preparation": encoded(prep)}
    bodies["private_bindings"] = encoded({"design_sha256": CB.pin(bodies["design"])["sha256"], "targets": targets})
    receipt = {"status": "prepared_source_only", "operator_pin": {"bytes": CB.PRODUCER_PIN[0], "sha256": CB.PRODUCER_PIN[1]},
               "manifest_snapshot_sha256": CB.pin(bodies["asset_manifest"])["sha256"],
               "preparation": {"sha256": CB.pin(bodies["preparation"])["sha256"]},
               "process": {"completion": {"returncode": 0}, "absence_verified": True}}
    actual = {"status": "original40_full27_prepared_and_externally_closed", "native": {"exit_code": 0},
              "closure": {"both_natural_child_returncodes": 0, "native_lease_free_at_observation": True},
              "actual_files": [{"path": "preparation/prepared/" + r["run"] + "/" + n, **p}
                               for r in rows if "prepared" in r for n, p in r["prepared"].items()]}
    bodies["attempt_receipt"], bodies["operator_result"] = encoded(receipt), encoded(actual)
    paths, pins = {}, {}
    for role, body in bodies.items():
        path = root / ("PREPARATION.json" if role == "preparation" else role + ".json")
        write(path, body)
        pins[role] = (len(body), hashlib.sha256(body).hexdigest())
        if role != "preparation":
            paths[role] = path
    return root, paths, pins, {r["run"]: r["input"] for r in query}


def submission(value=2.0):
    return {"schema": "neural067_session_predictions_v1", "contract_sha256": S.CONTRACT_SHA256,
            "columns": list(S.COLUMNS), "entries": [
                {"arm": a, "run": r, "session": s, "row_ids": list(range(n)),
                 "prediction": [[value] * 7 for _ in range(n)]}
                for a in S.ARMS for r, s, n in S.QUERY]}


class Callback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()
        cls.valid = fixture("valid")
        cls.prediction = submission()

    def test_01_full_panel_negative_scores_remain_negative(self):
        root, paths, pins, _ = self.valid
        with patch.dict(CB.EVIDENCE_PINS, pins, clear=True):
            result = CB.grade_submission(self.prediction, root, paths, scorer_path=SCORER)
        self.assertEqual((result["query_runs"], result["query_sessions"], result["full_rows_per_arm"], result["masked_rows_per_arm"]), (14, 7, 34490, 34490))
        for arm in S.ARMS:
            self.assertLess(result["arms"][arm]["held_out_session_r2"]["mean"], 0)
        self.assertFalse(result["access_mode_verified"])
        self.assertFalse(result["causal_program_execution_verified"])

    def test_02_all_constant_targets_remain_undefined(self):
        root, paths, pins, _ = fixture("constant", constant=True)
        with patch.dict(CB.EVIDENCE_PINS, pins, clear=True):
            result = CB.grade_submission(self.prediction, root, paths, scorer_path=SCORER)
        for arm in S.ARMS:
            self.assertIsNone(result["arms"][arm]["held_out_session_r2"]["mean"])
            for score in result["arms"][arm]["by_session"].values():
                self.assertEqual(score["status"], "undefined_all_targets_constant")
                self.assertEqual(score["per_channel_r2"], [None] * 7)

    def test_03_last_prediction_failure_reads_no_private_metadata(self):
        root, paths, _, _ = self.valid
        bad = submission()
        bad["entries"][-1]["prediction"][-1][0] = float("nan")
        with patch.object(CB, "load_reader", side_effect=AssertionError("private reader opened")) as opened:
            with self.assertRaises(ValueError):
                CB.grade_submission(bad, root, paths, scorer_path=SCORER)
        self.assertEqual(opened.call_count, 0)

    def test_04_authenticate_metadata_and_target_before_decode(self):
        root, paths, pins, _ = self.valid
        reader = CB.load_reader()
        bad = dict(pins)
        bad["private_bindings"] = (pins["private_bindings"][0], "0" * 64)
        with patch.dict(CB.EVIDENCE_PINS, bad, clear=True), patch.object(CB, "load_reader", return_value=reader), patch.object(reader, "arrays", side_effect=AssertionError("decode before authentication")) as decode:
            with self.assertRaisesRegex(ValueError, "exact original metadata"):
                CB.grade_submission(self.prediction, root, paths, scorer_path=SCORER)
            self.assertEqual(decode.call_count, 0)
        capture = reader.capture
        def altered(path, cap):
            raw = capture(path, cap)
            return raw[:-1] + bytes([raw[-1] ^ 1]) if Path(path).suffix == ".npz" else raw
        with patch.dict(CB.EVIDENCE_PINS, pins, clear=True), patch.object(CB, "load_reader", return_value=reader), patch.object(reader, "capture", side_effect=altered), patch.object(reader, "arrays", side_effect=AssertionError("decode before authentication")) as decode:
            with self.assertRaisesRegex(ValueError, "same captured authentic target"):
                CB.grade_submission(self.prediction, root, paths, scorer_path=SCORER)
            self.assertEqual(decode.call_count, 0)

    def test_05_strict_target_schema_mask_support_and_finiteness(self):
        def mask_value(y, m):
            m[0] = 2
            return y, m
        def nonfinite(y, m):
            y[0, 0] = NP.inf
            return y, m
        cases = {
            "float32": lambda y, m: (y.astype(NP.float32), m),
            "mask16": lambda y, m: (y, m.astype(NP.uint16)),
            "mask2": mask_value,
            "nonfinite": nonfinite,
            "shortrows": lambda y, m: (y[:-1], m),
            "maskcount": lambda y, m: (y, NP.zeros_like(m)),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                root, paths, pins, _ = fixture(name, target_mutation=change)
                with patch.dict(CB.EVIDENCE_PINS, pins, clear=True):
                    with self.assertRaises(ValueError):
                        CB.grade_submission(self.prediction, root, paths, scorer_path=SCORER)

    def test_06_metadata_units_and_query_support_refuse(self):
        def units(p, d):
            next(r for r in p["rows"] if r["role"] == "query")["units"] = "metres per second"
        def support(p, d):
            d["query"][-1]["n_rows"] -= 1
        for name, change in (("wrong-units", units), ("wrong-support", support)):
            with self.subTest(name=name):
                root, paths, pins, _ = fixture(name, metadata_mutation=change)
                with patch.dict(CB.EVIDENCE_PINS, pins, clear=True):
                    with self.assertRaises(ValueError):
                        CB.grade_submission(self.prediction, root, paths, scorer_path=SCORER)

    def test_07_qualification_emits_counts_without_metric_or_targets(self):
        root, paths, pins, _ = self.valid
        with patch.dict(CB.EVIDENCE_PINS, pins, clear=True), patch.object(CB, "load_scorer", return_value=S), patch.object(S, "grade", side_effect=AssertionError("scientific grade called")), patch.object(S, "metric", side_effect=AssertionError("metric called")):
            result = CB.qualify_targets(root, paths)
        self.assertEqual((len(result["runs"]), result["full_rows"], result["masked_rows"]), (14, 34490, 34490))
        self.assertFalse(result["scientific_score_computed"])
        self.assertFalse(result["readiness_promoted"])
        self.assertNotIn("velocity", json.dumps(result))

    def test_08_bridge_seam_freezes_inputs_and_rejects_wrong_source(self):
        root, paths, pins, inputs = self.valid
        original_module = CB.module
        changed = json.loads(json.dumps(inputs))
        def converted(*args, **kwargs):
            changed.clear()  # Caller mutation cannot replace snapshotted observations.
            return self.prediction
        bridge = types.SimpleNamespace(convert=converted)
        def module(path, expected, name):
            return bridge if expected == CB.BRIDGE_PIN else original_module(path, expected, name)
        with patch.dict(CB.EVIDENCE_PINS, pins, clear=True), patch.object(CB, "module", side_effect=module):
            result = CB.grade_journals([], lambda _: b"", changed, root, paths, scorer_path=SCORER)
        self.assertEqual(result["query_runs"], 14)
        wrong = json.loads(json.dumps(inputs)); wrong[S.QUERY[0][0]]["sha256"] = "0" * 64
        with patch.dict(CB.EVIDENCE_PINS, pins, clear=True), patch.object(CB, "module", side_effect=module):
            with self.assertRaisesRegex(ValueError, "journal observations bound"):
                CB.grade_journals([], lambda _: b"", wrong, root, paths, scorer_path=SCORER)

    def test_09_hostile_public_and_source_paths_refuse_without_private_reads(self):
        root, paths, _, _ = self.valid
        fifo = ROOT / "public.fifo"; os.mkfifo(fifo)
        linked = ROOT / "public.link"; linked.symlink_to(HERE / "target_callback.py")
        wrong = ROOT / "wrong-source.py"
        write(wrong, b"raise AssertionError(\"untrusted source executed\")\n")
        for path in (fifo, linked, wrong):
            with self.subTest(path=str(path)):
                with self.assertRaises(ValueError):
                    CB.module(path, CB.SCORER_PIN, "must_not_execute")
                argv = ["target_callback.py", "--submission", str(path), "--prepared-root", str(root), "--output", str(ROOT / "never-grade.json"), "--scorer-path", str(SCORER)]
                for key, value in paths.items():
                    argv += ["--" + key.replace("_", "-"), str(value)]
                with patch.object(sys, "argv", argv), patch.object(CB._Targets, "initialize", side_effect=AssertionError("private metadata read")) as opened:
                    with self.assertRaises(ValueError):
                        CB.main()
                    self.assertEqual(opened.call_count, 0)
        self.assertFalse((ROOT / "never-grade.json").exists())


class BoundedLog(io.StringIO):
    def write(self, value):
        if self.tell() + len(value.encode()) > 12288:
            raise RuntimeError("generated log cap")
        return super().write(value)


if __name__ == "__main__":
    log = BoundedLog()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Callback))
    body = encoded({"schema": "neural067_generated_target_callback_controls/v1", "tests_run": result.testsRun,
                    "failures": len(result.failures), "errors": len(result.errors), "passed": result.wasSuccessful(),
                    "generated_fixture_cumulative_bytes": WRITTEN, "fixture_limit_bytes": WRITE_LIMIT,
                    "authentic_payload_bytes": 0, "authentic_scores": 0, "runtime_probe_runs": 0,
                    "note": "Whole-metadata pins patched only inside synthetic tests; production has no test-mode switch. Bridge is a mocked composition seam, not a replay or requalification of its existing10 controls."})
    if len(body) > 4096:
        raise RuntimeError("test receipt cap")
    with (AUTHOR / "GENERATED_RESULT.v1.json").open("xb") as stream:
        stream.write(body)
    print(log.getvalue(), end="")
    raise SystemExit(0 if result.wasSuccessful() else 1)

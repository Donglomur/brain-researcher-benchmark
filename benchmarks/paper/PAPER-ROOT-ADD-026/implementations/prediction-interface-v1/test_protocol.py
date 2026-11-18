"""Generated complete-plan metadata and real819-sample observation controls."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("temporal_prediction_protocol", HERE / "protocol.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SOURCE_DIRECTORY = Path(os.environ.get("TEMPORAL_PRODUCER_DIR", HERE.parent / "source-model-producer-v1"))
WRITTEN_BYTES = 0


def pin(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def generated(source):
    rows = [{"trial_type": trial, "img_cat": category, "temp_cond": condition}
            for trial in source.replay.TRIALS for category in source.replay.CATEGORIES
            for condition in range(6)]
    lines = [" ".join(source.replay.HEADER)]
    for i, row in enumerate(rows):
        lines.append(" ".join([row["trial_type"], row["img_cat"], str(row["temp_cond"])] +
                              [str(1000000 + i * 1000 + j) for j in range(819)]))
    raw = ("\n".join(lines) + "\n").encode()
    metadata = {"schema": "temporal026-ordered-source-metadata/v1", "electrodes": [
        {"electrode_id": e["id"], "source_data_sha256": hashlib.sha256(raw).hexdigest(), "rows": rows}
        for e in source.replay.cohort()]}
    manifest = source.replay.freeze(metadata, 20261117)
    variables = {
        "t": ("\n".join(str(i / 512) for i in range(819)) + "\n").encode(),
        "cond_stim": ("\n".join(source.replay.CATEGORIES) + "\n").encode(),
        "cond_temp": b"17\n33\n67\n133\n267\n533\n",
        "timepoints_onepulse": b"10 11\n10 12\n10 13\n10 14\n10 15\n10 16\n",
        "timepoints_twopulse": b"10 11 20 21\n10 12 20 22\n10 13 20 23\n10 14 20 24\n10 15 20 25\n10 16 20 26\n",
    }
    inputs = {"schema": "temporal026-original-input-bindings/v1",
              "variables": {name: pin(name + ".txt", body) for name, body in variables.items()},
              "responses": {e["id"]: pin("response-%02d.txt" % i, raw)
                            for i, e in enumerate(source.replay.cohort())}}
    plans = {branch: source.producer.make_plan(manifest, manifest["manifest_sha256"], inputs,
                                              branch, replay=source.replay)
             for branch in source.replay.BRANCHES}
    return rows, raw, variables, manifest, plans


class ProtocolControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global WRITTEN_BYTES
        cls.source = p.Source(SOURCE_DIRECTORY)
        cls.rows, cls.raw, cls.variables, cls.manifest, cls.plans = generated(cls.source)
        cls.protocols = {branch: p.Protocol(plan, plan["plan_sha256"], cls.manifest,
                                            "a" * 64, "paper_data", cls.source)
                         for branch, plan in cls.plans.items()}
        cls.temp = tempfile.TemporaryDirectory(prefix="generated-observation-", dir=HERE)
        cls.root = Path(cls.temp.name).resolve()
        for name, body in cls.variables.items():
            (cls.root / (name + ".txt")).write_bytes(body)
            WRITTEN_BYTES += len(body)
        (cls.root / "response-00.txt").write_bytes(cls.raw)
        WRITTEN_BYTES += len(cls.raw)
        cls.addClassCleanup(cls.temp.cleanup)

    def first(self, branch="named_response_columns", mode="cv"):
        protocol = self.protocols[branch]
        return protocol, next(j["id"] for j in protocol.ordered_jobs if j["mode"] == mode)

    def test_complete_both_original_plans_and_delivery_order(self):
        for protocol in self.protocols.values():
            self.assertEqual(len(protocol.ordered_jobs), 2054)
            self.assertEqual(len({j["electrode_id"] for j in protocol.ordered_jobs}), 79)
            ordered = protocol.delivery_jobs
            self.assertEqual([j["mode"] for j in ordered], ["cv"] * 1896 + ["full"] * 158)
            for job in ordered:
                info = protocol.job_info(job["id"])
                if job["mode"] == "cv":
                    self.assertEqual((len(info["train_rows"]), len(info["prediction_rows"])), (66, 6))
                    self.assertFalse(set(info["train_rows"]) & set(info["prediction_rows"]))
                else:
                    self.assertEqual(info["column_branch"], "named_response_columns")
                    self.assertEqual(info["train_rows"], info["prediction_rows"])

    def test_named_projection_contains_no_held_response_cells(self):
        protocol, job = self.first()
        observation = protocol.project_job(self.root, job)
        held = {q["source_row"] for q in observation["queries"]}
        self.assertEqual(len(observation["training"]), 66)
        self.assertEqual(len(observation["variables"]["t"]), 819)
        self.assertEqual(observation["target_columns"], [str(i) for i in range(819)])
        for q in observation["queries"]:
            self.assertEqual(set(q), {"source_row", "trial_type", "img_cat", "temp_cond"})
        for row in observation["training"]:
            self.assertNotIn(row["source_row"], held)
            self.assertEqual(len(row["response"]), 819)
            self.assertEqual(row["response"][0], 1000000 + row["source_row"] * 1000)
            self.assertEqual(row["response"][-1], 1000000 + row["source_row"] * 1000 + 818)
        self.assertNotIn("input_bindings", observation)

    def test_positional_projection_and_targets_keep_exact_source_shift(self):
        positional, job = self.first("source_positional_cv")
        named = self.protocols["named_response_columns"]
        a, b = positional.project_job(self.root, job), named.project_job(self.root, job)
        self.assertEqual(a["queries"], b["queries"])
        self.assertEqual(a["target_columns"], ["temp_cond"] + [str(i) for i in range(818)])
        for shifted, original in zip(a["training"], b["training"]):
            self.assertEqual(shifted["response"], [float(shifted["temp_cond"])] + original["response"][:-1])
        ta, tb = positional.targets(self.root, job), named.targets(self.root, job)
        for identity, shifted, original in zip(ta["prediction_identities"], ta["observations"], tb["observations"]):
            self.assertEqual(shifted, [float(identity["temp_cond"])] + original[:-1])

    def test_full_projection_always_exposes_named_all72_and_marks_not_heldout(self):
        for branch in self.protocols:
            protocol, job = self.first(branch, "full")
            observation = protocol.project_job(self.root, job)
            self.assertEqual((len(observation["training"]), len(observation["queries"])), (72, 72))
            self.assertEqual(observation["column_branch"], "named_response_columns")
            self.assertIn("not held-out", observation["exposure"])
            self.assertEqual(observation["training"][0]["response"][0], 1000000)

    def test_assistance_and_method_are_frozen_separate_bindings(self):
        protocol, _ = self.first()
        plan = self.plans["named_response_columns"]
        other = p.Protocol(plan, plan["plan_sha256"], self.manifest, "a" * 64,
                           "paper_data_author_code", self.source)
        self.assertNotEqual(protocol.protocol_sha256, other.protocol_sha256)
        with self.assertRaisesRegex(ValueError, "frozen protocol"):
            protocol.method_sha256 = "b" * 64
        for method, condition in [("x" * 64, "paper_data"), ("a" * 64, "native")]:
            with self.assertRaises(ValueError):
                p.Protocol(plan, plan["plan_sha256"], self.manifest, method, condition, self.source)

    def test_caller_and_returned_metadata_mutation_does_not_change_plan(self):
        plan = copy.deepcopy(self.plans["named_response_columns"])
        manifest = copy.deepcopy(self.manifest)
        protocol = p.Protocol(plan, plan["plan_sha256"], manifest, "a" * 64, "paper_data", self.source)
        first = protocol.ordered_jobs[0]
        plan["jobs"][0]["id"] = "changed"
        manifest["electrodes"][0]["folds"][0]["test_rows"] = []
        returned = protocol.plan
        returned["jobs"][0]["id"] = "changed again"
        info = protocol.job_info(first["id"])
        info["prediction_rows"].clear()
        self.assertEqual(protocol.ordered_jobs[0], first)
        self.assertEqual(len(protocol.job_info(first["id"])["prediction_rows"]), 72)

    def test_unknown_job_and_incomplete_or_optional_plan_refused(self):
        protocol, _ = self.first()
        with self.assertRaisesRegex(ValueError, "unknown"):
            protocol.project_job(self.root, "not-a-job")
        plan = copy.deepcopy(self.plans["named_response_columns"])
        plan["jobs"].pop()
        plan["plan_sha256"] = p.digest({k: v for k, v in plan.items() if k != "plan_sha256"})
        with self.assertRaisesRegex(ValueError, "plan differs"):
            p.Protocol(plan, plan["plan_sha256"], self.manifest, "a" * 64, "paper_data", self.source)
        optional = self.source.producer.make_plan(
            self.manifest, self.manifest["manifest_sha256"],
            self.plans["named_response_columns"]["input_bindings"], "named_response_columns",
            scalings=["none", "S", "P"], replay=self.source.replay)
        self.assertEqual(len(optional["jobs"]), 3081)
        with self.assertRaisesRegex(ValueError, "complete original DN-none/S"):
            p.Protocol(optional, optional["plan_sha256"], self.manifest,
                       "a" * 64, "paper_data", self.source)

    def test_changed_response_body_refused_before_projection(self):
        global WRITTEN_BYTES
        protocol, job = self.first()
        path = self.root / "response-00.txt"
        original = self.raw
        changed = original[:-2] + b"9\n"
        try:
            path.write_bytes(changed); WRITTEN_BYTES += len(changed)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                protocol.project_job(self.root, job)
        finally:
            path.write_bytes(original); WRITTEN_BYTES += len(original)

    def test_mutated_producer_source_is_not_executed(self):
        global WRITTEN_BYTES
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory) / "producer.py"
            raw = b"raise RuntimeError('must not execute')\n"
            path.write_bytes(raw); WRITTEN_BYTES += len(raw)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                p.Source(directory)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        print("CUMULATIVE_GENERATED_FILE_WRITES_BYTES=%d" % WRITTEN_BYTES)

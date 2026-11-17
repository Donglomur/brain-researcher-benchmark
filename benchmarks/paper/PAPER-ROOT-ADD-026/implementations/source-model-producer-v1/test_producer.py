"""Generated-only dispatcher, integrity and complete-roster reduction controls.

One small invented response table is materialized once. All79 identities and
2054 coordinates are exercised as metadata; no authentic response is opened.
"""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import types
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent


def local_module(name, filename):
    import sys
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


producer = local_module("temporal_test_producer", "producer.py")
model = local_module("temporal_test_model_for_dispatch", "model.py")


class AuthenticatedReplayControls(unittest.TestCase):
    def test_loaded_cohort_is_immutable_authenticated_bytes_not_reopened_path(self):
        reference = Path(os.environ.get("TEMPORAL_REPLAY_DIR", HERE.parent / "source-cv-replay-v1"))
        code = producer.bounded_read(reference / "replay.py", 65536)
        roster = producer.bounded_read(reference / "cohort.json", 65536)
        expected = producer.parse_json(roster)["selected"]
        self.assertEqual(len(expected), 79)
        with tempfile.TemporaryDirectory(prefix="temporal-cohort-cache-control-") as directory:
            root = Path(directory)
            (root / "replay.py").write_bytes(code)
            (root / "cohort.json").write_bytes(roster)
            replay = producer.load_replay(root)
            self.assertEqual(replay.cohort(), expected)
            changed = replay.cohort()
            changed[0]["id"] = "mutated returned object"
            self.assertEqual(replay.cohort(), expected)
            replacement = root / "replacement.json"
            replacement.write_bytes(b"{}\n")
            os.replace(replacement, root / "cohort.json")
            self.assertEqual(replay.cohort(), expected)
            self.assertEqual(len(replay.cohort()), 79)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                producer.load_replay(root)


def pin(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def fit_metadata(scaling, success=True):
    names, parameters, _, _ = model.parameter_spec(scaling)
    result = {"parameter_names": list(names), "parameters": parameters.tolist(), "scaling": scaling,
              "success": success, "status": 1 if success else 0, "message": "generated numerical seam",
              "nfev": 1, "njev": 1, "cost": 0., "optimality": 0., "objective_sse": 0.,
              "objective_contract": model.SOURCE_OBJECTIVE,
              "solver_options": {"max_nfev": 500}, "runtime_scipy": "generated-seam",
              "source_runtime": dict(model.SOURCE_RUNTIME),
              "source_default_max_nfev_preserved": True, "historical_runtime_parity": False}
    return result


class NumericalSeam:
    """Tiny explicit fake of numerical fitting; real dispatch/IO remain active."""
    stimulus_timecourse = staticmethod(model.stimulus_timecourse)

    def __init__(self, success=True, error=None, invalid_prediction=False):
        self.calls = []
        self.prediction_calls = []
        self.success = success
        self.error = error
        self.invalid_prediction = invalid_prediction

    def fit(self, X, y, **kwargs):
        if self.error:
            raise ValueError(self.error)
        self.calls.append((X.copy(), y.copy(), copy.deepcopy(kwargs)))
        names, parameters, _, _ = model.parameter_spec(kwargs["scaling"])
        return types.SimpleNamespace(parameters=parameters, success=self.success,
                                     as_dict=lambda: fit_metadata(kwargs["scaling"], self.success))

    def predict(self, stimulus, parameters, **kwargs):
        windows = kwargs["pulse_windows"]
        if len(windows) not in (1, 2) or any(len(row) != 2 for row in windows):
            raise AssertionError("producer must pass source onset/offset pairs to numerical model")
        self.prediction_calls.append(copy.deepcopy(kwargs))
        result = np.arange(819, dtype=float) % 3 * .97 + .047
        if self.invalid_prediction:
            result[30] = np.nan
        if kwargs["components"]:
            return {"response": result, "linear": result, "drive": result, "numerator": result,
                    "normalization_pool": result, "denominator": np.ones(819),
                    "semisaturation": .2, "category_scale": 1.}
        return result


class ProducerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.replay = producer.load_replay(os.environ.get("TEMPORAL_REPLAY_DIR"))
        cls.rows = [{"trial_type": trial, "img_cat": category, "temp_cond": condition}
                    for trial in cls.replay.TRIALS for category in cls.replay.CATEGORIES for condition in range(6)]
        cls.observed = [float(i % 3) for i in range(819)]
        cls.observed[0], cls.observed[-1] = 7., 9.
        tokens = " ".join(str(int(x)) for x in cls.observed)
        cls.raw = (" ".join(cls.replay.HEADER) + "\n" + "\n".join(
            f"{row['trial_type']} {row['img_cat']} {row['temp_cond']} {tokens}" for row in cls.rows) + "\n").encode()
        cls.table_sha = hashlib.sha256(cls.raw).hexdigest()
        cls.cohort = cls.replay.cohort()
        metadata = {"schema": "temporal026-ordered-source-metadata/v1", "electrodes": [
            {"electrode_id": row["id"], "source_data_sha256": cls.table_sha, "rows": cls.rows}
            for row in cls.cohort]}
        cls.manifest = cls.replay.freeze(metadata, 20261117)
        cls.variables = {
            "t": ("\n".join(str(i) for i in range(819)) + "\n").encode(),
            "cond_stim": ("\n".join(cls.replay.CATEGORIES) + "\n").encode(),
            "cond_temp": b"17\n33\n67\n133\n267\n533\n",
            "timepoints_onepulse": b"10 11\n10 12\n10 13\n10 14\n10 15\n10 16\n",
            "timepoints_twopulse": b"10 11 20 21\n10 12 20 22\n10 13 20 23\n10 14 20 24\n10 15 20 25\n10 16 20 26\n",
        }
        cls.inputs = {"schema": "temporal026-original-input-bindings/v1",
                      "variables": {name: pin(name + ".txt", raw) for name, raw in cls.variables.items()},
                      "responses": {row["id"]: pin("response-%02d.txt" % i, cls.raw) for i, row in enumerate(cls.cohort)}}
        cls.plans = {branch: producer.make_plan(cls.manifest, cls.manifest["manifest_sha256"], cls.inputs, branch,
                                               replay=cls.replay) for branch in cls.replay.BRANCHES}
        cls.temporary = tempfile.TemporaryDirectory(prefix="temporal-generated-producer-")
        cls.root = Path(cls.temporary.name)
        for name, raw in cls.variables.items():
            (cls.root / (name + ".txt")).write_bytes(raw)
        (cls.root / "response-00.txt").write_bytes(cls.raw)
        cls.generated_fixture_bytes = len(cls.raw) + sum(map(len, cls.variables.values()))
        assert cls.generated_fixture_bytes < 150000
        cls.addClassCleanup(cls.temporary.cleanup)

    def job(self, branch="named_response_columns", mode="cv", scaling="none", fold=0):
        plan = self.plans[branch]
        identity = self.cohort[0]["id"] + "/DN-" + scaling + "/" + ("full" if mode == "full" else "fold%02d" % fold)
        return plan, identity

    def run_coordinate(self, branch="named_response_columns", mode="cv", scaling="none", fold=0, numerical=None):
        plan, identity = self.job(branch, mode, scaling, fold)
        numerical = numerical or NumericalSeam()
        result = producer.run_job(plan, plan["plan_sha256"], self.manifest, identity, self.root,
                                  self.replay, numerical)
        return result, numerical

    def records(self, plan, transform=None):
        """Streaming2054-result fixture; shape-compatible arrays shared in memory."""
        by_id = {item["electrode_id"]: item for item in self.manifest["electrodes"]}
        trace = [0.] * 819
        component = {key: trace for key in ("response", "linear", "drive", "numerator", "normalization_pool")}
        component.update(denominator=[1.] * 819, semisaturation=.2, category_scale=1.)
        observations = np.asarray(self.observed)
        variance = np.sum((observations - observations.mean()) ** 2) / 819
        cv_traces = {}
        for fold in range(12):
            # Avoid exact decimal half-ties: both levels of source rounding are
            # tested without depending on a floating reconstruction's last bit.
            targets = [.12331 + fold / 1000 + c * .00011 for c in range(6)]
            predictions = [(observations + math.sqrt((1 - target) * variance)).tolist() for target in targets]
            values = [producer.native_r2(self.observed, prediction) for prediction in predictions]
            cv_traces[fold] = (predictions, values)
        for index, job in enumerate(plan["jobs"]):
            item = by_id[job["electrode_id"]]
            if job["mode"] == "full":
                train = query = list(range(72))
            else:
                allocation = item["folds"][job["fold"]]
                train, query = allocation["train_rows"], allocation["test_rows"]
            record = {"schema": producer.RESULT_SCHEMA, "plan_sha256": plan["plan_sha256"],
                      "job": job, "source_data_sha256": item["source_data_sha256"],
                      "train_rows": train, "prediction_rows": query,
                      "prediction_identities": [item["rows"][i] for i in query],
                      "qualification": "unqualified_original_model_output", "status": "converged",
                      "fit": fit_metadata(job["scaling"]), "predictions": [trace] * len(query),
                      "observations": [trace] * len(query)}
            if job["mode"] == "full":
                record["components"] = [component] * 72
                record["exposure"] = "all72 named819 responses used in fit; biological summaries, not held-out performance"
            else:
                predictions, values = cv_traces[job["fold"]]
                rounded = np.round([value["value"] for value in values], 3)
                record.update(condition_r2=values, predictions=predictions,
                              observations=[self.observed] * 6,
                              rounded_condition_r2=rounded.tolist(), fold_r2=float(np.round(np.mean(rounded), 4)),
                              exposure="66 source training conditions; six disjoint queries; fresh original initialization")
            yield transform(index, record) if transform else record

    def collect(self, transform=None, results=None, seed=17):
        plan = self.plans["named_response_columns"]
        return producer.collect(plan, plan["plan_sha256"], self.manifest,
                                self.records(plan, transform) if results is None else results, seed, self.replay)

    def test_complete_metadata_plan_has_all2054_coordinates(self):
        plan = self.plans["named_response_columns"]
        self.assertEqual(len(plan["jobs"]), 2054)
        self.assertEqual(len({row["id"] for row in plan["jobs"]}), 2054)
        self.assertEqual(sum(row["mode"] == "full" for row in plan["jobs"]), 158)
        self.assertEqual(sum(row["mode"] == "cv" for row in plan["jobs"]), 1896)
        self.assertEqual(plan["counts"]["conditions"], 72)
        self.assertEqual(plan["counts"]["electrodes"], 79)
        self.assertEqual(len(list(self.root.glob("response-*.txt"))), 1)
        producer.validate_plan(plan, plan["plan_sha256"], self.manifest, self.replay)

    def test_branch_explicit_full_always_named_and_P_separate(self):
        for branch, plan in self.plans.items():
            self.assertTrue(all(row["response_columns"] == ("named_response_columns" if row["mode"] == "full" else branch)
                                for row in plan["jobs"]))
        expanded = producer.make_plan(self.manifest, self.manifest["manifest_sha256"], self.inputs,
                                      "source_positional_cv", ["none", "S", "P"], self.replay)
        self.assertEqual(len(expanded["jobs"]), 3081)
        self.assertEqual(sum(row["scaling"] == "P" for row in expanded["jobs"]), 1027)
        for bad in (None, "auto", "named", "pooled"):
            with self.assertRaises(ValueError):
                producer.make_plan(self.manifest, self.manifest["manifest_sha256"], self.inputs, bad, replay=self.replay)
        for modes in (["S"], ["none"], ["P"], ["S", "none"], ["none", "S", "P", "P"]):
            with self.assertRaises(ValueError):
                producer.make_plan(self.manifest, self.manifest["manifest_sha256"], self.inputs,
                                   "named_response_columns", modes, self.replay)

    def test_plan_refuses_missing_identity_binding_and_mutation(self):
        bad = copy.deepcopy(self.inputs)
        bad["responses"].pop(self.cohort[-1]["id"])
        with self.assertRaises(ValueError):
            producer.make_plan(self.manifest, self.manifest["manifest_sha256"], bad,
                               "named_response_columns", replay=self.replay)
        bad = copy.deepcopy(self.inputs)
        bad["responses"][self.cohort[0]["id"]]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            producer.make_plan(self.manifest, self.manifest["manifest_sha256"], bad,
                               "named_response_columns", replay=self.replay)
        changed = copy.deepcopy(self.plans["named_response_columns"])
        changed["jobs"].pop()
        changed["plan_sha256"] = producer.digest({k: v for k, v in changed.items() if k != "plan_sha256"})
        with self.assertRaises(ValueError):
            producer.validate_plan(changed, changed["plan_sha256"], self.manifest, self.replay)

    def test_cv_fresh66_training_six_queries_and_exact_column_branches(self):
        seam = NumericalSeam()
        for branch in self.replay.BRANCHES:
            result, _ = self.run_coordinate(branch=branch, scaling="S", numerical=seam)
            self.assertEqual(result["status"], "converged")
            X, Y, kwargs = seam.calls[-1]
            self.assertEqual(X.shape, (66, 819)); self.assertEqual(Y.shape, (66, 819))
            allocation = self.manifest["electrodes"][0]["folds"][0]
            self.assertEqual(result["train_rows"], allocation["train_rows"])
            self.assertEqual(result["prediction_rows"], allocation["test_rows"])
            self.assertFalse(set(result["train_rows"]) & set(result["prediction_rows"]))
            self.assertEqual(len(result["predictions"]), 6)
            self.assertEqual(kwargs["sample_rate"], 512); self.assertEqual(kwargs["max_nfev"], 500)
            self.assertEqual(set(kwargs), {"scaling", "categories", "pulse_windows", "sample_rate", "max_nfev"})
            if branch == "source_positional_cv":
                self.assertEqual(Y[:, 0].tolist(), [self.rows[i]["temp_cond"] for i in allocation["train_rows"]])
                np.testing.assert_array_equal(Y[0, 1:], self.observed[:-1])
            else:
                np.testing.assert_array_equal(Y[0], self.observed)
        self.assertEqual(len(seam.calls), 2)
        self.assertIsNot(seam.calls[0][1], seam.calls[1][1])

    def test_full_fit_uses_all72_named_responses_and_components(self):
        result, seam = self.run_coordinate(branch="source_positional_cv", mode="full", scaling="S")
        self.assertEqual(result["status"], "converged")
        self.assertEqual(seam.calls[0][1].shape, (72, 819))
        np.testing.assert_array_equal(seam.calls[0][1][0], self.observed)
        self.assertEqual(result["prediction_rows"], list(range(72)))
        self.assertEqual(len(result["components"]), 72)
        self.assertEqual(set(result["components"][0]), {"response", "linear", "drive", "numerator",
                         "normalization_pool", "denominator", "semisaturation", "category_scale"})
        self.assertNotIn("fold_r2", result)
        self.assertTrue(all(call["components"] for call in seam.prediction_calls))

    def test_condition_then_fold_rounding_matches_source(self):
        result, _ = self.run_coordinate(branch="source_positional_cv")
        scores = []
        for row, prediction in zip(result["prediction_rows"], result["predictions"]):
            observed = np.array([self.rows[row]["temp_cond"]] + self.observed[:-1])
            center = math.fsum(observed) / len(observed)
            scores.append(1 - math.fsum((observed - prediction) ** 2) /
                          math.fsum((observed - center) ** 2))
        np.testing.assert_allclose([r["value"] for r in result["condition_r2"]], scores, rtol=1e-14, atol=1e-14)
        self.assertEqual(result["rounded_condition_r2"], np.round(scores, 3).tolist())
        self.assertEqual(result["fold_r2"], float(np.round(np.mean(np.round(scores, 3)), 4)))

    def test_numerical_failures_and_nonconvergence_remain_explicit(self):
        for seam in (NumericalSeam(error="generated refusal"), NumericalSeam(invalid_prediction=True)):
            result, _ = self.run_coordinate(numerical=seam)
            self.assertEqual(result["status"], "numerical_failure")
            self.assertIn("error", result)
            self.assertNotIn("predictions", result)
        result, _ = self.run_coordinate(numerical=NumericalSeam(success=False))
        self.assertEqual(result["status"], "nonconverged_source_parameters_retained")
        self.assertFalse(result["fit"]["success"])

    def test_native_r2_undefined_and_finite_are_distinct(self):
        undefined = producer.native_r2([1, 1, 1], [1, 1, 1])
        self.assertIsNone(undefined["value"])
        self.assertTrue(undefined["zero_observed_variance"])
        self.assertEqual(producer.native_r2([0, 1, 2], [0, 1, 2]), {"value": 1., "status": "finite"})
        with self.assertRaises(ValueError): producer.native_r2([0, 1], [0, np.nan])

    def test_complete_streaming_collection_and_electrode_rounding(self):
        output = self.collect()
        self.assertEqual(output["complete_job_count"], 2054)
        self.assertEqual(output["failures"], [])
        self.assertEqual(len(output["full_fit_jobs"]), 158)
        self.assertEqual(len(output["electrode_cv"]), 158)
        expected_folds = [float(np.round(np.mean(np.round([.12331 + f / 1000 + c * .00011 for c in range(6)], 3)), 4)) for f in range(12)]
        expected_electrode = float(np.round(np.mean(expected_folds), 4))
        for row in output["electrode_cv"]:
            self.assertEqual(row["fold_r2"], expected_folds)
            self.assertEqual(row["r2"], expected_electrode)
        self.assertEqual(len(output["figure3_regional_cv"]), 6)
        for row in output["figure3_regional_cv"]:
            self.assertEqual(row["status"], "finite_descriptive")
            self.assertAlmostEqual(row["median"], expected_electrode)
            self.assertEqual(row["interval68"], [expected_electrode, expected_electrode])
        self.assertFalse(output["scientific_qualification"])
        self.assertFalse(output["bootstrap"]["historical_rng_recovered"])

    def test_collection_refuses_missing_duplicate_and_foreign_jobs(self):
        plan = self.plans["named_response_columns"]
        with self.assertRaises(ValueError): self.collect(results=(r for i, r in enumerate(self.records(plan)) if i != 10))
        first = next(self.records(plan))
        def duplicate():
            yield from self.records(plan)
            yield first
        with self.assertRaises(ValueError): self.collect(results=duplicate())
        def foreign(i, row):
            if i == 0: row["job"] = {**row["job"], "id": "invented/DN-none/full"}
            return row
        with self.assertRaises(ValueError): self.collect(transform=foreign)

    def test_collection_refuses_mutated_training_query_source_and_identity(self):
        mutations = [lambda r: r.update(source_data_sha256="0" * 64),
                     lambda r: r.update(train_rows=r["train_rows"][:-1]),
                     lambda r: r.update(prediction_rows=list(reversed(r["prediction_rows"]))),
                     lambda r: r.update(prediction_identities=r["prediction_identities"][:-1]),
                     lambda r: r.update(plan_sha256="0" * 64),
                     lambda r: r.update(job={**r["job"], "response_columns": "pooled"})]
        for mutate in mutations:
            def alter(i, row):
                if i == 1: mutate(row)
                return row
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.collect(transform=alter)

    def test_collection_refuses_forged_rounding_status_and_shape(self):
        mutations = [lambda r: r.update(fold_r2=.9),
                     lambda r: r.update(rounded_condition_r2=[.9] * 6),
                     lambda r: r.update(condition_r2=[{"value": None, "status": "finite"}] * 6),
                     lambda r: r.update(predictions=[[0.] * 818] * 6),
                     lambda r: r.update(status="success"),
                     lambda r: r.update(fit={**r["fit"], "success": False})]
        for mutate in mutations:
            def alter(i, row):
                if i == 1: mutate(row)
                return row
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): self.collect(transform=alter)

    def test_collection_retains_failure_coordinates_and_withholds_summaries(self):
        def fail(i, row):
            if i == 1:
                row = {k: v for k, v in row.items() if k not in {"fit", "predictions", "observations", "condition_r2", "rounded_condition_r2", "fold_r2"}}
                row.update(status="numerical_failure", error="ValueError: generated failure")
            return row
        output = self.collect(transform=fail)
        self.assertEqual(output["complete_job_count"], 2054)
        self.assertEqual(len(output["failures"]), 1)
        self.assertTrue(all(r["status"] == "undefined_incomplete_or_nonfinite" for r in output["figure3_regional_cv"]))
        self.assertIsNone(output["electrode_cv"][0]["r2"])

    def test_bound_member_hash_length_path_symlink_and_hardlink_refusal(self):
        filename = "small-generated.bin"
        raw = b"tiny generated fixture\n"
        target = self.root / filename
        target.write_bytes(raw)
        valid = pin(filename, raw)
        self.assertEqual(producer.read_member(self.root, valid), raw)
        for bad in ({**valid, "sha256": "0" * 64}, {**valid, "bytes": len(raw) + 1},
                    {**valid, "path": "../" + filename}, {**valid, "path": "./" + filename},
                    {**valid, "bytes": True}, {**valid, "unexpected": 1}):
            with self.subTest(pin=bad), self.assertRaises(ValueError): producer.read_member(self.root, bad)
        linked = self.root / "alias-generated.bin"
        linked.symlink_to(filename)
        with self.assertRaises(OSError): producer.read_member(self.root, {**valid, "path": linked.name})
        linked.unlink()
        os.link(target, linked)
        with self.assertRaises(ValueError): producer.read_member(self.root, valid)
        linked.unlink()
        parent = self.root / "parent-alias"
        parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError): producer.read_member(self.root, {**valid, "path": parent.name + "/" + filename})
        parent.unlink(); target.unlink()

    def test_json_and_exclusive_output_refuse_silent_mutations(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError): producer.parse_json(raw)
        path = self.root / "generated-output.json"
        value = {"status": "generated", "count": 8}
        proof = producer.write_new(path, value)
        self.assertEqual(proof["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError): producer.write_new(path, value)
        path.unlink()
        with self.assertRaises(ValueError): producer.write_new(path, value, limit=2)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

"""Generated orchestration controls. No source-law fit or authentic arrays."""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("author_reference_producer", PACKAGE / "producer.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture(n=2, ragged=True, extra_behavior=True):
    people = [f"{i}_epo" for i in range(n)]
    trials = []
    for person in people:
        for condition in p.panel.CONDITIONS:
            for contrast in (5, 20, 80):
                if ragged and person == "1_epo" and contrast == 5:
                    continue
                trials.append(dict(participant=person, epoch=f"{condition}-{contrast}",
                    condition=condition, contrast_percent=contrast, side="left", response="right",
                    rt_ms=700 + contrast, model_end_ms=710 + contrast,
                    event_times_ms=[0, 100, 200, 400, 500]))
    inv = [dict(participant=r["participant"], epoch=r["epoch"], disposition="retained") for r in trials]
    hmp = dict(schema="decision-times-export-v1", purpose="engineering_control",
        sample_rate_hz=512, time_unit="ms", contrast_unit="percent", time_origin="stimulus_onset",
        point_time_method="explicit_point_estimates", expected_participants=people,
        trial_inventory=inv, trials=trials)
    behavior = dict(time_unit="ms", contrast_unit="percent", trial_inventory=copy.deepcopy(inv),
        trials=[{k: v for k, v in r.items() if k not in ("model_end_ms", "event_times_ms")} for r in trials])
    if extra_behavior:
        row = copy.deepcopy(behavior["trials"][0])
        row.update(epoch="behavior-only", rt_ms=1234)
        behavior["trials"].append(row)
        behavior["trial_inventory"].append(dict(participant=row["participant"],
            epoch=row["epoch"], disposition="retained"))
    return dict(schema="decision-times-panel-targets-v2", hmp=hmp, behavior=behavior)


class RecordingBackend:
    def __init__(self, mutate=None, fail_at=None):
        self.calls = []
        self.mutate = mutate
        self.fail_at = fail_at

    def identity(self):
        return {"kind": "generated_recording_no_fit", "scientific_fits": 0}

    def fit_predict(self, law, latencies, contrasts, grid):
        self.calls.append(dict(law=law, latencies=list(latencies), contrasts=list(contrasts), grid=list(grid)))
        if self.fail_at == len(self.calls):
            raise RuntimeError("generated fitting failure")
        result = dict(parameters=[1., 1., 1.] if law == "fechner" else [1., 1.],
            contrast_fraction=list(grid), latency_seconds=[-.1 if law == "linear" else .1 for _ in grid],
            probability_correct=[.75 for _ in grid] if law == "fechner" else None,
            training_mse_seconds2=0.)
        if self.mutate:
            self.mutate(result)
        return result


class ProducerControls(unittest.TestCase):
    def test_complete_ragged_reference_panel_and_unqualified_status(self):
        target = fixture()
        backend = RecordingBackend()
        result = p.produce(target, backend)
        self.assertEqual(result["completed_fit_count"], 3 * 18 * 2 * 4)
        self.assertEqual(len(result["references"]), 3)
        prepared = p.panel.prepare(target)
        for method in result["references"]:
            self.assertEqual(len(method["held_out"]), 18 * 2 * 3)
            self.assertEqual(len(method["full_data"]), 18 * 2 * 3)
            checked = p.panel.score_method(method, prepared, p.panel.target_digest(target), True)
            self.assertEqual(len(checked["cells"]), 18)
        self.assertFalse(result["readiness_promoted"])
        self.assertIsNone(result["paper_win"])
        self.assertEqual(result["backend_identity"]["kind"], "generated_recording_no_fit")

    def test_full_source_cohort_geometry_is_not_silently_subset(self):
        result = p.produce(fixture(26, False, False), RecordingBackend())
        self.assertEqual(result["completed_fit_count"], 3 * 18 * 26 * 4)
        for method in result["references"]:
            self.assertEqual(len(method["full_data"]), 18 * 26 * 3)
            self.assertEqual(len(method["held_out"]), 18 * 26 * 3)
            self.assertEqual({r["participant"] for r in method["held_out"]},
                             {f"{i}_epo" for i in range(26)})

    def test_original_trials_units_incorrect_responses_and_B_H_separation(self):
        target = fixture()
        jobs = list(p.fit_jobs(p.panel.prepare(target)))
        select = lambda name: next(j for j in jobs if j["target"] == name and j["law"] == "linear"
            and j["participant"] == "0_epo" and j["condition"] == "accuracy" and j["mode"] == "full_data")
        rt, stage = select("rt"), select("stimulus_to_C1")
        self.assertEqual(rt["latency_seconds"], [.705, .72, .78, 1.234])
        self.assertEqual(rt["contrast_fraction"], [.05, .2, .8, .05])
        self.assertEqual(len(rt["fit_trial_keys"]), 4)
        self.assertEqual(len(stage["fit_trial_keys"]), 3)
        self.assertTrue(all(r["response"] != r["side"] for r in target["behavior"]["trials"]))
        self.assertEqual(stage["latency_seconds"], [0., 0., 0.])

    def test_ragged_global_omission_preserves_unobserved_person_prediction(self):
        target = fixture()
        prepared = p.panel.prepare(target)
        jobs = list(p.fit_jobs(prepared))
        job = next(j for j in jobs if j["participant"] == "1_epo" and j["mode"] == "held_out"
            and j["omitted_contrast_percent"] == 5)
        self.assertEqual(job["fit_contrasts_percent"], [20., 80.])
        self.assertEqual(job["prediction_contrasts_percent"], [5., 20., 80.])
        result = p.produce(target, RecordingBackend())
        self.assertTrue(any(r["participant"] == "1_epo" and r["contrast_percent"] == 5
            and r["fit_contrasts_percent"] == [20., 80.] for r in result["references"][0]["held_out"]))

    def test_held_contrast_removed_from_every_trial_without_mean_collapse(self):
        target = fixture()
        row = copy.deepcopy(target["hmp"]["trials"][0])
        row["epoch"] = "duplicate-contrast-distinct-trial"
        target["hmp"]["trials"].append(row)
        target["hmp"]["trial_inventory"].append(dict(participant=row["participant"], epoch=row["epoch"], disposition="retained"))
        target["behavior"]["trials"].append({k: v for k, v in row.items() if k not in ("model_end_ms", "event_times_ms")})
        target["behavior"]["trial_inventory"].append(dict(participant=row["participant"], epoch=row["epoch"], disposition="retained"))
        jobs = list(p.fit_jobs(p.panel.prepare(target)))
        selected = [j for j in jobs if j["target"] == "stimulus_to_C1" and j["participant"] == "0_epo"
                    and j["condition"] == "accuracy" and j["law"] == "linear"]
        self.assertEqual(len(selected[0]["fit_trial_keys"]), 4)
        self.assertEqual(len(next(j for j in selected if j["omitted_contrast_percent"] == 5)["fit_trial_keys"]), 2)
        self.assertEqual(len(next(j for j in selected if j["omitted_contrast_percent"] == 20)["fit_trial_keys"]), 3)

    def test_negative_linear_predictions_are_not_clipped(self):
        result = p.produce(fixture(), RecordingBackend())
        method = next(m for m in result["references"] if m["method_id"] == "linear")
        self.assertTrue(all(r["latency_ms"] == -100 for r in method["full_data"] + method["held_out"]))

    def test_backend_failure_does_not_return_partial_reference_panel(self):
        backend = RecordingBackend(fail_at=5)
        with self.assertRaisesRegex(RuntimeError, "generated fitting failure"):
            p.produce(fixture(), backend)
        self.assertEqual(len(backend.calls), 5)

    def test_rejects_malformed_or_nonfinite_source_results(self):
        mutations = [
            lambda r: r.update(latency_seconds=[math.nan] * 3),
            lambda r: r.update(latency_seconds=[True] * 3),
            lambda r: r.update(latency_seconds=[.1]),
            lambda r: r.update(contrast_fraction=[.05, .21, .8]),
            lambda r: r.update(probability_correct=[None] * 3),
            lambda r: r.update(probability_correct=[1.1] * 3),
            lambda r: r.update(training_mse_seconds2=-1),
            lambda r: r.update(parameters=[19., 1., 1.]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    p.produce(fixture(), RecordingBackend(mutate=mutation))

    def test_inconsistent_target_is_rejected_before_first_fit(self):
        target = fixture()
        target["hmp"]["sample_rate_hz"] = 100
        backend = RecordingBackend()
        with self.assertRaisesRegex(ValueError, "512 Hz"):
            p.produce(target, backend)
        self.assertEqual(backend.calls, [])

    def test_source_file_rejected_before_loading_dependencies_or_execution(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "models.py"
            path.write_text("raise RuntimeError('must not execute')\n")
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                p.load_author_backend(path)

    def test_original_adapter_uses_one_fit_and_same_latency_parameters_for_accuracy(self):
        events = []
        class NumpyShim:
            @staticmethod
            def asarray(values, dtype):
                return list(values)
        class Model:
            def __init__(self, law, latencies, contrast):
                events.append(("construct", law, list(latencies), list(contrast)))
                self.pars = [1., 1., 1.]
                self.mse = .25
            def fit(self):
                events.append(("fit",))
            def predictions(self, query, parameters):
                if parameters is not self.pars:
                    raise AssertionError("changed fitted parameters")
                events.append(("latency", tuple(query)))
                return query, [.1] * len(query)
            def predictions_accuracy(self, query, parameters):
                if parameters is not self.pars:
                    raise AssertionError("separately fitted accuracy")
                events.append(("accuracy", tuple(query)))
                return query, [.75] * len(query)
        backend = p.AuthorBackend({"latency": Model}, NumpyShim, p.AUTHOR_SHA256, {})
        result = backend.fit_predict("fechner", [.2, .3], [.05, .2], [.05, .2, .8])
        self.assertEqual([e[0] for e in events], ["construct", "fit", "latency", "accuracy"])
        self.assertEqual(result["training_mse_seconds2"], .25)
        self.assertEqual(result["probability_correct"], [.75] * 3)


if __name__ == "__main__":
    unittest.main()

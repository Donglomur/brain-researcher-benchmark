"""Generated recording shims only; no original source or scientific import/fit."""
import copy
import importlib.util
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings

P = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("original_method_collector", P / "collector.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def fixture():
    trials = [dict(participant="generated-person", epoch=f"{condition}-{contrast}", condition=condition,
        contrast_percent=contrast, side="left", response="right" if contrast == 5 else "left",
        rt_ms=700 + contrast, model_end_ms=710 + contrast, event_times_ms=[11, 111, 211, 411, 511])
        for condition in ("accuracy", "speed") for contrast in (5, 20, 80)]
    inventory = [dict(participant=r["participant"], epoch=r["epoch"], disposition="retained") for r in trials]
    hmp = dict(schema="decision-times-export-v1", purpose="engineering_control", sample_rate_hz=512,
        time_unit="ms", contrast_unit="percent", time_origin="stimulus_onset",
        point_time_method="explicit_point_estimates", expected_participants=["generated-person"],
        trial_inventory=inventory, trials=trials)
    behavior = dict(time_unit="ms", contrast_unit="percent", trial_inventory=copy.deepcopy(inventory),
        trials=[{k: v for k, v in r.items() if k not in ("model_end_ms", "event_times_ms")} for r in trials])
    return dict(schema="decision-times-panel-targets-v2", hmp=hmp, behavior=behavior)


class FakeNumpy:
    @staticmethod
    def asarray(values, dtype):
        return [dtype(v) for v in values]


class FakeDiagnosticArray:
    def __init__(self, values):
        self.values, self.dtype = values, "generated-float64"
        self.shape = (len(values), len(values[0]))

    def tolist(self):
        return copy.deepcopy(self.values)


class Probe:
    def __init__(self, **options):
        self.options, self.calls, self.results, self.models = options, [], [], []

    def optimizer(self, function, x, y, **kwargs):
        self.calls.append((function, x, y, kwargs))
        if self.options.get("warning"):
            warnings.warn("generated optimizer warning", UserWarning)
        if len(self.calls) == self.options.get("fail_at"):
            raise RuntimeError("generated optimizer failure")
        n = len(kwargs["p0"])
        cov = [[float("inf") if self.options.get("nonfinite") else .01 for _ in range(n)] for _ in range(n)]
        if self.options.get("typed_diag"):
            cov = FakeDiagnosticArray(cov)
        info = {"nfev": 3, "fvec": [float("nan") if self.options.get("nonfinite") else .1] * len(x)}
        if self.options.get("unsupported"):
            info["unserializable"] = object()
        result = ([1.0] * n, cov, info, "generated return; not a solver", 4)
        self.results.append(result)
        return result


def backend(**options):
    global scipy
    probe = Probe(**options)
    scipy = SimpleNamespace(optimize=SimpleNamespace(curve_fit=probe.optimizer))
    scientific = scipy

    class ShimLatency:
        def __init__(self, law, latencies, contrast):
            self.name, self.y, self.x = law, latencies, contrast
            self.lat_func = {"linear": self.lm_func, "pieron": self.pieron_func, "fechner": self.wf_diffusion}[law]
            probe.models.append(self)

        def lm_func(self, x, *args):
            raise AssertionError("a generated optimizer must not evaluate a model")

        def pieron_func(self, x, *args):
            raise AssertionError("a generated optimizer must not evaluate a model")

        def wf_diffusion(self, x, *args):
            raise AssertionError("a generated optimizer must not evaluate a model")

        def fit(self):
            bounds = {"linear": ([-float("inf")] * 2, [float("inf")] * 2),
                      "pieron": ([0, 0], [float("inf")] * 2),
                      "fechner": ([0, 0, 0], [18.51, 7.47, 3.69])}[self.name]
            kwargs = dict(p0=[1] * (3 if self.name == "fechner" else 2), bounds=bounds, full_output=True)
            if options.get("bad_p0"):
                kwargs["p0"][0] = 2
            if options.get("bad_bounds"):
                kwargs["bounds"][1][0] = 99
            if options.get("extra_keyword"):
                kwargs["method"] = "invented"
            if options.get("no_call"):
                self.pars, self.mse = [1.0] * len(kwargs["p0"]), .01
                return
            x = list(reversed(self.x)) if options.get("bad_input") else self.x
            self.received = scipy.optimize.curve_fit(self.lat_func, x, self.y, **kwargs)
            if options.get("twice"):
                scipy.optimize.curve_fit(self.lat_func, x, self.y, **kwargs)
            self.pars, _, _, _, _ = self.received
            self.mse = .01

        def predictions(self, query, pars):
            self.prediction_parameters = pars
            return query, [float("nan") if options.get("bad_prediction") else .25] * len(query)

        def predictions_accuracy(self, query, pars):
            self.accuracy_parameters = pars
            return query, [.75] * len(query)

    inner = c.source.AuthorBackend({"latency": ShimLatency}, FakeNumpy, c.source.AUTHOR_SHA256,
                                   {k: "generated-not-installed" for k in ("numpy", "scipy", "pandas", "matplotlib")})
    return inner, probe, scientific


class CollectorControls(unittest.TestCase):
    def assert_restored(self, inner, scientific):
        self.assertIs(inner.factory.fit.__globals__["scipy"], scientific)

    def test_complete_original_job_and_output_join_without_replacing_producer(self):
        targets = fixture()
        original, _, _ = backend()
        expected = c.source.produce(targets, original)
        inner, probe, scientific = backend()
        result = c.collect_injected(targets, inner)
        self.assertEqual(result["status"], "complete_observation")
        self.assertEqual(result["reference_production"]["references"], expected["references"])
        self.assertEqual(result["reference_production"]["fit_receipts"], expected["fit_receipts"])
        self.assertEqual(len(probe.calls), 216)
        self.assertEqual(len(result["optimizer_observations"]), 216)
        jobs = list(c.source.fit_jobs(c.source.panel.prepare(targets)))
        for job, trace in zip(jobs, result["optimizer_observations"]):
            self.assertEqual(trace["fit_input_sha256"], job["fit_input_sha256"])
            self.assertEqual(trace["optimizer_calls"][0]["input_trials"], len(job["fit_trial_keys"]))
            self.assertEqual(trace["optimizer_calls"][0]["returned"]["status"], 4)
        self.assertEqual(result["execution_origin"], "injected_backend_no_authentic_execution")
        self.assertFalse(result["scientific_qualification"])
        self.assert_restored(inner, scientific)

    def test_forwards_original_objects_and_returns_identical_five_value_tuple(self):
        inner, probe, scientific = backend()
        result = c.collect_injected(fixture(), inner)
        self.assertEqual(result["status"], "complete_observation")
        for model, call, returned in zip(probe.models, probe.calls, probe.results):
            function, x, y, kwargs = call
            self.assertIs(function, model.lat_func)
            self.assertIs(x, model.x)
            self.assertIs(y, model.y)
            self.assertIs(returned, model.received)
            self.assertIs(model.prediction_parameters, model.pars)
            if model.name == "fechner":
                self.assertIs(model.accuracy_parameters, model.pars)
            self.assertEqual(set(kwargs), {"p0", "bounds", "full_output"})
        self.assert_restored(inner, scientific)

    def test_nonfinite_diagnostics_are_retained_without_scientific_success(self):
        inner, _, scientific = backend(nonfinite=True, typed_diag=True)
        result = c.collect_injected(fixture(), inner)
        diag = result["optimizer_observations"][0]["optimizer_calls"][0]["returned"]
        self.assertEqual(diag["covariance"][0][0], {"nonfinite": "+inf"})
        self.assertEqual(diag["info"]["fvec"][0], {"nonfinite": "nan"})
        typed = result["optimizer_observations"][0]["optimizer_calls"][0]["return_types"]["covariance"]
        self.assertEqual(typed["dtype"], "generated-float64")
        self.assertEqual(typed["shape"], [len(diag["parameters"])] * 2)
        self.assertEqual(c.diagnostic(2**63 + 1), 2**63 + 1)
        self.assertEqual(result["status"], "complete_observation")
        self.assertFalse(result["readiness_promoted"])
        self.assert_restored(inner, scientific)

    def test_optimizer_failure_retains_partial_diagnostics_without_reference_panel(self):
        inner, probe, scientific = backend(fail_at=3, warning=True)
        with warnings.catch_warnings():
            warnings.simplefilter("always", UserWarning)
            result = c.collect_injected(fixture(), inner)
        self.assertEqual(result["status"], "failed_observation")
        self.assertIsNone(result["reference_production"])
        self.assertEqual(len(probe.calls), 3)
        self.assertEqual([x["status"] for x in result["optimizer_observations"]], ["complete", "complete", "failed"])
        failed = result["optimizer_observations"][-1]
        self.assertIn("generated optimizer failure", failed["optimizer_calls"][0]["error"]["message"])
        self.assertEqual(failed["warnings"][0]["message"], "generated optimizer warning")
        self.assert_restored(inner, scientific)

    def test_inherited_warning_ignore_and_error_actions_are_not_overridden(self):
        for action, status in [("ignore", "complete_observation"), ("error", "failed_observation")]:
            with self.subTest(action=action), warnings.catch_warnings():
                warnings.simplefilter(action, UserWarning)
                filters = list(warnings.filters)
                inner, _, scientific = backend(warning=True)
                result = c.collect_injected(fixture(), inner)
                self.assertEqual(result["status"], status)
                self.assertEqual(warnings.filters, filters)
                self.assertTrue(all(t["warnings"] == [] for t in result["optimizer_observations"]))
                self.assert_restored(inner, scientific)

    def test_changed_explicit_configuration_never_reaches_optimizer(self):
        for option in ("bad_p0", "bad_bounds", "extra_keyword"):
            with self.subTest(option=option):
                inner, probe, scientific = backend(**{option: True})
                result = c.collect_injected(fixture(), inner)
                self.assertEqual(result["status"], "failed_observation")
                self.assertEqual(probe.calls, [])
                self.assertIsNone(result["reference_production"])
                self.assert_restored(inner, scientific)

    def test_reordered_optimizer_trial_vectors_are_refused(self):
        inner, probe, scientific = backend(bad_input=True)
        result = c.collect_injected(fixture(), inner)
        self.assertEqual(result["status"], "failed_observation")
        self.assertIn("operands", result["error"]["message"])
        self.assertEqual(probe.calls, [])
        self.assert_restored(inner, scientific)

    def test_unsupported_diagnostic_serialization_fails_and_restores(self):
        inner, probe, scientific = backend(unsupported=True)
        result = c.collect_injected(fixture(), inner)
        self.assertEqual(result["status"], "failed_observation")
        self.assertEqual(len(probe.calls), 1)
        self.assertIsNone(result["reference_production"])
        self.assertIn("unsupported diagnostic", result["error"]["message"])
        self.assert_restored(inner, scientific)

    def test_missing_and_duplicate_calls_cannot_become_complete_evidence(self):
        for option, delegated in [("no_call", 0), ("twice", 1)]:
            with self.subTest(option=option):
                inner, probe, scientific = backend(**{option: True})
                result = c.collect_injected(fixture(), inner)
                self.assertEqual(result["status"], "failed_observation")
                self.assertEqual(len(probe.calls), delegated)
                self.assertIsNone(result["reference_production"])
                self.assert_restored(inner, scientific)

    def test_original_output_validation_failure_keeps_optimizer_diagnostics(self):
        inner, probe, scientific = backend(bad_prediction=True)
        result = c.collect_injected(fixture(), inner)
        self.assertEqual(result["status"], "failed_observation")
        self.assertIsNone(result["reference_production"])
        self.assertEqual(result["optimizer_observations"][0]["optimizer_calls"][0]["status"], "returned")
        self.assertEqual(len(probe.calls), 1)
        self.assert_restored(inner, scientific)

    def test_original_route_reuses_existing_loader_without_claiming_injected_authenticity(self):
        inner, _, _ = backend()
        with patch.object(c.source, "load_author_backend", return_value=inner) as loader:
            result = c.collect_original(fixture(), "generated-mock-loader-path")
        loader.assert_called_once_with("generated-mock-loader-path")
        self.assertEqual(result["execution_origin"], "existing_hash_pinned_source_loader_route_no_independent_attestation")
        self.assertFalse(result["backend_identity"]["independent_execution_attestation"])
        self.assertEqual(result["backend_identity"]["runtime_versions"]["scipy"], "generated-not-installed")

    def test_mismatched_backend_source_claim_is_refused_before_any_call(self):
        inner, probe, scientific = backend()
        inner.source_hash = "0" * 64
        result = c.collect_injected(fixture(), inner)
        self.assertEqual(result["status"], "failed_observation")
        self.assertEqual(probe.calls, [])
        self.assertEqual(result["optimizer_observations"], [])
        self.assert_restored(inner, scientific)

    def test_existing_loader_failure_is_retained_without_partial_reference_output(self):
        with patch.object(c.source, "load_author_backend", side_effect=ValueError("generated loader rejection")) as loader:
            result = c.collect_original(fixture(), "generated-invalid-source-path")
        loader.assert_called_once_with("generated-invalid-source-path")
        self.assertEqual(result["status"], "failed_observation")
        self.assertEqual(result["failure_stage"], "existing_source_loader")
        self.assertEqual(result["optimizer_observations"], [])
        self.assertIsNone(result["reference_production"])
        self.assertIsNone(result["backend_identity"])

    def test_warning_policy_records_string_compiled_and_empty_patterns_without_mutation(self):
        compiled = re.compile("generated", re.IGNORECASE)
        filters = [("ignore", "plain", UserWarning, "plain.module", 0),
                   ("default", compiled, RuntimeWarning, None, 7),
                   ("default", None, Warning, compiled, 0)]
        with patch.object(warnings, "filters", filters):
            observed = c.warning_filters()
            self.assertIs(warnings.filters, filters)
        self.assertEqual(observed[0]["message"], {"pattern": "plain", "flags": 0, "type": "str"})
        self.assertEqual(observed[1]["message"]["flags"], compiled.flags)
        self.assertEqual(observed[1]["module"], None)
        self.assertEqual(observed[2]["message"], None)
        self.assertEqual(observed[2]["module"]["pattern"], "generated")

    def test_default_warning_suppression_matches_unobserved_producer_and_forwards_handler(self):
        counts = []
        for observed in (False, True):
            messages = []
            def inherited(*args):
                messages.append(args)
            with warnings.catch_warnings():
                warnings.simplefilter("default", UserWarning)
                inner, _, scientific = backend(warning=True)
                with patch.object(warnings, "showwarning", inherited):
                    if observed:
                        result = c.collect_injected(fixture(), inner)
                        self.assertEqual(result["status"], "complete_observation")
                        self.assertEqual(sum(len(x["warnings"]) for x in result["optimizer_observations"]), 1)
                    else:
                        c.source.produce(fixture(), inner)
                    self.assertIs(warnings.showwarning, inherited)
                self.assert_restored(inner, scientific)
            counts.append(len(messages))
            self.assertEqual(len(messages[0]), 6)
            self.assertIs(messages[0][1], UserWarning)
            self.assertIsNone(messages[0][4])
            self.assertIsNone(messages[0][5])
        self.assertEqual(counts, [1, 1])

    def test_inherited_showwarning_exception_is_preserved_and_handler_restored(self):
        received = []
        def inherited(*args):
            received.append(args)
            raise RuntimeError("generated inherited warning handler failure")
        with warnings.catch_warnings():
            warnings.simplefilter("always", UserWarning)
            inner, probe, scientific = backend(warning=True)
            with patch.object(warnings, "showwarning", inherited):
                result = c.collect_injected(fixture(), inner)
                self.assertIs(warnings.showwarning, inherited)
            self.assert_restored(inner, scientific)
        self.assertEqual(len(received), 1)
        self.assertEqual(len(probe.calls), 1)
        self.assertEqual(result["status"], "failed_observation")
        self.assertIsNone(result["reference_production"])
        self.assertIn("inherited warning handler failure", result["error"]["message"])
        self.assertEqual(result["optimizer_observations"][0]["warnings"][0]["message"], "generated optimizer warning")


if __name__ == "__main__":
    unittest.main()

"""Generated interface controls; no author constructor or scientific libraries.

Run with: python3.11 -I -S -B /absolute/path/to/test_producer.py
These fixtures are invented. They do not establish authentic estimator parity.
"""
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import types
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "empirical_estimation_under_test", Path(__file__).with_name("producer.py"))
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def fixtures():
    units = [{"unit_id": f"invented-unit-{i}", "mouse_id": f"invented-mouse-{i % p.N_MICE}",
              "session_id": f"invented-session-{i % p.N_MICE}", "area": "invented-area",
              "fr_hz": 0.0, "lv": None} for i in range(p.N_UNITS)]
    cohort = {"schema": "isttc_empirical_cohort_v1", "source_sha256": "a" * 64,
              "units": units}
    windows = list(p.bridge().window_rows(cohort, 17))
    return cohort, windows


def recording(unit, ticks=None):
    return {"schema": "isttc_empirical_spikes_v1", "unit_id": unit["unit_id"],
            "fs_hz": p.FS, "signal_ticks": p.SIGNAL_TICKS,
            "spike_ticks": [] if ticks is None else ticks}


def records(cohort, windows):
    start, end = windows[0]["windows_ticks"][0]
    for i, unit in enumerate(cohort["units"]):
        ticks = [start, start, end - 1, end] if i == 0 else []
        yield recording(unit, ticks)


class SpyBackend:
    identity = {"kind": "invented_spy", "scientific_execution": False}

    def __init__(self):
        self.calls = 0
        self.first = []

    def fit(self, method, ticks, trials):
        if self.calls < 4:
            self.first.append((method, list(ticks), copy.deepcopy(trials)))
        self.calls += 1
        return p.METHODS.index(method) + 1.25, 0.0, "invented finite fit"


class ProducerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort, cls.windows = fixtures()

    def test_full_population_half_open_trials_and_content_receipt(self):
        backend = SpyBackend()
        estimates, receipt = p.produce(self.cohort, records(self.cohort, self.windows), self.windows, backend)
        self.assertEqual(backend.calls, 23100)
        expected = [(u["unit_id"], m) for u in self.cohort["units"] for m in p.METHODS]
        self.assertEqual([(r["unit_id"], r["method"]) for r in estimates["rows"]], expected)
        self.assertEqual(len(receipt["normalized_recordings"]), 5775)
        self.assertEqual((receipt["units"], receipt["mice"], receipt["fit_coordinates"]),
                         (5775, 26, 23100))
        self.assertEqual(receipt["cohort_sha256"], p.digest(self.cohort))
        self.assertEqual(receipt["windows_sha256"], p.digest(self.windows))
        self.assertEqual(receipt["estimates_sha256"], p.digest(estimates))
        self.assertEqual(receipt["normalized_recordings"][0]["sha256"],
                         p.digest(next(records(self.cohort, self.windows))))
        self.assertEqual(receipt["fit_rows_with_missing_fields"], 0)
        self.assertEqual(receipt["backend"], backend.identity)
        self.assertFalse(receipt["authentic_cohort_qualified"])
        self.assertFalse(receipt["native_numerical_parity_qualified"])
        self.assertIsNone(receipt["paper_reproduction_pass"])
        self.assertEqual([x[0] for x in backend.first], list(p.METHODS))
        for _, ticks, trials in backend.first:
            self.assertEqual(ticks, next(records(self.cohort, self.windows))["spike_ticks"])
            self.assertEqual(len(trials), 40)
            self.assertEqual(trials[0], [0, 0, 29999])
        self.assertEqual(p.bridge().slice_trials([0, 29999, 30000, 30000, 59999],
            [[0, 30000], [30000, 60000], [0, 30000]]),
            [[0, 29999], [0, 0, 29999], [0, 29999]])
        # The output remains in lag bins; the reducer owns the x50 conversion.
        self.assertEqual([r["tau_bins"] for r in estimates["rows"][:4]],
                         [1.25, 2.25, 3.25, 4.25])

    def test_scientific_failures_partial_fields_and_negative_values_retained(self):
        class Failing(SpyBackend):
            def fit(self, method, ticks, trials):
                self.calls += 1
                if not ticks:
                    return -2.0, -0.25, "finite negative values stay visible"
                if method == "acf_full":
                    return math.nan, 0.5, "tau missing"
                if method == "isttc_full":
                    return 0.0, -0.5, "nonpositive tau is not omitted"
                if method == "pearsonr_trial_avg":
                    return 3.0, math.inf, "R-squared missing"
                raise RuntimeError("invented optimizer failure")
        backend = Failing()
        estimates, receipt = p.produce(self.cohort, records(self.cohort, self.windows), self.windows, backend)
        a, b, c, d = estimates["rows"][:4]
        self.assertEqual((a["tau_bins"], a["r_squared"]), (None, 0.5))
        self.assertEqual((b["tau_bins"], b["r_squared"], b["failure_reason"]), (0.0, -0.5, None))
        self.assertEqual((c["tau_bins"], c["r_squared"]), (3.0, None))
        self.assertEqual((d["tau_bins"], d["r_squared"]), (None, None))
        for row in (a, c, d):
            self.assertTrue(row["failure_reason"])
        self.assertEqual(estimates["rows"][4]["tau_bins"], -2.0)
        self.assertEqual(estimates["rows"][4]["r_squared"], -0.25)
        self.assertEqual(receipt["fit_rows_with_missing_fields"], 3)
        self.assertEqual((len(estimates["rows"]), backend.calls), (23100, 23100))

    def test_protocol_mismatch_aborts_instead_of_becoming_fit_failure(self):
        class WrongBackend(SpyBackend):
            def fit(self, method, ticks, trials):
                raise p.BackendProtocolError("wrong author return contract")
        with self.assertRaises(p.BackendProtocolError):
            p.produce(self.cohort, records(self.cohort, self.windows), self.windows, WrongBackend())

    def test_missing_extra_and_reordered_recordings_refused(self):
        valid = list(records(self.cohort, self.windows))
        for rows in (valid[:-1], valid + [valid[-1]], [valid[1], valid[0]] + valid[2:]):
            with self.subTest(size=len(rows), first=rows[0]["unit_id"]):
                with self.assertRaises(ValueError):
                    p.produce(self.cohort, rows, self.windows, SpyBackend())

    def test_recording_clock_extent_population_and_integer_order_refused(self):
        unit = self.cohort["units"][0]
        mutations = ({"fs_hz": 1000}, {"fs_hz": True},
                     {"signal_ticks": p.SIGNAL_TICKS - 1}, {"unit_id": "extra-unit"},
                     {"spike_ticks": [-1]}, {"spike_ticks": [p.SIGNAL_TICKS]},
                     {"spike_ticks": [True]}, {"spike_ticks": [1.0]},
                     {"spike_ticks": [2, 1]}, {"unexpected": 1})
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                row = recording(unit)
                row.update(mutation)
                with self.assertRaises(ValueError):
                    p.validate_recording(row, unit)
        self.assertEqual(p.validate_recording(recording(unit, [1, 1]), unit), [1, 1])
        self.assertEqual(p.validate_recording(recording(unit), unit), [])

    def test_window_population_order_and_clock_are_frozen(self):
        for rows in (self.windows[:-1], self.windows + self.windows[:1],
                     [self.windows[1], self.windows[0]] + self.windows[2:]):
            with self.assertRaises(ValueError):
                p.validate_windows(self.cohort, rows)
        mutations = ({"seed": True}, {"seed": 2**64}, {"seed": 18},
                     {"replicate": 1}, {"fs_hz": 1000}, {"signal_ticks": 1},
                     {"draw_scope": "historical_rng_recovered"},
                     {"windows_ticks": [[0, p.TRIAL_TICKS]] * 39},
                     {"windows_ticks": [[1, p.TRIAL_TICKS]] * 40},
                     {"windows_ticks": [[-1, p.TRIAL_TICKS - 1]] * 40},
                     {"windows_ticks": [[p.SIGNAL_TICKS - p.TRIAL_TICKS + 1,
                                          p.SIGNAL_TICKS + 1]] * 40})
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                rows = list(self.windows)
                rows[0] = dict(rows[0], **mutation)
                with self.assertRaises(ValueError):
                    p.validate_windows(self.cohort, rows)
        changed = list(self.windows)
        intervals = [list(w) for w in changed[0]["windows_ticks"]]
        intervals[0] = [intervals[0][0] + 1, intervals[0][1] + 1]
        changed[0] = dict(changed[0], windows_ticks=intervals)
        backend = SpyBackend()
        with self.assertRaisesRegex(ValueError, "prospective seed"):
            p.produce(self.cohort, records(self.cohort, self.windows), changed, backend)
        self.assertEqual(backend.calls, 0)

    def test_full_cohort_and_mouse_population_required_before_fit(self):
        for units in (self.cohort["units"][:-1],
                      [dict(u, mouse_id="one-mouse") for u in self.cohort["units"]]):
            backend = SpyBackend()
            with self.assertRaises(ValueError):
                p.produce(dict(self.cohort, units=units), [], self.windows, backend)
            self.assertEqual(backend.calls, 0)


def author_spy():
    """Construct no scientific dependency; record the actual adapter's calls."""
    backend = p.AuthorBackend.__new__(p.AuthorBackend)
    calls = []
    backend.np = types.SimpleNamespace(asarray=lambda values: tuple(values))

    def operation(name, result):
        def call(*args, **kwargs):
            calls.append((name, args, kwargs))
            return result
        return call

    full_curve = list(range(21))
    trial_curve = list(range(20))
    backend.spikes = types.SimpleNamespace(
        bin_spike_train_fixed_len=operation("bin_full", "full-bins"),
        bin_trials=operation("bin_trials", "trial-bins"))
    backend.acf = operation("acf", full_curve)
    backend.curves = types.SimpleNamespace(
        acf_sttc=operation("sttc_full", full_curve),
        acf_pearsonr_trial_avg=operation("pearson_trials", ("matrix", trial_curve)),
        acf_sttc_trial_concat=operation("sttc_concat", trial_curve))
    backend.fitter = types.SimpleNamespace(func_single_exp=object(),
        fit_single_exp=operation("fit", ("popt", "pcov", 2.25, "ci", -0.5,
                                          "explained-variance", "invented fit")))
    return backend, calls


class AuthorCallControls(unittest.TestCase):
    def test_verified_source_refuses_wrong_bytes_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'benign_helper.py'
            marker = Path(directory) / 'executed.txt'
            body = ('from pathlib import Path\nPath(' + repr(str(marker)) +
                    ').write_text("invented execution")\nvalue = 73\n').encode()
            source.write_bytes(body)
            with self.assertRaisesRegex(ValueError, 'source bytes differ'):
                p._verified_module(source, '0' * 64, 'invented_wrong_pin')
            self.assertFalse(marker.exists())
            admitted_hash = hashlib.sha256(body).hexdigest()
            module = p._verified_module(source, admitted_hash, 'invented_admitted')
            self.assertEqual(module.value, 73)
            self.assertEqual(marker.read_text(), 'invented execution')
            marker.unlink()
            source.write_bytes(body + b'raise RuntimeError("changed source")\n')
            with self.assertRaisesRegex(ValueError, 'source bytes differ'):
                p._verified_module(source, admitted_hash, 'invented_changed')
            self.assertFalse(marker.exists())

    def test_malformed_backend_fields_and_shapes_are_protocol_errors(self):
        malformed = [(None, 0.5, "failed"), ("1.0", 0.5, "string"),
                     (True, 0.5, "boolean"), (1.0, False, "boolean"),
                     (1.0, 0.5), (1.0, 0.5, "extra", 0), {"tau": 1.0}]
        for result in malformed:
            with self.subTest(result=result):
                backend = types.SimpleNamespace(fit=lambda *args: result)
                with self.assertRaises(p.BackendProtocolError):
                    p._fit_row("invented", "acf_full", backend, [], [])

    def test_exact_four_author_calls_clocks_support_and_single_fit(self):
        backend, calls = author_spy()
        ticks, trials = [0, 1500, 30000], [[0, 1499], [1500]] * 20
        for method in p.METHODS:
            self.assertEqual(backend.fit(method, ticks, trials), (2.25, -0.5, "invented fit"))
        by_name = {name: (args, kwargs) for name, args, kwargs in calls if name != "fit"}
        self.assertEqual(by_name["bin_full"], ((ticks, 50, 30000, 54000000), {"verbose_": False}))
        self.assertEqual(by_name["acf"], (("full-bins",), {"nlags": 20}))
        self.assertEqual(by_name["sttc_full"], ((tuple(ticks), 20),
            {"lag_shift_": 1500, "sttc_dt_": 750, "signal_length_": 54000000, "verbose_": False}))
        self.assertEqual(by_name["bin_trials"], ((trials, 30000, 1500), {}))
        self.assertEqual(by_name["pearson_trials"], (("trial-bins", 20), {"verbose_": False}))
        self.assertEqual(by_name["sttc_concat"], (([tuple(t) for t in trials],),
            {"n_lags_": 20, "lag_shift_": 1500, "sttc_dt_": 750,
             "trial_len_": 30000, "zero_padding_len_": 90000, "verbose_": False}))
        fitted = [(args, kw) for name, args, kw in calls if name == "fit"]
        self.assertEqual(len(fitted), 4)
        self.assertEqual([len(args[0]) for args, _ in fitted], [21, 21, 20, 20])
        for _, kwargs in fitted:
            self.assertEqual(kwargs, {"start_idx_": 1, "exp_fun_": backend.fitter.func_single_exp})

    def test_author_curve_and_fit_return_mismatches_are_fatal(self):
        for method in p.METHODS:
            backend, calls = author_spy()
            if method == "acf_full":
                backend.acf = lambda *a, **k: [0] * 20
            elif method == "isttc_full":
                backend.curves.acf_sttc = lambda *a, **k: [0] * 20
            elif method == "pearsonr_trial_avg":
                backend.curves.acf_pearsonr_trial_avg = lambda *a, **k: ([], [0] * 21)
            else:
                backend.curves.acf_sttc_trial_concat = lambda *a, **k: [0] * 21
            with self.subTest(method=method):
                with self.assertRaises(p.BackendProtocolError):
                    backend.fit(method, [], [[]] * 40)
                self.assertFalse(any(name == "fit" for name, _, _ in calls))
        backend, _ = author_spy()
        backend.fitter.fit_single_exp = lambda *a, **k: (1, 2, 3)
        with self.assertRaises(p.BackendProtocolError):
            backend.fit("acf_full", [], [[]] * 40)

    def test_nonrepresentable_fit_units_preserve_other_field(self):
        backend = types.SimpleNamespace(fit=lambda *a: (1e308, -0.25, "overflow after ms conversion"))
        row = p._fit_row("invented", "acf_full", backend, [], [])
        self.assertIsNone(row["tau_bins"])
        self.assertEqual(row["r_squared"], -0.25)
        self.assertTrue(row["failure_reason"])

    def test_strict_json_refuses_duplicates_and_nonfinite_tokens(self):
        for body in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}'):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    p.strict_json(body)


if __name__ == "__main__":
    unittest.main()

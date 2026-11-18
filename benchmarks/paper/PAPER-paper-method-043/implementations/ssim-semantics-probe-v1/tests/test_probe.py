"""Generated mathematical and compatibility controls; no paper observations."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

SPEC = importlib.util.spec_from_file_location("neuropictor_probe", Path(__file__).resolve().parents[1] / "probe.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def independent_filter_score(x, y, channel=False):
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    def smooth(z):
        if channel:
            return gaussian_filter1d(z, axis=0, sigma=1.5, truncate=3.5, mode="reflect")
        return gaussian_filter(z, sigma=1.5, truncate=3.5, mode="reflect")
    mx, my = smooth(x), smooth(y)
    vx, vy, cov = smooth(x*x)-mx*mx, smooth(y*y)-my*my, smooth(x*y)-mx*my
    z = ((2*mx*my + .0001)*(2*cov + .0009)
         / ((mx*mx+my*my+.0001)*(vx+vy+.0009)))
    return float(z[5:-5, :].mean() if channel else z[5:-5, 5:-5].mean())


class Arithmetic(unittest.TestCase):
    def test_scalar_reference_against_independent_separable_filters(self):
        for name, x, y in p.generated_pairs():
            with self.subTest(name=name):
                got = p.reference_scores(x, y)
                self.assertAlmostEqual(got[p.MODES[0]], independent_filter_score(x, y), places=11)
                self.assertAlmostEqual(got[p.MODES[1]], independent_filter_score(x, y, True), places=11)
                self.assertGreater(abs(got[p.MODES[0]] - got[p.MODES[1]]), .001)

    def test_constant_pair_has_analytic_luminance_score(self):
        x = [[.2]*19 for _ in range(17)]
        y = [[.6]*19 for _ in range(17)]
        expected = (2*.2*.6+.0001)/(.2**2+.6**2+.0001)
        for score in p.reference_scores(x, y).values():
            self.assertAlmostEqual(score, expected, places=11)

    def test_identity_and_shape_range_guards(self):
        _, x, _ = p.generated_pairs()[0]
        self.assertTrue(all(abs(v-1)<1e-12 for v in p.reference_scores(x, x).values()))
        for invalid in ([[0.]*10]*23, [[0.]*29]*10, [[False]*29]*23,
                        [[float("nan")]*29]*23, [[1.1]*29]*23):
            with self.subTest(kind=str(invalid[0][0])):
                with self.assertRaises(p.ProbeError):
                    p.reference_scores(invalid, x)


class EnvironmentDiagnosis(unittest.TestCase):
    def test_exact_author_keywords_and_two_dimensional_call(self):
        calls = []
        def ssim(x, y, **kwargs):
            calls.append((x.shape, x.dtype.name, kwargs))
            return independent_filter_score(x, y)
        result = p.probe_callable(ssim, runtime={"fixture": "generated callable"})
        self.assertEqual(result["observed_semantics"], p.MODES[0])
        self.assertEqual(len(calls), 4)
        self.assertEqual({r[1] for r in calls}, {"float32", "float64"})
        self.assertTrue(all(r[2] == p.CALL_KWARGS for r in calls))
        self.assertFalse(result["historical_environment_identified"])
        self.assertFalse(result["native_metric_parity_verified"])
        self.assertFalse(result["paper_reproduction_established"])

    def test_last_axis_channel_branch(self):
        result = p.probe_callable(lambda x, y, **kw: independent_filter_score(x, y, True))
        self.assertEqual(result["observed_semantics"], p.MODES[1])

    def test_mixed_dtype_semantics_are_not_classified(self):
        result = p.probe_callable(lambda x, y, **kw: independent_filter_score(x, y, x.dtype == np.float32))
        self.assertIsNone(result["observed_semantics"])
        self.assertFalse(result["all_generated_calls_classified_consistently"])

    def test_nonfinite_nonscalar_constant_and_boolean_rejected(self):
        for output in (np.nan, np.inf, [1.], True, 1.):
            result = p.probe_callable(lambda x, y, **kw: output)
            self.assertIsNone(result["observed_semantics"])

    def test_exception_and_input_mutation_preserved(self):
        def rejected(x, y, **kwargs):
            raise TypeError("multichannel is not supported")
        result = p.probe_callable(rejected)
        self.assertTrue(all(r["exception_type"] == "TypeError" for r in result["observations"]))
        def mutated(x, y, **kwargs):
            score = independent_filter_score(x, y)
            x[0,0] = .5
            return score
        result = p.probe_callable(mutated)
        self.assertIsNone(result["observed_semantics"])
        self.assertTrue(all("mutated" in r["exception_message"] for r in result["observations"]))

    def test_report_exclusive_creation_and_no_forged_history(self):
        result = p.probe_callable(lambda x, y, **kw: independent_filter_score(x, y))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"probe.json"
            p.write_report(path, result)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["status"], "generated_environment_diagnostic_only")
            self.assertFalse(saved["paper_improvement_established"])
            with self.assertRaises(FileExistsError):
                p.write_report(path, result)


if __name__ == "__main__":
    unittest.main()

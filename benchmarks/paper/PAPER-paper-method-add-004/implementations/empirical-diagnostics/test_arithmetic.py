import unittest
import statistics
import empirical_bridge as e
from test_generated import unit, estimates
class ArithmeticControls(unittest.TestCase):
    def test_finite_pseudo_errors_cannot_emit_infinite_median(self):
        units=[unit("a"),unit("b")];rows=estimates(units)
        for u in units:
            rows[(u["unit_id"],"acf_full")]["tau_bins"]=1e-306
            rows[(u["unit_id"],"pearsonr_trial_avg")]["tau_bins"]=1.0
        with self.assertRaisesRegex(ValueError,"finite real"):
            e.reduce_rows(units,rows)
    def test_fmean_intermediate_overflow_is_explicit_refusal(self):
        with self.assertRaisesRegex(ValueError,"numeric summary"):
            e.finite_summary(statistics.fmean,[1e306]*1000)
if __name__=="__main__":unittest.main(verbosity=2)

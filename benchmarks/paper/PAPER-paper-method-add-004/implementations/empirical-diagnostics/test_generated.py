import copy
import json
import random
import unittest
import empirical_bridge as e

def unit(uid, mouse="mouse1"):
    return dict(unit_id=uid, mouse_id=mouse, session_id="session1", area="VISp",
                fr_hz=3.0, lv=0.8)

def estimates(units):
    vals = {"acf_full": 2.0, "isttc_full": 4.0,
            "pearsonr_trial_avg": 3.0, "sttc_trial_concat": 5.0}
    return {(u["unit_id"], m): dict(unit_id=u["unit_id"], method=m,
             tau_bins=vals[m], r_squared=0.7, failure_reason=None)
            for u in units for m in e.METHODS}

class Controls(unittest.TestCase):
    def test_author_start_support_and_endpoint(self):
        class Endpoint:
            def randrange(self, a, b):
                self.range = (a, b)
                return b - 1
        rng = Endpoint()
        self.assertEqual(e.draw_windows(rng, 10, 3, 2), [[7,10],[7,10]])
        self.assertEqual(rng.range, (0,8))

    def test_repeats_overlap_and_half_open(self):
        self.assertEqual(e.slice_trials([0,2,3,4,7], [[0,3],[2,5],[0,3]]),
                         [[0,2],[0,1,2],[0,2]])

    def test_deterministic_uniform_draw_matches_author_loop(self):
        a, b = random.Random(49), random.Random(49)
        expected = [[s,s+30] for s in [a.randrange(0,301-30+1) for _ in range(40)]]
        self.assertEqual(e.draw_windows(b,301,30,40), expected)

    def test_paired_full_reference_is_method_specific(self):
        units=[unit("a")]; report=e.reduce_rows(units,estimates(units))
        self.assertEqual(report["records"][0]["pseudo_ree_percent"],
                         {"pearsonr_trial_avg":50.0,"sttc_trial_concat":25.0})
        self.assertEqual(report["records"][0]["tau_ms"]["isttc_full"],200.0)

    def test_inclusive_thresholds(self):
        units=[unit("a")]; report=e.reduce_rows(units,estimates(units))
        self.assertEqual(report["summaries"]["pearsonr_trial_avg"]["within_percent"]["50"],100)
        self.assertEqual(report["summaries"]["pearsonr_trial_avg"]["within_percent"]["25"],0)

    def test_all_method_missing_union_and_ordered_exclusion(self):
        units=[unit("a"),unit("b"),unit("c")]; rows=estimates(units)
        rows[("a","acf_full")].update(tau_bins=None,failure_reason="fit failed")
        rows[("a","isttc_full")]["r_squared"]=-0.1
        rows[("b","sttc_trial_concat")]["r_squared"]=-0.2
        report=e.reduce_rows(units,rows)
        self.assertEqual(report["counts"],dict(original_units=3,
            missing_fit_or_covariate=1,negative_r2_after_missing=1,
            complete_cases=1,undefined_reference=0))
        self.assertEqual([r["unit_id"]for r in report["records"]],["a","b","c"])

    def test_missing_covariate_retained(self):
        units=[unit("a")];units[0]["lv"]=None
        self.assertEqual(e.reduce_rows(units,estimates(units))["records"][0]["status"],
                         "missing_fit_or_covariate")

    def test_r_squared_zero_is_retained(self):
        units=[unit("a")];rows=estimates(units)
        rows[("a","acf_full")]["r_squared"]=0
        self.assertEqual(e.reduce_rows(units,rows)["counts"]["complete_cases"],1)

    def test_zero_reference_is_explicit_not_dropped(self):
        units=[unit("a")];rows=estimates(units);rows[("a","acf_full")]["tau_bins"]=0
        report=e.reduce_rows(units,rows)
        self.assertFalse(report["numeric_complete"])
        self.assertEqual(report["records"][0]["status"],"undefined_reference")

    def test_coordinate_order_does_not_change_reference_pair(self):
        units=[unit("a"),unit("b")];rows=estimates(units)
        shuffled=dict(reversed(list(rows.items())))
        self.assertEqual(e.reduce_rows(units,rows),e.reduce_rows(units,shuffled))

    def test_missing_and_duplicate_coordinates_rejected(self):
        units=[unit("a")];rows=list(estimates(units).values())
        with self.assertRaises(ValueError):
            e.estimate_rows(dict(schema="isttc_empirical_estimates_v1",rows=rows[:-1]),units)
        with self.assertRaises(ValueError):
            e.estimate_rows(dict(schema="isttc_empirical_estimates_v1",rows=rows[:3]+rows[:1]),units)

    def test_nonfinite_boolean_and_undocumented_failure_rejected(self):
        for value in [True,float("inf"),float("nan")]:
            with self.assertRaises(ValueError): e.finite(value)
        units=[unit("a")];rows=list(estimates(units).values());rows[0]["tau_bins"]=None
        with self.assertRaises(ValueError):
            e.estimate_rows(dict(schema="isttc_empirical_estimates_v1",rows=rows),units)

    def test_full_population_gate_without_scientific_data(self):
        units=[{**unit(str(i),str(i%26)), "area": e.AREAS[i % len(e.AREAS)]}
               for i in range(5775)]
        doc=dict(schema="isttc_empirical_cohort_v1",source_sha256="0"*64,units=units)
        self.assertEqual(len(e.cohort(doc)),5775)
        for malformed in [units[:-1],units[:-1]+units[:1]]:
            with self.assertRaises(ValueError):e.cohort({**doc,"units":malformed})
        changed=[{**u,"mouse_id":"one_mouse"} for u in units]
        with self.assertRaises(ValueError):e.cohort({**doc,"units":changed})

    def test_full_cohort_requires_source_area_membership_and_coverage(self):
        units=[{**unit(str(i),str(i%26)), "area": e.AREAS[i % len(e.AREAS)]}
               for i in range(5775)]
        doc=dict(schema="isttc_empirical_cohort_v1",source_sha256="0"*64,units=units)
        # Correct dimensions alone must not admit a substituted area population.
        unknown=[dict(u) for u in units]
        unknown[0]["area"]="CA1"
        with self.assertRaisesRegex(ValueError,"unknown empirical source area"):
            e.cohort({**doc,"units":unknown})
        for missing in e.AREAS:
            replacement=next(area for area in e.AREAS if area != missing)
            incomplete=[{**u,"area":replacement if u["area"]==missing else u["area"]}
                        for u in units]
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(ValueError,"complete eight-area cohort required"):
                    e.cohort({**doc,"units":incomplete})
        single_area=[{**u,"area":"VISp"} for u in units]
        with self.assertRaisesRegex(ValueError,"complete eight-area cohort required"):
            e.cohort({**doc,"units":single_area})
        # Unequal counts and arbitrary input order remain allowed; authentic
        # per-area counts/identities are an external scientific requirement.
        self.assertEqual(e.cohort({**doc,"units":list(reversed(units))}),list(reversed(units)))
        skewed=[{**u,"area":e.AREAS[i] if i < len(e.AREAS) else "VISp"}
                for i,u in enumerate(units)]
        self.assertEqual(e.cohort({**doc,"units":skewed}),skewed)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):e.strict_json('{"a":1,"a":2}')
        with self.assertRaises(ValueError):e.strict_json('{"a":NaN}')

    def test_full_estimator_submission_keeps_missingness_differences(self):
        units=[{**unit(str(i),str(i%26)), "area": e.AREAS[i % len(e.AREAS)]}
               for i in range(5775)]
        c=dict(schema="isttc_empirical_cohort_v1",source_sha256="0"*64,units=units)
        ref=list(estimates(units).values());candidate=[dict(row) for row in ref]
        candidate[0].update(tau_bins=None,failure_reason="candidate failed")
        result=e.compare_reproduction(c,dict(schema="isttc_empirical_estimates_v1",rows=candidate),
                                     dict(schema="isttc_empirical_estimates_v1",rows=ref))
        self.assertEqual(result["method_coordinates"],23100)
        self.assertEqual(len(result["availability_mismatches"]),1)
        self.assertEqual(result["candidate_reduction"]["counts"]["original_units"],5775)
        self.assertEqual(result["errors_by_quantity"]["r_squared"]["compared_values"],23100)
        self.assertIsNone(result["scientific_pass"])
        self.assertFalse(result["full_output_support_matched"])
        self.assertTrue(all(value["mean_absolute_difference"] is None for value in result["errors_by_quantity"].values()))

    def test_undefined_reference_never_shrinks_denominator(self):
        units=[unit("a"),unit("b")];rows=estimates(units)
        rows[("a","acf_full")]["tau_bins"]=0
        report=e.reduce_rows(units,rows)
        summary=report["summaries"]["pearsonr_trial_avg"]
        self.assertEqual(summary["complete_case_denominator"],2)
        self.assertEqual(summary["defined_count"],1)
        self.assertFalse(summary["support_complete"])
        self.assertTrue(all(value is None for value in summary["within_percent"].values()))
        self.assertIsNone(summary["median_pseudo_ree_percent"])

    def test_tau_unit_conversion_overflow_refused(self):
        units=[unit("a")];rows=list(estimates(units).values());rows[0]["tau_bins"]=1e308
        with self.assertRaises(ValueError):
            e.estimate_rows(dict(schema="isttc_empirical_estimates_v1",rows=rows),units)

if __name__=="__main__":unittest.main(verbosity=2)


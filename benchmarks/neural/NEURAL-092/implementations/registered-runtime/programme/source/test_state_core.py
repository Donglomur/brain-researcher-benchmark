"""Invented metadata and rates only; no recordings, models or empirical fits."""
import importlib.util
from pathlib import Path
import hashlib
import json
import sys
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("neural092_state_generated", Path(__file__).with_name("state_core.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def row(uid, onset, run="REST", pupil="LOW", condition=("grating", 0.), block=0):
    return {"id": uid, "onset": onset, "run_bin": run, "pupil_bin": pupil,
            "condition_key": condition, "block": block}


def metadata(uid, area, rate=2., presence=.98, isi=.2, amp=.02):
    return {"unit_id": uid, "area": area, "FITbaseline": rate,
            "presence_ratio": presence, "isi_violations": isi, "amplitude_cutoff": amp}


class StateTests(unittest.TestCase):
    def test_chronological_zip_and_no_reuse(self):
        rows = [row("l2", 3.), row("h2", 4., "RUN"), row("l1", 1.), row("h1", 2., "RUN"), row("extra", 5.)]
        p = m.deterministic_pairs(rows)
        self.assertEqual([(x["low_id"], x["high_id"]) for x in p.pairs], [("l1", "h1"), ("l2", "h2")])
        self.assertEqual(p.unused, ({"index": 4, "id": "extra", "reason": "unmatched_low"},))
        self.assertEqual(len(set(p.low_indices + p.high_indices)), 4)

    def test_exact_condition_block_and_other_state_match(self):
        rows = [row("low", 0.), row("wrong_condition", 1., "RUN", condition=("grating", 90.)),
                row("wrong_block", 2., "RUN", block=1), row("wrong_pupil", 3., "RUN", "HIGH")]
        p = m.deterministic_pairs(rows)
        self.assertEqual(len(p.pairs), 0)
        self.assertEqual(len(p.unused), 4)

    def test_missing_pupil_only_allowed_for_running(self):
        rows = [row("low", 0., pupil="MISSING"), row("high", 1., "RUN", "MISSING"),
                row("transition", 2., "TRANSITION", "LOW"), row("unknown", 3., "MISSING", "HIGH")]
        running = m.deterministic_pairs(rows)
        self.assertEqual(running.report()["missing_pupil_pairs"], 1)
        self.assertEqual(len(running.unused), 2)
        pupil = m.deterministic_pairs(rows, "pupil")
        self.assertEqual(len(pupil.pairs), 0)
        self.assertEqual(len(pupil.unused), 4)

    def test_pupil_matches_low_high_same_running_bin(self):
        rows = [row("lo", 1., "RUN", "LOW"), row("hi", 2., "RUN", "HIGH"),
                row("rest_hi", 3., "REST", "HIGH"), row("middle", 4., "RUN", "MID")]
        p = m.deterministic_pairs(rows, "pupil")
        self.assertEqual([(x["low_id"], x["high_id"]) for x in p.pairs], [("lo", "hi")])
        self.assertEqual({x["reason"] for x in p.unused}, {"unmatched_high", "excluded_pupil_mid"})

    def test_pair_ids_are_permutation_invariant_with_onset_ties(self):
        rows = [row("lb", 1.), row("la", 1.), row("hb", 2., "RUN"), row("ha", 2., "RUN")]
        a = m.deterministic_pairs(rows)
        b = m.deterministic_pairs(rows[::-1])
        ids = lambda p: [(x["low_id"], x["high_id"]) for x in p.pairs]
        self.assertEqual(ids(a), [("la", "ha"), ("lb", "hb")])
        self.assertEqual(ids(a), ids(b))

    def test_signed_unit_effects_hand_calculation(self):
        p = m.deterministic_pairs([row("l", 0.), row("h", 1., "RUN")])
        e = m.unit_effects([[1., 2.], [3., 1.]], p, [1., 2.])
        self.assertEqual([x["value"] for x in e.report()["effects"]], [2., -.5])

    def test_exact_cancellation_before_pair_mean(self):
        rows = [row("l1", 0.), row("h1", 1., "RUN"), row("l2", 2.), row("h2", 3., "RUN")]
        p = m.deterministic_pairs(rows)
        e = m.unit_effects([[0.], [1e308], [1e308], [1.]], p, [1.])
        self.assertEqual(e.report()["effects"][0]["value"], .5)
        base = 1.1
        e = m.unit_effects([[base], [np.nextafter(base, 2.)], [base], [base]], p, [1.])
        self.assertEqual(e.report()["effects"][0]["value"], np.spacing(base)/2)

    def test_equal_unit_area_means_then_equal_available_areas(self):
        p = m.deterministic_pairs([row("l", 0.), row("h", 1., "RUN")])
        e = m.unit_effects([[0., 0., 0.], [1., 3., 10.]], p, [1., 1., 1.])
        areas = m.area_effects(e, ["VISp", "VISp", "VISl"])
        self.assertEqual(areas.report()["areas"]["VISp"]["effect"]["value"], 2.)
        self.assertEqual(areas.report()["areas"]["VISam"]["effect"]["status"], "absent_area")
        candidate = {a: (0. if areas.values[a] is not None else None) for a in m.AREAS}
        error = m.mean_absolute_error(candidate, areas)
        self.assertEqual(error.report()["mean_absolute_error"]["value"], 6.)

    def test_full_session_hierarchy_and_no_pair_undefined(self):
        good = m.SessionError(m.Fraction(2), ("VISp",), tuple(m.AREAS[1:]))
        other = m.SessionError(m.Fraction(8), ("VISp",), tuple(m.AREAS[1:]))
        result = m.aggregate_session_errors({"s1": good, "s2": good, "s3": other},
                                             {"s1": "m1", "s2": "m1", "s3": "m2"})
        self.assertEqual(result["primary_mean_absolute_error"]["value"], 5.)
        p = m.deterministic_pairs([row("only", 0.)])
        e = m.unit_effects([[1.]], p, [1.])
        areas = m.area_effects(e, ["VISp"])
        error = m.mean_absolute_error(dict.fromkeys(m.AREAS), areas)
        result = m.aggregate_session_errors({"s1": good, "s2": error}, {"s1": "m1", "s2": "m2"})
        self.assertEqual(result["primary_mean_absolute_error"]["status"], "undefined_required_session")
        self.assertEqual(result["undefined_session_ids"], ["s2"])

    def test_extreme_finite_effect_and_mean_error_are_tagged(self):
        p = m.deterministic_pairs([row("l", 0.), row("h", 1., "RUN")])
        e = m.unit_effects([[0.], [1e308]], p, [np.nextafter(0., 1.)])
        scalar = e.report()["effects"][0]
        self.assertEqual(scalar["status"], "finite")
        self.assertEqual(scalar["float64_status"], "overflow")
        self.assertIsNone(scalar["value"])
        area = m.area_effects(e, ["VISp"])
        candidate = dict.fromkeys(m.AREAS)
        candidate["VISp"] = 0.
        err = m.mean_absolute_error(candidate, area).report()
        self.assertEqual(err["mean_absolute_error"]["float64_status"], "overflow")
        json.dumps(err, allow_nan=False)

    def test_metadata_matching_equal_bin_counts_and_hash_order(self):
        rows = [metadata("p2", "VISp"), metadata("p1", "VISp"), metadata("l1", "VISl"),
                metadata("other_bin", "VISl", rate=4.), metadata("outside", "VISam")]
        result = m.matched_area_units(rows, ("VISp", "VISl"))
        order = sorted(["p1", "p2"], key=lambda x: (hashlib.sha256(x.encode()).hexdigest(), x))
        self.assertEqual(result["selected_unit_ids"]["VISp"], order[:1])
        self.assertEqual(result["selected_unit_ids"]["VISl"], ["l1"])
        self.assertEqual(result["outside_pair_unit_ids"], ["outside"])
        self.assertIn("other_bin", result["unmatched_unit_ids"])
        self.assertEqual(result, m.matched_area_units(rows[::-1], ("VISp", "VISl")))

    def test_metadata_bin_boundaries_and_no_query_inputs(self):
        rows = [metadata("p", "VISp", rate=1., presence=.97, isi=.1, amp=.05),
                metadata("l", "VISl", rate=1., presence=.97, isi=.1, amp=.05)]
        result = m.matched_area_units(rows, ("VISp", "VISl"))
        self.assertEqual(result["strata"][0]["bin_indices"], [1, 1, 1, 1])
        rows[0]["query_rate"] = 10.
        with self.assertRaises(m.StateInputError):
            m.matched_area_units(rows, ("VISp", "VISl"))

    def test_invalid_fields_reuse_and_null_support_not_silent(self):
        with self.assertRaises(m.StateInputError):
            m.deterministic_pairs([row("same", 0.), row("same", 1., "RUN")])
        with self.assertRaises(m.StateInputError):
            m.deterministic_pairs([row("bad", 0., condition=("grating", float("nan")))])
        p = m.PairingResult("running", 2, (0, 0), (1, 1), (), ())
        with self.assertRaises(m.StateInputError):
            m.unit_effects([[1.], [2.]], p, [1.])
        p = m.deterministic_pairs([row("l", 0.), row("h", 1., "RUN")])
        for rate, baseline in (([[1.], [-1.]], [1.]), ([[1.], [2.]], [0.])):
            with self.assertRaises(m.StateInputError):
                m.unit_effects(rate, p, baseline)
        area = m.area_effects(m.unit_effects([[1.], [2.]], p, [1.]), ["VISp"])
        candidate = dict.fromkeys(m.AREAS)
        candidate["VISp"] = 1.
        candidate["VISam"] = 0.
        with self.assertRaises(m.StateInputError):
            m.mean_absolute_error(candidate, area)


if __name__ == "__main__":
    unittest.main(verbosity=2)

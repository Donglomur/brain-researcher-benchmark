"""Independent software controls: invented RAM rows only; no released data reads."""
import importlib.util
import copy
import math
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "neural033_peer_core", Path(__file__).resolve().with_name("analysis_core.py"))
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
_score_spec = importlib.util.spec_from_file_location(
    "neural033_peer_score", Path(__file__).resolve().with_name("score.py"))
score = importlib.util.module_from_spec(_score_spec)
_score_spec.loader.exec_module(score)


def row(compartment, treatment, mouse, index, rate, baseline, outcome):
    return {"row_id": f"{compartment}-{treatment}-{mouse}-{index}",
            "mouse_id": f"{treatment}-{mouse}", "compartment": compartment,
            "treatment": treatment, "member_index0": mouse, "source_row0": index,
            "baseline_flag": {"kind": "list", "value": []},
            "followup_flag": {"kind": "list", "value": []},
            "baseline_volume": baseline, "followup_volume": baseline * 2.0 ** outcome,
            "event_rate": rate}


def cohort(mice=3):
    """Identical compartment signals, with nonlinear mouse-varying responses."""
    out = []
    permutations = {
        "control": [2, 9, 0, 7, 4, 11, 6, 1, 8, 3, 10, 5],
        "kir": [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5],
    }
    for compartment in ("apical", "basal"):
        for treatment, permutation in permutations.items():
            for index, baseline_index in enumerate(permutation[:4 * mice]):
                outcome = .04 * index ** 2 - .15 * baseline_index
                if treatment == "kir":
                    outcome += .07 * index
                out.append(row(compartment, treatment, index // 4, index,
                               index, 1 + baseline_index, outcome))
    return out


def oracle_balanced(rows, compartment):
    """Independent pairwise-CDF / normal-equation oracle for this finite fixture.

    Production uses sorting and SVD. This oracle is restricted to deliberately
    well-conditioned invented inputs and is never an alternative task runtime.
    """
    groups = {}
    for treatment in ("control", "kir"):
        values = [r for r in rows if r["compartment"] == compartment
                  and r["treatment"] == treatment]
        mice = {r["mouse_id"] for r in values}
        weights = [1 / (len(mice) * sum(s["mouse_id"] == r["mouse_id"] for s in values))
                   for r in values]
        ranks = []
        for field in ("event_rate", "baseline_volume"):
            ranks.append([sum(w * (float(s[field] < r[field]) + .5 * float(s[field] == r[field]))
                              for s, w in zip(values, weights)) for r in values])
        bins = [min(int(3*q), 2)*3 + min(int(3*s), 2) for q, s in zip(*ranks)]
        masses = [sum(w for b, w in zip(bins, weights) if b == cell) for cell in range(9)]
        groups[treatment] = values, weights, ranks, bins, masses
    target = [min(groups["control"][4][b], groups["kir"][4][b]) for b in range(9)]
    coefficients = {}
    for treatment, (values, weights, ranks, bins, masses) in groups.items():
        balanced = np.array([w*target[b]/masses[b] for w, b in zip(weights, bins)])
        balanced /= balanced.sum()
        x = np.array([[1., q, s] for q, s in zip(*ranks)])
        y = np.array([math.log2(r["followup_volume"])-math.log2(r["baseline_volume"])
                      for r in values])
        coefficients[treatment] = np.linalg.solve(x.T @ (balanced[:, None]*x),
                                                  x.T @ (balanced*y))
    return coefficients, target


class GeneratedPeerTests(unittest.TestCase):
    def test_equal_mouse_tied_cdf(self):
        rows = [row("apical", "control", 0, 0, 0., 1., 0.)]
        rows += [row("apical", "control", 1, i, 1., 2., 0.) for i in range(3)]
        value = core.group_data(rows, np)["apical_control"]
        np.testing.assert_allclose(value["weights"], [.5, 1/6, 1/6, 1/6], rtol=0, atol=1e-15)
        np.testing.assert_allclose(value["x"][:, 1], [.25, .75, .75, .75], rtol=0, atol=1e-15)
        np.testing.assert_allclose(value["x"][:, 2], [.25, .75, .75, .75], rtol=0, atol=1e-15)

    def test_collinearity_has_no_pseudoinverse_fallback(self):
        rows = cohort()
        for r in rows:
            r["event_rate"] = r["baseline_volume"]
        result = core.analyze(rows)
        for panel in result["panels"].values():
            for group in panel["groups"].values():
                self.assertEqual(group["status"], "unavailable")
                self.assertEqual(group["reason"], "rank_deficient")
                self.assertEqual(group["rank"], 2)
                self.assertIsNone(group["coefficients"])
            for contrast in panel["contrasts"].values():
                self.assertEqual(contrast["uncertainty_status"], "point_unavailable")

    def test_near_collinear_rank_guard(self):
        rows = cohort()[:12]
        data = core.group_data(rows, np)["apical_control"]
        q = np.linspace(.1, .9, len(rows))
        independent = np.array([(-1.) ** i for i in range(len(rows))])
        data["x"] = np.column_stack([np.ones(len(rows)), q, q + 1e-13*independent])
        rejected = core.fit_group(data, data["weights"], np)
        self.assertEqual(rejected["reason"], "rank_deficient")
        data["x"][:, 2] = q + 1e-4*independent
        self.assertEqual(core.fit_group(data, data["weights"], np)["status"], "defined")

    def test_two_mouse_points_survive_unavailable_uncertainty(self):
        result = core.analyze(cohort(mice=2))
        for panel in result["panels"].values():
            self.assertEqual(len(panel["delete_one_mouse"]), 4)
            for contrast in panel["contrasts"].values():
                self.assertIsNotNone(contrast["estimate"])
                self.assertEqual(contrast["uncertainty_status"], "deletion_unavailable")
                self.assertIsNone(contrast["jackknife_se"])
                self.assertIsNone(contrast["deletion_min"])
                self.assertIsNone(contrast["deletion_max"])

    def test_shared_compartment_mouse_deletion_and_cancellation(self):
        rows = cohort()
        real_panel = core.panel
        calls = []
        def observed_panel(selected, balanced, numpy):
            calls.append(({r["row_id"] for r in selected}, balanced))
            return real_panel(selected, balanced, numpy)
        with mock.patch.object(core, "panel", observed_panel):
            result = core.analyze(rows)
        all_ids = {r["row_id"] for r in rows}
        mice = {r["mouse_id"] for r in rows}
        for balanced in (False, True):
            observed = [selected for selected, b in calls if b == balanced]
            self.assertEqual(len(observed), 1 + len(mice))
            self.assertEqual(observed[0], all_ids)
            expected = [all_ids - {r["row_id"] for r in rows if r["mouse_id"] == m} for m in mice]
            self.assertCountEqual([frozenset(v) for v in observed[1:]], [frozenset(v) for v in expected])
        for panel in result["panels"].values():
            combined = panel["contrasts"][core.CONTRASTS[2]]
            self.assertEqual(combined["uncertainty_status"], "defined")
            self.assertAlmostEqual(combined["estimate"], 0., places=12)
            self.assertAlmostEqual(combined["jackknife_se"], 0., places=12)
            self.assertGreater(panel["contrasts"][core.CONTRASTS[0]]["jackknife_se"], .1)

    def test_balanced_deletion_reweights_both_treatments(self):
        rows = cohort()
        remaining = [r for r in rows if r["mouse_id"] != "kir-0"]
        full = core.panel(rows, True, np)
        changed = core.panel(remaining, True, np)
        oracle, masses = oracle_balanced(remaining, "apical")
        np.testing.assert_allclose(changed["matched_bin_mass"]["apical"], masses, atol=1e-14, rtol=0)
        for treatment in ("control", "kir"):
            actual = changed["groups"]["apical_"+treatment]["coefficients"]
            np.testing.assert_allclose([actual[k] for k in ("intercept", "activity_rank", "baseline_rank")],
                                       oracle[treatment], atol=1e-11, rtol=0)
        old_control = full["groups"]["apical_control"]["coefficients"]["activity_rank"]
        new_control = changed["groups"]["apical_control"]["coefficients"]["activity_rank"]
        self.assertGreater(abs(old_control-new_control), .01)
        analysis = core.analyze(rows)["panels"]["balanced"]
        expected_difference = float(oracle["kir"][1]-oracle["control"][1])
        self.assertAlmostEqual(analysis["delete_one_mouse"]["kir-0"][core.CONTRASTS[0]], expected_difference, places=11)
        # Independent stratified variance from the finite deletion estimates.
        variance = 0.
        for treatment in ("control", "kir"):
            values = [analysis["delete_one_mouse"][f"{treatment}-{i}"][core.CONTRASTS[0]] for i in range(3)]
            center = math.fsum(values)/3
            variance += 2/3*math.fsum((v-center)**2 for v in values)
        self.assertAlmostEqual(analysis["contrasts"][core.CONTRASTS[0]]["jackknife_se"], math.sqrt(variance), places=12)

    def test_zero_overlap_is_explicitly_unavailable(self):
        rows = []
        for compartment in ("apical", "basal"):
            for treatment in ("control", "kir"):
                for mouse in range(3):
                    for i in range(3):
                        baseline = 1 + (i if treatment == "control" else (i+1) % 3)
                        rows.append(row(compartment, treatment, mouse, i, i, baseline, .1*i))
        panel = core.analyze(rows)["panels"]["balanced"]
        for masses in panel["matched_bin_mass"].values():
            self.assertEqual(masses, [0.]*9)
        for group in panel["groups"].values():
            self.assertEqual(group["row_ids"], [])
            self.assertEqual(group["reason"], "insufficient_support")
        for contrast in panel["contrasts"].values():
            self.assertIsNone(contrast["estimate"])

    def test_both_visit_shaft_exclusions(self):
        r = row("apical", "control", 0, 0, 1., 1., 0.)
        r["baseline_flag"] = {"kind": "list", "value": ["Shaft Spine"]}
        self.assertEqual(core.exclusion(r), "baseline_shaft")
        r["baseline_flag"]["value"] = []
        r["followup_flag"] = {"kind": "str", "value": "Shaft Spine"}
        self.assertEqual(core.exclusion(r), "followup_shaft")

    def test_impossible_fit_support_rejected_before_reference(self):
        rows = cohort()
        analysis = core.analyze(rows)
        identity = {"row_ids": [r["row_id"] for r in rows],
                    "mouse_ids": sorted({r["mouse_id"] for r in rows})}
        original = {"schema_version": 1, "task_id": "NEURAL-033",
                    "contract_sha256": "c"*64, "input_sha256": "d"*64,
                    "analysis": analysis}
        changes = [
            {"row_ids": [], "mice": [], "n_rows": 0, "n_mice": 0,
             "effective_mice": None},
            {"effective_mice": -1.},
            {"effective_mice": None},
            {"effective_mice": 4.},
            {"mice": ["control-0"], "n_mice": 1, "effective_mice": 1.},
        ]
        for change in changes:
            with self.subTest(change=change):
                candidate = copy.deepcopy(original)
                candidate["analysis"]["panels"]["all"]["groups"]["apical_control"].update(change)
                called = []
                result, code = score.grade_bytes(score.io.encode(candidate), identity,
                    "c"*64, "d"*64, lambda: called.append(True))
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "invalid_submission")
                self.assertFalse(result["reference_invoked"])
                self.assertEqual(called, [])

    def test_normalized_error_retains_small_difference_and_extremes(self):
        for expected in (2., -2.):
            candidate = math.nextafter(expected, 0.)
            wanted = abs(candidate-expected)/(1+abs(expected))
            self.assertGreater(wanted, 0.)
            self.assertEqual(score.relative_error(candidate, expected), wanted)
        self.assertTrue(math.isfinite(score.relative_error(1.7e308, -1.7e308)))
        self.assertAlmostEqual(score.relative_error(1.7e308, -1.7e308), 2.)


if __name__ == "__main__":
    unittest.main()

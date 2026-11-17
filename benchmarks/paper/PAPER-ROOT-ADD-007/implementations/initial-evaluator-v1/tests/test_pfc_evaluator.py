"""Bounded generated controls; no authentic scientific result is asserted."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pfc_evaluator", ROOT / "pfc_evaluator.py")
pfc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pfc)


def packet():
    out = {"schema_version": 1,
           "provenance": {"kind": "generated_control", "conversion_receipt": "bounded fixture; no native payload", "mask_mapping": "explicit synthetic labels"},
           "mice": {m: list("abcde") for m in pfc.MICE}, "events": []}
    for mouse in pfc.MICE:
        for phase in pfc.PHASES:
            for cond in pfc.CONDITIONS:
                for repeat in range(4):
                    order = "abcde" if cond.endswith("L") else "edcba"
                    out["events"].append({"id": f"{mouse}-{phase}-{cond}-{repeat}", "mouse": mouse, "context": "Task", "session": phase,
                        "trial": f"{cond[-1]}-{repeat}", "phase": phase, "condition": cond,
                        "correct": True, "speed_pass": True, "onsets_s": {c: i*.05 for i,c in enumerate(order)}})
        for context in ("Sleep", "Arena"):
            for repeat in range(2):
                out["events"].append({"id": f"{mouse}-{context}-{repeat}", "mouse": mouse, "context": context, "session": context,
                    "trial": f"rest-{repeat}", "phase": None, "condition": "rest", "correct": False,
                    "speed_pass": False, "onsets_s": {c: i*.05 for i,c in enumerate("abcde")}})
    return out


class RankControls(unittest.TestCase):
    def test_hand_computed_orders_and_overlap(self):
        self.assertEqual(pfc.rank_correlation("abcde", "bacde"), (.9, 5))
        self.assertEqual(pfc.rank_correlation("xabyc", "cabz"), (-.5, 3))
        self.assertEqual(pfc.rank_correlation("ab", "bc"), (None, 1))
        with self.assertRaises(pfc.ContractError): pfc.rank_correlation("aa", "ab")

    def test_complete_three_cell_distribution(self):
        values, exact = pfc._rank_null(3, 0, 99)
        self.assertTrue(exact)
        np.testing.assert_allclose(sorted(values), [-1, -.5, -.5, .5, .5, 1])
        self.assertAlmostEqual(float(values.var()), .5)
        self.assertAlmostEqual(pfc.rank_test("abc", "abc", draws=99)["p_upper"], 1/6)
        self.assertAlmostEqual(pfc.rank_test("abcde", "abcde", draws=99)["p_upper"], 1/120)

    def test_clustering_is_recomputed_and_label_invariant(self):
        events = [e for e in packet()["events"] if e["mouse"]=="478" and e["phase"]=="learning" and e["condition"].startswith("outward")]
        result = pfc.fit_clusters(events, draws=99)
        self.assertEqual(len(result["templates"]), 2)
        renamed = copy.deepcopy(events)
        for e in renamed: e["onsets_s"] = {"cell_"+k: v for k,v in e["onsets_s"].items()}
        other = pfc.fit_clusters(renamed, draws=99)
        a,b = result["labels"], other["labels"]
        for x,y in itertools.product(a,a): self.assertEqual(a[x]==a[y], b[x]==b[y])

    def test_unrelated_singletons_are_not_recurrence(self):
        events = []
        for i, order in enumerate(("abcde", "edcba", "cdeab", "baedc")):
            events.append({"id":str(i), "session":"s", "trial":str(i), "onsets_s":{c:j*.05 for j,c in enumerate(order)}})
        result=pfc.fit_clusters(events,draws=99)
        self.assertEqual(result["significant_edges"],0)
        self.assertEqual(result["templates"],[])

    def test_four_mouse_uncertainty_cannot_manufacture_small_p(self):
        result = pfc._paired_summary([1,1,1,1])
        self.assertEqual(result["exact_signflip_two_sided_p"], .125)
        self.assertEqual(result["animal_bootstrap_percentile_95"], [1,1])
        with self.assertRaises(pfc.ContractError): pfc._paired_summary([1,1,1])


class BoundaryControls(unittest.TestCase):
    def test_all_mice_contexts_required_and_labels_rejected(self):
        p = packet(); p["events"]=[e for e in p["events"] if not(e["mouse"]=="485" and e["context"]=="Sleep")]
        with self.assertRaisesRegex(pfc.ContractError, "census"): pfc.validate_packet(p)
        p = packet(); p["events"][0]["cluster_id"] = 1
        with self.assertRaisesRegex(pfc.ContractError, "supplied clusters"): pfc.validate_packet(p)
        p = packet(); p["mice"].pop("478")
        with self.assertRaises(pfc.ContractError): pfc.validate_packet(p)

    def test_nonfinite_ties_unregistered_and_phase_leakage(self):
        for value in (float("nan"), -.1, .6):
            p = packet(); p["events"][0]["onsets_s"]["a"] = value
            with self.assertRaises(pfc.ContractError): pfc.validate_packet(p)
        p = packet(); p["events"][0]["onsets_s"]["b"] = 0
        with self.assertRaisesRegex(pfc.ContractError, "tied"): pfc.validate_packet(p)
        p = packet(); p["events"][0]["onsets_s"]["alien"] = .3
        with self.assertRaises(pfc.ContractError): pfc.validate_packet(p)
        p = packet(); p["events"][0]["phase"] = "learned"
        with self.assertRaisesRegex(pfc.ContractError, "crosses"): pfc.validate_packet(p)

    def test_session_phase_and_trial_correctness_consistency(self):
        p=packet(); p["events"][0]["phase"]="learned";p["events"][0]["trial"]="distinct_trial"
        with self.assertRaisesRegex(pfc.ContractError,"session"):pfc.validate_packet(p)
        p=packet();p["events"][0]["correct"]=False
        with self.assertRaisesRegex(pfc.ContractError,"correctness"):pfc.validate_packet(p)

    def test_matched_counts_disclosed(self):
        rows=[e for e in packet()["events"] if e["mouse"]=="478" and e["condition"].startswith("outward")]
        extra=copy.deepcopy(rows[0]);extra["id"]="extra";rows.append(extra)
        selected,census=pfc._match_phase_counts(rows,0)
        self.assertEqual(len(selected),16)
        self.assertEqual(sum(c["available"] for c in census),17)
        self.assertEqual(sum(c["selected"] for c in census),16)

    def test_pipeline_and_input_order_invariance(self):
        p=packet(); a=pfc.evaluate(p, draws=99, null_draws=19)
        p["events"].reverse(); b=pfc.evaluate(p, draws=99, null_draws=19)
        self.assertEqual(a,b)
        self.assertEqual(a["scientific_qualification"], "unknown")
        self.assertEqual(a["animal_summary"]["mean"], 0)
        self.assertEqual(len(a["animals"]),4)
        for animal in a["animals"]:
            self.assertEqual(sum(r["count"] for r in animal["selectivity_counts"]),64)
            self.assertEqual(len(animal["identity_alignment_null"]["values"]),19)
        json.dumps(a,allow_nan=False)

    def test_cli_json_output_and_malformed_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp,out=Path(tmp)/"in.json",Path(tmp)/"out.json"
            inp.write_text(json.dumps(packet()))
            run=subprocess.run([sys.executable,str(ROOT/"pfc_evaluator.py"),str(inp),"--output",str(out),"--rank-draws","99","--null-draws","19"],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(out.read_text())["engineering_resources"]["scientific_runs"],0)
            out.unlink(); inp.write_text('{"schema_version":NaN}')
            run=subprocess.run([sys.executable,str(ROOT/"pfc_evaluator.py"),str(inp),"--output",str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode,2);self.assertFalse(out.exists())


class DecoderControls(unittest.TestCase):
    def test_independently_computed_poisson_odds(self):
        # With k=[1,0], rates columns=[2,1] and [1,2], equal sums -> odds 2:1.
        d=pfc.poisson_decode([[1,0]], [[2,1],[1,2]], .5)
        np.testing.assert_allclose(d["posterior"], [[2/3,1/3]])
        self.assertEqual(d["position_indices"],[0])
        # Scaling rates and inversely scaling exposure leaves lambda unchanged.
        e=pfc.poisson_decode([[1,0]], [[4,2],[2,4]], .25)
        np.testing.assert_allclose(d["posterior"],e["posterior"])

    def test_zero_likelihood_ties_and_bad_counts(self):
        d=pfc.poisson_decode([[1,1]], [[0,0],[1,2]], .05)
        self.assertEqual(d["position_indices"],[None])
        self.assertEqual(d["posterior"],[[0,0]])
        d=pfc.poisson_decode([[0,0]], [[1,1],[1,1]], .05)
        self.assertEqual(d["position_indices"],[None])
        with self.assertRaises(pfc.ContractError): pfc.poisson_decode([[.5,0]], [[1,2],[2,1]], .05)
        with self.assertRaises(pfc.ContractError): pfc.poisson_decode([[1]], [[1,2],[2,1]], .05)

    def test_forward_reverse_and_group_shared_null(self):
        rates=np.full((5,5),.1);np.fill_diagonal(rates,100)
        counts=np.eye(5,dtype=int)*5
        f=pfc.trajectory_session([counts.tolist(),counts[::-1].tolist()],rates,.05,draws=99)
        self.assertAlmostEqual(f["events"][0]["rho"],1)
        self.assertAlmostEqual(f["events"][1]["rho"],-1)
        # A single cell map is permuted per draw for both opposite trajectories.
        np.testing.assert_allclose(f["events"][0]["null_rhos"],-np.array(f["events"][1]["null_rhos"]),atol=1e-14)
        self.assertIsNone(pfc.trajectory_replay(counts[:4],rates,.05,draws=99)["rho"])


if __name__ == "__main__": unittest.main()

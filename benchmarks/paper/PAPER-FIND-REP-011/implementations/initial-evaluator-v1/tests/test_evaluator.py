"""Analytic generated controls; none are empirical neuroscience observations."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rep011", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)


def control():
    data = {"schema_version": e.SCHEMA, "cohort": "iglusnfr2",
            "provenance": {"kind": "generated_engineering_control", "source_record": "zenodo.10108836",
                           "input_scope": "analytic engineering fixture, not empirical", "alignment_policy_id": "generated",
                           "activity_detection_policy_id": "generated-binary", "fate_assessment_id": "generated-known"},
            "sessions": [{"session_id": "early", "day": 1}, {"session_id": "middle", "day": 7}, {"session_id": "late", "day": 14}],
            "dendrites": []}
    for m in range(3):
        d = {"mouse_id": f"mouse{m}", "dendrite_id": "branch", "health_status": "eligible", "health_assessment_id": "generated",
             "arc_start_um": 0, "arc_end_um": 30, "spines": []}
        for j, states in enumerate((["present", "present", "present"], ["present", "absent", "absent"], ["present", "present", "absent"], ["present", "unknown", "unknown"])):
            s = {"spine_id": f"spine{j}", "observations": []}
            for i, state in enumerate(states):
                o = {"session_id": data["sessions"][i]["session_id"], "state": state}
                if state == "present":
                    trace = [1, 1, 0, 1, 0, 0] if j % 2 == 0 else [0, 1, 1, 1, 0, 0]
                    o.update(position_um=5+10*j/3, sample_hz=1, activity=trace,
                             continuous_complete_session=True)
                s["observations"].append(o)
            d["spines"].append(s)
        data["dendrites"].append(d)
    return data


class EventTests(unittest.TestCase):
    def test_independent_coactivity_control(self):
        # Reference reviewer derived 2 A events, 1 B event, 2 intersection runs.
        a, b = [1,1,0,1,0,0], [0,1,1,1,0,0]
        self.assertEqual(e.events(a), 2); self.assertEqual(e.events(b), 1)
        self.assertAlmostEqual(e.coactivity(a,b), math.sqrt(2))
        self.assertIsNone(e.coactivity(a, [0]*6))

    def test_entire_active_run_and_nonoverlap(self):
        self.assertEqual(e.events([1]*60), 1)
        self.assertEqual(e.coactivity([1,0,1,0], [0,1,0,1]), 0)
        self.assertEqual(e.coactivity([1]*60, [1]*60), 1)

    def test_duration_uses_sample_count(self):
        d = control()
        for s in d["dendrites"][0]["spines"]:
            o=s["observations"][0]; o.update(activity=[1]+[0]*59, sample_hz=2)
        rows, _ = e.derive(d)
        self.assertEqual(rows[0]["events_per_min"], 2)  # 1 event / 30 seconds.

    def test_exact_neighborhood_boundary_and_zero_denominator(self):
        d = control(); spines=d["dendrites"][0]["spines"]
        for s, x in zip(spines, [0,10,10.0001,30]): s["observations"][0]["position_um"] = x
        rows,_=e.derive(d)
        focal=rows[0]
        self.assertEqual(focal["neighbor_count"], 1)
        self.assertAlmostEqual(focal["local_coactivity"], math.sqrt(2))
        spines[1]["observations"][0]["activity"]=[0]*6
        rows,_=e.derive(d)
        self.assertIsNone(rows[0]["local_coactivity"])
        self.assertEqual(rows[0]["zero_activity_pair_count"],1)


class CohortTests(unittest.TestCase):
    def test_longitudinal_censoring_and_terminal_rows(self):
        rows,excluded=e.derive(control()); self.assertFalse(excluded)
        r=[r for r in rows if r["mouse_id"]=="mouse0"]
        self.assertEqual([x["label"] for x in r if x["spine_id"]=="spine0"], [0,0,None])
        self.assertEqual([x["label"] for x in r if x["spine_id"]=="spine2"], [0,1])
        cens=[x for x in r if x["spine_id"]=="spine3"]
        self.assertEqual(cens[0]["outcome_status"],"next_visit_unknown")
        self.assertEqual(cens[0]["start_day"],1); self.assertEqual(cens[0]["end_day"],7)

    def test_reappearance_and_new_spines_excluded_but_contemporaneous_neighbor_kept(self):
        d=control(); spines=d["dendrites"][0]["spines"]
        spines[1]["observations"][2]=copy.deepcopy(spines[1]["observations"][0])
        spines[1]["observations"][2]["session_id"]="late"
        before,_=e.derive(control()); after,excluded=e.derive(d)
        self.assertEqual(before[0]["local_coactivity"],after[0]["local_coactivity"])
        self.assertFalse(any(r["spine_id"]=="spine1" and r["mouse_id"]=="mouse0" for r in after))
        self.assertIn("reappearance_requires_identity_review",[x["reason"] for x in excluded])
        spines[1]["observations"][0]={"session_id":"early","state":"absent"}
        _,excluded=e.derive(d)
        self.assertIn("not_confirmed_baseline_present",[x["reason"] for x in excluded])

    def test_no_future_elimination_block_selection_for_prediction(self):
        d=control()
        for s in d["dendrites"][0]["spines"]:
            for i in (1,2):
                s["observations"][i]=copy.deepcopy(s["observations"][0]); s["observations"][i]["session_id"]=d["sessions"][i]["session_id"]
        rows,_=e.derive(d)
        r=[x for x in rows if x["mouse_id"]=="mouse0"]
        self.assertFalse(any(x["historical_elimination_block"] for x in r))
        predictions,folds,_=e.fit_predict(rows)
        self.assertTrue(any(p["key"][0]=="mouse0" for p in predictions["activity_local"]))

    def test_fail_closed_alignment_and_identity(self):
        for mutate in [lambda d: d["dendrites"][0]["spines"][0]["observations"].pop(),
                       lambda d: d["dendrites"][0]["spines"][0]["observations"][0].update(sample_hz=2),
                       lambda d: d["dendrites"][0]["spines"][0]["observations"][0].update(continuous_complete_session=False),
                       lambda d: d["dendrites"].append(copy.deepcopy(d["dendrites"][0])),
                       lambda d: d["dendrites"][0]["spines"][0]["observations"][0].update(activity=[1,0,float("nan"),0,0,0])]:
            d=control(); mutate(d)
            with self.assertRaises(e.ContractError): e.derive(d)


class PredictionTests(unittest.TestCase):
    def test_holdout_labels_do_not_change_fitted_transform_or_coefficients(self):
        rows,_=e.derive(control()); p,f,_=e.fit_predict(rows)
        changed=copy.deepcopy(rows)
        for r in changed:
            if r["mouse_id"]=="mouse0" and r["label"] is not None: r["label"]=1-r["label"]
        p2,f2,_=e.fit_predict(changed)
        self.assertEqual(f[0],f2[0])
        self.assertEqual([x for x in p["activity_local"] if x["key"][0]=="mouse0"],
                         [x for x in p2["activity_local"] if x["key"][0]=="mouse0"])
        for fold in f: self.assertNotIn(fold["test_mouse"],fold["train_mice"])

    def test_training_transform_ignores_extreme_test_features(self):
        rows,_=e.derive(control()); _,folds,_=e.fit_predict(rows)
        for r in rows:
            if r["mouse_id"]=="mouse0": r["events_per_min"]=1e9
        _,after,_=e.fit_predict(rows)
        self.assertEqual(folds[0],after[0])

    def test_equal_mouse_metrics_not_pooled(self):
        rows=[]; pred=[]
        for mouse,ys,ps in [("a",[0],[0]),("b",[1,1,1],[0,0,0])]:
            for i,(y,p) in enumerate(zip(ys,ps)):
                r=dict(mouse_id=mouse,dendrite_id="d",spine_id=str(i),session_id="s",next_session_id="t",label=y)
                rows.append(r); pred.append({"key":list(e.row_key(r)),"probability":p})
        scored=e.score(rows,pred)
        self.assertEqual(scored["equal_mouse"]["brier"],.5)
        self.assertEqual(scored["auc_defined_mice"],0)
        self.assertIsNone(scored["equal_mouse"]["auc"])
        self.assertAlmostEqual(scored["reliability_deciles"][0]["event_fraction"],.5)

    def test_prediction_coverage_and_probabilities(self):
        rows,_=e.derive(control()); predictions,_,_=e.fit_predict(rows); p=predictions["activity"]
        for wrong in [p[:-1],p+[p[0]],[{**p[0],"probability":float("nan")}] + p[1:],
                      [{**p[0],"probability":1.1}] + p[1:]]:
            with self.assertRaises(e.ContractError): e.score(rows,wrong)
        self.assertEqual(e.score(rows,p)["censored_rows"],3)

    def test_all_censored_mouse_is_explicit(self):
        d=control(); extra=copy.deepcopy(d["dendrites"][0]); extra["mouse_id"]="all_censored"
        for s in extra["spines"]:
            s["observations"][1:] = [{"session_id":"middle","state":"unknown"},{"session_id":"late","state":"unknown"}]
        d["dendrites"].append(extra)
        result=e.evaluate(d)
        self.assertEqual(result["unscorable_mice_all_intervals_censored"],["all_censored"])
        self.assertEqual(result["population"]["censored_scheduled_rows"],7)

    def test_single_class_folds_and_determinism(self):
        rows,_=e.derive(control())
        for r in rows:
            if r["label"] is not None: r["label"]=0
        p,_,_=e.fit_predict(rows)
        self.assertTrue(all(0 < x["probability"] < 1 for x in p["activity_local"]))
        self.assertEqual(e.evaluate(control()),e.evaluate(control()))

    def test_cli_real_path_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            source,out=Path(td)/"input.json",Path(td)/"output.json"
            source.write_text(json.dumps(control()))
            command=[sys.executable,str(ROOT/"evaluator.py"),str(source),str(out)]
            run=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads(out.read_text())
            self.assertEqual(result["scientific_qualification"],"unknown")
            self.assertEqual(result["population"]["known_rows"],15)
            repeat=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(repeat.returncode,0)


if __name__ == "__main__": unittest.main()

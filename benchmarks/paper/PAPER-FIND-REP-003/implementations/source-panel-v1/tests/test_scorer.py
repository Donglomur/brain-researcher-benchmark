"""Generated controls only; no paper data, target cache or scientific model."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_panel", ROOT / "scorer.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def folds(n=10):
    ids = list(range(101, 101+n))
    result = []
    for model in range(1, 51):
        test = [t for i, t in enumerate(ids, 1) if i % 10 == model % 10]
        result.append({"model": model, "test_trials": test, "train_trials": [t for t in ids if t not in test]})
    return ids, result


def fixture():
    common = dict(schema=s.SCHEMA, task_id=s.TASK, source_revision=s.REVISION,
                  joint_names=s.JOINTS, angle_units="degrees", time_ms=s.TIME_MS)
    ref = dict(common, role="operator_author_reference", sessions=[])
    cand = dict(common, role="candidate_predictions", sessions=[])
    ids, base_models = folds()
    for (mouse, date), area in s.SESSIONS.items():
        trials = [{"trial_number": t, "joint_angles": [[float(k+j) for j in range(24)] for k in range(51)]} for t in ids]
        rm, cm = [], []
        for record in base_models:
            # Author = constant prediction => zero VE. Candidate = half-scaled
            # target plus offset => VE 0.75, independent of offset.
            rm.append(dict(record, author_prediction=[[0.0]*24 for _ in range(51)], author_ve=[0.0]*24))
            cm.append(dict(model=record["model"], test_trials=record["test_trials"],
                           joint_angles=[[0.5*(k+j)+100.0 for j in range(24)] for k in range(51)]))
        ref["sessions"].append(dict(mouse=mouse, session=date, area=area, trials=trials, models=rm))
        cand["sessions"].append(dict(mouse=mouse, session=date, area=area, models=cm))
    return ref, cand


class SourcePanelTests(unittest.TestCase):
    def test_complete_ten_session_source_endpoint(self):
        ref, cand = fixture()
        result = s.evaluate(ref, cand)
        self.assertEqual(len(result["sessions"]), 10)
        self.assertEqual(len(result["paired_mouse_effects"]), 5)
        for session in result["sessions"]:
            self.assertEqual(session["author_summary"]["proximal_median_ve"], 0.0)
            self.assertEqual(session["candidate_summary"]["distal_median_ve"], 0.75)
            self.assertEqual(session["candidate_minus_author_summary"]["proximal_median_ve"], 0.75)
        self.assertIsNone(result["paper_win"])
        self.assertFalse(result["source_author_run_qualified"])

    def test_ve_retains_source_constant_bias_invariance(self):
        actual = [[float(k)]*24 for k in range(5)]
        biased = [[float(k+100)]*24 for k in range(5)]
        self.assertEqual(s.source_ve(actual, biased), [1.0]*24)
        # SSE/SST R2 would be -4999, so this distinguishes the source metric.

    def test_median_reduction_not_mean_or_flattened_median(self):
        panel = []
        for fit in range(50):
            # 4/7 joints have majority-zero folds; 3/7 have all-one folds.
            # Each joint median then proximal median is zero. Pooled median
            # and median of per-fit medians are both one.
            panel.append([0.0 if (fit+12*j) % 50 < 26 else 1.0 for j in range(4)] + [1.0]*3 + [0.4]*17)
        result = s.source_summary(panel)
        self.assertEqual(result["proximal_median_ve"], 0.0)
        self.assertEqual(result["distal_median_ve"], 0.4)

    def test_source_modulo_not_just_balanced_sizes(self):
        ids, models = folds(11)
        s.validate_models(models, ids)
        # Swap fold 1 (two trials) and fold 10 (one trial); both balanced and
        # complete, but inconsistent with source modulo model identities.
        for field in ("train_trials", "test_trials"):
            models[0][field], models[9][field] = models[9][field], models[0][field]
        with self.assertRaisesRegex(s.PanelError, "modulo"):
            s.validate_models(models, ids)

    def test_recorded_trial_order_and_partition_coverage(self):
        ids, models = folds(20)
        models[0]["test_trials"].reverse()
        with self.assertRaisesRegex(s.PanelError, "ordering"):
            s.validate_models(models, ids)
        ids, models = folds(20)
        models[1]["test_trials"] = models[0]["test_trials"]
        models[1]["train_trials"] = models[0]["train_trials"]
        with self.assertRaisesRegex(s.PanelError, "once"):
            s.validate_models(models, ids)

    def test_author_parity_rejects_fabricated_saved_scores(self):
        ref, cand = fixture()
        ref["sessions"][0]["models"][0]["author_ve"][0] = 0.01
        with self.assertRaisesRegex(s.PanelError, "saved source VE parity"):
            s.evaluate(ref, cand)

    def test_candidate_identity_and_original_cfa24_area(self):
        ref, cand = fixture()
        cand["sessions"][0]["models"][0]["test_trials"] = [999]
        with self.assertRaisesRegex(s.PanelError, "heldout identity"):
            s.evaluate(ref, cand)
        # cfa24 has reverse date/area ordering compared with other mice.
        self.assertEqual(s.SESSIONS[("cfa24", "220727")], "M1")
        self.assertEqual(s.SESSIONS[("cfa24", "220724")], "S1")
        cand["sessions"].pop()
        with self.assertRaisesRegex(s.PanelError, "ten original"):
            s.evaluate(ref, cand)

    def test_nonfinite_duplicate_keys_constant_joint(self):
        for value in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(s.PanelError):
                s.read_json_bytes(value)
        with self.assertRaisesRegex(s.PanelError, "constant"):
            s.source_ve([[1.0]*24]*3, [[0.0]*24]*3)
        with self.assertRaises(s.PanelError):
            s.matrix([[True]*24]*51, 51, "invalid")

    def test_preserve_negative_ve(self):
        actual = [[float(k)]*24 for k in range(5)]
        self.assertEqual(s.source_ve(actual, [[-float(k)]*24 for k in range(5)]), [-3.0]*24)


if __name__ == "__main__":
    unittest.main()

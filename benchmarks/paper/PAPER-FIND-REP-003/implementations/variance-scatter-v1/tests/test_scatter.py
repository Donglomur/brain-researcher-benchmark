"""Generated-only source companion controls; no neuroscience observations."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("variance_scatter", ROOT / "scatter.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
p = s._panel


def fixture():
    common = dict(schema=p.SCHEMA, task_id=p.TASK, source_revision=p.REVISION,
                  joint_names=p.JOINTS, angle_units="degrees", time_ms=p.TIME_MS)
    ref = dict(common, role="operator_author_reference", sessions=[])
    candidate = dict(common, role="candidate_predictions", sessions=[])
    trial_ids = list(range(101, 111))
    for (mouse, date), area in p.SESSIONS.items():
        trajectories = {
            trial: [[float((trial - 100) * (joint + 1) * time + trial)
                     for joint in range(24)] for time in range(51)]
            for trial in trial_ids
        }
        models, submitted = [], []
        for model in range(1, 51):
            test = [trial for trial in trial_ids if (trial - 100) % 10 == model % 10]
            target = trajectories[test[0]]
            models.append(dict(model=model, train_trials=[trial for trial in trial_ids if trial not in test],
                               test_trials=test, author_prediction=[[0.0] * 24 for _ in target],
                               author_ve=[0.0] * 24))
            submitted.append(dict(model=model, test_trials=test,
                                  joint_angles=[[0.5 * value + 100.0 for value in row] for row in target]))
        ref["sessions"].append(dict(mouse=mouse, session=date, area=area,
                                    trials=[dict(trial_number=trial, joint_angles=trajectories[trial])
                                            for trial in trial_ids], models=models))
        candidate["sessions"].append(dict(mouse=mouse, session=date, area=area, models=submitted))
    return ref, candidate


class ScatterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference, cls.candidate = fixture()
        cls.report = s.evaluate(cls.reference, cls.candidate)

    def test_complete_original_scatter_without_scalar_reduction(self):
        self.assertEqual(self.report["point_count"], 12000)
        self.assertEqual(len(self.report["sessions"]), 10)
        for session in self.report["sessions"]:
            self.assertEqual(len(session["points"]), 1200)
            self.assertEqual(session["source_branch"], "output")
            self.assertEqual(sum(point["joint_group"] == "proximal" for point in session["points"]), 350)
            self.assertEqual(sum(point["joint_group"] == "distal" for point in session["points"]), 850)
            for index, point in enumerate(session["points"]):
                joint, model = divmod(index, 50)
                self.assertEqual((point["joint_index"], point["model"]), (joint + 1, model + 1))
                self.assertEqual(point["joint_name"], p.JOINTS[joint])
                self.assertEqual(point["heldout_timepoint_count"], 51)
                trial_factor = (model % 10) + 1
                self.assertAlmostEqual(point["target_sample_variance_deg2"], 221 * trial_factor**2 * (joint + 1)**2)
                self.assertEqual(point["author_ve"], 0.0)
                self.assertEqual(point["candidate_ve"], 0.75)
        self.assertIsNone(self.report["paper_win"])
        self.assertFalse(self.report["scientifically_qualified"])
        self.assertNotIn("correlation", self.report)

    def test_sample_variance_keeps_n_minus_one(self):
        # Population variance would be1, but the source scatter uses2.
        self.assertEqual(s.sample_variances([[0.0] * 24, [2.0] * 24]), [2.0] * 24)

    def test_concatenate_trials_before_variance(self):
        trial_a, trial_b = [[0.0] * 24, [2.0] * 24], [[10.0] * 24, [12.0] * 24]
        values = s.sample_variances(trial_a + trial_b)
        self.assertAlmostEqual(values[0], 104 / 3)
        # Both per-trial variances are2; their mean is not the held-out variance.
        self.assertNotEqual(values[0], (s.sample_variances(trial_a)[0] + s.sample_variances(trial_b)[0]) / 2)

    def test_source_support_gate_is_not_bypassed(self):
        reference = dict(self.reference, sessions=self.reference["sessions"][:-1])
        with self.assertRaisesRegex(p.PanelError, "ten original"):
            s.evaluate(reference, self.candidate)
        candidate = dict(self.candidate, sessions=copy.deepcopy(self.candidate["sessions"]))
        candidate["sessions"][0]["models"][0]["test_trials"] = [999]
        with self.assertRaisesRegex(p.PanelError, "heldout identity"):
            s.evaluate(self.reference, candidate)

    def test_constant_nonfinite_boolean_and_shape_fail_closed(self):
        for rows in ([[1.0] * 24] * 3, [[float("nan")] * 24] * 3,
                     [[True] * 24] * 3, [[1.0] * 23] * 3):
            with self.assertRaises(ValueError):
                s.sample_variances(rows)

    def test_dependency_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "changed.py"
            path.write_bytes(b"raise Exception('must not execute')\n")
            with self.assertRaisesRegex(s.ScatterError, "dependency changed"):
                s._load_scorer(path)

    def test_candidate_commitment_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference, candidate, output = root / "r.json", root / "c.json", root / "out.json"
            reference.write_bytes(b"{}")
            candidate.write_bytes(b"{}")
            sha = hashlib.sha256(b"{}").hexdigest()
            args = ["--reference", str(reference), "--reference-sha256", sha,
                    "--candidate", str(candidate), "--candidate-sha256", "0" * 64,
                    "--output", str(output)]
            with self.assertRaisesRegex(s.ScatterError, "candidate hash"):
                s.main(args)
            self.assertFalse(output.exists())
            output.write_bytes(b"original")
            with self.assertRaisesRegex(s.ScatterError, "output already exists"):
                s.main(args)
            self.assertEqual(output.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()

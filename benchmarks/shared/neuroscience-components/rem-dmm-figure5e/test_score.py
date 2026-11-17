"""Generated-only boundary and numerical controls. No published data or answer caches."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("rem_score", Path(__file__).with_name("score.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture(mode="historical_fig5e"):
    sizes = [1, 2, 7, 15, 20]
    trials = []
    for mouse, size in enumerate(sizes):
        for _ in range(size):
            i = len(trials)
            trials.append({"trial_id": "synthetic_trial_%02d" % i,
                           "mouse_id": "synthetic_mouse_%d" % mouse,
                           "nrem_at_onset": True, "rem_within_60s": int(i < 20)})
    owner = {"schema": "rem-dmm-owner-v1", "task_id": s.TASK, "mode": mode,
             "provenance": {"article_sha256": s.ARTICLE_SHA, "official_code_commit": s.CODE_COMMIT,
                            "data_manifest_sha256": "0" * 64, "annotation_join_sha256": "1" * 64,
                            "cohort_join_sha256": "2" * 64},
             "mice": ["synthetic_mouse_%d" % i for i in range(5)], "trials": trials,
             "historical": None}
    predictions = []
    if mode == "historical_fig5e":
        splits = []
        for pc in range(1, 23):
            for rep in range(10):
                offset = (pc + rep) % 45
                order = trials[offset:] + trials[:offset]
                splits.append({"pc": pc, "repeat": rep,
                               "train_ids": [t["trial_id"] for t in order[:31]],
                               "test_ids": [t["trial_id"] for t in order[31:]]})
                for j, t in enumerate(order[31:]):
                    predictions.append({"pc": pc, "repeat": rep, "trial_id": t["trial_id"],
                                        "predicted_label": 1 - t["rem_within_60s"] if j < rep else t["rem_within_60s"]})
        owner["historical"] = {"split_realization_sha256": "3" * 64, "train_count": 31,
                               "bonferroni_factor": None, "splits": splits}
    else:
        predictions = [{"trial_id": t["trial_id"], "probability_rem_within_60s": float(t["rem_within_60s"])} for t in trials]
    candidate = {"schema": "rem-dmm-predictions-v1", "task_id": s.TASK, "mode": mode,
                 "case_plan_sha256": s.canonical_hash(s.public_plan(owner)), "predictions": predictions}
    return owner, candidate


class ScientificControls(unittest.TestCase):
    def test_full_historical_grid_and_exact_arithmetic(self):
        o, c = fixture()
        r = s.score(o, c)
        self.assertEqual(len(r["cells"]), 220)
        self.assertEqual(len(r["principal_components"]), 22)
        self.assertEqual(r["biological_mice"], 5)
        for cell in r["cells"]:
            self.assertEqual(cell["accuracy"], (14 - cell["repeat"]) / 14)
            self.assertEqual(sum(cell[k] for k in ["tp", "fp", "tn", "fn"]), 14)
        self.assertAlmostEqual(r["principal_components"][0]["mean_accuracy"], 9.5 / 14)
        self.assertIsNone(r["principal_components"][0]["p_bonferroni"])
        self.assertFalse(r["author_pipeline_parity_established"])

    def test_different_pc_splits_are_not_silently_shared(self):
        o, c = fixture()
        self.assertNotEqual(o["historical"]["splits"][0]["test_ids"], o["historical"]["splits"][10]["test_ids"])
        self.assertEqual(len(s.score(o, c)["cells"]), 220)

    def test_resampling_is_not_animal_replication(self):
        o, c = fixture()
        r = s.score(o, c)
        self.assertEqual(r["principal_components"][0]["df"], 9)
        self.assertIn("not independent animals", r["interpretation"])
        self.assertNotIn("animal_p_value", r)

    def test_one_sided_t_against_analytic_cauchy(self):
        for t in [-10, -1, 0, 1, 10]:
            self.assertAlmostEqual(s.t_upper_tail(t, 1), 0.5 - math.atan(t) / math.pi, places=12)

    def test_t_df9_known_quantile(self):
        self.assertAlmostEqual(s.t_upper_tail(1.8331129326536335, 9), 0.05, places=11)
        self.assertAlmostEqual(s.t_upper_tail(-1.8331129326536335, 9), 0.95, places=11)

    def test_explicit_bonferroni_not_implicit(self):
        a = s.summarize_accuracies([i / 14 for i in range(5, 15)], None)
        b = s.summarize_accuracies([i / 14 for i in range(5, 15)], 22)
        self.assertIsNone(a["p_bonferroni"])
        self.assertEqual(b["p_bonferroni"], min(1, 22 * b["p_one_sided_raw"]))

    def test_degenerate_test_explicit_undefined(self):
        for value in [0, 0.5, 1]:
            r = s.summarize_accuracies([value] * 10, None)
            self.assertIsNone(r["t_against_0_5"])
            self.assertIsNone(r["p_one_sided_raw"])

    def test_prospective_perfect_and_inverted(self):
        o, c = fixture("prospective_onset")
        self.assertEqual(s.score(o, c)["equal_mouse_brier"], 0)
        for r in c["predictions"]: r["probability_rem_within_60s"] = 1 - r["probability_rem_within_60s"]
        self.assertEqual(s.score(o, c)["equal_mouse_brier"], 1)

    def test_equal_mouse_weight_not_pooled_trials(self):
        o, c = fixture("prospective_onset")
        c["predictions"][0]["probability_rem_within_60s"] = 0
        r = s.score(o, c)
        self.assertEqual(r["equal_mouse_brier"], 0.2)
        self.assertEqual(r["pooled_trial_brier"], 1 / 45)
        self.assertIsNone(r["mice"][0]["class_conditional"]["0"]["brier"])

    def test_no_target_in_public_plan(self):
        o, _ = fixture()
        p = json.dumps(s.public_plan(o))
        self.assertNotIn("rem_within_60s", p)
        self.assertNotIn("provenance", p)

    def test_row_order_invariance(self):
        o, c = fixture()
        expected = s.score(o, c)
        c["predictions"].reverse()
        self.assertEqual(s.score(o, c), expected)

    def test_owner_boundary_mutations(self):
        mutations = [
            lambda o: o["trials"].pop(),
            lambda o: o["trials"][0].update(rem_within_60s=0),
            lambda o: o["trials"][0].update(rem_within_60s=True),
            lambda o: o["trials"][0].update(nrem_at_onset=False),
            lambda o: o["trials"][0].update(mouse_id="unknown"),
            lambda o: o["trials"][0].update(trial_id=o["trials"][1]["trial_id"]),
            lambda o: o["mice"].pop(),
            lambda o: o["historical"]["splits"].pop(),
            lambda o: o["historical"]["splits"][0].update(pc=23),
            lambda o: o["historical"]["splits"][0].update(repeat=True),
            lambda o: o["historical"]["splits"][0]["test_ids"].__setitem__(0, o["historical"]["splits"][0]["train_ids"][0]),
            lambda o: o["historical"].update(train_count=30),
            lambda o: o["historical"].update(bonferroni_factor=True),
            lambda o: o["provenance"].update(official_code_commit="wrong"),
            lambda o: o.update(extra="not allowed")]
        for i, mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                o, c = fixture(); mutate(o)
                with self.assertRaises(s.Invalid): s.score(o, c)

    def test_candidate_boundary_mutations(self):
        mutations = [
            lambda c: c["predictions"].pop(),
            lambda c: c["predictions"].__setitem__(0, copy.deepcopy(c["predictions"][1])),
            lambda c: c["predictions"][0].update(pc=True),
            lambda c: c["predictions"][0].update(predicted_label=0.5),
            lambda c: c["predictions"][0].update(predicted_label=True),
            lambda c: c["predictions"][0].update(trial_id="unseen"),
            lambda c: c["predictions"][0].update(cached_accuracy=1),
            lambda c: c.update(case_plan_sha256="0" * 64),
            lambda c: c.update(mode="prospective_onset")]
        for i, mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                o, c = fixture(); mutate(c)
                with self.assertRaises(s.Invalid): s.score(o, c)

    def test_prospective_invalid_probabilities(self):
        for value in [True, float("nan"), float("inf"), -0.01, 1.01, 10 ** 400, -(10 ** 400), "0.5", None]:
            with self.subTest(value=str(value)):
                o, c = fixture("prospective_onset"); c["predictions"][0]["probability_rem_within_60s"] = value
                with self.assertRaises(s.Invalid): s.score(o, c)

    def test_historical_material_refused_in_prospective(self):
        o, c = fixture("prospective_onset")
        o["historical"] = fixture()[0]["historical"]
        with self.assertRaises(s.Invalid): s.score(o, c)


class FilesystemControls(unittest.TestCase):
    def test_safe_json_and_deterministic_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp).resolve() / "x.json"; p.write_text('{"a":1}')
            obj, h = s.load(p)
            self.assertEqual(obj, {"a": 1})
            self.assertEqual(len(h), 64)

    def test_duplicate_nonfinite_deep_and_huge_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp).resolve() / "x.json"
            for body in ['{"a":1,"a":2}', '{"a":NaN}', '[' * 2000 + '0' + ']' * 2000, '{"a":' + '1' * 5000 + '}']:
                p.write_text(body)
                with self.assertRaises(s.Invalid): s.load(p)

    def test_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp).resolve(); p = q / "x.json"; p.write_text('{}')
            link = q / "link"; link.symlink_to(p)
            with self.assertRaises(s.Invalid): s.load(link)
            link.unlink(); os.link(p, link)
            with self.assertRaises(s.Invalid): s.load(p)

    def test_fifo_and_oversize_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp).resolve() / "x.json"; os.mkfifo(p)
            with self.assertRaises(s.Invalid): s.load(p)
            p.unlink(); p.write_bytes(b' ' * (s.MAX_BYTES + 1))
            with self.assertRaises(s.Invalid): s.load(p)
            p.write_bytes(b'')
            with self.assertRaises(s.Invalid): s.load(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)

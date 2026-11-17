"""Generated complete-population controls. No paper data, native libs or fits."""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pcca_eval", HERE / "evaluate.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    roster = json.loads((HERE / "ROSTER.json").read_bytes())["session_ids"]
    excluded = next(s for s in roster if s.startswith("Wa"))
    support = {"task": e.TASK, "schema": "pcca-prepared-support-v1",
               "preparation_binding": "0" * 64, "sessions": []}
    for i, s in enumerate(roster):
        y = [-1., -1., 1., 1.] if i % 2 else [-1., 1., -1., 1., -1., 1.]
        if s == excluded:
            y = [v * 10 for v in y]
        support["sessions"].append({"id": s, "channels": {"left": ["L1", "L2"], "right": ["R1", "R2"]},
                                    "trial_ids": [s + ":fabricated:" + str(j) for j in range(len(y))], "fast_pupil": y})
    raw = (json.dumps(support, sort_keys=True) + "\n").encode()
    sup, inc, targets, _ = e.manifest(raw, roster)
    rows = [{"kind": "header", "schema": "pcca-output-v1", "task": e.TASK,
             "support_sha256": hashlib.sha256(raw).hexdigest()}]
    for s in roster:
        rows.append({"kind": "model", "session": s, "channels": sup[s]["channels"],
                     "dimensions": {"across": 2, "left": 1, "right": 1},
                     "loadings": {"W_left": [[3., 0.], [0., 1.]], "W_right": [[1., 0.], [0., 3.]],
                                  "L_left": [[1.], [1.]], "L_right": [[2.], [2.]]},
                     "noise": {"left": [1., 1.], "right": [1., 1.]},
                     "selected_cv_loglik": [-1.] * 10, "final_loglik": -1.})
    for s, t, pair in ([(s, s, False) for s in inc] + [(s, t, True) for s in inc for t in inc if s != t and s[:2] == t[:2]]):
        n = min(len(targets[s]), len(targets[t]))
        row = ({"kind": "pair", "source": s, "target": t,
                "source_trial_ids": sup[s]["trial_ids"][:n], "target_trial_ids": sup[t]["trial_ids"][:n]}
               if pair else {"kind": "pupil", "session": t, "trial_ids": sup[t]["trial_ids"]})
        row["predictions"] = {mode: {g: [v * factor for v in targets[t][:n]] for g, factor in factors}
                              for mode, factors in (("all", (("across", 1.), ("within_left", 0.), ("within_right", .25))),
                                                    ("one", (("across", .5), ("within_left", 0.), ("within_right", .25))))}
        rows.append(row)
    return raw, rows


def write(path, rows):
    path.write_text("".join(json.dumps(r, allow_nan=False) + "\n" for r in rows))


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.rows = fixture()

    def score(self, rows=None, reference=None):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "candidate.jsonl"
            write(p, self.rows if rows is None else rows)
            rp = None
            if reference is not None:
                rp = Path(d) / "reference.jsonl"; write(rp, reference)
            return e.evaluate(self.raw, p, rp)

    def test_complete_and_analytic_metrics(self):
        r = self.score(reference=self.rows)
        self.assertEqual((len(r["models"]), len(r["pupil_r2"]), len(r["pairs"])), (42, 41, 552))
        self.assertEqual([r["aggregates"][a]["P05"]["ordered_pairs"] for a in e.ANIMALS], [240, 72, 240])
        self.assertEqual(r["aggregates"]["pooled"]["P01"]["paired_greater"]["n"], 84)
        self.assertEqual(r["aggregates"]["pooled"]["P03"]["paired_greater"]["n"], 82)
        area = next(iter(r["models"].values()))["areas"]["left"]
        self.assertAlmostEqual(area["mean_percent"]["across"], (9 / 11 + 1 / 3) * 50)
        self.assertNotAlmostEqual(area["mean_percent"]["across"], 100 * 10 / 14)
        self.assertEqual(area["dshared"], {"across": 2, "within": 1})
        self.assertEqual(r["aggregates"]["pooled"]["P03"]["means"]["across"], 1)
        self.assertEqual(r["aggregates"]["pooled"]["P04"]["means"]["across"], .75)
        self.assertTrue(all(v == 0 for x in r["reference_absolute_differences"]["pupil"].values() for y in x.values() for v in y.values()))
        self.assertIsNone(r["numerical_pass"])

    def test_rotations_and_signs_preserve_covariance(self):
        changed = copy.deepcopy(self.rows)
        for row in changed[1:43]:
            for k in ("W_left", "W_right"):
                row["loadings"][k] = [[y, -x] for x, y in row["loadings"][k]]
            for k in ("L_left", "L_right"):
                row["loadings"][k] = [[-x[0]] for x in row["loadings"][k]]
        r = self.score(changed, self.rows)
        for s in r["reference_absolute_differences"]["models"].values():
            self.assertTrue(all(x == 0 for row in s["cross_covariance"] for x in row))
            for h in ("left", "right"):
                self.assertTrue(all(x == 0 for m in s[h]["covariance"].values() for row in m for x in row))

    def test_analytic_spectrum_and_threshold(self):
        for scale in (1e-100, 1., 1e100):
            v, d = e.spectrum([[math.sqrt(.95) * scale, 0.], [0., math.sqrt(.05) * scale]])
            self.assertEqual(d, 1); self.assertAlmostEqual(v[0], .95)
        self.assertEqual(e.spectrum([[math.sqrt(.95 - 2e-9), 0.], [0., math.sqrt(.05 + 2e-9)]])[1], 2)
        self.assertEqual(e.spectrum([[1., 1.], [1., 1.]])[1], 1)
        with self.assertRaises(e.Invalid): e.spectrum([[0., 0.], [0., 0.]])

    def test_analytic_tails(self):
        # df1 is Cauchy, df2 has the elementary t/sqrt(t²+2) CDF.
        for data in ([1., 2.], [-2., -1.], [-2., 0., 3.], [1., 2., 3.]):
            r = e.t_greater(data); t = r["t"]
            expected = .5 - math.atan(t) / math.pi if len(data) == 2 else .5 - t / (2 * math.sqrt(t*t+2))
            self.assertAlmostEqual(r["p"], expected, places=13)
        self.assertIsNone(e.t_greater([0., 0.])["p"])
        self.assertEqual(e.t_greater([1., 1.])["p"], 0.)
        self.assertAlmostEqual(e.percentile([0., 10., 20., 30.], .25), 7.5)
        self.assertEqual(e.r2([0., 1.], [0., 3.]), -7.)
        with self.assertRaises(e.Invalid): e.r2([1., 1.], [1., 1.])

    def test_candidate_cannot_select_coverage(self):
        mutations = []
        for i in (1, 43, 84):
            x = copy.deepcopy(self.rows); x.pop(i); mutations.append(x)
        x = copy.deepcopy(self.rows); x.append(x[-1]); mutations.append(x)
        x = copy.deepcopy(self.rows); x.append(None); mutations.append(x)
        x = copy.deepcopy(self.rows); x[84]["source"], x[84]["target"] = x[84]["target"], x[84]["source"]; mutations.append(x)
        x = copy.deepcopy(self.rows); x[84]["target_trial_ids"].reverse(); mutations.append(x)
        x = copy.deepcopy(self.rows); x[43]["predictions"]["one"].pop("within_left"); mutations.append(x)
        x = copy.deepcopy(self.rows); x[1]["channels"]["left"].reverse(); mutations.append(x)
        x = copy.deepcopy(self.rows); x[1]["noise"]["left"][0] = -1.; mutations.append(x)
        x = copy.deepcopy(self.rows); x[1]["dimensions"]["across"] = True; mutations.append(x)
        for i, rows in enumerate(mutations):
            with self.subTest(i=i), self.assertRaises(e.Invalid): self.score(rows)

    def test_manifest_exclusion_and_binding(self):
        m = json.loads(self.raw); m["sessions"].pop()
        with self.assertRaises(e.Invalid): e.manifest(json.dumps(m).encode(), [x["session"] for x in self.rows[1:43]])
        m = json.loads(self.raw)
        for r in m["sessions"]: r["fast_pupil"] = [-1 if v < 0 else 1 for v in r["fast_pupil"]]
        with self.assertRaises(e.Invalid): e.manifest(json.dumps(m).encode(), [x["session"] for x in self.rows[1:43]])
        x = copy.deepcopy(self.rows); x[0]["support_sha256"] = "f" * 64
        with self.assertRaises(e.Invalid): self.score(x)

    def test_json_boundary_and_reference_refusal(self):
        with self.assertRaises(e.Invalid): e.decode(b'{"a":1,"a":2}')
        with self.assertRaises(e.Invalid): e.decode(b'{"a":NaN}')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x"; p.write_bytes(b'{"kind":"x"}')
            with self.assertRaises(e.Invalid): list(e.records(p))
            p.write_bytes(b' ' * (e.MAX_RECORD + 1) + b'\n')
            with self.assertRaises(e.Invalid): list(e.records(p))
            q = Path(d) / "link"; q.symlink_to(p)
            with self.assertRaises(OSError): list(e.records(q))
            fifo = Path(d) / "fifo"; os.mkfifo(fifo)
            with self.assertRaises(e.Invalid): list(e.records(fifo))
            with self.assertRaises(e.Invalid): e.read_regular(fifo, 10)
        with self.assertRaises(e.Invalid): self.score(reference=self.rows[:-1])


if __name__ == "__main__":
    unittest.main()

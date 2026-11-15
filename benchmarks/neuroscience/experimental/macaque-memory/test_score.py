"""Invented arithmetic and scientific-boundary checks, never authentic results."""
import copy
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
import score


def fixture():
    roster = [{"animal": a, "session": f"invented-{a}-{i}"}
              for a, n in (("animal_1", 18), ("animal_2", 17)) for i in range(n)]
    cases = [{"case_id": f"{r['animal']}-{r['session']}-{y}", **r,
              "block": "evaluation", "target": y} for r in roster for y in ("old", "new")]
    manifest = {"schema": "macaque-memory-protected-predictions-v1",
                "endpoint": "prospective_within_session_block_memory_age",
                "source_roster_sha256": hashlib.sha256(json.dumps(roster, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                "training_blocks": [{**r, "block": "training"} for r in roster], "cases": cases}
    submission = {"schema": "macaque-memory-submission-v1", "predictions": [
        {"case_id": c["case_id"], "p_new": 0.8 if c["target"] == "new" else 0.2} for c in cases]}
    baselines = {name: [{"case_id": c["case_id"], "p_new": 0.5} for c in cases] for name in score.BASELINES}
    return manifest, submission, baselines, roster


class Controls(unittest.TestCase):
    def test_json_boundary_refusals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented.json"
            for body in ('{"p_new":0.2,"p_new":0.9}', '{"p_new":NaN}'):
                path.write_text(body)
                with self.subTest(body=body), self.assertRaises(score.Invalid):
                    score.load(path)

    def test_hand_calculated_gain(self):
        out = score.score(*fixture())
        self.assertAlmostEqual(out["candidate"]["balanced_log_loss_nats"], -math.log(0.8))
        self.assertAlmostEqual(out["primary_gain_nats"], math.log(1.6))
        self.assertEqual(out["candidate"]["balanced_accuracy"], 1)

    def test_animal_and_condition_weight_not_row_pooling(self):
        m, s, b, r = fixture()
        # animal_1 is perfect and animal_2 completely reversed. Add 100 old animal_1 trials:
        # each animal and each within-session condition must still weigh equally.
        for row in s["predictions"]:
            if row["case_id"].startswith("animal_2-"):
                row["p_new"] = 1 - row["p_new"]
        for i in range(100):
            c = {**m["cases"][0], "case_id": f"duplicate-observation-{i}"}
            m["cases"].append(c)
            s["predictions"].append({"case_id": c["case_id"], "p_new": 0.2})
            for baseline in b.values(): baseline.append({"case_id": c["case_id"], "p_new": 0.5})
        out = score.score(m, s, b, r)
        self.assertAlmostEqual(out["candidate"]["balanced_accuracy"], 0.5)
        self.assertAlmostEqual(out["candidate"]["balanced_log_loss_nats"], -0.5 * math.log(0.8 * 0.2))

    def test_order_independence(self):
        m, s, b, r = fixture()
        a = score.score(m, s, b, r)
        s["predictions"].reverse();m["cases"].reverse()
        self.assertEqual(a, score.score(m, s, b, r))

    def test_scoring_clips_exact_zero_and_one(self):
        m, s, b, r = fixture()
        for c in s["predictions"]: c["p_new"] = float(c["p_new"] > 0.5)
        self.assertAlmostEqual(score.score(m,s,b,r)["candidate"]["balanced_log_loss_nats"], -math.log(1 - 1e-6))

    def test_refusals(self):
        def mutate(index, f):
            args = list(fixture());f(args[index]);return args
        bad = [
            mutate(0, lambda x: x["cases"].pop()),
            mutate(0, lambda x: x["cases"][0].update(block="training")),
            mutate(0, lambda x: x["cases"][0].update(target=0)),
            mutate(0, lambda x: x.update(endpoint="saved_cvAccuracy")),
            mutate(0, lambda x: x["cases"][0].update(animal="third_animal")),
            mutate(0, lambda x: x.update(source_roster_sha256="0"*64)),
            mutate(0, lambda x: x["training_blocks"].pop()),
            mutate(1, lambda x: x["predictions"].pop()),
            mutate(1, lambda x: x["predictions"][0].update(p_new=True)),
            mutate(1, lambda x: x["predictions"][0].update(p_new=float('nan'))),
            mutate(1, lambda x: x["predictions"][0].update(p_new=1.001)),
            mutate(1, lambda x: x["predictions"][0].update(target="old")),
            mutate(1, lambda x: x["predictions"][0].update(case_id=x["predictions"][1]["case_id"])),
            mutate(2, lambda x: x.pop("behavior_and_rate")),
        ]
        for i, args in enumerate(bad):
            with self.subTest(refusal=i), self.assertRaises(score.Invalid): score.score(*args)


if __name__ == "__main__": unittest.main(verbosity=2)

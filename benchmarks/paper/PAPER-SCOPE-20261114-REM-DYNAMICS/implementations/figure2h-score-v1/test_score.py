"""Generated controls only; no neuroscience observations or model fits."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

import score

GENERATED_TIMES = list(range(-150, 1, 10))  # Software fixture, not recovered paper grid.

def fixture(times=GENERATED_TIMES):
    events = [{"event_id": f"{kind}{i:03d}", "mouse_id": f"m{i % 5}", "label": label}
              for kind, count, label in (("r", 47, 1), ("w", 377, 0)) for i in range(count)]
    # Keep one biological unit in the census but outside every held draw.
    events[-1]["mouse_id"] = "m5"
    splits = [{"pc": pc, "repeat": rep,
               "train_ids": [f"{kind}{i:03d}" for kind in ("r", "w") for i in range(33)],
               "test_ids": [f"{kind}{i:03d}" for kind in ("r", "w") for i in range(33, 47)]}
              for pc in score.PCS for rep in score.REPEATS]
    owner = {"schema": "rem-fig2h-owner-v1", "task_id": score.TASK,
             "provenance": {"article_sha256": score.ARTICLE_SHA256,
                            "cohort_join_sha256": "a" * 64, "preprocessing_sha256": "b" * 64,
                            "split_source_sha256": "c" * 64, "time_grid_source_sha256": "d" * 64,
                            "time_grid_source_locator": "Generated test coordinates; not paper observations"},
             "mice": [f"m{i}" for i in range(6)], "events": events,
             "time_seconds": list(times), "rem_train_count": 33, "splits": splits}
    labels = {e["event_id"]: e["label"] for e in events}
    candidate = {"schema": "rem-fig2h-predictions-v1", "task_id": score.TASK,
                 "case_plan_sha256": score.canonical_hash(score.public_plan(owner)), "cells": []}
    for split in splits:
        for t in times:
            ids = list(reversed(split["test_ids"]))  # Identity join, not array-position assumption.
            predicted = [labels[eid] for eid in ids]
            for i in range(split["repeat"] % 3):
                predicted[i] = 1 - predicted[i]
            candidate["cells"].append({"pc": split["pc"], "repeat": split["repeat"],
                                       "time_seconds": t, "test_ids": ids,
                                       "predicted_labels": predicted})
    return owner, candidate


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner, cls.candidate = fixture()

    def test_complete_family_and_paired_accuracy(self):
        baseline = copy.deepcopy(self.candidate)
        for cell in baseline["cells"]:
            cell["predicted_labels"] = [0] * len(cell["test_ids"])
        report = score.score(self.owner, self.candidate, baseline)
        self.assertEqual(len(report["cells"]), 8800)
        self.assertEqual(len(report["curves"]), 352)
        first = report["curves"][0]
        # 9 perfect, 8 one-error, 8 two-error draws, each with 28 held events.
        expected_mean = (9 * 28 + 8 * 27 + 8 * 26) / (25 * 28)
        sse = 9 * (1 - expected_mean) ** 2 + 8 * (27 / 28 - expected_mean) ** 2 + 8 * (26 / 28 - expected_mean) ** 2
        self.assertAlmostEqual(first["mean_accuracy"], expected_mean)
        self.assertAlmostEqual(first["resampling_sem"], math.sqrt(sse / 24 / 25))
        self.assertAlmostEqual(first["mean_paired_accuracy_delta"], expected_mean - .5)
        cell = report["cells"][2]
        self.assertEqual((cell["tp"], cell["tn"], cell["fp"], cell["fn"]), (14, 12, 2, 0))
        self.assertEqual((cell["candidate_only_correct"], cell["baseline_only_correct"]), (14, 2))
        self.assertEqual(cell["mice"][-1]["n_test"], 0)
        self.assertIsNone(cell["mice"][-1]["accuracy"])
        self.assertIsNone(cell["mice"][-1]["paired_accuracy_delta"])
        self.assertEqual(len(report["event_support"]), 424)
        self.assertEqual(sum(e["held_split_uses"] == 0 for e in report["event_support"]), 396)
        self.assertFalse(report["paper_improvement_established"])
        self.assertFalse(report["author_parity_established"])

    def test_owner_failures(self):
        mutations = [
            lambda o: o["events"].pop(),
            lambda o: o["events"][0].update(label=True),
            lambda o: o["events"][0].update(mouse_id="missing"),
            lambda o: o.update(time_seconds=[]),
            lambda o: o["time_seconds"].__setitem__(0, -151),
            lambda o: o["time_seconds"].__setitem__(0, -140),
            lambda o: o["time_seconds"].__setitem__(0, float("nan")),
            lambda o: o["provenance"].update(time_grid_source_locator=" "),
            lambda o: o.update(rem_train_count=31),
            lambda o: o["splits"].__setitem__(1, o["splits"][0]),
            lambda o: o["splits"][0]["test_ids"].__setitem__(0, "r000"),
            lambda o: o["splits"][0]["test_ids"].__setitem__(14, "w000"),
            lambda o: o["splits"][0]["test_ids"].__setitem__(14, "r001"),
            lambda o: o["provenance"].update(article_sha256="0" * 64),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                owner = copy.deepcopy(self.owner)
                mutation(owner)
                with self.assertRaises(score.Invalid):
                    score.owner_index(owner)

    def test_original_rounding_can_be_bound_but_not_guessed(self):
        owner = copy.deepcopy(self.owner)
        owner["rem_train_count"] = 32
        for split in owner["splits"]:
            split["train_ids"] = [f"{kind}{i:03d}" for kind in ("r", "w") for i in range(32)]
            split["test_ids"] = [f"{kind}{i:03d}" for kind in ("r", "w") for i in range(32, 47)]
        score.owner_index(owner)
        with self.assertRaisesRegex(score.Invalid, "case-plan"):
            score.score(owner, self.candidate)

    def test_candidate_failures(self):
        _, splits = score.owner_index(self.owner)
        mutations = [
            lambda c: c["cells"].pop(),
            lambda c: c["cells"].__setitem__(1, c["cells"][0]),
            lambda c: c["cells"][0].update(time_seconds=-115),
            lambda c: c["cells"][0].update(pc=True),
            lambda c: c["cells"][0]["test_ids"].__setitem__(0, "w000"),
            lambda c: c["cells"][0]["test_ids"].__setitem__(0, c["cells"][0]["test_ids"][1]),
            lambda c: c["cells"][0]["predicted_labels"].__setitem__(0, 0.7),
            lambda c: c["cells"][0]["predicted_labels"].__setitem__(0, True),
            lambda c: c.update(case_plan_sha256="e" * 64),
            lambda c: c["cells"][0].update(targets=[0]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                # Only first cell is mutated; shallow copy the rest to keep controls light.
                candidate = dict(self.candidate)
                candidate["cells"] = list(self.candidate["cells"])
                candidate["cells"][0] = copy.deepcopy(candidate["cells"][0])
                mutation(candidate)
                with self.assertRaises(score.Invalid):
                    score.prediction_index(candidate, self.candidate["case_plan_sha256"], splits, self.owner["time_seconds"])

    def test_explicit_grid_has_no_inferred_cardinality_or_endpoint(self):
        # A deliberately short software fixture exercises the dynamic domain.
        # It is not offered as a substitute original paper endpoint.
        owner, candidate = fixture([-127.5, -117.5, -107.5])
        result = score.score(owner, candidate)
        self.assertEqual(result["time_seconds"], owner["time_seconds"])
        self.assertEqual(len(result["cells"]), 22 * 25 * 3)
        self.assertEqual(len(result["curves"]), 22 * 3)
        self.assertFalse(result["paper_reproduction_established"])
        missing = copy.deepcopy(candidate)
        missing["cells"].pop()
        with self.assertRaisesRegex(score.Invalid, "owner-bound"):
            score.score(owner, missing)
        altered = copy.deepcopy(owner)
        altered["time_seconds"] = [-127.5, -117.5]
        with self.assertRaisesRegex(score.Invalid, "case-plan"):
            score.score(altered, candidate)
        unrelated = copy.deepcopy(candidate)
        unrelated["cells"][0]["time_seconds"] = -150
        with self.assertRaisesRegex(score.Invalid, "indices"):
            score.score(owner, unrelated)

    def test_plan_has_no_targets_and_binds_provenance(self):
        plan = score.public_plan(self.owner)
        self.assertTrue(all(set(e) == {"event_id", "mouse_id"} for e in plan["events"]))
        altered = copy.deepcopy(self.owner)
        altered["provenance"]["preprocessing_sha256"] = "f" * 64
        self.assertNotEqual(score.canonical_hash(score.public_plan(altered)), self.candidate["case_plan_sha256"])

    def test_bounded_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.json"
            for body in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(body)
                with self.assertRaises(score.Invalid):
                    score.load(path)
            path.write_text('{"x":1}')
            self.assertEqual(score.load(path)[0], {"x": 1})
            # Real serializable prediction dimensions must fit the CLI's byte bound.
            self.assertLess(len(json.dumps(self.candidate).encode()), score.MAX_BYTES)


if __name__ == "__main__":
    unittest.main()

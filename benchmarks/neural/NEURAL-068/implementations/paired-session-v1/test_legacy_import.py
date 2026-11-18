"""Generated metadata/prediction controls; no real targets, arrays or participant."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("legacy_import", Path(__file__).with_name("legacy_import.py"))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
s = bridge.scorer


def fixture():
    metadata = []
    for i, (run, _) in enumerate(s.RUNS):
        n = 602 + i % 3
        metadata.append({"run": run, "source_sha256": format(i + 1, "064x"),
                         "time_s": [i * .02 for i in range(n)],
                         "trial": [1] * 500 + [2] * 100 + [3] * (n - 600),
                         "eval_mask": [True] * n})
    layout = s.make_layout(metadata)
    rows = [{"run": run, "role": "train"} for run in bridge.TRAIN]
    for row in layout["runs"]:
        start, stop = row["query_start_bin"], row["query_stop_bin"]
        rows.append({"run": row["run"], "role": "query", "n_rows": stop,
                     "source": {"sha256": row["source_sha256"]},
                     "split": {"query_start": start, "query_stop": stop,
                               "query_rows": stop - start, "query_scored_rows": sum(row["eval_mask"]),
                               "segments": [[0, 500], [500, start], [start, stop]],
                               "prefixes": {str(b): {"elapsed_seconds": b, "rows": b * 50,
                                                      "labeled_rows": row["calibration_labeled_rows"][str(b)]}
                                            for b in s.BUDGETS}}})
    pool = {"schema": bridge.LEGACY_SCHEMA, "packet_id": "pending", "labels": list(bridge.LABELS),
            "runs": rows, "scope": "generated", "shared_preparation": {},
            "performance_inspected": False, "scientific_computation": False}
    pool["packet_id"] = bridge.legacy_packet_id(pool)
    answers, targets = {}, {}
    for idx, row in enumerate(layout["runs"]):
        y = [[float(idx % 2) * 10.] * 7 for _ in row["row_ids"]]
        targets[row["run"]] = {"row_ids": row["row_ids"], "targets": y}
        for arm in s.ARMS:
            for budget in s.BUDGETS:
                key = s.context_id(row["run"], arm, budget)
                error = (1. - budget / 10.) if arm == "neural_clock" else 2.
                answers[key] = {"schema": bridge.LEGACY_SCHEMA, "packet_id": pool["packet_id"],
                                "context_id": key, "predictions": [[v + error for v in x] for x in y]}
    return layout, pool, answers, targets


class LegacyImportTests(unittest.TestCase):
    def test_complete_import_reaches_current_budget_gain_scorer(self):
        layout, pool, answers, targets = fixture()
        imported = bridge.convert(layout, pool, answers, expected_legacy_packet_id=pool["packet_id"])
        self.assertEqual(len(imported["contexts"]), 84)
        report = s.score(layout, imported, targets.__getitem__)
        self.assertEqual(report["status"], "scored")
        self.assertEqual(report["primary"]["0"], 0.)
        self.assertGreater(report["primary"]["10"], report["primary"]["5"])
        self.assertGreater(report["primary"]["5"], 0.)
        self.assertEqual(report["paired_gains"]["clock_only"], {"0": 0., "5": 0., "10": 0.})
        self.assertEqual(report["sessions"], 7)

    def test_conversion_is_exact_and_copies_prediction_rows(self):
        layout, pool, answers, _ = fixture()
        before = copy.deepcopy((layout, pool, answers))
        result = bridge.convert(layout, pool, answers, expected_legacy_packet_id=pool["packet_id"])
        self.assertEqual(before, (layout, pool, answers))
        first = next(iter(answers))
        self.assertEqual(result["contexts"][first]["predictions"], answers[first]["predictions"])
        result["contexts"][first]["predictions"][0][0] = -99.
        self.assertEqual(before, (layout, pool, answers))

    def test_external_generation_freeze_is_required(self):
        layout, pool, answers, _ = fixture()
        with self.assertRaises(s.ContractError):
            bridge.convert(layout, pool, answers, expected_legacy_packet_id="f" * 64)
        pool["scope"] = "modified after freeze"
        with self.assertRaisesRegex(s.ContractError, "generation"):
            bridge.convert(layout, pool, answers, expected_legacy_packet_id=pool["packet_id"])

    def test_wrong_source_split_prefix_or_channel_order_is_rejected(self):
        layout, pool, answers, _ = fixture()
        mutations = [
            (lambda p: p["runs"][13]["source"].update(sha256="f" * 64), "Same original NWB source hash"),
            (lambda p: p["runs"][13]["split"].update(query_start=601), "Exact recorded query support: query_start"),
            (lambda p: p["runs"][13]["split"].update(query_scored_rows=99), "Exact recorded query support: query_scored_rows"),
            (lambda p: p["runs"][13]["split"]["prefixes"]["5"].update(labeled_rows=249), "Same calibration label support"),
            (lambda p: p["runs"][13]["split"]["prefixes"]["0"].update(rows=True), "Exact prefix row support"),
            (lambda p: p["runs"][13].update(n_rows=999), "Complete third-segment suffix"),
            (lambda p: p["runs"][13]["split"]["segments"].__setitem__(1, [499, 600]), "Same recorded first-prefix/third-segment split"),
            (lambda p: p["labels"].reverse(), "Exact seven-channel order"),
            (lambda p: p["runs"].reverse(), "Exact legacy run order"),
            (lambda p: p["runs"][0].update(role="query"), "Exact training/query partition"),
        ]
        for mutate, reason in mutations:
            with self.subTest(expected_failure=reason):
                changed = copy.deepcopy(pool)
                mutate(changed)
                changed["packet_id"] = bridge.legacy_packet_id(changed)
                changed_answers = copy.deepcopy(answers)
                # Keep answer generations consistent with the selected mutated
                # pool. An unrelated later generation rejection must not make
                # a missing source/split/prefix guard look covered.
                for answer in changed_answers.values():
                    answer["packet_id"] = changed["packet_id"]
                with self.assertRaisesRegex(s.ContractError, reason):
                    bridge.convert(layout, changed, changed_answers,
                                   expected_legacy_packet_id=changed["packet_id"])

    def test_all_contexts_and_same_generation_required(self):
        layout, pool, answers, _ = fixture()
        first = next(iter(answers))
        mutations = [lambda a: a.pop(first), lambda a: a.update(extra={}),
                     lambda a: a[first].update(packet_id="f" * 64),
                     lambda a: a[first].update(context_id="different"),
                     lambda a: a[first].update(schema=s.VERSION),
                     lambda a: a[first].update(score=.9)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(answers)
                mutate(changed)
                with self.assertRaises(s.ContractError):
                    bridge.convert(layout, pool, changed, expected_legacy_packet_id=pool["packet_id"])

    def test_predictions_are_complete_finite_seven_channel_values(self):
        layout, pool, answers, _ = fixture()
        first = next(iter(answers))
        mutations = [lambda a: a[first]["predictions"].pop(),
                     lambda a: a[first]["predictions"][0].pop(),
                     lambda a: a[first]["predictions"][0].__setitem__(0, True),
                     lambda a: a[first]["predictions"][0].__setitem__(0, math.nan),
                     lambda a: a[first]["predictions"][0].__setitem__(0, math.inf)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(answers)
                mutate(changed)
                with self.assertRaises(s.ContractError):
                    bridge.convert(layout, pool, changed, expected_legacy_packet_id=pool["packet_id"])

    def test_canonical_generation_uses_legacy_ascii_and_terminal_newline(self):
        import hashlib
        import json
        _, pool, _, _ = fixture()
        pool["scope"] = "generated \u03b1"
        body = {key: value for key, value in pool.items() if key != "packet_id"}
        expected = hashlib.sha256((json.dumps(body, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")).hexdigest()
        self.assertEqual(bridge.legacy_packet_id(pool), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)

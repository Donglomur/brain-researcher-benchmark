import copy
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mint_reference import (TASK_ID, evaluate, make_schedule, mutual_information,
                            qe_intercept, quadratic_extrapolation, validate_packet)


def packet():
    # Complete deterministic binary Cartesian product, not a biological stand-in.
    neural = [[a, b] for _ in range(4) for a, b in itertools.product((0, 1), repeat=2)]
    return {"schema_version": 1, "task_id": TASK_ID, "data_kind": "generated_engineering_control", "expected_session_ids": ["control"], "provenance": {"source": "exact binary Cartesian product algebra control", "binning_status": "fixed_input_labels_native_provenance_unverified"}, "sessions": [{"session_id": "control", "animal_id": "engineering-group", "neuron_ids": ["a", "b"], "sample_ids": [f"sample-{i}" for i in range(16)], "ordering": "acquisition_order", "neural": neural, "stimulus": [a ^ b for a, b in neural]}]}


class ReferenceTests(unittest.TestCase):
    def test_exact_mi_oracles(self):
        self.assertAlmostEqual(mutual_information([0, 0, 1, 1], [0, 1, 0, 1]), 0)
        self.assertAlmostEqual(mutual_information([0, 0, 1, 1], [0, 0, 1, 1]), 1)
        r = [0] * 4 + [1] * 4
        s = [0, 0, 0, 1, 0, 1, 1, 1]
        self.assertAlmostEqual(mutual_information(r, s), 0.18872187554086717)
        self.assertAlmostEqual(mutual_information(r * 3, s * 3), mutual_information(r, s))
        self.assertAlmostEqual(mutual_information([10 + a for a in r], [20 + b for b in s]), mutual_information(r, s))

    def test_xor_and_redundancy(self):
        p = packet()["sessions"][0]
        r = p["neural"]; s = p["stimulus"]
        self.assertAlmostEqual(mutual_information([tuple(x) for x in r], s), 1)
        self.assertAlmostEqual(mutual_information([x[0] for x in r], s), 0)
        self.assertAlmostEqual(mutual_information([(x, x) for x in s], s), 1)
        self.assertAlmostEqual(sum(mutual_information(s, s) for _ in range(2)), 2)

    def test_negative_shuffle_subtraction_exact_enumeration(self):
        r, s = [0, 0, 1, 1], [0, 1, 0, 1]
        null = [mutual_information(r, [s[i] for i in order]) for order in itertools.permutations(range(4))]
        self.assertAlmostEqual(mutual_information(r, s) - statistics.fmean(null), -1 / 3)
        from mint_reference import _estimate
        plan = {"indices": list(range(4)), "qe_partitions": [], "null_orders": [list(x) for x in itertools.permutations(range(4))]}
        self.assertAlmostEqual(_estimate(r, s, plan)["shuffle_subtracted_bits"], -1 / 3)

    def test_qe_polynomial_identity_and_balanced_partitions(self):
        def f(n): return 0.3 + 5 / n + 8 / n ** 2
        self.assertAlmostEqual(qe_intercept(f(64), f(32), f(16)), .3)
        r = [0, 1] * 8
        self.assertAlmostEqual(quadratic_extrapolation(r, r, [list(range(16))]), 1)
        with self.assertRaises(ValueError): quadratic_extrapolation(r[:15], r[:15], [list(range(15))])
        with self.assertRaises(ValueError): quadratic_extrapolation(r, r, [[0] * 16])

    def test_schedules_are_common_joint_and_deterministic(self):
        args = (16, 8, 2, 5, 2, 123, "a", "circular_shift")
        a = make_schedule(*args); self.assertEqual(a, make_schedule(*args))
        for plan in a:
            self.assertEqual(len(set(plan["indices"])), 8)
            for order in plan["null_orders"]:
                self.assertEqual(sorted(order), list(range(16)))
                self.assertEqual(len({(order[i] - i) % 16 for i in range(16)}), 1)
                self.assertNotEqual(order, list(range(16)))
        self.assertNotEqual(a, make_schedule(16, 8, 2, 5, 2, 124, "a", "circular_shift"))

    def test_iid_selected_label_histogram_preserved(self):
        for plan in make_schedule(24, 8, 3, 7, 2, 9, "s", "iid_permutation"):
            for order in plan["null_orders"]:
                self.assertEqual(sorted(order[i] for i in plan["indices"]), plan["indices"])
                self.assertEqual(sorted(order), list(range(24)))

    def test_direct_mi_api_rejects_noninteger_states(self):
        for bad in (float("nan"), float("inf"), True, None, (1, float("nan"))):
            with self.assertRaises(ValueError): mutual_information([bad, 0], [0, 1])

    def test_all_pairs_full_count_negative_and_group_means(self):
        p = packet()
        p["sessions"][0]["neuron_ids"].append("duplicate-a")
        for row in p["sessions"][0]["neural"]: row.append(row[0])
        result = evaluate(p, sample_sizes=[8], repeats=2, null_count=4, qe_repeats=2)
        self.assertEqual(result["population"]["total_pairs"], 3)
        self.assertEqual(len(result["rows"]), 9)
        self.assertEqual({x["n"] for x in result["rows"]}, {8, 16})
        self.assertEqual(result["scientific_qualification"], "unknown")
        self.assertEqual(result, evaluate(p, sample_sizes=[8], repeats=2, null_count=4, qe_repeats=2))
        self.assertTrue(all(math.isfinite(r["plugin_bits"]) for r in result["rows"]))

    def test_full_recording_remainder_is_not_dropped(self):
        p = packet()
        s = p["sessions"][0]
        for name in ("sample_ids", "stimulus", "neural"): s[name].pop()
        result = evaluate(p, sample_sizes=[8], null_count=3)
        row = next(r for r in result["rows"] if r["n"] == 15)
        self.assertIsNone(row["qe_bits"])
        self.assertIsNotNone(row["shuffle_subtracted_bits"])
        self.assertEqual(row["full_n"], 15)

    def test_neuron_cap_is_explicit_source_semantics(self):
        p = packet(); q = copy.deepcopy(p)
        for r in p["sessions"][0]["neural"]: r[0] = 5 if r[0] else 0
        for r in q["sessions"][0]["neural"]: r[0] = 4 if r[0] else 0
        a = evaluate(p, sample_sizes=[8], null_count=3)
        b = evaluate(q, sample_sizes=[8], null_count=3)
        self.assertEqual(a["rows"], b["rows"])
        self.assertEqual(a["protocol"]["response_cap"], 4)

    def test_roster_shape_nonfinite_and_empty_rejected(self):
        for mut in [lambda p: p["expected_session_ids"].append("missing"), lambda p: p["sessions"][0]["neural"][0].append(0), lambda p: p["sessions"][0]["neural"][0].__setitem__(0, float("nan")), lambda p: p["sessions"][0]["stimulus"].__setitem__(0, True), lambda p: p["sessions"][0]["sample_ids"].__setitem__(0, "sample-1")]:
            p = packet(); mut(p)
            with self.assertRaises(ValueError): validate_packet(p)
        for sizes in ([9], [20], [], [8, 8]):
            with self.assertRaises(ValueError): evaluate(packet(), sample_sizes=sizes)

    def test_cli_runs_real_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "input.json", Path(tmp) / "result.json"
            src.write_text(json.dumps(packet()))
            subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "mint_reference.py"), str(src), str(dst), "--sample-sizes", "8", "--null-count", "3", "--qe-repeats", "2"], check=True, capture_output=True)
            self.assertEqual(json.loads(dst.read_text())["population"]["sessions"], 1)


if __name__ == "__main__": unittest.main()

"""Generated engineering controls; no authentic scientific results."""
import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import numpy as np

PACKAGE = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neds_evaluator", PACKAGE / "neds_evaluator.py")
ne = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ne)


def session(eid, animal="animal-1"):
    result = {"eid": eid, "animal_id": animal, "bin_width_seconds": 0.02,
              "unit_ids": ["unit-a", "unit-b"], "source_identity": {"kind": "generated_engineering", "exact_ONE_identity": "unresolved"}}
    for split, offset in (("train", 0), ("validation", 10), ("test", 20)):
        n = 4
        wave = np.tile(np.arange(100) % 3, (n, 1)).astype(float)
        wave += np.arange(n)[:, None] * 0.3
        spikes = np.stack([np.floor(wave + 1), 2 + np.floor(wave)], axis=2)
        result[split] = {"trial_ids": [f"trial-{offset+i}" for i in range(n)],
                         "spike": spikes.tolist(), "wheel": wave.tolist(), "whisker": (wave * 0.25 + 0.2).tolist(),
                         "choice": [-1, 1, -1, 1], "block": [0.2, 0.5, 0.8, 0.2]}
    return result


def bundle(full=False):
    roster = ne.load_roster()
    eids = roster["training_eids"] + roster["heldout_eids"] if full else [roster["training_eids"][0], roster["heldout_eids"][0]]
    return {"schema": "neds-binned-panel-v1", "source_commit": ne.COMMIT, "evidence_kind": "generated_engineering",
            "sessions": [session(eid, "animal-" + str(i)) for i, eid in enumerate(eids)]}


def oracle(s):
    return {task: {field: copy.deepcopy(s["test"][field]) for field in (("spike",) if task in ne.ENCODING else ne.BEHAVIORS)} for task in ne.TASKS}


class Metrics(unittest.TestCase):
    def test_independent_neuron_macro_not_spike_weighted(self):
        # Independently derived from Poisson log-likelihood cancellation.
        y = np.array([[[0, 0], [2, 20]]])
        p = np.array([[[0.5, 10], [1.5, 10]]])
        result = ne.bits_per_spike(y, p)
        self.assertAlmostEqual(result["per_unit"][0], np.log2(1.5))
        self.assertEqual(result["per_unit"][1], 0)
        self.assertAlmostEqual(result["session_mean"], np.log2(1.5) / 2)
        self.assertNotAlmostEqual(result["session_mean"], np.log2(1.5) / 11)

    def test_pinned_source_ast_reference(self):
        y = np.array([[[0, 2], [1, 3]], [[2, 1], [3, 0]]])
        result = ne.bits_per_spike(y, y + 0.25)
        for v in result["per_unit"]:
            self.assertAlmostEqual(v, 0.46843786782989394, places=14)

    def test_zero_floor_only_and_no_mutation(self):
        y = np.array([[[1], [0]]])
        rates = np.array([[[1e-12], [0.0]]])
        saved = rates.copy()
        actual = ne.bits_per_spike(y, rates)["session_mean"]
        expected = (1 - 1e-12 - 1e-9 + np.log(1e-12 / 0.5)) / np.log(2)
        self.assertAlmostEqual(actual, expected)
        np.testing.assert_array_equal(rates, saved)

    def test_finite_input_numeric_overflow_rejected(self):
        with self.assertRaises(ne.ContractError):
            ne.bits_per_spike(np.ones((1, 2, 1)), np.full((1, 2, 1), 1e308))
        with self.assertRaises(ne.ContractError):
            ne.r_squared([1, 2], [1e308, -1e308])
        with self.assertRaises(ne.ContractError):
            ne.r_squared([0, 1e-150], [1e150, -1e150])

    def test_train_null_is_separate(self):
        y = np.array([[[0], [2]]])
        rates = np.ones_like(y)
        self.assertEqual(ne.bits_per_spike(y, rates)["session_mean"], 0)
        other = ne.bits_per_spike(y, rates, np.ones((3, 2, 1)) * 3)
        self.assertAlmostEqual(other["session_mean"], (4 - 2 * np.log(3)) / 2 / np.log(2))
        self.assertEqual(other["null"], "training_mean_prospective")

    def test_degeneracy_and_unclipped_r2(self):
        bps = ne.bits_per_spike(np.zeros((2, 3, 1)), np.ones((2, 3, 1)))
        self.assertIsNone(bps["session_mean"])
        self.assertEqual(bps["zero_spike_unit_indices"], [0])
        self.assertEqual(ne.r_squared([1, 2, 3], [3, 2, 1])["r2"], -3)
        self.assertEqual(ne.r_squared([2, 2], [2, 3])["r2"], 0)
        self.assertTrue(ne.r_squared([2, 2], [2, 2])["constant_target"])
        with self.assertRaises(ne.ContractError):
            ne.bits_per_spike(np.ones((1, 2, 1)), -np.ones((1, 2, 1)))


class Contracts(unittest.TestCase):
    def setUp(self):
        self.b = bundle()
        self.s = self.b["sessions"][0]

    def test_full_roster_required_and_source_pins(self):
        self.assertEqual(len(ne.load_roster()["training_eids"]), 74)
        self.assertEqual(len(ne.load_roster()["heldout_eids"]), 10)
        with self.assertRaises(ne.ContractError):
            ne.validate_bundle(self.b)
        self.b["evidence_kind"] = "operator_supplied_unqualified"
        with self.assertRaises(ne.ContractError):
            ne.validate_bundle(self.b, True)
        self.assertEqual(len(ne.validate_bundle(bundle(True))), 84)

    def test_overlap_alias_nonfinite_and_unit_tampering(self):
        for attack in ("overlap", "alias", "nan", "unit"):
            s = copy.deepcopy(self.s)
            if attack == "overlap": s["test"]["trial_ids"][0] = s["train"]["trial_ids"][0]
            if attack == "alias": s["test"]["reward"] = [1, 1, 1, 1]
            if attack == "nan": s["test"]["wheel"][0][0] = float("nan")
            if attack == "unit": s["unit_ids"][1] = s["unit_ids"][0]
            with self.subTest(attack=attack), self.assertRaises(ne.ContractError):
                ne.validate_session(s)

    def test_target_mutations_do_not_enter_packets(self):
        baseline = ne.input_packet(self.s, "test", "decode_all")
        for f in ne.BEHAVIORS:
            changed = copy.deepcopy(self.s)
            changed["test"][f] = np.zeros_like(changed["test"][f]).tolist()
            self.assertEqual(baseline, ne.input_packet(changed, "test", "decode_all"))
        baseline = ne.input_packet(self.s, "test", "encode_all")
        changed = copy.deepcopy(self.s)
        changed["test"]["spike"] = np.ones_like(changed["test"]["spike"]).tolist()
        self.assertEqual(baseline, ne.input_packet(changed, "test", "encode_all"))
        self.assertEqual(set(ne.input_packet(self.s, "test", "encode_wheel")["inputs"]), {"wheel"})
        baseline["inputs"]["wheel"][0][0] = 900
        self.assertNotEqual(self.s["test"]["wheel"][0][0], 900)

    def test_reference_test_targets_cannot_fit_or_select(self):
        pred, recipes = ne.reference_predictions(self.s)
        changed = copy.deepcopy(self.s)
        changed["test"]["spike"] = (np.array(changed["test"]["spike"]) + 1000).tolist()
        changed_pred, changed_recipes = ne.reference_predictions(changed)
        for task in ne.ENCODING:
            self.assertEqual(pred[task], changed_pred[task])
            self.assertEqual(recipes[task + ":spike"], changed_recipes[task + ":spike"])
        changed = copy.deepcopy(self.s)
        for f in ("wheel", "whisker"):
            changed["test"][f] = (np.array(changed["test"][f]) + 1000).tolist()
        changed["test"]["choice"] = [1, 1, 1, 1]
        changed_pred, changed_recipes = ne.reference_predictions(changed)
        self.assertEqual(pred["decode_all"], changed_pred["decode_all"])
        for f in ne.BEHAVIORS:
            self.assertEqual(recipes["decode_all:" + f], changed_recipes["decode_all:" + f])

    def test_pair_completeness_packet_and_exposure(self):
        rows = [ne.make_receipt(s, method, oracle(s), "matched-budget-v1") for s in self.b["sessions"] for method in ("multitask", "task_specific")]
        result = ne.evaluate(self.b, rows, engineering_subset=True, draws=16)
        self.assertEqual(result["summaries"]["heldout"]["pareto_relation"], "tie")
        self.assertEqual(result["scientific_qualification"], "unknown")
        for attack in ("missing", "packet", "budget", "pretrain", "order"):
            bad = copy.deepcopy(rows)
            if attack == "missing": bad.pop()
            if attack == "packet": bad[0]["packet_sha256"]["decode_all"] = "0" * 64
            if attack == "budget": bad[0]["budget_contract"] = "more-compute"
            if attack == "pretrain": bad[0]["pretrained_eids"] = [ne.load_roster()["heldout_eids"][0]]
            if attack == "order": bad[0]["trial_ids"].reverse()
            with self.subTest(attack=attack), self.assertRaises(ne.ContractError):
                ne.evaluate(self.b, bad, engineering_subset=True, draws=16)

    def test_zero_spike_session_not_dropped(self):
        self.s["test"]["spike"] = np.zeros_like(self.s["test"]["spike"]).tolist()
        rows = [ne.make_receipt(s, m, oracle(s), "budget") for s in self.b["sessions"] for m in ("multitask", "task_specific")]
        result = ne.evaluate(self.b, rows, engineering_subset=True, draws=16)
        self.assertEqual(result["summaries"]["training"]["pareto_relation"], "undefined")
        metric = result["summaries"]["training"]["endpoints"]["encode_all:bits_per_spike"]
        self.assertIsNone(metric["session_macro"]["multitask"])
        self.assertEqual(metric["unscoreable_session_eids"], [self.s["eid"]])

    def test_full_panel_and_cli(self):
        b = bundle(True)
        rows = [ne.make_receipt(s, m, oracle(s), "generated-matched-budget") for s in b["sessions"] for m in ("multitask", "task_specific")]
        result = ne.evaluate(b, rows, draws=16)
        self.assertEqual(len(result["session_results"]), 84)
        self.assertEqual(result["summaries"]["training"]["sessions"], 74)
        self.assertEqual(result["summaries"]["heldout"]["sessions"], 10)
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            (p / "input.json").write_text(json.dumps(self.b))
            subprocess.run([sys.executable, str(PACKAGE / "neds_evaluator.py"), str(p / "input.json"), str(p / "output.json"), "--engineering-subset", "--bootstrap-draws", "16"], check=True, capture_output=True)
            got = json.loads((p / "output.json").read_text())
            self.assertEqual(got["methods"], ["prospective_ridge_reference"])
            self.assertTrue(got["reference_recipes"])

    def test_animal_macro_is_not_session_macro(self):
        rows = []
        for i, (animal, delta) in enumerate((("a", 0), ("a", 0), ("b", 3))):
            rows.append({"eid": str(i), "animal_id": animal, "cohort": "training", "scores": {"x": {"endpoints": {"wheel:r2": delta}}, "y": {"endpoints": {"wheel:r2": 0}}}})
        first = ne.summarize(rows, ("x", "y"), 64, 5)
        self.assertEqual(first, ne.summarize(rows, ("x", "y"), 64, 5))
        m = first["training"]["endpoints"]["wheel:r2"]
        self.assertEqual(m["paired_session_macro_difference"], 1)
        self.assertEqual(m["paired_animal_macro_difference"], 1.5)

if __name__ == "__main__":
    unittest.main()

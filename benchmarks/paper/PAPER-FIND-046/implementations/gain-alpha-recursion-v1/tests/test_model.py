"""Generated controls only; hand-derived recurrences, no empirical/native run."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "model.py"
spec = importlib.util.spec_from_file_location("find046_gain_alpha", MODULE)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def fixture():
    return {"schema_version": 1, "input_kind": "generated_engineering_control",
            "preprocessing": "author_figure3_preprocessed_ratTrial",
            "rat_trial": {"trial_ids": [f"trial{i}" for i in range(7)],
                          "reward": [None, 1, 5, 2, None, 4, 1],
                          "iti": [None, 2, 3, 4, None, 5, 6], "ntrials": [4, 3]}}


def receipt(payload, threshold06=4.0, threshold08=4.0, iti90=6.0):
    request = model.statistic_requests(payload)
    # Explicit engineering injection. These numbers are not asserted to be
    # MATLAB percentile outputs; native parity is deliberately outside this test.
    return {"schema_version": 1, "input_kind": payload["input_kind"],
            "request_sha256": model.canonical_hash(request),
            "producer": "generated branch-control values, not a native percentile result",
            "values": {"iti_p90": iti90, "first_rpe_alpha_0.6_p90": threshold06,
                       "first_rpe_alpha_0.8_p90": threshold08}}


def conditions(report):
    return {r["condition"]: r for r in report["conditions"]}


class RecurrenceTests(unittest.TestCase):
    def assertValues(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            if e is None:
                self.assertIsNone(a)
            else:
                self.assertAlmostEqual(a, e, places=11)

    def test_requests_preserve_missing_operands_and_alpha_specific_first_pass(self):
        p = fixture()
        q = model.statistic_requests(p)
        operands = {x["key"]: x["values"] for x in q["statistic_operands"]}
        self.assertEqual(operands["iti_p90"], p["rat_trial"]["iti"])
        self.assertValues(operands["first_rpe_alpha_0.6_p90"], [0, 4, -1.4, 3, None])
        self.assertValues(operands["first_rpe_alpha_0.8_p90"], [0, 4, -2.2, 3, None])

    def test_all_fixed_source_calls_and_full_row_reinsertion(self):
        p = fixture()
        result = model.reconstruct(p, receipt(p))
        c = conditions(result)
        self.assertEqual(set(c), {"figure3a", "gain_proestrus", "alpha_proestrus",
                                  "gain_diestrus", "alpha_diestrus"})
        self.assertValues(c["figure3a"]["Kappa"], [None, 1, 1, 3.4, None, 1, 2.8])
        self.assertValues(c["figure3a"]["RPE"], [None, 0, 4, -1.4, None, 3, None])
        self.assertValues(c["alpha_proestrus"]["Kappa"], [None, 1, 1, 4.2, None, 1, 3.4])
        self.assertEqual(result["retained_indices_zero_based"], [1, 2, 3, 5, 6])
        self.assertEqual(result["retained_session_start_positions_zero_based"], [0, 3])
        self.assertEqual(result["trial_ids"], p["rat_trial"]["trial_ids"])
        for name in ("gain_diestrus", "alpha_diestrus"):
            self.assertEqual(c[name]["RPE"], c["figure3a"]["RPE"])
        self.assertFalse(result["reproduction_qualified"])
        self.assertFalse(result["improvement_eligible"])
        self.assertEqual(result["native_statistic_authentication"], "not_established")

    def test_gain_strict_threshold_not_greater_or_equal(self):
        p = fixture()
        c = conditions(model.reconstruct(p, receipt(p, threshold06=4.0)))
        self.assertEqual(c["gain_proestrus"]["RPE"], c["gain_diestrus"]["RPE"])

    def test_engineered_statistic_receipt_exercises_gain_branch(self):
        p = fixture()
        c = conditions(model.reconstruct(p, receipt(p, threshold06=2.5)))
        self.assertValues(c["gain_proestrus"]["Kappa"], [None, 1, 1, 5.2, None, 1, 4.15])
        self.assertValues(c["gain_proestrus"]["RPE"], [None, 0, 7, -3.2, None, 5.25, None])
        # The alpha-only simulation remains unaffected by an unused gain threshold.
        self.assertValues(c["alpha_diestrus"]["Kappa"], [None, 1, 1, 3.4, None, 1, 2.8])

    def test_second_pass_initial_value_is_median_of_first_pass(self):
        p = fixture()
        p["rat_trial"] = {"trial_ids": [f"x{i}" for i in range(6)],
                          "reward": [None, 5, 5, 5, 5, 5],
                          "iti": [None, 2, 3, 4, 5, 6], "ntrials": [6]}
        c = conditions(model.reconstruct(p, receipt(p)))
        self.assertAlmostEqual(c["figure3a"]["initial_kappa"], 4.36)
        self.assertValues(c["figure3a"]["Kappa"], [None, 4.36, 4.744, 4.8976, 4.95904, 4.983616])
        self.assertAlmostEqual(c["alpha_proestrus"]["initial_kappa"], 4.84)

    def test_last_retained_session_start_is_not_silently_repaired(self):
        p = fixture()
        p["rat_trial"] = {"trial_ids": [f"x{i}" for i in range(6)],
                          "reward": [None, 1, 5, 2, None, 4],
                          "iti": [None, .1, .1, .1, None, .1], "ntrials": [4, 2]}
        result = model.reconstruct(p, receipt(p, iti90=.1))
        c = conditions(result)["figure3a"]
        self.assertAlmostEqual(c["initial_kappa"], 1.78)
        self.assertAlmostEqual(c["Kappa"][-1], 2.60992)
        self.assertIsNone(c["RPE"][-1])
        self.assertTrue(result["last_retained_row_starts_session"])
        self.assertFalse(result["final_session_start_reset_executed"])
        self.assertLess(c["LatOpt"][-1], 0, "source has no active floor clamp")

    def test_empty_sessions_preserved_and_missing_iti_controls_mask(self):
        p = fixture()
        p["rat_trial"]["ntrials"] = [0, 4, 0, 3, 0]
        p["rat_trial"]["reward"][0] = 9999
        result = model.reconstruct(p, receipt(p))
        self.assertEqual(result["ntrials"], [0, 4, 0, 3, 0])
        self.assertIsNone(conditions(result)["figure3a"]["Rewards"][0])

    def test_receipt_rejects_operand_tampering_missing_extra_and_kind(self):
        p = fixture()
        original = receipt(p)
        for mutate in (lambda r: r.update(request_sha256="0" * 64),
                       lambda r: r["values"].pop("iti_p90"),
                       lambda r: r["values"].update(extra=1),
                       lambda r: r.update(input_kind="authorized_native_export"),
                       lambda r: r["values"].update(iti_p90=999),
                       lambda r: r["values"].update(iti_p90=True)):
            r = copy.deepcopy(original)
            mutate(r)
            with self.assertRaises(model.ContractError):
                model.reconstruct(p, r)
        p["rat_trial"]["trial_ids"][1] = "renamed"
        with self.assertRaisesRegex(model.ContractError, "exact operands"):
            model.reconstruct(p, original)

    def test_invalid_full_input_is_rejected_without_filtering(self):
        mutators = (
            lambda p: p["rat_trial"]["ntrials"].append(1),
            lambda p: p["rat_trial"]["trial_ids"].__setitem__(1, "trial0"),
            lambda p: p["rat_trial"]["iti"].__setitem__(0, 2),
            lambda p: p["rat_trial"]["reward"].__setitem__(1, None),
            lambda p: p["rat_trial"]["iti"].__setitem__(1, float("inf")),
            lambda p: p.update(schema_version=True),
            lambda p: p["rat_trial"].update(extra=[]),
            lambda p: p["rat_trial"].update(iti=[None] * 7),
        )
        for mutate in mutators:
            p = fixture()
            mutate(p)
            with self.assertRaises(model.ContractError):
                model.statistic_requests(p)

    def test_cli_request_reconstruct_duplicate_keys_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = fixture()
            source, stats, output = root / "input.json", root / "receipt.json", root / "out.json"
            source.write_text(json.dumps(p))
            stats.write_text(json.dumps(receipt(p)))
            common = [sys.executable, "-I", "-S", "-B", str(MODULE)]
            r = subprocess.run(common + ["reconstruct", str(source), "--receipt", str(stats),
                                         "--output", str(output)], capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr.decode()[:1000])
            before = output.read_bytes()
            r = subprocess.run(common + ["reconstruct", str(source), "--receipt", str(stats),
                                         "--output", str(output)], capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            request_path = root / "requests.json"
            r = subprocess.run(common + ["requests", str(source), "--output", str(request_path)],
                               capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr.decode()[:1000])
            self.assertEqual(json.loads(request_path.read_text()), model.statistic_requests(p))
            source.write_text('{"schema_version":1,"schema_version":1}')
            bad = root / "bad.json"
            r = subprocess.run(common + ["requests", str(source), "--output", str(bad)],
                               capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 2)
            self.assertFalse(bad.exists())
            self.assertIn(b"duplicate JSON key", r.stderr)


if __name__ == "__main__":
    unittest.main()

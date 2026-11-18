"""Generated control tables only; no spikes, native sorter or study results."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("threshold_selector", Path(__file__).with_name("selector.py"))
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


def fixture():
    manifest = {
        "schema": "kilosort4_original_threshold_sweep_inputs_v1",
        "purpose": "historical_medium_drift_reconstruction", "case_id": "medium_drift",
        "scoring_profile": "R_paper40", "source_input_sha256": "a" * 64,
        "scoring_policy_sha256": "b" * 64, "grid_provenance_sha256": "c" * 64,
        "target_unit_ids": [f"u{i}" for i in range(600)],
        "thresholds": [{"threshold_id": "tA", "parameter_setting_sha256": "d" * 64},
                       {"threshold_id": "tB", "parameter_setting_sha256": "e" * 64}],
        "tie_policy": "unavailable",
    }
    banks = []
    for bank_id in ("one", "two"):
        tables = []
        for threshold in manifest["thresholds"]:
            units = [{"unit_id": key, "role": "single-unit-target", "score": 0.8}
                     for key in manifest["target_unit_ids"]]
            units[0]["score"] = math.nextafter(0.8, math.inf)
            if threshold["threshold_id"] == "tB":
                units[1]["score"] = 0.9
            tables.append({**threshold, "source_input_sha256": "a" * 64,
                           "scoring_policy_sha256": "b" * 64, "units": units})
        banks.append({"bank_id": bank_id, "implementation_sha256": ("f" if bank_id == "one" else "0") * 64,
                      "thresholds": tables})
    return manifest, {"schema": "kilosort4_original_threshold_sweep_exports_v1",
                      "manifest_sha256": s.digest(manifest), "banks": banks}


class SweepTests(unittest.TestCase):
    def run_sweep(self, m, e, **kw):
        return s.select_sweep(m, e, max_score_rows=kw.get("max_score_rows", 2400))

    def test_full_support_strict_binary64_boundary_and_honest_scope(self):
        m, e = fixture()
        result = self.run_sweep(m, e)
        self.assertEqual([x["correctly_identified"] for x in result["counts"]], [1, 2])
        self.assertEqual(result["selected_threshold_id"], "tB")
        self.assertEqual(result["logical_score_rows"], 2400)
        self.assertEqual(result["target_count"], 600)
        for key in ("historical_equivalence", "independent_bank_authorship_verified",
                    "source_authenticity_verified", "held_out_improvement_evidence"):
            self.assertIs(result[key], False)
        self.assertIsNone(result["paper_reproduction_decision"])
        self.assertIsNone(result["paper_improvement_decision"])

    def test_bank_disagreement_cannot_hide_behind_equal_counts(self):
        m, e = fixture()
        rows = e["banks"][1]["thresholds"][0]["units"]
        rows[0]["score"], rows[5]["score"] = rows[5]["score"], rows[0]["score"]
        with self.assertRaisesRegex(s.Invalid, "disagree per target"):
            self.run_sweep(m, e)

    def test_all_declared_thresholds_required(self):
        for mutation in ("missing", "extra", "duplicate"):
            m, e = fixture()
            rows = e["banks"][0]["thresholds"]
            if mutation == "missing": rows.pop()
            elif mutation == "extra": rows.append({**deepcopy(rows[0]), "threshold_id": "other"})
            else: rows.append(deepcopy(rows[0]))
            with self.assertRaises(s.Invalid): self.run_sweep(m, e)

    def test_duplicate_declared_threshold_is_not_implicit_tie_policy(self):
        m, e = fixture()
        m["thresholds"].append(deepcopy(m["thresholds"][0]))
        e["manifest_sha256"] = s.digest(m)
        with self.assertRaisesRegex(s.Invalid, "duplicate identity"):
            self.run_sweep(m, e)

    def test_original_600_targets_not_a_convenient_subset(self):
        for size in (599, 601):
            m, e = fixture()
            m["target_unit_ids"] = [f"u{i}" for i in range(size)]
            e["manifest_sha256"] = s.digest(m)
            with self.assertRaisesRegex(s.Invalid, "600 original"):
                self.run_sweep(m, e)

    def test_target_omission_duplicate_or_same_size_substitution_rejected(self):
        for mutation in ("missing", "duplicate", "substitution"):
            m, e = fixture()
            rows = e["banks"][0]["thresholds"][0]["units"]
            if mutation == "missing": rows.pop()
            elif mutation == "duplicate": rows[-1]["unit_id"] = rows[0]["unit_id"]
            else: rows[-1]["unit_id"] = "outside"
            with self.assertRaises(s.Invalid): self.run_sweep(m, e)

    def test_score_type_and_range_rejected_before_selection(self):
        for value in (True, None, "0.9", float("nan"), float("inf"), -float("inf"), -1.01, 1.01, 10**1000):
            m, e = fixture()
            e["banks"][0]["thresholds"][0]["units"][0]["score"] = value
            with self.assertRaises(s.Invalid): self.run_sweep(m, e)

    def test_source_profile_and_parameter_bindings_cannot_change(self):
        for key in ("source_input_sha256", "scoring_policy_sha256", "parameter_setting_sha256"):
            m, e = fixture()
            e["banks"][0]["thresholds"][0][key] = "9" * 64
            with self.assertRaises(s.Invalid): self.run_sweep(m, e)

    def test_background_mua_is_not_a_target(self):
        m, e = fixture()
        e["banks"][0]["thresholds"][0]["units"][0]["role"] = "MUA"
        with self.assertRaisesRegex(s.Invalid, "background MUA"):
            self.run_sweep(m, e)

    def test_two_distinct_bank_ids_are_required_not_independence_proof(self):
        for mutation in ("missing", "duplicate", "extra"):
            m, e = fixture()
            if mutation == "missing": e["banks"].pop()
            elif mutation == "duplicate": e["banks"][1]["bank_id"] = "one"
            else: e["banks"].append({**deepcopy(e["banks"][0]), "bank_id": "three"})
            with self.assertRaises(s.Invalid): self.run_sweep(m, e)

    def test_every_tie_requires_explicit_frozen_rule(self):
        m, e = fixture()
        for bank in e["banks"]:
            bank["thresholds"][1]["units"] = deepcopy(bank["thresholds"][0]["units"])
        with self.assertRaisesRegex(s.Invalid, "tie unresolved"):
            self.run_sweep(m, e)
        for policy, expected in (("first-declared", "tA"), ("last-declared", "tB")):
            m["tie_policy"] = policy
            e["manifest_sha256"] = s.digest(m)
            result = self.run_sweep(m, e)
            self.assertEqual(result["all_ties"], ["tA", "tB"])
            self.assertEqual(result["selected_threshold_id"], expected)

    def test_input_row_reordering_does_not_change_selected_threshold(self):
        m, e = fixture()
        for bank in e["banks"]:
            bank["thresholds"].reverse()
            for table in bank["thresholds"]: table["units"].reverse()
        result = self.run_sweep(m, e)
        self.assertEqual(result["selected_threshold_id"], "tB")
        self.assertEqual(result["declared_threshold_order"], ["tA", "tB"])

    def test_budget_refuses_instead_of_truncating_sweep(self):
        m, e = fixture()
        with self.assertRaisesRegex(s.Invalid, "exceeds logical"):
            self.run_sweep(m, e, max_score_rows=2399)
        for value in (True, 0, -1, 2400.0):
            with self.assertRaises(s.Invalid): self.run_sweep(m, e, max_score_rows=value)

    def test_other_case_profile_and_heldout_tuning_rejected(self):
        for key, value in (("case_id", "fast_drift"), ("scoring_profile", "R_source20"),
                           ("purpose", "held_out_improvement")):
            m, e = fixture()
            m[key] = value
            e["manifest_sha256"] = s.digest(m)
            with self.assertRaises(s.Invalid): self.run_sweep(m, e)

    def test_stale_manifest_identity_rejected(self):
        m, e = fixture()
        m["tie_policy"] = "first-declared"
        with self.assertRaisesRegex(s.Invalid, "manifest identity"):
            self.run_sweep(m, e)


if __name__ == "__main__":
    unittest.main(verbosity=2)

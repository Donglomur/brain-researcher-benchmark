"""Generated controls only; no empirical rows, training or source result values."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
spec = importlib.util.spec_from_file_location("brainwide_score_import", MODULE)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    cells, records = [], []
    for endpoint, (runs, nulls) in s.ENDPOINTS.items():
        for session in range(2):
            cell = dict(endpoint=endpoint, eid=f"generated-eid-{session}", region="generated-region",
                        subject=f"generated-mouse-{session}",
                        unit_ids=[f"generated-eid-{session}-unit-{i}" for i in range(5)],
                        pids=[f"generated-probe-{session}"], trial_ids=[str(i) for i in range(10)],
                        bin_counts=[1 if runs == 10 else 2] * 10,
                        outer_folds={str(run): [[i, i+5] for i in range(5)] for run in range(1, runs+1)})
            cells.append(cell)
            target = [[i % 2] if runs == 10 else [i, i+0.5] for i in range(10)]
            for pseudo in [-1, *range(1, nulls+1)]:
                for run in range(1, runs+1):
                    row = dict(endpoint=endpoint, eid=cell["eid"], region=cell["region"],
                               pseudo_id=pseudo, run_id=run,
                               score=1.0 if pseudo == -1 else (0.5 if runs == 10 else 0.0))
                    if pseudo == -1:
                        row.update(subject=cell["subject"], unit_ids=cell["unit_ids"][:], pids=cell["pids"][:],
                                   trial_ids=cell["trial_ids"][:], n_units=5,
                                   idxes_test=copy.deepcopy(cell["outer_folds"][str(run)]),
                                   targets=copy.deepcopy(target), predictions=copy.deepcopy(target))
                    records.append(row)
    roster = dict(schema="brainwide-decoder-roster/v1", source_revision=s.REVISION, freeze=s.FREEZE,
                  evidence_kind="generated_control", cells=cells)
    bundle = dict(schema="brainwide-decoder-formatted-export/v1", roster_digest=s.digest(roster), records=records)
    return roster, bundle


class Metrics(unittest.TestCase):
    def test_probability_tie_and_imbalance(self):
        # Source >0.5 gives class zero on a tie; plain accuracy here would be .75.
        self.assertEqual(s.balanced_accuracy([0, 0, 0, 1], [.5, .5, .5, .5]), .5)
        self.assertEqual(s.balanced_accuracy([0, 1], [.5, .8]), 1.)
        self.assertEqual(s.balanced_accuracy([False, True], [.5, .8]), 1.)
        with self.assertRaises(ValueError):
            s.balanced_accuracy([0, 0], [.1, .2])
        with self.assertRaises(ValueError):
            s.balanced_accuracy([0, 1], [.1, float("nan")])

    def test_continuous_concat_and_negative_scores(self):
        # Two nearly constant folds have poor fold R2 despite small whole-support error.
        y, p = [0, 1, 10, 11], [1, 2, 9, 10]
        self.assertAlmostEqual(s.r_squared(y, p), 1 - 4/101)
        fold_mean = (s.r_squared(y[:2], p[:2]) + s.r_squared(y[2:], p[2:]))/2
        self.assertEqual(fold_mean, -3.)
        self.assertNotEqual(s.r_squared(y, p), fold_mean)
        self.assertEqual(s.r_squared([3, 3], [3, 3]), 1.)
        self.assertEqual(s.r_squared([3, 3], [3, 4]), 0.)

    def test_full_run_balanced_accuracy_is_not_mean_fold_accuracy(self):
        y = [0, 0, 0, 1, 0, 1, 1, 1]
        p = [0, 0, 0, 0, 1, 1, 1, 1]
        self.assertEqual(s.balanced_accuracy(y, p), .75)
        self.assertEqual((s.balanced_accuracy(y[:4], p[:4])+s.balanced_accuracy(y[4:], p[4:]))/2, .5)

    def test_observed_value_changes_null_median(self):
        result = s.summarize_session([1, 1], [[0, 0], [.2, .2]])
        self.assertEqual(result["source_median_including_observed"], .2)
        self.assertEqual(result["paper_null_only_median"], .1)
        self.assertEqual(result["source_session_p"], 1/3)
        tied = s.summarize_session([.2], [[.2], [.3]])
        self.assertEqual(tied["source_session_p"], 1.)

    def test_null_runs_are_averaged_before_median(self):
        result = s.summarize_session([1, 1], [[0, 1], [0, 0], [0, 0]])
        self.assertEqual(result["paper_null_only_median"], 0.)
        self.assertEqual(result["source_median_including_observed"], .25)

    def test_paired_median_differs_from_difference_of_medians(self):
        rows = []
        for i, (real, null) in enumerate([(.1, 0), (.2, .8), (.9, .1)]):
            rows.append(dict(endpoint="choice", region="R", eid=str(i), subject=str(i),
                             real_score=real, source_median_including_observed=null,
                             paper_corrected_score=real-null, source_session_p=.1))
        row = s.summarize_regions(rows)[0]
        self.assertAlmostEqual(row["source_figure_effect"], .1)
        # Pick a case where median(real-null) != median(real)-median(null).
        rows[1]["real_score"] = .8
        rows[1]["paper_corrected_score"] = 0
        row = s.summarize_regions(rows)[0]
        self.assertAlmostEqual(row["source_figure_effect"], .7)
        self.assertAlmostEqual(row["paper_text_effect"], .1)

    def test_fisher_and_bh_independent_analytic_controls(self):
        product = .05 * .1
        self.assertAlmostEqual(s.fisher([.05, .1]), product*(1-math.log(product)))
        self.assertEqual(s.fisher([1, 1]), 1.)
        for a, b in zip(s.bh([.01, .04, .03]), [.03, .04, .04]):
            self.assertAlmostEqual(a, b)


class CompleteImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.bundle = fixture()

    def test_all_source_repetitions_and_endpoints(self):
        report = s.evaluate(self.roster, self.bundle)
        self.assertEqual(len(report["sessions"]), 10)
        self.assertEqual(len(report["regions"]), 5)
        self.assertEqual(report["scored_real_runs"], 68)
        self.assertEqual(len(self.bundle["records"]), 12868)
        for row in report["regions"]:
            expected = .5 if s.ENDPOINTS[row["endpoint"]][0] == 10 else 1.
            self.assertEqual(row["source_figure_effect"], expected)
            self.assertEqual(row["paper_text_effect"], expected)
        self.assertIn("software_component_only", report["qualification"])
        json.dumps(report, allow_nan=False)

    def test_leaf_order_is_irrelevant(self):
        bundle = dict(self.bundle, records=list(reversed(self.bundle["records"])))
        first, second = s.evaluate(self.roster, self.bundle), s.evaluate(self.roster, bundle)
        self.assertEqual(first["sessions"], second["sessions"])
        self.assertEqual(first["regions"], second["regions"])

    def test_binary_json_boolean_targets_preserve_labels(self):
        roster, bundle = fixture()
        for row in bundle["records"]:
            if row["pseudo_id"] == -1 and s.ENDPOINTS[row["endpoint"]][0] == 10:
                row["targets"] = [[bool(value[0])] for value in row["targets"]]
        self.assertEqual(s.evaluate(roster, bundle)["regions"], s.evaluate(self.roster, self.bundle)["regions"])

    def test_missing_or_duplicated_null_run_cannot_pass_count_check(self):
        rows = self.bundle["records"]
        for altered in [rows[:-1], rows[:-1]+[rows[-2]], rows+[rows[-1]]]:
            with self.assertRaises(ValueError):
                s.evaluate(self.roster, dict(self.bundle, records=altered))

    def test_real_support_mutations_rejected(self):
        for mutation in ("trial", "unit", "mouse", "probe", "fold", "prediction", "bin", "nonfinite"):
            row = copy.deepcopy(self.bundle["records"][0])
            if mutation == "trial": row["trial_ids"][0] = "unknown"
            if mutation == "unit": row["unit_ids"][0] = "unknown"
            if mutation == "mouse": row["subject"] = "other-mouse"
            if mutation == "probe": row["pids"] = ["other-probe"]
            if mutation == "fold": row["idxes_test"][0][0] = 1
            if mutation == "prediction": row["predictions"][1] = [0]
            if mutation == "bin": row["predictions"][0] = [0, 1]
            if mutation == "nonfinite": row["score"] = float("nan")
            bundle = dict(self.bundle, records=[row]+self.bundle["records"][1:])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                s.evaluate(self.roster, bundle)

    def test_fold_partition_may_not_be_changed_even_if_complete(self):
        row = copy.deepcopy(self.bundle["records"][0])
        row["idxes_test"][0], row["idxes_test"][1] = row["idxes_test"][1], row["idxes_test"][0]
        with self.assertRaises(ValueError):
            s.evaluate(self.roster, dict(self.bundle, records=[row]+self.bundle["records"][1:]))

    def test_real_targets_must_agree_across_runs(self):
        row = copy.deepcopy(self.bundle["records"][0])
        row["targets"][0] = row["predictions"][0] = [1]
        with self.assertRaises(ValueError):
            s.evaluate(self.roster, dict(self.bundle, records=[row]+self.bundle["records"][1:]))

    def test_endpoint_or_region_family_cannot_silently_shrink(self):
        roster = copy.deepcopy(self.roster)
        roster["cells"] = [r for r in roster["cells"] if r["endpoint"] != "feedback"]
        with self.assertRaises(ValueError): s.validate_roster(roster)
        roster = copy.deepcopy(self.roster)
        roster["cells"].pop()
        with self.assertRaises(ValueError): s.validate_roster(roster)

    def test_source_pins_and_roster_binding(self):
        roster = dict(self.roster, source_revision="unknown")
        with self.assertRaises(ValueError): s.evaluate(roster, self.bundle)
        bundle = dict(self.bundle, roster_digest="0"*64)
        with self.assertRaises(ValueError): s.evaluate(self.roster, bundle)

    def test_cli_pinned_inputs_and_non_overwriting_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roster, bundle, output = root/"roster.json", root/"bundle.json", root/"report.json"
            roster.write_text(json.dumps(self.roster))
            bundle.write_text(json.dumps(self.bundle))
            command = [sys.executable, "-B", str(MODULE), "--roster", str(roster),
                       "--roster-sha256", hashlib.sha256(roster.read_bytes()).hexdigest(),
                       "--bundle", str(bundle), "--bundle-sha256", hashlib.sha256(bundle.read_bytes()).hexdigest(),
                       "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(len(json.loads(output.read_text())["regions"]), 5)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            with self.assertRaises(ValueError): s.read_pinned(roster, "0"*64)


class ProbeSessionOwnership(unittest.TestCase):
    """A probe insertion belongs to one session, across its endpoint/region cells."""

    def test_same_probe_can_support_multiple_regions_and_endpoints(self):
        roster, _ = fixture()
        extra = copy.deepcopy(roster["cells"])
        for cell in extra:
            cell["region"] = "second-generated-region"
            cell["unit_ids"] = [unit + "-second-region" for unit in cell["unit_ids"]]
        roster["cells"].extend(extra)
        self.assertEqual(len(s.validate_roster(roster)), 20)

    def test_one_cross_session_probe_collision_is_rejected(self):
        roster, _ = fixture()
        roster["cells"][1]["pids"].append(roster["cells"][0]["pids"][0])
        with self.assertRaisesRegex(ValueError, "probe insertion assigned to different sessions"):
            s.validate_roster(roster)

    def test_consistent_export_cannot_hide_cross_session_probe_reassignment(self):
        roster, bundle = fixture()
        for cell in roster["cells"]:
            cell["pids"] = ["one-probe-insertion-for-two-sessions"]
        for row in bundle["records"]:
            if row["pseudo_id"] == -1:
                row["pids"] = ["one-probe-insertion-for-two-sessions"]
        bundle["roster_digest"] = s.digest(roster)
        with self.assertRaisesRegex(ValueError, "probe insertion assigned to different sessions"):
            s.evaluate(roster, bundle, include_indexed=True)


class IndexedExport(unittest.TestCase):
    """New complete-family export controls; no original data or model fits."""
    @classmethod
    def setUpClass(cls):
        cls.roster, cls.bundle = fixture()
        cls.report = s.evaluate(cls.roster, cls.bundle, include_indexed=True)
        cls.collections = cls.report["indexed_collections"]["collections"]

    def test_legacy_report_is_unchanged(self):
        legacy = s.evaluate(self.roster, self.bundle)
        self.assertEqual({k: v for k, v in self.report.items() if k != "indexed_collections"}, legacy)
        self.assertNotIn("indexed_collections", legacy)
        with self.assertRaises(ValueError):
            s.evaluate(self.roster, self.bundle, include_indexed=1)

    def test_complete_source_keyed_families_and_counts(self):
        self.assertEqual(len(self.collections), 70)
        for endpoint, (runs, nulls) in s.ENDPOINTS.items():
            for member, count in (("observed_run_score", 2*runs), ("null_run_score", 2*nulls*runs),
                                  ("null_pseudo_run_mean", 2*nulls), ("observed_session_mean", 2),
                                  ("source_figure_effect", 1)):
                c = self.collections[endpoint + "." + member]
                self.assertEqual(len(c["records"]), count)
                keys = [tuple(row[k] for k in c["record_key_fields"]) for row in c["records"]]
                self.assertEqual(len(keys), len(set(keys)))
            self.assertTrue(all(row["pseudo_id"] > 0 for row in self.collections[endpoint+".null_run_score"]["records"]))
            self.assertEqual({row["run_id"] for row in self.collections[endpoint+".observed_run_score"]["records"]},
                             set(range(1, runs+1)))

    def test_input_order_does_not_change_indexed_support_or_values(self):
        roster = dict(self.roster, cells=list(reversed(self.roster["cells"])))
        bundle = dict(self.bundle, roster_digest=s.digest(roster), records=list(reversed(self.bundle["records"])))
        self.assertEqual(s.evaluate(roster, bundle, include_indexed=True)["indexed_collections"],
                         self.report["indexed_collections"])

    def test_endpoint_specific_regions_are_not_rectangularized(self):
        roster, bundle = fixture()
        for cell in roster["cells"]:
            if cell["endpoint"] == "wheel_speed":
                cell["region"] = "wheel-only-region"
                cell["unit_ids"] = [u + "-wheel" for u in cell["unit_ids"]]
        for row in bundle["records"]:
            if row["endpoint"] == "wheel_speed":
                row["region"] = "wheel-only-region"
                if row["pseudo_id"] == -1:
                    row["unit_ids"] = [u + "-wheel" for u in row["unit_ids"]]
        bundle["roster_digest"] = s.digest(roster)
        cols = s.evaluate(roster, bundle, include_indexed=True)["indexed_collections"]["collections"]
        for endpoint in s.ENDPOINTS:
            expected = {"wheel-only-region" if endpoint == "wheel_speed" else "generated-region"}
            self.assertEqual({r["region"] for r in cols[endpoint+".null_run_score"]["records"]}, expected)

    def test_pseudo_run_means_keep_id_and_negative_r2(self):
        roster, bundle = fixture()
        for row in bundle["records"]:
            if row["endpoint"] == "wheel_speed" and row["eid"] == "generated-eid-0" and row["pseudo_id"] == 1:
                row["score"] = -3.0 if row["run_id"] == 1 else 1.0
        cols = s.evaluate(roster, bundle, include_indexed=True)["indexed_collections"]["collections"]
        records = cols["wheel_speed.null_pseudo_run_mean"]["records"]
        selected = [r for r in records if r["eid"] == "generated-eid-0" and r["pseudo_id"] == 1]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["value"], -1.0)
        untouched = [r for r in records if r["eid"] == "generated-eid-1" and r["pseudo_id"] == 1]
        self.assertEqual(untouched[0]["value"], 0.0)

    def test_recorded_observed_value_is_not_silently_replaced(self):
        roster, bundle = fixture()
        bundle["records"][0]["score"] = 1.0 - 1e-11
        cols = s.evaluate(roster, bundle, include_indexed=True)["indexed_collections"]["collections"]
        row = cols["stimulus_side.observed_run_score"]["records"][0]
        self.assertEqual(row["value"], 1.0 - 1e-11)
        self.assertEqual(row["recomputed_value"], 1.0)
        self.assertEqual(cols["stimulus_side.observed_session_mean"]["records"][0]["value"], 1.0)

    def test_summary_fields_keep_existing_values_and_boolean_type(self):
        for old in self.report["sessions"]:
            for member, field in (("observed_session_mean", "real_score"),
                                  ("source_median_including_observed", "source_median_including_observed"),
                                  ("paper_null_only_median", "paper_null_only_median"),
                                  ("paper_corrected_score", "paper_corrected_score"),
                                  ("source_session_p", "source_session_p")):
                rows = self.collections[old["endpoint"]+"."+member]["records"]
                row = next(r for r in rows if (r["eid"], r["region"]) == (old["eid"], old["region"]))
                self.assertEqual(row["value"], old[field])
        for old in self.report["regions"]:
            for member in ("source_figure_effect", "paper_text_effect", "source_fisher_p", "source_bh_q",
                           "source_fraction_significant_sessions", "source_significant"):
                row = next(r for r in self.collections[old["endpoint"]+"."+member]["records"]
                           if r["region"] == old["region"])
                self.assertEqual(row["value"], old[member])
                if member == "source_significant":
                    self.assertIs(type(row["value"]), bool)

    def test_indexed_mode_cannot_bypass_original_validation(self):
        for records in (self.bundle["records"][:-1], self.bundle["records"] + [self.bundle["records"][-1]]):
            with self.assertRaises(ValueError):
                s.evaluate(self.roster, dict(self.bundle, records=records), include_indexed=True)
        bundle = dict(self.bundle, roster_digest="0"*64)
        with self.assertRaises(ValueError):
            s.evaluate(self.roster, bundle, include_indexed=True)

    def test_units_match_declared_reproduction_members(self):
        declaration = json.loads((MODULE.parents[2] / "reproduction.v2.json").read_text())
        declared = {member["manifest_key"]: member["units"]
                    for family in declaration["findings"]
                    for member in family.get("representation", {}).get("members", [])}
        self.assertEqual(set(self.collections), set(declared))
        self.assertEqual({key: value["units"] for key, value in self.collections.items()}, declared)

    def test_no_mutation_or_authentication_claim(self):
        before = s.digest({"roster": self.roster, "bundle": self.bundle})
        report = s.evaluate(self.roster, self.bundle, include_indexed=True)
        self.assertEqual(before, s.digest({"roster": self.roster, "bundle": self.bundle}))
        self.assertFalse(report["indexed_collections"]["full_contract_complete"])
        self.assertEqual(report["indexed_collections"]["scientific_qualification"], "unknown")
        self.assertIn("not rescored or authenticated", report["indexed_collections"]["null_score_verification"])
        self.assertEqual(self.collections["choice.null_run_score"]["value_role"], "recorded_source_scalar_not_rescored")


if __name__ == "__main__":
    unittest.main()

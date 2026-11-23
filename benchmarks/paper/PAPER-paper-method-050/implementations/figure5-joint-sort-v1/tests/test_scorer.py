"""Generated joint-sort controls; no authentic spikes, fits or paper scores."""
import copy
from datetime import date, timedelta
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
SPEC = importlib.util.spec_from_file_location("joint_sort_scorer", MODULE)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def packet(n=1, dataset="A", rat="R"):
    units, assignments, references = [], [], []
    for pair in range(n):
        included = []
        for i in range(8):
            uid, session = pair * 10 + i, pair * 2 + 1 + i % 2
            units.append(dict(dataset=dataset, unit_id=uid, session_id=session, shank=0,
                              recording_date=(date(2020, 1, 1)+timedelta(days=session-1)).isoformat()))
            assignments.append(dict(dataset=dataset, unit_id=uid, track_id=pair*10+i//2+1))
            if i < 6:
                # Two reference matches, plus two mapped units that do not
                # share a reference cluster. The last two units are excluded.
                included.append(dict(unit_id=uid, joint_cluster_id=i//2 if i < 4 else i,
                                     individual_spike_count=10, coincident_individual_spike_count=6))
        references.append(dict(pair_id=f"{dataset}-{pair}", dataset=dataset,
                               left_session_id=pair*2+1, right_session_id=pair*2+2,
                               included_units=included, mapping_provenance="generated mapping",
                               complete_overlap_mapping=True, spike_time_tolerance_ms=1))
    # An unassessed session remains part of full-session tracking assignments.
    units.append(dict(dataset=dataset, unit_id=n*10, session_id=n*2+1, shank=0,
                      recording_date=(date(2020, 1, 1)+timedelta(days=n*2)).isoformat()))
    assignments.append(dict(dataset=dataset, unit_id=n*10, track_id=-1))
    return dict(schema_version="figure5-joint-sort/v1", source_kind="generated_engineering_control",
                complete_selected_session_population=True, population_provenance="generated population",
                dataset_to_rat={dataset: rat}, units=units, references=references,
                methods={name: dict(full_session_tracking=True,
                    joint_reference_excluded_from_matching_and_selection=True,
                    peth_excluded_from_matching_and_selection=True,
                    execution_provenance="generated full-session assignments",
                    assignments=copy.deepcopy(assignments)) for name in scorer.BASELINES})


class JointSortControls(unittest.TestCase):
    def test_confusion_pair_identities_and_excluded_units(self):
        fixture = packet()
        fixture["methods"]["DANT"]["assignments"][3]["track_id"] = 99
        result = scorer.score(fixture)
        row, = result["methods"]["DANT"]["pairs"]
        self.assertEqual((row["tp"], row["fp"], row["fn"]), (1, 1, 1))
        self.assertEqual(row["true_positive_matches"], [(0, 1)])
        self.assertEqual(row["false_positive_matches"], [(4, 5)])
        self.assertEqual(row["false_negative_matches"], [(2, 3)])
        self.assertEqual((row["precision_percent"], row["recall_percent"]), (50, 50))
        self.assertEqual(result["reference_panel"][0]["excluded_unit_ids"], [6, 7])
        self.assertEqual(result["population_unit_count"], 9)

    def test_equal_pair_mean_and_sample_sd_not_pooled_counts(self):
        fixture = packet(2)
        for row in fixture["methods"]["DANT"]["assignments"]:
            if row["unit_id"] in (13, 15):
                row["track_id"] = -1
        report = scorer.score(fixture)["methods"]["DANT"]
        values = [r["precision_percent"] for r in report["pairs"]]
        self.assertEqual(values, [200/3, 100])
        self.assertAlmostEqual(report["precision"]["mean_percent"], 250/3)
        self.assertAlmostEqual(report["precision"]["sample_sd_percentage_points"], 100/(3*math.sqrt(2)))
        self.assertNotEqual(report["precision"]["mean_percent"], 75)  # pooled3/4
        self.assertEqual(report["recall"]["mean_percent"], 75)

    def test_strict_overlap_boundary_and_source_tolerance(self):
        for field, value in (("coincident_individual_spike_count", 5),
                             ("coincident_individual_spike_count", 11),
                             ("individual_spike_count", 0),
                             ("individual_spike_count", True)):
            fixture = packet()
            fixture["references"][0]["included_units"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(scorer.InputError):
                scorer.score(fixture)
        fixture = packet()
        fixture["references"][0]["included_units"][0].update(
            individual_spike_count=5, coincident_individual_spike_count=3)
        self.assertEqual(scorer.score(fixture)["validation_pair_count"], 1)
        for value in (0.5, 2, True, "1"):
            fixture["references"][0]["spike_time_tolerance_ms"] = value
            with self.subTest(tolerance=value), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_many_to_one_joint_mapping_preserves_all_reference_pairs(self):
        fixture = packet()
        fixture["references"][0]["included_units"][2]["joint_cluster_id"] = 0
        result = scorer.score(fixture)
        self.assertEqual(result["reference_panel"][0]["reference_matches"], [(0, 1), (2, 1)])
        row, = result["methods"]["DANT"]["pairs"]
        self.assertEqual((row["tp"], row["fp"], row["fn"]), (1, 2, 1))

    def test_undefined_precision_blocks_summary_without_dropping_pair(self):
        fixture = packet(2)
        for row in fixture["methods"]["DANT"]["assignments"]:
            if row["unit_id"] < 10:
                row["track_id"] = -1
        report = scorer.score(fixture)["methods"]["DANT"]
        self.assertIsNone(report["pairs"][0]["precision_percent"])
        self.assertEqual(report["pairs"][0]["recall_percent"], 0)
        self.assertEqual(report["precision"]["undefined_pair_ids"], ["A-0"])
        self.assertIsNone(report["precision"]["mean_percent"])
        self.assertIsNone(report["precision"]["sample_sd_percentage_points"])
        self.assertEqual(report["recall"]["mean_percent"], 50)

    def test_undefined_recall_does_not_become_perfect_recall(self):
        fixture = packet()
        for row in fixture["references"][0]["included_units"]:
            if row["unit_id"] % 2:
                row["joint_cluster_id"] += 100
        report = scorer.score(fixture)["methods"]["DANT"]
        self.assertIsNone(report["recall"]["mean_percent"])
        self.assertEqual(report["precision"]["mean_percent"], 0)

    def test_full_population_coverage_and_track_constraints(self):
        for mutation in ("missing_unassessed", "duplicate", "unknown", "same_session", "shank"):
            fixture = packet()
            rows = fixture["methods"]["DANT"]["assignments"]
            if mutation == "missing_unassessed": rows.pop()
            elif mutation == "duplicate": rows.append(copy.deepcopy(rows[0]))
            elif mutation == "unknown": rows[0]["unit_id"] = 999
            elif mutation == "same_session": rows[2]["track_id"] = 1
            else: fixture["units"][1]["shank"] = 1
            with self.subTest(mutation=mutation), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_duplicate_unknown_or_outside_reference_mapping_rejected(self):
        for mutation in ("duplicate", "unknown", "outside", "empty_side"):
            fixture = packet()
            rows = fixture["references"][0]["included_units"]
            if mutation == "duplicate": rows.append(copy.deepcopy(rows[0]))
            elif mutation == "unknown": rows[0]["unit_id"] = 999
            elif mutation == "outside": rows[0]["unit_id"] = 10
            else: rows[:] = [r for r in rows if r["unit_id"] % 2 == 0]
            with self.subTest(mutation=mutation), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_duplicate_panel_id_or_session_pair_rejected(self):
        for same_id in (True, False):
            fixture = packet()
            row = copy.deepcopy(fixture["references"][0])
            if not same_id: row["pair_id"] = "second-name"
            fixture["references"].append(row)
            with self.subTest(same_id=same_id), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_consecutive_calendar_days_not_ordinal_session_adjacency(self):
        for day in ("2020-01-01", "2020-01-03"):
            fixture = packet()
            for row in fixture["units"]:
                if row["session_id"] == 2: row["recording_date"] = day
            with self.subTest(day=day), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_declarations_and_rat_coverage_required(self):
        for mutation in ("full_session_tracking", "joint_reference_excluded_from_matching_and_selection",
                         "peth_excluded_from_matching_and_selection", "rat", "complete_mapping"):
            fixture = packet()
            if mutation == "rat": fixture["dataset_to_rat"] = {}
            elif mutation == "complete_mapping": fixture["references"][0]["complete_overlap_mapping"] = False
            else: fixture["methods"]["DANT"][mutation] = False
            with self.subTest(mutation=mutation), self.assertRaises(scorer.InputError):
                scorer.score(fixture)

    def test_order_independence_and_candidate_cannot_change_baseline_panel(self):
        fixture = packet(2)
        expected = scorer.score(fixture)
        fixture["units"].reverse()
        fixture["references"].reverse()
        for ref in fixture["references"]: ref["included_units"].reverse()
        for method in fixture["methods"].values(): method["assignments"].reverse()
        self.assertEqual(scorer.score(fixture), expected)
        fixture["methods"]["candidate"] = copy.deepcopy(fixture["methods"]["DANT"])
        for row in fixture["methods"]["candidate"]["assignments"]: row["track_id"] = -1
        result = scorer.score(fixture)
        self.assertIsNone(result["methods"].pop("candidate")["precision"]["mean_percent"])
        self.assertEqual(result, expected)

    def test_ten_pair_five_rat_shape_is_never_source_authentication(self):
        fixture = packet(2, "D0", "R0")
        for i in range(1, 5):
            other = packet(2, f"D{i}", f"R{i}")
            for field in ("units", "references"): fixture[field].extend(other[field])
            fixture["dataset_to_rat"].update(other["dataset_to_rat"])
            for name in scorer.BASELINES:
                fixture["methods"][name]["assignments"].extend(other["methods"][name]["assignments"])
        result = scorer.score(fixture)
        self.assertEqual((result["validation_pair_count"], result["validation_rat_count"]), (10, 5))
        self.assertIn("unverified", result["qualification"])
        self.assertEqual(len(result["methods"]["DANT"]["pairs"]), 10)

    def test_cli_binds_exact_bytes_strict_json_and_no_overwrite(self):
        raw = json.dumps(packet()).encode()
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/"packet.json", Path(directory)/"result.json"
            source.write_bytes(raw)
            argv = [str(MODULE), str(source), str(target)]
            with patch.object(sys, "argv", argv): scorer.main()
            original = target.read_bytes()
            result = json.loads(original)
            self.assertEqual(result["input_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertIsNone(result["methods"]["DANT"]["precision"]["sample_sd_percentage_points"])
            with patch.object(sys, "argv", argv), self.assertRaises(FileExistsError): scorer.main()
            self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)

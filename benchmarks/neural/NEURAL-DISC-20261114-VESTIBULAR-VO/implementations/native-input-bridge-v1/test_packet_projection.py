"""Complete generated panels only; no authentic arrays, scoring or file export."""

import copy
import json
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("vestibular_projection", Path(__file__).with_name("packet_projection.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
KEY = b"generated operator-only opaque key" * 2


def generated_panel():
    """49 cells,35 relationships,3 single strata,10 conditions,all full repeats."""
    e = P.load_evaluator()
    neurons, pairs, groups, records = [], [], [], []
    conditions = list(e.CONDITIONS) + ["additional_measured_condition"]
    for animal, (count, pair_count) in P.COUNTS.items():
        ids = [f"PRIVATE-{animal}-neuron-{i}" for i in range(count)]
        neurons.extend({"id": n, "animal_id": animal} for n in ids)
        relationships = [(i, (i + 1) % count) for i in range(0, count, 2)]
        existing = {tuple(sorted(pair)) for pair in relationships}
        relationships.extend((i, j) for i in range(count) for j in range(i + 1, count)
                             if (i, j) not in existing)
        for index, (first, second) in enumerate(relationships[:pair_count]):
            pair_id = f"PRIVATE-{animal}-pair-{index}"
            members = [ids[first], ids[second]]
            pairs.append({"id": pair_id, "animal_id": animal, "neuron_ids": members,
                          "simultaneity_evidence_sha256": "a" * 64})
            groups.append({"id": pair_id + "-group", "animal_id": animal, "session_id": f"PRIVATE-{animal}-session-{index}",
                           "recording_id": f"PRIVATE-recording-{index}", "stratum": "simultaneous_pair",
                           "neuron_ids": members, "pair_id": pair_id})
        groups.append({"id": f"PRIVATE-{animal}-single-group", "animal_id": animal,
                       "session_id": f"PRIVATE-{animal}-single-session", "recording_id": "PRIVATE-single-recording",
                       "stratum": "single_neuron", "neuron_ids": ids[:1], "pair_id": None})
    for group in groups:
        for condition in conditions:
            for partition in ("train", "query"):
                identifier = f'{group["id"]}-{condition}-{partition}'
                origin = 9007199254740993 + len(records) * 100
                clock = {"id": identifier + "-PRIVATE-clock", "origin_tick": origin,
                         "seconds_numerator": 1, "seconds_denominator": 10, "tick_unit": "native-tick",
                         "target_unit": "documented-velocity-unit", "axis": "documented-rotation-axis",
                         "measurement_kind": "measured_angular_head_velocity",
                         "units_evidence_sha256": "b" * 64, "alignment_evidence_sha256": "c" * 64}
                channels = [{"neuron_id": neuron, "clock_id": clock["id"],
                             "alignment_evidence_sha256": clock["alignment_evidence_sha256"],
                             "event_times_s": [0.05, 0.2, 0.35, 0.35, 0.8],
                             "input_valid_intervals_s": [[0.0, 0.6], [0.7, 1.0]]}
                            for neuron in group["neuron_ids"]]
                records.append({"id": identifier, "group_id": group["id"], "condition": condition,
                                "repeat_id": f"PRIVATE-{partition}-repeat", "presentation_id": identifier + "-PRIVATE-presentation",
                                "partition": partition, "sample_ticks": [origin + k for k in (1, 3, 4, 7)],
                                "sample_times_s": [0.1, 0.3, 0.4, 0.7], "duration_s": 1.0,
                                "clock": clock, "channels": channels,
                                "target": [987654.321, 2.5, None, 3.75] if partition == "query" else [-1.25, -2.5, None, -3.75],
                                "valid_mask": [True, True, False, True]})
    records.append({"id": "PRIVATE-excluded-record", "group_id": groups[0]["id"], "condition": conditions[0],
                    "repeat_id": "PRIVATE-excluded-repeat", "presentation_id": "PRIVATE-excluded-presentation",
                    "partition": "excluded", "exclusion_reason": "generated acquisition failure",
                    "exclusion_evidence_sha256": "d" * 64})
    coverage = []
    for animal in P.COUNTS:
        for condition in conditions:
            for stratum in e.STRATA:
                local = [g for g in groups if g["animal_id"] == animal and g["stratum"] == stratum]
                coverage.append({"animal_id": animal, "condition": condition, "stratum": stratum,
                                 "status": "available", "group_repeats": [{"group_id": g["id"], "repeat_ids": ["PRIVATE-query-repeat"]} for g in local],
                                 "unavailable_groups": {}})
    return {"schema": "vestibular_prepared_repeats_v1", "task_id": P.TASK, "source_sha256": "1" * 64,
            "census": {"animals": list(P.COUNTS), "neurons": neurons, "pairs": pairs, "groups": groups,
                       "excluded_pairs": {}, "excluded_neurons": {}, "conditions": conditions,
                       "additional_conditions": {conditions[-1]: "generated additional authentic-condition stand-in"},
                       "coverage": coverage, "complete_source_record_ids": [row["id"] for row in records]},
            "records": records}


def admission_for(prepared):
    return {"schema": "vestibular_native_bridge_admission_v1", "kind": "generated_control",
            "source_sha256": prepared["source_sha256"], "prepared_sha256": P.canonical_sha256(prepared),
            "census_sha256": P.canonical_sha256(prepared["census"]), "role_binding_sha256": "2" * 64,
            "split_sha256": "3" * 64, "protocol_sha256": "4" * 64, "review_evidence_sha256": "5" * 64}


def project(prepared):
    admission = admission_for(prepared)
    return P.project(prepared, admission, accepted_admission_sha256=P.canonical_sha256(admission), id_key=KEY)


class ProjectionControls(unittest.TestCase):
    def setUp(self):
        self.prepared = generated_panel()

    def refused(self):
        with self.assertRaises(ValueError):
            project(self.prepared)

    def query(self):
        return self.prepared["records"][1]

    def test_complete_original_panel_and_no_prior_or_scoring(self):
        evaluator = P.load_evaluator()
        with patch.object(evaluator, "repeat_metrics", side_effect=AssertionError("no metric call")), \
             patch.object(evaluator, "validate_reference", side_effect=AssertionError("no synthetic prior")), \
             patch.object(P, "load_evaluator", return_value=evaluator):
            result = project(self.prepared)
        private, public = result["protected"], result["public"]
        self.assertEqual(len(private["census"]["neurons"]), 49)
        self.assertEqual(len(private["census"]["pairs"]), 35)
        self.assertEqual(len(private["source_records"]), 761)
        self.assertEqual(len(private["identity_map"]), 761)
        self.assertEqual(len(public["queries"]), 380)
        self.assertEqual(len(public["calibration"]), 380)
        self.assertEqual(len(private["cases"]), 380)
        self.assertFalse(private["prior_attached"])
        self.assertEqual(private["admission"]["kind"], "generated_control")
        self.assertEqual(private["census"], self.prepared["census"])
        for case in private["cases"]:
            self.assertEqual(set(case), {"id", "group_id", "condition", "repeat_id", "sample_ticks", "valid_mask", "target"})

    def test_public_whitelist_has_no_query_targets_masks_prior_or_real_ids(self):
        result = project(self.prepared)
        text = json.dumps(result["public"])
        for secret in ("PRIVATE-", "987654.321", "origin_tick", "presentation_id", "alignment_evidence_sha256", "prior", "source_sha256"):
            self.assertNotIn(secret, text)
        query = result["public"]["queries"][0]
        self.assertEqual(set(query), {"case_id", "group_id", "condition", "duration_s", "sample_ticks", "sample_times_s",
                                     "clock", "channel_ids", "event_times_s", "input_valid_intervals_s"})
        train = result["public"]["calibration"][0]
        self.assertEqual(train["calibration_velocity"], [-1.25, -2.5, None, -3.75])
        self.assertEqual(train["calibration_valid_mask"], [True, True, False, True])
        self.assertEqual(result["protected"]["cases"][0]["target"][0], 987654.321)

    def test_exact_ticks_above_float_precision_preserved_privately(self):
        result = project(self.prepared)
        private = result["protected"]["source_records"][1]
        public = result["public"]["queries"][0]
        self.assertEqual(private["sample_ticks"], self.query()["sample_ticks"])
        self.assertGreater(private["clock"]["origin_tick"], 2 ** 53)
        self.assertEqual(public["sample_ticks"], [1, 3, 4, 7])
        self.assertEqual(public["sample_times_s"], [0.1, 0.3, 0.4, 0.7])
        self.assertEqual(result["protected"]["cases"][0]["sample_ticks"], public["sample_ticks"])

    def test_record_and_channel_reorder_join_by_identity(self):
        before = project(self.prepared)
        self.prepared["records"].reverse()
        for row in self.prepared["records"]:
            if row["partition"] != "excluded":
                row["channels"].reverse()
        after = project(self.prepared)
        self.assertEqual(before["public"], after["public"])
        self.assertEqual(before["protected"]["cases"], after["protected"]["cases"])

    def test_public_channel_identity_reused_for_stable_neuron_across_pairs(self):
        result = project(self.prepared)
        n = self.prepared["census"]["neurons"][0]["id"]
        expected = result["protected"]["neuron_public_ids"][n]
        groups = {g["id"] for g in self.prepared["census"]["groups"] if n in g["neuron_ids"] and g["stratum"] == "simultaneous_pair"}
        group_map = {row["group_id"]: row["public_group_id"] for row in result["protected"]["identity_map"]}
        found = [q for q in result["public"]["queries"] if q["group_id"] in {group_map[g] for g in groups}]
        self.assertGreater(len(groups), 1)
        self.assertTrue(all(expected in q["channel_ids"] for q in found))
        self.assertEqual(len(result["protected"]["neuron_public_ids"]), 49)

    def test_changed_preparation_requires_matching_external_admission(self):
        admission = admission_for(self.prepared)
        accepted = P.canonical_sha256(admission)
        self.query()["target"][0] += 1
        with self.assertRaises(ValueError):
            P.project(self.prepared, admission, accepted_admission_sha256=accepted, id_key=KEY)
        admission = admission_for(self.prepared)
        with self.assertRaises(ValueError):
            P.project(self.prepared, admission, accepted_admission_sha256=accepted, id_key=KEY)

    def test_self_certified_baseline_flag_is_not_an_admission(self):
        self.prepared["baseline_qualified"] = True
        self.refused()

    def test_missing_or_duplicate_complete_record_refused(self):
        original = copy.deepcopy(self.prepared)
        self.prepared["records"].pop(1)
        self.refused()
        self.prepared = original
        self.prepared["records"].append(copy.deepcopy(self.query()))
        self.refused()

    def test_missing_original_neuron_or_pair_census_refused(self):
        original = copy.deepcopy(self.prepared)
        self.prepared["census"]["neurons"].pop()
        self.refused()
        self.prepared = original
        self.prepared["census"]["pairs"].pop()
        self.refused()

    def test_duplicate_pair_relationship_does_not_inflate_census(self):
        first, second = self.prepared["census"]["pairs"][:2]
        second["neuron_ids"] = first["neuron_ids"][:]
        self.refused()

    def test_cross_partition_source_presentation_refused(self):
        train, query = self.prepared["records"][:2]
        query["presentation_id"] = train["presentation_id"]
        self.refused()

    def test_excluded_alias_cannot_hide_cross_partition_presentation(self):
        self.prepared["records"][-1]["presentation_id"] = self.query()["presentation_id"]
        self.refused()

    def test_repeat_alias_cannot_be_relabelled_as_new_complete_record(self):
        train, query = self.prepared["records"][:2]
        query["repeat_id"] = train["repeat_id"]
        self.refused()

    def test_acquired_presentation_cannot_be_counted_twice_under_new_repeat_ids(self):
        duplicate = copy.deepcopy(self.query())
        duplicate["id"] = "PRIVATE-new-record-same-acquired-presentation"
        duplicate["repeat_id"] = "PRIVATE-new-repeat-same-acquired-presentation"
        self.prepared["records"].append(duplicate)
        self.prepared["census"]["complete_source_record_ids"].append(duplicate["id"])
        cell = self.prepared["census"]["coverage"][0]
        member = next(row for row in cell["group_repeats"] if row["group_id"] == duplicate["group_id"])
        member["repeat_ids"].append(duplicate["repeat_id"])
        # Source order, coverage and regenerated admission all agree; the defect
        # was counting the identical acquired presentation as another repeat.
        with self.assertRaisesRegex(ValueError, "duplicate active acquired presentation within group"):
            project(self.prepared)

    def test_query_requires_separate_group_condition_calibration(self):
        self.prepared["records"][0]["partition"] = "query"
        self.refused()

    def test_missing_channel_and_noncommon_clock_refused(self):
        original = copy.deepcopy(self.prepared)
        self.query()["channels"].pop()
        self.refused()
        self.prepared = copy.deepcopy(original)
        self.query()["channels"][0]["clock_id"] = "PRIVATE-different-acquisition"
        self.refused()
        self.prepared = original
        self.query()["channels"][0]["alignment_evidence_sha256"] = "f" * 64
        self.refused()

    def test_exact_documented_clock_and_measurement_required(self):
        original = copy.deepcopy(self.prepared)
        for mutate in (
            lambda q: q["sample_ticks"].__setitem__(0, float(q["sample_ticks"][0])),
            lambda q: q["sample_times_s"].__setitem__(0, 0.100001),
            lambda q: q["clock"].__setitem__("seconds_denominator", 1000),
            lambda q: q["clock"].__setitem__("measurement_kind", "commanded_velocity"),
        ):
            self.prepared = copy.deepcopy(original)
            mutate(self.query())
            self.refused()

    def test_no_silent_target_or_event_truncation(self):
        original = copy.deepcopy(self.prepared)
        self.query()["target"].pop()
        self.refused()
        self.prepared = copy.deepcopy(original)
        self.query()["duration_s"] = 0.7
        self.refused()
        self.prepared = original
        self.query()["channels"][0]["event_times_s"].append(1.0)
        self.refused()

    def test_missing_held_coverage_or_extra_condition_reason_refused(self):
        original = copy.deepcopy(self.prepared)
        self.prepared["census"]["coverage"][0]["group_repeats"].pop()
        self.refused()
        self.prepared = original
        self.prepared["census"]["additional_conditions"] = {}
        self.refused()

    def shared_pair_presentations(self):
        first, second = [self.prepared["census"]["groups"][index] for index in (0, 5)]
        second["session_id"], second["recording_id"] = first["session_id"], first["recording_id"]
        lookup = {(r["condition"], r["partition"]): r for r in self.prepared["records"]
                  if r["group_id"] == first["id"] and r["partition"] != "excluded"}
        selected = []
        for row in self.prepared["records"]:
            if row["group_id"] != second["id"]:
                continue
            original = lookup[(row["condition"], row["partition"])]
            for key in ("presentation_id", "sample_ticks", "sample_times_s", "duration_s", "clock", "target"):
                row[key] = copy.deepcopy(original[key])
            for channel in row["channels"]:
                channel["clock_id"] = row["clock"]["id"]
            selected.append(row)
        return first["neuron_ids"][0], selected

    def test_genuine_overlapping_pair_views_keep_one_stable_neuron(self):
        neuron, selected = self.shared_pair_presentations()
        result = project(self.prepared)
        self.assertEqual(len(result["protected"]["census"]["pairs"]), 35)
        self.assertEqual(len(result["protected"]["neuron_public_ids"]), 49)
        self.assertTrue(all(any(c["neuron_id"] == neuron for c in row["channels"]) for row in selected))

    def test_conflicting_shared_neuron_view_refused(self):
        neuron, selected = self.shared_pair_presentations()
        channel = next(c for c in selected[0]["channels"] if c["neuron_id"] == neuron)
        channel["event_times_s"].append(0.9)
        self.refused()

    def test_unavailable_group_retains_full_source_record_and_explicit_reason(self):
        query = self.query()
        replacement = {key: query[key] for key in ("id", "group_id", "condition", "repeat_id", "presentation_id")}
        replacement.update(partition="excluded", exclusion_reason="generated missing acquired target",
                           exclusion_evidence_sha256="d" * 64)
        self.prepared["records"][1] = replacement
        cell = self.prepared["census"]["coverage"][0]
        cell["group_repeats"] = [r for r in cell["group_repeats"] if r["group_id"] != query["group_id"]]
        cell["unavailable_groups"][query["group_id"]] = "generated missing acquired target"
        result = project(self.prepared)
        self.assertEqual(len(result["protected"]["source_records"]), 761)
        self.assertEqual(len(result["public"]["queries"]), 379)
        self.assertEqual(result["protected"]["census"]["coverage"][0]["unavailable_groups"], cell["unavailable_groups"])

    def test_complete_tiles_include_masked_coordinates_without_disclosing_mask(self):
        result = project(self.prepared)
        total = 0
        for query in result["public"]["queries"]:
            tiles = P.tile_query(query, 1, 0.15, 0.1)
            self.assertEqual([tile["core_start"] for tile in tiles], [0, 1, 2, 3])
            self.assertEqual([tile["sample_ticks"][0] for tile in tiles], query["sample_ticks"])
            self.assertEqual(len(tiles), len(query["sample_ticks"]))
            for tile in tiles:
                self.assertNotIn("valid_mask", tile)
                self.assertNotIn("target", tile)
                self.assertNotIn("PRIVATE-", json.dumps(tile))
                self.assertEqual(tile["core_end"], tile["core_start"] + 1)
            total += len(tiles)
        self.assertEqual(total, 1520)

    def test_tile_support_half_open_and_clipped_inside_repeat(self):
        query = project(self.prepared)["public"]["queries"][0]
        query["event_times_s"] = [[0.0, 0.1, 0.2, 0.3, 0.4, 0.7, 0.9] for _ in query["channel_ids"]]
        tiles = P.tile_query(query, 1, 0.1, 0.1)
        self.assertEqual(tiles[0]["history_start_s"], 0)
        self.assertEqual(tiles[0]["event_times_s"][0], [0.0, 0.1])
        self.assertEqual(tiles[0]["input_valid_intervals_s"][0], [[0.0, 0.2]])
        self.assertEqual(tiles[2]["event_times_s"][0], [0.4])
        for tile in tiles:
            low, high = tile["history_start_s"], tile["extent_end_s"]
            self.assertTrue(all(low <= x < high for ch in tile["event_times_s"] for x in ch))
            self.assertTrue(all(low <= a < b <= high for ch in tile["input_valid_intervals_s"] for a, b in ch))
        with self.assertRaises(ValueError):
            P.tile_query(query, 2, 0.1, 0.1)

    def test_training_or_target_bearing_object_is_not_a_query_tile(self):
        result = project(self.prepared)
        with self.assertRaises(ValueError):
            P.tile_query(result["public"]["calibration"][0], 1, 0.1, 0.1)
        query = result["public"]["queries"][0]
        query["target"] = [0.0] * 4
        with self.assertRaises(ValueError):
            P.tile_query(query, 1, 0.1, 0.1)

    def test_private_metadata_nested_in_public_clock_is_refused(self):
        original = project(self.prepared)["public"]["queries"][0]
        for key, value in (("target", [987654.321] * 4), ("real_neuron_id", "PRIVATE-D-neuron-0")):
            query = copy.deepcopy(original)
            query["clock"][key] = value
            with self.subTest(private_clock_field=key):
                with self.assertRaisesRegex(ValueError, "exact public clock fields required"):
                    P.tile_query(query, 1, 0.1, 0.1)

    def test_projection_owns_copies_and_does_not_mutate_source(self):
        source = copy.deepcopy(self.prepared)
        result = project(self.prepared)
        self.assertEqual(self.prepared, source)
        result["public"]["queries"][0]["event_times_s"][0].append(0.999)
        result["protected"]["cases"][0]["target"][0] = 0
        self.assertEqual(self.prepared, source)

    def test_past_history_shift_keeps_pairs_and_common_seam_mask(self):
        events = [[0.5, 2.0, 7.5], [1.0, 3.0, 8.0]]
        valid = [[[0.0, 10.0]], [[0.0, 10.0]]]
        shifted, intervals, mask = P.paired_shift(events, valid, 10.0, 3.0, 1.0, [0, 1, 2, 3, 4, 5, 8, 9])
        self.assertEqual(shifted, [[0.5, 3.5, 5.0], [1.0, 4.0, 6.0]])
        self.assertEqual(intervals, [[[0, 3.0], [3.0, 10.0]], [[0, 3.0], [3.0, 10.0]]])
        self.assertEqual(mask, [False, False, False, False, False, True, True, False])
        self.assertEqual(events, [[0.5, 2.0, 7.5], [1.0, 3.0, 8.0]])
        with self.assertRaises(ValueError):
            P.paired_shift(events, valid, 10.0, 3.0, 3.0, [5])

    def test_shift_respects_original_and_shifted_input_gaps(self):
        events = [[0.5], [0.5]]
        intervals = [[[0.0, 5.0], [7.0, 10.0]], [[0.0, 10.0]]]
        _, _, mask = P.paired_shift(events, intervals, 10.0, 3.0, 0.5, [1.5, 5, 7.5, 8.5])
        self.assertEqual(mask, [True, True, True, False])


if __name__ == "__main__":
    unittest.main()

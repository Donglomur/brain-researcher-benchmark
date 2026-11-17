"""Bounded generated NEURAL047 clock controls; no native data or model runs."""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-047/implementations/neural-047/full-conditional-programme-v3"
CLOSURE = ROOT / "benchmarks/integrity/current-closures/numeric-neural047/SOURCE.json"


def load_program():
    """Load the stdlib-only package under a task-specific test namespace."""
    name = "_neural047_clock_controls"
    spec = importlib.util.spec_from_file_location(name, PACKAGE / "program/__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return tuple(importlib.import_module(name + suffix) for suffix in
                 (".legacy.history", ".legacy.features", ".legacy.prepare", ".packets"))


def ratio(value):
    return (value, 1) if type(value) is int else value.as_integer_ratio()


def elapsed_at_least(value, origin, bound):
    """Independent linear-oracle predicate using integer cross multiplication."""
    vn, vd = ratio(value)
    on, od = ratio(origin)
    bn, bd = ratio(bound)
    return (vn * od - on * vd) * bd >= bn * vd * od


def elapsed_float(value, origin):
    vn, vd = ratio(value)
    on, od = ratio(origin)
    return (vn * od - on * vd) / (vd * od)


def record(times, episodes, name="generated"):
    n = len(times)
    state = [0] * n
    for start, end in episodes:
        state[start:end + 1] = [1] * (end - start + 1)
    return {
        "recording_id": name, "split_group": name, "split_unit": "animal",
        "source_pin": {"bytes": 236931813,
                       "sha256": "4fcf5906d95d144ed1d6741cc86f4ef4fd332dec0f52e00ee5f34e8b75fe6d45"},
        "evidence": {"time_mapping": "generated control; no native qualification",
                     "dv_orientation": "dorsal_positive: generated control",
                     "saav_identity": "SAAV: generated control",
                     "group_identity": "generated animal",
                     "processed_signal_support": "generated only"},
        "time_seconds": times, "native_frame0": list(range(n)),
        "velocity": [i / 32 for i in range(n)], "dv": [0.25] * n,
        "saav": [i / 64 for i in range(n)], "reversal_state": state,
        "events": [{"event_id": "event_%d" % i, "onset_index0": start,
                    "end_index0": end} for i, (start, end) in enumerate(episodes)],
    }


def lower_boundary_record():
    times = [494.0, 495.0, math.nextafter(495.2, -math.inf), 495.2,
             math.nextafter(495.2, math.inf), 496.0, 497.0, 498.0,
             499.0, 500.0, 501.0, 502.0, 503.0]
    return record(times, [(6, 9)])


def panel_records():
    records = []
    for name in ("generated_a", "generated_b", "generated_c"):
        row = record(list(range(30)), [(5, 9), (18, 22)], name)
        row["dv"][23:25] = [-0.25, -0.25]
        records.append(row)
    return records


def normalized(records):
    return {"schema": "neural047-normalized-native-v1", "source_pin": records[0]["source_pin"],
            "complete_WT_recording_roster": [r["recording_id"] for r in records],
            "excluded_recordings": [], "records": records,
            "mapping_status": "generated controls; no native qualification"}


class ClockArithmetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history, cls.features, cls.prepare, cls.packets = load_program()

    def one_case(self, row):
        cases, exclusions = self.history.extract(row)
        self.assertEqual(exclusions, [])
        self.assertEqual(len(cases), 1)
        case = cases[0]
        times = row["time_seconds"]
        origin = times[case["landmark_index0"]]
        onset = times[row["events"][0]["onset_index0"]]
        expected_landmark = next(i for i, t in enumerate(times)
                                 if elapsed_at_least(t, onset, 2.4))
        self.assertEqual(case["landmark_index0"], expected_landmark)
        expected = [i for i in range(expected_landmark + 1)
                    if elapsed_at_least(times[i], origin, -4.8)]
        self.assertEqual(case["source_indices0"], expected)
        for arm in ("N", "B", "NB"):
            view = case["views"][arm]
            self.assertEqual(view["time_offset_seconds"],
                             [elapsed_float(times[i], origin) for i in expected])
            self.assertEqual(self.history.summaries(view, arm), self.features.summaries(view, arm))
        return case

    def exclusion(self, row, reason):
        self.assertEqual(self.history.extract(row),
                         ([], [{"event_id": "event_0", "reason": reason}]))

    def test_lower_boundary_and_adjacent_represented_values(self):
        case = self.one_case(lower_boundary_record())
        self.assertEqual(case["source_indices0"], list(range(4, 10)))
        self.assertGreater(case["views"]["N"]["time_offset_seconds"][0], -4.8)

    def test_exact_endpoints_are_inclusive(self):
        row = record([-4.8, -2.4, 0.0, 1.0, 2.4, 3.0, 4.0], [(2, 4)])
        case = self.one_case(row)
        self.assertEqual(case["landmark_index0"], 4)
        self.assertEqual(case["source_indices0"], [1, 2, 3, 4])
        self.assertEqual(case["views"]["N"]["time_offset_seconds"][0], -4.8)

    def test_relative_float_rounding_does_not_expand_membership(self):
        row = record([-1.0, -(2 ** -54), 0.0, 1.0, 2.4, 4.8, 5.0, 6.0], [(4, 5)])
        self.assertEqual(row["time_seconds"][1] - 4.8, -4.8)
        self.assertEqual(self.one_case(row)["source_indices0"], [2, 3, 4, 5])

    def test_recording_coverage_uses_exact_boundary(self):
        # 495.2 is just earlier than the true bound; its successor is too late.
        row = record([495.2, 496.0, 497.0, 498.0, 499.0, 500.0, 501.0, 502.0], [(2, 5)])
        self.assertEqual(self.one_case(row)["source_indices0"], [1, 2, 3, 4, 5])
        row["time_seconds"][0] = math.nextafter(495.2, math.inf)
        self.exclusion(row, "incomplete_pre_landmark_recording")
        # Rounded absolute subtraction gives 95.2, which is too late.
        row = record([95.2, 96.0, 97.0, 98.0, 99.0, 100.0, 101.0, 102.0], [(2, 5)])
        self.exclusion(row, "incomplete_pre_landmark_recording")

    def test_ordinary_landmark_waits_for_minimum_elapsed_time(self):
        row = record([494.0, 495.5, 497.6, 499.8, 500.0, 500.2, 501.0, 502.0, 503.0], [(2, 6)])
        self.assertEqual(self.one_case(row)["landmark_index0"], 5)
        row["events"][0]["end_index0"] = 4
        row["reversal_state"][5:7] = [0, 0]
        self.exclusion(row, "not_observed_reversing_at_landmark")

    def test_coarse_clock_excludes_five_second_history_and_two_second_landmark(self):
        origin = 2 ** 52
        row = record([float(origin + i) for i in range(16)], [(6, 10)])
        case = self.one_case(row)
        self.assertEqual(case["landmark_index0"], 9)
        self.assertEqual(case["source_indices0"], [5, 6, 7, 8, 9])
        self.assertEqual(case["views"]["N"]["time_offset_seconds"], [-4, -3, -2, -1, 0])

    def test_mixed_integer_float_difference_is_rounded_only_once(self):
        origin = 2 ** 53
        times = [origin + i for i in range(8)] + [float(origin + 8), origin + 9, origin + 10]
        row = record(times, [(5, 8)])
        case = self.one_case(row)
        self.assertEqual(case["views"]["N"]["time_offset_seconds"], [-4, -3, -2, -1, 0])
        self.assertEqual(times[7] - times[8], 0.0)  # historical mixed coercion

    def test_generated_integer_and_fractional_clock_families(self):
        for origin in (-1024, 0, 500, 2 ** 20, 2 ** 45, 2 ** 52):
            for step in (0.25, 0.5, 1.0):
                times = sorted(set(origin + i * step for i in range(65)))
                if len(times) < 16:
                    continue
                row = record(times, [(len(times) // 3, len(times) - 4)])
                with self.subTest(origin=origin, step=step):
                    self.one_case(row)

    def test_missing_channel_at_excluded_lower_sample_is_not_used(self):
        row = lower_boundary_record()
        for channel in ("velocity", "dv", "saav"):
            row[channel][3] = None
        self.one_case(row)
        for channel in ("velocity", "dv", "saav"):
            missing = copy.deepcopy(row)
            missing[channel][4] = None
            self.exclusion(missing, "missing_behavior_or_neural_history")

    def test_native_gap_at_lower_boundary_still_rejects(self):
        row = lower_boundary_record()
        row["native_frame0"] = [i + (i >= 4) for i in range(len(row["time_seconds"]))]
        self.exclusion(row, "missing_native_history_frames")

    def test_existing_endpoint_exclusions_and_sign_are_preserved(self):
        base = lower_boundary_record()
        for values, expected in (([1, 1], 1), ([-1, -1], 0)):
            row = copy.deepcopy(base)
            row["dv"][10:12] = values
            self.assertEqual(self.one_case(row)["label"], expected)
        for values, reason in (([None, 1], "missing_post_reversal_orientation"),
                               ([1, -1], "zero_direction_endpoint")):
            row = copy.deepcopy(base)
            row["dv"][10:12] = values
            self.exclusion(row, reason)
        row = copy.deepcopy(base)
        row["native_frame0"] = [i + (i >= 11) for i in range(len(row["time_seconds"]))]
        self.exclusion(row, "censored_post_reversal_endpoint")

    def test_outside_landmark_and_short_reversal_remain_exclusions(self):
        self.exclusion(record([0.0, 0.5, 1.0], [(0, 2)]), "landmark_outside_recording")
        self.exclusion(record(list(range(15)), [(5, 6)]), "not_observed_reversing_at_landmark")

    def test_complete_maximal_event_roster_is_still_required(self):
        row = panel_records()[0]
        row["events"].pop()
        with self.assertRaisesRegex(ValueError, "Complete maximal observed reversal roster"):
            self.history.extract(row)

    def test_unrepresentable_offsets_abort_extraction_and_whole_panel(self):
        row = record([0.0, math.ulp(0.0), 1.0, 2.4, 4.8, 5.0, 6.0], [(3, 4)], "collision")
        with self.assertRaisesRegex(ValueError, "representable strictly ordered offsets"):
            self.history.extract(row)
        records = panel_records()
        records[1] = row
        with self.assertRaisesRegex(ValueError, "representable strictly ordered offsets"):
            self.packets.construct(normalized(records), bytes(range(32)))

    def test_both_existing_feature_validators_remain_strict(self):
        for times in ([-5.0, 0.0], [-4.8, -4.8, 0.0], [-1.0, 0.25], [-1.0, -0.5]):
            view = {"time_offset_seconds": times, "saav_history": [1.0] * len(times)}
            for module in (self.history, self.features):
                with self.assertRaisesRegex(ValueError, "Past-only strictly ordered physical histories"):
                    module.summaries(view, "N")

    def test_complete_generated_panel_keeps_all_animals_events_and_views(self):
        prepared = self.packets.construct(normalized(panel_records()), bytes(range(32)))
        self.assertEqual(len(prepared["panel"]["folds"]), 3)
        self.assertEqual(len(prepared["folds"]), 9)
        self.assertEqual(len(prepared["targets"]["targets"]), 6)
        self.assertEqual(len(prepared["audit"]["lineage"]), 6)
        for row in prepared["audit"]["exclusions"]:
            self.assertEqual((row["source_events"], row["eligible_events"], row["excluded"]), (2, 2, []))
        jobs = self.packets.compile_jobs(prepared)
        self.assertEqual(jobs["job_count"], 45)
        self.assertFalse(jobs["scientific_ready"])
        self.assertFalse(prepared["audit"]["external_clock_and_identity_mapping_certified_by_this_script"])
        self.assertEqual(prepared["audit"]["scientific_fits"], 0)
        self.assertEqual(prepared["audit"]["metric_calls"], 0)

    def test_new_boundary_exclusion_cannot_silently_drop_an_animal(self):
        records = panel_records()
        records[1] = record([494.0, 495.5, 497.6, 499.8, 500.0, 500.2, 501.0, 502.0],
                            [(2, 4)], "generated_b")
        audit, panel, folds, targets = self.prepare.build(normalized(records), bytes(range(32)))
        self.assertEqual(audit["empty_groups"], ["generated_b"])
        self.assertEqual((panel, folds, targets), (None, None, None))
        with self.assertRaisesRegex(ValueError, "Complete source support insufficient"):
            self.packets.construct(normalized(records), bytes(range(32)))


class CurrentSourceBinding(unittest.TestCase):
    def test_current_source_and_predecessor_are_explicitly_distinct(self):
        descriptor = json.loads(CLOSURE.read_text())
        for item in descriptor["current_files"] + descriptor["preserved_files"]:
            body = (ROOT / item["path"]).read_bytes()
            self.assertEqual(len(body), item["bytes"], item["path"])
            self.assertEqual(hashlib.sha256(body).hexdigest(), item["sha256"], item["path"])
        manifest = json.loads((PACKAGE / "RUNTIME_SOURCE_MANIFEST.json").read_text())
        changed = []
        for item in manifest["files"]:
            body = (PACKAGE / item["path"]).read_bytes()
            if {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()} != {
                    key: item[key] for key in ("bytes", "sha256")}:
                changed.append(item["path"])
        self.assertEqual(changed, ["program/legacy/history.py"])
        old_history = next(item for item in manifest["files"] if item["path"] == changed[0])
        self.assertEqual(descriptor["predecessor_history"], old_history)
        self.assertFalse(descriptor["native_manifest_selection"])
        self.assertFalse(descriptor["scientific_qualification"])
        self.assertFalse(descriptor["historical_qualification_transferred"])


class RuntimeSourceIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_program()
        cls.common, cls.deployment, cls.runner = tuple(
            importlib.import_module("_neural047_clock_controls." + name)
            for name in ("common", "deployment", "runner"))
        cls.current_path = PACKAGE / "CURRENT_RUNTIME_SOURCE_MANIFEST.json"
        cls.current = json.loads(cls.current_path.read_text())
        cls.historical = json.loads((PACKAGE / "RUNTIME_SOURCE_MANIFEST.json").read_text())

    def ledger(self):
        return self.common.Ledger({"wall_seconds": 30, "read_bytes": 2000000,
                                   "write_bytes": 2000000, "provider_requests": 1,
                                   "input_tokens": 1, "output_tokens": 1})

    def test_complete_current_identity_passes_both_existing_source_guards(self):
        self.assertEqual(self.current["schema"], "neural047-source-freeze-v1")
        self.assertEqual(len(self.current["files"]), 27)
        self.assertEqual([r["path"] for r in self.current["files"]],
                         [r["path"] for r in self.historical["files"]])
        self.assertEqual([new["path"] for new, old in zip(self.current["files"], self.historical["files"])
                          if new != old], ["program/legacy/history.py"])
        self.deployment.code_snapshot(PACKAGE, self.current, self.ledger())
        with tempfile.TemporaryDirectory(prefix="neural047-current-source-") as temporary:
            ledger = self.ledger()
            selected = self.common.read_json(self.current_path,
                                            self.common.pin(self.current_path.read_bytes()),
                                            ledger, "generated selected manifest control")
            destination = Path(temporary).resolve() / "snapshot"
            try:
                result = self.runner.snapshot(PACKAGE, selected, destination, ledger)
                self.assertEqual({p.relative_to(result).as_posix() for p in result.rglob("*") if p.is_file()},
                                 {r["path"] for r in self.current["files"]})
                self.deployment.code_snapshot(result, selected, self.ledger())
                self.assertEqual(ledger.observed["write_bytes"], sum(r["bytes"] for r in selected["files"]))
                self.assertEqual(ledger.observed["provider_requests"], 0)
            finally:
                if destination.exists():
                    destination.chmod(0o700)
                    for path in destination.rglob("*"):
                        if path.is_dir():
                            path.chmod(0o700)

    def test_historical_manifest_refuses_corrected_source(self):
        with self.assertRaisesRegex(ValueError, "Exact single-link regular file|Exact full file identity"):
            self.deployment.code_snapshot(PACKAGE, self.historical, self.ledger())
        with tempfile.TemporaryDirectory(prefix="neural047-old-source-") as temporary:
            with self.assertRaisesRegex(ValueError, "Exact single-link regular file|Exact full file identity"):
                self.runner.snapshot(PACKAGE, self.historical, Path(temporary).resolve() / "snapshot", self.ledger())

    def test_changed_source_bytes_cannot_retain_current_identity(self):
        with tempfile.TemporaryDirectory(prefix="neural047-mutated-source-") as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            for row in self.current["files"]:
                target = source / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                body = (PACKAGE / row["path"]).read_bytes()
                if row["path"] == "program/legacy/history.py":
                    body = b"!" + body[1:]
                target.write_bytes(body)
            with self.assertRaisesRegex(ValueError, "Exact full file identity"):
                self.deployment.code_snapshot(source, self.current, self.ledger())
            with self.assertRaisesRegex(ValueError, "Exact full file identity"):
                self.runner.snapshot(source, self.current, root / "snapshot", self.ledger())

    def test_changed_manifest_bytes_cannot_retain_selected_manifest_pin(self):
        with tempfile.TemporaryDirectory(prefix="neural047-mutated-manifest-") as temporary:
            path = Path(temporary).resolve() / "manifest.json"
            body = self.current_path.read_bytes()
            path.write_bytes(body.replace(b"history.py", b"historx.py"))
            with self.assertRaisesRegex(ValueError, "Exact full file identity"):
                self.common.read_json(path, self.common.pin(body), self.ledger(), "generated altered manifest")


if __name__ == "__main__":
    unittest.main()

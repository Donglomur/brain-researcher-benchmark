"""Generated software counterexamples only; no native source data or targets."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import complete_roster as e


def fixture():
    families = ["drifting_gratings", "drifting_gratings", "natural_scenes",
                "natural_scenes", "natural_movie_one", "natural_movie_one",
                "invalid_presentation", "drifting_gratings"]
    starts = [0, 10, 20, 30, 40, 50, 60, 51.05]
    presentations = [{"presentation_id": "p" + str(i), "stimulus_name": family,
                      "stimulus_condition_id": None if i == 6 else "c" + str(i),
                      "start_time": start, "stop_time": start + 1, "stimulus": {}}
                     for i, (family, start) in enumerate(zip(families, starts))]
    session = {"session_id": "s", "mouse_id": "m", "session_type": "brain_observatory_1.1",
               "source_file_sha256": "a" * 64, "source_file_bytes": 123,
               "units": [{"unit_id": uid, "probe_id": uid,
                          "spike_times": sorted(t + delta for t in starts for delta in (0.25, 0.75))}
                         for uid in ("u1", "u2")],
               "presentations": presentations,
               "invalid_intervals": [{"start_time": 30, "stop_time": 31, "scope": "u1"}],
               "running_samples": [], "pupil_samples": []}
    protocol = {"schema_version": 1, "contract_sha256": e.v1.CONTRACT_SHA256,
                "sdk_commit": e.v1.SDK_PIN, "session_type": "brain_observatory_1.1",
                "heldout_families": ["natural_scenes", "natural_movie_one"],
                "temporal_guard_seconds": 0.1, "pupil_max_age_seconds": 1,
                "state_history_seconds": 1, "state_prior_seconds": 1,
                "quality_selection_policy": "generated software control; no authentic recording",
                "sessions": [{"session_id": "s", "mouse_id": "m", "unit_ids": ["u1", "u2"],
                              "source_file_sha256": "a" * 64, "source_file_bytes": 123,
                              "presentation_ids": [p["presentation_id"] for p in presentations],
                              "presentation_table_sha256": e.v1.digest(presentations)}]}
    return e.v1.prepare({"source": e.v1.SOURCE, "sessions": [session]}, protocol)


def rebind(public, private):
    private["public_sha256"] = e.v1.digest(public)
    keys = {tuple(row["key"]) for row in public["query"]}
    private["targets"] = [row for row in private["targets"] if tuple(row["key"]) in keys]


class RosterControls(unittest.TestCase):
    def test_complete_preparation_preserves_original_metric_and_audits_exclusions(self):
        public, private = fixture()
        predictions = e.v1.fit_controls(public)["mean_rate"]
        original = e.v1.score(public, private, predictions)
        result = e.score(public, private, predictions)
        coverage = result.pop("declared_roster_coverage")
        self.assertEqual(result, original)
        self.assertEqual(coverage, {"declared_observations": 16, "training_observations": 4,
                                   "query_observations": 7, "excluded_observations": 5,
                                   "selected_units": 2, "selected_sessions": 1})
        self.assertEqual({row["reason"] for row in private["exclusions"]},
                         {"invalid_stimulus", "temporal_guard", "zero_valid_exposure"})

    def test_old_scorer_accepts_missing_query_repeat_new_scorer_rejects_it(self):
        public, private = fixture()
        public["query"] = [r for r in public["query"] if r["key"] != ["s", "u2", "p3"]]
        rebind(public, private)
        predictions = e.v1.fit_controls(public)["mean_rate"]
        self.assertEqual(e.v1.score(public, private, predictions)["overall"]["status"], "finite")
        with self.assertRaisesRegex(ValueError, "unaccounted"):
            e.score(public, private, predictions)

    def test_missing_training_repeat_or_whole_unit_rejected(self):
        for unit in (False, True):
            public, private = fixture()
            for split in ("training", "query"):
                public[split] = [r for r in public[split]
                                 if not (r["key"][1] == "u2" if unit else
                                         split == "training" and r["key"][2] == "p1")]
            rebind(public, private)
            with self.assertRaises(ValueError):
                e.validate_packet(public, private)

    def test_missing_whole_presentation_exclusion_rejected(self):
        public, private = fixture()
        private["exclusions"] = [r for r in private["exclusions"] if r["reason"] != "invalid_stimulus"]
        with self.assertRaisesRegex(ValueError, "unaccounted"):
            e.validate_packet(public, private)

    def test_unit_requires_every_held_family_even_with_accounted_exclusions(self):
        public, private = fixture()
        removed = [r for r in public["query"] if r["key"][1] == "u1" and r["family"] == "natural_movie_one"]
        public["query"] = [r for r in public["query"] if r not in removed]
        private["exclusions"] += [{"key": r["key"], "reason": "zero_valid_exposure"} for r in removed]
        rebind(public, private)
        with self.assertRaisesRegex(ValueError, "every heldout family"):
            e.validate_packet(public, private)

    def test_presentation_metadata_is_shared_but_exposure_and_counts_are_unit_specific(self):
        for field, value in (("family", "natural_movie_one"), ("condition_id", "other"),
                             ("start_time", 19.5), ("stimulus", {"frame": 9}),
                             ("running_speed", 2)):
            public, private = fixture()
            row = public["query"][0]
            row[field] = value
            if field == "running_speed":
                row["running_coverage"] = 1
            rebind(public, private)
            with self.assertRaises(ValueError):
                e.validate_packet(public, private)
        public, private = fixture()
        public["query"][0]["exposure_seconds"] = 0.5
        private["targets"][0]["count"] = 0
        rebind(public, private)
        e.validate_packet(public, private)

    def test_condition_cannot_cross_families_within_same_split(self):
        public, private = fixture()
        for row in public["query"]:
            row["condition_id"] = "same-condition"
        rebind(public, private)
        with self.assertRaisesRegex(ValueError, "condition identity"):
            e.validate_packet(public, private)

    def test_unexpected_public_top_level_target_field_rejected(self):
        public, private = fixture()
        public["targets"] = copy.deepcopy(private["targets"])
        rebind(public, private)
        with self.assertRaisesRegex(ValueError, "unexpected public"):
            e.validate_packet(public, private)

    def test_roster_mouse_and_membership_are_binding(self):
        for mutation in ("mouse", "presentation", "unit", "session"):
            public, private = fixture()
            selected = private["source_roster"][0]
            if mutation == "mouse":
                selected["mouse_id"] = "wrong"
            elif mutation == "presentation":
                selected["presentation_ids"].remove("p2")
            elif mutation == "unit":
                selected["unit_ids"].append("missing-unit")
            else:
                extra = copy.deepcopy(selected)
                extra["session_id"] = "missing-session"
                private["source_roster"].append(extra)
            with self.assertRaises(ValueError):
                e.validate_packet(public, private)

    def test_duplicate_unknown_and_overlapping_exclusions_rejected(self):
        cases = [lambda p: p["exclusions"].append(copy.deepcopy(p["exclusions"][0])),
                 lambda p: p["exclusions"].append({"key": ["s", "u1", "p2"], "reason": "zero_valid_exposure"}),
                 lambda p: p["exclusions"].append({"key": ["s", "u1", "p6"], "reason": "zero_valid_exposure"}),
                 lambda p: p["exclusions"].append({"session_id": "s", "presentation_id": "p2", "reason": "temporal_guard"}),
                 lambda p: p["exclusions"].append({"key": ["s", "alien", "p3"], "reason": "zero_valid_exposure"}),
                 lambda p: p["exclusions"].append({"reason": "low_spike_count"})]
        for change in cases:
            public, private = fixture()
            change(private)
            with self.assertRaises(ValueError):
                e.validate_packet(public, private)

    def test_target_keys_and_count_validity_remain_strict(self):
        for mutation in (lambda p: p["targets"].pop(),
                         lambda p: p["targets"].append(copy.deepcopy(p["targets"][0])),
                         lambda p: p["targets"][0].update(count=True)):
            public, private = fixture()
            mutation(private)
            with self.assertRaises(ValueError):
                e.validate_packet(public, private)

    def test_cli_emits_unchanged_endpoint_with_coverage(self):
        public, private = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("public", public), ("private", private),
                                ("predictions", e.v1.fit_controls(public)["running_pupil"])):
                e.v1.write_json(root / (name + ".json"), value)
            command = [sys.executable, "-I", "-B", str(Path(e.__file__))]
            for name in ("public", "private", "predictions", "output"):
                command += ["--" + name, str(root / (name + ".json"))]
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads((root / "output.json").read_text())
            self.assertEqual(output["overall"]["mouse_macro_bits_per_spike"], 0)
            self.assertEqual(output["declared_roster_coverage"]["declared_observations"], 16)


if __name__ == "__main__":
    unittest.main()

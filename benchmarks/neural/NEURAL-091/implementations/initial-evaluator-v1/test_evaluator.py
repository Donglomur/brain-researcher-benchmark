"""Generated engineering controls. No recording data or reproduction claims."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import evaluator as e


def fixture():
    presentations = [
        {"presentation_id": "train1", "stimulus_name": "drifting_gratings", "stimulus_condition_id": "c1", "start_time": 0, "stop_time": 2, "stimulus": {"orientation": 0}},
        {"presentation_id": "near", "stimulus_name": "drifting_gratings", "stimulus_condition_id": "c1", "start_time": 3.5, "stop_time": 3.9},
        {"presentation_id": "query1", "stimulus_name": "natural_scenes", "stimulus_condition_id": "q1", "start_time": 4, "stop_time": 6, "stimulus": {"frame": 1}},
        {"presentation_id": "query2", "stimulus_name": "natural_scenes", "stimulus_condition_id": "q1", "start_time": 7, "stop_time": 9, "stimulus": {"frame": 1}},
    ]
    session = {"session_id": "s1", "mouse_id": "m1", "session_type": "brain_observatory_1.1", "source_file_sha256": "a" * 64, "source_file_bytes": 123,
               "units": [{"unit_id": "u1", "probe_id": "p1", "spike_times": [0, 1, 2, 4, 4.5, 6, 7, 8, 9]}],
               "presentations": presentations, "invalid_intervals": [],
               "running_samples": [{"start_time": 0, "stop_time": 2, "velocity": 2}, {"start_time": 2, "stop_time": 4, "velocity": 2}, {"start_time": 4, "stop_time": 6, "velocity": 2}, {"start_time": 6, "stop_time": 9, "velocity": 2}],
               "pupil_samples": [{"time": 0, "pupil_area": 100}, {"time": 4, "pupil_area": None}, {"time": 6, "pupil_area": 200}, {"time": 7, "pupil_area": 999}]}
    protocol = {"schema_version": 1, "contract_sha256": e.CONTRACT_SHA256, "sdk_commit": e.SDK_PIN,
                "session_type": "brain_observatory_1.1", "heldout_families": ["natural_scenes"],
                "temporal_guard_seconds": 0.2, "pupil_max_age_seconds": 2, "state_prior_seconds": 1, "state_history_seconds": 2,
                "quality_selection_policy": "Generated engineering fixture; no native eligibility claim",
                "sessions": [{"session_id": "s1", "mouse_id": "m1", "source_file_sha256": "a" * 64, "source_file_bytes": 123,
                              "unit_ids": ["u1"], "presentation_ids": [p["presentation_id"] for p in presentations], "presentation_table_sha256": e.digest(presentations)}]}
    return {"source": e.SOURCE, "sessions": [session]}, protocol


def repin(bundle, protocol):
    presentations = bundle["sessions"][0]["presentations"]
    protocol["sessions"][0]["presentation_ids"] = [p["presentation_id"] for p in presentations]
    protocol["sessions"][0]["presentation_table_sha256"] = e.digest(presentations)


class PipelineTests(unittest.TestCase):
    def test_full_prepare_control_score_and_guard(self):
        bundle, protocol = fixture()
        public, private = e.prepare(bundle, protocol)
        self.assertEqual([r["count"] for r in public["training"]], [2])
        self.assertEqual([r["count"] for r in private["targets"]], [2, 2])
        self.assertEqual(len(public["query"]), 2)
        self.assertEqual(private["exclusions"], [{"session_id": "s1", "presentation_id": "near", "reason": "temporal_guard"}])
        self.assertTrue(all("count" not in r for r in public["query"]))
        controls = e.fit_controls(public)
        self.assertEqual([r["rate_hz"] for r in controls["mean_rate"]], [1, 1])
        result = e.score(public, private, controls["mean_rate"])
        self.assertEqual(result["overall"]["mouse_macro_bits_per_spike"], 0)
        self.assertEqual(result["overall"]["mouse_count"], 1)
        self.assertIsNone(result["uncertainty"]["limits"])

    def test_heldout_spikes_do_not_change_public_or_controls(self):
        bundle, protocol = fixture()
        before, protected = e.prepare(bundle, protocol)
        bundle["sessions"][0]["units"][0]["spike_times"] += [8.1, 8.2]
        bundle["sessions"][0]["units"][0]["spike_times"].sort()
        after, changed = e.prepare(bundle, protocol)
        self.assertEqual(before, after)
        self.assertEqual(e.fit_controls(before), e.fit_controls(after))
        self.assertNotEqual(protected["targets"], changed["targets"])

    def test_missing_eye_is_retained_and_causal(self):
        bundle, protocol = fixture()
        public, _ = e.prepare(bundle, protocol)
        self.assertIsNone(public["query"][0]["pupil_area"])
        self.assertEqual(public["query"][0]["pupil_coverage"], 0)
        self.assertEqual(public["query"][1]["pupil_area"], 200)
        self.assertEqual(public["query"][1]["pupil_coverage"], 0.5)
        controls = e.fit_controls(public)
        self.assertEqual(len(controls["running_pupil"]), 2)

    def test_query_state_uses_only_preonset_history(self):
        bundle, protocol = fixture()
        public, _ = e.prepare(bundle, protocol)
        bundle["sessions"][0]["pupil_samples"][-1]["pupil_area"] = 123456
        bundle["sessions"][0]["running_samples"][-1]["velocity"] = 123456
        changed, _ = e.prepare(bundle, protocol)
        self.assertEqual(public, changed)

    def test_stimulus_invalid_closed_boundary_mask(self):
        bundle, protocol = fixture()
        bundle["sessions"][0]["invalid_intervals"] = [{"start_time": 6, "stop_time": 6.1, "scope": "stimulus"}]
        public, private = e.prepare(bundle, protocol)
        self.assertEqual([r["key"][2] for r in public["query"]], ["query2"])
        self.assertIn({"session_id": "s1", "presentation_id": "query1", "reason": "invalid_stimulus"}, private["exclusions"])

    def test_invalid_presentation_null_condition(self):
        bundle, protocol = fixture()
        bundle["sessions"][0]["presentations"][1].update(stimulus_name="invalid_presentation", stimulus_condition_id=None)
        repin(bundle, protocol)
        _, private = e.prepare(bundle, protocol)
        self.assertEqual(private["exclusions"][0]["reason"], "invalid_stimulus")

    def test_incomplete_cohort_and_presentation_rejected(self):
        for mutate in (lambda b, p: b["sessions"][0]["units"].clear(),
                       lambda b, p: b["sessions"][0]["presentations"].pop(),
                       lambda b, p: b["sessions"][0].update(source_file_bytes=124),
                       lambda b, p: b["sessions"][0].update(mouse_id="wrong")):
            bundle, protocol = fixture()
            mutate(bundle, protocol)
            with self.assertRaises(ValueError):
                e.prepare(bundle, protocol)

    def test_repeats_overlaps_and_unknown_fields_rejected(self):
        for mutate in (lambda b: b["sessions"][0]["presentations"][0].update(stimulus_condition_id="q1"),
                       lambda b: b["sessions"][0]["presentations"][2].update(start_time=3.8),
                       lambda b: b["sessions"][0]["presentations"][2].update(stimulus={"spike_count": 2})):
            bundle, protocol = fixture()
            mutate(bundle)
            repin(bundle, protocol)
            with self.assertRaises(ValueError):
                e.prepare(bundle, protocol)

    def test_prediction_keys_and_values_are_strict(self):
        public, private = e.prepare(*fixture())
        baseline = e.fit_controls(public)["mean_rate"]
        bad = [baseline[:-1], baseline + baseline[:1], [dict(r, extra=1) for r in baseline]]
        for value in (-1, float("nan"), float("inf"), True, "1"):
            rows = copy.deepcopy(baseline)
            rows[0]["rate_hz"] = value
            bad.append(rows)
        for rows in bad:
            with self.assertRaises(ValueError):
                e.score(public, private, rows)

    def test_public_tampering_and_leakage_rejected(self):
        public, private = e.prepare(*fixture())
        baseline = e.fit_controls(public)["mean_rate"]
        public["query"][0]["spike_count"] = 2
        with self.assertRaises(ValueError):
            e.score(public, private, baseline)
        del public["query"][0]["spike_count"]
        public["query"][0]["running_speed"] = 999
        with self.assertRaises(ValueError):
            e.score(public, private, baseline)

    def test_json_and_cli_roundtrip(self):
        bundle, protocol = fixture()
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            for name, value in (("bundle", bundle), ("protocol", protocol)):
                e.write_json(directory / (name + ".json"), value)
            program = str(Path(e.__file__).resolve())
            result = subprocess.run([sys.executable, program, "prepare", "--bundle", str(directory / "bundle.json"), "--protocol", str(directory / "protocol.json"), "--public", str(directory / "public.json"), "--private", str(directory / "private.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((directory / "private.json").stat().st_mode & 0o777, 0o600)
            public, private = e.read_json(directory / "public.json"), e.read_json(directory / "private.json")
            e.write_json(directory / "predictions.json", e.fit_controls(public)["mean_rate"])
            result = subprocess.run([sys.executable, program, "score", "--public", str(directory / "public.json"), "--private", str(directory / "private.json"), "--predictions", str(directory / "predictions.json"), "--output", str(directory / "score.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(e.read_json(directory / "score.json")["overall"]["mouse_macro_bits_per_spike"], 0)
            for raw in ('{"x": NaN}', '{"x": 1, "x": 2}'):
                (directory / "bad.json").write_text(raw)
                with self.assertRaises(ValueError):
                    e.read_json(directory / "bad.json")


if __name__ == "__main__":
    unittest.main()

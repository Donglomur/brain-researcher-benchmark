"""Generated complete-cohort delivery controls, not authentic calcium evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np

SPEC = importlib.util.spec_from_file_location("neural025_delivery_test", Path(__file__).with_name("delivery.py"))
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)

SESSIONS = [
    ("cfa17_20200825_172828", "cfa17", "M1"), ("cfa17_20200827_165724", "cfa17", "S1"),
    ("cfa19_20200820_143508", "cfa19", "M1"), ("cfa19_20200826_191222", "cfa19", "S1"),
    ("cfa20_20201114_194635", "cfa20", "M1"), ("cfa20_20201118_200612", "cfa20", "S1"),
    ("cfa22_20220605_182006", "cfa22", "M1"), ("cfa22_20220611_174801", "cfa22", "S1"),
    ("cfa24_20220727_160603", "cfa24", "M1"), ("cfa24_20220724_155906", "cfa24", "S1"),
]
JOINTS = "SHDRf SHDRa SHDRr ELBOf WRSTf WRSTd WRSTr MCP1f MCP2f MCP3f MCP4f MCP1a MCP2a MCP3a MCP4a MCP1o MCP4o P1P2 P2P3 P3P4 PIP1f PIP2f PIP3f PIP4f".split()


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def fixture():
    header = dict(task_id="NEURAL-025", author_commit="815b610b3beddfed5a3abf611d3a465ab9e4ce5c",
                  target_field="jointAngles", target_units="degrees", joint_names=JOINTS,
                  feature_variant="smoothed_deconvolved_events",
                  event_conditioning="retrospective_public_liftTimeDLC",
                  upstream_exposure_policy="processed_inputs_no_fold_safe_claim")
    dataset = dict(header, schema="calcium_normalized_v1", sessions=[])
    protocol = dict(header, schema="calcium_protocol_v1", sessions=[], condition="within_mouse",
                    metric_policy="train_sd_trial_session_mouse_macro_v1",
                    recipe_selection="fixed_before_evaluation_no_data_tuning", window_ms=[-100, 400],
                    grid_step_ms=10, cell_budget=2, pca_components=1, ridge_alpha=0.,
                    new_mouse_cases=[], limits=dict(max_total_timepoints=5000,
                    max_rois_per_session=4, max_trials_per_session=10))
    context = dict(schema="calcium_reach_context_v1", task_id="NEURAL-025",
                   event_conditioning="retrospective_public_liftTimeDLC", sessions=[])
    time = list(range(-100, 401, 10))
    for sid, mouse, region in SESSIONS:
        tids = [f"{sid}:private-source-trial-{n}" for n in [17, 23, 34, 42, 55, 68]]
        common = dict(session_id=sid, mouse_id=mouse, region=region,
                      roi_ids=["z-signal", "a-signal", "query-only-change", "constant"],
                      native_neural_field="data", upstream_temporal_support_ms=[-170, 470])
        for key in ("source_asset_sha256", "clock_evidence_sha256", "feature_provenance_sha256",
                    "normalization_recipe_sha256", "upstream_exposure_sha256", "trial_selection_policy_sha256"):
            common[key] = sha(["generated-not-native", sid, key])
        protocol["sessions"].append(dict(common, all_trial_ids=tids, training_trial_ids=tids[:4],
                                         evaluation_trial_ids=tids[4:], trial_census_sha256=sha(tids)))
        trials, labels = [], []
        for i, (tid, amplitude) in enumerate(zip(tids, [1., 3., 1., 3., 2., 2.])):
            z = amplitude * np.linspace(-1., 1., 51)
            x = np.column_stack([z, 2*z, np.zeros(51), np.ones(51)])
            y = z[:, None] + np.arange(24)[None, :]
            trials.append(dict(trial_id=tid, neural_trial_id=tid, target_trial_id=tid,
                               neural_time_ms=time, target_time_ms=time, neural=x.tolist(), targets=y.tolist()))
            labels.append(dict(trial_id=tid, original_trial_number=[17, 23, 34, 42, 55, 68][i],
                               reach_target="left" if i in (0, 1, 4) else "right"))
        dataset["sessions"].append(dict(common, trials=trials))
        context["sessions"].append(dict(session_id=sid, source_asset_sha256=common["source_asset_sha256"],
                                        native_target_mapping_sha256=sha("generated-LR"), trials=labels))
    return json.loads(json.dumps([dataset, protocol, context]))


class DeliveryControls(unittest.TestCase):
    def setUp(self):
        self.dataset, self.protocol, self.context = fixture()
        self.packet, self.index = self.prepare()
        self.program = sha("generated reference code identity; not a native run")

    def prepare(self):
        return d.prepare(self.dataset, self.protocol, self.context,
                         expected_protocol_sha256=sha(self.protocol), expected_context_sha256=sha(self.context))

    def response(self):
        return d.reference_response(self.packet, expected_packet_sha256=sha(self.packet),
                                    frozen_program_sha256=self.program)

    def collect(self, response, mode="frozen_program"):
        return d.collect_response(response, self.packet, self.index,
                                  expected_packet_sha256=sha(self.packet), expected_index_sha256=sha(self.index),
                                  expected_mode=mode, expected_program_sha256=self.program if mode == "frozen_program" else None)

    def test_complete_51_sample_24_joint_budget_and_paired_biology(self):
        self.assertEqual(len(self.packet["sessions"]), 10)
        self.assertEqual(self.packet["time_ms"], list(range(-100, 401, 10)))
        for session in self.packet["sessions"]:
            self.assertEqual(len(session["training"]), 4)
            self.assertEqual(len(session["query"]), 2)
            self.assertEqual(session["roi_ids"], ["roi-001", "roi-002"])
            for row in session["training"] + session["query"]:
                self.assertEqual(np.asarray(row["neural"]).shape, (51, 2))
            self.assertEqual(np.asarray(session["training"][0]["targets"]).shape, (51, 24))
            self.assertTrue(all(set(row) == {"case_id", "reach_target", "neural"} for row in session["query"]))
        self.assertEqual([(s["mouse_id"], s["region"]) for s in self.packet["sessions"]][-2:],
                         [("mouse-05", "M1"), ("mouse-05", "S1")])

    def test_hidden_targets_do_not_affect_any_participant_byte(self):
        before = d.p.canonical_bytes(self.packet)
        for session in self.dataset["sessions"]:
            for row in session["trials"][4:]:
                row["targets"] = (np.asarray(row["targets"]) + 12345).tolist()
        packet, index = self.prepare()
        self.assertEqual(before, d.p.canonical_bytes(packet))
        self.assertNotEqual(index["normalized_input_sha256"], self.index["normalized_input_sha256"])

    def test_query_only_variance_never_changes_selection(self):
        for session in self.dataset["sessions"]:
            for row in session["trials"][4:]:
                for i, x in enumerate(row["neural"]):
                    x[2] = (-1)**i * 1e8
        packet, index = self.prepare()
        self.assertEqual(packet, self.packet)
        self.assertTrue(all(s["selected_roi_ids"] == ["a-signal", "z-signal"] for s in index["sessions"].values()))

    def test_packet_whitelists_context_and_source_identity(self):
        self.context["private_answer_notes"] = "never-deliver-this"
        self.context["sessions"][0]["trials"][4]["trajectory"] = "never-deliver-this"
        packet, _ = self.prepare()
        text = json.dumps(packet)
        self.assertNotIn("never-deliver-this", text)
        self.assertNotIn("private-source-trial", text)
        self.assertNotIn("normalized_input_sha256", packet)

    def test_context_omission_duplicate_number_and_mismatched_source_reject(self):
        original = copy.deepcopy(self.context)
        for mutation in (lambda c: c["sessions"][0]["trials"].pop(),
                         lambda c: c["sessions"][0]["trials"][0].update(original_trial_number=23),
                         lambda c: c["sessions"][0].update(source_asset_sha256="a"*64)):
            self.context = copy.deepcopy(original)
            mutation(self.context)
            with self.assertRaises(d.p.Refusal):
                self.prepare()

    def test_reference_matches_independently_known_line_and_existing_scorer(self):
        response = self.response()
        native = self.collect(response)
        expected = np.linspace(-2, 2, 51)[:, None] + np.arange(24)[None, :]
        for rows in native.values():
            for value in rows.values():
                np.testing.assert_allclose(value, expected, atol=2e-13, rtol=1e-13)
        metrics = d.p.score_predictions(self.dataset, self.protocol, native, expected_protocol_sha256=sha(self.protocol))
        result = d.score_response(self.dataset, self.protocol, response, self.packet, self.index,
                                  expected_protocol_sha256=sha(self.protocol), expected_packet_sha256=sha(self.packet),
                                  expected_index_sha256=sha(self.index), expected_mode="frozen_program",
                                  expected_program_sha256=self.program)
        self.assertEqual(result["metrics"], metrics)
        self.assertFalse(result["process_isolation_verified"])

    def test_all_four_mode_receipts_use_identical_complete_predictions(self):
        expected = self.collect(self.response())
        for mode in d.MODES:
            response = self.response()
            response["mode"] = mode
            if mode != "frozen_program":
                del response["frozen_program_sha256"]
            self.assertEqual(self.collect(response, mode), expected)

    def test_mode_program_and_endpoint_mismatch_reject(self):
        for key, value in [("mode", "direct_observation"), ("frozen_program_sha256", "b"*64),
                           ("target_field", "jointVelocities"), ("target_units", "degrees_per_second"),
                           ("joint_names", JOINTS[::-1]), ("time_ms", list(range(-100, 400, 10)))]:
            response = self.response()
            response[key] = value
            with self.assertRaises(d.p.Refusal):
                self.collect(response)

    def test_missing_extra_malformed_and_nonfinite_predictions_reject(self):
        for mutation in (lambda r: r["predictions"].pop("session-10"),
                         lambda r: r["predictions"]["session-01"].pop("query-00001"),
                         lambda r: r["predictions"]["session-01"].update(extra=[[0.]*24]*51),
                         lambda r: r["predictions"]["session-01"]["query-00001"].pop(),
                         lambda r: r["predictions"]["session-01"]["query-00001"][0].__setitem__(0, float("nan")),
                         lambda r: r["predictions"]["session-01"]["query-00001"][0].__setitem__(0, True)):
            response = self.response()
            mutation(response)
            with self.assertRaises(d.p.Refusal):
                self.collect(response)

    def test_scoring_rejects_post_export_private_target_changes(self):
        self.dataset["sessions"][0]["trials"][4]["targets"][0][0] += 1.
        with self.assertRaises(d.p.Refusal):
            d.score_response(self.dataset, self.protocol, self.response(), self.packet, self.index,
                             expected_protocol_sha256=sha(self.protocol), expected_packet_sha256=sha(self.packet),
                             expected_index_sha256=sha(self.index), expected_mode="frozen_program",
                             expected_program_sha256=self.program)

    def test_trace_full_grid_training_units_and_query_target_refusal(self):
        action = dict(session_id="session-01", split="query", case_id="query-00001", signal="neural", channel="roi-001")
        row = d.trace(self.packet, action, expected_packet_sha256=sha(self.packet))
        np.testing.assert_allclose(row["values"], np.linspace(-4, 4, 51))
        svg = ET.fromstring(d.render_trace(self.packet, action, expected_packet_sha256=sha(self.packet)))
        self.assertEqual(len(svg.find("{http://www.w3.org/2000/svg}polyline").attrib["points"].split()), 51)
        action.update(signal="targets", channel="SHDRf")
        with self.assertRaises(d.p.Refusal):
            d.trace(self.packet, action, expected_packet_sha256=sha(self.packet))
        action.update(split="training", case_id="training-00001")
        self.assertEqual(d.trace(self.packet, action, expected_packet_sha256=sha(self.packet))["units"], "degrees")

    def test_velocity_is_a_separate_delivered_endpoint(self):
        for record in (self.dataset, self.protocol):
            record.update(target_field="jointVelocities", target_units="degrees_per_second")
        self.packet, self.index = self.prepare()
        response = self.response()
        self.assertEqual(response["target_units"], "degrees_per_second")
        self.assertEqual(len(response["joint_names"]), 24)
        self.collect(response)

    def test_participant_only_cli_and_bounded_reader(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "participant.json"
            path.write_bytes(d.p.canonical_bytes(self.packet))
            cmd = [sys.executable, "-B", str(Path(__file__).with_name("delivery.py")),
                   "--packet", str(path), "--expected-packet-sha256", sha(self.packet),
                   "--frozen-program-sha256", self.program,
                   "--max-input-bytes", str(path.stat().st_size), "--max-output-bytes", "1000000"]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.collect(json.loads(result.stdout))
            cmd[-3] = "1"
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"input-byte budget", result.stderr)


if __name__ == "__main__":
    unittest.main()

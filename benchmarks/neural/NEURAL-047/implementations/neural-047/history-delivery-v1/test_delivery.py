"""Generated software controls only; no authentic histories, fits, or model calls."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural047_delivery_test_subject", HERE / "delivery.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
from neural047_delivery_source.legacy.prepare import build, SOURCE_PIN


def fixture():
    records = []
    for animal in range(3):
        curvature = [0.1 * ((i + animal) % 3 - 1) for i in range(32)]
        curvature[10] = curvature[11] = -1
        curvature[25] = curvature[26] = 1
        records.append({
            "recording_id": f"generated_record_{animal}", "split_group": f"generated_animal_{animal}",
            "split_unit": "animal", "source_pin": SOURCE_PIN,
            "evidence": {"time_mapping": "generated integer seconds", "dv_orientation": "dorsal_positive:generated",
                         "saav_identity": "SAAV:generated", "group_identity": "generated distinct groups",
                         "processed_signal_support": "generated fixture only"},
            "time_seconds": list(range(32)), "native_frame0": list(range(32)),
            "velocity": [float(i % 5 - 2) for i in range(32)], "dv": curvature,
            "saav": [(i + animal) / 7 for i in range(32)],
            "reversal_state": [int(5 <= i <= 9 or 20 <= i <= 24) for i in range(32)],
            "events": [{"event_id": "a", "onset_index0": 5, "end_index0": 9},
                       {"event_id": "b", "onset_index0": 20, "end_index0": 24}]})
    normalized = {"schema": "neural047-normalized-native-v1", "source_pin": SOURCE_PIN,
                  "complete_WT_recording_roster": [r["recording_id"] for r in records],
                  "excluded_recordings": [], "records": records, "mapping_status": "generated only"}
    _, panel, folds, _ = build(normalized, bytes(range(32)))
    return panel, folds


def request(packet):
    return {"action": "submit", "predictions": [{"case_key": row["case_key"], "p_dorsal": .25}
                                                 for row in packet["query"]]}


def session(panel, packet, mode="typed_viewer"):
    return d.Session(panel, packet, mode, d.digest(packet))


def full_history(packet, case=None):
    return {"action": "history", "case_key": case or packet["query"][0]["case_key"],
            "channels": list(d.CHANNELS[packet["arm"]]), "start_seconds": -4.8, "end_seconds": 0}


class DeliveryControls(unittest.TestCase):
    def setUp(self):
        self.panel, self.folds = fixture()

    def test_direct_exact_roundtrip_every_sample_label_and_case(self):
        for packet in self.folds:
            s = session(self.panel, packet, "direct_observation")
            document = s.open()["document"]
            recovered = {}
            active = None
            for line in document.splitlines():
                if line.startswith("Case "):
                    active = line.split()[1]
                    recovered[active] = []
                elif line and line[0].isdigit() and "\t" in line:
                    recovered[active].append([json.loads(v) for v in line.split("\t")])
            self.assertEqual(len(recovered), 6)
            for role in ("training", "query"):
                for row in packet[role]:
                    f = row["features"]
                    expected = [[i, t, *[f[c][i] for c in d.CHANNELS[packet["arm"]]]]
                                for i, t in enumerate(f["time_offset_seconds"])]
                    self.assertEqual(recovered[row["case_key"]], expected)
                    header = next(line for line in document.splitlines() if line.startswith("Case " + row["case_key"]))
                    self.assertEqual("dorsal=" in header, role == "training")
            self.assertNotIn("generated_record_", document)
            self.assertNotIn("generated_animal_", document)

    def test_viewer_preserves_native_times_values_and_svg_point_identity(self):
        for packet in self.folds:
            s = session(self.panel, packet)
            opened = s.open()
            self.assertEqual(len(opened["catalog"]), 6)
            for role in ("training", "query"):
                for row in packet[role]:
                    rendered = s.dispatch(full_history(packet, row["case_key"]))
                    self.assertEqual(rendered["time_offset_seconds"], row["features"]["time_offset_seconds"])
                    self.assertEqual(rendered["sample_indices"], list(range(5)))
                    self.assertEqual(rendered["values"], {c: row["features"][c] for c in d.CHANNELS[packet["arm"]]})
                    self.assertEqual("dorsal" in rendered, role == "training")
                    root = ET.fromstring(rendered["svg"])
                    points = root.findall("{http://www.w3.org/2000/svg}circle")
                    self.assertEqual(len(points), 5 * len(d.CHANNELS[packet["arm"]]))
                    for i, point in enumerate(points[:5]):
                        t = row["features"]["time_offset_seconds"][i]
                        self.assertAlmostEqual(float(point.attrib["cx"]), 70 + 800 * (t + 4.8) / 4.8, places=4)

    def test_time_selection_uses_inclusive_native_samples(self):
        packet = self.folds[0]
        s = session(self.panel, packet)
        s.open()
        action = full_history(packet)
        action.update(start_seconds=-3, end_seconds=-1)
        result = s.dispatch(action)
        self.assertEqual(result["time_offset_seconds"], [-3, -2, -1])
        self.assertEqual(result["sample_indices"], [1, 2, 3])

    def test_invalid_observation_actions_leave_context_unmodified(self):
        packet = self.folds[0]
        s = session(self.panel, packet)
        s.open()
        actions = [{"action": "read_file", "path": "targets.json"},
                   {**full_history(packet), "case_key": "../other_fold"},
                   {**full_history(packet), "channels": ["dv"]},
                   {**full_history(packet), "channels": ["saav_history", "saav_history"]},
                   {**full_history(packet), "end_seconds": .01},
                   {**full_history(packet), "start_seconds": -5},
                   {**full_history(packet), "start_seconds": True},
                   {**full_history(packet), "end_seconds": float("nan")},
                   {**full_history(packet), "start_seconds": -.7, "end_seconds": -.2},
                   {**full_history(packet), "target": 1}]
        for action in actions:
            with self.assertRaises(ValueError):
                s.dispatch(action)
            self.assertEqual(s.action_count, 1)
            self.assertFalse(s.closed)

    def test_direct_tools_and_post_close_operations_refused(self):
        s = session(self.panel, self.folds[0], "direct_observation")
        with self.assertRaises(ValueError):
            s.dispatch(request(self.folds[0]))
        s.open()
        for action in ({"action": "catalog"}, full_history(self.folds[0])):
            with self.assertRaises(ValueError):
                s.dispatch(action)
        s.dispatch(request(self.folds[0]))
        with self.assertRaises(ValueError):
            s.dispatch(request(self.folds[0]))
        with self.assertRaises(ValueError):
            s.open()

    def test_transport_capacity_failure_never_truncates_or_closes_context(self):
        s = session(self.panel, self.folds[0])
        s.open()
        original_cap = d.CAP
        try:
            d.CAP = s.transcript_bytes + 10
            with self.assertRaises(ValueError):
                s.dispatch(full_history(self.folds[0]))
            self.assertFalse(s.closed)
            self.assertEqual(s.action_count, 1)
        finally:
            d.CAP = original_cap
        self.assertEqual(len(s.dispatch(full_history(self.folds[0]))["sample_indices"]), 5)

    def test_session_observations_are_detached_from_caller_mutation(self):
        packet = copy.deepcopy(self.folds[0])
        expected = copy.deepcopy(packet["query"][0]["features"])
        pin = d.digest(packet)
        s = d.Session(self.panel, packet, "typed_viewer", pin)
        packet["query"][0]["features"]["saav_history"][0] = 999
        pin["sha256"] = "0" * 64
        s.open()
        result = s.dispatch(full_history(self.folds[0]))
        self.assertEqual(result["values"]["saav_history"], expected["saav_history"])
        self.assertNotEqual(s.receipt["observations_pin"]["sha256"], "0" * 64)

    def test_complete_training_identity_and_packet_pins_enforced(self):
        packet = self.folds[0]
        damaged = copy.deepcopy(packet)
        damaged["training"].pop()
        with self.assertRaises(ValueError):
            session(self.panel, damaged)
        damaged = copy.deepcopy(packet)
        damaged["training"][0]["group"] = damaged["training"][-1]["group"]
        with self.assertRaises(ValueError):
            session(self.panel, damaged)
        damaged = copy.deepcopy(packet)
        damaged["query"][0]["dorsal"] = 1
        with self.assertRaises(ValueError):
            session(self.panel, damaged)
        damaged = copy.deepcopy(packet)
        damaged["query"][0]["features"]["time_offset_seconds"][-1] = .01
        with self.assertRaises(ValueError):
            session(self.panel, damaged)
        with self.assertRaises(ValueError):
            d.Session(self.panel, packet, "typed_viewer", {"bytes": 1, "sha256": "0" * 64})

    def test_submission_join_and_probability_failures_preserve_retry(self):
        packet = self.folds[0]
        s = session(self.panel, packet)
        s.open()
        bad = []
        for probability in (True, -0.1, 1.1, math.inf, math.nan, "0.5"):
            action = request(packet)
            action["predictions"][0]["p_dorsal"] = probability
            bad.append(action)
        bad += [{"action": "submit", "predictions": request(packet)["predictions"][:1]},
                {"action": "submit", "predictions": [request(packet)["predictions"][0]] * 2},
                {"action": "abstain", "reason": ""}]
        for action in bad:
            with self.assertRaises(ValueError):
                s.dispatch(action)
            self.assertFalse(s.closed)
        response = s.dispatch(request(packet))
        self.assertEqual(response["observation_actions"], 1)
        self.assertTrue(s.closed)

    def paired(self):
        contexts, responses = {}, {}
        for mode in d.MODES:
            contexts[mode], responses[mode] = [], []
            for packet in self.folds:
                s = session(self.panel, packet, mode)
                s.open()
                contexts[mode].append(copy.deepcopy(s.receipt))
                responses[mode].append(s.dispatch(request(packet)))
        return contexts, responses

    def test_paired_collection_preserves_mode_and_original_scorer_format(self):
        contexts, responses = self.paired()
        pair = d.collect_paired(self.panel, contexts, responses)
        for mode, collection in pair["collections"].items():
            probabilities, abstained = d.admit(self.panel, collection["submission"])
            self.assertEqual(len(probabilities), 9)
            self.assertFalse(abstained)
            self.assertEqual(collection["mode"], mode)
        self.assertNotEqual(contexts[d.MODES[0]][0]["delivery_id"], contexts[d.MODES[1]][0]["delivery_id"])

    def test_incomplete_duplicate_crossmode_and_substituted_pairs_refused(self):
        contexts, responses = self.paired()
        short = copy.deepcopy(responses)
        short[d.MODES[0]].pop()
        duplicate = copy.deepcopy(responses)
        duplicate[d.MODES[0]][-1] = duplicate[d.MODES[0]][0]
        crossed = copy.deepcopy(responses)
        crossed[d.MODES[0]][0] = crossed[d.MODES[1]][0]
        for invalid in (short, duplicate, crossed):
            with self.assertRaises(ValueError):
                d.collect_paired(self.panel, contexts, invalid)
        changed = copy.deepcopy(self.folds[0])
        changed["query"][0]["features"]["saav_history"][0] += .01
        s = session(self.panel, changed, d.MODES[1])
        s.open()
        contexts[d.MODES[1]][0] = s.receipt
        responses[d.MODES[1]][0] = s.dispatch(request(changed))
        with self.assertRaises(ValueError):
            d.collect_paired(self.panel, contexts, responses)

    def test_abstention_remains_complete_and_unscored_without_target_access(self):
        contexts, responses = self.paired()
        s = session(self.panel, self.folds[0], d.MODES[0])
        s.open()
        responses[d.MODES[0]][0] = s.dispatch({"action": "abstain", "reason": "cannot interpret"})
        result = d.collect_paired(self.panel, contexts, responses)
        from neural047_delivery_source.legacy.scorer_core import score
        def forbidden():
            raise AssertionError("Private callback must never be opened after abstention")
        grade = score(self.panel, result["collections"][d.MODES[0]]["submission"], forbidden)
        self.assertEqual(grade["status"], "abstained")
        self.assertEqual(grade["private_target_callbacks"], 0)

    def test_cli_stream_and_eof_failure(self):
        with tempfile.TemporaryDirectory(prefix="neural047-delivery-control-") as name:
            # macOS temp paths can traverse /var -> /private/var; use the actual
            # directory while retaining the production transport's symlink ban.
            root = Path(name).resolve()
            d.io.put(root / "panel.json", self.panel, d.CAP)
            packet = self.folds[0]
            pin = d.io.put(root / "packet.json", packet, d.CAP)
            common = [sys.executable, "-I", "-S", "-B", str(HERE / "delivery.py"), "session",
                      "--panel", str(root / "panel.json"), "--packet", str(root / "packet.json"),
                      "--expected-packet-sha256", pin["sha256"], "--expected-packet-bytes", str(pin["bytes"])]
            for mode in d.MODES:
                path = root / (mode + ".json")
                proc = subprocess.run(common + ["--mode", mode, "--output", str(path),
                                               "--context-output", str(root / (mode + ".context.json")),
                                               "--transcript-output", str(root / (mode + ".audit.json"))],
                                      input=d.io.canonical(request(packet)), capture_output=True, timeout=15)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                lines = [json.loads(line) for line in proc.stdout.splitlines()]
                self.assertEqual(len(lines), 2)
                self.assertEqual(lines[-1], d.io.json_file(path, d.CAP))
                self.assertEqual(lines[-1]["context"]["mode"], mode)
                audit = d.io.json_file(root / (mode + ".audit.json"), d.CAP)
                self.assertTrue(audit["response_persisted"])
                self.assertIsNone(audit["failure_type"])
                self.assertEqual(audit["actions"][-1]["previous"], lines[-1]["observation_transcript_sha256"])
            proc = subprocess.run(common + ["--mode", d.MODES[0], "--output", str(root / "eof.json"),
                                           "--context-output", str(root / "eof.context.json"),
                                           "--transcript-output", str(root / "eof.audit.json")],
                                  input=b"", capture_output=True, timeout=15)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((root / "eof.json").exists())
            audit = d.io.json_file(root / "eof.audit.json", d.CAP)
            self.assertFalse(audit["closed"])
            self.assertEqual(audit["failure_type"], "ValueError")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Generated controls only. Never opens authentic signal or label files."""
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sleep_viewer_tested", HERE / "viewer.py")
viewer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = viewer
spec.loader.exec_module(viewer)
GENERATED_BYTES = 0


def pin(path):
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": viewer.sha(body)}


class FakePacket:
    def __init__(self, case="development-001", epochs=2):
        self.case, self.epochs = case, epochs
        self.clock = [[i / 120, 0.0, 1.0] for i in range(epochs)]
        self.pins = {"generated_only": True}

    def samples(self, start, stop, channels):
        return [[0.0] * (stop - start) for _ in channels]

    def close(self):
        pass


class FakeRenderer:
    @staticmethod
    def render(epoch_id, start_sample, channels, values, gain, clocks, raster, *, target_start_sample):
        # Deterministic generated stand-in for state/history tests only.
        return viewer.encode([epoch_id, start_sample, channels, gain, clocks, target_start_sample])


def write_history(root, packet):
    global GENERATED_BYTES
    root.mkdir()
    manifest = {"schema": "sleep-whole-person-viewer-session/v1", "mode": viewer.MODE,
                "case_id": packet.case, "epochs": packet.epochs, "max_actions": packet.epochs * 2 + 1,
                "inputs": packet.pins, "source": viewer.source_identity(),
                "runtime": viewer.runtime_identity(), "prompt": viewer.PROMPT}
    (root / "manifest.json").write_bytes(viewer.encode(manifest))
    session = viewer.Session(packet, manifest["max_actions"], None, FakeRenderer)
    chain = viewer.sha(viewer.encode(manifest))
    rows = []
    requests = []
    for index in range(packet.epochs):
        requests += [{"action": "epoch", "index": index},
                     {"action": "respond", "epoch_id": f"{packet.case}/{index:05d}", "probabilities": [0.2] * 5}]
    requests += [{"action": "finish"}]
    for request in requests:
        response = session.handle(request)
        row = {"ordinal": session.actions, "previous": chain, "request": request,
               "response_sha256": viewer.sha(viewer.encode(response))}
        rows.append(row)
        chain = viewer.sha(viewer.encode(row))
    (root / "actions.jsonl").write_bytes(b"".join(viewer.encode(row) for row in rows))
    (root / "completion.json").write_bytes(viewer.encode({"actions": session.actions,
        "last_sha256": chain, "case_id": packet.case, "epochs": packet.epochs, "mode": viewer.MODE}))
    GENERATED_BYTES += sum(path.stat().st_size for path in root.iterdir())
    return rows


def packet_fixture(root, epochs=2):
    global GENERATED_BYTES
    root.mkdir()
    signal = np.arange(3 * epochs * 3000, dtype=np.float64).reshape(3, epochs * 3000) * 1e-9
    np.save(root / "signals.npy", signal, allow_pickle=False)
    np.savez(root / "clock.npz", epoch_start_seconds=np.arange(epochs, dtype=np.float64) * 30,
             clock_features=np.asarray([[i / 120, 0.0, 1.0] for i in range(epochs)], dtype=np.float64))
    manifest = {"generated_fixture": True}
    (root / "manifest.json").write_bytes(viewer.encode(manifest))
    fact = {"epochs": epochs, "manifest": manifest,
            "raw_member_pins": {path.name: pin(path) for path in root.iterdir()}}
    GENERATED_BYTES += sum(path.stat().st_size for path in root.iterdir())
    return fact, signal


class ViewerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # macOS exposes its temporary directory through /var -> /private/var.
        # Resolve that known fixture parent without weakening runtime link checks.
        cls.old_tempdir = tempfile.tempdir
        tempfile.tempdir = str(Path(tempfile.gettempdir()).resolve())

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls.old_tempdir

    def session(self, epochs=2, budget=None):
        return viewer.Session(FakePacket(epochs=epochs), budget or 2 * epochs + 20, None, FakeRenderer)

    def test_response_requires_complete_target_observation(self):
        session = self.session()
        response = {"action": "respond", "epoch_id": "development-001/00000", "probabilities": [0.2] * 5}
        with self.assertRaisesRegex(ValueError, "previously rendered"):
            session.handle(response)
        session.handle({"action": "window", "start_sample": 100, "stop_sample": 3100})
        with self.assertRaises(ValueError):
            session.handle(response)
        session.handle({"action": "epoch", "index": 0})
        self.assertEqual(session.handle(response)["completed_epochs"], 1)
        with self.assertRaisesRegex(ValueError, "first final"):
            session.handle(response)

    def test_missing_channel_is_not_complete_target_observation(self):
        session = self.session()
        session.handle({"action": "channels", "channels": ["EEG Fpz-Cz"]})
        with self.assertRaises(ValueError):
            session.handle({"action": "respond", "epoch_id": session.epoch_id(), "probabilities": [0.2] * 5})
        session.handle({"action": "channels", "channels": list(viewer.CHANNELS)})
        session.handle({"action": "respond", "epoch_id": session.epoch_id(), "probabilities": [0.2] * 5})

    def test_future_context_available_without_target_relabel(self):
        session = self.session(epochs=10)
        result = session.handle({"action": "window", "start_sample": 27000, "stop_sample": 30000})
        self.assertEqual(result["epoch_id"], "development-001/00000")
        self.assertEqual(result["state"]["start_sample"], 27000)
        self.assertEqual(session.seen, set())
        self.assertEqual(result["clock_features"], {"elapsed_hours": 0.0, "wall_clock_sin": 0.0, "wall_clock_cos": 1.0})

    def test_no_raw_samples_in_participant_projection(self):
        result = self.session().handle({"action": "inspect"})
        self.assertEqual(set(result), {"kind", "mode", "epoch_id", "state", "clock_features",
                                      "sample_rate_hz", "signal_units", "display_units", "image"})
        self.assertEqual(set(result["image"]), {"mime_type", "base64"})

    def test_typed_actions_bounds_and_unavailable_tools(self):
        bad = [{"action": "python", "code": "pass"}, {"action": "epoch", "index": True},
               {"action": "epoch", "index": 2}, {"action": "epoch", "index": -1},
               {"action": "window", "start_sample": 0, "stop_sample": 99},
               {"action": "window", "start_sample": 0, "stop_sample": 6001},
               {"action": "window", "start_sample": -1, "stop_sample": 3000},
               {"action": "gain", "microvolts_per_division": 0},
               {"action": "channels", "channels": ["EEG Fpz-Cz", "EEG Fpz-Cz"]},
               {"action": "channels", "channels": []}, {"action": "inspect", "feedback": True}]
        for request in bad:
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.session().handle(request)

    def test_probability_contract(self):
        for bad in ([True, 0, 0, 0, 0], [float("nan")] * 5, [float("inf"), 0, 0, 0, 0], [10**1000, 0, 0, 0, 0],
                    [1.1, -0.1, 0, 0, 0], [0.2] * 4, [0.1] * 5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                viewer.probabilities(bad)
        self.assertEqual(viewer.probabilities([1, 0, 0, 0, 0]), [1.0, 0, 0, 0, 0])

    def test_incomplete_finish_and_budget_are_not_silent_drops(self):
        session = self.session(budget=5)
        with self.assertRaisesRegex(ValueError, "Every whole-clock"):
            session.handle({"action": "finish"})
        for _ in range(4):
            session.handle({"action": "inspect"})
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            session.handle({"action": "inspect"})
        with self.assertRaises(ValueError):
            self.session(budget=4)

    def test_exact_complete_replay_then_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "session"
            packet = FakePacket()
            write_history(root, packet)
            answers, receipt = viewer.replay(root, packet, None, FakeRenderer)
            self.assertEqual(set(answers), {0, 1})
            self.assertEqual(receipt["actions"], 5)

    def test_replay_rejects_changed_response_reordering_and_omission(self):
        for mutation in ("digest", "reorder", "missing", "truncated", "foreign"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "session"
                packet = FakePacket()
                rows = write_history(root, packet)
                if mutation == "digest": rows[0]["response_sha256"] = "0" * 64
                elif mutation == "reorder": rows[0], rows[1] = rows[1], rows[0]
                elif mutation == "missing": rows.pop(1)
                elif mutation == "foreign": rows[1]["request"]["epoch_id"] = "development-002/00000"
                body = b"".join(viewer.encode(row) for row in rows)
                (root / "actions.jsonl").write_bytes(body[:-1] if mutation == "truncated" else body)
                with self.assertRaises(ValueError):
                    viewer.replay(root, packet, None, FakeRenderer)

    def test_replay_rejects_wrong_mode_inputs_source_and_person(self):
        for field, value in (("mode", "ordinary_feature_programme"), ("inputs", {}),
                             ("source", {}), ("case_id", "development-002"), ("runtime", {})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "session"
                packet = FakePacket()
                write_history(root, packet)
                manifest = viewer.decode((root / "manifest.json").read_bytes())
                manifest[field] = value
                (root / "manifest.json").write_bytes(viewer.encode(manifest))
                with self.assertRaisesRegex(ValueError, "condition mismatch"):
                    viewer.replay(root, packet, None, FakeRenderer)

    def test_packet_mapping_channel_and_clock_geometry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "packet"
            fact, values = packet_fixture(root)
            with patch.object(viewer, "source_facts", return_value=fact):
                packet = viewer.Packet(root, "development-001")
            try:
                sampled = packet.samples(2900, 3100, list(viewer.CHANNELS))
                np.testing.assert_array_equal(sampled, values[:, 2900:3100])
                self.assertEqual(packet.clock[1].tolist(), [1 / 120, 0, 1])
            finally:
                packet.close()

    def test_packet_rejects_changed_signal_before_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "packet"
            fact, _ = packet_fixture(root)
            with (root / "signals.npy").open("r+b") as stream:
                stream.seek(-8, 2)
                stream.write(b"\0" * 8)
            with patch.object(viewer, "source_facts", return_value=fact), self.assertRaisesRegex(ValueError, "checksum"):
                viewer.Packet(root, "development-001")

    def test_packet_detects_post_admission_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "packet"
            fact, _ = packet_fixture(root)
            with patch.object(viewer, "source_facts", return_value=fact):
                packet = viewer.Packet(root, "development-001")
            try:
                with (root / "signals.npy").open("r+b") as stream:
                    stream.seek(-8, 2)
                    stream.write(b"\0" * 8)
                with self.assertRaisesRegex(ValueError, "changed"):
                    packet.samples(0, 100, list(viewer.CHANNELS))
            finally:
                packet.close()

    def test_authenticated_signal_fingerprint_cannot_be_rebased(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "packet"
            fact, _ = packet_fixture(root)
            original = viewer.pinned_file
            def changed_after_hash(path, expected):
                stream = original(path, expected)
                if Path(path).name == "signals.npy":
                    with Path(path).open("r+b") as writer:
                        writer.seek(-8, 2)
                        writer.write(b"\0" * 8)
                return stream
            with patch.object(viewer, "source_facts", return_value=fact), \
                 patch.object(viewer, "pinned_file", side_effect=changed_after_hash), \
                 self.assertRaisesRegex(ValueError, "changed"):
                viewer.Packet(root, "development-001")

    def test_locked_body_reauthenticates_actual_returned_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "metadata.json"
            path.write_bytes(b'{"a":1}\n')
            expected, original = pin(path), viewer.pinned_file
            def changed_after_hash(source, frozen):
                stream = original(source, frozen)
                path.write_bytes(b'{"a":2}\n')
                return stream
            with patch.object(viewer, "pinned_file", side_effect=changed_after_hash), \
                 self.assertRaisesRegex(ValueError, "changed"):
                viewer.locked_body(path, expected)

    def test_packet_rejects_wrong_clock_geometry_even_with_fixture_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "packet"
            fact, _ = packet_fixture(root)
            np.savez(root / "clock.npz", epoch_start_seconds=np.asarray([30., 60.]),
                     clock_features=np.zeros((2, 3)))
            fact["raw_member_pins"]["clock.npz"] = pin(root / "clock.npz")
            with patch.object(viewer, "source_facts", return_value=fact), self.assertRaisesRegex(ValueError, "whole-clock"):
                viewer.Packet(root, "development-001")

    def test_packet_rejects_linked_members_and_extra_target_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "packet"
            fact, _ = packet_fixture(root)
            (root / "labels.json").write_text("{}")
            with patch.object(viewer, "source_facts", return_value=fact), self.assertRaisesRegex(ValueError, "three original"):
                viewer.Packet(root, "development-001")
            (root / "labels.json").unlink()
            (root / "clock.npz").rename(Path(temp) / "clock.npz")
            (root / "clock.npz").symlink_to(Path(temp) / "clock.npz")
            with patch.object(viewer, "source_facts", return_value=fact), self.assertRaisesRegex(ValueError, "Linked"):
                viewer.Packet(root, "development-001")

    def test_real_generated_packet_serve_and_raster_replay(self):
        global GENERATED_BYTES
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet_root = root / "packet"
            fact, _ = packet_fixture(packet_root)
            requests = []
            for i in range(2):
                requests += [{"action": "epoch", "index": i}, {"action": "respond",
                    "epoch_id": f"development-001/{i:05d}", "probabilities": [0.2] * 5}]
            requests.append({"action": "finish"})
            args = types.SimpleNamespace(output=root / "session", packet=packet_root,
                                         case="development-001", max_actions=5)
            stdin = types.SimpleNamespace(buffer=io.BytesIO(b"".join(viewer.encode(r) for r in requests)))
            stdout = io.StringIO()
            with patch.object(viewer, "source_facts", return_value=fact), \
                 patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
                viewer.serve(args)
                packet = viewer.Packet(packet_root, "development-001")
            try:
                raster, _, renderer = viewer.dependencies()
                answers, receipt = viewer.replay(args.output, packet, raster, renderer)
                self.assertEqual(set(answers), {0, 1})
                self.assertEqual(receipt["actions"], 5)
                messages = [viewer.decode(line) for line in stdout.getvalue().splitlines()]
                self.assertEqual([row["kind"] for row in messages],
                                 ["instructions", "view", "response_accepted", "view", "response_accepted", "complete"])
                for row in (messages[1], messages[3]):
                    self.assertTrue(viewer.base64.b64decode(row["image"]["base64"]).startswith(b"\x89PNG\r\n\x1a\n"))
            finally:
                packet.close()
            GENERATED_BYTES += sum(path.stat().st_size for path in args.output.iterdir())

    def test_duplicate_nonfinite_metadata_rejected(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                viewer.decode(body)

    def test_output_path_cannot_normalize_into_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkout, outside = root / "checkout", root / "outside"
            checkout.mkdir()
            outside.mkdir()
            destination = outside / ".." / "checkout" / "output"
            with patch.object(viewer, "ROOT", checkout), self.assertRaisesRegex(ValueError, "external"):
                viewer.fresh_output(destination)
            self.assertFalse((checkout / "output").exists())

    def test_first_failed_input_is_preserved_and_cannot_be_collected(self):
        global GENERATED_BYTES
        for raw in (b"", b"not-json\n", b"\xff\n", b"x" * (viewer.MAX_REQUEST + 2)):
            with self.subTest(raw_size=len(raw)), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                packet = FakePacket()
                args = types.SimpleNamespace(output=root / "failed", packet=root / "unused",
                                             case=packet.case, max_actions=5)
                stdin = types.SimpleNamespace(buffer=io.BytesIO(raw))
                with patch.object(viewer, "Packet", return_value=packet), \
                     patch.object(viewer, "dependencies", return_value=(None, None, FakeRenderer)), \
                     patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", io.StringIO()), \
                     self.assertRaises(ValueError):
                    viewer.serve(args)
                failure = viewer.decode((args.output / "failure.json").read_bytes())
                captured = raw[:viewer.MAX_REQUEST + 1]
                self.assertEqual(failure["status"], "incomplete")
                self.assertEqual(failure["last_input_capture"]["sha256"], viewer.sha(captured))
                self.assertEqual(viewer.base64.b64decode(failure["last_input_capture"]["base64"]), captured)
                self.assertEqual(failure["last_input_capture"]["possible_truncation"], len(raw) > viewer.MAX_REQUEST + 1)
                self.assertFalse((args.output / "completion.json").exists())
                with self.assertRaisesRegex(ValueError, "Failed sessions"):
                    viewer.replay(args.output, packet, None, FakeRenderer)
                GENERATED_BYTES += sum(path.stat().st_size for path in args.output.iterdir())

    def test_all_5450_generated_responses_use_original_validator(self):
        global GENERATED_BYTES
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packets = {case: FakePacket(case, count) for case, count in viewer.CASES.items()}
            sessions = []
            for case, packet in packets.items():
                path = root / case
                write_history(path, packet)
                sessions.append(path)
            raster, adapter, _ = viewer.dependencies()
            args = types.SimpleNamespace(output=root / "collection", packets=[root / "p1", root / "p2"], sessions=sessions)
            with patch.object(viewer, "Packet", side_effect=lambda _path, case: packets[case]), \
                 patch.object(viewer, "dependencies", return_value=(raster, adapter, FakeRenderer)):
                viewer.collect(args)
            report = viewer.decode((args.output / "collection.json").read_bytes())
            self.assertEqual(report["epochs"], 5450)
            self.assertLess(report["submission"]["bytes"], 4000000)
            with np.load(args.output / "predictions.npz", allow_pickle=False) as arrays:
                self.assertEqual(arrays["development-001__epoch_id"][-1], "development-001/02779")
                self.assertEqual(arrays["development-002__epoch_id"][-1], "development-002/02669")
            GENERATED_BYTES += sum(path.stat().st_size for path in args.output.iterdir())


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        print("Generated fixture bytes retained or deleted:", GENERATED_BYTES)

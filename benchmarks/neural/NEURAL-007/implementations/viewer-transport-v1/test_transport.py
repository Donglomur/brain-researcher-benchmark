"""Independent controls using invented signals, never authentic neural data."""
from __future__ import annotations

import base64
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sleep_transport_controlled", HERE / "transport.py")
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)

# A valid, explicitly generated one-pixel PNG exercises byte framing; scientific
# renderer correctness is covered by the unchanged viewer's separate controls.
GENERATED_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
)


class GeneratedPacket:
    def __init__(self, case="development-001", epochs=2):
        self.case = case
        self.epochs = epochs
        self.clock = [[index / 120, 0.0, 1.0] for index in range(epochs)]
        self.pins = {"generated_fixture_only": {"case": case, "epochs": epochs}}

    def samples(self, start, stop, channels):
        return [[0.0] * (stop - start) for _ in channels]

    def close(self):
        pass


class GeneratedRenderer:
    @staticmethod
    def render(*args, **kwargs):
        return GENERATED_PNG


CLIENT_HELPER = r'''
import json, os, struct, sys
PREFIX = struct.Struct("!II")
def exact(size):
    body = bytearray()
    while len(body) < size:
        part = sys.stdin.buffer.read(size-len(body))
        if not part: raise EOFError("missing frame")
        body.extend(part)
    return bytes(body)
def receive():
    hsize, isize = PREFIX.unpack(exact(8))
    if not (0 < hsize <= 32768 and 0 <= isize <= 4*1024*1024):
        raise ValueError("unsafe server frame")
    return json.loads(exact(hsize)), exact(isize)
def send(action):
    body = json.dumps(action, allow_nan=False, separators=(",", ":")).encode()
    sys.stdout.buffer.write(PREFIX.pack(len(body), 0) + body)
    sys.stdout.buffer.flush()
def complete():
    ready, image = receive()
    assert not image
    for index in range(ready["epochs"]):
        send({"action": "epoch", "index": index})
        view, png = receive()
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        send({"action": "respond", "epoch_id": view["epoch_id"], "probabilities": [0.2]*5})
        response, image = receive()
        assert response["kind"] == "response_accepted" and not image
    send({"action": "finish"})
    final, image = receive()
    assert final["kind"] == "complete" and not image
'''


class TransportControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.packet = GeneratedPacket()
        self.client_number = 0
        self.session_number = 0
        self.adapter = t.v.dependencies()[1]

    def tearDown(self):
        self.temp.cleanup()

    def client(self, suffix):
        self.client_number += 1
        path = self.root / f"client-{self.client_number}.py"
        path.write_text(CLIENT_HELPER + "\n" + suffix)
        return path

    def limits(self, **changes):
        values = dict(max_actions=20, max_images=10,
                      max_output_bytes=32*1024**2, wall_seconds=10)
        values.update(changes)
        return t.Limits(**values)

    @contextlib.contextmanager
    def generated_dependencies(self):
        with patch.object(t.v, "dependencies", return_value=(None, self.adapter, GeneratedRenderer)), \
                patch.object(t.v, "CASES", {"development-001": 2, "development-002": 2}):
            yield

    def run_client(self, source="complete()", *, packet=None, limits=None):
        self.session_number += 1
        path = self.root / f"session-{self.session_number}"
        with self.generated_dependencies():
            receipt = t.run_person(packet or self.packet, path, self.client(source),
                                   python=sys.executable, sandbox="protocol_only",
                                   limits=limits or self.limits())
        return path, receipt

    def test_wire_roundtrip_preserves_exact_png_and_metadata(self):
        header = {"kind": "view", "epoch_id": "development-001/00000", "clock": [0.0, 0.0, 1.0]}
        frame = t.wire(header, GENERATED_PNG)
        self.assertEqual(struct.unpack("!II", frame[:8])[1], len(GENERATED_PNG))
        self.assertEqual(t.unpack(frame), (header, GENERATED_PNG))
        self.assertEqual(t.unpack(t.wire({"action": "inspect"}), inbound=True),
                         ({"action": "inspect"}, b""))

    def test_frame_parser_refuses_unbounded_or_ambiguous_lengths(self):
        cases = [b"", b"abc", struct.pack("!II", 2**32-1, 0),
                 struct.pack("!II", 1, 1) + b"{}", struct.pack("!II", 0, 0),
                 struct.pack("!II", 2, 0) + b"{}trailer"]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                t.unpack(raw, inbound=True)

    def test_limits_reject_invalid_types_nonfinite_and_insufficient_capacity(self):
        bad = [dict(max_actions=True), dict(max_actions=4), dict(max_actions=100001),
               dict(max_images=False), dict(max_images=1), dict(max_output_bytes=0),
               dict(max_output_bytes=True), dict(wall_seconds=0),
               dict(wall_seconds=float("nan")), dict(wall_seconds=float("inf"))]
        for values in bad:
            with self.subTest(values=values), self.assertRaises((ValueError, TypeError)):
                self.limits(**values).validate(2)

    def test_complete_person_roundtrip_replays_original_viewer(self):
        path, receipt = self.run_client()
        self.assertEqual(receipt["status"], "complete_unscored")
        self.assertEqual((receipt["actions"], receipt["images"]), (5, 2))
        self.assertEqual(receipt["client_exit_code"], 0)
        self.assertFalse(receipt["forced_stop"])
        with self.generated_dependencies():
            audited = t.audit_transport(path, self.packet)
            answers, viewer_receipt = t.v.replay(path / "viewer", self.packet, None, GeneratedRenderer)
        self.assertEqual(answers, {0: [0.2]*5, 1: [0.2]*5})
        self.assertEqual(audited["result"], receipt)
        self.assertEqual(viewer_receipt["actions"], 5)
        self.assertFalse(audited["boundary"]["provider_context_qualified"])
        self.assertFalse(audited["boundary"]["scientific_qualification"])

    def test_ready_and_view_projection_do_not_expose_operator_material(self):
        path, _ = self.run_client()
        raw = (path / "transport" / "wire.bin").read_bytes()
        rows = [json.loads(line) for line in (path / "transport" / "journal.jsonl").read_bytes().splitlines()]
        expected_ready = {"kind", "episode_id", "mode", "case_id", "epochs", "prompt", "actions", "limits", "instructions"}
        rendered = 0
        for row in rows:
            if row["direction"] != "out":
                continue
            body = raw[row["offset"]:row["offset"]+row["bytes"]]
            header, image = t.unpack(body)
            self.assertNotIn(str(self.root).encode(), body)
            self.assertNotIn(b"development-002", body)
            for forbidden in ("packet", "inputs", "source", "labels", "score", "samples", "path"):
                self.assertNotIn(forbidden, header)
            if row["sequence"] == 0:
                self.assertEqual(set(header), expected_ready)
                self.assertFalse(image)
            if header["kind"] == "view":
                rendered += 1
                self.assertEqual(image, GENERATED_PNG)
                self.assertEqual(header["image"], {"mime_type": "image/png", "bytes": len(image)})
                self.assertNotIn("base64", header["image"])
        self.assertEqual(rendered, 2)

    def test_fresh_child_environment_and_working_directory_per_person(self):
        import subprocess
        real_popen = subprocess.Popen
        script = "assert 'SLEEP_TRANSPORT_CONTROL_SECRET' not in os.environ\nassert not os.listdir('.')\ncomplete()"
        clients = []
        with patch.dict(os.environ, {"SLEEP_TRANSPORT_CONTROL_SECRET": "do-not-inherit"}), \
                patch.object(t.subprocess, "Popen", wraps=real_popen) as spawned:
            for case in ("development-001", "development-002"):
                path, result = self.run_client(script, packet=GeneratedPacket(case))
                self.assertEqual(result["status"], "complete_unscored")
                clients.append(json.loads((path / "BOUNDARY.json").read_bytes()))
        self.assertEqual(spawned.call_count, 2)
        self.assertNotEqual(clients[0]["episode_id"], clients[1]["episode_id"])
        self.assertEqual(clients[0]["client_sha256"], clients[1]["client_sha256"])
        calls = spawned.call_args_list
        self.assertNotEqual(calls[0].kwargs["cwd"], calls[1].kwargs["cwd"])
        for call in calls:
            self.assertTrue(call.kwargs["close_fds"])
            self.assertTrue(call.kwargs["start_new_session"])
            self.assertEqual(call.kwargs["env"], {"LANG": "C", "LC_ALL": "C"})

    def assert_failed(self, path, result, reason=None):
        self.assertEqual(result["status"], "failed")
        self.assertTrue((path / "failure.json").is_file())
        self.assertTrue((path / "viewer" / "failure.json").is_file())
        if reason:
            self.assertIn(reason.lower(), result["reason"]["message"].lower())
        with self.generated_dependencies(), self.assertRaises(ValueError):
            t.audit_transport(path, self.packet)

    def test_invalid_action_fails_whole_session_and_keeps_exact_input(self):
        for action in ({"action": "read_file", "path": "/etc/passwd"},
                       {"action": "respond", "epoch_id": "development-001/00000", "probabilities": [0.2]*5},
                       {"action": "finish"}, {"action": "epoch", "index": True},
                       {"action": "inspect", "labels": True}):
            with self.subTest(action=action):
                path, result = self.run_client("receive()\nsend(" + repr(action) + ")")
                self.assert_failed(path, result)
                raw = (path / "transport" / "wire.bin").read_bytes()
                rows = [json.loads(line) for line in (path / "transport" / "journal.jsonl").read_bytes().splitlines()]
                last = rows[-1]
                header, image = t.unpack(raw[last["offset"]:last["offset"]+last["bytes"]], inbound=True)
                self.assertEqual(header, action)
                self.assertFalse(image)

    def test_first_valid_epoch_answer_cannot_be_replaced(self):
        script = '''
receive()
send({"action":"epoch","index":0}); view,_=receive()
send({"action":"respond","epoch_id":view["epoch_id"],"probabilities":[1,0,0,0,0]}); receive()
send({"action":"respond","epoch_id":view["epoch_id"],"probabilities":[0,1,0,0,0]})
'''
        path, result = self.run_client(script)
        self.assert_failed(path, result, "first final")
        rows = [json.loads(line) for line in (path / "viewer" / "actions.jsonl").read_bytes().splitlines()]
        responses = [r["request"] for r in rows if r["request"]["action"] == "respond"]
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["probabilities"], [1, 0, 0, 0, 0])

    def test_malformed_json_and_nonfinite_values_fail(self):
        bodies = [b'\xff', b'{"action":"inspect","action":"finish"}',
                  b'{"action":"gain","microvolts_per_division":NaN}', b'['*1000]
        for body in bodies:
            with self.subTest(body=body[:80]):
                script = "receive()\nbody=" + repr(body) + "\nsys.stdout.buffer.write(PREFIX.pack(len(body),0)+body);sys.stdout.buffer.flush()"
                path, result = self.run_client(script)
                self.assert_failed(path, result)

    def test_invalid_frame_lengths_rejected_from_header_only(self):
        for header in (struct.pack("!II", 2**32-1, 0), struct.pack("!II", 1, 1)):
            with self.subTest(header=header):
                script = "receive()\nsys.stdout.buffer.write(" + repr(header) + ");sys.stdout.buffer.flush()"
                path, result = self.run_client(script)
                self.assert_failed(path, result, "frame")
                rows = [json.loads(line) for line in (path / "transport" / "journal.jsonl").read_bytes().splitlines()]
                last = rows[-1]
                self.assertFalse(last["complete"])
                self.assertEqual(last["bytes"], 8)
                raw = (path / "transport" / "wire.bin").read_bytes()
                self.assertEqual(raw[last["offset"]:], header)

    def test_truncated_input_and_eof_are_failed_attempts(self):
        for tail in (b"", b"abc", struct.pack("!II", 15, 0)+b'{"action":'):
            with self.subTest(tail=tail):
                script = "receive()\nsys.stdout.buffer.write(" + repr(tail) + ");sys.stdout.buffer.flush()"
                path, result = self.run_client(script)
                self.assert_failed(path, result)
                rows = [json.loads(line) for line in (path / "transport" / "journal.jsonl").read_bytes().splitlines()]
                self.assertFalse(rows[-1]["complete"])
                self.assertEqual(rows[-1]["bytes"], len(tail))

    def test_wall_deadline_stops_only_the_owned_client(self):
        path, result = self.run_client("receive()\nimport time\ntime.sleep(2)",
                                       limits=self.limits(wall_seconds=0.5))
        self.assert_failed(path, result, "deadline")
        self.assertTrue(result["forced_stop"])
        self.assertNotEqual(result["client_exit_code"], 0)

    def test_action_image_and_output_limits_prevent_silent_truncation(self):
        scripts = [
            ("receive()\nfor _ in range(3):\n send({'action':'inspect'});receive()",
             self.limits(max_images=2), "image budget"),
            ("receive()\nsend({'action':'inspect'});receive()\nfor i in range(2):\n send({'action':'epoch','index':i});v,_=receive()\n send({'action':'respond','epoch_id':v['epoch_id'],'probabilities':[0.2]*5});receive()\nsend({'action':'finish'})",
             self.limits(max_actions=5, max_images=5), "action budget"),
            ("receive()\nsend({'action':'inspect'})",
             self.limits(max_output_bytes=t.PNG_MAX+t.HEADER_MAX+t.RESERVE), "output budget"),
        ]
        for script, limits, reason in scripts:
            with self.subTest(reason=reason):
                path, result = self.run_client(script, limits=limits)
                self.assert_failed(path, result, reason)

    def test_nonzero_exit_after_complete_does_not_pass(self):
        path, result = self.run_client("complete()\nraise RuntimeError('after-finish')")
        self.assert_failed(path, result, "Owned client cleanup or successful exit unverified")
        self.assertNotEqual(result["client_exit_code"], 0)

    def test_descendant_cleanup_requires_post_reap_group_absence(self):
        script = '''
complete()
import subprocess
subprocess.Popen([sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(10)"],
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                 close_fds=True)
'''
        path, result = self.run_client(script)
        self.assertEqual(result["client_exit_code"], 0)
        cleanup = result["process_ownership"]
        self.assertTrue(cleanup["exit_observed_before_stop"])
        self.assertTrue(cleanup["leader_unreaped_before_signal"])
        self.assertTrue(cleanup["reaped"])
        self.assertEqual(cleanup["group_signal"], "sent")
        self.assertFalse(cleanup["descendant_containment_qualified"])
        # Orphan reaping is kernel/host dependent. Never admit unresolved group
        # presence, and never infer no descendants from a successful signal.
        if cleanup["group_absence_observed"]:
            self.assertTrue(cleanup["cleanup_complete"])
            self.assertEqual(result["status"], "complete_unscored")
            self.assertEqual(result["process_group_cleanup"], "absent")
        else:
            self.assertFalse(cleanup["cleanup_complete"])
            self.assert_failed(path, result, "unverified")

    def test_changed_wire_and_missing_journal_refused(self):
        path, _ = self.run_client()
        wire_path = path / "transport" / "wire.bin"
        original = wire_path.read_bytes()
        wire_path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.generated_dependencies(), self.assertRaises(ValueError):
            t.audit_transport(path, self.packet)
        wire_path.write_bytes(original)
        (path / "transport" / "journal.jsonl").unlink()
        with self.generated_dependencies(), self.assertRaises(OSError):
            t.audit_transport(path, self.packet)

    def test_partial_evidence_open_failure_closes_prior_streams(self):
        for missing in ("journal.jsonl", "actions.jsonl"):
            with self.subTest(missing=missing):
                path, _ = self.run_client()
                opened = []
                original = t.ordinary
                def interrupted_open(file, cap):
                    if Path(file).name == missing:
                        raise FileNotFoundError("generated admission interruption")
                    stream, metadata = original(file, cap)
                    opened.append(stream)
                    return stream, metadata
                try:
                    with self.generated_dependencies(), patch.object(t, "ordinary", side_effect=interrupted_open), \
                            self.assertRaises(FileNotFoundError):
                        t.audit_transport(path, self.packet)
                    self.assertTrue(opened)
                    self.assertTrue(all(stream.closed for stream in opened),
                                    "An evidence-reader admission failure leaked an already opened descriptor")
                finally:
                    for stream in opened:
                        stream.close()

    def test_boundary_source_limits_client_and_qualification_tampering_refused(self):
        path, _ = self.run_client()
        target = path / "BOUNDARY.json"
        original = target.read_bytes()
        mutations = [("source", {}), ("client_sha256", "0"*64),
                     ("profile_sha256", "0"*64), ("scientific_qualification", True),
                     ("provider_context_qualified", True), ("case_id", "development-002")]
        for field, value in mutations:
            with self.subTest(field=field):
                boundary = json.loads(original)
                boundary[field] = value
                target.write_bytes(t.encode(boundary))
                with self.generated_dependencies(), self.assertRaises(ValueError):
                    t.audit_transport(path, self.packet)
        boundary = json.loads(original)
        boundary["limits"]["max_actions"] += 1
        target.write_bytes(t.encode(boundary))
        with self.generated_dependencies(), self.assertRaises(ValueError):
            t.audit_transport(path, self.packet)
        target.write_bytes(original)
        with (path / "client.py").open("ab") as out:
            out.write(b"\n# changed after capture\n")
        with self.generated_dependencies(), self.assertRaises(ValueError):
            t.audit_transport(path, self.packet)

    def test_viewer_history_and_transport_must_agree(self):
        path, _ = self.run_client()
        action_path = path / "viewer" / "actions.jsonl"
        rows = [json.loads(line) for line in action_path.read_bytes().splitlines()]
        rows[1]["request"]["probabilities"] = [1, 0, 0, 0, 0]
        action_path.write_bytes(b"".join(t.encode(row) for row in rows))
        with self.generated_dependencies(), self.assertRaises(ValueError):
            t.audit_transport(path, self.packet)

    def test_different_valid_viewer_history_with_identical_answers_is_refused(self):
        path, _ = self.run_client()
        viewer_root = path / "viewer"
        manifest = json.loads((viewer_root / "manifest.json").read_bytes())
        old = [json.loads(line) for line in (viewer_root / "actions.jsonl").read_bytes().splitlines()]
        requests = [row["request"] for row in old]
        requests[0] = {"action": "inspect"}
        with self.generated_dependencies():
            session = t.v.Session(self.packet, manifest["max_actions"], None, GeneratedRenderer)
            chain = t.digest(t.encode(manifest))
            rows = []
            for request in requests:
                response = session.handle(request)
                row = {"ordinal": session.actions, "previous": chain, "request": request,
                       "response_sha256": t.digest(t.encode(response))}
                rows.append(row)
                chain = t.digest(t.encode(row))
            (viewer_root / "actions.jsonl").write_bytes(b"".join(t.encode(row) for row in rows))
            (viewer_root / "completion.json").write_bytes(t.encode({
                "actions": session.actions, "last_sha256": chain, "case_id": self.packet.case,
                "epochs": self.packet.epochs, "mode": t.v.MODE}))
            answers, _ = t.v.replay(viewer_root, self.packet, None, GeneratedRenderer)
            self.assertEqual(answers, {0: [0.2]*5, 1: [0.2]*5})
            with self.assertRaisesRegex(ValueError, "Wire request differs"):
                t.audit_transport(path, self.packet)

    def test_dependency_body_is_authenticated_before_import(self):
        fixture = self.root / "source"
        fixture.mkdir()
        binding = json.loads((HERE / "SOURCE_BINDINGS.json").read_bytes())
        key = next(key for key in binding["members"] if key.endswith("/viewer.py"))
        binding["members"][key]["sha256"] = "0"*64
        (fixture / "SOURCE_BINDINGS.json").write_bytes(t.encode(binding))
        with patch.object(t, "HERE", fixture), self.assertRaisesRegex(ValueError, "dependency mismatch"):
            t.load_viewer()

    def generated_boundary(self, index):
        return {"schema": "generated_only", "mode": t.v.MODE,
                "limits": {"max_actions": 6000, "max_images": 3000,
                           "max_output_bytes": 32*1024**2, "wall_seconds": 10},
                "sandbox": "protocol_only", "client_sha256": "a"*64,
                "python": sys.executable, "source": t.source_identity(),
                "episode_id": str(index)*32}

    def test_full_5450_generated_collection_uses_original_validator(self):
        packets = [GeneratedPacket(case, epochs) for case, epochs in t.v.CASES.items()]
        for index, packet in enumerate(packets):
            packet.root = self.root / f"packet-{index}"
        sessions = [self.root / f"complete-{i}" for i in range(2)]
        output = self.root / "collection"
        boundaries = [self.generated_boundary(i) for i in range(2)]
        lookup = {str(p.root): p for p in packets}
        def replay(_path, packet, _raster, _renderer):
            return {i: [0.2]*5 for i in range(packet.epochs)}, {"generated_only": True}
        with patch.object(t, "audit_transport", side_effect=[{"boundary": b} for b in boundaries]), \
                patch.object(t.v, "Packet", side_effect=lambda root, case: lookup[str(root)]), \
                patch.object(t.v, "replay", side_effect=replay), \
                patch.object(t.v, "dependencies", return_value=(None, self.adapter, GeneratedRenderer)):
            result = t.collect(packets, sessions, output)
        self.assertEqual(result["epochs"], 5450)
        self.assertFalse(result["scientific_qualification"])
        with np.load(output / "predictions.npz", allow_pickle=False) as data:
            self.assertEqual(data["class_order"].tolist(), ["W", "N1", "N2", "N3", "R"])
            for packet in packets:
                self.assertEqual(data[packet.case+"__probabilities"].shape, (packet.epochs, 5))
                self.assertEqual(data[packet.case+"__epoch_id"].tolist(),
                                 [f"{packet.case}/{i:05d}" for i in range(packet.epochs)])

    def test_collection_refuses_missing_duplicate_and_mixed_people(self):
        packets = [GeneratedPacket(case, epochs) for case, epochs in t.v.CASES.items()]
        for i, packet in enumerate(packets):
            packet.root = self.root / f"packet-{i}"
        sessions = [self.root / f"person-{i}" for i in range(2)]
        with patch.object(t.v, "collect") as final_collector:
            for people, paths in ((packets[:1], sessions[:1]), (packets[::-1], sessions),
                                  (packets, [sessions[0]]*2)):
                with self.subTest(people=[p.case for p in people]), self.assertRaises(ValueError):
                    t.collect(people, paths, self.root / "invalid")
            for field, value in (("client_sha256", "b"*64), ("sandbox", "macos"),
                                 ("episode_id", "0"*32), ("source", {})):
                boundaries = [self.generated_boundary(i) for i in range(2)]
                boundaries[1][field] = value
                with self.subTest(field=field), \
                        patch.object(t, "audit_transport", side_effect=[{"boundary": b} for b in boundaries]), \
                        self.assertRaises(ValueError):
                    t.collect(packets, sessions, self.root / "invalid")
            final_collector.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)

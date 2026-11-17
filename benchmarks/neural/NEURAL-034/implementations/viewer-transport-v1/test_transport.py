"""Independent actual-sandbox transport controls; invented observations only.

The real viewer state machine, replay and collection execute. Only packet
observations and rasterization are replaced with explicitly generated fixtures.
No authentic signal, private target, model, scientific renderer or API is used.
"""
from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("neural034_independent_transport", HERE / "transport.py")
t = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = t
SPEC.loader.exec_module(t)
FRAMEWORK = Path("/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=")
CAP = 8 * 1024 * 1024
WRITTEN = 0


def pins():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("transport.py", "SOURCE_BINDINGS.json", "scripted_client.py")}


START_PINS = pins()


def charge_tree(path):
    """Charge every completed run once, before any evidence mutation/deletion."""
    global WRITTEN
    WRITTEN += sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())
    if WRITTEN > CAP:
        raise RuntimeError("Generated controls exceeded allocated known-byte ceiling")


def write(path, body):
    global WRITTEN
    if isinstance(body, str):
        body = body.encode()
    if WRITTEN + len(body) > CAP:
        raise RuntimeError("Generated control write would exceed allocated ceiling")
    path.write_bytes(body)
    WRITTEN += len(body)


class GeneratedPacket:
    def __init__(self, fold, ids, path):
        self.fold, self.ids, self.path = fold, list(ids), Path(path)
        self.pin = {"bytes": 0, "sha256": hashlib.sha256(f"generated-no-arrays-fold-{fold}".encode()).hexdigest()}

    def observation(self, role, index):
        if role not in ("training", "query") or type(index) is not int or not 0 <= index < (120 if role == "training" else 20):
            raise ValueError("Generated observation outside complete active fold")
        result = {"generated_only": True, "role": role, "index": index}
        if role == "training":
            result["label"] = index % 2
        return result


class GeneratedRenderer:
    calls = 0

    @staticmethod
    def render(observation, gain, raster):
        if observation.get("generated_only") is not True:
            raise AssertionError("Only generated observation fixture permitted")
        GeneratedRenderer.calls += 1
        return PNG, []


CLIENT_HELPER = r'''
import json, os, struct, sys
PREFIX = struct.Struct("!II")
def exact(n):
    out = bytearray()
    while len(out) < n:
        part = sys.stdin.buffer.read(n-len(out))
        if not part: raise EOFError("Truncated frame")
        out.extend(part)
    return bytes(out)
def receive():
    hs, ps = PREFIX.unpack(exact(8))
    assert 0 < hs <= 32768 and 0 <= ps <= 4*1024*1024
    return json.loads(exact(hs)), exact(ps)
def send(value):
    body = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    sys.stdout.buffer.write(PREFIX.pack(len(body),0)+body); sys.stdout.buffer.flush()
def complete():
    header, image = receive()
    assert header["training_windows"] == 120 and header["query_windows"] == 20 and not image
    for index in range(20):
        send({"action":"query","index":index}); view, png = receive()
        assert png.startswith(b"\x89PNG\r\n\x1a\n") and "context_label" not in view
        send({"action":"respond","query_id":view["query_id"],"probability":0.5}); response,_ = receive()
        assert response["kind"] == "response_accepted"
    send({"action":"finish"}); response,_ = receive()
    assert response["kind"] == "complete"
'''


class TransportControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin" or not FRAMEWORK.is_file() or not Path("/usr/bin/sandbox-exec").is_file():
            raise RuntimeError("These boundary controls require the admitted installed macOS framework runtime")
        cls.root = Path(tempfile.mkdtemp(prefix="neural034-independent-", dir=os.environ.get("NEURAL034_CONTROL_TMP"))).resolve()
        if os.environ.get("NEURAL034_RETAIN_CONTROLS") != "1":
            cls.addClassCleanup(shutil.rmtree, cls.root)
        cls.counter = 0
        cls.raster, cls.renderer, cls.input_rows, cls.ids = t.v.dependencies()
        cls.packets = [GeneratedPacket(fold, cls.ids[fold], cls.root / f"generated-fold-{fold:02d}.npz") for fold in range(7)]
        cls.sentinels = [cls.root / name for name in ("generated-raw-packet.txt", "generated-private-target.txt", "generated-other-fold.txt")]
        for path in cls.sentinels:
            write(path, "generated operator-only sentinel; not neuroscience data\n")
        cls.forbidden_write = cls.root / "forbidden-write.txt"
        cls.sessions, cls.results, cls.spawned = [], [], []
        source_fd = os.open(cls.sentinels[0], os.O_RDONLY)
        # The sentinel fd is deliberately inheritable; Popen close_fds must
        # remove it, independently of the candidate's filesystem policy.
        os.set_inheritable(source_fd, True)
        probes = f'''
import ctypes, os, socket, subprocess
assert 'NEURAL034_OPERATOR_SECRET' not in os.environ
assert not os.listdir('.'), 'Writable state carried across folds'
try: open('fresh-marker.txt','w').write('forbidden')
except PermissionError: pass
else: raise AssertionError('Participant filesystem write allowed')
for path in {list(map(str, cls.sentinels))!r}:
    try: open(path,'rb').read()
    except PermissionError: pass
    else: raise AssertionError('Operator/other-fold path became readable')
try: open({str(cls.forbidden_write)!r},'w').write('forbidden')
except PermissionError: pass
else: raise AssertionError('Write outside active workspace allowed')
try: inherited = os.read({source_fd},256)
except OSError: pass
else: assert b'operator-only sentinel' not in inherited, 'Private fd inherited'
libc=ctypes.CDLL(None,use_errno=True)
mib=(ctypes.c_int*3)(1,49,os.getppid()); size=ctypes.c_size_t(65536); memory=ctypes.create_string_buffer(size.value)
assert libc.sysctl(mib,3,memory,ctypes.byref(size),None,0)==-1 and ctypes.get_errno()==1
try: socket.socket().connect(('127.0.0.1',9))
except PermissionError: pass
else: raise AssertionError('Network access allowed')
try: subprocess.run(['/bin/echo','forbidden'],check=True)
except PermissionError: pass
else: raise AssertionError('Child creation allowed')
'''
        cls.complete_client = cls.root / "complete-boundary-client.py"
        write(cls.complete_client, probes + "\n" + (HERE / "scripted_client.py").read_text())
        real_popen = t.subprocess.Popen
        def capture(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            cls.spawned.append({"pid": child.pid, "cwd": kwargs.get("cwd"), "env": kwargs.get("env"),
                                "close_fds": kwargs.get("close_fds"), "start_new_session": kwargs.get("start_new_session")})
            return child
        try:
            with cls.dependencies(), patch.dict(os.environ, {"NEURAL034_OPERATOR_SECRET": "generated-private-value"}), \
                    patch.object(t.subprocess, "Popen", side_effect=capture):
                for packet in cls.packets:
                    path = cls.root / f"complete-fold-{packet.fold:02d}"
                    result = t.run_fold(packet, path, cls.complete_client, python=FRAMEWORK,
                                        sandbox="macos", limits=cls.limits())
                    charge_tree(path)
                    cls.sessions.append(path)
                    cls.results.append(result)
                    if result["status"] != "complete_unscored":
                        raise AssertionError(f"Actual sandbox full-fold control failed: {result}")
        finally:
            os.close(source_fd)
        cls.initial_renderer_calls = GeneratedRenderer.calls

    @classmethod
    def tearDownClass(cls):
        end = pins()
        print(json.dumps({"generated_known_bytes_written": WRITTEN, "allocation_bytes": CAP,
                          "actual_sandbox_fold_processes": len(cls.sessions), "authentic_payloads_read": 0,
                          "model_calls": 0, "scientific_renders": 0, "source_start_sha256": START_PINS,
                          "source_end_sha256": end, "framework_python": str(FRAMEWORK),
                          "generated_evidence_root": str(cls.root),
                          "retain_evidence": os.environ.get("NEURAL034_RETAIN_CONTROLS") == "1",
                          "participant_filesystem_writes_permitted": False,
                          "initial_fixture_png_calls": cls.initial_renderer_calls,
                          "all_fixture_png_calls": GeneratedRenderer.calls}, sort_keys=True))
        if end != START_PINS:
            raise RuntimeError("Source changed during independent controls")

    @classmethod
    def limits(cls, **changes):
        fields = dict(max_actions=180, max_images=150, max_output_bytes=16*1024*1024, wall_seconds=12)
        fields.update(changes)
        return t.Limits(**fields)

    @classmethod
    @contextlib.contextmanager
    def dependencies(cls):
        rows = dict(cls.input_rows)
        rows.update({f"fold-{p.fold:02d}": p.pin for p in cls.packets})
        with patch.object(t.v, "dependencies", return_value=(None, GeneratedRenderer, rows, cls.ids)):
            yield

    def run_client(self, script="complete()", *, limits=None, sandbox="macos"):
        type(self).counter += 1
        number = self.counter
        client = self.root / f"control-client-{number}.py"
        write(client, CLIENT_HELPER + "\n" + script)
        output = self.root / f"control-run-{number}"
        with self.dependencies():
            result = t.run_fold(self.packets[0], output, client, python=FRAMEWORK,
                                sandbox=sandbox, limits=limits or self.limits())
        charge_tree(output)
        return output, result

    def assert_failed(self, output, result):
        self.assertEqual(result["status"], "failed")
        self.assertTrue((output / "failure.json").is_file())
        with self.dependencies(), self.assertRaises((ValueError, OSError)):
            t.audit_transport(output, self.packets[0])

    def test_full_seven_actual_sandbox_folds_and_fresh_state(self):
        self.assertEqual(self.initial_renderer_calls, 980)
        self.assertEqual(len(self.spawned), 7)
        self.assertEqual(len({row["pid"] for row in self.spawned}), 7)
        self.assertEqual(len({str(row["cwd"]) for row in self.spawned}), 7)
        self.assertFalse(self.forbidden_write.exists())
        episodes = []
        for path, result, packet, child in zip(self.sessions, self.results, self.packets, self.spawned):
            self.assertEqual((result["actions"], result["images"]), (161, 140))
            self.assertEqual(result["client_exit_code"], 0)
            self.assertFalse(result["forced_stop"])
            self.assertTrue(child["close_fds"] and child["start_new_session"])
            self.assertEqual(child["env"], {"LANG": "C", "LC_ALL": "C"})
            self.assertFalse(Path(child["cwd"]).exists())
            with self.dependencies():
                audited = t.audit_transport(path, packet)
            boundary = audited["boundary"]
            episodes.append(boundary["episode_id"])
            self.assertEqual(boundary["sandbox"], "macos")
            self.assertEqual(boundary["workspace_policy"], "empty_read_only")
            self.assertIs(boundary["workspace_initially_empty"], True)
            self.assertIs(boundary["fresh_process_per_fold"], True)
            self.assertIs(result["workspace_destroyed"], True)
            self.assertFalse(boundary["provider_context_qualified"])
            self.assertFalse(boundary["scientific_qualification"])
            with self.assertRaises(ProcessLookupError):
                os.killpg(child["pid"], 0)
        self.assertEqual(len(set(episodes)), 7)

    def test_public_wire_contains_images_and_only_active_labels(self):
        output = self.sessions[0]
        raw = (output / "transport/wire.bin").read_bytes()
        rows = [json.loads(line) for line in (output / "transport/journal.jsonl").read_bytes().splitlines()]
        training, queries = [], []
        for row in rows:
            if row["direction"] != "out":
                continue
            body = raw[row["offset"]:row["offset"] + row["bytes"]]
            header, image = t.unpack(body)
            self.assertNotIn(str(self.root).encode(), body)
            for key in ("packet", "source", "path", "targets", "raw", "fold", "training_labels"):
                self.assertNotIn(key, header)
            if header["kind"] == "view":
                self.assertEqual(image, PNG)
                self.assertNotIn("base64", header["image"])
                self.assertEqual((header["samples"], header["cells"]), (300, 12))
                if header["role"] == "training":
                    training.append(header["index"])
                    self.assertEqual(header["context_label"], header["index"] % 2)
                else:
                    queries.append(header["query_id"])
                    self.assertNotIn("context_label", header)
        self.assertEqual(training, list(range(120)))
        self.assertEqual(queries, self.ids[0])
        for other in range(1, 7):
            for query in self.ids[other]:
                self.assertNotIn(query.encode(), raw)

    def test_actual_complete_collector_preserves_all_140_query_identities(self):
        output = self.root / "complete-collection"
        before = GeneratedRenderer.calls
        with self.dependencies(), patch.object(t.v, "collect", side_effect=AssertionError("Unexpected third renderer replay")):
            result = t.collect(self.packets, self.sessions, output)
        self.assertEqual(GeneratedRenderer.calls - before, 1960)
        charge_tree(output)
        self.assertFalse(result["scientific_qualification"])
        body = json.loads((output / "probabilities.json").read_bytes())
        self.assertEqual(body, {"schema_version": 1, "probabilities": [
            {"fold": fold, "query_id": query, "probability": .5} for fold in range(7) for query in self.ids[fold]]})

    def test_frame_length_duplicate_json_and_nonfinite_refusals(self):
        frames = [b"", b"abc", struct.pack("!II", 2**32-1, 0), struct.pack("!II", 0, 0),
                  struct.pack("!II", 2, 1) + b"{}x", struct.pack("!II", 2, 0) + b"{}extra"]
        for raw in frames:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                t.unpack(raw, inbound=True)
        for body in (b'{"action":"inspect","action":"finish"}', b'{"action":"respond","probability":NaN}'):
            output, result = self.run_client("receive()\nbody=" + repr(body) + "\nsys.stdout.buffer.write(PREFIX.pack(len(body),0)+body);sys.stdout.buffer.flush()")
            self.assert_failed(output, result)

    def test_invalid_action_cross_fold_and_first_final_answers_refused(self):
        requests = [{"action": "read_file", "path": str(self.sentinels[0])}, {"action": "query", "index": True},
                    {"action": "training", "index": 120}, {"action": "inspect", "fold": 1}, {"action": "finish"}]
        for request in requests:
            with self.subTest(request=request):
                output, result = self.run_client("receive()\nsend(" + repr(request) + ")")
                self.assert_failed(output, result)
        for query, probability, duplicate in ((self.ids[1][0], .5, False), (None, True, False), (None, .5, True)):
            script = "receive()\nsend({'action':'query','index':0});view,_=receive()\n"
            script += "send({'action':'respond','query_id':" + (repr(query) if query else "view['query_id']") + ",'probability':" + repr(probability) + "})\n"
            if duplicate:
                script += "receive()\nsend({'action':'respond','query_id':view['query_id'],'probability':1.0})\n"
            output, result = self.run_client(script)
            self.assert_failed(output, result)
            if duplicate:
                rows = [json.loads(line) for line in (output / "viewer/actions.jsonl").read_bytes().splitlines()]
                responses = [r["request"] for r in rows if r["request"]["action"] == "respond"]
                self.assertEqual(len(responses), 1)
                self.assertEqual(responses[0]["probability"], .5)

    def test_limits_require_complete_access_and_refuse_invalid_types(self):
        for change in (dict(max_actions=True), dict(max_actions=160), dict(max_images=139),
                       dict(max_images=True), dict(max_output_bytes=0), dict(wall_seconds=0),
                       dict(wall_seconds=float("nan")), dict(wall_seconds=float("inf"))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.limits(**change).validate()

    def test_deadline_eof_and_nonzero_completion_fail_closed(self):
        for script, limit in (("receive()", self.limits()),
                              ("receive()\nimport time\ntime.sleep(3)", self.limits(wall_seconds=.3)),
                              ("complete()\nraise RuntimeError('after finish')", self.limits())):
            output, result = self.run_client(script, limits=limit)
            self.assert_failed(output, result)
            if "sleep(3)" in script:
                self.assertTrue(result["forced_stop"])
                self.assertNotEqual(result["client_exit_code"], 0)

    def test_live_action_image_and_output_budgets_fail_without_partial_success(self):
        cases = [
            ("receive()\nfor i in range(141):\n send({'action':'inspect'});receive()",
             self.limits(max_images=140)),
            ("receive()\nfor i in range(121):\n send({'action':'training','index':i%120});receive()\n"
             "for i in range(20):\n send({'action':'query','index':i});view,_=receive()\n"
             " send({'action':'respond','query_id':view['query_id'],'probability':0.5});receive()\n"
             "send({'action':'finish'})", self.limits(max_actions=161)),
            ("receive()\nsend({'action':'inspect'})",
             self.limits(max_output_bytes=t.PNG_MAX+t.HEADER_MAX+t.PREFIX.size+t.RESERVE)),
        ]
        for script, limits in cases:
            with self.subTest(limits=limits):
                output, result = self.run_client(script, limits=limits)
                self.assert_failed(output, result)

    def test_protocol_only_success_cannot_enter_restricted_collector(self):
        output, result = self.run_client(sandbox="protocol_only")
        self.assertEqual(result["status"], "complete_unscored")
        sessions = [output, *self.sessions[1:]]
        with self.dependencies(), self.assertRaises(ValueError):
            t.collect(self.packets, sessions, self.root / "diagnostic-not-collectable")

    def test_collection_refuses_missing_duplicate_and_wrong_order(self):
        for packets, sessions in ((self.packets[:-1], self.sessions[:-1]),
                                  (self.packets[::-1], self.sessions),
                                  (self.packets, [self.sessions[0]] * 7)):
            with self.subTest(folds=[p.fold for p in packets]), self.dependencies(), self.assertRaises(ValueError):
                t.collect(packets, sessions, self.root / "invalid-collection")

    def test_wire_and_viewer_history_changes_are_refused(self):
        output, result = self.run_client()
        self.assertEqual(result["status"], "complete_unscored")
        wire = output / "transport/wire.bin"
        original = wire.read_bytes()
        write(wire, original[:-1] + bytes([original[-1] ^ 1]))
        with self.dependencies(), self.assertRaises(ValueError):
            t.audit_transport(output, self.packets[0])
        write(wire, original)
        journal = output / "viewer/actions.jsonl"
        original = journal.read_bytes()
        rows = [json.loads(line) for line in original.splitlines()]
        rows[1]["request"]["probability"] = .75
        write(journal, b"".join(t.encode(row) for row in rows))
        with self.dependencies(), self.assertRaises(ValueError):
            t.audit_transport(output, self.packets[0])

    def test_boundary_profile_client_and_false_qualification_mutations_refused(self):
        output, result = self.run_client()
        self.assertEqual(result["status"], "complete_unscored")
        boundary = output / "BOUNDARY.json"
        original = boundary.read_bytes()
        for field, value in (("source", {}), ("client_sha256", "0"*64), ("profile_sha256", "0"*64),
                             ("scientific_qualification", True), ("provider_context_qualified", True)):
            with self.subTest(field=field):
                changed = json.loads(original)
                changed[field] = value
                write(boundary, t.encode(changed))
                with self.dependencies(), self.assertRaises(ValueError):
                    t.audit_transport(output, self.packets[0])
        write(boundary, original)
        client = output / "client.py"
        write(client, client.read_bytes() + b"\n# postcapture mutation\n")
        with self.dependencies(), self.assertRaises(ValueError):
            t.audit_transport(output, self.packets[0])


class TrailingFrameControl(unittest.TestCase):
    def test_extra_framed_output_after_finish_is_captured_and_refused(self):
        """Exercise the new postfinish branch without replaying seven folds."""
        root = Path(tempfile.mkdtemp(prefix="neural034-trailing-", dir=os.environ.get("NEURAL034_CONTROL_TMP"))).resolve()
        if os.environ.get("NEURAL034_RETAIN_CONTROLS") != "1":
            self.addCleanup(shutil.rmtree, root)
        _, _, rows, ids = t.v.dependencies()
        packet = GeneratedPacket(0, ids[0], root / "generated-packet.npz")
        rows = dict(rows)
        rows["fold-00"] = packet.pin
        client = root / "trailing-client.py"
        write(client, CLIENT_HELPER + "\ncomplete()\nsend({'action':'finish'})\n")
        output = root / "attempt"
        before = WRITTEN
        try:
            with patch.object(t.v, "dependencies", return_value=(None, GeneratedRenderer, rows, ids)):
                result = t.run_fold(packet, output, client, python=FRAMEWORK, sandbox="macos",
                                    limits=t.Limits(180, 150, 16*1024*1024, 12))
                charge_tree(output)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["reason"]["message"], "output_after_finish")
                self.assertEqual(result["client_exit_code"], 0)
                self.assertEqual(result["process_group_cleanup"], "absent")
                self.assertIs(result["workspace_destroyed"], True)
                self.assertFalse((output / "viewer/completion.json").exists())
                self.assertTrue((output / "viewer/failure.json").is_file())
                journal = [json.loads(line) for line in (output / "transport/journal.jsonl").read_bytes().splitlines()]
                last = journal[-1]
                self.assertEqual(last["direction"], "in")
                self.assertIs(last["complete"], False)
                wire = (output / "transport/wire.bin").read_bytes()
                self.assertEqual(t.unpack(wire[last["offset"]:], inbound=True), ({"action": "finish"}, b""))
                with self.assertRaisesRegex(ValueError, "Failed transport"):
                    t.audit_transport(output, packet)
        finally:
            print(json.dumps({"targeted_branch": "extra_output_after_finish", "generated_evidence_root": str(root),
                              "generated_known_bytes_written_total_this_process": WRITTEN,
                              "generated_attempt_bytes": WRITTEN-before, "source_start_sha256": START_PINS,
                              "source_end_sha256": pins(), "authentic_payloads_read": 0}, sort_keys=True))
        self.assertEqual(pins(), START_PINS)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Portable generated protocol controls; no sandbox/isolation qualification.

Runs without macOS, without skipping security tests, and without pretending the
diagnostic process has a filesystem boundary. Actual sandbox controls are the
separate test_transport.py command and are never invoked from this suite.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HELPER = HERE / "test_transport.py"
HELPER_SHA256 = "d6447b194db5d2efa2170c114c459c858a58fe1204289de9165a1fa1ff9c8e9a"
if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA256:
    raise RuntimeError("Independent generated helper source changed")
SPEC = importlib.util.spec_from_file_location("neural034_portable_fixture_definitions", HELPER)
F = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = F
SPEC.loader.exec_module(F)
t = F.t


class PortableProtocolControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="neural034-portable-", dir=os.environ.get("NEURAL034_CONTROL_TMP"))).resolve()
        if os.environ.get("NEURAL034_RETAIN_CONTROLS") != "1":
            cls.addClassCleanup(shutil.rmtree, cls.root)
        _, _, cls.rows, cls.ids = t.v.dependencies()
        cls.packets = [F.GeneratedPacket(fold, cls.ids[fold], cls.root / f"invented-{fold}.npz") for fold in range(7)]
        cls.rows = dict(cls.rows)
        cls.rows.update({f"fold-{p.fold:02d}": p.pin for p in cls.packets})
        cls.client = cls.root / "diagnostic-client.py"
        F.write(cls.client, F.CLIENT_HELPER + "\ncomplete()\n")
        cls.sessions, cls.results = [], []
        cls.counter = 0
        with cls.dependencies():
            for packet in cls.packets:
                output = cls.root / f"diagnostic-fold-{packet.fold}"
                result = t.run_fold(packet, output, cls.client, python=sys.executable,
                                    sandbox="protocol_only", limits=cls.limits())
                F.charge_tree(output)
                cls.sessions.append(output)
                cls.results.append(result)
                if result["status"] != "complete_unscored":
                    raise AssertionError(f"Generated diagnostic failed: {result}")

    @classmethod
    @contextlib.contextmanager
    def dependencies(cls):
        with patch.object(t.v, "dependencies", return_value=(None, F.GeneratedRenderer, cls.rows, cls.ids)):
            yield

    @staticmethod
    def limits():
        return t.Limits(180, 150, 16 * 1024 * 1024, 10)

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({"portable_methods": 5, "actual_sandbox_tests_executed": 0,
                          "sandbox_simulated": False, "diagnostic_full_fold_processes": 7,
                          "generated_evidence_root": str(cls.root), "known_fixture_bytes_written": F.WRITTEN,
                          "fixture_png_calls": F.GeneratedRenderer.calls, "authentic_payloads_read": 0,
                          "source_start_sha256": F.START_PINS, "source_end_sha256": F.pins(),
                          "helper_sha256": HELPER_SHA256, "python": sys.version}, sort_keys=True))
        if F.pins() != F.START_PINS:
            raise RuntimeError("Production source changed during portable controls")

    def test_strict_binary_json_framing_preserves_exact_png(self):
        header = {"kind": "view", "image": {"mime_type": "image/png", "bytes": len(F.PNG)}}
        self.assertEqual(t.unpack(t.wire(header, F.PNG)), (header, F.PNG))
        self.assertEqual(t.unpack(t.wire({"action": "inspect"}), inbound=True), ({"action": "inspect"}, b""))
        for raw in (b"", b"broken", struct.pack("!II", 0, 0), struct.pack("!II", 2**32-1, 0),
                    struct.pack("!II", 2, 1) + b"{}x", struct.pack("!II", 2, 0) + b"{}trailer"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                t.unpack(raw, inbound=True)
        for body in (b'{"action":"inspect","action":"finish"}', b'{"v":NaN}', b'\xff'):
            with self.subTest(body=body), self.assertRaises((ValueError, UnicodeError)):
                t.unpack(struct.pack("!II", len(body), 0) + body, inbound=True)

    def test_view_projection_is_role_specific_and_rejects_hidden_fields(self):
        session = t.v.Session(self.packets[0], 180, None, F.GeneratedRenderer)
        training = session.handle({"action": "training", "index": 119})
        query = session.handle({"action": "query", "index": 19})
        train_header, train_png = t.projection(training)
        query_header, query_png = t.projection(query)
        self.assertEqual((train_png, query_png), (F.PNG, F.PNG))
        self.assertEqual(train_header["context_label"], 1)
        self.assertNotIn("context_label", query_header)
        self.assertNotIn("base64", query_header["image"])
        self.assertEqual(query_header["query_id"], self.ids[0][19])
        for field, value in (("context_label", 0), ("targets", [0, 1]), ("source_path", "/invented/private"),
                             ("raw_windows", []), ("fold", 1)):
            with self.subTest(field=field):
                changed = copy.deepcopy(query)
                changed[field] = value
                with self.assertRaises(ValueError):
                    t.projection(changed)
        changed = copy.deepcopy(query)
        changed["image"]["path"] = "/invented/image"
        with self.assertRaises(ValueError):
            t.projection(changed)

    def test_live_diagnostic_completion_replays_without_isolation_claim(self):
        for result in self.results:
            self.assertEqual((result["actions"], result["images"]), (41, 20))
            self.assertEqual(result["client_exit_code"], 0)
            self.assertIs(result["scientific_qualification"], False)
            self.assertIs(result["provider_context_qualified"], False)
        with self.dependencies():
            audited = t.audit_transport(self.sessions[0], self.packets[0])
        self.assertEqual(audited["boundary"]["sandbox"], "protocol_only")
        self.assertEqual(audited["answers"], dict.fromkeys(self.ids[0], .5))
        self.assertIs(audited["boundary"]["scientific_qualification"], False)
        self.assertFalse((self.sessions[0] / "sandbox.sb").exists())

    def test_first_final_and_terminal_failures_remain_failed_histories(self):
        scripts = ["receive()\nsend({'action':'finish'})",
                   "receive()\nsend({'action':'query','index':0});view,_=receive()\n"
                   "send({'action':'respond','query_id':view['query_id'],'probability':.5});receive()\n"
                   "send({'action':'respond','query_id':view['query_id'],'probability':1.0})",
                   "complete()\nsend({'action':'finish'})"]
        for index, script in enumerate(scripts):
            with self.subTest(index=index):
                client = self.root / f"invalid-client-{index}.py"
                F.write(client, F.CLIENT_HELPER + "\n" + script)
                output = self.root / f"invalid-attempt-{index}"
                with self.dependencies():
                    result = t.run_fold(self.packets[0], output, client, python=sys.executable,
                                        sandbox="protocol_only", limits=self.limits())
                    F.charge_tree(output)
                    self.assertEqual(result["status"], "failed")
                    self.assertFalse((output / "viewer/completion.json").exists())
                    with self.assertRaisesRegex(ValueError, "Failed transport"):
                        t.audit_transport(output, self.packets[0])
                if index == 1:
                    rows = [json.loads(line) for line in (output / "viewer/actions.jsonl").read_bytes().splitlines()]
                    answers = [row["request"] for row in rows if row["request"]["action"] == "respond"]
                    self.assertEqual(len(answers), 1)
                    self.assertEqual(answers[0]["probability"], .5)

    def test_seven_homogeneous_diagnostic_folds_never_collect_as_restricted(self):
        output = self.root / "must-not-exist"
        with self.dependencies(), self.assertRaisesRegex(ValueError, "Restricted collection rejects protocol-only"):
            t.collect(self.packets, self.sessions, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

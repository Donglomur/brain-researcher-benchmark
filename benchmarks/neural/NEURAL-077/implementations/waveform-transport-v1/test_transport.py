"""Independent generated controls for complete numerical-waveform transport.

All observations, responses and targets in this file are invented software
fixtures. Tests perform no authentic-data read, model call, fit or scoring.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
PREFIX = struct.Struct("!I")


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


t = module(HERE / "transport.py", "independent_waveform_transport")
d = module(HERE.parent / "complete-direct-condition-v1/delivery.py", "independent_existing_delivery")

HELPER = '''import json, os, struct, sys, time
P = struct.Struct("!I")
def exact(n):
    out = bytearray()
    while len(out) < n:
        part = sys.stdin.buffer.read(n-len(out))
        if not part: raise RuntimeError("input ended")
        out.extend(part)
    return bytes(out)
def receive():
    return exact(P.unpack(exact(4))[0]).decode("utf-8")
def send(body):
    if isinstance(body, str): body = body.encode("utf-8")
    sys.stdout.buffer.write(P.pack(len(body)) + body)
    sys.stdout.buffer.flush()
'''


def wire(body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return PREFIX.pack(len(body)) + body


def fixture_members():
    ids = [f"{case}-{i:024x}" for case in d.CASES for i in range(200)]
    members = {
        "manifest.json": d.encoded({"development_ids": ids, "query_count": 400,
                                    "demonstration_count": 4, "natural_class_prior_supplied": False}),
        "queries.jsonl": b"".join(d.encoded({"trial_id": name, "channels": [[0], [1]]}) for name in ids),
        "demonstrations.json": b'[{"generated":true}]\n',
        "prompt.txt": (d.NO_TOOLS + "\n{{demonstrations_json}}\n{{query_json}}\n").encode(),
        "response_schema.json": b"{}\n",
    }
    return members


class EpisodeControls(unittest.TestCase):
    retained_fixture_bytes = 0
    ephemeral_client_state_bytes = 0

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="generated-neural077-waveform-")
        self.root = Path(self.temp.name).resolve()
        self.row = {"ordinal": 0, "trial_id": "development-001-" + "0" * 24,
                    "prompt": "Generated query: development-001-" + "0" * 24 + "\n"}
        self.row["context_sha256"] = hashlib.sha256(self.row["prompt"].encode()).hexdigest()
        self.answer = json.dumps({"trial_id": self.row["trial_id"], "target_probability": 0.25})
        self.serial = 0
        self.python = sys.executable

    def tearDown(self):
        type(self).retained_fixture_bytes += sum(p.stat().st_size for p in self.root.rglob("*")
                                                if p.is_file() and not p.is_symlink())
        self.temp.cleanup()

    @classmethod
    def tearDownClass(cls):
        print("GENERATED_EPISODE_FIXTURE_ACCOUNTING " + json.dumps({
            "retained_bytes_before_each_cleanup": cls.retained_fixture_bytes,
            "known_ephemeral_client_state_bytes": cls.ephemeral_client_state_bytes,
            "unmeasured_filesystem_or_process_overhead": "unknown"}))

    def client(self, source):
        self.serial += 1
        path = self.root / f"client-{self.serial}.py"
        path.write_text(HELPER + "\n" + source)
        return path

    def run_client(self, source, *, row=None, condition="legacy_waveform_no_tools", limits=None, sandbox="protocol_only"):
        client = self.client(source)
        output = self.root / f"episode-{self.serial}"
        envelope, receipt = t.run_episode(row or self.row, condition, output, client,
                                          self.python, sandbox=sandbox, limits=limits)
        return output, envelope, receipt

    def test_exact_prompt_first_response_and_minimal_environment(self):
        source = (f"prompt = receive()\nassert prompt == {self.row['prompt']!r}\n"
                  "assert os.listdir('.') == []\nassert 'NEURAL077_GENERATED_SECRET' not in os.environ\n"
                  f"send({self.answer!r})\n")
        with mock.patch.dict(os.environ, {"NEURAL077_GENERATED_SECRET": "must-not-reach-client"}):
            output, envelope, receipt = self.run_client(source)
        self.assertEqual(envelope, {"ordinal": 0, "trial_id": self.row["trial_id"],
                                   "context_sha256": self.row["context_sha256"],
                                   "status": "ok", "response": self.answer, "error": None})
        self.assertEqual((output / "INPUT.bin").read_bytes(), wire(self.row["prompt"]))
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), wire(self.answer))
        self.assertEqual(json.loads((output / "ATTEMPT.json").read_text()), envelope)
        self.assertEqual(json.loads((output / "END.json").read_text()), receipt)

    def test_first_final_cannot_be_replaced(self):
        second = json.dumps({"trial_id": self.row["trial_id"], "target_probability": 0.9})
        raw = wire(self.answer) + wire(second)
        output, envelope, _ = self.run_client(f"receive()\nsys.stdout.buffer.write({raw!r}); sys.stdout.buffer.flush()\n")
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual(envelope["response"], self.answer)
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), wire(self.answer))

    def test_each_query_starts_with_no_previous_working_state(self):
        client = self.client("""prompt = receive()
assert not os.path.exists('prior-query-state')
with open('prior-query-state', 'w') as stream: stream.write('generated')
identifier = prompt.strip().split()[-1]
send(json.dumps({'trial_id': identifier, 'target_probability': 0.25}))
""")
        for ordinal in (0, 1):
            row = dict(self.row, ordinal=ordinal,
                       trial_id="development-001-" + f"{ordinal:024x}")
            row["prompt"] = "Generated query: " + row["trial_id"] + "\n"
            row["context_sha256"] = hashlib.sha256(row["prompt"].encode()).hexdigest()
            envelope, _ = t.run_episode(row, "legacy_waveform_no_tools",
                                        self.root / f"fresh-{ordinal}", client, self.python,
                                        sandbox="protocol_only")
            self.assertEqual(envelope["status"], "ok")
            type(self).ephemeral_client_state_bytes += len("generated")

    def test_invalid_first_final_stays_invalid_after_valid_second(self):
        invalid = '{"trial_id":"wrong","target_probability":0.9}'
        raw = wire(invalid) + wire(self.answer)
        output, envelope, _ = self.run_client(f"receive()\nsys.stdout.buffer.write({raw!r}); sys.stdout.buffer.flush()\n")
        self.assertEqual(envelope["status"], "error")
        self.assertIsNone(envelope["response"])
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), wire(invalid))

    def test_original_response_rules_on_real_child_output(self):
        wrongs = [
            b"\xff",
            b"{}",
            json.dumps({"trial_id": self.row["trial_id"], "target_probability": True}).encode(),
            json.dumps({"trial_id": self.row["trial_id"], "target_probability": 1.01}).encode(),
            ('{"trial_id":' + json.dumps(self.row["trial_id"]) + ',"target_probability":NaN}').encode(),
            ('{"trial_id":' + json.dumps(self.row["trial_id"]) + ',"target_probability":0.2,"target_probability":0.3}').encode(),
            json.dumps({"trial_id": self.row["trial_id"], "target_probability": 0.2, "extra": 1}).encode(),
        ]
        for bad in wrongs:
            with self.subTest(body=bad):
                output, envelope, _ = self.run_client(f"receive()\nsend({bad!r})\n")
                self.assertEqual(envelope["status"], "error")
                self.assertEqual((output / "OUTPUT.bin").read_bytes(), wire(bad))

    def test_oversized_response_is_refused_from_header(self):
        output, envelope, _ = self.run_client("receive()\nsys.stdout.buffer.write(P.pack(2**32-1)); sys.stdout.buffer.flush()\ntime.sleep(.1)\n")
        self.assertEqual(envelope["status"], "error")
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), PREFIX.pack(2**32 - 1))

    def test_truncated_response_preserves_only_observed_bytes(self):
        partial = PREFIX.pack(50) + b"short"
        output, envelope, _ = self.run_client(f"receive()\nsys.stdout.buffer.write({partial!r}); sys.stdout.buffer.flush()\n")
        self.assertEqual(envelope["status"], "error")
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), partial)

    def test_post_final_nonzero_exit_refuses_admission(self):
        output, envelope, _ = self.run_client(f"receive()\nsend({self.answer!r})\nsys.exit(7)\n")
        self.assertEqual(envelope["status"], "error")
        self.assertIsNone(envelope["response"])
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), wire(self.answer))

    def test_no_response_deadline_and_owned_cleanup(self):
        output, envelope, receipt = self.run_client("receive()\ntime.sleep(5)\n",
                                                    limits=t.Limits(wall_seconds=.1))
        self.assertEqual(envelope["status"], "error")
        self.assertIsNone(envelope["response"])
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), b"")

    def test_expired_campaign_deadline_records_without_launch(self):
        client = self.client("raise RuntimeError('must never execute')")
        output = self.root / "expired"
        limits = t.Limits()
        _, python, config = t.configuration(client, self.python, "protocol_only", limits)
        with mock.patch.object(t.subprocess, "Popen", side_effect=AssertionError("child launch prohibited")):
            envelope, receipt = t._episode(self.row, "legacy_waveform_no_tools", output,
                                           client, python, "protocol_only", limits,
                                           config["client"], campaign_deadline=time.monotonic() - 1)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["error"], "campaign_deadline_not_started")
        self.assertIs(receipt["launched"], False)
        self.assertEqual((output / "INPUT.bin").read_bytes(), b"")
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), b"")

    def test_post_final_hang_is_not_success(self):
        output, envelope, _ = self.run_client(f"receive()\nsend({self.answer!r})\ntime.sleep(5)\n",
                                               limits=t.Limits(wall_seconds=1))
        self.assertEqual(envelope["status"], "error")
        self.assertEqual((output / "OUTPUT.bin").read_bytes(), wire(self.answer))

    def test_wrong_context_hash_refused_before_dispatch(self):
        bad = dict(self.row, context_sha256="0" * 64)
        with self.assertRaises((ValueError, OSError)):
            self.run_client("raise RuntimeError('must never execute')", row=bad)

    def test_existing_output_cannot_be_overwritten(self):
        client = self.client("raise RuntimeError('must not execute')")
        output = self.root / "occupied"
        output.mkdir()
        sentinel = output / "sentinel"
        sentinel.write_bytes(b"retain")
        with self.assertRaises((ValueError, FileExistsError)):
            t.run_episode(self.row, "legacy_waveform_no_tools", output, client, self.python,
                          sandbox="protocol_only")
        self.assertEqual(sentinel.read_bytes(), b"retain")

    def test_linked_client_refused(self):
        real = self.client(f"receive()\nsend({self.answer!r})\n")
        link = self.root / "client-link.py"
        link.symlink_to(real)
        with self.assertRaises((ValueError, OSError)):
            t.run_episode(self.row, "legacy_waveform_no_tools", self.root / "linked", link,
                          self.python, sandbox="protocol_only")

    def test_invalid_limits_are_not_silently_normalized(self):
        for values in ({"wall_seconds": True}, {"wall_seconds": 0}, {"wall_seconds": float("nan")},
                       {"wall_seconds": float("inf")}, {"max_prompt_bytes": True},
                       {"max_prompt_bytes": 0}, {"campaign_seconds": -1},
                       {"campaign_seconds": float("nan")}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                t.Limits(**values).validate()

    def test_oversized_prompt_refused_before_dispatch(self):
        with self.assertRaises((ValueError, OSError)):
            self.run_client("raise RuntimeError('must never execute')", limits=t.Limits(max_prompt_bytes=1))

    def test_only_existing_two_waveform_conditions_are_permitted(self):
        for condition in ("zero_shot", "ordinary_feature_programme", "tool_assisted_waveform", "unknown"):
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                self.run_client("raise RuntimeError('must never execute')", condition=condition)

    def test_matched_programme_receives_exact_declared_prompt(self):
        contexts = [list(d.context_rows(fixture_members(), c))[0] for c in d.CONDITIONS]
        self.assertEqual(contexts[0]["prompt"].replace(d.NO_TOOLS, d.PROGRAMME_TOOLS), contexts[1]["prompt"])
        source = f"assert receive() == {contexts[1]['prompt']!r}\nsend({json.dumps({'trial_id': contexts[1]['trial_id'], 'target_probability': 0.5})!r})\n"
        output, envelope, _ = self.run_client(source, row=contexts[1], condition=d.CONDITIONS[1])
        self.assertEqual(envelope["status"], "ok")
        self.assertEqual((output / "INPUT.bin").read_bytes(), wire(contexts[1]["prompt"]))


class CompleteCampaignControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="generated-neural077-complete-")
        cls.root = Path(cls.temp.name).resolve()
        cls.members = fixture_members()
        cls.modules = d.dependencies()
        cls.modules["exporter"].PINS = {
            name: (len(body), d.descriptor(body)["sha256"]) for name, body in cls.members.items()}
        cls.delivery = cls.root / "delivery"
        (cls.delivery / "public").mkdir(parents=True)
        for name, body in cls.members.items():
            (cls.delivery / "public" / name).write_bytes(body)
        cls.client = cls.root / "generated-client.py"
        cls.client.write_text(HELPER + '''
import re
prompt = receive()
identifier = re.search(r'development-00[12]-[0-9a-f]{24}', prompt).group()
send(json.dumps({'trial_id':identifier, 'target_probability':0.25}))
''')
        cls.campaign = cls.root / "campaign"
        cls.dependency_patch = mock.patch.object(t, "dependencies", return_value=(d, cls.modules["response"]))
        cls.delivery_patch = mock.patch.object(d, "dependencies", return_value=cls.modules)
        cls.dependency_patch.start()
        cls.delivery_patch.start()
        cls.serial = 0
        cls.rewritten_bytes = 0
        try:
            t.run_campaign(cls.delivery, d.CONDITIONS[0], cls.campaign, cls.client, sys.executable,
                           sandbox="protocol_only", limits=t.Limits(wall_seconds=2, campaign_seconds=150))
        except BaseException:
            cls.delivery_patch.stop()
            cls.dependency_patch.stop()
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.delivery_patch.stop()
        cls.dependency_patch.stop()
        retained = sum(p.stat().st_size for p in cls.root.rglob("*")
                       if p.is_file() and not p.is_symlink())
        print("GENERATED_CAMPAIGN_FIXTURE_ACCOUNTING " + json.dumps({
            "retained_bytes_before_cleanup": retained,
            "known_overwrite_and_restore_bytes": cls.rewritten_bytes,
            "known_logical_written_bytes_lower_bound": retained + cls.rewritten_bytes,
            "unmeasured_filesystem_or_process_overhead": "unknown"}))
        cls.temp.cleanup()

    def destination(self):
        type(self).serial += 1
        return self.root / f"collection-{self.serial}"

    def first_episode(self):
        paths = sorted(p for p in self.campaign.rglob("ATTEMPT.json") if p.is_file())
        self.assertEqual(len(paths), 400)
        return paths[0].parent

    def test_complete400_actual_existing_collector_and_numpy(self):
        import numpy as np
        output = self.destination()
        t.collect(self.delivery, d.CONDITIONS[0], self.campaign, output)
        self.assertTrue((output / "TRANSPORT_COMPLETE.json").is_file())
        with np.load(output / "submission.npz", allow_pickle=False) as arrays:
            self.assertEqual(set(arrays.files), {"trial_ids", "target_probability"})
            expected = json.loads(self.members["manifest.json"])["development_ids"]
            self.assertEqual(arrays["trial_ids"].tolist(), expected)
            self.assertEqual(arrays["target_probability"].tolist(), [0.25] * 400)
        receipt = json.loads((output / "COMPLETE.json").read_text())
        self.assertEqual(receipt["responses"], 400)
        self.assertEqual(receipt["private_target_reads"], 0)
        self.assertIs(receipt["scoring_performed"], False)

    def test_other_condition_cannot_relabel_same_campaign(self):
        with self.assertRaises((ValueError, OSError)):
            t.collect(self.delivery, d.CONDITIONS[1], self.campaign, self.destination())

    def test_campaign_configuration_and_completion_counts_cannot_change(self):
        for name in ("MANIFEST.json", "COMPLETE.json"):
            path = self.campaign / name
            original = path.read_bytes()
            mode = path.stat().st_mode & 0o777
            value = json.loads(original)
            if name == "MANIFEST.json":
                value["configuration"]["sandbox"] = "undeclared"
            else:
                value["successful"] = 399
            changed = json.dumps(value).encode()
            try:
                path.chmod(0o600)
                path.write_bytes(changed)
                type(self).rewritten_bytes += len(changed)
                with self.subTest(member=name), self.assertRaises((ValueError, OSError)):
                    t.collect(self.delivery, d.CONDITIONS[0], self.campaign, self.destination())
            finally:
                path.write_bytes(original)
                type(self).rewritten_bytes += len(original)
                path.chmod(mode)

    def test_attempt_ledger_cannot_disagree_with_saved_first_responses(self):
        path = self.campaign / "attempts.jsonl"
        original = path.read_bytes()
        mode = path.stat().st_mode & 0o777
        changed = original.replace(b"0.25", b"0.75", 1)
        self.assertNotEqual(changed, original)
        try:
            path.chmod(0o600)
            path.write_bytes(changed)
            type(self).rewritten_bytes += len(changed)
            with self.assertRaises((ValueError, OSError)):
                t.collect(self.delivery, d.CONDITIONS[0], self.campaign, self.destination())
        finally:
            path.write_bytes(original)
            type(self).rewritten_bytes += len(original)
            path.chmod(mode)

    def test_all_bound_episode_evidence_tampering_refused(self):
        episode = self.first_episode()
        for filename in ("INPUT.bin", "OUTPUT.bin", "MANIFEST.json", "END.json", "ATTEMPT.json"):
            path = episode / filename
            original = path.read_bytes()
            mode = path.stat().st_mode & 0o777
            try:
                path.chmod(0o600)
                path.write_bytes(original + b" ")
                type(self).rewritten_bytes += len(original) + 1
                with self.subTest(member=filename), self.assertRaises((ValueError, OSError)):
                    t.collect(self.delivery, d.CONDITIONS[0], self.campaign, self.destination())
            finally:
                path.write_bytes(original)
                type(self).rewritten_bytes += len(original)
                path.chmod(mode)

    def test_missing_episode_refused(self):
        episode = self.first_episode()
        path = episode / "ATTEMPT.json"
        hidden = episode / "hidden-generated-attempt"
        path.rename(hidden)
        try:
            with self.assertRaises((ValueError, OSError)):
                t.collect(self.delivery, d.CONDITIONS[0], self.campaign, self.destination())
        finally:
            hidden.rename(path)

    def test_campaign_client_replacement_refused(self):
        path = self.campaign / "CLIENT.py"
        original = path.read_bytes()
        mode = path.stat().st_mode & 0o777
        try:
            path.chmod(0o600)
            path.write_bytes(original + b"\n# altered\n")
            type(self).rewritten_bytes += len(original) + len(b"\n# altered\n")
            with self.assertRaises((ValueError, OSError)):
                t.collect(self.delivery, d.CONDITIONS[0], self.campaign, self.destination())
        finally:
            path.write_bytes(original)
            type(self).rewritten_bytes += len(original)
            path.chmod(mode)

    def test_packet_tamper_refused(self):
        path = self.delivery / "public/queries.jsonl"
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b'"channels":[[0],[1]]', b'"channels":[[2],[1]]', 1))
            type(self).rewritten_bytes += len(original)
            with self.assertRaises((ValueError, OSError)):
                t.collect(self.delivery, d.CONDITIONS[0], self.campaign, self.destination())
        finally:
            path.write_bytes(original)
            type(self).rewritten_bytes += len(original)


if __name__ == "__main__":
    unittest.main()

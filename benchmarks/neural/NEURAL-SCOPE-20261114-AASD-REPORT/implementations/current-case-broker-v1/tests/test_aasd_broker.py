"""Generated controls; no native EEG/audio, participant models or fitted results."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

_SPEC = importlib.util.spec_from_file_location("aasd_broker", Path(__file__).resolve().parents[1] / "aasd_broker.py")
b = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(b)


def generated_inventory():
    people = [f"private-person-{i}" for i in range(18)]
    result = {"schema": "aasd-inventory-v1", "participants": people,
              "mixture_folds": {"private-a": 0, "private-b": 1, "private-c": 2},
              "mixture_map_provenance": "Generated test, not biological evidence", "trials": []}
    for person in people:
        for block in range(7):
            for slot in range(10):
                trial = {"trial_id": f"{person}-{block}-{slot}", "participant": person,
                         "block_id": f"private-block-{block}", "trial_in_block": slot + 1,
                         "order": block * 10 + slot + 1,
                         "condition": "passive" if block == 6 else "active",
                         "status": "available" if slot == 0 and block in (0, 1, 2, 6) else "missing",
                         "reason": "Generated missing slot", "mixture_family": ("private-a", "private-b", "private-c")[block % 3],
                         "duration_ns": 3 * b.d.a.NS,
                         "duration_discrepancy_reason": "Three-second generated fixture, never native duration"}
                if trial["status"] == "available":
                    trial.update(sample_count=384, sample_origin_ns=0, valid_spans=[[0, 384]],
                                 initial_state=block % 2, key_events=[], state_mapping_provenance="Generated states")
                result["trials"].append(trial)
    return result


def generated_observation():
    return {"schema": "aasd-normalized-observation-v1", "channels": ["C3", "C4"],
            "eeg_unit": "uV", "eeg_samples": [[i / 1000 for i in range(384)], [-i / 1000 for i in range(384)]],
            "audio": {"sample_rate_hz": 8, "sample_origin_ns": 0,
                      "samples": [[i / 100 for i in range(24)], [-i / 100 for i in range(24)]]}}


class BrokerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.inventory = generated_inventory()
        cls.artifacts = {}
        cls.extra_written_bytes = 0
        cls.journals = []
        def save_in_memory(path, value):
            kind = "index" if path.name == "index.json" else "packet" if path.parent.name == "packets" else "audio"
            mode = path.parent.name if kind == "index" else path.parent.parent.name
            identity = None if kind == "index" else path.stem
            cls.artifacts[(mode, kind, identity)] = copy.deepcopy(value)
        binding = cls.root / "private-binding.json"
        with mock.patch.object(b.d, "write_json", side_effect=save_in_memory):
            b.d.export(cls.inventory, lambda _: generated_observation(), cls.root / "public", binding)
        cls.binding = b.d.a.strict_load(binding)
        cls.extra_written_bytes += binding.stat().st_size

    @classmethod
    def tearDownClass(cls):
        written = cls.extra_written_bytes + sum(path.stat().st_size for path in cls.journals if path.exists())
        receipt = os.environ.get("AASD_TEST_RECEIPT")
        if receipt:
            Path(receipt).write_text(json.dumps({"scope": "generated fixtures only", "temporary_logical_written_bytes": written,
                                               "generated_trial_slots": 1260, "generated_cases": 72, "generated_cells": 54}) + "\n")
        cls.temporary.cleanup()

    def reader(self, mode="tool_assisted", artifacts=None):
        values = self.artifacts if artifacts is None else artifacts
        return lambda kind, identity=None: values[(mode, kind, identity)]

    def session(self, mode="tool_assisted", *, artifacts=None, limit=12):
        path = self.root / (self._testMethodName + f"-{len(self.journals)}.jsonl")
        session = b.Broker(self.inventory, self.binding, mode, self.reader(mode, artifacts), path, max_actions_per_case=limit)
        self.journals.append(path)
        self.addCleanup(session.close)
        return session

    def answer(self, session, packet, p=0.75):
        return session.handle({"operation": "answer", "request_id": packet["request_id"], "p_right": p})

    def test_complete_real_exporter_to_broker_to_unchanged_scorer(self):
        session = self.session()
        routes = set()
        count = 0
        while session.position < len(session.bundle.order):
            routes.add(tuple(session.operator_route().values()))
            packet = session.handle({"operation": "observe"})
            audio = session.handle({"operation": "audio", "resource_id": packet["audio_resource"]})
            self.assertEqual(packet["observation"]["eeg_samples"][0], [i / 1000 for i in range(64, 320)])
            self.assertEqual(audio["samples"], generated_observation()["audio"]["samples"])
            self.assertEqual(self.answer(session, packet), {"accepted": True})
            count += 1
        self.assertEqual((count, len(routes)), (72, 54))
        predictions = session.finish()
        replay = b.replay_file(self.inventory, self.binding, "tool_assisted", self.reader(), session.journal.path)
        self.assertEqual(predictions, replay)
        result = b.d.a.score(self.inventory, predictions)
        self.assertEqual(result["primary"]["macro"]["balanced_accuracy"]["all_18"], 0.5)
        self.assertEqual(sum(row["n"] for row in result["primary"]["participants"]), 54)
        self.assertEqual(sum(row["n"] for row in result["passive_motor_report_diagnostic"]["participants"]), 18)
        self.assertEqual(session.journal.fd, None)
        with self.assertRaises(b.ContractError):
            session.handle({"operation": "observe"})

    def test_no_advance_without_current_observation_and_valid_answer(self):
        session = self.session()
        first = session.bundle.order[0]
        with self.assertRaises(b.ContractError):
            session.handle({"operation": "answer", "request_id": first, "p_right": 0.5})
        self.assertEqual(session.position, 0)
        packet = session.handle({"operation": "observe"})
        next_id = session.bundle.order[1]
        with self.assertRaises(b.ContractError):
            session.handle({"operation": "answer", "request_id": next_id, "p_right": 0.5})
        self.assertEqual(session.journal.path.stat().st_size, 0)
        self.answer(session, packet)
        self.assertEqual(session.position, 1)
        session.handle({"operation": "observe"})
        with self.assertRaises(b.ContractError):
            self.answer(session, packet)
        self.assertEqual(session.position, 1)
        with self.assertRaises(b.ContractError):
            session.finish()

    def test_current_audio_only_and_no_operator_metadata(self):
        session = self.session()
        packet = session.handle({"operation": "observe"})
        for request in ({"operation": "audio", "resource_id": "../private-binding"},
                        {"operation": "audio", "resource_id": "f" * 32},
                        {"operation": "route"}, {"operation": "observe", "request_id": session.bundle.order[1]}):
            with self.assertRaises(b.ContractError):
                session.handle(request)
        forbidden = {"participant", "case_id", "label", "trial_id", "key_events", "condition", "held_mixture_fold", "order", "block_id"}
        def inspect(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden & value.keys())
                for item in value.values():
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
        inspect(packet)
        inspect(session.handle({"operation": "audio", "resource_id": packet["audio_resource"]}))

    def test_packet_and_audio_tampering_fail_before_answer(self):
        for target in ("packet", "audio", "extra"):
            values = copy.deepcopy(self.artifacts)
            rid = sorted(r["request_ids"]["tool_assisted"] for r in self.binding["rows"])[0]
            packet = values[("tool_assisted", "packet", rid)]
            if target == "packet":
                packet["observation"]["eeg_samples"][0][0] += 1
            elif target == "audio":
                values[("tool_assisted", "audio", packet["audio_resource"])]["samples"][0][0] = 0.5
            else:
                packet["label"] = 1
            session = self.session(artifacts=values)
            with self.assertRaises(b.ContractError):
                session.handle({"operation": "observe"})
            self.assertEqual((session.position, session.journal.path.stat().st_size), (0, 0))

    def test_returned_observations_cannot_mutate_cached_inputs(self):
        session = self.session()
        packet = session.handle({"operation": "observe"})
        packet["observation"]["eeg_samples"][0][0] = 999
        packet["audio_resource"] = "f" * 32
        fresh = session.handle({"operation": "observe"})
        self.assertEqual(fresh["observation"]["eeg_samples"][0][0], 0.064)
        audio = session.handle({"operation": "audio", "resource_id": fresh["audio_resource"]})
        audio["samples"][0][0] = 1
        self.assertEqual(session.handle({"operation": "audio", "resource_id": fresh["audio_resource"]})["samples"][0][0], 0)

    def test_probability_contract_never_changes_coverage(self):
        session = self.session(limit=32)
        packet = session.handle({"operation": "observe"})
        for value in (True, float("nan"), float("inf"), 10**400, -0.01, 1.01, "0.5"):
            with self.assertRaises(b.ContractError):
                self.answer(session, packet, value)
        self.assertEqual((session.position, session.journal.path.stat().st_size), (0, 0))
        self.answer(session, packet, 0)
        self.assertEqual(session.position, 1)

    def test_budget_failure_is_terminal_and_keeps_denominator(self):
        with self.assertRaises(b.ContractError):
            self.session(limit=2)
        session = self.session(limit=3)
        session.handle({"operation": "observe"})
        session.handle({"operation": "observe"})
        session.handle({"operation": "observe"})
        with self.assertRaises(b.ContractError):
            session.handle({"operation": "observe"})
        self.assertTrue(session.failed)
        self.assertEqual((session.position, len(session.bundle.order)), (0, 72))
        with self.assertRaises(b.ContractError):
            session.finish()

    def test_cross_arm_ids_and_direct_mode_rejected(self):
        tool = self.session()
        frozen = self.session("frozen_program")
        left = tool.handle({"operation": "observe"})
        right = frozen.handle({"operation": "observe"})
        self.assertNotEqual(left["request_id"], right["request_id"])
        with self.assertRaises(b.ContractError):
            self.answer(tool, right)
        with self.assertRaises(b.ContractError):
            b.Bundle(self.inventory, self.binding, "direct_observation", self.reader())

    def test_missing_passive_or_duplicate_index_refused(self):
        cases = {c["case_id"]: c for c in b.d.a.prepare(self.inventory)["cases"]}
        passive_id = next(r["request_ids"]["tool_assisted"] for r in self.binding["rows"] if cases[r["case_id"]]["condition"] == "passive")
        for kind in ("missing_passive", "duplicate"):
            values = copy.deepcopy(self.artifacts)
            index = values[("tool_assisted", "index", None)]["requests"]
            if kind == "missing_passive":
                index[:] = [row for row in index if row["request_id"] != passive_id]
            else:
                index[-1] = index[0]
            with self.assertRaises(b.ContractError):
                b.Bundle(self.inventory, self.binding, "tool_assisted", self.reader(artifacts=values))

    def test_fsync_failure_cannot_advance_or_retry(self):
        session = self.session()
        packet = session.handle({"operation": "observe"})
        with mock.patch.object(b.os, "fsync", side_effect=OSError("generated durability failure")):
            with self.assertRaises(OSError):
                self.answer(session, packet)
        self.assertTrue(session.failed)
        self.assertEqual(session.position, 0)
        self.assertGreater(session.journal.path.stat().st_size, 0)
        with self.assertRaises(b.ContractError):
            self.answer(session, packet)

    def test_existing_journal_is_never_overwritten(self):
        session = self.session()
        with self.assertRaises(FileExistsError):
            b.Broker(self.inventory, self.binding, "tool_assisted", self.reader(), session.journal.path, max_actions_per_case=3)

    def test_directory_durability_failure_closes_owned_descriptors(self):
        path = self.root / "directory-sync-failure.jsonl"
        self.journals.append(path)
        with mock.patch.object(b.os, "close", wraps=b.os.close) as close:
            with mock.patch.object(b.os, "fsync", side_effect=OSError("generated directory durability failure")):
                with self.assertRaises(OSError):
                    b.Journal(path)
            self.assertEqual(close.call_count, 2)
        self.assertEqual(path.stat().st_size, 0)
        with self.assertRaises(FileExistsError):
            b.Journal(path)

    def test_replay_rejects_missing_tampered_and_reordered_records(self):
        session = self.session()
        # Do not write a second full journal just to test replay. Construct its
        # expected public chain in memory from the independently exported inputs.
        records, previous = [], b.ZERO
        for sequence, rid in enumerate(session.bundle.order):
            packet, _ = session.bundle.load(rid)
            row = {"schema": "aasd-current-case-answer-v1", "sequence": sequence, "request_id": rid,
                   "p_right": 0.25, "observation_sha256": session.bundle.rows[rid]["observation_sha256"],
                   "audio_sha256": packet["observation"]["audio_sha256"], "previous": previous}
            row["record_sha256"] = b.d.digest(row)
            previous = row["record_sha256"]
            records.append(row)
        self.assertEqual(len(b.replay_records(session.bundle, records)), 72)
        bad = copy.deepcopy(records)
        bad[0]["p_right"] = 0.9
        for altered in (records[:-1], bad, [records[1], records[0]] + records[2:]):
            with self.assertRaises(b.ContractError):
                b.replay_records(session.bundle, altered)

    def test_file_store_and_journal_parser_bounds(self):
        root = self.root / "file-store"
        (root / "tool_assisted").mkdir(parents=True)
        path = root / "tool_assisted/index.json"
        raw = b'{"a": 1, "a": 2}\n'
        path.write_bytes(raw)
        type(self).extra_written_bytes += len(raw)
        store = b.FileStore(root, "tool_assisted", max_artifact_bytes=1024)
        with self.assertRaises(b.ContractError):
            store("index")
        with self.assertRaises(b.ContractError):
            b.FileStore(root, "tool_assisted", max_artifact_bytes=2)("index")
        with self.assertRaises(b.ContractError):
            store("packet", "../private-binding")
        external = self.root / "oversized-journal.jsonl"
        external.write_bytes(b"x" * 4097)
        type(self).extra_written_bytes += 4097
        with self.assertRaises(b.ContractError):
            b._read_journal(external, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

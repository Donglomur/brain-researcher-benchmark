"""Generated packet, raster, timing, boundary and scorer-compatibility controls."""

import base64
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import zlib

from viewer import Session, ViewError, BINDING_FIELDS, _load_protocol
import viewer


PROTOCOL = _load_protocol()
KEY = b"invented-fixture-private-key-0123456789"


def make_packet(num=256, den=1, k=29, flags=(), value=None):
    descriptor = {"assessment_id": "invented-viewer-control", "representation_sha256": "a" * 64,
                  "detector_sha256": "b" * 64}
    count = (k + 2) * num // den + 1
    record = {"recording_id": "eeg1", "sample_rate": {"num": num, "den": den},
              "sample_count": count, "units": "uV",
              "quality_flags": [i in flags for i in range(k + 2)]}
    value = value or (lambda i, c: ((i % 19) - 9) * (c + 1) / 10)
    def read(_rid, start, stop):
        return [[value(i, c) for c in range(18)] for i in range(start, stop)]
    packet = PROTOCOL._payload(descriptor, KEY, record, k, 0, read)
    packet["input_sha256"] = PROTOCOL.digest(packet)
    return packet, {name: packet[name] for name in BINDING_FIELDS}


def view(start=0, stop=30, channels=None, scale=10):
    return {"action": "view", "start_sample": start, "stop_sample": stop,
            "channels": [0] if channels is None else channels, "units_per_division": scale}


def png_rows(frame):
    raw = base64.b64decode(frame["png_base64"], validate=True)
    if hashlib.sha256(raw).hexdigest() != frame["png_sha256"]:
        raise AssertionError("wrong PNG commitment")
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("not PNG")
    index, payload, kinds, width, height = 8, b"", [], None, None
    while index < len(raw):
        size = struct.unpack(">I", raw[index:index + 4])[0]
        kind, body = raw[index + 4:index + 8], raw[index + 8:index + 8 + size]
        crc = struct.unpack(">I", raw[index + 8 + size:index + 12 + size])[0]
        if zlib.crc32(kind + body) != crc:
            raise AssertionError("wrong PNG CRC")
        kinds.append(kind)
        if kind == b"IHDR":
            width, height, depth, color, compress, filter_, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, color, compress, filter_, interlace) != (8, 2, 0, 0, 0):
                raise AssertionError("unexpected PNG encoding")
        elif kind == b"IDAT":
            payload += body
        index += size + 12
    if kinds != [b"IHDR", b"IDAT", b"IEND"]:
        raise AssertionError("unexpected PNG chunks or hidden text")
    decoded = zlib.decompress(payload)
    if len(decoded) != height * (width * 3 + 1):
        raise AssertionError("wrong decoded frame size")
    rows = []
    for y in range(height):
        at = y * (width * 3 + 1)
        if decoded[at] != 0:
            raise AssertionError("unexpected scanline filter")
        rows.append(decoded[at + 1:at + 1 + width * 3])
    return width, height, rows


class ViewerControls(unittest.TestCase):
    def test_native_geometry_all_channels_and_samples_remain_addressable(self):
        packet, binding = make_packet()
        session = Session(packet, binding)
        description = session.act({"action": "describe"})
        self.assertEqual(description["sample_count"], 7680)
        self.assertEqual(description["montage"], list(PROTOCOL.MONTAGE))
        self.assertEqual(description["sample_clock"], {"first_tick": 0, "step_ticks": 1, "ticks_per_second": 256})
        # Endpoint pages verify that no implicit prefix truncation hides the last
        # samples/channels. Page union is mathematical support, not visual parity.
        covered = {i for first in range(0, 7680, 512) for i in range(first, min(first + 512, 7680))}
        self.assertEqual(covered, set(range(7680)))
        for channels in ([0, 1, 2, 3, 4, 5], [12, 13, 14, 15, 16, 17]):
            result = session.act(view(7168, 7680, channels))
            self.assertEqual(result["source_samples_visited_per_channel"], 512)
            self.assertEqual(result["selection"]["channels"], channels)

    def test_rational_phase_is_preserved_without_resampling(self):
        packet, binding = make_packet(7, 4, 30)
        session = Session(packet, binding)
        description = session.act({"action": "describe"})
        expected = [n for n in range(56) if Fraction(1) <= Fraction(n * 4, 7) < 31]
        self.assertEqual(len(packet["samples"]), len(expected))
        self.assertEqual(description["sample_clock"], {"first_tick": 1, "step_ticks": 4, "ticks_per_second": 7})
        frame = session.act(view(0, 53))
        self.assertEqual(frame["source_samples_visited_per_channel"], 53)

    def test_png_contains_only_image_chunks_and_expected_zero_and_scale_points(self):
        packet, binding = make_packet(1, 1, value=lambda i, c: 0 if i == 0 else 10)
        frame = Session(packet, binding).act(view(0, 2, scale=10))
        width, height, rows = png_rows(frame)
        self.assertEqual((width, height), (1200, 320))
        # Fixed visual contract: zero at y200; positive one division is25px up.
        self.assertEqual(rows[200][150 * 3:150 * 3 + 3], b"\x00\x00\x00")
        self.assertEqual(rows[175][1180 * 3:1180 * 3 + 3], b"\x00\x00\x00")
        self.assertNotIn("samples", frame)
        self.assertNotIn("quality_flags", frame)

    def test_original_flags_and_final_second_are_retained(self):
        packet, binding = make_packet(1, 1, flags=(0, 5, 29))
        session = Session(packet, binding)
        description = session.act({"action": "describe"})
        self.assertEqual([i for i, flag in enumerate(description["quality_flags"]) if flag], [0, 5, 29])
        self.assertEqual(description["prediction_interval_seconds"], [29, 30])
        _, _, rows = png_rows(session.act(view(28, 30)))
        self.assertEqual(rows[70][155 * 3:155 * 3 + 3], bytes((225, 145, 20)))
        self.assertEqual(rows[70][189 * 3:189 * 3 + 3], bytes((235, 235, 235)))

    def test_clipping_is_reported_and_gain_can_reveal_the_same_sample(self):
        packet, binding = make_packet(1, 1, value=lambda i, c: 100)
        session = Session(packet, binding)
        narrow = session.act(view(0, 2, scale=1))
        broad = session.act(view(0, 2, scale=100))
        self.assertEqual(narrow["clipped_sample_counts"], [2])
        self.assertEqual(broad["clipped_sample_counts"], [0])
        self.assertEqual(narrow["binding"], broad["binding"])
        self.assertNotEqual(narrow["png_sha256"], broad["png_sha256"])

    def test_extreme_finite_values_produce_clipping_not_unbounded_coordinates(self):
        packet, binding = make_packet(1, 1, value=lambda i, c: (-1 if i % 2 else 1) * 1e308)
        result = Session(packet, binding).act(view(0, 2, scale=1e-308))
        self.assertEqual(result["clipped_sample_counts"], [2])
        png_rows(result)

    def test_private_fields_bad_hash_and_self_rehash_cannot_replace_protected_binding(self):
        packet, binding = make_packet(1, 1)
        for defect in ("private", "changed", "self_rehash", "expected_case"):
            changed, expected = deepcopy(packet), deepcopy(binding)
            if defect == "private":
                changed["expert_labels"] = [1, 0, 0]
            elif defect == "expected_case":
                expected["case_id"] = "0" * 64
            else:
                changed["samples"][0][0] += 1
                if defect == "self_rehash":
                    changed["input_sha256"] = PROTOCOL.digest({k: v for k, v in changed.items() if k != "input_sha256"})
            with self.subTest(defect=defect), self.assertRaises(ViewError):
                Session(changed, expected)

    def test_invalid_packet_shapes_types_units_and_clock_fail_before_rendering(self):
        packet, binding = make_packet(1, 1)
        for defect in ("future", "missing", "channel", "nan", "bool", "flags", "clock", "units", "fold"):
            changed = deepcopy(packet)
            if defect == "future": changed["samples"].append([0] * 18)
            elif defect == "missing": changed["samples"].pop()
            elif defect == "channel": changed["samples"][0].pop()
            elif defect == "nan": changed["samples"][0][0] = float("nan")
            elif defect == "bool": changed["samples"][0][0] = True
            elif defect == "flags": changed["quality_flags"][0] = 1
            elif defect == "clock": changed["sample_clock"]["first_tick"] = 1
            elif defect == "units": changed["units"] = "normalized"
            else: changed["fold"] = False
            with self.subTest(defect=defect), self.assertRaises(ViewError):
                Session(changed, binding)

    def test_unknown_actions_extra_fields_future_and_out_of_range_views_fail(self):
        packet, binding = make_packet()
        session = Session(packet, binding)
        bad = [{"action": "read_file", "path": "x"}, {"action": "describe", "labels": True},
               view(-1, 4), view(0, 513), view(7670, 7681), view(0, 2, [18]),
               view(0, 2, [0, 0]), view(0, 2, [True]), view(0, 2, list(range(7))),
               view(0, 2, scale=0), view(0, 2, scale=float("nan")), view(0, 2, scale=True)]
        for action in bad:
            with self.subTest(action=action), self.assertRaises(ViewError):
                session.act(action)

    def test_input_mutation_and_returned_metadata_cannot_change_frozen_session(self):
        packet, binding = make_packet(1, 1)
        session = Session(packet, binding)
        before = session.act(view())
        packet["samples"][0][0] = 12345
        packet["quality_flags"][0] = True
        binding["case_id"] = "0" * 64
        description = session.act({"action": "describe"})
        description["quality_flags"][0] = True
        self.assertEqual(before, session.act(view()))
        self.assertFalse(session.act({"action": "describe"})["quality_flags"][0])

    def test_final_probability_is_required_bound_and_single_assignment(self):
        packet, binding = make_packet(1, 1)
        session = Session(packet, binding)
        with self.assertRaises(ViewError): session.finish()
        good = {"action": "answer", "case_id": binding["case_id"],
                "input_sha256": binding["input_sha256"], "probability": 0.25}
        for change in ({"probability": True}, {"probability": -0.1}, {"probability": 1.1},
                       {"probability": float("inf")}, {"input_sha256": "0" * 64}, {"case_id": "0" * 64}):
            with self.assertRaises(ViewError): session.act(dict(good, **change))
        self.assertTrue(session.act(good)["accepted"])
        for action in (good, {"action": "describe"}, view()):
            with self.assertRaises(ViewError): session.act(action)
        expected = dict(binding, probability=0.25)
        self.assertEqual(session.finish(), expected)
        result = session.finish()
        result["probability"] = 0.8
        self.assertEqual(session.finish(), expected)

    def test_owned_snapshot_is_validated_before_caller_can_mutate_after_validation(self):
        packet, binding = make_packet(1, 1)
        baseline = Session(packet, binding).act(view())
        original_validator = viewer._validate
        def mutate_caller_after_validation(snapshot, expected, protocol):
            original_validator(snapshot, expected, protocol)
            packet["samples"][0][0] = 100000
            binding["case_id"] = "0" * 64
        with patch.object(viewer, "_validate", mutate_caller_after_validation):
            session = Session(packet, binding)
        self.assertEqual(session.act(view()), baseline)

    def test_exact_zero_and_one_probabilities_are_valid(self):
        packet, binding = make_packet(1, 1)
        for probability in (0, 1):
            session = Session(packet, binding)
            session.act({"action": "answer", "case_id": binding["case_id"],
                         "input_sha256": binding["input_sha256"], "probability": probability})
            self.assertEqual(session.finish()["probability"], probability)

    def test_all79_generated_case_rows_work_with_unchanged_complete_support_scorer(self):
        ids = ["eeg" + str(i) for i in range(1, 80)]
        assignment = PROTOCOL.fold_map(ids, "viewer-fixture")
        descriptor = {"schema": PROTOCOL.DESCRIPTION_SCHEMA, "assessment_id": "viewer-cohort-control",
            "protocol_id": PROTOCOL.PROTOCOL, "source_version": PROTOCOL.SOURCE_VERSION,
            "fold_seed": "viewer-fixture", "representation_sha256": "a" * 64,
            "detector_sha256": "b" * 64, "source_admission_sha256": "c" * 64,
            "montage": list(PROTOCOL.MONTAGE),
            "development_by_fold": {str(f): [next(rid for rid in ids if assignment[rid] != f)] for f in range(5)},
            "recordings": [{"recording_id": rid, "eeg_sha256": "d" * 64,
                "sample_rate": {"num": 1, "den": 1}, "sample_count": 30,
                "sample_zero_annotation_second": 0, "units": "uV", "labels": [[0] * 30 for _ in range(3)],
                "quality_flags": [False] * 30} for rid in ids]}
        reader = lambda rid, start, stop: [[i + c / 100 for c in range(18)] for i in range(start, stop)]
        reference = PROTOCOL.prepare_reference(descriptor, reader, KEY)
        expected = list(reference.case_rows())
        rows = []
        for rid, binding in zip(reference.record_ids(), expected):
            packet = PROTOCOL.packet(reference, rid, 29, reader)
            session = Session(packet, binding)
            session.act({"action": "answer", "case_id": binding["case_id"],
                         "input_sha256": binding["input_sha256"], "probability": 0.25})
            rows.append(session.finish())
        evaluator_path = Path(__file__).resolve().parent.parent / "complete-support-evaluator/evaluate.py"
        spec = importlib.util.spec_from_file_location("_viewer_test_existing_evaluate", evaluator_path)
        evaluator = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"protocol": PROTOCOL}):
            spec.loader.exec_module(evaluator)
        report = evaluator.evaluate(reference, rows)
        self.assertEqual((report["n_infants"], report["n_cases"]), (79, 79))
        self.assertEqual(report["primary_soft_vote_brier"], 1 / 16)
        with self.assertRaises(PROTOCOL.ContractError): evaluator.evaluate(reference, rows[:-1])


if __name__ == "__main__":
    unittest.main()

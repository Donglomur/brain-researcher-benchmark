"""Generated-only selector integration controls; run this file as a stdlib CLI.

No native arrays, authentic clocks, held packets, model services, or scientific
qualification are exercised. One real nine-configuration reference pass uses
47 generated training records and 376 tiny, synthetic nine-map packets. The
remaining declared trial rows are explicitly GENERATED exclusions, not claims
about eligibility in original recordings. Fault controls replace predict only;
the actual admission, PNG decoder, prediction indexing and scorer remain active.

One successful private freeze is written; no full manifest/packet is written.
The output must be a new directory. One freeze <=256 KiB and CHECK.log/RESULT.json
combined <=32 KiB are the selected artifact envelope. Installed stdlib/startup
I/O is separate from the bounded named-content reservations reported below.
"""
import argparse
import base64
import copy
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import time
import types
import unittest
from unittest import mock
import zlib


SOURCE_BYTES = 13267
SOURCE_SHA256 = "332b63dc681668e614b2e2c9d4f0c6e7f3cfde90e4dfd6ef2044527a74bfcd18"
EXPECTED_DEPENDENCIES = {
    "roster": ("direction-scorer/roster.py", 2755,
        "0f1ac943d56edc5305be4ba74f5d27c8cfa626e555092b7a51a1f6f2641dd4c9"),
    "scorer": ("direction-scorer/scorer.py", 14874,
        "11d1b2a330d5c32c6c2ea93c5c54de5d58c9d4d31008ccafd235afa3a732ad50"),
    "reference": ("rendered-references-v1/reference.py", 11970,
        "ed37e6dda9d55e791f8bd751d787ea0d6c314a5c463d631f8266e01e5c73985a"),
    "admission": ("outer-training-selection-v1/admission.py", 10586,
        "66495eafec42da3dec4db0cb951e3419464237899261c1bf22b5b37405f57268"),
}
EXPECTED_CONFIGURATIONS = (
    ("uniform", None), ("squared_distance", None), ("cosine", None),
    ("linear_ridge", .001), ("linear_ridge", .01), ("linear_ridge", .1),
    ("linear_ridge", 1), ("linear_ridge", 10), ("linear_ridge", 100),
)
FIXTURE_WRITE_LIMIT = 262144
REPORT_WRITE_LIMIT = 32768
NAMED_READ_LIMIT = 2097152
S = MODULES = FIXTURE = OUTPUT = None
NAMED_READ_RESERVED = 0
FIXTURE_WRITTEN = 0


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(body):
    return hashlib.sha256(body).hexdigest()


def reserve_read(n):
    global NAMED_READ_RESERVED
    if type(n) is not int or n < 0 or NAMED_READ_RESERVED + n > NAMED_READ_LIMIT:
        raise ValueError("generated control named-read budget")
    NAMED_READ_RESERVED += n


def load_source(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ordinary selected source path")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size != SOURCE_BYTES:
        raise ValueError("exact selected source extent")
    reserve_read(SOURCE_BYTES + 1)
    with path.open("rb") as f:
        body = f.read(SOURCE_BYTES + 1)
    if len(body) != SOURCE_BYTES or sha(body) != SOURCE_SHA256:
        raise ValueError("exact selected source digest")
    mod = types.ModuleType("_generated_fus_selection_controls_source")
    mod.__file__ = str(path)
    exec(compile(body, str(path), "exec"), mod.__dict__)
    if mod.DEPENDENCIES != EXPECTED_DEPENDENCIES:
        raise ValueError("exact selected dependency closure")
    if mod.CONFIGURATIONS != EXPECTED_CONFIGURATIONS:
        raise ValueError("fixed nine configurations")
    return mod


def generated_png(direction):
    """Independent minimal PNG encoder, not the production codec."""
    rgb = b"".join(bytes([255 if i == direction else 0]) * 3 for i in range(8))
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
    body = (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 1, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(b"\0" + rgb)) + chunk(b"IEND", b""))
    return base64.b64encode(body).decode("ascii")


class GeneratedCohort:
    def __init__(self, roster):
        self.held = "L-S27-R99"
        self.roster = tuple(roster)
        self.positive = [r for r in roster if r[3] > 0]
        self.training = [r for r in self.positive if r[0] != self.held]
        ids = [r[0] for r in self.training]
        review = sha(b"GENERATED independent-adjudication placeholder")
        self.manifest = {"schema": "fus_outer_training_episodes_v1",
            "held_record_id": self.held,
            "zero_record": {"record_id": "L-S45-R1",
                            "reconciliation_sha256": sha(b"GENERATED zero record")},
            "review_sha256": review, "episodes": []}
        self.packets = {}
        self.truth = {}
        self.query_zero = {}
        self.lookup = {}
        pngs = [generated_png(i) for i in range(8)]
        for ri, (rid, animal, system, declared, elapsed) in enumerate(self.training):
            fold = "fold_" + sha(("GENERATED inner fold " + rid).encode())[:32]
            qids = ["q_" + format(ri * 32 + i, "032x") for i in range(16)]
            self.query_zero[rid] = qids[8]
            def image(qid, direction, calibration=False):
                result = {"map_id": qid, "shape": [1, 8], "spatial_pitch": [1, 1],
                    "spatial_pitch_unit": "generated_pixel", "native_hz": 2,
                    "source_float": "binary64", "scale": 2, "invalid_pixels": 0,
                    "saturated_pixels": 0, "png_base64": pngs[direction]}
                if calibration:
                    result["direction_degrees"] = 45 * direction
                return result
            calibration = [image(qids[c], c, True) for c in range(8)]
            trials = [{"disposition": "eligible", "source_order": i,
                       "query_id": qids[i], "direction": i % 8} for i in range(16)]
            trials.extend({"disposition": "adjudicated_excluded", "source_order": i,
                "exclusion_reason": "missing_timing", "adjudication_sha256": review}
                for i in range(16, declared))
            descriptors = []
            for c in range(8):
                qid = qids[8 + c]
                packet = {"schema": "fus_nine_map_packet_v1", "fold_key": fold,
                    "query_id": qid, "class_angles_degrees": list(range(0, 360, 45)),
                    "context": "GENERATED fixture; no authentic neural-data or clock claim.",
                    "calibration": calibration, "query": image(qid, c)}
                body = canonical(packet)
                self.packets[(rid, qid)] = body
                self.truth[qid] = (rid, animal, c)
                self.lookup[qid] = body
                descriptors.append({"query_id": qid, "bytes": len(body), "sha256": sha(body)})
            self.manifest["episodes"].append({"record_id": rid, "native_hz": 2,
                "reconciliation_sha256": sha(("GENERATED reconciliation " + rid).encode()),
                "clock_mapping_sha256": sha(("GENERATED clock " + rid).encode()),
                "representation_sha256": sha(("GENERATED representation " + rid).encode()),
                "fold_key": fold,
                "scale": {"value": 2, "training_record_ids": [x for x in ids if x != rid],
                    "recipe_sha256": MODULES["admission"].SCALE_RECIPE_SHA256,
                    "receipt_sha256": sha(("GENERATED scale receipt " + rid).encode())},
                "trials": trials, "packets": descriptors})
        self.wire = canonical(self.manifest)
        self.total_packet_bytes = sum(len(v) for v in self.packets.values())
        self.expected_loads = list(self.packets)
        self.real_wire = None
        self.fault_wire = None
        self.same_byte_calls = []

    def load(self, rid, qid):
        if rid == self.held:
            raise AssertionError("held packet callback is forbidden during selection")
        return self.packets[(rid, qid)]

    def select(self, manifest=None, loader=None, **overrides):
        body = self.wire if manifest is None else canonical(manifest)
        options = {"expected_manifest_sha256": sha(body),
            "load_packet": self.load if loader is None else loader,
            "max_manifest_bytes": 8388608, "max_packet_bytes": 8192,
            "max_total_packet_bytes": self.total_packet_bytes,
            "max_map_pixels": 8}
        options.update(overrides)
        return S.select_fold(body, **options)

    def real(self):
        if self.real_wire is None:
            self.real_wire = self.select()
        return json.loads(self.real_wire)

    def faults(self):
        if self.fault_wire is not None:
            return json.loads(self.fault_wire)
        first_l = next(r[0] for r in self.training if r[1] == "L")
        first_p = next(r[0] for r in self.training if r[1] == "P")
        def predictor(body, *, method, ridge_lambda, **unused):
            packet = json.loads(body)
            qid = packet["query_id"]
            rid, animal, direction = self.truth[qid]
            self.same_byte_calls.append((qid, id(body), sha(body), method, ridge_lambda))
            if method == "squared_distance" and direction == 0:
                raise RuntimeError("GENERATED predictor failure")
            if method == "cosine" and direction == 1:
                return {"query_id": qid, "probabilities": [0] * 8}
            if method == "linear_ridge" and ridge_lambda == .001:
                return {"query_id": "q_" + "f" * 32, "probabilities": [1 / 8] * 8}
            if method == "linear_ridge" and ridge_lambda == .1:
                return None
            if method == "linear_ridge" and ridge_lambda == .01 and direction == 1:
                qid = self.query_zero[rid]
            correct = True
            if method == "linear_ridge" and ridge_lambda == 1:
                correct = animal == "L"
            if method == "linear_ridge" and ridge_lambda == 10:
                correct = rid == first_l
            if method == "linear_ridge" and ridge_lambda == 100:
                correct = rid == first_p
            chosen = direction if correct else (direction + 1) % 8
            return {"query_id": qid, "probabilities": [int(i == chosen) for i in range(8)]}
        with mock.patch.object(MODULES["reference"], "predict", side_effect=predictor):
            self.fault_wire = self.select()
        return json.loads(self.fault_wire)


class SelectionControls(unittest.TestCase):
    def assert_before_loader(self, mutate, **options):
        manifest = copy.deepcopy(FIXTURE.manifest)
        mutate(manifest)
        called = []
        def forbidden(*args):
            called.append(args)
            raise AssertionError("admission must fail before packet reads")
        with self.assertRaises(ValueError):
            FIXTURE.select(manifest, forbidden, **options)
        self.assertEqual(called, [])

    def case_01_real_reference_full_training_roster(self):
        result = FIXTURE.real()
        self.assertEqual(len(FIXTURE.roster), 49)
        self.assertEqual(sum(r[3] for r in FIXTURE.roster), 20622)
        self.assertEqual(len(FIXTURE.positive), 48)
        self.assertEqual(len(FIXTURE.training), 47)
        self.assertEqual(sum(len(e["trials"]) for e in FIXTURE.manifest["episodes"]), 20306)
        self.assertEqual(result["training_queries"], 376)
        self.assertEqual(result["training_records"], [r[0] for r in FIXTURE.training])
        self.assertNotIn(FIXTURE.held, result["training_records"])
        self.assertEqual(len(result["candidates"]), 9)
        for i, candidate in enumerate(result["candidates"]):
            expected = {"numerator": 1, "denominator": 8 if i == 0 else 1}
            self.assertEqual(candidate["equal_animal_session_balanced_accuracy"], expected)
            self.assertEqual(candidate["predictor_exceptions"], 0)
            self.assertEqual(len(candidate["sessions"]), 47)
        self.assertEqual(result["choices"]["template"]["method"], "squared_distance")
        self.assertEqual(result["choices"]["ridge"]["ridge_lambda"], .001)
        for name in ("native_source_authenticated", "protected_isolation_established", "scientifically_qualified"):
            self.assertIs(result[name], False)

    def case_02_held_episode_rejected_before_loader(self):
        self.assert_before_loader(lambda m: m["episodes"][0].__setitem__("record_id", FIXTURE.held))

    def case_03_missing_training_record_rejected_before_loader(self):
        self.assert_before_loader(lambda m: m["episodes"].pop())

    def case_04_duplicate_and_reordered_training_records(self):
        self.assert_before_loader(lambda m: m["episodes"].__setitem__(1, m["episodes"][0]))
        self.assert_before_loader(lambda m: m["episodes"].reverse())

    def case_05_zero_record_identity_preserved(self):
        self.assert_before_loader(lambda m: m["zero_record"].__setitem__("record_id", FIXTURE.held))

    def case_06_all_declared_source_trials_required(self):
        self.assert_before_loader(lambda m: m["episodes"][-1]["trials"].pop())

    def case_07_late_missing_query_class_refuses_all_loading(self):
        self.assert_before_loader(lambda m: m["episodes"][-1]["trials"][15].__setitem__("direction", 6))

    def case_08_scale_excludes_both_outer_and_inner_record(self):
        self.assert_before_loader(lambda m: m["episodes"][-1]["scale"]["training_record_ids"].__setitem__(0, FIXTURE.held))
        self.assert_before_loader(lambda m: m["episodes"][0]["scale"]["training_record_ids"].__setitem__(0, m["episodes"][0]["record_id"]))

    def case_09_exact_scale_recipe_binding(self):
        self.assert_before_loader(lambda m: [e["scale"].__setitem__("recipe_sha256", "a" * 64) for e in m["episodes"]])

    def case_10_strict_integer_and_scale_types(self):
        mutations = [lambda m: m["episodes"][0].__setitem__("native_hz", True),
            lambda m: m["episodes"][0]["trials"][0].__setitem__("source_order", False),
            lambda m: m["episodes"][0]["trials"][0].__setitem__("direction", False),
            lambda m: m["episodes"][0]["scale"].__setitem__("value", True)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.assert_before_loader(mutation)

    def case_11_unadjudicated_exclusion_and_duplicate_query_refused(self):
        self.assert_before_loader(lambda m: m["episodes"][-1]["trials"][-1].__setitem__("adjudication_sha256", "b" * 64))
        self.assert_before_loader(lambda m: m["episodes"][-1]["trials"][8].__setitem__("query_id", m["episodes"][0]["trials"][8]["query_id"]))

    def case_12_complete_training_packet_denominator_required(self):
        self.assert_before_loader(lambda m: m["episodes"][-1]["packets"].pop())

    def case_13_manifest_and_complete_packet_budgets_precede_loader(self):
        self.assert_before_loader(lambda m: None, expected_manifest_sha256="0" * 64)
        self.assert_before_loader(lambda m: None, max_total_packet_bytes=FIXTURE.total_packet_bytes - 1)
        self.assert_before_loader(lambda m: None, max_packet_bytes=1)

    def case_14_identical_immutable_packet_for_all_nine_configs(self):
        FIXTURE.faults()
        self.assertEqual(len(FIXTURE.same_byte_calls), 3384)
        for i, (rid, qid) in enumerate(FIXTURE.expected_loads):
            calls = FIXTURE.same_byte_calls[9 * i:9 * (i + 1)]
            body = FIXTURE.packets[(rid, qid)]
            self.assertIs(type(body), bytes)
            self.assertEqual([(c[3], c[4]) for c in calls], list(EXPECTED_CONFIGURATIONS))
            self.assertEqual({c[0] for c in calls}, {qid})
            self.assertEqual({c[1] for c in calls}, {id(body)})
            self.assertEqual({c[2] for c in calls}, {sha(body)})

    def case_15_prediction_faults_keep_denominators(self):
        rows = FIXTURE.faults()["candidates"]
        expected = [Fraction(1), Fraction(7, 8), Fraction(7, 8), Fraction(0),
                    Fraction(3, 4), Fraction(0), Fraction(1, 2), Fraction(1, 50), Fraction(1, 44)]
        for row, score in zip(rows, expected):
            self.assertEqual(row["equal_animal_session_balanced_accuracy"],
                             {"numerator": score.numerator, "denominator": score.denominator})
            for session in row["sessions"]:
                self.assertEqual(session["class_support"], [1] * 8)
        self.assertEqual(rows[1]["predictor_exceptions"], 47)
        self.assertTrue(all(s["invalid_by_class"] == [1, 0, 0, 0, 0, 0, 0, 0] for s in rows[1]["sessions"]))
        self.assertTrue(all(s["prediction_issues"]["missing_queries"] == 1 for s in rows[1]["sessions"]))
        self.assertTrue(all(s["prediction_issues"]["malformed_rows"] == 1 for s in rows[2]["sessions"]))
        self.assertTrue(all(s["whole_episode_invalid"] for s in rows[3]["sessions"]))
        self.assertTrue(all(s["prediction_issues"]["duplicate_rows"] == 1 and s["prediction_issues"]["missing_queries"] == 1 for s in rows[4]["sessions"]))

    def case_16_uniform_is_separate_from_family_selection(self):
        result = FIXTURE.faults()
        self.assertEqual(result["choices"], {"uniform": {"method": "uniform", "ridge_lambda": None},
            "template": {"method": "squared_distance", "ridge_lambda": None},
            "ridge": {"method": "linear_ridge", "ridge_lambda": .01}})

    def case_17_exact_equal_animal_then_session_class_balancing(self):
        def row(animal, support, correct):
            confusion = [[0] * 8 for _ in range(8)]
            for i in range(8):
                confusion[i][i] = correct[i]
                confusion[i][(i + 1) % 8] = support[i] - correct[i]
            return {"animal": animal, "class_support": support, "confusion": confusion}
        rows = [row("L", [5] * 8, [5] * 8), row("L", [9] + [1] * 7, [0] * 8),
                row("P", [1, 1] + [3] * 6, [1, 1] + [0] * 6)]
        self.assertEqual(S.grouped_score(rows), Fraction(3, 8))
        self.assertNotEqual(S.grouped_score(rows), Fraction(5, 12))
        n = 10**18
        almost = [row("L", [n] * 8, [n - 1] + [n] * 7), row("P", [n] * 8, [n] * 8)]
        self.assertEqual(S.grouped_score(almost), 1 - Fraction(1, 16 * n))
        self.assertLess(S.grouped_score(almost), 1)

    def case_18_missing_packet_body_aborts_instead_of_freeze(self):
        called = []
        def absent(rid, qid):
            called.append((rid, qid))
            return None
        with self.assertRaises(ValueError):
            FIXTURE.select(loader=absent)
        self.assertEqual(called, [FIXTURE.expected_loads[0]])

    def case_19_late_corruption_cannot_return_partial_selection(self):
        calls = []
        last = FIXTURE.expected_loads[-1]
        def late(rid, qid):
            calls.append((rid, qid))
            body = FIXTURE.load(rid, qid)
            return body + b" " if (rid, qid) == last else body
        def perfect(body, **unused):
            qid = json.loads(body)["query_id"]
            direction = FIXTURE.truth[qid][2]
            return {"query_id": qid, "probabilities": [int(i == direction) for i in range(8)]}
        with mock.patch.object(MODULES["reference"], "predict", side_effect=perfect):
            with self.assertRaises(ValueError):
                FIXTURE.select(loader=late)
        self.assertEqual(calls, FIXTURE.expected_loads)

    def mutate_first_packet(self, change, packet_index=0):
        manifest = copy.deepcopy(FIXTURE.manifest)
        episode = manifest["episodes"][0]
        desc = episode["packets"][packet_index]
        key = (episode["record_id"], desc["query_id"])
        packet = json.loads(FIXTURE.packets[key])
        change(packet)
        altered = canonical(packet)
        desc.update(bytes=len(altered), sha256=sha(altered))
        def loader(rid, qid):
            return altered if (rid, qid) == key else FIXTURE.load(rid, qid)
        return manifest, loader

    def case_20_protected_query_field_rejected(self):
        m, loader = self.mutate_first_packet(lambda p: p["query"].__setitem__("direction_degrees", 0))
        with self.assertRaises(ValueError):
            FIXTURE.select(m, loader, max_total_packet_bytes=FIXTURE.total_packet_bytes + 8192)

    def case_21_episode_fold_and_nested_scale_bound_to_manifest(self):
        for change in [lambda p: p.__setitem__("fold_key", "fold_" + "f" * 32),
                       lambda p: [v.__setitem__("scale", 3) for v in p["calibration"] + [p["query"]]]]:
            m, loader = self.mutate_first_packet(change)
            with self.assertRaises(ValueError):
                FIXTURE.select(m, loader, max_total_packet_bytes=FIXTURE.total_packet_bytes + 8192)

    def case_22_support_context_cannot_change_between_queries(self):
        m, loader = self.mutate_first_packet(lambda p: p.__setitem__("context", "GENERATED changed context"), 1)
        def uniform(body, **unused):
            return {"query_id": json.loads(body)["query_id"], "probabilities": [1 / 8] * 8}
        with mock.patch.object(MODULES["reference"], "predict", side_effect=uniform) as predictor:
            with self.assertRaises(ValueError):
                FIXTURE.select(m, loader, max_total_packet_bytes=FIXTURE.total_packet_bytes + 8192)
        self.assertEqual(predictor.call_count, 9)

    def case_23_publish_freeze_returns_only_after_private_durable_write(self):
        global FIXTURE_WRITTEN
        FIXTURE.real()
        wire = FIXTURE.real_wire
        self.assertLessEqual(len(wire), FIXTURE_WRITE_LIMIT)
        path = OUTPUT / "PRIVATE_FREEZE.json"
        events = []
        fsync = os.fsync
        def observed_fsync(fd):
            events.append("directory_fsync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_fsync")
            return fsync(fd)
        with mock.patch.object(S.os, "fsync", side_effect=observed_fsync):
            descriptor = S.publish_freeze(wire, path, expected_sha256=sha(wire))
        FIXTURE_WRITTEN += len(wire)
        events.append("publish_returned")
        # This caller-side event demonstrates the required ordering; it is not
        # a claim that the selector sandboxes or authenticates held-data access.
        events.append("simulated_held_access")
        self.assertEqual(events, ["file_fsync", "directory_fsync", "publish_returned", "simulated_held_access"])
        self.assertEqual(descriptor, {"held_record_id": FIXTURE.held, "freeze_sha256": sha(wire)})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)
        reserve_read(len(wire) + 1)
        with path.open("rb") as f:
            self.assertEqual(f.read(len(wire) + 1), wire)
        with self.assertRaises(FileExistsError):
            S.publish_freeze(wire, path, expected_sha256=sha(wire))
        self.assertEqual(path.stat().st_size, len(wire))
        with self.assertRaises(ValueError):
            S.publish_freeze(wire, OUTPUT / "MUST_NOT_EXIST.json", expected_sha256="0" * 64)
        self.assertFalse((OUTPUT / "MUST_NOT_EXIST.json").exists())

    def case_24_full_48_fold_descriptor_coverage(self):
        descriptors = [{"held_record_id": r[0], "freeze_sha256": sha(("GENERATED freeze " + r[0]).encode())}
                       for r in FIXTURE.positive]
        result = S.verify_coverage(descriptors)
        self.assertEqual(result["positive_folds"], 48)
        self.assertEqual(result["zero_record"], "L-S45-R1")
        self.assertEqual(result["descriptor_sha256"], sha(canonical(descriptors)))
        for name in ("freeze_bodies_authenticated", "fresh_process_isolation_established", "scientifically_qualified"):
            self.assertIs(result[name], False)
        malformed = [descriptors[:-1], descriptors + [descriptors[0]],
                     [descriptors[0]] + descriptors[:-1], list(reversed(descriptors))]
        for value in malformed:
            with self.assertRaises(ValueError):
                S.verify_coverage(value)
        altered = copy.deepcopy(descriptors)
        altered[4]["held_record_id"] = "L-S45-R1"
        with self.assertRaises(ValueError):
            S.verify_coverage(altered)


    def test_01_real_reference_full_training(self):
        self.case_01_real_reference_full_training_roster()

    def test_02_complete_admission_precedes_loader(self):
        cases = [getattr(self, n) for n in sorted(dir(self)) if n.startswith("case_") and 2 <= int(n[5:7]) <= 13]
        for case in cases:
            with self.subTest(control=case.__name__):
                case()

    def test_03_identical_bytes_for_nine_configurations(self):
        self.case_14_identical_immutable_packet_for_all_nine_configs()

    def test_04_prediction_failures_preserve_denominators_and_families(self):
        self.case_15_prediction_faults_keep_denominators()
        self.case_16_uniform_is_separate_from_family_selection()

    def test_05_exact_grouped_rational_score(self):
        self.case_17_exact_equal_animal_then_session_class_balancing()

    def test_06_missing_and_late_corrupt_packet_abort(self):
        self.case_18_missing_packet_body_aborts_instead_of_freeze()
        self.case_19_late_corruption_cannot_return_partial_selection()

    def test_07_packet_private_identity_and_scale_boundaries(self):
        self.case_20_protected_query_field_rejected()
        self.case_21_episode_fold_and_nested_scale_bound_to_manifest()

    def test_08_same_support_context_for_all_queries(self):
        self.case_22_support_context_cannot_change_between_queries()

    def test_09_exclusive_durable_freeze_before_held_event(self):
        self.case_23_publish_freeze_returns_only_after_private_durable_write()

    def test_10_all_48_fold_descriptor_roster(self):
        self.case_24_full_48_fold_descriptor_coverage()


class BoundedTranscript(io.StringIO):
    def __init__(self):
        super().__init__()
        self.bytes_written = 0
    def write(self, text):
        size = len(text.encode("utf-8"))
        if self.bytes_written + size > 16384:
            raise ValueError("unittest transcript ceiling")
        self.bytes_written += size
        result = super().write(text)
        sys.stdout.write(text)
        sys.stdout.flush()
        return result


class PositiveResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positive_methods = []
    def addSuccess(self, test):
        self.positive_methods.append(test.id())
        super().addSuccess(test)


def write_once(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as f:
            f.write(body)
            f.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def main():
    global S, MODULES, FIXTURE, OUTPUT
    default = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=default / "outer-training-selection-v1/selection.py")
    parser.add_argument("--dependencies", type=Path, default=default)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source / "selection.py" if args.source.is_dir() else args.source
    OUTPUT = args.output.absolute()
    if OUTPUT.exists() or OUTPUT.is_symlink() or any(p.is_symlink() for p in OUTPUT.parents):
        raise ValueError("fresh ordinary generated-control output required")
    # Never permit the artifact directory inside either selected source closure.
    resolved_output = OUTPUT.resolve()
    for protected in (source.resolve().parent, args.dependencies.resolve()):
        if resolved_output == protected or protected in resolved_output.parents:
            raise ValueError("output must be separate from selected source closure")
    OUTPUT.mkdir(mode=0o700)
    started = time.monotonic()
    S = load_source(source)
    # One real, exact dependency load; repeated cohort controls reuse those same
    # modules. Extent+1 reservations include all failed read prefixes.
    reserve_read(sum(n + 1 for _, n, _ in EXPECTED_DEPENDENCIES.values()))
    MODULES = S._dependencies(args.dependencies)
    FIXTURE = GeneratedCohort(MODULES["roster"].ROSTER)
    names = sorted(n for n in vars(SelectionControls) if n.startswith("test_"))
    expected = ["__main__.SelectionControls." + n for n in names]
    log = BoundedTranscript()
    with mock.patch.object(S, "_dependencies", return_value=MODULES):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelectionControls)
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=PositiveResult).run(suite)
    log_body = log.getvalue().encode("utf-8")
    successful = (result.wasSuccessful() and result.testsRun == len(expected) == 10
        and result.positive_methods == expected and not result.skipped
        and not result.expectedFailures and not result.unexpectedSuccesses)
    report = {"schema": "fus-generated-selection-controls/v1", "generated_only": True,
        "authentic_source_agreement_claimed": False, "scientific_qualification_claimed": False,
        "successful": successful, "tests_run": result.testsRun,
        "positive_methods": result.positive_methods, "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "source": {"bytes": SOURCE_BYTES, "sha256": SOURCE_SHA256},
        "dependency_pins": {k: {"bytes": n, "sha256": d} for k, (_, n, d) in EXPECTED_DEPENDENCIES.items()},
        "fixture": {"original_roster_rows": 49, "positive_roster_rows": 48,
            "training_records": 47, "held_record": FIXTURE.held, "generated_training_queries": 376,
            "declared_training_census_rows": 20306, "map_shape": [1, 8],
            "manifest_bytes_in_memory": len(FIXTURE.wire), "packet_bytes_in_memory": FIXTURE.total_packet_bytes,
            "real_predictor_calls_planned_and_single_cached_pass": 3384},
        "named_read_reserved_bytes": NAMED_READ_RESERVED,
        "fixture_logical_write_bytes": FIXTURE_WRITTEN,
        "fixture_write_ceiling_bytes": FIXTURE_WRITE_LIMIT,
        "report_write_ceiling_bytes": REPORT_WRITE_LIMIT,
        "elapsed_seconds": time.monotonic() - started,
        "limits": "Source/generated controls only. Private freeze publication ordering does not establish held-data isolation. Coverage descriptors do not authenticate48 freeze bodies."}
    body = canonical(report) + b"\n"
    if FIXTURE_WRITTEN > FIXTURE_WRITE_LIMIT or len(log_body) + len(body) > REPORT_WRITE_LIMIT:
        raise ValueError("generated-control artifact ceiling")
    write_once(OUTPUT / "CHECK.log", log_body)
    write_once(OUTPUT / "RESULT.json", body)
    print(json.dumps({"successful": successful, "tests_run": result.testsRun,
        "positive_methods": len(result.positive_methods), "result_bytes": len(body),
        "result_sha256": sha(body), "fixture_written": FIXTURE_WRITTEN,
        "named_read_reserved": NAMED_READ_RESERVED}))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())

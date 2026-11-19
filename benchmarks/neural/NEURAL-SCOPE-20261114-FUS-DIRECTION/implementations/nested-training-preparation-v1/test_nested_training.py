"""Generated-only nested46 preparation controls; no original data or model fits.

All projection, normalized-record, packet, manifest and receipt bodies stay in
bounded memory. Only a <=32KiB combined normal unittest log/result is written.
One genuine public-wrapper preparation is followed by narrowly scoped refusal
controls using the same authenticated dependencies. A selector compatibility
pass replaces predict with a uniform no-fit stub; actual admission, packet
decoding and scorer remain active. This does not establish protected isolation.
"""
import argparse
import base64
import copy
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


PREPARE_PIN = (4378, "0d81e1b4467a3b3077d51f3f9c240a9a9e2f2b99a659189fd41e90fb79b54cb0")
SELECTOR_PIN = (13267, "74fb73a271fe441207e5053f8c03a01a21705567018aca9b70498c40fd983cf4")
CONFIGS = (("uniform", None), ("squared_distance", None), ("cosine", None),
           ("linear_ridge", .001), ("linear_ridge", .01), ("linear_ridge", .1),
           ("linear_ridge", 1), ("linear_ridge", 10), ("linear_ridge", 100))
READ_CEILING = 2097152
REPORT_CEILING = 32768
W = DEPS = DEPENDENCY_ROOT = COHORT = None
READ_RESERVED = 0
PREPARE_CALLS = 0


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(body):
    return hashlib.sha256(body).hexdigest()


def reserve(n):
    global READ_RESERVED
    if type(n) is not int or n < 0 or READ_RESERVED + n > READ_CEILING:
        raise ValueError("bounded generated named-content read reservation")
    READ_RESERVED += n


def load_module(path, pin, name):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ordinary source ancestors")
    size, digest = pin
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size != size:
        raise ValueError("exact source extent")
    reserve(size + 1)
    with path.open("rb") as f:
        body = f.read(size + 1)
    if len(body) != size or sha(body) != digest:
        raise ValueError("exact source digest")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def dependency_reservation(module):
    reserve(sum(v[1] + 1 for v in module.DEPENDENCIES.values()))


class GeneratedCohort:
    def __init__(self, roster, mode="ordinary"):
        self.held = "L-S27-R99"
        self.rows = [r for r in roster if r[3] > 0 and r[0] != self.held]
        self.ids = [r[0] for r in self.rows]
        self.bodies = {}
        self.projection = {"schema": "fus_nested_training_input_v1", "held_record_id": self.held,
            "zero_record": {"record_id": "L-S45-R1", "reconciliation_sha256": sha(b"GENERATED zero")},
            "review_sha256": sha(b"GENERATED independent eligibility review"), "records": []}
        for index, (rid, animal, system, count, elapsed) in enumerate(self.rows):
            shape = [1, 3] if index % 2 == 0 else [2, 2]
            pitch = [1, 1] if index % 2 == 0 else [.25, .5]
            amplitude = index + 1
            finite_deltas = [amplitude, -amplitude] if index % 2 == 0 else [amplitude, 0, -amplitude]
            baseline = [2] * len(finite_deltas) + [0]
            if mode == "zero":
                memory = [2] * len(finite_deltas) + [1]
            elif mode == "nonfinite":
                memory = ["nan"] * len(finite_deltas) + [1]
            else:
                memory = [2 * (1 + d) for d in finite_deltas] + [1]
            trials, normalized_trials = [], []
            for ordinal in range(count):
                sid = "GENERATED:" + rid + ":trial:" + str(ordinal)
                if ordinal < 16:
                    qid = "q_" + format(index * 32 + ordinal, "032x")
                    timing = {"baseline_start": 0, "baseline_end": 1, "cue": 2,
                        "memory_start": 3, "memory_end": 4, "go": 5,
                        "acquisition_start": 3, "acquisition_end": 4}
                    trials.append({"source_trial_id": sid, "source_order": ordinal,
                        "disposition": "eligible", "query_id": qid, "direction": ordinal // 2,
                        "timing": timing, "exclusion_reason": None, "adjudication_sha256": None})
                    frames = [{"frame_id": sid + ":baseline", "source_order": 0,
                        "start": 0, "end": 1, "complete": True, "pixels": baseline},
                        {"frame_id": sid + ":memory", "source_order": 1,
                        "start": 3, "end": 4, "complete": True, "pixels": memory}]
                else:
                    trials.append({"source_trial_id": sid, "source_order": ordinal,
                        "disposition": "adjudicated_excluded", "query_id": None, "direction": None,
                        "timing": None, "exclusion_reason": "missing_timing",
                        "adjudication_sha256": self.projection["review_sha256"]})
                    frames = None
                normalized_trials.append({"source_trial_id": sid, "source_order": ordinal, "frames": frames})
            normalized = {"schema": "fus_normalized_fullfield_record_v1", "record_id": rid,
                "native_hz": 2, "source_float": "binary64", "shape": shape,
                "spatial_pitch": pitch, "spatial_pitch_unit": "generated_grid",
                "acquisition_census_sha256": sha(("GENERATED census " + rid).encode()),
                "trials": normalized_trials}
            body = wire(normalized)
            self.bodies[rid] = body
            record = {"record_id": rid, "native_hz": 2,
                "reconciliation_sha256": sha(("GENERATED reconciliation " + rid).encode()),
                "clock_mapping_sha256": sha(("GENERATED clock " + rid).encode()),
                "representation_sha256": sha(("GENERATED representation " + rid).encode()), "trials": trials}
            self.projection["records"].append({"fold_key": "fold_" + sha(("GENERATED fold " + rid).encode())[:32],
                "normalized_source": {"bytes": len(body), "sha256": sha(body)}, "record": record})
        self.input_wire = wire(self.projection)
        self.one_pass_bytes = sum(map(len, self.bodies.values()))
        self.output = None
        self.staged = {}
        self.loads = []

    def prepare(self, *, projection=None, loader=None, stage=None, fresh_dependencies=False, **overrides):
        global PREPARE_CALLS
        body = self.input_wire if projection is None else wire(projection)
        def normal_load(rid):
            if rid == self.held:
                raise AssertionError("outer-held normalized callback forbidden")
            self.loads.append(rid)
            return self.bodies[rid]
        def normal_stage(rid, qid, packet):
            if type(packet) is not bytes or (rid, qid) in self.staged:
                raise AssertionError("one immutable private packet per generated query")
            self.staged[(rid, qid)] = packet
        opts = {"expected_projection_sha256": sha(body), "max_projection_bytes": 8388608,
            "max_record_bytes": 262144, "max_total_record_bytes": 2 * self.one_pass_bytes,
            "max_map_bytes": 12, "max_packet_bytes": 8192, "max_total_packet_bytes": 2097152,
            "max_manifest_bytes": 8388608, "max_receipt_bytes": 2097152,
            "dependency_root": DEPENDENCY_ROOT}
        opts.update(overrides)
        PREPARE_CALLS += 1
        if fresh_dependencies:
            dependency_reservation(W)
            return W.prepare_training(body, loader or normal_load, stage or normal_stage, **opts)
        with mock.patch.object(W, "_dependencies", return_value=DEPS):
            return W.prepare_training(body, loader or normal_load, stage or normal_stage, **opts)

    def completed(self):
        if self.output is None:
            self.output = self.prepare(fresh_dependencies=True)
        return json.loads(self.output["manifest"]), json.loads(self.output["receipt"])


def png_rgb(item):
    """Independent raw scanline read for hand-expected pixels; no production encoder."""
    body = base64.b64decode(item["png_base64"], validate=True)
    if body[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("PNG signature")
    offset, compressed = 8, None
    for expected in (b"IHDR", b"IDAT", b"IEND"):
        n = struct.unpack(">I", body[offset:offset + 4])[0]
        kind = body[offset + 4:offset + 8]
        payload = body[offset + 8:offset + 8 + n]
        if kind != expected:
            raise AssertionError("PNG chunk sequence")
        if expected == b"IDAT":
            compressed = payload
        offset += n + 12
    raw = zlib.decompress(compressed)
    h, w = item["shape"]
    if len(raw) != h * (1 + 3 * w):
        raise AssertionError("complete generated PNG extent")
    rows = [raw[i * (1 + 3 * w):(i + 1) * (1 + 3 * w)] for i in range(h)]
    if any(row[0] != 0 for row in rows):
        raise AssertionError("generated PNG filter")
    return b"".join(row[1:] for row in rows)


class NestedControls(unittest.TestCase):
    def test_01_real_public_preparation_hand_scales_and_counts(self):
        manifest, receipt = COHORT.completed()
        self.assertEqual(COHORT.loads, COHORT.ids + COHORT.ids)
        self.assertNotIn(COHORT.held, COHORT.loads)
        self.assertEqual(len(COHORT.staged), 376)
        self.assertEqual(receipt["normalized_loads"], 94)
        self.assertEqual(receipt["returned_normalized_bytes"], 2 * COHORT.one_pass_bytes)
        self.assertEqual([receipt[k] for k in ("roster_records", "positive_records", "training_records", "declared_source_trials", "training_source_trials", "training_maps", "query_packets")],
                         [49, 48, 47, 20622, 20306, 752, 376])
        self.assertEqual(sum(r["valid_pixels"] for r in receipt["source_summaries"]), 1872)
        self.assertEqual(sum(r["invalid_pixels"] for r in receipt["source_summaries"]), 752)
        self.assertEqual(receipt["manifest_sha256"], sha(COHORT.output["manifest"]))
        self.assertEqual(receipt["manifest_bytes"], len(COHORT.output["manifest"]))
        self.assertEqual(receipt["total_packet_bytes"], sum(map(len, COHORT.staged.values())))
        for i, (episode, scale) in enumerate(zip(manifest["episodes"], receipt["scale_receipts"])):
            rid = COHORT.ids[i]
            expected_ids = [r for r in COHORT.ids if r != rid]
            self.assertEqual([r["record_id"] for r in scale["contributors"]], expected_ids)
            self.assertEqual(episode["scale"]["training_record_ids"], expected_ids)
            self.assertEqual(scale["training_records"], 46)
            self.assertEqual(scale["training_maps"], 736)
            self.assertEqual(scale["training_invalid_pixels"], 736)
            self.assertEqual(scale["training_valid_pixels"], 1840 if i % 2 == 0 else 1824)
            self.assertEqual(scale["scale"], 46 if i == 46 else 47)
            self.assertEqual(episode["scale"]["value"], scale["scale"])
            self.assertEqual(episode["scale"]["receipt_sha256"], sha(wire(scale)))
        for key in ("native_source_authenticated", "full_resolution_delivery_qualified", "protected_evaluation_established", "scientifically_qualified"):
            self.assertIs(receipt[key], False)
        self.assertIs(receipt["publication_requires_success_and_operator_commit"], True)

    def test_02_full_census_geometry_masks_and_early_query_preserved(self):
        manifest, _ = COHORT.completed()
        for i, episode in enumerate(manifest["episodes"]):
            original = COHORT.projection["records"][i]["record"]
            self.assertEqual(len(episode["trials"]), len(original["trials"]))
            self.assertEqual([t["source_order"] for t in episode["trials"]], list(range(len(original["trials"]))))
            support_ids = [original["trials"][j]["query_id"] for j in range(0, 16, 2)]
            query_ids = [original["trials"][j]["query_id"] for j in range(1, 16, 2)]
            self.assertEqual([p["query_id"] for p in episode["packets"]], query_ids)
            self.assertLess(original["trials"][1]["source_order"], original["trials"][14]["source_order"])
            for descriptor in episode["packets"]:
                body = COHORT.staged[(episode["record_id"], descriptor["query_id"])]
                self.assertEqual((len(body), sha(body)), (descriptor["bytes"], descriptor["sha256"]))
                packet = json.loads(body)
                self.assertEqual([m["map_id"] for m in packet["calibration"]], support_ids)
                self.assertEqual([m["direction_degrees"] for m in packet["calibration"]], list(range(0, 360, 45)))
                for image in packet["calibration"] + [packet["query"]]:
                    self.assertEqual(image["shape"], [1, 3] if i % 2 == 0 else [2, 2])
                    self.assertEqual(image["spatial_pitch"], [1, 1] if i % 2 == 0 else [.25, .5])
                    self.assertEqual(image["invalid_pixels"], 1)
                    self.assertEqual(image["saturated_pixels"], 2 if i == 46 else 0)
                    self.assertEqual(image["source_float"], "binary64")
        # Independent exact half-up expectations for d=±1/s47, d=±46/s47,
        # and clipped d=±47/s46; the invalid last pixel stays magenta.
        for index, expected in [(0, bytes([130] * 3 + [125] * 3 + [255, 0, 255])),
                                (45, bytes([252] * 3 + [128] * 3 + [3] * 3 + [255, 0, 255])),
                                (46, bytes([255] * 3 + [0] * 3 + [255, 0, 255]))]:
            episode = manifest["episodes"][index]
            packet = json.loads(COHORT.staged[(episode["record_id"], episode["packets"][0]["query_id"])])
            self.assertEqual(png_rgb(packet["query"]), expected)

    def test_03_all_metadata_admitted_before_any_loader(self):
        mutations = [lambda p: p["records"][0]["record"].__setitem__("record_id", COHORT.held),
                     lambda p: p["records"].pop(),
                     lambda p: p["records"][-1]["record"]["trials"].pop(),
                     lambda p: p["records"][-1]["record"]["trials"][15].__setitem__("direction", 6)]
        for i, mutate in enumerate(mutations):
            with self.subTest(case=i):
                projection = copy.deepcopy(COHORT.projection)
                mutate(projection)
                called = []
                def forbidden(*args):
                    called.append(args)
                    raise AssertionError("metadata refusal must precede callbacks")
                with self.assertRaises(ValueError):
                    COHORT.prepare(projection=projection, loader=forbidden, stage=forbidden)
                self.assertEqual(called, [])
                del projection

    def test_04_zero_or_nonfinite_corpus_refuses_before_staging(self):
        for mode in ("zero", "nonfinite"):
            with self.subTest(mode=mode):
                fixture = GeneratedCohort(DEPS["roster"].ROSTER, mode)
                stages = []
                with self.assertRaises(ValueError):
                    fixture.prepare(stage=lambda *args: stages.append(args[:2]))
                self.assertEqual(fixture.loads, fixture.ids)
                self.assertEqual(stages, [])
                self.assertIsNone(fixture.output)
                del fixture

    def test_05_loader_failure_or_changed_second_pass_returns_no_manifest(self):
        for kind in ("late_failure", "changed_second_pass"):
            with self.subTest(kind=kind):
                calls, stages = [], []
                completed = None
                def load(rid):
                    self.assertNotEqual(rid, COHORT.held)
                    calls.append(rid)
                    if kind == "late_failure" and len(calls) == 94:
                        raise RuntimeError("GENERATED late normalized loader failure")
                    body = COHORT.bodies[rid]
                    if kind == "changed_second_pass" and len(calls) == 48:
                        normalized = json.loads(body)
                        census = normalized["acquisition_census_sha256"]
                        normalized["acquisition_census_sha256"] = ("0" if census[0] != "0" else "1") + census[1:]
                        altered = wire(normalized)
                        self.assertEqual(len(altered), len(body))
                        self.assertNotEqual(sha(altered), sha(body))
                        return altered
                    return body
                with self.assertRaises((ValueError, RuntimeError)):
                    completed = COHORT.prepare(loader=load, stage=lambda rid, qid, body: stages.append((rid, qid)))
                self.assertIsNone(completed)
                self.assertEqual(len(calls), 94 if kind == "late_failure" else 48)
                self.assertEqual(len(stages), 368 if kind == "late_failure" else 0)

    def test_06_preflight_and_staging_byte_caps_refuse_complete_result(self):
        called = []
        def forbidden(*args):
            called.append(args)
            raise AssertionError("two-pass bytes must be admitted before load")
        with self.assertRaises(ValueError):
            COHORT.prepare(loader=forbidden, stage=forbidden,
                           max_total_record_bytes=2 * COHORT.one_pass_bytes - 1)
        self.assertEqual(called, [])
        COHORT.completed()
        first_bytes = len(next(iter(COHORT.staged.values())))
        stages = []
        with self.assertRaises(ValueError):
            COHORT.prepare(loader=lambda rid: COHORT.bodies[rid],
                           stage=lambda rid, qid, body: stages.append((rid, qid)),
                           max_total_packet_bytes=first_bytes)
        self.assertEqual(stages, [next(iter(COHORT.staged))])

    def test_07_stage_callback_failure_has_no_completed_manifest(self):
        attempted, retained = [], []
        def stage(rid, qid, body):
            attempted.append((rid, qid))
            if len(attempted) == 3:
                raise OSError("GENERATED private stage failure")
            retained.append((rid, qid))
        result = None
        with self.assertRaises(OSError):
            result = COHORT.prepare(loader=lambda rid: COHORT.bodies[rid], stage=stage)
        self.assertIsNone(result)
        self.assertEqual(attempted, list(COHORT.staged)[:3])
        self.assertEqual(retained, list(COHORT.staged)[:2])

    def test_08_accepted_selector_actual_arguments_exclude_private_truth(self):
        manifest, _ = COHORT.completed()
        selector = load_module(DEPENDENCY_ROOT / "outer-training-selection-v1/selection.py",
                               SELECTOR_PIN, "_nested_generated_selector")
        dependency_reservation(selector)
        modules = selector._dependencies(DEPENDENCY_ROOT)
        admitted = modules["admission"].admit(manifest, modules["roster"].ROSTER)
        self.assertEqual(len(admitted), 47)
        counter, current = [0], [None]
        root_keys = {"schema", "fold_key", "query_id", "class_angles_degrees", "context", "calibration", "query"}
        map_keys = {"map_id", "shape", "spatial_pitch", "spatial_pitch_unit", "native_hz",
                    "source_float", "scale", "invalid_pixels", "saturated_pixels", "png_base64"}
        def uniform_stub(*args, **kwargs):
            # Inspect ACTUAL arguments, not only a separately serialized file.
            self.assertEqual(len(args), 1)
            self.assertIs(type(args[0]), bytes)
            self.assertEqual(set(kwargs), {"method", "ridge_lambda", "max_packet_bytes", "max_map_pixels"})
            self.assertEqual((kwargs["method"], kwargs["ridge_lambda"]), CONFIGS[counter[0] % 9])
            self.assertEqual((kwargs["max_packet_bytes"], kwargs["max_map_pixels"]), (8192, 4))
            body = args[0]
            if counter[0] % 9 == 0:
                current[0] = body
            else:
                self.assertIs(body, current[0])
            packet = json.loads(body)
            self.assertEqual(set(packet), root_keys)
            self.assertEqual(set(packet["query"]), map_keys)
            for i, support in enumerate(packet["calibration"]):
                self.assertEqual(set(support), map_keys | {"direction_degrees"})
                self.assertEqual(support["direction_degrees"], i * 45)
            counter[0] += 1
            # The stub neither reads owner truth nor uses any private metadata.
            return {"query_id": packet["query_id"], "probabilities": [1 / 8] * 8}
        with mock.patch.object(selector, "_dependencies", return_value=modules):
            with mock.patch.object(modules["reference"], "predict", side_effect=uniform_stub):
                frozen = selector.select_fold(COHORT.output["manifest"],
                    expected_manifest_sha256=sha(COHORT.output["manifest"]),
                    load_packet=lambda rid, qid: COHORT.staged[(rid, qid)],
                    max_manifest_bytes=8388608, max_packet_bytes=8192,
                    max_total_packet_bytes=sum(map(len, COHORT.staged.values())), max_map_pixels=4)
        result = json.loads(frozen)
        self.assertEqual(counter[0], 3384)
        self.assertEqual(result["training_queries"], 376)
        for candidate in result["candidates"]:
            self.assertEqual(candidate["predictor_exceptions"], 0)
            self.assertEqual(candidate["equal_animal_session_balanced_accuracy"], {"numerator": 1, "denominator": 8})
        self.assertEqual(result["choices"]["template"]["method"], "squared_distance")
        self.assertEqual(result["choices"]["ridge"]["ridge_lambda"], .001)
        self.assertIs(result["scientifically_qualified"], False)


class Transcript(io.StringIO):
    def __init__(self):
        super().__init__()
        self.count = 0
    def write(self, text):
        n = len(text.encode("utf-8"))
        if self.count + n > 16384:
            raise ValueError("bounded actual unittest transcript")
        self.count += n
        result = super().write(text)
        sys.stdout.write(text)
        sys.stdout.flush()
        return result


class PositiveResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positive = []
    def addSuccess(self, test):
        self.positive.append(test.id())
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
    global W, DEPS, DEPENDENCY_ROOT, COHORT
    local = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=local / "prepare.py")
    parser.add_argument("--dependencies", type=Path, default=local.parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source / "prepare.py" if args.source.is_dir() else args.source
    output = args.output.absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError("new ordinary output required")
    for protected in (source.resolve().parent, args.dependencies.resolve()):
        if output.resolve() == protected or protected in output.resolve().parents:
            raise ValueError("output must not enter selected source closure")
    output.mkdir(mode=0o700)
    started = time.monotonic()
    DEPENDENCY_ROOT = args.dependencies
    W = load_module(source, PREPARE_PIN, "_nested_generated_prepare")
    dependency_reservation(W)
    DEPS = W._dependencies(DEPENDENCY_ROOT)
    COHORT = GeneratedCohort(DEPS["roster"].ROSTER)
    names = sorted(n for n in vars(NestedControls) if n.startswith("test_"))
    expected = ["__main__.NestedControls." + n for n in names]
    transcript = Transcript()
    result = unittest.TextTestRunner(stream=transcript, verbosity=2, resultclass=PositiveResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NestedControls))
    success = (result.wasSuccessful() and result.testsRun == len(expected) == 8 and
               result.positive == expected and not result.skipped and not result.expectedFailures
               and not result.unexpectedSuccesses)
    report = {"schema": "fus_generated_nested46_controls_v1", "generated_only": True,
        "successful": success, "tests_run": result.testsRun, "positive_methods": result.positive,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "prepare_source": {"bytes": PREPARE_PIN[0], "sha256": PREPARE_PIN[1]},
        "selector_source": {"bytes": SELECTOR_PIN[0], "sha256": SELECTOR_PIN[1]},
        "dependency_pins": {k: {"bytes": v[1], "sha256": v[2]} for k, v in W.DEPENDENCIES.items()},
        "prepare_calls": PREPARE_CALLS, "named_read_reserved_bytes": READ_RESERVED,
        "in_memory_generated_fixture": {"projection_bytes": len(COHORT.input_wire),
            "one_pass_normalized_bytes": COHORT.one_pass_bytes,
            "staged_packet_bytes": sum(map(len, COHORT.staged.values())),
            "manifest_bytes": 0 if COHORT.output is None else len(COHORT.output["manifest"]),
            "receipt_bytes": 0 if COHORT.output is None else len(COHORT.output["receipt"]),
            "declared_training_trial_rows": 20306, "training_records": 47, "query_packets": 376},
        "fixture_artifact_bytes": 0, "report_ceiling_bytes": REPORT_CEILING,
        "elapsed_seconds": time.monotonic() - started,
        "authentic_source_agreement_claimed": False, "protected_isolation_established": False,
        "scientific_qualification_claimed": False,
        "scope": "Generated source mechanics only; no original source, real neuronal values, native campaign, fit or model service. Packet arguments inspected directly; external custody remains a separate requirement."}
    log = transcript.getvalue().encode("utf-8")
    body = wire(report) + b"\n"
    if len(log) + len(body) > REPORT_CEILING:
        raise ValueError("combined generated report ceiling")
    write_once(output / "CHECK.log", log)
    write_once(output / "RESULT.json", body)
    print(json.dumps({"successful": success, "tests_run": result.testsRun,
        "positive_methods": len(result.positive), "result_bytes": len(body), "result_sha256": sha(body),
        "named_read_reserved_bytes": READ_RESERVED, "report_bytes": len(log) + len(body)}))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

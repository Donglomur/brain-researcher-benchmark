"""Generated-only equivalence controls; never opens source EEG or labels.

Run through the shared bounded test pool. Named existing source/profile files
are imported, but SourceCorpus.__init__ and the authentic Corpus are never run.
The in-memory generated handle exercises the literal retained calibration and
IntervalReader code. It is not an authenticated/admitted Helsinki source.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
from types import FunctionType, SimpleNamespace
import unittest

KEY = b"generated-only-assessor-key-000000"
P = A = R = SOURCES = None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class GeneratedHandle:
    def __init__(self, rid, header):
        self.rid, self.header, self.offset, self.reads = rid, header, 0, 0

    def seek(self, offset):
        self.offset = offset

    def read(self, count):
        assert count == self.header.record_bytes and self.offset % count == 0
        second = self.offset // count
        self.reads += 1
        seed = int(self.rid[3:])
        return b"".join(struct.pack("<256h", *(
            ((seed + second * 3 + channel * 7 + i) % 127) - 63
            for i in range(256))) for channel in range(len(self.header.channels)))


class GeneratedAsset:
    def __init__(self, rid, header):
        self.name = rid + ".edf"
        self.identity = ["generated-memory-only", rid, header.records]
        self.sha256 = hashlib.sha256(("generated:" + rid).encode()).hexdigest()
        self.handle = GeneratedHandle(rid, header)
        self.checks, self.changed = 0, False

    def check_unchanged(self):
        self.checks += 1
        if self.changed:
            raise A.SourceError("generated asset changed")


def corpus(length=30, longer=None):
    """Deliberately bypass authentic admission, using only invented byte streams."""
    electrodes = sorted({e for pair in SOURCES.intake.MONTAGE for e in pair})
    channels = tuple(SOURCES.intake.Channel(e, "uV", -32768.0, 32767.0,
                                          -32768, 32767, 256, i * 512)
                     for i, e in enumerate(electrodes))
    owner = object.__new__(A.SourceCorpus)
    owner.sources, owner._closed = SOURCES, False
    assets, headers = {}, {}
    for infant in range(1, 80):
        rid = "eeg" + str(infant)
        seconds = (longer or {}).get(rid, length)
        header = SOURCES.intake.Header(0, seconds, len(electrodes) * 512, channels,
                                      tuple((e, i) for i, e in enumerate(electrodes)),
                                      hashlib.sha256((rid + str(seconds)).encode()).hexdigest())
        headers[infant] = header
        assets[rid + ".edf"] = GeneratedAsset(rid, header)
    owner._corpus = SimpleNamespace(assets=assets, headers=headers)
    owner.source_lineage = {"generated_only": True, "fixture_id": "memory-v1"}
    owner.reader = A.IntervalReader(owner._lookup, SOURCES.intake.MONTAGE)
    return owner


def description(owner=None, rate=None):
    rate = rate or {"num": 256, "den": 1}
    records = []
    for infant in range(1, 80):
        rid = "eeg" + str(infant)
        seconds = owner._corpus.headers[infant].records if owner else 30
        count = seconds * rate["num"] // rate["den"]
        records.append(dict(recording_id=rid,
                            eeg_sha256=owner._corpus.assets[rid + ".edf"].sha256 if owner else "1" * 64,
                            sample_rate=deepcopy(rate), sample_count=count,
                            sample_zero_annotation_second=0, units="uV",
                            labels=[[int((i + expert) % 7 == 0) for i in range(seconds)]
                                    for expert in range(3)],
                            quality_flags=[i % 11 == 0 for i in range(seconds)]))
    folds = P.fold_map([r["recording_id"] for r in records], "generated-folds")
    return dict(schema=P.DESCRIPTION_SCHEMA, assessment_id='generated α \\ "samples"\n',
                protocol_id=P.PROTOCOL, source_version=P.SOURCE_VERSION,
                fold_seed="generated-folds", representation_sha256="2" * 64,
                detector_sha256="3" * 64, source_admission_sha256="4" * 64,
                montage=list(P.MONTAGE), recordings=records,
                development_by_fold={str(f): [next(rid for rid in sorted(folds) if folds[rid] != f)]
                                     for f in range(5)})


def rolling(owner, desc, budget=R.DEFAULT_CACHE_BYTES if R else 8 * 1024 * 1024):
    eligible = R._eligible(P, A, desc, owner.read_samples)
    if eligible is None:
        raise AssertionError("generated exact-code reader unexpectedly missed fast eligibility")
    actual, snapshots = eligible
    return R._RollingSamples(P, A, actual, snapshots, budget)


class Equivalence(unittest.TestCase):
    def test_complete_79_record_reference_and_existing_packet(self):
        owner = corpus(longer={"eeg1": 33})
        desc = description(owner)
        baseline = P.prepare_reference(desc, owner.read_samples, KEY)
        owner.reader.clear()
        stats = {}
        optimized = R.prepare_reference(P, desc, owner.read_samples, KEY,
                                        source_adapter=A, statistics=stats)
        self.assertEqual(stats["path"], "pinned_source_rolling")
        self.assertIs(type(optimized), P.Reference)
        self.assertEqual(optimized.document, baseline.document)
        self.assertEqual(optimized.reference_sha256, baseline.reference_sha256)
        self.assertEqual(list(optimized.case_rows()), list(baseline.case_rows()))
        for fold in range(5):
            self.assertEqual(optimized.partition(fold), baseline.partition(fold))
        self.assertEqual(stats["windows"], 82)
        self.assertEqual(stats["serialized_scalars"], (79 * 30 + 3) * 256 * 18)
        self.assertEqual(P.packet(optimized, "eeg1", 32, owner.read_samples),
                         P.packet(baseline, "eeg1", 32, owner.read_samples))
        self.assertEqual(desc, description(owner))

    def test_exact_full_bytes_overlap_boundaries_metadata(self):
        owner = corpus(longer={"eeg1": 36})
        desc = description(owner)
        engine = rolling(owner, desc)
        record = desc["recordings"][0]
        fold = P.fold_map(A.RECORD_IDS, desc["fold_seed"])["eeg1"]
        for k in (29, 30, 35, 29, 31):
            expected = P.canonical_bytes(P._payload(desc, KEY, record, k, fold, owner.read_samples))
            actual = b"".join(engine.payload_chunks(desc, KEY, record, k, fold))
            self.assertEqual(actual, expected)
            self.assertEqual(engine.payload_digest(desc, KEY, record, k, fold), hashlib.sha256(expected).hexdigest())
        self.assertLessEqual(len(engine.cache), 31)

    def test_partial_intervals_source_switch_and_clock_reset(self):
        owner = corpus(length=36)
        desc = description(owner)
        engine = rolling(owner, desc)
        for rid, start, stop in (("eeg1", 1, 7681), ("eeg1", 255, 257),
                                  ("eeg2", 512, 8192), ("eeg1", 0, 7680),
                                  ("eeg2", 35 * 256, 36 * 256)):
            self.assertEqual(b"".join(engine.sample_chunks(rid, start, stop)),
                             P.canonical_bytes(owner.read_samples(rid, start, stop)))
        engine.clear()
        self.assertEqual(len(engine.cache), 0)
        self.assertEqual(engine.retained, 0)
        self.assertEqual(set(engine.identities), {"eeg1", "eeg2"})
        self.assertEqual(b"".join(engine.sample_chunks("eeg1", 0, 256)),
                         P.canonical_bytes(owner.read_samples("eeg1", 0, 256)))

    def test_float_spelling_and_exact_row_slices(self):
        edges = [0, 0.0, -0.0, 1, 1.0, 5e-324, 1e-7, 1e-6, 1e20, 1e21,
                 1.7976931348623157e308, -1.7976931348623157e308, 10 ** 308,
                 -10 ** 308, 0.1, -0.1, 2 ** 53, float(2 ** 53)]
        rows = [list(edges) for _ in range(256)]
        fragment = R._Fragment(P, rows)
        self.assertEqual(b"[" + fragment.body + b"]", P.canonical_bytes(rows))
        for start, stop in ((0, 1), (255, 256), (1, 255), (0, 256)):
            self.assertEqual(b"[" + bytes(fragment.interval(start, stop)) + b"]",
                             P.canonical_bytes(rows[start:stop]))
        self.assertIn(b"0,0.0,-0.0,1,1.0", fragment.body)

    def test_rejects_same_invalid_numbers_and_layout(self):
        for value in (True, False, float("nan"), float("inf"), -float("inf"), 10 ** 10000, "1"):
            rows = [[0.0] * 18 for _ in range(256)]
            rows[0][0] = value
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(P.ContractError):
                    R._Fragment(P, rows)
                with self.assertRaises(P.ContractError):
                    P._finite(value, "EEG sample")
        for rows in ([], [[0] * 18] * 255, [[0] * 17] * 256, [None] * 256):
            with self.assertRaises(P.ContractError):
                R._Fragment(P, rows)

    def test_cache_byte_bounds_and_zero_cache(self):
        owner = corpus()
        desc = description(owner)
        expected = P.canonical_bytes(owner.read_samples("eeg1", 0, 7680))
        for bound in (0, 100, 45000):
            engine = rolling(owner, desc, bound)
            for _ in range(2):
                self.assertEqual(b"".join(engine.sample_chunks("eeg1", 0, 7680)), expected)
            self.assertLessEqual(engine.retained, bound)
            self.assertLessEqual(engine.stats["peak_cached_payload_bytes"], bound)
            self.assertLessEqual(engine.stats["peak_cached_seconds"], 31)

    def test_cache_hit_checks_asset_before_and_after(self):
        owner = corpus()
        engine = rolling(owner, description(owner))
        asset = owner._corpus.assets["eeg1.edf"]
        first = b"".join(engine.sample_chunks("eeg1", 0, 256))
        reads, checks = asset.handle.reads, asset.checks
        self.assertEqual(b"".join(engine.sample_chunks("eeg1", 0, 256)), first)
        self.assertEqual(asset.handle.reads, reads)
        self.assertEqual(asset.checks - checks, 2)
        iterator = engine.sample_chunks("eeg1", 0, 256)
        self.assertEqual(next(iterator), b"[")
        asset.changed = True
        with self.assertRaises(A.SourceError):
            b"".join(iterator)
        with self.assertRaises(A.SourceError):
            b"".join(engine.sample_chunks("eeg1", 0, 256))

    def test_identity_guard_survives_clear(self):
        for field in ("identity", "sha256", "header"):
            owner = corpus()
            engine = rolling(owner, description(owner))
            b"".join(engine.sample_chunks("eeg1", 0, 256))
            engine.clear()
            if field == "identity":
                owner._corpus.assets["eeg1.edf"].identity.append("changed-in-place")
            elif field == "sha256":
                owner._corpus.assets["eeg1.edf"].sha256 = "9" * 64
            else:
                owner._corpus.headers[1] = owner._corpus.headers[2]
            with self.subTest(field=field), self.assertRaises(A.SourceError):
                b"".join(engine.sample_chunks("eeg1", 0, 256))

    def test_reader_montage_and_lineage_mutations(self):
        for field in ("reader", "montage", "lineage", "closed", "lookup"):
            owner = corpus()
            engine = rolling(owner, description(owner))
            b"".join(engine.sample_chunks("eeg1", 0, 256))
            if field == "reader":
                owner.reader = A.IntervalReader(owner._lookup, SOURCES.intake.MONTAGE)
            elif field == "montage":
                owner.reader.montage = tuple(reversed(owner.reader.montage))
            elif field == "lineage":
                owner.source_lineage["fixture_id"] = "changed"
            elif field == "closed":
                owner._closed = True
            else:
                owner.reader.lookup = lambda rid: owner._lookup(rid)
            with self.subTest(field=field), self.assertRaises(A.SourceError):
                b"".join(engine.sample_chunks("eeg1", 0, 256))

    def test_callable_replacement_and_defaults_fail_closed(self):
        owner = corpus()
        desc = description(owner)
        engine = rolling(owner, desc)
        original = A.read_calibrated_record
        try:
            A.read_calibrated_record = lambda *args: original(*args)
            self.assertIsNone(R._eligible(P, A, desc, owner.read_samples))
            with self.assertRaises(A.SourceError):
                b"".join(engine.sample_chunks("eeg1", 0, 256))
        finally:
            A.read_calibrated_record = original
        try:
            original.__defaults__ = (None,)
            self.assertIsNone(R._eligible(P, A, desc, owner.read_samples))
            with self.assertRaises(A.SourceError):
                b"".join(engine.sample_chunks("eeg1", 0, 256))
        finally:
            original.__defaults__ = None

    def test_cloned_code_with_altered_globals_falls_back(self):
        owner = corpus()
        desc = description(owner)
        original = A.read_calibrated_record
        try:
            altered = dict(original.__globals__, FS=128)
            A.read_calibrated_record = FunctionType(original.__code__, altered)
            self.assertIsNone(R._eligible(P, A, desc, owner.read_samples))
        finally:
            A.read_calibrated_record = original

    def test_fallback_passes_original_arguments_without_copy(self):
        class NoCopy(dict):
            def __deepcopy__(self, memo):
                raise AssertionError("wrapper must not copy unsupported input")
        original_document = NoCopy(marker="sentinel")
        callback = lambda *args: None
        seen = []
        sentinel = object()
        def generic(document, reader, key):
            seen.append((document, reader, key))
            return sentinel
        facade = SimpleNamespace(prepare_reference=generic)
        self.assertIs(R.prepare_reference(facade, original_document, callback, KEY), sentinel)
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0][0], original_document)
        self.assertIs(seen[0][1], callback)
        self.assertIs(seen[0][2], KEY)

    def test_unsupported_readers_and_source_descriptors(self):
        owner = corpus()
        desc = description(owner)
        self.assertIsNone(R._eligible(P, A, desc, lambda *a: owner.read_samples(*a)))
        class SubReader(A.IntervalReader):
            pass
        owner.reader = SubReader(owner._lookup, SOURCES.intake.MONTAGE)
        self.assertIsNone(R._eligible(P, A, desc, owner.read_samples))
        owner.reader = A.IntervalReader(owner._lookup, SOURCES.intake.MONTAGE)
        desc["recordings"][0]["eeg_sha256"] = "f" * 64
        self.assertIsNone(R._eligible(P, A, desc, owner.read_samples))
        desc = description(owner)
        owner.reader.montage = tuple(reversed(owner.reader.montage))
        self.assertIsNone(R._eligible(P, A, desc, owner.read_samples))

    def test_rational_rate_callback_fallback_document_equality(self):
        desc = description(rate={"num": 5, "den": 2})
        calls = []
        def callback(rid, start, stop):
            calls.append((rid, start, stop))
            return [[float((i + c) % 3) for c in range(18)] for i in range(start, stop)]
        baseline = P.prepare_reference(desc, callback, KEY)
        baseline_calls = calls[:]
        calls.clear()
        stats = {}
        actual = R.prepare_reference(P, desc, callback, KEY, source_adapter=A, statistics=stats)
        self.assertEqual(actual.document, baseline.document)
        self.assertEqual(actual.reference_sha256, baseline.reference_sha256)
        self.assertEqual(calls, baseline_calls)
        self.assertEqual(stats, {"path": "unchanged_generic"})

    def test_validation_errors_preserved_without_source_access(self):
        desc = description(rate={"num": 5, "den": 2})
        def forbidden(*args):
            raise AssertionError("invalid metadata must not read samples")
        for key, document in ((b"short", desc), (KEY, dict(desc, montage=[]))):
            with self.assertRaises(P.ContractError) as old:
                P.prepare_reference(document, forbidden, key)
            with self.assertRaises(P.ContractError) as new:
                R.prepare_reference(P, document, forbidden, key, source_adapter=A)
            self.assertEqual(str(old.exception), str(new.exception))

    def test_new_cache_lifecycle_does_not_reuse_other_source(self):
        left, right = corpus(), corpus()
        right._corpus.assets["eeg1.edf"].identity.append("independent-instance")
        a, b = rolling(left, description(left)), rolling(right, description(right))
        self.assertEqual(b"".join(a.sample_chunks("eeg1", 0, 256)),
                         b"".join(b.sample_chunks("eeg1", 0, 256)))
        self.assertIsNot(a.cache, b.cache)
        self.assertEqual(a.stats["cache_misses"], 1)
        self.assertEqual(b.stats["cache_misses"], 1)
        self.assertNotEqual(a.identities["eeg1"], b.identities["eeg1"])


def measure():
    """Small generated sequential-window measurement; no corpus extrapolation."""
    rows = []
    expected = None
    for repetition in range(3):
        for kind in (("generic", "rolling") if repetition % 2 == 0 else ("rolling", "generic")):
            owner = corpus(longer={"eeg1": 69})
            desc = description(owner)
            record = desc["recordings"][0]
            fold = P.fold_map(A.RECORD_IDS, desc["fold_seed"])["eeg1"]
            engine = rolling(owner, desc) if kind == "rolling" else None
            started = time.perf_counter()
            hashes = [(engine.payload_digest(desc, KEY, record, k, fold) if engine else
                       P.digest(P._payload(desc, KEY, record, k, fold, owner.read_samples)))
                      for k in range(29, 69)]
            elapsed = time.perf_counter() - started
            if expected is None:
                expected = hashes
            if hashes != expected:
                raise AssertionError("measurement payload hashes differ")
            rows.append(dict(path=kind, repetition=repetition, seconds=elapsed,
                             generated_source_second_reads=owner._corpus.assets["eeg1.edf"].handle.reads,
                             scalar_serializations=(engine.stats["serialized_scalars"] if engine else 40 * 30 * 256 * 18),
                             statistics=deepcopy(engine.stats) if engine else None))
    return dict(schema="nexp005-generated-rolling-measurement-v1", generated_only=True,
                authentic_arrays_read=False, windows=40, seconds_of_invented_source=69,
                channels=18, sample_rate=256, trials=rows,
                equality="all 40 full-payload SHA256 values equal across all six trials",
                scope="CPU-shared local generated fixture; no authentic speedup or corpus runtime claim")


def main():
    global P, A, R, SOURCES
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--measurement-output", type=Path)
    parser.add_argument("--tests", nargs="*")
    args = parser.parse_args()
    adapter_root = args.repository / "benchmarks/neural/NEURAL-EXP-005/implementations/source-admission-v1"
    sys.path.insert(0, str(adapter_root))
    A = load("_generated_nexp005_adapter", adapter_root / "source_adapter.py")
    SOURCES = A.load_sources()
    P = SOURCES.current
    R = load("_generated_nexp005_rolling", Path(__file__).with_name("rolling_reference.py"))
    suite = (unittest.TestSuite(Equivalence(name) for name in args.tests) if args.tests
             else unittest.defaultTestLoader.loadTestsFromTestCase(Equivalence))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    if args.measurement_output:
        document = measure()
        body = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
        if len(body) > 16384:
            raise ValueError("generated measurement exceeds declared 16 KiB output bound")
        with args.measurement_output.open("xb") as handle:
            handle.write(body)
        print(json.dumps({"measurement_bytes": len(body), "measurement_sha256": hashlib.sha256(body).hexdigest()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

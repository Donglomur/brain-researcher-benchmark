"""Focused invented controls; no HTTP/HDF5 imports, sockets or authentic arrays."""
import copy
import argparse
import io
import json
import hashlib
import struct
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import range_io as r
import manifest
import pipeline

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--original-root", type=Path, default=ROOT.parent / "neural-063" / "complete-omission-v1")
options, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]


class Headers:
    def __init__(self, values): self.values = list(values)
    def items(self): return iter(self.values)


def asset():
    return r.Asset("1", "https://visual-behavior-ophys-data.s3.us-west-2.amazonaws.com/"
        "visual-behavior-ophys/behavior_ophys_experiments/behavior_ophys_experiment_1.nwb?versionId=V",
        "V", '"abcd-2"', 10, "a" * 128).validate()


def limits(**changes):
    values = dict(max_requests=8, response_body_bytes=32, logical_read_bytes=64,
                  record_bytes=8192, block_bytes=4, cache_blocks=2, read_operation_bytes=8,
                  hdf5_cache_bytes=8, seconds=60, request_seconds=5)
    values.update(changes)
    return r.Limits(**values)


def request(start=0, end=3):
    return Headers([("Accept-Encoding", "identity"), ("If-Match", '"abcd-2"'),
                    ("Range", f"bytes={start}-{end}")])


def response(start=0, end=3):
    return Headers([("x-amz-version-id", "V"), ("ETag", '"abcd-2"'),
                    ("Content-Range", f"bytes {start}-{end}/10"), ("Content-Length", str(end-start+1))])


def started(budget=None):
    budget = budget or r.Budget(limits())
    a = asset()
    budget.begin(a, "GET", a.url, request())
    return a, budget


class TransportControls(unittest.TestCase):
    def test_accepted_range_binds_body_and_keeps_false_full_hash_claim(self):
        a, b = started()
        b.response(a, 206, a.url, response())
        b.body(a, b"abcd")
        self.assertEqual((b.requests, b.body_reserved, b.body_observed), (1, 4, 4))
        self.assertIsNone(b.pending)
        self.assertEqual(b.records[0]["sha256"], "88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589")
        self.assertFalse(b.receipt()["full_object_BLAKE2b_verified"])
        self.assertIsNone(b.receipt()["physical_wire_bytes"])

    def test_pre_request_refusals_do_not_consume_or_dispatch(self):
        variants = [request(-1, 2), request(4, 2), request(7, 10), request(0, 9),
                    Headers([("Accept-Encoding", "identity"), ("If-Match", '"abcd-2"')]),
                    Headers(request().values + [("range", "bytes=0-3")])]
        for headers in variants:
            with self.subTest(headers=headers.values):
                b = r.Budget(limits()); a = asset()
                with self.assertRaises(r.RangeContractError): b.begin(a, "GET", a.url, headers)
                self.assertEqual((b.requests, b.body_reserved), (0, 0))
        for method, url in [("HEAD", asset().url), ("GET", asset().url + "&other=1")]:
            b = r.Budget(limits())
            with self.assertRaises(r.RangeContractError): b.begin(asset(), method, url, request())
            self.assertEqual(b.requests, 0)

    def test_budget_exhaustion_occurs_before_a_second_request(self):
        for setting in ({"max_requests": 1}, {"response_body_bytes": 4}, {"record_bytes": 512}):
            with self.subTest(setting=setting):
                a, b = started(r.Budget(limits(**setting)))
                b.response(a, 206, a.url, response()); b.body(a, b"abcd")
                with self.assertRaises(r.RangeContractError): b.begin(a, "GET", a.url, request(4, 7))
                self.assertEqual((b.requests, b.body_reserved, b.record_reserved), (1, 4, 512))

    def test_response_identity_encoding_and_duplicate_headers_fail_closed(self):
        changes = [("x-amz-version-id", "other"), ("ETag", '"other-2"'),
                   ("Content-Range", "bytes 0-3/11"), ("Content-Range", "bytes 1-4/10"),
                   ("Content-Length", "3"), ("Content-Encoding", "gzip"), ("Transfer-Encoding", "chunked")]
        for key, value in changes:
            a, b = started(); h = response()
            h.values = [(k, v) for k, v in h.values if k != key] + [(key, value)]
            with self.subTest(key=key, value=value):
                with self.assertRaises(r.RangeContractError): b.response(a, 206, a.url, h)
                self.assertEqual(b.body_observed, 0)
        for key in ("etag", "content-length", "X-AMZ-VERSION-ID", "Content-Range"):
            a, b = started(); h = response(); h.values.append((key, "duplicate"))
            with self.assertRaises(r.RangeContractError): b.response(a, 206, a.url, h)

    def test_full_response_redirect_and_unbound_response_refused(self):
        for status, history, suffix in [(200, (), ""), (416, (), ""), (206, (object(),), ""), (206, (), "&redirect=1")]:
            a, b = started()
            with self.assertRaises(r.RangeContractError): b.response(a, status, a.url + suffix, response(), history)
        b = r.Budget(limits())
        with self.assertRaises(r.RangeContractError): b.response(asset(), 206, asset().url, response())

    def test_short_extra_and_unverified_bodies_preserve_failed_reservation(self):
        for body in (b"abc", b"abcde"):
            a, b = started(); b.response(a, 206, a.url, response())
            with self.assertRaises(r.RangeContractError): b.body(a, body)
            b.abort()
            self.assertEqual((b.body_reserved, b.body_observed, b.requests), (4, 0, 1))
            self.assertTrue(b.receipt()["failed"])
            with self.assertRaises(r.RangeContractError): b.begin(a, "GET", a.url, request())
        a, b = started()
        with self.assertRaises(r.RangeContractError): b.body(a, b"abcd")

    def test_bounded_file_cannot_trigger_full_fetch_and_counts_reads(self):
        class Stream(io.BytesIO):
            def __init__(self): super().__init__(b"0123456789"); self.calls = []
            def read(self, size=-1): self.calls.append(size); return super().read(size)
        stream = Stream(); b = r.Budget(limits()); f = r.BoundedFile(stream, asset(), b)
        for size in (-1, 9, True):
            with self.assertRaises(r.RangeContractError): f.read(size)
        self.assertEqual(stream.calls, [])
        self.assertEqual(f.read(3), b"012")
        f.seek(-2, 2); out = bytearray(2); self.assertEqual(f.readinto(out), 2)
        self.assertEqual(bytes(out), b"89")
        self.assertEqual((b.logical_reads, stream.calls), (5, [3, 2]))
        for offset, whence in [(-1, 0), (1, 2), (0, 4)]:
            with self.assertRaises(r.RangeContractError): f.seek(offset, whence)

    def test_actual_configured_cache_fetcher_clips_final_block(self):
        calls = []
        cache = types.SimpleNamespace(name="blockcache", maxblocks=2, blocksize=4,
            fetcher=lambda start, end: calls.append((start, end)) or b"x" * (end-start))
        stream = types.SimpleNamespace(cache=cache)
        r.configure_cache(stream, asset(), limits())
        self.assertEqual(stream.cache.fetcher(8, 12), b"xx")
        self.assertEqual(calls, [(8, 10)])
        cache.maxblocks = 3
        with self.assertRaises(r.RangeContractError): r.configure_cache(stream, asset(), limits())

    def test_session_closes_even_when_file_or_cache_cleanup_fails(self):
        for fail in ("stream", "cache"):
            events = []
            def close():
                events.append("stream")
                stream.cache = None  # installed fsspec discards this in read-mode close
                if fail == "stream": raise RuntimeError("generated close failure")
            def clear():
                events.append("cache")
                if fail == "cache": raise RuntimeError("generated clear failure")
            stream = types.SimpleNamespace(close=close, cache=types.SimpleNamespace(
                _fetch_block_cached=types.SimpleNamespace(cache_clear=clear)))
            with self.assertRaises(RuntimeError): r.close_runtime(stream, lambda: events.append("session"))
            self.assertEqual(events, ["stream", "cache", "session"])


class ScientificControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pins = json.loads((ROOT / "ORIGINAL_SOURCES.json").read_text())["files"]
        cls.native, cls.alg, cls.original_io = pipeline.load_original(options.original_root, pins)

    def fixture(self):
        records = [{"key": "p:" + str(i), "start": i * .75, "omitted": i in (4, 8), "image": "a"} for i in range(11)]
        rows = [{"ophys_experiment_id": str(i), "ophys_session_id": "10", "mouse_id": "1", "split": "query"} for i in (1, 2)]
        planes = {row["ophys_experiment_id"]: {"experiment": row["ophys_experiment_id"], "session": "10", "mouse": "1", "split": "query",
            "presentations": copy.deepcopy(records), "presentation_sha256": pipeline.digest(records),
            "neural_metadata": {"clock": [i / 100 for i in range(1001)], "columns": [0, 1]}} for row in rows}
        return rows, planes

    def test_complete_session_uses_original_schedule_support_and_all15bins(self):
        rows, planes = self.fixture()
        session, supports = pipeline.derive_session(rows, planes, self.alg)
        self.assertEqual(session["selected"], self.alg.schedule(planes["1"]["presentations"])["selected"])
        self.assertEqual(len(session["selected"]), 2)
        for eid, support in supports.items():
            self.assertEqual(support["supported"], 2)
            self.assertEqual([len(e["spans"]) for e in support["supported_events"]], [15, 15])
            self.assertEqual(support["privacy"]["held_target_intervals"], 2)
            self.assertEqual(support["privacy"]["intersections"], 0)

    def test_missing_plane_disagreement_and_swapped_hierarchy_are_refused(self):
        rows, planes = self.fixture()
        with self.assertRaises(r.RangeContractError): pipeline.derive_session(rows, {"1": planes["1"]}, self.alg)
        for field in ("experiment", "session", "mouse", "split"):
            changed = copy.deepcopy(planes); changed["2"][field] = "other"
            with self.assertRaises(r.RangeContractError): pipeline.derive_session(rows, changed, self.alg)
        changed = copy.deepcopy(planes); changed["2"]["presentations"][0]["image"] = "other"
        with self.assertRaises(r.RangeContractError): pipeline.derive_session(rows, changed, self.alg)

    def test_clock_unsupported_stays_in_complete_census(self):
        rows, planes = self.fixture(); planes["2"]["neural_metadata"]["clock"] = [0., 10.]
        _, supports = pipeline.derive_session(rows, planes, self.alg)
        self.assertEqual((supports["2"]["supported"], supports["2"]["clock_unsupported"]), (0, 2))
        self.assertEqual(supports["2"]["scheduled"], 2)
        self.assertEqual(supports["1"]["supported"], 2)

    def test_nested_wrong_schema_and_identity_are_not_role_equivalence(self):
        ref = {"visibility": "operator"}
        store = types.SimpleNamespace(read_json=lambda *a, **k: {"schema": "old_full_hash_schema"})
        with self.assertRaises(r.RangeContractError): pipeline.read_value(store, ref, "role", 1024, "range_schema")
        with self.assertRaises(r.RangeContractError): pipeline.read_value(store, {"visibility": "participant"}, "role", 1024, "range_schema")
        with self.assertRaisesRegex(r.RangeContractError, "exact six-module source closure"):
            pipeline.load_original(ROOT, {})

    def test_projection_wrapper_preserves_valid_columns_baseline_and_slice_hashes(self):
        class Array:
            dtype = "float64"
            def __init__(self, rows): self.rows = rows; self.shape = (len(rows), 3)
            def tobytes(self, order):
                self.order = order
                return b"".join(struct.pack("<d", value) for row in self.rows for value in row)
            def tolist(self): return [list(row) for row in self.rows]
        values = [[0., 9999., float(2*i)] for i in range(15)]
        class Dataset:
            def __getitem__(self, key):
                span, columns = key
                if columns != slice(None): raise AssertionError("native full-row read changed")
                return Array(values[span])
        records = [{"image": "a", "omitted": False, "start": i*.75} for i in range(4)]
        spans = [[i, i+1] for i in range(15)]
        support = {"supported_events": [{"key": "p:3", "presentation_index": 3, "onset": 2.25, "spans": spans}]}
        row = {"ophys_experiment_id": "1", "mouse_id": "2", "ophys_session_id": "3", "split": "query",
               "context": {key: "invented" for key in self.alg.CONTEXT}}
        rows, receipts = pipeline.project_events(Dataset(), {"columns": [2, 0]}, records, support, self.alg, row)
        self.assertEqual(rows[0]["history"], [float(i-11) for i in range(12)])
        self.assertEqual(rows[0]["target"], [1., 2., 3.])
        self.assertEqual(rows[0]["spans"], spans)
        self.assertEqual([p["start_relative_seconds"] for p in rows[0]["previous"]], [-2.25, -1.5, -.75])
        self.assertEqual(len(receipts), 15)
        for i, receipt in enumerate(receipts):
            expected = b"".join(struct.pack("<d", value) for value in values[i])
            self.assertEqual(receipt, {"left": i, "right": i+1, "shape": [1, 3], "dtype": "float64",
                                      "sha256_C_order": hashlib.sha256(expected).hexdigest()})

    def test_layout_reads_metadata_only_and_reports_decompression_shape(self):
        class Dataset:
            shape = (100, 4); size = 400; chunks = (10, 4)
            dtype = types.SimpleNamespace(itemsize=8)
            compression = "gzip"; compression_opts = 4; shuffle = True; fletcher32 = False; scaleoffset = None
            id = types.SimpleNamespace(get_storage_size=lambda: 1024)
            def __getitem__(self, key): raise AssertionError("neural array read during layout")
        got = pipeline.layout(Dataset())
        self.assertEqual((got["full_logical_array_bytes"], got["uncompressed_chunk_bytes"], got["dataset_storage_bytes"]), (3200, 320, 1024))

    def test_full_original_cohort_and_mouse_split_cannot_be_reduced(self):
        assignments = {str(i): "fit" if i <= 73 else "validation" if i <= 88 else "query" for i in range(1, 108)}
        counts = [133066 // 1936 + (i < 133066 % 1936) for i in range(1936)]
        rows = []
        for i, count in enumerate(counts):
            session = i % 703 + 1; mouse = str((session-1) % 107 + 1)
            rows.append({"ophys_experiment_id": str(i+1), "ophys_session_id": str(session),
                         "mouse_id": mouse, "split": assignments[mouse], "rois": [None] * count})
        selection = {"experiments": rows, "mouse_assignments": assignments}
        self.assertEqual(len(manifest.full_scope(selection)), 1936)
        with self.assertRaises(r.RangeContractError): manifest.full_scope({**selection, "experiments": rows[:-1]})
        broken = copy.copy(assignments); broken["107"] = "fit"
        with self.assertRaises(r.RangeContractError): manifest.full_scope({**selection, "mouse_assignments": broken})


if __name__ == "__main__":
    unittest.main()

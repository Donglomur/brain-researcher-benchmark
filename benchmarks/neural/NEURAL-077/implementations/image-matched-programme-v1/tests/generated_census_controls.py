"""Generated private-driver controls. No production viewer or neural data imports."""
import argparse
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

D = ROOT = None
WRITTEN = READ = 0
FIXTURE_CAP = 16 * 1024**2
READ_CAP = 64 * 1024**2


def put(path, body, *, charge=True):
    global WRITTEN
    if charge:
        if WRITTEN + len(body) > FIXTURE_CAP:
            raise RuntimeError("Generated fixture write cap")
        WRITTEN += len(body)
    with path.open("xb") as stream:
        stream.write(body)


def get(path):
    global READ
    body = path.read_bytes(); READ += len(body)
    if READ > READ_CAP:
        raise RuntimeError("Generated read cap")
    return body


def scalar_pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def byte_wire(header, image=b""):
    body = D.encode(header)
    return struct.pack("!II", len(body), len(image)) + body + image


def byte_unpack(raw):
    n, m = struct.unpack("!II", raw[:8])
    if len(raw) != 8 + n + m:
        raise ValueError("fixture wire extent")
    return json.loads(raw[8:8+n]), raw[8+n:]


class FakeLimits:
    max_actions = 128
    max_images = 32
    max_output_bytes = 128 * 1024**2
    wall_seconds = 300

    def validate(self):
        return None


def state():
    return {"record": "query", "start_sample": -256, "stop_sample": 768,
            "units_per_division": 20, "channels": ["Cz", "Pz"], "display_filter": "none"}


class GeneratedRows:
    def __init__(self, ids):
        self.ids, self.accesses = ids, []
        self.current = self.cached = None

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, ordinal):
        if not 0 <= ordinal < len(self.ids):
            raise ValueError("fixture index")
        if self.current != ordinal:
            self.accesses.append(ordinal)
            self.current = ordinal
            self.cached = {"trial_id": self.ids[ordinal]}
        return self.cached

    def clear(self):
        self.current = self.cached = None


class GeneratedRoute:
    """Explicit byte/metadata stub, never a PNG renderer or real packet loader."""
    def __init__(self, owner, *, fail_at=None, lower_after=None, close_fail=False):
        self.owner, self.fail_at, self.lower_after, self.close_fail = owner, fail_at, lower_after, close_fail
        ids = tuple("q-" + format(i + 1, "032x") for i in range(6400))
        self.rows = GeneratedRows(ids)
        self.session = types.SimpleNamespace(_closed=False,
            _files={"generated_extent_only": {"bytes": D.PUBLIC_BYTES-D.MANIFEST["bytes"]}},
            _rows={key: {"bytes": 7, "sha256": hashlib.sha256(key.encode()).hexdigest()} for key in ids})
        self.data = {"rows": self.rows, "trial_ids": ids, "_session": self.session,
                     "profile_commitment": "2" * 64, "_budget": None}
        self.calls = []; self.finalize_calls = 0; self.rendering = False
        route = self

        class View:
            def __init__(self, data, ordinal, mode, output):
                if mode != "four_demo":
                    raise AssertionError("four demos")
                self.dataset, self.ordinal, self.output = data, ordinal, Path(output)
                self.query = data["rows"][ordinal]
                self.state, self.closed, self.sequence = state(), False, 0
                self.prompt = "native permission; " + self.query["trial_id"]
                self.frame_encoding = {"scope": "generated-byte-stub-not-image-codec"}
                self.output.mkdir(); (self.output / "frames").mkdir()
                put(self.output / "SESSION.json", b"{}\n", charge=True)
                put(self.output / "prompt.txt", b"generated\n", charge=True)
                route.calls.append(ordinal)
                if ordinal == route.lower_after:
                    data["_budget"].write_limit = data["_budget"].writes + D.FINAL_RESERVE + D.CASE_RESERVE - 1

            def handle(self, raw):
                if raw != b'{"action":"inspect"}':
                    route.finalize_calls += 1
                    raise AssertionError("No finalize/prediction request")
                if self.ordinal == route.fail_at:
                    put(self.output / "frames/0000.png", b"partial", charge=True)
                    raise ValueError("injected generated session failure")
                self.sequence = 1
                # Deliberately not a valid PNG; this tests bytes/custody only.
                image = b"generated-image-bytes-" + self.ordinal.to_bytes(4, "big")
                put(self.output / "frames/0000.png", image, charge=True)
                put(self.output / "action-0000.json", b"{}\n", charge=True)
                return {"bytes": image, "ordinal": self.ordinal}

        def projection(result):
            return {"status": "rendered", "remaining_actions": 127,
                    "image": {"mime_type": "image/png", "bytes": len(result["bytes"])}}, bytes(result["bytes"])

        def ready(view, limits, episode_id, *, budget=None):
            return {"status": "ready", "episode_id": episode_id, "trial_id": view.query["trial_id"],
                "prompt": view.prompt, "actions": {}, "limits": {}, "instructions": "generated only",
                "profile": D.PROFILE, "profile_commitment": "2" * 64}

        def programme_ready(view, limits, episode_id, *, budget=None):
            row = ready(view, limits, episode_id, budget=budget)
            row["prompt"] = row["prompt"].replace("native permission", "programme permission")
            return row

        def close(data):
            data["rows"].clear(); data["_session"]._closed = True
            if route.close_fail:
                raise OSError("injected source close failure")

        viewer = types.SimpleNamespace(Session=View, initial_state=state, encode=D.encode,
            ordered_ids=lambda data: data["trial_ids"], close_source=close)
        self.direct = types.SimpleNamespace(v=viewer, projection=projection, ready_header=ready,
            wire=byte_wire, unpack=byte_unpack, Limits=FakeLimits)
        self.programme = types.SimpleNamespace(projection=projection, ready_header=programme_ready,
            wire=byte_wire, unpack=byte_unpack)
        self.adapter = types.SimpleNamespace(programme_prompt=lambda text: text.replace("native permission", "programme permission"))

    def dataset_for(self, deps, public, *, profile, manifest_pin, budget):
        if profile != D.PROFILE or manifest_pin != D.MANIFEST:
            raise AssertionError("binding arguments")
        self.data["_budget"] = budget
        return self.data

    def dependencies(self, root, *, profile):
        return {"transport": self.direct, "image_transport": self.programme, "adapter": self.adapter,
                "provider": types.SimpleNamespace(dataset_for=self.dataset_for)}


class Controls(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / self._testMethodName
        self.root.mkdir()

    def plan(self):
        source, public = self.root / "source", self.root / "public"
        source.mkdir(); public.mkdir()
        return {"schema": "erp-initial-image-census-plan/v1", "qualification": "shared_render_local_initial_projections",
            "source_root": str(source), "source_guard": {"path": str(self.root / "guard.json"), "pin": scalar_pin(b"{}")},
            "accepted_source_commit": "a" * 40, "public_root": str(public), "manifest": dict(D.MANIFEST),
            "output": str(self.root / "run"), "runtime": {"invocation": "generated", "prefix": "generated",
                "python_version": [3,11,6], "numpy_version": "NOT_IMPORTED", "numpy_origin": "generated",
                "zlib_compile_version": "NOT_IMPORTED", "zlib_runtime_version": "NOT_IMPORTED",
                "bodies": [{"path": str(self.root / "runtime.bin"), "pin": scalar_pin(b"x")}]},
            "limits": {"read_bytes": 256*1024**2, "write_bytes": 26*1024**3,
                       "work_seconds": 120, "closure_seconds": 30}, "hash_whole_shards": False}

    def run_generated(self, *, fail_at=None, lower_after=None, close_fail=False, full=False, expired=False):
        global WRITTEN
        plan = self.plan(); route = GeneratedRoute(self, fail_at=fail_at, lower_after=lower_after, close_fail=close_fail)
        plan["limits"]["write_bytes"] = FIXTURE_CAP - WRITTEN + D.CASE_RESERVE + D.FINAL_RESERVE
        route.rendering = True
        intervals = []

        @contextmanager
        def deadline(seconds):
            intervals.append(seconds)
            yield

        pair = types.SimpleNamespace(dependencies=route.dependencies, deadline=deadline)
        def sources(plan, budget):
            return Path(plan["source_root"]), {D.PREFIX+"image-matched-programme-v1/pair.py": b"generated, never executed"}, {"generated": True}
        fsyncs = []
        before_run_charge = WRITTEN
        real_driver_write = D.write_fd
        def metered_driver_write(fd, body, budget, **kwargs):
            global WRITTEN
            if WRITTEN + len(body) > FIXTURE_CAP:
                raise RuntimeError("Independent generated fixture ceiling")
            WRITTEN += len(body)
            return real_driver_write(fd, body, budget, **kwargs)
        real_fsync = os.fsync
        def recording_fsync(fd):
            fsyncs.append(fd)
            if not full:
                real_fsync(fd)
        clock = (lambda: 500.0) if expired else D.time.monotonic
        with patch.object(D, "runtime_identity", return_value={"generated_stub": True}), \
             patch.object(D, "authenticate_sources", side_effect=sources), \
             patch.object(D, "module", return_value=pair), \
             patch.object(D, "write_fd", side_effect=metered_driver_write), \
             patch.object(D.os, "fsync", side_effect=recording_fsync), \
             patch.object(D.time, "monotonic", side_effect=clock), redirect_stdout(io.StringIO()) as captured:
            code = D.run(plan, scalar_pin(b"generated plan"), 0.0 if expired else clock())
        emitted = json.loads(captured.getvalue())
        self.assertGreaterEqual(WRITTEN-before_run_charge, emitted["cumulative_write_charge_bytes"])
        self.assertLessEqual(WRITTEN, FIXTURE_CAP)
        result = json.loads(get(Path(plan["output"]) / "RESULT.json"))
        self.assertNotIn("numpy", sys.modules)
        return code, result, route, Path(plan["output"]), intervals, fsyncs

    def test_01_plan_refuses_bad_manifest_overlap_and_null_binding(self):
        plan = self.plan()
        D.validate_plan(plan)
        for mutate in (lambda p: p.update(manifest={"bytes": 1, "sha256": "0"*64}),
                       lambda p: p.update(output=p["source_root"]),
                       lambda p: p.update(accepted_source_commit=None),
                       lambda p: p["limits"].update(write_bytes=True)):
            bad = json.loads(json.dumps(plan)); mutate(bad)
            with self.assertRaises((ValueError, TypeError)):
                D.validate_plan(bad)

    def test_02_real_read_rejects_corrupt_digest_and_symlink(self):
        path = self.root / "body"; put(path, b"generated source")
        budget = D.Budget(1024, 10*1024**2)
        self.assertEqual(D.read(path, 64, budget, scalar_pin(b"generated source")), b"generated source")
        with self.assertRaises(ValueError):
            D.read(path, 64, budget, scalar_pin(b"different"))
        link = self.root / "link"; link.symlink_to(path)
        self.addCleanup(link.unlink)
        with self.assertRaises(ValueError): D.read(link, 64, budget)
        with self.assertRaises(ValueError): D.decode(b'{"a":1,"a":2}')

    def test_03_real_source_guard_detects_digest_drift(self):
        source = self.root / "source"; source.mkdir()
        relative = "benchmarks/generated.py"; target = source / relative
        target.parent.mkdir(); put(target, b"generated")
        guard = {"files": [{"repository_path": relative, **scalar_pin(b"CORRUPT")}]}
        raw = D.encode(guard); path = self.root / "guard.json"; put(path, raw)
        plan = {"source_root": str(source), "source_guard": {"path": str(path), "pin": scalar_pin(raw)}}
        with self.assertRaisesRegex(ValueError, "Content pin mismatch"):
            D.authenticate_sources(plan, D.Budget(4096, 10*1024**2))

    def test_04_distinct_generated_byte_images_and_matching_projections(self):
        route = GeneratedRoute(self)
        results = []
        for ordinal in (0,1):
            view = route.direct.v.Session(route.data, ordinal, "four_demo", self.root / str(ordinal))
            result = D.check_images(view, route.direct, route.programme, route.adapter, D.Budget(4096, 10*1024**2))
            self.assertTrue(result["image_bytes_equal"])
            self.assertFalse(result["independent_native_deliveries"])
            results.append(result["direct_png"])
        self.assertNotEqual(results[0], results[1])

    def test_05_corrupt_projection_and_extra_header_are_rejected(self):
        for ordinal, kind in enumerate(("image", "header", "wire")):
            route = GeneratedRoute(self)
            view = route.direct.v.Session(route.data, ordinal, "four_demo", self.root / kind)
            if kind == "image":
                original = route.programme.projection
                route.programme.projection = lambda raw: (original(raw)[0], b"different")
            elif kind == "header":
                original = route.programme.ready_header
                route.programme.ready_header = lambda *a, **k: dict(original(*a, **k), forbidden="extra")
            else:
                route.programme.unpack = lambda raw: ({"wrong": True}, b"wrong")
            with self.assertRaises(ValueError):
                D.check_images(view, route.direct, route.programme, route.adapter, D.Budget(4096, 10*1024**2))

    def test_06_journal_constructor_fsync_failure_closes_fd(self):
        opened = []; real_open = os.open
        def opening(*args, **kwargs):
            fd = real_open(*args, **kwargs); opened.append(fd); return fd
        with patch.object(D.os, "open", side_effect=opening), patch.object(D, "fsync_directory", side_effect=OSError("injected")):
            with self.assertRaises(OSError): D.Journal(self.root/"j", D.Budget(1024, 10*1024**2), 512)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError): os.fstat(opened[0])

    def test_07_interrupted_write_precharges_request_and_retains_partial_bytes(self):
        global WRITTEN
        path = self.root / "partial"; fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        budget = D.Budget(1024, 10*1024**2); real_write = os.write; calls = []
        def short_then_fail(number, body):
            calls.append(1)
            if len(calls) == 1: return real_write(number, body[:3])
            raise OSError("injected short-write failure")
        try:
            with patch.object(D.os, "write", side_effect=short_then_fail):
                with self.assertRaises(OSError): D.write_fd(fd, b"1234567890", budget)
        finally: os.close(fd)
        self.assertEqual(budget.writes, 10)
        self.assertEqual(get(path), b"123"); WRITTEN += 10

    def test_08_partial_journal_does_not_advance_committed_chain(self):
        global WRITTEN
        budget = D.Budget(1024, 10*1024**2); journal = D.Journal(self.root/"j", budget, 512)
        real_write = os.write; calls = []
        def partial(fd, body):
            calls.append(1)
            if len(calls) == 1: return real_write(fd, body[:4])
            raise OSError("injected")
        try:
            with patch.object(D.os, "write", side_effect=partial):
                with self.assertRaises(OSError): journal.append({"generated": True})
            self.assertEqual((journal.rows, journal.bytes, journal.previous), (0,0,"0"*64))
        finally: journal.close()
        self.assertEqual((self.root/"j").stat().st_size, 4); WRITTEN += budget.writes

    def test_09_real_fsync_precedes_cleanup_and_deleted_bytes_stay_charged(self):
        global WRITTEN
        route = GeneratedRoute(self); case = self.root / "case"
        view = route.direct.v.Session(route.data,0,"four_demo",case); view.handle(b'{"action":"inspect"}')
        budget = D.Budget(4096,10*1024**2); inventory, size = D.account_case(case,0,budget)
        journal = D.Journal(self.root/"census",budget,512); events=[]; real_fsync=os.fsync; real_unlink=Path.unlink
        def sync(fd): events.append("fsync"); return real_fsync(fd)
        def unlink(path,*a,**k):
            self.assertIn("fsync",events); events.append("unlink"); return real_unlink(path,*a,**k)
        with patch.object(D.os,"fsync",side_effect=sync), patch.object(Path,"unlink",new=unlink):
            journal.append({"generated_commit":scalar_pin(b"checked")})
            D.delete_committed_case(case,inventory,budget)
        journal.close(); self.assertFalse(case.exists()); self.assertEqual(budget.deleted_bytes,size)
        self.assertGreaterEqual(budget.writes,size); WRITTEN += budget.writes-size

    def test_10_unmeasurable_scratch_charged_once_and_retained(self):
        case=self.root/"case";case.mkdir();target=self.root/"target";put(target,b"generated")
        link = case/"bad-link"; link.symlink_to(target)
        self.addCleanup(link.unlink)
        budget=D.Budget(4096,20*1024**2)
        for _ in range(2):
            with self.assertRaises(ValueError): D.account_case(case,3,budget)
        self.assertEqual(budget.writes,D.CASE_RESERVE)
        self.assertEqual(len(budget.accounting_unresolved),1)
        self.assertTrue((case/"bad-link").is_symlink())

    def test_11_mutated_cleanup_inventory_refuses(self):
        route=GeneratedRoute(self);case=self.root/"case"
        view=route.direct.v.Session(route.data,0,"four_demo",case);view.handle(b'{"action":"inspect"}')
        inventory,size=D.scratch_inventory(case);put(case/"unexpected",b"do not delete")
        with self.assertRaises(ValueError): D.delete_committed_case(case,inventory,D.Budget(4096,10*1024**2))
        self.assertTrue((case/"frames/0000.png").exists())

    def test_12_first_failure_preserves_failed_and_unattempted_census(self):
        code,result,route,output,_,_=self.run_generated(fail_at=2)
        self.assertEqual(code,1);self.assertEqual(route.calls,[0,1,2]);self.assertEqual(route.rows.accesses,[0,1,2])
        self.assertEqual([x["status"] for x in result["statuses"][:4]],
            ["initial_projection_equal","initial_projection_equal","failed","unattempted"])
        self.assertEqual(len(result["statuses"]),6400);self.assertTrue(result["packet_closed"])
        self.assertTrue((output/"scratch/0002/frames/0000.png").exists())
        self.assertEqual(route.finalize_calls,0)

    def test_13_lowered_write_ceiling_stops_before_next_case(self):
        code,result,route,_,_,_=self.run_generated(lower_after=1)
        self.assertEqual(code,1);self.assertEqual(route.calls,[0,1])
        self.assertTrue(all(x["status"]=="unattempted" for x in result["statuses"][2:]))
        self.assertIn("write ceiling",result["failure"]["message"])

    def test_14_source_close_failure_is_not_reported_closed(self):
        code,result,route,_,_,_=self.run_generated(fail_at=0,close_fail=True)
        self.assertEqual(code,1);self.assertFalse(result["packet_closed"])
        self.assertIn("close failure",result["close_error"])

    def test_15_expired_preflight_never_opens_dataset(self):
        code,result,route,_,intervals,_=self.run_generated(expired=True)
        self.assertEqual(code,1);self.assertEqual(route.calls,[]);self.assertEqual(intervals,[])
        self.assertFalse(result["roster_authenticated"])
        self.assertEqual(result["unattempted_without_authenticated_ids"],6400)

    def test_zz_16_full_6400_generated_orchestration_complete(self):
        code,result,route,output,intervals,fsyncs=self.run_generated(full=True)
        self.assertEqual(code,0);self.assertEqual(result["status"],"complete_initial_local_projections")
        self.assertEqual(route.calls,list(range(6400)));self.assertEqual(route.rows.accesses,list(range(6400)))
        self.assertEqual(len(result["statuses"]),6400)
        self.assertTrue(all(x["status"]=="initial_projection_equal" for x in result["statuses"]))
        self.assertTrue(result["packet_closed"]);self.assertEqual(route.finalize_calls,0)
        self.assertEqual(list((output/"scratch").iterdir()),[])
        self.assertEqual(result["native_participant_deliveries"],0)
        self.assertFalse(result["driver_attests_own_outer_closure"])
        self.assertEqual(result["journals"]["census"]["complete_rows"],6400)
        self.assertEqual(result["journals"]["census"]["uncommitted_tail_bytes"],0)
        previous="0"*64
        lines=get(output/"CENSUS.jsonl").splitlines(keepends=True)
        self.assertEqual(len(lines),6400)
        for ordinal,raw in enumerate(lines):
            row=json.loads(raw);self.assertEqual(row["ordinal"],ordinal);self.assertEqual(row["previous_sha256"],previous)
            self.assertTrue(row["image_comparison"]["image_bytes_equal"])
            previous=hashlib.sha256(raw).hexdigest()
        self.assertEqual(previous,result["journals"]["census"]["last_sha256"])
        self.assertGreater(len(fsyncs),12800);self.assertEqual(len(intervals),1)


def main():
    global D,ROOT,READ
    parser=argparse.ArgumentParser();parser.add_argument("--candidate",required=True)
    parser.add_argument("--candidate-bytes",type=int,required=True);parser.add_argument("--candidate-sha256",required=True)
    parser.add_argument("--fixture-root",required=True);parser.add_argument("--method",action="append",default=[])
    args=parser.parse_args();ROOT=Path(args.fixture_root);ROOT.mkdir(mode=0o700,exist_ok=False)
    candidate=Path(args.candidate);body=get(candidate)
    if scalar_pin(body)!={"bytes":args.candidate_bytes,"sha256":args.candidate_sha256}:
        raise ValueError("Candidate pin")
    spec=importlib.util.spec_from_file_location("private_generated_census_candidate",candidate)
    D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D
    # Execute the already-authenticated body, not a second unpinned loader read.
    exec(compile(body,str(candidate),"exec"),D.__dict__)
    if "numpy" in sys.modules:raise AssertionError("No NumPy permitted")
    suite=(unittest.TestSuite(Controls(name) for name in args.method) if args.method else
           unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if "numpy" in sys.modules:raise AssertionError("No NumPy import")
    receipt={"scope":"generated stdlib private-driver controls; source/runtime/viewer stubs; no actual image or original data",
        "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
        "candidate":scalar_pin(body),"generated_write_charge_bytes":WRITTEN,"explicit_generated_read_bytes":READ,
        "fixture_write_cap":FIXTURE_CAP,"fixture_read_cap":READ_CAP,
        "full6400_control_fsync":"call-recorded only; separate small real-fsync controls cover ordering/failures",
        "native_delivery_qualified":False,"renderer_imports":0,"numpy_imports":0,"original_data_reads":0}
    raw=(json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode();put(ROOT/"TEST_RESULT.json",raw)
    print(json.dumps(receipt,sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__=="__main__":raise SystemExit(main())

#!/usr/bin/env python3
"""Focused, data-free complete PLAN serialization regressions.

Default: the reviewed public source beside this test. Repeat --source PATH SHA256
POLICY to run the same four methods against public-v1 and private-v2 together.
Only the whole absent --output-root is created; generated plans stay in RAM.
"""
import argparse
import ast
from contextlib import contextmanager
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
import types
import unittest

PUBLIC_SHA = "4504f21b26c08c9b6efc542441d2cb74914a85b96ea76ad2dcc4f95e3a2c6b6d"
MIB = 1024*1024
OLD_PLAN_CAP = 4*MIB
DOCUMENT_CAP = 40*MIB
PROVED_DOCUMENT_UPPER = 41942205
SOURCE_READ_CAP = 131072
GENERATED_READ_CAP = 12*MIB
LARGE_DOCUMENT_CAP = 6*MIB-8192
REPORT_CAP = 32768
LOG_CAP = 16384
RESULT_CAP = 16384
WORK_SECONDS = 52
DRIVER_SECONDS = 55
METHODS = (
    "test01_complete_bound_and_production_cap_binding",
    "test02_legal_large_plan_and_actual_consumer",
    "test03_exact_boundaries_and_legacy_read_signature",
    "test04_ordinary_content_and_separate_alias_policies",
)
CONTEXTS = []
ROOT = None
END = None
COVERAGE = []
LARGE_RESULTS = []
COUNTERS = {"source_reserved_read_bytes": 0, "generated_stream_read_bytes": 0,
            "report_requested_bytes": 0, "injected_input_opens": 0,
            "injected_input_closes": 0, "production_serializer_calls": 0,
            "production_consumer_calls": 0}

def need(ok, text):
    if not ok:
        raise RuntimeError(text)

def check():
    need(time.monotonic() < END, "finite generated work/publication deadline")

def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def bump(key, n, cap):
    check()
    need(type(n) is int and n >= 0 and COUNTERS[key]+n <= cap, "finite " + key)
    COUNTERS[key] += n

def publish(path, raw):
    bump("report_requested_bytes", len(raw), REPORT_CAP)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}

def production_calls(text):
    tree = ast.parse(text)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    serializers = []
    consumers = []
    for node in ast.walk(main):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "bounded_encoded" and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "plan":
            serializers.append(node)
        if node.func.id == "bounded_json" and isinstance(node.args[0], ast.Subscript):
            # The profile read starts with Name(path); this is the APPLY PLAN read.
            consumers.append(node)
    need(len(serializers) == len(consumers) == 1, "one actual PLAN encoder and consumer expression")
    return serializers[0], consumers[0]

def invoke_serializer(ctx, value, cap=None):
    check()
    env = dict(ctx["module"].__dict__)
    limits = dict(env["LIMITS"])
    if cap is not None:
        limits["plan_document_bytes"] = cap
    env.update(plan=value, LIMITS=limits)
    COUNTERS["production_serializer_calls"] += 1
    return eval(ctx["serializer_code"], env)

def invoke_consumer(ctx, raw, budget, cap=None, pin_override=None):
    check()
    m = ctx["module"]
    limits = dict(m.LIMITS)
    if cap is not None:
        limits["plan_document_bytes"] = cap
    pin = {"path": "/generated/PLAN.json", "bytes": len(raw), "sha256": sha(raw)}
    if pin_override:
        pin.update(pin_override)
    env = dict(m.__dict__)
    env.update(profile={"plan": pin}, budget=budget, LIMITS=limits)
    COUNTERS["production_consumer_calls"] += 1
    with injected_input(m, raw, pin["path"]):
        return eval(ctx["consumer_code"], env)

@contextmanager
def injected_input(module, raw, path):
    """Only the physical file boundary is doubled; parser/hash/budgets are real."""
    check()
    old_open, old_check = module.open_regular, module.check_input
    token = object()
    handles = []
    class GeneratedHandle(io.BytesIO):
        def read(self, n=-1):
            need(type(n) is int and 0 <= n <= module.CHUNK, "bounded actual reader request")
            value = super().read(n)
            bump("generated_stream_read_bytes", len(value), GENERATED_READ_CAP)
            return value
        def close(self):
            if not self.closed:
                COUNTERS["injected_input_closes"] += 1
            super().close()
    def opening(got_path, size=None):
        need(str(got_path) == path and size == len(raw), "exact generated input descriptor")
        COUNTERS["injected_input_opens"] += 1
        handle = GeneratedHandle(raw)
        handles.append(handle)
        return handle, token
    def stable(handle, got_path, before):
        need(handle in handles and str(got_path) == path and before is token
             and handle.tell() == len(raw), "generated handle custody/complete read")
    module.open_regular, module.check_input = opening, stable
    try:
        yield
    finally:
        module.open_regular, module.check_input = old_open, old_check
        need(all(h.closed for h in handles), "real bounded_json closed every returned handle")

def snapshot(budget):
    return dict(budget.counters), budget.plan_document_metadata_bytes

def row(path, kind="file", link="", data=b"", mode=0o644, offset=0):
    return {"path": path, "type": kind, "mode": mode,
            "bytes": len(data) if kind == "file" else 0,
            "link": link, "offset": offset, "sha256": sha(data) if kind == "file" else "",
            "raw_name": path}

def required(path, data=b""):
    return {"path": path, "bytes": len(data), "sha256": sha(data)}

def plan_for(ctx, projection, required_rows):
    version = "v1" if ctx["policy"] == "public-v1" else "v2"
    return {"schema": "language-provider-rootfs-plan/" + version,
            "image": ctx["module"].IMAGE,
            "archive": {"bytes": 1024, "sha256": sha(b"\0"*1024)},
            "required": required_rows, "projection": projection}

def large_fixture():
    # Three shared <=240-character directory components and 200-character leaves.
    # Every source file is ordinary, zero-byte, and required. No alias-policy
    # difference is involved in the large common legal composition.
    components = ["a"*240, "b"*240, "c"*240]
    prefix = "/".join(components)
    rows = [row("/".join(components[:n]), "dir", mode=0o755) for n in (1, 2, 3)]
    needs = []
    for index in range(1100):
        name = prefix + "/" + ("f%04d_" % index) + "z"*194
        need(len(name) == 923 and max(map(len, name.split("/"))) <= 240,
             "literal bounded generated path construction")
        rows.append(row(name))
        needs.append(required(name))
    return rows, needs

def complete(ctx, method):
    COVERAGE.append({"method": method, "policy": ctx["policy"], "source_sha256": ctx["pin"]["sha256"]})

class PlanSerializationControls(unittest.TestCase):
    def test01_complete_bound_and_production_cap_binding(self):
        for ctx in CONTEXTS:
            with self.subTest(policy=ctx["policy"]):
                m = ctx["module"]
                self.assertEqual(m.LIMITS["plan_bytes"], 4194304)
                self.assertEqual(m.LIMITS["plan_document_bytes"], 41943040)
                self.assertEqual(m.LIMITS["audit_bytes"], 33554432)
                self.assertEqual(m.LIMITS["metadata_bytes"], 33554432)
                self.assertEqual(m.LIMITS["read_bytes"], 6442450944)
                empty_manifest = {"schema": "language-frozen-public-tree/v1", "kind": "runtime",
                    "condition": "generic", "directories": [], "files": []}
                empty_plan = {"schema": "language-provider-rootfs-plan/v2",
                    "image": "sha256:ab2bea4ced8dac37524a995444e928b80c4db04e9f5e7fddd26ea5dd3962781e",
                    "archive": {"bytes": 536870912, "sha256": "f"*64}, "required": [],
                    "projection": {"directories": [], "files": [], "audit": []}}
                self.assertEqual(len(encoded(empty_manifest))-1-4, 106)
                self.assertEqual(len(encoded(empty_plan))-1-8, 293)
                derived = (4194304-1023)+(33554432+1)+(4194304-107)+293+1
                self.assertEqual(derived, PROVED_DOCUMENT_UPPER)
                self.assertEqual(DOCUMENT_CAP-derived, 835)
                for call in (ctx["serializer_ast"], ctx["consumer_ast"]):
                    bound = call.args[1] if call.func.id == "bounded_encoded" else call.args[3]
                    self.assertIsInstance(bound, ast.Subscript)
                    self.assertEqual(ast.dump(bound, include_attributes=False),
                                     ast.dump(ast.parse("LIMITS['plan_document_bytes']", mode="eval").body,
                                              include_attributes=False))
                keywords = {k.arg: k.value for k in ctx["consumer_ast"].keywords}
                self.assertEqual(ast.dump(keywords["plan_document"], include_attributes=False),
                                 ast.dump(ast.Constant(True), include_attributes=False))
                # Independent literal canonical JSON: framing, escaped newline,
                # non-ASCII escape, sorted keys, booleans and final newline.
                literal = b'{"a":[true,null],"z":"\\u00e9\\n"}\n'
                self.assertEqual(invoke_serializer(ctx, {"z": "\u00e9\n", "a": [True, None]}), literal)
                b = m.Budget()
                self.assertEqual(set(b.counters), {"read_bytes", "written_bytes", "metadata_bytes",
                    "inner_tar_metadata_bytes_read", "inner_tar_boundary_probe_bytes_read"})
                self.assertEqual(b.plan_document_metadata_bytes, 0)
                complete(ctx, self._testMethodName)

    def test02_legal_large_plan_and_actual_consumer(self):
        for ctx in CONTEXTS:
            with self.subTest(policy=ctx["policy"]):
                check()
                m = ctx["module"]
                rows, needs = large_fixture()
                projection = m.project_roster(rows, needs, m.Budget())
                generated = plan_for(ctx, projection, needs)
                manifest = m.verify_projection(generated, m.Budget())
                self.assertEqual(len(needs), 1100)
                self.assertTrue(all(r["bytes"] == 0 for r in projection["files"]))
                self.assertEqual(sum(r.get("action") == "mode-normalize" for r in projection["audit"]), 1100)
                self.assertFalse(any(r.get("action") == "dangling-symlink-leaf-omit"
                                     for r in projection["audit"]))
                raw = invoke_serializer(ctx, generated)
                self.assertGreater(len(raw), OLD_PLAN_CAP)
                self.assertLessEqual(len(raw), LARGE_DOCUMENT_CAP)
                # This is the actual unchanged encoder, invoked through the
                # selected production call expression with the old cap.
                with self.assertRaises(m.Refusal):
                    invoke_serializer(ctx, generated, OLD_PLAN_CAP)
                # The actual APPLY read expression must choose document mode.
                # Ordinary metadata is deliberately only seven bytes here.
                b = m.Budget({"metadata_bytes": 7})
                decoded = invoke_consumer(ctx, raw, b)
                self.assertTrue(decoded == generated, "complete real bounded-reader round trip")
                self.assertEqual(b.plan_document_metadata_bytes, len(raw))
                self.assertEqual(b.counters["metadata_bytes"], len(raw))
                self.assertEqual(b.counters["read_bytes"], len(raw))
                b.read(7, metadata=True)
                before = snapshot(b)
                with self.assertRaises(m.Refusal):
                    b.read(1, metadata=True)
                self.assertEqual(snapshot(b), before, "ordinary cap refusal does not mutate counters")
                decoded_manifest = m.verify_projection(decoded, m.Budget())
                self.assertTrue(decoded_manifest == manifest, "actual downstream PLAN validation agrees")
                LARGE_RESULTS.append({"policy": ctx["policy"], "source_sha256": ctx["pin"]["sha256"],
                    "generated_regular_files": 1100, "generated_required_files": 1100,
                    "document_bytes": len(raw), "document_sha256": sha(raw),
                    "old_4MiB_refused": True, "new_document_guard_accepted": True,
                    "actual_bounded_reader_and_verify_projection_accepted": True,
                    "authentic_plan_size_inferred": False})
                complete(ctx, self._testMethodName)
                del decoded, decoded_manifest, raw, generated, manifest, projection, rows, needs
                gc.collect()

    def test03_exact_boundaries_and_legacy_read_signature(self):
        for ctx in CONTEXTS:
            with self.subTest(policy=ctx["policy"]):
                m = ctx["module"]
                value = {"x": [0]}
                literal = b'{"x":[0]}\n'
                exact = len(literal)
                self.assertEqual(invoke_serializer(ctx, value, exact), literal)
                with self.assertRaises(m.Refusal):
                    invoke_serializer(ctx, value, exact-1)
                b = m.Budget({"plan_document_bytes": exact, "metadata_bytes": 1})
                self.assertEqual(invoke_consumer(ctx, literal, b, exact), value)
                self.assertEqual(snapshot(b)[1], exact)
                before = snapshot(b)
                with self.assertRaises(m.Refusal):
                    b.read(1, metadata=True, plan_document=True)
                self.assertEqual(snapshot(b), before)
                opens = COUNTERS["injected_input_opens"]
                c = m.Budget({"plan_document_bytes": exact, "metadata_bytes": 1})
                with self.assertRaises(m.Refusal):
                    invoke_consumer(ctx, literal, c, exact-1)
                self.assertEqual(COUNTERS["injected_input_opens"], opens)
                self.assertEqual(snapshot(c), (dict.fromkeys(c.counters, 0), 0))
                bad = m.Budget({"plan_document_bytes": exact, "metadata_bytes": 1})
                with self.assertRaisesRegex(m.Refusal, "JSON digest"):
                    invoke_consumer(ctx, literal, bad, exact, {"sha256": "0"*64})
                self.assertEqual(bad.plan_document_metadata_bytes, exact)
                # Independent document, ordinary metadata, and total-read caps.
                d = m.Budget({"plan_document_bytes": 8, "metadata_bytes": 6, "read_bytes": 20})
                d.read(8, metadata=True, plan_document=True)
                d.read(6, metadata=True)
                state = snapshot(d)
                for kwargs in ({"metadata": True}, {"metadata": True, "plan_document": True}):
                    with self.assertRaises(m.Refusal):
                        d.read(1, **kwargs)
                    self.assertEqual(snapshot(d), state)
                total = m.Budget({"plan_document_bytes": 10, "metadata_bytes": 8, "read_bytes": 14})
                total.read(8, metadata=True, plan_document=True)
                total.read(6, metadata=True)
                state = snapshot(total)
                with self.assertRaises(m.Refusal):
                    total.read(1, metadata=True, plan_document=True)
                self.assertEqual(snapshot(total), state)
                for flag in (0, 1, None, ""):
                    fresh = m.Budget()
                    state = snapshot(fresh)
                    with self.assertRaises(m.Refusal):
                        fresh.read(1, metadata=True, plan_document=flag)
                    self.assertEqual(snapshot(fresh), state)
                    with self.assertRaises(m.Refusal):
                        m.read_exact(io.BytesIO(b"a"), 1, fresh, True, plan_document=flag)
                    self.assertEqual(snapshot(fresh), state)
                fresh = m.Budget()
                state = snapshot(fresh)
                with self.assertRaises(m.Refusal):
                    fresh.read(1, metadata=False, plan_document=True)
                self.assertEqual(snapshot(fresh), state)
                class LegacyBudget:
                    def __init__(self):
                        self.calls = []
                    def read(self, count, metadata=False):
                        self.calls.append((count, metadata))
                legacy = LegacyBudget()
                self.assertEqual(m.read_exact(io.BytesIO(b"abc"), 3, legacy, True), b"abc")
                bump("generated_stream_read_bytes", 3, GENERATED_READ_CAP)
                self.assertEqual(legacy.calls, [(3, True)])
                # Explicit bounded_json document-mode misuse refuses before I/O.
                fresh = m.Budget({"plan_document_bytes": exact})
                with injected_input(m, literal, "/generated/PLAN.json"):
                    for bad_flag in (0, 1, None, ""):
                        with self.assertRaises(m.Refusal):
                            m.bounded_json("/generated/PLAN.json",
                                {"bytes": exact, "sha256": sha(literal)}, fresh, exact,
                                plan_document=bad_flag)
                    with self.assertRaises(m.Refusal):
                        m.bounded_json("/generated/PLAN.json",
                            {"bytes": exact, "sha256": sha(literal)}, fresh, exact+1,
                            plan_document=True)
                self.assertEqual(snapshot(fresh), (dict.fromkeys(fresh.counters, 0), 0))
                complete(ctx, self._testMethodName)

    def test04_ordinary_content_and_separate_alias_policies(self):
        for ctx in CONTEXTS:
            with self.subTest(policy=ctx["policy"]):
                m = ctx["module"]
                data = b"unchanged"
                rows = [row("dir", "dir", mode=0o755), row("dir/file", data=data, offset=8),
                        row("nonrequired", data=b"extra", offset=32),
                        row("shortcut", "symlink", "dir/file"),
                        row("chain", "symlink", "shortcut"), row("view", "symlink", "dir")]
                needs = [required("dir/file", data)]
                projected = m.project_roster(rows, needs, m.Budget())
                files = {r["path"]: r for r in projected["files"]}
                for name, chain in (("dir/file", []), ("shortcut", ["shortcut"]),
                                    ("chain", ["chain", "shortcut"]), ("view/file", ["view"])):
                    self.assertEqual((files[name]["bytes"], files[name]["sha256"], files[name]["offset"],
                                      files[name]["source"], files[name]["mode"]),
                                     (len(data), sha(data), 8, "dir/file", 0o444))
                    chain_hash = sha((json.dumps(chain, separators=(",", ":"))+"\n").encode())
                    self.assertEqual((files[name]["hops"], files[name]["chain_sha256"]),
                                     (len(chain), chain_hash))
                self.assertEqual(files["nonrequired"]["sha256"], sha(b"extra"))
                p = plan_for(ctx, projected, needs)
                self.assertEqual(m.verify_projection(p, m.Budget())["schema"],
                                 "language-frozen-public-tree/v1")
                broken = rows + [row("broken", "symlink", "absent")]
                if ctx["policy"] == "public-v1":
                    with self.assertRaises(m.Refusal):
                        m.project_roster(broken, needs, m.Budget())
                else:
                    accepted = m.project_roster(broken, needs, m.Budget())
                    omissions = [r for r in accepted["audit"]
                                 if r.get("action") == "dangling-symlink-leaf-omit"]
                    self.assertEqual(len(omissions), 1)
                    self.assertEqual((omissions[0]["path"], omissions[0]["chain"],
                                      omissions[0]["missing_final_component"]),
                                     ("broken", ["broken"], "absent"))
                    self.assertNotIn("broken", {r["path"] for r in accepted["files"]})
                with self.assertRaises(m.Refusal):
                    m.project_roster(rows, needs, m.Budget({"plan_bytes": 1024}))
                with self.assertRaises(m.Refusal):
                    m.project_roster(rows, needs, m.Budget({"audit_bytes": 1}))
                complete(ctx, self._testMethodName)

class BoundedLog(io.TextIOBase):
    def __init__(self):
        self.parts = []
        self.size = 0
        self.truncated = False
    def write(self, text):
        raw = text.encode("utf-8", "replace")
        left = LOG_CAP-self.size
        if len(raw) > left:
            self.truncated = True
        part = raw[:left]
        self.parts.append(part)
        self.size += len(part)
        return len(text)
    def body(self):
        return b"".join(self.parts)

class CountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.starts, self.stops, self.successes = [], [], []
    def startTest(self, test):
        self.starts.append(test.id())
        super().startTest(test)
    def stopTest(self, test):
        self.stops.append(test.id())
        super().stopTest(test)
    def addSuccess(self, test):
        self.successes.append(test.id())
        super().addSuccess(test)

def load_selected(spec, number):
    path, expected, policy = spec
    p = Path(path).absolute()
    need(policy in ("public-v1", "private-v2") and re.fullmatch("[0-9a-f]{64}", expected),
         "explicit source SHA and separate policy")
    st = p.lstat()
    need(p.resolve() == p and stat.S_ISREG(st.st_mode) and st.st_nlink == 1
         and not p.is_symlink() and st.st_size <= 65536, "ordinary bounded selected source")
    bump("source_reserved_read_bytes", st.st_size+1, SOURCE_READ_CAP)
    with p.open("rb") as stream:
        raw = stream.read(st.st_size+1)
    need(len(raw) == st.st_size and sha(raw) == expected, "exact reviewed source hash")
    text = raw.decode()
    serializer, consumer = production_calls(text)
    module = types.ModuleType("selected_serialization_%d" % number)
    module.__file__ = str(p)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(p), "exec"), module.__dict__)
    return {"module": module, "policy": policy,
            "pin": {"path": str(p), "bytes": len(raw), "sha256": sha(raw)},
            "serializer_ast": serializer, "consumer_ast": consumer,
            "serializer_code": compile(ast.Expression(serializer), str(p)+":PLAN-call", "eval"),
            "consumer_code": compile(ast.Expression(consumer), str(p)+":consumer-call", "eval")}

def main(argv=None):
    global ROOT, END, CONTEXTS
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--source", nargs=3, action="append", metavar=("PATH", "SHA256", "POLICY"))
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    selected = args.source or [[str(Path(__file__).resolve().with_name("prepare_provider_rootfs.py")),
                                PUBLIC_SHA, "public-v1"]]
    need(1 <= len(selected) <= 2 and len({x[2] for x in selected}) == len(selected),
         "one explicit source or unique public/private pair")
    started = time.monotonic()
    END = started+WORK_SECONDS
    root = Path(args.output_root)
    need(root.is_absolute() and root.resolve() == root and not os.path.lexists(root)
         and root.parent.is_dir() and root.parent.resolve() == root.parent,
         "whole absent output leaf and existing ordinary parent")
    root.mkdir(mode=0o700)
    ROOT = root
    log = BoundedLog()
    result = None
    failure = None
    old_handler = signal.getsignal(signal.SIGALRM)
    def timeout(_sig, _frame):
        raise TimeoutError("finite52s generated work within55s driver")
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, WORK_SECONDS)
    try:
        CONTEXTS = [load_selected(spec, n) for n, spec in enumerate(selected)]
        need(tuple(unittest.defaultTestLoader.getTestCaseNames(PlanSerializationControls)) == METHODS,
             "exact four-method roster")
        suite = unittest.TestSuite(PlanSerializationControls(name) for name in METHODS)
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=CountedResult).run(suite)
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)[:512]}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    elapsed = time.monotonic()-started
    END = started+DRIVER_SECONDS
    transcript = log.body()
    log_pin = publish(ROOT/"TEST_LOG.txt", transcript)
    expected = [PlanSerializationControls(name).id() for name in METHODS]
    coverage_ok = (len(COVERAGE) == 4*len(selected) and
        {(r["method"], r["policy"]) for r in COVERAGE} ==
        {(name, spec[2]) for name in METHODS for spec in selected})
    passed = (failure is None and result is not None and result.wasSuccessful()
              and result.testsRun == 4 and not result.skipped and result.starts == expected
              and result.stops == expected and result.successes == expected and coverage_ok
              and len(CONTEXTS) == len(selected) and not log.truncated and elapsed < WORK_SECONDS
              and COUNTERS["injected_input_opens"] == COUNTERS["injected_input_closes"])
    report = {"schema": "language-plan-serialization-generated-controls/v1",
        "status": "passed" if passed else "failed",
        "sources": [{"policy": c["policy"], **c["pin"]} for c in CONTEXTS],
        "expected_methods": expected, "tests_run": result.testsRun if result else 0,
        "starts": result.starts if result else [], "stops": result.stops if result else [],
        "successes": result.successes if result else [], "source_checks": COVERAGE,
        "expected_source_checks": 4*len(selected), "large_generated_compositions": LARGE_RESULTS,
        "failures": len(result.failures) if result else 0, "errors": len(result.errors) if result else 0,
        "skips": len(result.skipped) if result else 0, "runner_failure": failure,
        "log_truncated": log.truncated, "timeout": elapsed >= WORK_SECONDS,
        "elapsed_seconds": elapsed, "test_log": log_pin, "counters_before_result": dict(COUNTERS),
        "limits": {"source_read": SOURCE_READ_CAP, "generated_stream_read": GENERATED_READ_CAP,
                   "large_document_each": LARGE_DOCUMENT_CAP, "reports_total": REPORT_CAP,
                   "test_log": LOG_CAP, "result": RESULT_CAP, "work_seconds": WORK_SECONDS,
                   "driver_seconds": DRIVER_SECONDS, "source_count": 2},
        "actual_paths": ["project_roster", "verify_projection", "main final PLAN encoding expression",
                         "main APPLY PLAN bounded_json expression", "bounded_json", "read_exact", "Budget.read"],
        "injected_boundary": "Generated BytesIO open/check/close only; no filesystem fixture or actual APPLY. Reader/hash/parser/accounting code is real.",
        "not_exercised": ["real archive", "scan_export", "full production main", "apply_plan",
                          "native/Docker/runtime", "benchmark data or model"],
        "authentic_complete_plan_bytes": None, "authentic_full_size_inferred_from_generated": False,
        "bound_domain": "Complete documents emitted after successful project_roster, not every arbitrary hash-selected APPLY JSON. Future APPLY must join an authentic successful PLAN descriptor.",
        "original_archive_reads": 0, "scientific_data_reads": 0, "fits": 0,
        "subprocesses": 0, "fixture_file_bytes": 0,
        "input_qualified": False, "provider_qualified": False, "scientific_qualified": False,
        "ordinary_interpreter_stdlib_import_IO_separately_metered": False, "retry_allowed": False}
    body = encoded(report)
    need(len(body) <= RESULT_CAP, "complete bounded RESULT")
    pin = publish(ROOT/"RESULT.json", body)
    sys.stdout.buffer.write(transcript)
    sys.stdout.buffer.write(encoded({"status": report["status"], "result": pin, "counters": COUNTERS}))
    sys.stdout.buffer.flush()
    return 0 if passed else 2

if __name__ == "__main__":
    raise SystemExit(main())

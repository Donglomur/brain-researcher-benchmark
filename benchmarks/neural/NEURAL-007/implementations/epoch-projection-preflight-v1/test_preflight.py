"""Generated controls for the thin N007 projection preflight.

One deterministic fixture per person is reused in memory for all 5,450
projections. The maintained projection, renderer, Session and request builder
run unchanged. No original signal, provider, Docker or grader is used.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "preflight.py"
ROOT = Path(os.environ["N007_PREFLIGHT_CONTROL_ROOT"]).absolute()
REPOSITORY = Path(os.environ["N007_DEPENDENCY_ROOT"]).absolute()
EPOCH = REPOSITORY / "benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1"
CASES = (("development-001", 2780), ("development-002", 2670))
MAX_CAMPAIGN_BYTES = 4 * 2**20
MAX_CAPTURE_BYTES = 96 * 2**10
MAX_RUN_RECORD_BYTES = 128 * 2**10
FINAL_RESERVE_BYTES = 256 * 2**10
UNEXPECTED_MUTATIONS = []
CREATED = []
RUNS = []
COUNTER = 0
FIXTURES = None
BASELINE = None
STARTED = None

# This observes exact maintained function-code objects. It does not replace a
# loader, projection, renderer, request builder, or driver branch.
BOOTSTRAP = r'''
import cProfile, importlib.util, json, os, resource, sys, types
driver, arguments, repo, attack, target, fixture_paths = sys.argv[1:]
fixture_paths = set(json.loads(fixture_paths))
arguments = json.loads(arguments)
root = repo + "/benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1/"
wanted = {(root+"contract.py", "project_epoch"): "project_epoch",
          (root+"epoch_visual.py", "initial"): "initial",
          (root+"epoch_visual.py", "request_bytes"): "request_bytes"}
observed = {"core_calls": {v: 0 for v in wanted.values()},
            "attack": attack or None, "attack_attempted": False,
            "attack_denied": False, "canary_read_attempts": 0, "fixture_body_read_attempts": 0,
            "network_or_process_attempts": 0, "original_path_attempts": 0}
def audit(event, args):
    if event == "open" and args:
        try: path = os.fspath(args[0])
        except TypeError: path = ""
        if path == target:
            observed["canary_read_attempts"] += 1
        if path in fixture_paths and not ((isinstance(args[1], str) and any(c in args[1] for c in "wax+")) or (isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
            observed["fixture_body_read_attempts"] += 1
        if isinstance(path, str) and "/artifacts-build/sleep-eog-raw-development-001/" in path:
            observed["original_path_attempts"] += 1
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"):
        observed["network_or_process_attempts"] += 1
sys.addaudithook(audit)
spec = importlib.util.spec_from_file_location("n007_control_preflight", driver)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
if attack == "preloaded_contract":
    stale = types.ModuleType("contract")
    stale.__file__ = root + "contract.py"
    sys.modules["contract"] = stale
profile = None
def attack_hook(frame, event, value):
    at_projection = (frame.f_code.co_filename, frame.f_code.co_name) in wanted and frame.f_code.co_name == "project_epoch"
    at_terminal = frame.f_code.co_filename == driver and frame.f_code.co_name == "put" and frame.f_locals.get("relative") == "REPORT.json"
    if event == "call" and ((attack in ("write_fixture", "read_canary") and at_projection) or (attack == "terminal_write" and at_terminal)):
        sys.setprofile(None)
        observed["attack_attempted"] = True
        try:
            if attack in ("write_fixture", "terminal_write"):
                with open(target, "wb") as stream:
                    stream.write(b"GENERATED_FORBIDDEN_MUTATION")
            elif attack == "read_canary":
                with open(target, "rb") as stream:
                    stream.read(1)
            else:
                raise AssertionError("Unknown generated attack")
        except PermissionError:
            observed["attack_denied"] = True
try:
    if attack:
        sys.setprofile(attack_hook)
    else:
        profile = cProfile.Profile()
        profile.enable()
    code = module.main(arguments)
except BaseException as error:
    code = 99
    observed["uncaught"] = type(error).__name__
finally:
    sys.setprofile(None)
    if profile is not None:
        profile.disable()
        for item in profile.getstats():
            code_object = item.code
            if isinstance(code_object, str):
                continue
            key = (code_object.co_filename, code_object.co_name)
            if key in wanted:
                observed["core_calls"][wanted[key]] += item.callcount
observed["entry_return_code"] = code
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
observed["child_peak_rss_bytes"] = int(rss if sys.platform == "darwin" else rss * 1024)
observed["rss_scope"] = "maximum this generated child only; not whole process-tree or enforced quota"
print("CONTROL_OBSERVATION=" + json.dumps(observed, sort_keys=True, separators=(",", ":")))
sys.exit(code if type(code) is int and 0 <= code <= 255 else 99)
'''

def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def write_new(path, raw, terminal=False):
    if type(raw) is not bytes:
        raise TypeError("Exact fixture bytes required")
    path = Path(path)
    reserve = 0 if terminal else FINAL_RESERVE_BYTES
    if retained_bytes() + len(raw) + reserve + sum(x["charged_bytes"] for x in UNEXPECTED_MUTATIONS) > MAX_CAMPAIGN_BYTES:
        raise AssertionError("Generated cumulative write cap would be exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    CREATED.append({"path": str(path), **pin(raw)})
    check_accounting()
    return {"path": str(path), **pin(raw)}

def retained_bytes():
    total = 0
    for path in ROOT.rglob("*"):
        if path.is_file() and not path.is_symlink():
            total += path.stat().st_size
    return total

def check_accounting():
    # Every selected writer uses create-only files. No fixture mutation or
    # restoration is permitted; denied writes must leave their bytes unchanged.
    total = retained_bytes() + sum(x["charged_bytes"] for x in UNEXPECTED_MUTATIONS)
    if total > MAX_CAMPAIGN_BYTES:
        raise AssertionError("Generated campaign write cap exceeded")
    return total

def fixtures():
    global FIXTURES, BASELINE
    if FIXTURES is not None:
        return FIXTURES
    spec = importlib.util.spec_from_file_location("n007_fixture_contract", EPOCH / "contract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for person_index, (case, _) in enumerate(CASES):
        signals = [
            [float((person_index + 1) * (channel + 1)) * 1e-5 *
             math.sin(2 * math.pi * (sample + channel * 3) / (97 + person_index * 17))
             for sample in range(3000)]
            for channel in range(3)]
        raw = module.signal_bytes(signals)
        if len(raw) != 72128:
            raise AssertionError("Complete generated NPY extent changed")
        descriptor = write_new(ROOT / "fixtures" / (case + ".npy"), raw)
        rows.append({"case_id": case, "signals": descriptor})
    canary = write_new(ROOT / "protected-generated-canary.bin", b"GENERATED_ONLY_NO_ORIGINAL_CONTENT\n")
    source = {"path": str(EPOCH / "epoch_visual.py"), **pin((EPOCH / "epoch_visual.py").read_bytes())}
    BASELINE = {
        "schema": "n007_epoch_host_preflight_v1", "mode": "generated_control", "selected": True,
        "repository_root": str(REPOSITORY), "output_root": "",
        "limits": {"read_bytes": 64 * 2**20, "write_bytes": 3 * 2**20, "wall_seconds": 120},
        "knowledge": {"schema": "sleep007_epoch_shared_knowledge_v1", "provider": "openai",
                      "model": "generated-preflight-control", "revision": "generated-only-no-model",
                      "policy": "shared_declared_base_agent_prior_only", "external_assets": []},
        "budget": {"max_turns": 2, "max_images": 2, "max_history_bytes": 8 * 2**20,
                   "max_request_bytes": 8 * 2**20, "max_response_bytes": 8192,
                   "max_total_provider_bytes": 8 * 2**20 + 8193, "context_tokens": 131072,
                   "output_tokens": 256, "wall_seconds": 120, "image_detail": "original"},
        "source": source, "fixtures": rows, "materials": None,
    }
    FIXTURES = {"rows": rows, "canary": canary}
    return FIXTURES

def snapshots():
    f = fixtures()
    return {row["signals"]["path"]: pin(Path(row["signals"]["path"]).read_bytes()) for row in f["rows"]} | {
        f["canary"]["path"]: pin(Path(f["canary"]["path"]).read_bytes())}

def run_entry(label, change=None, *, attack="", target=None, corrupt_cli_hash=False):
    global COUNTER
    fixtures()
    COUNTER += 1
    case_root = ROOT / f"{COUNTER:02d}-{label}"
    case_root.mkdir()
    protocol = copy.deepcopy(BASELINE)
    protocol["output_root"] = str(case_root / "output")
    if label != "complete-generated":
        protocol["limits"]["write_bytes"] = 196608
    if change is not None:
        change(protocol, case_root)
    protocol_descriptor = write_new(case_root / "PROTOCOL.json", encoded(protocol))
    before = snapshots()
    arguments = ["--protocol", protocol_descriptor["path"], "--bytes", str(protocol_descriptor["bytes"]),
                 "--sha256", "0" * 64 if corrupt_cli_hash else protocol_descriptor["sha256"]]
    environment = dict(os.environ)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        environment[key] = "1"
    command = [sys.executable, "-I", "-B", "-c", BOOTSTRAP, str(DRIVER), json.dumps(arguments),
               str(REPOSITORY), attack, str(target or fixtures()["canary"]["path"]),
               json.dumps([row["signals"]["path"] for row in fixtures()["rows"]])]
    forecast = (retained_bytes() + protocol["limits"]["write_bytes"] + 2 * MAX_CAPTURE_BYTES
                + MAX_RUN_RECORD_BYTES + FINAL_RESERVE_BYTES
                + sum(x["charged_bytes"] for x in UNEXPECTED_MUTATIONS))
    if forecast > MAX_CAMPAIGN_BYTES:
        raise AssertionError("Remaining generated allocation cannot admit this bounded child")
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=150)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    elapsed = time.monotonic() - started
    capture_exceeded = len(stdout) > MAX_CAPTURE_BYTES or len(stderr) > MAX_CAPTURE_BYTES
    write_new(case_root / "stdout.txt", stdout[:MAX_CAPTURE_BYTES])
    write_new(case_root / "stderr.txt", stderr[:MAX_CAPTURE_BYTES])
    after = snapshots()
    inputs_changed = after != before
    marker = b"CONTROL_OBSERVATION="
    lines = stdout.splitlines()
    records = [json.loads(line[len(marker):]) for line in lines if line.startswith(marker)]
    if len(records) != 1:
        raise AssertionError("One bounded independent entry observation required")
    observation = records[0]
    superseded = {path for path in before if before[path] != after[path]}
    if attack in ("write_fixture", "terminal_write") and observation["attack_attempted"] and not observation["attack_denied"]:
        superseded.add(str(target))
    if superseded:
        # Current retained extents already count the replacement write. Add the
        # lost old extents so even a failed read-only control stays cumulative.
        UNEXPECTED_MUTATIONS.append({"case": label, "before": before, "after": after,
                                     "charged_bytes": sum(before[path]["bytes"] for path in superseded)})
    report_path = Path(protocol["output_root"]) / "REPORT.json"
    report = json.loads(report_path.read_bytes()) if report_path.is_file() else None
    closure_path = Path(protocol["output_root"]) / "CLOSURE.json"
    closure = json.loads(closure_path.read_bytes()) if closure_path.is_file() else None
    record = {"label": label, "returncode": process.returncode, "timed_out": timed_out,
              "wall_seconds": elapsed, "observation": observation,
              "protocol": protocol_descriptor, "capture_exceeded": capture_exceeded,
              "stdout_returned_bytes": len(stdout), "stderr_returned_bytes": len(stderr),
              "input_pins_before": before,
              "input_pins_after": after, "report": report, "closure": closure}
    RUNS.append(record)
    raw_record = encoded(record)
    if len(raw_record) > MAX_RUN_RECORD_BYTES:
        raise AssertionError("Bounded generated observation record exceeded")
    write_new(case_root / "OBSERVATION.json", raw_record)
    if inputs_changed:
        raise AssertionError("Generated immutable input/canary changed; mutation preserved")
    if capture_exceeded:
        raise AssertionError("Returned child pipe capture exceeded post-capture bound")
    if timed_out:
        raise AssertionError("Generated child exceeded fixed wall limit")
    check_accounting()
    return protocol, record

def no_effects(test, record):
    observation = record["observation"]
    test.assertEqual(observation["original_path_attempts"], 0)
    test.assertEqual(observation["network_or_process_attempts"], 0)
    test.assertNotIn("uncaught", observation)

def denials(value):
    return len(value) if isinstance(value, list) else value

class PreflightControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global STARTED
        if not ROOT.is_dir() or any(ROOT.iterdir()):
            raise AssertionError("Use one existing empty owned generated-control directory")
        STARTED = time.monotonic()
        fixtures()

    def refused(self, record, *, before_projection=True):
        self.assertEqual(record["returncode"], 2)
        no_effects(self, record)
        if before_projection:
            self.assertEqual(record["observation"]["core_calls"]["project_epoch"], 0)
            self.assertEqual(record["observation"]["fixture_body_read_attempts"], 0)
        if record["report"] is not None:
            self.assertEqual(record["report"]["status"], "failed")
        self.assertEqual(record["input_pins_before"], record["input_pins_after"])

    def test_01_complete_generated_roster_real_core_and_two_requests(self):
        protocol, result = run_entry("complete-generated")
        self.assertEqual(result["returncode"], 0)
        no_effects(self, result)
        self.assertEqual(result["observation"]["core_calls"],
                         {"project_epoch": 5450, "initial": 2, "request_bytes": 2})
        report = result["report"]
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["mode"], "generated_control")
        self.assertEqual(report["roster_epochs"], 5450)
        self.assertEqual(report["projection_count"], 5450)
        self.assertEqual(report["request_count"], 2)
        self.assertEqual(result["observation"]["fixture_body_read_attempts"], 2)
        self.assertIs(report["original_body_access"], False)
        self.assertIs(report["full_original_projection_qualified"], False)
        self.assertIs(report["original_operation_enabled"], False)
        self.assertEqual(denials(report["guard_denials"]), 0)
        self.assertEqual(report["source_identity_scope"],
                         "Executed visual/contract/renderer dependency closure authenticated; epoch_provider.py local pin is recorded, not executed or independently qualified.")
        output = Path(protocol["output_root"])
        actual_output_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        self.assertIsNotNone(result["closure"])
        self.assertEqual(result["closure"]["status"], "passed")
        self.assertEqual(denials(result["closure"]["guard_denials"]), 0)
        self.assertEqual(result["closure"]["counters"]["cumulative_artifact_write_bytes"], actual_output_bytes)
        self.assertEqual((output / "GUARD_DENIALS.jsonl").read_bytes(), b"")
        expected = [f"{case}/{index:05d}" for case, count in CASES for index in range(count)]
        raw_lines = (output / "roster.jsonl").read_bytes().splitlines(keepends=True)
        self.assertEqual(len(raw_lines), 5450)
        previous = "0" * 64
        for expected_id, raw in zip(expected, raw_lines):
            row = json.loads(raw)
            self.assertEqual(set(row), {"epoch_id", "metadata", "signals", "previous_sha256"})
            self.assertEqual(row["epoch_id"], expected_id)
            self.assertEqual(row["previous_sha256"], previous)
            self.assertEqual(row["signals"]["bytes"], 72128)
            self.assertEqual(len(row["signals"]["sha256"]), 64)
            self.assertGreater(row["metadata"]["bytes"], 0)
            previous = hashlib.sha256(raw).hexdigest()
        for case, _ in CASES:
            anchor = output / "anchors" / case
            metadata = json.loads((anchor / "case.json").read_bytes())
            self.assertEqual(metadata["epoch_id"], case + "/00000")
            self.assertEqual(metadata["shape"], [3, 3000])
            self.assertEqual(metadata["sample_count"], 3000)
            self.assertEqual(metadata["sample_rate_hz"], 100)
            self.assertEqual(metadata["signals"], pin((anchor / "signals.npy").read_bytes()))
            request = json.loads((anchor / "request.json").read_bytes())
            self.assertEqual(len(request["input"]), 1)
            content = request["input"][0]["content"]
            images = [x for x in content if x["type"] == "input_image"]
            self.assertEqual(len(images), 1)
            png = base64.b64decode(images[0]["image_url"].split(",", 1)[1], validate=True)
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", png[16:24]), (1400, 820))
            self.assertEqual(images[0]["detail"], "original")
            self.assertEqual(request["tools"], [])
            self.assertEqual(request["tool_choice"], "none")
            self.assertIs(request["store"], False)
            self.assertEqual(request["truncation"], "disabled")
            self.assertNotIn("previous_response_id", request)
            self.assertNotIn("conversation", request)
        proposals = json.loads((output / "PROPOSED_EXPOSURES.json").read_bytes())
        self.assertEqual(proposals["status"], "incomplete_false_approval_proposals")
        self.assertEqual([row["epoch_id"] for row in proposals["rows"]], [case + "/00000" for case, _ in CASES])
        for row in proposals["rows"]:
            self.assertIs(row["approved"], False)
            self.assertIs(row["role_boundary_verified"], False)
            self.assertIsNone(row["programme_source"])
            self.assertIsNone(row["image_content_boundary"])
            self.assertEqual(len(row["required_six_mounts"]), 6)
        for name in ("provider_capacity_qualified", "input_token_bound_qualified", "remote_context_qualified",
                     "complete_paired_campaign_qualified", "shared_model_prior_qualified",
                     "hostile_programme_containment_qualified", "scientific_readiness", "population_generalization"):
            self.assertIs(report[name], False)
        self.assertNotIn("predictions.npz", {p.name for p in output.rglob("*")})
        self.assertNotIn("END.json", {p.name for p in output.rglob("*")})
        self.assertTrue(proposals)

    def test_02_protocol_digest_refuses_before_fixture_or_projection(self):
        _, result = run_entry("bad-protocol-pin", corrupt_cli_hash=True)
        self.refused(result)

    def test_03_changed_source_body_refuses_before_fixture_or_projection(self):
        def change(protocol, root):
            private_repo = root / "generated-repository"
            copied_source = private_repo / "benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1/epoch_visual.py"
            raw = (EPOCH / "epoch_visual.py").read_bytes()
            # Only this disposable generated source copy changes. W is read-only.
            changed = raw.replace(b"Portable", b"Portablf", 1)
            self.assertEqual(len(changed), len(raw))
            self.assertNotEqual(pin(changed), pin(raw))
            write_new(copied_source, changed)
            protocol["repository_root"] = str(private_repo)
            protocol["source"]["path"] = str(copied_source)
        _, result = run_entry("bad-source-body", change)
        self.refused(result)
        self.assertIsNotNone(result["report"])
        self.assertEqual(result["report"]["failure_stage"], "maintained_source_runtime")
        self.assertEqual(result["report"]["error"]["message"], "descriptor identity mismatch")

    def test_04_original_selection_cannot_be_authorized_by_generated_protocol(self):
        def change(protocol, root):
            protocol["mode"] = "original"
            protocol["selected"] = True
            protocol["fixtures"] = []
            protocol["materials"] = fixtures()["canary"]
        _, result = run_entry("original-disabled", change)
        self.refused(result)
        self.assertEqual(result["observation"]["canary_read_attempts"], 0)

    def test_05_reordered_roster_refuses_before_projection(self):
        def change(protocol, root):
            protocol["fixtures"].reverse()
        _, result = run_entry("reordered-fixtures", change)
        self.refused(result)
        def duplicate(protocol, root):
            protocol["fixtures"][1]["signals"] = copy.deepcopy(protocol["fixtures"][0]["signals"])
        _, result = run_entry("duplicate-fixture-source", duplicate)
        self.refused(result)

    def test_06_existing_output_is_not_overwritten(self):
        def change(protocol, root):
            out = Path(protocol["output_root"])
            out.mkdir()
            write_new(out / "PRESERVE.bin", b"GENERATED_EXISTING_OUTPUT\n")
        protocol, result = run_entry("existing-output", change)
        self.refused(result)
        self.assertEqual((Path(protocol["output_root"]) / "PRESERVE.bin").read_bytes(), b"GENERATED_EXISTING_OUTPUT\n")

    def test_07_caught_readonly_input_write_still_fails_actual_entry(self):
        target = fixtures()["rows"][0]["signals"]["path"]
        _, result = run_entry("caught-input-write", attack="write_fixture", target=target)
        self.refused(result, before_projection=False)
        self.assertTrue(result["observation"]["attack_attempted"])
        self.assertTrue(result["observation"]["attack_denied"])
        self.assertIsNotNone(result["report"])
        self.assertGreaterEqual(denials(result["report"]["guard_denials"]), 1)
        self.assertEqual(result["report"]["error"]["message"], "sticky guard denial")

    def test_08_caught_outside_read_still_fails_actual_entry(self):
        _, result = run_entry("caught-outside-read", attack="read_canary", target=fixtures()["canary"]["path"])
        self.refused(result, before_projection=False)
        self.assertTrue(result["observation"]["attack_attempted"])
        self.assertTrue(result["observation"]["attack_denied"])
        self.assertEqual(result["observation"]["canary_read_attempts"], 1)
        self.assertGreaterEqual(denials(result["report"]["guard_denials"]), 1)
        self.assertEqual(result["report"]["error"]["message"], "sticky guard denial")

    def test_09_write_ceiling_refusal_has_bounded_failure_evidence(self):
        def change(protocol, root):
            protocol["limits"]["write_bytes"] = 131072
        _, result = run_entry("small-write-allocation", change, attack="terminal_write",
                              target=fixtures()["rows"][0]["signals"]["path"])
        self.refused(result, before_projection=False)
        output = Path(result["protocol"]["path"]).parent / "output"
        total = sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) if output.exists() else 0
        self.assertLessEqual(total, 131072)
        self.assertIsNotNone(result["report"])
        self.assertEqual(result["report"]["failure_stage"], "anchor")
        self.assertLessEqual(result["observation"]["core_calls"]["project_epoch"], 2)
        self.assertTrue(result["observation"]["attack_attempted"])
        self.assertTrue(result["observation"]["attack_denied"])
        self.assertIsNotNone(result["closure"])
        self.assertEqual(result["closure"]["status"], "failed")
        self.assertGreaterEqual(denials(result["closure"]["guard_denials"]), 1)
        journal = [json.loads(line) for line in (output / "GUARD_DENIALS.jsonl").read_bytes().splitlines()]
        self.assertGreaterEqual(len(journal), 1)

    def test_10_preloaded_contract_refuses_before_fixture_or_projection(self):
        _, result = run_entry("preloaded-contract", attack="preloaded_contract")
        self.refused(result)
        self.assertIsNotNone(result["report"])
        self.assertEqual(result["report"]["failure_stage"], "maintained_source_runtime")

def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PreflightControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {"schema": "n007_preflight_generated_controls_v1",
               "tests_run": result.testsRun, "failures": len(result.failures),
               "errors": len(result.errors), "skips": len(result.skipped),
               "selected_original_operations": 0, "selected_api_calls": 0,
               "selected_containers": 0, "observed_runs": RUNS,
               "cumulative_create_only_artifact_bytes_before_result": retained_bytes(),
               "unexpected_fixture_mutations": UNEXPECTED_MUTATIONS, "scope": "Generated source controls only; no authentic input, provider, containment or science qualification."}
    write_new(ROOT / "RESULT.json", encoded(summary), terminal=True)
    print(json.dumps({"result": str(ROOT / "RESULT.json"), "artifact_bytes": retained_bytes(),
                      "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)},
                     sort_keys=True))
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    raise SystemExit(main())

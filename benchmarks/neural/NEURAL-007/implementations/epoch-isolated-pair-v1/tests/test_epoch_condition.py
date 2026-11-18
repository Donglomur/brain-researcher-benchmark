"""Finite generated controls for the explicitly separate epoch condition.

All signals are generated, complete three-channel 3000-sample epochs. No
original packet, provider, Docker daemon or participant programme is executed.
These controls cannot qualify authentic capacity, hidden priors or containment.
"""
from contextlib import contextmanager, ExitStack, redirect_stdout
import base64
import importlib
import io
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get("N007_EPOCH_SOURCE_ROOT", HERE.parent))
sys.path.insert(0, str(SOURCE))
C = importlib.import_module("contract")
if Path(C.__file__).resolve() != (SOURCE / "contract.py").resolve():
    raise ValueError("Tests require the single co-located contract module")
V = importlib.import_module("epoch_visual")
EP = importlib.import_module("epoch_provider")
PG = importlib.import_module("epoch_programme")
PA = importlib.import_module("epoch_admission")

CONTROL = Path(os.environ["N007_EPOCH_CONTROL_ROOT"])
CREATED_ROOTS = []
INITIAL_EXTENTS = {}
EXTRA_WRITES = []
PENDING_RESTORE_BYTES = 0
FIXTURES = None
VISUAL_RUNS = None
VISUAL_ATTEMPTED = False
RUNTIME = None
PROGRAMME_RUNTIME = None
PROGRAMME_FIXTURE = None
MAX_FIXTURE_BYTES = 2621440
MAX_MUTATION_BYTES = 917504
MAX_PNG_BYTES = 131072
MAX_REQUEST_BYTES = 393216
SECRET = "GENERATED_EPOCH_CONTROL_SECRET_0123456789"
TOKEN_BOUND_CALLS = []


def capture_created_files():
    for root in CREATED_ROOTS:
        for path in root.rglob("*"):
            if path.is_file():
                INITIAL_EXTENTS.setdefault(str(path), path.stat().st_size)


def artifact_accounting():
    """Retained creation extents plus separately charged mutation/restoration.

Producer paths are fresh and never overwritten. Capture creation before any
test mutation, and include partial files if a producer or assertion failed.
No fixture or failed custody is removed automatically.
"""
    capture_created_files()
    created = sum(INITIAL_EXTENTS.values())
    extra = sum(item["bytes"] for item in EXTRA_WRITES)
    return {"classification": "GENERATED_COMPONENT_ONLY",
            "fixture_roots": [str(root) for root in CREATED_ROOTS],
            "created_files": len(INITIAL_EXTENTS), "created_file_bytes": created,
            "extra_write_bytes": extra, "extra_writes": list(EXTRA_WRITES),
            "cumulative_fixture_write_bytes": created + extra,
            "cumulative_fixture_cap_bytes": MAX_FIXTURE_BYTES,
            "producer_overwrites": 0, "producer_deletions": 0}


def check_fixture_budget():
    accounting = artifact_accounting()
    if accounting["cumulative_fixture_write_bytes"] > MAX_FIXTURE_BYTES:
        raise AssertionError("Generated fixture allocation exceeded")


@contextmanager
def retained_mutation(path, raw):
    """Preserve the original fixture and charge both writes, even on failure."""
    global PENDING_RESTORE_BYTES
    path = Path(path)
    capture_created_files()
    original = path.read_bytes()
    proposed = len(raw) + len(original)
    if sum(item["bytes"] for item in EXTRA_WRITES) + proposed + PENDING_RESTORE_BYTES > MAX_MUTATION_BYTES:
        raise AssertionError("Generated mutation allocation exceeded before writing")
    if sum(INITIAL_EXTENTS.values()) + sum(item["bytes"] for item in EXTRA_WRITES) + proposed + PENDING_RESTORE_BYTES > MAX_FIXTURE_BYTES:
        raise AssertionError("Generated fixture allocation exceeded before writing")
    EXTRA_WRITES.append({"path": str(path), **C.pin(raw), "purpose": "mutation"})
    PENDING_RESTORE_BYTES += len(original)
    try:
        path.write_bytes(raw)
        yield
    finally:
        EXTRA_WRITES.append({"path": str(path), **C.pin(original), "purpose": "restoration"})
        PENDING_RESTORE_BYTES -= len(original)
        path.write_bytes(original)


def knowledge(model="generated-epoch-agent"):
    return {"schema": "sleep007_epoch_shared_knowledge_v1", "provider": "openai",
            "model": model, "revision": "generated-fixed-revision",
            "policy": "shared_declared_base_agent_prior_only", "external_assets": []}


def dependency_root():
    supplied = os.environ.get("N007_DEPENDENCY_ROOT")
    if supplied:
        return Path(supplied).absolute()
    for parent in SOURCE.resolve().parents:
        if (parent / "benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/viewer.py").is_file():
            return parent
    raise ValueError("Set N007_DEPENDENCY_ROOT for an unpublished source preparation")


def runtime():
    global RUNTIME
    if RUNTIME is None:
        root = dependency_root()
        implementations = root / "benchmarks/neural/NEURAL-007/implementations"
        old_sender = Path(os.environ.get("N007_WHOLE_HISTORY_INTEGRATION_ROOT",
                                        implementations / "viewer-provider-integration-v1"))
        old_admission = Path(os.environ.get("N007_WHOLE_HISTORY_ADMISSION_ROOT",
                                           implementations / "finite-workflow-v1"))
        RUNTIME = V.load_runtime(root, old_sender, old_admission, SOURCE / "contract.py")
    return RUNTIME


def programme_runtime():
    global PROGRAMME_RUNTIME
    if PROGRAMME_RUNTIME is None:
        implementations = dependency_root() / "benchmarks/neural/NEURAL-007/implementations"
        old_admission = Path(os.environ.get("N007_WHOLE_HISTORY_ADMISSION_ROOT",
                                           implementations / "finite-workflow-v1"))
        PROGRAMME_RUNTIME = PG.load_runtime(implementations, old_admission)
    return PROGRAMME_RUNTIME


def programme_fixture():
    global PROGRAMME_FIXTURE
    if PROGRAMME_FIXTURE is not None:
        return PROGRAMME_FIXTURE
    f = fixtures(); root = f["root"] / "programme"
    root.mkdir(mode=0o700)
    source = C.write_new(root / "SOURCE.json", C.encode({
        "schema": "sleep007_epoch_source_v1",
        "files": {name: C.pin((SOURCE / name).read_bytes()) for name in sorted(PG.RUNTIME_FILES)}}))
    prior = C.write_new(root / "KNOWLEDGE.json", C.encode(knowledge()))
    code = root / "generated_program.py"
    C.write_new(code, b"# GENERATED_COMPONENT_ONLY; this programme is never executed.\nraise RuntimeError('not selected')\n")
    prepared = PG.prepare_programme(code, prior, source, root / "prepared",
                                    image="sha256:" + "1" * 64)
    value, frozen, definition, checked_prior = PG.checked_prepared(prepared)
    PROGRAMME_FIXTURE = {"root": root, "source": source, "knowledge": prior, "prepared": prepared,
                         "value": value, "frozen": frozen, "definition": definition,
                         "checked_knowledge": checked_prior}
    check_fixture_budget()
    return PROGRAMME_FIXTURE


def budget(turns=2):
    return runtime()["provider"].Budget(
        max_turns=turns, max_images=2, max_history_bytes=MAX_REQUEST_BYTES,
        max_request_bytes=MAX_REQUEST_BYTES, max_response_bytes=8192,
        max_total_provider_bytes=1048576, context_tokens=131072,
        output_tokens=256, wall_seconds=120, image_detail="original")


def request_parts(raw):
    value = C.decode(raw)
    if len(raw) > MAX_REQUEST_BYTES:
        raise AssertionError("Generated request cap exceeded before sender")
    if len(value["input"]) != 1 or value["input"][0]["role"] != "user":
        raise AssertionError("A target request contains another message context")
    content = value["input"][0]["content"]
    header = C.decode(content[0]["text"])
    images = []
    for item in content[1:]:
        if item["type"] != "input_image" or not item["image_url"].startswith("data:image/png;base64,"):
            raise AssertionError("Exact image-only evidence expected")
        png = base64.b64decode(item["image_url"].split(",", 1)[1], validate=True)
        if not (0 < len(png) <= MAX_PNG_BYTES and png[:8] == b"\x89PNG\r\n\x1a\n"
                and struct.unpack(">II", png[16:24]) == (1400, 820)):
            raise AssertionError("Generated complete original-canvas PNG exceeds its fixture cap")
        images.append(png)
    if not 1 <= len(images) <= 2:
        raise AssertionError("Only overview and optional same-target detail are allowed")
    return value, header, images


def control_token_bound(raw, deadline):
    request_parts(raw)
    TOKEN_BOUND_CALLS.append(C.pin(raw))
    # A generated response/accounting bound, deliberately not a capacity oracle.
    return 65536


def provider_response(action, response_id):
    return C.encode({"object": "response", "id": response_id, "status": "completed",
                     "error": None, "incomplete_details": None, "model": knowledge()["model"],
                     "tools": [], "tool_choice": "none", "parallel_tool_calls": False,
                     "store": False, "background": False, "truncation": "disabled",
                     "previous_response_id": None, "conversation": None, "max_output_tokens": 256,
                     "output": [{"type": "message", "role": "assistant", "status": "completed",
                                 "content": [{"type": "output_text", "text": C.encode({"viewer_action": action}).decode()}]}],
                     "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}})


class FakeResponse:
    status = 200

    def __init__(self, body):
        if not 0 < len(body) <= 8192:
            raise AssertionError("Generated response cap exceeded before custody")
        self.body, self.length = io.BytesIO(body), len(body)

    def read(self, count):
        raw = self.body.read(min(count, 73)); self.length -= len(raw)
        return raw

    def getheader(self, name, default=None):
        return "identity"

    def close(self):
        pass


class FakeHTTPS:
    sock = None

    def __init__(self, owner, host, port, timeout, context):
        if host != "api.openai.com" or port != 443 or timeout <= 0 or not context.check_hostname:
            raise AssertionError("Unchanged sender TLS interface required")
        self.owner = owner

    def set_debuglevel(self, level):
        if level != 0:
            raise AssertionError("No credential-bearing debug output")

    def request(self, method, path, *, body, headers, encode_chunked):
        if (method, path, encode_chunked) != ("POST", "/v1/responses", False):
            raise AssertionError("One exact unchanged HTTPS operation")
        if headers["Authorization"] != "Bearer " + SECRET:
            raise AssertionError("Generated credential descriptor mismatch")
        request_parts(body)
        self.owner.requests.append(body)

    def getresponse(self):
        if not self.owner.responses:
            raise AssertionError("No unselected generated retry or extra turn")
        return FakeResponse(self.owner.responses.pop(0))

    def close(self):
        pass


class FakeFactory:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, *args, **kwargs):
        return FakeHTTPS(self, *args, **kwargs)


def visual_runs():
    global VISUAL_RUNS, VISUAL_ATTEMPTED
    if VISUAL_RUNS is not None:
        return VISUAL_RUNS
    if VISUAL_ATTEMPTED:
        raise AssertionError("Prior generated fixture failed; automatic retry is forbidden")
    VISUAL_ATTEMPTED = True
    f = fixtures()
    actions = [[{"action": "window", "start_sample": 400, "stop_sample": 900},
                {"action": "respond", "epoch_id": f["packets"][0].epoch_id, "probabilities": [0.2] * 5}],
               [{"action": "respond", "epoch_id": f["packets"][1].epoch_id,
                 "probabilities": [0.1, 0.2, 0.3, 0.1, 0.3]}]]
    runs = []
    for index, (packet, commands) in enumerate(zip(f["packets"], actions)):
        factory = FakeFactory([provider_response(action, f"resp_generated_epoch_{index}_{turn}")
                               for turn, action in enumerate(commands)])
        root = f["root"] / ("visual_" + str(index))
        original_write = runtime()["base_client"].write_new
        original_json = runtime()["sender"].Custody.json
        def bounded_metadata(directory, name, raw, cap=32768):
            if len(raw) > 16384:
                raise AssertionError("Generated provider metadata cap exceeded before writing")
            if index == 1 and name == "000000.json":
                raise OSError("GENERATED_COMPONENT_ONLY durable event sink failure")
            return original_write(directory, name, raw, cap)
        def bounded_custody_json(custody, name, value):
            if len(runtime()["sender"].encode(value)) > 16384:
                raise AssertionError("Generated HTTP/bridge metadata cap exceeded before writing")
            return original_json(custody, name, value)
        with patch.object(runtime()["base_client"], "write_new", side_effect=bounded_metadata), \
             patch.object(runtime()["sender"].Custody, "json", new=bounded_custody_json):
            if index == 0:
                end = EP.run_epoch(runtime(), packet, knowledge(), budget(len(commands)), root, SECRET,
                                   control_token_bound, session_id="a" * 32, http_factory=factory)
            else:
                try:
                    EP.run_epoch(runtime(), packet, knowledge(), budget(len(commands)), root, SECRET,
                                 control_token_bound, session_id="b" * 32, http_factory=factory)
                except ValueError as exc:
                    if "durable_event_before_action" not in str(exc):
                        raise
                else:
                    raise AssertionError("Sink failure must withhold the accepted answer")
        if index == 1:
            end = C.decode((root / "END.json").read_bytes())
            if end["status"] != "failed_no_admission" or end["first_accepted_answer"] or end["probabilities"] is not None:
                raise AssertionError("Generated failed custody was incorrectly accepted")
        if factory.responses or len(factory.requests) != len(commands):
            raise AssertionError("Generated target did not close on its first accepted answer")
        runs.append({"root": root, "packet": packet, "factory": factory, "end": end, "failed": index == 1})
        check_fixture_budget()
    VISUAL_RUNS = runs
    return runs


class TargetClock:
    def __init__(self, index):
        self.index, self.calls = index, []

    def __getitem__(self, index):
        if index != self.index:
            raise AssertionError("Projection read another target's clock")
        self.calls.append(index)
        return (index * 30 / 3600, 0.0, 1.0)


class GeneratedPerson:
    """Only the requested target can be read; no full-night array is present."""
    def __init__(self, case, index, phase):
        self.case, self.index, self.phase = case, index, phase
        self.epochs = dict(C.CASES)[case]
        self.clock, self.calls = TargetClock(index), []
        self.rows = [[(channel + 1) * 0.000008 * math.sin((sample + phase) * math.pi / (25 + channel * 9))
                      for sample in range(3000)] for channel in range(3)]

    def samples(self, start, stop, channels):
        expected = (self.index * 3000, (self.index + 1) * 3000, list(C.CHANNELS))
        if (start, stop, channels) != expected:
            raise AssertionError("Projection requested a neighbouring epoch or incomplete channels")
        self.calls.append((start, stop, tuple(channels)))
        return [list(row) for row in self.rows]


def fixtures():
    global FIXTURES
    if FIXTURES is not None:
        return FIXTURES
    root = CONTROL / "epoch_condition"
    CREATED_ROOTS.append(root)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    C.write_new(root / "GENERATED_COMPONENT_ONLY", b"Complete synthetic epochs; no genuine provider or capacity qualification.\n")
    people = [GeneratedPerson("development-001", 1, 0), GeneratedPerson("development-002", 0, 7)]
    packets = [C.project_epoch(person, person.index) for person in people]
    if any(len(packet.signals_npy) != 72128 or len(C.encode(packet.metadata())) > 4096 for packet in packets):
        raise AssertionError("Frozen complete generated epoch extent changed before writing")
    descriptors = [C.write_projection(packet, root / ("target_" + str(index)))
                   for index, packet in enumerate(packets)]
    FIXTURES = {"root": root, "people": people, "packets": packets, "descriptors": descriptors}
    check_fixture_budget()
    return FIXTURES


class ContractControls(unittest.TestCase):
    def test_complete_three_channel_epoch_projection_and_boundary(self):
        f = fixtures()
        for person, packet, descriptor in zip(f["people"], f["packets"], f["descriptors"]):
            self.assertEqual(person.calls, [(person.index * 3000, (person.index + 1) * 3000, tuple(C.CHANNELS))])
            self.assertEqual(set(person.clock.calls), {person.index})
            self.assertEqual(packet.samples(0, 3000, list(C.CHANNELS)), person.rows)
            self.assertEqual(C.read_projection(descriptor).signals_npy, packet.signals_npy)
            self.assertEqual(packet.metadata()["shape"], [3, 3000])
            self.assertFalse(hasattr(packet, "root"))
            self.assertFalse(hasattr(packet, "packet"))
            for start, stop, channels in [(-1, 2999, list(C.CHANNELS)), (0, 3001, list(C.CHANNELS)),
                                           (3000, 6000, list(C.CHANNELS)), (0, 3000, list(reversed(C.CHANNELS)))]:
                with self.subTest(window=(start, stop), channels=channels), self.assertRaises(ValueError):
                    packet.samples(start, stop, channels)
            for field, value in [("shape", [4, 3000]), ("sample_count", 2999),
                                 ("start_sample", packet.start_sample + 3000), ("channels", list(C.CHANNELS[:2]))]:
                metadata = packet.metadata(); metadata[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    C.EpochPacket(metadata, packet.signals_npy)
            for field in ("previous_answers", "labels", "parent_packet_root"):
                metadata = packet.metadata(); metadata[field] = "GENERATED_FORBIDDEN"
                with self.subTest(extra=field), self.assertRaises(ValueError):
                    C.EpochPacket(metadata, packet.signals_npy)
            for raw in (packet.signals_npy.replace(b"'<f8'", b"'>f8'", 1),
                        packet.signals_npy.replace(b"(3, 3000)", b"(4, 2250)", 1),
                        packet.signals_npy + b"\0" * 8):
                metadata = packet.metadata(); metadata["signals"] = C.pin(raw)
                with self.assertRaises(ValueError):
                    C.EpochPacket(metadata, raw)
        bad = C.write_projection(f["packets"][0], f["root"] / "forbidden_extra_input")
        C.write_new(Path(bad["root"]) / "labels.npy", b"GENERATED_FORBIDDEN_NOT_LABEL_DATA")
        with self.assertRaises(ValueError):
            C.read_projection(bad)
        check_fixture_budget()

    def test_all_5450_targets_subject_boundaries_and_first_answer_lock(self):
        names = C.required_targets()
        self.assertEqual(len(names), 5450)
        self.assertEqual(len(set(names)), 5450)
        self.assertEqual((names[0], names[2779], names[2780], names[-1]),
                         ("development-001/00000", "development-001/02779",
                          "development-002/00000", "development-002/02669"))
        collector = C.FirstAnswers()
        evidence = C.pin(b"GENERATED_COMPONENT_ONLY metadata control; no provider evidence")
        collector.accept(names[0], [0.2] * 5, evidence)
        with self.assertRaises(ValueError):
            collector.accept(names[0], [1.0, 0.0, 0.0, 0.0, 0.0], evidence)
        with self.assertRaises(ValueError):
            collector.complete()
        for name in names[1:]:
            collector.accept(name, [0.2] * 5, evidence)
        rows = collector.complete()
        self.assertEqual([row["epoch_id"] for row in rows], list(names))
        self.assertEqual(rows[0]["probabilities"], [0.2] * 5)
        for altered in (rows[:-1], rows[::-1], rows[:2780] + rows[:2670]):
            with self.assertRaises(ValueError):
                C.checked_complete_rows(altered)
        for name in ("development-001/02780", "development-002/02670", "development-003/00000"):
            with self.assertRaises(ValueError):
                C.checked_target(name)

    def test_shared_prior_declaration_is_explicit_and_does_not_allow_assets(self):
        declared = knowledge()
        self.assertEqual(C.checked_knowledge(declared), declared)
        for field, value in [("external_assets", ["generated-yasa-model"]),
                             ("policy", "programme_only_training"), ("revision", "")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                C.checked_knowledge(dict(declared, **{field: value}))
        for field in declared:
            missing = dict(declared); del missing[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                C.checked_knowledge(missing)
        with self.assertRaises(ValueError):
            C.checked_knowledge(dict(declared, hidden_prior_equality_qualified=True))


class ProgrammeControls(unittest.TestCase):
    def phase(self):
        f, p = fixtures(), programme_fixture()
        mounts, packet = PG.make_mounts(p["value"], p["frozen"]["files"], f["descriptors"][0])
        origin = time.monotonic()
        resources = dict(programme_runtime()["common"].PROGRAMME_RESOURCES)
        request = PG.phase_request(packet.epoch_id, p["definition"], PG.plain(p["value"]["definition"]),
                                   C.pin(b"GENERATED_COMPONENT_ONLY external exposure placeholder"),
                                   resources, origin, origin + 200)
        return mounts, packet, request, origin + 300

    def test_exact_same_epoch_file_mounts_and_canonical_resource_limits(self):
        f, p = fixtures(), programme_fixture()
        mounts, packet, request, deadline = self.phase()
        self.assertEqual(set(mounts), PG.INPUT_TARGETS)
        self.assertEqual(packet.signals_npy, f["packets"][0].signals_npy)
        self.assertEqual(mounts["/input/signals.npy"]["files"], {"signals.npy": f["descriptors"][0]["signals"]})
        self.assertEqual(mounts["/input/case.json"]["files"], {"case.json": f["descriptors"][0]["case"]})
        self.assertTrue(all(item["kind"] == "file" for item in mounts.values()))
        other_mounts, other = PG.make_mounts(p["value"], p["frozen"]["files"], f["descriptors"][1])
        self.assertEqual(other.signals_npy, f["packets"][1].signals_npy)
        self.assertNotEqual(other_mounts["/input/signals.npy"]["files"], mounts["/input/signals.npy"]["files"])
        self.assertIs(p["definition"]["hidden_pretraining_verified"], False)
        self.assertIs(p["definition"]["matched_agent_provenance_qualified"], False)
        self.assertEqual(p["definition"]["additional_training_or_reference_assets"], [])
        altered = C.decode(C.encode(mounts)); altered["/input/other_epoch.npy"] = altered["/input/signals.npy"]
        with self.assertRaises(ValueError):
            PG.checked_mounts(altered)
        altered = C.decode(C.encode(mounts)); altered["/input/signals.npy"]["kind"] = "directory"
        with self.assertRaises(ValueError):
            PG.checked_mounts(altered)
        altered = C.decode(C.encode(mounts))
        altered["/input/signals.npy"]["files"]["other_epoch.npy"] = f["descriptors"][1]["signals"]
        with self.assertRaises(ValueError):
            PG.checked_mounts(altered)
        PG.validate_request(programme_runtime(), request, mounts, deadline)
        self.assertEqual(len(request["resources"]), 18)
        missing = C.decode(C.encode(request)); del missing["resources"]["scratch_bytes"]
        with self.assertRaises(ValueError):
            PG.validate_request(programme_runtime(), missing, mounts, deadline)
        unaligned = C.decode(C.encode(request)); unaligned["resources"]["scratch_bytes"] += 1
        with self.assertRaises(ValueError):
            PG.validate_request(programme_runtime(), unaligned, mounts, deadline)
        check_fixture_budget()

    def test_unqualified_exposure_stops_before_execution_and_model_image_mismatches_fail(self):
        f, p = fixtures(), programme_fixture()
        root = p["root"]
        exposure = C.write_new(root / "INVALID_EXPOSURE.json", C.encode({}))
        boundary = C.write_new(root / "INVALID_BOUNDARY.json", C.encode({}))
        resources = dict(programme_runtime()["common"].PROGRAMME_RESOURCES)
        origin = time.monotonic()
        class NoExecution:
            calls = 0
            def execute_phase(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("Unqualified exposure reached participant execution")
        provider = NoExecution()
        with self.assertRaises(ValueError):
            PG.execute_phase(programme_runtime(), provider, p["prepared"], f["descriptors"][0],
                             exposure, resources, origin, origin + 200, origin + 300, [],
                             boundary_audit=boundary)
        self.assertEqual(provider.calls, 0)
        wrong_image = dict(p["definition"], image="sha256:" + "2" * 64)
        request = PG.phase_request(f["packets"][0].epoch_id, wrong_image, PG.plain(p["value"]["definition"]),
                                   PG.plain(exposure), resources, origin, origin + 200)
        request_descriptor = C.write_new(root / "WRONG_IMAGE_REQUEST.json", C.encode(request))
        empty_receipt = C.write_new(root / "EMPTY_NEGATIVE_RECEIPT.json", C.encode({}))
        record = {"epoch_id": f["packets"][0].epoch_id, "projection": f["descriptors"][0],
                  "prepared": p["prepared"], "exposure": exposure, "boundary_audit": boundary,
                  "request": request_descriptor, "receipt": empty_receipt,
                  "observer_value": {"receipt": {}, "receipt_pin": PG.plain(empty_receipt),
                                     "independent_candidate_channel": True},
                  "prediction": empty_receipt, "result": empty_receipt}
        # Synthetic incomplete records exercise rejection only, never positive admission.
        with self.assertRaisesRegex(ValueError, "Exact epoch producer request"):
            PG.admit_phase(programme_runtime(), record, f["packets"][0], knowledge())
        with self.assertRaisesRegex(ValueError, "Same pinned shared prior declaration"):
            PG.admit_phase(programme_runtime(), record, f["packets"][0], knowledge("different-generated-model"))
        check_fixture_budget()

    def test_old_condition_partial_panel_and_both_pretruth_entries_fail_closed(self):
        f, p = fixtures(), programme_fixture()
        root = p["root"]
        row = {"epoch_id": f["packets"][0].epoch_id, "record": p["prepared"]}
        def collection(name, condition):
            return C.write_new(root / name, C.encode({"schema": "sleep007_epoch_arm_collection_v1",
                "condition": condition, "knowledge": p["knowledge"], "source": p["source"],
                "rows": [row], "submission": p["prepared"]}))
        old = collection("OLD_CONDITION.json", "whole_person_raw_viewer_zero_shot")
        with self.assertRaisesRegex(ValueError, "no whole-history pooling"):
            PA._collection(old, C.VISUAL_CONDITION)
        visual = collection("PARTIAL_VISUAL.json", C.VISUAL_CONDITION)
        programme = collection("PARTIAL_PROGRAMME.json", C.PROGRAMME_CONDITION)
        with self.assertRaisesRegex(ValueError, "Complete5450"):
            PA._collection(visual, C.VISUAL_CONDITION)
        dependency = dependency_root()
        implementations = dependency / "benchmarks/neural/NEURAL-007/implementations"
        sender_root = Path(os.environ.get("N007_WHOLE_HISTORY_INTEGRATION_ROOT", implementations / "viewer-provider-integration-v1"))
        admission_root = Path(os.environ.get("N007_WHOLE_HISTORY_ADMISSION_ROOT", implementations / "finite-workflow-v1"))
        never_private = root / "NEVER_OPEN_PRIVATE_TARGETS.json"
        config = {"schema": "sleep007_epoch_pair_request_v1", "source": p["source"],
                  "viewer_collection": visual, "programme_collection": programme,
                  "packet_roots": {}, "references": {},
                  "private_locations": {"path": str(never_private), "bytes": 1, "sha256": "0" * 64},
                  "implementations_root": str(implementations), "finite_bindings_root": str(admission_root),
                  "visual_runtime": {"root": str(dependency), "whole_history_integration_root": str(sender_root),
                                     "whole_history_admission_root": str(admission_root)}}
        out = root / "NEVER_START_GRADER"
        with patch.object(PA.subprocess, "Popen", side_effect=AssertionError("Invalid public bundle launched grader")):
            with self.assertRaisesRegex(ValueError, "Complete5450"):
                PA.coordinate_compare(config, out, grader_wall_seconds=1)
        self.assertFalse(out.exists())
        request = C.write_new(root / "PARTIAL_PAIR_REQUEST.json", C.encode(config))
        capture = io.StringIO()
        with redirect_stdout(capture):
            result = PA.main(["--request", request["path"], "--bytes", str(request["bytes"]), "--sha256", request["sha256"]])
        self.assertEqual(result, 2)
        failure = C.decode(capture.getvalue().encode())
        self.assertEqual(failure, {"status": "failed", "failure_stage": "public_admission", "private_loader_calls": 0})
        self.assertFalse(never_private.exists())
        check_fixture_budget()


class VisualControls(unittest.TestCase):
    def test_full_overview_survives_detail_controls_and_first_answer_closes_target(self):
        packet = fixtures()["packets"][0]
        session = V.Session(packet, runtime(), 8, "c" * 32)
        initial, images = session.initial()
        self.assertEqual(initial["overview"]["state"],
                         {"start_sample": 0, "stop_sample": 3000, "gain_uv": 50, "channels": list(C.CHANNELS)})
        self.assertEqual(len(images), 1)
        overview = images[0]
        for action in ({"action": "window", "start_sample": 400, "stop_sample": 900},
                       {"action": "channels", "channels": [C.CHANNELS[1]]},
                       {"action": "gain", "microvolts_per_division": 100}):
            session.handle(action)
            value, header, current_images = request_parts(V.request_bytes(session, knowledge()["model"], budget(), knowledge()))
            self.assertEqual(current_images[0], overview)
            self.assertEqual(header["observation"]["overview"], initial["overview"])
            self.assertEqual(header["observation"]["target"], packet.metadata())
            self.assertEqual(len(current_images), 2)
            self.assertEqual(value["tools"], [])
            self.assertEqual(value["tool_choice"], "none")
            self.assertIsNone(value.get("previous_response_id"))
            self.assertIsNone(value.get("conversation"))
            self.assertNotIn("history", header)
            self.assertNotIn("previous_answers", header["observation"])
        for action in ({"action": "epoch", "index": 0},
                       {"action": "window", "start_sample": -100, "stop_sample": 3000},
                       {"action": "window", "start_sample": 0, "stop_sample": 3001},
                       {"action": "respond", "epoch_id": "development-001/00000", "probabilities": [0.2] * 5}):
            with self.assertRaises(ValueError):
                session.handle(action)
        with self.assertRaises(ValueError):
            V.request_bytes(session, "different-generated-model", budget(), knowledge())
        accepted = session.handle({"action": "respond", "epoch_id": packet.epoch_id, "probabilities": [0.2] * 5})
        self.assertTrue(accepted["full_three_channel_epoch_available"])
        for action in ({"action": "inspect"},
                       {"action": "respond", "epoch_id": packet.epoch_id, "probabilities": [1, 0, 0, 0, 0]}):
            with self.assertRaises(ValueError):
                session.handle(action)
        self.assertEqual(session.answer, [0.2] * 5)
        self.assertNotEqual(V.CONDITION, runtime()["viewer"].MODE)
        self.assertEqual(runtime()["provider"].PROVIDER_IMAGE_CAP, 1500)

    def test_generated_sender_replay_fresh_contexts_and_exact_image_tamper_rejection(self):
        runs = visual_runs()
        before_bound = len(TOKEN_BOUND_CALLS)
        self.assertEqual(before_bound, 3)
        self.assertNotEqual(runs[0]["end"]["session_id"], runs[1]["end"]["session_id"])
        all_response_ids = []
        for index, run in enumerate(runs):
            other = runs[1 - index]["packet"].epoch_id
            for raw in run["factory"].requests:
                _, header, _ = request_parts(raw)
                self.assertEqual(header["observation"]["target"], run["packet"].metadata())
                self.assertNotIn(other.encode(), raw)
            if run["failed"]:
                self.assertEqual(run["end"]["failure_stage"], "durable_event_before_action")
                self.assertIsNone(run["end"]["probabilities"])
                self.assertIs(run["end"]["first_accepted_answer"], False)
                with self.assertRaises(ValueError):
                    EP.audit_session(run["root"], run["packet"], runtime(), knowledge())
                audited = run["end"]
            else:
                audited = EP.audit_session(run["root"], run["packet"], runtime(), knowledge())
                self.assertEqual(audited["probabilities"], run["end"]["probabilities"])
            for key in ("provider_context_qualified", "provider_capacity_qualified", "token_bound_qualified", "scientific_qualification"):
                self.assertIs(audited[key], False)
                self.assertIs(run["end"][key], False)
            all_response_ids.extend(audited["response_ids"])
        self.assertEqual(len(all_response_ids), len(set(all_response_ids)))
        self.assertNotEqual(request_parts(runs[0]["factory"].requests[0])[2][0],
                            request_parts(runs[1]["factory"].requests[0])[2][0])
        self.assertEqual(len(TOKEN_BOUND_CALLS), before_bound)
        self.assertEqual([len(run["factory"].requests) for run in runs], [2, 1])
        with self.assertRaises(ValueError):
            EP.audit_session(runs[0]["root"], runs[1]["packet"], runtime(), knowledge())
        with self.assertRaises(ValueError):
            EP.audit_session(runs[0]["root"], runs[0]["packet"], runtime(), knowledge("different-generated-model"))
        path = runs[0]["root"] / "turns/000001/REQUEST.bin"
        value = C.decode(path.read_bytes())
        self.assertEqual(len(value["input"][0]["content"]), 3)
        del value["input"][0]["content"][1]  # Remove immutable overview, retain only detail.
        with retained_mutation(path, V.encode(value)):
            with self.assertRaises(ValueError):
                EP.audit_session(runs[0]["root"], runs[0]["packet"], runtime(), knowledge())
        EP.audit_session(runs[0]["root"], runs[0]["packet"], runtime(), knowledge())
        check_fixture_budget()

    def test_resigned_actual_bytes_fit_but_worst_response_reserve_must_fail(self):
        run = visual_runs()[0]
        root = run["root"]
        config_path, end_path = root / "CONFIG.json", root / "END.json"
        config = C.decode(config_path.read_bytes()); end = C.decode(end_path.read_bytes())
        requests = [(root / f"turns/{turn:06d}/REQUEST.bin").read_bytes() for turn in range(2)]
        responses = [(root / f"turns/{turn:06d}/RESPONSE.bin").read_bytes() for turn in range(2)]
        actual = sum(map(len, requests + responses))
        reserve = len(requests[0]) + len(responses[0]) + len(requests[1]) + config["budget"]["max_response_bytes"] + 1
        self.assertLess(actual, reserve)
        altered_limit = (actual + reserve) // 2
        config["budget"]["max_request_bytes"] = max(map(len, requests))
        config["budget"]["max_history_bytes"] = max(map(len, requests))
        config["budget"]["max_total_provider_bytes"] = altered_limit
        EP.checked_budget(runtime(), config["budget"])
        config_raw = V.encode(config); config_pin = V.pin(config_raw)
        changes = [(config_path, config_raw)]
        previous = "0" * 64
        for turn in range(2):
            folder = root / "turns" / f"{turn:06d}"
            http = C.decode((folder / "HTTP.json").read_bytes()); http["config_pin"] = config_pin
            event_path = root / "events" / f"{turn:06d}.json"
            event = C.decode(event_path.read_bytes())
            event["config"], event["previous_sha256"] = config_pin, previous
            event_raw = V.encode(event); previous = V.pin(event_raw)["sha256"]
            changes.extend([(folder / "HTTP.json", runtime()["sender"].encode(http)),
                            (folder / "BRIDGE.json", runtime()["sender"].encode(event)),
                            (event_path, event_raw)])
        end["config"] = config_pin; changes.append((end_path, V.encode(end)))
        with ExitStack() as stack:
            for path, raw in changes:
                stack.enter_context(retained_mutation(path, raw))
            with self.assertRaisesRegex(ValueError, "[Rr]eserv"):
                EP.audit_session(root, run["packet"], runtime(), knowledge())
        EP.audit_session(root, run["packet"], runtime(), knowledge())
        check_fixture_budget()


if __name__ == "__main__":
    unittest.main()

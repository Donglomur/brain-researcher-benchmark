"""Additive resource-accounting successor; original scientific protocol unchanged.

NEURAL-095 four-cell producer; trusted transport required, never a sandbox.

No backend is constructed, scientific data read, or model/code executed here.
Candidate execution belongs in an isolated transport implementing Backend.
This source produces complete submission NPZ bytes and gates existing paired
validation/grading. It deliberately does not invoke the historical pair driver,
which would grade the first pair before the other mode has committed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import re
import stat
import struct
import sys
import time
from types import ModuleType
from typing import Protocol
import zipfile


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(body):
    need(type(body) is bytes, "Immutable bytes required")
    return sha256(body).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def hash_id(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def pinned_source(path, size, expected):
    """Bounded no-follow read; execute only the exact source bytes checked."""
    import os
    need(path.resolve() == path.absolute(), "No source-path symlinks")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == size,
             "Pinned ordinary source")
        body = os.read(descriptor, size + 1)
        need(len(body) == size and digest(body) == expected, "Exact dependency source")
        return body
    finally:
        os.close(descriptor)


DEPENDENCY = {
    "path": "neural017-adaptive-protocol-source-20261114-v1/revision-v2/adaptive_protocol.py",
    "bytes": 22776,
    "sha256": "20533b7ceff1adee84ca18dea0547ecdee08c9ca13607e2d6c801cd7108e5be3",
}
_dependency_path = Path(__file__).resolve().parent.parent / DEPENDENCY["path"]
_dependency_body = pinned_source(_dependency_path, DEPENDENCY["bytes"], DEPENDENCY["sha256"])
_dependency = ModuleType("_dmfc095_pinned_n017_budget_types")
sys.modules[_dependency.__name__] = _dependency
exec(compile(_dependency_body, str(_dependency_path), "exec"), _dependency.__dict__)
Usage, Limits = _dependency.Usage, _dependency.Limits

MODES = ("frozen_program", "case_adaptive")
VIEWS = ("cue_only", "neural")
CELLS = tuple((mode, view) for mode in MODES for view in VIEWS)
CASE_COUNT = 258
TRAIN_COUNT = 748
OUTPUT_CAP = 1048576
REFERENCE_NAMES = (
    "nominal_sample_interval", "exact_condition_training_median", "cue_clock_ridge",
    "cue_clock_total_spike_ridge", "cue_clock_temporal_spike_ridge",
)
MANIFEST = {
    "path": "dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json",
    "bytes": 5861,
    "sha256": "5344d316d22875849cf68784b2ace39811c4b560d1e973d09454dd0a99f9595d",
}
ABSENCE = ("producer_absent", "controller_absent", "tools_absent",
           "holder_absent", "volume_absent")


def load_manifest():
    path = Path(__file__).resolve().parent.parent / MANIFEST["path"]
    value = json.loads(pinned_source(path, MANIFEST["bytes"], MANIFEST["sha256"]))
    scope = value["scientific_scope"]
    need(scope["assessment_cases_per_view"] == CASE_COUNT and
         scope["training_trials"] == TRAIN_COUNT and
         scope["references"] == list(REFERENCE_NAMES), "Unchanged complete scientific scope")
    return value


def submission_npz(case_ids, predictions):
    """Deterministic NumPy v1 archives using only stdlib; not scientific IO.

    Existing validator remains authoritative. This encoder permits finite
    negative predictions and emits the unchanged <U11 / <f8 two-vector schema.
    """
    need(type(case_ids) is tuple and len(case_ids) == CASE_COUNT and
         len(set(case_ids)) == CASE_COUNT and all(type(x) is str and 0 < len(x) <= 11
         and "\x00" not in x for x in case_ids), "All 258 unique U11 case IDs")
    need(type(predictions) is tuple and len(predictions) == CASE_COUNT and
         all(type(x) in (int, float) and math.isfinite(x) for x in predictions),
         "All 258 finite real scalar predictions")

    def npy(descriptor, data):
        header = repr({"descr": descriptor, "fortran_order": False,
                       "shape": (CASE_COUNT,)}).encode("ascii")
        padding = (-(10 + len(header) + 1)) % 64
        header += b" " * padding + b"\n"
        return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + data

    ids = b"".join(x.encode("utf-32-le") + b"\0" * (44 - len(x) * 4) for x in case_ids)
    values = struct.pack("<" + "d" * CASE_COUNT, *predictions)
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, body in (("case_id.npy", npy("<U11", ids)),
                           ("prediction_ms.npy", npy("<f8", values))):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            bundle.writestr(info, body)
    body = out.getvalue()
    need(len(body) <= OUTPUT_CAP, "Bounded submission")
    return body


@dataclass(frozen=True)
class Reply:
    payload: object
    usage: Usage
    memory_upper_bound_bytes: int
    controller_sha256: str
    decision_origin: str

    def __post_init__(self):
        need(isinstance(self.usage, Usage), "Typed trusted usage")
        need(type(self.memory_upper_bound_bytes) is int and self.memory_upper_bound_bytes >= 0,
             "Integer memory allocation upper bound")


class Backend(Protocol):
    """Trusted operator implementation only; never exposed to candidate code.

    Receipts must come from the transport, not controller assertions. Calls
    require hard deadline/resource preemption, no network except authenticated
    metered model service for adaptive mode, and per-cell fresh isolation.
    admit/freeze/commit/stop are trusted setup/capture/cleanup only: no candidate,
    model or tool computation may run there. All such work, including failures,
    belongs inside metered operate(prepare/decide/tool/export).
    """
    def admit(self, specification: dict) -> dict:
        """Authenticate source/assets, create fresh cell; expose NO query yet."""
    def freeze(self, specification: dict) -> dict:
        """Durably freeze source/method and fitted training artifacts, no query IO."""
    def operate(self, request: dict, *, reservation: Usage, deadline_us: int,
                memory_bytes: int) -> Reply:
        """prepare=train only; decide/tool=full allowed query context, frozen fits.
        Export stops producer/controller/tools, captures exact NPZ via live
        holder, then removes holder/volume. Return artifact + all-absence receipt.
        Transport must not count a per-case reset or permit query-driven fitting.
        """
    def commit(self, body: bytes, receipt: dict) -> str:
        """Durably commit immutable stopped bytes and exact receipt."""
    def stop(self) -> dict:
        """Attempt every cleanup even on partial failure; prove complete absence."""


class Evaluator(Protocol):
    def seal(self, four_cell_record: dict) -> str:
        """Durably commit exact all-four record before any private operation."""
    def validate_pair(self, *, mode, outputs, joint_sha256, source_manifest) -> dict:
        """Run exact existing pair_worker validate, target/reference mounts absent."""
    def grade_pair(self, *, mode, outputs, joint_sha256, prior_validation,
                   source_manifest, all_four_sha256) -> dict:
        """Run exact existing pair_worker grade with original five references.
        Construct private-bearing worker only here, after both public validations.
        No result is returned to any candidate session.
        """


def stopped(receipt):
    return type(receipt) is dict and all(receipt.get(key) is True for key in ABSENCE)


class Cell:
    """One entire view, one aggregate budget, 258 serial prediction decisions."""
    def __init__(self, *, mode, view, source, method, case_ids, limits, reservations,
                 tool_ids, backend, comparison_id, manifest, clock_us, on_admission):
        self.mode, self.view, self.source, self.method = mode, view, source, method
        self.case_ids, self.limits, self.reservations = case_ids, limits, reservations
        self.tool_ids, self.backend, self.comparison_id = tool_ids, backend, comparison_id
        self.manifest, self.clock = manifest, clock_us
        self.on_admission = on_admission
        self.source_sha, self.method_sha = digest(source), digest(method)
        self.used, self.preparation_used, self.transport_reported = Usage(), Usage(), Usage()
        self.state, self.failure, self.session_id = "new", None, None
        self.started = self.last_clock = None
        self.output = self.commit_record = None
        self.closed, self.cleanup_error = False, None

    def now(self):
        now = self.clock()
        need(type(now) is int and now >= 0 and
             (self.last_clock is None or now >= self.last_clock), "Monotonic integer clock")
        self.last_clock = now
        return now

    def check_clock(self, preparation=False):
        now = self.now()
        need(now - self.started < self.limits.wall_us, "Whole-view wall budget exhausted")
        if preparation:
            need(now - self.started < self.limits.preparation_wall_us,
                 "Preparation wall budget exhausted")
        return now

    def specification(self):
        identity = self.manifest["evaluator_only_assets"]["identity"]
        return json.loads(encode({
            "protocol": "NEURAL-095/four-cell-adaptive/v1", "mode": self.mode,
            "view": self.view, "comparison_id": self.comparison_id,
            "limits_sha256": self.limits.identity(), "source_sha256": self.source_sha,
            "method_sha256": self.method_sha, "source": self.source.decode("utf-8"),
            "method": self.method.decode("utf-8"), "case_count": CASE_COUNT,
            "training_count": TRAIN_COUNT, "case_ids_sha256": digest(encode(self.case_ids)),
            "public_inputs": self.manifest["public_views"][self.view]["public_inputs"],
            "public_identity": identity, "tool_ids": list(self.tool_ids),
            "reservation_policy_sha256": digest(encode({key: asdict(value)
                for key, value in self.reservations.items()})),
            "reset": "fresh_cell_state_retained_within_all_258_cases",
            "query_transduction": "forbidden_training_artifacts_read_only_after_freeze",
        }))

    def request(self, operation, payload=None):
        preparation = self.state == "preparation"
        need(self.state in ("preparation", "query"), "Active public phase")
        need((operation == "prepare") == preparation, "Training-only preparation boundary")
        self.check_clock(preparation)
        reserve = self.reservations[operation]
        next_used = self.used.add(reserve)
        next_preparation = self.preparation_used.add(reserve) if preparation else self.preparation_used
        need(next_used.within(self.limits.total) and
             next_preparation.within(self.limits.preparation), "Aggregate budget exhausted")
        # Reservation is charged before dispatch and retained on missing receipts.
        self.used, self.preparation_used = next_used, next_preparation
        deadline = self.started + (self.limits.preparation_wall_us if preparation
                                   else self.limits.wall_us)
        reply = self.backend.operate({"operation": operation, "payload": payload},
            reservation=reserve, deadline_us=deadline, memory_bytes=self.limits.max_memory_bytes)
        need(isinstance(reply, Reply), "Trusted complete upper-bound receipt required")
        self.transport_reported = self.transport_reported.add(reply.usage)
        excess = Usage(**{key: max(0, getattr(reply.usage, key) - value)
                         for key, value in asdict(reserve).items()})
        self.used = self.used.add(excess)
        if preparation:
            self.preparation_used = self.preparation_used.add(excess)
        need(reply.usage.within(reserve), "Metered resource overrun retained and rejected")
        need(reply.memory_upper_bound_bytes <= self.limits.max_memory_bytes, "Memory limit exceeded")
        need(reply.controller_sha256 == self.source_sha, "Execution source origin mismatch")
        expected_origin = "preparation" if preparation else self.mode
        need(reply.decision_origin == expected_origin, "Execution mode origin mismatch")
        if self.mode == "frozen_program":
            need(reply.usage.model_input_tokens == reply.usage.model_output_tokens ==
                 reply.usage.model_cost_microusd == 0, "Frozen program cannot invoke a model")
        self.check_clock(preparation)
        if operation != "export":
            need(len(encode(reply.payload)) <= self.limits.response_bytes, "Bounded reply")
        return reply.payload

    def run(self):
        need(self.state == "new" and not self.closed, "Cell is single-use")
        self.started = self.now()  # Explicit admission, not object construction.
        self.state = "preparation"
        try:
            spec = self.specification()
            admission = self.backend.admit(json.loads(encode(spec)))
            need(type(admission) is dict and admission.get("specification_sha256") == digest(encode(spec))
                 and admission.get("fresh_state") is True and admission.get("query_released") is False
                 and admission.get("method_wire_validated") is True
                 and admission.get("tool_manifest_matched") is True
                 and admission.get("public_assets_verified") is True
                 and type(admission.get("session_id")) is str and 0 < len(admission["session_id"]) <= 128,
                 "Authenticated fresh cell admission without query")
            self.session_id = admission["session_id"]
            self.on_admission(self.session_id)
            self.check_clock(True)
            preparation = self.request("prepare")
            need(type(preparation) is dict and set(preparation) == {"training_artifacts_sha256"}
                 and hash_id(preparation["training_artifacts_sha256"]), "Bound training artifacts")
            freeze_spec = {"specification_sha256": digest(encode(spec)), **preparation,
                           "source_sha256": self.source_sha, "method_sha256": self.method_sha}
            frozen = self.backend.freeze(json.loads(encode(freeze_spec)))
            self.check_clock(True)
            need(frozen == {"freeze_sha256": digest(encode(freeze_spec)), "query_released": False},
                 "Durable freeze before query release")
            self.state = "query"
            predictions = []
            for case_id in self.case_ids:
                while True:
                    action = self.request("decide", {"case_id": case_id,
                        "completed_cases": len(predictions), "full_query_batch_visible": True})
                    need(type(action) is dict, "Typed decision")
                    if action.get("action") == "predict":
                        need(set(action) == {"action", "case_id", "prediction_ms"}
                             and action["case_id"] == case_id, "One prediction for current case")
                        value = action["prediction_ms"]
                        need(type(value) in (int, float) and math.isfinite(value), "Finite scalar prediction")
                        predictions.append(float(value))
                        break
                    need(set(action) == {"action", "tool_id", "arguments"} and action["action"] == "tool"
                         and action["tool_id"] in self.tool_ids and type(action["arguments"]) is dict,
                         "Only allowlisted public frozen-fit tools")
                    # Backend returns this observation to its isolated controller;
                    # there is no host-path, evaluator, fit, or private-grade opcode.
                    self.request("tool", {"case_id": case_id, **action})
            body = submission_npz(self.case_ids, tuple(predictions))
            exported = self.request("export", {"submission": body})
            need(type(exported) is dict and set(exported) == {"submission", "absence"}
                 and exported["submission"] == body and stopped(exported["absence"]),
                 "Exact live-holder capture followed by complete removal required")
            self.state = "stopped"
            record = {"mode": self.mode, "view": self.view, "session_id": self.session_id,
                "submission": {"bytes": len(body), "sha256": digest(body)},
                "source_sha256": self.source_sha, "method_sha256": self.method_sha,
                "freeze_sha256": frozen["freeze_sha256"], "limits_sha256": self.limits.identity(),
                "charged_upper_bound_usage": asdict(self.used), "transport_reported_usage": asdict(self.transport_reported),
                "cpu_usage_kind": "conservative_numeric80_plus_actor8_wall_upperbounds",
                "memory_usage_kind": "configuredallocationupperbound_notobservedpeak",
                "preparation_charged_upper_bound_usage": asdict(self.preparation_used),
                "absence": json.loads(encode(exported["absence"])), "case_count": CASE_COUNT}
            need(self.backend.commit(body, json.loads(encode(record))) == digest(encode(record)),
                 "Durable cell commitment")
            self.output, self.commit_record = body, record
            self.state = "committed"
            return body, record
        except Exception as error:
            self.failure = type(error).__name__ + ": " + str(error)
            self.state = "failed"
            raise
        finally:
            self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True  # Even failed cleanup is terminal; never reset/retry a cell.
        try:
            need(stopped(self.backend.stop()), "Cleanup did not prove complete absence")
        except Exception as error:
            self.cleanup_error = type(error).__name__ + ": " + str(error)
            self.state = "failed"
            raise


class Study:
    """All four cells commit and stop, both pairs validate, then private grading.

    Sources/methods are precommitted per mode and identical across its views.
    This checks identity, not scientific matched-method review. No candidate can
    access this object, evaluator, private assets, or another cell's observations.
    """
    def __init__(self, *, sources, methods, case_ids, limits, reservations, tool_ids,
                 backend_factory, evaluator, comparison_id, clock_us=None):
        need(type(sources) is dict and set(sources) == set(MODES) and type(methods) is dict
             and set(methods) == set(MODES), "Exactly two source/method commitments")
        for mode in MODES:
            need(type(sources[mode]) is bytes and 0 < len(sources[mode]) <= 65536,
                 "Bounded committed UTF-8 program/policy")
            sources[mode].decode("utf-8")
            need(type(methods[mode]) is bytes and 0 < len(methods[mode]) <= 32768,
                 "Bounded committed method document")
            methods[mode].decode("utf-8")
        # Validate public IDs without reading authentic data or importing numpy.
        submission_npz(case_ids, (0.0,) * CASE_COUNT)
        need(isinstance(limits, Limits), "Explicit matched aggregate Limits")
        need(type(reservations) is dict and set(reservations) == {"prepare", "decide", "tool", "export"}
             and all(isinstance(x, Usage) and x.calls >= 1 and x.within(limits.total)
                     for x in reservations.values()), "Common positive per-operation reservations")
        need(reservations["prepare"].within(limits.preparation), "Preparation reservation inside total")
        need(type(tool_ids) is tuple and len(tool_ids) == len(set(tool_ids)) and
             all(type(x) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,63}@[0-9a-f]{64}", x)
                 for x in tool_ids), "Exact immutable reviewed tool identities")
        need(type(comparison_id) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", comparison_id),
             "Bounded comparison identifier")
        self.manifest = load_manifest()
        self.sources, self.methods = dict(sources), dict(methods)
        self.case_ids, self.limits = case_ids, limits
        self.reservations, self.tool_ids = dict(reservations), tool_ids
        self.factory, self.evaluator, self.comparison_id = backend_factory, evaluator, comparison_id
        self.clock = clock_us or (lambda: time.monotonic_ns() // 1000)
        self.state, self.cells, self.outputs, self.records = "new", {}, {}, {}
        self.validations, self.grades = {}, {}
        self.four_sha = None

    def run(self):
        need(self.state == "new", "Study is single-use, including failed grading")
        self.state = "producing"
        seen_backends, seen_sessions = [], set()
        def on_admission(session_id):
            need(session_id not in seen_sessions, "Fresh nonreused isolated session identity")
            seen_sessions.add(session_id)
        try:
            for mode, view in CELLS:
                backend = self.factory(mode, view)
                need(all(backend is not prior for prior in seen_backends), "Fresh backend per cell")
                seen_backends.append(backend)
                cell = Cell(mode=mode, view=view, source=self.sources[mode], method=self.methods[mode],
                    case_ids=self.case_ids, limits=self.limits, reservations=self.reservations,
                    tool_ids=self.tool_ids, backend=backend, comparison_id=self.comparison_id,
                    manifest=self.manifest, clock_us=self.clock, on_admission=on_admission)
                self.cells[(mode, view)] = cell
                output, record = cell.run()
                self.outputs[(mode, view)], self.records[(mode, view)] = output, record
            four = {"protocol": "NEURAL-095/four-cell-adaptive/v1", "comparison_id": self.comparison_id,
                "case_count_per_cell": CASE_COUNT, "limits_sha256": self.limits.identity(),
                "delivery_manifest_sha256": MANIFEST["sha256"],
                "cells": [self.records[key] for key in CELLS],
                "reference_names": list(REFERENCE_NAMES), "private_grades_so_far": 0}
            need(self.evaluator.seal(json.loads(encode(four))) == digest(encode(four)),
                 "Durable all-four commitment barrier")
            self.four_sha, self.state = digest(encode(four)), "validating"
            joints = {}
            for mode in MODES:
                outputs = {view: self.outputs[(mode, view)] for view in VIEWS}
                pins = {view: {"bytes": len(body), "sha256": digest(body)} for view, body in outputs.items()}
                joint = digest(encode({"all_four_sha256": self.four_sha, "mode": mode, "submissions": pins}))
                result = self.evaluator.validate_pair(mode=mode, outputs=outputs,
                    joint_sha256=joint, source_manifest=json.loads(encode(self.manifest)))
                need(type(result) is dict and result.get("status") == "valid_complete_pair"
                     and result.get("submissions") == pins and result.get("joint_commit_sha256") == joint
                     and result.get("identity") == self.manifest["evaluator_only_assets"]["identity"]
                     and result.get("private_target_reads") == 0 and result.get("private_target_decodes") == 0
                     and result.get("private_reference_reads") == 0,
                     "Existing target-free complete-pair validation required")
                self.validations[mode], joints[mode] = json.loads(encode(result)), joint
            self.state = "grading"
            for mode in MODES:
                result = self.evaluator.grade_pair(mode=mode,
                    outputs={view: self.outputs[(mode, view)] for view in VIEWS},
                    joint_sha256=joints[mode], prior_validation=json.loads(encode(self.validations[mode])),
                    source_manifest=json.loads(encode(self.manifest)), all_four_sha256=self.four_sha)
                expected_pins = {view: {"bytes": len(self.outputs[(mode, view)]),
                    "sha256": digest(self.outputs[(mode, view)])} for view in VIEWS}
                need(type(result) is dict and result.get("status") == "paired_predictions_scored"
                     and result.get("joint_commit_sha256") == joints[mode]
                     and result.get("submissions") == expected_pins
                     and result.get("identity") == self.manifest["evaluator_only_assets"]["identity"]
                     and result.get("private_target_reads") == 1 and result.get("private_target_decodes") == 1
                     and result.get("private_reference_reads") == 3 and result.get("new_fits_in_trusted_grader") == 0
                     and result.get("logical_metric_calls") == 2,
                     "Existing unchanged paired grade required")
                self.grades[mode] = json.loads(encode(result))
            self.state = "complete"
            return {"status": "four_cell_outputs_scored", "all_four_sha256": self.four_sha,
                    "grades": self.grades, "operational_qualification_claimed": False}
        except Exception:
            self.state = "failed"
            raise

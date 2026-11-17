"""Trusted protocol state machine, not an execution sandbox or cost allocation.

The backend belongs to the operator and must isolate candidate code. It supplies
metered PUBLIC operations and the unchanged NEURAL-017 validator/grader. No
backend is constructed here. This module has no network, subprocess or array IO.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
import time
from typing import Protocol

FULL_SHAPE = (574, 140, 45)
TRAIN_SHAPE = (1721, 140, 137)
PUBLIC_FIELDS = (
    "train_counts_heldin", "train_counts_heldout", "eval_counts_heldin",
    "train_trial_ids", "eval_trial_ids", "heldin_unit_ids", "heldout_unit_ids",
    "train_condition_ids", "eval_condition_ids", "bin_left_edges_ms",
    "eval_valid_mask", "source_manifest_sha256", "panel_fingerprint",
)
TRAIN_FIELDS = (
    "train_counts_heldin", "train_counts_heldout", "train_trial_ids",
    "heldin_unit_ids", "heldout_unit_ids", "train_condition_ids",
    "bin_left_edges_ms", "source_manifest_sha256",
)
SCORING_FIELDS = (
    "expected_counts", "trial_ids", "heldout_unit_ids", "bin_left_edges_ms",
    "prediction_units", "panel_fingerprint",
)
SUBMISSION_CAP = 33554432
SOURCE_CAP = 65536
METRIC = "pooled_poisson_co_smoothing_bits_per_spike"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    require(isinstance(value, bytes), "Immutable bytes required")
    return sha256(value).hexdigest()


def hash_id(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def json_copy(value):
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def integer(value):
    return type(value) is int and value >= 0


@dataclass(frozen=True)
class Usage:
    """Trusted usage in integers; no binary-float money/time accumulation."""
    calls: int = 0
    cpu_us: int = 0
    model_input_tokens: int = 0
    model_output_tokens: int = 0
    model_cost_microusd: int = 0

    def __post_init__(self):
        require(all(integer(v) for v in asdict(self).values()), "Nonnegative integer usage")

    def add(self, other):
        return Usage(**{k: v + getattr(other, k) for k, v in asdict(self).items()})

    def within(self, limit):
        return all(v <= getattr(limit, k) for k, v in asdict(self).items())

    def maximum(self, other):
        return Usage(**{k: max(v, getattr(other, k)) for k, v in asdict(self).items()})


@dataclass(frozen=True)
class Limits:
    """Paired limits frozen before preparation; none constitutes a grant."""
    total: Usage
    preparation: Usage
    wall_us: int
    preparation_wall_us: int
    max_memory_bytes: int
    response_bytes: int = 262144

    def __post_init__(self):
        require(isinstance(self.total, Usage) and isinstance(self.preparation, Usage),
                "Typed usage ceilings")
        require(self.preparation.within(self.total), "Preparation is inside total")
        for value in (self.wall_us, self.preparation_wall_us,
                      self.max_memory_bytes, self.response_bytes):
            require(type(value) is int and value > 0, "Positive integer limit")
        require(self.preparation_wall_us <= self.wall_us, "Preparation wall inside total")
        require(self.response_bytes <= 1048576, "Bounded public response")

    def identity(self):
        return digest(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode())


@dataclass(frozen=True)
class Reply:
    """Only a trusted metering transport may construct these usage reports."""
    payload: object
    usage: Usage
    peak_memory_bytes: int
    controller_sha256: str | None = None
    decision_origin: str = "preparation"

    def __post_init__(self):
        require(isinstance(self.usage, Usage), "Typed backend usage")
        require(integer(self.peak_memory_bytes), "Nonnegative measured peak memory")


class Backend(Protocol):
    def public(self, request: dict, *, reservation: Usage, deadline_us: int,
               memory_bytes: int, mode: str, controller_sha256: str | None) -> Reply:
        """Isolated public operation. Stop at reservation/deadline/resource caps."""
    def freeze_controller(self, source: bytes, mode: str) -> str:
        """Durably capture controller/policy bytes before any query release."""
    def stop(self) -> dict:
        """Recovery/close: reap every candidate resource and prove absence."""
    def finalize(self) -> tuple[bytes, dict]:
        """Stop producer/tools/controller; capture through live trusted holder;
        then remove holder/volume and return immutable bytes plus final absence.
        On exception, caller still invokes stop() in finally.
        """
    def commit(self, submission: bytes, receipt: dict) -> str:
        """Durably persist exact stopped bytes and receipt; return matching SHA256."""
    def validate(self, submission: bytes) -> dict:
        """Invoke unchanged public-only full-panel validator; no targets/comparator."""
    def grade(self, submission: bytes) -> dict:
        """Existing isolated scorer; no candidate/controller can receive its result."""


class Session:
    """One session, all 574 trials, one total budget, exactly one private grade.

    This object remains operator-only. A candidate sends JSON requests through a
    trusted transport; never give it this object, backend, operator filesystem or
    Python process. Every view/tool/model operation goes through public().
    """

    def __init__(self, *, mode, limits, tool_ids, backend, comparison_id,
                 public_packet_sha256, reservation_policy_sha256, trial_ids, clock_us=None):
        require(mode in ("frozen_program", "case_adaptive"), "Known mode")
        require(isinstance(limits, Limits), "Explicit common paired limits")
        require(isinstance(tool_ids, tuple) and tool_ids and
                len(set(tool_ids)) == len(tool_ids) and
                all(isinstance(x, str) and 0 < len(x) <= 128 for x in tool_ids),
                "Exact immutable tool/checkpoint identities")
        require(hash_id(public_packet_sha256), "Bound public packet")
        require(hash_id(reservation_policy_sha256), "Bound common reservation policy")
        require(isinstance(comparison_id, str) and 0 < len(comparison_id) <= 128,
                "Bound comparison ID")
        require(isinstance(trial_ids, tuple) and len(trial_ids) == 574 and
                len(set(trial_ids)) == 574 and
                all(isinstance(x, str) and 0 < len(x) <= 256 for x in trial_ids),
                "All 574 public trial identities; no subset profile")
        self.mode, self.limits, self.backend = mode, limits, backend
        self.tool_ids, self.trial_ids = tool_ids, trial_ids
        self.comparison_id, self.packet_sha = comparison_id, public_packet_sha256
        self.reservation_policy_sha = reservation_policy_sha256
        self.clock = clock_us or (lambda: time.monotonic_ns() // 1000)
        self.started = self.clock()
        require(integer(self.started), "Integer monotonic clock")
        self.last_clock = self.started
        self.state, self.used, self.preparation_used = "preparation", Usage(), Usage()
        self.events, self.controller_sha, self.submission = [], None, None
        self.commit_receipt, self.grade_result = None, None
        self.failure = None
        self.terminal_outcome = None
        self._paired_token = None
        self._event("start", common=self.common_identity())

    def common_identity(self):
        """Compare this exactly across paired modes, excluding the mode itself."""
        return {
            "protocol": "NEURAL-017/session-interaction/v1",
            "comparison_id": self.comparison_id, "limits_sha256": self.limits.identity(),
            "public_packet_sha256": self.packet_sha, "tools": list(self.tool_ids),
            "reservation_policy_sha256": self.reservation_policy_sha,
            "shape": list(FULL_SHAPE), "biological_cases": 1,
            "public_fields": list(PUBLIC_FIELDS),
        }

    def _event(self, event, **values):
        self.events.append(json_copy(dict(event=event, **values)))

    def _now(self):
        now = self.clock()
        require(integer(now) and now >= self.last_clock, "Monotonic clock")
        self.last_clock = now
        return now

    def _clock_check(self):
        now = self._now()
        if now - self.started >= self.limits.wall_us:
            self._fail("total_wall_budget_exhausted")
        if self.state == "preparation" and now - self.started >= self.limits.preparation_wall_us:
            self._fail("preparation_wall_budget_exhausted")
        return now

    def _fail(self, reason):
        self.failure = reason
        self.state = "failed"
        self._event("failed", reason=reason, usage=asdict(self.used))
        raise ValueError(reason)

    def freeze_controller(self, source):
        """Commit fixed source or adaptive policy before any query access."""
        require(self.state == "preparation", "Freeze once before opening case")
        self._clock_check()
        require(isinstance(source, bytes) and 0 < len(source) <= SOURCE_CAP,
                "Bounded controller/policy source")
        self.state = "freezing"  # No reentrant query during durable source capture.
        try:
            expected = digest(source)
            require(self.backend.freeze_controller(source, self.mode) == expected,
                    "Exact durable controller-source commitment")
            now = self._now()
            require(now - self.started < self.limits.preparation_wall_us and
                    now - self.started < self.limits.wall_us,
                    "Controller commitment within preparation/total wall limits")
            self.controller_sha = expected
            self.state = "case"
            self._event("controller_frozen", sha256=self.controller_sha,
                        mode=self.mode, before_query_release=True, durable=True)
            return self.controller_sha
        except BaseException as exc:
            self.state, self.failure = "failed", "controller_commit_failed"
            self._event("controller_commit_failed", exception_type=type(exc).__name__)
            raise

    def request(self, request, reservation):
        """Only public train/view/tool operations. No grading or arbitrary paths."""
        require(self.state in ("preparation", "case"), "Public access phase closed")
        self._clock_check()
        require(isinstance(request, dict), "JSON object request")
        require(len(json.dumps(request, allow_nan=False).encode()) <= SOURCE_CAP,
                "Bounded public request including source/arguments")
        request = json_copy(request)
        operation = request.get("op")
        if operation == "view":
            require(set(request) <= {"op", "scope", "trial_id"}, "Exact view request")
            scope = request.get("scope")
            require(scope in ("training", "panel", "trial"), "Known public scope")
            if scope != "training":
                require(self.state == "case", "Freeze controller before query view")
            if scope == "trial":
                require(request.get("trial_id") in self.trial_ids, "Public trial ID")
            else:
                require("trial_id" not in request, "No trial ID for whole view")
            fields = TRAIN_FIELDS if scope == "training" else PUBLIC_FIELDS
            request["allowed_fields"] = list(fields)
            # Full-panel/transductive observed-input access is identical in both modes.
        elif operation == "tool":
            require(set(request) == {"op", "tool_id", "arguments"}, "Exact tool request")
            require(request["tool_id"] in self.tool_ids, "Frozen permitted tool")
            require(isinstance(request["arguments"], dict), "Tool arguments object")
            request["allowed_fields"] = list(TRAIN_FIELDS if self.state == "preparation"
                                             else PUBLIC_FIELDS)
        else:
            raise ValueError("Only public view/tool requests; private scores unavailable")
        require(isinstance(reservation, Usage) and reservation.calls == 1,
                "Reserve one attempted call plus worst-case trusted work")
        require(self.used.add(reservation).within(self.limits.total), "Total budget exhausted")
        preparing = self.state == "preparation"
        if preparing:
            require(self.preparation_used.add(reservation).within(self.limits.preparation),
                    "Preparation budget exhausted")
        # Charge before dispatch. Missing/failed receipts keep the full reservation.
        self.used = self.used.add(reservation)
        if preparing:
            self.preparation_used = self.preparation_used.add(reservation)
        deadline = self.started + (self.limits.preparation_wall_us if preparing
                                   else self.limits.wall_us)
        self._event("public_dispatch", operation=request["op"],
                    scope=request.get("scope"), tool_id=request.get("tool_id"),
                    reservation=asdict(reservation), phase=self.state)
        try:
            reply = self.backend.public(
                request, reservation=reservation, deadline_us=deadline,
                memory_bytes=self.limits.max_memory_bytes, mode=self.mode,
                controller_sha256=self.controller_sha)
            require(isinstance(reply, Reply), "Trusted typed tool receipt required")
            # Conservative reservation charging is identical for both arms. Actual
            # overrun is additionally charged, then fails the whole attempt.
            extra = Usage(**{k: max(0, v - getattr(reservation, k))
                             for k, v in asdict(reply.usage).items()})
            self.used = self.used.add(extra)
            if preparing:
                self.preparation_used = self.preparation_used.add(extra)
            require(reply.usage.calls == 1, "Attempted call must be charged")
            if not reply.usage.within(reservation):
                self._fail("trusted_tool_exceeded_reservation")
            if reply.peak_memory_bytes > self.limits.max_memory_bytes:
                self._fail("trusted_tool_exceeded_memory")
            origin = ("preparation" if preparing else
                      "committed_program" if self.mode == "frozen_program" else
                      "adaptive_policy")
            require(reply.controller_sha256 == self.controller_sha and
                    reply.decision_origin == origin,
                    "Trusted transport must bind actual controller and decision origin")
            self._clock_check()
            serialized = json.dumps(reply.payload, allow_nan=False,
                                    separators=(",", ":")).encode()
            require(len(serialized) <= self.limits.response_bytes, "Public response cap")
            self._event("public_completed", actual=asdict(reply.usage),
                        charged=asdict(reservation), peak_memory_bytes=reply.peak_memory_bytes,
                        response_sha256=digest(serialized))
            return json.loads(serialized)
        except BaseException as exc:
            if self.state != "failed":
                self.state, self.failure = "failed", "public_operation_failed"
                self._event("public_failed", exception_type=type(exc).__name__,
                            full_reservation_retained=asdict(reservation))
            raise

    def finish(self):
        """Close public transport; producer stop → live-holder capture →
        complete resource removal → durable commit → public validation.

        The operator calls this after candidate completion. Missing output,
        incomplete output or invalid numbers never produce a private grade.
        Backend resources must also be stopped after every exception by close().
        """
        require(self.state == "case", "One complete open case required")
        self._clock_check()
        self.state = "closing"  # Public requests permanently disabled first.
        try:
            submission, absent = self.backend.finalize()
            require(isinstance(absent, dict) and
                    set(absent) == {"controller", "tools", "producer", "holder", "volume"} and
                    all(v is True for v in absent.values()), "All candidate resources absent")
            self._event("all_candidate_resources_absent")
            require(isinstance(submission, bytes) and 0 < len(submission) <= SUBMISSION_CAP,
                    "Single bounded immutable predictions.npz")
            receipt = {
                "submission_sha256": digest(submission), "submission_bytes": len(submission),
                "controller_sha256": self.controller_sha, "mode": self.mode,
                "common": self.common_identity(), "usage": asdict(self.used),
                "preparation_usage": asdict(self.preparation_used),
                "all_candidate_resources_absent": True,
                "committed_before_private_grade": True,
                "prediction_contract_valid": None,
                "full_shape_required": list(FULL_SHAPE),
                "candidate_elapsed_us": self._now() - self.started,
            }
            require(self.backend.commit(submission, json_copy(receipt)) ==
                    receipt["submission_sha256"], "Durable exact output commitment")
            self.submission, self.commit_receipt = submission, json_copy(receipt)
            self.state = "committed"
            self._event("full_submission_committed", **receipt)
            valid = self.backend.validate(submission)
            require(isinstance(valid, dict) and
                    valid.get("status") == "valid_prediction_contract" and
                    valid.get("prediction_contract_valid") is True and
                    valid.get("scientific_score_computed") is False and
                    valid.get("submission_sha256") == receipt["submission_sha256"],
                    "Existing public-only full-panel validation must succeed")
            self.state = "validated"
            self._event("existing_full_panel_public_validator_passed")
            return json_copy(receipt)
        except BaseException as exc:
            self.state, self.failure = "failed", "finish_failed"
            self._event("finish_failed", exception_type=type(exc).__name__)
            raise

    def private_grade(self, paired_token=None):
        """Operator-only one-shot call, never a candidate request operation."""
        require(paired_token is not None and paired_token is self._paired_token,
                "Both paired arms must commit before either private grade")
        require(self.state == "validated", "Full committed validation precedes private grade")
        self.state = "grading"  # Mark before call: no retries after exception.
        self._event("private_grade_requested")
        try:
            result = self.backend.grade(self.submission)
            require(isinstance(result, dict) and result.get("status") == "scored" and
                    result.get("submission_sha256") == self.commit_receipt["submission_sha256"],
                    "Existing isolated grader must bind this submission")
            self.grade_result, self.state = json_copy(result), "graded"
            self._event("private_grade_completed")
            return json_copy(result)
        except BaseException as exc:
            self.state, self.failure = "failed", "private_grade_failed"
            self._event("private_grade_failed", exception_type=type(exc).__name__)
            raise

    def close(self):
        """Always call in finally; failure never grants an automatic retry."""
        if self.state != "closed":
            self.terminal_outcome = self.state
        self.state = "closed"  # Terminal even if stop fails or calls back into us.
        absence = self.backend.stop()
        require(isinstance(absence, dict) and
                set(absence) == {"controller", "tools", "producer", "holder", "volume"} and
                all(v is True for v in absence.values()), "Cleanup absence unverified")
        self._event("final_cleanup_verified")
        return json_copy(absence)

    def report(self):
        """Operator evidence, never candidate input; no inferred operational grant."""
        return json_copy({
            "status": self.state, "terminal_outcome": self.terminal_outcome,
            "mode": self.mode, "failure": self.failure,
            "common": self.common_identity(), "usage": asdict(self.used),
            "preparation_usage": asdict(self.preparation_used), "events": self.events,
            "root_external_witness": None, "root_current_tip_adoption": None,
            "execution_authority": False, "operational_backend_qualified": False,
        })


class PairedStudy:
    """Join both complete commitments before releasing any private score.

    Trusted transports, common profile and immutable source must already be
    independently reviewed. This join supplies no cost or execution authority.
    """

    def __init__(self, fixed, adaptive):
        require(isinstance(fixed, Session) and isinstance(adaptive, Session),
                "Two trusted sessions")
        require(fixed.mode == "frozen_program" and adaptive.mode == "case_adaptive",
                "One arm of each mode")
        require(fixed is not adaptive and fixed.backend is not adaptive.backend,
                "Isolated per-arm state and backend")
        require(fixed.state == adaptive.state == "preparation", "Join before preparation")
        require(fixed.common_identity() == adaptive.common_identity() and
                fixed.trial_ids == adaptive.trial_ids, "Identical panel/tools/budgets")
        self.fixed, self.adaptive, self.state = fixed, adaptive, "preparation"

    def grade(self):
        require(self.state == "preparation", "Exactly one paired scoring request")
        require(self.fixed.state == self.adaptive.state == "validated",
                "Both full outputs committed and validated before either private grade")
        token = object()
        self.fixed._paired_token = self.adaptive._paired_token = token
        self.state = "grading"
        try:
            left = self.fixed.private_grade(token)
            right = self.adaptive.private_grade(token)
            self.state = "graded"
            return {"fixed": left, "adaptive": right,
                    "same_panel_tools_and_caps": True,
                    "biological_cases": 1, "independent_biological_replicates": 0}
        except BaseException:
            self.state = "failed"
            raise


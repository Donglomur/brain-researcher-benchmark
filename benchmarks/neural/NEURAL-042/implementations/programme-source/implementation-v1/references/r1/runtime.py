"""Independent R1 custody-free numeric support; imports perform no numeric work."""
import contextlib
import hashlib
import importlib.metadata
import json
import math
import re
import time

REFERENCE = "R1"
METRICS = ("corrected_mi", "mi", "trial_null", "shift_null", "early_mi", "late_mi",
           "theta_power", "gamma_power", "firing_rate", "harmonic_plv", "waveform_asymmetry")
DESIGNS = ("count_only", "nuisance_matched")
CONTRASTS = ("load3_minus_load1_correct", "correct_minus_incorrect_within_load")
PAIRS = tuple((f, g) for f in (4, 6) for g in range(70, 141, 5))
ID = re.compile(r"[0-9a-f]{24}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class ReferenceFailure(RuntimeError):
    def __init__(self, reason, record=None):
        super().__init__(reason)
        self.record = {"reason": reason, **(record or {})}


def require(ok, reason):
    if not ok:
        raise ReferenceFailure(reason)


def number(x):
    if type(x) not in (int, float):
        return False
    try:
        return math.isfinite(x)
    except OverflowError:
        return False


def extent(x, *, positive=False):
    return type(x) is int and (1 if positive else 0) <= x <= 2**63 - 1


class Budget:
    """Prospective logical reservations, never a physical RSS/CPU certificate."""
    KINDS = ("elements", "work_units", "serialized_bytes", "events")

    def __init__(self, origin, deadline, limits, *, clock=time.monotonic):
        require(number(origin) and number(deadline) and deadline > origin, "original_clock")
        require(type(limits) is dict and set(limits) == {*self.KINDS, "live_bytes"}, "budget_keys")
        require(all(extent(v, positive=True) for v in limits.values()), "positive_int64_limits")
        self.origin, self.deadline, self.clock = float(origin), float(deadline), clock
        self.limits, self.used = dict(limits), {k: 0 for k in self.KINDS}
        self.live = self.peak = 0
        self.failures = []
        self.tick()

    def fail(self, reason, **detail):
        self.failures.append({"reason": reason, **detail})
        raise ReferenceFailure(reason, {"budget": self.snapshot()})

    def tick(self):
        if self.failures:
            raise ReferenceFailure("budget_already_failed", {"budget": self.snapshot()})
        now = self.clock()
        if not number(now) or not self.origin <= now <= self.deadline:
            self.fail("original_deadline_or_clock", observed=now if number(now) else None)
        return float(now)

    def reserve(self, kind, units):
        self.tick()
        if kind not in self.used or type(units) is not int or units < 0:
            self.fail("invalid_reservation")
        if self.used[kind] + units > self.limits[kind]:
            self.fail("reservation_exceeds_limit", kind=kind, requested=units)
        self.used[kind] += units

    @contextlib.contextmanager
    def hold(self, extent):
        self.tick()
        if type(extent) is not int or extent < 0:
            self.fail("invalid_live_reservation")
        if self.live + extent > self.limits["live_bytes"]:
            self.fail("declared_live_limit", requested=extent)
        self.live += extent
        self.peak = max(self.peak, self.live)
        try:
            yield
        finally:
            self.live -= extent

    def snapshot(self):
        # No final clock call here: failure reporting must not erase a primary error.
        return {"origin": self.origin, "deadline": self.deadline, "limits": dict(self.limits),
                "reserved": dict(self.used), "planned_live_current": self.live,
                "planned_live_peak": self.peak, "failures": list(self.failures),
                "physical_RSS_or_CPU_measured": False}


def libraries():
    """Production has no relaxed version route or dependency installation."""
    try:
        versions = {k: importlib.metadata.version(k) for k in ("numpy", "scipy")}
    except importlib.metadata.PackageNotFoundError as exc:
        raise ReferenceFailure("qualified_numerical_dependency_missing") from exc
    require(versions == {"numpy": "2.2.6", "scipy": "1.15.3"}, "qualified_numerical_versions_required")
    import numpy as np
    from scipy import signal
    from scipy.optimize import linear_sum_assignment
    return np, signal, linear_sum_assignment


def seed(identity):
    require(type(identity) is str, "rng_identity")
    return int.from_bytes(hashlib.sha256(("neural042-v1:" + identity).encode("utf-8")).digest()[:8], "big")


def typed_pin(pin):
    return (type(pin) is dict and set(pin) == {"bytes", "sha256"}
            and extent(pin["bytes"])
            and type(pin["sha256"]) is str and HEX.fullmatch(pin["sha256"]) is not None)


def validate_lineage(lineage):
    require(type(lineage) is dict and set(lineage) ==
            {"packet", "source", "environment", "reference_source", "protocol"}, "lineage_keys")
    require(all(typed_pin(v) for v in lineage.values()), "typed_lineage_pins")


def validate_snapshot(value):
    require(type(value) is dict and set(value) == {
        "origin", "deadline", "limits", "reserved", "planned_live_current", "planned_live_peak",
        "failures", "physical_RSS_or_CPU_measured"}, "final_person_budget_keys")
    require(number(value["origin"]) and number(value["deadline"])
            and value["deadline"] > value["origin"], "final_person_original_clock")
    limits, reserved = value["limits"], value["reserved"]
    require(type(limits) is dict and set(limits) == {*Budget.KINDS, "live_bytes"}
            and all(extent(v, positive=True) for v in limits.values()), "final_person_budget_limits")
    require(type(reserved) is dict and set(reserved) == set(Budget.KINDS)
            and all(extent(v) and v <= limits[k] for k, v in reserved.items()), "final_person_budget_reservations")
    current, peak = value["planned_live_current"], value["planned_live_peak"]
    require(extent(current) and extent(peak) and current <= peak <= limits["live_bytes"]
            and value["failures"] == [] and type(value["failures"]) is list
            and value["physical_RSS_or_CPU_measured"] is False, "successful_person_budget_snapshot")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def slot(budget, capacity):
    """Call before constructing the payload; encoding and copied envelope share this cap."""
    budget.reserve("events", 1)
    budget.reserve("serialized_bytes", capacity)
    return capacity


def event(kind, payload, world, person, lineage, budget, capacity):
    budget.tick()
    with budget.hold(capacity * 3):
        result = {"schema": "neural042_reference_event_v1", "reference": REFERENCE,
                  "world": world, "person": person, "kind": kind, "payload": payload,
                  "lineage": dict(lineage), "budget": budget.snapshot()}
        raw = canonical(result)
        require(len(raw) <= capacity, "event_exceeded_reserved_encoding")
        budget.tick()
        return result


def failure_context(error, budget, phase, progress):
    snapshot = budget.snapshot() if isinstance(budget, Budget) else None
    if isinstance(error, ReferenceFailure):
        error.record.setdefault("phase", phase)
        error.record.setdefault("progress", progress)
        error.record.setdefault("budget", snapshot)
        return error
    return ReferenceFailure("unexpected_reference_failure", {"phase": phase, "progress": progress,
                            "error_type": type(error).__name__, "budget": snapshot})

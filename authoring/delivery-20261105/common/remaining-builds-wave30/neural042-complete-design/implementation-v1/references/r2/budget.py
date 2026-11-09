"""Cooperative, prospective logical budgets; not a physical process monitor."""
import math
import time
from contextlib import contextmanager

KINDS = ("elements", "work_units", "serialized_bytes", "events")
LIMITS = frozenset((*KINDS, "live_bytes"))


class ReferenceFailure(RuntimeError):
    def __init__(self, code, record):
        super().__init__(code)
        self.record = record


def real(value):
    return type(value) in (int, float) and math.isfinite(value)


class Budget:
    def __init__(self, origin, deadline, limits, *, clock=time.monotonic):
        if not real(origin) or not real(deadline) or deadline <= origin:
            raise ValueError("finite original clock interval required")
        if type(limits) is not dict or set(limits) != LIMITS:
            raise ValueError("exact budget dimensions required")
        if any(type(x) is not int or x <= 0 for x in limits.values()):
            raise ValueError("strict positive integer limits required")
        if not callable(clock):
            raise ValueError("clock callable required")
        self.origin, self.deadline, self.clock = origin, deadline, clock
        self.limits = dict(limits)
        self.spent = {k: 0 for k in KINDS}
        self.live_current = self.live_peak = 0
        self.failures = []
        self.tick()

    def snapshot(self):
        return {"origin": self.origin, "deadline": self.deadline,
                "limits": dict(self.limits), "reservations": dict(self.spent),
                "planned_live_current": self.live_current,
                "planned_live_peak": self.live_peak, "failures": list(self.failures),
                "physical_RSS_measured": False}

    def fail(self, code):
        self.failures.append(str(code))
        raise ReferenceFailure(str(code), {"status": "failed", "reason": str(code),
                                          "budget": self.snapshot()})

    def tick(self):
        value = self.clock()
        if not real(value) or value < self.origin or value > self.deadline:
            self.fail("original_clock_outside_interval")

    def reserve(self, kind, units):
        if type(units) is not int or units < 0 or kind not in LIMITS:
            self.fail("invalid_prospective_reservation")
        if kind == "live_bytes":
            self.live_peak = max(self.live_peak, self.live_current + units)
            if self.live_current + units > self.limits[kind]:
                self.fail("live_bytes_limit")
        else:
            # The rejected attempt remains charged. No refund on later failure.
            self.spent[kind] += units
            if self.spent[kind] > self.limits[kind]:
                self.fail(kind + "_limit")
        self.tick()

    @contextmanager
    def live(self, units):
        self.reserve("live_bytes", units)
        self.live_current += units
        try:
            yield
        finally:
            self.live_current -= units

    def numeric(self, elements, work, live):
        self.reserve("elements", int(elements))
        self.reserve("work_units", int(work))
        return self.live(int(live))


def require(ok, code, budget):
    if not ok:
        budget.fail(code)


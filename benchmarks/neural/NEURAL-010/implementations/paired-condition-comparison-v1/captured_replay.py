"""Source-owned, bounded metadata replay around the unchanged target barrier.

No participant callback or alternative evaluator is accepted. The upstream
scorer may still reopen its fixed, hash-checked source kernels; operand reads
are captured here and never fall back to the filesystem during replay.
"""
import json
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def frozen(value):
    """Snapshot only exact JSON containers; reject custom conversion hooks."""
    if type(value) is dict:
        need(all(type(k) is str for k in value), "string snapshot keys")
        return {k: frozen(v) for k, v in value.items()}
    if type(value) is list:
        return [frozen(v) for v in value]
    need(type(value) in (str, int, float, bool, type(None)), "JSON snapshot values")
    # Serialization rejects nonfinite floats before any operator I/O.
    json.dumps(value, allow_nan=False)
    return value


def canonical(value):
    return json.dumps(frozen(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


class DeferredAssessment(BaseException):
    """An exact instance marks a reached, intentionally unopened target gate."""


class Retention:
    def __init__(self, maximum):
        need(type(maximum) is int and 0 < maximum <= 256 * 1048576,
             "bounded joint captured-metadata allowance")
        self.maximum, self.used = maximum, 0

    def reserve(self, count):
        need(type(count) is int and count >= 0 and self.used + count <= self.maximum,
             "joint immutable capture allowance exhausted")
        self.used += count


class ArmBudget:
    """Both passes share one child allowance and one whole-comparison clock."""
    def __init__(self, limits, aggregate, u):
        self.limits = frozen(limits)
        self.local = u.Budget(self.limits)
        self.local.origin = aggregate.origin
        self.local.end = min(aggregate.end, aggregate.origin + self.limits["seconds"])
        self.origin, self.end = self.local.origin, self.local.end
        self.aggregate = aggregate
        self.used = self.local.used

    def charge(self, key, count):
        # A failed operation never refunds either allowance. Charge the outer
        # account first so a later per-arm refusal still preserves attempted cost.
        self.aggregate.charge(key, count)
        self.local.charge(key, count)

    def tick(self):
        self.charge("read_bytes", 0)


class CapturedIO:
    def __init__(self, actual, retention, u):
        need(type(actual) is u.IO, "fixed captured upstream filesystem IO required")
        self.actual, self.retention, self.u = actual, retention, u
        self.budget = actual.budget
        self.events = []
        self.cursor = 0
        self.replaying = False
        self.boundary = DeferredAssessment("joint assessment deferred")
        self.assessment = None
        self.assessment_cap = None
        self.admission_hits = 0
        self.replay_hits = 0
        self.target_bytes = None
        self.created_body = None
        self.created_descriptor = None
        self.created_directory = None

    def charge(self, count):
        self.budget.charge("read_bytes", count)

    def _event(self, method, arguments, acquire, *, extent=None):
        key = canonical([method, arguments])
        if self.replaying:
            need(self.cursor < len(self.events), "unexpected replay access")
            old_key, value, logical_read = self.events[self.cursor]
            need(key == old_key, "replay access identity/order changed")
            self.cursor += 1
            self.charge(logical_read)
            return value if type(value) is bytes else frozen(value)
        # For bodies with a declared size, reserve before the physical capture.
        overhead = len(key) + 128
        if extent is not None:
            self.retention.reserve(overhead + extent)
        value, logical_read = acquire()
        need(type(value) is bytes or value is None or type(value) is list,
             "bounded immutable replay result")
        if type(value) is bytes:
            need(extent is not None and len(value) <= extent, "capture reservation extent")
            stored = value
            # Retention is a bound on resident captured objects, not a refunded
            # read/work budget. Release only unused pre-read capacity.
            self.retention.used -= extent - len(value)
        else:
            stored = frozen(value)
            if extent is None:
                self.retention.reserve(overhead + len(canonical(stored)))
            else:
                actual = len(canonical(stored))
                need(actual <= extent, "metadata reservation extent")
                self.retention.used -= extent - actual
        self.events.append((key, stored, logical_read))
        return value if type(value) is bytes else frozen(stored)

    def capture(self, desc, role, cap=16 * 1048576):
        desc = frozen(desc)
        self.u.c.descriptor(desc, True)
        need(type(role) is str and type(cap) is int and 0 < desc["bytes"] <= cap,
             "exact captured operand bounds")
        need(Path(desc["path"]).name.casefold() not in
             ("assessment.json", "train.json", "validation.json"),
             "protected body cannot enter metadata replay")
        return self._event("capture", [desc, role, cap],
                           lambda: (self.actual.capture(desc, role, cap), desc["bytes"] + 1),
                           extent=desc["bytes"])

    def journal_body(self, path, role):
        path = str(path)
        self.u.c.absolute(path)
        need(type(role) is str, "journal role")
        need(Path(path).name.casefold() not in ("assessment.json", "train.json", "validation.json"),
             "protected body cannot enter journal replay")
        # Upstream journal frames have a fixed 64-KiB ceiling; reserve it first.
        return self._event("journal_body", [path, role],
                           lambda: self._journal(path, role), extent=self.u.c.EVENT_CAP)

    def _journal(self, path, role):
        raw = self.actual.journal_body(path, role)
        return raw, len(raw) + 1

    def names(self, path):
        path = str(path)
        self.u.c.absolute(path)
        def acquire():
            names = self.actual.names(path)
            need(type(names) is list and len(names) <= 10000
                 and all(type(n) is str and len(n.encode()) <= 1024 for n in names),
                 "bounded captured namespace")
            count = len(canonical(names)) + 1
            self.charge(count)
            return names, count
        # At most 10,000 bounded names plus JSON escaping (six bytes per code
        # point) and separators. This is transient capacity, released to actual
        # retained extent after the source-bounded listing returns.
        return self._event("names", [path], acquire, extent=10000 * (6 * 1024 + 3) + 2)

    def stat_only(self, desc, role):
        desc = frozen(desc)
        self.u.c.descriptor(desc, True)
        need(type(role) is str, "stat-only role")
        def acquire():
            self.actual.stat_only(desc, role)
            return None, 0
        return self._event("stat_only", [desc, role], acquire)

    def capture_training(self, *args, **kwargs):
        raise ValueError("paired zero-training score must not read training labels")

    def capture_assessment(self, desc, cap=16 * 1048576):
        desc = frozen(desc)
        self.u.c.descriptor(desc, True)
        need(type(cap) is int and 0 < desc["bytes"] <= cap
             and Path(desc["path"]).name == "assessment.json", "exact selected assessment")
        if not self.replaying:
            self.admission_hits += 1
            need(self.admission_hits == 1, "one exact admission target boundary")
            self.assessment, self.assessment_cap = canonical(desc), cap
            raise self.boundary
        self.replay_hits += 1
        need(self.replay_hits == 1 and self.cursor == len(self.events),
             "all captured metadata must replay before one target use")
        need(canonical(desc) == self.assessment and cap == self.assessment_cap
             and type(self.target_bytes) is bytes, "unchanged common protected assessment")
        self.charge(len(self.target_bytes) + 1)
        need(self.u.c.same(self.u.pin(self.target_bytes), self.u.c.bare(desc)),
             "replayed immutable assessment pin")
        return self.target_bytes

    def enable_replay(self, target_bytes):
        need(self.admission_hits == 1 and not self.replaying
             and type(target_bytes) is bytes, "complete one-way replay transition")
        self.replaying = True
        self.target_bytes = target_bytes
        self.cursor = 0

    def directory(self, path):
        need(self.replaying and self.replay_hits == 1
             and self.cursor == len(self.events) and self.created_directory is None,
             "no publication before complete joint admission and own scoring")
        self.created_directory = self.actual.directory(path)
        return self.created_directory

    def create(self, path, body):
        need(self.replaying and self.created_directory is not None
             and Path(path) == self.created_directory / "RESULT.json"
             and self.created_body is None and type(body) is bytes,
             "single original result output")
        self.retention.reserve(len(body))
        self.created_descriptor = self.actual.create(path, body)
        self.created_body = body
        return frozen(self.created_descriptor)

    def unique_capture(self, role):
        found = []
        for key, body, _ in self.events:
            method, args = json.loads(key)
            if method == "capture" and args[1] == role:
                found.append(body)
        need(len(found) == 1, "one source-captured " + role)
        return found[0]

    def capture_multiset(self, role):
        """Compare bound bodies across arms independently of JSON object order.

        Sorting preserves multiplicity. Descriptor identity and actual bytes
        both participate; neither a set of hashes nor an acquisition-order
        assumption can erase a duplicated or substituted reference.
        """
        found = []
        for key, body, _ in self.events:
            method, args = json.loads(key)
            if method == "capture" and args[1] == role:
                found.append((canonical(args[0]), body))
        return tuple(sorted(found))

"""Source-level prospective costs; never a claim about allocator/RSS qualification."""
import json
import math
import time

LIMITS = ('read_bytes', 'write_bytes', 'serialized_bytes', 'allocation_bytes',
          'live_bytes', 'elements', 'work', 'files')


class ReferenceFailure(RuntimeError):
    def __init__(self, message, record=None):
        super().__init__(message)
        self.record = record or {}


def require(value, message):
    if not value:
        raise ReferenceFailure(message)


class Budget:
    def __init__(self, origin, deadline, limits, clock=None):
        require(type(origin) in (int, float) and type(deadline) in (int, float)
                and math.isfinite(origin) and math.isfinite(deadline)
                and 0 <= origin < deadline, 'invalid original clock')
        require(type(limits) is dict and set(limits) == set(LIMITS), 'budget keys')
        require(all(type(v) is int and v >= 0 for v in limits.values()), 'budget integers')
        self.origin, self.deadline = float(origin), float(deadline)
        self.limits = dict(limits)
        self.used = {k: 0 for k in LIMITS}
        self.rejected = []
        self.resident = 0
        self.plans = []
        self.clock = clock or time.monotonic
        self.last = 'construct'
        self.tick('construct')

    def snapshot(self):
        return {'origin': self.origin, 'deadline': self.deadline,
                'limits': dict(self.limits), 'charged': dict(self.used),
                'rejected_reservations': list(self.rejected), 'resident_source_bound': self.resident,
                'prospective_operation_plans': list(self.plans),
                'last_operation': self.last,
                'physical_io_native_workspace_rss': 'unmeasured; independent qualification required'}

    def fail(self, reason):
        raise ReferenceFailure(reason, self.snapshot())

    def tick(self, operation):
        self.last = operation
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or not self.origin <= now < self.deadline:
            self.fail('original clock unavailable/expired at ' + operation)

    def charge(self, key, amount, operation):
        self.tick(operation)
        if key not in self.limits or type(amount) is not int or amount < 0:
            self.fail('invalid charge')
        after = self.used[key] + amount
        if after > self.limits[key]:
            self.rejected.append({'key': key, 'requested': amount, 'proposed_total': after,
                                  'limit': self.limits[key], 'operation': operation})
            self.fail('prospective ' + key + ' limit at ' + operation)
        self.used[key] = after

    def workspace(self, amount, operation):
        """Conservative simultaneous source-level bound, including caller-held arrays."""
        self.tick(operation)
        if type(amount) is not int or amount < 0:
            self.fail('invalid live bound')
        amount += self.resident
        if amount > self.limits['live_bytes']:
            self.rejected.append({'key': 'live_bytes', 'requested': amount,
                                  'limit': self.limits['live_bytes'], 'operation': operation})
            self.fail('prospective live_bytes limit at ' + operation)
        self.used['live_bytes'] = max(self.used['live_bytes'], amount)

    def retain(self, amount, operation):
        """Conservatively retained input/state bodies throughout a worker invocation."""
        self.workspace(amount, operation)
        self.resident += amount

    def preflight(self, bounds, operation):
        self.tick(operation)
        for key, amount in bounds.items():
            require(key in self.limits and type(amount) is int and amount >= 0, 'preflight bound')
            if self.used[key]+amount > self.limits[key]:
                self.rejected.append({'key': key, 'requested': amount, 'operation': operation,
                                      'proposed_total': self.used[key]+amount, 'limit': self.limits[key]})
                self.fail('full-operation prospective '+key+' bound')
        self.plans.append({'operation': operation, 'bounds': dict(bounds),
                           'meaning': 'conservative source reservation, not measured physical cost'})

    def arrays(self, amount, operation, live=None):
        self.workspace(amount if live is None else live, operation)
        self.charge('allocation_bytes', amount, operation)
        self.charge('elements', amount, operation + ': conservative byte-as-element upper bound')

    def ops(self, amount, operation):
        self.charge('work', int(amount), operation)


def json_bound(obj, depth=0):
    require(depth < 64, 'metadata nesting')
    if obj is None or type(obj) is bool:
        return 5
    if type(obj) is int:
        require(abs(obj) < 2**127, 'oversize metadata integer')
        return 40
    if type(obj) is float:
        require(math.isfinite(obj), 'nonfinite metadata')
        return 32
    if type(obj) is str:
        return 2 + 12 * len(obj)
    if type(obj) in (list, tuple):
        return 2 + sum(1 + json_bound(v, depth + 1) for v in obj)
    if type(obj) is dict:
        require(all(type(k) is str for k in obj), 'metadata keys')
        return 2 + sum(2 + json_bound(k, depth + 1) + json_bound(v, depth + 1) for k, v in obj.items())
    raise ReferenceFailure('unsafe metadata object')


def encode(obj, budget, purpose):
    bound = json_bound(obj)
    budget.charge('serialized_bytes', bound, purpose + ': prospective JSON encoding')
    budget.workspace(2 * bound, purpose + ': JSON workspace')
    value = json.dumps(obj, ensure_ascii=True, separators=(',', ':'),
                       sort_keys=True, allow_nan=False).encode('ascii')
    require(len(value) <= bound, 'JSON bound violated')
    budget.tick(purpose + ': encoded')
    return value

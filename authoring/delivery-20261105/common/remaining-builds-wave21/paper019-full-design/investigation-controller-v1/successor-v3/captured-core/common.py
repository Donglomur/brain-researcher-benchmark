"""Typed scientific core primitives; no input acquisition or runtime authority."""
import hashlib
import json
import math

TASK = 'PAPER-ROOT-ADD-019'
STRATA = ('offer_CPIn', 'reward_SideOff', 'side_on', 'opt_out')
VARIANTS = ('B', 'D', 'ACh', 'F')
ACCESS = ('A_clarified', 'B_author_code')

class Refusal(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Refusal(reason)

def finite(value, name='finite number'):
    need(type(value) in (int, float) and math.isfinite(value), name)
    return float(value)

def integer(value, minimum=0):
    need(type(value) is int and value >= minimum, 'integer extent')
    return value

def token(value):
    need(type(value) is str and 0 < len(value) <= 160 and
         all(c.isalnum() or c in '_-.' for c in value), 'opaque token')
    return value

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')

def pin(value):
    raw = canonical(value)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def require_pin(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact pin fields')
    integer(value['bytes'])
    need(type(value['sha256']) is str and len(value['sha256']) == 64 and
         all(c in '0123456789abcdef' for c in value['sha256']), 'SHA256 pin')
    return value

class LogicalBudget:
    """Reserve attempted work before execution; failed reservations are retained.

    This is logical work accounting, not CPU, RSS, I/O or process enforcement.
    The caller's selected original clock must encompass all source/worker work.
    """
    def __init__(self, limits, origin, deadline, clock):
        need(type(limits) is dict and limits, 'explicit logical work limits')
        self.limits = {k: integer(v, 1) for k, v in limits.items()}
        self.used = {k: 0 for k in limits}
        self.origin, self.deadline, self.clock = finite(origin), finite(deadline), clock
        need(self.origin < self.deadline, 'original clock interval')
        self.failures = []
        self.tick()

    def tick(self):
        now = finite(self.clock())
        need(self.origin <= now < self.deadline, 'original strict scientific deadline')
        return now

    def reserve(self, charges, phase):
        self.tick()
        need(type(charges) is dict and set(charges) <= set(self.used), 'known resource dimensions')
        for key, amount in charges.items():
            integer(amount)
        for key, amount in charges.items():
            self.used[key] += amount
        exceeded = [k for k in charges if self.used[k] > self.limits[k]]
        if exceeded:
            self.failures.append({'phase': str(phase), 'exceeded': exceeded,
                                  'charges': dict(charges)})
            raise Refusal('logical allocation exceeded: ' + ','.join(exceeded))

    def failed(self, phase, error):
        self.failures.append({'phase': str(phase), 'error_type': type(error).__name__})

    def report(self):
        return {'limits': dict(self.limits), 'reserved_attempted': dict(self.used),
                'failures': list(self.failures), 'origin': self.origin,
                'deadline': self.deadline, 'physical_usage_measured': False}

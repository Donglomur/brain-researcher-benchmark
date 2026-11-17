"""Prospective logical cost admission, not a physical allocator or timer watchdog."""
import math
import time

class Failure(RuntimeError):
    def __init__(self, message, snapshot, later=None):
        super().__init__(message)
        self.snapshot = snapshot
        self.later = list(later or [])

class Budget:
    KEYS = ('read_bytes', 'write_bytes', 'serialized_bytes', 'allocation_bytes',
            'live_bytes', 'elements', 'work', 'files')
    def __init__(self, origin, deadline, limits, clock=None):
        self.clock = clock or time.monotonic
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (origin, deadline)) or not origin < deadline:
            raise ValueError('invalid inherited clock')
        if not isinstance(limits, dict) or set(limits) != set(self.KEYS):
            raise ValueError('exact budget keys required')
        if any(type(v) is not int or v < 0 for v in limits.values()):
            raise ValueError('finite nonnegative integer limits required')
        self.origin, self.deadline = origin, deadline
        self.limits = dict(limits)
        self.used = dict.fromkeys(self.KEYS, 0)
        self.events = []
        self.activities = {}
        self.tick()
    def snapshot(self):
        return {'origin': self.origin, 'deadline': self.deadline,
                'used': dict(self.used), 'limits': dict(self.limits),
                'logical_reservations_not_physical_measurements': True,
                'events': list(self.events),
                'activities': {k:dict(v,entered_incomplete=v['entered']-v['completed'],
                                   unentered=v['total']-v['entered']) for k,v in self.activities.items()}}
    def fail(self, message):
        raise Failure(message, self.snapshot())
    def tick(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or not self.origin <= now < self.deadline:
            self.fail('original clock outside admitted interval')
        return now
    def reserve(self, label, **cost):
        self.tick()
        if set(cost) - set(self.KEYS) or any(type(v) is not int or v < 0 for v in cost.values()):
            self.fail('invalid reservation')
        # Live reservations conservatively accumulate with no release until worker exit.
        # This overcounts disjoint lifetimes but never combines overlapping plans by max.
        proposed = {k: self.used[k] + cost.get(k, 0) for k in self.KEYS}
        ok = all(proposed[k] <= self.limits[k] for k in self.KEYS)
        self.events.append({'label': str(label), 'cost': dict(cost), 'admitted': ok})
        if not ok:
            self.fail('prospective resource cap: ' + str(label))
        self.used = proposed
    def begin(self, name, total):
        self.tick()
        if name in self.activities or type(total) is not int or total<0: self.fail("activity identity")
        self.activities[name]={"total":total,"entered":0,"completed":0}
    def enter(self, name):
        self.tick(); a=self.activities[name]
        if a["entered"]!=a["completed"] or a["entered"]>=a["total"]: self.fail("activity entry")
        a["entered"]+=1
    def complete(self, name):
        self.tick(); a=self.activities[name]
        if a["entered"]!=a["completed"]+1: self.fail("activity completion")
        a["completed"]+=1
    def barrier(self, label):
        self.tick()
        # Bounded stage journal only; per-training-step details go in complete step IDs.


def dimensions(n, c, family, config, budget, training=True, native_workspace=0):
    """Conservative full-shape plan; opaque native workspace is separately qualified.

    Counts cover repeated temporaries even though live memory may be reused. They
    are intentionally upper bounds, not benchmark feasibility or measured FLOPs.
    """
    if any(type(v) is not int or v < 0 for v in (n, c, native_workspace)) or c == 0:
        budget.fail('invalid geometry/workspace')
    p = 6 + 165*c
    raw = n*c*5000
    base = 8*(raw*24 + n*p*24 + c*5000*40 + p*p*4 + n*n*4 + 1)
    work = max(1, raw*256 + n*p*128)
    allocations = base
    if family == 'R' and training:
        k = min(n, p)
        work += 32*(n*p*k + k**3 + n*p)
        allocations += 8*(16*k*k + 8*n*p)
    elif family == 'B':
        trees = config['trees'] if training else config['trees']
        leaves = config['leaves']
        work += max(1, trees * (n*p*64*leaves*64 if training else n*leaves*16))
        allocations += 64*max(1,trees*n*p*64*leaves)
    elif family == 'T':
        w = config['width']; epochs = config['epochs'] if training else 1
        b = min(32, max(1,n))
        params = w*(2*c)*25+w + 3*(2*(w*w*9+w)) + w*(20*w+6+48*c)+w+w+1
        # Includes all retained inputs, graph activations/backward scratch and
        # independent fp64 gradient reductions; workspace bound is additional.
        base += 4*(params*24 + b*(w*5000*16 + w*1000*128 + c*5000*16))
        work += max(1, epochs*n*128*(2*c*w*25*5000 + 6*w*w*9*1000 + params))
        allocations += base*max(1, epochs*((n+b-1)//b))
    budget.reserve('full-'+family+('-fit' if training else '-predict'),
                   live_bytes=base+native_workspace, allocation_bytes=allocations+native_workspace,
                   elements=(allocations+7)//8, work=work)
    return {'n': n, 'channels': c, 'features': p, 'live_plan': base+native_workspace,
            'allocation_plan': allocations+native_workspace, 'work_plan': work}

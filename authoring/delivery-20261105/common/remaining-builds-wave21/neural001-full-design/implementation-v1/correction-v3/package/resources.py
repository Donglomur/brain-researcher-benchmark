"""Monotonic whole-program accounting; unknown/failed usage never becomes zero."""
from fractions import Fraction
from .protocol import Refusal, require, finite_number

ADDITIVE = ('wall_seconds', 'cpu_seconds', 'accelerator_seconds', 'provider_requests', 'input_tokens',
            'output_tokens', 'reasoning_tokens', 'tool_calls', 'read_bytes', 'write_bytes',
            'retained_log_bytes', 'source_revisions')
PEAK = ('resident_bytes', 'scratch_bytes', 'retained_bytes')


def quantities(x, fields):
    require(type(x) is dict and set(x) == set(fields), 'complete resource fields required')
    result = {}
    for k in fields:
        if type(x[k]) is Fraction:
            require(x[k] >= 0, 'nonnegative internal exact attribution required')
            result[k] = x[k]
        else:
            finite_number(x[k], k)
            result[k] = Fraction(str(x[k]))
    return result


class Ledger:
    def __init__(self, *, origin, deadline, limits, peaks, clock):
        finite_number(origin, 'original origin')
        finite_number(deadline, 'original deadline', positive=True)
        require(origin < deadline, 'original clock order required')
        self.origin, self.deadline, self.last, self.clock = origin, deadline, origin, clock
        self.limits, self.peak_limits = quantities(limits, ADDITIVE), quantities(peaks, PEAK)
        self.charged = dict.fromkeys(ADDITIVE, Fraction(0))
        self.observed = dict.fromkeys(ADDITIVE, Fraction(0))
        self.maximum = dict.fromkeys(PEAK, Fraction(0))
        self.active = None
        self.seen = set()
        self.terminal = False
        self.unknown = []
        self.check()

    def check(self):
        now = self.clock()
        finite_number(now, 'monotonic now')
        if self.terminal or now < self.last or now < self.origin or now >= self.deadline:
            self.terminal = True
            raise Refusal('terminal ledger, original clock rollback or deadline exhaustion')
        self.last = now
        return now

    def reserve(self, identity, amounts, peaks):
        self.check()
        require(self.active is None and identity not in self.seen, 'one fresh outstanding attempt required')
        a, p = quantities(amounts, ADDITIVE), quantities(peaks, PEAK)
        require(any(a.values()), 'positive complete attempt reservation required')
        for k in ADDITIVE:
            if self.charged[k] + a[k] > self.limits[k]:
                self.terminal = True
                raise Refusal('full budget exhausted before dispatch: ' + k)
        for k in PEAK:
            if p[k] > self.peak_limits[k]:
                self.terminal = True
                raise Refusal('peak reservation exhausted before dispatch: ' + k)
        token = object()
        self.active = (token, identity, a, p)
        self.seen.add(identity)
        for k in ADDITIVE:
            self.charged[k] += a[k]
        return token

    def admit_prelaunch(self, identity, amounts, peaks):
        """Retain already-observed prelaunch facts, even zero additive usage.

        This is observation admission, not a fictitious positive reservation for
        completed work. Any overrun is retained before refusal and input access.
        """
        require(self.active is None and identity not in self.seen,'fresh prelaunch observation')
        a,p=quantities(amounts,ADDITIVE),quantities(peaks,PEAK)
        self.seen.add(identity)
        for key in ADDITIVE:
            self.charged[key]+=a[key];self.observed[key]+=a[key]
        for key in PEAK:self.maximum[key]=max(self.maximum[key],p[key])
        problems=[]
        try:self.check()
        except Refusal as error:problems.append(str(error))
        problems.extend('prelaunch additive overrun:'+k for k in ADDITIVE if self.charged[k]>self.limits[k])
        problems.extend('prelaunch peak overrun:'+k for k in PEAK if self.maximum[k]>self.peak_limits[k])
        if problems:
            self.terminal=True
            raise Refusal(';'.join(problems))
        return {'identity':identity,'observations_retained':True,'invented_positive_usage':False}

    def finish(self, token, amounts, peaks, *, failed=False):
        require(self.active is not None and token is self.active[0], 'original reservation capability required')
        a, p = quantities(amounts, ADDITIVE), quantities(peaks, PEAK)
        _, identity, reserved, peak_reserved = self.active
        problems = []
        try:
            self.check()
        except Refusal as e:
            problems.append(str(e))
        for k in ADDITIVE:
            self.observed[k] += a[k]
            if a[k] > reserved[k]:
                self.charged[k] += a[k] - reserved[k]
                problems.append('unreserved consumption:' + k)
            if self.charged[k] > self.limits[k]:
                problems.append('total consumption:' + k)
        for k in PEAK:
            self.maximum[k] = max(self.maximum[k], p[k])
            if p[k] > peak_reserved[k] or p[k] > self.peak_limits[k]:
                problems.append('peak overrun:' + k)
        self.active = None
        if failed or problems:
            self.terminal = True
        if problems:
            raise Refusal(';'.join(problems))
        return {'identity': identity, 'failed': failed, 'original_origin': self.origin,
                'original_deadline': self.deadline, 'cost_reservation_retained': True}

    def abandon(self, token, reason):
        require(self.active is not None and token is self.active[0], 'original reservation capability required')
        self.unknown.append((self.active[1], tuple(ADDITIVE), tuple(PEAK), reason))
        self.active = None
        self.terminal = True
        # All reservation charges stay. Unknown observations are not filled with zero.

    def snapshot(self):
        def display(d):
            return {k: str(v) for k, v in d.items()}
        return {'origin': self.origin, 'deadline': self.deadline, 'last': self.last,
                'charged': display(self.charged), 'observed': display(self.observed),
                'peaks': display(self.maximum), 'unknown': list(self.unknown),
                'terminal': self.terminal, 'outstanding': self.active is not None}

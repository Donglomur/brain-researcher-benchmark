"""Exact-real finite-domain math only; no authentic input/custody or native parity.

Reviewed proposal: p768, ln terms256, exp degree128, range reduction2^11.
Every finite input is retained exactly. No float exp/log/power is used.
"""
from dataclasses import dataclass
import math
import time

P = 768
D = 1 << P
MAX_BITS = 8192
MAX_WIDTH = 1 << (P - 96)
RAW_UNIT = 1 << 1074
LN_TERMS = 256
EXP_DEGREE = 128
RANGE_POWER = 11


class Refusal(ValueError):
    pass


def require(ok, why):
    if not ok:
        raise Refusal(why)


def integer(x):
    require(type(x) is int, 'exact nonboolean integer')
    require(x.bit_length() <= MAX_BITS, 'integer bit cap')
    return x


def add(a, b):
    integer(a); integer(b)
    require(max(a.bit_length(), b.bit_length()) + 1 <= MAX_BITS, 'addition intermediate bit cap')
    return integer(a + b)


def mul(a, b):
    integer(a); integer(b)
    require(a.bit_length() + b.bit_length() <= MAX_BITS, 'multiplication intermediate bit cap')
    return integer(a * b)


def ceil_div(a, b):
    integer(a); integer(b)
    require(b > 0, 'positive divisor')
    return integer(-((-a) // b))


@dataclass(frozen=True)
class Rat:
    n: int
    d: int = 1

    def __post_init__(self):
        integer(self.n); integer(self.d)
        require(self.d != 0, 'nonzero rational denominator')
        n, d = self.n, self.d
        if d < 0:
            n, d = -n, -d
        g = math.gcd(abs(n), d)
        object.__setattr__(self, 'n', n // g)
        object.__setattr__(self, 'd', d // g)

    def plus(self, other):
        require(type(other) is Rat, 'exact rational operand')
        g = math.gcd(self.d, other.d)
        a, b = self.d // g, other.d // g
        return Rat(add(mul(self.n, b), mul(other.n, a)), mul(a, other.d))

    def neg(self):
        return Rat(-self.n, self.d)

    def minus(self, other):
        require(type(other) is Rat, 'exact rational operand')
        return self.plus(other.neg())

    def times(self, other):
        require(type(other) is Rat, 'exact rational operand')
        g, h = math.gcd(abs(self.n), other.d), math.gcd(abs(other.n), self.d)
        return Rat(mul(self.n // g, other.n // h), mul(self.d // h, other.d // g))

    def over(self, other):
        require(type(other) is Rat and other.n != 0, 'nonzero exact rational divisor')
        return self.times(Rat(other.d, other.n))

    def le(self, other):
        require(type(other) is Rat, 'exact rational operand')
        return mul(self.n, other.d) <= mul(other.n, self.d)


@dataclass(frozen=True)
class Interval:
    lo: int
    hi: int

    def __post_init__(self):
        integer(self.lo); integer(self.hi)
        require(self.lo <= self.hi, 'ordered interval')

    def contains(self, value):
        require(type(value) is Rat, 'exact rational target')
        return mul(self.lo, value.d) <= mul(value.n, D) <= mul(self.hi, value.d)


def from_rat(x):
    require(type(x) is Rat, 'exact rational conversion')
    n = mul(x.n, D)
    return Interval(n // x.d, ceil_div(n, x.d))


def plus(a, b):
    require(type(a) is Interval and type(b) is Interval, 'interval operands')
    return Interval(add(a.lo, b.lo), add(a.hi, b.hi))


def times(a, b):
    require(type(a) is Interval and type(b) is Interval, 'interval operands')
    products = [mul(x, y) for x in (a.lo, a.hi) for y in (b.lo, b.hi)]
    return Interval(min(products) // D, ceil_div(max(products), D))


def positive_reciprocal(a):
    require(type(a) is Interval and a.lo > 0, 'positive reciprocal interval')
    square = mul(D, D)
    return Interval(square // a.hi, ceil_div(square, a.lo))


def intersect(a, lower, upper):
    require(type(a) is Interval, 'interval intersection')
    integer(lower); integer(upper)
    require(lower <= upper, 'ordered proved range')
    return Interval(max(a.lo, lower), min(a.hi, upper))


class Budget:
    """Caller-owned cumulative ledger. The selected worker supplies one shared ledger."""
    def __init__(self, *, deadline, max_calls, max_values):
        require(type(deadline) is float and math.isfinite(deadline) and deadline > time.monotonic(), 'future finite deadline')
        require(type(max_calls) is int and 0 < max_calls <= 100000, 'bounded call limit')
        require(type(max_values) is int and 0 < max_values <= 2000000, 'bounded value limit')
        self.deadline, self.max_calls, self.max_values = deadline, max_calls, max_values
        self.calls = self.values = self.supplied_values = self.steps = 0

    def check(self):
        require(time.monotonic() < self.deadline, 'kernel deadline')
        self.steps += 1

    def call(self):
        self.check()
        require(self.calls + 1 <= self.max_calls, 'scalar certification cap')
        self.calls += 1

    def supplied_inputs(self, count):
        self.check()
        require(type(count) is int and count >= 0, 'supplied raw input count')
        require(self.supplied_values + count <= self.max_values, 'supplied raw value cap')
        self.supplied_values += count

    def inputs(self, count):
        self.check()
        require(type(count) is int and count >= 0, 'raw input count')
        require(self.values + count <= self.max_values, 'raw value cap')
        self.values += count


@dataclass(frozen=True)
class Mean:
    value: Rat | None
    count: int
    positions: int


def exact_mean(values, budget):
    require(type(budget) is Budget, 'exact budget')
    require(type(values) in (list, tuple), 'finite concrete source group')
    budget.supplied_inputs(len(values))
    return _mean_after_supply(values, budget)


def _mean_after_supply(values, budget):
    # Private reduction: callers have already charged every supplied position.
    budget.inputs(len(values))
    require(len(values) == 15, 'all fifteen source positions')
    total, count, mask = 0, 0, 0
    for position, value in enumerate(values):
        budget.check()
        require(type(value) is float, 'binary64 float input, not integer/bool/narrow scalar')
        if math.isnan(value):
            continue
        require(math.isfinite(value), 'infinite raw value refuses whole reference')
        require(abs(value) <= 1000.0, 'prospective raw domain')
        n, d = value.as_integer_ratio()
        integer(n); integer(d)
        require(d > 0 and d & (d - 1) == 0 and d <= RAW_UNIT, 'exact binary64 dyadic denominator')
        coefficient = mul(n, RAW_UNIT // d)
        total = add(total, coefficient)
        count += 1
        mask |= 1 << position
    return Mean(Rat(total, mul(count, RAW_UNIT)) if count else None, count, mask)


def exact_float(value):
    require(type(value) is float and math.isfinite(value), 'finite binary64 candidate')
    n, d = value.as_integer_ratio()
    require(d > 0 and d & (d - 1) == 0 and d <= RAW_UNIT, 'candidate binary64 dyadic denominator')
    return Rat(n, d)


def ln10_interval(budget):
    """Fixed positive series and exact tail; no floating logarithm or cached answer."""
    require(type(budget) is Budget, 'exact budget')
    z = Rat(9, 11)
    z2 = z.times(z)
    term, total = z, Rat(0)
    for k in range(LN_TERMS):
        budget.check()
        total = total.plus(term.times(Rat(2, 2 * k + 1)))
        term = term.times(z2)
    # term is now z^(2*N+1).
    tail = term.times(Rat(2)).over(Rat(2 * LN_TERMS + 1).times(Rat(1).minus(z2)))
    require(tail.le(Rat(1, 1 << 134)), 'proved logarithm tail admission')
    lower, upper = from_rat(total), from_rat(total.plus(tail))
    return Interval(lower.lo, upper.hi)


def positive_exp_reduced(t, budget):
    require(type(t) is Interval and 0 <= t.lo <= t.hi <= D // 2, 'Taylor half-unit domain')
    require(type(budget) is Budget, 'exact budget')
    polynomial = Interval(D, D)
    # T_N(t)=1+t/1*(1+t/2*(...*(1+t/N))).
    for k in range(EXP_DEGREE, 0, -1):
        budget.check()
        denominator = mul(D, k)
        lo = mul(t.lo, polynomial.lo) // denominator
        hi = ceil_div(mul(t.hi, polynomial.hi), denominator)
        polynomial = Interval(add(D, lo), add(D, hi))
    # Uniform exact upper remainder2^-256, representable on the fixed grid.
    return Interval(polynomial.lo, add(polynomial.hi, 1 << (P - 256)))


@dataclass(frozen=True)
class Pair:
    interval: Interval | None
    pin: Mean
    pout: Mean


class Certifier:
    """Pure finite-domain certifier; possesses no authentic-source authority."""
    def __init__(self, budget):
        require(type(budget) is Budget, 'exact shared budget')
        self.budget = budget
        self.log_constant = None

    def pair(self, pin_values, pout_values):
        self.budget.call()  # Counts failed attempts and exact-zero shortcuts too.
        require(type(pin_values) in (list, tuple) and type(pout_values) in (list, tuple), 'two finite concrete source groups')
        self.budget.supplied_inputs(len(pin_values) + len(pout_values))
        a = _mean_after_supply(pin_values, self.budget)
        b = _mean_after_supply(pout_values, self.budget)
        if a.value is None or b.value is None:
            return Pair(None, a, b)
        delta = b.value.minus(a.value)
        if delta.n == 0:
            return Pair(Interval(0, 0), a, b)
        if self.log_constant is None:
            self.log_constant = ln10_interval(self.budget)
        magnitude = Rat(abs(delta.n), delta.d)
        scale = Rat(1, 10 * (1 << RANGE_POWER))
        lower_arg = magnitude.times(Rat(self.log_constant.lo, D)).times(scale)
        upper_arg = magnitude.times(Rat(self.log_constant.hi, D)).times(scale)
        t = Interval(from_rat(lower_arg).lo, from_rat(upper_arg).hi)
        exponent = positive_exp_reduced(t, self.budget)
        require(exponent.lo >= D, 'positive exponential lower bound')
        for _ in range(RANGE_POWER):
            self.budget.check()
            exponent = times(exponent, exponent)
        reciprocal = intersect(positive_reciprocal(exponent), 0, D)
        # (1-r)/(1+r) decreases on the proved domain[0,1].
        low = from_rat(Rat(D - reciprocal.hi, D + reciprocal.hi)).lo
        high = from_rat(Rat(D - reciprocal.lo, D + reciprocal.lo)).hi
        result = Interval(low, high) if delta.n > 0 else Interval(-high, -low)
        result = intersect(result, -D, D)
        self.budget.check()
        return Pair(result, a, b)


def mean_intervals(values):
    require(type(values) in (list, tuple) and 0 < len(values) <= 28, 'bounded concrete reduction')
    lo = hi = count = 0
    for value in values:
        if value is None:
            continue
        require(type(value) is Interval and -D <= value.lo <= value.hi <= D, 'bounded real contrast interval')
        lo, hi = add(lo, value.lo), add(hi, value.hi)
        count += 1
    return (Interval(lo // count, ceil_div(hi, count)) if count else None), count


@dataclass(frozen=True)
class Window:
    interval: Interval | None
    time_counts: tuple
    frequency_count: int


def window(rows):
    require(type(rows) in (list, tuple) and len(rows) == 7, 'all seven fixed frequencies')
    means, counts = [], []
    for row in rows:
        require(type(row) in (list, tuple) and len(row) == 28, 'all twenty-eight fixed times')
        value, count = mean_intervals(row)
        means.append(value); counts.append(count)
    value, count = mean_intervals(means)
    if value is not None:
        require(value.hi - value.lo <= MAX_WIDTH, 'final map certificate diameter')
    return Window(value, tuple(counts), count)

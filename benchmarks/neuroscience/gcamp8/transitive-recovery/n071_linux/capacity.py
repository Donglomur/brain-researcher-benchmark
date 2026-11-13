"""Required finite capacities. Unknown reservations remain committed."""
import math
from dataclasses import dataclass
from .custody import require

FLOW = frozenset(("read_bytes", "write_bytes", "creation_attempts",
                  "child_attempts", "provider_calls", "input_tokens",
                  "output_tokens", "currency_units"))
PEAK = frozenset(("live_fds", "rss_bytes"))
CLOCK = frozenset(("wall_seconds", "cpu_seconds"))
REQUIRED = FLOW | PEAK | CLOCK

def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0

@dataclass(eq=False)
class Reservation:
    owner: object
    dimension: str
    capacity: int | float
    effect: str
    acknowledged: int | float = 0
    retired: bool = False
    unknown: bool = False

class Capacity:
    def __init__(self, owner, limits):
        require(type(limits) is dict and set(limits) == REQUIRED, "complete-profile")
        require(all(finite(x) for x in limits.values()), "finite-profile")
        require(all(type(limits[k]) is int for k in REQUIRED-CLOCK-{"currency_units"}),
                "integer-capacities")
        self.owner = owner
        self.limits = dict(limits)
        self.used = dict.fromkeys(FLOW, 0)
        self.held = dict.fromkeys(FLOW | PEAK, 0)
        self.live = dict.fromkeys(PEAK, 0)
        self.peak = dict.fromkeys(PEAK, 0)
        self.reservations = []
        self.clock = dict.fromkeys(CLOCK, 0)

    def reserve(self, dimension, amount, effect, *, cleanup=False):
        require(dimension in FLOW | PEAK and finite(amount), "reservation-domain")
        if dimension not in {"currency_units"}:
            require(type(amount) is int, "reservation-integer")
        if not cleanup:
            self.owner.custody.raise_first()
            require(not self.owner.custody.unknown, "owner-uncertain")
        current = self.used[dimension] if dimension in FLOW else self.live[dimension]
        require(current + self.held[dimension] + amount <= self.limits[dimension],
                "capacity-" + dimension)
        r = Reservation(self, dimension, amount, effect)
        self.reservations.append(r)
        self.held[dimension] += amount
        return r

    def settle(self, r, acknowledged, *, unknown=False):
        require(type(r) is Reservation and r.owner is self and
                any(x is r for x in self.reservations) and not r.retired,
                "original-once-reservation")
        require(finite(acknowledged) and acknowledged <= r.capacity, "settlement-range")
        r.retired = True
        r.acknowledged = acknowledged
        r.unknown = bool(unknown)
        # Unknown suffix retains the remaining capacity. No success refund.
        self.held[r.dimension] -= acknowledged if unknown else r.capacity
        if r.dimension in FLOW:
            self.used[r.dimension] += acknowledged
        else:
            self.live[r.dimension] += acknowledged
            self.peak[r.dimension] = max(self.peak[r.dimension], self.live[r.dimension])
        if unknown:
            self.owner.custody.uncertain(r.effect, {"held": r.capacity-acknowledged})

    def consume_attempt(self, dimension, effect, *, cleanup=False):
        r = self.reserve(dimension, 1, effect, cleanup=cleanup)
        self.settle(r, 1)
        return r

    def release_live(self, dimension, amount, *, known):
        require(dimension in PEAK and type(amount) is int and
                0 <= amount <= self.live[dimension], "live-release")
        if known:
            self.live[dimension] -= amount
        else:
            self.owner.custody.uncertain("release-" + dimension, {"amount": amount})

    def observe_clock(self, wall, cpu):
        require(finite(wall) and finite(cpu), "clock-observation")
        require(wall >= self.clock["wall_seconds"] and cpu >= self.clock["cpu_seconds"],
                "original-monotonic-clocks")
        self.clock.update(wall_seconds=wall, cpu_seconds=cpu)
        require(all(self.clock[k] <= self.limits[k] for k in CLOCK), "clock-cap")

    def report(self):
        return {"limits": dict(self.limits), "used": dict(self.used),
                "held": dict(self.held), "live": dict(self.live),
                "peak": dict(self.peak), "clock": dict(self.clock),
                "unknown": list(self.owner.custody.unknown),
                "counter_coverage": "explicit-owned-effects-only"}


@dataclass(eq=False)
class CompositeReservation:
    owner:object
    dimension:str
    capacity:int|float
    tokens:list
    retired:bool=False
    acknowledged:int|float=0

class CompositeCapacity:
    """One actual effect viewed in original global and scope ledgers, once each.

    This is an internal source adapter, not a new allowance. It can only be
    constructed from the original registered native invocation and live scope.
    """
    def __init__(self,invocation,scope):
        from .supervision import require_invocation,Scope
        require_invocation(invocation)
        require(type(scope)is Scope and invocation.scopes.get(scope.name)is scope and
                not scope.closed,'actual-original-charged-scope')
        self.invocation,self.scope=invocation,scope
        self.owner=invocation.owner
        self.views=tuple(invocation._capacities(scope))
        self.limits={k:min(c.limits[k]for c in self.views)for k in REQUIRED}
        self.reservations=[]
    def reserve(self,dimension,amount,effect,*,cleanup=False):
        if dimension=='live_fds':
            traced=sum(len(row['fds'])for row in self.invocation.processes.values())
            in_flight=sum(self.invocation.fd_pending.values())
            for view in self.views:
                require(traced+in_flight+view.live['live_fds']+view.held['live_fds']+amount
                        <=view.limits['live_fds'],'combined-parent-and-traced-fd-admission')
        r=CompositeReservation(self,dimension,amount,[]);self.reservations.append(r)
        try:
            for view in self.invocation.effect_capacities(self.scope,dimension):
                r.tokens.append(view.reserve(dimension,amount,effect,cleanup=cleanup))
        except BaseException as error:
            self.owner.custody.fail(error,'composite-original-reservation')
            for t in r.tokens:
                try:t.owner.settle(t,0)
                except BaseException as later:self.owner.custody.fail(later,'composite-reservation-retirement')
            self.owner.custody.raise_first()
        return r
    def settle(self,r,acknowledged,*,unknown=False):
        require(type(r)is CompositeReservation and r.owner is self and
                any(x is r for x in self.reservations)and not r.retired,'original-composite-token')
        r.retired=True;r.acknowledged=acknowledged
        for t in r.tokens:
            try:t.owner.settle(t,acknowledged,unknown=unknown)
            except BaseException as error:
                self.owner.custody.fail(error,'independent-original-view-settlement')
                self.owner.custody.uncertain('composite-settlement',{'dimension':r.dimension})
        self.owner.custody.raise_first()
    def consume_attempt(self,dimension,effect,*,cleanup=False):
        r=self.reserve(dimension,1,effect,cleanup=cleanup);self.settle(r,1);return r
    def release_live(self,dimension,amount,*,known):
        for view in self.views:
            try:view.release_live(dimension,amount,known=known)
            except BaseException as error:self.owner.custody.fail(error,'independent-live-view-release')
        self.owner.custody.raise_first()

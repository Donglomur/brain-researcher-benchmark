"""Versioned exclusive cumulative ownership; original Budget math remains unchanged."""
from .guard import Budget
from .custody import need
from four_programmes.common import closed, integer, finite, same, encode, pin

_COUNTERS = ("read_reserved","write_reserved","read_completed","write_completed",
             "array_live","array_peak","array_cumulative","cpu_usec")
_IMMUTABLE = ("campaign_id","clock_binding","origin_seconds","deadline_seconds",
              "read_cap","write_cap","array_cap")
_FIELDS = ("schema","campaign_id","generation","clock_binding","origin_seconds",
           "deadline_seconds","read_cap","write_cap","array_cap",*_COUNTERS,
           "physical_OS_IO_measured","physical_RSS_measured_by_controller")

def validate_state(state):
    closed(state, _FIELDS)
    need(state["schema"] == "critical_init_cumulative_budget_state_v3", "state schema")
    need(type(state["campaign_id"]) is str and state["campaign_id"], "campaign")
    integer(state["generation"]); finite(state["origin_seconds"]); finite(state["deadline_seconds"])
    need(state["origin_seconds"] < state["deadline_seconds"], "original interval")
    for key in ("read_cap","write_cap","array_cap"):
        integer(state[key], 1)
    for key in _COUNTERS:
        integer(state[key])
    need(state["read_completed"] <= state["read_reserved"] <= state["read_cap"] and
         state["write_completed"] <= state["write_reserved"] <= state["write_cap"],
         "exact monotone IO prefix within original caps")
    need(state["array_live"] <= state["array_peak"] <= state["array_cap"] and
         state["array_peak"] <= state["array_cumulative"], "exact array lineage")
    need(state["physical_OS_IO_measured"] is False and
         state["physical_RSS_measured_by_controller"] is False, "logical observations only")
    return state

def extends(earlier, later, *, generation):
    validate_state(earlier); validate_state(later)
    need(all(same(earlier[k], later[k]) for k in _IMMUTABLE), "identical original limits and clock")
    need(later["generation"] == generation, "exact serial generation")
    need(all(later[k] >= earlier[k] for k in _COUNTERS if k != "array_live"),
         "complete monotone original prefix; no reset or additive merge")
    return later

class ExclusiveBudget(Budget):
    """One programme writer, distinct from the previously reserved H bridge meter."""
    def __init__(self, state, *, owner, lease_pin=None, previous_return=None):
        validate_state(state)
        need(owner in ("C","W"), "fixed original budget owner")
        self._active = True
        self._owner = owner
        self._failure_only = False
        self._lease_pin = lease_pin
        self._base = None
        self._previous_return = previous_return
        self._consumed_returns = {}
        self.campaign_id = state["campaign_id"]
        self.clock_binding = state["clock_binding"]
        self.generation = state["generation"]
        # This is an explicitly versioned reconstruction, not Budget.adopt.
        super().__init__(seconds=state["deadline_seconds"]-state["origin_seconds"],
                         read_bytes=state["read_cap"],write_bytes=state["write_cap"],
                         array_bytes=state["array_cap"],origin=state["origin_seconds"])
        self.deadline = state["deadline_seconds"]
        for key in _COUNTERS:
            setattr(self, key, state[key])
        need(self.snapshot() == state, "exact original state bootstrap")
    def _token(self):
        need(self._active, "programme writer token is suspended or terminal")
    def check(self):
        self._token()
        return super().check()
    def release_array(self, amount):
        self._token()
        return super().release_array(amount)
    def adopt(self, record):
        raise ValueError("maxima-based Budget.adopt is forbidden in exclusive v3")
    def require_operation(self, operation):
        self._token()
        need(not self._failure_only or operation == "report", "failed state is report-only")
        self.check()
    def snapshot(self):
        self._token()
        r = {"schema":"critical_init_cumulative_budget_state_v3",
             "campaign_id":self.campaign_id,"generation":self.generation,
             "clock_binding":self.clock_binding,"origin_seconds":self.origin,
             "deadline_seconds":self.deadline,"read_cap":self.read_cap,
             "write_cap":self.write_cap,"array_cap":self.array_cap,
             "physical_OS_IO_measured":False,"physical_RSS_measured_by_controller":False}
        r.update({k:getattr(self,k) for k in _COUNTERS})
        return validate_state(r)
    def suspend(self, lease_pin, lease, base_pin):
        self.require_operation("stage")
        need(self._owner == "C" and self.array_live == 0, "C has no outstanding arrays at transfer")
        base = self.snapshot()
        need(lease["campaign_id"] == self.campaign_id and lease["base_generation"] == self.generation
             and lease["base_state"] == base_pin and lease["previous_return"] == self._previous_return,
             "unique actual C prefix and prior return")
        need(pin(encode(base)) == {k:base_pin[k] for k in ("bytes","sha256")}, "exact frozen base")
        self._base = base
        self._lease_pin = dict(lease_pin)
        self._active = False
        return base
    def export_terminal(self, *, failure_only=False):
        # After a deadline/error there is no new programme operation. The
        # earlier H terminal share may still capture a known exact prefix.
        # This is not permission to continue science or renew the deadline.
        need(type(failure_only) is bool, "explicit terminal disposition")
        self._token()
        if not failure_only:
            self.require_operation("stage")
        need(self._owner == "W", "only original worker terminal")
        need(self.array_live == 0, "all original owned arrays released before worker transfer")
        self.generation += 1
        state = self.snapshot()
        self._active = False
        return state
    def restore(self, admission):
        # A source-owned StageAdmission is created only by the complete closure consumer.
        from .stage_closure import StageAdmission
        need(type(admission) is StageAdmission, "complete typed original stage admission")
        ret, terminal = admission.budget_return, admission.terminal
        key = encode(admission.return_pin)
        if key in self._consumed_returns:
            need(self._consumed_returns[key] == encode(terminal), "same prior return observation")
            return {"already_consumed":True,"state_mutated":False}
        need(self._owner == "C" and not self._active and self._base is not None,
             "exact suspended C owner")
        need(ret["lease"] == self._lease_pin and ret["previous_return"] == self._previous_return
             and ret["campaign_id"] == self.campaign_id, "actual lease return lineage")
        need(ret["disposition"] in ("eligible_exact_successor","failure_only") and
             terminal is not None and not ret["unknown_dimensions"], "known exact terminal only")
        extends(self._base, terminal, generation=self.generation + 1)
        need(terminal["array_live"] == 0, "no hidden terminal arrays")
        for name in _COUNTERS:
            setattr(self, name, terminal[name])
        self.generation = terminal["generation"]
        self._failure_only = ret["disposition"] == "failure_only"
        self._previous_return = dict(admission.return_pin)
        self._consumed_returns[key] = encode(terminal)
        self._active = True
        self._lease_pin = None
        self._base = None
        return {"already_consumed":False,"state_mutated":True,"failure_only":self._failure_only}

    def export_controller_terminal(self, *, failure_only=False):
        """Final C prefix after report writes; no new W generation or allowance.

        Protected-grade arrays remain recorded as live until the original C
        process exits. The earlier H bridge owns only the subsequent metadata
        transport; it cannot perform a new programme operation after this seal.
        """
        need(type(failure_only) is bool and self._owner=='C' and self.generation==5,
             'fixed completed five-stage C terminal, never a worker export')
        self._token()
        if not failure_only:self.require_operation('report')
        state=self.snapshot()
        self._active=False
        return state

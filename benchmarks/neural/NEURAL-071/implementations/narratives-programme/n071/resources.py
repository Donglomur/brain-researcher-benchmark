"""Cumulative reservations, actual effect settlement and original clocks."""
import time
from contextlib import contextmanager
from .errors import need
from .identity import finite

P1 = {"provider_calls": 16, "input_tokens": 60000, "output_tokens": 16000,
      "wall_seconds": 3600, "cpu_seconds": 28800, "rss_bytes": 64 * 2**30,
      "read_bytes": 128 * 2**30, "write_bytes": 8 * 2**30,
      "creation_attempts": 50000, "live_fds": 256, "child_attempts": 64}
R1 = {"provider_calls": 0, "input_tokens": 0, "output_tokens": 0,
      "wall_seconds": 7200, "cpu_seconds": 115200, "rss_bytes": 64 * 2**30,
      "read_bytes": 512 * 2**30, "write_bytes": 64 * 2**30,
      "creation_attempts": 200000, "live_fds": 256, "child_attempts": 128}

class Budget:
    def __init__(self, limits, name, observer=None):
        need(type(limits) is dict and limits and all(finite(v) and v >= 0 for v in limits.values()),
             "finite-profile")
        self.limits = dict(limits)
        self.name = name
        self.used = {k: 0 for k in limits}
        self.reserved = {k: 0 for k in limits}
        self.pending = {}
        self.effects = []
        self.unknown = []
        self.sequence = 0
        self.live = 0
        self.fd_peak = 0
        self.start = time.monotonic()
        self.utc_start = time.time()
        self.cpu_start = time.process_time()
        self.child_cpu = 0
        self.rss_peak = None
        self.scope_memory_receipt = None
        self.observed_scope_costs = None
        self.closed = False
        self.observer = observer

    def reserve(self, key, amount, effect):
        need(not self.closed and not self.unknown, "budget-unusable")
        need(key in self.limits and finite(amount) and amount >= 0, "budget-dimension")
        need(self.used[key] + self.reserved[key] + amount <= self.limits[key], "reservation-" + key)
        self.sequence += 1
        token = self.sequence
        self.pending[token] = [key, amount, effect]
        self.reserved[key] += amount
        return token

    def settle(self, token, acknowledged, unknown=False):
        need(token in self.pending and finite(acknowledged) and acknowledged >= 0, "settlement")
        key, capacity, effect = self.pending[token]
        need(acknowledged <= capacity, "settlement-overrun")
        del self.pending[token]
        self.reserved[key] -= capacity
        self.used[key] += acknowledged
        self.effects.append({"token": token, "dimension": key, "capacity": capacity,
                             "acknowledged": acknowledged, "effect": effect,
                             "unknown_possible_prefix": bool(unknown)})
        if unknown:
            self.unknown.append({"token": token, "effect": effect, "unacknowledged_capacity": capacity-acknowledged})

    def attempt(self, key, effect):
        token = self.reserve(key, 1, effect)
        self.settle(token, 1)
        return token

    def acquired_fd(self, reservation):
        self.settle(reservation, 1)
        self.live += 1
        self.fd_peak = max(self.fd_peak, self.live)

    def reserve_fd(self, effect):
        need(self.live + self.reserved["live_fds"] < self.limits["live_fds"], "live-fd-limit")
        # live_fds is a simultaneous capacity; lifetime opens are in effects.
        need(not self.closed and not self.unknown, "budget-unusable")
        self.sequence += 1
        t = self.sequence
        self.pending[t] = ["live_fds", 1, effect]
        self.reserved["live_fds"] += 1
        return t

    def fd_closed(self, known=True):
        if known:
            need(self.live > 0, "fd-close-ownership")
            self.live -= 1
        else:
            self.unknown.append({"effect": "fd-close", "unacknowledged_capacity": "owned descriptor closure"})

    def observe_process(self, child_cpu, tree_rss):
        need(finite(child_cpu) and child_cpu >= 0 and type(tree_rss) is int and tree_rss >= 0,
             "process-measurement")
        self.child_cpu += child_cpu
        self.rss_peak = max(self.rss_peak or 0, tree_rss)
        need(self.rss_peak <= self.limits["rss_bytes"], "tree-memory-limit")

    def observe_complete_scope_memory(self,receipt):
        need(receipt["scope"]==self.name and receipt["from_monotonic"]<=self.start and
             receipt["through_monotonic"]>=self.last_effect_end and receipt["complete_tree"] is True and
             receipt["includes_controller"] is True and receipt["unknown_intervals"]==[],
             "complete-scope-memory-observation")
        need(type(receipt["peak_rss_bytes"])is int and
             0<=receipt["peak_rss_bytes"]<=self.limits["rss_bytes"],"whole-scope-memory")
        costs=receipt["complete_scope_costs"]
        # The qualified protected monitor includes native/SDK/file/socket effects
        # omitted by the explicit Store counters. Never assume those effects zero.
        for key in ("read_bytes","write_bytes","creation_attempts","child_attempts",
                    "cpu_seconds","wall_seconds"):
            need(key in costs and finite(costs[key]) and
                 self.used[key]<=costs[key]<=self.limits[key],"complete-observed-cost-"+key)
        need(costs["final_live_fds"]==0 and
             self.fd_peak<=costs["peak_live_fds"]<=self.limits["live_fds"] and
             costs["original_descendant_waits_complete"] is True,"complete-observed-resource-closure")
        self.observed_scope_costs=costs
        self.scope_memory_receipt=receipt

    def checkpoint(self):
        wall = time.monotonic() - self.start
        cpu = time.process_time() - self.cpu_start + self.child_cpu
        need(wall <= self.limits["wall_seconds"] and cpu <= self.limits["cpu_seconds"], "clock-budget")
        return wall, cpu

    def close(self, require_tree_measurement=True):
        # The qualified outer owner closes/observes the complete scope after its
        # final artifact readback. Transporting this closure belongs to that outer
        # owner's separately accounted scope; no self-measurement fiction.
        wall,cpu=self.checkpoint()
        self.used["wall_seconds"]=wall
        self.used["cpu_seconds"]=cpu
        self.last_effect_end=time.monotonic()
        if require_tree_measurement:
            need(self.observer is not None,"missing-qualified-scope-observer")
            self.observe_complete_scope_memory(self.observer.close(self.report(),self.last_effect_end))
        wall, cpu = self.checkpoint()
        need(not self.pending and not self.unknown and self.live == 0, "cost-closure")
        need(not require_tree_measurement or self.scope_memory_receipt is not None, "missing-tree-memory-cost")
        self.used["wall_seconds"] = wall
        self.used["cpu_seconds"] = cpu
        self.used["rss_bytes"] = (None if self.scope_memory_receipt is None else
                                  self.scope_memory_receipt["peak_rss_bytes"])
        self.closed = True
        return self.report()

    def report(self):
        return {"name": self.name, "limits": self.limits, "used": dict(self.used),
                "reserved": dict(self.reserved), "effects": list(self.effects),
                "unknown": list(self.unknown), "live_fds": self.live, "peak_live_fds": self.fd_peak,
                "original_monotonic_start": self.start, "original_utc_start": self.utc_start,
                "scope_memory_receipt":self.scope_memory_receipt,
                "observed_complete_scope_costs":self.observed_scope_costs,
                "closed": self.closed, "whole_host_admission_is_separate": True}

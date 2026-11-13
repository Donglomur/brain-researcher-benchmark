"""Complete F/I quantitative accounting. Authority/profile admission remains external."""
from copy import deepcopy
from .contracts import need, finite, CONDITIONS, ARMS, STATUS

FIELDS = ("wall_seconds", "cpu_seconds", "read_bytes", "write_bytes", "tool_calls",
          "fit_calls", "provider_tokens")
PHASES = ("investigation", "fit", "inference", "failed_work")
INTEGER_FIELDS = FIELDS[2:]

def cost(value):
    need(type(value) is dict and set(value) == set(FIELDS), "exact cost fields")
    for k, v in value.items():
        need(finite(v) and v >= 0, "nonnegative finite cost")
        if k in INTEGER_FIELDS:
            need(type(v) is int, "integer work count")
    return dict(value)

def zero():
    return {k: 0 for k in FIELDS}

class LifecycleLedger:
    def __init__(self, session_ids, paired_limits, global_limits):
        need(len(session_ids) == len(set(session_ids)) == 29, "complete session cost roster")
        self.sessions = tuple(session_ids)
        self.limits = cost(paired_limits); self.global_limits = cost(global_limits)
        self.global_f = None
        self.events, self.used = [], {}
        self.poisoned = False

    def global_development(self, measured, identity):
        need(self.global_f is None and not self.events and not self.poisoned,
             "one global F development record before session work")
        measured = cost(measured)
        self.global_f = {"identity": deepcopy(identity), "measured": measured}
        if any(measured[k] > self.global_limits[k] for k in FIELDS):
            self.poisoned = True
            raise ValueError("global development cap; failed costs retained")

    def charge(self, session_id, condition, arm, phase, measured, *, evidence, failed=False):
        need(not self.poisoned and self.global_f is not None, "healthy admitted ledger")
        need(session_id in self.sessions and condition in CONDITIONS and arm in ARMS
             and phase in PHASES, "exact lifecycle cell")
        need(type(evidence) is dict and evidence, "measurement/provenance evidence")
        measured = cost(measured)
        key = (session_id, condition, arm)
        accum = self.used.setdefault(key, zero())
        for k in FIELDS:
            accum[k] += measured[k]
        self.events.append({"session_id": session_id, "condition": condition, "arm": arm,
                            "phase": phase, "cost": measured, "evidence": deepcopy(evidence),
                            "failed": bool(failed)})
        # Development is charged once globally, allocated across 29x4 F cells.
        allocation = {k: self.global_f["measured"][k] / (29 * 4) if arm == "F" else 0
                      for k in FIELDS}
        if any(accum[k] + allocation[k] > self.limits[k] for k in FIELDS):
            self.poisoned = True
            raise ValueError("paired lifecycle cap exceeded; complete attempted costs retained")

    def report(self):
        allocation = {s: {k: self.global_f["measured"][k]/29 for k in FIELDS}
                      for s in self.sessions} if self.global_f else None
        cells = []
        for s in self.sessions:
            for c in CONDITIONS:
                for a in ARMS:
                    cells.append({"session_id": s, "condition": c, "arm": a,
                                  "cost": deepcopy(self.used.get((s,c,a), zero())),
                                  "status": "observed" if (s,c,a) in self.used else "unattempted"})
        return {"status": STATUS, "poisoned": self.poisoned, "global_F_once": self.global_f,
                "global_F_equal_session_allocation": allocation, "cells": cells,
                "events": deepcopy(self.events), "equal_F_I_and_C_CN_ceiling": self.limits,
                "actual_provider_or_measurement_qualification": False}

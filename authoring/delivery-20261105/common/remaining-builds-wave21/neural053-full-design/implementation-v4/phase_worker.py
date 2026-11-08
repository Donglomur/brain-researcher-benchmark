"""Actual operator phase child. Completion authority belongs to its parent."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cohort import require
from io_support import Budget, checked_bytes
from phase_manifest import budget_snapshot


class IncrementBudget(Budget):
    """Original ledger plus independently reserved per-phase incremental caps."""
    def __init__(self, snapshot, caps):
        super().__init__(snapshot["limits"], snapshot["origin_monotonic"], snapshot["deadline_monotonic"])
        require(set(snapshot["used"]) == set(self.limits) == set(caps) and
                all(type(snapshot["used"][k]) is int and 0 <= snapshot["used"][k] <= self.limits[k] and
                    type(caps[k]) is int and 0 <= caps[k] <= self.limits[k] - snapshot["used"][k] for k in self.limits),
                "Exact original ledger and reserved incremental counters")
        self.used = dict(snapshot["used"])
        self.base_used = dict(self.used)
        self.increment_caps = dict(caps)

    def charge(self, name, amount=1):
        require(name in self.increment_caps and type(amount) is int and amount >= 0 and
                self.used[name] - self.base_used[name] + amount <= self.increment_caps[name], "Phase reservation exhausted")
        super().charge(name, amount)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--envelope", required=True); p.add_argument("--bytes", required=True, type=int)
    p.add_argument("--sha256", required=True)
    args = p.parse_args()
    require(0 < args.bytes <= 16 * 1024 * 1024, "Bounded phase bootstrap envelope")
    # Parent reserved all child costs before launch. Bootstrap has a finite cap;
    # it is debited after the gate captures the original before-ledger, including
    # on admission failure. It never creates a new clock or enlarges limits.
    class Bootstrap:
        def charge(self, name, amount): require(name == "source_read" and amount == args.bytes, "Exact bootstrap debit")
    body = checked_bytes(args.envelope, {"bytes": args.bytes, "sha256": args.sha256}, Bootstrap())
    envelope = json.loads(body)
    require(envelope.get("schema") == "neural053_phase_child_envelope_v2", "Phase child envelope")
    budget = IncrementBudget(envelope["budget_before"], envelope["increment_caps"])
    budget.bootstrap_read_bytes = len(body)
    from frontdoor import execute_stage
    output = execute_stage(envelope["phase"], envelope["invocation"], envelope["permit"], envelope["permit"]["bindings"],
                           frozenset(envelope["approved_receipts"]), budget)
    print(json.dumps({"schema": "neural053_phase_child_return_v2", "phase": envelope["phase"], "output_manifest": output,
                      "budget_after": budget_snapshot(budget), "increment_used": {k:budget.used[k]-budget.base_used[k] for k in budget.used},
                      "scientific_qualification_conferred": False}, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__": main()

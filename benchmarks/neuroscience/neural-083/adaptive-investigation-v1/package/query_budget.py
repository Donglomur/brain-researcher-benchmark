"""Pure per-query native-time reservation ledger; no native/model integration.

The caller dispatches only after reserve() returns and must use that grant's
query_deadline as the absolute lifecycle deadline. Failed dispatch has no refund.
"""
from __future__ import annotations

import math
import time

SCHEMA = "neural083-query-budget-v1"
MAX_SECONDS = 86400
MAX_TOOL_CALLS = 4096
MAX_CLOCK = 1000000000000
ENTRANTS = frozenset(("case_adaptive_equal_inputs_tools_compute", "frozen_program", "decoder_alone"))
_SNAPSHOT_KEYS = frozenset((
    "schema", "total_native_seconds", "max_tool_calls", "entrant", "query_seconds",
    "whole_deadline", "started", "deadline", "grants", "remaining_seconds"))
_GRANT_KEYS = frozenset((
    "ordinal", "producer_seconds", "query_started", "query_deadline",
    "total_native_seconds", "remaining_seconds"))


class QueryBudgetError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _bad(code):
    raise QueryBudgetError(code)


def _integer(value, minimum, maximum, field):
    if type(value) is not int:
        _bad(field + "_type")
    if not minimum <= value <= maximum:
        _bad(field + "_range")
    return value


def _clock(value, field):
    # Check integer bounds before float conversion or math.isfinite, which can
    # otherwise raise OverflowError for a huge integer rather than refuse it.
    if type(value) is int:
        if not 0 <= value <= MAX_CLOCK:
            _bad(field + "_range")
        return float(value)
    if type(value) is not float:
        _bad(field + "_type")
    if not math.isfinite(value) or not 0 <= value <= MAX_CLOCK:
        _bad(field + "_range")
    return value


def _closed(value, keys, field):
    if type(value) is not dict or set(value) != keys:
        _bad(field + "_keys")


def _configuration(total_native_seconds, max_tool_calls, entrant, query_seconds,
                   whole_deadline):
    total = _integer(total_native_seconds, 1, MAX_SECONDS, "total_native_seconds")
    calls = _integer(max_tool_calls, 1, MAX_TOOL_CALLS, "max_tool_calls")
    seconds = _integer(query_seconds, 1, MAX_SECONDS, "query_seconds")
    if type(entrant) is not str or entrant not in ENTRANTS:
        _bad("entrant")
    if total < calls:
        _bad("total_below_common_call_cap")
    return {"total_native_seconds": total, "max_tool_calls": calls,
            "entrant": entrant, "query_seconds": seconds,
            "whole_deadline": _clock(whole_deadline, "whole_deadline")}


def _deadline(config, started):
    end = min(config["whole_deadline"], started + config["query_seconds"])
    end = _clock(end, "deadline")
    if end <= started:
        _bad("deadline_not_after_start")
    return end


def _call_limit(config):
    return config["max_tool_calls"] if config["entrant"] == "case_adaptive_equal_inputs_tools_compute" else 1


def _grant(config, started, deadline, ordinal, remaining):
    slots = _call_limit(config) - ordinal
    if slots <= 0:
        _bad("tool_call_limit")
    if remaining <= 0:
        _bad("native_seconds_exhausted")
    seconds = (remaining + slots - 1) // slots
    return {"ordinal": ordinal, "producer_seconds": seconds,
            "query_started": started, "query_deadline": deadline,
            "total_native_seconds": config["total_native_seconds"],
            "remaining_seconds": remaining - seconds}


class QueryBudget:
    """One serial query owner; reservations are committed before dispatch.

    total_native_seconds and max_tool_calls are the common comparison caps.
    Adaptive partitions that same total over its remaining permitted calls.
    Frozen-program and decoder-alone entrants have one internal native call,
    which receives the same full total; their recorded common cap is unchanged.

    The remaining native allocation is distinct from remaining wall time.
    Original query/whole deadlines constrain actual dispatch independently.
    """
    def __init__(self, total_native_seconds, max_tool_calls, entrant, query_seconds,
                 whole_deadline, started=None):
        self._config = _configuration(total_native_seconds, max_tool_calls, entrant,
                                      query_seconds, whole_deadline)
        observed = time.monotonic() if started is None else started
        self._started = _clock(observed, "started")
        self._deadline = _deadline(self._config, self._started)
        self._last_observed = self._started
        self._remaining = self._config["total_native_seconds"]
        self._grants = []

    @property
    def started(self):
        return self._started

    @property
    def deadline(self):
        return self._deadline

    @property
    def whole_deadline(self):
        return self._config["whole_deadline"]

    def tick(self):
        now = _clock(time.monotonic(), "observed_clock")
        if now < self._started or now < self._last_observed:
            _bad("clock_moved_backwards")
        self._last_observed = now
        if now >= self._config["whole_deadline"]:
            _bad("whole_deadline_exhausted")
        if now >= self._deadline:
            _bad("query_deadline_exhausted")
        return self._deadline - now

    def reserve(self):
        self.tick()
        grant = _grant(self._config, self._started, self._deadline,
                       len(self._grants), self._remaining)
        # Append and debit before returning a dispatchable grant. Returned dicts
        # are copies; downstream mutation cannot alter this ledger.
        self._grants.append(grant)
        self._remaining = grant["remaining_seconds"]
        return dict(grant)

    def snapshot(self):
        candidate = {"schema": SCHEMA, **self._config, "started": self._started,
                     "deadline": self._deadline,
                     "grants": [dict(item) for item in self._grants],
                     "remaining_seconds": self._remaining}
        # A complete bounded fold independently checks cumulative reservations.
        return replay(candidate, **self._config)


def replay(snapshot, *, total_native_seconds, max_tool_calls, entrant,
           query_seconds, whole_deadline):
    """Reconstruct the complete ledger without reading any clock.

    The outer verifier must bind snapshot.started to the independently recorded
    actor start. This pure function checks source/config/grant coherence; it does
    not attest that a recorded clock or dispatch actually occurred.
    """
    config = _configuration(total_native_seconds, max_tool_calls, entrant,
                            query_seconds, whole_deadline)
    _closed(snapshot, _SNAPSHOT_KEYS, "snapshot")
    if type(snapshot["schema"]) is not str or snapshot["schema"] != SCHEMA:
        _bad("snapshot_schema")
    recorded = _configuration(snapshot["total_native_seconds"], snapshot["max_tool_calls"],
                              snapshot["entrant"], snapshot["query_seconds"],
                              snapshot["whole_deadline"])
    if recorded != config:
        _bad("snapshot_configuration")
    started = _clock(snapshot["started"], "started")
    deadline = _deadline(config, started)
    if _clock(snapshot["deadline"], "deadline") != deadline:
        _bad("snapshot_deadline")
    grants = snapshot["grants"]
    if type(grants) is not list or len(grants) > _call_limit(config):
        _bad("snapshot_grants")
    remaining = config["total_native_seconds"]
    checked = []
    for ordinal, actual in enumerate(grants):
        _closed(actual, _GRANT_KEYS, "grant")
        normalized = {
            "ordinal": _integer(actual["ordinal"], 0, MAX_TOOL_CALLS - 1, "grant_ordinal"),
            "producer_seconds": _integer(actual["producer_seconds"], 1, MAX_SECONDS,
                                         "grant_producer_seconds"),
            "query_started": _clock(actual["query_started"], "grant_query_started"),
            "query_deadline": _clock(actual["query_deadline"], "grant_query_deadline"),
            "total_native_seconds": _integer(actual["total_native_seconds"], 1, MAX_SECONDS,
                                             "grant_total_native_seconds"),
            "remaining_seconds": _integer(actual["remaining_seconds"], 0, MAX_SECONDS,
                                          "grant_remaining_seconds")}
        expected = _grant(config, started, deadline, ordinal, remaining)
        if normalized != expected:
            _bad("grant_mismatch")
        checked.append(expected)
        remaining = expected["remaining_seconds"]
    if _integer(snapshot["remaining_seconds"], 0, MAX_SECONDS, "remaining_seconds") != remaining:
        _bad("snapshot_remaining")
    return {"schema": SCHEMA, **config, "started": started, "deadline": deadline,
            "grants": checked, "remaining_seconds": remaining}


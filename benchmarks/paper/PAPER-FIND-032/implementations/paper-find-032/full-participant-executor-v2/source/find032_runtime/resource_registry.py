"""Pure lifecycle state for the original complete FIND032 programme.

The concrete surviving parent's Journal is the sole effect seam. This module
never opens data, starts a process, controls Docker, or issues qualification.
"""
import hashlib
import json
import re

from .resource_journal import Journal


TASK = "PAPER-FIND-032"
CASES = 2
RESOURCE_COUNT = 6
MAX_EVENTS = 29
PROGRAMME_CAP = 1024
TRANSITION_CAP = 1024
ROLES = ("volume", "holder", "candidate")
ARMS = ("A", "B")


class RegistryError(ValueError):
    """A fixed, bounded lifecycle contract failed."""


def _need(condition, reason):
    if not condition:
        raise RegistryError(reason)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _keys(value, expected):
    _need(type(value) is dict and set(value) == set(expected), "exact-request-fields")


def _identity(value):
    _need(type(value) is list and len(value) == 1 and
          type(value[0]) is str and value[0] in ARMS, "fixed-whole132-arm")
    return (value[0],)


class Registry:
    """One parent-owned session; no lifecycle request is retried or replayed.

    State precedes the durable append. A publication failure leaves that exact
    possible effect and original exception in memory, and poisons dispatch.
    Recovery reads are permitted; they never rewrite an unsuccessful history.
    """

    def __init__(self, journal, session):
        _need(type(journal) is Journal, "original-concrete-journal")
        _need(type(session) is str and re.fullmatch("[0-9a-f]{24}", session) is not None,
              "original-parent-session")
        self.journal = journal
        self.session = session
        self._identities = None
        self._active = None
        self._finished = 0
        self._role_cursor = 0
        self._rows = {}
        self._names = set()
        self._event_count = 0
        self._durable_count = 0
        self._append_returns = []
        self._last_record = None
        self._errors = []
        self._first_error = None
        self._poisoned = False
        self._dispatching = False
        self._failed_closure = False

    def _poison(self, error):
        self._poisoned = True
        if self._first_error is None:
            self._first_error = error
        if not any(original is error for original in self._errors):
            self._errors.append(error)

    def _record(self, op, **fields):
        _need(self._event_count < MAX_EVENTS, "complete-event-bound")
        record = {"schema": "find032_resource_transition_v1", "task_id": TASK,
                  "session": self.session, "sequence": self._event_count,
                  "op": op, **fields}
        limit = PROGRAMME_CAP if op == "programme" else TRANSITION_CAP
        _need(len(_encoded(record)) <= limit, "original-record-extent")
        return record

    def _append(self, record):
        # The corresponding state mutation has already happened. In particular,
        # attempted=True is never rolled back after an uncertain append return.
        self._last_record = record
        self._event_count += 1
        result = self.journal.append(record)
        self._append_returns.append(result)  # original before any projection
        _need(type(result) is dict and set(result) ==
              {"bytes", "sha256", "offset", "sequence"}, "original-append-result")
        limit = PROGRAMME_CAP if record["op"] == "programme" else TRANSITION_CAP
        _need(type(result["bytes"]) is int and 0 < result["bytes"] <= limit + 64 and
              type(result["offset"]) is int and result["offset"] >= 0 and
              type(result["sequence"]) is int and
              result["sequence"] == record["sequence"] and
              type(result["sha256"]) is str and
              re.fullmatch("[0-9a-f]{64}", result["sha256"]) is not None,
              "bounded-original-append-result")
        if self._poisoned:
            raise self._first_error
        self._durable_count += 1

    def _current(self, index):
        _need(type(index) is int and 0 <= index < CASES and
              self._active == index, "original-active-case")

    def _row(self, index, role):
        self._current(index)
        _need(type(role) is str and role in ROLES and (index, role) in self._rows,
              "original-reserved-resource")
        return self._rows[index, role]

    def dispatch(self, request):
        """Admit one exact fixed lifecycle request; return only after append."""
        if self._poisoned:
            raise self._first_error
        if self._dispatching:
            error = RegistryError("registry-reentrant-dispatch")
            self._poison(error)
            raise error
        self._dispatching = True
        try:
            _need(type(request) is dict and type(request.get("op")) is str,
                  "typed-lifecycle-request")
            op = request["op"]
            fields = {
                "programme": {"op", "identities"},
                "begin": {"op", "index", "identity"},
                "reserve": {"op", "index", "role"},
                "attempt": {"op", "index", "role"},
                "ack": {"op", "index", "role", "identifier"},
                "close": {"op", "index", "role", "result"},
                "finish": {"op", "index"},
            }
            _need(op in fields, "fixed-lifecycle-operation")
            _keys(request, fields[op])
            _need(not self._failed_closure or op == "close",
                  "failed-closure-blocks-new-work")
            # Each method validates finite field shapes before JSON encoding.
            if op == "programme":
                return self._programme(request)
            if op == "begin":
                return self._begin(request)
            if op == "reserve":
                return self._reserve(request)
            if op == "attempt":
                return self._attempt(request)
            if op == "ack":
                return self._ack(request)
            if op == "close":
                return self._close(request)
            return self._finish(request)
        except BaseException as error:
            self._poison(error)
            raise
        finally:
            self._dispatching = False

    def _programme(self, request):
        _need(self._identities is None and self._event_count == 0, "programme-once")
        values = request["identities"]
        _need(type(values) is list and len(values) == CASES, "complete-two-whole132-programme-identities")
        identities = tuple(_identity(value) for value in values)
        _need(identities == tuple((arm,) for arm in ARMS), "original-whole-programme-arm-order")
        # Also bound every eventual begin before accepting the programme.
        for index, identity in enumerate(identities):
            prospective = {"schema": "find032_resource_transition_v1", "task_id": TASK,
                           "session": self.session, "sequence": MAX_EVENTS - 1,
                           "op": "begin", "index": index, "identity": list(identity)}
            _need(len(_encoded(prospective)) <= TRANSITION_CAP, "full-begin-extent")
        record = self._record("programme", identities=[list(x) for x in identities])
        self._identities = identities
        self._append(record)
        return {"op": "programme", "cases": CASES, "resources": RESOURCE_COUNT,
                "maximum_events": MAX_EVENTS}

    def _begin(self, request):
        index = request["index"]
        _need(self._identities is not None and self._active is None and
              type(index) is int and index == self._finished and index < CASES,
              "next-original-case-once")
        identity = _identity(request["identity"])
        _need(identity == self._identities[index], "exact-programme-identity")
        record = self._record("begin", index=index, identity=list(identity))
        self._active = index
        self._role_cursor = 0
        self._append(record)
        return {"op": "begin", "index": index}

    def _reserve(self, request):
        index, role = request["index"], request["role"]
        self._current(index)
        _need(type(role) is str and self._role_cursor < len(ROLES) and
              role == ROLES[self._role_cursor] and (index, role) not in self._rows,
              "next-original-resource-role-once")
        _need(len(self._rows) < RESOURCE_COUNT, "complete-resource-bound")
        token = hashlib.sha256(_encoded([self.session, index, role])).hexdigest()[:24]
        prefix = "slicetca-" + token
        kind = "volume" if role == "volume" else "container"
        name = prefix + ("-volume" if kind == "volume" else "-" + role)
        _need(name not in self._names, "unique-original-resource-name")
        resource = {"case_index": index, "role": role, "kind": kind,
                    "name": name, "owner": prefix + "/" + role,
                    "attempted": False, "acknowledged": False}
        record = self._record("reserve", index=index, role=role,
                              resource=dict(resource))
        self._rows[index, role] = {"resource": resource, "close_seen": False,
                                  "closed": False, "closure": None}
        self._names.add(name)
        self._role_cursor += 1
        self._append(record)
        return dict(resource)

    def _attempt(self, request):
        index, role = request["index"], request["role"]
        row = self._row(index, role)
        resource = row["resource"]
        _need(not row["close_seen"] and resource["attempted"] is False and
              resource["acknowledged"] is False, "original-create-attempt-once")
        changed = dict(resource, attempted=True)
        record = self._record("attempt", index=index, role=role, resource=changed)
        resource["attempted"] = True
        self._append(record)
        return dict(resource)

    def _ack(self, request):
        index, role, identifier = request["index"], request["role"], request["identifier"]
        row = self._row(index, role)
        resource = row["resource"]
        _need(not row["close_seen"] and resource["attempted"] is True and
              resource["acknowledged"] is False, "attempt-before-one-acknowledgment")
        _need(type(identifier) is str, "returned-create-identifier")
        changed = dict(resource, acknowledged=True)
        if resource["kind"] == "container":
            _need(re.fullmatch("[0-9a-f]{64}", identifier) is not None,
                  "original-container-id")
            changed["id"] = identifier
        else:
            _need(identifier == resource["name"], "original-volume-acknowledgment")
        record = self._record("ack", index=index, role=role, resource=changed,
                              identifier=identifier)
        resource.update(changed)
        self._append(record)
        return dict(resource)

    def _closure(self, value, resource):
        _need(type(value) is dict and type(value.get("kind")) is str and
              type(value.get("name")) is str and value.get("kind") == resource["kind"] and
              value.get("name") == resource["name"], "exact-original-retirement-resource")
        if set(value) == {"kind", "name", "closed", "error_type"}:
            _need(value["closed"] is False and type(value["error_type"]) is str and
                  re.fullmatch("[A-Za-z_][A-Za-z0-9_]{0,127}", value["error_type"]) is not None,
                  "failed-original-retirement")
            return dict(value)
        if resource["attempted"] is False:
            fields = {"kind", "name", "create_not_attempted", "collision_preserved",
                      "observed_namespace_empty", "removed", "closed"}
            _keys(value, fields)
            _need(all(type(value[k]) is bool for k in fields - {"kind", "name"}) and
                  value["create_not_attempted"] is True and value["removed"] is False and
                  value["collision_preserved"] is not value["observed_namespace_empty"] and
                  value["closed"] is value["observed_namespace_empty"],
                  "original-not-attempted-retirement")
        else:
            fields = {"kind", "name", "removed", "absence_observed",
                      "creation_outcome_unknown", "closed"}
            _keys(value, fields)
            _need(all(type(value[k]) is bool for k in fields - {"kind", "name"}),
                  "typed-original-retirement")
            unknown = not resource["acknowledged"] and not value["removed"]
            _need(value["creation_outcome_unknown"] is unknown and
                  value["closed"] is (value["absence_observed"] and not unknown),
                  "unchanged-unacknowledged-creation-uncertainty")
        return dict(value)

    def _close(self, request):
        index, role = request["index"], request["role"]
        row = self._row(index, role)
        _need(not row["close_seen"], "one-original-retirement-observation")
        closure = self._closure(request["result"], row["resource"])
        record = self._record("close", index=index, role=role,
                              resource=dict(row["resource"]), result=closure)
        row["close_seen"] = True
        row["closure"] = closure
        row["closed"] = closure["closed"]
        self._failed_closure = self._failed_closure or not row["closed"]
        self._append(record)
        return dict(closure)

    def _finish(self, request):
        index = request["index"]
        self._current(index)
        _need(self._role_cursor == len(ROLES), "all-three-original-resource-roles")
        rows = [self._rows[index, role] for role in ROLES]
        _need(all(row["resource"]["attempted"] is True and
                  row["resource"]["acknowledged"] is True and
                  row["close_seen"] is True and row["closed"] is True for row in rows),
              "all-original-created-resources-closed")
        record = self._record("finish", index=index)
        self._finished += 1
        self._active = None
        self._append(record)
        return {"op": "finish", "index": index}

    def recovery_rows(self):
        """Copies of every known not-closed obligation, including partial append."""
        return tuple(dict(row["resource"]) for row in self._rows.values()
                     if row["closed"] is not True)

    def natural_complete(self):
        """Lifecycle completion only; never scientific or external-exit admission."""
        return (not self._poisoned and not self._failed_closure and
                self._identities is not None and self._finished == CASES and
                self._active is None and len(self._rows) == RESOURCE_COUNT and
                self._event_count == self._durable_count == MAX_EVENTS and
                all(row["close_seen"] is True and row["closed"] is True and
                    row["resource"]["attempted"] is True and
                    row["resource"]["acknowledged"] is True
                    for row in self._rows.values()))

    def snapshot(self):
        """Finite original state, retaining exception objects without stringifying.

        This object is deliberately not a JSON evidence receipt. The parent's
        concrete journal owns original bytes, errors and publication authority.
        """
        return {"schema": "find032_resource_registry_snapshot_v1", "task_id": TASK,
                "session": self.session, "identities": self._identities,
                "active_case": self._active, "finished_cases": self._finished,
                "event_attempts": self._event_count, "durable_events": self._durable_count,
                "poisoned": self._poisoned, "failed_closure": self._failed_closure,
                "first_error": self._first_error, "errors": tuple(self._errors),
                "append_returns": tuple(self._append_returns),
                "last_record": self._last_record,
                "resources": tuple({"resource": dict(row["resource"]),
                                    "close_seen": row["close_seen"], "closed": row["closed"],
                                    "closure": None if row["closure"] is None else
                                    dict(row["closure"])} for row in self._rows.values()),
                "natural_lifecycle_complete": self.natural_complete()}

"""Full private study graph and chronological candidate phase state.

No arrays, files, model calls or provider connections are accessed here. All
record identities remain trusted-host data; public exports are separate.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import hmac
from typing import Iterable, Mapping
from .custody import CustodyError, canonical, digest, require_digest

CONDITIONS = ("original", "spatial_scrambled", "C_only")
ARMS = ("F", "I")
REPETITIONS = (0, 1, 2)
FAMILIES = ("ridge", "linear_ovr_svm", "rbf_ovr_svm", "extra_trees", "centroid")
PEOPLE = ("sub-01", "sub-02", "sub-04", "sub-05", "sub-06", "sub-07", "sub-08",
          "sub-09", "sub-11", "sub-12", "sub-13", "sub-14", "sub-15")


@dataclass(frozen=True)
class PrivateRecord:
    case_id: str
    person: str
    label: int
    construction: str

    def __post_init__(self):
        if not self.case_id or not isinstance(self.case_id, str) or not isinstance(self.person, str):
            raise CustodyError("record identity")
        if type(self.label) is not int or not 0 <= self.label < 25:
            raise CustodyError("record label")
        if self.construction not in ("AP", "PA", "FFX"):
            raise CustodyError("construction must be explicitly normalized by admission")

    def to_dict(self):
        return {"case_id": self.case_id, "person": self.person,
                "label": self.label, "construction": self.construction}


@dataclass(frozen=True)
class CandidateContext:
    context_id: str
    outer_person: str
    condition: str
    arm: str
    repetition: int
    reference_context_id: str

    def private_dict(self):
        return {"context_id": self.context_id, "outer_person": self.outer_person,
                "condition": self.condition, "arm": self.arm,
                "repetition": self.repetition,
                "reference_context_id": self.reference_context_id}

    @property
    def binding_digest(self):
        return digest(self.private_dict())

    def public_dict(self):
        # No public pseudonym, phase, counts-by-class, source IDs or source ordering.
        return {"context_id": self.context_id, "condition": self.condition,
                "arm": self.arm, "repetition": self.repetition}


@dataclass(frozen=True)
class Fold:
    outer_person: str
    training_people: tuple[str, ...]
    query_ids: tuple[str, ...]
    training_ids: tuple[str, ...]

    def inner_people(self):
        for validation_person in self.training_people:
            yield validation_person, tuple(p for p in self.training_people if p != validation_person)


class StudyPlan:
    def __init__(self, records: Iterable[PrivateRecord], *, assessment_digest: str,
                 source_contract_digest: str, context_key: bytes, domain: str):
        if domain not in ("invented", "authentic"):
            raise CustodyError("explicit study domain")
        if not isinstance(context_key, bytes) or len(context_key) < 32:
            raise CustodyError("private context key at least256 bits")
        self.records = tuple(records)
        if not self.records or any(not isinstance(x, PrivateRecord) for x in self.records):
            raise CustodyError("explicit private records required")
        self._by_id = {r.case_id: r for r in self.records}
        if len(self._by_id) != len(self.records):
            raise CustodyError("duplicate private record IDs")
        self.domain = domain
        self.assessment_digest = require_digest(assessment_digest)
        self.source_contract_digest = require_digest(source_contract_digest)
        self.people = tuple(sorted({x.person for x in self.records}))
        cells = {(x.person, x.label) for x in self.records}
        if domain == "authentic":
            if len(self.records) != 9532 or self.people != PEOPLE or len(cells) != 300:
                raise CustodyError("full original source support is required")
            if {r.label for r in self.records} != set(range(25)):
                raise CustodyError("all25 labels required")
            if {p: sum(1 for q,c in cells if q == p) for p in self.people} != {
                p: (12 if p == "sub-02" else 13 if p == "sub-08" else 25) for p in PEOPLE}:
                raise CustodyError("frozen available-cell support mismatch")
        elif len(self.people) < 3:
            raise CustodyError("invented fold control needs at least3 people")
        self.record_digest = digest([r.to_dict() for r in self.records])
        self.binding_digest = digest({"domain": domain, "records": self.record_digest,
            "assessment": self.assessment_digest, "source_contract": self.source_contract_digest})
        self._context_key = bytes(context_key)

    def records_for(self, people: Iterable[str]):
        allowed = frozenset(people)
        if not allowed <= frozenset(self.people):
            raise CustodyError("unknown person in fold")
        return tuple(r for r in self.records if r.person in allowed)

    def fold(self, outer_person: str):
        if outer_person not in self.people:
            raise CustodyError("unknown held person")
        train = tuple(p for p in self.people if p != outer_person)
        return Fold(outer_person, train,
                    tuple(r.case_id for r in self.records_for((outer_person,))),
                    tuple(r.case_id for r in self.records_for(train)))

    def folds(self):
        return tuple(self.fold(person) for person in self.people)

    def _opaque(self, payload):
        return hmac.new(self._context_key, canonical([self.binding_digest, payload]), hashlib.sha256).hexdigest()

    def contexts(self):
        result = []
        for person in self.people:
            for condition in CONDITIONS:
                reference_id = self._opaque(["reference", person, condition])
                for arm in ARMS:
                    for repetition in REPETITIONS:
                        context_id = self._opaque(["candidate", person, condition, arm, repetition])
                        result.append(CandidateContext(context_id, person, condition, arm, repetition, reference_id))
        if self.domain == "authentic" and len(result) != 234:
            raise CustodyError("complete234-context graph required")
        return tuple(result)

    def assert_complete_closure(self, closures: Mapping[str, str]):
        expected = {c.context_id for c in self.contexts()}
        if set(closures) != expected:
            raise CustodyError("scoring requires all contexts, including failures")
        for value in closures.values():
            require_digest(value)
        return digest({"plan": self.binding_digest,
                       "closures": dict(sorted(closures.items()))})

    def structural_work(self, grid_blocks):
        # This is plan arithmetic, never evidence that a fit or prediction ran.
        expected_views = {"original": ("N", "C", "NC"),
                          "spatial_scrambled": ("N", "C", "NC"), "C_only": ("C",)}
        seen = set()
        H = 0
        for b in grid_blocks:
            k = (b["condition"], b["view"], b["family"])
            if k in seen or k[0] not in expected_views or k[1] not in expected_views[k[0]] or k[2] not in FAMILIES:
                raise CustodyError("grid block identity")
            seen.add(k)
            if b["H"] != len(b["configurations"]):
                raise CustodyError("grid cell count")
            H += b["H"]
        if len(seen) != 35 or H != 353:
            raise CustodyError("full353-cell35-block graph required")
        S, N = len(self.people), len(self.records)
        return {"domain": self.domain, "records": N, "people": S, "blocks":35,
                "H": H, "inner_fit_bundles": S*(S-1)*H,
                "outer_fit_bundles": S*35, "calibrators": S*35,
                "PCA_fits": S*S*2*4,
                "candidate_contexts": S*3*2*3,
                "candidate_case_vectors": 3*2*3*N,
                "scientific_runs_observed": 0}


@dataclass
class ContextState:
    """Trusted chronological state. Candidate feedback remains closed until all cells close."""
    context: CandidateContext
    state: str = "allocated"
    program_digest: str | None = None
    prediction_digest: str | None = None
    failure: str | None = None
    events: list = field(default_factory=list)

    def _event(self, action, binding):
        require_digest(binding)
        previous = self.events[-1]["event_digest"] if self.events else "0"*64
        entry = {"context": self.context.context_id, "index":len(self.events),
                 "state":self.state, "action":action, "binding":binding, "previous":previous}
        entry["event_digest"] = digest(entry)
        self.events.append(entry)

    def prepare(self, training_export_digest, eligible_models_digest):
        if self.state != "allocated":
            raise CustodyError("prepare only once")
        require_digest(training_export_digest); require_digest(eligible_models_digest)
        self.state = "prepared"
        self._event("prepare", digest([training_export_digest, eligible_models_digest]))

    def begin_authoring(self, policy_digest):
        if self.state != "prepared":
            raise CustodyError("authoring order")
        self.state = "authoring"
        self._event("authoring", policy_digest)

    def allow_model_call(self):
        if self.state == "authoring" or (self.state == "query_open" and self.context.arm == "I"):
            return
        raise CustodyError("language-model call forbidden in this phase")

    def seal_program(self, program_digest):
        if self.context.arm != "F" or self.state != "authoring":
            raise CustodyError("only F seals before query")
        self.program_digest = require_digest(program_digest)
        self.state = "sealed"
        self._event("seal", program_digest)

    def open_query(self, query_export_digest):
        if self.context.arm == "F" and (self.state != "sealed" or self.program_digest is None):
            raise CustodyError("F must freeze before query")
        if self.context.arm == "I" and self.state != "authoring":
            raise CustodyError("I query order")
        self.state = "query_open"
        self._event("query", query_export_digest)

    def submit(self, prediction_digest, *, failure=None):
        if self.state != "query_open":
            raise CustodyError("submission requires query phase")
        self.prediction_digest = require_digest(prediction_digest)
        if failure is not None and (not isinstance(failure,str) or not failure):
            raise CustodyError("failure must be explicit")
        self.failure = failure
        self.state = "submitted"
        self._event("submit", prediction_digest)

    def close(self, resource_receipt_digest):
        if self.state != "submitted":
            raise CustodyError("close order")
        self.state = "closed"
        self._event("close", resource_receipt_digest)
        return digest({"context":self.context.binding_digest, "program":self.program_digest,
                       "prediction":self.prediction_digest, "failure":self.failure,
                       "events":self.events})

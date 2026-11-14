"""Explicit metadata contracts; these records do not confer input custody."""
from dataclasses import dataclass
import math
from .catalogue import DECLARED_ENDPOINTS, DECLARED_PEOPLE


class ContractError(ValueError):
    pass


class UnqualifiedInput(ContractError):
    pass


@dataclass(frozen=True)
class SelectedEvaluationSupport:
    """External authority's immutable selection, not an issued credential.

    The implementation of independent support authentication is absent. This
    record only defines the receipt that the real evaluator must consume.
    """
    selection_identity: str
    protocol_identity: str
    taxonomy_identity: str
    eligibility_identity: str
    support_identity: str
    map_length: int
    dtype: str

    def validate(self):
        require(all(type(v) is str and bool(v.strip()) for v in
                    (self.selection_identity, self.protocol_identity,
                     self.taxonomy_identity, self.eligibility_identity,
                     self.support_identity)), 'Unresolved evaluator support selection')
        require(type(self.map_length) is int and self.map_length > 1,
                'Invalid selected evaluator map length')
        require(type(self.dtype) is str and self.dtype == '<f8',
                'Evaluator requires one-dimensional little-endian float64 maps')
        return self


class UnissuedSupportAuthority:
    """Explicit hold until a separately authenticated support owner is supplied."""
    def authenticate_selected_support(self):
        raise UnqualifiedInput('Independent selected-support issuer is unimplemented')


def require(condition, message):
    if not condition:
        raise ContractError(message)


def unique(values, name):
    values = tuple(values)
    require(bool(values) and len(set(values)) == len(values), name + ' must be nonempty and unique')
    return values


def positive(value, name, zero=False):
    require(type(value) in (int, float) and math.isfinite(value), name + ' must be finite')
    require(value >= 0 if zero else value > 0, name + ' is outside its declared domain')


@dataclass(frozen=True)
class Endpoint:
    identity: str
    task: str
    contrast: str
    family: str
    dependency_group: str

    def validate(self):
        require(all(type(x) is str and bool(x) for x in (self.identity, self.task, self.contrast, self.family, self.dependency_group)),
                'Unresolved endpoint/family/dependency metadata')


@dataclass(frozen=True)
class Design:
    endpoint: str
    text: str
    coefficients: tuple
    provenance: str

    def validate(self):
        require(type(self.text) is str and bool(self.text.strip()), 'Missing declared design description')
        require(type(self.provenance) is str and bool(self.provenance), 'Missing design provenance')
        require(type(self.coefficients) is tuple and all(type(row) is tuple and len(row) == 2 for row in self.coefficients),
                'Design coefficients must be immutable named pairs')
        names = [row[0] for row in self.coefficients]
        require(len(names) == len(set(names)), 'Duplicate design coefficient')
        for name, value in self.coefficients:
            require(type(name) is str and bool(name), 'Invalid design coefficient identity')
            require(type(value) in (int, float) and math.isfinite(value), 'Nonfinite design coefficient')


@dataclass(frozen=True)
class Case:
    person: str
    endpoint: str
    status: str
    reason: str
    source_identity: str | None

    def validate(self):
        require(self.status in ('present', 'absent', 'ambiguous', 'unestablished'), 'Unknown case disposition')
        require(bool(self.reason), 'Every case requires a disposition reason')
        require(bool(self.source_identity) if self.status == 'present' else self.source_identity is None,
                'Only a present case may carry an admitted source identity')


@dataclass(frozen=True)
class Population:
    people: tuple
    endpoints: tuple
    cases: tuple
    declaration_pin: str
    taxonomy_pin: str
    eligibility_pin: str

    def validate(self):
        require(all(type(v) is tuple for v in (self.people, self.endpoints, self.cases)), 'Population collections must be immutable tuples')
        require(all(type(e) is Endpoint for e in self.endpoints) and all(type(c) is Case for c in self.cases),
                'Population rows must use the exact immutable source contracts')
        people = unique(self.people, 'people')
        ids = unique((e.identity for e in self.endpoints), 'endpoints')
        require(len(ids) == 51 and len({e.task for e in self.endpoints}) == 12,
                'P1 must account for all 51 declarations and 12 tasks')
        require(set(people) == set(DECLARED_PEOPLE), 'Planned first-release population differs from the selected declaration')
        require({(e.identity, e.task, e.contrast) for e in self.endpoints} == set(DECLARED_ENDPOINTS),
                'Endpoint identities differ from the complete selected method catalogue')
        require(bool(self.declaration_pin) and bool(self.taxonomy_pin) and bool(self.eligibility_pin),
                'Missing declaration/taxonomy/eligibility selection')
        for e in self.endpoints:
            e.validate()
        groups = {}
        for e in self.endpoints:
            groups.setdefault(e.dependency_group, set()).add(e.family)
        require(all(len(v) == 1 for v in groups.values()), 'A dependent contrast group crosses family holdouts')
        keys = [(c.person, c.endpoint) for c in self.cases]
        require(len(keys) == len(set(keys)), 'Duplicate person/endpoint disposition')
        require(set(keys) == {(p, e) for p in people for e in ids}, 'Missing or extra planned case disposition')
        for c in self.cases:
            c.validate()
        return self


@dataclass(frozen=True)
class FitConfig:
    rank: int
    component_penalty: float
    ridge_penalty: float
    max_iterations: int
    relative_tolerance: float

    def validate(self):
        require(type(self.rank) is int and self.rank > 0, 'Invalid declared rank')
        positive(self.component_penalty, 'component penalty', zero=True)
        positive(self.ridge_penalty, 'ridge penalty')
        require(type(self.max_iterations) is int and self.max_iterations > 0, 'Invalid iteration bound')
        positive(self.relative_tolerance, 'relative tolerance')
        return self


@dataclass(frozen=True)
class Protocol:
    configurations: tuple
    tuning_metric: str
    spatial_support_identity: str
    selection_identity: str
    max_fits: int

    def validate(self):
        require(type(self.configurations) is tuple and all(type(c) is FitConfig for c in self.configurations),
                'Configurations must be exact immutable source records')
        unique(self.configurations, 'configurations')
        for c in self.configurations:
            c.validate()
        require(self.tuning_metric in ('mean_squared_error', 'map_correlation'), 'Unselected tuning metric')
        require(bool(self.spatial_support_identity) and bool(self.selection_identity), 'Missing selected support/protocol identity')
        require(type(self.max_fits) is int and self.max_fits > 0, 'Missing whole-programme fit limit')
        return self

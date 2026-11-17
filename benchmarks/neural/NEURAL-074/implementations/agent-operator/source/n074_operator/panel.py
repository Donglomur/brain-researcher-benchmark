"""Whole-panel preflight and a distinct arbitrary-agent descriptive comparison.

No statistic claims population inference, original-method parity or SOTA. The
three fixed algorithms remain a separate exact ProgrammeResult throughout.
"""
from dataclasses import dataclass
import hashlib
import math
from n074.evaluation import _preflight, _map_envelope, result_digest
from n074.models import ARMS
from n074.metrics import map_quantities
from n074.splits import outer_folds
from .candidate import (CandidatePanel, AgentPrediction, finite_map, validate_receipt,
                         validate_policy, fold_document, content_pin, identity)
from .host_contract import Programme, FoldRequest, OwnerReceipt
from .owned_io import Pin, require, text, json_bytes


class SelectionAuthority:
    """Only a trusted frozen selection, not a new credential or target capability."""
    def __init__(self, selection):
        self.selection = selection

    def authenticate_selected_support(self):
        return self.selection.support


def preflight(selection, candidate, references, programme, policy, authority):
    """Authenticate COMPLETE candidate and fixed-reference sets before any target."""
    validate_policy(policy)
    require(type(candidate) is CandidatePanel and type(programme) is Programme,
            'Exact candidate panel and independently selected submission')
    require(candidate.completion == 'complete_source_attempt', 'Aborted candidate panel cannot be evaluated')
    require((candidate.selection_identity, candidate.programme_identity, candidate.policy_identity) ==
            (selection.identity, programme.identity, policy.identity), 'Candidate selection/submission/policy differs')
    require(type(candidate.predictions) is tuple and type(candidate.receipts) is tuple,
            'Candidate collections must be immutable')
    # This existing check preserves the exact three-arm reference envelope.
    reference_lookup, endpoints = _preflight(references, result_digest(references),
        selection.population, selection.maximum_map_bytes, selection.support.support_identity,
        selection.support.map_length, authority)
    folds = {(f.held_person, f.held_family): f for f in outer_folds(selection.population)}
    cases = {(c.person, c.endpoint): c for c in selection.population.cases}
    receipt_lookup, seen = {}, set()
    for pair in candidate.receipts:
        require(type(pair) is tuple and len(pair) == 2, 'Exact immutable request/receipt pair')
        request, receipt = pair
        require(type(request) is FoldRequest and type(receipt) is OwnerReceipt, 'Exact owned host contracts')
        key = (request.held_person, request.held_family)
        require(key in folds and key not in receipt_lookup and folds[key].eligible, 'Unexpected or duplicate native fold')
        fold = folds[key]
        require(request.selection_identity == selection.identity and request.programme_identity == programme.identity and
                request.query_endpoints == fold.query_endpoints and request.map_length == selection.support.map_length,
                'Native request changed the selected fold/query geometry')
        require(type(request.inputs) is tuple and type(request.input_manifest) is Pin and
                all(type(r) is tuple and len(r) == 2 and type(r[0]) is str and type(r[1]) is Pin
                    for r in request.inputs), 'Exact immutable input carrier roster')
        require(len({r[0] for r in request.inputs}) == len(request.inputs) and
                ('fold.json', request.input_manifest) in request.inputs, 'Complete unique manifest identity')
        require(len(request.inputs) == len(fold.training_people) * len(fold.training_endpoints) + 1 and
                sum(r[1].bytes for r in request.inputs) <= policy.maximum_input_bytes,
                'Native input carrier count/extent differs from full fold')
        for _, pin in request.inputs:
            pin.validate()
        descriptors = {(r.person, r.endpoint): r.pin for r in selection.maps}
        manifest_pin = content_pin(json_bytes(fold_document(selection, fold), policy.maximum_metadata_bytes))
        expected_inputs = tuple(('train-%06d.f64' % index, descriptors[p, e])
            for index, (p, e) in enumerate((p, e) for p in fold.training_people for e in fold.training_endpoints))
        expected_inputs += (('fold.json', manifest_pin),)
        require(request.input_manifest == manifest_pin and request.inputs == expected_inputs,
                'Native inputs do not match the exact independently selected fold maps/designs')
        expected_identity = identity({'selection': selection.identity, 'person': fold.held_person,
            'family': fold.held_family, 'input_manifest': manifest_pin.document(),
            'inputs': [(name, pin.document()) for name, pin in expected_inputs]})
        require(request.identity == expected_identity, 'Native fold content identity mismatch')
        validate_receipt(receipt, request, programme, policy, seen)
        receipt_lookup[key] = (request, receipt)
    require(set(receipt_lookup) == {key for key, fold in folds.items() if fold.eligible},
            'Missing native disposition for a declared eligible fold')
    lookup = {}
    for row in candidate.predictions:
        require(type(row) is AgentPrediction, 'Exact immutable arbitrary-candidate prediction')
        key = (row.person, row.endpoint)
        require(key in cases and key not in lookup, 'Unknown or duplicate candidate case')
        require(row.family == endpoints[row.endpoint].family, 'Candidate family changed')
        fold = folds[row.person, row.family]
        if not fold.eligible:
            require(row.status == 'ineligible_support' and row.value is None and type(row.reason) is str and bool(row.reason),
                    'Ineligible full-support disposition must be retained')
        elif receipt_lookup[row.person, row.family][1].status != 'completed':
            require(row.status == 'candidate_failed' and row.value is None and type(row.reason) is str and bool(row.reason),
                    'Failed owner disposition cannot supply a partial prediction')
        else:
            require(row.status == 'predicted' and row.reason is None and cases[key].status == 'present',
                    'Completed owner must supply every selected query prediction')
            _map_envelope(row.value, 'P1_AGENT:' + row.person + ':' + row.endpoint,
                          selection.support.support_identity, selection.support.map_length, selection.maximum_map_bytes)
        lookup[key] = row
    require(set(lookup) == set(cases), 'Complete arbitrary candidate roster required')
    for key, (request, receipt) in receipt_lookup.items():
        if receipt.status == 'completed':
            digest = hashlib.sha256()
            extent = 0
            for endpoint in request.query_endpoints:
                raw = lookup[request.held_person, endpoint].value.values
                digest.update(raw); extent += len(raw)
            require((extent, digest.hexdigest()) == (receipt.output.bytes, receipt.output.sha256),
                    'Committed candidate maps differ from the closed native output')
    # Do not postpone validation of a late row until after earlier targets.
    for row in candidate.predictions + references.predictions:
        if row.value is not None:
            finite_map(row.value.values)
    return lookup, reference_lookup, endpoints


@dataclass(frozen=True)
class Comparison:
    person: str
    family: str
    endpoint: str
    status: str
    metrics: tuple
    effects: tuple
    reason: str | None


def evaluate(selection, candidate, references, programme, policy, protected_owner):
    """The caller must first load an independently pinned closed COMMIT carrier.

    This low-level function is intentionally not the public packet entry point.
    It never calls a candidate owner, training model or untrusted callback after
    the first protected target. All prediction arrays decode before ANY target.
    """
    candidate_rows, reference_rows, endpoints = preflight(selection, candidate, references,
                                                         programme, policy, protected_owner)
    decoded_candidate = {k: row.value.array('P1_AGENT:' + row.person + ':' + row.endpoint,
        selection.support.support_identity, selection.maximum_map_bytes)
        for k, row in candidate_rows.items() if row.status == 'predicted'}
    decoded_reference = {k: row.value.array('P1:' + row.person + ':' + row.endpoint + ':' + row.arm,
        selection.support.support_identity, selection.maximum_map_bytes)
        for k, row in reference_rows.items() if row.status == 'predicted'}
    result = []
    for case in selection.population.cases:
        key = (case.person, case.endpoint)
        agent = candidate_rows[key]
        refs = [reference_rows[case.person, case.endpoint, arm] for arm in ARMS]
        family = endpoints[case.endpoint].family
        if case.status != 'present' or agent.status != 'predicted' or any(r.status != 'predicted' for r in refs):
            result.append(Comparison(case.person, family, case.endpoint, 'unpaired_support', (), (),
                                     'Candidate, all fixed algorithms and target require the same complete support'))
            continue
        try:
            target = protected_owner.read_protected_target(case.person, case.endpoint, case.source_identity)
            _map_envelope(target, case.source_identity, selection.support.support_identity,
                          selection.support.map_length, selection.maximum_map_bytes)
            values = target.array(case.source_identity, selection.support.support_identity, selection.maximum_map_bytes)
            metrics = {'agent': map_quantities(decoded_candidate[key], values)}
            for arm in ARMS:
                metrics[arm] = map_quantities(decoded_reference[case.person, case.endpoint, arm], values)
            effects = []
            for arm in ARMS:
                for metric, direction in (('map_correlation', 1), ('mean_squared_error', -1), ('mean_absolute_error', -1)):
                    a, b = metrics['agent'][metric], metrics[arm][metric]
                    value = None if a is None or b is None else direction * (a - b)
                    if value is not None and not math.isfinite(value):
                        value = None
                    effects.append((arm, metric, value))
            result.append(Comparison(case.person, family, case.endpoint, 'paired',
                tuple((arm, tuple(sorted(metrics[arm].items()))) for arm in ('agent',) + ARMS), tuple(effects), None))
        except Exception as error:
            result.append(Comparison(case.person, family, case.endpoint, 'target_or_score_failed', (), (), type(error).__name__))
    return tuple(result)


def summarize(comparisons, population):
    """All declared conditions/families/people remain in the finite-panel denominator."""
    population.validate()
    expected = {(c.person, c.endpoint) for c in population.cases}
    require(len(comparisons) == len(expected) and {(c.person, c.endpoint) for c in comparisons} == expected,
            'Complete unique comparison roster required')
    endpoint_family = {e.identity: e.family for e in population.endpoints}
    require(all(c.family == endpoint_family[c.endpoint] for c in comparisons), 'Comparison family changed')
    families = tuple(dict.fromkeys(e.family for e in population.endpoints))
    effects = []
    for arm in ARMS:
        for metric in ('map_correlation', 'mean_squared_error', 'mean_absolute_error'):
            cells = []
            for person in population.people:
                for family in families:
                    rows = [c for c in comparisons if c.person == person and c.family == family]
                    found = [[v for a, m, v in row.effects if a == arm and m == metric] for row in rows]
                    valid = bool(rows) and all(row.status == 'paired' and len(v) == 1 and
                        v[0] is not None and math.isfinite(v[0]) for row, v in zip(rows, found))
                    value = math.fsum(v[0] / len(rows) for v in found) if valid else None
                    cells.append((person, family, value))
            people = []
            for person in population.people:
                values = [v for p, _, v in cells if p == person]
                value = math.fsum(v / len(families) for v in values) if all(v is not None for v in values) else None
                people.append((person, value))
            complete = all(v is not None for _, v in people)
            overall = math.fsum(v / len(people) for _, v in people) if complete else None
            effects.append({'reference': arm, 'metric': metric, 'cells': tuple(cells),
                            'person_effects': tuple(people), 'balanced_effect': overall,
                            'status': 'complete_descriptive' if complete else 'incomplete_no_pooled_effect'})
    return {'condition': 'prospective_arbitrary_agent_comparison', 'effects': tuple(effects),
            'primary_metric': None, 'primary_decision': None, 'population_inference': None,
            'scientifically_qualified': False,
            'limitations': 'Scientific decisions remain separately frozen operands; no fixed-algorithm tuning/parity claim transfers to the agent'}

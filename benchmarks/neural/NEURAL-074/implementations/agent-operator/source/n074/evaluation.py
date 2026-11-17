"""Independent target-consuming calculations, with genuine issuance still external."""
from dataclasses import dataclass
import hashlib
import json
import math
from .contracts import require, UnqualifiedInput, SelectedEvaluationSupport, Population, FitConfig
from .maps import MapValue
from .metrics import map_quantities
from .models import ARMS
from .programme import Prediction, ProgrammeResult

REFERENCES = ('full_rank_ridge', 'rank_matched_ridge')


def result_digest(result):
    """Bind immutable prediction values and every disposition; not a timestamp issuer."""
    rows = []
    for p in result.predictions:
        v = p.value
        if v is not None:
            require(type(v.values) is bytes and hashlib.sha256(v.values).hexdigest() == v.sha256,
                    'Prediction bytes changed before commitment')
        rows.append((p.person, p.family, p.endpoint, p.arm, p.status, p.reason,
                     None if v is None else (v.source_identity, v.support_identity, v.length, v.sha256)))
    metadata = {'protocol': result.protocol_identity, 'taxonomy': result.taxonomy_identity,
                'eligibility': result.eligibility_identity, 'support': result.support_identity,
                'predictions': rows, 'fit_events': result.fit_events, 'stage_events': result.stage_events,
                'completion': result.completion,
                'configurations': [(key, arm, index, vars(config)) for key, arm, index, config in result.selected_configurations]}
    return hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class CaseEvaluation:
    person: str
    family: str
    endpoint: str
    status: str
    metrics: tuple
    effects: tuple
    reason: str | None


def _immutable(value):
    """Closed immutable metadata domain, including nested logical event labels."""
    if type(value) is tuple:
        return all(_immutable(v) for v in value)
    if type(value) in (str, int, bool, type(None)):
        return True
    return type(value) is float and math.isfinite(value)


def _sha256(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _map_envelope(value, expected_source, expected_support, expected_length, maximum_bytes):
    """No numerical import or decode: bind the exact immutable float64 extent."""
    require(type(value) is MapValue, 'Expected the exact immutable MapValue contract')
    require(type(value.source_identity) is str and value.source_identity == expected_source,
            'Prediction or target source identity mismatch')
    require(type(value.support_identity) is str and value.support_identity == expected_support,
            'Prediction or target spatial support mismatch')
    require(type(value.length) is int and value.length == expected_length,
            'Map length differs from independently selected evaluator geometry')
    require(type(value.values) is bytes and len(value.values) == 8 * expected_length <= maximum_bytes,
            'Map is not the selected immutable one-dimensional float64 extent')
    require(_sha256(value.sha256) and hashlib.sha256(value.values).hexdigest() == value.sha256,
            'Map value identity mismatch')


def _preflight(result, commitment, population, maximum_map_bytes,
               expected_support_identity, expected_map_length, support_authority):
    """Validate the WHOLE batch before any target request or numerical map decode."""
    require(type(population) is Population, 'Expected exact immutable Population')
    population.validate()
    require(type(expected_support_identity) is str and bool(expected_support_identity.strip()),
            'Missing independently selected support identity')
    require(type(expected_map_length) is int and expected_map_length > 1,
            'Missing independently selected map length')
    require(type(maximum_map_bytes) is int and maximum_map_bytes > 0 and
            8 * expected_map_length <= maximum_map_bytes, 'Invalid evaluator map retention bound')
    if support_authority is None or not callable(getattr(support_authority, 'authenticate_selected_support', None)):
        raise UnqualifiedInput('Independent selected-support issuer is absent')
    # NO candidate or candidate-derived geometry is passed into the authority.
    selected = support_authority.authenticate_selected_support()
    require(type(selected) is SelectedEvaluationSupport, 'Unissued or invalid selected-support receipt')
    selected.validate()
    require((selected.support_identity, selected.map_length) ==
            (expected_support_identity, expected_map_length), 'Evaluator geometry selection mismatch')
    require(type(result) is ProgrammeResult, 'Expected exact immutable ProgrammeResult')
    require(result.completion == 'complete_source_attempt', 'Aborted programme is not eligible for target scoring')
    require(all(type(v) is str and bool(v.strip()) for v in
                (result.protocol_identity, result.taxonomy_identity, result.eligibility_identity,
                 result.support_identity, result.native_observation)), 'Invalid result identity domain')
    require((result.protocol_identity, result.taxonomy_identity, result.eligibility_identity, result.support_identity) ==
            (selected.protocol_identity, selected.taxonomy_identity, selected.eligibility_identity, selected.support_identity),
            'Result differs from independent evaluator selection')
    require(result.taxonomy_identity == population.taxonomy_pin and
            result.eligibility_identity == population.eligibility_pin, 'Evaluation population selection mismatch')
    require(all(type(v) is tuple for v in (result.predictions, result.fit_events,
                                          result.selected_configurations, result.stage_events)),
            'Result collections must be immutable tuples')
    require(_immutable(result.fit_events) and _immutable(result.stage_events),
            'Result events contain mutable or invalid metadata')
    for row in result.selected_configurations:
        require(type(row) is tuple and len(row) == 4 and type(row[0]) is tuple and _immutable(row[0]) and
                type(row[1]) is str and row[1] in ARMS and type(row[2]) is int and row[2] >= 0 and
                type(row[3]) is FitConfig, 'Invalid immutable selected-configuration row')
        row[3].validate()
    require(all(type(p) is Prediction for p in result.predictions), 'Invalid prediction record domain')
    endpoints = {e.identity: e for e in population.endpoints}
    cases = {(c.person, c.endpoint): c for c in population.cases}
    lookup = {}
    unsuccessful = ('ineligible_support', 'ineligible_inner_support', 'training_input_failed',
                    'selection_failed', 'final_prediction_failed')
    for p in result.predictions:
        require(all(type(v) is str and bool(v) for v in (p.person, p.family, p.endpoint, p.arm, p.status)),
                'Invalid prediction identity/status domain')
        key = (p.person, p.endpoint, p.arm)
        require(key not in lookup and (p.person, p.endpoint) in cases and p.arm in ARMS,
                'Duplicate or unknown prediction case/arm')
        c = cases[p.person, p.endpoint]
        require(p.family == endpoints[p.endpoint].family, 'Output family differs from selected taxonomy')
        require(type(c.reason) is str and bool(c.reason) and
                (type(c.source_identity) is str and bool(c.source_identity) if c.status == 'present'
                 else c.source_identity is None), 'Invalid selected target disposition')
        if p.status == 'predicted':
            require(p.reason is None and c.status == 'present', 'Predicted row has inconsistent disposition')
            _map_envelope(p.value, 'P1:' + p.person + ':' + p.endpoint + ':' + p.arm,
                          expected_support_identity, expected_map_length, maximum_map_bytes)
        else:
            require(p.status in unsuccessful and p.value is None and type(p.reason) is str and bool(p.reason),
                    'Failed/ineligible prediction must have a known status, no value and an explicit reason')
        lookup[key] = p
    expected = {(c.person, c.endpoint, arm) for c in population.cases for arm in ARMS}
    require(set(lookup) == expected, 'Incomplete prediction pairing')
    require(_sha256(commitment) and result_digest(result) == commitment, 'Prediction commitment mismatch')
    return lookup, endpoints


def evaluate(result, commitment, population, protected_reader, maximum_map_bytes, *,
             expected_support_identity, expected_map_length, support_authority):
    """Validate the complete candidate/reference batch before protected target access.

    Required geometry must come from a separately authenticated selected support
    contract, owned by the evaluator, never copied from a candidate. The authority
    receives no candidate arguments. Its genuine implementation, protected-reader
    custody and commitment timing remain unissued external requirements.
    """
    lookup, endpoints = _preflight(result, commitment, population, maximum_map_bytes,
                                  expected_support_identity, expected_map_length, support_authority)
    # Decode ALL successful predictions before ANY target request. Immutable byte
    # buffers remain the retained source; these read-only views cannot change it.
    # A late nonfinite/decode failure aborts evaluation with zero target requests.
    predictions = {key: p.value.array('P1:' + p.person + ':' + p.endpoint + ':' + p.arm,
                                     expected_support_identity, maximum_map_bytes)
                   for key, p in lookup.items() if p.status == 'predicted'}
    output = []
    for c in population.cases:
        e = endpoints[c.endpoint]
        rows = [lookup[c.person, c.endpoint, arm] for arm in ARMS]
        if c.status != 'present' or not all(p.status == 'predicted' for p in rows):
            output.append(CaseEvaluation(c.person, e.family, c.endpoint, 'unpaired_support', (), (),
                                         'All arms and the target must cover the same declared case'))
            continue
        try:
            target_value = protected_reader.read_protected_target(c.person, c.endpoint, c.source_identity)
            _map_envelope(target_value, c.source_identity, expected_support_identity,
                          expected_map_length, maximum_map_bytes)
            target = target_value.array(c.source_identity, expected_support_identity, maximum_map_bytes)
            values = {p.arm: map_quantities(predictions[c.person, c.endpoint, p.arm], target) for p in rows}
            effects = []
            for reference in REFERENCES:
                for metric, direction in (('map_correlation', 1), ('mean_squared_error', -1), ('mean_absolute_error', -1)):
                    a, b = values['shared_components'][metric], values[reference][metric]
                    gain = None if a is None or b is None else direction * (a - b)
                    effects.append((reference, metric, gain))
            output.append(CaseEvaluation(c.person, e.family, c.endpoint, 'paired',
                                         tuple((arm, tuple(sorted(values[arm].items()))) for arm in ARMS), tuple(effects), None))
        except Exception as error:
            output.append(CaseEvaluation(c.person, e.family, c.endpoint, 'target_or_score_failed', (), (), type(error).__name__))
    require(len(output) == len(population.cases), 'Scoring lost a declared disposition')
    return tuple(output)



def summarize(evaluations, population):
    """Balanced descriptive effects for the entire declared panel, never a favorable subset."""
    population.validate()
    expected = {(c.person, c.endpoint) for c in population.cases}
    require(len(evaluations) == len(expected) and {(e.person, e.endpoint) for e in evaluations} == expected,
            'Incomplete or duplicate evaluation support')
    expected_family = {e.identity: e.family for e in population.endpoints}
    require(all(e.family == expected_family[e.endpoint] for e in evaluations), 'Evaluation family assignment changed')
    families = tuple(dict.fromkeys(e.family for e in population.endpoints))
    results = []
    for reference in REFERENCES:
        for metric in ('map_correlation', 'mean_squared_error', 'mean_absolute_error'):
            cells = []
            valid = True
            for person in population.people:
                for family in families:
                    cases = [r for r in evaluations if r.person == person and r.family == family]
                    values = []
                    for row in cases:
                        matches = [value for ref, met, value in row.effects if ref == reference and met == metric]
                        if row.status != 'paired' or len(matches) != 1 or matches[0] is None:
                            valid = False
                        else:
                            values.append(matches[0])
                    # An invalid cell stays visible; it cannot change the denominator.
                    value = sum(values) / len(values) if cases and len(values) == len(cases) else None
                    cells.append((person, family, value))
            person_effects = []
            for person in population.people:
                values = [v for p, _, v in cells if p == person]
                value = sum(values) / len(values) if len(values) == len(families) and all(v is not None for v in values) else None
                person_effects.append((person, value))
            overall = sum(v for _, v in person_effects) / len(person_effects) if valid else None
            results.append({'reference': reference, 'metric': metric, 'cells': tuple(cells),
                            'person_effects': tuple(person_effects), 'balanced_effect': overall,
                            'status': 'complete_descriptive' if valid else 'incomplete_no_pooled_effect'})
    return {'effects': tuple(results), 'primary_metric': None, 'primary_decision': None,
            'multiplicity_family': REFERENCES,
            'simultaneous_significance_claim': False,
            'inference_status': 'PENDING: root-selected primary metric, inferential procedure and thresholds are not established',
            'uncertainty_units': 'biological people with declared family dependence; overlapping fitted folds are not independent',
            'scientifically_qualified': False}

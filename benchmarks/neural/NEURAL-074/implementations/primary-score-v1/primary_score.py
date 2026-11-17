"""Executable NEURAL-074 primary endpoint; no population-inference claim.

Requires the unchanged sibling agent-operator/source package on sys.path.
The fixed endpoint comes from the current task's prospective contract, not
from a winner selected after observing a score. Only the fixed three-arm
ProgrammeResult is accepted by evaluate_primary; arbitrary agent Comparisons
are a different condition and cannot be relabeled as shared components.
"""
import math

from n074 import evaluation
from n074.contracts import Population, require
from n074.models import ARMS

PROTOCOL_VERSION = 'neural074-primary-correlation-gain-v1'
PRIMARY_REFERENCE = 'rank_matched_ridge'
PRIMARY_METRIC = 'map_correlation'
METRICS = ('map_correlation', 'mean_squared_error', 'mean_absolute_error')
REFERENCES = ('full_rank_ridge', 'rank_matched_ridge')
VALUE_KEYS = frozenset(('map_correlation', 'correlation_status',
                        'mean_squared_error', 'mean_absolute_error', 'mean_bias',
                        'prediction_mean', 'target_mean'))


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _pairs(value, name):
    require(type(value) is tuple and all(type(row) is tuple and len(row) == 2
                                        and type(row[0]) is str for row in value),
            name + ' must use immutable named pairs')
    require(len({row[0] for row in value}) == len(value), name + ' has duplicate keys')
    return dict(value)


def _validate_rows(evaluations, population):
    require(type(population) is Population, 'Exact selected Population required')
    population.validate()
    require(type(evaluations) is tuple and all(type(row) is evaluation.CaseEvaluation
                                             for row in evaluations),
            'Exact immutable fixed-programme CaseEvaluations required')
    expected = {(case.person, case.endpoint): case for case in population.cases}
    keys = [(row.person, row.endpoint) for row in evaluations]
    require(len(keys) == len(expected) and len(set(keys)) == len(keys)
            and set(keys) == set(expected), 'Complete unique 663-case evaluation roster required')
    families = {endpoint.identity: endpoint.family for endpoint in population.endpoints}
    output = {}
    for row in evaluations:
        key = row.person, row.endpoint
        require(row.family == families[row.endpoint], 'Evaluation family differs from selected taxonomy')
        if row.status != 'paired':
            require(row.status in ('unpaired_support', 'target_or_score_failed')
                    and row.metrics == () and row.effects == ()
                    and type(row.reason) is str and bool(row.reason),
                    'Failed case must retain an explicit disposition without score values')
            output[key] = None
            continue
        require(expected[key].status == 'present' and row.reason is None,
                'Paired case conflicts with selected target disposition')
        arms = _pairs(row.metrics, 'arm metrics')
        require(set(arms) == set(ARMS), 'All three fixed arms are required')
        values = {}
        for arm in ARMS:
            quantities = _pairs(arms[arm], 'map quantities')
            require(set(quantities) == VALUE_KEYS, 'Complete map metric schema required')
            correlation = quantities['map_correlation']
            require(correlation is None or (_finite(correlation) and -1 <= correlation <= 1),
                    'Correlation must be finite in [-1, 1] or explicitly undefined')
            require(quantities['correlation_status'] ==
                    ('undefined_constant_map' if correlation is None else 'defined'),
                    'Correlation value and status disagree')
            for name in VALUE_KEYS - {'map_correlation', 'correlation_status'}:
                require(_finite(quantities[name]), 'Nonfinite map quantity')
            require(quantities['mean_squared_error'] >= 0 and quantities['mean_absolute_error'] >= 0,
                    'Map error quantities cannot be negative')
            values[arm] = quantities
        # Derive contrasts from independently scored arm quantities, rather than
        # trusting a separately supplied gain column. Retain the old column and
        # require its exact consistency so conflicting evidence is not hidden.
        require(type(row.effects) is tuple and all(type(item) is tuple and len(item) == 3
                and type(item[0]) is str and type(item[1]) is str for item in row.effects),
                'Effects must use immutable reference/metric/value triples')
        effect_keys = [(ref, metric) for ref, metric, _ in row.effects]
        require(len(effect_keys) == 6 and set(effect_keys) ==
                {(ref, metric) for ref in REFERENCES for metric in METRICS},
                'Exactly six paired effects required')
        recorded = {(ref, metric): value for ref, metric, value in row.effects}
        for reference in REFERENCES:
            for metric in METRICS:
                a, b = values['shared_components'][metric], values[reference][metric]
                gain = None if a is None or b is None else (a - b if metric == 'map_correlation' else b - a)
                prior = recorded[reference, metric]
                require((gain is None and prior is None) or
                        (_finite(gain) and _finite(prior) and prior == gain),
                        'Recorded effect disagrees with finite arm quantities')
        output[key] = values
    return output


def summarize_primary(evaluations, population):
    """Compute the fixed prospective score on the entire declared population.

    A missing or undefined member prevents its contrast's pooled effect. All
    person/family cells and every failed case remain visible; negative gains
    keep their sign. Endpoints, families, and people receive equal weight at
    their respective levels. No p value or confidence interval is invented.
    """
    values = _validate_rows(evaluations, population)
    families = tuple(dict.fromkeys(endpoint.family for endpoint in population.endpoints))
    family_endpoints = {family: tuple(endpoint.identity for endpoint in population.endpoints
                                     if endpoint.family == family) for family in families}
    effects = []
    for reference in REFERENCES:
        for metric in METRICS:
            cells = []
            for person in population.people:
                for family in families:
                    gains = []
                    for endpoint in family_endpoints[family]:
                        arms = values[person, endpoint]
                        if arms is None:
                            gains.append(None)
                            continue
                        a, b = arms['shared_components'][metric], arms[reference][metric]
                        gains.append(None if a is None or b is None else
                                     (a - b if metric == 'map_correlation' else b - a))
                    value = (math.fsum(gain / len(gains) for gain in gains)
                             if all(gain is not None for gain in gains) else None)
                    cells.append((person, family, value))
            people = []
            for person in population.people:
                cells_for_person = [value for p, _, value in cells if p == person]
                value = (math.fsum(value / len(families) for value in cells_for_person)
                         if all(value is not None for value in cells_for_person) else None)
                people.append((person, value))
            complete = all(value is not None for _, value in people)
            effect = (math.fsum(value / len(people) for _, value in people) if complete else None)
            effects.append({'reference': reference, 'metric': metric, 'cells': tuple(cells),
                            'person_effects': tuple(people), 'balanced_effect': effect,
                            'status': 'complete_descriptive' if complete else 'incomplete_no_pooled_effect'})
    primary = next(effect for effect in effects if effect['reference'] == PRIMARY_REFERENCE
                   and effect['metric'] == PRIMARY_METRIC)
    return {
        'schema': PROTOCOL_VERSION,
        'condition': 'fixed_shared_components_programme',
        'population_identity': {'declaration': population.declaration_pin,
                                'taxonomy': population.taxonomy_pin,
                                'eligibility': population.eligibility_pin},
        'primary_metric': PRIMARY_METRIC,
        'primary_reference': PRIMARY_REFERENCE,
        'primary_direction': 'higher',
        'primary_units': 'signed Pearson correlation difference',
        'primary_effect': primary['balanced_effect'],
        'primary_status': primary['status'],
        'primary_decision': None,
        'effects': tuple(effects),
        'case_dispositions': tuple((row.person, row.family, row.endpoint, row.status, row.reason)
                                   for row in evaluations),
        'declared_cases': len(population.cases),
        'declared_people': len(population.people),
        'declared_families': len(families),
        'population_inference': None,
        'inference_status': 'Participant-cluster uncertainty, family dependence and companion multiplicity remain unselected',
        'scientifically_qualified': False,
    }


def evaluate_primary(result, commitment, population, protected_reader, maximum_map_bytes, *,
                     expected_support_identity, expected_map_length, support_authority):
    """Preserve the existing complete-batch preflight before any target access.

    The operator must select this version before protected evaluation and must
    still own authentic support, independent commitment timing and custody.
    This function issues none of those credentials.
    """
    rows = evaluation.evaluate(result, commitment, population, protected_reader, maximum_map_bytes,
                               expected_support_identity=expected_support_identity,
                               expected_map_length=expected_map_length,
                               support_authority=support_authority)
    summary = summarize_primary(rows, population)
    summary['prediction_commitment'] = commitment
    summary['protocol_identity'] = result.protocol_identity
    summary['support_identity'] = result.support_identity
    return rows, summary

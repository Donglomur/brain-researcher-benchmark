"""Matched fixed-programme comparison on one protected target capture.

This is evaluator-only source. It neither runs a programme nor authenticates
commitment timing, native execution, selected inputs or target custody.
"""
import math

from n074 import evaluation
from n074.contracts import require
from primary_score import (evaluate_primary, PRIMARY_METRIC, PRIMARY_REFERENCE,
                           REFERENCES)

COMPARISON_VERSION = 'neural074-paired-primary-gain-v1'


class _SelectedAuthority:
    def __init__(self, selected):
        self.selected = selected

    def authenticate_selected_support(self):
        return self.selected


class _TargetCapture:
    def __init__(self, reader, support, length, maximum_bytes):
        self.reader, self.support = reader, support
        self.length, self.maximum_bytes = length, maximum_bytes
        self.values, self.failures = {}, {}

    def read_protected_target(self, person, endpoint, source_identity):
        key = person, endpoint, source_identity
        if key not in self.values and key not in self.failures:
            try:
                value = self.reader.read_protected_target(*key)
                evaluation._map_envelope(value, source_identity, self.support,
                                         self.length, self.maximum_bytes)
                value.array(source_identity, self.support, self.maximum_bytes)
                self.values[key] = value
            except Exception as error:
                # A live exception retains its traceback and possibly a rejected
                # oversized target. The inherited evaluator records only the
                # class name, so retain exactly that immutable failure evidence.
                self.failures[key] = type(error).__name__
        if key in self.failures:
            # This fresh surrogate has the same class-name attribution consumed
            # by evaluation.evaluate, without retaining or invoking the original
            # exception object/type. It is never kept in the target cache.
            raise type(self.failures[key], (Exception,), {})() from None
        return self.values[key]


def compare_primary(first_result, first_commitment, second_result, second_commitment,
                    population, protected_reader, maximum_map_bytes, *,
                    expected_support_identity, expected_map_length,
                    support_authority, maximum_target_panel_bytes):
    """Compare two fixed results with the same references and complete panel.

    Both batches and all successful prediction bytes are admitted before the
    first target request. Each requested target, including failure, is captured
    at most once and replayed to the unchanged primary evaluator. The explicit
    panel bound covers retained raw target bytes, not hard process RSS.
    """
    population.validate()
    require(type(expected_map_length) is int and expected_map_length > 1,
            'Independently selected map length required')
    required_bytes = sum(case.status == 'present' for case in population.cases) * 8 * expected_map_length
    require(type(maximum_target_panel_bytes) is int and
            maximum_target_panel_bytes >= required_bytes,
            'Target panel retention allowance is insufficient')
    require(support_authority is not None and
            callable(getattr(support_authority, 'authenticate_selected_support', None)),
            'Independent selected-support issuer is absent')
    # Capture the independently selected support once; the existing preflight
    # verifies the exact immutable receipt against each result and population.
    authority = _SelectedAuthority(support_authority.authenticate_selected_support())
    lookups = []
    for result, commitment in ((first_result, first_commitment),
                               (second_result, second_commitment)):
        lookup, _ = evaluation._preflight(result, commitment, population, maximum_map_bytes,
            expected_support_identity, expected_map_length, authority)
        lookups.append(lookup)
    first, second = lookups
    require(all(first[key] == second[key] for key in first if key[2] in REFERENCES),
            'Matched comparison requires identical fixed reference predictions and dispositions')
    configurations = [tuple(row for row in result.selected_configurations if row[1] in REFERENCES)
                      for result in (first_result, second_result)]
    require(configurations[0] == configurations[1], 'Fixed reference configuration selection differs')
    for lookup in lookups:
        for row in lookup.values():
            if row.status == 'predicted':
                row.value.array('P1:' + row.person + ':' + row.endpoint + ':' + row.arm,
                                expected_support_identity, maximum_map_bytes)
    capture = _TargetCapture(protected_reader, expected_support_identity,
                             expected_map_length, maximum_map_bytes)
    reports, rows = [], []
    for result, commitment in ((first_result, first_commitment),
                               (second_result, second_commitment)):
        case_rows, report = evaluate_primary(result, commitment, population, capture,
            maximum_map_bytes, expected_support_identity=expected_support_identity,
            expected_map_length=expected_map_length, support_authority=authority)
        rows.append(case_rows)
        reports.append(report)
    effects = []
    for a, b in zip(reports[0]['effects'], reports[1]['effects']):
        cells = tuple((person, family, None if av is None or bv is None else av - bv)
                      for (person, family, av), (_, _, bv) in zip(a['cells'], b['cells']))
        people = tuple((person, None if av is None or bv is None else av - bv)
                       for (person, av), (_, bv) in zip(a['person_effects'], b['person_effects']))
        complete = all(value is not None for _, value in people)
        effects.append({'reference': a['reference'], 'metric': a['metric'], 'cells': cells,
            'person_effects': people,
            'balanced_effect': math.fsum(value / len(people) for _, value in people) if complete else None,
            'status': 'complete_descriptive' if complete else 'incomplete_no_pooled_effect'})
    primary = next(effect for effect in effects if effect['reference'] == PRIMARY_REFERENCE
                   and effect['metric'] == PRIMARY_METRIC)
    report = {
        'schema': COMPARISON_VERSION,
        'condition': 'paired_fixed_shared_components_programmes',
        'difference_direction': 'first_minus_second',
        'common_references_required': True,
        'first': reports[0], 'second': reports[1],
        'paired_primary_gain_difference': primary['balanced_effect'],
        'paired_primary_status': primary['status'],
        'effects': tuple(effects),
        'target_captures': tuple((person, endpoint, source, value.sha256)
                                 for (person, endpoint, source), value in capture.values.items()),
        'target_failures': tuple((person, endpoint, source, failure)
                                 for (person, endpoint, source), failure in capture.failures.items()),
        'maximum_retained_raw_target_bytes': required_bytes,
        'primary_decision': None, 'population_inference': None,
        'scientifically_qualified': False,
    }
    return rows[0], rows[1], report

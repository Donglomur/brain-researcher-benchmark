"""Full-field native numerical comparison, separate from scientific acceptance."""
from fractions import Fraction
import math
from core import need


def field(candidate, reference, scale):
    """Source metric with exact finite arithmetic and explicit undefined support."""
    need(type(scale) in (int, float) and math.isfinite(scale) and scale > 0,
         'Externally fixed positive native-unit scale, before candidate work')
    need(len(candidate) == len(reference), 'Complete original field extent')
    total, supported, undefined = Fraction(0), 0, 0
    for c, r in zip(candidate, reference):
        need(type(c) in (int, float) and type(r) in (int, float), 'Primitive native scalars')
        cf, rf = math.isfinite(c), math.isfinite(r)
        if not cf or not rf:
            same = ((math.isnan(c) and math.isnan(r)) or
                    (math.isinf(c) and math.isinf(r) and (c > 0) == (r > 0)))
            if not same:
                return {'available': False, 'reason': 'undefined_pattern_mismatch'}
            undefined += 1
            continue
        total += abs(Fraction(c)-Fraction(r))/(Fraction(scale)+abs(Fraction(r)))
        supported += 1
    if not supported:
        return {'available': False, 'reason': 'wholly_undefined', 'unsupported': undefined}
    exact = total/supported
    try:
        value = float(exact)
    except OverflowError:
        value = math.inf
    status = 'finite'
    if math.isinf(value):
        value, status = None, 'positive_infinity'
    elif value == 0 and exact > 0:
        status = 'positive_underflow'
    return {'available': True, 'mean_error': value, 'status': status,
            'supported': supported, 'unsupported': undefined,
            'exact_numerator': str(exact.numerator), 'exact_denominator': str(exact.denominator)}


def aggregate(rows, expected_roster):
    """Entry→item→person→panel, preserving all required support and failures."""
    need([(r['panel'], r['person'], r['item']) for r in rows] == expected_roster,
         'Complete predeclared ordered field/person/item roster')
    if any(not r['error']['available'] for r in rows):
        return {'available': False, 'reason': 'required_field_unavailable', 'rows': rows}
    panels = {}
    for r in rows:
        value = Fraction(int(r['error']['exact_numerator']), int(r['error']['exact_denominator']))
        panels.setdefault(r['panel'], {}).setdefault(r['person'], []).append(value)
    panel_means = {}
    for panel, people in panels.items():
        person_means = [sum(values, Fraction(0))/len(values) for values in people.values()]
        panel_means[panel] = sum(person_means, Fraction(0))/len(person_means)
    need(panel_means, 'No empty native comparison')
    exact = sum(panel_means.values(), Fraction(0))/len(panel_means)
    try:
        value = float(exact)
    except OverflowError:
        value = math.inf
    return {'available': True, 'normalized_absolute_error': None if math.isinf(value) else value,
            'status': 'positive_infinity' if math.isinf(value) else
                      ('positive_underflow' if value == 0 and exact > 0 else 'finite'),
            'rows': rows, 'historical_reproduction_established': False,
            'same_fit_audit_is_independent_fit_reproduction': False,
            'scientific_acceptance_threshold': None}

"""Folded-angle/pixel diagnostics; no data access, fitting or admission effects."""
import math

UNITS = {'angle': 'degrees', 'magnitude': 'pixels', 'speed': 'pixels/second'}


def _number(value):
    if type(value) not in (int, float):
        raise ValueError('ordinary finite number required; bool refused')
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError('finite binary64 input required') from error
    if not math.isfinite(value):
        raise ValueError('finite binary64 input required')
    return value


def finite_mean(values):
    """Preserve ordinary fsum arithmetic; scale only if its intermediate overflows."""
    values = [_number(value) for value in values]
    if not values:
        raise ValueError('nonempty mean support required')
    try:
        mean = math.fsum(values) / len(values)
    except OverflowError:
        mean = math.fsum(value / len(values) for value in values)
    if not math.isfinite(mean):
        raise ValueError('nonfinite mean')
    return mean


def _squares(pairs):
    try:
        result = math.fsum((left - right) ** 2 for left, right in pairs)
    except OverflowError:
        return None
    return result if math.isfinite(result) else None


def person_score(targets, predictions):
    """Pool all events per person. Numerical failure never becomes an infinite R²."""
    if len(targets) != len(predictions):
        raise ValueError('complete paired score rows required')
    y = [_number(value) for value in targets]
    p = [_number(value) for value in predictions]
    if not y:
        return {'status': 'undefined_empty_person', 'n': 0, 'target_mean': None,
                'sse': 0., 'sst': 0., 'r2': None}
    mean = finite_mean(y)
    sse = _squares(zip(y, p))
    sst = _squares((value, mean) for value in y)
    r2 = None
    if sse is None or sst is None:
        status = 'undefined_numerical_failure'
    elif sst == 0:
        status = 'undefined_constant_person'
    else:
        r2 = 1. - sse / sst
        if math.isfinite(r2):
            status = 'defined'
        else:
            status = 'undefined_numerical_failure'
            r2 = None
    return {'status': status, 'n': len(y), 'target_mean': mean,
            'sse': sse, 'sst': sst, 'r2': r2}


def paired_day_score(targets, raw, projected, endpoint):
    """Day diagnostics only: never average these day-level R² into the endpoint."""
    if endpoint not in UNITS or not (len(targets) == len(raw) == len(projected)):
        raise ValueError('named endpoint and complete raw/projected day support required')
    y = [_number(value) for value in targets]
    r = [_number(value) for value in raw]
    p = [_number(value) for value in projected]
    if any(not (-90 <= value <= 90) if endpoint == 'angle' else value < 0 for value in y):
        raise ValueError('authentic labels outside selected target domain; never clip labels')
    expected = [min(90., max(-90., value)) if endpoint == 'angle' else max(0., value) for value in r]
    if expected != p:
        raise ValueError('common target-blind raw/projected prediction relation required')
    raw_score, projected_score = person_score(y, r), person_score(y, p)
    for score in (raw_score, projected_score):
        score['status'] = score['status'].replace('_person', '_day')
    return {'n': len(y), 'units': UNITS[endpoint], 'projection_changed': sum(a != b for a, b in zip(r, p)),
            'raw': raw_score, 'projected': projected_score,
            'role': 'day_diagnostic_not_macro_weight'}

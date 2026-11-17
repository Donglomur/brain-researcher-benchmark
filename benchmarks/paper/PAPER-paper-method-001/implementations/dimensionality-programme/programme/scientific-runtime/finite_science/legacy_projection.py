"""Exact pure function lines from approved legacy core; no I/O entry point."""
import math

def need(ok, message):
    if not ok:
        raise ValueError(message)


def validate(value, design):
    need(type(value) is dict and set(value) == {'records'}, 'exact records object required')
    rows = value['records']
    expected = {(p['point'], e) for p in design['cases'] for e in design['estimators']}
    need(type(rows) is list and len(rows) == len(expected), 'complete76-record panel required')
    result = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'point', 'estimator', 'A', 'B', 'ratio'}, 'record fields')
        need(type(row['point']) is str and type(row['estimator']) is str, 'string identity')
        key = row['point'], row['estimator']
        need(key in expected and key not in result, 'unknown or duplicate record')
        parsed = {}
        for field in ('A', 'B', 'ratio'):
            x = row[field]
            need(type(x) in (int, float), 'real number required')
            x = float(x)
            need(math.isfinite(x) and abs(x) <= 1e100, 'finite bounded numerical value')
            parsed[field] = x
        result[key] = parsed
    need(set(result) == expected, 'complete exact panel')
    return result


def rms(values):
    return math.sqrt(math.fsum(x*x for x in values) / len(values))


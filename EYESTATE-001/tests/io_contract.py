"""Strict identities and finite data, with order/format equivalence."""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from metric_contract import require


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path')
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(path.is_file(), f'regular file required: {path}')
    return path


def sha256(path):
    h = hashlib.sha256()
    with regular(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'nonfinite JSON')
    elif isinstance(value, dict):
        for v in value.values(): finite_json(v)
    elif isinstance(value, list):
        for v in value: finite_json(v)


def json_text(text):
    def pairs(items):
        out = {}
        for key, val in items:
            require(key not in out, 'duplicate JSON key')
            out[key] = val
        return out
    def bad(value):
        raise AssertionError('nonfinite JSON constant ' + value)
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    finite_json(result)
    return result


def read_json(path):
    return json_text(regular(path).read_text())


def integer(value, json_number=False):
    require(not isinstance(value, (bool, np.bool_)), 'Boolean is not integer')
    require(not json_number or isinstance(value, (int, float)), 'JSON integer number required')
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise AssertionError('invalid integer') from exc
    require(d.is_finite() and d == d.to_integral_value(), 'exact finite integer required')
    require(Decimal(-9223372036854775808) <= d <= Decimal(9223372036854775807), 'signed int64 integer range')
    return int(d)


def number(value, json_number=False):
    require(not isinstance(value, (bool, np.bool_)), 'Boolean is not number')
    require(not json_number or isinstance(value, (int, float)), 'JSON numeric value required')
    try: out = float(value)
    except (TypeError, ValueError) as exc: raise AssertionError('numeric value required') from exc
    require(math.isfinite(out), 'finite numeric value required')
    return out


def axis(array):
    require(array.ndim == 1 and array.dtype.kind in 'iuf', 'integer-valued numeric axis')
    values = [integer(v) for v in array]
    bound = np.iinfo(np.int64)
    require(all(bound.min <= v <= bound.max for v in values), 'axis overflow')
    require(len(set(values)) == len(values), 'duplicate axis')
    return np.asarray(values, dtype=np.int64)


def boolean(value):
    if isinstance(value, (bool, np.bool_)): return bool(value)
    require(isinstance(value, str) and value.strip().lower() in ('true', 'false', '0', '1'), 'Boolean flag')
    return value.strip().lower() in ('true', '1')


def close(actual, expected, atol, rtol, name='value'):
    a, b = np.asarray(actual), np.asarray(expected)
    require(a.dtype.kind in 'iuf' and a.shape == b.shape and np.isfinite(a).all(), f'{name}: shape/finite numeric')
    require(np.all(np.abs(a - b) <= atol + rtol * np.abs(b)), f'{name}: numeric mismatch')


def match(actual, expected, atol=0., rtol=0., closed=False, path='JSON'):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), f'{path}: required object fields')
        if closed: require(set(expected) == set(actual), f'{path}: closed object')
        for k, v in expected.items(): match(actual[k], v, atol, rtol, closed, path + '.' + k)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f'{path}: list shape')
        for a, b in zip(actual, expected): match(a, b, atol, rtol, closed, path)
    elif expected is None:
        require(actual is None, f'{path}: null required')
    elif isinstance(expected, bool):
        require(type(actual) is bool and actual == expected, f'{path}: Boolean mismatch')
    elif isinstance(expected, int):
        require(integer(actual, True) == expected, f'{path}: integer mismatch')
    elif isinstance(expected, float):
        close(number(actual, True), expected, atol, rtol, path)
    else:
        require(isinstance(actual, str) and actual == expected, f'{path}: exact string')


def csv_rows(path, columns):
    with regular(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)) and
                set(columns) <= set(reader.fieldnames), 'CSV required unique columns')
        rows = list(reader)
    require(all(None not in row and all(row[k] is not None for k in columns) for row in rows), 'CSV malformed row')
    return rows


def row_match(actual, expected, atol=0., rtol=0., path='CSV'):
    for key, val in expected.items():
        require(key in actual, f'{path}: required field {key}')
        text = actual[key]
        if val is None: require(text.strip() == '', f'{key}: undefined blank required')
        elif isinstance(val, bool): require(boolean(text) == val, f'{key}: flag mismatch')
        elif isinstance(val, int): require(integer(text) == val, f'{key}: integer mismatch')
        elif isinstance(val, float): close(number(text), val, atol, rtol, key)
        else: require(text == val, f'{key}: source category mismatch')


def index_rows(rows, keys, integer_keys=()):
    result = {}
    for row in rows:
        key = tuple(integer(row[k]) if k in integer_keys else row[k] for k in keys)
        require(key not in result, 'duplicate scientific key')
        result[key] = row
    return result

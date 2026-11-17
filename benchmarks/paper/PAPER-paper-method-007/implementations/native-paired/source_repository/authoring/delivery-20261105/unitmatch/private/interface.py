"""Strict stdlib-only candidate admission, before reference or scientific imports."""
import json
import math
from pathlib import Path
from io_utils import capture

MAX_BYTES = 100_000_000
MICE = [f'Mouse{i}' for i in range(1,6)]


def unique(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def captured_json(path, limit=MAX_BYTES):
    try:
        raw,digest = capture(path,limit)
    except OSError as error:
        raise ValueError('bounded regular JSON file required') from error
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    return value,digest


def strict_json(path, limit=MAX_BYTES):
    return captured_json(path,limit)[0]


def validate(document, cohort, access_view):
    if access_view not in ('A','B'):
        raise ValueError('operator-selected A or B required')
    if type(document)!=dict or set(document)!={'schema','access_view','method_name','folds'}:
        raise ValueError('exact top-level keys')
    if document['schema']!='unitmatch_submission_v1' or document['access_view']!=access_view:
        raise ValueError('schema or view mismatch')
    if type(document['method_name'])!=str or not 1<=len(document['method_name'])<=160:
        raise ValueError('bounded method name')
    folds = document['folds']
    if type(folds)!=list or len(folds)!=5:
        raise ValueError('all five held-out mice required')
    sizes = {m['mouse_id']:len(m['units']) for m in cohort['mice']}
    if set(sizes)!=set(MICE):
        raise ValueError('cohort identity')
    for fold, mouse in zip(folds,MICE):
        if type(fold)!=dict or set(fold)!={'held_out_mouse','development_mice','probabilities'}:
            raise ValueError('exact fold keys')
        if fold['held_out_mouse']!=mouse or fold['development_mice']!=[m for m in MICE if m!=mouse]:
            raise ValueError('fold identity/order or leakage declaration')
        matrix = fold['probabilities']; n=sizes[mouse]
        if type(matrix)!=list or len(matrix)!=n:
            raise ValueError('matrix row extent')
        for row in matrix:
            if type(row)!=list or len(row)!=n:
                raise ValueError('matrix column extent')
            if any(type(v) not in (int,float) or not 0<=v<=1 or not math.isfinite(v) for v in row):
                raise ValueError('probabilities must be finite numbers in [0,1]')
    return document

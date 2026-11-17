"""Strict scalar response parsing and full public coverage. No private access."""
import json,math


def pairs(items):
    value={}
    for key,item in items:
        if key in value:raise ValueError('Duplicate response field')
        value[key]=item
    return value


def parse(body,expected_id):
    if type(body)is not bytes or not 0<len(body)<=4096:raise ValueError('Bounded UTF-8 response required')
    value=json.loads(body.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in()).throw(ValueError('Nonfinite constant')))
    if type(value)is not dict or set(value)!={'trial_id','target_probability'}:raise ValueError('Exact two-field response')
    if type(value['trial_id'])is not str or value['trial_id']!=expected_id:raise ValueError('Exact current query identity')
    p=value['target_probability']
    if type(p)not in(int,float)or not 0<=p<=1 or not math.isfinite(p):raise ValueError('One finite scalar probability in [0,1]')
    return float(p)


def complete(rows,expected_ids):
    if len(expected_ids)!=400 or len(set(expected_ids))!=400:raise ValueError('Complete fixed public ID set')
    if len(rows)!=400:raise ValueError('All responses required; no adaptive omission')
    observed={}
    for body in rows:
        if type(body)is not bytes or not 0<len(body)<=4096:raise ValueError('Bounded single response')
        value=json.loads(body.decode('utf-8'),object_pairs_hook=pairs)
        identifier=value.get('trial_id')if type(value)is dict else None
        if type(identifier)is not str or identifier not in expected_ids or identifier in observed:raise ValueError('Unknown/duplicate trial')
        observed[identifier]=parse(body,identifier)
    if set(observed)!=set(expected_ids):raise ValueError('Missing public identities')
    return [observed[x]for x in expected_ids]

"""Exact original candidate JSON parser; metadata parsing remains separate.

The _parse function is unchanged from the pinned spatial/vendor/interface.py.
Both spatial and spectral collection use this same original lexical domain.
"""
import json
import math

class InvalidSubmission(ValueError):
    pass

def _parse(body):
    text=body.decode('utf-8');depth=0;quoted=False;escape=False
    for c in text:
        if quoted:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in '[{':
            depth+=1
            if depth>12:raise InvalidSubmission('JSON nesting bound')
        elif c in ']}':depth-=1
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise InvalidSubmission('Duplicate JSON key')
            d[k]=v
        return d
    def integer(s):
        if len(s)>18:raise InvalidSubmission('Integer text bound')
        return int(s)
    def number(s):
        v=float(s)
        if not math.isfinite(v):raise InvalidSubmission('Nonfinite JSON number')
        return v
    def bad(s):raise InvalidSubmission('Nonfinite JSON constant')
    return json.loads(text,object_pairs_hook=pairs,parse_int=integer,parse_float=number,parse_constant=bad)

def parse(body,cap):
    if type(body)is not bytes or not 0<len(body)<=cap:
        raise InvalidSubmission('Bounded original candidate JSON bytes required')
    return _parse(body)

"""Closed public/private metadata and exact scalar domains. No scientific imports."""
import hashlib
import json
import math
from pathlib import PurePosixPath

class Refusal(ValueError): pass

def need(ok, reason):
    if not ok: raise Refusal(reason)

def fields(value, names):
    need(type(value) is dict and all(type(k) is str for k in value), 'plain string-key object')
    need(set(value) == set(names), 'closed fields: '+','.join(names))
    return value

def uint(value, positive=False):
    need(type(value) is int and value >= int(positive), 'exact nonnegative integer, not Boolean')
    return value

def real(value):
    need(type(value) in (int,float) and math.isfinite(value), 'finite real, not Boolean')
    return value

def text(value):
    need(type(value) is str and 0 < len(value.encode('utf-8')) <= 1024, 'bounded nonempty UTF8 text')
    return value

def relative(value):
    text(value); p=PurePosixPath(value)
    need(not p.is_absolute() and p.as_posix()==value and '..' not in p.parts and '\\' not in value and '\0' not in value, 'literal confined path')
    return value

def digest(value):
    need(type(value) is str and len(value)==64 and set(value)<=set('0123456789abcdef'), 'SHA256')
    return value

def pin(value):
    fields(value,('path','bytes','sha256'));relative(value['path']);uint(value['bytes'],True);digest(value['sha256']);return value

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def parse(raw):
    need(type(raw) is bytes,'exact UTF8 bytes')
    def pairs(rows):
        d={}
        for k,v in rows: need(k not in d,'duplicate JSON key');d[k]=v
        return d
    def invalid(_): raise Refusal('nonfinite JSON token')
    result=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    encoded(result)
    return result

def sha(raw): return hashlib.sha256(raw).hexdigest()

PEOPLE=tuple('sub-%02d'%i for i in range(1,11))
PANELS=('IMAGE','PRE','BASE','LATE')
MODES=('F','I')
CATEGORIES=53
WINDOWS={'PRE':(-100000,0),'LATE':(200000,400000)}
EXPOSURE={'corpus':'public_THINGS_EEG2','representation':'released_session_MVNN','claim':'retrospective_noncausal','taxonomy':'THINGSplus53_multilabel','native_total_io':'unobserved'}
LIMIT_FIELDS=('wall_seconds','cpu_seconds','read_bytes','write_bytes','live_bytes','files','model_calls','stream_bytes')

def limits(value):
    fields(value,LIMIT_FIELDS)
    for k in ('wall_seconds','cpu_seconds'):need(real(value[k])>0,'positive actual lifetime')
    for k in LIMIT_FIELDS[2:]:uint(value[k],True)
    return dict(value)

def exposure(value):
    fields(value,EXPOSURE)
    need(encoded(value)==encoded(EXPOSURE),'exact retained public/transductive/overlap interpretation')
    return value

def cell(value):
    fields(value,('person','mode','panel'))
    need(value['person'] in PEOPLE and value['mode'] in MODES and value['panel'] in PANELS,'closed full cell')
    return dict(value)

def cell_key(value):
    c=cell(value);return '/'.join(c[k] for k in ('person','mode','panel'))

def registry():
    return [dict(person=p,mode=m,panel=x) for p in PEOPLE for m in MODES for x in PANELS]

def prediction(value, expected_ids, expected_cell, fit_sha):
    fields(value,('schema','cell','fit_state_sha256','query_ids','category_schema_sha256','probabilities'))
    need(value['schema']=='neural057-prediction-v1' and cell(value['cell'])==cell(expected_cell),'original prediction cell')
    need(value['fit_state_sha256']==digest(fit_sha),'same original fit state')
    digest(value['category_schema_sha256'])
    need(type(value['query_ids']) is list and value['query_ids']==list(expected_ids),'complete original query order')
    rows=value['probabilities'];need(type(rows) is list and len(rows)==len(expected_ids),'one row per query')
    for row in rows:
        need(type(row) is list and len(row)==CATEGORIES,'all fixed categories, no row normalization')
        for p in row: need(0<=real(p)<=1,'Bernoulli probability')
    return value

def tagged(value):
    if math.isinf(value): return {'status':'positive_infinity','value':None}
    return {'status':'finite','value':real(value)}

"""Literal pinned public artifact validation; no truth, scoring or model code."""
import csv,io,json,math

N = 100000

BASE = ('acf', 'isttc', 'pearsonr', 'isttc_trials')

EXTRA = ('improved_full', 'improved_trials')

REV = 'e78cfd2b2ea79b7a7e707db7b79e218212497e43'

class Invalid(ValueError):
    pass

def strict_json(data):
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result: raise Invalid('duplicate JSON key')
            result[k]=v
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda v: (_ for _ in ()).throw(Invalid('nonfinite JSON')))
    except (ValueError,RecursionError) as e:
        raise Invalid('invalid JSON') from e

def validate(estimates, metadata, n=N):
    meta=strict_json(metadata)
    if not isinstance(meta,dict) or set(meta)!={'schema','condition','source_commit','notes'} or meta['schema']!='isttc_submission_v1' or meta['condition'] not in ('reproduction','improvement') or meta['source_commit']!=REV or not isinstance(meta['notes'],str) or len(meta['notes'])>12000:
        raise Invalid('invalid method metadata')
    methods=BASE+(EXTRA if meta['condition']=='improvement' else ())
    result={k:[None]*n for k in methods}
    seen={k:bytearray(n) for k in methods}
    reader=csv.reader(io.StringIO(estimates.decode('utf-8'),newline=''),strict=True)
    if next(reader,None)!=['unit_id','method','status','tau_ms']:
        raise Invalid('exact CSV header required')
    count=0
    for row in reader:
        if len(row)!=4:raise Invalid('exact four columns required')
        ident,method,status,value=row
        if len(ident)>6 or not ident.isascii() or not ident.isdecimal() or str(int(ident))!=ident:
            raise Invalid('canonical integer unit ID required')
        i=int(ident)
        if method not in result or not 0<=i<n or seen[method][i]:
            raise Invalid('unexpected or duplicate method/unit')
        if status=='ok':
            try:v=float(value)
            except ValueError:raise Invalid('invalid estimate')
            if not math.isfinite(v) or v<=0:raise Invalid('positive finite milliseconds required')
            result[method][i]=v
        elif status=='failed':
            if value!='':raise Invalid('failed estimate must have empty tau_ms')
        else:raise Invalid('invalid status')
        seen[method][i]=1;count+=1
        if count>n*len(methods):raise Invalid('too many rows')
    if count!=n*len(methods) or any(0 in v for v in seen.values()):
        raise Invalid('complete method-by-unit support required')
    return result,meta

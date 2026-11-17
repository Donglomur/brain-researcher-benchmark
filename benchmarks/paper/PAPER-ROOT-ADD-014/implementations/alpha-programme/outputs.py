"""Strict public output admission before any protected scoring callback."""
import math
from common import need, canonical
from candidate_json import parse
import protocol

CAP=16*1024**2

def parameters(value,row):
    need(type(value)is list and len(value)==5 and all(type(x)in (int,float) and math.isfinite(x) for x in value),'five finite nonboolean spatial parameters')
    r,c,s,g,gr=value
    need(-49<=r<=150 and -49<=c<=150 and s>=0 and 0<=gr<=1,'original public parameter domain')
    need(row['allow_negative_gain'] or g>=0,'condition-specific gain sign')
    need(row['model']!='OG' or gr==0,'OG fixes zero global ratio')
    return list(value) # S=0/GR=1 are retained as unsupported forward values, not dropped.


def spatial(raw,rows,sha,person=None,role=None):
    v=parse(raw,CAP)
    keys={'schema','roster_sha256','cases'} | ({'participant','role'} if person else set())
    need(type(v)is dict and set(v)==keys and v['roster_sha256']==sha,'bound exact spatial schema')
    need(v['schema']==('visual_alpha_context_parameters_v1' if person else 'visual_alpha_parameters_v1'),'exact context/full schema')
    if person:
        need(v['participant']==person and v['role']==role and role in protocol.ROLES,'exact context identity')
        rows=[r for r in rows if r['participant']==person]
    need(type(v['cases'])is list and len(v['cases'])==len(rows),'all original cases required')
    expected={r['case_id']:r for r in rows};out={}
    for row in v['cases']:
        fields={'case_id','parameters'} if person else {'case_id',*protocol.ROLES}
        need(type(row)is dict and set(row)==fields and type(row['case_id'])is str and row['case_id'] in expected and row['case_id'] not in out,'exact unique case support')
        r=expected[row['case_id']];out[r['case_id']]={'case_id':r['case_id']}
        for key in ('parameters',) if person else protocol.ROLES:out[r['case_id']][key]=parameters(row[key],r)
    return {**v,'cases':[out[r['case_id']] for r in rows]}


def spectral(raw,rows,sha):
    v=parse(raw,CAP)
    need(type(v)is dict and set(v)=={'schema','roster_sha256','cases'} and v['schema']=='visual_alpha_timecourses_v1' and v['roster_sha256']==sha,'original spectral output schema')
    need(type(v['cases'])is list and len(v['cases'])==36,'all36 timecourse matrices')
    expected={r['case_id']:r for r in rows};out={}
    for row in v['cases']:
        need(type(row)is dict and set(row)=={'case_id','values'} and type(row['case_id'])is str and row['case_id'] in expected and row['case_id'] not in out,'unique original spectral case')
        vals=row['values'];need(type(vals)is list and len(vals)==len(expected[row['case_id']]['electrode_ids']),'exact native electrode rows')
        for values in vals:
            need(type(values)is list and len(values)==75 and all(x is None or (type(x)in (int,float) and math.isfinite(x)) for x in values),'all75 finite-or-null values')
        out[row['case_id']]=row
    return {**v,'cases':[out[r['case_id']] for r in rows]}


def assemble(raw_by_key,rows,sha):
    need(set(raw_by_key)=={(p,r) for p in protocol.PEOPLE for r in protocol.ROLES},'complete27 independent contexts')
    output={}
    for person in protocol.PEOPLE:
        for role in protocol.ROLES:
            v=spatial(raw_by_key[person,role],rows,sha,person,role)
            for c in v['cases']:output.setdefault(c['case_id'],{'case_id':c['case_id']})[role]=c['parameters']
    return spatial(canonical({'schema':'visual_alpha_parameters_v1','roster_sha256':sha,'cases':[output[r['case_id']] for r in rows]}),rows,sha)

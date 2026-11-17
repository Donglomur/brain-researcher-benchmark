"""Public identity and full-output admission only. No private access or fitting."""
import re

def public_contract(value):
    c.need(type(value)is dict and set(value)=={'schema','sessions'} and value['schema']=='neural035-public-v1','public schema')
    rows=value['sessions'];c.need(type(rows)is list and len(rows)==14,'all14 sessions')
    sessions=set();queries=set();cells=0
    def opaque(v):return type(v)is str and re.fullmatch('[0-9a-f]{64}',v)
    for row in rows:
        c.need(type(row)is dict and set(row)=={'session_id','cell_ids','file','bytes','sha256','calibration_starts_seconds','validation_starts_seconds','queries'},'exact public-only fields')
        sid=row['session_id'];c.need(opaque(sid) and sid not in sessions,'unique opaque session');sessions.add(sid)
        ids=row['cell_ids'];c.need(type(ids)is list and len(ids)>=2 and len(set(ids))==len(ids) and all(opaque(x) for x in ids),'same-session cell order')
        cells+=len(ids);c.need(row['file']==sid+'.npz','session file binding');c.only_pin(row)
        c.need(row['calibration_starts_seconds']==[0,30,60,90] and row['validation_starts_seconds']==[150],'original public chronological blocks')
        c.need(type(row['queries'])is list and len(row['queries'])==2,'two future blocks')
        for query,start in zip(row['queries'],[210,270],strict=True):
            c.need(type(query)is dict and set(query)=={'query_id','start_seconds'} and type(query['start_seconds'])is int and query['start_seconds']==start,'exact query metadata')
            q=query['query_id'];c.need(opaque(q) and q not in queries,'unique opaque query');queries.add(q)
    c.need(cells==1012 and len(queries)==28,'complete1012 session-local cells and28 queries')
    return value

def admit_pair(candidate,operator,public,core):
    public_contract(public)
    # Both original complete admissions occur before any private callback.
    return core.validate_submission(candidate,public),core.validate_submission(operator,public)

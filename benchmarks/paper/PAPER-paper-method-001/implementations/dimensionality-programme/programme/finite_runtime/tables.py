"""Declared complete actor products and trusted case manifests."""
from __future__ import annotations
from .common import require,decode,RESULT_LIMIT


def actor_table(store,record,field,allowed_roles):
    value=record['response']['payload'][field]
    if isinstance(value,list):return value
    require(type(value) is dict and set(value)=={'record_index'},'DECLARED_RECORD_INDEX_REQUIRED')
    index=value['record_index'];declared={x['path']:x for x in record['response']['artifacts']}
    require(declared.get(index['path'])==index,'UNDECLARED_ACTOR_RECORD_INDEX')
    root=store.json(index,allowed_roles)
    require(root['schema']=='finite_actor_records_v1','ACTOR_RECORD_SCHEMA_MISMATCH')
    result=[]
    for part in root['parts']:
        store.meter.checkpoint('next_actor_record_shard')
        require(declared.get(part['path'])==part,'UNDECLARED_ACTOR_RECORD_SHARD')
        body=store.read(part,allowed_roles)
        for line in body.splitlines():
            store.meter.checkpoint('next_actor_record');result.append(decode(line,RESULT_LIMIT))
    require(len(result)==root['records'],'ACTOR_RECORD_CENSUS_MISMATCH')
    return result


def trusted_table(store,index,role):
    root=store.json(index,{'qualified_plan_index'})
    require(root['schema']=='finite_trusted_records_v1','TRUSTED_RECORD_SCHEMA_MISMATCH')
    count=0
    for part in root['parts']:
        store.meter.checkpoint('next_trusted_manifest_shard')
        body=store.read(part,{role})
        for line in body.splitlines():
            store.meter.checkpoint('next_trusted_manifest_record')
            count+=1;yield decode(line,RESULT_LIMIT)
    require(count==root['records'],'TRUSTED_RECORD_CENSUS_MISMATCH')

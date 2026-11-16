"""Publish an externally qualified target/query bridge; never extract EEG or fit.

The complete source/data/code/weights qualification remains external. A declared
provenance string is not proof of authentic datasets, model selection or exclusion.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'public'))
from contract import need,exact,sha,validate_query,encode,digest
from arrays import snapshot
from io_utils import read
from score import references


def publish(plan,plan_sha,source_root,out,panel,cap=100_000_000):
    exact(plan,('schema','query','targets','reference_metrics','reference_source_sha256','source_bindings','provenance'))
    need(plan['schema']=='cbramod_target_bridge_v1','external target bridge');sha(plan_sha);sha(plan['reference_source_sha256'])
    q=validate_query(plan['query'],panel);references(plan['reference_metrics'],panel,q['purpose'])
    dmap={d['id']:d for d in panel['primary_downstream_datasets']};qmap={d['id']:d for d in q['datasets']}
    need(type(plan['targets']) is dict and set(plan['targets'])==set(dmap),'full12 protected target files')
    need(type(plan['source_bindings']) is dict and set(plan['source_bindings'])==set(dmap),'all complete dataset/source dispositions')
    for name,item in plan['targets'].items():
        exact(item,('path','shape','dtype','bytes','sha256'));sha(item['sha256'])
        need(type(item['path']) is str and re.fullmatch('[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*',item['path']) and '..' not in Path(item['path']).parts,'ordinary relative target path')
        need(type(item['shape']) is list and all(type(n) is int for n in item['shape']) and item['shape']==[len(qmap[name]['rows']),1],'N-by-one complete target support')
        need(item['dtype'] in ('<f4','<f8') and type(item['bytes']) is int and item['bytes']>=80,'float target envelope')
        record=plan['source_bindings'][name]
        exact(record,('original_inventory_sha256','prepared_input_sha256','selected_split_sha256','class_order_sha256','unit_and_preprocessing_sha256','pretraining_overlap_review_sha256','source_coverage_sha256'))
        for value in record.values():sha(value)
        need(record['selected_split_sha256']==qmap[name]['split_sha256'] and record['unit_and_preprocessing_sha256']==qmap[name]['preprocessing_sha256'],'source/query split and preprocessing joins')
        need(record['prepared_input_sha256']==qmap[name]['input_sha256'] and record['class_order_sha256']==digest(qmap[name]['class_labels']),'prepared input and canonical label-order joins')
    provenance=plan['provenance']
    exact(provenance,('unresolved','external_qualification_sha256','run_seed_identity_sha256','validation_selection_sha256','candidate_independence_sha256'))
    need(provenance['unresolved']==[],'external source/target/run qualification must be resolved first')
    for name,value in provenance.items():
        if name!='unresolved':sha(value)
    need(provenance['external_qualification_sha256']==q['source_qualification_sha256'],'selected qualification join')
    # No mechanism here claims the evidence behind these hashes was audited.
    meta={'public/QUERY.json':encode(q),'private/REFERENCE_METRICS.json':encode(plan['reference_metrics']),
        'private/SOURCE_BINDINGS.json':encode(plan['source_bindings']),'private/PROVENANCE.json':encode(provenance)}
    target_rows={name:{**item,'path':'private/targets/'+name+'.npy'} for name,item in plan['targets'].items()}
    op={'schema':'cbramod_operator_v1','query':{'path':'public/QUERY.json','sha256':hashlib.sha256(meta['public/QUERY.json']).hexdigest()},
        'targets':target_rows,'reference_metrics':{'path':'private/REFERENCE_METRICS.json','sha256':hashlib.sha256(meta['private/REFERENCE_METRICS.json']).hexdigest()},
        'reference_source_sha256':plan['reference_source_sha256'],'scientific_qualification':False}
    meta['OPERATOR.json']=encode(op)
    pins=[{'path':path,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()} for path,body in meta.items()]
    pins += [{k:row[k] for k in ('path','bytes','sha256')} for row in target_rows.values()]
    complete=encode({'schema':'cbramod_target_packet_v1','plan_sha256':plan_sha,'files':pins,
        'scientific_qualification':False,'training_or_evaluation_EEG_provisioned':False,'model_or_native_code_provisioned':False})
    need(type(cap) is int and cap>0 and sum(p['bytes'] for p in pins)+len(complete)<=cap,'complete retained cap before output creation')
    out=Path(out);need(not out.exists() and not out.is_symlink(),'fresh operator output');(out/'private/targets').mkdir(parents=True)
    for name,item in plan['targets'].items():
        a=snapshot(source_root,item,out/target_rows[name]['path'])
        try:
            if dmap[name]['task']!='regression':need(np.equal(a,np.floor(a)).all() and (a>=0).all() and (a<dmap[name]['classes']).all(),'complete canonical class-order labels')
        finally:a._mmap.close()
    # Failed target validation cannot publish a query, operator binding or marker.
    for name,body in meta.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body);p.chmod(0o444)
    (out/'COMPLETE.json').write_bytes(complete);(out/'COMPLETE.json').chmod(0o444)
    return {'files':len(pins)+1,'bytes':sum(p['bytes'] for p in pins)+len(complete),'completion_sha256':hashlib.sha256(complete).hexdigest(),'scientific_qualification':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--cap',type=int,default=100_000_000);a=p.parse_args()
    plan,sha_value=read(a.plan,256_000_000,a.plan_sha256);panel,_=read(ROOT/'public/PANEL.json',2_000_000)
    print(encode(publish(plan,sha_value,Path(a.plan).resolve().parent,a.output,panel,a.cap)).decode(),end='')

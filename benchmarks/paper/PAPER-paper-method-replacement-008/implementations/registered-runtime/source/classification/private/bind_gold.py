"""Data-only target projection and frozen trusted-reference binding; no fitting or scoring."""
import sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import numpy as np
from io_contract import capture,parse,put,fresh
from arrays import read_array,write_array
from protocol import digest,canonical
from design import validate_public,hexhash
from prepare import bound_json


def bind(pool_path,public_path,baseline_path,out_path,max_output_bytes):
    pool=parse(capture(pool_path,cap=32000000));pb=capture(public_path,cap=32000000);pub=validate_public(parse(pb))
    if pool.get('pool_id')!=digest({k:v for k,v in pool.items() if k!='pool_id'}) or pool.get('public')!=pub:raise ValueError('Exact prepared pool/public generation')
    if [x['id'] for x in pool['contexts']]!=[x['id'] for x in pub['contexts']]:raise ValueError('Complete770 target contexts')
    bb=capture(baseline_path,cap=32000000);baseline=parse(bb);required=[e for e in pub['contexts'] if e['protocol']=='chronological']
    if set(baseline)!={'schema','panel_id','model','provenance','predictions'} or baseline['schema']!='barista_trusted_reference_v1' or baseline['panel_id']!=pub['panel_id'] or baseline['model']!='barista_parcels_channels' or len(baseline['predictions'])!=700:raise ValueError('Complete trusted chronological parcels/channels baseline')
    provenance=baseline['provenance'];keys={'program_sha256','training_config_sha256','checkpoint_sha256','exposure_audit_sha256','execution_receipt_sha256'}
    if set(provenance)!=keys or any(not hexhash(provenance[k]) for k in keys):raise ValueError('Required authentic trusted comparator provenance identities')
    # Admit all baseline values before numerical target reads and before any output.
    for row,e in zip(baseline['predictions'],required):
        if set(row)!={'id','query_ids_sha256','values'} or row['id']!=e['id'] or row['query_ids_sha256']!=e['query_ids_sha256']:raise ValueError('Same-support trusted predictions')
        a=read_array(Path(baseline_path).parent,row['values'],shape=(e['query_count'],),cap=4000000)
        if a.dtype.kind!='f' or (a<0).any() or (a>1).any():raise ValueError('Finite trusted probabilities')
    if type(max_output_bytes) is not int or max_output_bytes<=0:raise ValueError('Explicit output allowance')
    baseline_by_id={x['id']:x for x in baseline['predictions']};out=fresh(out_path);out.mkdir();records=[];used=0
    def emit(name,values):
        nonlocal used
        if used+values.nbytes+4096>max_output_bytes:raise ValueError('Owned target output allowance')
        d=write_array(out/name,values,cap=4000000);used+=d['bytes'];return d
    for rec,e in zip(pool['contexts'],pub['contexts']):
        d=bound_json(Path(pool_path).parent,rec['metadata']);labels=read_array(Path(pool_path).parent,d['labels'],shape=(len(d['rows']),),cap=4000000)
        if labels.dtype.str!='<i8' or not np.isin(labels,[0,1]).all():raise ValueError('Binary full source target')
        if digest([x['id'] for x in d['query']])!=e['query_ids_sha256'] or len(d['query'])!=e['query_count']:raise ValueError('Bound complete query target roster')
        values=labels[[x['index'] for x in d['query']]];pin=emit(e['id']+'-labels.npy',values);row={'id':e['id'],'query_ids_sha256':e['query_ids_sha256'],'labels':pin}
        if e['id'] in baseline_by_id:
            desc=baseline_by_id[e['id']]['values'];a=read_array(Path(baseline_path).parent,desc,shape=(e['query_count'],),cap=4000000);row['trusted_parcels_channels']=emit(e['id']+'-trusted.npy',a)
        records.append(row)
    # The bound trusted artifact is the exact initially captured body, not a later filename read.
    binding={'schema':'barista_gold_binding_v1','panel_id':pub['panel_id'],'public_sha256':hashlib.sha256(pb).hexdigest(),'contexts':records,'trusted_reference_provenance':dict(provenance,baseline_artifact_sha256=hashlib.sha256(bb).hexdigest(),metadata_is_not_execution_attestation=True)}
    if used+len(canonical(binding))+1>max_output_bytes:raise ValueError('Owned output allowance includes metadata')
    put(out/'GOLD_BINDING.json',binding);return binding

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--pool',required=True);p.add_argument('--public',required=True);p.add_argument('--baseline',required=True);p.add_argument('--out',required=True);p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args();bind(Path(a.pool),Path(a.public),Path(a.baseline),Path(a.out),a.max_output_bytes)

"""Authenticate an externally qualified complete VisNav bridge; no native extraction.

This is deterministic binding work. It cannot manufacture event tokens, missing
recordings, trial/session identities, label bins or original split provenance.
All source arrays remain in the closed operator store, never in public packets.
"""
import sys,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from contract import *
from array_io import array,finite
import numpy as np

def bridge(v,q,root,production=True):
    query(q,production)
    require(digest(v)==q['qualification']['bridge_sha256'],'externally selected exact bridge before any array reads')
    exact(v,('schema','closed_operator_exclusive','source_roster_sha256','transformation_program_sha256','original_inputs','recordings'))
    require(v['schema']=='neuroformer_qualified_bridge_v1' and v['closed_operator_exclusive'] is True,'closed qualified operator store')
    for k in ('source_roster_sha256','transformation_program_sha256'):sha256(v[k])
    require(v['source_roster_sha256']==q['qualification']['source_manifest_sha256'],'source roster join')
    require(type(v['original_inputs']) is list and len(v['original_inputs'])>0,'original input pins')
    paths=[]
    for x in v['original_inputs']:
        exact(x,('source_id','bytes','sha256'));identifier(x['source_id']);sha256(x['sha256']);require(type(x['bytes']) is int and x['bytes']>0,'source bytes');paths.append(x['source_id'])
    require(len(paths)==len(set(paths)),'unique originals')
    required={r['recording'] for c in q['cases'] for r in rows_for(q,c)}
    require(type(v['recordings']) is list and {r['id'] for r in v['recordings']}==required and len(v['recordings'])==len(required),'complete recording support')
    records={}
    for r in v['recordings']:
        exact(r,('id','animal','cohort','neurons','ticks','neural_tick_us','behavior_tick_us','event_definition_sha256','class_map_sha256','source_ids','arrays'))
        identifier(r['id']);identifier(r['animal']);require(r['cohort'] in COHORTS,'native cortical locus')
        require(r['neurons']==q['cohorts'][r['cohort']]['neurons'],'all native units')
        require(type(r['ticks']) is int and r['ticks']>=50 and r['ticks']%10==0,'complete aligned temporal extent')
        require(r['neural_tick_us']==5000 and r['behavior_tick_us']==50000,'explicit normalized timing')
        for k in ('event_definition_sha256','class_map_sha256'):sha256(r[k])
        require(type(r['source_ids']) is list and r['source_ids'] and set(r['source_ids'])<=set(paths),'recording original-source join')
        names={'neural','speed','speed_class','video'}|({'gaze'} if r['cohort']=='lateral' else set())
        exact(r['arrays'],names)
        for name,d in r['arrays'].items():
            descriptor(d);shape=d['shape'];n=r['ticks']//10
            expected=[r['ticks'],r['neurons']] if name=='neural' else [n,2] if name=='gaze' else [n,1]
            if name=='video':require(len(shape)==3 and shape[0]==n and max(shape[1:])<=4096,'complete video time/geometry')
            else:require(shape==expected,'complete aligned input shape')
            require(d['dtype']==('<i4' if name in ('neural','speed_class') else '|u1' if name=='video' else '<f8'),'bridge dtype')
            with array(root,d) as a:
                finite(a)
                if name=='neural':require(bool((a>=0).all()),'nonnegative derived event counts')
                if name=='speed_class':require(bool(((a>=0)&(a<25)).all()),'exact25-class labels')
        records[r['id']]=r
    for cohort,c in q['cohorts'].items():
        require(c['source_recording'] in records,'both native source recordings')
        r=records[c['source_recording']];require(r['animal']==c['animal'] and r['cohort']==cohort,'native animal/recording identity join')
    for c in q['cases']:
        for row in rows_for(q,c):
            r=records[row['recording']]
            require(r['animal']==row['animal'] and r['cohort']==c['definition']['cohort'],'support identity/locus')
            require(row['start_tick']%10==0 and row['stop_tick']==row['start_tick']+10 and row['stop_tick']<=r['ticks'],'exact50ms output block')
            require(row['start_tick']>=40 and row['context_start_tick']<=row['start_tick']-40,'complete200ms context guard')
    return v

def publish(q,v,observations,output,max_bytes,production=True):
    out=fresh(output);bridge(v,q,observations,production)
    target={'schema':'neuroformer_private_binding_v1','query_sha256':digest(q),'bridge':v,'bridge_sha256':digest(v),'external_source_qualification_required':True}
    bodies={'QUERY.json':encode(q),'TARGET.json':encode(target),'OUTPUT_INDEX.json':encode(output_index(q))}
    pins=[{'path':k,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for k,b in bodies.items()]
    marker=encode({'schema':'neuroformer_packet_complete_v1','files':pins,'no_native_execution':True})
    require(type(max_bytes) is int and sum(map(len,bodies.values()))+len(marker)<=max_bytes,'exact metadata cap before publication')
    out.mkdir(mode=0o700)
    for k,b in bodies.items():(out/k).write_bytes(b)
    (out/'COMPLETE.json').write_bytes(marker)
    return target

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('query','bridge','observations','output'):ap.add_argument('--'+k,required=True)
    ap.add_argument('--max-bytes',type=int,required=True);a=ap.parse_args()
    publish(load(a.query),load(a.bridge),a.observations,a.output,a.max_bytes)
if __name__=='__main__':main()

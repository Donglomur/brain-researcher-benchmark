"""Complete prediction admission before private numerical labels/references."""
import sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import numpy as np
from io_contract import capture,parse,put,fresh
from arrays import read_array
from design import TASK_ID,ARMS,MODELS,contexts,validate_public,outputs,hexhash
from metrics import auc,aggregate,improvement

JSON_CAP=32000000
ARRAY_CAP=4000000
TOTAL_CAP=512000000

class InvalidSubmission(ValueError):pass


def admit(public,body,base):
    try:
        sub=parse(body)
        if not isinstance(sub,dict) or set(sub)!={'task_id','panel_id','predictions'} or sub['task_id']!=TASK_ID or sub['panel_id']!=public['panel_id']:raise ValueError('Exact task/generation')
        expected=list(outputs(public));rows=sub['predictions']
        if not isinstance(rows,list) or len(rows)!=len(expected):raise ValueError('Complete22960 predictions required')
        total=0
        for row,e in zip(rows,expected):
            keys=('id','arm','model','query_ids_sha256')
            if not isinstance(row,dict) or set(row)!=set(keys)|{'values'} or any(row[k]!=e[k] for k in keys):raise ValueError('Exact complete ordered prediction identities')
            d=row['values']
            if not isinstance(d,dict) or type(d.get('bytes')) is not int or not 0<d['bytes']<=ARRAY_CAP:raise ValueError('Per-array cap')
            total+=d['bytes']
            if total>TOTAL_CAP:raise ValueError('Aggregate candidate cap')
            a=read_array(base,d,cap=ARRAY_CAP)
            if a.shape!=(e['query_count'],) or a.dtype.kind!='f' or (a<0).any() or (a>1).any():raise ValueError('Full finite probability support')
        return rows,expected
    except (ValueError,TypeError,KeyError,OSError,OverflowError) as exc:raise InvalidSubmission(str(exc)) from exc


def grade(public_path,gold_path,submission_path,loader=None):
    public_body=capture(public_path,cap=JSON_CAP);public=validate_public(parse(public_body));gold=parse(capture(gold_path,cap=JSON_CAP))
    if not isinstance(gold,dict) or set(gold)!={'schema','panel_id','public_sha256','contexts','trusted_reference_provenance'} or gold['schema']!='barista_gold_binding_v1' or gold['panel_id']!=public['panel_id'] or gold['public_sha256']!=hashlib.sha256(public_body).hexdigest():raise ValueError('Operator private binding/generation')
    required_provenance={'program_sha256','training_config_sha256','checkpoint_sha256','exposure_audit_sha256','execution_receipt_sha256','baseline_artifact_sha256'}
    provenance=gold['trusted_reference_provenance']
    if not isinstance(provenance,dict) or set(provenance)!=required_provenance|{'metadata_is_not_execution_attestation'} or any(not hexhash(provenance[k]) for k in required_provenance) or provenance['metadata_is_not_execution_attestation'] is not True:raise ValueError('Operator trusted-reference provenance identity contract')
    if len(gold['contexts'])!=len(public['contexts']):raise ValueError('Operator complete context targets')
    for g,e in zip(gold['contexts'],public['contexts']):
        if g.get('id')!=e['id'] or g.get('query_ids_sha256')!=e['query_ids_sha256']:raise ValueError('Operator target identity')
    try:rows,expected=admit(public,capture(submission_path,cap=JSON_CAP),Path(submission_path).parent)
    except (InvalidSubmission,OSError,ValueError) as exc:return {'task_id':TASK_ID,'status':'invalid_submission','reason':str(exc),'primary':None,'private_numeric_inputs_opened':False}
    byid={x['id']:x for x in gold['contexts']};native={arm:[] for arm in ARMS};improved={arm:[] for arm in ARMS};trusted={arm:[] for arm in ARMS}
    # Every candidate array has already been admitted. Recapture exact pins for use.
    for row,e in zip(rows,expected):
        if loader is None:
            y=read_array(Path(gold_path).parent,byid[e['id']]['labels'],cap=ARRAY_CAP)
            b=read_array(Path(gold_path).parent,byid[e['id']]['trusted_parcels_channels'],cap=ARRAY_CAP) if e['model']=='improved' else None
        else:y,b=loader(byid[e['id']],e)
        p=read_array(Path(submission_path).parent,row['values'],cap=ARRAY_CAP)
        record={k:e[k] for k in ('protocol','person','task','fold','seed','model')};record.update(auc(y,p));record['id']=e['id']
        if e['model']=='improved':
            if b is None:raise ValueError('Missing trusted chronological comparison')
            baseline={k:record[k] for k in ('id','protocol','person','task','fold','seed')};baseline.update(auc(y,b));improved[e['arm']].append(record);trusted[e['arm']].append(baseline)
        else:native[e['arm']].append(record)
    summaries={};comparisons={};primary={}
    for arm in ARMS:
        ex=[e for e in expected if e['arm']==arm and e['model']!='improved'];summaries[arm]=aggregate(native[arm],ex)
        ex=[e for e in expected if e['arm']==arm and e['model']=='improved'];comparisons[arm]=improvement(improved[arm],ex,trusted[arm]);primary[arm]=comparisons[arm]['absolute_improved_auc']['mean']
    return {'task_id':TASK_ID,'status':'defined' if all(v is not None for v in primary.values()) else 'undefined_required_support','primary':primary,'source_classification':summaries,'chronological_improvement':comparisons,'all_cell_results':native,'improvement_cells':improved,'trusted_comparison_cells':trusted,'historical_reproduction_established':False,'model_identity_or_exposure_verified':False,'scientific_significance_established':False}


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--public',required=True);p.add_argument('--gold',required=True);p.add_argument('--submission',required=True);p.add_argument('--out',required=True);a=p.parse_args();fresh(a.out)
    try:r=grade(Path(a.public),Path(a.gold),Path(a.submission))
    except (ValueError,KeyError,TypeError,OSError,OverflowError) as e:r={'task_id':TASK_ID,'status':'operator_error','reason':str(e),'primary':None}
    put(a.out,r)

if __name__=='__main__':main()

#!/usr/bin/python3
"""Candidate-visible reference inspect/predict CLI, standalone and label-free.

Only these public files plus the independently qualified NumPy runtime are needed.
All operands are explicit immutable public artifacts; no evaluator import/path.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from public_transform import apply_transform
from public_model import PublicModelLimits,from_dict,predict_raw


def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('duplicate JSON key')
        out[k]=v
    return out


def read_json(path,cap,sha=None):
    with open(path,'rb') as f:body=f.read(cap+1)
    if len(body)>cap or (sha and hashlib.sha256(body).hexdigest()!=sha):raise ValueError('public artifact pin/cap')
    return json.loads(body.decode('utf-8'),object_pairs_hook=unique,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def probabilities(scores,temperature):
    result=[]
    for row in scores:
        row=[float(x) for x in row];mx=max(row)
        e=[math.exp((v-mx)/temperature) for v in row];total=math.fsum(e);p=[v/total for v in e]
        if any(not math.isfinite(v) for v in p) or max(range(25),key=p.__getitem__)!=max(range(25),key=row.__getitem__):
            raise ValueError('calibration numerical ordering gate')
        result.append(p)
    return result


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if len(argv)<2 or argv[0] not in ('inspect','predict'):raise ValueError('inspect NAME | predict NAME PHASE [CASE_ID...]')
    root=Path(__file__).resolve().parent
    # The small closed index contains only public names, byte extents/digests and
    # qualified logical capacities. It has no private context, fit IDs or labels.
    index=read_json(root/'index.json',1048576)
    name=argv[1]
    if name not in index['tools']:raise ValueError('unknown reference tool')
    item=index['tools'][name]
    tool=read_json(root/item['file'],item['bytes'],item['sha256'])
    if argv[0]=='inspect':
        if len(argv)!=2:raise ValueError('inspect arity')
        print(json.dumps(tool,sort_keys=True,separators=(',',':'),allow_nan=False));return
    if len(argv)<3 or argv[2] not in ('/data/training','/data/query'):raise ValueError('explicit admitted phase directory')
    phase=Path(argv[2]); filename='training.jsonl' if phase.name=='training' else 'query.jsonl'
    selected=argv[3:]
    if len(selected)!=len(set(selected)):raise ValueError('duplicate requested ID')
    rows=[];seen=set()
    with open(phase/filename,'rb') as f:
        for line in f:
            row=json.loads(line,object_pairs_hook=unique)
            cid=row['case_id']
            if cid in seen:raise ValueError('duplicate public row')
            seen.add(cid)
            if not selected or cid in selected:rows.append(row)
    if selected and set(selected)!={r['case_id'] for r in rows}:raise ValueError('unknown requested ID')
    if selected:
        lookup={r['case_id']:r for r in rows};rows=[lookup[k] for k in selected]
    if not rows:raise ValueError('empty input')
    alg=tool['transform']['algorithm'];view=alg['view'];N=C=None
    if view!='C':
        D=math.prod(alg['geometry_shape']);vectors=[]
        for row in rows:
            expected='arrays/'+row['case_id']+'.f64'
            if row.get('array_file')!=expected:raise ValueError('opaque array binding')
            with open(phase/expected,'rb') as f:body=f.read(D*8+1)
            if len(body)!=D*8:raise ValueError('full common-grid array extent')
            vectors.append(np.frombuffer(body,dtype='<f8'))
        N=np.stack(vectors)
    if view!='N':C=np.asarray([r['C'] for r in rows],dtype=np.float64)
    X=apply_transform(tool['transform'],N,C)
    limits=PublicModelLimits(**index['model_limits'])
    model=from_dict(tool['model'],expected_parameter_digest=item['parameter_digest'],limits=limits)
    raw=predict_raw(model,X,limits=limits)
    for row,p in zip(rows,probabilities(raw,tool['temperature'])):
        print(json.dumps({'case_id':row['case_id'],'probabilities':p},separators=(',',':'),allow_nan=False))

if __name__=='__main__':main()

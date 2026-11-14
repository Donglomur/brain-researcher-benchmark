"""Fixed scientific R2 tool: no hidden targets, query fitting or candidate code."""
import time
ORIGIN=time.monotonic()
import argparse
import base64
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from n055.common import require,parse,encoded
from n055.learning import synthetic,pearson,probabilities
from n055.assignment import assign

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--config',required=True)
    a=p.parse_args();request=parse(Path(a.request).read_bytes());config=parse(Path(a.config).read_bytes())
    require(config['kind']=='fixed_r2_scientific_v1' and request['role']=='fixed_scientific_predictor','fixed original R2 tool')
    deadline=request['deadline']
    def guard(stage):require(time.monotonic()<deadline,'original tool deadline:'+stage)
    guard('entry');operation=request['operation'];payload=request['payload']
    if operation=='development_report':
        method=parse(Path('/bank/selected_method.json').read_bytes())
        require(method['cell']['evaluated_system']=='R2','exact independent R2 training-only bank')
        result={'reference_detail':method['reference_detail'],'selected_settings':method['selected_settings'],
                'outer_query_outcomes':False,'purpose':'original nested training-only report'}
    else:
        import numpy as np
        with np.load('/bank/model.bin',allow_pickle=False) as z:model={k:z[k] for k in z.files}
        require(str(model['kind'])=='ridge','actual R2 ridge model')
        model['kind']='ridge';temperature=float(model.pop('temperature'))
        if operation=='training_predictions':
            require(request['phase']=='FIT','training prediction operator only during FIT')
            rows=payload['rows'];require(type(rows)is list and 0<len(rows)<=200 and len(set(rows))==len(rows) and all(type(i)is int and 0<=i<16540 for i in rows),'explicit bounded permitted training rows')
            features=np.load('/input/training_image_features.npy',allow_pickle=False,mmap_mode='r')[rows]
        else:
            require(request['phase']=='INFER' and operation in ('candidate_predictions','query_scores'),'current outer-view inference operators')
            features=np.load('/input/candidate_features.npy',allow_pickle=False,mmap_mode='r')
            require(features.shape==(200,4096),'original candidate feature geometry')
        prediction=synthetic(model,features,guard)
        require(prediction.shape==(len(features),1700) and np.isfinite(prediction).all(),'complete fixed predictor output')
        def binary(array):
            value=np.asarray(array,dtype='<f8',order='C');raw=value.tobytes(order='C')
            return {'encoding':'base64','dtype':'<f8','shape':list(value.shape),'bytes':len(raw),'data':base64.b64encode(raw).decode('ascii')}
        result={'synthetic_eeg':binary(prediction),'training_or_current_view_only':True,'query_fit':False}
        if operation=='query_scores':
            query=np.load('/input/query.npy',allow_pickle=False,mmap_mode='r')
            require(query.shape==(200,17,100) and np.isfinite(query).all(),'whole actual transformed query view')
            scores=pearson(query,prediction);probs=probabilities(scores,temperature);assignment=assign(scores)
            case=parse(Path('/input/CASE.json').read_bytes())
            result.update(correlation_scores=binary(scores),independent_probabilities=binary(probs),
                          assignment=[case['candidate_ids'][i] for i in assignment],temperature=temperature)
    guard('after original fixed scientific operation')
    raw=encoded({'schema':'neural055-provider-result-v3','role':'fixed_scientific_predictor','result':result,
                 'usage':{'input_tokens':0,'output_tokens':0,'cpu_placement':'same_original_native_cgroup'},
                 'request_sha256':request['request_sha256'],'source_identity':config['source_identity']})
    require(len(raw)<=8388608,'bounded complete scientific tool result')
    offset=0
    while offset<len(raw):
        n=os.write(1,raw[offset:]);require(n>0,'actual tool response write');offset+=n
    guard('after response publication')
    return 0

if __name__=='__main__':raise SystemExit(main())


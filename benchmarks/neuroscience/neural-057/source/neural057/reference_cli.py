"""Concrete reference FIT -> state NPZ -> fresh INFER, no query data in FIT."""
import argparse,io
from pathlib import Path
from .domain import parse,encoded,need,sha,pin,CATEGORIES
from .learning import fit_reference,predict,load_state

def raw_member(root,d):
    pin(d);p=root/d['path'];need(p.parent==root and not p.is_symlink(),'fixed immediate public member')
    b=p.read_bytes();need(len(b)==d['bytes'] and sha(b)==d['sha256'],'complete public input identity');return b

def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='operation',required=True)
    f=sp.add_parser('fit');f.add_argument('--train',required=True);f.add_argument('--model-output',required=True)
    i=sp.add_parser('infer');i.add_argument('--query',required=True);i.add_argument('--model',required=True);i.add_argument('--output',required=True)
    a=ap.parse_args();import numpy as np
    if a.operation=='fit':
        p=Path(a.train);doc=parse(p.read_bytes());need(doc['schema']=='neural057-fit-view-v1','fixed reference FIT view')
        x=np.load(io.BytesIO(raw_member(p.parent,doc['features'])),allow_pickle=False);y=np.load(io.BytesIO(raw_member(p.parent,doc['targets'])),allow_pickle=False)
        need(y.shape==(len(x),CATEGORIES) and len(doc['people'])==len(doc['concepts'])==len(x),'complete public training rows')
        state,selection=fit_reference(x,y,doc['people'],doc['concepts'],doc['roles'],{k:tuple(v) for k,v in doc['groups'].items()},doc['cell']['mode'])
        buff=io.BytesIO();np.savez(buff,**state);body=buff.getvalue();out=Path(a.model_output);out.write_bytes(body)
        method={'schema':'neural057-selected-method-v1','cell':doc['cell'],'category_schema_sha256':doc['category_schema_sha256'],'state_sha256':sha(body),'method_id':'weighted-independent-logistic-v1','fit_view_sha256':sha(p.read_bytes()),'selection':dict(selection,prior=state['prior'].tolist())}
        (out.parent/'selected_method.json').write_bytes(encoded(method))
        (out.parent/'operations.json').write_bytes(encoded({'schema':'neural057-participant-declaration-v1','phase':'FIT','cell':doc['cell'],'services':[],'query_access':False,'native_cost_authority':False}))
    else:
        p=Path(a.query);doc=parse(p.read_bytes());need(doc['schema']=='neural057-query-view-v1','fixed reference INFER view')
        state_bytes=Path(a.model).read_bytes();need(sha(state_bytes)==doc['fit_state_sha256'],'same-cell immutable fitted state')
        x=np.load(io.BytesIO(raw_member(p.parent,doc['features'])),allow_pickle=False);state=load_state(a.model);prob=predict(state,x)
        need(prob.shape==(len(doc['query_ids']),CATEGORIES),'complete native prediction')
        out=Path(a.output);out.write_bytes(encoded({'schema':'neural057-prediction-v1','cell':doc['cell'],'fit_state_sha256':sha(state_bytes),'query_ids':doc['query_ids'],'category_schema_sha256':doc['category_schema_sha256'],'probabilities':prob.tolist()}))
        (out.parent/'operations.json').write_bytes(encoded({'schema':'neural057-participant-declaration-v1','phase':'INFER','cell':doc['cell'],'services':[],'query_transform_fitting':False,'native_cost_authority':False}))

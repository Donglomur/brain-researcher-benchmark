"""Trusted native tool body, appended after the exact existing reference core.

The assembler supplies TOOL_MODE, ACTION and ANALYSIS. Fitting is this fixed
body only. Query analysis executes transient Python in the existing offline,
read-only native profile, with exactly one query and immutable training state.
Arbitrary Python semantic compliance still needs independent method review.
"""
import argparse
import json
from pathlib import Path
import pickle

_reference_fit = fit
_reference_infer = infer
_validate_training = validate_training


def _json(path):
    raw=Path(path).read_bytes()
    if len(raw)>2000000:raise ValueError('bounded condition metadata')
    return json.loads(raw)


def _identity(v):
    return {k:v[k] for k in ('generation','case','setting','arm')}


def _main():
    import numpy as np
    p=argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument('kind',choices=('fit','infer'));p.add_argument('--input',required=True)
    p.add_argument('--model');p.add_argument('--out',required=True);a=p.parse_args()
    root=Path(a.input);v=_json(root/'case.json')
    if TOOL_MODE not in ('generic_numerical','decoder_alone','agent_plus_decoder'):
        raise ValueError('selected numerical/decoder tool mode')
    if a.kind=='fit':
        if ACTION!='construct_training_state' or ANALYSIS or a.model is not None:
            raise ValueError('fixed training-state construction only')
        x=np.load(root/'training.npy',allow_pickle=False)
        _validate_training(v,x)
        if x.dtype!=np.dtype('<f4') or not x.flags.c_contiguous or not np.isfinite(x).all():
            raise ValueError('original finite training geometry')
        decoder=_reference_fit(v,x) if TOOL_MODE!='generic_numerical' else None
        value=dict(schema='neural083_immutable_training_state_v1',identity=_identity(v),
                   tool_mode=TOOL_MODE,training_metadata=v,training=x,decoder=decoder)
        # Only this trusted, captured constructor can produce a model loaded by
        # this worker. Query-generated analysis never enters this fit branch.
        raw=pickle.dumps(value,protocol=5)
        if len(raw)>536870912:raise ValueError('original native model cap')
        with Path(a.out).open('xb') as f:f.write(raw)
        return
    if a.model is None or ACTION not in ('python','decoder','frozen_program'):
        raise ValueError('fixed single-query analysis operation')
    raw=Path(a.model).read_bytes()
    if len(raw)>536870912:raise ValueError('bounded trusted training state')
    state=pickle.loads(raw)
    if (state.get('schema')!='neural083_immutable_training_state_v1'
        or state['identity']!=_identity(v) or state['tool_mode']!=TOOL_MODE):
        raise ValueError('same frozen condition training state')
    q=np.load(root/'query.npy',allow_pickle=False)
    shape=(1,5) if v['arm']=='CONTEXT' else (1,251,20)
    if q.shape!=shape or q.dtype!=np.dtype('<f4') or not np.isfinite(q).all() or len(v['query'])!=1:
        raise ValueError('one finite opaque query only')
    x=state['training'];x.setflags(write=False);q.setflags(write=False)
    def decoder():
        if state['decoder'] is None:raise ValueError('decoder tool absent from generic condition')
        # The unchanged reference enforces its original 100-row interface.
        # Apply that fixed pointwise kernel to 100 copies of this one query;
        # no other query is exposed, and there is no fitting at inference.
        values=_reference_infer(state['decoder'],np.repeat(q,100,axis=0))
        if len(values)!=100 or any(z!=values[0] for z in values):
            raise ValueError('fixed decoder must be pointwise on identical rows')
        return float(values[0])
    if ACTION=='decoder':
        if ANALYSIS:raise ValueError('decoder tool accepts no transient code')
        try:result={'p_right':decoder()}
        except (ValueError,RuntimeError,FloatingPointError,ArithmeticError) as error:
            result={'abstain':type(error).__name__+':'+str(error)[:200]}
    else:
        if TOOL_MODE=='decoder_alone' or not isinstance(ANALYSIS,str) or not 0<len(ANALYSIS.encode())<=65536:
            raise ValueError('bounded numerical analysis source')
        scope=dict(np=np,training=x,training_metadata=state['training_metadata'],
                   query=q,query_metadata=v)
        if TOOL_MODE=='agent_plus_decoder':scope['decoder_probability']=decoder
        exec(compile(ANALYSIS,'<selected-single-query-analysis>','exec'),scope)
        if 'result' not in scope:raise ValueError('analysis must assign JSON result')
        result=scope['result']
    output=dict(schema='neural083_single_query_tool_result_v1',identity=_identity(v),
                query=v['query'][0],action=ACTION,result=result)
    encoded=(json.dumps(output,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    if len(encoded)>65536:raise ValueError('bounded complete numerical result')
    with Path(a.out).open('xb') as f:f.write(encoded)


if __name__=='__main__':_main()

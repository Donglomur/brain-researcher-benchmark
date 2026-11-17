"""Candidate-visible frozen reference inference, mounted under /tools.

Use only in a separately qualified current-case container. This script performs
no training. The query matrix is already transformed by the operator's arm.
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile


def bounded(path,cap):
    with Path(path).open('rb') as f:
        body=f.read(cap+1)
    if len(body)>cap:raise ValueError('Complete frozen tool input exceeds qualified bound')
    return body


def sibling(name,filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parent/filename)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--family',choices=('R0','R1','R2'),required=True)
    parser.add_argument('--query-metadata',required=True)
    parser.add_argument('--query')
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    import numpy as np
    codec=sibling('neural001_reference_bundle_codec','reference_bundle_codec.py')
    meta=codec.strict_json(bounded(args.query_metadata,65536))
    codec.require(type(meta)is dict and type(meta.get('length'))is int and 4<=meta['length']<=61440
                  and meta.get('fs_hz')==64,'exact current query support')
    if args.family=='R0':
        codec.require(meta.get('arm')=='no_neural' and args.query is None,'prior tool gets no neural view')
        prior=codec.strict_json(bounded(Path(__file__).parent/'R0.json',4096))
        codec.require(set(prior)=={'family','target_mean'} and prior['family']=='R0'
                      and type(prior['target_mean'])in(int,float) and np.isfinite(prior['target_mean']),
                      'finite training-only scalar prior')
        result=np.full(meta['length'],prior['target_mean'],dtype='<f8')
    else:
        codec.require(args.query is not None and meta.get('arm')in('neural','within_query_half_shift'),
                      'one transformed current neural query required')
        bundle=bounded(Path(__file__).parent/(args.family+'.zip'),32*1048576)
        codec._zip_preflight(bundle)
        with zipfile.ZipFile(io.BytesIO(bundle)) as z:
            rows=z.infolist()
            codec.require(len(rows)<=16 and len({r.filename for r in rows})==len(rows)
                and all(r.compress_type==zipfile.ZIP_STORED and not(r.flag_bits&1) for r in rows)
                and sum(r.file_size for r in rows)<=32*1048576,'bounded immutable bundle')
            codec.require(z.getinfo('metadata.json').file_size<=262144,'bounded full reference metadata')
            metadata=codec.strict_json(z.read('metadata.json'))
            shapes=codec._state_schema(metadata,262144)
            codec.require(set(z.namelist())=={'metadata.json'}|{'arrays/'+name+'.npy' for name in shapes},
                          'exact reference array members')
            arrays={name:codec._decode_npy(z.read('arrays/'+name+'.npy'),shape,np) for name,shape in shapes.items()}
        engine=sibling('neural001_candidate_reference_engine','reference_engine.py')
        state=engine.restore_state(metadata,arrays)
        codec.require(state.family==args.family,'requested frozen reference family')
        # Operator serialization is stored NPZ with exactly one array. External
        # mount custody authenticates it; never look up a source/public waveform.
        qb=bounded(args.query,151*1048576)
        with zipfile.ZipFile(io.BytesIO(qb)) as z:
            rows=z.infolist();codec.require(len(rows)==1 and rows[0].filename=='meg.npy'
                and rows[0].compress_type==zipfile.ZIP_STORED
                and rows[0].file_size<=meta['length']*306*8+4106,'one current full-sensor matrix')
            meg=codec._decode_npy(z.read(rows[0]),(meta['length'],306),np)
        view=dict(meta,meg=meg)
        result=engine.predict_reference(state,view,progress=lambda event:None)
    with Path(args.output).open('wb') as f:np.lib.format.write_array(f,result,version=(1,0),allow_pickle=False)
    return 0


if __name__=='__main__':raise SystemExit(main())

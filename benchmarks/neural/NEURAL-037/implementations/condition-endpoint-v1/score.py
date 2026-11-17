#!/usr/bin/env python3
"""Candidate JSON admission precedes any private file access."""
import argparse
from pathlib import Path
import numpy as np
import delivery_io as io
from array_io import array_file
import scorer_core as core


def load_targets(path,pin,public):
    metadata=io.json_file(path,524288,pin)
    io.exact(metadata,['schema','packet_id','contexts'])
    io.need(metadata['schema']=='neural037-targets-v1' and metadata['packet_id']==public['packet_id'], 'Pinned target generation')
    wanted=core.public_contract(public); io.need(set(metadata['contexts'])==set(wanted),'Complete private support')
    result={}
    for name,value in metadata['contexts'].items():
        io.exact(value,['means','counts','training_scale'])
        shape=(len(wanted[name]['cell_keys']),wanted[name]['frames'])
        for kind in ['means','counts']: io.exact(value[kind],['path','bytes','sha256'])
        result[name]={'means':array_file(io.resolve(path.parent,value['means']['path']),value['means'],np,'<f8',shape),
            'counts':array_file(io.resolve(path.parent,value['counts']['path']),value['counts'],np,'<u2',shape),
            'training_scale':value['training_scale']}
    return {'packet_id':metadata['packet_id'],'contexts':result}


def main():
    p=argparse.ArgumentParser();p.add_argument('--public',type=Path,required=True);p.add_argument('--submission',type=Path,required=True)
    p.add_argument('--private',type=Path,required=True);p.add_argument('--private-bytes',type=int,required=True)
    p.add_argument('--private-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    pin={'bytes':a.private_bytes,'sha256':a.private_sha256};io.check_pin(pin,524288)
    public=io.json_file(a.public,524288);core.public_contract(public)
    try:
        submission=io.json_file(a.submission,64000000);core.admit(public,submission,np)
    except (ValueError,OSError) as error:
        result={'status':'invalid_submission','metric':None,'private_target_callbacks':0,'reason':str(error)[:500]}
    else:
        result=core.score(public,submission,lambda:load_targets(a.private,pin,public),np)
    io.put(a.output,result,4000000);return 0 if result['status']=='scored' else 2


if __name__=='__main__': raise SystemExit(main())

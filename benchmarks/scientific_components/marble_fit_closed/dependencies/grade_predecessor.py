"""Standalone future embedding grader; no candidate or native model execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from interface import admit,captured_at,parse_json,npy_header


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--submission',type=Path,required=True);p.add_argument('--access-view',choices=['A','B'],required=True)
    p.add_argument('--baseline-root',type=Path,required=True,help='Operator-owned three-comparator embedding artifacts')
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists() or args.output.is_symlink():raise ValueError('fresh output required')
    protocol_bytes=(args.root/'public/protocol.json').read_bytes()
    spec=parse_json(protocol_bytes);assets=parse_json((args.root/'private/ASSETS.json').read_bytes())
    admitted={'candidate':admit(args.submission,spec,args.access_view,'candidate')}
    for method in ('marble','cebra-time','cebra-behavior'):
        admitted[method]=admit(args.baseline_root/method,spec,'B',method)
    # Every embedding and metadata byte is admitted before private behavior data.
    pinned={x['path']:x for x in assets['files']};label_bytes={}
    directory=os.open(args.root/'private/labels',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for rat in spec['rats']:
            name=rat['rat'];raw,digest=captured_at(directory,name+'.npy',2_000_000)
            if digest!=pinned[f'private/labels/{name}.npy']['sha256']:raise ValueError('private behavior pin')
            header=npy_header(raw,(rat['raw_samples'],3));label_bytes[name]=(raw,header)
    finally:os.close(directory)
    from score_core import arrays,score,improvement
    labels=arrays(label_bytes)
    scores={method:score(arrays(value[1]),labels,spec) for method,value in admitted.items()}
    output={'schema':'marble_grade_v1','protocol_id':spec['protocol_id'],'access_view':args.access_view,'scores':scores,
        'candidate_vs_native_marble':improvement(scores['candidate'],scores['marble']),
        'captured_artifact_hashes':{method:value[2] for method,value in admitted.items()},
        'protocol_sha256':hashlib.sha256(protocol_bytes).hexdigest(),
        'baseline_native_provenance_requires_operator_verification':True,'access_attestation':False,
        'consistency_is_descriptive_alignment_not_out_of_sample_transfer':True}
    with args.output.open('x') as file:json.dump(output,file,indent=2,allow_nan=False);file.write('\n')


if __name__=='__main__':main()

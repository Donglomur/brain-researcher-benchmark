"""Literal trusted launcher. Inspect authenticates source only; run needs external authority."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

LOADER_PIN = {'bytes': 5549, 'sha256': 'a37a04ff1b0036810751512ccf2dcba45f8401e0a2ecf932bc636af454a8fb55'}
SOURCE_PIN = {'bytes': 2295, 'sha256': 'b0cb8ef53c946ea9f4d0bddab5f6f1d7c4153a79d870a98bbb62021e7f665011'}

def context():
    root = Path(__file__).resolve().parent
    path = root / 'captured_loader.py'
    # This literal launcher and interpreter are the operator's trust anchor.
    # The captured loader then checks every component before any module import.
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('ordinary launcher source')
    with path.open('rb') as f:
        body = f.read(LOADER_PIN['bytes'] + 1)
    if {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()} != LOADER_PIN:
        raise ValueError('captured loader identity')
    module = types.ModuleType('_cerebellar_bootstrap')
    exec(compile(body, '<captured_loader>', 'exec'), module.__dict__)
    return module.load(root, SOURCE_PIN)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('inspect','run'))
    parser.add_argument('--request')
    parser.add_argument('--request-pin', type=json.loads)
    parser.add_argument('--authority')
    parser.add_argument('--authority-pin', type=json.loads)
    args = parser.parse_args()
    ctx = context()
    try:
        if args.action == 'inspect':
            if any(v is not None for v in (args.request,args.request_pin,args.authority,args.authority_pin)):
                raise ValueError('inspect has no run operands')
            print(json.dumps({'schema':'neural030_frozen_source_inspection_v1','source':SOURCE_PIN,
                'source_files':len(ctx.bodies),'phase_count':192,'case_arm_cells':64,
                'scientific_qualification':False,'native_qualification':False,'run_authorized':False}))
        else:
            if any(v is None for v in (args.request,args.request_pin,args.authority,args.authority_pin)):
                raise ValueError('all independently selected request and authority operands are required')
            result = ctx.module('controller').run_frozen(args.request,args.request_pin,args.authority,args.authority_pin,
                                                       SOURCE_PIN,ctx.worker_source())
            # Evaluation remains private in the owned output root, never stdout.
            print(json.dumps({'completed_phases':result['completed_phases'],
                              'scientific_qualification':False,'evaluation_exported_to_stdout':False}))
    finally:
        ctx.close()

if __name__ == '__main__':
    main()

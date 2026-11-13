"""Complete N055 terminal entry. Capture original clocks before project imports."""
import time
ORIGINAL_MONOTONIC=time.monotonic()
ORIGINAL_CPU=time.process_time()
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
import sys

def strict_pairs(rows):
    result={}
    for k,v in rows:
        if k in result:raise ValueError('duplicate source/plan key')
        result[k]=v
    return result

def read_pin(path,n,digest,cap):
    p=Path(path)
    if not p.is_absolute() or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('canonical unlinked bootstrap source')
    s=p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=n or not 0<n<=cap:raise ValueError('bounded exact bootstrap source')
    def identity(value):return (value.st_dev,value.st_ino,value.st_mode,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)
    with p.open('rb') as f:
        if identity(os.fstat(f.fileno()))!=identity(s):raise ValueError('same original bootstrap handle')
        raw=f.read(n+1)
        if identity(os.fstat(f.fileno()))!=identity(s):raise ValueError('stable original bootstrap handle')
    if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=digest or identity(p.lstat())!=identity(s):raise ValueError('stable complete bootstrap source')
    return raw

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['inspect','prepare','prepare-features','run'],nargs='?',default='inspect')
    parser.add_argument('--source-root',required=True);parser.add_argument('--source-manifest',required=True)
    parser.add_argument('--manifest-bytes',type=int,required=True);parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--plan',required=True);parser.add_argument('--plan-bytes',type=int,required=True);parser.add_argument('--plan-sha256',required=True)
    parser.add_argument('--operator-root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    root=Path(args.source_root);manifest=Path(args.source_manifest)
    if not manifest.is_relative_to(root):raise ValueError('source manifest within exact root')
    manifest_raw=read_pin(manifest,args.manifest_bytes,args.manifest_sha256,1048576)
    source=json.loads(manifest_raw,object_pairs_hook=strict_pairs)
    if set(source)!= {'schema','files'} or source['schema']!='neural055-complete-runtime-source-v1':raise ValueError('complete ordinary runtime manifest')
    seen=set()
    for d in source['files']:
        if set(d)!={'path','bytes','sha256','mode','role'}:raise ValueError('closed source descriptor')
        rel=Path(d['path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel)!=d['path'] or d['path'] in seen:raise ValueError('canonical unique source path')
        seen.add(d['path'])
        if d['role'] not in ('runtime_source','legacy_source','source_contract','public_instructions'):raise ValueError('ordinary code only before import')
        read_pin(root/rel,d['bytes'],d['sha256'],16777216)
    if 'central_entry.py' not in seen or Path(__file__).resolve()!=root/'central_entry.py':raise ValueError('executed exact selected bootstrap')
    raw=read_pin(Path(args.plan),args.plan_bytes,args.plan_sha256,16777216)
    plan=json.loads(raw,object_pairs_hook=strict_pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    sys.path.insert(0,str(root))
    from n055.central import execute
    descriptor={'path':str(manifest.relative_to(root)),'bytes':len(manifest_raw),'sha256':hashlib.sha256(manifest_raw).hexdigest(),
                'mode':oct(stat.S_IMODE(manifest.stat().st_mode)),'role':'complete_runtime_manifest'}
    # Bootstrap reads are a conservative original same-lifetime debit. They are
    # not silently omitted merely because project accounting starts later.
    initial=len(manifest_raw)+len(raw)+sum(d['bytes'] for d in source['files'])
    if initial>plan['limits']['read_bytes']:raise ValueError('original bootstrap exceeds selected read budget')
    result=execute(args.mode,plan,args.operator_root,root,descriptor,args.output,ORIGINAL_MONOTONIC,ORIGINAL_CPU,bootstrap_read_bytes=initial)
    print(json.dumps({'status':result['status'],'mode':args.mode,'terminal':str(Path(args.output)/'TERMINAL.json')},sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())


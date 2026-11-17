#!/usr/bin/env python3
"""Trusted central child. The source-owned caller, not this file, observes exit."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

BOOTSTRAP_READS=0
BOOTSTRAP_CAP=65537


def need(ok,message):
    if not ok:raise ValueError(message)


def parse(raw):
    def pairs(rows):
        out={}
        for key,value in rows:
            need(key not in out,'Duplicate worker bootstrap key');out[key]=value
        return out
    return json.loads(raw.decode(),object_pairs_hook=pairs,
        parse_constant=lambda _:need(False,'Nonfinite worker metadata'))


def capture(path,expected,cap,deadline):
    global BOOTSTRAP_READS
    need(time.monotonic()<deadline,'Original worker cutoff before bootstrap capture')
    p=Path(path);need(p.is_absolute() and '..'not in p.parts and not any(v.is_symlink()for v in(p,*p.parents)),'Ordinary worker source path')
    need(type(expected)is dict and set(expected)=={'bytes','sha256'} and type(expected['bytes'])is int and 0<expected['bytes']<=cap and re.fullmatch('[a-f0-9]{64}',expected['sha256']),'Exact worker startup descriptor')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==expected['bytes'],'Exact ordinary worker startup extent')
        need(BOOTSTRAP_READS+before.st_size+1<=BOOTSTRAP_CAP,'Reserve worker bootstrap read before I/O');BOOTSTRAP_READS+=before.st_size+1
        chunks=[];left=before.st_size
        while left:
            need(time.monotonic()<deadline,'Original worker source capture cutoff')
            raw=os.read(fd,min(65536,left));need(bool(raw),'Complete worker source read');chunks.append(raw);left-=len(raw)
        need(not os.read(fd,1),'Worker source EOF');raw=b''.join(chunks)
        fields=lambda s:(s.st_dev,s.st_ino,s.st_nlink,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(fields(before)==fields(os.fstat(fd))==fields(p.lstat()) and hashlib.sha256(raw).hexdigest()==expected['sha256'],'Stable exact worker source')
        return raw
    except BaseException as error:primary=error;raise
    finally:
        try:os.close(fd)
        except BaseException as error:
            if primary is None:raise
            primary.add_note('Worker bootstrap close uncertainty: '+type(error).__name__)


def module(name,path,raw):
    need(name not in sys.modules,'No ambient worker central dependency')
    value=types.ModuleType(name);value.__file__=str(path);value.__cached__=None
    sys.modules[name]=value;exec(compile(raw,str(path),'exec',dont_inherit=True),value.__dict__);return value


def main(argv=None):
    global BOOTSTRAP_CAP
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--request-bytes',type=int,required=True);p.add_argument('--request-sha256',required=True);p.add_argument('--cutoff',type=float,required=True)
    a=p.parse_args(argv)
    request_pin={'bytes':a.request_bytes,'sha256':a.request_sha256}
    raw=capture(a.request,request_pin,65536,a.cutoff);r=parse(raw)
    fields={'schema','operation_path','operation_pin','parent_source_root','parent_manifest_path','parent_manifest_pin','central_root','central_manifest','parent_output','worker_return','origin','original_end','worker_cutoff','read_cap','write_cap'}
    need(type(r)is dict and set(r)==fields and r['schema']=='paper_i_central_worker_request_v1','Exact immutable worker request')
    need(all(type(r[k])in(int,float) and math.isfinite(r[k]) for k in ('origin','worker_cutoff','original_end')) and r['origin']<=time.monotonic()<r['worker_cutoff']==a.cutoff<r['original_end'],'Original finite worker clock')
    need(type(r['read_cap']) is int and BOOTSTRAP_READS<=r['read_cap']<=2**63-1 and type(r['write_cap']) is int and 0<r['write_cap']<=65536,'Exact bounded caller-worker bootstrap allocation');BOOTSTRAP_CAP=r['read_cap']
    central=Path(r['central_root']);manifest_ref=r['central_manifest']
    manifest_raw=capture(central/'SOURCE_MANIFEST.json',manifest_ref,262144,a.cutoff);manifest=parse(manifest_raw)
    need(manifest['schema']=='paper_i_central_executable_source_v1','Exact worker central source manifest')
    used=len(raw)+len(manifest_raw)
    bodies={}
    for name,expected in manifest['files'].items():
        need(re.fullmatch('[A-Za-z0-9_.-]+',name) and name not in ('.','..'),'Flat exact worker source member')
        body=capture(central/name,expected,1048576,a.cutoff);bodies[name]=body;used+=len(body)
    need(bodies['caller_worker.py']==capture(Path(__file__).absolute(),manifest['files']['caller_worker.py'],1048576,a.cutoff),'Worker self matches captured qualified bytes')
    used+=len(bodies['caller_worker.py'])
    safe=module('paper_i_central_safety',central/'safety.py',bodies['safety.py'])
    source=module('paper_i_central_source',central/'source.py',bodies['source.py'])
    io=safe.IO(r['origin'],r['read_cap'],r['write_cap']);io.deadline=r['worker_cutoff'];io.read_charge(BOOTSTRAP_READS)
    operation_raw=io.read(r['operation_path'],r['operation_pin'],1048576)
    operation=safe.parse(operation_raw)
    need(r['original_end']==r['origin']+operation['global_limits']['wall_seconds'],'Worker preserves exact original operation deadline')
    need(operation['source_manifest']['path']==r['parent_manifest_path'] and {k:operation['source_manifest'][k]for k in('bytes','sha256')}==r['parent_manifest_pin'],'Literal original manifest operand unchanged')
    bundle=source.capture_parent(io,r['parent_source_root'],r['parent_manifest_path'],r['parent_manifest_pin'])
    original=source.bootstrap(bundle,r['parent_source_root'])
    # The bootstrap performs the original authenticated same-process reexecution.
    # No observer-mode parent modules may be preloaded into this fresh worker.
    result=original.run(r['operation_path'],r['operation_pin'],r['parent_output'],origin=r['origin'])
    io.tick();safe.descriptor(result)
    returned={'schema':'paper_i_central_worker_return_v1','request':request_pin,'operation':r['operation_pin'],
        'parent_source':r['parent_manifest_pin'],'central_source':manifest_ref,'origin':r['origin'],
        'deadline':r['original_end'],'worker_cutoff':r['worker_cutoff'],'parent_output':r['parent_output'],
        'outer_receipt':result,'bootstrap_read_bytes':io.reads,'worker_write_reservation':r['write_cap'],
        'parent_result_provisional_until_caller_observes_natural_exit':True,'scientific_qualified':False}
    io.save(r['worker_return'],safe.encode(returned));io.tick()
    return 0


if __name__=='__main__':raise SystemExit(main())

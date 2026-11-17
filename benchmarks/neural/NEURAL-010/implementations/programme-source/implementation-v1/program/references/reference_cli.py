"""Future native reference entrypoint. Source existence grants no execution authority.

The separately qualified controller owns process isolation, exact complete source
support, immutable mounts, all 9,706 fit identities, label-release barriers and
real runtime/resource admission. This process refuses incomplete declared jobs.
Run with Python -I -B; the authenticated bootstrap enables only captured siblings.
"""
import argparse
import builtins
import os
import types
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import sys

OPERANDS={
 'features':('record','waveform'),
 'fit':('family','condition','grid_index','records','support','support_sha256','expected_people','context','selection','feature_bindings'),
 'infer':('model','fit_receipt','records','threshold','feature_bindings'),
 'validate':('predictions','records','thresholds'),
 'select':('family','condition','context','validation_receipts','expected_validation_people')}
COMMON=('schema','command','source_identity','limits')
SOURCE_FILES=('common.py','contracts.py','event_protocol.py','features.py','learners.py','math_core.py','reference_cli.py','selection.py')
SHA=re.compile(r'[0-9a-f]{64}\Z')

def guard(ok,message):
    if not ok:raise ValueError(message)

def strict_pairs(items):
    result={}
    for k,v in items:guard(k not in result,'duplicate JSON key');result[k]=v
    return result

def strict(raw):return json.loads(raw,object_pairs_hook=strict_pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def read_source(path,size,digest,ledger,cap):
    guard(type(size) is int and 0<size<=4000000 and type(digest) is str and SHA.fullmatch(digest),'bounded source identity')
    guard(ledger['entry']+ledger['bootstrap']+size+1<=cap,'source read reservation before opening any body');ledger['bootstrap']+=size+1
    guard(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'ordinary absolute captured path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);guard(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==size,'ordinary complete source extent')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(size+1)
        after=os.fstat(fd);named=path.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        guard(len(raw)==size and hashlib.sha256(raw).hexdigest()==digest and all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields),'stable exact captured bytes')
    finally:os.close(fd)
    return raw


def bootstrap(args):
    # Initial interpreter source loading is a declared pinned-entry reservation,
    # not a measurement of interpreter/library/OS traffic. Parent reserves it.
    cap=args.read_cap_bytes;guard(type(cap) is int and cap>0,'external same max_input cap before request read')
    root=Path(__file__).resolve().parent;entry_size=Path(__file__).stat().st_size;guard(0<entry_size<=4000000 and entry_size<=cap,'initial entry source reservation');ledger={'entry':entry_size,'bootstrap':0,'imports':0}
    guard(args.request.is_absolute() and not args.request.is_symlink(),'absolute request');size=args.request.stat().st_size;raw=read_source(args.request,size,args.request_sha256,ledger,cap);request=strict(raw)
    guard(type(request) is dict and set(request)==set(COMMON)|set(OPERANDS[args.command]) and request['schema']=='neural010-reference-request-v1' and request['command']==args.command,'exact typed request')
    budget=request['limits'].get('max_input_bytes');guard(type(budget) is int and budget==cap,'same external/embedded max_input cap')
    identity=request['source_identity'];guard(type(identity) is dict and set(identity)=={'bytes','sha256'},'exact source identity');source_raw=read_source(root/'SOURCE_MANIFEST.json',identity['bytes'],identity['sha256'],ledger,cap);manifest=strict(source_raw)
    guard(type(manifest) is dict and set(manifest)=={'schema','files','numerical_qualification','authentic_execution'} and manifest['schema']=='neural010-reference-source-v1' and manifest['numerical_qualification'] is False and manifest['authentic_execution'] is False,'source-only captured closure')
    guard(type(manifest['files']) is list and [r['name'] for r in manifest['files']]==list(SOURCE_FILES),'all8 captured source members');bodies={}
    for row in manifest['files']:
        guard(type(row) is dict and set(row)=={'name','bytes','sha256'},'exact source member');bodies[row['name']]=read_source(root/row['name'],row['bytes'],row['sha256'],ledger,cap)
    guard(len(bodies['reference_cli.py'])==ledger['entry'],'actual captured entry extent matches initial reservation')
    guard(all(Path(name).stem not in sys.modules for name in SOURCE_FILES if name!='reference_cli.py'),'no preloaded ambient sibling modules')
    # Compile exactly captured bytes. No sys.path insertion, pyc read or sibling
    # import reread is performed; native/stdlib imports remain runtime scope.
    modules={};original=builtins.__import__
    def load(name):
        if name in modules:return modules[name]
        guard(name+'.py' in bodies and name!='reference_cli','captured sibling import only')
        module=types.ModuleType('_neural010_reference_'+name);module.__file__=str(root/(name+'.py'));module.__package__='';modules[name]=module
        def importer(n,g=None,l=None,fromlist=(),level=0):
            if level==0 and n+'.py' in bodies and n!='reference_cli':return load(n)
            return original(n,g,l,fromlist,level)
        module.__dict__['__builtins__']={**vars(builtins),'__import__':importer};exec(compile(bodies[name+'.py'],module.__file__,'exec'),module.__dict__);return module
    return request,size,ledger,load

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=sorted(OPERANDS));parser.add_argument('--request',type=Path,required=True);parser.add_argument('--request-sha256',required=True);parser.add_argument('--read-cap-bytes',type=int,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();request,size,source_reservations,load=bootstrap(args)
    common=load('common');need=common.need;io=common.IO(request['limits']);io.source_reservations=source_reservations;io.charge_read(sum(source_reservations.values()))
    extract=load('features').extract;fit=load('learners').fit;infer=load('learners').infer;validate=load('selection').validate;select=load('selection').select
    out=args.output;need(out.is_absolute() and not any(p.is_symlink() for p in (out,*out.parents)) and not out.exists() and out.parent.is_dir(),'fresh absolute ordinary output directory');out.mkdir()
    try:
        result={'features':extract,'fit':fit,'infer':infer,'validate':validate,'select':select}[args.command](request,io,out,request['source_identity'])
        receipt={'schema':'neural010-command-completion-v2','command':args.command,'request':{'path':str(args.request),'bytes':size,'sha256':args.request_sha256},'source_identity':request['source_identity'],'output':result,'limits':request['limits'],'native_qualification':False,'physical_cost_measured':False,'interpreter_library_io_included':False}
        completion=io.complete(out/'COMPLETE.json',receipt);print(json.dumps(completion,sort_keys=True))
    except BaseException as exc:
        # Preserve all partial files. No retry, reduced fit or alternate algorithm.
        failure={'schema':'neural010-command-failure-v1','command':args.command,'request_sha256':args.request_sha256,'exception_type':type(exc).__name__,'read_reserved_bytes':io.reads,'write_reserved_bytes':io.writes,'successful_artifact_bytes':io.artifact_bytes,'parent_whole_allocation_retained':True,'complete':False,'retry_authorized':False}
        try:io.write_json(out/'FAILURE.json',failure)
        except BaseException:pass
        raise

if __name__=='__main__':main()

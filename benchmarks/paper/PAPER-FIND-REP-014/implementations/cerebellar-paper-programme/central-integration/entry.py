#!/usr/bin/env python3
"""Qualified full I entry: bootstrap only until exact source and gate admission."""
import time
ORIGIN = time.monotonic()
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import types

HERE = Path(__file__).absolute().parent
REPO = HERE.parents[5]
BINDINGS_PIN = {'bytes':1453,'sha256':'a54a13fdf68150ece64f6f98832bc5aa72768e394bddc8c3de894226c8762a91'}
BOOTSTRAP_READS = 0
BOOTSTRAP_CAP = 268435456


def need(ok, message):
    if not ok: raise ValueError(message)


def decode(raw):
    def pairs(rows):
        out = {}
        for key,value in rows:
            need(key not in out, 'Duplicate bootstrap key');out[key] = value
        return out
    return json.loads(raw.decode(), object_pairs_hook=pairs,
                      parse_constant=lambda _:need(False,'Nonfinite bootstrap metadata'))


def capture(path, expected=None, cap=1048576):
    global BOOTSTRAP_READS
    need(time.monotonic() < ORIGIN+120, 'Original startup deadline')
    path = Path(path).absolute()
    need('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)), 'Ordinary bootstrap path')
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded bootstrap file')
        if expected is not None:need(before.st_size == expected['bytes'],'Exact bootstrap extent')
        BOOTSTRAP_READS += before.st_size+1
        need(BOOTSTRAP_READS <= BOOTSTRAP_CAP,'Bootstrap read ceiling')
        chunks=[];remaining=before.st_size
        while remaining:
            need(time.monotonic() < ORIGIN+120,'Original startup during capture')
            part=os.read(fd,min(65536,remaining));need(bool(part),'Complete bootstrap body')
            chunks.append(part);remaining-=len(part)
        need(not os.read(fd,1),'Bootstrap EOF')
        raw=b''.join(chunks)
        fields=lambda s:(s.st_dev,s.st_ino,s.st_nlink,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(fields(before)==fields(os.fstat(fd))==fields(path.lstat()),'Stable bootstrap identity')
        actual={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if expected is not None:need(actual==expected,'Exact bootstrap SHA')
        return raw
    except BaseException as error:
        primary=error;raise
    finally:
        try:os.close(fd)
        except BaseException as error:
            if primary is None:raise
            primary.add_note('Bootstrap close uncertainty: '+type(error).__name__)


def execute(name,path,raw):
    need(name not in sys.modules,'No ambient central module')
    module=types.ModuleType(name);module.__file__=str(path);module.__cached__=None
    module._CAPTURED_SHA256=hashlib.sha256(raw).hexdigest()
    sys.modules[name]=module
    exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
    return module


def qualified_source():
    bindings=decode(capture(HERE/'BINDINGS.json',BINDINGS_PIN,16384))
    tool=bindings['central_tools']['neurobench_campaign.py']
    gate=execute('_paper_i_central_campaign',REPO/tool['path'],capture(REPO/tool['path'],{k:tool[k] for k in ('bytes','sha256')}))
    target=REPO/bindings['runtime_manifest'];document=decode(capture(target,cap=262144))
    need(document.get('id')=='PAPER-FIND-REP-014','Exact registered task')
    need(gate.verified_program_runtime(target,document,REPO),
         'Program runner has no separate passing qualification; score verification is insufficient')
    meta=document['program_execution'];_,wrapper=gate._program_entry(meta,REPO)
    need(wrapper==HERE/'entry.py','Exact full I registered wrapper')
    freeze_ref=meta['source_freeze']
    freeze_raw=capture(REPO/freeze_ref['path'],{k:freeze_ref[k] for k in ('bytes','sha256')},1048576)
    freeze=decode(freeze_raw);files=freeze['files']
    own_path=bindings['central_root']+'/SOURCE_MANIFEST.json'
    own_raw=capture(REPO/own_path,files[own_path],262144);own=decode(own_raw)
    need(own['schema']=='paper_i_central_executable_source_v1' and set(own['files'])=={'entry.py','runner.py','caller_worker.py','safety.py','source.py','binding.py','receipts.py','BINDINGS.json','STATIC_DEPENDENCIES.json'},'Exact complete central source manifest')
    need(sum(p['bytes'] for p in own['files'].values())<=8388608,'Bounded full central source closure')
    bodies={}
    for name,expected in own['files'].items():
        need(type(name)is str and re.fullmatch('[A-Za-z0-9_.-]+',name) and name not in ('.','..'), 'Flat exact central production source')
        need(files.get(bindings['central_root']+'/'+name)==expected,'Every central member independently qualified')
        bodies[name]=capture(HERE/name,expected)
    need(bodies.get('BINDINGS.json')==capture(HERE/'BINDINGS.json',BINDINGS_PIN,16384),'Same admitted bootstrap bindings')
    static=decode(bodies['STATIC_DEPENDENCIES.json'])
    for path,expected in static['files'].items():
        need(files.get(path)==expected,'Complete static scientific/campaign qualification closure')
    for row in bindings['central_tools'].values():
        need(files.get(row['path'])=={k:row[k] for k in ('bytes','sha256')},'All central tools qualified')
    parent=bindings['parent_manifest'];parent_pin={k:parent[k] for k in ('bytes','sha256')}
    need(files.get(parent['path'])==parent_pin,'Parent manifest qualified')
    parent_raw=capture(REPO/parent['path'],parent_pin)
    for row in decode(parent_raw)['files']:
        need(files.get(bindings['parent_root']+'/'+row['path'])=={k:row[k] for k in ('bytes','sha256')},'All38 parent bodies independently qualified')
    q=meta['verification'];qraw=capture(REPO/q['qualification_path'],cap=2097152)
    need(hashlib.sha256(qraw).hexdigest()==q['qualification_sha256'],'Exact qualification raw body')
    return {'bindings':bindings,'own_manifest_raw':own_raw,'own_files':own['files'],'bodies':bodies,
            'freeze_pin':{'bytes':len(freeze_raw),'sha256':hashlib.sha256(freeze_raw).hexdigest()},
            'qualification_pin':{'bytes':len(qraw),'sha256':hashlib.sha256(qraw).hexdigest()},
            'document':decode(qraw),'bootstrap_read_bytes':BOOTSTRAP_READS,'parent_manifest_raw':parent_raw}


def main():
    need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'No inherited active timer')
    old=signal.getsignal(signal.SIGALRM);primary=None;result=None
    def alarm(signum,frame):raise TimeoutError('Original central deadline')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,ORIGIN+120-time.monotonic()))
    try:
        context=qualified_source()
        for filename,name in (('safety.py','paper_i_central_safety'),('source.py','paper_i_central_source'),
            ('binding.py','paper_i_central_binding'),('receipts.py','paper_i_central_receipts'),('runner.py','paper_i_central_runner')):
            execute(name,HERE/filename,context['bodies'][filename])
        runner=sys.modules['paper_i_central_runner']
        result=runner.run(context,REPO,HERE,ORIGIN,sys.argv[1:])
    except BaseException as error:
        primary=error;raise
    finally:
        errors=[]
        for name,action in (('timer',lambda:signal.setitimer(signal.ITIMER_REAL,0)),('handler',lambda:signal.signal(signal.SIGALRM,old))):
            try:action()
            except BaseException as error:errors.append(name+':'+type(error).__name__)
        if errors:
            if primary is not None:primary.add_note('Central cleanup: '+','.join(errors))
            else:raise RuntimeError('Central cleanup: '+','.join(errors))

    need(result is not None and time.monotonic()<result['deadline'],'Final caller return after timer/handler cleanup remains before original deadline')
    return 0


if __name__=='__main__':raise SystemExit(main())

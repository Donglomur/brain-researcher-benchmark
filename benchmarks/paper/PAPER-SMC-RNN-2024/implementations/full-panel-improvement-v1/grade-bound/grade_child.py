"""Trusted resource-bound child; execs the unchanged retained grade/lock once."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import sys
import types


def need(ok,message):
    if not ok:raise ValueError(message)


def read(path,cap=2097152):
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'ordinary exact child source')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'bounded source metadata')
        raw=f.read(cap+1);b=os.fstat(f.fileno());c=p.lstat()
    need(len(raw)==a.st_size and all(getattr(a,k)==getattr(b,k)==getattr(c,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')),'stable child source')
    return raw


def decode(raw):
    def unique(rows):
        out={}
        for k,v in rows:need(k not in out,'unique JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:need(False,'finite JSON'))


def child_argv(g,invocation):
    # The same metadata gate is repeated before either protected body read.
    g.validate_invocation(invocation)
    need(sys.platform=='linux' and os.geteuid()==0,'selected trusted Linux grading role')
    need(resource.getrlimit(resource.RLIMIT_CPU)==(600,605),'one whole-grader CPU budget across exec')
    need(sys.executable==g.PYTHON,'exact scientific interpreter invocation')
    # No early protected-body reads here. The retained grader preserves its
    # evaluator-source ordering after the lock and reads the TEST target only
    # after the original prediction snapshot.
    prepared=invocation['prepared']
    return [sys.executable,'-I','-B',prepared['owner_entry']['path'],'grade','--owner',prepared['owner_root'],
            '--result-sha256',invocation['owner_result_sha256'],'--target',invocation['private_files']['target']['path'],
            '--evaluator',invocation['private_files']['evaluator']['path'],'--output',invocation['report_path'],
            '--scratch-bytes',str(invocation['scratch_bytes'])]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',required=True);p.add_argument('--sha256',required=True);p.add_argument('--source-sha256',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;raw=read(root/'SOURCE.json')
    need(hashlib.sha256(raw).hexdigest()==a.source_sha256,'host-selected helper source manifest')
    source=decode(raw);need(source['schema']=='smc_full_panel_grade_sources_v1'
        and set(source['files'])=={'grade_bound.py','grade_child.py','owned_exit.py','bounded_capture.py','label_policy.py'},'exact public source closure')
    bodies={}
    for name,pin in source['files'].items():
        body=read(root/name);need({'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}==pin,'authenticated complete helper source');bodies[name]=body
    g=types.ModuleType('_smc_bound_grade_child');g.__file__=str(root/'grade_bound.py')
    exec(compile(bodies['grade_bound.py'],g.__file__,'exec'),g.__dict__)
    raw=read(a.request);need(hashlib.sha256(raw).hexdigest()==a.sha256,'exact selected grading request')
    argv=child_argv(g,decode(raw));os.execv(sys.executable,argv)


if __name__=='__main__':main()

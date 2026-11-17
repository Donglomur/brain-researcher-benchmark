#!/usr/bin/env python3
"""Authenticate the whole ordinary source closure before package imports."""
import os,sys
if not sys.flags.isolated or not sys.flags.no_site:
    os.execv(sys.executable,[sys.executable,'-I','-S','-B',__file__,*sys.argv[1:]])
import argparse,hashlib,json,pathlib,stat,time
START=time.monotonic();CPU=time.process_time();ROOT=pathlib.Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('source-check','prepare','run'))
    parser.add_argument('--task',required=True,choices=('PAPER-FIND-044','NEURAL-045','NEURAL-046'))
    parser.add_argument('--source-bytes',required=True,type=int);parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--condition');parser.add_argument('--program');parser.add_argument('--output');parser.add_argument('--review');parser.add_argument('--other-reserve-bytes',type=int)
    a=parser.parse_args();read=0
    def capture(relative,size,expected):
        nonlocal read
        p=pathlib.Path(relative)
        if p.is_absolute() or '..' in p.parts or p.as_posix()!=relative:raise ValueError('source member path')
        full=ROOT/p
        if any(q.is_symlink() for q in (full,*full.parents)):raise ValueError('source symlink')
        s=full.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=size or size>8<<20:raise ValueError('ordinary source pin')
        b=full.read_bytes();read+=len(b)
        if len(b)!=size or hashlib.sha256(b).hexdigest()!=expected:raise ValueError('source bytes changed')
        return b
    try:
        raw=capture('CURRENT_SOURCE_LOCK.json',a.source_bytes,a.source_sha256)
        def pairs(items):
            out={}
            for k,v in items:
                if k in out:raise ValueError('duplicate source-lock key')
                out[k]=v
            return out
        lock=json.loads(raw,object_pairs_hook=pairs)
        if lock.get('schema')!='reward_complete_central_current_source_lock_v1':raise ValueError('current source-lock schema')
        if len(lock['files'])>256 or len({p['path'] for p in lock['files']})!=len(lock['files']):raise ValueError('source closure size/duplicates')
        for p in lock['files']:capture(p['path'],p['bytes'],p['sha256'])
        members={p['path']:p for p in lock['files']}
        for name,field in (('SOURCE_LOCK.json','predecessor_source_lock'),('SOURCE.json','predecessor_distribution')):
            if members.get(name)!=lock[field]:raise ValueError('historical source binding')
        prior=lock['predecessor_distribution']
        distribution=json.loads(capture(prior['path'],prior['bytes'],prior['sha256']),object_pairs_hook=pairs)
        if set(members)!=({p['path'] for p in distribution['files']}|{'SOURCE.json'})-{'README.md'}:raise ValueError('current source closure membership')
        # No current working directory, user site hooks, or PYTHONPATH entry is
        # used for local modules. The installed interpreter/stdlib is separately
        # unqualified; no claimed hostile sandbox is created by this bootstrap.
        sys.path[:]=[str(ROOT)]+[p for p in sys.path if p and pathlib.Path(p).is_absolute() and not pathlib.Path(p).is_relative_to(ROOT)]
        from central.source import inspect,FULL
        from central.plan import conditions
        expected={'bytes':a.source_bytes,'sha256':a.source_sha256}
        if a.action=='source-check':
            s=inspect(expected)
            if (a.condition or FULL) not in conditions(a.task):raise ValueError('unknown named route')
            result={'task':a.task,'condition':a.condition or FULL,'canonical_ids':s['canonical_ids'],'independent_corpora':1,
                'paper_panels':166,'source_conditions':13,'neural_cells':84,'deployment':'unconfigured',
                'scientific_qualification':False,'bootstrap_source_bytes':read,'source':expected}
        else:
            if any(v is None for v in (a.program,a.output,a.review,a.other_reserve_bytes)):raise ValueError('complete reviewed request/output/reservation required')
            from central.execute import execute
            result=execute(a.action,a.task,a.condition,a.program,a.output,a.review,a.other_reserve_bytes,expected,START,CPU,read)
        print(json.dumps(result,allow_nan=False,sort_keys=True));return 2 if result.get('failure') else 0
    except BaseException as e:
        print(json.dumps({'status':'refused','type':type(e).__name__,'reason':str(e),'scientific_qualification':False}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

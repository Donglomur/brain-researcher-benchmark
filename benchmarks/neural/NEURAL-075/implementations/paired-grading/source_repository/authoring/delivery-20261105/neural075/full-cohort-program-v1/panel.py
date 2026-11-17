"""Concrete complete A/B controller; source build does not authorize execution.

Both programs must be committed before this entrypoint starts any data staging.
Only the accepted trusted stager sees the protected collection. Candidates see
one complete case and public material; no private scorer is imported or called.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import types
import stat

HERE = Path(__file__).resolve().parent
PANEL_CAP = 2_000_000_000
VIEW_CAP = 200_000_000
STAGE_SECONDS = 900
HOST_READ_CEILING = 200_000_000_000
HOST_WRITE_CEILING = 32_000_000_000


def load(expected):
    # The root must supply the independently selected source manifest identity.
    def bounded(p):
        if any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('Unlinked source')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as f:
            a=os.fstat(f.fileno())
            if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=100000):raise ValueError('Bounded source')
            b=f.read(a.st_size+1);z=os.fstat(f.fileno());n=p.lstat()
        if len(b)!=a.st_size or any(getattr(a,k)!=getattr(z,k) or getattr(a,k)!=getattr(n,k)for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')):raise ValueError('Stable source')
        return b
    raw = bounded(HERE/'SOURCE_MANIFEST.json')
    if len(raw) > 100000 or {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} != expected:
        raise ValueError('Exact selected controller source')
    manifest = json.loads(raw); p = manifest['runtime_files']['invoke.py']
    body = bounded(HERE/'invoke.py')
    if {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()} != p:
        raise ValueError('Exact invocation source')
    m = types.ModuleType('owned075_invocation'); m.__file__ = str(HERE/'invoke.py')
    exec(compile(body,m.__file__,'exec'),m.__dict__)
    m.source(expected)
    return m


def environment():
    return {k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','LD_','DYLD_'))
            and k not in ('DOCKER_HOST','DOCKER_CONTEXT')}


def observed(m,e,argv,end):
    raw, record = e.ch.child(argv,end,environment())
    m.child_ok(record)
    return e.r.parse(raw), record


def collection_sources(m,e,root):
    """Only compact metadata/source here; authentic pool is stager-only."""
    root = m.path(root)
    m.capture(root/'COLLECTION.json',e.lock['collection_manifest'],100000)
    for name,p in e.lock['collection_sources'].items():
        # Exact stager modules, manifests and public material; never answers.
        m.capture(root/name,p,8_000_000)
    return root


def make_identity(m,e,view,case,access,w):
    """Use only the natural-zero exact trusted stager's owned output."""
    expected = {'inputs.npz','case.json'}
    if access == 'B': expected |= {'author_code/'+n for n in e.lock['author_files']}
    files,dirs,used = m.tree_names(view,40)
    m.need(files == expected and dirs == ({'author_code'} if access == 'B' else set()) and used <= VIEW_CAP)
    w.mkdir(view/'public',0o755)
    for name,p in e.lock['public_files'].items():
        source=e.repo/'authoring/delivery-20261105/common/exports/neural075'/name
        w.bytes(view/name,m.capture(source,p,200000),200000)
    files,dirs,used = m.tree_names(view,40)
    pins = {}
    for name in sorted(files):
        if name == 'inputs.npz':
            c=e.r.parse(m.capture(view/'case.json',cap=2**20)); q={k:c['inputs'][k]for k in ('bytes','sha256')}
            e.r.opaque_pin(view/name,q,VIEW_CAP); pins[name]=q
        else: pins[name]=m.pin(m.capture(view/name,cap=2**20))
    identity={'schema':'neural075_input_identity_v1','case_id':case,'access':access,
              'files':pins,'context_pin':pins['case.json']}
    ip=w.json(view/'INPUT_IDENTITY.json',identity,30000)
    for d in [view,*(view/n for n in dirs)]:d.chmod(0o555)
    for n in files:(view/n).chmod(0o444)
    m.view_admit(e,case,view,ip,True)
    return ip


def retire_view(m,e,case,view,identity_pin,w):
    """Exact owned view only, after positive candidate/holder/volume closure."""
    m.view_admit(e,case,view,identity_pin,True)
    files,dirs,_=m.tree_names(view,40)
    for d in [view,*(view/n for n in dirs)]:d.chmod(0o700)
    for name in sorted(files):
        p=view/name; m.need(p.is_file() and not p.is_symlink());p.unlink()
    for name in sorted(dirs,key=lambda x:len(Path(x).parts),reverse=True):(view/name).rmdir()
    view.rmdir();m.syncdir(view.parent);m.need(not os.path.lexists(view))


def run(m,repo,sp,commits,collection,out,other,socket):
    e=m.dependencies(repo);m.source(sp)
    m.need(type(commits)is dict and set(commits)=={'A','B'})
    frozen={}
    for access in ('A','B'):
        row=commits[access];m.need(set(row)=={'directory','commit_pin'})
        c,body=m.read_commit(e,row['directory'],row['commit_pin'],sp)
        m.need(c['access']==access);frozen[access]=c
    # No pool/body read, stager, candidate or output exists before both freezes.
    collection=collection_sources(m,e,collection);out=m.path(out);socket=m.path(socket)
    m.need(not os.path.lexists(out) and out!=collection and out not in collection.parents and collection not in out.parents)
    for row in commits.values():
        d=m.path(row['directory']);m.need(d!=out and d not in out.parents and out not in d.parents)
    total_seconds=sum(30*(frozen[a]['seconds']+660+STAGE_SECONDS+120)for a in ('A','B'))+1800
    origin=time.monotonic();end=origin+total_seconds
    m.need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.))
    old=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Complete075 controller cutoff')))
    owned=False;w=None
    charges={'read_reserved':2_000_000_000,'write_reserved':PANEL_CAP}
    def reserve(read,write):
        m.need(charges['read_reserved']+read<=HOST_READ_CEILING and charges['write_reserved']+write<=HOST_WRITE_CEILING)
        charges['read_reserved']+=read;charges['write_reserved']+=write
    try:
        signal.setitimer(signal.ITIMER_REAL,total_seconds)
        w=m.Writer(e,out,other,PANEL_CAP)
        w.mkdir(out);owned=True;w.mkdir(out/'views');w.mkdir(out/'runs')
        w.json(out/'FROZEN_PANEL.json',{'schema':'neural075_frozen_ab_panel_v1','source':sp,
               'commits':commits,'collection_manifest':e.lock['collection_manifest'],
               'ordered_cases':list(m.CASES),'access_order':['A','B'],'feedback':'none',
               'programs_frozen_before_query_staging':True,'seconds':total_seconds},100000)
        all_records={};proofs=[]
        for access in ('A','B'):
            w.mkdir(out/'runs'/access);records=[]
            for index,case in enumerate(m.CASES):
                # Nonrefundable conservative complete-case reservations include
                # staging, repeated hashes/receipt joins and later view removal.
                reserve(2_000_000_000,250_000_000)
                w.guard(VIEW_CAP+48_000_000)
                person,arm,phase=case.split('/');view=out/'views'/f'{access}-{index:02d}'
                args=[str(Path(sys.executable).resolve()),'-I','-B',str(HERE/'stage.py'),str(collection/'operator.py'),
                      json.dumps(e.lock['pins']['operator']),'stage',
                      '--collection',str(collection),'--manifest-sha256',e.lock['collection_manifest']['sha256'],
                      '--task','neural075','--person',person,'--arm',arm,'--phase',phase,'--access',access,
                      '--output',str(view),'--output-cap',str(VIEW_CAP),'--seconds',str(STAGE_SECONDS)]
                value,child=observed(m,e,args,min(end-600,time.monotonic()+STAGE_SECONDS+60))
                m.need(value['status']=='one_context_staged_requires_observed_exit_zero' and value['task_id']=='NEURAL-075' and value['candidate_execution']is False)
                ip=make_identity(m,e,view,case,access,w)
                directory=out/'runs'/access/f'{index:02d}'
                row=commits[access]
                args=[str(Path(sys.executable).resolve()),'-I','-B',str(HERE/'invoke.py'),'run-case',
                      '--repo',str(e.repo),'--source-pin',json.dumps(sp),'--commit',str(m.path(row['directory'])),
                      '--commit-pin',json.dumps(row['commit_pin']),'--case',case,'--view',str(view),
                      '--identity-pin',json.dumps(ip),'--output',str(directory),'--other',str(other+PANEL_CAP),
                      '--socket',str(socket)]
                value,producer=observed(m,e,args,min(end-600,time.monotonic()+frozen[access]['seconds']+720))
                m.need(set(value)=={'status','case','host_exit'} and value['status']=='closed' and value['case']==case)
                m.receipt(e,frozen[access],row['commit_pin'],sp,case,directory,value['host_exit'])
                proof=w.json(out/'runs'/access/f'{index:02d}-HOST.json',{'case':case,'access':access,'stage_child':child,
                    'invocation_child':producer,'input_identity':ip,'host_exit':value['host_exit']},100000)
                retire_view(m,e,case,view,ip,w)
                records.append({'case':case,'directory':str(directory),'host_exit':value['host_exit'],
                                'enclosing_natural_zero_observed':True})
                proofs.append({'case':case,'access':access,'record':proof})
            m.need([r['case']for r in records]==list(m.CASES));all_records[access]=records
        # This barrier precedes either final collection and any possible grading.
        m.need(len(proofs)==60 and not list((out/'views').iterdir()))
        closed=w.json(out/'CLOSED60.json',{'schema':'neural075_closed60_v1','source':sp,'commits':commits,
                    'records':proofs,'candidate_calls':60,'feedback_calls':0,'private_scoring_calls':0},100000)
        products={}
        for access in ('A','B'):
            reserve(2_000_000_000,160_000_000)
            rp=w.json(out/(access+'-RECEIPTS.json'),all_records[access],100000);row=commits[access]
            args=[str(Path(sys.executable).resolve()),'-I','-B',str(HERE/'invoke.py'),'collect',
                  '--repo',str(e.repo),'--source-pin',json.dumps(sp),'--commit',str(m.path(row['directory'])),
                  '--commit-pin',json.dumps(row['commit_pin']),'--receipts',str(out/(access+'-RECEIPTS.json')),
                  '--receipts-pin',json.dumps(rp),'--output',str(out/access),'--other',str(other+PANEL_CAP)]
            value,child=observed(m,e,args,min(end-60,time.monotonic()+660))
            m.need(value['status']=='collected' and value['outputs']==30)
            complete=e.r.parse(m.capture(out/access/'COMPLETE.json',value['completion']))
            m.need(complete['source']==sp and complete['commit']==row['commit_pin'] and complete['cases']==list(m.CASES) and complete['access']==access)
            products[access]={'completion':value['completion'],'child':child}
        w.guard();m.need(time.monotonic()<end)
        q=w.json(out/'COMPLETE.json',{'schema':'neural075_complete_ab_program_panel_v1','source':sp,'commits':commits,
                    'closed60':closed,'collections':products,'cases_per_access':30,'candidate_invocations':60,
                    'scientific_tasks':1,'private_scoring_calls':0,'runtime_qualified':False,
                    'scientific_qualification_added':False,'conservative_host_phase_reservations':charges,
                    'elapsed':time.monotonic()-origin,'limit':total_seconds},100000)
        m.need(time.monotonic()<end);return {'status':'complete_unscored','completion':q,'outputs':60}
    except BaseException as exc:
        if owned:
            try:w.json(out/'FAILURE.json',{'error_type':type(exc).__name__,'automatic_retry':False,
                    'partial_is_not_full_panel':True,'resource_recovery_may_be_required':True,
                    'nonrefundable_host_phase_reservations':charges},100000)
            except BaseException:pass
        raise
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        finally:signal.signal(signal.SIGALRM,old)


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--source-pin',required=True)
    p.add_argument('--commits',required=True);p.add_argument('--commits-pin',required=True)
    p.add_argument('--collection',required=True);p.add_argument('--output',required=True)
    p.add_argument('--other',type=int,required=True);p.add_argument('--socket',required=True);a=p.parse_args()
    try:
        sp=json.loads(a.source_pin);m=load(sp);e=m.dependencies(a.repo)
        commits=e.r.parse(m.capture(a.commits,json.loads(a.commits_pin),10000))
        value=run(m,a.repo,sp,commits,a.collection,a.output,a.other,a.socket)
        print(json.dumps(value,separators=(',',':')));return 0
    except BaseException as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())

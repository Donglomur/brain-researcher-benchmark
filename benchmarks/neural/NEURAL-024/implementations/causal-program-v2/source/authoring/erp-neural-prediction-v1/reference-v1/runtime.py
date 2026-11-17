#!/usr/bin/env python3
"""Prepared trusted schema intake; no candidate code, fits or acquisition.

Run only via run_outer.py after a source-pinned root review. All numerical
decoding is confined to the single offline worker; host code is standard library.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
DOCKER = '/usr/local/bin/docker'
STAGE = 'erp-neural-reference-v1'
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'NUMBA_NUM_THREADS')
TMPFS = {'/tmp': 'rw,noexec,nosuid,nodev,size=16777216,mode=1777'}
ULIMITS = {'cpu': (150, 151), 'core': (0, 0), 'nofile': (1024, 1024),
           'fsize': (5000000, 5000000)}
ACTIVE_DOCKER = None


def need(condition, message):
    if not condition:
        raise ValueError(message)


def ordinary(path, cap):
    path = Path(os.path.abspath(path))
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'linked path')
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= cap,
         'bounded ordinary single-link file required: '+str(path))
    return path


def pin(path, cap=240000000):
    path = ordinary(path, cap)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
             'opened file identity')
        h = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            b = os.read(fd, min(131072, remaining))
            need(bool(b), 'truncated source'); h.update(b); remaining -= len(b)
        after = os.fstat(fd)
        attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        need(not os.read(fd, 1) and all(getattr(before,k)==getattr(after,k) for k in attrs),
             'file changed during hashing')
        return {'bytes': before.st_size, 'sha256': h.hexdigest()}
    finally:
        os.close(fd)


def tree_bytes(root):
    total=0
    for p in root.rglob('*'):
        need(not p.is_symlink(),'linked output')
        if p.is_file(): total+=ordinary(p,10000000).stat().st_size
    return total


def write(path,value):
    data=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    need(len(data)<=600000 and not path.exists(),'fresh bounded evidence')
    root=HERE/'execution-001'
    need(tree_bytes(root)+len(data)<=19000000,'19MB execution artifact limit;1MB preparation reserve')
    direct=sum(p.stat().st_size for p in root.iterdir()if p.is_file()and p.name!='predictions.jsonl')
    need(direct+len(data)<=2000000,'2MB operator evidence allocation')
    with path.open('xb')as f:f.write(data);f.flush();os.fsync(f.fileno())
    path.chmod(0o644)


def docker(argv, deadline, cap=300000):
    global ACTIVE_DOCKER
    need(time.monotonic() < deadline, 'Docker deadline')
    env = dict(os.environ, DOCKER_CONFIG=str(ROOT/'.cache-build/docker-config'),
               DOCKER_HOST=os.environ['NEURAL024_DOCKER_HOST'])
    # Inherit the controller group so the outer watchdog also kills its CLI child.
    p = subprocess.Popen([DOCKER, *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    ACTIVE_DOCKER = p
    sel = selectors.DefaultSelector(); buffers = {'stdout':bytearray(), 'stderr':bytearray()}
    for label, stream in [('stdout',p.stdout), ('stderr',p.stderr)]:
        os.set_blocking(stream.fileno(),False); sel.register(stream,selectors.EVENT_READ,label)
    try:
        while sel.get_map():
            need(time.monotonic() < deadline, 'Docker command timed out')
            for key,_ in sel.select(min(.05,max(0,deadline-time.monotonic()))):
                b=os.read(key.fileobj.fileno(),32768)
                if not b: sel.unregister(key.fileobj)
                else:
                    buffers[key.data].extend(b)
                    need(sum(map(len,buffers.values())) <= cap, 'Docker response cap')
        rc=p.wait(timeout=max(.001,deadline-time.monotonic()))
        return {'returncode':rc, **{k:bytes(v).decode('utf-8',errors='replace') for k,v in buffers.items()}}
    finally:
        sel.close()
        if p.poll() is None:
            p.kill(); p.wait(timeout=.4)
        p.stdout.close(); p.stderr.close(); ACTIVE_DOCKER=None


def absent(result,name):
    if result['returncode'] != 1 or result['stdout'].strip() not in ('','[]'): return False
    msg=result['stderr'].strip()
    body={f'No such container: {name}',f'no such container: {name}'}
    if msg in {f'Error: No such object: {name}',f'error: no such object: {name}'} | {
        p+m for p in ('Error response from daemon: ','error response from daemon: ') for m in body}:
        return True
    def unique(pairs):
        d={}
        for k,v in pairs:
            need(k not in d,'duplicate error key'); d[k]=v
        return d
    try:
        prefix='Error response from daemon: '
        if msg.startswith(prefix):
            obj=json.loads(msg[len(prefix):],object_pairs_hook=unique)
            return type(obj) is dict and set(obj)=={'message'} and obj['message'] in body
    except (ValueError,TypeError): pass
    return False


def cleanup(name,deadline):
    result={'container':name,'absent':False}
    try: result['remove']=docker(['rm','--force',name],min(deadline,time.monotonic()+2))
    except Exception as exc: result['remove_error']=repr(exc)
    try:
        result['inspect']=docker(['inspect','--type','container',name],deadline)
        result['absent']=absent(result['inspect'],name)
    except Exception as exc: result['inspect_error']=repr(exc)
    return result


def verify(info,name,mounts,environment,user,program,interactive=False):
    h,c,s=info['HostConfig'],info['Config'],info['State']
    need(info['Name']=='/'+name and info['Image']==c['Image']==IMAGE and c['User']==user
         and c['Entrypoint']==['python'] and c['Cmd']==['-I','-B','/program/'+program]
         and c['WorkingDir']=='/tmp' and not c.get('Volumes') and not c['Tty']
         and c['OpenStdin'] is interactive, 'worker identity')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and not h['Privileged']
         and h['CapDrop']==['ALL'] and not h.get('CapAdd')
         and h['SecurityOpt']==['no-new-privileges:true'] and not h.get('Devices')
         and not h.get('DeviceRequests') and not h.get('DeviceCgroupRules')
         and not h.get('PortBindings') and h['PidMode']!='host' and h['IpcMode']!='host'
         and h.get('RestartPolicy',{}).get('Name') in ('no',''), 'offline/nonroot policy')
    need(h['Memory']==h['MemorySwap']==4*1024**3 and h['NanoCpus']==2000000000
         and h['PidsLimit']==32 and h['ShmSize']==1048576, 'resource limits')
    need(h['Tmpfs']==TMPFS and h['LogConfig']=={'Type':'none','Config':{}}, 'scratch/log limits')
    need(len(h['Ulimits'])==len(ULIMITS) and
         {r['Name']:(r['Soft'],r['Hard']) for r in h['Ulimits']}==ULIMITS,'exact ulimits')
    env=dict(v.split('=',1) for v in c['Env'])
    need(len(env)==len(c['Env']) and env==environment,'exact environment')
    for rows,key,effective in ((h.get('Mounts',[]),'Target',False),
            ([r for r in info['Mounts'] if r['Type']!='tmpfs'],'Destination',True)):
        need(len(rows)==len(mounts) and {r[key] for r in rows}==set(mounts),'exact mount inventory')
        for row in rows:
            src,ro=mounts[row[key]]
            alias=row['Source']==src or (src.startswith('/Users/') and row['Source']=='/host_mnt'+src)
            need(row['Type']=='bind' and alias and not row.get('VolumeOptions')
                 and (row['RW'] is (not ro) if effective else row.get('ReadOnly',False) is ro),
                 'exact source/alias/access mode')
    need(len({r['Destination'] for r in info['Mounts']})==len(info['Mounts'])
         and all(r['Destination'] in TMPFS and r['RW'] for r in info['Mounts'] if r['Type']=='tmpfs'),
         'no extra effective mounts')
    need(s['Status']=='created' and not s['Running'] and s['Pid']==0,'prestart created/not-running/pid0')


def read_review(path):
    rp=pin(path,100000);review=json.loads(Path(path).read_text());fp=pin(HERE/'FREEZE.json',100000)
    need(review.get('status')=='approved_for_one_reference_stage' and review.get('stage')==STAGE,'specific root approval required')
    need(review.get('freeze_sha256')==fp['sha256'],'exact reviewed freeze')
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    for row in freeze['files']:
        need(pin(ROOT/row['path'])=={'bytes':row['bytes'],'sha256':row['sha256']},'frozen source/evidence changed:'+row['path'])
    plan=json.loads((HERE/'PLAN.json').read_text())
    need(plan['whole_seconds']==plan['charge_seconds']==180 and plan['prior_charged_seconds']==440 and plan['known_after_charge']==620,'additional nonreset allowance')
    need(review.get('prior_charged_seconds')==440 and review.get('charge_seconds')==180,'review cost binding')
    return review,rp,plan,fp


def environment():
    return dict(os.environ,DOCKER_CONFIG=str(ROOT/'.cache-build/docker-config'),DOCKER_HOST=os.environ['NEURAL024_DOCKER_HOST'])


def create(name,program,mounts,base_env,deadline,run,interactive=False,extra_env=None):
    need(os.getuid()>0,'nonroot UID');user=f'{os.getuid()}:{os.getgid()}'
    env=dict(base_env);env.update({k:'2'for k in THREADS},PYTHONDONTWRITEBYTECODE='1');env.update(extra_env or {})
    initial=docker(['inspect','--type','container',name],min(deadline,time.monotonic()+3));write(run/(program+'.absence.json'),initial);need(absent(initial,name),'exact fresh container absence')
    argv=['create','--pull','never','--name',name,'--network','none','--read-only','--user',user,'--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory',str(4*1024**3),'--memory-swap',str(4*1024**3),'--cpus','2','--pids-limit','32','--shm-size','1048576','--log-driver','none','--workdir','/tmp','--entrypoint','python','--tmpfs','/tmp:'+TMPFS['/tmp']]
    if interactive:argv+=['-i']
    for k,(a,b)in ULIMITS.items():argv+=['--ulimit',f'{k}={a}:{b}']
    for k in (*THREADS,'PYTHONDONTWRITEBYTECODE',*(extra_env or {})):argv+=['--env',k+'='+env[k]]
    tokens=[]
    for dst,(src,ro)in mounts.items():
        p=Path(src);need(str(p.absolute())==src and not any(c in src for c in ',\r\n') and all(not q.is_symlink()for q in(p,*p.parents)),'canonical mount source')
        if ro:ordinary(p,10000000);need(p.stat().st_mode&4,'world-readable immutable source')
        else:need(p.is_dir() and not any(p.iterdir()) and p.stat().st_uid==os.getuid() and (p.stat().st_mode&0o777)==0o755,'empty owned0755 output')
        token=f'type=bind,src={src},dst={dst}'+(',readonly'if ro else '');tokens.append(token);argv+=['--mount',token]
    argv+=[IMAGE,'-I','-B','/program/'+program]
    need([argv[i+1]for i,x in enumerate(argv[:-1])if x=='--mount']==tokens,'literal canonical CLI mount proof')
    write(run/(program+'.create-intent.json'),{'container':name,'argv':[DOCKER,*argv],'mounts':mounts,'owned_before_dispatch':True})
    result=docker(argv,deadline);write(run/(program+'.create.json'),result);need(result['returncode']==0,'create failed')
    raw=docker(['inspect','--type','container',name],deadline);write(run/(program+'.prestart.json'),raw);need(raw['returncode']==0,'prestart inspection')
    verify(json.loads(raw['stdout'])[0],name,mounts,env,user,program,interactive)


def ended(name,program,deadline,run):
    raw=docker(['inspect','--type','container',name],deadline);write(run/(program+'.postrun.json'),raw);need(raw['returncode']==0,'postrun inspect')
    state=json.loads(raw['stdout'])[0]['State'];need(state['Status']=='exited'and not state['Running']and state['Pid']==0 and state['ExitCode']==0 and not state.get('OOMKilled')and not state.get('Error'),'clean worker exit')
    clean=cleanup(name,min(deadline,time.monotonic()+4));write(run/(program+'.cleanup.json'),clean);need(clean['absent'],'remove before next stage')
    return clean


def run_worker(name,program,mounts,base_env,deadline,run):
    create(name,program,mounts,base_env,deadline,run)
    result=docker(['start','--attach',name],deadline);write(run/(program+'.stdout.json'),result);need(result['returncode']==0,'worker failure:'+program)
    return ended(name,program,deadline,run)


def cleanup_order(names,run):
    files={'convert':'convert.py','train':'train.py','predict':'predict.py','score':'score_results.py'}
    def latest(item):
        path=run/(files[item[0]]+'.create-intent.json')
        return path.stat().st_mtime_ns if path.exists() else -1
    return sorted(names.items(),key=latest,reverse=True)

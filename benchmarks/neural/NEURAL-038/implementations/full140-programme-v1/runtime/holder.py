"""Trusted read-only tmpfs keeper/capture. Never parses candidate JSON."""
import argparse,base64,hashlib,json,os,re,stat,time
from pathlib import Path
CAP=16000000
CAPACITY=16777216

def need(ok,msg):
    if not ok:raise ValueError(msg)

def guard(root=Path('/capture')):
    cg=Path('/sys/fs/cgroup')
    need(os.getuid()==65534 and (cg/'memory.max').read_text().strip()=='536870912' and (cg/'memory.swap.max').read_text().strip()=='0' and (cg/'pids.max').read_text().strip()=='64','Observed holder cgroup bounds')
    quota,period=map(int,(cg/'cpu.max').read_text().split());need(quota==period and period>0,'Observed holder one CPU')
    rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines() if x.split(' - ',1)[0].split()[4]==str(root)]
    need(len(rows)==1,'Exact capture mount')
    left,right=rows[0].split(' - ',1)
    need(right.split()[0]=='tmpfs' and {'ro','noexec','nosuid','nodev'}<=set(left.split()[5].split(',')),'Read-only tmpfs')
    s=os.statvfs(root);need(s.f_blocks*s.f_frsize==CAPACITY,'Exact bounded volume')
    ready=[x for x in Path('/proc/self/mountinfo').read_text().splitlines() if x.split(' - ',1)[0].split()[4]=='/ready']
    need(len(ready)==1,'Exact holder-private ready mount')
    left,right=ready[0].split(' - ',1)
    need(right.split()[0]=='tmpfs' and {'rw','noexec','nosuid','nodev'}<=set(left.split()[5].split(',')),'Private writable ready tmpfs')
    r=os.statvfs('/ready');need(r.f_blocks*r.f_frsize==4096,'Exact4KiB ready capacity')
    r=Path('/ready').lstat();need(stat.S_ISDIR(r.st_mode) and stat.S_IMODE(r.st_mode)==0o700 and r.st_uid==r.st_gid==65534,'Private ready owner/mode')
    return root

def captured(root):
    # Bounded inventory: stop at the second entry, do not follow directories.
    with os.scandir(root) as scan:
        first=next(scan,None);second=next(scan,None)
        need(first is not None and first.name=='report.json' and second is None,'Only report.json')
    path=root/'report.json';s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=CAP,'Single-link bounded regular output')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);parts=[];count=0
        while count<=CAP:
            b=os.read(fd,min(65536,CAP+1-count))
            if not b:break
            parts.append(b);count+=len(b)
        z=os.fstat(fd);named=path.lstat()
        fields=('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
        need(all(getattr(s,k)==getattr(a,k)==getattr(z,k)==getattr(named,k) for k in fields),'Stable stopped output')
    finally:os.close(fd)
    raw=b''.join(parts);need(len(raw)==s.st_size,'Exact output extent')
    return {'schema':'neural038_opaque_capture_v1','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'base64':base64.b64encode(raw).decode('ascii')}

def token(value):
    need(type(value)is str and re.fullmatch('neural038-[a-f0-9]{24}/holder',value),'Exact holder identity token')
    return (json.dumps({'schema':'neurobench_holder_ready_v1','owner':value},sort_keys=True,separators=(',',':'))+'\n').encode('ascii')

def ready(value):
    expected=token(value);path=Path('/ready/READY')
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:return False
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==len(expected),'Exact ready marker extent')
        raw=os.read(fd,len(expected)+1);z=os.fstat(fd);n=path.lstat()
        need(all(getattr(a,k)==getattr(z,k)==getattr(n,k) for k in ('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')),'Stable ready marker')
        need(raw==expected,'Same holder initialized marker');return True
    finally:os.close(fd)

def initialize(root,value):
    need(os.getpid()==1,'Only holder PID1 publishes readiness')
    expected=token(value)
    with os.scandir('/ready') as scan:need(next(scan,None) is None,'Fresh private ready directory')
    with os.scandir(root) as scan:need(next(scan,None) is None,'Fresh output volume before ready')
    fd=os.open('/ready/temp.pending',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        view=memoryview(expected)
        while view:
            n=os.write(fd,view);need(n>0,'Ready marker write progress');view=view[n:]
        os.fsync(fd)
    finally:os.close(fd)
    # Only PID1 writes this fresh private mount. Readers see absent or the complete marker.
    os.rename('/ready/temp.pending','/ready/READY')
    fd=os.open('/ready',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    need(ready(value),'Own initialized marker')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['hold','ready','capture']);p.add_argument('--owner-token',required=True);a=p.parse_args();root=guard();token(a.owner_token)
    if a.action=='hold':
        initialize(root,a.owner_token)
        while True:time.sleep(1)
    elif a.action=='ready':print(json.dumps({'ready':ready(a.owner_token)},separators=(',',':')))
    else:
        need(ready(a.owner_token),'Holder initialization precedes capture')
        print(json.dumps(captured(root),separators=(',',':')))
if __name__=='__main__':main()

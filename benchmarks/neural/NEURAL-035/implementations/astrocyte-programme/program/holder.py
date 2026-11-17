"""Trusted opaque keeper; readiness is private, attempt-bound, and precedes producer access."""
import argparse,base64,hashlib,json,os,re,stat,time
from pathlib import Path
CAP=2000000
CAPACITY=8388608
READY_CAP=256
READY_ROOT=Path('/ready')
READY_SCHEMA='neurobench_holder_ready_v1'

def need(ok,msg):
    if not ok:raise ValueError(msg)

def owner_token(value):
    need(type(value)is str and re.fullmatch('neural035-[a-f0-9]{24}/holder',value),'exact current holder owner token')
    return value

def mount_guard(root,capacity,readonly):
    rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines() if x.split(' - ',1)[0].split()[4]==str(root)]
    need(len(rows)==1,'exact private mount')
    left,right=rows[0].split(' - ',1)
    options=set(left.split()[5].split(','))
    need(right.split()[0]=='tmpfs' and {'ro' if readonly else 'rw','noexec','nosuid','nodev'}<=options,'exact tmpfs mount policy')
    fs=os.statvfs(root);need(fs.f_blocks*fs.f_frsize==capacity,'exact bounded tmpfs')

def guard(root=Path('/capture')):
    cg=Path('/sys/fs/cgroup')
    need(os.getuid()==65534 and (cg/'memory.max').read_text().strip()=='134217728' and (cg/'memory.swap.max').read_text().strip()=='0' and (cg/'pids.max').read_text().strip()=='64','observed holder cgroup bounds')
    quota,period=map(int,(cg/'cpu.max').read_text().split());need(quota==period and period>0,'observed holder one CPU')
    mount_guard(root,CAPACITY,True);mount_guard(READY_ROOT,4096,False)
    sr=READY_ROOT.lstat();need(stat.S_ISDIR(sr.st_mode) and stat.S_IMODE(sr.st_mode)==0o700 and sr.st_uid==sr.st_gid==65534,'private readiness ownership/mode')
    return root

def marker_bytes(owner):
    return (json.dumps({'schema':READY_SCHEMA,'owner':owner_token(owner)},sort_keys=True,separators=(',',':'))+'\n').encode('ascii')

def publish_ready(root,owner,ready_root=READY_ROOT):
    need(os.getpid()==1,'only initial keeper PID1 publishes readiness')
    with os.scandir(root) as scan:need(next(scan,None)is None,'fresh output volume before readiness')
    with os.scandir(ready_root) as scan:need(next(scan,None)is None,'fresh holder-private ready root')
    body=marker_bytes(owner);need(len(body)<=READY_CAP,'bounded marker')
    pending=ready_root/'.pending';final=ready_root/'READY'
    fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        offset=0
        while offset<len(body):
            n=os.write(fd,body[offset:]);need(n>0,'complete marker write');offset+=n
        os.fsync(fd)
    finally:os.close(fd)
    os.rename(pending,final)
    fd=os.open(ready_root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def ready(owner,ready_root=READY_ROOT):
    expected=marker_bytes(owner);path=ready_root/'READY'
    try:fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    except FileNotFoundError:return False
    try:
        first=os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink==1 and first.st_uid==first.st_gid==65534 and 0<first.st_size<=READY_CAP,'ordinary private bounded marker')
        raw=os.read(fd,READY_CAP+1);last=os.fstat(fd);named=path.lstat()
        fields=('st_dev','st_ino','st_mode','st_size','st_nlink','st_uid','st_gid','st_mtime_ns','st_ctime_ns')
        need(len(raw)==first.st_size and all(getattr(first,k)==getattr(last,k)==getattr(named,k) for k in fields),'stable complete readiness marker')
        need(raw==expected,'exact current-attempt readiness marker')
    finally:os.close(fd)
    return True

def captured(root,owner):
    need(ready(owner),'capture requires prior admitted keeper readiness')
    with os.scandir(root) as scan:
        first=next(scan,None);second=next(scan,None)
        need(first is not None and first.name=='predictions.json' and second is None,'only predictions.json')
    path=root/'predictions.json';s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=CAP,'single-link bounded regular output')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);parts=[];count=0
        while count<=CAP:
            b=os.read(fd,min(65536,CAP+1-count))
            if not b:break
            parts.append(b);count+=len(b)
        z=os.fstat(fd);named=path.lstat();fields=('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
        need(all(getattr(s,k)==getattr(a,k)==getattr(z,k)==getattr(named,k) for k in fields),'stable stopped output')
    finally:os.close(fd)
    raw=b''.join(parts);need(len(raw)==s.st_size,'exact output extent')
    return {'schema':'slicetca_capture_v1','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'base64':base64.b64encode(raw).decode('ascii')}

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['hold','ready','capture']);p.add_argument('--owner-token',required=True)
    a=p.parse_args();owner=owner_token(a.owner_token);root=guard()
    if a.action=='hold':
        publish_ready(root,owner)
        while True:time.sleep(1)
    elif a.action=='ready':print(json.dumps({'ready':ready(owner)},separators=(',',':')))
    else:print(json.dumps(captured(root,owner),separators=(',',':')))
if __name__=='__main__':main()

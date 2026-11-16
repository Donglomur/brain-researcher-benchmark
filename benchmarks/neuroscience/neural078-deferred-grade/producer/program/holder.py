"""Trusted read-only tmpfs keeper/capture. Never parses candidate JSON."""
import argparse,base64,hashlib,json,os,re,stat,time
from pathlib import Path
CAP=65536
CAPACITY=1048576

def need(ok,msg):
    if not ok:raise ValueError(msg)

def guard(root=Path('/capture')):
    cg=Path('/sys/fs/cgroup')
    need(os.getuid()==65534 and (cg/'memory.max').read_text().strip()=='134217728' and (cg/'memory.swap.max').read_text().strip()=='0' and (cg/'pids.max').read_text().strip()=='64','Observed holder cgroup bounds')
    quota,period=map(int,(cg/'cpu.max').read_text().split());need(quota==period and period>0,'Observed holder one CPU')
    rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines() if x.split(' - ',1)[0].split()[4]==str(root)]
    need(len(rows)==1,'Exact capture mount')
    left,right=rows[0].split(' - ',1)
    need(right.split()[0]=='tmpfs' and {'ro','noexec','nosuid','nodev'}<=set(left.split()[5].split(',')),'Read-only tmpfs')
    s=os.statvfs(root);need(s.f_blocks*s.f_frsize==CAPACITY,'Exact bounded volume')
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
    return {'schema':'neural078_opaque_capture_v1','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'base64':base64.b64encode(raw).decode('ascii')}

READY_CAPACITY=4096
READY_OPTIONS='rw,nosuid,nodev,noexec,size=4096,uid=65534,gid=65534,mode=0700'

def ready_guard(root=Path('/ready')):
    rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines() if x.split(' - ',1)[0].split()[4]==str(root)]
    need(len(rows)==1,'Exact private readiness mount')
    left,right=rows[0].split(' - ',1);flags=set(left.split()[5].split(','))
    need(right.split()[0]=='tmpfs' and {'rw','noexec','nosuid','nodev'}<=flags and 'ro' not in flags,'Private writable readiness tmpfs')
    s=root.lstat();need(stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode)==0o700 and s.st_uid==s.st_gid==65534,'Private readiness directory owner/mode')
    v=os.statvfs(root);need(v.f_blocks*v.f_frsize==READY_CAPACITY,'Exact readiness capacity')
    return root

def marker_bytes(owner,kind=None):
    need(type(owner)is str and re.fullmatch(r'neural078-[0-9a-f]{24}/holder',owner),'Exact holder owner token')
    value={'schema':'neurobench_holder_ready_v1','owner':owner}
    # TASK_KIND_CHECK is replaced by the source author, not a runtime hook.
    need(kind is None,'No output role in this holder ABI')
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')
    need(len(raw)<=256,'Bounded readiness marker')
    return raw

def marker_stamp(s):
    return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns'))

def marker_ready(root,expected):
    path=root/'READY'
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:return False
    try:
        a=os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and stat.S_IMODE(a.st_mode)==0o600 and a.st_nlink==1 and a.st_uid==a.st_gid==65534 and a.st_size==len(expected),'Exact ordinary readiness marker')
        parts=[];remaining=len(expected)+1
        while remaining:
            raw=os.read(fd,remaining)
            if not raw:break
            parts.append(raw);remaining-=len(raw)
        need(b''.join(parts)==expected and marker_stamp(a)==marker_stamp(os.fstat(fd))==marker_stamp(path.lstat()),'Stable matching initialized-holder marker')
    finally:os.close(fd)
    return True

def publish_ready(root,expected):
    need(os.getpid()==1,'Only holder initializer publishes readiness')
    with os.scandir(root) as scan:need(next(scan,None)is None,'Fresh private readiness volume')
    temporary=root/'.pending';target=root/'READY'
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        offset=0
        while offset<len(expected):
            count=os.write(fd,expected[offset:]);need(type(count)is int and count>0,'Complete readiness marker write');offset+=count
        os.fsync(fd);s=os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1 and s.st_uid==s.st_gid==65534 and s.st_size==len(expected) and marker_stamp(s)==marker_stamp(temporary.lstat()),'Stable private marker before publication')
    finally:os.close(fd)
    # One initialized PID1 is the only writer of this fresh holder-private mount.
    # Rename reuses the same data-bearing inode; no second 4KiB page is needed.
    need(not os.path.lexists(target),'No earlier readiness marker')
    os.rename(temporary,target)
    directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(directory)
    finally:os.close(directory)
    need(marker_ready(root,expected),'Published matching readiness marker')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['hold','ready','capture']);p.add_argument('--owner-token',required=True);a=p.parse_args();root=guard();ready_root=ready_guard();expected=marker_bytes(a.owner_token)
    if a.action=='hold':
        with os.scandir(root) as scan:need(next(scan,None) is None,'Fresh output volume')
        publish_ready(ready_root,expected)
        while True:time.sleep(1)
    elif a.action=='ready':print(json.dumps({'ready':marker_ready(ready_root,expected)},separators=(',',':')))
    else:
        need(marker_ready(ready_root,expected),'Initialized holder required for capture')
        print(json.dumps(captured(root),separators=(',',':')))
if __name__=='__main__':main()

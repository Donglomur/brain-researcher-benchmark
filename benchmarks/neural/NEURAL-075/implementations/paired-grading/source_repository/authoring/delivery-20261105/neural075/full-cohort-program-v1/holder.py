"""Read-only output keeper: one stopped score file, bounded chunk transport."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import time

CAP = 4 * 1024**2
CHUNK = 4 * 1024**2
VOLUME = 16 * 1024**2

def require(ok):
    if not ok:
        raise ValueError('stopped output boundary')

def identity(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)

def read(root, name, offset=None):
    """Same-open bounded capture. Producer must already be removed by host."""
    require(root.is_dir() and not root.is_symlink())
    with os.scandir(root) as it:
        rows = [next(it, None) for _ in range(2)]
    require(rows[1] is None and rows[0] is not None and rows[0].name == 'prediction.json')
    require(name in {'prediction.json'})
    path = root/name; before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= CAP)
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        require(identity(os.fstat(f.fileno())) == identity(before))
        if offset is None:
            digest = hashlib.sha256(); total = 0
            while total <= before.st_size:
                raw = f.read(min(CHUNK, before.st_size+1-total))
                if not raw: break
                total += len(raw); digest.update(raw)
            require(total == before.st_size)
            out = {'schema':'neural075_output_index_v1','bytes':total,'sha256':digest.hexdigest()}
        else:
            require(type(offset) is int and 0 <= offset < before.st_size and offset % CHUNK == 0)
            f.seek(offset); raw = f.read(min(CHUNK, before.st_size-offset))
            require(len(raw) == min(CHUNK, before.st_size-offset))
            out = {'schema':'neural075_output_chunk_v1','offset':offset,'total_bytes':before.st_size,
                   'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                   'base64':base64.b64encode(raw).decode('ascii')}
        require(identity(os.fstat(f.fileno())) == identity(before) == identity(path.lstat()))
    return out

def guard(root):
    cg=Path('/sys/fs/cgroup')
    require(os.getuid()==65534 and (cg/'memory.max').read_text().strip()=='268435456'
            and (cg/'memory.swap.max').read_text().strip()=='0' and (cg/'pids.max').read_text().strip()=='64')
    q,p=map(int,(cg/'cpu.max').read_text().split());require(q==p and p>0)
    rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines()
          if x.split(' - ',1)[0].split()[4]==str(root)]
    require(len(rows)==1);a,b=rows[0].split(' - ',1)
    require(b.split()[0]=='tmpfs' and {'ro','noexec','nosuid','nodev'} <= set(a.split()[5].split(',')))
    s=os.statvfs(root);require(s.f_blocks*s.f_frsize==VOLUME)

def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=('hold','ready','index','chunk'));a.add_argument('--offset',type=int);a.add_argument('--name',choices=('prediction.json',))
    v=a.parse_args();root=Path('/capture');guard(root)
    if v.action=='hold':
        with os.scandir(root) as it:require(next(it,None) is None)
        while True:time.sleep(1)
    elif v.action=='ready':print('{"ready":true}')
    else:print(json.dumps(read(root,v.name,None if v.action=='index' else v.offset),separators=(',',':')))

if __name__=='__main__':main()

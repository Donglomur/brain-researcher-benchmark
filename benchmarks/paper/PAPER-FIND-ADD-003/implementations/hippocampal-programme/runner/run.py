"""Public phase publisher: no paper method, labels, evaluator or reference code."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def require(ok,why):
    if not ok:raise ValueError(why)


def publish(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    primary=None
    try:
        offset=0
        while offset<len(raw):
            n=os.write(fd,raw[offset:]);require(n>0,'Complete publication progress');offset+=n
        os.fsync(fd)
    except BaseException as e:primary=e;raise
    finally:
        try:os.close(fd)
        except BaseException:
            if primary is None:raise
    parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(parent)
    finally:os.close(parent)


def main():
    request_raw=Path('/request.json').read_bytes();request=json.loads(request_raw)
    job=json.loads(Path('/job/JOB.json').read_bytes())
    command=job['command'];require(type(command) is list and command and command[0].startswith('/'),'Exact absolute producer command')
    completed=subprocess.run(command,stdin=subprocess.DEVNULL,check=False,close_fds=True)
    require(completed.returncode==0,'Producer nonzero: outputs remain unadmitted')
    root=Path('/output');limits=request['resources']
    require(not (root/'OUTPUTS.json').exists(),'Only fixed publisher creates completion envelope')
    if not (root/'RESULT.json').exists():publish(root/'RESULT.json',canonical({'schema':'h_producer_result_v1','action':request['action'],'role':request['role'],'producer_exit':0}))
    files={};total=0
    for p in sorted(root.rglob('*')):
        st=p.lstat();require(not stat.S_ISLNK(st.st_mode),'No exported links')
        if stat.S_ISDIR(st.st_mode):continue
        require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<=limits['max_file_bytes'],'Bounded ordinary complete output')
        total+=st.st_size;require(total<=limits['max_output_bytes'] and len(files)<limits['max_files'],'Complete output extent')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd);h=hashlib.sha256();n=0
            while True:
                part=os.read(fd,1048576)
                if not part:break
                n+=len(part);require(n<=before.st_size,'Stable output extent');h.update(part)
            after=os.fstat(fd)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and n==before.st_size,'Stable complete output')
        finally:os.close(fd)
        files[str(p.relative_to(root))]={'bytes':n,'sha256':h.hexdigest()}
    body=canonical({'schema':'h_transport_output_manifest_v1','phase_id':request['phase_id'],'request_sha256':pin(request_raw)['sha256'],'files':files})
    require(len(body)<=limits['manifest_bytes'] and total+len(body)<=limits['max_output_bytes'],'Final manifest allocation')
    publish(root/'OUTPUTS.json',body)


if __name__=='__main__':main()

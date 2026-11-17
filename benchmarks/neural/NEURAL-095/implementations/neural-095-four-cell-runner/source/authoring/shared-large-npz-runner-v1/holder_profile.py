"""Trusted tmpfs holder/capture; no candidate imports or numerical decoding."""
from pathlib import Path
import argparse,base64,hashlib,json,os,stat,time
CAPACITY=40*1024*1024;HARD_MAX_OUTPUT=32*1024*1024

def guard():
    root=Path('/capture');rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines()if x.split(' - ',1)[0].split()[4]=='/capture'];assert len(rows)==1
    left,right=rows[0].split(' - ',1);assert right.split()[0]=='tmpfs'and {'ro','noexec','nosuid','nodev'}<=set(left.split()[5].split(','))
    st=os.statvfs(root);assert st.f_blocks*st.f_frsize==CAPACITY
    return root

def capture(output_name,max_output):
    root=guard()
    if set(os.listdir(root))!={output_name}:return {'status':'output_boundary_rejected','reason':'exact_single_submission_required'}
    fd=os.open(root/output_name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<before.st_size<=max_output):return {'status':'output_boundary_rejected','reason':'bounded_single_link_regular_output_required'}
        chunks=[];total=0
        while total<before.st_size:
            b=os.read(fd,min(65536,before.st_size-total));assert b,'truncated output';chunks.append(b);total+=len(b)
        after=os.fstat(fd);assert os.read(fd,1)==b''and tuple(getattr(before,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))==tuple(getattr(after,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
    finally:os.close(fd)
    body=b''.join(chunks);return {'status':'captured','name':output_name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'base64':base64.b64encode(body).decode()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['hold','capture']);p.add_argument('--output-name',required=True);p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    assert 0<a.max_output_bytes<=HARD_MAX_OUTPUT and 0<len(a.output_name)<=64 and a.output_name not in('.', '..')and all(c.isascii()and(c.isalnum()or c in'._-')for c in a.output_name)
    if a.action=='capture':print(json.dumps(capture(a.output_name,a.max_output_bytes),separators=(',',':')))
    else:
        assert list(guard().iterdir())==[];print('HOLDER_READY',flush=True)
        while True:time.sleep(10)

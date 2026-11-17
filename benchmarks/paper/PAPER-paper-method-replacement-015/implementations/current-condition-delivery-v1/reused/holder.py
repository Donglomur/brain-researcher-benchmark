"""Read-only output keeper; inert two-file capture after producer removal.
Reuses the NEURAL069 capture/guard/hold pattern. No numeric deserialization,
candidate import, private target access, grading or fit occurs here.
"""
import argparse,base64,hashlib,json,os,stat,time
from pathlib import Path
CAPACITY=33554432
FOLD_CAP=100000
TOTAL_CAP=1100000

def need(ok,msg):
    if not ok:raise ValueError(msg)
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def parse(b):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'Duplicate key');out[k]=v
        return out
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))
def capture(p,cap):
    s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=cap,'Ordinary bounded output')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);parts=[];n=0
        while n<=cap:
            b=os.read(fd,min(65536,cap+1-n))
            if not b:break
            n+=len(b);parts.append(b)
        z=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_mode','st_size','st_nlink','st_mtime_ns','st_ctime_ns')
        need(all(getattr(s,k)==getattr(a,k)==getattr(z,k)==getattr(named,k)for k in fields),'Stable stopped output')
        body=b''.join(parts);need(len(body)==s.st_size,'Exact extent');return body
    finally:os.close(fd)
def prediction_cap(lock):
    need(type(lock)is dict and set(lock)=={'schema','prediction_max_bytes'} and lock['schema']=='cascade_spinal_capture_lock_v1','Exact trusted capture lock')
    cap=lock['prediction_max_bytes']
    need(type(cap)is int and 0<cap<=TOTAL_CAP,'Trusted shape-derived prediction cap')
    return cap
def index(root,lock):
    cap=prediction_cap(lock);wanted={'fold.json','predictions.npy'};found=set()
    with os.scandir(root)as scan:
        for item in scan:
            need(len(found)<2 and item.name in wanted and item.name not in found,'Exact two-file output inventory')
            s=item.stat(follow_symlinks=False);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'Ordinary output inventory');found.add(item.name)
    need(found==wanted,'Complete two-file output inventory')
    fold=capture(root/'fold.json',FOLD_CAP);prediction=capture(root/'predictions.npy',cap)
    need(len(fold)+len(prediction)<=TOTAL_CAP,'Combined output extent')
    return {'schema':'cascade_spinal_capture_index_v1','files':[
        {'path':'fold.json',**pin(fold)}, {'path':'predictions.npy',**pin(prediction)}]}
def file_reply(root,idx,name):
    row=next((r for r in idx['files']if r['path']==name),None);need(row is not None,'Bound output name')
    body=capture(root/name,row['bytes']);need(pin(body)=={k:row[k]for k in ('bytes','sha256')},'Captured output pin')
    return {'schema':'cascade_spinal_capture_file_v1','path':name,**pin(body),'base64':base64.b64encode(body).decode('ascii')}
def guard(root):
    cg=Path('/sys/fs/cgroup');need(os.getuid()==65534 and (cg/'memory.max').read_text().strip()=='134217728' and (cg/'memory.swap.max').read_text().strip()=='0' and (cg/'pids.max').read_text().strip()=='64','Holder resources')
    q,p=map(int,(cg/'cpu.max').read_text().split());need(q==p and p>0,'Holder CPU')
    rows=[x for x in Path('/proc/self/mountinfo').read_text().splitlines()if x.split(' - ',1)[0].split()[4]==str(root)]
    need(len(rows)==1,'Capture mount');a,b=rows[0].split(' - ',1);need(b.split()[0]=='tmpfs' and {'ro','noexec','nosuid','nodev'}<=set(a.split()[5].split(',')),'Readonly tmpfs')
    s=os.statvfs(root);need(s.f_blocks*s.f_frsize==CAPACITY,'Bounded output tmpfs')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['hold','ready','index','file']);p.add_argument('--name');a=p.parse_args();root=Path('/capture');guard(root)
    if a.action=='hold':
        with os.scandir(root)as scan:need(next(scan,None)is None,'Fresh volume')
        while True:time.sleep(1)
    elif a.action=='ready':print('{"ready":true}')
    else:
        lock=parse(capture(Path('/trusted/LOCK.json'),100000));idx=index(root,lock)
        result=idx if a.action=='index'else file_reply(root,idx,a.name)
        print(json.dumps(result,separators=(',',':'),allow_nan=False))
if __name__=='__main__':main()

"""Read-only output keeper; inert 81-file capture after producer removal.
No array deserialization, candidate imports, targets, grading or fits.
"""
import argparse,base64,hashlib,json,os,re,stat,time
from pathlib import Path
CAPACITY=33554432

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
def records(raw,lock):
    need(type(raw)is bytes and 0<len(raw)<=100000,'Bounded submission')
    v=parse(raw)
    need(type(v)is dict and set(v)=={'task_id','roster_sha256','predictions'} and v['task_id']=='NEURAL-069' and v['roster_sha256']==lock['roster']['sha256'],'Exact task/roster')
    rows=v['predictions'];need(type(rows)is list and len(rows)==80 and len(lock['cases'])==80,'All80 outputs')
    names=set();total=0
    for row,c in zip(rows,lock['cases']):
        need(type(row)is dict and set(row)=={'id','path','bytes','sha256'} and row['id']==c['id'],'Ordered case identity')
        name=row['path'];need(type(name)is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\.npy',name) is not None and '..' not in name and name not in names,'Distinct safe filename');names.add(name)
        need(type(row['bytes'])is int and 0<row['bytes']<=c['max_bytes'],'Shape-derived extent bound')
        need(type(row['sha256'])is str and re.fullmatch('[a-f0-9]{64}',row['sha256']) is not None,'Digest');total+=row['bytes']
    need(total+len(raw)<=lock['output_bytes_cap'],'Full panel extent');return rows

def index(root,lock):
    raw=capture(root/'submission.json',100000);rows=records(raw,lock);wanted={'submission.json',*[r['path']for r in rows]};found=set()
    with os.scandir(root)as scan:
        for item in scan:
            need(len(found)<81 and item.name in wanted and item.name not in found,'Exact81-file output inventory')
            s=item.stat(follow_symlinks=False);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'Ordinary output inventory');found.add(item.name)
    need(found==wanted,'Complete81-file output inventory');return {'schema':'neural069_capture_index_v1','submission':{'path':'submission.json',**pin(raw)},'predictions':rows}
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
        if a.action=='index':print(json.dumps(idx,separators=(',',':')))
        else:
            row=next((r for r in [idx['submission'],*idx['predictions']]if r['path']==a.name),None);need(row is not None,'Bound output name')
            body=capture(root/a.name,row['bytes']);need(pin(body)=={k:row[k]for k in ('bytes','sha256')},'Captured output pin')
            print(json.dumps({'schema':'neural069_capture_file_v1','path':a.name,**pin(body),'base64':base64.b64encode(body).decode('ascii')},separators=(',',':')))
if __name__=='__main__':main()

"""Trusted standalone output holder; never imported into the candidate process."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

CAP=8_000_000_000
ATTRS=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')


def need(v,m):
    if not v: raise ValueError(m)


def strict(raw):
    def pairs(items):
        value={}
        for k,v in items:
            need(k not in value,'Duplicate JSON'); value[k]=v
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))


def ordinary(path):
    need(all(not p.is_symlink() for p in (path,*path.parents)),'No linked output paths')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); a=os.fstat(fd)
    if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1):
        os.close(fd);raise ValueError('Single-link ordinary output')
    return fd,a


def stable(path,fd,a):
    z,linked=os.fstat(fd),path.lstat()
    need(all(getattr(a,k)==getattr(z,k)==getattr(linked,k) for k in ATTRS),'Stable complete output')


def read(path,cap):
    fd,a=ordinary(path)
    try:
        need(0<a.st_size<=cap,'Bounded metadata');raw=os.read(fd,cap+1)
        need(len(raw)==a.st_size,'Complete metadata');stable(path,fd,a);return raw
    finally:os.close(fd)


def write(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f:f.write(raw);f.flush();os.fsync(fd)
    finally:os.close(fd)
    os.chmod(path,0o444)


def capture(root,output,expected,end):
    raw=read(root/'submission.json',4_000_000);c=strict(raw)
    need(set(c)=={'schema','task_id','query_sha256','information_arm','files'} and
         c['schema']=='cbramod_prediction_artifacts_v1' and c['task_id']==expected['task_id'] and
         c['query_sha256']==expected['query_sha256'] and c['information_arm']==expected['information_arm'],
         'Exact arm and query binding')
    need(type(c['files']) is list and len(c['files'])==len(expected['cases']),'Complete original case roster')
    names=set();total=0
    for row,case in zip(c['files'],expected['cases']):
        need(type(row) is dict and set(row)=={'case','path','shape','dtype','bytes','sha256'} and
             row['case']==case['case'] and row['shape']==case['shape'] and
             all(type(x) is int for x in row['shape']) and row['dtype'] in ('<f4','<f8'),'Complete original artifact rectangle')
        need(type(row['path']) is str and re.fullmatch(r'predictions/[A-Za-z0-9_.-]{1,160}\.npy',row['path']) and
             row['path'] not in names,'Unique safe output path')
        need(type(row['bytes']) is int and 80<=row['bytes']<=CAP and type(row['sha256']) is str and
             re.fullmatch('[0-9a-f]{64}',row['sha256']),'Bounded artifact pin')
        total+=row['bytes'];need(total<=CAP,'Full8GB candidate budget');names.add(row['path'])
    need({p.name for p in root.iterdir()}=={'submission.json','predictions'} and
         not(root/'predictions').is_symlink() and (root/'predictions').is_dir() and
         {'predictions/'+p.name for p in (root/'predictions').iterdir()}==names,'Exact output tree, no extras')
    need(not any(output.iterdir()),'Fresh trusted capture directory')
    (output/'predictions').mkdir(mode=0o755)
    (output/'predictions').chmod(0o755)
    for row in c['files']:
        source=root/row['path'];dest=output/row['path'];fd,a=ordinary(source);out=None
        try:
            need(a.st_size==row['bytes'],'Complete artifact extent')
            out=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            sha=hashlib.sha256();count=0
            with os.fdopen(fd,'rb',closefd=False) as f,os.fdopen(out,'wb',closefd=False) as g:
                while True:
                    need(time.monotonic()<end,'Whole capture deadline')
                    b=f.read(min(65536,row['bytes']+1-count))
                    if not b:break
                    count+=len(b);need(count<=row['bytes'],'Artifact grew');sha.update(b);g.write(b)
                g.flush();os.fsync(out)
            stable(source,fd,a)
            need(count==row['bytes'] and sha.hexdigest()==row['sha256'],'Full artifact hash')
            os.chmod(dest,0o444)
        finally:
            os.close(fd)
            if out is not None:os.close(out)
    write(output/'submission.json',raw)
    return {'status':'captured','files':len(names),'artifact_bytes':total,
            'submission':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}


def main():
    need(sys.flags.isolated,'Isolated trusted helper')
    if sys.argv[1:] == ['hold']:
        while True:time.sleep(30)
    need(len(sys.argv)==3 and sys.argv[1]=='capture','Exact capture operation')
    seconds=int(sys.argv[2]);need(1<=seconds<=86400,'Explicit whole capture budget')
    expected=strict(read(Path('/trusted/expected.json'),4_000_000))
    result=capture(Path('/capture'),Path('/export'),expected,time.monotonic()+seconds)
    print(json.dumps(result,allow_nan=False,sort_keys=True))


if __name__=='__main__':main()

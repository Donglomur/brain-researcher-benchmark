"""Bounded actual ordinary-file copy and prefix custody; no array interpretation."""
import hashlib
import os
from pathlib import Path
from .common import require,ordinary,stamp,CaptureFailure

def copy(src,dst,expected,budget,records):
    src=Path(src);dst=Path(dst);before=ordinary(src)
    require(before.st_size==expected['bytes'] and not dst.exists(),'original source extent/fresh destination')
    budget.check('before stream copy');budget.admit_read(expected['bytes']+1);budget.admit_write(expected['bytes'])
    row={'source':str(src),'destination':str(dst),'expected':expected,'read_bytes':0,'written_bytes':0,'complete':False,'errors':[]}
    records.append(row);fi=fo=None;h=hashlib.sha256();first=None
    try:
        fi=os.open(src,os.O_RDONLY|os.O_NOFOLLOW);fo=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        budget.file_created()
        require(stamp(os.fstat(fi))==stamp(before),'same original open source')
        while True:
            budget.check('before copy read');body=os.read(fi,min(1048576,expected['bytes']+1-row['read_bytes']))
            row['read_bytes']+=len(body);budget.read(len(body));budget.check('after copy read return')
            require(row['read_bytes']<=expected['bytes'],'source grew')
            if not body:break
            offset=0
            while offset<len(body):
                try:n=os.write(fo,memoryview(body)[offset:])
                except BaseException as exc:
                    n=budget.failed_write('copy:'+str(dst),exc,len(body)-offset)
                    if type(n)is int and 0<n<=len(body)-offset:
                        budget.written(n);h.update(memoryview(body)[offset:offset+n]);row['written_bytes']+=n
                    elif n is None:row['unknown_write_extent']=True
                    raise
                n=budget.write_count('copy:'+str(dst),n,len(body)-offset)
                if n is None:row['unknown_write_extent']=True
                require(n is not None and n>0,'positive actual copy write')
                budget.written(n);h.update(memoryview(body)[offset:offset+n]);row['written_bytes']+=n;offset+=n
                budget.check('after copy write return')
        require(row['read_bytes']==row['written_bytes']==expected['bytes'] and h.hexdigest()==expected['sha256'],'whole exact source copy')
        require(stamp(os.fstat(fi))==stamp(before)==stamp(src.lstat()),'original stable source')
        os.fchmod(fo,0o444);os.fsync(fo);budget.check('after copy fsync')
    except BaseException as exc:first=exc;row['errors'].append(('copy',exc))
    finally:
        for role,fd in [('output',fo),('input',fi)]:
            if fd is not None:
                try:os.close(fd)
                except BaseException as exc:
                    row['errors'].append(('close_'+role,exc))
                    budget.uncertain('copy:'+str(dst)+':'+role,'managed_descriptor_closure',exc,descriptor=fd)
                    if first is None:first=exc
        row['sha256']=h.hexdigest()
    if first is not None:raise CaptureFailure(first,row['errors'],None,expected) from first
    budget.check('after copy closure');row['complete']=True
    return {'bytes':row['written_bytes'],'sha256':row['sha256']}

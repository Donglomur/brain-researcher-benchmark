"""Run only the immutable original baseline and capture exact two-file output.

Future scientific producer, not invoked during source construction. Original
warnings/prints and failed-fit dispositions are preserved. Daemon logs disabled.
"""
import sys
sys.path.insert(0,'/trusted')
from entry_common import guard,need
import os,stat,runpy
from pathlib import Path

def publish(source,target,cap):
    a=b=None;primary=None
    try:
        a=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);s=os.fstat(a)
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=cap,'complete bounded baseline file')
        b=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);left=s.st_size
        while left:
            x=os.read(a,min(left,1048576));need(x,'complete baseline copy');left-=len(x);v=memoryview(x)
            while v:n=os.write(b,v);need(n>0,'complete baseline write');v=v[n:]
        need(not os.read(a,1),'exact baseline EOF');os.fsync(b)
    except BaseException as e:primary=e;raise
    finally:
        failures=[]
        for fd in (a,b):
            if fd is not None:
                try:os.close(fd)
                except BaseException as e:failures.append(type(e).__name__)
        if failures:
            if primary is not None:primary.add_note('Independent baseline FD cleanup: '+','.join(failures))
            else:raise OSError('Independent baseline FD cleanup: '+','.join(failures))

def main():
    guard('reference');root=Path('/work/reference');need(not root.exists(),'fresh exact baseline staging')
    sys.argv=['/trusted/baseline.py','--input','/input/data','--output',str(root)]
    runpy.run_path('/trusted/baseline.py',run_name='__main__')
    need({p.name for p in root.iterdir()}=={'estimates.csv','methods.json'},'exact original baseline outputs')
    for name,cap in [('estimates.csv',100000000),('methods.json',20000)]:publish(root/name,Path('/output')/name,cap)
    fd=os.open('/output',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
if __name__=='__main__':main()

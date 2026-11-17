"""Authenticated capsule-local imports; adapted from selected N042 launcher.

The launcher's own bytes/image/argv are authenticated by the enclosing Engine.
This is source construction; no native deployment has been qualified.
"""
import hashlib,importlib.abc,importlib.util,json,math,os,stat,sys,time
from pathlib import Path

def main(path,size,sha,origin,deadline):
    reserved=0;cap=2<<20
    def tick():
        if not(math.isfinite(origin) and math.isfinite(deadline) and origin<=time.monotonic()<deadline):raise ValueError('original capsule deadline')
    def capture(path,size,sha):
        nonlocal reserved
        tick();p=Path(path)
        if not str(p).startswith('/inputs/') or any(x in('.','..') for x in str(p).split('/')):raise ValueError('fixed input namespace')
        if type(size)is not int or size<0 or reserved+size+1>cap:raise ValueError('precharged source extent')
        reserved+=size+1
        for parent in p.parents:
            if not stat.S_ISDIR(os.lstat(parent).st_mode):raise ValueError('ordinary input parents')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=size or before.st_mode&0o222:raise ValueError('exact readonly source')
            chunks=[];left=size
            while left:
                tick();part=os.read(fd,min(left,65536))
                if not part:raise ValueError('short captured source')
                chunks.append(part);left-=len(part)
            stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if os.read(fd,1) or stamp(before)!=stamp(os.fstat(fd)) or stamp(before)!=stamp(os.lstat(p)):raise ValueError('source inode/name changed')
            raw=b''.join(chunks)
            if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('source identity changed')
            return raw
        finally:
            primary=sys.exception()
            try:os.close(fd)
            except BaseException as later:
                if primary is not None:raise BaseExceptionGroup('source and close',[primary,later])from None
                raise
    def parse(raw):
        def pairs(rows):
            out={}
            for k,v in rows:
                if k in out:raise ValueError('duplicate JSON key')
                out[k]=v
            return out
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite')))
    cfg=parse(capture(path,size,sha));cap=cfg['source_read_bytes']
    if not(reserved<=cap<=32<<20) or cfg['origin']!=origin or cfg['deadline']!=deadline or cfg['schema']!='n041_launch_v1':raise ValueError('exact launch admission')
    bodies={}
    for name,p in cfg['files'].items():
        if not name.endswith('.py') or '/' in name or '\\' in name or name.startswith('.'):raise ValueError('flat exact source member')
        bodies[name[:-3]]=(capture('/inputs/source/'+name,p['bytes'],p['sha256']),'/inputs/source/'+name)
    class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,fullname,path=None,target=None):
            return importlib.util.spec_from_loader(fullname,self) if fullname in bodies else None
        def create_module(self,spec):return None
        def exec_module(self,module):
            tick();raw,name=bodies[module.__name__];module.__file__=name
            exec(compile(raw,name,'exec',dont_inherit=True),module.__dict__);tick()
    if any(k in sys.modules for k in bodies):raise ValueError('no preloaded task source module')
    sys.meta_path.insert(0,Captured())
    rp=cfg['request'];req=parse(capture('/inputs/REQUEST.json',rp['bytes'],rp['sha256']))
    if req['origin']!=origin or req['deadline']!=deadline:raise ValueError('request clock join')
    from core import encoded,pin,need
    identity=req.pop('request_identity');need(pin(encoded(req))==identity,'complete request identity');req['request_identity']=identity
    entry=cfg['entry']
    if entry not in('worker','preparation_worker'):raise ValueError('fixed captured worker entry')
    module=__import__(entry)
    return module.run(req)

if __name__=='__main__':
    if len(sys.argv)!=6:raise ValueError('exact capsule argv')
    main(sys.argv[1],int(sys.argv[2]),sys.argv[3],float(sys.argv[4]),float(sys.argv[5]))

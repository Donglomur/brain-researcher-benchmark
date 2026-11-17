"""Source-bound root entry; no source imports or cache reads before admission."""
import hashlib,json,os,stat,sys,types
from pathlib import Path

class BootstrapFailure(RuntimeError):
    def __init__(self,first,secondary,prefix):
        self.first=first;self.secondary=tuple(secondary);self.prefix=prefix
        super().__init__('source bootstrap failed; original and close errors retained')
def capture(path,cap):
    fd=None;raw=bytearray();first=None;secondary=[]
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or not 0<s.st_size<=cap:raise ValueError('finite ordinary bootstrap member')
        while len(raw)<=s.st_size:
            part=os.read(fd,min(65536,s.st_size+1-len(raw)))
            if not part:break
            raw.extend(part)
        t=os.fstat(fd)
        if len(raw)!=s.st_size or (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=(t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns):raise ValueError('stable bootstrap capture')
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                if first is None:first=error
                else:secondary.append(error)
    if first is not None:raise BootstrapFailure(first,secondary,bytes(raw))from first
    return bytes(raw)
def main():
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise ValueError('actual -I -S -B required')
    if len(sys.argv)not in(5,8)or sys.argv[1]not in('run','child'):raise ValueError('usage: entry.py run CONFIG CONFIG_SHA256 SOURCE_MANIFEST_SHA256')
    root=Path(__file__).absolute().parent;manifest=capture(root/'SOURCE_MANIFEST.json',65536)
    if hashlib.sha256(manifest).hexdigest()!=sys.argv[4]:raise ValueError('externally selected source graph')
    lock=json.loads(manifest);rows={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']}for r in lock['files']};total=0;bodies={}
    if len(rows)!=len(lock['files']):raise ValueError('unique source graph')
    for name,row in rows.items():
        if '/'in name or not name.endswith('.py'):continue
        total+=row['bytes']+1
        if total>1048576:raise ValueError('fixed whole native bootstrap source ceiling')
        raw=capture(root/name,row['bytes'])
        if len(raw)!=row['bytes']or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('source member pin')
        bodies[name]=raw
    package=types.ModuleType('n090native');package.__path__=[str(root)];sys.modules['n090native']=package
    for name in('common','source_loader','process','cgroup','token_budget','broker','native','owner','controller'):
        mod=types.ModuleType('n090native.'+name);mod.__package__='n090native';mod.__file__=str(root/(name+'.py'));sys.modules[mod.__name__]=mod
        exec(compile(bodies[name+'.py'],mod.__file__,'exec',dont_inherit=True),mod.__dict__)
    raw=capture(sys.argv[2],1048576)
    if hashlib.sha256(raw).hexdigest()!=sys.argv[3]:raise ValueError('externally selected complete request')
    cfg=sys.modules['n090native.common'].parse(raw);controller=sys.modules['n090native.controller']
    if sys.argv[1]=='child':
        if len(sys.argv)!=8:raise ValueError('exact internal timing argv')
        controller.run_child(cfg,root,rows,tuple(float(x)for x in sys.argv[5:]))
    else:
        if len(sys.argv)!=5:raise ValueError('exact external argv')
        controller.invoke(cfg,root,rows,Path(sys.argv[2]).absolute(),{'bytes':len(raw),'sha256':sys.argv[3]},{'bytes':len(manifest),'sha256':sys.argv[4]})
if __name__=='__main__':main()

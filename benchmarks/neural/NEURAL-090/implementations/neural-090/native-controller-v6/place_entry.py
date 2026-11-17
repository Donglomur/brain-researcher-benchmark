"""Fixed trusted exec-time cgroup join; no Python preexec callback or project import."""
import base64,json,os,stat,sys,time
from pathlib import Path

def main():
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)or len(sys.argv)<8 or sys.argv[6]!='--':raise ValueError('fixed placement argv')
    target=Path(sys.argv[1]);identity=(int(sys.argv[2]),int(sys.argv[3]));destination=Path(sys.argv[4]);end=float(sys.argv[5]);argv=sys.argv[7:]
    first=None;secondary=[];directory=handle=None;prefix=b'';record={'schema':'n090-actual-placement-v1','pid':os.getpid(),'cgroup':str(target),'identity':list(identity),'moved':False,'readback':None,'descriptor_closure_known':False}
    def before():
        if time.monotonic()>=end:raise TimeoutError('original placement cutoff')
    def remember(where,error):
        nonlocal first
        if first is None:first=(where,error)
        else:secondary.append((where,error))
    try:
        before()
        if not str(target).startswith('/sys/fs/cgroup/')or any(p.is_symlink()for p in(target,*target.parents)):raise ValueError('literal selected cgroup')
        directory=os.open(target,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);s=os.fstat(directory)
        if (s.st_dev,s.st_ino)!=identity:raise ValueError('actual selected cgroup identity')
        handle=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW,dir_fd=directory);raw=str(os.getpid()).encode();offset=0
        while offset<len(raw):
            before();n=os.write(handle,raw[offset:])
            if n<=0:raise OSError('placement write progress')
            offset+=n
        record['moved']=True
    except BaseException as error:remember('placement',error)
    finally:
        for name,fd in(('procs-close',handle),('directory-close',directory)):
            if fd is not None:
                try:os.close(fd)
                except BaseException as error:remember(name,error)
    handle=None
    if first is None:
        try:
            before();handle=os.open('/proc/self/cgroup',os.O_RDONLY|os.O_NOFOLLOW);prefix=os.read(handle,8193)
            if len(prefix)>8192:raise ValueError('placement cgroup readback cap')
            body=prefix.decode().strip();record['readback']=body
            if body!='0::/'+str(target.relative_to('/sys/fs/cgroup')):raise ValueError('actual unified placement readback')
        except BaseException as error:remember('placement-readback',error)
        finally:
            if handle is not None:
                try:os.close(handle)
                except BaseException as error:remember('readback-close',error)
    record['descriptor_closure_known']=first is None
    record['first']=None if first is None else{'where':first[0],'type':type(first[1]).__name__}
    record['secondary']=[{'where':w,'type':type(e).__name__}for w,e in secondary]
    record['kernel_prefix_base64']=base64.b64encode(prefix).decode()
    fd=None
    try:
        before();raw=(json.dumps(record,sort_keys=True,separators=(',',':'))+'\n').encode()
        if len(raw)>16384:raise ValueError('preselected placement record cap')
        fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);offset=0
        while offset<len(raw):
            before();n=os.write(fd,raw[offset:])
            if n<=0:raise OSError('placement record write progress')
            offset+=n
        os.fsync(fd)
    except BaseException as error:remember('placement-publication',error)
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:remember('placement-publication-close',error)
    if first is not None:
        record['first']={'where':first[0],'type':type(first[1]).__name__};record['secondary']=[{'where':w,'type':type(e).__name__}for w,e in secondary]
        sys.stderr.write(json.dumps(record,separators=(',',':'))+'\n');sys.stderr.flush();raise SystemExit(1)
    before();os.execv(argv[0],argv)
if __name__=='__main__':main()

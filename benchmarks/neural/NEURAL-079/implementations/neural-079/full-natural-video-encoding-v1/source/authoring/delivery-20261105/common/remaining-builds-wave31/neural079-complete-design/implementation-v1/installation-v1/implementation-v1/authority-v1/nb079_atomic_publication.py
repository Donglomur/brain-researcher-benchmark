"""Standalone selected Linux atomic metadata publisher; imports are inert.

No application modules, supplied callbacks, permission/results objects or science.
A caller precharges the published bounds before construction/calls and retains
these independently measured attempted/returned facts, including every failure.
"""
import hashlib
import os
import stat
import time
from pathlib import PurePosixPath


def require(ok,message):
    if not ok:raise ValueError(message)
def fields(value,names):require(type(value) is dict and set(value)==set(names),'exact atomic metadata fields')
def integer(value,minimum=0):require(type(value) is int and value>=minimum,'finite nonbool integer');return value
def path(value):
    require(type(value) is str and value.startswith('/') and not value.startswith('//') and str(PurePosixPath(value))==value and '..' not in PurePosixPath(value).parts and '\x00' not in value,'canonical ordinary path');return value
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def identity(st):return {'device':st.st_dev,'inode':st.st_ino}
def stamp(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
def secondary(first,error,stage):
    rows=list(getattr(first,'atomic_secondary',[]));rows.append({'stage':stage,'type':type(error).__name__});first.atomic_secondary=rows

def cleanup(operations,first=None):
    for name,operation in operations:
        try:operation()
        except BaseException as error:
            if first is None:first=error
            else:secondary(first,error,name)
    return first


def directory(value):
    path(value);fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);first=None
    try:
        for name in PurePosixPath(value).parts[1:]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);old,fd=fd,child
            os.close(old)
        result,fd=fd,None;return result
    except BaseException as error:first=error;raise
    finally:
        error=cleanup([] if fd is None else [('directory traversal close',lambda:os.close(fd))],first)
        if first is None and error is not None:raise error


class AtomicPublication:
    def __init__(self,publication,original_clock,limits,*,execution_enabled=False):
        require(execution_enabled is True,'atomic publication disabled before file/clock/library effects')
        self.records=[];self.source_record=None;self.implementation_record=None;self.closed=False;self.library=None;self.rename=None
        self.attempted_source_bytes=0;self.returned_source_bytes=0;self.attempted_write_bytes=0;self.returned_write_bytes=0
        try:
            fields(publication,('method','implementation','libc','libc_identity'));require(publication['method']=='linux_renameat2_noreplace_v1','one selected atomic ABI')
            fields(publication['libc'],('path','pin'));path(publication['libc']['path']);fields(publication['libc']['pin'],('bytes','sha256'))
            integer(publication['libc']['pin']['bytes']);h=publication['libc']['pin']['sha256'];require(type(h) is str and len(h)==64 and all(c in '0123456789abcdef' for c in h),'exact native library SHA256')
            fields(publication['implementation'],('path','pin'));path(publication['implementation']['path']);fields(publication['implementation']['pin'],('bytes','sha256'))
            integer(publication['implementation']['pin']['bytes']);digest=publication['implementation']['pin']['sha256'];require(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'exact implementation SHA256')
            require(publication['implementation']['path']==__file__,'actual selected captured implementation path; aliases preserve source filename')
            fields(publication['libc_identity'],('device','inode'))
            for v in publication['libc_identity'].values():integer(v)
            fields(original_clock,('origin','scientific','closeout','outer'));c=[integer(original_clock[k]) for k in ('origin','scientific','closeout','outer')];require(all(a<b for a,b in zip(c,c[1:])),'one original strictly ordered clock')
            fields(limits,('maximum_source_bytes','maximum_publication_bytes','block_bytes','maximum_publications','maximum_total_write_bytes','maximum_path_chars'))
            for value in limits.values():integer(value,1)
            require(limits['block_bytes']<=limits['maximum_publication_bytes'] and publication['libc']['pin']['bytes']+publication['implementation']['pin']['bytes']<=limits['maximum_source_bytes'],'selected whole library/publication extents')
            self.publication=publication;self.original_clock=original_clock;self.limits=limits
            self.implementation_record=self.capture_source(publication['implementation'],None)
            self.source_record=self.capture_source(publication['libc'],publication['libc_identity'])
            # The only native call target is the selected libc's fixed symbol.
            # Its loaded handle remains owned until actual process exit.
            import ctypes
            self.tick('scientific');self.library=ctypes.CDLL(publication['libc']['path'],use_errno=True)
            self.rename=self.library.renameat2;self.rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];self.rename.restype=ctypes.c_int
            current=os.stat(publication['libc']['path'],follow_symlinks=False)
            require(stamp(current)==tuple(self.source_record['identity_stamp']),'same captured library after selected loader operation')
            self.tick('scientific')
        except BaseException as error:self.closed=True;error.atomic_prefix=self.prefix();raise
    def tick(self,phase):
        require(phase in ('scientific','closeout','outer'),'original named phase');now=time.monotonic_ns();require(self.original_clock['origin']<=now<self.original_clock[phase],'original atomic operation cutoff');return now
    def capture_source(self,item,expected_identity):
        self.attempted_source_bytes+=item['pin']['bytes']+1
        record={'descriptor':item,'attempted_bytes':item['pin']['bytes']+1,'returned_bytes':0,'eof':False,'stable':False};
        if expected_identity is None:self.implementation_record=record
        else:self.source_record=record
        parent=None;fd=None;first=None;digest=hashlib.sha256();count=0
        try:
            self.tick('scientific');require(len(item['path'])<=self.limits['maximum_path_chars'],'bounded selected library path')
            parent=directory(str(PurePosixPath(item['path']).parent));fd=os.open(PurePosixPath(item['path']).name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent);before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_mode&0o022==0 and before.st_size==item['pin']['bytes'] and (expected_identity is None or identity(before)==expected_identity),'actual protected ordinary selected library inode and extent')
            while count<=before.st_size:
                self.tick('scientific');raw=os.read(fd,min(self.limits['block_bytes'],before.st_size-count+1));count+=len(raw);self.returned_source_bytes+=len(raw);record['returned_bytes']=count
                if not raw:record['eof']=True;break
                require(count<=before.st_size,'library extent grew');digest.update(raw)
            require(record['eof'] and count==before.st_size and digest.hexdigest()==item['pin']['sha256'] and stamp(os.fstat(fd))==stamp(before),'whole original library hash/EOF/stability')
            record.update(stable=True,identity_stamp=list(stamp(before)))
        except BaseException as error:first=error
        first=cleanup(([] if fd is None else [('selected library close',lambda:os.close(fd))])+([] if parent is None else [('selected library parent close',lambda:os.close(parent))]),first)
        if first is not None:record['failure_type']=type(first).__name__;raise first
        self.tick('scientific');return record
    def rename_noreplace(self,fd,temp,name):
        import ctypes
        ctypes.set_errno(0);result=self.rename(fd,os.fsencode(temp),fd,os.fsencode(name),1)
        if result!=0:
            error=ctypes.get_errno();raise OSError(error,os.strerror(error))
    def publish(self,root,name,raw,phase='scientific'):
        require(not self.closed and self.rename is not None,'actual admitted live publisher')
        fields(root,('path','identity','owner_uid','mode'));path(root['path']);fields(root['identity'],('device','inode'))
        for value in (*root['identity'].values(),root['owner_uid'],root['mode']):integer(value)
        require(type(name) is str and name not in ('','.','..') and '/' not in name and '\x00' not in name and not name.startswith('.nb079-pending-'),'one final safe metadata leaf')
        require(type(raw) is bytes and len(raw)<=self.limits['maximum_publication_bytes'],'whole actual metadata bytes before effects')
        temp='.nb079-pending-'+name;require(len(root['path']+'/'+temp)<=self.limits['maximum_path_chars'],'bounded temporary/final namespace')
        self.attempted_write_bytes+=len(raw)
        record={'path':root['path']+'/'+name,'temporary_path':root['path']+'/'+temp,'intended_pin':pin(raw),'written_bytes':0,'temporary_fsynced':False,'temporary_close_attempted':False,'temporary_closed':False,'renamed_noreplace':False,'namespace_fsynced':False,'complete':False}
        if len(self.records)>=self.limits['maximum_publications']:
            self.closed=True;error=ValueError('finite complete atomic publication count');error.atomic_prefix=self.prefix();raise error
        self.records.append(record)
        parent=None;fd=None;owned_temp=False;temp_identity=None;first=None;digest=hashlib.sha256()
        try:
            require(self.attempted_write_bytes<=self.limits['maximum_total_write_bytes'],'whole cumulative metadata write ceiling');self.tick(phase)
            parent=directory(root['path']);st=os.fstat(parent)
            require(identity(st)==root['identity'] and st.st_uid==root['owner_uid']==os.geteuid() and stat.S_IMODE(st.st_mode)==root['mode'] and root['mode']&0o022==0,'actual owned protected publication root')
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=parent);owned_temp=True;temp_identity=identity(os.fstat(fd))
            while record['written_bytes']<len(raw):
                self.tick(phase);done=record['written_bytes'];n=os.write(fd,memoryview(raw)[done:done+self.limits['block_bytes']]);require(type(n) is int and 0<n<=min(self.limits['block_bytes'],len(raw)-done),'actual positive bounded metadata write')
                digest.update(raw[done:done+n]);record['written_bytes']+=n;self.returned_write_bytes+=n
            os.fsync(fd);record['temporary_fsynced']=True;self.tick(phase)
            closing,fd=fd,None;record['temporary_close_attempted']=True;os.close(closing);record['temporary_closed']=True
            # No final name is visible before the complete fsynced body closes.
            self.tick(phase);self.rename_noreplace(parent,temp,name);owned_temp=False;record['renamed_noreplace']=True
            os.fsync(parent);record['namespace_fsynced']=True
            final=os.stat(name,dir_fd=parent,follow_symlinks=False)
            require(stat.S_ISREG(final.st_mode) and final.st_nlink==1 and identity(final)==temp_identity and final.st_size==len(raw),'same complete ordinary final inode after nonreplacement rename')
            record['observed_ns']=self.tick(phase)
        except BaseException as error:first=error;record['failure_type']=type(error).__name__
        operations=[]
        if fd is not None:operations.append(('owned temporary close',lambda:os.close(fd)))
        if owned_temp:
            def remove():
                current=os.stat(temp,dir_fd=parent,follow_symlinks=False);require(identity(current)==temp_identity,'only own unchanged temporary inode cleanup');os.unlink(temp,dir_fd=parent);os.fsync(parent)
            operations.append(('owned temporary unlink/sync',remove))
        if parent is not None:operations.append(('publication root close',lambda:os.close(parent)))
        first=cleanup(operations,first);record['written_sha256']=digest.hexdigest()
        if first is None:
            try:self.tick(phase)
            except BaseException as error:first=error
        if first is not None:self.closed=True;error=first;error.atomic_prefix=self.prefix();raise error
        record['complete']=True;return {'descriptor':{'path':record['path'],'pin':pin(raw)},'record':dict(record)}
    def prefix(self):
        return {'implementation':self.implementation_record,'source':self.source_record,'attempted_source_bytes':self.attempted_source_bytes,'returned_source_bytes':self.returned_source_bytes,'attempted_write_bytes':self.attempted_write_bytes,'returned_write_bytes':self.returned_write_bytes,'records':list(self.records),'native_handle_retained_until_process_exit':self.library is not None,'closed':self.closed,'physical_total_claim':False}
    def close(self):self.closed=True

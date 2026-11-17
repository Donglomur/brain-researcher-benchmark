"""Bounded fd-relative regular-file I/O. No input discovery outside named roots.

Read-only modes are preparation, NOT proof of an immutable backing mount.
Trusted-host custody is separately required; hostile same-host administrators
can defeat ordinary filesystem permissions and are not in this claim.
"""
from dataclasses import dataclass, asdict
import hashlib
import os
import posixpath
import re
import stat
from ..core.custody import digest
from ..process_guard.contracts import MemberPin


class ContextIOError(RuntimeError):
    pass


@dataclass(frozen=True)
class IOLimits:
    max_files: int
    max_directories: int
    max_depth: int
    max_file_bytes: int
    max_total_bytes: int
    block_bytes: int = 65536

    def validate(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value <= 0:
                raise ContextIOError('positive finite I/O limit required: '+name)
        if self.block_bytes > 1048576 or self.max_depth > 256:
            raise ContextIOError('block/depth exceeds conservative implementation bound')

    @property
    def fingerprint(self):
        self.validate()
        return digest(asdict(self))


@dataclass
class IOCounter:
    metadata_entries_inspected: int = 0
    source_bytes_read: int = 0
    export_bytes_received: int = 0
    staging_bytes_written: int = 0
    source_files_copied: int = 0
    files_written: int = 0
    directories_created: int = 0
    write_calls: int = 0
    source_read_calls: int = 0
    maximum_write_chunk: int = 0

    def to_dict(self):
        return asdict(self)


def relative_path(value):
    if (not isinstance(value, str) or not value or value.startswith('/')
        or posixpath.normpath(value) != value or value in ('.', '..')
        or value.startswith('../') or '\x00' in value or '\\' in value
        or any(ord(c)<32 or ord(c)==127 for c in value)
        or set(value.split('/')) & {'.git','.hg','.svn','.ssh','.aws','.codex'}):
        raise ContextIOError('canonical safe relative path required')
    return value


def absolute_path(value):
    if (not isinstance(value, str) or not value.startswith('/') or value=='/'
        or posixpath.normpath(value)!=value or '\x00' in value or '\\' in value):
        raise ContextIOError('explicit canonical absolute path required')
    for part in value.split('/')[1:]:
        if not part or part in ('.','..') or any(ord(c)<32 or ord(c)==127 for c in part):
            raise ContextIOError('unsafe absolute path component')
    return value


def token(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,96}',value):
        raise ContextIOError('opaque safe output child name required')
    return value


def identity(st):
    return (st.st_dev, st.st_ino)


def revision(st):
    return (st.st_dev,st.st_ino,st.st_mode,st.st_nlink,st.st_size,
            st.st_mtime_ns,st.st_ctime_ns)


def _dirflags():
    if not all(hasattr(os,k) for k in ('O_DIRECTORY','O_NOFOLLOW','O_CLOEXEC')):
        raise ContextIOError('qualified no-follow directory primitives unavailable')
    return os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC


def open_absolute_dir(path):
    absolute_path(path)
    fd=os.open('/',_dirflags())
    try:
        for part in path.split('/')[1:]:
            nxt=os.open(part,_dirflags(),dir_fd=fd)
            os.close(fd);fd=nxt
        return fd
    except BaseException:
        os.close(fd);raise


def open_relative_dir(root_fd,path):
    fd=os.dup(root_fd)
    try:
        if path:
            relative_path(path)
            for part in path.split('/'):
                nxt=os.open(part,_dirflags(),dir_fd=fd)
                os.close(fd);fd=nxt
        return fd
    except BaseException:
        os.close(fd);raise


def root_still_named(path,fd):
    other=open_absolute_dir(path)
    try:
        if identity(os.fstat(fd))!=identity(os.fstat(other)):
            raise ContextIOError('root pathname identity changed')
    finally:os.close(other)


def require_regular(st,device=None):
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1
        or st.st_mode & (stat.S_ISUID|stat.S_ISGID)
        or (device is not None and st.st_dev!=device)):
        raise ContextIOError('single-link same-device regular file required')


@dataclass(frozen=True)
class InventoryFile:
    path: str
    size: int
    revision: tuple
    output_mode: int


@dataclass(frozen=True)
class Inventory:
    files: tuple
    directories: tuple  # (relative_path, device, inode, mode, mtime_ns, ctime_ns)
    bytes: int


def inventory(root_fd,limits,counter):
    """Complete bounded metadata enumeration of one authorized root, no body read.

    Empty directories are retained. Reparse/symlink/device/hardlink entries and
    cross-device subtrees are rejected; nothing outside this FD is followed.
    """
    limits.validate();device=os.fstat(root_fd).st_dev;files=[];dirs=[];total=0
    def visit(fd,prefix,depth):
        nonlocal total
        if depth>limits.max_depth:raise ContextIOError('inventory depth cap')
        st=os.fstat(fd)
        if st.st_dev!=device or st.st_mode & (stat.S_ISUID|stat.S_ISGID):raise ContextIOError('cross-device/special directory forbidden')
        dirs.append((prefix,st.st_dev,st.st_ino,st.st_mode,st.st_mtime_ns,st.st_ctime_ns))
        if len(dirs)>limits.max_directories:raise ContextIOError('directory cap')
        # scandir is consumed incrementally: a giant directory cannot allocate an
        # unbounded list before the entry cap. Only admitted names are sorted.
        names=[]
        with os.scandir(fd) as scan:
            for ent in scan:
                counter.metadata_entries_inspected+=1
                if len(names)+len(files)+len(dirs)>limits.max_files+limits.max_directories:
                    raise ContextIOError('inventory entry cap')
                names.append(ent.name)
        for name in sorted(names):
            path=name if not prefix else prefix+'/'+name
            relative_path(path)
            current=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if stat.S_ISDIR(current.st_mode):
                child=os.open(name,_dirflags(),dir_fd=fd)
                try:
                    if revision(os.fstat(child))!=revision(current):raise ContextIOError('directory changed before open')
                    visit(child,path,depth+1)
                finally:os.close(child)
            else:
                require_regular(current,device)
                if current.st_size>limits.max_file_bytes:raise ContextIOError('source file cap')
                total+=current.st_size
                if total>limits.max_total_bytes or len(files)>=limits.max_files:
                    raise ContextIOError('complete source tree exceeds cap')
                mode=0o555 if current.st_mode&0o111 else 0o444
                files.append(InventoryFile(path,current.st_size,revision(current),mode))
        if revision(os.fstat(fd))!=revision(st):raise ContextIOError('directory mutated during inventory')
    visit(root_fd,'',0)
    return Inventory(tuple(sorted(files,key=lambda p:p.path)),tuple(sorted(dirs)),total)


class TreeWriter:
    """Exclusive new tree. Errors leave an unqualified, caller-owned partial tree.

    No cleanup of existing paths, reuse, overwrite, rename, or recursive deletion.
    A caller must retain failure/cost evidence and separately dispose owned debris.
    """
    def __init__(self,parent_path,name,limits,counter):
        absolute_path(parent_path);token(name);limits.validate()
        self.parent_path=parent_path;self.name=name;self.limits=limits;self.counter=counter
        self.path=parent_path+'/'+name;self.members={};self.file_revisions={};self.directories={};self.bytes=0
        self.parent_fd=open_absolute_dir(parent_path);self.fd=None;self.closed=False
        try:
            pst=os.fstat(self.parent_fd)
            if pst.st_uid!=os.geteuid() or pst.st_mode&0o022:
                raise ContextIOError('output parent must be caller-owned and not group/world writable')
            os.mkdir(name,0o700,dir_fd=self.parent_fd)
            self.fd=os.open(name,_dirflags(),dir_fd=self.parent_fd)
            st=os.fstat(self.fd)
            if st.st_dev!=pst.st_dev:raise ContextIOError('new output root changed device')
            self.device=st.st_dev;self.directories['']=identity(st)
            counter.directories_created+=1
        except BaseException:
            if self.fd is not None:os.close(self.fd)
            os.close(self.parent_fd);self.closed=True;raise

    def mkdir(self,path):
        relative_path(path)
        parts=path.split('/')
        if len(parts)>self.limits.max_depth:raise ContextIOError('output depth cap')
        for n in range(1,len(parts)+1):
            current='/'.join(parts[:n])
            if current in self.directories:continue
            if len(self.directories)>=self.limits.max_directories:raise ContextIOError('output directory cap')
            parent='/'.join(parts[:n-1]);pfd=open_relative_dir(self.fd,parent)
            try:
                os.mkdir(parts[n-1],0o700,dir_fd=pfd)
                child=os.open(parts[n-1],_dirflags(),dir_fd=pfd)
                try:
                    st=os.fstat(child)
                    if st.st_dev!=self.device:raise ContextIOError('output directory device changed')
                    self.directories[current]=identity(st)
                finally:os.close(child)
                self.counter.directories_created+=1
            finally:os.close(pfd)

    def _reserve(self,path,size,mode):
        relative_path(path)
        if (type(size) is not int or size<0 or mode not in (0o444,0o555)
            or size>self.limits.max_file_bytes or self.bytes+size>self.limits.max_total_bytes
            or len(self.members)>=self.limits.max_files or path in self.members
            or len(path.split('/'))>self.limits.max_depth):
            raise ContextIOError('output extent/member limit or duplicate')
        parent=posixpath.dirname(path)
        if parent:self.mkdir(parent)
        self.bytes+=size

    def _write(self,path,size,mode,chunks):
        self._reserve(path,size,mode);parent=posixpath.dirname(path)
        pfd=open_relative_dir(self.fd,parent);fd=None;count=0;h=hashlib.sha256()
        try:
            fd=os.open(posixpath.basename(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=pfd)
            before=os.fstat(fd);require_regular(before,self.device)
            for chunk in chunks:
                if not isinstance(chunk,(bytes,memoryview)) or len(chunk)>self.limits.block_bytes:
                    raise ContextIOError('bounded byte chunks required')
                if count+len(chunk)>size:raise ContextIOError('source exceeded exact extent')
                view=memoryview(chunk);h.update(view);count+=len(view)
                while view:
                    n=os.write(fd,view)
                    if n<=0:raise ContextIOError('short/zero filesystem write')
                    self.counter.staging_bytes_written+=n;self.counter.write_calls+=1
                    self.counter.maximum_write_chunk=max(self.counter.maximum_write_chunk,n)
                    view=view[n:]
            if count!=size:raise ContextIOError('source ended before exact extent')
            os.fchmod(fd,mode);os.utime(fd,ns=(0,0));os.fsync(fd)
            after=os.fstat(fd);require_regular(after,self.device)
            named=os.stat(posixpath.basename(path),dir_fd=pfd,follow_symlinks=False)
            if (identity(before)!=identity(after) or revision(after)!=revision(named)
                or after.st_size!=size or stat.S_IMODE(after.st_mode)!=mode or after.st_mtime_ns!=0):
                raise ContextIOError('written file identity/extent/mode changed')
            pin=MemberPin(path,size,h.hexdigest(),mode);pin.validate();self.members[path]=pin;self.file_revisions[path]=revision(after)
            self.counter.files_written+=1
            return pin
        finally:
            if fd is not None:os.close(fd)
            os.close(pfd)

    def write_bytes(self,path,body,mode=0o444):
        if type(body) is not bytes:raise ContextIOError('exact byte body required')
        size=len(body);block=self.limits.block_bytes
        return self._write(path,size,mode,(memoryview(body)[p:p+block] for p in range(0,size,block)))

    def copy_file(self,source_root_fd,item,destination):
        if type(item) is not InventoryFile:raise ContextIOError('typed inventoried source required')
        pfd=open_relative_dir(source_root_fd,posixpath.dirname(item.path));fd=None
        try:
            fd=os.open(posixpath.basename(item.path),os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=pfd)
            st=os.fstat(fd);require_regular(st,os.fstat(source_root_fd).st_dev)
            if revision(st)!=item.revision:raise ContextIOError('source changed since drained inventory')
            def chunks():
                remaining=item.size
                while remaining:
                    chunk=os.read(fd,min(remaining,self.limits.block_bytes));self.counter.source_read_calls+=1
                    if not chunk:raise ContextIOError('short source body')
                    self.counter.source_bytes_read+=len(chunk);remaining-=len(chunk);yield chunk
                extra=os.read(fd,1);self.counter.source_read_calls+=1;self.counter.source_bytes_read+=len(extra)
                if extra:raise ContextIOError('source grew during copy')
                named=os.stat(posixpath.basename(item.path),dir_fd=pfd,follow_symlinks=False)
                if revision(os.fstat(fd))!=item.revision or revision(named)!=item.revision:
                    raise ContextIOError('source changed during copy')
            pin=self._write(destination,item.size,item.output_mode,chunks())
            self.counter.source_files_copied+=1
            return pin
        finally:
            if fd is not None:os.close(fd)
            os.close(pfd)

    def finish(self):
        if self.closed:raise ContextIOError('writer already closed')
        root_still_named(self.parent_path,self.parent_fd);root_still_named(self.path,self.fd)
        observed=inventory(self.fd,self.limits,self.counter)
        if ({f.path:(f.size,f.output_mode) for f in observed.files}
            !={p:(m.bytes,m.mode) for p,m in self.members.items()}
            or {f.path:f.revision for f in observed.files}!=self.file_revisions
            or {d[0]:(d[1],d[2]) for d in observed.directories}!=self.directories):
            raise ContextIOError('output tree differs from exact complete manifest')
        for path in sorted(self.directories,key=lambda p:(p.count('/'),p),reverse=True):
            fd=open_relative_dir(self.fd,path)
            try:
                if identity(os.fstat(fd))!=self.directories[path]:raise ContextIOError('output directory changed')
                os.fchmod(fd,0o555);os.utime(fd,ns=(0,0));os.fsync(fd)
            finally:os.close(fd)
        root_still_named(self.path,self.fd)
        return tuple(self.members[p] for p in sorted(self.members))

    def close(self):
        if not self.closed:
            os.close(self.fd);os.close(self.parent_fd);self.closed=True

"""Concrete descriptor-relative reads/writes with immediate acquired-FD custody."""
import hashlib
import os
import stat
from dataclasses import dataclass
from .custody import require, Owner
from .capacity import Capacity

_KEY = object()

def component(name):
    require(type(name) is str and name not in ("", ".", "..") and
            "/" not in name and "\x00" not in name, "single-path-component")
    return name

def relative(name):
    require(type(name) is str and not name.startswith("/"), "relative-path")
    parts = name.split("/")
    for part in parts:
        component(part)
    return parts

@dataclass(frozen=True)
class FilePin:
    path: str
    size: int
    sha256: str
    mode: int
    def validate(self):
        relative(self.path)
        require(type(self.size) is int and self.size >= 0 and
                type(self.sha256) is str and len(self.sha256) == 64 and
                all(c in "0123456789abcdef" for c in self.sha256) and
                type(self.mode) is int and 0 <= self.mode <= 0o777, "file-pin")

class OwnedFD:
    def __init__(self, key, owner, capacity, fd, attempt, reservation):
        require(key is _KEY, "fd-source-only")
        self.owner = owner
        self.capacity = capacity
        self.fd = fd
        self.attempt = attempt
        self.reservation = reservation
        self.close_attempted = False
        self.closed = False
        self.accounted = False
        self.identity = None
        owner.retain(self)  # before accounting or fstat
        attempt.returned.append(self)

    def require_live(self):
        require(type(self) is OwnedFD and any(x is self for x in self.owner.resources)
                and not self.close_attempted, "actual-live-descriptor")
        return self.fd

    def close(self):
        if self.close_attempted:
            return
        self.close_attempted = True
        try:
            os.close(self.fd)
            self.closed = True
        except BaseException as error:
            self.attempt.fail(error, "fd-close")
            self.attempt.uncertain("fd-close", {"fd": self.fd})
        if self.accounted:
            try:
                self.capacity.release_live("live_fds", 1, known=self.closed)
            except BaseException as error:
                self.attempt.fail(error, "fd-close-accounting")
                self.attempt.uncertain("fd-close-accounting", {"fd": self.fd})
        self.attempt.raise_first()

def own_returned_fd(owner, capacity, fd, attempt, reservation):
    resource = OwnedFD(_KEY, owner, capacity, fd, attempt, reservation)
    try:
        capacity.settle(reservation, 1)
        resource.accounted = True
        s = os.fstat(fd)
        resource.identity = (s.st_dev, s.st_ino, s.st_mode)
    except BaseException as error:
        attempt.fail(error, "fd-acquisition-observation")
        attempt.uncertain("fd-acquisition-observation", {"fd": fd})
        try:
            resource.close()
        except BaseException:
            pass
        attempt.raise_first()
    return resource

def acquire_fd(owner, capacity, name, flags, *, parent=None, mode=0o400,
               cleanup=False):
    attempt = owner.begin("open:" + name, cleanup=cleanup)
    reservation = capacity.reserve("live_fds", 1, "open:" + name, cleanup=cleanup)
    try:
        fd = os.open(name, flags | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                     mode, dir_fd=parent)
    except BaseException as error:
        attempt.fail(error, "fd-open")
        try:
            capacity.settle(reservation, 0)
        except BaseException as later:
            attempt.fail(later, "fd-open-settlement")
            attempt.uncertain("fd-open-settlement", name)
        attempt.raise_first()
    return own_returned_fd(owner, capacity, fd, attempt, reservation)

class Directory:
    def __init__(self, key, fd, absolute):
        require(key is _KEY and type(fd) is OwnedFD and
                stat.S_ISDIR(os.fstat(fd.require_live()).st_mode), "directory-source")
        self.fd = fd
        self.absolute = absolute
        self.owner = fd.owner
        self.capacity = fd.capacity

    @classmethod
    def open_absolute(cls, owner, capacity, path):
        require(type(path) is str and path.startswith("/") and
                os.path.normpath(path) == path, "absolute-normal-path")
        current = acquire_fd(owner, capacity, "/", os.O_RDONLY | os.O_DIRECTORY)
        absolute = ""
        try:
            for part in path.split("/")[1:]:
                if not part:
                    continue
                component(part)
                nxt = acquire_fd(owner, capacity, part, os.O_RDONLY | os.O_DIRECTORY,
                                 parent=current.require_live())
                old = current
                current = nxt  # retain new before retiring prior
                old.close()
                absolute += "/" + part
            return cls(_KEY, current, absolute or "/")
        except BaseException as error:
            owner.custody.fail(error, "directory-open")
            try:
                current.close()
            except BaseException:
                pass
            owner.custody.raise_first()

    def child(self, name, *, create=False):
        component(name)
        if create:
            self.capacity.consume_attempt("creation_attempts", "mkdir:" + name)
            attempt = self.owner.begin("mkdir:" + name)
            try:
                os.mkdir(name, 0o700, dir_fd=self.fd.require_live())
                attempt.returned.append(("directory-created", self, name))
            except FileExistsError as error:
                attempt.fail(error, "exclusive-directory-exists")
                attempt.raise_first()
            except BaseException as error:
                attempt.fail(error, "mkdir")
                attempt.uncertain("mkdir", name)
                attempt.raise_first()
        child = acquire_fd(self.owner, self.capacity, name, os.O_RDONLY | os.O_DIRECTORY,
                           parent=self.fd.require_live())
        return Directory(_KEY, child, self.absolute.rstrip("/") + "/" + name)

    def parent(self, name):
        parts = relative(name)
        current = self
        opened = []
        try:
            for part in parts[:-1]:
                current = current.child(part)
                opened.append(current.fd)
            return current, parts[-1], opened
        except BaseException as error:
            self.owner.custody.fail(error, "relative-parent")
            for fd in reversed(opened):
                try: fd.close()
                except BaseException: pass
            self.owner.custody.raise_first()

class CapturedBody:
    __slots__ = ("_owner", "_pin", "_raw", "_identity", "_attempt", "_memory",
                 "_binding", "_released")
    def __init__(self, key, owner, pin, raw, identity, attempt, memory):
        require(key is _KEY, "capture-source-only")
        self._owner, self._pin, self._raw = owner, pin, raw
        self._identity, self._attempt, self._memory = identity, attempt, memory
        self._binding = (owner, pin, raw, identity, attempt, memory)
        self._released = False
        attempt.returned.append(self)

    @property
    def owner(self):
        self.validate()
        return self._owner

    @property
    def raw(self):
        self.validate()
        return self._raw

    @property
    def pin(self):
        self.validate()
        return self._pin

    def validate(self):
        original = self._binding
        require(not self._released and self._owner is original[0] and
                self._pin is original[1] and self._raw is original[2] and
                self._identity is original[3] and self._attempt is original[4] and
                self._memory is original[5] and self._attempt.complete,
                "original-capture-binding")
        require(len(self._raw) == self._pin.size and
                hashlib.sha256(self._raw).hexdigest() == self._pin.sha256,
                "original-capture-bytes")

    def close(self):
        # Exposing raw bytes permits legitimate borrower references. Retiring this
        # view must never release their memory commitment or requalify the body.
        self._released = True

def capture(root, pin):
    require(type(root) is Directory and type(pin) is FilePin, "captured-source-types")
    pin.validate()
    owner, cap = root.owner, root.capacity
    attempt = owner.begin("capture:" + pin.path)
    read = memory = fd = None
    parents = []
    returned = 0
    read_pending = False
    chunks = []
    attempt.returned.append(chunks)  # failed prefixes retained under memory hold
    try:
        read = cap.reserve("read_bytes", pin.size+1, "capture:" + pin.path)
        memory = cap.reserve("rss_bytes", 2*(pin.size+1), "capture-buffers:" + pin.path)
        cap.settle(memory, memory.capacity)  # committed before allocating buffers
        parent, leaf, parents = root.parent(pin.path)
        fd = acquire_fd(owner, cap, leaf, os.O_RDONLY, parent=parent.fd.require_live())
        before = os.fstat(fd.require_live())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == pin.size and stat.S_IMODE(before.st_mode) == pin.mode,
                "capture-file-shape")
        while returned < pin.size+1:
            read_pending = True
            part = os.read(fd.require_live(), min(65536, pin.size+1-returned))
            returned += len(part)  # before append/allocation
            read_pending = False
            attempt.returned.append(part)  # exact returned prefix even if append fails
            if not part:
                break
            chunks.append(part)
        after = os.fstat(fd.require_live())
        current = os.stat(leaf, dir_fd=parent.fd.require_live(), follow_symlinks=False)
        identity = tuple(getattr(before, k) for k in
                         ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))
        require(identity == tuple(getattr(after,k) for k in
                                  ("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns")) and
                current.st_dev == before.st_dev and current.st_ino == before.st_ino,
                "capture-same-open-and-name")
        raw = b"".join(chunks)
        require(returned == pin.size and hashlib.sha256(raw).hexdigest() == pin.sha256,
                "capture-exact-bytes-and-eof")
    except BaseException as error:
        attempt.fail(error, "capture")
        if read_pending:
            attempt.uncertain("capture-read", {"known_bytes": returned})
    finally:
        if read is not None:
            try: cap.settle(read, returned, unknown=read_pending)
            except BaseException as error:
                attempt.fail(error, "capture-read-settlement")
                attempt.uncertain("capture-read-settlement", {"known_bytes": returned})
        for handle in ([fd] if fd is not None else []) + list(reversed(parents)):
            try: handle.close()
            except BaseException as error:
                attempt.fail(error, "capture-independent-close")
    attempt.raise_first()
    attempt.finish()
    return CapturedBody(_KEY, owner, pin, raw, identity, attempt, memory)

def publish(root, name, raw, *, mode=0o400):
    require(type(root) is Directory and type(raw) is bytes and mode in (0o400,0o444,0o500),
            "publication-types")
    relative(name)
    owner, cap = root.owner, root.capacity
    attempt = owner.begin("publish:" + name)
    attempt.returned.append(raw)  # retained full submitted bytes
    write = fd = None
    parents = []
    acknowledged = 0
    pending = False
    try:
        memory = cap.reserve("rss_bytes", len(raw), "publication-buffer")
        cap.settle(memory, len(raw))
        write = cap.reserve("write_bytes", len(raw), "publish:" + name)
        parent, leaf, parents = root.parent(name)
        cap.consume_attempt("creation_attempts", "publish-create:" + name)
        fd = acquire_fd(owner, cap, leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        parent=parent.fd.require_live(), mode=0o600)
        while acknowledged < len(raw):
            pending = True
            n = os.write(fd.require_live(), memoryview(raw)[acknowledged:])
            acknowledged += n
            pending = False
            require(n > 0 and acknowledged <= len(raw), "publication-progress")
        pending = True
        os.fsync(fd.require_live())
        os.fchmod(fd.require_live(), mode)
        pending = False
    except BaseException as error:
        attempt.fail(error, "publication")
        if pending:
            attempt.uncertain("publication-effect", {"known_written": acknowledged})
    finally:
        if write is not None:
            try: cap.settle(write, acknowledged, unknown=pending)
            except BaseException as error:
                attempt.fail(error, "publication-settlement")
                attempt.uncertain("publication-settlement", {"known_written": acknowledged})
        for handle in ([fd] if fd is not None else []) + list(reversed(parents)):
            try: handle.close()
            except BaseException as error:
                attempt.fail(error, "publication-independent-close")
    attempt.raise_first()
    pin = FilePin(name, len(raw), hashlib.sha256(raw).hexdigest(), mode)
    result = capture(root, pin)
    require(result.raw == raw, "publication-original-readback")
    attempt.returned.append(result)
    attempt.finish()
    return result

class VerifiedFile:
    __slots__=("body","descriptor","binding")
    def __init__(self,key,body,descriptor):
        require(key is _KEY and type(body)is CapturedBody and type(descriptor)is OwnedFD,
                "verified-file-source")
        self.body,self.descriptor=body,descriptor
        self.binding=(body,descriptor)
    @property
    def owner(self):
        self.require_live()
        return self.descriptor.owner
    def require_live(self):
        require(self.body is self.binding[0] and self.descriptor is self.binding[1],
                "verified-file-original-binding")
        self.body.validate()
        fd=self.descriptor.require_live()
        s=os.fstat(fd)
        require(tuple(getattr(s,k) for k in
                      ("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns"))==
                self.body._identity,"verified-file-current-inode")
        require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and
                stat.S_IMODE(s.st_mode)==self.body.pin.mode,"verified-file-mode")
        return fd

def open_verified(root,pin):
    body=capture(root,pin)
    parent,leaf,parents=root.parent(pin.path)
    descriptor=None
    attempt=root.owner.begin("retain-verified-file:"+pin.path)
    try:
        descriptor=acquire_fd(root.owner,root.capacity,leaf,os.O_RDONLY,
                              parent=parent.fd.require_live())
        result=VerifiedFile(_KEY,body,descriptor)
        result.require_live()
        attempt.returned.append(result)
    except BaseException as error:
        attempt.fail(error,"verified-file-open")
    finally:
        for directory in reversed(parents):
            try:directory.close()
            except BaseException as error:attempt.fail(error,"verified-file-parent-close")
    attempt.raise_first()
    attempt.finish()
    return result



@dataclass(frozen=True,eq=False)
class CopiedFile:
    source:FilePin
    destination:FilePin
    source_identity:tuple
    destination_identity:tuple
    attempt:object

def copy_stream(source_root,source_pin,destination_root,name,*,mode=0o400,chunk_bytes):
    """Copy opaque scientific bodies without retaining a programme-sized buffer.

    Original full read/write/readback extents are admitted first. Successful
    temporary byte references are retired before memory release. Failed prefixes
    remain with the original attempt and its memory commitment.
    """
    require(type(source_root)is Directory and type(destination_root)is Directory and
            source_root.owner is destination_root.owner and type(source_pin)is FilePin,
            'same-original-copy-owner')
    require(type(chunk_bytes)is int and 0<chunk_bytes<=1048576,'finite-copy-chunk')
    source_pin.validate();component(name)
    owner=source_root.owner;cap=destination_root.capacity
    a=owner.begin('opaque-stream-copy:'+source_pin.path)
    tokens=[];fdin=fdout=None;parents=[];parent=None;part=None
    read_count=write_count=0;pending_read=pending_write=False;source_identity=None
    memory=None;copied=None
    try:
        memory=cap.reserve('rss_bytes',2*chunk_bytes,'stream-copy-buffer')
        cap.settle(memory,2*chunk_bytes)
        read=cap.reserve('read_bytes',2*(source_pin.size+1),'copy-and-readback');tokens.append(read)
        write=cap.reserve('write_bytes',source_pin.size,'copy-write');tokens.append(write)
        parent,leaf,parents=source_root.parent(source_pin.path)
        fdin=acquire_fd(owner,cap,leaf,os.O_RDONLY,parent=parent.fd.require_live())
        before=os.fstat(fdin.require_live())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and
                before.st_size==source_pin.size and stat.S_IMODE(before.st_mode)==source_pin.mode,
                'original-opaque-copy-source')
        source_identity=tuple(getattr(before,k)for k in
            ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
        cap.consume_attempt('creation_attempts','exclusive-opaque-copy')
        fdout=acquire_fd(owner,cap,name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,
                         parent=destination_root.fd.require_live(),mode=mode)
        digest=hashlib.sha256()
        while read_count<source_pin.size:
            pending_read=True
            part=os.read(fdin.require_live(),min(chunk_bytes,source_pin.size-read_count))
            read_count+=len(part);pending_read=False
            require(part,'opaque-copy-short-source')
            digest.update(part);offset=0
            while offset<len(part):
                pending_write=True
                count=os.write(fdout.require_live(),memoryview(part)[offset:])
                write_count+=count;pending_write=False
                require(count>0,'opaque-copy-write-progress');offset+=count
            part=None
        pending_read=True;part=os.read(fdin.require_live(),1)
        read_count+=len(part);pending_read=False
        require(part==b'' and digest.hexdigest()==source_pin.sha256,'opaque-source-exact-eof-hash')
        part=None
        after=os.fstat(fdin.require_live())
        require(source_identity==tuple(getattr(after,k)for k in
                ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'opaque-source-stable')
        os.fchmod(fdout.require_live(),mode);os.fsync(fdout.require_live())
        fdout.close();fdout=None
        fdout=acquire_fd(owner,cap,name,os.O_RDONLY,parent=destination_root.fd.require_live())
        observed=0;digest=hashlib.sha256()
        while observed<source_pin.size:
            pending_read=True;part=os.read(fdout.require_live(),min(chunk_bytes,source_pin.size-observed))
            read_count+=len(part);pending_read=False;observed+=len(part)
            require(part,'copy-readback-short');digest.update(part);part=None
        pending_read=True;part=os.read(fdout.require_live(),1)
        read_count+=len(part);pending_read=False
        require(part==b'' and digest.hexdigest()==source_pin.sha256,'copy-readback-exact')
        part=None;s=os.fstat(fdout.require_live())
        require(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==source_pin.size and
                stat.S_IMODE(s.st_mode)==mode,'copy-readback-inode')
        target=FilePin(name,source_pin.size,source_pin.sha256,mode)
        copied=CopiedFile(source_pin,target,source_identity,
                         tuple(getattr(s,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),a)
    except BaseException as error:
        a.fail(error,'opaque-copy')
        if part is not None:a.returned.append(part)
        if pending_read or pending_write:a.uncertain('opaque-copy-unreturned-io',
            {'read':read_count,'write':write_count})
    finally:
        for fd in [fdin,fdout,*reversed(parents)]:
            if fd is not None:
                try:fd.close()
                except BaseException as e:a.fail(e,'opaque-copy-independent-close')
        for i,t in enumerate(tokens):
            try:cap.settle(t,read_count if i==0 else write_count,
                           unknown=pending_read if i==0 else pending_write)
            except BaseException as e:a.fail(e,'opaque-copy-independent-settlement')
        if memory is not None and memory.retired and a.first is None:
            # No byte object is returned in CopiedFile; all temporary references
            # are gone. Failed attempts retain their commitment instead.
            part=None
            try:cap.release_live('rss_bytes',memory.capacity,known=True)
            except BaseException as e:a.fail(e,'opaque-copy-buffer-release')
    a.raise_first();a.finish();a.returned.append(copied);return copied

def charged_directory(original,invocation,scope):
    from .capacity import CompositeCapacity
    require(type(original)is Directory and original.owner is invocation.owner,
            "original-scope-directory-descriptor")
    capacity=CompositeCapacity(invocation,scope)
    attempt=original.owner.begin("charged-original-directory-dup")
    token=capacity.reserve("live_fds",1,"charged-directory-dup")
    acquired=None
    try:
        fd=os.dup(original.fd.require_live())
        acquired=own_returned_fd(original.owner,capacity,fd,attempt,token)
        os.set_inheritable(fd,False)
        result=Directory(_KEY,acquired,original.absolute)
        attempt.returned.append(result);attempt.finish();return result
    except BaseException as error:
        attempt.fail(error,"charged-directory-dup")
        if acquired is not None:
            try:acquired.close()
            except BaseException:pass
        elif not token.retired:
            try:capacity.settle(token,0,unknown=bool(attempt.returned))
            except BaseException as later:attempt.fail(later,"charged-directory-dup-settlement")
        attempt.raise_first()

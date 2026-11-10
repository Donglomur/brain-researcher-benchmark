"""Owned ordinary artifacts. No read exceeds its pre-admitted syscall capacity."""
import hashlib
import os
import stat
from .errors import Custody, need
from .identity import canonical, parse, relative

class Store:
    def __init__(self, root, budget, output_prefix=None, admitted_directories=()):
        self.root = os.fspath(root)
        self.budget = budget
        self.created = []
        self.observations = []
        self.accounting_observations = []
        self.directories = set()
        self.output_prefix = None if output_prefix is None else relative(output_prefix)
        s = os.lstat(self.root)
        need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode), "store-root")
        for name in admitted_directories:
            relative(name)
            state=os.lstat(self.path(name))
            need(stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode),"admitted-store-directory")
            self.directories.add(name)
        need(self.output_prefix is None or self.output_prefix not in self.directories,
             "fresh-worker-output-prefix")

    def path(self, name):
        relative(name)
        components = name.split("/")
        current = self.root
        for part in components[:-1]:
            current = os.path.join(current, part)
            s = os.lstat(current)
            need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode), "store-parent")
        return os.path.join(self.root, name)

    def _uncertain(self, custody, effect, **facts):
        try:self.budget.unknown.append({"effect":effect,"unacknowledged_capacity":"accounting or closure",**facts})
        except BaseException as exc:custody.retain(exc,"accounting-unknown-record")

    def _settle(self, token, acknowledged, unknown, custody):
        observation={"token":token,"acknowledged":acknowledged,"unknown_prefix":unknown,
                     "settled":False,"custody":custody}
        self.accounting_observations.append(observation)
        try:
            self.budget.settle(token, acknowledged, unknown=unknown)
            observation["settled"]=True
        except BaseException as exc:
            custody.retain(exc,"settlement")
            self._uncertain(custody,"store-settlement",token=token,acknowledged=acknowledged,
                            unknown_possible_prefix=unknown)

    def _open(self, path, flags, custody, mode=0o400):
        fd_token = self.budget.reserve_fd("open:" + path)
        try:
            fd = os.open(path, flags | os.O_NOFOLLOW, mode)
        except BaseException as exc:
            custody.retain(exc,"fd-open")
            self._settle(fd_token,0,False,custody)
            custody.raise_first()
        try:self.budget.acquired_fd(fd_token)
        except BaseException as exc:
            custody.retain(exc,"fd-acquisition-accounting")
            self._uncertain(custody,"store-fd-acquisition")
            self._close(fd,custody)
            custody.raise_first()
        return fd

    def _close(self, fd, custody):
        try:
            os.close(fd)
        except BaseException as exc:
            custody.retain(exc, "fd-close")
            try:self.budget.fd_closed(False)
            except BaseException as later:
                custody.retain(later,"fd-close-accounting")
                self._uncertain(custody,"store-fd-close")
        else:
            try:self.budget.fd_closed()
            except BaseException as exc:
                custody.retain(exc,"fd-close-accounting")
                self._uncertain(custody,"store-fd-close-accounting")

    def read(self, record):
        name, size, expected = record["path"], record["bytes"], record["sha256"]
        need(type(size) is int and size >= 0, "read-size")
        path = self.path(name)
        # EOF observation is an additional possible byte and is admitted up front.
        reservation = self.budget.reserve("read_bytes", size + 1, "read:" + name)
        fd = None
        custody = Custody()
        self.observations.append(custody)
        chunks = []
        acknowledged = 0
        interrupted = False
        try:
            fd = self._open(path, os.O_RDONLY, custody)
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "regular-single-owner")
            need(before.st_size == size, "extent-before-read")
            if "mode" in record:
                need(stat.S_IMODE(before.st_mode)==record["mode"],"read-mode")
            while acknowledged < size + 1:
                try:
                    body = os.read(fd, min(1024 * 1024, size + 1 - acknowledged))
                except BaseException:
                    interrupted = True
                    raise
                acknowledged += len(body)
                if not body:
                    break
                chunks.append(body)
            after = os.fstat(fd)
            need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
                 (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), "read-stability")
            data = b"".join(chunks)
            need(len(data) == size and hashlib.sha256(data).hexdigest() == expected, "read-pin")
        except BaseException as exc:
            if custody.first is None or custody.first[1]is not exc:custody.retain(exc, "read")
        finally:
            try:self._settle(reservation, acknowledged, interrupted, custody)
            except BaseException as exc:custody.retain(exc,"settlement-owner")
            finally:
                if fd is not None:self._close(fd, custody)
        custody.raise_first()
        return data

    def write(self, name, data, mode=0o400):
        need(type(data) is bytes and mode in (0o400,0o444,0o500), "write-body")
        relative(name)
        if self.output_prefix is not None:
            name=self.output_prefix+"/"+name
            self.directory(name.rsplit("/",1)[0])
        path = self.path(name)
        reservation = self.budget.reserve("write_bytes", len(data), "write:" + name)
        fd = None
        acknowledged = 0
        unknown = False
        custody = Custody()
        self.observations.append(custody)
        creation_acknowledged = False
        try:
            self.budget.attempt("creation_attempts", "create:" + name)
            fd = self._open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, custody, 0o600)
            creation_acknowledged = True
            while acknowledged < len(data):
                try:
                    n = os.write(fd, data[acknowledged:])
                except BaseException:
                    unknown = True
                    raise
                need(type(n) is int and 0 < n <= len(data)-acknowledged, "write-progress")
                acknowledged += n
            try:
                os.fsync(fd)
                os.fchmod(fd, mode)
            except BaseException:
                unknown = True
                raise
        except BaseException as exc:
            if custody.first is None or custody.first[1]is not exc:custody.retain(exc, "write")
        finally:
            try:self._settle(reservation, acknowledged, unknown, custody)
            except BaseException as exc:custody.retain(exc,"settlement-owner")
            finally:
                if fd is not None:self._close(fd, custody)
        custody.raise_first()
        need(creation_acknowledged, "creation-unacknowledged")
        record = {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "mode": mode}
        need(self.read(record) == data, "write-readback")
        self.created.append(record)
        return record

    def json(self, record):
        return parse(self.read(record))

    def put(self, name, value):
        return self.write(name, canonical(value))

    def directory(self, name, exclusive=False):
        """Own every creation before effect; never adopt a pre-existing unknown dir."""
        relative(name)
        parts=name.split("/")
        for index in range(1,len(parts)+1):
            local="/".join(parts[:index])
            if local in self.directories:
                need(not (exclusive and index==len(parts)),"directory-once")
                self.path(local+"/member") # checks every owned parent is still a real directory
                continue
            path=self.path(local)
            self.budget.attempt("creation_attempts","directory:"+local)
            try:os.mkdir(path,0o700)
            except BaseException:
                self.budget.unknown.append({"effect":"directory:"+local,
                                           "unacknowledged_capacity":"creation"})
                raise
            self.directories.add(local)
        return self.path(name)

    def copy_from(self, reader, source, destination):
        """Exact explicit source-to-destination transfer, charged to each Store owner."""
        from .identity import descriptor
        descriptor(source);descriptor(destination)
        need((source["bytes"],source["sha256"])==
             (destination["bytes"],destination["sha256"]),"copy-source-identity")
        need(destination["mode"] in (0o400,0o444,0o500),"immutable-copy-mode")
        body=reader.read(source)
        if "/" in destination["path"]:
            self.directory(destination["path"].rsplit("/",1)[0])
        result=self.write(destination["path"],body,destination["mode"])
        need(result==destination,"copy-destination-identity")
        return result

"""Bounded fresh owned files and durable journal; never claims process isolation."""
import os
import stat
import hashlib
from pathlib import Path
from .contracts import need, canonical, pin

def stamp(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink)

def directory_stamp(st):
    # Creating owned child directories legitimately changes a directory's nlink.
    return (st.st_dev, st.st_ino, st.st_mode)

class OwnedDirectory:
    def __init__(self, path, max_bytes):
        need(type(max_bytes) is int and max_bytes > 0, "positive byte allowance")
        self.path = Path(path).absolute()
        self.max_bytes, self.written, self.closed = max_bytes, 0, False
        self.readback_bytes = 0
        self.parents = []
        self.fd = None
        try:
            # Hold the complete already-existing ancestry; no parent construction.
            parent = self.path.parent
            for p in reversed([parent, *parent.parents]):
                fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                self.parents.append((p, fd, directory_stamp(os.fstat(fd))))
            self._check_parents()
            parentfd = self.parents[-1][1]
            os.mkdir(self.path.name, mode=0o700, dir_fd=parentfd)
            self.fd = os.open(self.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=parentfd)
            self.root_stamp = directory_stamp(os.fstat(self.fd))
            os.fsync(parentfd)
            self.check()
        except BaseException:
            self.close()
            raise

    @classmethod
    def attach(cls, path, max_bytes, expected):
        """Reopen only our recorded child, with exact inode custody, never inferred ownership."""
        self = cls.__new__(cls)
        self.path=Path(path).absolute(); self.max_bytes=max_bytes
        self.written=0; self.readback_bytes=0; self.closed=False; self.fd=None; self.parents=[]
        need(type(max_bytes) is int and max_bytes>0,"positive attach allowance")
        try:
            parent=self.path.parent
            for p in reversed([parent,*parent.parents]):
                fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                self.parents.append((p,fd,directory_stamp(os.fstat(fd))))
            self.fd=os.open(self.path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,
                            dir_fd=self.parents[-1][1])
            self.root_stamp=directory_stamp(os.fstat(self.fd))
            need(tuple(expected)==self.root_stamp,"owned child identity changed")
            self.check(); return self
        except BaseException:
            self.close();raise

    def _check_parents(self):
        for p, fd, saved in self.parents:
            need(directory_stamp(os.fstat(fd)) == saved and
                 directory_stamp(os.stat(p, follow_symlinks=False)) == saved, "ancestor custody lost")

    def check(self):
        need(not self.closed and self.fd is not None, "owned directory closed")
        self._check_parents()
        need(directory_stamp(os.fstat(self.fd)) == self.root_stamp and
             directory_stamp(os.stat(self.path, follow_symlinks=False)) == self.root_stamp,
             "owned root replaced")

    def _name(self, name):
        need(type(name) is str and name not in ("", ".", "..") and "/" not in name
             and "\\" not in name and "\0" not in name, "single file name")

    def write(self, name, body):
        self._name(name); self.check()
        need(type(body) is bytes, "exact bytes")
        # Full attempted extent is charged before creating any file.
        self.written += len(body)
        need(self.written <= self.max_bytes, "owned byte cap")
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "ordinary new file")
            view = memoryview(body)
            while view:
                n = os.write(fd, view)
                need(n > 0, "short write")
                view = view[n:]
            os.fsync(fd)
            observed = os.pread(fd, len(body)+1, 0)
            self.readback_bytes += len(observed)
            need(observed == body, "same-open exact body readback")
            after = os.fstat(fd)
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            need(stamp(after) == stamp(current) == stamp(before)
                 and after.st_size == len(body), "published file custody")
            self.check()
            os.fsync(self.fd)
            return pin(body)
        finally:
            os.close(fd)

    def read_exact(self,name,expected):
        """Authenticate one already-owned ordinary body through the held directory."""
        self._name(name);self.check()
        need(type(expected) is dict and set(expected)=={"bytes","sha256"},"exact expected body pin")
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.fd)
        try:
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected["bytes"],
                 "owned existing body extent")
            body=os.pread(fd,before.st_size+1,0);self.readback_bytes+=len(body)
            need(pin(body)==expected,"owned existing body identity")
            need(stamp(before)==stamp(os.fstat(fd))==stamp(os.stat(name,dir_fd=self.fd,follow_symlinks=False)),
                 "same-open existing body custody")
            self.check();return body
        finally:os.close(fd)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.fd is not None:
            os.close(self.fd); self.fd = None
        for _, fd, _ in reversed(self.parents):
            os.close(fd)
        self.parents.clear()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

class Journal:
    def __init__(self, directory, name, max_bytes):
        directory._name(name); directory.check()
        need(type(max_bytes) is int and max_bytes > 0, "journal byte cap")
        self.directory, self.name, self.max_bytes = directory, name, max_bytes
        self.total, self.poisoned, self.closed = 0, False, False
        self.fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=directory.fd)
        self.saved = stamp(os.fstat(self.fd))
        self.digest = hashlib.sha256()
        try:
            os.fsync(self.fd); os.fsync(directory.fd)
        except BaseException:
            self.poisoned = True; self.close(); raise

    def append(self, body):
        need(not self.closed and not self.poisoned, "journal unavailable")
        need(type(body) is bytes and body.endswith(b"\n"), "whole newline record")
        try:
            self.directory.check()
            self.total += len(body); self.directory.written += len(body)
            need(self.total <= self.max_bytes and self.directory.written <= self.directory.max_bytes,
                 "journal attempted extent cap")
            need(stamp(os.fstat(self.fd)) == self.saved == stamp(os.stat(
                self.name, dir_fd=self.directory.fd, follow_symlinks=False)), "journal custody")
            view = memoryview(body)
            while view:
                n = os.write(self.fd, view); need(n > 0, "journal short write"); view = view[n:]
            os.fsync(self.fd)
            need(os.fstat(self.fd).st_size == self.total, "journal full extent")
            observed = os.pread(self.fd, len(body), self.total-len(body))
            self.directory.readback_bytes += len(observed)
            need(observed == body, "exact journal record readback")
            self.directory.check()
            need(stamp(os.stat(self.name, dir_fd=self.directory.fd,
                               follow_symlinks=False)) == self.saved, "journal name replaced")
            self.digest.update(body)
            return pin(body)
        except BaseException:
            self.poisoned = True
            raise

    def seal(self):
        need(not self.closed and not self.poisoned, "healthy journal before seal")
        try:
            self.directory.check(); os.fsync(self.fd); os.fsync(self.directory.fd)
            actual = hashlib.sha256(); offset = 0
            while offset < self.total:
                block = os.pread(self.fd, min(65536, self.total-offset), offset)
                self.directory.readback_bytes += len(block)
                need(block, "journal truncated during seal")
                actual.update(block); offset += len(block)
            need(os.fstat(self.fd).st_size == self.total and actual.digest() == self.digest.digest(),
                 "complete durable journal identity")
            need(stamp(os.fstat(self.fd)) == self.saved == stamp(os.stat(
                self.name, dir_fd=self.directory.fd, follow_symlinks=False)), "sealed journal custody")
            return {"bytes": self.total, "sha256": actual.hexdigest()}
        except BaseException:
            self.poisoned = True
            raise

    def close(self):
        if not self.closed:
            os.close(self.fd); self.closed = True

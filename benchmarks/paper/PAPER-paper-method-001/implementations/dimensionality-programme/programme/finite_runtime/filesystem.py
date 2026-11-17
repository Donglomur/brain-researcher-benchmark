"""Metered files with pre-open role admission and exact byte identities."""
from __future__ import annotations
import hashlib
import os
import stat
from pathlib import Path
from .common import require, Refusal, relative_path, content_descriptor, encode, decode

class Store:
    def __init__(self, root, meter, journal, *, denied_paths=(), denied_hashes=(), denied_prefixes=(), paper_admitter=None):
        self.root = Path(root)
        self.meter, self.journal = meter, journal
        self.denied_paths = frozenset(denied_paths)
        self.denied_hashes = frozenset(denied_hashes)
        self.denied_prefixes=tuple(denied_prefixes)
        self.paper_admitter=paper_admitter
        self.meter.checkpoint('store_root_open')
        self.root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def _parent(self, name, create=False):
        parts = relative_path(name).split('/')
        fd = os.dup(self.root_fd)
        try:
            for part in parts[:-1]:
                self.meter.checkpoint('path_component')
                if create:
                    try: os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError: pass
                new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd); fd = new
            return fd, parts[-1]
        except BaseException:
            os.close(fd); raise

    def admit(self, descriptor, allowed_roles):
        content_descriptor(descriptor)
        name = descriptor['path']
        if descriptor['role']=='paper_view':
            require(self.paper_admitter is not None,'PAPER_ACCESS_NOT_SEPARATELY_QUALIFIED')
            self.paper_admitter(descriptor)
        else:
            require(name not in self.denied_paths and descriptor['sha256'] not in self.denied_hashes
                    and not any(name==p or name.startswith(p.rstrip('/')+'/') for p in self.denied_prefixes),
                    'LOCAL_ONLY_PRIMARY_OR_RESTRICTED_BODY', name)
            require(not (set(descriptor.get('aliases', [])) & self.denied_paths) and not any(
                alias==p or alias.startswith(p.rstrip('/')+'/') for alias in descriptor.get('aliases',[])
                for p in self.denied_prefixes),
                    'LOCAL_ONLY_ALIAS')
        require(descriptor['role'] in allowed_roles, 'ROLE_NOT_EXPOSED', descriptor['role'])
        self.meter.checkpoint('body_role_admission')

    def read(self, descriptor, allowed_roles):
        self.admit(descriptor, allowed_roles)
        n = descriptor['bytes']
        self.journal.append('READ_INTENT', {'descriptor': descriptor, 'allowed_roles': sorted(allowed_roles)})
        self.meter.reserve('read_bytes', n + 1, 'body_read_capacity')
        parent, leaf = self._parent(descriptor['path'])
        fd = None
        try:
            self.meter.checkpoint('immediately_before_body_open')
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            st = os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_size == n, 'BODY_KIND_OR_SIZE_CHANGED')
            chunks, total = [], 0
            while total <= n:
                self.meter.checkpoint('before_body_read_chunk')
                body = os.read(fd, min(65536, n + 1 - total))
                self.meter.observe('read_bytes', len(body))
                if not body: break
                chunks.append(body); total += len(body)
            result = b''.join(chunks)
            require(len(result) == n and hashlib.sha256(result).hexdigest() == descriptor['sha256'],
                    'BODY_IDENTITY_CHANGED')
            self.meter.checkpoint('body_read_complete')
            return result
        finally:
            if fd is not None: os.close(fd)
            os.close(parent)

    def write(self, name, body, *, role, producer, media_type='application/json', extra=None):
        relative_path(name)
        require(type(body) is bytes, 'BYTE_OUTPUT_REQUIRED')
        require(name not in self.denied_paths and hashlib.sha256(body).hexdigest() not in self.denied_hashes
                and not any(name==p or name.startswith(p.rstrip('/')+'/') for p in self.denied_prefixes),
                'PRIMARY_WRITE_DENIED')
        self.journal.append('WRITE_INTENT', {'path': name, 'bytes': len(body), 'role': role})
        self.meter.reserve('write_bytes', len(body), 'body_write_capacity')
        parent, leaf = self._parent(name, create=True);fd = None;sent = 0
        try:
            self.meter.checkpoint('immediately_before_body_create')
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            while sent < len(body):
                self.meter.checkpoint('before_body_write_chunk')
                n = os.write(fd, body[sent:sent+65536])
                require(n > 0, 'ZERO_WRITE');sent += n;self.meter.observe('write_bytes', n)
            self.meter.checkpoint('before_body_fsync');os.fsync(fd)
            self.meter.checkpoint('body_write_complete')
        except BaseException as exc:
            self.meter.unknown({'path': name, 'observed_written': sent}, exc)
            raise
        finally:
            if fd is not None:os.close(fd)
            os.close(parent)
        desc = {'path': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                'media_type': media_type, 'role': role, 'producer': producer}
        if extra: desc.update(extra)
        return content_descriptor(desc)

    def json(self, descriptor, allowed_roles):
        return decode(self.read(descriptor, allowed_roles))

    def write_json(self, name, value, **kw):
        return self.write(name, encode(value), **kw)

    def close(self):
        os.close(self.root_fd)

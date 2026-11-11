"""Worker-local ownership and bounded ordinary artifacts, not a native issuer."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import stat


class Unavailable(Exception):
    def __init__(self, code, details):
        self.code, self.details = code, details
        super().__init__(code)


def require(condition, code, details=None):
    if not condition:
        raise Unavailable(code, details)


def unique(rows, key):
    answer = {}
    for row in rows:
        value = row[key]
        require(isinstance(value, str) and value and value not in answer,
                'duplicate-or-invalid-identity', key)
        answer[value] = row
    return answer


@dataclass(frozen=True)
class Occurrence:
    owner: object
    ordinal: int
    stage: str
    raw: BaseException
    traceback: object


class Owner:
    """Each actual catch is distinct; propagation explicitly carries its event."""
    def __init__(self):
        self.events = []
        self.first = None
        self.propagating = None

    def catch(self, stage, raw):
        event = Occurrence(self, len(self.events), stage, raw,
                           BaseException.__traceback__.__get__(raw))
        self.merge(event)
        return event

    def merge(self, event):
        if not any(x.owner is event.owner and x.ordinal == event.ordinal
                   for x in self.events):
            self.events.append(event)
            if self.first is None:
                self.first = event

    def close(self, stage, resource):
        try:
            resource.close()
        except BaseException as error:
            self.catch(stage, error)

    def raise_first(self):
        if self.first is not None:
            self.propagating = self.first
            raise BaseException.with_traceback(self.first.raw, self.first.traceback)

    def catch_or_propagate(self, stage, raw):
        event, self.propagating = self.propagating, None
        if event is not None and event.raw is raw:
            self.merge(event)
            return event
        return self.catch(stage, raw)

    def relay(self, other):
        for event in other.events: self.merge(event)
        if other.first is not None:
            self.propagating = other.first
            other.raise_first()

    def describe(self):
        # Diagnostic text is deliberately optional, never a prerequisite to retirement.
        return [{'ordinal': i, 'stage': e.stage,
                 'raw_type': type(e.raw).__name__} for i, e in enumerate(self.events)]


class Budget:
    """Logical local accounting; excludes native/library/descendant physical work."""
    def __init__(self, *, read_bytes, write_bytes, array_bytes, operations):
        self.limits = dict(read=read_bytes, write=write_bytes,
                           array=array_bytes, operations=operations)
        require(all(type(v) is int and v > 0 for v in self.limits.values()),
                'invalid-worker-logical-limits')
        self.used = dict.fromkeys(self.limits, 0)

    def charge(self, name, amount):
        require(type(amount) is int and amount >= 0, 'invalid-logical-debit', name)
        value = self.used[name] + amount
        require(value <= self.limits[name], 'worker-logical-limit',
                {'domain': name, 'attempted': value, 'limit': self.limits[name]})
        self.used[name] = value


class Artifacts:
    """Bounded local reader/writer. Parent capture/isolation remains external.

    Input paths are selected operator payload locations, never evidence of a
    protected/native capability. The parent must create isolated read-only views
    and independently capture all output files before accepting any result.
    """
    def __init__(self, output, budget, owner):
        self.output = Path(output)
        require(self.output.is_dir() and not self.output.is_symlink(),
                'output-root-must-exist')
        require(not any(self.output.iterdir()), 'output-root-not-empty')
        self.budget, self.owner, self.outputs = budget, owner, []

    def read(self, pin):
        p = Path(pin['path'])
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        local = Owner()
        data = None
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_size == pin['bytes'],
                    'input-extent-mismatch', str(p))
            self.budget.charge('read', before.st_size)
            self.budget.charge('array', 2*before.st_size)
            chunks, left = [], before.st_size
            while left:
                b = os.read(fd, min(left, 65536))
                require(bool(b), 'short-input-read', str(p))
                chunks.append(b); left -= len(b)
            require(os.read(fd, 1) == b'', 'input-grew', str(p))
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                     before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                     after.st_ctime_ns), 'input-changed', str(p))
            data = b''.join(chunks)
            require(hashlib.sha256(data).hexdigest() == pin['sha256'],
                    'input-digest-mismatch', str(p))
        except BaseException as error:
            local.catch('artifact-read', error)
        finally:
            try: os.close(fd)
            except BaseException as error: local.catch('artifact-read-close', error)
        self.owner.relay(local)
        return data

    def authenticate(self, pin):
        """Hash an original full recording without retaining its bytes in memory."""
        fd=os.open(Path(pin['path']),os.O_RDONLY|os.O_NOFOLLOW)
        local=Owner()
        try:
            before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_size==pin['bytes'], 'input-extent-mismatch')
            self.budget.charge('read',before.st_size)
            digest=hashlib.sha256();left=before.st_size
            while left:
                block=os.read(fd,min(left,65536))
                require(bool(block),'short-input-read')
                digest.update(block);left-=len(block)
            require(os.read(fd,1)==b'', 'input-grew')
            after=os.fstat(fd)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'input-changed')
            require(digest.hexdigest()==pin['sha256'],'input-digest-mismatch')
        except BaseException as error:local.catch('artifact-authenticate',error)
        finally:
            try:os.close(fd)
            except BaseException as error:local.catch('artifact-authenticate-close',error)
        self.owner.relay(local)
        return dict(pin)

    def write(self, name, data):
        require(isinstance(name, str) and name and '/' not in name and name not in {'.','..'},
                'unsafe-output-member')
        require(type(data) is bytes, 'output-must-be-bytes')
        self.budget.charge('write', len(data))
        fd = os.open(self.output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        local = Owner()
        try:
            offset = 0
            while offset < len(data):
                n = os.write(fd, data[offset:offset + 65536])
                require(type(n) is int and 0 < n <= min(65536, len(data)-offset),
                        'short-or-invalid-output-write', name)
                offset += n
            os.fsync(fd)
        except BaseException as error:
            local.catch('artifact-write', error)
        finally:
            try: os.close(fd)
            except BaseException as error: local.catch('artifact-write-close', error)
        self.owner.relay(local)
        row = {'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
               'capture': 'parent-owned-protected-capture-required'}
        self.outputs.append(row)
        return row

    def json(self, name, value):
        data = (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()
        return self.write(name, data)

    def array(self, pin, dtype, shape):
        # The worker imports numerical libraries only after explicit execution.
        import io
        import numpy as np
        count = 1
        for dim in shape:
            require(type(dim) is int and dim >= 0, 'array-dimension')
            count *= dim
        dt = np.dtype(dtype)
        require(not dt.hasobject, 'object-array-forbidden')
        self.budget.charge('array', count * dt.itemsize)
        data = self.read(pin)
        local=Owner();f=io.BytesIO(data);a=None
        try:
            version=np.lib.format.read_magic(f)
            require(version in {(1,0),(2,0)},'unsupported-npy-format')
            reader=(np.lib.format.read_array_header_1_0 if version==(1,0)
                    else np.lib.format.read_array_header_2_0)
            got_shape,fortran,got_dtype=reader(f,max_header_size=4096)
            require(got_shape==tuple(shape) and got_dtype==dt and not got_dtype.hasobject,
                    'array-header-schema-mismatch')
            require(len(data)-f.tell()==count*dt.itemsize,'array-payload-extent')
            f.seek(0)
            a=np.load(f,allow_pickle=False,max_header_size=4096)
        except BaseException as error:local.catch('array-decode',error)
        finally:local.close('array-input-buffer-close',f)
        self.owner.relay(local)
        require(type(a) is np.ndarray and a.shape == tuple(shape) and a.dtype == dt,
                'array-schema-mismatch')
        return a

    def json_input(self,pin):
        def pairs(items):
            out={}
            for key,value in items:
                require(key not in out,'duplicate-json-key',key);out[key]=value
            return out
        def constant(value):
            raise Unavailable('nonfinite-json-constant',value)
        return json.loads(self.read(pin),object_pairs_hook=pairs,parse_constant=constant)

    def inventory_tree(self,root):
        """Full local output inventory; parent still performs protected capture.

        This is a trusted-worker postcondition, not a race-safe native capability.
        The outer runtime must freeze the worker tree before its own capture.
        """
        root=Path(root)
        require(root.is_relative_to(self.output) and root.is_dir() and not root.is_symlink(),
                'output-tree-outside-worker')
        rows=[]
        for path in sorted(root.rglob('*')):
            mode=path.lstat().st_mode
            require(not stat.S_ISLNK(mode),'output-symlink')
            if stat.S_ISDIR(mode):continue
            require(stat.S_ISREG(mode),'nonregular-output')
            local=Owner();fd=None;digest=hashlib.sha256();size=0
            try:
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                before=os.fstat(fd);self.budget.charge('read',before.st_size)
                while size<before.st_size:
                    block=os.read(fd,min(65536,before.st_size-size))
                    require(bool(block),'short-output-inventory');digest.update(block);size+=len(block)
                require(os.read(fd,1)==b'','output-inventory-growth')
                after=os.fstat(fd)
                require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
                        'output-inventory-changed')
            except BaseException as error:local.catch('output-inventory',error)
            finally:
                if fd is not None:
                    try:os.close(fd)
                    except BaseException as error:local.catch('output-inventory-close',error)
            self.owner.relay(local)
            rows.append({'name':str(path.relative_to(self.output)),'bytes':size,
                         'sha256':digest.hexdigest(),'capture':'parent-capture-required'})
        require(bool(rows),'empty-sorter-output-tree')
        self.outputs.extend(rows)
        return rows

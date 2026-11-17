"""Closed ordinary-source/metadata primitives; no scientific imports."""
import hashlib
import json
import math
import os
import stat
from pathlib import Path, PurePosixPath

class Refusal(Exception):
    pass

def require(ok, reason):
    if not ok:
        raise Refusal(reason)

def pairs(rows):
    out = {}
    for k, v in rows:
        require(k not in out, 'duplicate JSON key')
        out[k] = v
    return out

def reject_constant(value):
    raise Refusal('nonfinite JSON scalar')

def parse(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=reject_constant)

def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def diagnostic_text(value, limit=512):
    """Diagnostic-only text: no arbitrary str/repr, bounded safe Unicode."""
    if type(limit) is not int:
        return '<invalid diagnostic text bound>'
    limit=min(512,max(0,limit))
    if type(value) is not str:
        return '<non-string diagnostic; raw annotation retained>'
    # Escape unpaired surrogates only in this diagnostic projection. This is
    # never used for scientific metadata, source identities or protocol hashes.
    return value[:limit].encode('utf-8','backslashreplace').decode('utf-8')[:limit]

def diagnostic_type(value):
    """Only exact trusted classes have names; arbitrary types get a fixed marker.

    Neither metaclass attribute descriptors nor equality/formatting callbacks
    are inspected. Raw original objects remain in their original carriers.
    """
    kind=type(value)
    for exact,name in ((str,'str'),(int,'int'),(float,'float'),(bool,'bool'),
                       (list,'list'),(tuple,'tuple'),(dict,'dict'),
                       (BaseException,'BaseException'),(Exception,'Exception'),
                       (ValueError,'ValueError'),(TypeError,'TypeError'),
                       (RuntimeError,'RuntimeError'),(OSError,'OSError'),
                       (UnicodeError,'UnicodeError'),(UnicodeEncodeError,'UnicodeEncodeError'),
                       (UnicodeDecodeError,'UnicodeDecodeError'),(Refusal,'Refusal')):
        if kind is exact:return name
    return 'non_builtin_type; raw object retained'

def diagnostic_projection(value, maximum_nodes=256, maximum_depth=6):
    """Finite plain-data emergency view, never authoritative input/result data."""
    if type(maximum_nodes) is not int or type(maximum_depth) is not int:
        return '<invalid diagnostic bounds; raw object retained>'
    maximum_nodes=min(256,max(0,maximum_nodes));maximum_depth=min(6,max(0,maximum_depth))
    remaining=[maximum_nodes]
    def project(item,depth):
        if remaining[0]<=0 or depth>maximum_depth:
            return '<diagnostic extent omitted; raw object retained>'
        remaining[0]-=1
        kind=type(item)
        if item is None or kind is bool:return item
        if kind is str:return diagnostic_text(item)
        if kind is int:
            return item if int.bit_length(item)<=128 else '<large integer omitted>'
        if kind is float:
            return item if math.isfinite(item) else '<nonfinite diagnostic scalar>'
        if kind is list or kind is tuple:
            out=[]
            for member in item:
                if remaining[0]<=0:
                    out.append('<remaining diagnostic members omitted>');break
                out.append(project(member,depth+1))
            return out
        if kind is dict:
            out={}
            for key,member in item.items():
                if remaining[0]<=0:
                    out['__diagnostic_remaining_members_omitted__']=True;break
                remaining[0]-=1  # Colliding/invalid keys still consume traversal.
                name=diagnostic_text(key,128)
                if name in out:
                    out['__diagnostic_key_collision_omitted__']=True;continue
                out[name]=project(member,depth+1)
            return out
        return '<non-plain diagnostic object: '+diagnostic_type(item)+'>'
    return project(value,0)

def sha(body):
    return hashlib.sha256(body).hexdigest()

def pin(body):
    return {'bytes': len(body), 'sha256': sha(body)}

def keys(value, required, optional=()):
    require(type(value) is dict, 'object required')
    require(set(required) <= set(value) <= set(required) | set(optional), 'closed field set')

def integer(value, low=0, high=None):
    require(type(value) is int and value >= low and (high is None or value <= high), 'bounded integer required')
    return value

def finite(value, positive=False):
    require(type(value) in (int, float) and math.isfinite(value) and (not positive or value > 0), 'finite number required')
    return value

def relative(value):
    require(type(value) is str and value and '\\' not in value and '\x00' not in value, 'ordinary relative path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and all(x not in ('', '.', '..') for x in p.parts), 'canonical path')
    return p

def ordinary(path):
    p = Path(path)
    require(p.is_absolute(), 'absolute trusted path')
    for part in (p, *p.parents):
        s = part.lstat()
        require(not stat.S_ISLNK(s.st_mode), 'symlink forbidden')
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'single-link ordinary file')
    return s

def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def descriptor(d):
    keys(d, ('path', 'bytes', 'sha256', 'mode', 'role'))
    relative(d['path']); integer(d['bytes'])
    require(type(d['sha256']) is str and len(d['sha256']) == 64 and all(c in '0123456789abcdef' for c in d['sha256']), 'SHA256')
    require(d['mode'] in ('0o644', '0o600', '0o444', '0o755', '0o700', '0o555'), 'ordinary mode')
    require(type(d['role']) is str and d['role'], 'explicit role')

def capture(root, d, budget, cap=None):
    descriptor(d); p = Path(root) / str(relative(d['path']))
    budget.check('before capture')
    s = ordinary(p); require(s.st_size == d['bytes'] and oct(stat.S_IMODE(s.st_mode)) == d['mode'], 'source extent/mode')
    require(cap is None or d['bytes'] <= cap, 'source cap')
    budget.admit_read(d['bytes'])
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    result = bytearray();first=None;failures=[]
    try:
        require(stamp(os.fstat(fd)) == stamp(s), 'same opened source')
        while True:
            b = os.read(fd, min(65536, d['bytes'] + 1 - len(result)))
            result.extend(b)
            budget.read(len(b))  # Preserve original returned prefix before a quota refusal.
            budget.check('after read return')
            require(len(result) <= d['bytes'], 'source grew')
            if not b:
                break
        require(stamp(os.fstat(fd)) == stamp(s) == stamp(p.lstat()), 'stable source identity')
    except BaseException as exc:
        first=exc;failures.append(('read',exc))
    finally:
        try:os.close(fd)
        except BaseException as exc:
            failures.append(('close',exc))
            budget.uncertain('capture:'+str(p),'managed_descriptor_closure',exc,descriptor=fd)
            if first is None:first=exc
    if first is not None:
        error=CaptureFailure(first,failures,result,d)
        raise error from first
    budget.check('after capture close')
    body = bytes(result)
    require(len(body) == d['bytes'] and sha(body) == d['sha256'], 'exact source bytes')
    return body

class CaptureFailure(Exception):
    def __init__(self,first,failures,received,descriptor):
        self.original_exception=first;self.failures=failures;self.received=received;self.descriptor=descriptor
        super().__init__('original input capture failed')

class FailureCarrier:
    """Strong original objects are retained before fallible formatting/publication."""
    def __init__(self):
        self.first = None
        self.failures = []
        self.originals = []
        self.durable = False
        self.contained = False
    def retain(self, value):
        self.originals.append(value)
        return value
    def fail(self, exc, stage):
        record = (stage, exc)
        if self.first is None:
            self.first = record
        self.failures.append(record)
    def document(self):
        # No custom exception __str__, __repr__, annotation conversion or
        # attribute lookup is needed to publish custody. Raw records stay intact.
        out=[]
        for stage,exc in self.failures[:32]:
            try:
                args=BaseException.args.__get__(exc)
                count=len(args) if type(args) is tuple else None
                message=diagnostic_text(args[0]) if type(args) is tuple and len(args)==1 and type(args[0]) is str else '<raw exception arguments retained>'
            except BaseException:
                count=None;message='<argument observation unavailable; raw exception retained>'
            out.append({'stage':diagnostic_text(stage,256),'type':diagnostic_type(exc),
                        'message':message,'argument_count':count})
        return {'first_error':out[0] if out else None,'errors':out,
                'durable':self.durable,'contained':self.contained,
                'original_error_records':len(self.failures),'projected_error_records':len(out),
                'unprojected_error_records':max(0,len(self.failures)-len(out)),
                'diagnostic_policy':'bounded_argument_projection_no_custom_str_or_repr',
                'raw_original_objects_retained':True}

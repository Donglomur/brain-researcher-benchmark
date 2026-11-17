"""Bounded ordinary-file IO for a portable trusted verifier; no candidate execution."""
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]

def read_bytes(path, cap):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symbolic links are not admitted')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        if not stat.S_ISREG(first.st_mode) or first.st_nlink != 1 or not 0 < first.st_size <= cap:
            raise ValueError('Bounded nonempty singly linked ordinary file required')
        chunks = []; left = cap + 1
        while left:
            chunk = os.read(fd, min(left, 1048576))
            if not chunk: break
            chunks.append(chunk); left -= len(chunk)
        body = b''.join(chunks); last = os.fstat(fd)
        stable = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if stable(first) != stable(last) or len(body) != first.st_size:
            raise ValueError('File changed during read')
        return body
    finally:
        os.close(fd)

def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def strict_json(body):
    def pairs(items):
        out = {}
        for k,v in items:
            if k in out: raise ValueError('Duplicate JSON key')
            out[k] = v
        return out
    def bad(_): raise ValueError('Nonfinite JSON token')
    return json.loads(body.decode('utf-8',errors='strict'), object_pairs_hook=pairs,parse_constant=bad)

def asset(target):
    # The operator controls this manifest. Never accept it from a candidate mount.
    records = strict_json(read_bytes(ROOT/'private/asset_manifest.json', 2097152))['files']
    matches = [x for x in records if x['target'] == target]
    if len(matches) != 1: raise ValueError('Unique packaged asset required: '+target)
    record = matches[0]
    body = read_bytes(ROOT/target, record['bytes'])
    if pin(body) != {k:record[k] for k in ('bytes','sha256')}:
        raise ValueError('Packaged asset pin differs: '+target)
    return body

def encode(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def write_new(path, body):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in path.parents): raise ValueError('Output parent symlink')
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f:
            f.write(body); f.flush(); os.fsync(fd)
    finally: os.close(fd)

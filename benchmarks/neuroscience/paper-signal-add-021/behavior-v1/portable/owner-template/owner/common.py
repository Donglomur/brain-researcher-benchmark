"""Small owner-only ordinary-file custody, with explicit finite accounting."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

class Refusal(ValueError):
    pass

def need(value, code):
    if not value:
        raise Refusal(code)

def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def decode(body, cap=1048576):
    need(type(body) is bytes and len(body) <= cap, 'bounded_json')
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    def bad(value):
        raise Refusal('nonfinite_json')
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)

def pin(body):
    need(type(body) is bytes, 'exact_body')
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def admit_pin(value, cap):
    need(type(value) is dict and set(value) == {'bytes','sha256'}, 'closed_pin')
    need(type(value['bytes']) is int and 0 <= value['bytes'] <= cap, 'pin_extent')
    h = value['sha256']
    need(type(h) is str and len(h) == 64 and all(c in '0123456789abcdef' for c in h), 'pin_hash')
    return value

def plain(value):
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts, 'absolute_ordinary_path')
    need(not any(q.is_symlink() for q in (p,*p.parents)), 'no_symlink_path')
    return p

def signature(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

class Budget:
    def __init__(self, deadline, read_limit, write_limit):
        need(type(deadline) in (int,float) and math.isfinite(deadline) and
             type(read_limit) is type(write_limit) is int and read_limit>0 and write_limit>0, 'finite_budget')
        self.deadline = deadline
        self.read_limit = read_limit
        self.write_limit = write_limit
        self.reads = self.reserved = self.successful = 0

    def check(self):
        need(time.monotonic() < self.deadline, 'original_deadline')

    def charge_read(self, amount):
        self.check()
        need(type(amount) is int and amount >= 0 and self.reads + amount <= self.read_limit, 'managed_read_limit')
        self.reads += amount

    def reserve_write(self, amount):
        self.check()
        need(type(amount) is int and amount >= 0 and self.reserved + amount <= self.write_limit, 'attempted_write_limit')
        self.reserved += amount

def read(path, expected, budget, cap=1048576, mode=None):
    admit_pin(expected, cap)
    p = plain(path)
    budget.check()
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'ordinary_input')
        if mode is not None:
            need(stat.S_IMODE(before.st_mode) == mode, 'selected_input_mode')
        budget.charge_read(before.st_size)
        blocks = []
        remaining = before.st_size
        while remaining:
            budget.check()
            b = os.read(fd, min(65536,remaining))
            need(bool(b), 'complete_read')
            blocks.append(b)
            remaining -= len(b)
        need(signature(before) == signature(os.fstat(fd)) == signature(p.lstat()), 'input_stable')
        body = b''.join(blocks)
        need(pin(body) == expected, 'input_pin')
    finally:
        os.close(fd)
    budget.check()
    return body

def write(path, body, budget, mode=0o400):
    need(type(body) is bytes, 'exact_output_bytes')
    p = plain(path)
    budget.reserve_write(len(body))
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    failure = None
    try:
        at = 0
        while at < len(body):
            budget.check()
            n = os.write(fd, body[at:])
            need(n > 0, 'complete_write')
            at += n
        os.fsync(fd)
        os.fchmod(fd, mode)
    except BaseException as error:
        failure = error
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if failure is None:
                failure = error
            else:
                failure.add_note('output descriptor close failed: ' + type(error).__name__)
    if failure is not None:
        raise failure
    budget.successful += len(body)
    budget.check()
    return {'path': str(p), **pin(body)}


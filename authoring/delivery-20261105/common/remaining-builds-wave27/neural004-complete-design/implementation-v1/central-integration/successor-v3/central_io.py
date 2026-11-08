"""Bounded source/receipt I/O; captured bytes only, no numerical imports."""
import hashlib
import json
import math
import os
import stat
import time
import uuid
from pathlib import Path

def need(ok,why):
    if not ok:raise ValueError(why)

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def parse(raw):
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'Duplicate metadata field');out[k]=v
        return out
    def floating(value):
        x=float(value);need(math.isfinite(x),'Finite JSON number');return x
    return json.loads(raw,object_pairs_hook=pairs,parse_float=floating,parse_constant=lambda _:need(False,'Nonfinite JSON'))

def ordinary(path):
    path=Path(path).absolute()
    need('..' not in path.parts and not any(x.is_symlink() for x in (path,*path.parents)),'Ordinary no-traversal path')
    need(all(not x.exists() or x.is_dir() for x in path.parents),'Ordinary directory ancestors')
    return path

def descriptor(value,cap=1048576,with_path=False,empty=False):
    keys={'bytes','sha256'}|({'path'} if with_path else set())
    need(type(value)is dict and set(value)==keys,'Exact descriptor fields')
    need(type(value['bytes'])is int and (0 if empty else 1)<=value['bytes']<=cap,'Bounded descriptor length')
    h=value['sha256'];need(type(h)is str and len(h)==64 and all(x in '0123456789abcdef' for x in h),'SHA256 identity')
    if with_path:need(type(value['path'])is str and Path(value['path']).is_absolute(),'Absolute descriptor path')
    return value

def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def cleanup_note(primary, action, error):
    detail = {'action': action, 'type': type(error).__name__, 'message': str(error)[:2000]}
    primary.cleanup_errors = [*getattr(primary, 'cleanup_errors', []), detail]
    if hasattr(primary, 'add_note'):
        primary.add_note('Cleanup uncertainty: ' + str(detail))

def capture(path, cap, expected=None):
    path = Path(path)
    need(type(cap) is int and cap > 0, 'Prospective explicit byte cap')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'Bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        after = os.fstat(fd)
        need(stat.S_ISREG(after.st_mode) and
             (before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and len(raw) == before.st_size,
             'Stable complete captured file')
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if primary is None:
                raise
            cleanup_note(primary, 'capture.close', error)
    if expected is not None:
        need(pin(raw) == expected, 'Exact operator-bound bytes/SHA')
    return raw

def sync_parent(path):
    """Durably order owned publication/removal; retain primary fsync failure."""
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    primary = None
    try:
        os.fsync(directory)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(directory)
        except BaseException as error:
            if primary is None:
                raise
            cleanup_note(primary, 'directory.close', error)

def durable_new(path, raw):
    """Exclusive full-body publication after checked writes/fsync/close.

    Only our own inode is removed on failure. No success receipt is returned
    after short/zero writes, failed close, publication or directory fsync.
    Arrays use this same primitive before completion metadata is published.
    """
    path = Path(path)
    need(type(raw) is bytes, 'Immutable complete output body')
    need(not path.exists() and not path.is_symlink(), 'Fresh metadata output')
    temporary = path.parent / ('.' + path.name + '.' + uuid.uuid4().hex + '.partial')
    fd = None
    owned = None
    published = False
    def remove_owned(target):
        try:
            state = os.stat(target, follow_symlinks=False)
        except FileNotFoundError:
            return
        need(owned == (state.st_dev, state.st_ino) and stat.S_ISREG(state.st_mode),
             'Cleanup refused a replaced/unowned output inode')
        os.unlink(target)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        state = os.fstat(fd)
        need(stat.S_ISREG(state.st_mode), 'Owned regular output')
        owned = (state.st_dev, state.st_ino)
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            written = os.write(fd, view[offset:])
            need(type(written) is int and 0 < written <= len(view)-offset, 'Complete checked write progress')
            offset += written
        os.fsync(fd)
        closing, fd = fd, None
        os.close(closing)
        os.link(temporary, path, follow_symlinks=False)
        published = True
        remove_owned(temporary)
        sync_parent(path)
        return pin(raw)
    except BaseException as primary:
        actions = []
        if fd is not None:
            actions.append(('output.close', lambda: os.close(fd)))
        if owned is not None and published:
            actions.append(('published.remove_owned', lambda: remove_owned(path)))
        if owned is not None:
            actions.append(('temporary.remove_owned', lambda: remove_owned(temporary)))
        for label, action in actions:
            try:
                action()
            except BaseException as error:
                cleanup_note(primary, label, error)
        raise


class IO:
    """Conservative source/control/receipt ledger; no credit after failed writes."""
    def __init__(self,read_cap,write_cap,retained_cap,origin,end):
        self.read_cap=read_cap;self.write_cap=write_cap;self.retained_cap=retained_cap
        self.origin=origin;self.end=end;self.last=origin;self.reads=self.writes=self.retained=0
        for x in (read_cap,write_cap,retained_cap):need(type(x)is int and x>0,'Positive IO allocation')
    def tick(self):
        now=time.monotonic();need(self.last<=now<self.end,'Original monotonic clock with rollback refusal');self.last=now;return now
    def capture(self,path,expected=None,cap=1048576,allow_empty=False):
        self.tick();path=ordinary(path);state=path.lstat()
        need(stat.S_ISREG(state.st_mode) and state.st_nlink==1 and (0 if allow_empty else 1)<=state.st_size<=cap,'Bounded ordinary source/receipt')
        if expected is not None:
            descriptor(expected,cap,empty=allow_empty);need(state.st_size==expected['bytes'],'Exact extent before capture')
        read_cap=max(1,state.st_size);self.reads+=read_cap+1;need(self.reads<=self.read_cap,'Reserved cumulative source/receipt read')
        raw=capture(path,read_cap,expected)
        named=path.lstat();fields=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        need(all(getattr(state,k)==getattr(named,k) for k in fields),'Captured name still identifies exact regular inode')
        self.tick();return raw
    def directories(self,path):
        path=ordinary(path);todo=[];q=path
        while not q.exists():
            need(len(todo)<32,'Bounded owned directory depth');todo.append(q);q=q.parent
        need(q.is_dir(),'Directory anchor')
        for q in reversed(todo):self.tick();q.mkdir(mode=0o700);sync_parent(q)
    def save(self,path,body):
        self.tick();need(type(body)is bytes,'Immutable bounded metadata bytes');path=ordinary(path)
        self.writes+=len(body);self.retained+=len(body)
        need(self.writes<=self.write_cap and self.retained<=self.retained_cap,'Reserved full control write/retention before publication')
        self.directories(path.parent);result=durable_new(path,body);self.tick();return result
    def freeze(self,path):
        self.tick();path=ordinary(path);state=path.lstat();need(stat.S_ISREG(state.st_mode) and state.st_nlink==1,'Owned ordinary source snapshot')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
        try:
            observed=os.fstat(fd);need((state.st_dev,state.st_ino)==(observed.st_dev,observed.st_ino),'Unchanged source inode');os.fchmod(fd,0o444);os.fsync(fd)
        except BaseException as error:primary=error;raise
        finally:
            try:os.close(fd)
            except BaseException as error:
                if primary is None:raise
                cleanup_note(primary,'freeze.close',error)
        sync_parent(path);self.tick()
    def snapshot(self):
        return {'read_bytes':self.reads,'write_bytes':self.writes,'retained_bytes':self.retained,'origin':self.origin,'deadline':self.end,'observed':self.last,'kernel_IO_or_RSS_measured':False}


def budget_counters(budget):
    """Retain last-known counters without calling a clock that already failed."""
    import copy
    return {'origin':budget.origin,'deadline':budget.end,'observed':budget.last,
            'logical_read_charge':budget.reads,'logical_write_charge':budget.writes,
            'retained_charge':budget.retained,'producer_reservations':copy.deepcopy(budget.reservations),
            'successfully_captured_host_file_read_bytes':budget.file_reads,
            'successfully_published_host_file_write_bytes':budget.file_writes,
            'last_successful_observation_only':True,'new_clock_observation':False,
            'kernel_native_IO_or_RSS_certified':False}


def failure_record(primary,stage,counters,known=None):
    return {'schema':'neural065_central_failure_evidence_v2','stage':stage,
            'initiating_error':{'type':type(primary).__name__,'message':str(primary)[:2000]},
            'ordered_secondary_errors':list(getattr(primary,'cleanup_errors',[])),
            'notes':list(getattr(primary,'__notes__',[])),
            'known_counters':counters,'known':known,'unknown_costs_not_zero':True,
            'no_refund_of_original_reservations':True,'invalidates_any_OBSERVED':True,
            'transitive_custody_if_not_independently_joined':'unknown','automatic_retry':False,
            'scientific_qualified':False}


def stderr_failure(value,deadline,limit=8192):
    """Bounded nonblocking diagnostic fallback, never scientific continuation.

    Its record describes pre-write known counters. Successful stream custody is
    still external; this function does not certify its caller's natural exit.
    """
    import select
    raw=encoded(value);need(len(raw)<=limit,'Complete bounded failure fallback')
    written=0;primary=None;old=None
    try:
        old=os.get_blocking(2);os.set_blocking(2,False)
        while written<len(raw):
            remaining=deadline-time.monotonic();need(remaining>0,'Original failure-only diagnostic cutoff')
            ready=select.select([], [2], [], min(.05,remaining))[1]
            if not ready:continue
            try:n=os.write(2,raw[written:])
            except BlockingIOError:continue
            need(type(n)is int and n>0,'Complete checked fallback write');written+=n
        return {'reserved_bytes':len(raw),'written_bytes':written,'complete':True}
    except BaseException as e:
        primary=e;e.partial_failure_stream={'reserved_bytes':len(raw),'written_bytes':written,'complete':False};raise
    finally:
        if old is not None:
            try:os.set_blocking(2,old)
            except BaseException as e:
                if primary is None:raise
                cleanup_note(primary,'failure.stderr.restore',e)

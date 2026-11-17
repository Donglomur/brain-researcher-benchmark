"""Bounded ordinary capture and truthful failure prefixes; no qualification issuer."""
import hashlib
import os
import stat
import time
from dataclasses import dataclass
from .domain import Pin, Refusal, canonical, relative, strict_json

class Budget:
    def __init__(self, limits):
        self.limits = limits
        self.started_ns = time.monotonic_ns()
        self.deadline_ns = self.started_ns + limits.wall_ns
        self.read_bytes = self.write_bytes = self.members = 0
        self.attempts = []
        self.raw_first = None
        self.secondary = []
    def fail(self, stage, error):
        row = {'stage': stage, 'type': type(error).__name__, 'message': str(error)[:4096]}
        if self.raw_first is None: self.raw_first = row
        else: self.secondary.append(row)
    def before(self, operation, amount):
        self.attempts.append({'operation': operation, 'planned_bytes': amount, 'completed': False})
        try:
            if amount < 0 or amount > self.limits.member_bytes: raise Refusal('member capacity')
            if self.read_bytes + self.write_bytes + amount > self.limits.total_bytes:
                raise Refusal('aggregate capacity')
            if time.monotonic_ns() >= self.deadline_ns: raise Refusal('original deadline')
        except BaseException as exc:
            self.fail(operation, exc); raise
        return len(self.attempts)-1
    def observed(self, index, amount, write=False):
        if write: self.write_bytes += amount
        else: self.read_bytes += amount
        self.attempts[index]['observed_bytes'] = amount
        self.attempts[index]['completed'] = True
    def prefix(self):
        # These are explicit local byte occurrences, not native child CPU/RSS totals.
        return {'read_bytes': self.read_bytes, 'write_bytes': self.write_bytes,
                'members': self.members, 'attempts': list(self.attempts),
                'raw_first': self.raw_first, 'secondary': list(self.secondary),
                'cpu_ns': None, 'peak_memory_bytes': None, 'native_io_bytes': None,
                'unfinished_span': True, 'original_deadline_ns': self.deadline_ns}

@dataclass(frozen=True)
class Capture:
    store: object
    ordinal: int
    pin: Pin

class Store:
    """A retained directory FD, not an untrusted record selecting filesystem authority.

    A future qualified host must create the private roots and their access policy.
    Construction here supplies byte custody only; it never supplies native admission.
    """
    def __init__(self, root, budget, writable=False):
        self.budget = budget; self.writable = writable; self.captures = []; self.publication_attempts = set()
        self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.identity = (os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino)
        self.closed = False
    def _parent(self, path, create=False):
        parts = relative(path).split('/')
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                if create:
                    try: os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError: pass
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                previous, fd = fd, nxt
                os.close(previous)
            return fd, parts[-1]
        except BaseException:
            try: os.close(fd)
            except OSError: pass
            raise
    def read(self, pin):
        if self.closed or type(pin) is not Pin: raise Refusal('closed store/Pin')
        attempt = self.budget.before('read:'+pin.path, pin.bytes)
        parent = fd = None; chunks = []; observed = 0
        try:
            parent, name = self._parent(pin.path)
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size != pin.bytes: raise Refusal('regular exact source')
            while observed < pin.bytes:
                block = os.read(fd, min(65536, pin.bytes-observed))
                if not block: raise Refusal('short source')
                chunks.append(block); observed += len(block)
            if os.read(fd, 1): raise Refusal('source extension')
            raw = b''.join(chunks)
            if hashlib.sha256(raw).hexdigest() != pin.sha256: raise Refusal('source identity')
            self.budget.observed(attempt, observed)
            return raw
        except BaseException as exc:
            self.budget.read_bytes += observed
            self.budget.attempts[attempt]['observed_bytes'] = observed
            self.budget.fail('read:'+pin.path, exc); raise
        finally:
            for owned in (fd, parent):
                if owned is not None:
                    try: os.close(owned)
                    except OSError as exc: self.budget.fail('read-close', exc)
    def json(self, pin): return strict_json(self.read(pin))
    def put(self, path, raw):
        if self.closed or not self.writable or type(raw) is not bytes: raise Refusal('write authority')
        if path in self.publication_attempts:
            exc=Refusal('publication path already attempted'); self.budget.fail('write:'+path,exc); raise exc
        self.publication_attempts.add(path)
        relative(path)
        if self.budget.members >= self.budget.limits.members: raise Refusal('member count')
        attempt = self.budget.before('write:'+path, len(raw))
        if self.budget.read_bytes + self.budget.write_bytes + 2*len(raw) > self.budget.limits.total_bytes:
            raise Refusal('capture plus full readback exceeds original aggregate capacity')
        # Retain attempted occurrence before every fallible filesystem effect.
        self.budget.members += 1
        parent = fd = None; observed = 0; verified = bytearray(); readback_counted = False
        try:
            parent, name = self._parent(path, create=True)
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            while observed < len(raw):
                n = os.write(fd, raw[observed:observed+65536])
                if n <= 0: raise Refusal('zero write')
                observed += n
            os.fsync(fd); os.lseek(fd, 0, os.SEEK_SET)
            while len(verified) < len(raw):
                block = os.read(fd, min(65536, len(raw)-len(verified)))
                if not block: raise Refusal('short capture readback')
                verified.extend(block)
            if bytes(verified) != raw or os.read(fd, 1): raise Refusal('capture readback')
            os.fchmod(fd, 0o400)
            self.budget.observed(attempt, observed, write=True)
            # Readback is a separate occurrence, including its bytes and budget.
            self.budget.read_bytes += len(verified)
            readback_counted = True
            if self.budget.read_bytes+self.budget.write_bytes > self.budget.limits.total_bytes:
                raise Refusal('capture readback aggregate capacity')
            pin = Pin(path, len(raw), hashlib.sha256(raw).hexdigest())
            capture = Capture(self, len(self.captures), pin)
            self.captures.append(capture)
            return capture
        except BaseException as exc:
            if not self.budget.attempts[attempt]['completed']: self.budget.write_bytes += observed
            if not readback_counted: self.budget.read_bytes += len(verified)
            self.budget.attempts[attempt]['observed_bytes'] = observed
            self.budget.attempts[attempt]['readback_observed_bytes'] = len(verified)
            self.budget.fail('write:'+path, exc); raise
        finally:
            for owned in (fd, parent):
                if owned is not None:
                    try: os.close(owned)
                    except OSError as exc: self.budget.fail('write-close', exc)
    def put_json(self, path, value): return self.put(path, canonical(value))
    def require_capture(self, capture):
        if type(capture) is not Capture or capture.store is not self:
            raise Refusal('foreign capture owner')
        if not 0 <= capture.ordinal < len(self.captures) or self.captures[capture.ordinal] is not capture:
            raise Refusal('capture occurrence')
        return capture.pin
    def earlier_capture(self, pin, before):
        """Resolve to the actual registered occurrence, never grant from equal metadata."""
        self.require_capture(before)
        matches=[c for c in self.captures[:before.ordinal] if c.pin==pin]
        if len(matches)!=1:raise Refusal('missing/nonunique earlier captured product')
        self.require_capture(matches[0]);return matches[0]
    def close_once(self):
        if self.closed: return
        self.closed = True; fd, self.fd = self.fd, None
        try: os.close(fd)
        except OSError as exc: self.budget.fail('store-close', exc); raise

def finish(store, status, products, budget):
    """Full prefix is captured before the bounded terminal; first failure is never reset."""
    try:
        prefix = budget.prefix()
        cost = store.put_json('final/cost-prefix.json', prefix)
        terminal = {'schema': 'trial_session_terminal_v1', 'status': 'failed' if budget.raw_first is not None else status,
                    'products': [store.require_capture(x).document() for x in products],
                    'cost_prefix': cost.pin.document(), 'raw_first': budget.raw_first,
                    'secondary': list(budget.secondary), 'scientifically_qualified': False}
        return store.put_json('final/terminal.json', terminal)
    except BaseException as exc:
        budget.fail('final-publication', exc)
        # No retry of either consumed path, no invented empty cost prefix.
        return None

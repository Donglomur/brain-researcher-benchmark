"""Bounded task-local metadata; this module grants no execution authority."""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import struct
import time

HERE = Path(__file__).resolve().parent
FRAME_CAP = 2 * 1024**2
JOURNAL_CAP = 32 * 1024**2
EVENT_CAP = 4096
CLI_CAP = 512
PAIR_SECONDS = {'reproduction': 173760, 'improvement': 22560}
RECOVERY_SECONDS = 60
CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(value):
    # This is the unchanged Provider's exact wire encoding, not pretty metadata.
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def unique(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate owner metadata key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite owner metadata'))


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and value['bytes'] > 0
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact positive metadata descriptor')
    return value


def ordinary(value):
    p = Path(value).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)),
         'Unlinked absolute owner path')
    return p


def body(value, expected=None, cap=FRAME_CAP):
    p = ordinary(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'Bounded single-link owner file')
        raw = stream.read(cap + 1)
        after, named = os.fstat(stream.fileno()), p.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
         for k in fields), 'Stable complete owner metadata')
    if expected is not None:
        need(pin(raw) == descriptor(expected), 'Owner metadata pin changed')
    return raw


def read(value, expected=None, cap=FRAME_CAP):
    return parse(body(value, expected, cap))


def publish(value, document, cap=FRAME_CAP):
    p = ordinary(value)
    raw = encoded(document)
    need(len(raw) <= cap, 'Owner metadata output cap')
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return pin(raw)


class OwnerWriter:
    """One precharged cap for every parent publication, including failed writes."""
    def __init__(self, initial_bytes=0):
        need(type(initial_bytes) is int and 0 <= initial_bytes < JOURNAL_CAP,
             'Bounded existing owner publications')
        # Seven bounded process records, transient publication storage and lock
        # metadata are charged conservatively rather than refunded from retention.
        self.used = initial_bytes + 256 * 1024
        self.terminal_reserve = 2 * 1024**2

    def publish(self, value, document, *, terminal=False):
        size = len(encoded(document))
        need(size <= FRAME_CAP and self.used + size <= JOURNAL_CAP - (0 if terminal else self.terminal_reserve),
             'Whole owner metadata ceiling with reserved terminal evidence')
        self.used += size  # A partial failed publication consumes its full charge.
        return publish(value, document)


def frame(value):
    raw = encoded(value)
    need(0 < len(raw) <= FRAME_CAP, 'Bounded owner frame')
    return struct.pack('!I', len(raw)) + raw


def extract(buffer):
    if len(buffer) < 4:
        return None
    length, = struct.unpack('!I', buffer[:4])
    need(0 < length <= FRAME_CAP, 'Bounded announced owner frame')
    if len(buffer) < 4 + length:
        return None
    raw = bytes(buffer[4:4 + length])
    del buffer[:4 + length]
    return parse(raw)


class Channel:
    """A synchronous anonymous socket inherited only by the trusted controller."""
    def __init__(self, sock, invocation_pin, deadline):
        self.sock, self.invocation_pin, self.deadline = sock, invocation_pin, deadline
        self.sequence = 0

    def __call__(self, name, value):
        left = self.deadline - time.monotonic()
        need(left > 0, 'Owner callback before retained controller cutoff')
        message = {'schema': 'smc_owner_rpc_v1', 'invocation_pin': self.invocation_pin,
                   'sequence': self.sequence, 'event': name, 'value': value}
        self.sock.settimeout(left)
        self.sock.sendall(frame(message))
        buffer = bytearray()
        while True:
            left = self.deadline - time.monotonic()
            need(left > 0, 'Parent acknowledgement before retained cutoff')
            self.sock.settimeout(left)
            chunk = self.sock.recv(min(65536, FRAME_CAP + 4 - len(buffer)))
            need(chunk, 'Parent owner closed without acknowledgement')
            buffer.extend(chunk)
            response = extract(buffer)
            if response is not None:
                need(not buffer and response == {'schema': 'smc_owner_ack_v1',
                     'sequence': self.sequence, 'message_pin': pin(encoded(message))},
                     'Exact synchronous persisted parent acknowledgement')
                need(time.monotonic() < self.deadline, 'Parent acknowledgement received before original cutoff')
                self.sequence += 1
                return

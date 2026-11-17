"""Admission and cumulative I/O guards for one owned DoSEI native producer.

No scientific input is opened before exact root admission, active artifact
reservation and direct native-lease identity have been checked. No dispatch is
performed here. Counters conservatively precharge interrupted I/O requests.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import stat
import sys
import time
import types

E = Path('/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/comprehensive-revision-20261116-v2')
RAW = Path('/Users/nicholas/Documents/Codex/neuroscience-benchmark-data/dosei-native-v2-20261117')
OUTPUT = RAW / 'full-eeg-native-v1'
OWNER = 'complete_dosei'
RESERVATION = 'dosei-full-eeg-native-artifacts-20261117'
ARCHIVE_SHA = 'd2c4e94ddfbea1b3ad825bf7d61b0571d5e84e868916fb4d86981c3802d4917d'
ARCHIVE_MD5 = 'b98c8a81d2e866085f9e7ac75a950754'
ARCHIVE_BYTES = 724356077
LIMITS = {'output_bytes': 2147483648, 'metadata_output_bytes': 67108864,
          'compressed_source_read_bytes': 1610612736, 'saved_scientific_read_bytes': 16777216,
          'operational_read_bytes': 67108864, 'overall_seconds': 7200, 'internal_seconds': 7180,
          'member_seconds': 165, 'cpu_soft_seconds': 6790, 'cpu_hard_seconds': 6800,
          'declared_ram_bytes': 536870912, 'threads': 1, 'automatic_retries': 0}
STAT_KEYS = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
FINAL_RESERVE = 524288
METADATA_FINAL_RESERVE = 262144


def require(ok, message):
    if not ok:
        raise ValueError(message)


def signature(value):
    return {key: getattr(value, key) for key in STAT_KEYS}


def unique_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    def finite_float(token):
        value = float(token)
        require(math.isfinite(value), 'nonfinite JSON float conversion')
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def encode(value, cap):
    pieces = []; total = 1
    for fragment in json.JSONEncoder(sort_keys=True, ensure_ascii=True, allow_nan=False,
                                     separators=(',', ':')).iterencode(value):
        part = fragment.encode('utf-8'); total += len(part)
        require(total <= cap, 'serialized JSON exceeds frozen file ceiling')
        pieces.append(part)
    return b''.join(pieces) + b'\n'


class ReadMeter:
    def __init__(self, cap):
        self.cap = cap; self.charged = 0; self.known = 0

    def read(self, fd, count):
        require(type(count) is int and 0 <= count <= 1048576, 'bounded descriptor read required')
        require(self.charged + count <= self.cap, 'cumulative input read grant exhausted')
        self.charged += count
        # If a signal interrupts before reconciliation, the entire grant stays
        # charged. Never reset an unknown read to zero or retry the operation.
        raw = os.read(fd, count)
        self.known += len(raw)
        self.charged -= count - len(raw)
        return raw

    def report(self):
        return {'ceiling_bytes': self.cap, 'charged_bytes': self.charged,
                'known_returned_bytes': self.known,
                'unreconciled_grant_upper_bound_bytes': self.charged - self.known}


def read_regular(path, cap, meter):
    path = Path(path)
    require(path.is_absolute() and path.parent.resolve() == path.parent, 'real absolute input parent required')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'regular bounded input required')
        require(signature(before) == signature(path.lstat()), 'input path/descriptor disagreement')
        pieces = []; total = 0
        while True:
            raw = meter.read(fd, min(1048576, cap + 1 - total))
            if not raw: break
            pieces.append(raw); total += len(raw)
            require(total <= cap, 'input grew beyond file ceiling')
        require(total == before.st_size and signature(before) == signature(os.fstat(fd)) == signature(path.lstat()),
                'input identity changed during bounded read')
        return b''.join(pieces)
    finally:
        os.close(fd)


def validate_authority(ledger, args, protocol, *, pid, parent_pid, permit_pending=False):
    binding = {'path': str(args.protocol), 'sha256': args.protocol_sha256}
    approvals = [row for row in ledger.get('approved_native_protocols', []) if row['id'] == args.approval_id]
    require(len(approvals) == 1 and approvals[0]['owner'] == OWNER and approvals[0]['approved_by'] == '/root'
            and approvals[0]['protocol'] == binding, 'exact root protocol approval required')
    reservations = [row for row in ledger['reservations'] if row['id'] == RESERVATION]
    require(len(reservations) == 1, 'unique native artifact reservation required')
    reservation = reservations[0]
    require(reservation['owner'] == OWNER and reservation['kind'] == 'artifact' and reservation['status'] == 'active'
            and type(reservation['reserved_bytes']) is int and reservation['reserved_bytes'] == LIMITS['output_bytes']
            and reservation['destination'] == str(OUTPUT), 'exact active 2 GiB reservation required')
    runs = [row for row in ledger['native_runs'] if row['id'] == args.native_run_id]
    require(len(runs) == 1, 'unique owned native lease required')
    run = runs[0]
    command = [protocol['python_executable'], '-I', '-S', '-B', protocol['producer_path'],
               '--protocol', str(args.protocol), '--protocol-sha256', args.protocol_sha256,
               '--approval-id', args.approval_id, '--native-run-id', args.native_run_id]
    require(run['owner'] == OWNER and run['status'] == 'running' and run['protocol'] == binding
            and run['approval_id'] == args.approval_id and run['command'] == command
            and type(run['coordinator_pid']) is int and run['coordinator_pid'] == parent_pid,
            'producer must be the exact directly owned native command')
    require(type(run['requested_threads']) is int and run['requested_threads'] == 1 and
            type(run['declared_max_working_ram_bytes']) is int and
            run['declared_max_working_ram_bytes'] == LIMITS['declared_ram_bytes'], 'native resource scope mismatch')
    if permit_pending and run.get('child_pid') is None:
        return False
    require(type(run.get('child_pid')) is int and run['child_pid'] == pid, 'native producer PID is not owned')
    return True


class MeteredArchive:
    def __init__(self, path, expected_signature, meter):
        self.path = Path(path); self.expected_signature = expected_signature; self.meter = meter
        require(self.path.parent.resolve() == self.path.parent, 'archive parent changed')
        self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
        try: self.check_identity()
        except BaseException:
            os.close(self.fd); self.fd = None; raise

    def check_identity(self):
        observed = os.fstat(self.fd)
        require(stat.S_ISREG(observed.st_mode) and signature(observed) == self.expected_signature
                and signature(self.path.lstat()) == self.expected_signature, 'original archive identity changed')

    def read(self, size=-1):
        if size == -1:
            remaining = self.expected_signature['st_size'] - self.tell()
            require(0 <= remaining <= 65557, 'unbounded non-tail archive read refused')
            size = remaining
        require(type(size) is int and 0 <= size <= 1048576, 'unbounded archive read refused')
        return self.meter.read(self.fd, size)

    def readinto(self, buffer):
        view = memoryview(buffer)
        require(view.c_contiguous and not view.readonly, 'writable contiguous read buffer required')
        view = view.cast('B')
        raw = self.read(len(view)); view[:len(raw)] = raw; return len(raw)

    def seek(self, offset, whence=0):
        require(type(offset) is int and whence in (0, 1, 2), 'invalid archive seek')
        position = os.lseek(self.fd, offset, whence)
        require(0 <= position <= self.expected_signature['st_size'], 'archive seek outside authenticated extent')
        return position

    def tell(self): return os.lseek(self.fd, 0, os.SEEK_CUR)
    def seekable(self): return True
    def readable(self): return True

    def close(self):
        if self.fd is not None:
            try: self.check_identity()
            finally: os.close(self.fd); self.fd = None

    def __enter__(self): return self
    def __exit__(self, *unused): self.close()


class OutputBudget:
    def __init__(self, directory, total=LIMITS['output_bytes'], metadata=LIMITS['metadata_output_bytes']):
        self.directory = Path(directory); self.total = total; self.metadata = metadata
        self.charged = 0; self.known = 0; self.metadata_charged = 0; self.metadata_known = 0
        self.writers = []

    def charge(self, count, *, binary, critical):
        reserve = 0 if critical else FINAL_RESERVE
        metadata_reserve = 0 if critical else METADATA_FINAL_RESERVE
        require(self.charged + count <= self.total - reserve, 'whole-run artifact ceiling/final reserve')
        if not binary:
            require(self.metadata_charged + count <= self.metadata - metadata_reserve, 'whole-run sidecar ceiling/final reserve')
            self.metadata_charged += count
        self.charged += count

    def writer(self, name, cap, *, binary=False, critical=False):
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,180}', name), 'unsafe output name')
        require(type(cap) is int and 0 <= cap <= self.total, 'invalid output file cap')
        require(len(self.writers) < 2048, 'output file ceiling')
        writer = Writer(self, name, cap, binary, critical)
        self.writers.append(writer); return writer


class Writer:
    def __init__(self, budget, name, cap, binary, critical):
        self.budget = budget; self.path = budget.directory / name; self.cap = cap
        self.binary = binary; self.critical = critical; self.known = 0; self.charged = 0
        self.digest = hashlib.sha256(); self.closed = False; self.final_signature = None
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)

    def write(self, raw):
        require(not self.closed and isinstance(raw, (bytes, bytearray, memoryview)), 'invalid output write')
        view = memoryview(raw)
        require(view.c_contiguous, 'noncontiguous output buffer refused')
        view = view.cast('B')
        require(self.charged + len(view) <= self.cap, 'per-file output ceiling')
        self.budget.charge(len(view), binary=self.binary, critical=self.critical)
        self.charged += len(view)
        written = os.write(self.fd, view)
        self.known += written; self.budget.known += written
        if not self.binary: self.budget.metadata_known += written
        self.digest.update(view[:written])
        # Short/unknown bytes remain conservatively charged; caller refuses
        # completion rather than repairing/retrying a short output write.
        return written

    def close(self):
        if not self.closed:
            try:
                os.fsync(self.fd)
                self.final_signature = signature(os.fstat(self.fd))
            finally:
                os.close(self.fd); self.closed = True

    def binding(self):
        require(self.closed and self.final_signature is not None, 'writer must be closed before binding')
        require(self.charged == self.known == self.final_signature['st_size'], 'unknown/partial write cannot be a complete stream')
        require(signature(self.path.lstat()) == self.final_signature and stat.S_ISREG(self.path.lstat().st_mode), 'closed output changed')
        return {'path': str(self.path), 'bytes': self.known, 'sha256': self.digest.hexdigest(),
                'closed_file_signature': dict(self.final_signature),
                'hash_scope': 'exact successful unbuffered writes with post-close identity/size check; independent disk rehash pending'}


def timeout(signum, frame):
    raise TimeoutError('owned native producer reached its member/wall/CPU deadline or was interrupted')


class GuardContext:
    def __init__(self, args):
        self.args = args; self.started = time.monotonic(); self.lock_fd = None; self.archive_opened = False
        self.parent_pid = os.getppid()
        self.source_meter = ReadMeter(LIMITS['compressed_source_read_bytes'])
        self.saved_meter = ReadMeter(LIMITS['saved_scientific_read_bytes'])
        self.operational_meter = ReadMeter(LIMITS['operational_read_bytes'])
        bootstrap_bytes = args.bootstrap_operational_read_bytes
        require(type(bootstrap_bytes) is int and 0 < bootstrap_bytes <= 65536, 'bounded guard bootstrap accounting required')
        self.operational_meter.charged = self.operational_meter.known = bootstrap_bytes
        self.protocol = self.load_json(args.protocol, args.protocol_sha256, 1048576, scientific=False)
        protocol = self.protocol
        require(protocol['schema'] == 'dosei_full_native_eeg_preparation_v1' and protocol['owner'] == OWNER,
                'native protocol schema/owner mismatch')
        require(protocol['limits'] == LIMITS and all(type(value) is int for value in protocol['limits'].values()), 'frozen resource limits changed')
        require(protocol['full_scope_recordings'] == 171 and protocol['total_source_rows'] == 70760492,
                'complete original population required')
        require(protocol['approval_id'] == args.approval_id and protocol['native_run_id'] == args.native_run_id,
                'protocol execution identity mismatch')
        require(protocol['output_directory'] == str(OUTPUT) and protocol['output_reservation_id'] == RESERVATION,
                'wrong artifact destination/reservation')
        require(protocol['archive_path'] == str(RAW/'data.zip') and protocol['archive_sha256'] == ARCHIVE_SHA
                and protocol['archive_md5'] == ARCHIVE_MD5 and protocol['archive_signature']['st_size'] == ARCHIVE_BYTES,
                'wrong authenticated original archive')
        require(protocol['canonical_scoring'] is False and protocol['model_execution'] is False,
                'scientific execution scope changed')
        require(str(Path(sys.argv[0]).absolute()) == protocol['producer_path'] and
                str(Path(__file__).absolute()) == protocol['guards_path'], 'wrong producer/guard source path')
        self.load_bytes(Path(protocol['producer_path']), protocol['producer_sha256'], 65536, scientific=False)
        self.load_bytes(Path(__file__), protocol['guards_sha256'], 65536, scientific=False)
        deadline = time.monotonic() + 2
        while True:
            ledger = unique_json(read_regular(E/'RESOURCES.json', 8388608, self.operational_meter))
            if validate_authority(ledger, args, protocol, pid=os.getpid(), parent_pid=os.getppid(), permit_pending=True): break
            require(time.monotonic() < deadline, 'native producer registration deadline')
            time.sleep(0.05)
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM, signal.SIGXCPU):
            signal.signal(signum, timeout)
        old_soft, old_hard = resource.getrlimit(resource.RLIMIT_CPU)
        require(old_hard == resource.RLIM_INFINITY or old_hard >= LIMITS['cpu_hard_seconds'], 'existing CPU hard limit is lower than frozen policy')
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_soft_seconds'], LIMITS['cpu_hard_seconds']))
        signal.setitimer(signal.ITIMER_REAL, LIMITS['internal_seconds'])
        require(OUTPUT.parent.resolve() == OUTPUT.parent, 'output parent must be real')
        if not OUTPUT.exists(): OUTPUT.mkdir(mode=0o700)
        require(stat.S_ISDIR(OUTPUT.lstat().st_mode) and not OUTPUT.lstat().st_mode & 0o077, 'private output directory required')
        require(not any(OUTPUT.iterdir()), 'existing native attempt refused; no retries or overwrite')
        self.lock_fd = os.open(OUTPUT/'cohort-output.lock', os.O_RDWR|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0), 0o600)
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.output = OutputBudget(OUTPUT)

    def load_bytes(self, path, sha256, cap, scientific=True):
        require(type(sha256) is str and re.fullmatch(r'[0-9a-f]{64}', sha256), 'invalid SHA256 pin')
        raw = read_regular(Path(path), cap, self.saved_meter if scientific else self.operational_meter)
        require(hashlib.sha256(raw).hexdigest() == sha256, 'frozen input bytes changed')
        return raw

    def load_json(self, path, sha256, cap, scientific=True):
        return unique_json(self.load_bytes(path, sha256, cap, scientific))

    def load_module(self, path, sha256, name):
        require(name in ('numeric_policy', 'numeric_stream', 'annotation_events', 'inventory_guard'), 'unapproved module identity')
        raw = self.load_bytes(Path(path), sha256, 65536, scientific=False)
        module = types.ModuleType(name); module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        return module

    def open_archive(self):
        require(not self.archive_opened, 'only one original archive handle/pass is admitted')
        require(os.getppid() == self.parent_pid, 'owned coordinator exited before source opening')
        self.archive_opened = True
        source = MeteredArchive(RAW/'data.zip', self.protocol['archive_signature'], self.source_meter)
        try:
            sha = hashlib.sha256(); md5 = hashlib.md5(usedforsecurity=False); count = 0
            while True:
                block = source.read(1048576)
                if not block: break
                count += len(block); sha.update(block); md5.update(block)
            require(count == ARCHIVE_BYTES and sha.hexdigest() == ARCHIVE_SHA and md5.hexdigest() == ARCHIVE_MD5,
                    'complete original archive authentication failed')
            source.check_identity()
            require(os.getppid() == self.parent_pid, 'owned coordinator exited during archive authentication')
            source.seek(0)
            return source
        except BaseException:
            source.close(); raise

    def writer(self, name, cap, binary=False):
        return self.output.writer(name, cap, binary=binary)

    def json(self, name, value, cap, critical=False):
        raw = encode(value, cap)
        writer = self.output.writer(name, cap, critical=critical)
        try: require(writer.write(raw) == len(raw), 'short metadata write; preserve failed artifact')
        finally: writer.close()
        return writer.binding()

    def check_boundary(self):
        require(os.getppid() == self.parent_pid, 'owned coordinator exited; no next source member')
        elapsed = time.monotonic() - self.started
        usage = resource.getrusage(resource.RUSAGE_SELF)
        cpu = usage.ru_utime + usage.ru_stime
        require(elapsed + LIMITS['member_seconds'] + 10 < LIMITS['internal_seconds'], 'insufficient wall allowance for next full member/finalization')
        require(cpu + LIMITS['member_seconds'] + 10 < LIMITS['cpu_soft_seconds'], 'insufficient CPU allowance for next full member/finalization')

    @contextmanager
    def member_deadline(self):
        self.check_boundary()
        signal.setitimer(signal.ITIMER_REAL, LIMITS['member_seconds'])
        try: yield
        finally:
            remaining = LIMITS['internal_seconds'] - (time.monotonic() - self.started)
            signal.setitimer(signal.ITIMER_REAL, max(0.001, remaining))

    def resources(self):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        retained = 0; files = 0
        for path in OUTPUT.iterdir():
            item = path.lstat(); require(stat.S_ISREG(item.st_mode), 'unexpected output entry')
            retained += item.st_size; files += 1
        require(files <= 2049 and retained <= LIMITS['output_bytes'], 'retained artifact inventory cap')
        return {'compressed_source_reads': self.source_meter.report(), 'saved_scientific_reads': self.saved_meter.report(),
                'operational_reads': self.operational_meter.report(), 'charged_output_bytes': self.output.charged,
                'known_written_output_bytes': self.output.known, 'charged_metadata_bytes': self.output.metadata_charged,
                'known_written_metadata_bytes': self.output.metadata_known, 'retained_bytes_at_snapshot': retained,
                'retained_files_at_snapshot': files, 'wall_seconds': time.monotonic()-self.started,
                'cpu_user_seconds': usage.ru_utime, 'cpu_system_seconds': usage.ru_stime,
                'cpu_scope': 'single owned producer including its code, authentication, parsing and finalization; outer controller/launcher overhead reported separately',
                'cpu_limits_soft_hard_seconds': [6790, 6800],
                'maxrss_bytes': usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                'RAM_is_declared_not_OS_enforced': True,
                'missing_final_resource_receipt_requires_full_frozen_read_CPU_grants_charged': True}

    def close(self):
        if hasattr(self, 'output'):
            for writer in self.output.writers:
                if not writer.closed:
                    try: writer.close()
                    except Exception: pass
        if self.lock_fd is not None:
            os.close(self.lock_fd); self.lock_fd = None

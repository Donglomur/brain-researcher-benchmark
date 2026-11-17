"""Trusted container-only adapter for the existing five-file program ABI.

This source is rendered with an exact candidate body. It receives no reference
or operator selection. The host never imports or executes candidate source.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time

CAPS = {'cells.csv': 500000, 'branches.csv': 4000000, 'author_sections.csv': 3000000,
        'components.csv': 250000, 'summary.json': 200000, 'interpretation.json': 20000}
REQUIRED = set(CAPS) - {'interpretation.json'}
TOTAL = 8000000
LOG_CAP = 65536


def need(ok, message):
    if not ok:
        raise ValueError(message)


def signature(s):
    return tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
                                       'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def capture_files(root):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'ordinary_output_directory')
    entries = list(root.iterdir())
    need(REQUIRED <= {p.name for p in entries} <= set(CAPS), 'exact_output_files')
    files = {}; total = 0
    for p in sorted(entries):
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            a = os.fstat(fd)
            need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= CAPS[p.name], 'ordinary_bounded_output')
            total += a.st_size; need(total <= TOTAL, 'aggregate_output_extent')
            pieces = []; remaining = a.st_size
            while remaining:
                block = os.read(fd, min(65536, remaining))
                need(block, 'complete_output'); pieces.append(block); remaining -= len(block)
            need(signature(a) == signature(os.fstat(fd)) == signature(p.lstat()), 'stable_output')
            files[p.name] = b''.join(pieces)
        finally:
            os.close(fd)
    need({p.name for p in root.iterdir()} == set(files), 'final_output_membership')
    return files


def execute_program(program, input_root, output_root, temporary_root, *, seconds=60):
    """Called only inside the container, or with explicitly invented test programs."""
    need(type(program) is bytes and 0 < len(program) <= 131072, 'program_extent')
    program.decode('utf-8')
    need(seconds == 60, 'fixed_candidate_seconds')
    output_root = Path(output_root); temporary_root = Path(temporary_root)
    need(not output_root.exists(), 'fresh_output_directory'); output_root.mkdir(mode=0o700)
    p = temporary_root / 'purkinje-selected-program.py'
    with p.open('xb') as stream:
        stream.write(program); stream.flush(); os.fsync(stream.fileno())
    p.chmod(0o400)
    start = time.monotonic(); deadline = start + seconds
    child = subprocess.Popen([sys.executable, '-I', '-B', str(p), '--input', str(input_root), '--out', str(output_root)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True, cwd=str(output_root))
    selector = selectors.DefaultSelector(); logs = {'stdout': bytearray(), 'stderr': bytearray()}
    try:
        for name, pipe in (('stdout', child.stdout), ('stderr', child.stderr)):
            os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map() or child.poll() is None:
            need(time.monotonic() < deadline, 'candidate_time_limit')
            for key, _ in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                raw = os.read(key.fileobj.fileno(), min(65536, LOG_CAP - len(logs[key.data]) + 1))
                if not raw:
                    selector.unregister(key.fileobj); continue
                need(len(logs[key.data]) + len(raw) <= LOG_CAP, 'candidate_log_limit')
                logs[key.data].extend(raw)
        need(child.wait(timeout=max(.001, deadline - time.monotonic())) == 0, 'candidate_nonzero')
        files = capture_files(output_root)
        need(time.monotonic() < deadline + 10, 'candidate_capture_time_limit')
        return files
    finally:
        if child.poll() is None:
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait(timeout=2)
        selector.close(); child.stdout.close(); child.stderr.close()


def run(program):
    files = execute_program(program, '/input', '/work/output', '/tmp')
    wire = {'schema': 'purkinje-program-files/v1', 'files': {
        name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
               'base64': base64.b64encode(raw).decode('ascii')}
        for name, raw in sorted(files.items())}}
    body = (json.dumps(wire, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(body) <= 12 * 1024 * 1024, 'wire_extent')
    sys.stdout.buffer.write(body); sys.stdout.buffer.flush()

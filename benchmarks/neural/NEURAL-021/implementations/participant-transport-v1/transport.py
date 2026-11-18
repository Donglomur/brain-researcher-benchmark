"""Bounded N021 text/vector participant messages and trusted replay handoff.

The pipe client is NOT a filesystem sandbox or a no-tools enforcement mechanism.
Source/packets stay in the operator API; local clients retain host capabilities.
No private target loader, score feedback, scientific fit or model API is present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
import struct
import subprocess
import sys
import time
import types

SCHEMA = 'neural021_participant_messages_v1'
ADMISSION = {'state': 'unadmitted', 'artifacts_alone_admissible': False,
             'requires': 'Independent controller retains exit zero within the whole-operation deadline '
                         'and hashes every output, including lifecycle.jsonl, before handoff.'}
MAX_REQUEST = 8192
MAX_RESPONSE = 512 * 1024
MAX_MESSAGES = 2048 + 92 + 1
MAX_RECEIVED = MAX_MESSAGES * (MAX_REQUEST + 4)
MAX_SENT = (MAX_MESSAGES + 1) * (MAX_RESPONSE + 4)
MAX_STDERR = 16384
MAX_SIDECAR = 2 * 1024**2
GRADE_PIN = {'bytes': 13817, 'sha256': 'f66b0c331a098af06172dd54793f04ac4425de1f7e8923120218cc68c57a3fc5'}
HERE = Path(__file__).resolve().parent


class Refusal(ValueError):
    pass


class SignalTermination(Exception):
    def __init__(self, signum):
        self.signum = signum
        super().__init__('operator termination signal')


def need(value, message):
    if not value:
        raise Refusal(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def strict_json(body):
    need(type(body) is bytes and 0 < len(body) <= MAX_REQUEST, 'bounded nonempty JSON request')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate request key')
            result[key] = value
        return result
    def integer(text):
        need(len(text) <= 24, 'bounded integer token')
        return int(text)
    def number(text):
        need(len(text) <= 64, 'bounded float token')
        value = float(text)
        need(math.isfinite(value), 'finite request numbers')
        return value
    def constant(_):
        raise Refusal('nonfinite JSON constant')
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                          parse_int=integer, parse_float=number, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise Refusal('malformed request JSON') from error


def load_sources(implementations_root=None):
    """Operator-selected location, with exact pinned existing code bodies."""
    root = Path(implementations_root or HERE.parent).absolute()
    need('..' not in root.parts and all(not p.is_symlink() for p in (root, *root.parents)),
         'ordinary implementation root')
    path = root / 'observation-grade-v1/grade.py'
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'ordinary replay source ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == GRADE_PIN['bytes'], 'ordinary original replay extent')
        body = stream.read(GRADE_PIN['bytes'] + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(identity(before) == identity(after) == identity(path.stat()) and pin(body) == GRADE_PIN,
         'original replay source changed')
    module = types.ModuleType('neural021_transport_grade')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module, module.load_sources()


def frame(body, cap):
    need(type(body) is bytes and 0 < len(body) <= cap, 'frame body exceeds cap or is empty')
    return struct.pack('!I', len(body)) + body


def read_frame(channel):
    header = channel.read_exact(4)
    need(type(header) is bytes and len(header) == 4, 'incomplete frame header')
    length = struct.unpack('!I', header)[0]
    need(0 < length <= MAX_REQUEST, 'request frame extent refused before body read')
    body = channel.read_exact(length)
    need(type(body) is bytes and len(body) == length, 'incomplete frame body')
    return body


class Exchange:
    """Trusted message dispatcher. It is not itself an untrusted Python API."""
    def __init__(self, sources, packet, mode):
        delivery = sources['delivery']
        need(type(packet) is delivery.Packet and len(packet.training) == 272
             and len(packet.queries) == 92, 'complete original packet')
        need(mode in delivery.MODES, 'explicit existing observation mode')
        self.session = delivery.Session(packet, mode)
        self.packet, self.mode = packet, mode
        self.rows, self.received, self.sent = [], 0, 0
        self.finished = False
        self.pending = None

    def hello(self):
        # No arrays, Python objects, code paths, private target identities or scores.
        return encode({'schema': SCHEMA, 'type': 'hello', 'mode': self.mode,
            'calibration_count': 272, 'queries': [
                {'trial_id': row.trial_id, 'condition': row.condition} for row in self.packet.queries],
            'response_shape': [30, 2], 'velocity_units': 'm/s',
            'observation_format': 'image/svg+xml as UTF-8 text/vector content',
            'calibration_policy': 'all 272 available; views are optional and recorded',
            'max_views': 2048, 'max_request_bytes': MAX_REQUEST, 'max_response_bytes': MAX_RESPONSE,
            'actions': ['calibration', 'view', 'answer', 'finish'] + (['crop'] if self.mode == 'typed_viewer' else []),
            'capability_boundary': 'Message allowlist only; local pipe clients are not OS-isolated or proven tool-free.'})

    def dispatch(self, body):
        need(not self.finished and len(self.rows) < MAX_MESSAGES, 'sealed or exhausted message session')
        value = strict_json(body)
        need(type(value) is dict and type(value.get('seq')) is int
             and value['seq'] == len(self.rows), 'exact monotone request sequence')
        operation = value.get('op')
        fields = {
            'calibration': {'index'}, 'view': {'trial_id'},
            'crop': {'trial_id', 'unit_start', 'unit_stop', 'bin_start', 'bin_stop'},
            'answer': {'trial_id', 'velocity_m_s'}, 'finish': set(),
        }
        need(type(operation) is str and operation in fields
             and set(value) == {'seq', 'op'} | fields[operation], 'exact allowed action fields')
        if operation == 'calibration':
            rendered = self.session.calibration(value['index'])
            answer = {'type': 'svg', 'media_type': 'image/svg+xml', 'svg': rendered}
        elif operation in ('view', 'crop'):
            need(operation != 'crop' or self.mode == 'typed_viewer', 'crops require typed viewer')
            viewport = {key: value[key] for key in fields[operation] - {'trial_id'}}
            rendered = self.session.view(value['trial_id'], **viewport)
            answer = {'type': 'svg', 'media_type': 'image/svg+xml', 'svg': rendered}
        elif operation == 'answer':
            answer = {'type': 'answer_ack', **self.session.answer(value['trial_id'], value['velocity_m_s'])}
        else:
            self.pending = self.session.finish()
            self.finished = True
            answer = {'type': 'complete', 'queries': 92, 'grading_pending': True}
        response = encode({'seq': value['seq'], **answer})
        need(len(response) <= MAX_RESPONSE, 'response cap exceeded')
        row = {'seq': value['seq'], 'op': operation, 'request': pin(body), 'response': pin(response),
               'previous_sha256': self.rows[-1]['sha256'] if self.rows else '0' * 64}
        row['sha256'] = pin(encode(row))['sha256']
        self.rows.append(row)
        return response

    def run(self, channel):
        hello = self.hello()
        channel.write(frame(hello, MAX_RESPONSE))
        self.sent += 4 + len(hello)
        while not self.finished:
            body = read_frame(channel)
            self.received += 4 + len(body)
            need(self.received <= MAX_RECEIVED, 'cumulative request cap')
            response = self.dispatch(body)
            self.sent += 4 + len(response)
            need(self.sent <= MAX_SENT, 'cumulative response cap')
            channel.write(frame(response, MAX_RESPONSE))
        return {'schema': 'neural021_transport_exchange_v1', 'mode': self.mode,
                'hello': pin(hello), 'messages': len(self.rows), 'frames': self.rows,
                'request_wire_bytes': self.received, 'response_wire_bytes': self.sent,
                'observation_sha256': self.packet.observation_sha256,
                'exchange_alone_is_not_admission': True}


class PipeChannel:
    """Bounded pipe I/O with deadline and stderr drainage; not an OS sandbox."""
    def __init__(self, process, deadline):
        self.process, self.deadline = process, deadline
        self.infd, self.outfd, self.errfd = process.stdin.fileno(), process.stdout.fileno(), process.stderr.fileno()
        for fd in (self.infd, self.outfd, self.errfd):
            os.set_blocking(fd, False)
        self.stderr_bytes = 0
        self.stderr_hash = hashlib.sha256()
        self.err_open = True

    def ready(self, writing=False):
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, 'participant deadline exceeded')
        readable, writable, _ = select.select(
            [self.outfd] + ([self.errfd] if self.err_open else []),
            [self.infd] if writing else [], [], min(remaining, .2))
        if self.err_open and self.errfd in readable:
            chunk = os.read(self.errfd, min(4096, MAX_STDERR + 1 - self.stderr_bytes))
            if not chunk:
                self.err_open = False
            self.stderr_bytes += len(chunk)
            need(self.stderr_bytes <= MAX_STDERR, 'participant stderr cap')
            self.stderr_hash.update(chunk)
        return self.outfd in readable, self.infd in writable

    def read_exact(self, size):
        output = bytearray()
        while len(output) < size:
            available, _ = self.ready()
            if available:
                chunk = os.read(self.outfd, size - len(output))
                need(bool(chunk), 'participant EOF before complete frame')
                output.extend(chunk)
        return bytes(output)

    def write(self, body):
        position = 0
        while position < len(body):
            premature, available = self.ready(writing=True)
            need(not premature, 'client must await each complete response; no pipelining')
            if available:
                sent = os.write(self.infd, body[position:position + 65536])
                need(sent > 0, 'participant input pipe closed')
                position += sent

    def close_success(self):
        self.process.stdin.close()
        out_open = True
        while out_open or self.err_open or self.process.poll() is None:
            remaining = self.deadline - time.monotonic()
            need(remaining > 0, 'participant failed to close after finish')
            fds = ([self.outfd] if out_open else []) + ([self.errfd] if self.err_open else [])
            readable, _, _ = select.select(fds, [], [], min(remaining, .02))
            if self.outfd in readable:
                extra = os.read(self.outfd, 1)
                need(not extra, 'trailing participant bytes after finish')
                out_open = False
            if self.err_open and self.errfd in readable:
                chunk = os.read(self.errfd, min(4096, MAX_STDERR + 1 - self.stderr_bytes))
                self.stderr_bytes += len(chunk)
                need(self.stderr_bytes <= MAX_STDERR, 'participant stderr cap')
                self.stderr_hash.update(chunk)
                self.err_open = bool(chunk)
        need(self.process.returncode == 0, 'participant exit must be zero')
        need(not group_exists(self.process.pid), 'owned participant group still exists')
        return {'leader_exit_code': 0, 'stdout_eof': True, 'stderr_eof': True,
                'owned_process_group_absent': True, 'group_id': self.process.pid,
                'stderr': {'bytes': self.stderr_bytes, 'sha256': self.stderr_hash.hexdigest()},
                'scope': 'Observed leader/pipes/owned group only; escaped descendants and external activity are not excluded.'}


def group_exists(group):
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    return True


def cleanup(process, group_already_closed=False):
    """Only the newly created owned group; no unrelated process signals."""
    if not group_already_closed:
        for sig, wait in ((signal.SIGTERM, .2), (signal.SIGKILL, .3)):
            try:
                if group_exists(process.pid):
                    os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            until = time.monotonic() + wait
            while time.monotonic() < until:
                process.poll()
                if not group_exists(process.pid):
                    break
                time.sleep(.01)
    process.poll()
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream and not stream.closed:
            stream.close()
    return {'leader_reaped': process.poll() is not None, 'leader_exit_code': process.returncode,
            'owned_process_group_absent': True if group_already_closed else not group_exists(process.pid),
            'absence_basis': 'prior_successful_closure' if group_already_closed else 'post_cleanup_probe',
            'group_id': process.pid}


def run_participant(grade, sources, packet, mode, argv, cwd, timeout_seconds, *, observer):
    need(type(argv) is list and 1 <= len(argv) <= 32
         and all(type(arg) is str and 0 < len(arg.encode()) <= 4096 and '\0' not in arg for arg in argv)
         and Path(argv[0]).is_absolute(), 'explicit bounded operator participant command')
    need(type(timeout_seconds) in (int, float) and 1 <= timeout_seconds <= 3600,
         'explicit bounded operator deadline')
    need(callable(observer), 'operator-owned durable lifecycle observer required')
    cwd = grade.ordinary_path(cwd)
    need(cwd.is_dir(), 'existing ordinary participant working directory')
    environment = {'PATH': '/usr/bin:/bin', 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                   **{key: '1' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                                          'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')}}
    exchange = Exchange(sources, packet, mode)  # Validate before creating a child.
    started = time.monotonic()
    deadline = started + timeout_seconds
    process = None
    group_already_closed = False
    protected_phase, pending_signal = True, None
    previous_handlers = {}
    def interrupted(signum, _frame):
        nonlocal pending_signal
        pending_signal = signum
        # Finish PID registration/cleanup before honoring catchable interruption.
        # SIGKILL and OS failure still need external supervision; neither is hidden.
        if not protected_phase:
            raise SignalTermination(signum)
    try:
        for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupted)
        observer({'phase': 'before_spawn', 'command_sha256': pin(encode(argv))['sha256']})
        process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        observer({'phase': 'spawned', 'leader_pid': process.pid, 'owned_process_group': process.pid})
        protected_phase = False
        if pending_signal is not None:
            raise SignalTermination(pending_signal)
        channel = PipeChannel(process, deadline)
        transcript = exchange.run(channel)
        closure = channel.close_success()
        group_already_closed = True
        observer({'phase': 'owned_participant_closed', **closure})
        # This first replay is after clean EOF, reaped leader and group-absence observation.
        submission, visual_receipt = exchange.pending
        replay = grade.replay(sources, packet, mode, submission, visual_receipt)
        need(time.monotonic() <= deadline, 'deadline exceeded during replay')
        observer({'phase': 'replay_complete', 'submission': pin(submission), 'receipt': pin(visual_receipt)})
        receipt = {'schema': 'neural021_participant_transport_receipt_v1', 'mode': mode,
                   'status': 'closed_owned_process_and_complete_original_replay',
                   'admission': dict(ADMISSION),
                   'exchange': transcript, 'closure': closure,
                   'participant_command_sha256': pin(encode(argv))['sha256'],
                   'wall_seconds_through_replay': time.monotonic() - started,
                   'submission': pin(submission), 'visual_receipt': pin(visual_receipt),
                   'replay': pin(encode(replay)), 'source_replay': GRADE_PIN,
                   'runtime_qualified': False, 'scientific_qualified': False, 'submission_ready': False,
                   'isolation_qualified': False, 'raster_display_qualified': False,
                   'note': 'Trusted operator lineage only. Pipe clients may compute or read their host filesystem. '
                           'SVG text/vector transport does not prove native understanding, raster viewing or no-tools use.'}
        need(len(encode(receipt)) <= MAX_SIDECAR, 'bounded transport receipt')
        return submission, visual_receipt, encode(replay), encode(receipt)
    finally:
        protected_phase = True
        try:
            if process is not None:
                observed = cleanup(process, group_already_closed)
                observer({'phase': 'cleanup_observed', **observed})
                need(observed['leader_reaped'] and observed['owned_process_group_absent'],
                     'owned cleanup incomplete; durable lifecycle record retained')
        finally:
            for signum, previous in previous_handlers.items():
                signal.signal(signum, previous)
        if pending_signal is not None:
            raise SignalTermination(pending_signal)


def operator_collect(public_root, mode, argv, participant_cwd, output_root,
                     timeout_seconds=180, implementations_root=None):
    need(type(timeout_seconds) in (int, float) and 1 <= timeout_seconds <= 3600,
         'bounded whole-operation deadline')
    deadline = time.monotonic() + timeout_seconds
    grade, sources = load_sources(implementations_root)
    public_root, output_root = grade.ordinary_path(public_root), grade.ordinary_path(output_root)
    impl = grade.IMPLEMENTATIONS
    need(public_root.is_dir() and output_root.parent.is_dir() and not os.path.lexists(output_root)
         and not output_root.is_relative_to(public_root) and not output_root.is_relative_to(impl),
         'fresh separate operator output directory')
    import numpy as np  # Existing dependency only; no installation or private targets.
    packet = sources['delivery'].load_public(public_root, np)
    need(time.monotonic() + 1 <= deadline, 'deadline exhausted before participant')
    output_root.mkdir(mode=0o700)
    lifecycle_path = output_root / 'lifecycle.jsonl'
    lifecycle_bytes = 0
    with lifecycle_path.open('xb') as lifecycle:
        os.chmod(lifecycle_path, 0o600)
        def observer(event):
            nonlocal lifecycle_bytes
            body = encode(event)
            need(lifecycle_bytes + len(body) <= 16384, 'bounded lifecycle journal')
            lifecycle.write(body)
            lifecycle.flush()
            os.fsync(lifecycle.fileno())
            lifecycle_bytes += len(body)
        result = run_participant(grade, sources, packet, mode, argv, participant_cwd,
                                 deadline - time.monotonic(), observer=observer)
    need(time.monotonic() <= deadline, 'deadline exceeded after participant cleanup')
    caps = (grade.MAX_JSON, grade.MAX_JSON, grade.MAX_RESULT, MAX_SIDECAR)
    names = ('submission.json', 'visual_receipt.json', 'replay.json', 'transport.json')
    need(all(len(body) <= cap for body, cap in zip(result, caps)), 'bounded complete output set')
    # Completion/transport record is written last. Partial output is not admissible.
    for name, body in zip(names, result):
        need(time.monotonic() <= deadline, 'deadline exceeded during artifact writing')
        with (output_root / name).open('xb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    need(time.monotonic() <= deadline, 'deadline exceeded at final acceptance')
    return {'status': 'complete_transport_and_source_replay', 'mode': mode, 'queries': 92,
            'output_bytes': sum(map(len, result)) + lifecycle_bytes, 'private_target_reads': 0,
            'admission': dict(ADMISSION)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', required=True)
    parser.add_argument('--mode', choices=('direct_observation', 'typed_viewer'), required=True)
    parser.add_argument('--participant-cwd', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--timeout-seconds', type=int, default=180)
    parser.add_argument('--implementations-root')
    parser.add_argument('participant', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.participant[1:] if args.participant[:1] == ['--'] else args.participant
    try:
        result = operator_collect(args.public_root, args.mode, command, args.participant_cwd,
                                  args.output_root, args.timeout_seconds, args.implementations_root)
    except SignalTermination as error:
        print(json.dumps({'status': 'interrupted_transport', 'signal': error.signum,
                          'admissible_handoff': False, 'automatic_retry': False}), file=sys.stderr)
        return 128 + error.signum
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        print('{"status":"failed_transport","admissible_handoff":false,"automatic_retry":false}', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

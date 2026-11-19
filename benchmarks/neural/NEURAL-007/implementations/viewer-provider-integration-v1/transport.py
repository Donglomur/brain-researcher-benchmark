"""Bounded whole-person sleep image/action transport; no model or score execution."""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = Path(globals().get('DEPENDENCY_ROOT', HERE.parents[4]))
VIEWER = ROOT / 'benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1'
PREFIX = struct.Struct('!II')
HEADER_MAX = 32768
PNG_MAX = 4 * 1024**2
MAX_REQUEST = 8192
MAX_CLIENT = 256 * 1024
MAX_JOURNAL = 128 * 1024**2
RESERVE = 4096


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def ordinary(path, cap):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Linked path refused')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = os.fdopen(fd, 'rb')
    try:
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= cap,
             'Bounded single-link regular file required')
        return stream, info
    except BaseException:
        stream.close()
        raise


def identity(info):
    return tuple(getattr(info, key) for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def read_body(path, cap):
    stream, before = ordinary(path, cap)
    with stream:
        body = stream.read(cap + 1)
        need(len(body) <= cap and identity(before) == identity(os.fstat(stream.fileno())) ==
             identity(Path(path).stat()), 'File changed during capture')
    return body


def load_viewer():
    bindings = decode(read_body(HERE / 'SOURCE_BINDINGS.json', 65536))
    expected = {f'benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/{name}'
                for name in ('viewer.py', 'render.py', 'SOURCE_BINDINGS.json', 'SOURCE_FACTS.json')}
    expected |= {'benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/raster.py',
                 'benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/vendor/candidate_adapter.py'}
    need(set(bindings) == {'schema', 'members'} and bindings['schema'] == 'sleep-viewer-transport-dependencies/v1'
         and set(bindings['members']) == expected, 'Exact sleep source closure required')
    bodies = {}
    for relative, pin in bindings['members'].items():
        need(set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int and 0 < pin['bytes'] <= 256 * 1024,
             'Invalid source pin')
        body = read_body(ROOT / relative, 256 * 1024)
        need(len(body) == pin['bytes'] and digest(body) == pin['sha256'], 'Sleep dependency mismatch')
        bodies[relative] = body
    path = VIEWER / 'viewer.py'
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('sleep_transport_viewer', loader=None))
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(bodies[str(path.relative_to(ROOT))], str(path), 'exec'), module.__dict__)
    return module


v = load_viewer()


def load_process_owner():
    # Trusted helper only; the participant never receives this source or path.
    path = Path(globals().get('DEPENDENCY_ROOT', ROOT)) / 'benchmarks/shared/viewer-process-ownership-v1/owned_exit.py'
    body = read_body(path, 65536)
    if len(body) != 8088 or hashlib.sha256(body).hexdigest() != 'd1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426':
        raise ValueError('Process ownership helper source mismatch')
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('viewer_owned_exit', loader=None))
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


owner = load_process_owner()


def source_identity():
    return {name: {'bytes': len(body), 'sha256': digest(body)}
            for name in ('transport.py', 'SOURCE_BINDINGS.json')
            for body in (read_body(HERE / name, 256 * 1024),)}


@dataclass(frozen=True)
class Limits:
    max_actions: int
    max_images: int
    max_output_bytes: int
    wall_seconds: float

    def validate(self, epochs):
        need(type(epochs) is int and epochs > 0, 'Positive epoch count required')
        need(type(self.max_actions) is int and 2 * epochs + 1 <= self.max_actions <= 100000,
             'Action budget must cover the whole person within 100000 actions')
        need(type(self.max_images) is int and epochs <= self.max_images <= self.max_actions,
             'Image budget must cover every complete target')
        need(type(self.max_output_bytes) is int and PNG_MAX + HEADER_MAX + RESERVE <= self.max_output_bytes <= 4 * 1024**3,
             'Explicit output budget must fit a maximum frame and be at most 4 GiB')
        need(type(self.wall_seconds) in (int, float) and math.isfinite(self.wall_seconds)
             and 0 < self.wall_seconds <= 86400, 'Finite positive wall budget within one day required')


class WireFailure(Exception):
    def __init__(self, reason, captured=b''):
        super().__init__(reason)
        self.reason, self.captured = reason, captured


def wire(header, image=b''):
    body = encode(header)
    need(0 < len(body) <= HEADER_MAX and len(image) <= PNG_MAX, 'Response exceeds framing bound')
    return PREFIX.pack(len(body), len(image)) + body + image


def unpack(raw, inbound=False):
    need(len(raw) >= PREFIX.size, 'Missing frame prefix')
    hs, ps = PREFIX.unpack(raw[:PREFIX.size])
    need(0 < hs <= (MAX_REQUEST if inbound else HEADER_MAX) and
         (ps == 0 if inbound else 0 <= ps <= PNG_MAX), 'Invalid frame lengths')
    need(len(raw) == PREFIX.size + hs + ps, 'Frame length mismatch')
    return decode(raw[PREFIX.size:PREFIX.size + hs]), raw[PREFIX.size + hs:]


def wait_fd(fd, event, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WireFailure('deadline')
    with selectors.DefaultSelector() as selector:
        selector.register(fd, event)
        if not selector.select(remaining):
            raise WireFailure('deadline')


def read_frame(fd, deadline):
    captured = bytearray()
    def read_to(size):
        while len(captured) < size:
            try:
                wait_fd(fd, selectors.EVENT_READ, deadline)
                body = os.read(fd, size - len(captured))
            except BlockingIOError:
                continue
            except WireFailure as exc:
                raise WireFailure(exc.reason, bytes(captured)) from None
            if not body:
                raise WireFailure('transport_eof', bytes(captured))
            captured.extend(body)
    read_to(PREFIX.size)
    hs, ps = PREFIX.unpack(captured)
    if not 0 < hs <= MAX_REQUEST or ps:
        raise WireFailure('invalid_frame_length', bytes(captured))
    read_to(PREFIX.size + hs)
    return bytes(captured)


def write_frame(fd, body, deadline):
    sent = 0
    try:
        while sent < len(body):
            wait_fd(fd, selectors.EVENT_WRITE, deadline)
            try:
                count = os.write(fd, body[sent:])
                if count == 0:
                    raise WireFailure('output_not_delivered')
                sent += count
            except BlockingIOError:
                continue
    except (OSError, WireFailure):
        raise WireFailure('output_not_delivered', body[:sent]) from None


ACTIONS = {
    'inspect': {}, 'epoch': {'index': 'integer epoch ordinal within this person'},
    'window': {'start_sample': 'integer', 'stop_sample': 'integer; half-open 100..6000 samples'},
    'gain': {'microvolts_per_division': list(v.GAINS)},
    'channels': {'channels': list(v.CHANNELS)},
    'respond': {'epoch_id': 'current target ID', 'probabilities': 'five finite probabilities in W,N1,N2,N3,R order'},
    'finish': {},
}


def ready_header(packet, limits, episode):
    return {'kind': 'instructions', 'episode_id': episode, 'mode': v.MODE, 'case_id': packet.case,
            'epochs': packet.epochs, 'prompt': v.PROMPT, 'actions': ACTIONS,
            'limits': dict(asdict(limits), max_request_bytes=MAX_REQUEST, max_image_bytes=PNG_MAX),
            'instructions': 'Only typed actions are accepted. PNG frame parts are image content, not text. '
                            'Each epoch accepts its first valid response only. Finish requires every epoch. '
                            'An invalid request fails this session; no labels or scoring feedback are supplied.'}


def projection(response):
    kind = response.get('kind')
    if kind == 'view':
        need(set(response) == {'kind', 'mode', 'epoch_id', 'state', 'clock_features', 'sample_rate_hz',
                               'signal_units', 'display_units', 'image'}, 'Unexpected viewer fields')
        need(set(response['state']) == {'epoch', 'start_sample', 'stop_sample', 'gain_uv', 'channels'} and
             set(response['clock_features']) == set(v.CLOCK) and
             set(response['image']) == {'mime_type', 'base64'}, 'Unexpected nested viewer fields')
        need(response['image']['mime_type'] == 'image/png', 'PNG image required')
        png = base64.b64decode(response['image']['base64'], validate=True)
        need(png.startswith(b'\x89PNG\r\n\x1a\n') and len(png) <= PNG_MAX, 'Bounded PNG required')
        header = {key: value for key, value in response.items() if key != 'image'}
        header['image'] = {'mime_type': 'image/png', 'bytes': len(png)}
        return header, png
    fields = {'response_accepted': {'kind', 'epoch_id', 'completed_epochs'},
              'complete': {'kind', 'case_id', 'epochs'}}
    need(kind in fields and set(response) == fields[kind], 'Unexpected response fields')
    return dict(response), b''


def sandbox_profile(client):
    need(sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').is_file(), 'macOS sandbox-exec required')
    quoted = json.dumps(str(Path(client).resolve()))
    return ('(version 1) (deny default) (deny sysctl* process-info* network* process-fork) '
            '(allow process-info* (target self)) (allow process-exec) (allow file-read-metadata) '
            '(allow sysctl-read (sysctl-name "kern.ostype") (sysctl-name "kern.osrelease") '
            '(sysctl-name "kern.version") (sysctl-name "kern.hostname") (sysctl-name "hw.machine")) '
            '(allow file-read-data (literal "/") (subpath "/System") (subpath "/usr") '
            '(subpath "/Library/Frameworks") (literal "/dev/null") (literal "/dev/urandom") '
            '(literal "/dev/random") (literal ' + quoted + '))')


class Journal:
    def __init__(self, path):
        path.mkdir(mode=0o700)
        self.raw = (path / 'wire.bin').open('xb')
        self.log = (path / 'journal.jsonl').open('xb')
        self.sequence, self.offset, self.previous = 0, 0, '0' * 64

    def record(self, direction, body, complete=True):
        self.raw.write(body)
        self.raw.flush()
        row = {'sequence': self.sequence, 'direction': direction, 'offset': self.offset,
               'bytes': len(body), 'sha256': digest(body), 'complete': complete, 'previous': self.previous}
        encoded = encode(row)
        self.log.write(encoded)
        self.log.flush()
        self.previous = digest(encoded)
        self.sequence += 1
        self.offset += len(body)

    def close(self):
        self.raw.close()
        self.log.close()


def viewer_manifest(packet, limits):
    return {'schema': 'sleep-whole-person-viewer-session/v1', 'mode': v.MODE, 'case_id': packet.case,
            'epochs': packet.epochs, 'max_actions': limits.max_actions, 'inputs': packet.pins,
            'source': v.source_identity(), 'runtime': v.runtime_identity(), 'prompt': v.PROMPT}


def run_person(packet, output, client, python=sys.executable, sandbox='macos', limits=None, client_launcher=None):
    owner.preflight()
    need(isinstance(limits, Limits), 'Explicit frozen Limits required')
    limits.validate(packet.epochs)
    need(packet.case in v.CASES and packet.epochs == v.CASES[packet.case], 'Complete declared person required')
    need(sandbox in ('macos', 'protocol_only'), 'Unknown sandbox mode')
    client_body = read_body(client, MAX_CLIENT)
    selected_python = Path(python).absolute()
    python = selected_python.resolve(strict=True)
    need(python.is_file(), 'Existing interpreter required')
    if client_launcher is not None:
        need(sandbox == 'protocol_only', 'Trusted launcher requires the operator profile')
        # Preserve the explicitly selected venv entrypoint; the original default
        # participant path still resolves and applies its original sandbox rules.
        python = selected_python
    if sandbox == 'macos':
        need(any(python.is_relative_to(Path(base)) for base in ('/System', '/usr', '/Library/Frameworks')),
             'macOS client requires interpreter in admitted system runtime roots')
    output = v.fresh_output(output)
    viewer_dir = output / 'viewer'
    viewer_dir.mkdir(mode=0o700)
    captured_client = output / 'client.py'
    v.write_new(captured_client, client_body)
    profile = sandbox_profile(captured_client) if sandbox == 'macos' else None
    episode = uuid.uuid4().hex
    boundary = {'schema': 'sleep-viewer-transport/v1', 'episode_id': episode, 'case_id': packet.case,
                'epochs': packet.epochs, 'mode': v.MODE, 'limits': asdict(limits), 'sandbox': sandbox,
                'client_sha256': digest(client_body), 'python': str(python), 'source': source_identity(),
                'profile_sha256': digest(profile.encode()) if profile else None,
                'fresh_process_per_person': True, 'provider_context_qualified': False,
                'provider_image_capacity_qualified': False, 'scientific_qualification': False}
    v.write_new(output / 'BOUNDARY.json', encode(boundary))
    if profile:
        v.write_new(output / 'sandbox.sb', profile.encode())
    journal = Journal(output / 'transport')
    child, session, action_log = None, None, None
    observer, cleanup = None, None
    reason, forced_stop, images, outbound = None, False, 0, 0
    started = time.monotonic()
    deadline = started + limits.wall_seconds
    chain, exit_code, group_cleanup = None, None, None
    def send(header, png=b''):
        nonlocal images, outbound
        body = wire(header, png)
        need(outbound + len(body) <= limits.max_output_bytes, 'Output byte budget exhausted')
        try:
            write_frame(child.stdin.fileno(), body, deadline)
        except WireFailure as exc:
            journal.record('out', exc.captured, False)
            raise
        journal.record('out', body)
        outbound += len(body)
        images += bool(png)
    try:
        raster, _, renderer = v.dependencies()
        session = v.Session(packet, limits.max_actions, raster, renderer)
        manifest = viewer_manifest(packet, limits)
        v.write_new(viewer_dir / 'manifest.json', encode(manifest))
        chain = digest(encode(manifest))
        action_log = (viewer_dir / 'actions.jsonl').open('xb')
        with tempfile.TemporaryDirectory(prefix='sleep-viewer-client-') as cwd:
            command = [str(python), '-I', '-S', '-B', str(captured_client)]
            if profile:
                command = ['/usr/bin/sandbox-exec', '-p', profile] + command
            if client_launcher is None:
                child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, cwd=cwd, env={'LANG': 'C', 'LC_ALL': 'C'},
                                         close_fds=True, start_new_session=True)
            else:
                # Trusted operator only, preserving the default participant boundary.
                need(sandbox == 'protocol_only', 'Trusted provider launcher is not the participant sandbox')
                child = client_launcher(command, cwd)
            observer = owner.ExitObserver(child)
            os.set_blocking(child.stdin.fileno(), False)
            os.set_blocking(child.stdout.fileno(), False)
            send(ready_header(packet, limits, episode))
            while not session.finished:
                try:
                    raw = read_frame(child.stdout.fileno(), deadline)
                except WireFailure as exc:
                    journal.record('in', exc.captured, False)
                    raise
                journal.record('in', raw)
                request, _ = unpack(raw, inbound=True)
                needs_image = isinstance(request, dict) and request.get('action') in ('inspect', 'epoch', 'window', 'gain', 'channels')
                if needs_image:
                    need(images < limits.max_images, 'Image budget exhausted')
                    need(outbound + PNG_MAX + HEADER_MAX + PREFIX.size + RESERVE <= limits.max_output_bytes,
                         'Maximum next image exceeds remaining output budget')
                response = session.handle(request)
                row = {'ordinal': session.actions, 'previous': chain, 'request': request,
                       'response_sha256': digest(encode(response))}
                body = encode(row)
                action_log.write(body)
                action_log.flush()
                chain = digest(body)
                send(*projection(response))
            child.stdin.close()
            remaining = min(2.0, deadline - time.monotonic())
            need(remaining > 0, 'Deadline reached before clean client exit')
            if not observer.wait(time.monotonic() + remaining):
                raise WireFailure('client_did_not_exit')

    except Exception as exc:
        reason = {'type': type(exc).__name__, 'message': str(exc)[:1000]}
        failure = {'status': 'failed', 'case_id': packet.case, 'reason': reason}
        for folder in (output, viewer_dir):
            try:
                v.write_new(folder / 'failure.json', encode(failure))
            except OSError:
                pass
    finally:
        if child is not None:
            cleanup = owner.stop_and_reap(child, observer, time.monotonic() + 2.0)
            forced_stop = not cleanup['exit_observed_before_stop']
            exit_code = cleanup['returncode']
            group_cleanup = 'absent' if cleanup['group_absence_observed'] else 'unverified'
            if not cleanup['cleanup_complete'] or exit_code != 0 or forced_stop:
                reason = reason or {'type': 'ChildProcessError', 'message': 'Owned client cleanup or successful exit unverified'}
            for stream in (child.stdin, child.stdout):
                if stream and not stream.closed:
                    stream.close()
        if action_log:
            action_log.close()
        journal.close()
    if reason is not None:
        for folder in (output, viewer_dir):
            if not os.path.lexists(folder / 'failure.json'):
                v.write_new(folder / 'failure.json', encode({'status': 'failed', 'case_id': packet.case, 'reason': reason}))
    else:
        v.write_new(viewer_dir / 'completion.json', encode({'actions': session.actions, 'last_sha256': chain,
                    'case_id': packet.case, 'epochs': packet.epochs, 'mode': v.MODE}))
    result = {'schema': 'sleep-viewer-transport-result/v1', 'status': 'complete_unscored' if reason is None else 'failed',
              'case_id': packet.case, 'episode_id': episode, 'actions': session.actions if session else 0,
              'images': images, 'output_bytes': outbound, 'wire_bytes': journal.offset,
              'wire_records': journal.sequence, 'last_sha256': journal.previous,
              'client_exit_code': exit_code, 'forced_stop': forced_stop,
              'process_group_cleanup': group_cleanup, 'process_ownership': cleanup,
              'wall_seconds': time.monotonic() - started, 'reason': reason,
              'provider_context_qualified': False, 'scientific_qualification': False}
    v.write_new(output / 'RESULT.json', encode(result))
    return result


def audit_transport(path, packet):
    path = v.unlinked(path)
    need(not os.path.lexists(path / 'failure.json'), 'Failed transport cannot be collected')
    boundary = decode(read_body(path / 'BOUNDARY.json', 65536))
    expected_keys = {'schema', 'episode_id', 'case_id', 'epochs', 'mode', 'limits', 'sandbox', 'client_sha256',
                     'python', 'source', 'profile_sha256', 'fresh_process_per_person',
                     'provider_context_qualified', 'provider_image_capacity_qualified', 'scientific_qualification'}
    need(set(boundary) == expected_keys and boundary['schema'] == 'sleep-viewer-transport/v1'
         and boundary['mode'] == v.MODE and boundary['case_id'] == packet.case and boundary['epochs'] == packet.epochs
         and boundary['source'] == source_identity() and boundary['fresh_process_per_person'] is True
         and boundary['provider_context_qualified'] is False and boundary['provider_image_capacity_qualified'] is False
         and boundary['scientific_qualification'] is False, 'Transport/source/person boundary mismatch')
    episode = boundary['episode_id']
    need(type(episode) is str and len(episode) == 32 and all(c in '0123456789abcdef' for c in episode), 'Invalid episode ID')
    need(type(boundary['limits']) is dict and set(boundary['limits']) == set(Limits.__dataclass_fields__), 'Exact limits required')
    limits = Limits(**boundary['limits'])
    limits.validate(packet.epochs)
    need(digest(read_body(path / 'client.py', MAX_CLIENT)) == boundary['client_sha256'], 'Client capture changed')
    sandbox = boundary['sandbox']
    need(sandbox in ('macos', 'protocol_only'), 'Unknown recorded sandbox')
    profile = sandbox_profile(path / 'client.py') if sandbox == 'macos' else None
    need(boundary['profile_sha256'] == (digest(profile.encode()) if profile else None), 'Sandbox profile mismatch')
    if profile:
        need(read_body(path / 'sandbox.sb', 65536) == profile.encode(), 'Sandbox capture changed')
    else:
        need(not os.path.lexists(path / 'sandbox.sb'), 'Unexpected sandbox capture')
    raster, _, renderer = v.dependencies()
    # Preserve the existing viewer's complete source/input/action/answer validator.
    answers, viewer_receipt = v.replay(path / 'viewer', packet, raster, renderer)
    session = v.Session(packet, limits.max_actions, raster, renderer)
    manifest = decode(read_body(path / 'viewer' / 'manifest.json', 65536))
    need(manifest == viewer_manifest(packet, limits), 'Viewer and transport limits differ')
    raw = log = actions = None
    try:
        raw, raw_before = ordinary(path / 'transport' / 'wire.bin', limits.max_output_bytes + limits.max_actions * (MAX_REQUEST + PREFIX.size))
        log, log_before = ordinary(path / 'transport' / 'journal.jsonl', MAX_JOURNAL)
        actions, actions_before = ordinary(path / 'viewer' / 'actions.jsonl', 64 * 1024**2)
    except BaseException:
        for stream in (raw, log, actions):
            if stream is not None:
                stream.close()
        raise
    previous, offset, sequence, images, outbound, pending, action_row = '0' * 64, 0, 0, 0, 0, None, None
    try:
        while True:
            line = log.readline(4097)
            if not line:
                break
            need(0 < len(line) <= 4096 and line.endswith(b'\n'), 'Bounded complete journal line required')
            row = decode(line)
            need(set(row) == {'sequence', 'direction', 'offset', 'bytes', 'sha256', 'complete', 'previous'}
                 and type(row['sequence']) is int and row['sequence'] == sequence and type(row['offset']) is int
                 and row['offset'] == offset and row['previous'] == previous and row['complete'] is True,
                 'Incomplete or reordered transport journal')
            direction = 'out' if sequence % 2 == 0 else 'in'
            need(row['direction'] == direction and type(row['bytes']) is int and
                 PREFIX.size < row['bytes'] <= PREFIX.size + HEADER_MAX + PNG_MAX, 'Invalid transport record')
            body = raw.read(row['bytes'])
            need(len(body) == row['bytes'] and digest(body) == row['sha256'], 'Wire capture changed')
            header, png = unpack(body, inbound=direction == 'in')
            if sequence == 0:
                need(body == wire(ready_header(packet, limits, episode)), 'Initial participant projection changed')
            elif direction == 'in':
                need(not session.finished and session.actions < limits.max_actions, 'Actions after finish or budget')
                action_line = actions.readline(MAX_REQUEST + 1025)
                need(0 < len(action_line) <= MAX_REQUEST + 1024 and action_line.endswith(b'\n'),
                     'Complete bounded viewer action required')
                action_row = decode(action_line)
                need(action_row['ordinal'] == session.actions + 1 and encode(action_row['request']) == encode(header),
                     'Wire request differs from original viewer action')
                pending = header
            else:
                need(pending is not None, 'Missing action before response')
                needs_image = isinstance(pending, dict) and pending.get('action') in ('inspect', 'epoch', 'window', 'gain', 'channels')
                if needs_image:
                    need(images < limits.max_images and outbound + PNG_MAX + HEADER_MAX + PREFIX.size + RESERVE <= limits.max_output_bytes,
                         'Recorded action violated capacity')
                response = session.handle(pending)
                need(digest(encode(response)) == action_row['response_sha256'],
                     'Wire response differs from original viewer action result')
                need(body == wire(*projection(response)), 'Wire response differs from exact viewer result')
                pending = None
            if direction == 'out':
                outbound += len(body)
                images += bool(png)
                need(outbound <= limits.max_output_bytes, 'Recorded output exceeded budget')
            offset += len(body)
            previous, sequence = digest(encode(row)), sequence + 1
            need(sequence <= 2 * limits.max_actions + 1, 'Too many transport records')
        need(raw.read(1) == b'' and actions.read(1) == b'' and pending is None and session.finished and session.answers == answers,
             'Incomplete transport or extra wire data')
        for stream, before, file in ((raw, raw_before, path / 'transport' / 'wire.bin'),
                                     (log, log_before, path / 'transport' / 'journal.jsonl'),
                                     (actions, actions_before, path / 'viewer' / 'actions.jsonl')):
            need(identity(before) == identity(os.fstat(stream.fileno())) == identity(file.stat()), 'Transport evidence changed')
    finally:
        raw.close()
        log.close()
        actions.close()
    result = decode(read_body(path / 'RESULT.json', 16384))
    cleanup = result.get('process_ownership', {})
    need(cleanup.get('cleanup_complete') is True and cleanup.get('leader_unreaped_before_signal') is True and cleanup.get('exit_observed_before_stop') is True and cleanup.get('reaped') is True and cleanup.get('returncode') == 0 and cleanup.get('group_absence_observed') is True, 'Owned cleanup receipt required')
    expected = {'schema': 'sleep-viewer-transport-result/v1', 'status': 'complete_unscored', 'case_id': packet.case,
                'episode_id': episode, 'actions': session.actions, 'images': images, 'output_bytes': outbound,
                'wire_bytes': offset, 'wire_records': sequence, 'last_sha256': previous, 'client_exit_code': 0,
                'forced_stop': False, 'wall_seconds': result.get('wall_seconds'), 'reason': None,
                'process_group_cleanup': 'absent', 'process_ownership': cleanup,
                'provider_context_qualified': False, 'scientific_qualification': False}
    integer_fields = ('actions', 'images', 'output_bytes', 'wire_bytes', 'wire_records', 'client_exit_code')
    need(result == expected and all(type(result[key]) is int for key in integer_fields)
         and result['forced_stop'] is False and type(result['wall_seconds']) in (int, float) and math.isfinite(result['wall_seconds'])
         and 0 <= result['wall_seconds'] <= limits.wall_seconds + 2, 'Incomplete or invalid client result')
    return {'boundary': boundary, 'viewer': viewer_receipt, 'result': result,
            'boundary_sha256': digest(encode(boundary)), 'result_sha256': digest(encode(result))}


def collect(packets, sessions, output):
    need(len(packets) == len(sessions) == len(v.CASES), 'Both complete people required')
    need([p.case for p in packets] == list(v.CASES) and [p.epochs for p in packets] == list(v.CASES.values()),
         'Canonical people and order required')
    paths = [v.unlinked(p) for p in sessions]
    need(len({str(p.resolve()) for p in paths}) == len(v.CASES), 'Distinct person sessions required')
    receipts = {p.case: audit_transport(path, p) for p, path in zip(packets, paths)}
    boundaries = [row['boundary'] for row in receipts.values()]
    shared = ('schema', 'mode', 'limits', 'sandbox', 'client_sha256', 'python', 'source')
    need(all({k: b[k] for k in shared} == {k: boundaries[0][k] for k in shared} for b in boundaries),
         'Mixed participant/limits/source/sandbox conditions')
    need(len({b['episode_id'] for b in boundaries}) == len(v.CASES), 'Fresh person episode identities required')
    # Existing collector reauthenticates raw packets and original complete submission schema.
    args = argparse.Namespace(packets=[p.root for p in packets], sessions=[p / 'viewer' for p in paths], output=output)
    v.collect(args)
    receipt = {'schema': 'sleep-viewer-transport-collection/v1', 'mode': v.MODE, 'epochs': sum(v.CASES.values()),
               'status': 'complete_unscored', 'sessions': receipts, 'source': source_identity(),
               'provider_context_qualified': False, 'scientific_qualification': False,
               'scope': 'Complete local image/action transport and original validator only; not model interpretation or protected evaluation.'}
    v.write_new(Path(output) / 'TRANSPORT_COMPLETE.json', encode(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('person')
    run.add_argument('--case', choices=v.CASES, required=True)
    run.add_argument('--packet', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--client', type=Path, required=True)
    run.add_argument('--python', type=Path, required=True)
    run.add_argument('--sandbox', choices=('macos', 'protocol_only'), required=True)
    run.add_argument('--max-actions', type=int, required=True)
    run.add_argument('--max-images', type=int, required=True)
    run.add_argument('--max-output-bytes', type=int, required=True)
    run.add_argument('--wall-seconds', type=float, required=True)
    gather = sub.add_parser('collect')
    gather.add_argument('--packets', nargs=2, type=Path, required=True)
    gather.add_argument('--sessions', nargs=2, type=Path, required=True)
    gather.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    packets = []
    try:
        if args.command == 'person':
            packet = v.Packet(args.packet, args.case)
            packets.append(packet)
            result = run_person(packet, args.output, args.client, args.python, args.sandbox,
                                Limits(args.max_actions, args.max_images, args.max_output_bytes, args.wall_seconds))
            return 0 if result['status'] == 'complete_unscored' else 2
        for case, path in zip(v.CASES, args.packets):
            packets.append(v.Packet(path, case))
        collect(packets, args.sessions, args.output)
        return 0
    except (ValueError, OSError, KeyError, TypeError, EOFError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 2
    finally:
        for packet in packets:
            packet.close()


if __name__ == '__main__':
    raise SystemExit(main())

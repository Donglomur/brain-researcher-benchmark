"""Restricted active-fold calcium image/action transport; no model or scoring.

The operator owns packets and immutable histories. Only one active fold's typed
image interface reaches a fresh local participant process. Protocol-only runs
are diagnostics and cannot enter the restricted seven-fold collector.
"""
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
ROOT = HERE.parents[4]
VIEWER = HERE.parent / 'fold-viewer-v1'
PREFIX = struct.Struct('!II')
HEADER_MAX = 32768
PNG_MAX = 4 * 1024**2
MAX_REQUEST = 4096
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
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Linked path refused')
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
    expected = {f'benchmarks/neural/NEURAL-034/implementations/fold-viewer-v1/{name}'
                for name in ('viewer.py', 'render.py', 'SOURCE_BINDINGS.json')}
    expected |= {'benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/raster.py',
                 'benchmarks/neural/NEURAL-034/implementations/neural034-portable/INPUTS.json',
                 'benchmarks/neural/NEURAL-034/implementations/registered-runtime/public/cases.json',
                 'benchmarks/neural/NEURAL-034/implementations/registered-runtime/grader.py'}
    need(set(bindings) == {'schema', 'members'} and bindings['schema'] == 'neural034-viewer-transport-dependencies/v1'
         and set(bindings['members']) == expected, 'Exact calcium viewer source closure required')
    bodies = {}
    for relative, pin in bindings['members'].items():
        need(set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int and 0 < pin['bytes'] <= 256 * 1024,
             'Invalid source pin')
        body = read_body(ROOT / relative, 256 * 1024)
        need(len(body) == pin['bytes'] and digest(body) == pin['sha256'], 'Calcium viewer dependency mismatch')
        bodies[relative] = body
    path = VIEWER / 'viewer.py'
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('neural034_transport_viewer', loader=None))
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(bodies[str(path.relative_to(ROOT))], str(path), 'exec'), module.__dict__)
    return module


v = load_viewer()


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

    def validate(self):
        need(type(self.max_actions) is int and v.TRAIN + 2 * v.QUERIES + 1 <= self.max_actions <= v.MAX_ACTIONS,
             'Action budget must permit all 120 demonstrations and all 20 complete query responses')
        need(type(self.max_images) is int and v.TRAIN + v.QUERIES <= self.max_images <= self.max_actions,
             'Image budget must permit the complete 140-window fold')
        need(type(self.max_output_bytes) is int and PNG_MAX + HEADER_MAX + PREFIX.size + RESERVE <= self.max_output_bytes <= 4 * 1024**3,
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
    'inspect': {}, 'training': {'index': 'integer 0..119 within the active fold'},
    'query': {'index': 'integer 0..19 within the active fold'},
    'gain': {'units_per_division': 'finite shared display gain from 2^-20 to 2^60'},
    'respond': {'query_id': 'current query ID', 'probability': 'finite context-B probability in [0,1]'},
    'finish': {},
}


def ready_header(packet, limits, episode):
    return {'kind': 'instructions', 'episode_id': episode, 'mode': v.MODE,
            'training_windows': v.TRAIN, 'query_windows': v.QUERIES, 'prompt': v.PROMPT, 'actions': ACTIONS,
            'limits': dict(asdict(limits), max_request_bytes=MAX_REQUEST, max_image_bytes=PNG_MAX),
            'instructions': 'Only typed actions are accepted. PNG frame parts are image content, not text. '
                            'Each query accepts its first valid response only. Finish requires all 20 queries. '
                            'An invalid request fails this session; no query labels or scoring feedback are supplied.'}


def projection(response):
    kind = response.get('kind')
    if kind == 'view':
        common = {'kind', 'mode', 'role', 'index', 'gain_units_per_division', 'clipped_cells',
                  'samples', 'cells', 'sample_rate_hz', 'window_seconds', 'first_sample_seconds',
                  'last_sample_seconds', 'image'}
        role = response.get('role')
        need(role in ('training', 'query') and set(response) == common |
             ({'context_label'} if role == 'training' else {'query_id'}), 'Unexpected viewer fields')
        need(set(response['image']) == {'mime_type', 'base64'}, 'Unexpected nested viewer fields')
        need(response['image']['mime_type'] == 'image/png', 'PNG image required')
        png = base64.b64decode(response['image']['base64'], validate=True)
        need(png.startswith(b'\x89PNG\r\n\x1a\n') and len(png) <= PNG_MAX, 'Bounded PNG required')
        header = {key: value for key, value in response.items() if key != 'image'}
        header['image'] = {'mime_type': 'image/png', 'bytes': len(png)}
        return header, png
    fields = {'response_accepted': {'kind', 'query_id', 'completed_queries'},
              'complete': {'kind', 'queries'}}
    need(kind in fields and set(response) == fields[kind], 'Unexpected response fields')
    return dict(response), b''


def sandbox_profile(client, workspace):
    need(sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').is_file(), 'macOS sandbox-exec required')
    quoted = json.dumps(str(Path(client).resolve()))
    scratch = json.dumps(str(Path(workspace).resolve()))
    return ('(version 1) (deny default) (deny sysctl* process-info* network* process-fork) '
            '(allow process-info* (target self)) (allow process-exec) (allow file-read-metadata) '
            '(allow sysctl-read (sysctl-name "kern.ostype") (sysctl-name "kern.osrelease") '
            '(sysctl-name "kern.version") (sysctl-name "kern.hostname") (sysctl-name "hw.machine")) '
            '(allow file-read-data (literal "/") (subpath "/System") (subpath "/usr") '
            '(subpath "/Library/Frameworks") (literal "/dev/null") (literal "/dev/urandom") '
            '(literal "/dev/random") (literal ' + quoted + ')) '
            '(allow file-read-data (subpath ' + scratch + '))')


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
    # Preserve the original operator viewer format so its replay validator stays
    # independent. Transport-specific proof is recorded in BOUNDARY/RESULT.
    return {'schema': 'neural034-fold-viewer-session/v1', 'mode': v.MODE, 'fold': packet.fold,
            'input': packet.pin, 'query_ids': packet.ids, 'max_actions': limits.max_actions,
            'source': v.source_identity(), 'runtime': v.runtime_identity(), 'prompt': v.PROMPT,
            'participant_reset': 'required_external_per_fold; not proven by this operator viewer'}


def run_fold(packet, output, client, python=sys.executable, sandbox='macos', limits=None):
    need(isinstance(limits, Limits), 'Explicit frozen Limits required')
    limits.validate()
    need(type(packet.fold) is int and packet.fold in v.FOLDS and len(packet.ids) == v.QUERIES
         and len(set(packet.ids)) == v.QUERIES, 'Complete declared fold required')
    need(sandbox in ('macos', 'protocol_only'), 'Unknown sandbox mode')
    client_body = read_body(client, MAX_CLIENT)
    python = Path(python).resolve(strict=True)
    need(python.is_file(), 'Existing interpreter required')
    if sandbox == 'macos':
        need(python.is_relative_to(Path('/Library/Frameworks/Python.framework')),
             'Explicit installed framework Python required; system launchers are not admitted')
    output = v.fresh(output)
    viewer_dir = output / 'viewer'
    viewer_dir.mkdir(mode=0o700)
    captured_client = output / 'client.py'
    v.write_new(captured_client, client_body)
    workspace_manager = tempfile.TemporaryDirectory(prefix='neural034-fold-client-')
    workspace = Path(workspace_manager.name).resolve(strict=True)
    episode = uuid.uuid4().hex
    try:
        need(not any(workspace.iterdir()), 'Fresh empty participant workspace required')
        profile = sandbox_profile(captured_client, workspace) if sandbox == 'macos' else None
        boundary = {'schema': 'neural034-viewer-transport/v1', 'episode_id': episode, 'fold': packet.fold,
                'queries': v.QUERIES, 'mode': v.MODE, 'limits': asdict(limits), 'sandbox': sandbox,
                'client_sha256': digest(client_body), 'python': str(python), 'source': source_identity(),
                'profile_sha256': digest(profile.encode()) if profile else None,
                'workspace': str(workspace), 'workspace_initially_empty': True, 'workspace_policy': 'empty_read_only',
                'fresh_process_per_fold': True, 'provider_context_qualified': False,
                'provider_image_capacity_qualified': False, 'scientific_qualification': False}
        v.write_new(output / 'BOUNDARY.json', encode(boundary))
        if profile:
            v.write_new(output / 'sandbox.sb', profile.encode())
        journal = Journal(output / 'transport')
    except BaseException:
        workspace_manager.cleanup()
        raise
    child, session, action_log = None, None, None
    reason, forced_stop, images, outbound = None, False, 0, 0
    started = time.monotonic()
    deadline = started + limits.wall_seconds
    chain, exit_code, group_cleanup, workspace_destroyed = None, None, None, False
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
        raster, renderer, _, _ = v.dependencies()
        session = v.Session(packet, limits.max_actions, raster, renderer)
        manifest = viewer_manifest(packet, limits)
        v.write_new(viewer_dir / 'manifest.json', encode(manifest))
        chain = digest(encode(manifest))
        action_log = (viewer_dir / 'actions.jsonl').open('xb')
        command = [str(python), '-I', '-S', '-B', str(captured_client)]
        if profile:
            command = ['/usr/bin/sandbox-exec', '-p', profile] + command
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, cwd=workspace, env={'LANG': 'C', 'LC_ALL': 'C'},
                                 close_fds=True, start_new_session=True)
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
            needs_image = isinstance(request, dict) and request.get('action') in ('inspect', 'training', 'query', 'gain')
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
        try:
            exit_code = child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise WireFailure('client_did_not_exit') from None
        need(exit_code == 0, 'Client failed after completion')
        try:
            trailing = os.read(child.stdout.fileno(), MAX_REQUEST + PREFIX.size + 1)
        except BlockingIOError:
            raise WireFailure('output_pipe_remained_open_after_exit') from None
        if trailing:
            journal.record('in', trailing, False)
            raise WireFailure('output_after_finish')
    except BaseException as exc:
        reason = {'type': type(exc).__name__, 'message': str(exc)[:1000]}
        failure = {'status': 'failed', 'fold': packet.fold, 'reason': reason}
        for folder in (output, viewer_dir):
            try:
                v.write_new(folder / 'failure.json', encode(failure))
            except OSError:
                pass
    finally:
        if child is not None:
            if child.poll() is None:
                forced_stop = True
            # The original group can outlive its leader. Never leave a child
            # behind merely because the leader has already exited successfully.
            try:
                os.killpg(child.pid, signal.SIGKILL)
                group_cleanup = 'signalled'
                if reason is None:
                    reason = {'type': 'ChildProcessError', 'message': 'Client process group remained after completion'}
            except ProcessLookupError:
                group_cleanup = 'absent'
            except OSError as exc:
                group_cleanup = 'error'
                reason = {'type': type(exc).__name__, 'message': 'Owned process-group cleanup could not be verified'}
                if forced_stop:
                    child.kill()
            if forced_stop:
                child.wait(timeout=2)
            exit_code = child.returncode
            for stream in (child.stdin, child.stdout):
                if stream and not stream.closed:
                    stream.close()
        if action_log:
            action_log.close()
        journal.close()
        try:
            workspace_manager.cleanup()
            workspace_destroyed = not os.path.lexists(workspace)
            need(workspace_destroyed, 'Participant workspace still exists')
        except BaseException as exc:
            reason = {'type': type(exc).__name__, 'message': 'Participant workspace removal failed'}
    if reason is not None:
        for folder in (output, viewer_dir):
            if not os.path.lexists(folder / 'failure.json'):
                v.write_new(folder / 'failure.json', encode({'status': 'failed', 'fold': packet.fold, 'reason': reason}))
    else:
        v.write_new(viewer_dir / 'completion.json', encode({'actions': session.actions, 'last_sha256': chain,
                    'fold': packet.fold, 'queries': v.QUERIES, 'mode': v.MODE}))
    result = {'schema': 'neural034-viewer-transport-result/v1', 'status': 'complete_unscored' if reason is None else 'failed',
              'fold': packet.fold, 'episode_id': episode, 'actions': session.actions if session else 0,
              'images': images, 'output_bytes': outbound, 'wire_bytes': journal.offset,
              'wire_records': journal.sequence, 'last_sha256': journal.previous,
              'client_exit_code': exit_code, 'forced_stop': forced_stop,
              'process_group_cleanup': group_cleanup,
              'workspace_destroyed': workspace_destroyed,
              'wall_seconds': time.monotonic() - started, 'reason': reason,
              'provider_context_qualified': False, 'scientific_qualification': False}
    v.write_new(output / 'RESULT.json', encode(result))
    return result


def audit_transport(path, packet):
    path = v.plain(path)
    need(not os.path.lexists(path / 'failure.json'), 'Failed transport cannot be collected')
    boundary = decode(read_body(path / 'BOUNDARY.json', 65536))
    expected_keys = {'schema', 'episode_id', 'fold', 'queries', 'mode', 'limits', 'sandbox', 'client_sha256',
                     'python', 'source', 'profile_sha256', 'workspace', 'workspace_initially_empty', 'workspace_policy', 'fresh_process_per_fold',
                     'provider_context_qualified', 'provider_image_capacity_qualified', 'scientific_qualification'}
    need(set(boundary) == expected_keys and boundary['schema'] == 'neural034-viewer-transport/v1'
         and boundary['mode'] == v.MODE and type(boundary['fold']) is int and boundary['fold'] == packet.fold
         and type(boundary['queries']) is int and boundary['queries'] == v.QUERIES
         and boundary['source'] == source_identity() and boundary['fresh_process_per_fold'] is True
         and boundary['workspace_initially_empty'] is True
         and boundary['workspace_policy'] == 'empty_read_only'
         and boundary['provider_context_qualified'] is False and boundary['provider_image_capacity_qualified'] is False
         and boundary['scientific_qualification'] is False, 'Transport/source/fold boundary mismatch')
    episode = boundary['episode_id']
    need(type(episode) is str and len(episode) == 32 and all(c in '0123456789abcdef' for c in episode), 'Invalid episode ID')
    need(type(boundary['limits']) is dict and set(boundary['limits']) == set(Limits.__dataclass_fields__), 'Exact limits required')
    limits = Limits(**boundary['limits'])
    limits.validate()
    need(digest(read_body(path / 'client.py', MAX_CLIENT)) == boundary['client_sha256'], 'Client capture changed')
    sandbox = boundary['sandbox']
    need(sandbox in ('macos', 'protocol_only'), 'Unknown recorded sandbox')
    workspace = v.plain(boundary['workspace'])
    need(workspace.is_absolute() and workspace.name.startswith('neural034-fold-client-')
         and not os.path.lexists(workspace) and not workspace.is_relative_to(ROOT)
         and not workspace.is_relative_to(path), 'Completed independent workspace must be absent')
    python = Path(boundary['python'])
    need(python.is_absolute() and '..' not in python.parts, 'Absolute recorded interpreter required')
    if sandbox == 'macos':
        need(python.is_relative_to(Path('/Library/Frameworks/Python.framework')),
             'Recorded runtime is not admitted framework Python')
    profile = sandbox_profile(path / 'client.py', workspace) if sandbox == 'macos' else None
    need(boundary['profile_sha256'] == (digest(profile.encode()) if profile else None), 'Sandbox profile mismatch')
    if profile:
        need(read_body(path / 'sandbox.sb', 65536) == profile.encode(), 'Sandbox capture changed')
    else:
        need(not os.path.lexists(path / 'sandbox.sb'), 'Unexpected sandbox capture')
    raster, renderer, _, _ = v.dependencies()
    # Preserve the existing viewer's complete source/input/action/answer validator.
    answers, viewer_receipt = v.replay(path / 'viewer', packet, raster, renderer)
    session = v.Session(packet, limits.max_actions, raster, renderer)
    manifest = decode(read_body(path / 'viewer' / 'manifest.json', 65536))
    need(encode(manifest) == encode(viewer_manifest(packet, limits)), 'Viewer and transport limits differ')
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
                needs_image = isinstance(pending, dict) and pending.get('action') in ('inspect', 'training', 'query', 'gain')
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
    expected = {'schema': 'neural034-viewer-transport-result/v1', 'status': 'complete_unscored', 'fold': packet.fold,
                'episode_id': episode, 'actions': session.actions, 'images': images, 'output_bytes': outbound,
                'wire_bytes': offset, 'wire_records': sequence, 'last_sha256': previous, 'client_exit_code': 0,
                'forced_stop': False, 'wall_seconds': result.get('wall_seconds'), 'reason': None,
                'process_group_cleanup': 'absent',
                'workspace_destroyed': True,
                'provider_context_qualified': False, 'scientific_qualification': False}
    integer_fields = ('fold', 'actions', 'images', 'output_bytes', 'wire_bytes', 'wire_records', 'client_exit_code')
    need(result == expected and all(type(result[key]) is int for key in integer_fields)
         and result['forced_stop'] is False and result['workspace_destroyed'] is True
         and result['provider_context_qualified'] is False and result['scientific_qualification'] is False
         and type(result['wall_seconds']) in (int, float) and math.isfinite(result['wall_seconds'])
         and 0 <= result['wall_seconds'] <= limits.wall_seconds + 2, 'Incomplete or invalid client result')
    return {'boundary': boundary, 'viewer': viewer_receipt, 'result': result, 'answers': answers,
            'boundary_sha256': digest(encode(boundary)), 'result_sha256': digest(encode(result))}


def collect(packets, sessions, output):
    need(len(packets) == len(sessions) == len(v.FOLDS), 'Seven complete folds required')
    need([p.fold for p in packets] == list(v.FOLDS) and all(type(p.fold) is int for p in packets),
         'Canonical folds and order required')
    paths = [v.plain(p) for p in sessions]
    need(len({str(p.resolve()) for p in paths}) == len(v.FOLDS), 'Distinct fold sessions required')
    receipts = {str(p.fold): audit_transport(path, p) for p, path in zip(packets, paths)}
    boundaries = [row['boundary'] for row in receipts.values()]
    shared = ('schema', 'mode', 'limits', 'sandbox', 'client_sha256', 'python', 'source')
    need(all({k: b[k] for k in shared} == {k: boundaries[0][k] for k in shared} for b in boundaries),
         'Mixed participant/limits/source/sandbox conditions')
    need(all(b['sandbox'] == 'macos' for b in boundaries), 'Restricted collection rejects protocol-only diagnostics')
    need(len({b['episode_id'] for b in boundaries}) == len(v.FOLDS) and
         len({b['workspace'] for b in boundaries}) == len(v.FOLDS), 'Fresh fold process/context identities required')
    # Audit already invokes the unchanged original viewer replay. Retain its
    # complete probability output, while additionally requiring restricted local
    # process histories. No target/reference results are opened and no grader
    # is executed; the existing dependency check authenticates grader source.
    _, _, inputs, ids = v.dependencies()
    rows, viewer_receipts = [], {}
    for packet in packets:
        fold = packet.fold
        need(packet.ids == ids[fold] and packet.pin ==
             {key: inputs[f'fold-{fold:02d}'][key] for key in ('bytes', 'sha256')},
             'Original authenticated fold identity required')
        checked = receipts[str(fold)]
        answers = checked.pop('answers')
        need(set(answers) == set(ids[fold]), 'Complete original fold responses required')
        rows.extend({'fold': fold, 'query_id': query_id, 'probability': answers[query_id]} for query_id in ids[fold])
        viewer_receipts[str(fold)] = checked['viewer']
    need(len(rows) == 140 and len({(r['fold'], r['query_id']) for r in rows}) == 140,
         'Complete original 140-query submission required')
    body = encode({'schema_version': 1, 'probabilities': rows})
    need(len(body) <= 100000, 'Original complete probability-file extent')
    output = v.fresh(output)
    v.write_new(output / 'probabilities.json', body)
    v.write_new(output / 'collection.json', encode({'schema': 'neural034-fold-viewer-collection/v1', 'mode': v.MODE,
                'folds': 7, 'queries': 140, 'submission': {'bytes': len(body), 'sha256': digest(body)},
                'sessions': viewer_receipts, 'source': v.source_identity(), 'runtime': v.runtime_identity(),
                'scope': 'Complete original-format output after image/history replay; no targets or grader called.',
                'participant_reset_qualified': False, 'provider_delivery_qualified': False, 'scientific_qualification': False}))
    receipt = {'schema': 'neural034-viewer-transport-collection/v1', 'mode': v.MODE, 'folds': 7, 'queries': 140,
               'status': 'complete_unscored', 'sessions': receipts, 'source': source_identity(),
               'submission': {'bytes': len(body), 'sha256': digest(body)},
               'restricted_local_process_transport': True,
               'provider_context_qualified': False, 'scientific_qualification': False,
               'scope': 'Seven fresh restricted local image/action processes and original viewer replay only; no external provider, model interpretation or scientific qualification.'}
    v.write_new(output / 'TRANSPORT_COMPLETE.json', encode(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('fold')
    run.add_argument('--fold', type=int, choices=v.FOLDS, required=True)
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
    gather.add_argument('--packets', nargs=7, type=Path, required=True)
    gather.add_argument('--sessions', nargs=7, type=Path, required=True)
    gather.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _, _, inputs, ids = v.dependencies()
        if args.command == 'fold':
            packet = v.Packet(args.packet, args.fold, inputs[f'fold-{args.fold:02d}'], ids[args.fold])
            result = run_fold(packet, args.output, args.client, args.python, args.sandbox,
                                Limits(args.max_actions, args.max_images, args.max_output_bytes, args.wall_seconds))
            return 0 if result['status'] == 'complete_unscored' else 2
        packets = [v.Packet(path, fold, inputs[f'fold-{fold:02d}'], ids[fold])
                   for fold, path in zip(v.FOLDS, args.packets)]
        collect(packets, args.sessions, args.output)
        return 0
    except (ValueError, OSError, KeyError, TypeError, EOFError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

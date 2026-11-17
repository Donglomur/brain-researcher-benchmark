"""Restricted matched-modality participant transport for NEURAL-034.

Reuse the accepted framing, bounded files, journal and macOS sandbox primitives.
Each process and replay owns one immutable condition-specific controls.Session;
the prior combined viewer replay and module globals are never patched. Session
wall deadlines are cooperative around synchronous rendering and I/O. External
provider state, scientific competence and hard whole-job limits are unqualified.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
# Never inherit a possibly fold-labelled TMPDIR/TEMP/TMP from the operator.
TEMP_ROOT = Path('/tmp').resolve(strict=True)
HISTORY_MAX = 64 * 1024**2
SCHEMA = 'neural034-modality-viewer-transport/v1'
RESULT_SCHEMA = 'neural034-modality-viewer-transport-result/v1'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _capture(path):
    """Small source-only bootstrap before the pinned transport is available."""
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'Linked dependency path refused')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 256 * 1024,
             'Bounded ordinary dependency source required')
        body = stream.read(256 * 1024 + 1)
        key = lambda s: tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
        need(len(body) == before.st_size and key(before) == key(os.fstat(stream.fileno())) == key(path.stat()),
             'Dependency changed during capture')
    return body


def _pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate dependency key')
        result[key] = value
    return result


_SELF = _capture(HERE / 'transport.py')
_BINDINGS = _capture(HERE / 'SOURCE_BINDINGS.json')
_MEMBERS = json.loads(_BINDINGS, object_pairs_hook=_pairs)


def _check_dependencies():
    prefix = 'benchmarks/neural/NEURAL-034/implementations/'
    expected = {prefix + 'modality-viewer-controls-v1/' + name
                for name in ('controls.py', 'render.py', 'SOURCE_BINDINGS.json')}
    expected |= {prefix + 'viewer-transport-v1/' + name for name in ('transport.py', 'SOURCE_BINDINGS.json')}
    need(set(_MEMBERS) == {'schema', 'members'} and
         _MEMBERS['schema'] == 'neural034-modality-transport-dependencies/v1' and
         set(_MEMBERS['members']) == expected, 'Exact prior controls/transport closure required')
    bodies = {}
    for relative, pin in _MEMBERS['members'].items():
        need(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int,
             'Exact dependency pin required')
        body = _capture(ROOT / relative)
        need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
             'Pinned modality dependency changed')
        bodies[relative] = body
    return bodies


def _load_controls():
    bodies = _check_dependencies()
    path = HERE.parent / 'modality-viewer-controls-v1' / 'controls.py'
    name = 'neural034_restricted_modality_controls'
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(bodies[str(path.relative_to(ROOT))], str(path), 'exec'), module.__dict__)
    _check_dependencies()
    return module


C = _load_controls()
T = C.T
V = T.v
Limits = T.Limits


def source_identity():
    _check_dependencies()
    result = {}
    for name, original in (('transport.py', _SELF), ('SOURCE_BINDINGS.json', _BINDINGS)):
        body = T.read_body(HERE / name, 256 * 1024)
        need(body == original, 'Loaded transport source differs from disk')
        result[name] = {'bytes': len(body), 'sha256': T.digest(body)}
    return result


def _failure(exc, prefix=None):
    return {'type': type(exc).__name__, 'message': ((prefix + ': ') if prefix else '') + str(exc)[:1000]}


def _code_path(value, output, workspace, *, absent):
    """Opaque execution location; never the operator's evidence pathname."""
    need(type(value) is str and Path(value).is_absolute(), 'Absolute opaque client code path required')
    path = V.plain(value)
    directory = path.parent
    need(path.name == 'client.py' and directory.parent == TEMP_ROOT and
         C.re.fullmatch(r'neural034-modality-code-[a-z0-9_]{8}', directory.name) and
         directory != workspace and not directory.is_relative_to(workspace) and
         not workspace.is_relative_to(directory) and not directory.is_relative_to(ROOT) and
         not directory.is_relative_to(output) and not output.is_relative_to(directory),
         'Independent opaque temporary code directory required')
    if absent:
        need(not os.path.lexists(path) and not os.path.lexists(directory),
             'Completed participant code directory must be absent')
    return path


def run_fold(packet, output, client, *, condition, python, sandbox='macos', limits):
    """Run one fresh restricted process with one fixed observation condition."""
    selection = C.Selection(condition, limits)
    need(sandbox in ('macos', 'protocol_only'), 'Known explicit sandbox required')
    source = source_identity()
    client_body = T.read_body(client, T.MAX_CLIENT)
    python = Path(python).resolve(strict=True)
    need(python.is_file(), 'Existing explicit interpreter required')
    if sandbox == 'macos':
        need(python.is_relative_to(Path('/Library/Frameworks/Python.framework')),
             'Explicit installed framework Python required')
    episode = uuid.uuid4().hex
    session = C.Session(packet, selection, episode)
    output = V.fresh(output)
    viewer_dir = output / 'viewer'
    viewer_dir.mkdir(mode=0o700)
    captured_client = output / 'client.py'
    V.write_new(captured_client, client_body)
    workspace_manager = tempfile.TemporaryDirectory(prefix='neural034-modality-client-', dir=TEMP_ROOT)
    workspace = Path(workspace_manager.name).resolve(strict=True)
    code_manager, code_directory = None, None
    code_directory_destroyed = False
    journal = action_log = child = None
    reason, cleanup_errors = None, []
    forced_stop, group_cleanup, workspace_destroyed = False, None, False
    exit_code, images, outbound = None, 0, 0
    started = time.monotonic()
    deadline = started + limits.wall_seconds

    def check_deadline():
        if time.monotonic() >= deadline:
            raise T.WireFailure('deadline')

    def send(header, image=b''):
        nonlocal images, outbound
        check_deadline()
        body = T.wire(header, image)
        need(outbound + len(body) <= limits.max_output_bytes, 'Output byte budget exhausted')
        try:
            T.write_frame(child.stdin.fileno(), body, deadline)
        except T.WireFailure as exc:
            journal.record('out', exc.captured, False)
            raise
        journal.record('out', body)
        outbound += len(body)
        images += bool(image)

    try:
        need(not any(workspace.iterdir()), 'Fresh empty participant workspace required')
        code_manager = tempfile.TemporaryDirectory(prefix='neural034-modality-code-', dir=TEMP_ROOT)
        code_directory = Path(code_manager.name).resolve(strict=True)
        need(not any(code_directory.iterdir()), 'Fresh empty opaque code directory required')
        participant_code = _code_path(str(code_directory / 'client.py'), output, workspace, absent=False)
        V.write_new(participant_code, client_body)
        need(T.read_body(participant_code, T.MAX_CLIENT) == client_body,
             'Opaque execution source must match the captured client bytes')
        profile = T.sandbox_profile(participant_code, workspace) if sandbox == 'macos' else None
        boundary = {
            'schema': SCHEMA, 'condition': condition, 'visible_modalities': list(C.select(condition)),
            'mode': C.mode(condition), 'episode_id': episode, 'fold': packet.fold, 'queries': V.QUERIES,
            'limits': asdict(limits), 'sandbox': sandbox, 'client_sha256': T.digest(client_body),
            'python': str(python), 'source': source,
            'profile_sha256': T.digest(profile.encode()) if profile else None,
            'code_path': str(participant_code),
            'workspace': str(workspace), 'workspace_initially_empty': True,
            'workspace_policy': 'empty_read_only', 'fresh_process_per_fold': True,
            'provider_context_qualified': False, 'provider_image_capacity_qualified': False,
            'scientific_qualification': False,
        }
        V.write_new(output / 'BOUNDARY.json', T.encode(boundary))
        if profile:
            V.write_new(output / 'sandbox.sb', profile.encode())
        V.write_new(viewer_dir / 'manifest.json', T.encode(session._manifest))
        action_log = (viewer_dir / 'actions.jsonl').open('xb')
        journal = T.Journal(output / 'transport')
        command = [str(python), '-I', '-S', '-B', str(participant_code)]
        if profile:
            command = ['/usr/bin/sandbox-exec', '-p', profile] + command
        check_deadline()
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, cwd=workspace, env={'LANG': 'C', 'LC_ALL': 'C'},
                                 close_fds=True, start_new_session=True)
        os.set_blocking(child.stdin.fileno(), False)
        os.set_blocking(child.stdout.fileno(), False)
        send(session.ready)
        finished = False
        while not finished:
            check_deadline()
            try:
                raw = T.read_frame(child.stdout.fileno(), deadline)
            except T.WireFailure as exc:
                journal.record('in', exc.captured, False)
                raise
            journal.record('in', raw)
            request, _ = T.unpack(raw, inbound=True)
            check_deadline()
            response = session.handle(request)
            check_deadline()
            action_log.write(T.encode(session._history[-1]))
            action_log.flush()
            send(*C.projection(response, condition))
            finished = response['kind'] == 'complete'
        child.stdin.close()
        remaining = min(2.0, deadline - time.monotonic())
        need(remaining > 0, 'Deadline reached before clean client exit')
        try:
            exit_code = child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise T.WireFailure('client_did_not_exit') from None
        check_deadline()
        need(exit_code == 0, 'Client failed after completion')
        try:
            trailing = os.read(child.stdout.fileno(), T.MAX_REQUEST + T.PREFIX.size + 1)
        except BlockingIOError:
            raise T.WireFailure('output_pipe_remained_open_after_exit') from None
        if trailing:
            journal.record('in', trailing, False)
            raise T.WireFailure('output_after_finish')
        completed = session.finish_record()
        need(completed['images'] == images and completed['outbound_bytes'] == outbound,
             'Session and delivered output accounting differ')
    except BaseException as exc:
        reason = _failure(exc)
    finally:
        if child is not None:
            try:
                forced_stop = child.poll() is None
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                    group_cleanup = 'signalled'
                    cleanup_errors.append({'type': 'ChildProcessError', 'message': 'Owned process group remained after session'})
                except ProcessLookupError:
                    group_cleanup = 'absent'
                except OSError as exc:
                    group_cleanup = 'error'
                    cleanup_errors.append(_failure(exc, 'Owned process-group cleanup'))
                    if forced_stop:
                        child.kill()
                if forced_stop:
                    child.wait(timeout=2)
                exit_code = child.returncode
            except BaseException as exc:
                cleanup_errors.append(_failure(exc, 'Owned child reap'))
            finally:
                for stream in (child.stdin, child.stdout):
                    if stream and not stream.closed:
                        try:
                            stream.close()
                        except BaseException as exc:
                            cleanup_errors.append(_failure(exc, 'Owned pipe close'))
        for stream in (action_log, journal):
            if stream is not None:
                try:
                    stream.close()
                except BaseException as exc:
                    cleanup_errors.append(_failure(exc, 'Evidence stream close'))
        try:
            workspace_manager.cleanup()
            workspace_destroyed = not os.path.lexists(workspace)
            need(workspace_destroyed, 'Participant workspace still exists')
        except BaseException as exc:
            cleanup_errors.append(_failure(exc, 'Participant workspace removal'))
        if code_manager is not None:
            try:
                code_manager.cleanup()
                code_directory_destroyed = code_directory is not None and not os.path.lexists(code_directory)
                need(code_directory_destroyed, 'Participant code directory still exists')
            except BaseException as exc:
                cleanup_errors.append(_failure(exc, 'Participant code directory removal'))
    if cleanup_errors and reason is None:
        reason = cleanup_errors[0]
    if reason is None:
        V.write_new(viewer_dir / 'history.json', T.encode(completed))
    else:
        failure = {'status': 'failed', 'condition': condition, 'fold': packet.fold,
                   'reason': reason, 'cleanup_errors': cleanup_errors}
        for folder in (output, viewer_dir):
            V.write_new(folder / 'failure.json', T.encode(failure))
    result = {
        'schema': RESULT_SCHEMA, 'condition': condition,
        'status': 'complete_unscored' if reason is None else 'failed',
        'fold': packet.fold, 'episode_id': episode, 'actions': len(session._history),
        'images': images, 'output_bytes': outbound,
        'wire_bytes': journal.offset if journal else 0, 'wire_records': journal.sequence if journal else 0,
        'last_sha256': journal.previous if journal else '0' * 64, 'client_exit_code': exit_code,
        'forced_stop': forced_stop, 'process_group_cleanup': group_cleanup,
        'workspace_destroyed': workspace_destroyed, 'code_directory_destroyed': code_directory_destroyed,
        'wall_seconds': time.monotonic() - started,
        'reason': reason, 'cleanup_errors': cleanup_errors,
        'provider_context_qualified': False, 'scientific_qualification': False,
    }
    V.write_new(output / 'RESULT.json', T.encode(result))
    return result


def _boundary_header(path, packet, condition):
    """Validate public execution metadata without rendering or wire replay."""
    C.select(condition)
    path = V.plain(path)
    need(not os.path.lexists(path / 'failure.json') and not os.path.lexists(path / 'viewer' / 'failure.json'),
         'Failed transport cannot be collected')
    boundary = T.decode(T.read_body(path / 'BOUNDARY.json', 65536))
    keys = {'schema', 'condition', 'visible_modalities', 'mode', 'episode_id', 'fold', 'queries', 'limits',
            'sandbox', 'client_sha256', 'python', 'source', 'profile_sha256', 'code_path', 'workspace',
            'workspace_initially_empty', 'workspace_policy', 'fresh_process_per_fold',
            'provider_context_qualified', 'provider_image_capacity_qualified', 'scientific_qualification'}
    need(type(boundary) is dict and set(boundary) == keys and boundary['schema'] == SCHEMA and
         boundary['condition'] == condition and boundary['visible_modalities'] == list(C.select(condition)) and
         boundary['mode'] == C.mode(condition) and type(boundary['fold']) is int and boundary['fold'] == packet.fold and
         type(boundary['queries']) is int and boundary['queries'] == V.QUERIES and
         boundary['source'] == source_identity() and boundary['workspace_initially_empty'] is True and
         boundary['workspace_policy'] == 'empty_read_only' and boundary['fresh_process_per_fold'] is True and
         boundary['provider_context_qualified'] is False and boundary['provider_image_capacity_qualified'] is False and
         boundary['scientific_qualification'] is False, 'Exact condition/source/fold boundary required')
    episode = boundary['episode_id']
    need(type(episode) is str and C.re.fullmatch('[0-9a-f]{32}', episode), 'Exact opaque episode identity required')
    need(type(boundary['limits']) is dict and set(boundary['limits']) == set(Limits.__dataclass_fields__),
         'Exact recorded limits required')
    limits = Limits(**boundary['limits'])
    selection = C.Selection(condition, limits)
    need(boundary['sandbox'] in ('macos', 'protocol_only'), 'Known recorded sandbox required')
    need(type(boundary['client_sha256']) is str and C.re.fullmatch('[0-9a-f]{64}', boundary['client_sha256']),
         'Exact client source identity required')
    need(type(boundary['workspace']) is str and Path(boundary['workspace']).is_absolute(),
         'Absolute opaque participant workspace required')
    workspace = V.plain(boundary['workspace'])
    need(workspace.parent == TEMP_ROOT and C.re.fullmatch(r'neural034-modality-client-[a-z0-9_]{8}', workspace.name) and
         not os.path.lexists(workspace) and not workspace.is_relative_to(ROOT) and not workspace.is_relative_to(path),
         'Completed fresh independent workspace must be absent')
    _code_path(boundary['code_path'], path, workspace, absent=True)
    python = Path(boundary['python'])
    need(python.is_absolute() and '..' not in python.parts, 'Absolute recorded interpreter required')
    if boundary['sandbox'] == 'macos':
        need(python.is_relative_to(Path('/Library/Frameworks/Python.framework')), 'Framework Python required')
    return path, boundary, selection


def audit_transport(path, packet, condition):
    """One replay matches condition, complete action chain and every wire byte."""
    path, boundary, selection = _boundary_header(path, packet, condition)
    limits, episode = selection.limits, boundary['episode_id']
    need(T.digest(T.read_body(path / 'client.py', T.MAX_CLIENT)) == boundary['client_sha256'], 'Captured client changed')
    sandbox = boundary['sandbox']
    workspace = V.plain(boundary['workspace'])
    profile = T.sandbox_profile(boundary['code_path'], workspace) if sandbox == 'macos' else None
    need(boundary['profile_sha256'] == (T.digest(profile.encode()) if profile else None), 'Sandbox profile differs')
    if profile:
        need(T.read_body(path / 'sandbox.sb', 65536) == profile.encode(), 'Sandbox capture changed')
    else:
        need(not os.path.lexists(path / 'sandbox.sb'), 'Unexpected diagnostic sandbox capture')

    session = C.Session(packet, selection, episode)
    manifest = T.decode(T.read_body(path / 'viewer' / 'manifest.json', 65536))
    need(T.encode(manifest) == T.encode(session._manifest), 'Condition/source/input/prompt/budget manifest differs')
    saved = T.decode(T.read_body(path / 'viewer' / 'history.json', HISTORY_MAX))
    raw = log = actions = None
    try:
        raw, raw_before = T.ordinary(path / 'transport' / 'wire.bin',
                                    limits.max_output_bytes + limits.max_actions * (T.MAX_REQUEST + T.PREFIX.size))
        log, log_before = T.ordinary(path / 'transport' / 'journal.jsonl', T.MAX_JOURNAL)
        actions, actions_before = T.ordinary(path / 'viewer' / 'actions.jsonl', HISTORY_MAX)
    except BaseException:
        for stream in (raw, log, actions):
            if stream is not None:
                stream.close()
        raise
    previous, offset, sequence, images, outbound = '0' * 64, 0, 0, 0, 0
    pending = action_row = None
    finished = False
    try:
        while True:
            line = log.readline(4097)
            if not line:
                break
            need(0 < len(line) <= 4096 and line.endswith(b'\n'), 'Bounded complete journal line required')
            row = T.decode(line)
            need(type(row) is dict and set(row) == {'sequence', 'direction', 'offset', 'bytes', 'sha256', 'complete', 'previous'} and
                 type(row['sequence']) is int and row['sequence'] == sequence and type(row['offset']) is int and
                 row['offset'] == offset and row['previous'] == previous and row['complete'] is True,
                 'Incomplete or reordered transport journal')
            direction = 'out' if sequence % 2 == 0 else 'in'
            need(row['direction'] == direction and type(row['bytes']) is int and
                 T.PREFIX.size < row['bytes'] <= T.PREFIX.size + T.HEADER_MAX + T.PNG_MAX, 'Invalid transport record')
            body = raw.read(row['bytes'])
            need(len(body) == row['bytes'] and T.digest(body) == row['sha256'], 'Wire capture changed')
            header, png = T.unpack(body, inbound=direction == 'in')
            if sequence == 0:
                need(body == T.wire(session.ready), 'Initial condition projection changed')
            elif direction == 'in':
                need(not finished and len(session._history) < limits.max_actions, 'Actions after finish or budget')
                action_line = actions.readline(T.MAX_REQUEST + 1025)
                need(0 < len(action_line) <= T.MAX_REQUEST + 1024 and action_line.endswith(b'\n'),
                     'Complete bounded condition action required')
                action_row = T.decode(action_line)
                need(type(action_row) is dict and set(action_row) == {'ordinal', 'previous', 'request', 'response_sha256'} and
                     type(action_row['ordinal']) is int and action_row['ordinal'] == len(session._history) + 1 and
                     T.encode(action_row['request']) == T.encode(header), 'Wire request differs from condition history')
                pending = header
            else:
                need(pending is not None, 'Missing action before response')
                response = session.handle(pending)
                need(T.encode(session._history[-1]) == T.encode(action_row), 'Condition action/image chain changed')
                need(body == T.wire(*C.projection(response, condition)), 'Wire response differs from exact condition result')
                finished = response['kind'] == 'complete'
                pending = None
            if direction == 'out':
                outbound += len(body)
                images += bool(png)
                need(outbound <= limits.max_output_bytes, 'Recorded output exceeded budget')
            offset += len(body)
            previous, sequence = T.digest(T.encode(row)), sequence + 1
            need(sequence <= 2 * limits.max_actions + 1, 'Too many transport records')
        need(raw.read(1) == b'' and actions.read(1) == b'' and pending is None and finished,
             'Incomplete transport or extra wire/action data')
        completed = session.finish_record()
        need(T.encode(saved) == T.encode(completed) and completed['images'] == images and
             completed['outbound_bytes'] == outbound, 'Completed condition history/accounting differs')
        for stream, before, file in ((raw, raw_before, path / 'transport' / 'wire.bin'),
                                    (log, log_before, path / 'transport' / 'journal.jsonl'),
                                    (actions, actions_before, path / 'viewer' / 'actions.jsonl')):
            need(T.identity(before) == T.identity(os.fstat(stream.fileno())) == T.identity(file.stat()),
                 'Transport evidence changed during replay')
    finally:
        raw.close()
        log.close()
        actions.close()

    result = T.decode(T.read_body(path / 'RESULT.json', 16384))
    expected = {
        'schema': RESULT_SCHEMA, 'condition': condition, 'status': 'complete_unscored',
        'fold': packet.fold, 'episode_id': episode, 'actions': len(session._history),
        'images': images, 'output_bytes': outbound, 'wire_bytes': offset, 'wire_records': sequence,
        'last_sha256': previous, 'client_exit_code': 0, 'forced_stop': False,
        'process_group_cleanup': 'absent', 'workspace_destroyed': True, 'code_directory_destroyed': True,
        'wall_seconds': result.get('wall_seconds'), 'reason': None, 'cleanup_errors': [],
        'provider_context_qualified': False, 'scientific_qualification': False,
    }
    ints = ('fold', 'actions', 'images', 'output_bytes', 'wire_bytes', 'wire_records', 'client_exit_code')
    need(T.encode(result) == T.encode(expected) and all(type(result[k]) is int for k in ints) and
         type(result['wall_seconds']) in (int, float) and math.isfinite(result['wall_seconds']) and
         0 <= result['wall_seconds'] <= limits.wall_seconds + 2, 'Complete bounded successful client result required')
    return {'boundary': boundary, 'result': result, 'answers': completed['probabilities'],
            'history': {'bytes': len(T.encode(completed)), 'sha256': T.digest(T.encode(completed))},
            'boundary_sha256': T.digest(T.encode(boundary)), 'result_sha256': T.digest(T.encode(result))}


def _preflight(condition, packets, sessions):
    """Reject mismatched policy and identities before any rendering/replay."""
    C.select(condition)
    need(type(packets) is list and type(sessions) is list and len(packets) == len(sessions) == len(V.FOLDS),
         'Seven complete canonical fold packets/sessions required')
    need([p.fold for p in packets] == list(V.FOLDS) and all(type(p.fold) is int for p in packets),
         'Canonical fold order required')
    paths = [V.plain(path) for path in sessions]
    need(len({str(path.resolve()) for path in paths}) == 7, 'Distinct fold session paths required')
    _, _, inputs, ids = V.dependencies()
    for packet in packets:
        need(packet.ids == ids[packet.fold] and packet.pin ==
             {key: inputs[f'fold-{packet.fold:02d}'][key] for key in ('bytes', 'sha256')},
             'Original complete authenticated fold identity required')
    boundaries = [_boundary_header(path, packet, condition)[1] for packet, path in zip(packets, paths)]
    _matched_boundaries(boundaries, 7)
    return paths, ids, boundaries


def _prepare(condition, packets, sessions):
    paths, ids, _ = _preflight(condition, packets, sessions)
    receipts = {str(packet.fold): audit_transport(path, packet, condition)
                for packet, path in zip(packets, paths)}
    _matched_boundaries([r['boundary'] for r in receipts.values()], 7)
    rows = []
    for packet in packets:
        answers = receipts[str(packet.fold)].pop('answers')
        need(set(answers) == set(ids[packet.fold]), 'Complete original fold responses required')
        rows.extend({'fold': packet.fold, 'query_id': query_id, 'probability': answers[query_id]}
                    for query_id in ids[packet.fold])
    need(len(rows) == 140 and len({(r['fold'], r['query_id']) for r in rows}) == 140,
         'Complete unchanged 140-query support required')
    body = T.encode({'schema_version': 1, 'probabilities': rows})
    need(len(body) <= 100000, 'Bounded original-format probability output required')
    receipt = {
        'schema': 'neural034-modality-viewer-transport-collection/v1', 'condition': condition,
        'visible_modalities': list(C.select(condition)), 'mode': C.mode(condition),
        'folds': 7, 'queries': 140, 'status': 'complete_unscored', 'sessions': receipts,
        'source': source_identity(), 'submission': {'bytes': len(body), 'sha256': T.digest(body)},
        'restricted_local_process_transport': True, 'provider_context_qualified': False,
        'provider_delivery_qualified': False, 'scientific_qualification': False, 'score': None,
        'scope': 'Seven fresh restricted local processes; exact condition-bound image/action replay. '
                 'No external provider, model interpretation, target/reference read or scoring.',
    }
    return body, receipt


def _matched_boundaries(boundaries, count):
    need(len(boundaries) == count, 'Complete expected boundary set required')
    shared = ('schema', 'limits', 'sandbox', 'client_sha256', 'python', 'source')
    baseline = {key: boundaries[0][key] for key in shared}
    need(all({key: b[key] for key in shared} == baseline for b in boundaries),
         'Matched client/interpreter/limits/source/sandbox required')
    need(all(b['sandbox'] == 'macos' for b in boundaries), 'Restricted collection rejects protocol-only diagnostics')
    need(len({b['episode_id'] for b in boundaries}) == count and len({b['workspace'] for b in boundaries}) == count and
         len({b['code_path'] for b in boundaries}) == count,
         'Fresh distinct process/context identities required across every condition and fold')


def _write_collection(output, body, receipt):
    V.write_new(output / 'probabilities.json', body)
    V.write_new(output / 'TRANSPORT_COMPLETE.json', T.encode(receipt))


def collect(condition, packets, sessions, output):
    """Collect one exact seven-fold condition after restricted transport replay."""
    body, receipt = _prepare(condition, packets, sessions)
    output = V.fresh(output)
    _write_collection(output, body, receipt)
    return receipt


def collect_matched(packets, sessions_by_condition, output):
    """Collect three matched conditions, each on the same original 140 cases."""
    need(type(sessions_by_condition) is dict and set(sessions_by_condition) == set(C.CONDITIONS),
         'Exactly all three declared observation conditions required')
    need(all(type(paths) is list and len(paths) == 7 for paths in sessions_by_condition.values()),
         'Exactly seven session paths per condition required')
    all_paths = [V.plain(path) for paths in sessions_by_condition.values() for path in paths]
    need(len(all_paths) == 21 and len({str(path.resolve()) for path in all_paths}) == 21,
         'Twenty-one distinct condition/fold session paths required')
    metadata = [_preflight(condition, packets, sessions_by_condition[condition]) for condition in C.CONDITIONS]
    _matched_boundaries([boundary for _, _, boundaries in metadata for boundary in boundaries], 21)
    prepared = {condition: _prepare(condition, packets, sessions_by_condition[condition])
                for condition in C.CONDITIONS}
    boundaries = [session['boundary'] for _, receipt in prepared.values() for session in receipt['sessions'].values()]
    _matched_boundaries(boundaries, 21)
    receipt = {
        'schema': 'neural034-matched-modality-transport-collection/v1', 'status': 'complete_unscored',
        'conditions': list(C.CONDITIONS), 'folds_per_condition': 7, 'queries_per_condition': 140,
        'unique_original_queries': 140, 'prediction_rows_across_conditions': 420,
        'matched_policy': {key: boundaries[0][key] for key in ('limits', 'sandbox', 'client_sha256', 'python', 'source')},
        'submissions': {condition: item[1]['submission'] for condition, item in prepared.items()},
        'source': source_identity(), 'restricted_local_process_transport': True,
        'provider_context_qualified': False, 'provider_delivery_qualified': False,
        'scientific_qualification': False, 'score': None,
        'scope': 'Same task, seven mice and original 140 cases under three observation conditions; '
                 'equal client source and per-fold budgets, fresh local processes. '
                 'No model/provider-context, difficulty, causal neural contribution or scientific-result claim.',
    }
    output = V.fresh(output)
    for condition, (body, per_condition) in prepared.items():
        directory = output / condition
        directory.mkdir(mode=0o700)
        _write_collection(directory, body, per_condition)
    V.write_new(output / 'MATCHED_COMPLETE.json', T.encode(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('fold')
    run.add_argument('--condition', choices=C.CONDITIONS, required=True)
    run.add_argument('--fold', type=int, choices=V.FOLDS, required=True)
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
    gather.add_argument('--condition', choices=C.CONDITIONS, required=True)
    gather.add_argument('--packets', nargs=7, type=Path, required=True)
    gather.add_argument('--sessions', nargs=7, type=Path, required=True)
    gather.add_argument('--output', type=Path, required=True)
    matched = sub.add_parser('collect-matched')
    matched.add_argument('--packets', nargs=7, type=Path, required=True)
    matched.add_argument('--combined-sessions', nargs=7, type=Path, required=True)
    matched.add_argument('--calcium-sessions', nargs=7, type=Path, required=True)
    matched.add_argument('--behavior-sessions', nargs=7, type=Path, required=True)
    matched.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _, _, inputs, ids = V.dependencies()
        if args.command == 'fold':
            packet = V.Packet(args.packet, args.fold, inputs[f'fold-{args.fold:02d}'], ids[args.fold])
            limits = Limits(args.max_actions, args.max_images, args.max_output_bytes, args.wall_seconds)
            result = run_fold(packet, args.output, args.client, condition=args.condition,
                              python=args.python, sandbox=args.sandbox, limits=limits)
            return 0 if result['status'] == 'complete_unscored' else 2
        packets = [V.Packet(path, fold, inputs[f'fold-{fold:02d}'], ids[fold])
                   for fold, path in zip(V.FOLDS, args.packets)]
        if args.command == 'collect':
            collect(args.condition, packets, args.sessions, args.output)
        else:
            collect_matched(packets, {'combined_calcium_behavior_v1': args.combined_sessions,
                                     'calcium_only_v1': args.calcium_sessions,
                                     'behavior_only_v1': args.behavior_sessions}, args.output)
        return 0
    except (ValueError, OSError, KeyError, TypeError, EOFError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

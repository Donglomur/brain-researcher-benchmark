"""Operator-owned, bounded image/action transport. No provider or model invocation."""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import struct
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
PREFIX = struct.Struct('!II')  # JSON bytes, then PNG bytes; input PNG length must be zero.
PNG_MAX = 4 * 1024 * 1024
HEADER_MAX = 32768
RESERVE = 1024  # Terminal notification, never a silently discarded answer.
LEGACY_PROFILE = 'legacy400'
FULL32_PROFILE = 'erp-full32-visual-v1'


def load_viewer():
    root = Path(globals().get('IMPLEMENTATIONS_ROOT', HERE.parent))
    pins = json.loads((HERE / 'SOURCE_BINDINGS.json').read_text())['members']
    for relative, pin in pins.items():
        body = (root / relative).read_bytes()
        if len(body) != pin['bytes'] or hashlib.sha256(body).hexdigest() != pin['sha256']:
            raise ValueError('Viewer dependency pin mismatch')
    path = root / 'visual-viewer-v1/viewer.py'
    spec = importlib.util.spec_from_file_location('transport_viewer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v = load_viewer()


def load_process_owner():
    # Trusted helper only; the participant never receives this source or path.
    path = Path(globals().get('IMPLEMENTATIONS_ROOT', HERE.parent)).parents[3] / 'benchmarks/shared/viewer-process-ownership-v1/owned_exit.py'
    body = v.read_regular(path, 65536)
    if len(body) != 8088 or hashlib.sha256(body).hexdigest() != 'd1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426':
        raise ValueError('Process ownership helper source mismatch')
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('viewer_owned_exit', loader=None))
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


owner = load_process_owner()


def load_profile_successor(*, budget=None):
    """The accepted metadata restriction is selected only for full32."""
    path = Path(globals().get('IMPLEMENTATIONS_ROOT', HERE.parent)) / 'full32-paired-runtime-v1/profile_successor.py'
    body = v.read_regular(path, 4096, budget=budget)
    v.need(len(body) == 2083 and v.digest(body) == '2dbd9c27c8e522880c095fc4b8f7ea12132538a07fc29c83e7fcbce5623689a4',
           'Full32 sandbox metadata policy source mismatch')
    return v.load_module('full32_visual_profile_successor', path, body)


@dataclass(frozen=True)
class Limits:
    max_actions: int = 128
    max_images: int = 32
    max_output_bytes: int = 128 * 1024 * 1024
    wall_seconds: float = 300

    def validate(self):
        v.need(type(self.max_actions) is int and 2 <= self.max_actions <= v.MAX_ACTIONS, 'Actions must be 2..128')
        v.need(type(self.max_images) is int and 1 <= self.max_images < self.max_actions, 'Images must be 1..actions-1')
        v.need(type(self.max_output_bytes) is int and PNG_MAX + HEADER_MAX + RESERVE <= self.max_output_bytes <= 512 * 1024 * 1024,
               'Output cap must fit an initial image and be at most 512 MiB')
        v.need(type(self.wall_seconds) in (int, float) and 0 < self.wall_seconds <= 3600, 'Deadline must be within one hour')


class WireFailure(Exception):
    def __init__(self, reason, captured=b''):
        super().__init__(reason)
        self.reason, self.captured = reason, captured


def wire(header, image=b''):
    body = v.encode(header)
    v.need(len(body) <= HEADER_MAX and len(image) <= PNG_MAX, 'Response exceeds framing bound')
    return PREFIX.pack(len(body), len(image)) + body + image


def unpack(raw, inbound=False):
    v.need(len(raw) >= PREFIX.size, 'Missing frame prefix')
    hsize, isize = PREFIX.unpack(raw[:PREFIX.size])
    v.need(0 < hsize <= (v.MAX_REQUEST if inbound else HEADER_MAX), 'Invalid header length')
    v.need(isize == 0 if inbound else 0 <= isize <= PNG_MAX, 'Invalid image length')
    v.need(len(raw) == PREFIX.size + hsize + isize, 'Frame length mismatch')
    return v.decode(raw[PREFIX.size:PREFIX.size + hsize]), raw[PREFIX.size + hsize:]


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
                part = os.read(fd, size - len(captured))
            except BlockingIOError:
                continue
            except WireFailure as error:
                raise WireFailure(error.reason, bytes(captured)) from None
            if not part:
                raise WireFailure('transport_eof', bytes(captured))
            captured.extend(part)

    read_to(PREFIX.size)
    hsize, isize = PREFIX.unpack(captured)
    if not 0 < hsize <= v.MAX_REQUEST or isize != 0:
        # Never allocate/read an attacker-declared unbounded payload.
        raise WireFailure('invalid_frame_length', bytes(captured))
    read_to(PREFIX.size + hsize)
    return bytes(captured)


def write_frame(fd, body, deadline):
    count = 0
    try:
        while count < len(body):
            wait_fd(fd, selectors.EVENT_WRITE, deadline)
            try:
                count += os.write(fd, body[count:])
            except BlockingIOError:
                continue
    except (BrokenPipeError, OSError, WireFailure):
        raise WireFailure('output_not_delivered', body[:count]) from None


def projection(result):
    """Copy only the viewer's documented fields; PNG bytes are their own frame part."""
    status = result['status']
    if status == 'rendered':
        v.need(set(result) == {'status', 'display', 'remaining_actions', 'image'}, 'Unexpected viewer projection')
        display = result['display']
        permitted = {'record', 'start_sample', 'stop_sample', 'units_per_division', 'channels', 'display_filter',
                     'sampling_hz', 'start_ms', 'stop_ms_exclusive', 'last_sample_ms', 'units', 'positive', 'renderer'}
        v.need(set(display) in (permitted, permitted | {'demonstration_target'}), 'Unexpected display metadata')
        v.need(display['record'] != 'query' or 'demonstration_target' not in display, 'Query label prohibited')
        v.need(result['image']['mime_type'] == 'image/png', 'Only PNG is permitted')
        png = base64.b64decode(result['image']['base64'], validate=True)
        v.need(png.startswith(b'\x89PNG\r\n\x1a\n'), 'PNG signature required')
        return {'status': status, 'display': display, 'remaining_actions': result['remaining_actions'],
                'image': {'mime_type': 'image/png', 'bytes': len(png)}}, png
    if status == 'rejected':
        v.need(set(result) == {'status', 'error', 'remaining_actions'}, 'Unexpected rejection fields')
        return dict(result), b''
    v.need(status in ('valid_unscored', 'invalid_response') and set(result) == {'status', 'response_sha256', 'terminal'},
           'Unexpected terminal fields')
    return dict(result), b''


def profile_fields(dataset, *, budget=None):
    """Only the static display commitment crosses the participant boundary."""
    profile = v.profile_name(dataset)
    if profile == LEGACY_PROFILE:
        return {}
    v.need(profile == FULL32_PROFILE and len(dataset['rows']) == 6400, 'Complete explicit full32 visual profile')
    return {'profile': profile, 'profile_commitment': v.profile_commitment(dataset, budget=budget)}


def boundary_manifest(limits, sandbox, client, episode_id, profile, dataset=None, *, budget=None):
    manifest = {'schema': 'neural077_visual_transport_v1', 'episode_id': episode_id,
            'limits': asdict(limits), 'sandbox': sandbox, 'client_sha256': v.digest(v.read_regular(Path(client), 1048576, budget=budget)),
            'fresh_process_per_query': True, 'provider_context_qualified': False,
            'provider_image_capacity_qualified': False, 'performance_claim': 'none',
            'sandbox_profile_sha256': v.digest(profile.encode()) if profile else None,
            'implementation_sha256': {name: v.digest(v.read_regular(HERE / name, 131072, budget=budget))
                                      for name in ('transport.py', 'SOURCE_BINDINGS.json')}}
    binding = profile_fields(dataset, budget=budget) if dataset is not None else {}
    if binding:
        # Operator evidence only. This dictionary is never put in ready_header.
        manifest.update(binding, packet_sha256=dataset['packet'], client_path=str(Path(client).resolve()))
    return manifest


def ready_header(session, limits, episode_id, *, budget=None):
    header = {'status': 'ready', 'episode_id': episode_id, 'trial_id': session.query['trial_id'], 'prompt': session.prompt,
            'actions': v.decode(v.read_regular(v.HERE / 'actions.schema.json', 131072, budget=budget)),
            'limits': dict(asdict(limits), max_request_bytes=v.MAX_REQUEST, max_image_bytes=PNG_MAX),
            'instructions': 'Use only the declared viewer actions. Image parts are PNG content, not text. '
                            'The first finalize is terminal. No query feedback or other-query context is available.'}
    header.update(profile_fields(getattr(session, 'dataset', {}), budget=budget))
    return header


def sandbox_profile(script, *, visual_profile=LEGACY_PROFILE, budget=None):
    """macOS scripted-client boundary; not a remote-provider or hostile-kernel proof."""
    v.need(sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').exists(), 'macOS sandbox-exec required')
    v.need(visual_profile in (LEGACY_PROFILE, FULL32_PROFILE), 'Unknown explicit sandbox visual profile')
    script = Path(script).resolve()
    quoted = json.dumps(str(script))
    base = ('(version 1) (deny default) (deny sysctl* process-info* network* process-fork) '
            '(allow process-info* (target self)) (allow process-exec) (allow file-read-metadata) '
            '(allow sysctl-read (sysctl-name "kern.ostype") (sysctl-name "kern.osrelease") '
            '(sysctl-name "kern.version") (sysctl-name "kern.hostname") (sysctl-name "hw.machine")) '
            '(allow file-read-data (literal "/") (subpath "/System") (subpath "/usr") '
            '(subpath "/Library/Frameworks") (literal "/dev/null") (literal "/dev/urandom") '
            '(literal "/dev/random") (literal ' + quoted + '))')
    return load_profile_successor(budget=budget).successor_profile(base, script) if visual_profile == FULL32_PROFILE else base


class Journal:
    def __init__(self, path):
        self.path, self.previous, self.sequence = path, '0' * 64, 0
        path.mkdir(mode=0o700)

    def record(self, direction, body, complete=True):
        name = f'{self.sequence:04d}-{direction}.bin'
        v.write_new(self.path / name, body)
        event = {'sequence': self.sequence, 'direction': direction, 'file': name,
                 'bytes': len(body), 'sha256': v.digest(body), 'complete': complete,
                 'previous_sha256': self.previous}
        encoded = v.encode(event)
        v.write_new(self.path / f'{self.sequence:04d}.json', encoded)
        self.previous = v.digest(encoded)
        self.sequence += 1


def run_episode(dataset, ordinal, mode, output, client, python=sys.executable,
                sandbox='macos', limits=None, client_launcher=None):
    """Spawn one trusted bridge/script. Participant requests cannot select these arguments."""
    owner.preflight()
    limits = limits or Limits()
    limits.validate()
    v.need(not profile_fields(dataset) or mode == 'four_demo', 'Full32 visual profile requires unchanged four demonstrations')
    client, python = Path(client).resolve(strict=True), Path(python).resolve(strict=True)
    profile = sandbox_profile(client, visual_profile=v.profile_name(dataset)) if sandbox == 'macos' else None
    v.need(sandbox in ('macos', 'protocol_only'), 'Unknown sandbox mode')
    session = v.Session(dataset, ordinal, mode, output)
    journal = Journal(session.output / 'transport')
    episode_id = uuid.uuid4().hex
    manifest = boundary_manifest(limits, sandbox, client, episode_id, profile, dataset=dataset)
    v.write_new(journal.path / 'MANIFEST.json', v.encode(manifest))
    if profile:
        v.write_new(journal.path / 'sandbox.sb', profile.encode())
    deadline = time.monotonic() + limits.wall_seconds
    started, images, output_bytes = time.monotonic(), 0, 0
    child, reason, terminal, forced_stop = None, None, None, False
    observer, cleanup = None, None

    def send(header, png=b''):
        nonlocal output_bytes, images
        body = wire(header, png)
        v.need(output_bytes + len(body) <= limits.max_output_bytes, 'Output accounting overflow')
        try:
            write_frame(child.stdin.fileno(), body, deadline)
        except WireFailure as error:
            journal.record('out', error.captured, complete=False)
            raise
        journal.record('out', body)
        output_bytes += len(body)
        images += bool(png)

    try:
        with tempfile.TemporaryDirectory(prefix='neural077-client-') as cwd:
            command = [str(python), '-I', '-S', '-B', str(client)]
            if profile:
                command = ['/usr/bin/sandbox-exec', '-p', profile] + command
            # No packet/output paths, credentials, parent environment or inherited handles.
            # Only trusted operator code may supply this launcher. The provider
            # route is explicitly protocol_only, never a macOS sandbox claim.
            if client_launcher is None:
                child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, cwd=cwd, env={'LANG': 'C', 'LC_ALL': 'C'},
                                         close_fds=True, start_new_session=True)
            else:
                v.need(sandbox == 'protocol_only', 'Trusted provider launcher is not sandboxed')
                child = client_launcher(command, cwd)
                v.need(isinstance(child, subprocess.Popen), 'Owned trusted child required')
            observer = owner.ExitObserver(child)
            os.set_blocking(child.stdout.fileno(), False)
            os.set_blocking(child.stdin.fileno(), False)
            initial, png = projection(session.handle(b'{"action":"inspect"}'))
            initial['remaining_actions'] = limits.max_actions - session.sequence
            header = ready_header(session, limits, episode_id)
            header['initial'] = initial
            send(header, png)
            while not session.closed:
                try:
                    raw = read_frame(child.stdout.fileno(), deadline)
                except WireFailure as error:
                    journal.record('in', error.captured, complete=False)
                    raise
                journal.record('in', raw)
                # read_frame bounded the payload; viewer owns JSON/action validation.
                request_bytes = raw[PREFIX.size:]
                try:
                    request = v.decode(request_bytes)
                    v.transition(session.state, request, mode)
                    render_requested = request['action'] != 'finalize'
                except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
                    render_requested = False
                reason = None
                if session.sequence >= limits.max_actions:
                    reason = 'action_limit'
                elif render_requested and images >= limits.max_images:
                    reason = 'image_limit'
                elif render_requested and output_bytes + PNG_MAX + HEADER_MAX + RESERVE > limits.max_output_bytes:
                    reason = 'output_byte_limit'
                if reason:
                    send({'status': 'closed', 'error': reason, 'terminal': True})
                    raise WireFailure(reason)
                projected, png = projection(session.handle(request_bytes))
                projected['remaining_actions'] = limits.max_actions - session.sequence if not session.closed else 0
                # Remaining actions is transport-owned; final does not include this field in viewer API.
                if session.closed:
                    projected.pop('remaining_actions')
                send(projected, png)
            terminal = v.decode((session.output / 'FINAL.json').read_bytes())['status']
            if not observer.wait(min(deadline, time.monotonic() + 2.0)):
                raise WireFailure('client_did_not_exit')

    except WireFailure as error:
        reason = error.reason
    except Exception:
        # No exception/path/stderr reflection to the participant.
        reason = 'operator_failure'
    finally:
        if child is not None:
            cleanup = owner.stop_and_reap(child, observer, time.monotonic() + 2.0)
            forced_stop = not cleanup['exit_observed_before_stop']
            if not cleanup['cleanup_complete'] or cleanup['returncode'] != 0 or forced_stop:
                reason = reason or 'client_cleanup_or_exit_unverified'
            child.stdin.close()
            child.stdout.close()
        if reason:
            session.closed = True
            if not (session.output / 'FAILED.json').exists():
                v.write_new(session.output / 'FAILED.json', v.encode({'reason': reason, 'last_action_sha256': session.previous}))
        receipt = {'schema': 'neural077_transport_end_v1', 'status': terminal if terminal and not reason else 'failed',
                   'reason': reason, 'messages': journal.sequence, 'last_message_sha256': journal.previous,
                   'manifest_sha256': v.digest(v.encode(manifest)), 'images': images, 'output_bytes': output_bytes,
                   'elapsed_seconds': time.monotonic() - started,
                   'client_exit_code': child.returncode if child is not None else None,
                   'client_forced_stop': forced_stop, 'process_ownership': cleanup,
                   'viewer_final_sha256': v.digest((session.output / 'FINAL.json').read_bytes())
                       if (session.output / 'FINAL.json').exists() else None,
                   'scoring_performed': False}
        v.write_new(journal.path / 'END.json', v.encode(receipt))
    return receipt


def audit_transport(path, dataset, ordinal, mode, *, budget=None):
    """Bind complete exact transport messages to the existing viewer action/frame audit."""
    path = Path(path)
    transport = path / 'transport'
    manifest = v.decode(v.read_regular(transport / 'MANIFEST.json', HEADER_MAX, budget=budget))
    end = v.decode(v.read_regular(transport / 'END.json', HEADER_MAX, budget=budget))
    binding = profile_fields(dataset, budget=budget)
    v.need(not binding or mode == 'four_demo', 'Full32 visual profile requires unchanged four demonstrations')
    expected_binding = dict(binding, packet_sha256=dataset['packet']) if binding else {}
    v.need({key: manifest[key] for key in ('profile', 'profile_commitment', 'packet_sha256') if key in manifest}
           == expected_binding, 'Transport profile or operator packet binding mismatch')
    if binding:
        client_path = manifest.get('client_path')
        v.need(type(client_path) is str and Path(client_path).is_absolute() and '..' not in Path(client_path).parts,
               'Explicit operator client path required for exact sandbox-policy audit')
    else:
        v.need('client_path' not in manifest, 'Legacy transport does not admit full32 client-path field')
    limits = Limits(**manifest['limits']); limits.validate()
    v.need(manifest['implementation_sha256'] == {name: v.digest(v.read_regular(HERE / name, 131072, budget=budget))
           for name in ('transport.py', 'SOURCE_BINDINGS.json')}, 'Transport implementation mismatch')
    v.need(end['status'] == 'valid_unscored' and end['reason'] is None and not (path / 'FAILED.json').exists(), 'Transport did not complete')
    v.need(end['client_exit_code'] == 0 and end['client_forced_stop'] is False, 'Client did not close successfully')
    cleanup = end.get('process_ownership', {})
    v.need(cleanup.get('cleanup_complete') is True and cleanup.get('leader_unreaped_before_signal') is True and cleanup.get('exit_observed_before_stop') is True and cleanup.get('reaped') is True and cleanup.get('returncode') == 0 and cleanup.get('group_absence_observed') is True, 'Owned cleanup receipt required')
    v.need(end['manifest_sha256'] == v.digest(v.encode(manifest)), 'Manifest mismatch')
    v.need(manifest['sandbox'] in ('macos', 'protocol_only'), 'Unknown recorded sandbox')
    if manifest['sandbox'] == 'macos':
        recorded_policy = v.read_regular(transport / 'sandbox.sb', HEADER_MAX, budget=budget)
        v.need(v.digest(recorded_policy) == manifest['sandbox_profile_sha256'], 'Sandbox policy mismatch')
        if binding:
            v.need(recorded_policy == sandbox_profile(client_path, visual_profile=FULL32_PROFILE, budget=budget).encode(),
                   'Exact full32 metadata-restricted sandbox policy required')
    else:
        v.need(manifest['sandbox_profile_sha256'] is None, 'Unexpected sandbox policy')
    final_raw = v.read_regular(path / 'FINAL.json', HEADER_MAX, budget=budget)
    v.need(end['viewer_final_sha256'] == v.digest(final_raw), 'Final binding mismatch')
    v.audit_session(path, dataset, ordinal, mode, budget=budget)
    final = v.decode(final_raw)
    actions = final['actions']
    v.need(2 <= actions <= limits.max_actions and end['messages'] == 2 * actions - 1, 'Message/action count mismatch')
    expected_names = {'MANIFEST.json', 'END.json'} | ({'sandbox.sb'} if manifest['sandbox'] == 'macos' else set())
    previous, images, total_output = '0' * 64, 0, 0
    prompt = v.scientific_prompt(dataset['rows'][ordinal]['trial_id'], mode)
    class Prompt:
        pass
    context = Prompt(); context.prompt = prompt; context.query = dataset['rows'][ordinal]; context.dataset = dataset
    action_index, action = None, None
    for sequence in range(end['messages']):
        direction = 'out' if sequence % 2 == 0 else 'in'
        name = f'{sequence:04d}-{direction}.bin'
        expected_names.update((name, f'{sequence:04d}.json'))
        event_raw = v.read_regular(transport / f'{sequence:04d}.json', HEADER_MAX, budget=budget)
        event = v.decode(event_raw)
        body = v.read_regular(transport / name, PNG_MAX + HEADER_MAX + PREFIX.size, budget=budget)
        v.need(event == {'sequence': sequence, 'direction': direction, 'file': name, 'bytes': len(body),
                        'sha256': v.digest(body), 'complete': True, 'previous_sha256': previous}, 'Transport chain mismatch')
        previous = v.digest(event_raw)
        index = (sequence + 1) // 2
        if index != action_index:
            action = v.decode(v.read_regular(path / f'action-{index:04d}.json', HEADER_MAX, budget=budget))
            action_index = index
        if direction == 'in':
            hsize, isize = PREFIX.unpack(body[:PREFIX.size])
            v.need(0 < hsize <= v.MAX_REQUEST and isize == 0 and len(body) == PREFIX.size + hsize, 'Input frame mismatch')
            v.need(body[PREFIX.size:] == base64.b64decode(action['request_base64'], validate=True), 'Action/wire mismatch')
            continue
        header, png = unpack(body)
        total_output += len(body); images += bool(png)
        if action['status'] == 'rendered':
            expected_png = v.read_regular(path / action['detail']['frame'], PNG_MAX, budget=budget)
            projected = {'status': 'rendered', 'display': action['detail']['display'],
                         'remaining_actions': limits.max_actions - index - 1,
                         'image': {'mime_type': 'image/png', 'bytes': len(expected_png)}}
        elif action['status'] == 'rejected':
            expected_png = b''
            projected = {'status': 'rejected', 'error': 'Invalid action or parameters', 'remaining_actions': limits.max_actions - index - 1}
        else:
            expected_png = b''
            projected = {'status': 'valid_unscored', 'response_sha256': final['response_sha256'], 'terminal': True}
        if sequence == 0:
            expected = ready_header(context, limits, manifest['episode_id'], budget=budget); expected['initial'] = projected
        else:
            expected = projected
        v.need(header == expected and png == expected_png, 'Participant response projection mismatch')
    v.need(set(p.name for p in transport.iterdir()) == expected_names, 'Unexpected/missing transport artifact')
    v.need(previous == end['last_message_sha256'] and images == end['images'] <= limits.max_images and
           total_output == end['output_bytes'] <= limits.max_output_bytes, 'Transport totals mismatch')
    return end


def collect(packet, sessions, mode, output, implementation_root=None, *,
            profile=LEGACY_PROFILE, manifest_pin=None, condition=None, budget=None):
    v.need((profile == LEGACY_PROFILE and condition is None)
           or (profile == FULL32_PROFILE and mode == 'four_demo'
               and condition in ('visual_direct_four_demo', 'visual_program_four_demo')),
           'Explicit full32 visual arm condition required; legacy condition remains the viewer mode')
    dataset = v.source(packet, implementation_root, profile=profile, manifest_pin=manifest_pin, budget=budget)
    try:
        sessions, output = Path(sessions), Path(output)
        names = [v.session_name(dataset, i) for i in range(v.collection_count(dataset))]
        v.need(sorted(p.name for p in sessions.iterdir()) == names, 'Exactly the complete profile sessions required')
        audited = [audit_transport(sessions / name, dataset, i, mode, budget=budget) for i, name in enumerate(names)]
        configurations = []
        for name in names:
            manifest = v.decode(v.read_regular(sessions / name / 'transport/MANIFEST.json', HEADER_MAX, budget=budget))
            configurations.append({key: value for key, value in manifest.items() if key != 'episode_id'})
        v.need(all(config == configurations[0] for config in configurations), 'Mixed transport/client/limit configurations')
        if profile == FULL32_PROFILE:
            expected_sandbox = 'macos' if condition == 'visual_program_four_demo' else 'protocol_only'
            v.need(configurations[0]['sandbox'] == expected_sandbox, 'Selected visual arm transport boundary mismatch')
        # The maintained viewer collector owns complete response admission.
        receipt = v.collect(packet, sessions, mode, output, implementation_root,
                            profile=profile, manifest_pin=manifest_pin, budget=budget)
        transport_receipt = {'schema': 'neural077_transport_collection_v1', 'queries': len(audited),
                             'status': 'complete_unscored_transport_collection', 'condition': condition or mode,
                             'submission_sha256': receipt['submission_sha256'], 'scoring_performed': False,
                             'configuration_sha256': v.digest(v.encode(configurations[0])),
                             'performance_claim': 'none', 'provider_qualification': 'not_established'}
        binding = profile_fields(dataset, budget=budget)
        if binding:
            transport_receipt.update(binding, packet_sha256=dataset['packet'])
        v.write_new(output / 'TRANSPORT_COMPLETE.json', v.encode(transport_receipt))
        return transport_receipt
    finally:
        v.close_source(dataset)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('episode', 'campaign', 'collect'):
        command = sub.add_parser(name)
        command.add_argument('--packet', type=Path, required=True)
        command.add_argument('--implementation-root', type=Path)
        command.add_argument('--profile', choices=(LEGACY_PROFILE, FULL32_PROFILE), default=LEGACY_PROFILE)
        command.add_argument('--manifest-bytes', type=int)
        command.add_argument('--manifest-sha256')
        command.add_argument('--mode', choices=v.MODES, required=True)
        command.add_argument('--output', type=Path, required=True)
        if name == 'collect':
            command.add_argument('--sessions', type=Path, required=True)
            command.add_argument('--condition', choices=('visual_direct_four_demo', 'visual_program_four_demo'))
        else:
            command.add_argument('--client', type=Path, required=True)
            command.add_argument('--python', default=sys.executable)
            command.add_argument('--sandbox', choices=('macos', 'protocol_only'), default='macos')
            for option, default, kind in (('max-actions', 128, int), ('max-images', 32, int),
                                           ('max-output-bytes', 128 * 1024 * 1024, int), ('wall-seconds', 300, float)):
                command.add_argument('--' + option, type=kind, default=default)
            if name == 'episode':
                command.add_argument('--ordinal', type=int, required=True)
    args = vars(parser.parse_args(argv))
    name = args.pop('command')
    try:
        extent, digest = args.pop('manifest_bytes'), args.pop('manifest_sha256')
        v.need((extent is None) == (digest is None), 'Both exact manifest pin fields are required')
        args['manifest_pin'] = None if extent is None else {'bytes': extent, 'sha256': digest}
        if name == 'collect':
            result = collect(**args)
        else:
            limits = Limits(**{key: args.pop(key) for key in asdict(Limits())}); limits.validate()
            dataset = v.source(args.pop('packet'), args.pop('implementation_root'),
                               profile=args.pop('profile'), manifest_pin=args.pop('manifest_pin'))
            try:
                if name == 'episode':
                    result = run_episode(dataset=dataset, limits=limits, **args)
                else:
                    root = args.pop('output'); root.mkdir(mode=0o700, parents=False, exist_ok=False)
                    names = [v.session_name(dataset, i) for i in range(v.collection_count(dataset))]
                    receipts = [run_episode(dataset, i, output=root / item, limits=limits, **args) for i, item in enumerate(names)]
                    result = {'attempts': len(names), 'valid_unscored': sum(row['status'] == 'valid_unscored' for row in receipts),
                              'performance_claim': 'none', 'scoring_performed': False}
            finally:
                v.close_source(dataset)
        print(json.dumps(result, sort_keys=True))
        success = (result.get('status') == 'valid_unscored' if name == 'episode' else
                   result.get('valid_unscored') == result.get('attempts') if name == 'campaign' else
                   result.get('status') == 'complete_unscored_transport_collection')
        return 0 if success else 2
    except (ValueError, OSError, UnicodeError, KeyError, TypeError):
        print('Transport refused; inspect operator configuration or evidence.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

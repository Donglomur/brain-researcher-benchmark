"""Generated component controls; never public admission or provider qualification.

The sole positive fixture temporarily changes the in-memory test roster to two
epochs. Original source files/pins, production cap and public admission are not
patched. No provider, original packet, waveform renderer or model is used.
"""
from contextlib import contextmanager
from dataclasses import asdict
import importlib.util
import io
import os
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

SOURCE = Path(os.environ['N007_SENDER_SOURCE_ROOT'])
ROOT = Path(os.environ['N007_DEPENDENCY_ROOT'])
CONTROL = Path(os.environ['N007_CONTROL_ROOT'])
spec = importlib.util.spec_from_file_location('n007_generated_sender_control', SOURCE / 'client.py')
client = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = client
spec.loader.exec_module(client)
SECRET = 'GENERATED_COMPONENT_SECRET_0123456789'
CREATED_FIXTURE_ROOTS = []


def fixture_accounting():
    """Our creation paths never overwrite/delete; caller charges its own mutations.

    This remains callable after failure and includes partial fixture files. Every
    returned byte was written once by this fixture producer; no cleanup occurs.
    """
    files = [p for root in CREATED_FIXTURE_ROOTS for p in root.rglob('*') if p.is_file()]
    return {'fixture_roots': [str(root) for root in CREATED_FIXTURE_ROOTS],
            'created_file_bytes': sum(p.stat().st_size for p in files),
            'created_files': len(files), 'producer_overwrites': 0, 'producer_deletions': 0}


def config(runtime, case='development-001'):
    p = runtime['provider']
    b = p.Budget(max_turns=12000, max_images=1500, max_history_bytes=16384,
                 max_request_bytes=16384, max_response_bytes=4096,
                 max_total_provider_bytes=1048576, context_tokens=20000,
                 output_tokens=128, wall_seconds=30)
    return {'schema': 'neural007_viewer_provider_session_v1', 'root': str(ROOT),
            'integration_root': str(SOURCE), 'case_id': case, 'model': 'generated-control-model',
            'budget': asdict(b), 'source': runtime['source'], 'token_bound_source': None}


def private_dir(path):
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def limits(runtime):
    return runtime['transport'].Limits(max_actions=6000, max_images=3000,
                                       max_output_bytes=8388608, wall_seconds=35)


def png(pixel):
    def chunk(kind, raw):
        return struct.pack('!I', len(raw)) + kind + raw + struct.pack('!I', zlib.crc32(kind + raw) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0' + bytes(pixel))) + chunk(b'IEND', b''))


def response(p, action, ordinal):
    return p.encode({'object': 'response', 'id': 'resp_generated_' + str(ordinal),
                     'status': 'completed', 'error': None, 'incomplete_details': None,
                     'model': 'generated-control-model', 'tools': [], 'tool_choice': 'none',
                     'parallel_tool_calls': False, 'store': False, 'background': False,
                     'truncation': 'disabled', 'previous_response_id': None, 'conversation': None,
                     'max_output_tokens': 128,
                     'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                                 'content': [{'type': 'output_text', 'text': p.encode({'viewer_action': action}).decode()}]}],
                     'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}})


class FakeResponse:
    status = 200
    def __init__(self, raw):
        self.raw = io.BytesIO(raw)
        self.length = len(raw)
    def read(self, count):
        value = self.raw.read(min(count, 37))
        self.length -= len(value)
        return value
    def getheader(self, name, default=None):
        return 'identity'
    def close(self):
        pass


class FakeHTTPS:
    """Finite fake transport only; the unchanged real Sender owns all custody."""
    sock = None
    def __init__(self, owner, host, port, timeout, context):
        assert host == 'api.openai.com' and port == 443 and timeout > 0 and context.check_hostname
        self.owner = owner
    def set_debuglevel(self, level):
        assert level == 0
    def request(self, method, path, *, body, headers, encode_chunked):
        assert method == 'POST' and path == '/v1/responses' and not encode_chunked
        assert headers['Authorization'] == 'Bearer ' + SECRET
        self.owner.requests.append(body)
    def getresponse(self):
        assert self.owner.responses
        return FakeResponse(self.owner.responses.pop(0))
    def close(self):
        pass


class Factory:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
    def __call__(self, *args, **kwargs):
        return FakeHTTPS(self, *args, **kwargs)


@contextmanager
def generated_session(output_root, event_sink_failure=False):
    """Shared sender/admission fixture. Caller must never invoke public admit."""
    output_root = Path(output_root)
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    CREATED_FIXTURE_ROOTS.append(output_root)
    (output_root / 'GENERATED_COMPONENT_ONLY').write_text('Two synthetic epochs; fake HTTPS; no provider qualification.\n')
    runtime = client.load_runtime(ROOT, SOURCE)
    p, t = runtime['provider'], runtime['transport']
    tiny = {'development-001': 2, 'development-002': 2}
    with patch.object(client, 'CASES', tiny), patch.object(t.v, 'CASES', tiny), \
         patch.object(p.policy, 'pinned_module', return_value=t):
        cfg = config(runtime)
        tlimits = limits(runtime)
        case = 'development-001'
        packet = SimpleNamespace(case=case, epochs=2)
        ready = t.wire(t.ready_header(packet, tlimits, 'a' * 32))
        actions = [{'action': 'inspect'},
                   {'action': 'respond', 'epoch_id': case + '/00000', 'probabilities': [0.2] * 5},
                   {'action': 'epoch', 'index': 1},
                   {'action': 'respond', 'epoch_id': case + '/00001', 'probabilities': [0.2] * 5},
                   {'action': 'finish'}]
        def view(index, pixels):
            image = png(pixels)
            state = {'epoch': index, 'start_sample': index * 3000, 'stop_sample': (index + 1) * 3000,
                     'gain_uv': 50, 'channels': list(t.v.CHANNELS)}
            header = {'kind': 'view', 'mode': client.CONDITION, 'epoch_id': f'{case}/{index:05d}',
                      'state': state, 'clock_features': {key: 0 for key in t.v.CLOCK},
                      'sample_rate_hz': 100, 'signal_units': 'V', 'display_units': 'uV',
                      'image': {'mime_type': 'image/png', 'bytes': len(image)}}
            return t.wire(header, image)
        observations = [ready, view(0, (255, 0, 0)),
                        t.wire({'kind': 'response_accepted', 'epoch_id': case + '/00000', 'completed_epochs': 1}),
                        view(1, (0, 255, 0)),
                        t.wire({'kind': 'response_accepted', 'epoch_id': case + '/00001', 'completed_epochs': 2}),
                        t.wire({'kind': 'complete', 'case_id': case, 'epochs': 2})]
        provider_root, transport_root = output_root / 'provider', output_root / 'session'
        fd = private_dir(provider_root)
        factory = Factory([response(p, action, ordinal + 1) for ordinal, action in enumerate(actions)])
        output = io.BytesIO()
        original_write = client.write_new
        def controlled_write(directory, name, raw, cap=32768):
            if event_sink_failure and name == '000001.json':
                raise OSError('GENERATED_COMPONENT_ONLY event sink refusal')
            return original_write(directory, name, raw, cap)
        try:
            with patch.object(client, 'write_new', side_effect=controlled_write):
                success = client.run_session(runtime, cfg, SECRET, fd, io.BytesIO(b''.join(observations)), output,
                                             lambda request, deadline: 1000, http_factory=factory)
        finally:
            os.close(fd)
        if event_sink_failure:
            assert not success and len(factory.requests) == 1 and output.getvalue() == b''
        else:
            assert success and not factory.responses and len(factory.requests) == 5
            assert output.getvalue() == b''.join(t.wire(action) for action in actions)
        transport_root.mkdir(mode=0o700)
        (transport_root / 'transport').mkdir(mode=0o700)
        wire = observations[0] if event_sink_failure else observations[0] + b''.join(
            t.wire(action) + observation for action, observation in zip(actions, observations[1:]))
        (transport_root / 'transport/wire.bin').write_bytes(wire)
        (transport_root / 'BOUNDARY.json').write_bytes(p.encode({'limits': asdict(tlimits)}))
        end = p.decode((provider_root / 'CLIENT_END.json').read_bytes())
        assert all(end[key] is False for key in ('provider_capacity_qualified', 'provider_context_qualified',
                                                'scientific_qualification', 'token_bound_qualified'))
        yield client, runtime, provider_root, transport_root


class SenderControls(unittest.TestCase):
    def test_recorder_failure_withholds_prepared_action(self):
        with generated_session(CONTROL / 'sink_failure', event_sink_failure=True) as (_, runtime, root, _):
            end = runtime['provider'].decode((root / 'CLIENT_END.json').read_bytes())
            self.assertEqual(end['status'], 'failed_no_admission')
            self.assertEqual(end['turns'], 1)
            self.assertEqual(end['events'], 1)
            self.assertEqual([p.name for p in (root / 'events').iterdir()], ['000000.json'])
            self.assertTrue((root / 'turns/000000/HTTP.json').is_file())
            self.assertTrue((root / 'turns/000000/BRIDGE.json').is_file())

    def test_trusted_launcher_uses_only_explicit_descriptors(self):
        op_spec = importlib.util.spec_from_file_location('n007_generated_operator_control', SOURCE / 'operator.py')
        operator = importlib.util.module_from_spec(op_spec)
        op_spec.loader.exec_module(operator)
        runtime = client.load_runtime(ROOT, SOURCE)
        cfg = client.encode(config(runtime))
        folder = CONTROL / 'launcher_private'
        directory = private_dir(folder)
        CREATED_FIXTURE_ROOTS.append(folder)
        captured = {}
        class Child:
            stdin = io.BytesIO()
            stdout = io.BytesIO()
        def popen(argv, **options):
            captured.update(argv=argv, options=options,
                            inherited=[os.dup(fd) for fd in options['pass_fds']])
            return Child()
        try:
            with patch.object(operator.subprocess, 'Popen', side_effect=popen):
                operator.launch(['pinned-python', '-I', '-S', '-B', 'captured-client.py'], str(CONTROL),
                                SECRET.encode(), cfg, directory, runtime['transport'], time.monotonic() + 5)
            credential_fd, config_fd, custody_fd = captured['inherited']
            self.assertEqual(os.read(credential_fd, 4096), SECRET.encode())
            self.assertEqual(os.read(config_fd, 32768), cfg)
            self.assertEqual(os.fstat(custody_fd).st_ino, os.fstat(directory).st_ino)
            self.assertNotIn(SECRET, ' '.join(captured['argv']))
            self.assertEqual(captured['argv'][:4], ['pinned-python', '-I', '-B', 'captured-client.py'])
            self.assertEqual(captured['options']['env'], {'LANG': 'C', 'LC_ALL': 'C'})
            self.assertTrue(captured['options']['close_fds'])
            self.assertTrue(captured['options']['start_new_session'])
        finally:
            for fd in captured.get('inherited', []):
                os.close(fd)
            os.close(directory)

    def test_canonical_people_refused_before_any_callback(self):
        runtime = client.load_runtime(ROOT, SOURCE)
        p, t = runtime['provider'], runtime['transport']
        for case, epochs in client.CASES.items():
            folder = CONTROL / ('canonical_' + case)
            fd = private_dir(folder)
            CREATED_FIXTURE_ROOTS.append(folder)
            def forbidden(*args, **kwargs):
                raise AssertionError('Canonical capacity failure must precede bound and HTTP calls')
            try:
                frame = t.wire(t.ready_header(SimpleNamespace(case=case, epochs=epochs), limits(runtime), 'b' * 32))
                out = io.BytesIO()
                self.assertFalse(client.run_session(runtime, config(runtime, case), SECRET, fd, io.BytesIO(frame), out,
                                                    forbidden, http_factory=forbidden))
                self.assertEqual(out.getvalue(), b'')
            finally:
                os.close(fd)
            end = p.decode((folder / 'CLIENT_END.json').read_bytes())
            self.assertEqual(end['turns'], 0)
            self.assertEqual(list((folder / 'turns').iterdir()), [])
            events = [p.decode(path.read_bytes())['bridge'] for path in sorted((folder / 'events').iterdir())]
            self.assertEqual([event['event'] for event in events], ['ready', 'failed_no_further_action'])
            self.assertEqual(events[-1]['failure_stage'], 'canonical_full_history_image_capacity')

    def test_sender_ceiling_is_additional_and_token_oracle_is_not_invented(self):
        runtime = client.load_runtime(ROOT, SOURCE)
        cfg = config(runtime)
        cfg['budget']['max_request_bytes'] = 8388609
        cfg['budget']['max_total_provider_bytes'] = 16777216
        with self.assertRaisesRegex(ValueError, 'sender request ceiling'):
            client.checked_config(cfg, runtime)
        with self.assertRaisesRegex(ValueError, 'unqualified/unavailable'):
            client.external_bound(config(runtime))(b'{}', time.monotonic() + 10)

    def test_exact_request_context_rejects_wrong_person(self):
        value = {'model': 'generated-control-model', 'max_output_tokens': 128,
                 'input': [{'content': [{'text': client.encode({'case_id': 'development-002', 'epochs': 2670}).decode()}]}]}
        with self.assertRaisesRegex(ValueError, 'full-person prompt'):
            client.RequestAdapter(client.encode(value), 'development-001', 'generated-control-model', 128)


if __name__ == '__main__':
    unittest.main()

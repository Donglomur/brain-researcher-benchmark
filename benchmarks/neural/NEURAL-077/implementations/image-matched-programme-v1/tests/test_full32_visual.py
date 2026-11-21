"""Affected full32 visual controls, generated only; no model/provider/native run.

The coordinator supplies an authenticated complete staged implementation tree.
A test-only replacement of fixed asset data pins admits invented demonstrations;
all PacketSession/profile/source, action, image and submission validators remain
production functions. Per-case generated custody suppliers are documented in
admission_controls.py; they are never installed in production.
"""
import base64
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import importlib.util
import sys
HERE = Path(__file__).resolve().parent
sys.modules['test_visual_full32'] = sys.modules[__name__]
_spec = importlib.util.spec_from_file_location('generated_support', HERE/'generated_support.py')
g = importlib.util.module_from_spec(_spec)
sys.modules['generated_support'] = g
_spec.loader.exec_module(g)

ROOT = None
FIXTURES = None
ENV = {}
RUNTIME_EXPECTATIONS = {}


def configure(root, fixtures):
    global ROOT, FIXTURES
    ROOT, FIXTURES = Path(root).resolve(), Path(fixtures).resolve()


def setup_environment():
    if ENV:
        return ENV
    observed_runtime = None
    if RUNTIME_EXPECTATIONS:
        import platform
        import numpy as np
        if (platform.python_version(), np.__version__) != (RUNTIME_EXPECTATIONS['python'], RUNTIME_EXPECTATIONS['numpy']):
            raise ValueError('Runtime differs from the explicitly selected control versions')
        observed_runtime = {'python': platform.python_version(), 'numpy': np.__version__,
                            'executable': sys.executable, 'prefix': sys.prefix, 'numpy_origin': np.__file__}
    image = g.load('generated_full32_image_pair', ROOT / 'image-matched-programme-v1/pair.py')
    deps = image.dependencies(ROOT, profile=g.PROFILE)
    transport, viewer = deps['transport'], deps['transport'].v
    consumer = g.load('generated_full32_consumer', ROOT / 'full32-paired-benchmark-v1/consumer.py')
    profile = viewer._profile_dependency('profile', ROOT)
    _, modules = viewer.dependencies(ROOT)
    packet = g.Packet(FIXTURES / 'generated-packet', consumer)
    consumer.LEGACY_PINS = packet.legacy_pins
    original_profile_loader = viewer._profile_dependency
    def generated_asset_boundary(name, implementation_root=None, budget=None):
        module = original_profile_loader(name, implementation_root, budget)
        if name == 'consumer':
            module.LEGACY_PINS = packet.legacy_pins
        return module
    # Only external fixed asset descriptors change. Source loading/authentication
    # and all production PacketSession/profile checks execute unchanged.
    with patch.object(viewer, '_profile_dependency', generated_asset_boundary):
        dataset = viewer.source(packet.root, ROOT, profile=g.PROFILE, manifest_pin=packet.manifest_pin)
    client = g.load('generated_full32_visual_client', ROOT / 'visual-provider-pair-v1/visual_client.py')
    bridge = deps['bridge']
    codec = g.load('generated_full32_codec', ROOT / 'visual-provider-pair-v1/transfer_png.py')
    original = client.source(ROOT / 'waveform-provider-v1/client.py', client.ORIGINAL_SENDER)
    ENV.update(image=image, deps=deps, t=transport, v=viewer, consumer=consumer, profile=profile,
               validator=modules['validator'], packet=packet, data=dataset, client=client,
               bridge=bridge, codec=codec, original=original,
               generated_asset_boundary=generated_asset_boundary, runtime_versions=observed_runtime)
    return ENV


def charge_viewer_writes(viewer):
    original = viewer.write_new
    def tracked(path, body):
        if Path(path).suffix == '.png' and len(body) > 1024**2:
            raise AssertionError('Generated full32 PNG exceeds 1MiB fixture bound before write')
        g.charge_write(body)
        return original(path, body)
    return patch.object(viewer, 'write_new', tracked)


class VisualFull32Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = setup_environment()

    def test_01_complete_missing_duplicate_and_substituted_rosters(self):
        e = self.e; packet, consumer = e['packet'], e['consumer']
        with consumer.PacketSession(packet.root, packet.manifest_pin) as session:
            self.assertEqual(session.trial_ids, packet.ids)
        mutations = [packet.roster[:-1], [packet.roster[0]] + packet.roster[:-1]]
        substituted = copy.deepcopy(packet.roster)
        substituted[-1]['trial_id'] = 'q-' + 'f' * 32
        mutations.append(substituted)
        for index, rows in enumerate(mutations):
            with self.subTest(mutation=index):
                pin = packet.roster_variant(rows)
                if index < 2:
                    with self.assertRaises(ValueError):
                        consumer.PacketSession(packet.root, pin)
                else:
                    # An authenticated substitute roster cannot silently select
                    # the old span: exact query identity is checked lazily.
                    with consumer.PacketSession(packet.root, pin) as session:
                        with self.assertRaises(ValueError):
                            session.query_record('q-' + 'f' * 32)
        packet.restore()

    def test_02_lazy_one_query_same_four_demos_numeric_context_unchanged(self):
        e = self.e; packet, consumer, profile = e['packet'], e['consumer'], e['profile']
        donor = e['validator']
        donor_namespace = dict(donor.__dict__)
        donor_functions = {name: (donor_namespace[name], donor_namespace[name].__code__)
                           for name in ('validate', '_public_ids', '_read_candidate')}
        def donor_unchanged():
            self.assertEqual(set(donor.__dict__), set(donor_namespace))
            for name, value in donor_namespace.items():
                self.assertIs(donor.__dict__[name], value)
            for name, (function, code) in donor_functions.items():
                self.assertIs(getattr(donor, name), function)
                self.assertIs(getattr(donor, name).__code__, code)
        opened = []
        original = consumer.PacketSession._open
        def observed(session, name, size):
            opened.append(name)
            return original(session, name, size)
        with patch.object(consumer.PacketSession, '_open', observed):
            data = profile.source(packet.root, packet.manifest_pin, consumer, e['validator'])
            try:
                donor_unchanged()
                # Exact errors prove expected-roster admission runs before any
                # attempted candidate I/O; the nonexistent path alone would
                # otherwise be converted into the donor's generic file error.
                malformed = ((list(packet.ids[:-1]), 'Exactly 6400 expected opaque IDs required'),
                             ([packet.ids[0]] + list(packet.ids[:-1]), 'Sorted unique full32 opaque roster required'),
                             (list(reversed(packet.ids)), 'Sorted unique full32 opaque roster required'),
                             (list(packet.ids[:-1]) + ['development-001'], 'Sorted unique full32 opaque roster required'))
                for ids, message in malformed:
                    with self.assertRaises(donor.InvalidSubmission) as caught:
                        data['validator'].validate(FIXTURES/'never-created-roster-probe.npz', ids)
                    self.assertEqual(str(caught.exception), message)
                    donor_unchanged()
                self.assertEqual(len(data['rows']), 6400)
                self.assertFalse(any(name.startswith('queries/') for name in opened))
                first = data['rows'][7]
                self.assertIs(data['rows'][7], first)
                self.assertEqual(sum(name.startswith('queries/') for name in opened), 1)
                self.assertEqual(data['rows']._ordinal, 7)
                self.assertEqual(len(data['demos']), 4)
                self.assertEqual(data['demos'], data['_session'].demonstration_records())
                data['rows'][8]
                self.assertEqual(sum(name.startswith('queries/') for name in opened), 2)
                self.assertEqual(data['rows']._ordinal, 8)
                session = data['_session']
                direct = session.context(packet.ids[7], 'numeric_direct_four_demo')
                programme = session.context(packet.ids[7], 'numeric_program_four_demo')
                self.assertEqual(direct['prompt'].replace(consumer.NO_TOOLS, consumer.PROGRAMME_TOOLS), programme['prompt'])
                self.assertEqual(direct['context_sha256'], g.pin(direct['prompt'].encode())['sha256'])
                for invalid in (True, -1, 6400, slice(0, 1)):
                    with self.assertRaises(ValueError):
                        data['rows'][invalid]
            finally:
                profile.close(data)
            donor_unchanged()
            with self.assertRaises(ValueError):
                data['rows'][0]

    def test_03_real_initial_and_action_pixel_identity_lossless_codec(self):
        e = self.e; v, t, data, codec = e['v'], e['t'], e['data'], e['codec']
        sessions = []
        with charge_viewer_writes(v):
            for arm in ('direct', 'programme'):
                sessions.append(v.Session(data, 11, 'four_demo', FIXTURES / ('pixels-' + arm)))
            actions = ({'action': 'inspect'}, {'action': 'select', 'record': 'demo2'},
                       {'action': 'window', 'start_sample': -128, 'stop_sample': 256})
            for action in actions:
                pair = [t.projection(session.handle(v.encode(action))) for session in sessions]
                self.assertEqual(pair[0], pair[1])
                native = sessions[0].raster.render(sessions[0]._record(), sessions[0].state, sessions[0].mode)
                self.assertEqual(len(native), 3445148)
                original_png = pair[0][1]
                expected_compressed, expected_mapping = codec.encode_transport_image(native)
                self.assertEqual(original_png, expected_compressed)
                self.assertTrue(codec.verify_equivalence(native, original_png, expected_mapping))
                e.setdefault('generated_compression_samples', []).append(
                    {'native_bytes': len(native), 'retained_bytes': len(original_png),
                     'scope': 'generated fixture only; not cohort compression'})
                event = v.decode((sessions[0].output/f'action-{sessions[0].sequence-1:04d}.json').read_bytes())
                self.assertTrue(codec.verify_equivalence(native, original_png, event['detail']['encoding']))
                delivered, mapping = codec.encode_transport_image(original_png)
                self.assertTrue(codec.verify_equivalence(original_png, delivered, mapping))
                self.assertEqual(codec.scanlines(original_png), codec.scanlines(delivered))
                bad = copy.deepcopy(mapping); bad['scanlines']['sha256'] = '0' * 64
                with self.assertRaises(ValueError):
                    codec.verify_equivalence(original_png, delivered, bad)
            a = t.ready_header(sessions[0], t.Limits(), 'a' * 32)
            b = e['deps']['image_transport'].ready_header(sessions[1], t.Limits(), 'b' * 32)
            expected = dict(a, episode_id='b' * 32,
                            prompt=e['deps']['adapter'].programme_prompt(a['prompt']))
            self.assertEqual(b, expected)
            for session in sessions:
                response = v.encode({'trial_id': session.query['trial_id'], 'target_probability': 0.5}).decode()
                session.handle(v.encode({'action': 'finalize', 'response': response}))
        for session in sessions:
            v.audit_session(session.output, data, 11, 'four_demo')
        # The bounded decoder must reject framing corruption, truncated streams
        # and an otherwise valid PNG carrying more than the fixed scanline size.
        import zlib
        overlong = codec.SIGNATURE + codec.chunk(b'IHDR', codec.IHDR) + codec.chunk(
            b'IDAT', zlib.compress(b'\0' * (codec.SCAN_BYTES+1), 9)) + codec.chunk(b'IEND', b'')
        for bad in (original_png[:-1], original_png+b'extra', overlong):
            with self.assertRaises(ValueError):
                codec.scanlines(bad)
        # Preserve the legacy default renderer path without another on-disk
        # PNG: generated writes are captured in memory at the file boundary.
        query = dict(sessions[0].query, trial_id='development-001-'+'0'*24)
        legacy = {'rows': [query]*400, 'demos': data['demos'], 'packet': {'generated': 'legacy-branch'},
                  'parser': data['parser'], 'validator': data['validator']}
        saved = {}
        with patch.object(v, 'write_new', side_effect=lambda path, body: saved.__setitem__(str(path), body)):
            legacy_session = v.Session(legacy, 0, 'four_demo', FIXTURES/'legacy-render-branch')
            legacy_result = legacy_session.handle(v.encode({'action':'inspect'}))
        legacy_png = base64.b64decode(legacy_result['image']['base64'])
        raw = legacy_session.raster.render(query, legacy_session.state, 'four_demo')
        self.assertEqual(legacy_png, raw)
        self.assertEqual(len(legacy_png), 3445148)
        legacy_event = v.decode(saved[str(legacy_session.output/'action-0000.json')])
        self.assertNotIn('encoding', legacy_event['detail'])

    def test_04_profile_context_opaque_id_and_raw_leak_refusal(self):
        e = self.e; v, t, b = e['v'], e['t'], e['bridge']
        with charge_viewer_writes(v):
            session = v.Session(e['data'], 19, 'four_demo', FIXTURES / 'projection')
            projected, png = t.projection(session.handle(v.encode({'action': 'inspect'})))
        e['projection_session'] = session
        header = t.ready_header(session, t.Limits(), 'c' * 32); header['initial'] = projected
        binding = {'profile': g.PROFILE, 'profile_commitment': e['profile'].PROFILE_COMMITMENT,
                   'context_sha256': g.pin(session.prompt.encode())['sha256']}
        history, mapping = b.first_frame(header, png, session.query['trial_id'], e['codec'].encode_transport_image, **binding)
        self.assertTrue(history and mapping)
        self.assertNotIn('roster', json.dumps(header))
        for mutation in ('person', 'raw_channels', 'target', 'source_order', 'encoding'):
            bad = copy.deepcopy(header); bad['initial']['display'][mutation] = 'forbidden'
            with self.assertRaises(ValueError):
                b.first_frame(bad, png, session.query['trial_id'], e['codec'].encode_transport_image, **binding)
        for field in ('profile_commitment', 'context_sha256'):
            bad_binding = dict(binding); bad_binding[field] = 'f' * 64
            with self.assertRaises(ValueError):
                b.first_frame(header, png, session.query['trial_id'], e['codec'].encode_transport_image, **bad_binding)
        for profile, trial in (('legacy400', session.query['trial_id']),
                               (g.PROFILE, 'development-001-' + '0' * 24),
                               ('numeric_direct_four_demo', session.query['trial_id'])):
            with self.assertRaises(ValueError):
                b.identifier(trial, profile)
        bad = copy.deepcopy(header); bad['prompt'] += ' ' + e['packet'].ids[20]
        with self.assertRaises(ValueError):
            b.first_frame(bad, png, session.query['trial_id'], e['codec'].encode_transport_image, **binding)
        bad = copy.deepcopy(projected); bad['display']['demonstration_target'] = 1
        with self.assertRaises(ValueError):
            b.projection(bad, png, profile=g.PROFILE)

    def test_05_legacy_visual_and_numeric_defaults_remain_distinct(self):
        e = self.e; v, b, consumer = e['v'], e['bridge'], e['consumer']
        legacy = {'rows': [{'trial_id': 'development-001-' + format(i, '024x')} for i in range(400)]}
        self.assertEqual(v.profile_name(legacy), 'legacy400')
        self.assertEqual(v.collection_count(legacy), 400)
        self.assertEqual(v.session_name(legacy, 7), '007')
        self.assertEqual(v.session_name(e['data'], 7), '0007')
        self.assertEqual(consumer.QUERY_COUNT, 6400)
        self.assertEqual(consumer.CONDITIONS, ('numeric_direct_four_demo', 'numeric_program_four_demo'))
        self.assertEqual(b.identifier(legacy['rows'][0]['trial_id']), legacy['rows'][0]['trial_id'])
        with self.assertRaises(ValueError):
            v.collection_count({'rows': legacy['rows'], 'profile': g.PROFILE})
        with self.assertRaises(ValueError):
            v.source(e['packet'].root, ROOT, manifest_pin=e['packet'].manifest_pin)
        with self.assertRaises(ValueError):
            v.source(e['packet'].root, ROOT, profile=g.PROFILE)
        declaration = {'schema': 'neural077_image_programme_exposure_v1', 'statement': 'Generated image-only declaration',
                       'held_query_access_declared': False, 'provider_output_access_declared': False}
        self.assertEqual(e['image'].exposure_record(declaration), declaration)
        full = dict(declaration, raw_numerical_demonstration_access_declared=False,
                    pooled_query_access_declared=False, private_target_access_declared=False,
                    test_wide_feedback_declared=False, natural_class_prior_used_declared=False,
                    six_person_training_or_fitted_coefficients_used_declared=False)
        self.assertEqual(e['image'].exposure_record(full, g.PROFILE), full)
        for key in set(full)-set(declaration):
            with self.assertRaises(ValueError):
                e['image'].exposure_record(dict(full, **{key: True}), g.PROFILE)
        with self.assertRaises(ValueError):
            e['image'].exposure_record(declaration, g.PROFILE)

    def test_06_first_invalid_finalize_terminal_and_one_finite_http_request(self):
        e = self.e; v, t, client, bridge = e['v'], e['t'], e['client'], e['bridge']
        with charge_viewer_writes(v):
            session = v.Session(e['data'], 23, 'four_demo', FIXTURES / 'invalid-final')
            projected, png = t.projection(session.handle(v.encode({'action': 'inspect'})))
            header = t.ready_header(session, t.Limits(), 'd' * 32); header['initial'] = projected
            raw_response = v.encode({'trial_id': session.query['trial_id'], 'target_probability': 2.0})
            action = v.encode({'action': 'finalize', 'response': raw_response.decode()})
            terminal = session.handle(action)
            self.assertEqual(terminal['status'], 'invalid_response')
            self.assertTrue(terminal['terminal'])
            self.assertEqual(session.handle(v.encode({'action': 'inspect'}))['status'], 'closed')
        cfg = {'schema': 'neural077_visual_provider_client_v1', 'model': 'generated-model',
               'max_output_tokens': 100, 'deadline': time.monotonic() + 30,
               'trial_id': session.query['trial_id'], 'implementations_root': str(ROOT),
               'source_bindings': e['deps']['bindings'],
               'sender_path': str(ROOT / 'waveform-provider-v1/client.py'), 'sender_pin': client.ORIGINAL_SENDER,
               'bridge_path': str(ROOT / 'visual-provider-pair-v1/visual_bridge.py'),
               'bridge_pin': g.pin((ROOT / 'visual-provider-pair-v1/visual_bridge.py').read_bytes()),
               'codec_path': str(ROOT / 'visual-provider-pair-v1/transfer_png.py'),
               'codec_pin': g.pin((ROOT / 'visual-provider-pair-v1/transfer_png.py').read_bytes()),
               'max_request_bytes': 1048576, 'max_requests': 127,
               'max_query_request_bytes': 512 * 1024**2, 'max_query_response_bytes': 128 * 1024**2,
               'profile': g.PROFILE, 'profile_commitment': e['profile'].PROFILE_COMMITMENT,
               'context_sha256': g.pin(session.prompt.encode())['sha256']}
        cfg = client.configuration(client.encoded(cfg))
        custody = FIXTURES / 'invalid-custody'; custody.mkdir(mode=0o700)
        fd = os.open(custody, os.O_RDONLY | os.O_DIRECTORY)
        http, output = g.HTTP([g.provider(action)]), io.BytesIO()
        try:
            ok = client.serve(cfg, client.pin(client.encoded(cfg)), 'GENERATED_NOT_A_CREDENTIAL', fd,
                              e['original'], bridge, e['codec'], g.Alarm(),
                              io.BytesIO(t.wire(header, png) + t.wire(terminal)), output, http_factory=http)
        finally:
            os.close(fd)
        for path in custody.rglob('*'):
            if path.is_file():
                g.charge_write(path.read_bytes())
        self.assertFalse(ok)
        self.assertEqual(len(http.requests), 1)
        self.assertEqual(output.getvalue(), bridge.PREFIX.pack(len(action), 0) + action)
        end = json.loads((custody / 'CLIENT_END.json').read_bytes())
        self.assertEqual(end['status'], 'failed_no_admission')
        self.assertTrue(end['first_finalize_terminal'])
        self.assertTrue(end['no_further_request_after_finalize'])
        self.assertEqual(end['terminal_frame'], g.pin(t.wire(terminal)))
        self.assertEqual(end['final_response'], g.pin(raw_response))

    def test_07_full32_metadata_policy_restriction_and_legacy_default(self):
        t = self.e['t']
        client = FIXTURES / 'policy-client.py'
        original_exists = Path.exists
        with patch.object(t.sys, 'platform', 'darwin'), patch.object(Path, 'exists',
                lambda path: True if str(path) == '/usr/bin/sandbox-exec' else original_exists(path)):
            legacy = t.sandbox_profile(client)
            explicit_legacy = t.sandbox_profile(client, visual_profile='legacy400')
            narrowed = t.sandbox_profile(client, visual_profile=g.PROFILE)
        self.assertEqual(legacy, explicit_legacy)
        self.assertIn('(allow file-read-metadata)', legacy)
        self.assertNotIn('(allow file-read-metadata)', narrowed)
        self.assertIn('(literal "/Library")', narrowed)
        self.assertIn('(literal ' + json.dumps(str(client.resolve())) + ')', narrowed)
        self.assertNotIn('(subpath ' + json.dumps(str(FIXTURES)) + ')', narrowed)
        self.assertNotIn('(subpath "/Users")', narrowed)
        self.assertNotIn('(subpath "/tmp")', narrowed)
        for runtime in ('/System', '/usr', '/Library/Frameworks'):
            self.assertIn('(subpath ' + json.dumps(runtime) + ')', narrowed)
        with self.assertRaises(ValueError):
            t.sandbox_profile(client, visual_profile='numeric_program_four_demo')

    def test_08_failed_collection_closes_lazy_packet_handle(self):
        e = self.e; v = e['v']
        data = e['profile'].source(e['packet'].root, e['packet'].manifest_pin, e['consumer'], e['validator'])
        # The existing output directory fails before any response/array access.
        output = FIXTURES / 'existing-collection'; output.mkdir()
        with patch.object(v, 'source', return_value=data):
            with self.assertRaises((ValueError, FileExistsError)):
                v.collect(e['packet'].root, FIXTURES / 'no-sessions', 'four_demo', output,
                          ROOT, profile=g.PROFILE, manifest_pin=e['packet'].manifest_pin)
        self.assertTrue(data['_session']._closed)
        self.assertIsNone(data['rows']._record)

    def test_09_real_session_transport_custody_audit_and_tamper(self):
        e = self.e; v, t, client, provider = e['v'], e['t'], e['client'], e['deps']['provider']
        data, deps, ordinal = e['data'], e['deps'], 29
        limits = provider.budgets(t, 30, 300, 1048576, 512*1024**2, 128*1024**2,
                                 1024**3, 1024**3, profile=g.PROFILE)
        beginning = time.monotonic()
        manifest = {'limits': limits, 'model': 'generated-model', 'max_output_tokens': 100,
                    'started_monotonic': beginning, 'deadline': beginning + 300,
                    'operator': provider.v.identity(deps['s'])}
        root, proot = FIXTURES / 'audited-session', FIXTURES / 'audited-provider'
        proot.mkdir(mode=0o700); custody = proot / 'custody'; custody.mkdir(mode=0o700)
        with charge_viewer_writes(v):
            session = v.Session(data, ordinal, 'four_demo', root)
            projection, png = t.projection(session.handle(v.encode({'action': 'inspect'})))
            header = t.ready_header(session, t.Limits(**limits['transport']), 'e' * 32)
            header['initial'] = projection
            raw_response = v.encode({'trial_id': session.query['trial_id'], 'target_probability': 0.25})
            action = v.encode({'action': 'finalize', 'response': raw_response.decode()})
            terminal = session.handle(action)
            journal = t.Journal(root / 'transport')
            boundary = t.boundary_manifest(t.Limits(**limits['transport']), 'protocol_only',
                       ROOT / 'visual-provider-pair-v1/visual_client.py', 'e' * 32, None, dataset=data)
            v.write_new(journal.path / 'MANIFEST.json', v.encode(boundary))
            for direction, raw in (('out', t.wire(header, png)), ('in', t.wire(json.loads(action))), ('out', t.wire(terminal))):
                journal.record(direction, raw)
            # Explicit synthetic process-receipt boundary. No child was launched.
            # Actual auditor validates these fields; tampering below must fail.
            closure = {'cleanup_complete': True, 'leader_unreaped_before_signal': True,
                       'exit_observed_before_stop': True, 'reaped': True, 'returncode': 0,
                       'group_absence_observed': True}
            end = {'schema': 'neural077_transport_end_v1', 'status': 'valid_unscored', 'reason': None,
                   'messages': journal.sequence, 'last_message_sha256': journal.previous,
                   'manifest_sha256': v.digest(v.encode(boundary)), 'images': 1,
                   'output_bytes': len(t.wire(header, png)) + len(t.wire(terminal)),
                   'elapsed_seconds': 0.0, 'client_exit_code': 0, 'client_forced_stop': False,
                   'process_ownership': closure, 'viewer_final_sha256': v.digest((root/'FINAL.json').read_bytes()),
                   'scoring_performed': False}
            v.write_new(root/'transport/END.json', v.encode(end))
        started = time.monotonic()
        cfg = provider.configuration(deps, session.query['trial_id'], 'generated-model', 100,
                                     started + 28, limits, data)
        config_body = client.encoded(cfg)
        g.write(proot / 'CONFIG.json', config_body)
        fd = os.open(custody, os.O_RDONLY | os.O_DIRECTORY)
        http, outgoing = g.HTTP([g.provider(action)]), io.BytesIO()
        try:
            ok = client.serve(cfg, g.pin(config_body), 'GENERATED_NOT_A_CREDENTIAL', fd,
                              e['original'], e['bridge'], e['codec'], g.Alarm(),
                              io.BytesIO(t.wire(header, png) + t.wire(terminal)), outgoing, http_factory=http)
        finally:
            os.close(fd)
        for path in custody.rglob('*'):
            if path.is_file():
                g.charge_write(path.read_bytes())
        self.assertTrue(ok)
        self.assertEqual(len(http.requests), 1)
        self.assertEqual(outgoing.getvalue(), t.wire(json.loads(action)))
        g.write(proot/'OPERATOR_END.json', g.encode({'started_monotonic': started,
                'finished_monotonic': time.monotonic(), 'config': g.pin(config_body),
                'transport_end': g.pin((root/'transport/END.json').read_bytes())}))
        audit_budget = deps['full32_pair'].Budget(64*1024**2, 1024**2, time.monotonic()+60)
        audited = provider.audit_episode(root, proot, data, ordinal, deps, manifest, budget=audit_budget)
        self.assertEqual(audited['probability'], 0.25)
        self.assertEqual(audited['turns'], 1)
        # Audit refuses an unclosed generated instance before admitting custody.
        path = root/'transport/END.json'; original_end = path.read_bytes()
        changed = copy.deepcopy(end); changed['process_ownership']['group_absence_observed'] = False
        g.write(path, g.encode(changed))
        with self.assertRaises(ValueError):
            provider.audit_episode(root, proot, data, ordinal, deps, manifest, budget=audit_budget)
        g.write(path, original_end)
        # Actual retained-request audit, not only an injected per-episode result.
        request = custody/'000/REQUEST.bin'; original_request = request.read_bytes()
        g.write(request, original_request.replace(b'generated-model', b'substitute-model'))
        with self.assertRaises(ValueError):
            provider.audit_episode(root, proot, data, ordinal, deps, manifest, budget=audit_budget)
        g.write(request, original_request)
        self.assertGreater(audit_budget.read, len(png))
        self.assertLessEqual(audit_budget.read, 64*1024**2)


        # Exercise the real programme permission/audit adapter too, reusing the
        # existing one-image projection Session so no second renderer fixture
        # is needed. The candidate is never executed and closure is synthetic.
        image_transport = deps['image_transport']
        from contextlib import ExitStack
        host = ExitStack(); self.addCleanup(host.close)
        original_exists = Path.exists
        host.enter_context(patch.object(t.sys, 'platform', 'darwin'))
        host.enter_context(patch.object(Path, 'exists', lambda path:
            True if str(path) == '/usr/bin/sandbox-exec' else original_exists(path)))
        programme = e['projection_session']
        client_path = FIXTURES/'generated-programme-client.py'
        g.write(client_path, b'# Generated source fixture; never executed.\n')
        policy = image_transport.sandbox_profile(client_path, visual_profile=g.PROFILE, budget=audit_budget)
        with charge_viewer_writes(v):
            response = v.encode({'trial_id': programme.query['trial_id'], 'target_probability': 0.5})
            final_action = v.encode({'action': 'finalize', 'response': response.decode()})
            final_header = programme.handle(final_action)
            action0 = v.decode((programme.output/'action-0000.json').read_bytes())
            native_png = (programme.output/action0['detail']['frame']).read_bytes()
            initial_projection = {'status': 'rendered', 'display': action0['detail']['display'],
                'remaining_actions': 127, 'image': {'mime_type': 'image/png', 'bytes': len(native_png)}}
            first = image_transport.ready_header(programme, t.Limits(), 'f'*32, budget=audit_budget)
            first['initial'] = initial_projection
            journal = t.Journal(programme.output/'transport')
            boundary = image_transport.boundary_manifest(t.Limits(), 'macos', client_path, 'f'*32,
                       policy, dataset=data, budget=audit_budget)
            v.write_new(journal.path/'MANIFEST.json', v.encode(boundary))
            v.write_new(journal.path/'sandbox.sb', policy.encode())
            for direction, raw in (('out', t.wire(first, native_png)), ('in', t.wire(json.loads(final_action))),
                                   ('out', t.wire(final_header))):
                journal.record(direction, raw)
            programme_end = {'schema':'neural077_transport_end_v1', 'status':'valid_unscored', 'reason':None,
                'messages':journal.sequence, 'last_message_sha256':journal.previous,
                'manifest_sha256':v.digest(v.encode(boundary)), 'images':1,
                'output_bytes':len(t.wire(first,native_png))+len(t.wire(final_header)), 'elapsed_seconds':0.0,
                'client_exit_code':0, 'client_forced_stop':False, 'process_ownership':closure,
                'viewer_final_sha256':v.digest((programme.output/'FINAL.json').read_bytes()), 'scoring_performed':False}
            v.write_new(journal.path/'END.json',v.encode(programme_end))
        checked = image_transport.audit_transport(programme.output, data, 19, 'four_demo', budget=audit_budget)
        self.assertEqual(checked['status'], 'valid_unscored')
        original_policy = (journal.path/'sandbox.sb').read_bytes()
        g.write(journal.path/'sandbox.sb', original_policy+b' (allow file-read-metadata)')
        with self.assertRaises(ValueError):
            image_transport.audit_transport(programme.output, data, 19, 'four_demo', budget=audit_budget)
        g.write(journal.path/'sandbox.sb', original_policy)
        self.assertLessEqual(audit_budget.read, 64*1024**2)


def make_suite(root, fixture_root, *, expected_python_version=None, expected_numpy_version=None):
    """One affected campaign; caller authenticates complete source guards first."""
    configure(root, fixture_root)
    if (expected_python_version is None) != (expected_numpy_version is None):
        raise ValueError('Both explicit runtime versions or neither required')
    if expected_python_version is not None:
        RUNTIME_EXPECTATIONS.update(python=expected_python_version, numpy=expected_numpy_version)
    if FIXTURES.exists():
        raise ValueError('Fresh generated fixture destination required')
    FIXTURES.mkdir(mode=0o700)
    # All temporary validator snapshots stay inside the owned generated root.
    tempfile.tempdir = str(FIXTURES)
    admission = g.load('generated_full32_admission_controls', HERE/'admission_controls.py')
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(VisualFull32Controls))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(admission.FullRosterAdmissionControls))
    return suite


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementations-root', type=Path, required=True)
    parser.add_argument('--fixture-root', type=Path, required=True)
    parser.add_argument('--expected-python-version')
    parser.add_argument('--expected-numpy-version')
    args = parser.parse_args(argv)
    result = unittest.TextTestRunner(verbosity=2).run(make_suite(args.implementations_root, args.fixture_root,
        expected_python_version=args.expected_python_version, expected_numpy_version=args.expected_numpy_version))
    if ENV:
        ENV['v'].close_source(ENV['data'])
    print(json.dumps({'schema': 'neural077_full32_visual_generated_controls_v1',
          'methods_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
          'skips': len(result.skipped), 'fixture_bytes_written_cumulative': g.WRITTEN,
          'generated_capture_bytes_supplied_cumulative': g.SUPPLIED,
          'runtime_versions': ENV.get('runtime_versions'),
          'generated_compression_samples': ENV.get('generated_compression_samples', []),
          'source_only_generated': True, 'native_children': 0, 'network_requests': 0,
          'model_attempts': 0, 'scientific_results': 0}, sort_keys=True))
    return 0 if result.wasSuccessful() and result.testsRun == 16 and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())

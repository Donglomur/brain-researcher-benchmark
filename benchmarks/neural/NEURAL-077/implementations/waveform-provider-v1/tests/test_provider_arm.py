"""Invented provider responses and targets only; never contact a model/API."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import provider_arm as a
import support as s

# CI can use its checked-out sibling tree; authoring supplies only scoped source
# dependencies through this explicit existing checkout path in the test command.
SOURCE_ROOT = Path(os.environ.get('NEURAL077_TEST_IMPLEMENTATIONS_ROOT', HERE.parent)).resolve()
MODEL = 'generated-resolved-model'
TOKENS = 128


def provider_reply(identifier, ordinal=0):
    answer = json.dumps({'trial_id': identifier, 'target_probability': 0.5}, separators=(',', ':'))
    return s.encode({'object': 'response', 'status': 'completed', 'error': None, 'incomplete_details': None,
        'id': f'resp_generated_{ordinal}', 'model': MODEL, 'max_output_tokens': TOKENS,
        'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False, 'store': False,
        'truncation': 'disabled', 'previous_response_id': None, 'conversation': None,
        'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                    'content': [{'type': 'output_text', 'text': answer}]}],
        'usage': {'input_tokens': 10, 'output_tokens': 2, 'total_tokens': 12}}), answer.encode()


class ProviderArmControls(unittest.TestCase):
    written = 0

    @classmethod
    def put(cls, path, body):
        if path.exists(): path.chmod(0o600)
        path.write_bytes(body); cls.written += len(body)
        return s.pin(body)

    @classmethod
    def npz(cls, **values):
        stream = io.BytesIO(); np.savez(stream, **values); return stream.getvalue()

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-provider-arm-')
        cls.root = Path(cls.temp.name).resolve(); cls.arm = cls.root / 'provider'
        cls.arm.mkdir(); (cls.arm / 'episodes').mkdir()
        cls.deps = s.sources(SOURCE_ROOT)
        cls.rows = [{'ordinal': i, 'trial_id': f'development-{1+i//200:03d}-{i%200:024x}',
                     'prompt': cls.deps['bridge'].NO_TOOLS + '\n' + f'development-{1+i//200:03d}-{i%200:024x}'}
                    for i in range(400)]
        for row in cls.rows: row['context_sha256'] = s.pin(row['prompt'].encode())['sha256']
        cls.manifest = {'schema': 'neural077_trusted_provider_campaign_v1', 'route': s.ROUTE,
            'condition': s.CONDITION, 'queries': 400, 'demonstrations': 4, 'model': MODEL, 'max_output_tokens': TOKENS,
            'limits': a.limits(10, 1000, 262144), 'source': cls.deps['bindings'], 'operator': s.identity(),
            'client_interpreter': {'path': sys.executable, 'pin': s.pin(b'generated interpreter identity')},
            'retry_policy': 'none', 'credentials_channel': 'operator_owned_inherited_pipe',
            'remote_context_qualified': False, 'provider_capacity_qualified': False,
            'local_participant_sandbox': None, 'participant_code_executed_locally': False,
            'started_monotonic': 1000.0, 'deadline': 2000.0}
        cls.manifest_pin = cls.put(cls.arm / 'MANIFEST.json', s.encode(cls.manifest))
        cls.ends = []; envelopes = []
        for row in cls.rows:
            directory = cls.arm / 'episodes' / f"{row['ordinal']:03d}"
            directory.mkdir(); (directory / 'custody').mkdir()
            cfg = a.config_for(row, cls.deps, MODEL, TOKENS, 1008.0)
            cfg_pin = cls.put(directory / 'CONFIG.json', s.encode(cfg))
            incoming = cls.deps['transport'].PREFIX.pack(len(row['prompt'].encode())) + row['prompt'].encode()
            response, answer = provider_reply(row['trial_id'], row['ordinal'])
            outgoing = cls.deps['transport'].PREFIX.pack(len(answer)) + answer
            input_pin = cls.put(directory / 'INPUT.bin', incoming)
            output_pin = cls.put(directory / 'OUTPUT.bin', outgoing)
            request = cls.deps['bridge'].request_body(row['prompt'], MODEL, TOKENS)
            cls.put(directory / 'custody/REQUEST.bin', request)
            cls.put(directory / 'custody/RESPONSE.bin', response)
            receipts = []
            cls.deps['bridge'].exchange(row['prompt'], model=MODEL, max_output_tokens=TOKENS,
                                       send_json=lambda body, raw=response: raw, record=receipts.append)
            cls.put(directory / 'custody/BRIDGE.json', s.encode({'schema': 'neural077_provider_binding_bridge_v1',
                    'config_pin': cfg_pin, 'status': 'recorded', 'receipt': receipts[0], 'failure': None}))
            cls.put(directory / 'custody/HTTP.json', s.encode({'schema': 'neural077_https_binding_v1',
                    'config_pin': cfg_pin, 'endpoint': 'https://api.openai.com/v1/responses',
                    'request': s.pin(request), 'response': s.pin(response), 'status_code': 200,
                    'request_complete': True, 'response_complete': True, 'body_overflow': False,
                    'requests_attempted': 1, 'redirects_followed': 0, 'retries': 0, 'connection_closed': True,
                    'credential_retained': False, 'failure': None, 'started_monotonic': 1000.0,
                    'finished_monotonic': 1001.0, 'deadline': 1008.0}))
            end = {'schema': 'neural077_trusted_provider_episode_end_v1', 'status': 'closed_first_answer',
                   'error_type': None, 'config': cfg_pin, 'input': input_pin, 'output': output_pin,
                   'child_pid': 20000 + row['ordinal'], 'child_exit_code': 0, 'direct_child_reaped': True,
                   'forced_stop': False, 'descendant_absence_verified': False, 'started_monotonic': 1000.0,
                   'finished_monotonic': 1001.0, 'elapsed_seconds': 1.0, 'credential_persisted': False,
                   'provider_context_qualified': False, 'provider_capacity_qualified': False, 'scoring_performed': False}
            cls.ends.append(cls.put(directory / 'END.json', s.encode(end)))
            envelopes.append({key: row[key] for key in ('ordinal', 'trial_id', 'context_sha256')})
            envelopes[-1].update(status='ok', response=answer.decode(), error=None)
        cls.ledger = b''.join(s.encode(item) for item in envelopes)
        cls.ledger_pin = cls.put(cls.arm / 'attempts.jsonl', cls.ledger)
        members = {'manifest.json': s.encode({'query_count': 400, 'demonstration_count': 4,
                    'development_ids': [row['trial_id'] for row in cls.rows], 'natural_class_prior_supplied': False})}
        delivery = cls.deps['delivery']; actual_modules = delivery.dependencies()
        with mock.patch.object(delivery, 'packet_members', return_value=members), \
             mock.patch.object(delivery, 'context_rows', return_value=iter(cls.rows)), \
             mock.patch.object(delivery, 'dependencies', return_value=actual_modules):
            collection = delivery.collect(cls.root / 'unused', s.CONDITION, cls.arm / 'attempts.jsonl', cls.arm / 'collection')
        cls.written += sum(item.stat().st_size for item in (cls.arm / 'collection').iterdir())
        cls.receipt = {'schema': a.ARM_SCHEMA, 'status': 'closed_unscored_provider_arm', 'route': s.ROUTE,
            'condition': s.CONDITION, 'queries': 400, 'demonstrations': 4, 'source': cls.deps['bindings'],
            'operator': s.identity(), 'manifest': cls.manifest_pin, 'episode_ends': cls.ends,
            'attempts': cls.ledger_pin, 'collection': s.pin(s.read(cls.arm / 'collection/COMPLETE.json')),
            'submission': collection['submission'], 'usage': {'input_tokens': 4000, 'output_tokens': 800, 'total_tokens': 4800},
            'all_direct_children_reaped': True, 'descendant_absence_verified': False, 'local_participant_sandbox': None,
            'remote_context_qualified': False, 'provider_capacity_qualified': False, 'scientific_qualification': False,
            'private_target_reads': 0, 'scoring_performed': False}
        cls.receipt_pin = cls.put(cls.arm / 'ARM.json', s.encode(cls.receipt))

    @classmethod
    def tearDownClass(cls):
        print('GENERATED_PROVIDER_ARM_CUMULATIVE_BYTES=' + str(cls.written))
        cls.temp.cleanup()

    def admit(self):
        with mock.patch.object(self.deps['transport'], 'contexts', return_value=self.rows):
            return a.admit_arm(self.arm, self.receipt_pin, self.root / 'unused', self.deps)

    def altered(self, path, value, check):
        old = path.read_bytes()
        self.put(path, s.encode(value) if not isinstance(value, bytes) else value)
        try:
            with self.assertRaises((ValueError, KeyError)):
                check()
        finally:
            self.put(path, old)

    def test_complete_400_generated_provider_custody_uses_original_collector(self):
        submitted = self.admit()
        self.assertEqual(submitted[1], self.receipt['submission'])
        with np.load(submitted[0], allow_pickle=False) as arrays:
            self.assertEqual(arrays['target_probability'].tolist(), [0.5] * 400)

    def test_full_context_count_identity_and_order_are_required(self):
        for rows in (self.rows[:-1], [self.rows[0]] * 400, list(reversed(self.rows))):
            with mock.patch.object(self.deps['transport'], 'contexts', return_value=rows), self.assertRaises(ValueError):
                a.admit_arm(self.arm, self.receipt_pin, self.root, self.deps)

    def test_complete_raw_prompt_cannot_be_replaced(self):
        directory = self.arm / 'episodes/000'
        self.altered(directory / 'INPUT.bin', b'changed prompt',
                     lambda: a.audit_episode(directory, self.rows[0], self.deps, self.manifest))

    def test_first_emitted_answer_cannot_be_replaced(self):
        directory = self.arm / 'episodes/000'
        changed = s.encode({'trial_id': self.rows[0]['trial_id'], 'target_probability': .9})
        framed = self.deps['transport'].PREFIX.pack(len(changed)) + changed
        self.altered(directory / 'OUTPUT.bin', framed,
                     lambda: a.audit_episode(directory, self.rows[0], self.deps, self.manifest))

    def test_changed_model_tools_history_and_incomplete_response_refuse(self):
        directory = self.arm / 'episodes/000'; target = directory / 'custody/RESPONSE.bin'
        original = s.decode(target.read_bytes())
        for name, value in [('model', 'other'), ('tools', [{'type': 'function'}]),
                            ('previous_response_id', 'resp_prior'), ('status', 'incomplete')]:
            changed = copy.deepcopy(original); changed[name] = value
            self.altered(target, changed, lambda: a.audit_episode(directory, self.rows[0], self.deps, self.manifest))

    def test_no_closed_connection_or_complete_response_no_admission(self):
        directory = self.arm / 'episodes/000'; target = directory / 'custody/HTTP.json'
        original = s.decode(target.read_bytes())
        for name, value in [('connection_closed', False), ('response_complete', False), ('retries', 1),
                            ('body_overflow', True), ('status_code', 302), ('request_complete', False),
                            ('finished_monotonic', 3000.0)]:
            changed = copy.deepcopy(original); changed[name] = value
            self.altered(target, changed, lambda: a.audit_episode(directory, self.rows[0], self.deps, self.manifest))

    def test_failed_unreaped_or_overbudget_query_refuses(self):
        directory = self.arm / 'episodes/000'; target = directory / 'END.json'
        original = s.decode(target.read_bytes())
        for name, value in [('direct_child_reaped', False), ('forced_stop', True), ('child_exit_code', 3),
                            ('elapsed_seconds', 11), ('started_monotonic', 900.0)]:
            changed = copy.deepcopy(original); changed[name] = value
            self.altered(target, changed, lambda: a.audit_episode(directory, self.rows[0], self.deps, self.manifest))

    def test_missing_provider_custody_refuses(self):
        target = self.arm / 'episodes/000/custody/BRIDGE.json'; spare = target.with_suffix('.saved')
        target.rename(spare)
        try:
            with self.assertRaises(ValueError):
                a.audit_episode(target.parent.parent, self.rows[0], self.deps, self.manifest)
        finally:
            spare.rename(target)

    def test_provider_route_is_not_accepted_as_macos_local_collection(self):
        with self.assertRaises((ValueError, KeyError)):
            self.deps['pair']._closed(self.receipt, s.CONDITION)

    def test_changed_operator_dependency_refuses_before_import(self):
        original = s.read
        def guard(path, *args, **kwargs):
            if str(path).endswith('waveform-pair-v1/pair.py'):
                raise ValueError('generated source drift')
            return original(path, *args, **kwargs)
        with mock.patch.object(s, 'read', side_effect=guard), self.assertRaisesRegex(ValueError, 'source drift'):
            s.sources(SOURCE_ROOT)

    def test_actual_fresh_evaluator_refuses_bad_identity_without_private_read(self):
        root = self.root / 'fresh-failed-evaluator'; root.mkdir()
        request = {'implementations_root': str(SOURCE_ROOT), 'output': str(root / 'grade'),
                   'schema': 'neural077_trusted_provider_pair_request_v1', 'operator': {}, 'source': {}}
        request_pin = self.put(root / 'request.json', s.encode(request))
        result = subprocess.run([sys.executable, '-B', str(HERE / 'provider_arm.py'), '_grade',
                                '--request', str(root / 'request.json'), '--sha256', request_pin['sha256']],
                                capture_output=True, timeout=15, env={'LANG': 'C', 'LC_ALL': 'C'}, check=False)
        self.assertEqual(result.returncode, 2)
        failure = s.decode((root / 'grade/FAILED.json').read_bytes())
        type(self).written += (root / 'grade/FAILED.json').stat().st_size
        self.assertFalse(failure['accounting']['both_public_validated_before_private'])
        self.assertEqual(failure['accounting']['private_reference_attempts'], 0)
        self.assertEqual(failure['accounting']['target_loader_attempts'], 0)


class RealBrokerControls(unittest.TestCase):
    def test_real_fresh_client_fd_bridge_roundtrip_uses_only_generated_http(self):
        with tempfile.TemporaryDirectory(prefix='generated-provider-child-') as raw:
            root = Path(raw).resolve(); deps = s.sources(SOURCE_ROOT)
            identifier = 'development-001-' + '0' * 24
            prompt = deps['bridge'].NO_TOOLS + '\n' + identifier
            row = {'ordinal': 0, 'trial_id': identifier, 'prompt': prompt, 'context_sha256': s.pin(prompt.encode())['sha256']}
            response, answer = provider_reply(identifier)
            source = '''import importlib.util,io,sys
spec=importlib.util.spec_from_file_location('generated_bound_client', CLIENT_PATH)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class Socket:
    def settimeout(self,value):pass
class Response:
    status=200
    def __init__(self):self.body=io.BytesIO(RESPONSE);self.length=len(RESPONSE)
    def read(self,n):
        value=self.body.read(n);self.length-=len(value);return value
    def getheader(self,key,default=None):return default
    def close(self):pass
class Connection:
    def __init__(self,*args,**kwargs):self.sock=Socket()
    def set_debuglevel(self,value):pass
    def request(self,*args,**kwargs):pass
    def getresponse(self):return Response()
    def close(self):pass
raise SystemExit(c.main(http_factory=Connection))
'''.replace('CLIENT_PATH', repr(str(HERE / 'client.py'))).replace('RESPONSE', repr(response))
            fake = root / 'fake_http_client.py'; fake.write_text(source)
            token = bytearray(b'GENERATED_ONLY_TOKEN_NOT_A_CREDENTIAL')
            start = time.monotonic()
            end = a.episode(row, deps, root / 'episode', MODEL, TOKENS, token, sys.executable, 10, start + 10, fake)
            manifest = {'model': MODEL, 'max_output_tokens': TOKENS, 'limits': a.limits(10, 10, 262144),
                        'started_monotonic': start, 'deadline': start + 10}
            envelope, response_id, usage = a.audit_episode(root / 'episode', row, deps, manifest)
            self.assertEqual(envelope['response'].encode(), answer)
            self.assertTrue(end['direct_child_reaped'])
            for file in (root / 'episode').rglob('*'):
                if file.is_file():self.assertNotIn(token, file.read_bytes())
            written = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
            http_file = root / 'episode/custody/HTTP.json'
            original = http_file.read_bytes()
            for field, value in [('started_monotonic', end['started_monotonic'] - .1),
                                 ('finished_monotonic', end['finished_monotonic'] + .1)]:
                changed = s.decode(original); changed[field] = value
                self.assertLess(changed['finished_monotonic'], changed['deadline'])
                body = s.encode(changed); http_file.write_bytes(body); written += len(body)
                try:
                    with self.assertRaisesRegex(ValueError, 'outside enclosing episode'):
                        a.audit_episode(root / 'episode', row, deps, manifest)
                finally:
                    http_file.write_bytes(original); written += len(original)
            print('GENERATED_REAL_BROKER_FIXTURE_BYTES=' + str(written))

    def test_credential_pipe_does_not_require_environment_and_is_closed(self):
        deps = s.sources(SOURCE_ROOT)
        read_fd, write_fd = os.pipe(); os.write(write_fd, b'GENERATED_TOKEN'); os.close(write_fd)
        value = a.credential(read_fd, deps['transport'])
        self.assertEqual(value, bytearray(b'GENERATED_TOKEN'))
        with self.assertRaises(OSError):os.fstat(read_fd)
        value[:] = b'\0' * len(value)


class ProtectedGradeControls(unittest.TestCase):
    """New route composition; original generated fixture and numerical evaluator."""
    @classmethod
    def setUpClass(cls):
        filename = SOURCE_ROOT / 'waveform-pair-v1/tests/test_pair.py'
        spec = importlib.util.spec_from_file_location('n077_original_generated_fixture', filename)
        cls.fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.fixtures)
        cls.base = cls.fixtures.PairControls
        cls.base.setUpClass()  # Construct invented labels/references; no old tests run.
        cls.deps = s.sources(SOURCE_ROOT)
        cls.deps.update(pair=cls.fixtures.pair, comparator=cls.base.comparator,
                        original_bodies=dict(cls.base.bodies))
        cls.deps['original_bodies']['registered-runtime/assets.json'] = s.encode(cls.base.assets)
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-provider-grade-')
        cls.root = Path(cls.temp.name).resolve(); cls.serial = 0; cls.extra = 0

    @classmethod
    def tearDownClass(cls):
        cls.base.tearDownClass()
        print('GENERATED_PROVIDER_GRADE_EXTRA_BYTES=' + str(cls.extra))
        cls.temp.cleanup()

    def invoke(self, invalid=None):
        type(self).serial += 1
        directory = self.root / str(self.serial); directory.mkdir()
        arms = [(self.base.a, self.base.prediction_pin, self.base.receipt_pin),
                (self.base.b, self.base.prediction_pin, self.base.receipt_pin)]
        if invalid is not None:
            raw = self.base.npz(trial_ids=np.array(sum(self.base.ids.values(), [])),
                                target_probability=np.zeros(399, dtype=np.float64))
            target = directory / 'invalid.npz'; target.write_bytes(raw); type(self).extra += len(raw)
            arms[invalid] = (target, s.pin(raw), self.base.receipt_pin)
        request = {'schema': 'neural077_trusted_provider_pair_request_v1', 'operator': s.identity(),
                   'source': self.deps['bindings'], 'implementations_root': str(SOURCE_ROOT),
                   'output': str(directory / 'grade'), 'a': {'root': 'generated', 'receipt': self.base.receipt_pin},
                   'b': {'root': 'generated', 'receipt': self.base.receipt_pin}, 'delivery_root': 'generated',
                   'private_locations': str(self.base.locations)}
        raw = s.encode(request); target = directory / 'request.json'; target.write_bytes(raw)
        type(self).extra += len(raw)
        original_read = self.deps['pair'].read
        def guard(path, *args, **kwargs):
            if invalid is not None:self.assertNotEqual(Path(path), self.base.locations)
            return original_read(path, *args, **kwargs)
        with mock.patch.object(s, 'sources', return_value=self.deps), \
             mock.patch.object(a, 'admit_arm', return_value=arms[0]), \
             mock.patch.object(self.deps['pair'], '_admit_arm', return_value=arms[1]), \
             mock.patch.object(self.deps['pair'], 'public_roster', return_value=self.base.ids), \
             mock.patch.object(self.deps['pair'], 'read', side_effect=guard):
            try:
                return a.grade(target, s.pin(raw)['sha256'])
            finally:
                for file in (directory / 'grade').iterdir():
                    type(self).extra += file.stat().st_size
                    value = s.decode(file.read_bytes())
                    type(self).extra += value['accounting']['temporary_submission_bytes_created']
                    if invalid is not None:
                        self.assertFalse(value['accounting']['both_public_validated_before_private'])
                        self.assertEqual(value['accounting']['private_reference_attempts'], 0)
                        self.assertEqual(value['accounting']['target_loader_attempts'], 0)

    def test_new_provider_pair_route_reuses_original_protected_arithmetic(self):
        report = self.invoke()
        self.assertEqual(report['operator_route'], 'trusted_provider_and_macos_programme_pair_v1')
        self.assertEqual(report['trial_count'], 400)
        self.assertEqual(report['a_minus_b']['participant_macro_balanced_accuracy'], 0)
        self.assertEqual(report['a_minus_b']['participant_macro_log_loss'], 0)
        self.assertEqual(report['accounting']['target_loader_attempts'], 2)
        self.assertEqual(report['accounting']['private_reference_attempts'], 2)
        self.assertEqual(len(report['a']['canonical_score']['candidate_minus_reference']), 6)

    def test_either_malformed_public_submission_refuses_before_private_file(self):
        for arm in (0, 1):
            with self.subTest(arm=arm), self.assertRaises(ValueError):
                self.invoke(invalid=arm)


if __name__ == '__main__':unittest.main(verbosity=2)

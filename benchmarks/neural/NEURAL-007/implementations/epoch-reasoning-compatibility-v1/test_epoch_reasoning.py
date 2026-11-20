"""Generated-only optional epoch-reasoning integration controls.

No authentic signal, label, provider, model or container is accessed. Exact
responses and invented opaque payloads remain only in private fixture custody.
"""
from contextlib import contextmanager, redirect_stdout
from dataclasses import replace
import base64
import hashlib
import importlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WORKSPACE, SOURCE, CONTROL = map(Path, sys.argv[1:4])
sys.argv = [sys.argv[0]]
sys.dont_write_bytecode = True
os.umask(0o077)
EPOCH = WORKSPACE / 'benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1'
sys.path.insert(0, str(EPOCH))
C = importlib.import_module('contract')
V = importlib.import_module('epoch_visual')
EP = importlib.import_module('epoch_provider')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


RP = load('generated_epoch_reasoning_donor', WORKSPACE / 'benchmarks/neural/NEURAL-007/implementations/viewer-provider-reasoning-v1/provider.py')
A = load('generated_epoch_reasoning_adapter', SOURCE / 'epoch_reasoning.py')
RUNTIME = V.load_runtime(WORKSPACE)
PA = load('generated_epoch_reasoning_admission', SOURCE / 'epoch_admission.py')
import numpy as np
CONTROL.mkdir(mode=0o700, parents=False, exist_ok=False)
(CONTROL / 'GENERATED_COMPONENT_ONLY').write_text('Synthetic epochs and fake HTTPS only. No scientific or provider qualification.\n')
SECRET = 'GENERATED_EPOCH_REASONING_TRANSPORT_0123456789'
OPAQUE = 'GENERATED_OPAQUE_PRIVATE_PAYLOAD'
CREATION = {}
EXTRA_WRITES = []
MAX_ARTIFACTS = 8 * 2**20
MAX_MUTATIONS = 2 * 2**20
TOKENS = []


def snapshot():
    for path in CONTROL.rglob('*'):
        if path.is_file():
            CREATION.setdefault(str(path), path.stat().st_size)
    total = sum(CREATION.values()) + sum(row['bytes'] for row in EXTRA_WRITES)
    if total > MAX_ARTIFACTS:
        raise AssertionError('Generated fixture artifact cap exceeded')
    return total


def read(path):
    return Path(path).read_bytes()


def encode(value):
    return C.encode(value)


def decoded(path):
    return C.decode(read(path))


def knowledge():
    return {'schema': 'sleep007_epoch_shared_knowledge_v1', 'provider': 'openai',
            'model': 'generated-epoch-reasoning-model', 'revision': 'generated-fixed-revision',
            'policy': 'shared_declared_base_agent_prior_only', 'external_assets': []}


class GeneratedPerson:
    def __init__(self, case, index):
        self.case, self.index = case, index
        self.epochs = dict(C.CASES)[case]
        self.clock = {index: (index * 30 / 3600, 0.0, 1.0)}

    def samples(self, start, stop, channels):
        if (start, stop, channels) != (self.index * 3000, (self.index + 1) * 3000, list(C.CHANNELS)):
            raise AssertionError('Generated projection attempted another epoch')
        return [[(i + 1) * 8e-6 * math.sin((s + self.index) * math.pi / (25 + i * 9))
                 for s in range(3000)] for i in range(3)]


PACKET = C.project_epoch(GeneratedPerson('development-001', 1), 1)
OTHER = C.project_epoch(GeneratedPerson('development-002', 0), 0)
C.write_projection(PACKET, CONTROL / 'target')
C.write_projection(OTHER, CONTROL / 'other_target')


def budget(turns=2, **updates):
    value = RUNTIME['provider'].Budget(
        max_turns=turns, max_images=2, max_history_bytes=393216,
        max_request_bytes=393216, max_response_bytes=300000,
        max_total_provider_bytes=2 * 2**20, context_tokens=131072,
        output_tokens=256, wall_seconds=15, image_detail='original')
    return replace(value, **updates)


def request_parts(raw):
    value = C.decode(raw)
    if len(value['input']) != 1 or value['input'][0]['role'] != 'user':
        raise AssertionError('Another target or action transcript entered request')
    content = value['input'][0]['content']
    header = C.decode(content[0]['text'])
    images = []
    for item in content[1:]:
        if item['type'] != 'input_image' or not item['image_url'].startswith('data:image/png;base64,'):
            raise AssertionError('PNG must remain actual image content')
        png = base64.b64decode(item['image_url'].split(',', 1)[1], validate=True)
        if not (png[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', png[16:24]) == (1400, 820)):
            raise AssertionError('Original complete renderer canvas required')
        images.append(png)
    if not 1 <= len(images) <= 2 or OPAQUE.encode() in raw:
        raise AssertionError('Only current overview/detail without opaque replay')
    return value, header, images


def token_bound(raw, deadline):
    request_parts(raw)
    TOKENS.append(C.pin(raw))
    return 65536  # Generated fixture bound, never a provider capacity claim.


def response(action, ordinal, *, effort='low', reasoning=True):
    message = {'id': 'msg_generated_' + str(ordinal), 'type': 'message', 'role': 'assistant',
               'status': 'completed', 'content': [{'type': 'output_text',
                  'text': encode({'viewer_action': action}).decode()}]}
    value = {'object': 'response', 'id': 'resp_generated_' + str(ordinal), 'status': 'completed',
             'error': None, 'incomplete_details': None, 'model': knowledge()['model'],
             'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False,
             'store': False, 'background': False, 'truncation': 'disabled',
             'previous_response_id': None, 'conversation': None, 'max_output_tokens': 256,
             'output': [message],
             'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120,
                       'output_tokens_details': {'reasoning_tokens': 10},
                       'input_tokens_details': {'cached_tokens': 0}}}
    if reasoning:
        value['reasoning'] = {'context': 'current_turn', 'effort': effort}
        message['phase'] = 'final_answer'
        value['output'].insert(0, {'id': 'rs_generated_' + str(ordinal), 'type': 'reasoning',
                                  'summary': [], 'encrypted_content': OPAQUE, 'status': 'completed'})
    return value


def final(packet=PACKET):
    return {'action': 'respond', 'epoch_id': packet.epoch_id, 'probabilities': [0.2] * 5}


class FakeResponse:
    status = 200
    def __init__(self, raw):
        if not 0 < len(raw) <= 300000:
            raise AssertionError('Generated response is outside frozen fixture cap')
        self.stream, self.length = io.BytesIO(raw), len(raw)
    def read(self, count):
        result = self.stream.read(min(count, 4096)); self.length -= len(result)
        return result
    def getheader(self, name, default=None):
        return 'identity'
    def close(self):
        pass


class FakeHTTPS:
    sock = None
    def __init__(self, owner, host, port, timeout, context):
        if host != 'api.openai.com' or port != 443 or timeout <= 0 or not context.check_hostname:
            raise AssertionError('Existing bounded sender TLS interface changed')
        self.owner = owner
    def set_debuglevel(self, level):
        if level != 0:
            raise AssertionError('No credential-bearing debug output')
    def request(self, method, path, *, body, headers, encode_chunked):
        if (method, path, encode_chunked) != ('POST', '/v1/responses', False):
            raise AssertionError('Existing single HTTPS operation changed')
        if headers['Authorization'] != 'Bearer ' + SECRET:
            raise AssertionError('Generated credential mismatch')
        request_parts(body)
        self.owner.requests.append(body)
    def getresponse(self):
        if not self.owner.responses:
            raise AssertionError('Unselected retry or extra provider turn')
        return FakeResponse(self.owner.responses.pop(0))
    def close(self):
        pass


class Factory:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
    def __call__(self, *args, **kwargs):
        return FakeHTTPS(self, *args, **kwargs)


def descriptor(path):
    path = Path(path)
    return {'path': str(path), **C.pin(path.read_bytes())}


SELECTION = {'execution_policy': 'current_turn_reasoning_v1', 'reasoning_effort': 'low',
             'adapter': descriptor(SOURCE / 'epoch_reasoning.py'),
             'bindings': descriptor(SOURCE / 'SOURCE_BINDINGS.json'),
             'reasoning_provider': descriptor(Path(RP.__file__))}
DONOR_GLOBALS = {name: dict(module.__dict__) for name, module in [('EP', EP), ('V', V), ('RP', RP)]}
def simple_globals(module):
    result = {}
    for name, value in module.__dict__.items():
        if name.startswith('__') or type(value) not in (dict, list, set):
            continue
        try:
            result[name] = encode(sorted(value) if type(value) is set else value)
        except (TypeError, ValueError):
            pass
    return result
DONOR_MUTABLE = {name: simple_globals(module) for name, module in [('EP', EP), ('V', V), ('RP', RP)]}
RUNTIME_SOURCE = encode(RUNTIME['source'])
DIRECT = A.bind(EP, RP, RUNTIME, execution_policy='current_turn_reasoning_v1', reasoning_effort='low')
LOW = A.load_selected(SELECTION, EP, RUNTIME)
HIGH = A.load_selected(dict(SELECTION, reasoning_effort='high'), EP, RUNTIME)
HAPPY = None
COLLECTED = None


def run(name, replies, *, adapter=LOW, packet=PACKET, allocation=None, fail=False):
    root = CONTROL / name
    factory = Factory([encode(value) for value in replies])
    allocation = allocation or budget(max(1, len(replies)))
    try:
        result = adapter.run_epoch(packet, knowledge(), allocation, root, SECRET, token_bound,
                                   session_id=hashlib.sha256(name.encode()).hexdigest()[:32],
                                   http_factory=factory)
    except ValueError:
        if not fail:
            raise
        result = decoded(root / 'END.json')
    else:
        if fail:
            raise AssertionError('Generated invalid response was accepted')
    snapshot()
    return root, factory, result


def happy():
    global HAPPY
    if HAPPY is None:
        HAPPY = run('accepted', [response({'action': 'window', 'start_sample': 400, 'stop_sample': 900}, 1),
                                 response(final(), 2), response(final(), 3)], allocation=budget(3))
    return HAPPY


@contextmanager
def mutation(path, raw, name):
    path = Path(path)
    snapshot()
    original = read(path)
    allowance = len(raw) * 2 + len(original)
    if sum(row['bytes'] for row in EXTRA_WRITES) + allowance > MAX_MUTATIONS:
        raise AssertionError('Generated mutation reservation exceeded')
    folder = CONTROL / 'mutations'
    folder.mkdir(mode=0o700, exist_ok=True)
    retained = folder / (name + '.bin')
    retained.write_bytes(raw)
    CREATION[str(retained)] = len(raw)
    EXTRA_WRITES.append({'path': str(path), 'bytes': len(raw), 'purpose': 'mutation'})
    path.write_bytes(raw)
    try:
        yield
    finally:
        EXTRA_WRITES.append({'path': str(path), 'bytes': len(original), 'purpose': 'restoration'})
        path.write_bytes(original)
        snapshot()


def compact_collection():
    """Real full-roster collector; declared virtual projection/auditor seams only.

The canonical IDs, ordering, FirstAnswers, collection policy and NPZ submission
are real. This never claims 5,450 provider runs or original signal projections.
"""
    global COLLECTED
    if COLLECTED is not None:
        return COLLECTED
    prior = C.write_new(CONTROL / 'KNOWLEDGE.json', encode(knowledge()))
    source = C.write_new(CONTROL / 'GENERATED_SOURCE.json', encode({'generated_source_control_only': True}))
    rows, virtual = [], {}
    for ordinal, target in enumerate(C.required_targets()):
        session = str(CONTROL / 'virtual_sessions' / target)
        record = {'epoch_id': target, 'projection': {'root': str(CONTROL / 'virtual_projections' / target)},
                  'session_root': session,
                  'end': {'path': session + '/END.json', **C.pin(b'{}')}}
        raw = encode(record)
        item = {'path': str(CONTROL / 'virtual_records' / f'{ordinal:05d}.json'), **C.pin(raw)}
        rows.append({'epoch_id': target, 'record': item})
        virtual[item['path']] = raw
        virtual[record['end']['path']] = b'{}'
    selected = PA._select_visual_runtime(RUNTIME, SELECTION)
    selected_policy = selected['_epoch_reasoning_policy']
    calls = []
    def generated_audit(session_root, packet, declared):
        if session_root != str(CONTROL / 'virtual_sessions' / packet.epoch_id) or declared != knowledge():
            raise AssertionError('Compact generated auditor target/knowledge mismatch')
        calls.append(packet.epoch_id)
        identity = hashlib.sha256(packet.epoch_id.encode()).hexdigest()
        return {'epoch_id': packet.epoch_id, 'probabilities': [0.2] * 5,
                'knowledge': C.pin(encode(knowledge())), 'session_id': identity[:32],
                'response_ids': ['resp_generated_collection_' + identity[:32]]}
    selected['_epoch_reasoning_adapter'] = SimpleNamespace(policy=selected_policy, audit_session=generated_audit)
    item = {'rows': rows, 'virtual': virtual, 'knowledge': prior, 'source': source,
            'selected_runtime': selected, 'policy': selected_policy, 'auditor_calls': calls}
    with compact_io(item), patch.object(PA, '_select_visual_runtime') as select:
        def chosen(runtime, selection):
            if runtime is not RUNTIME or selection != SELECTION:
                raise AssertionError('Collector lost explicit operator-selected compatibility')
            return selected
        select.side_effect = chosen
        result = PA.collect_visual(rows, prior, source, RUNTIME, CONTROL / 'complete_generated_collection',
                                   reasoning_compatibility=SELECTION)
        if select.call_count != 1:
            raise AssertionError('Collector must explicitly select one immutable policy')
        collection, declared = PA._collection(result, C.VISUAL_CONDITION)
    item.update(descriptor=result, collection=collection)
    # Subsequent public-path controls reuse the exact generated collection bytes
    # through the declared descriptor fixture seam; no private data is supplied.
    item['virtual'][result['path']] = read(result['path'])
    programme = dict(collection, condition=C.PROGRAMME_CONDITION)
    programme.pop('reasoning_compatibility')
    raw = encode(programme)
    item['programme'] = {'path': str(CONTROL / 'virtual_programme_collection.json'), **C.pin(raw)}
    item['virtual'][item['programme']['path']] = raw
    COLLECTED = item
    snapshot()
    return item


@contextmanager
def compact_io(item):
    original_descriptor, original_projection = PA.P.descriptor, C.read_projection
    def resolve(value, cap):
        if value.get('path') in item['virtual']:
            raw = item['virtual'][value['path']]
            if len(raw) > cap or C.pin(raw) != {key: value[key] for key in ('bytes', 'sha256')}:
                raise ValueError('Generated virtual descriptor identity mismatch')
            return raw
        return original_descriptor(value, cap)
    def projection(value):
        prefix = str(CONTROL / 'virtual_projections') + '/'
        if not value.get('root', '').startswith(prefix):
            return original_projection(value)
        target = value['root'][len(prefix):]
        C.checked_target(target)
        return SimpleNamespace(epoch_id=target, signals_npy=b'GENERATED_VIRTUAL_PROJECTION',
                               metadata=lambda: {'epoch_id': target, 'generated_virtual': True})
    def source_freeze(value):
        if value != item['source']:
            raise AssertionError('Unselected source-freeze mock operand')
        return {'generated_fixture_only': True}
    with patch.object(PA.P, 'descriptor', side_effect=resolve), \
         patch.object(C, 'read_projection', side_effect=projection), \
         patch.object(PA.P, 'source_freeze', side_effect=source_freeze):
        yield


class EpochReasoningControls(unittest.TestCase):
    def test_01_explicit_opt_in_and_private_donor_state(self):
        self.assertEqual(np.__version__, '1.26.3', 'Observe existing selected NumPy once; no binary qualification')
        with self.assertRaises(TypeError):
            A.bind(EP, RP, RUNTIME, reasoning_effort='low')
        for policy, effort in [('wrong', 'low'), ('current_turn_reasoning_v1', 'invented'),
                               ('current_turn_reasoning_v1', None)]:
            with self.subTest(policy=policy, effort=effort), self.assertRaises(ValueError):
                A.bind(EP, RP, RUNTIME, execution_policy=policy, reasoning_effort=effort)
        self.assertEqual(LOW.policy['parser_binding'], 'pinned_previous_initializer_removed_v1')
        self.assertEqual(DIRECT.policy['parser_binding'], 'already_loaded_authenticated_parser_v1')
        for name, module in [('EP', EP), ('V', V), ('RP', RP)]:
            self.assertTrue(set(module.__dict__) == set(DONOR_GLOBALS[name]), 'Donor namespace changed')
            self.assertTrue(all(module.__dict__[key] is value for key, value in DONOR_GLOBALS[name].items()),
                            'Donor global identity changed')
            self.assertTrue(simple_globals(module) == DONOR_MUTABLE[name], 'Donor mutable declaration changed')

    def test_02_complete_epoch_run_and_exact_audit(self):
        root, factory, result = happy()
        self.assertEqual(result['status'], 'complete_unscored')
        self.assertTrue(result['first_accepted_answer'])
        self.assertEqual(len(factory.requests), 2)
        self.assertEqual(len(factory.responses), 1, 'First accepted answer must stop further provider calls')
        audited = LOW.audit_session(root, PACKET, knowledge())
        self.assertTrue(audited['probabilities'] == [0.2] * 5)
        self.assertEqual(audited['epoch_id'], PACKET.epoch_id)
        self.assertFalse(any(value is True for key, value in audited.items() if key.endswith('_qualified')))
        parts = [request_parts(raw) for raw in factory.requests]
        self.assertTrue(all(value['reasoning'] == {'context': 'current_turn', 'effort': 'low'}
                            for value, _, _ in parts))
        self.assertEqual([len(images) for _, _, images in parts], [1, 2])
        self.assertTrue(parts[0][2][0] == parts[1][2][0], 'Immutable overview changed')
        self.assertTrue(all(header['observation']['target'] == PACKET.metadata() for _, header, _ in parts))
        self.assertTrue(all(header['public_task']['total_epochs'] == 5450 for _, header, _ in parts))
        self.assertTrue(OPAQUE.encode() not in encode(result) + encode(audited), 'Opaque content left private custody')
        for index in range(2):
            turn = root / 'turns' / f'{index:06d}'
            self.assertTrue(read(turn / 'REQUEST.bin') == factory.requests[index])
            self.assertTrue(OPAQUE.encode() in read(turn / 'RESPONSE.bin'), 'Exact private opaque body was lost')
            event = decoded(root / 'events' / f'{index:06d}.json')
            self.assertTrue(OPAQUE.encode() not in encode(event), 'Raw opaque content entered event metadata')
            self.assertTrue(event['request'] == C.pin(factory.requests[index]))

    def test_03_effective_policy_model_and_stale_target_fail_closed(self):
        variants = []
        wrong_effort = response(final(), 10, effort='high'); variants.append(('effort', wrong_effort))
        wrong_context = response(final(), 11); wrong_context['reasoning']['context'] = 'all_turns'; variants.append(('context', wrong_context))
        wrong_model = response(final(), 12); wrong_model['model'] = 'wrong-model'; variants.append(('model', wrong_model))
        variants.append(('other_target', response(final(OTHER), 13)))
        for name, reply in variants:
            with self.subTest(case=name):
                root, factory, end = run('failed_' + name, [reply], fail=True)
                self.assertEqual(len(factory.requests), 1)
                self.assertEqual(end['status'], 'failed_no_admission')
                self.assertFalse(end['first_accepted_answer'])
                self.assertIsNone(end['probabilities'])
                self.assertTrue(read(root / 'turns/000000/RESPONSE.bin') == encode(reply), 'Failed exact response was lost')
                self.assertTrue(OPAQUE.encode() not in encode(end), 'Opaque content left private failed custody')
                with self.assertRaises(ValueError):
                    LOW.audit_session(root, PACKET, knowledge())

    def test_04_malformed_and_overbound_reasoning_refused(self):
        malformed = response(final(), 20); malformed['output'][0]['summary'] = [{'type': 'summary_text', 'text': 'GENERATED_FORBIDDEN'}]
        overflow = response(final(), 21); overflow['output'][0]['encrypted_content'] = 'x' * (262144 + 1)
        for name, reply in [('malformed', malformed), ('opaque_extent', overflow)]:
            with self.subTest(case=name):
                root, factory, end = run('failed_' + name, [reply], fail=True)
                self.assertEqual(len(factory.requests), 1)
                self.assertFalse(end['first_accepted_answer'])
                self.assertTrue(read(root / 'turns/000000/RESPONSE.bin') == encode(reply), 'Failed body not retained exactly')
        oversized_metadata = response(final(), 22)
        oversized_metadata['usage']['generated_extra_report'] = 'x' * 35000
        root, factory, end = run('failed_custody_metadata_extent', [oversized_metadata], fail=True)
        self.assertFalse(end['first_accepted_answer'])
        self.assertEqual(end['failure_stage'], 'durable_event_before_action')
        self.assertTrue(read(root / 'turns/000000/RESPONSE.bin') == encode(oversized_metadata),
                        'Exact body must survive bounded custody metadata refusal')

    def test_05_second_effort_and_baseline_unchanged(self):
        root, factory, result = run('accepted_high', [response(final(), 30, effort='high')], adapter=HIGH)
        self.assertEqual(result['status'], 'complete_unscored')
        self.assertEqual(C.decode(factory.requests[0])['reasoning']['effort'], 'high')
        self.assertEqual(HIGH.audit_session(root, PACKET, knowledge())['epoch_id'], PACKET.epoch_id)
        with self.assertRaises(ValueError):
            LOW.audit_session(root, PACKET, knowledge())
        factory = Factory([encode(response(final(), 31, reasoning=False))])
        baseline = CONTROL / 'baseline_original'
        end = EP.run_epoch(RUNTIME, PACKET, knowledge(), budget(1), baseline, SECRET, token_bound,
                           session_id='b' * 32, http_factory=factory)
        self.assertEqual(end['status'], 'complete_unscored')
        self.assertTrue('reasoning' not in C.decode(factory.requests[0]))
        self.assertEqual(EP.audit_session(baseline, PACKET, RUNTIME, knowledge())['epoch_id'], PACKET.epoch_id)
        with self.assertRaises(ValueError):
            EP.response_action(RUNTIME, knowledge()['model'], budget(1), encode(response(final(), 32)), 65536)
        for name, module in [('EP', EP), ('V', V), ('RP', RP)]:
            self.assertTrue(set(module.__dict__) == set(DONOR_GLOBALS[name]), 'Donor namespace changed')
            self.assertTrue(all(module.__dict__[key] is value for key, value in DONOR_GLOBALS[name].items()),
                            'Donor global identity changed')
            self.assertTrue(simple_globals(module) == DONOR_MUTABLE[name], 'Donor mutable declaration changed')
        snapshot()

    def test_06_post_reasoning_request_size_is_bounded(self):
        session = V.Session(PACKET, RUNTIME, 1, 'c' * 32); session.initial()
        original = V.request_bytes(session, knowledge()['model'], budget(1), knowledge())
        limit = len(original)
        allocation = budget(1, max_history_bytes=limit, max_request_bytes=limit)
        root, factory, end = run('failed_request_extent', [response(final(), 40)], allocation=allocation, fail=True)
        self.assertEqual(factory.requests, [])
        self.assertEqual(end['turns'], 0)
        self.assertFalse(end['first_accepted_answer'])

    def test_07_exact_custody_rejects_config_request_response_and_event_tampering(self):
        root, _, _ = happy()
        changes = []
        config = decoded(root / 'CONFIG.json')
        # Adding an unrecognized effort declaration must fail exact reconstruction.
        changes.append((root / 'CONFIG.json', encode(dict(config, generated_wrong_effort='high')), 'config_effort'))
        changed_source = json.loads(json.dumps(config)); changed_source['source']['generated_wrong_parser_pin'] = {'bytes': 1, 'sha256': '0' * 64}
        changes.append((root / 'CONFIG.json', encode(changed_source), 'parser_identity'))
        req = decoded(root / 'turns/000000/REQUEST.bin'); req['reasoning']['effort'] = 'high'
        changes.append((root / 'turns/000000/REQUEST.bin', encode(req), 'request_effort'))
        reply = decoded(root / 'turns/000000/RESPONSE.bin'); reply['output'][0]['encrypted_content'] += '_ALTERED'
        changes.append((root / 'turns/000000/RESPONSE.bin', encode(reply), 'response_opaque'))
        event = decoded(root / 'events/000000.json'); event['generated_wrong_effort'] = 'high'
        changes.append((root / 'events/000000.json', encode(event), 'event_policy'))
        for path, raw, name in changes:
            with self.subTest(case=name), mutation(path, raw, name), self.assertRaises(ValueError):
                LOW.audit_session(root, PACKET, knowledge())
        self.assertEqual(LOW.audit_session(root, PACKET, knowledge())['epoch_id'], PACKET.epoch_id)

    def test_08_response_identity_and_first_answer_custody(self):
        first = response({'action': 'inspect'}, 50)
        second = response(final(), 50)
        root, factory, end = run('failed_reused_response', [first, second], fail=True)
        self.assertEqual(len(factory.requests), 2)
        self.assertFalse(end['first_accepted_answer'])
        session = V.Session(PACKET, RUNTIME, 2, 'd' * 32); session.initial(); session.handle(final())
        with self.assertRaises(ValueError):
            session.handle(final())
        answers = C.FirstAnswers(); answers.accept(PACKET.epoch_id, [0.2] * 5, C.pin(b'generated'))
        with self.assertRaises(ValueError):
            answers.accept(PACKET.epoch_id, [0.2] * 5, C.pin(b'generated'))
        with self.assertRaises(ValueError):
            answers.complete()
        self.assertTrue(C.TOTAL == 5450 and C.CASES == (('development-001', 2780), ('development-002', 2670)))

    def test_09_complete_collector_policy_and_original_roster(self):
        f = compact_collection()
        self.assertTrue(f['auditor_calls'] == list(C.required_targets()), 'Collector omitted/reordered canonical targets')
        self.assertEqual(f['collection']['reasoning_compatibility'], LOW.policy)
        self.assertEqual(len(f['collection']['rows']), 5450)
        with np.load(f['collection']['submission']['path'], allow_pickle=False) as saved:
            self.assertTrue(saved['class_order'].tolist() == list(C.CLASSES))
            for case, count in C.CASES:
                self.assertTrue(saved[case + '__probabilities'].shape == (count, 5))
                self.assertTrue(saved[case + '__epoch_id'].tolist() == [C.target(case, i) for i in range(count)])
        for suffix, rows in [('missing', f['rows'][:-1]), ('order', list(reversed(f['rows'])))]:
            destination = CONTROL / ('never_incomplete_' + suffix)
            with compact_io(f), self.assertRaises(ValueError):
                PA.collect_visual(rows, f['knowledge'], f['source'], RUNTIME, destination,
                                  reasoning_compatibility=SELECTION)
            self.assertFalse(destination.exists())
        with self.assertRaises(ValueError):
            PA._select_visual_runtime(f['selected_runtime'], SELECTION)
        self.assertIs(PA._select_visual_runtime(RUNTIME, None), RUNTIME)

    def test_10_public_and_protected_selection_refuse_promotion_before_private_targets(self):
        f = compact_collection()
        source_loads = []
        private_calls = []
        def public_sources():
            source_loads.append(True)
            raise RuntimeError('GENERATED_PUBLIC_BOUNDARY_STOP_NO_PRIVATE_DATA')
        def forbidden_private(*args, **kwargs):
            private_calls.append(True)
            raise AssertionError('Generated controls must never request private targets')
        programme_runtime = {'claim_matched_information': False, 'matched_access_audit': None,
                             'common': SimpleNamespace(load_sources=public_sources),
                             'grading': SimpleNamespace(private_targets=forbidden_private)}
        impl = WORKSPACE / 'benchmarks/neural/NEURAL-007/implementations'
        config = {'schema': 'sleep007_epoch_pair_request_v1', 'source': f['source'],
                  'viewer_collection': f['descriptor'], 'programme_collection': f['programme'],
                  'packet_roots': {case: 'GENERATED_UNUSED_' + case for case, _ in C.CASES},
                  'references': {}, 'private_locations': {'path': str(CONTROL / 'NEVER_PRIVATE_TARGETS'),
                                                         'bytes': 1, 'sha256': '0' * 64},
                  'implementations_root': str(impl), 'finite_bindings_root': str(impl / 'finite-workflow-v1'),
                  'visual_runtime': {'root': str(WORKSPACE),
                       'whole_history_integration_root': str(impl / 'viewer-provider-integration-v1'),
                       'whole_history_admission_root': str(impl / 'finite-workflow-v1')},
                  'reasoning_compatibility': SELECTION}
        no_selection = dict(config); no_selection.pop('reasoning_compatibility')
        wrong_effort = dict(config, reasoning_compatibility=dict(SELECTION, reasoning_effort='high'))
        wrong_adapter = dict(config, reasoning_compatibility=dict(SELECTION,
                            adapter=dict(SELECTION['adapter'], sha256='0' * 64)))
        for name, value in [('ordinary', no_selection), ('effort', wrong_effort), ('adapter', wrong_adapter)]:
            request = C.write_new(CONTROL / ('public_' + name + '.json'), encode(value))
            with self.subTest(selection=name), compact_io(f), \
                 patch.object(PA.P, 'load_runtime', return_value=programme_runtime), \
                 patch.object(V, 'load_runtime', return_value=RUNTIME), \
                 patch.object(PA.subprocess, 'Popen', side_effect=AssertionError('No grader launch for invalid public policy')):
                with self.assertRaises(ValueError):
                    PA._public(value)
                destination = CONTROL / ('never_grader_' + name)
                with self.assertRaises(ValueError):
                    PA.coordinate_compare(value, destination, grader_wall_seconds=1)
                self.assertFalse(destination.exists())
                capture = io.StringIO()
                with redirect_stdout(capture):
                    code = PA.main(['--request', request['path'], '--bytes', str(request['bytes']),
                                    '--sha256', request['sha256']])
                self.assertEqual(code, 2)
                self.assertTrue(C.decode(capture.getvalue().encode()) ==
                     {'status': 'failed', 'failure_stage': 'public_admission', 'private_loader_calls': 0})
            self.assertEqual(source_loads, [], 'Policy mismatch reached scientific source/packet/reference loading')
            self.assertEqual(private_calls, [])
        # The correct selected policy traverses the real public policy join and
        # reaches the explicit generated stop, still before any private load.
        with compact_io(f), patch.object(PA.P, 'load_runtime', return_value=programme_runtime), \
             patch.object(V, 'load_runtime', return_value=RUNTIME), \
             self.assertRaisesRegex(RuntimeError, 'GENERATED_PUBLIC_BOUNDARY_STOP'):
            PA._public(config)
        self.assertEqual(len(source_loads), 1)
        self.assertEqual(private_calls, [])
        self.assertFalse((CONTROL / 'NEVER_PRIVATE_TARGETS').exists())
        snapshot()

    def test_11_original_state_remains_after_selected_collection_and_public_paths(self):
        for name, module in [('EP', EP), ('V', V), ('RP', RP)]:
            self.assertTrue(set(module.__dict__) == set(DONOR_GLOBALS[name]), 'Donor namespace changed')
            self.assertTrue(all(module.__dict__[key] is value for key, value in DONOR_GLOBALS[name].items()),
                            'Donor global identity changed')
            self.assertTrue(simple_globals(module) == DONOR_MUTABLE[name], 'Donor mutable declaration changed')
        self.assertTrue(encode(RUNTIME['source']) == RUNTIME_SOURCE)
        self.assertNotIn('_epoch_reasoning_policy', RUNTIME)
        self.assertNotIn('_epoch_reasoning_adapter', RUNTIME)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EpochReasoningControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    charged = snapshot()
    report = {'classification': 'GENERATED_COMPONENT_ONLY', 'tests_run': result.testsRun,
              'success': result.wasSuccessful(), 'failures': len(result.failures), 'errors': len(result.errors),
              'created_file_bytes': sum(CREATION.values()), 'created_files': len(CREATION),
              'extra_write_bytes': sum(row['bytes'] for row in EXTRA_WRITES),
              'cumulative_fixture_write_bytes': charged, 'extra_writes': EXTRA_WRITES,
              'artifact_cap_bytes': MAX_ARTIFACTS, 'native_predictions': 0,
              'provider_execution_qualified': False, 'scientific_qualification': False,
              'complete_cohort_admission': False, 'token_bound_qualified': False,
              'python_version_observed': sys.version, 'numpy_version_observed': np.__version__,
              'runtime_binary_closure_qualified': False}
    report['whole_roster_control'] = {'targets': 5450, 'people': 2,
          'real_collector_first_answers_submission_and_policy_join': True,
          'mocked_seams': ['source-freeze admission of generated source marker',
                          'virtual per-target descriptors and projection payloads',
                          'per-target audit results in complete-roster collection only',
                          'programme runtime and waveform runtime loading in public boundary controls'],
          'actual_adapter_two_turn_run_and_audit_separate': True,
          'protected_private_target_calls': 0}
    (CONTROL / 'CONTROL_RESULT.json').write_bytes(encode(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)

"""Generated in-memory ownership/grade controls; no process, cgroup or data use.

The fake metadata store checks hashes and records publication ordering. It does
not qualify fsync, Linux containment, Docker, scientific packages or execution.
"""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common
import journal
import runner

encoded, pin = common.encoded, common.pin
CONDITIONS = common.CONDITIONS
SOURCE = pin(b'generated-owner-source')
DEPLOYMENT = pin(b'generated-unqualified-deployment')
ROOT = Path('/generated/smc-owner')
OUTPUT = Path('/generated/smc-output')
RESOURCE_POLICY = 'measured_caps_and_oom_kill_v1'


class MaterialBindingControls(unittest.TestCase):
    def test_owner_source_closes_over_selected_material_and_unresolved_deployment(self):
        self.assertEqual(runner.legacy.source_identity(), pin((HERE / 'SOURCE.json').read_bytes()))
        episode = runner.legacy.load()
        self.assertEqual(episode.source_identity(), runner.legacy.LEGACY_SOURCE)
        self.assertEqual(episode.material_binding()['new_pair'],
                         {'bytes': 5658, 'sha256': 'a88725a6d3b8c7509826d7c9a4034c796a04635e4bce80cb887468e688f976bc'})
        with self.assertRaisesRegex(ValueError, 'unresolved_deployment_binding'):
            episode.deployment_binding()

    def test_owner_source_rejects_stale_episode_dependency(self):
        previous = {'bytes': 1487, 'sha256': '4aa4bbc6573ba6f71fc3e56bc5e23dac91547622b5921c96338141a5e8c5ce41'}
        with patch.object(runner.legacy, 'LEGACY_SOURCE', previous):
            with self.assertRaisesRegex(ValueError, 'Exact successor and predecessor closure'):
                runner.legacy.source_identity()


class MemoryFiles:
    def __init__(self):
        self.files = {}
        self.trace = []
        self.fail_publication = False

    def put(self, path, value):
        raw = encoded(value)
        self.files[str(path)] = raw
        return pin(raw)

    def body(self, path, expected=None, cap=common.FRAME_CAP):
        raw = self.files[str(path)]
        if len(raw) > cap or (expected is not None and pin(raw) != expected):
            raise ValueError('Generated immutable metadata mismatch')
        return raw

    def read(self, path, expected=None, cap=common.FRAME_CAP):
        return common.parse(self.body(path, expected, cap))

    def publish(self, path, value, **_):
        if self.fail_publication:
            raise OSError('generated publication failure')
        result = self.put(path, value)
        self.trace.append(('published', value.get('message', {}).get('event'), str(path)))
        return result


def limits():
    return {'cpu_seconds': 7200, 'producer_seconds': 10800, 'memory_bytes': 8589934592,
            'cpu_nanos': 6000000000, 'pids': 32, 'scratch_bytes': 536870912}


def plan(invocation, invocation_pin, phase, _runtime=None):
    name = 'smc-' + invocation['aggregate_nonce'] + ('-a' if phase == CONDITIONS[0] else '-b')
    return {'schema': 'smc_cgroup_plan_v1', 'phase_id': phase, 'name': name,
            'parent': '/generated/cgroup', 'path': '/generated/cgroup/' + name,
            'cgroup_parent': '/generated-delegation/' + name,
            'deployment_pin': invocation['deployment_pin'], 'invocation_pin': invocation_pin}


class FakeScopes:
    def __init__(self, files):
        self.files = files
        self.prepared, self.attached = set(), set()
        self.fail_prepare = self.fail_finish = False
        self.after_prepare = lambda: None

    def prepare(self, phase, selected_plan, selected_limits, *, intent_ref, request_pin):
        event = self.files.read(intent_ref['path'], {k: intent_ref[k] for k in ('bytes', 'sha256')})
        row = event['message']['value']['record']
        assert row['event'] == 'CGROUP-INTENT'
        assert row['request_sha256'] == request_pin['sha256']
        assert row['value'] == {'plan': selected_plan, 'limits': selected_limits}
        self.files.trace.append(('prepare', phase))
        if self.fail_prepare:
            raise ValueError('generated scope creation refusal')
        self.prepared.add(phase)
        self.after_prepare()

    def attach(self, phase, value):
        assert phase in self.prepared and phase not in self.attached
        self.attached.add(phase)
        self.files.trace.append(('attach', phase, value['container_id']))

    def finish(self, phase):
        self.files.trace.append(('finish', phase))
        if self.fail_finish or phase not in self.attached:
            raise ValueError('generated missing or over-cap terminal counters')
        return {'complete': True, 'within_limits': True, 'receipt_pin': pin(b'generated-terminal-counter-proof')}


class JournalHarness:
    def __init__(self):
        self.files = MemoryFiles()
        self.now = 10.0
        self.invocation = {'output': str(OUTPUT), 'owner': str(ROOT),
            'protocol_path': '/generated/protocol/PROTOCOL.json', 'protocol_pin': pin(b'protocol'),
            'source': SOURCE, 'aggregate_nonce': 'a' * 32, 'deployment_pin': DEPLOYMENT,
            'clock': {'origin': 1.0, 'controller_deadline': 100.0, 'deadline': 160.0,
                      'outcome': 'improvement', 'clock_identity': 'linux:generated'}}
        self.invocation_pin = pin(encoded(self.invocation))
        self.runtime = {'image': 'sha256:' + 'b' * 64}
        self.protocol = {'source': pin(b'episode-source'), 'outcome': 'improvement'}
        self.legacy = SimpleNamespace(REQUEST_SCHEMA='smc_aggregate_phase_request_v1',
            JOURNAL_SCHEMA='smc_aggregate_transport_journal_v1',
            OWNERSHIP_SCHEMA='smc_aggregate_phase_ownership_v1', TRANSPORT_SHA='d' * 64,
            COMMAND=['/usr/local/bin/python', '-I', '-S', '-B', '/runner/worker.py'],
            admit_protocol=lambda *_: (self.protocol, self.runtime),
            resources=lambda *_: limits(), aggregate_plan=plan, read=self.files.read,
            validate_closed=lambda *_: None)
        self.scopes = FakeScopes(self.files)
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(journal, 'ordinary', lambda path: Path(path)))
        self.stack.enter_context(patch.object(journal, 'body', self.files.body))
        self.stack.enter_context(patch.object(journal.time, 'monotonic', lambda: self.now))
        self.subject = journal.ParentJournal(ROOT / 'events', self.invocation, self.invocation_pin,
            SOURCE, self.legacy, SimpleNamespace(capture=Mock()), self.files, self.scopes)

    def close(self):
        self.stack.close()

    def call(self, name, value, **kwargs):
        message = {'schema': 'smc_owner_rpc_v1', 'invocation_pin': self.invocation_pin,
                   'sequence': self.subject.sequence, 'event': name, 'value': value}
        ack = self.subject.accept(message, **kwargs)
        assert ack == {'schema': 'smc_owner_ack_v1', 'sequence': message['sequence'],
                       'message_pin': pin(encoded(message))}
        self.files.trace.append(('ack', name))
        return ack

    def ready(self):
        self.call('CONTROLLER-READY', {'generated': True}, controller_check=lambda value: None)

    def request(self, phase):
        exposure = self.files.put(OUTPUT / 'jobs' / phase / 'EXPOSURE.json', {'generated_phase': phase})
        request = {'schema': self.legacy.REQUEST_SCHEMA, 'phase_id': phase, 'action': 'held_attempt',
            'role': 'A' if phase == CONDITIONS[0] else 'B', 'image': self.runtime['image'],
            'command': self.legacy.COMMAND, 'workdir': '/work', 'source': self.protocol['source'],
            'exposure': exposure, 'clock': {'origin': 1.0, 'phase_deadline': 100.0},
            'resources': limits(), 'aggregate': plan(self.invocation, self.invocation_pin, phase),
            'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        return request

    def prepared(self, phase, mutate=None, pretty=False):
        request = self.request(phase)
        if mutate:
            mutate(request)
        path = OUTPUT / 'jobs' / phase / 'REQUEST.json'
        descriptor = self.files.put(path, request)
        if pretty:
            raw = (json.dumps(request, indent=2) + '\n').encode()
            self.files.files[str(path)] = raw
            descriptor = pin(raw)
        return self.call('PREPARED', {'request': request, 'request_file': descriptor})

    def setup_pair(self):
        self.ready()
        for phase in CONDITIONS:
            self.prepared(phase)

    def provider(self, name, value, phase=CONDITIONS[0], mutate_row=None):
        row = {'schema': self.legacy.JOURNAL_SCHEMA, 'phase_id': phase,
            'request_sha256': pin(encoded(self.subject.prepared[phase]))['sha256'],
            'index': self.subject.indices[phase], 'event': name, 'value': value}
        if mutate_row:
            mutate_row(row)
        return self.call(name, {'record': row, 'pin': pin(encoded(row))})

    def own(self, phase=CONDITIONS[0]):
        prefix = 'osl-' + ('a' if phase == CONDITIONS[0] else 'b') * 24
        resources = {key: {'kind': 'volume' if key == 'volume' else 'container',
            'name': prefix + '-' + key, 'owner': prefix + '/' + key,
            'attempted': False, 'acknowledged': False} for key in ('volume', 'holder', 'producer')}
        owner = {'schema': self.legacy.OWNERSHIP_SCHEMA, 'phase_id': phase,
            'request_pin': pin(encoded(self.subject.prepared[phase])),
            'engine_source_pin': {'bytes': 1, 'sha256': self.legacy.TRANSPORT_SHA},
            'original_deadline': 160.0, 'phase_deadline': 90.0, 'attempt_prefix': prefix,
            'resources': resources, 'aggregate': self.subject.prepared[phase]['aggregate']}
        self.provider('OWNERSHIP', {'ownership': owner, 'ownership_pin': pin(encoded(owner))}, phase)

    def intent(self, phase=CONDITIONS[0]):
        request = self.subject.prepared[phase]
        return self.provider('CGROUP-INTENT', {'plan': request['aggregate'], 'limits': request['resources']}, phase)

    def producer(self, phase=CONDITIONS[0]):
        resource = copy.deepcopy(self.subject.ownership[phase]['ownership']['resources']['producer'])
        resource.update(attempted=True, acknowledged=True, id='c' * 64)
        self.provider('RESOURCE-ACK', resource, phase)

    def attachment(self, phase=CONDITIONS[0], container_id='c' * 64):
        return self.provider('CGROUP-ATTACHED', {'pid': 1234, 'container_id': container_id,
            'cgroup_parent': self.subject.prepared[phase]['aggregate']['cgroup_parent']}, phase)

    def final(self, phase=CONDITIONS[0]):
        return self.provider('CGROUP-FINAL', {'plan': self.subject.prepared[phase]['aggregate']}, phase)


class JournalControls(unittest.TestCase):
    def harness(self):
        value = JournalHarness()
        self.addCleanup(value.close)
        return value

    def test_prepared_refuses_rehashed_noncanonical_request_bytes(self):
        h = self.harness(); h.ready()
        with self.assertRaises(ValueError):
            h.prepared(CONDITIONS[0], pretty=True)
        self.assertNotIn(CONDITIONS[0], h.subject.prepared)

    def test_prepared_binds_profile_clock_invocation_and_deployment(self):
        changes = [lambda r: r['resources'].update(memory_bytes=4294967296),
            lambda r: r['clock'].update(origin=2.0),
            lambda r: r['aggregate'].update(invocation_pin=pin(b'other-invocation')),
            lambda r: r['aggregate'].update(deployment_pin=pin(b'other-deployment'))]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                h = self.harness(); h.ready()
                with self.assertRaises(ValueError): h.prepared(CONDITIONS[0], mutate=change)

    def test_both_requests_precede_any_provider_ownership(self):
        h = self.harness(); h.ready(); h.prepared(CONDITIONS[0])
        with self.assertRaises(ValueError): h.own()
        self.assertEqual(h.subject.ownership, {})

    def test_intent_publication_precedes_scope_creation_and_ack(self):
        h = self.harness(); h.setup_pair(); h.own(); h.intent()
        tail = h.files.trace[-3:]
        self.assertEqual(tail[0][:2], ('published', 'CGROUP-INTENT'))
        self.assertEqual(tail[1], ('prepare', CONDITIONS[0]))
        self.assertEqual(tail[2], ('ack', 'CGROUP-INTENT'))

    def test_failed_publication_or_prepare_never_acknowledges_release(self):
        for stage in ('publication', 'prepare'):
            with self.subTest(stage=stage):
                h = self.harness(); h.setup_pair(); h.own()
                h.files.fail_publication = stage == 'publication'
                h.scopes.fail_prepare = stage == 'prepare'
                with self.assertRaises((OSError, ValueError)): h.intent()
                self.assertNotIn(('ack', 'CGROUP-INTENT'), h.files.trace)
                self.assertNotIn(CONDITIONS[0], h.subject.aggregate_started)
                if stage == 'publication':
                    self.assertFalse(any(row[0] == 'prepare' for row in h.files.trace))

    def test_post_publication_original_deadline_refuses_ack(self):
        h = self.harness(); h.setup_pair(); h.own()
        h.scopes.after_prepare = lambda: setattr(h, 'now', 100.0)
        with self.assertRaises(ValueError): h.intent()
        self.assertIn(CONDITIONS[0], h.scopes.prepared)
        self.assertNotIn(('ack', 'CGROUP-INTENT'), h.files.trace)

    def test_cli_release_requires_observed_aggregate_ownership(self):
        h = self.harness(); h.setup_pair(); h.own()
        event = {'index': 0, 'phase': 'generated', 'cap': 1024, 'original_end': 80.0}
        with self.assertRaises(ValueError): h.provider('CLI-INTENT', event)
        self.assertEqual(h.subject.intents, {})

    def test_attachment_requires_original_acknowledged_producer_id(self):
        for producer, identity in ((False, 'c' * 64), (True, 'd' * 64)):
            with self.subTest(producer=producer):
                h = self.harness(); h.setup_pair(); h.own(); h.intent()
                if producer: h.producer()
                with self.assertRaises(ValueError): h.attachment(container_id=identity)
                self.assertEqual(h.scopes.attached, set())

    def test_duplicate_aggregate_events_cannot_reuse_authority(self):
        h = self.harness(); h.setup_pair(); h.own(); h.intent()
        with self.assertRaises(ValueError): h.intent()
        h.producer(); h.attachment()
        with self.assertRaises(ValueError): h.attachment()
        h.final()
        with self.assertRaises(ValueError): h.final()

    def test_counter_finish_failure_has_no_ack_or_success(self):
        h = self.harness(); h.setup_pair(); h.own(); h.intent(); h.producer(); h.attachment()
        h.scopes.fail_finish = True
        with self.assertRaises(ValueError): h.final()
        self.assertNotIn(('ack', 'CGROUP-FINAL'), h.files.trace)
        self.assertEqual(h.subject.aggregate_final, {})
        self.assertEqual(h.subject.closed, set())

    def test_rehashed_provider_record_still_binds_request_and_sequence(self):
        for change in (lambda r: r.update(request_sha256='f' * 64), lambda r: r.update(index=r['index'] + 1)):
            h = self.harness(); h.setup_pair(); h.own()
            request = h.subject.prepared[CONDITIONS[0]]
            with self.assertRaises(ValueError):
                h.provider('CGROUP-INTENT', {'plan': request['aggregate'], 'limits': request['resources']}, mutate_row=change)


class GradeFixture:
    """Rehash every edited fixture so predicates, not stale outer pins, are tested."""
    def __init__(self, mutation=None, pretty_request=False):
        self.files = MemoryFiles()
        self.mutate = mutation or (lambda _stage, _phase, _doc: None)
        self.invocation = {'output': str(OUTPUT), 'protocol_path': '/generated/protocol/PROTOCOL.json',
            'protocol_pin': pin(b'protocol'), 'source': SOURCE, 'aggregate_nonce': 'a' * 32,
            'deployment_pin': DEPLOYMENT,
            'clock': {'origin': 1.0, 'deadline': 22561.0, 'controller_deadline': 22501.0,
                      'outcome': 'improvement', 'clock_identity': 'linux:generated'}}
        self.invocation_pin = self.files.put(ROOT / 'INVOCATION.json', self.invocation)
        self.clock = self.invocation['clock']
        closure = {'schema': 'smc_parent_observed_controller_closure_v1', 'source': SOURCE,
            'invocation_pin': self.invocation_pin, 'clock': self.clock,
            'future_controller_and_acknowledged_cli_release_closed': True,
            'controller_group': {'absence_verified': True},
            'acknowledged_cli': {'all_acknowledged_cli_absent': True}}
        self.mutate('controller_closure', None, closure)
        closure_pin = self.files.put(ROOT / 'CONTROLLER_CLOSED.json', closure)
        natural, closed, phases = {}, {}, {}
        for phase in CONDITIONS:
            selected_plan = plan(self.invocation, self.invocation_pin, phase)
            request = {'schema': 'smc_aggregate_phase_request_v1', 'phase_id': phase,
                'resources': limits(), 'aggregate': selected_plan,
                'clock': {'origin': self.clock['origin'], 'phase_deadline': self.clock['controller_deadline']}}
            self.mutate('request', phase, request)
            request_path = OUTPUT / 'jobs' / phase / 'REQUEST.json'
            request_pin = self.files.put(request_path, request)
            if pretty_request:
                raw = (json.dumps(request, indent=2) + '\n').encode()
                self.files.files[str(request_path)] = raw
                request_pin = pin(raw)
            owner = {'schema': 'smc_aggregate_scope_owner_v1', 'phase_id': phase,
                'source': SOURCE, 'invocation_pin': self.invocation_pin, 'clock': self.clock,
                'request_pin': request_pin, 'plan': request['aggregate'], 'limits': request['resources']}
            self.mutate('owner', phase, owner)
            owner_pin = self.files.put(ROOT / ('CGROUP-' + phase + '-OWNER.json'), owner)
            producer = {'source': SOURCE, 'invocation_pin': self.invocation_pin, 'clock': self.clock,
                'request_pin': request_pin, 'owner_pin': owner_pin,
                'event': {'pid': 1234, 'container_id': 'c' * 64, 'cgroup_parent': selected_plan['cgroup_parent']}}
            self.mutate('attached', phase, producer)
            self.files.put(ROOT / ('CGROUP-' + phase + '-ATTACHED.json'), producer)
            counter = {'cpu_usage_usec': 1000, 'cpu_stat': {'usage_usec': 1000, 'user_usec': 800, 'system_usec': 200},
                'memory_peak_bytes': 1024,
                'memory_events': {'low': 0, 'high': 0, 'max': 0, 'oom': 0, 'oom_kill': 0, 'oom_group_kill': 0},
                'pids_events': {'max': 0}, 'cgroup_events_before': {'populated': 0, 'frozen': 0},
                'cgroup_events': {'populated': 0, 'frozen': 0}}
            for stage, destination in (('finished', natural), ('closed', closed)):
                receipt = {'schema': 'smc_aggregate_scope_receipt_v1', 'phase_id': phase,
                    'source': SOURCE, 'invocation_pin': self.invocation_pin, 'clock': self.clock,
                    'request_pin': request_pin, 'plan': request['aggregate'], 'limits': request['resources'],
                    'owner_pin': owner_pin, 'producer': producer, 'counters': copy.deepcopy(counter),
                    'empty': True, 'within_limits': True, 'complete': True, 'errors': [],
                    'zero_cpu_overshoot_claim': False, 'resource_policy': RESOURCE_POLICY}
                self.mutate(stage, phase, receipt)
                receipt_pin = self.files.put(ROOT / ('CGROUP-' + phase + '-' + stage.upper() + '.json'), receipt)
                destination[phase] = {**copy.deepcopy(receipt), 'receipt_pin': receipt_pin}
            ownership_pin = pin(encoded({'generated_provider_owner': phase}))
            docker_receipt = {'schema': 'smc_aggregate_phase_receipt_v1', 'phase_id': phase,
                'request_sha256': request_pin['sha256'], 'ownership_pin': ownership_pin,
                'all_native_resources_closed': True}
            self.mutate('provider_receipt', phase, docker_receipt)
            path = OUTPUT / 'control' / phase / 'RECEIPT.json'
            receipt_pin = self.files.put(path, docker_receipt)
            phases[phase] = {'request_pin': request_pin, 'ownership_pin': ownership_pin,
                'receipt_pin': receipt_pin, 'receipt_path': str(path),
                'all_resources_closed': True, 'producer_container_id': 'c' * 64}
        provider = {'schema': 'smc_aggregate_provider_closure_v1', 'invocation_pin': self.invocation_pin,
            'source': SOURCE, 'clock': self.clock, 'controller_closure_pin': closure_pin,
            'phases': phases, 'recovery_cli_absent': True}
        self.mutate('provider_document', None, provider)
        provider_pin = self.files.put(ROOT / 'PROVIDER_CLOSED.json', provider)
        close_doc = {'schema': 'smc_aggregate_closed_v1', 'invocation_pin': self.invocation_pin,
            'source': SOURCE, 'clock': self.clock, 'controller_closure_pin': closure_pin,
            'value': {'controller_closure_pin': closure_pin, 'scopes': closed,
                      'complete': True, 'all_scopes_empty': True, 'counters_complete': True, 'within_limits': True}}
        self.mutate('closed_wrapper', None, close_doc)
        close_pin = self.files.put(ROOT / 'AGGREGATE_CLOSED.json', close_doc)
        remove_doc = {'schema': 'smc_aggregate_removed_v1', 'invocation_pin': self.invocation_pin,
            'source': SOURCE, 'clock': self.clock, 'provider_closure_pin': provider_pin,
            'value': {'provider_closure_pin': provider_pin, 'scopes': {p: True for p in CONDITIONS},
                      'complete': True, 'all_scopes_removed': True}}
        self.mutate('removed_wrapper', None, remove_doc)
        remove_pin = self.files.put(ROOT / 'AGGREGATE_REMOVED.json', remove_doc)
        pair = {'owner_invocation_pin': self.invocation_pin, 'owner_source': SOURCE,
            'protocol_path': self.invocation['protocol_path'], 'protocol_sha256': self.invocation['protocol_pin']['sha256'],
            'outcome': self.clock['outcome']}
        pair_pin = self.files.put(OUTPUT / 'PAIR_CLOSED.json', pair)
        self.result = {'status': 'closed_pair', 'error': None, 'recovery_error': None, 'cleanup_errors': [],
            'source': SOURCE, 'invocation_pin': self.invocation_pin, 'controller_closure_pin': closure_pin,
            'pair_closed_pin': pair_pin, 'recovery_cli': {'all_acknowledged_cli_absent': True},
            'controller_execution': {'natural_exit': True},
            'aggregate': {'close_pin': close_pin, 'remove_pin': remove_pin,
                          'provider_closure_pin': provider_pin, 'phase_proofs': natural}}
        self.result_pin = self.files.put(ROOT / 'RESULT.json', self.result)
        self.private = Mock(return_value={'generated_private_grade_reached': True})

    def grade(self):
        with patch.object(runner, 'ordinary', lambda p: Path(p)), \
                patch.object(runner, 'body', self.files.body), patch.object(runner, 'read', self.files.read), \
                patch.object(runner.legacy, 'source_identity', lambda: SOURCE), \
                patch.object(runner.legacy, 'load', lambda: SimpleNamespace(_grade_from_owned_pair=self.private)):
            return runner.grade(ROOT, self.result_pin['sha256'], Path('/never-read/target'),
                                Path('/never-read/scorer'), Path('/never-written/result'), 1)


class GradeControls(unittest.TestCase):
    def refused_before_private_grade(self, fixture):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            fixture.grade()
        fixture.private.assert_not_called()

    def test_complete_exact_parent_proofs_reach_private_grader_once(self):
        fixture = GradeFixture()
        self.assertEqual(fixture.grade(), {'generated_private_grade_reached': True})
        fixture.private.assert_called_once()

    def test_each_scope_proof_is_authenticated_before_target_access(self):
        for suffix in ('FINISHED', 'CLOSED', 'OWNER', 'ATTACHED'):
            with self.subTest(suffix=suffix):
                fixture = GradeFixture()
                path = ROOT / ('CGROUP-' + CONDITIONS[0] + '-' + suffix + '.json')
                fixture.files.files[str(path)] += b' '
                self.refused_before_private_grade(fixture)

    def test_rehashed_over_cap_cpu_peak_or_oom_kill_refused(self):
        changes = [lambda c: c.update(cpu_usage_usec=7200000001),
            lambda c: c.update(memory_peak_bytes=8589934593),
            lambda c: c['memory_events'].update(oom_kill=1),
            lambda c: c['memory_events'].update(oom_group_kill=1)]
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                def mutate(stage, phase, receipt):
                    if stage in ('finished', 'closed'): change(receipt['counters'])
                self.refused_before_private_grade(GradeFixture(mutate))

    def test_raw_cpu_table_cannot_disagree_with_summary(self):
        def mutate(stage, phase, receipt):
            if stage in ('finished', 'closed'):
                receipt['counters']['cpu_stat']['usage_usec'] = 7200000001
        self.refused_before_private_grade(GradeFixture(mutate))

    def test_missing_required_terminal_counter_is_unknown_not_zero(self):
        for key in ('oom_kill', 'max'):
            with self.subTest(key=key):
                def mutate(stage, phase, receipt):
                    if stage in ('finished', 'closed'):
                        table = 'memory_events' if key == 'oom_kill' else 'pids_events'
                        receipt['counters'][table].pop(key)
                self.refused_before_private_grade(GradeFixture(mutate))

    def test_handled_denials_and_reclaim_remain_observed_not_failure(self):
        def mutate(stage, phase, receipt):
            if stage in ('finished', 'closed'):
                receipt['counters']['memory_events'].update(max=3, oom=2)
                receipt['counters']['pids_events']['max'] = 4
        fixture = GradeFixture(mutate)
        fixture.grade()
        fixture.private.assert_called_once()

    def test_both_empty_observations_required(self):
        for key in ('cgroup_events_before', 'cgroup_events'):
            with self.subTest(key=key):
                def mutate(stage, phase, receipt):
                    if stage in ('finished', 'closed'): receipt['counters'][key]['populated'] = 1
                self.refused_before_private_grade(GradeFixture(mutate))

    def test_missing_condition_or_incomplete_removal_refused(self):
        for stage in ('closed_wrapper', 'removed_wrapper'):
            with self.subTest(stage=stage):
                def mutate(current, phase, document):
                    if current == stage:
                        if stage == 'closed_wrapper': document['value']['scopes'].pop(CONDITIONS[1])
                        else: document['value']['scopes'][CONDITIONS[1]] = False
                self.refused_before_private_grade(GradeFixture(mutate))

    def test_refreshed_clock_rebound_owner_or_container_refused(self):
        for selection in ('clock', 'owner', 'container'):
            with self.subTest(selection=selection):
                def mutate(stage, phase, doc):
                    if selection == 'clock' and stage == 'closed_wrapper':
                        doc['clock'] = {**doc['clock'], 'deadline': 999999.0}
                    if selection == 'owner' and stage == 'owner':
                        doc['invocation_pin'] = pin(b'replacement invocation')
                    if selection == 'container' and stage == 'attached':
                        doc['event']['container_id'] = 'e' * 64
                self.refused_before_private_grade(GradeFixture(mutate))

    def test_rehashed_noncanonical_request_refused_before_private_grade(self):
        self.refused_before_private_grade(GradeFixture(pretty_request=True))

    def test_missing_or_regressing_counters_refused(self):
        for selection in ('unknown', 'regression'):
            with self.subTest(selection=selection):
                def mutate(stage, phase, doc):
                    if stage == 'closed':
                        if selection == 'unknown': doc['counters'] = None
                        else:
                            doc['counters']['cpu_usage_usec'] = 999
                            doc['counters']['cpu_stat']['usage_usec'] = 999
                self.refused_before_private_grade(GradeFixture(mutate))


if __name__ == '__main__':
    observed = ('test_aggregate_owner.py', 'journal.py', 'runner.py', 'common.py',
                'cgroup.py', 'legacy.py', 'cli_custody.py', 'process_owner.py', 'trusted_controller.py')
    before = {name: pin((HERE / name).read_bytes()) for name in observed}
    print(json.dumps({'schema': 'smc_aggregate_owner_generated_source_v1',
                      'source_before': before, 'fixture_storage': 'in_memory_only'}), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = {name: pin((HERE / name).read_bytes()) for name in observed}
    stable = before == after
    print(json.dumps({'schema': 'smc_aggregate_owner_generated_result_v1',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'source_unchanged': stable, 'source_after': after,
        'fixture_files_written': 0, 'native_process_cgroup_or_scientific_execution': False}), flush=True)
    raise SystemExit(0 if result.wasSuccessful() and stable else 1)

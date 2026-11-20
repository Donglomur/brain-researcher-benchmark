"""Generated ACK controls; the caller supplies authenticated derived source bytes.

No filesystem, process, cgroup or Provider execution occurs in exercise_ack.
Production Channel and ParentJournal bodies run in isolated namespaces. Their
socket, monotonic clock, metadata store and cgroup observations are doubles.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
from types import SimpleNamespace


def _pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _provider_order(testcase, raw):
    """Static evidence only: the actual Provider is never imported or executed."""
    tree = ast.parse(raw, filename='selected_transport/provider.py')
    provider = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Provider')
    execute = next(n for n in provider.body if isinstance(n, ast.FunctionDef) and n.name == 'execute_phase')
    records = [n for n in execute.body if isinstance(n, ast.FunctionDef) and n.name == 'record']
    testcase.assertEqual(len(records), 1)
    tail = records[0].body[-1]
    testcase.assertIsInstance(tail, ast.Expr)
    testcase.assertIsInstance(tail.value, ast.Call)
    testcase.assertIsInstance(tail.value.func, ast.Name)
    testcase.assertEqual(tail.value.func.id, 'journal')
    testcase.assertEqual(len(tail.value.args), 2)
    release_calls = [n for n in ast.walk(execute) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name) and n.func.id == 'call'
        and any(isinstance(a, ast.Constant) and a.value == 'producer_release' for a in n.args)]
    testcase.assertEqual(len(release_calls), 1)
    matches = []
    for block in (n.body for n in ast.walk(execute) if isinstance(n, ast.Try)):
        for index, statement in enumerate(block[:-1]):
            call = statement.value if isinstance(statement, ast.Expr) else None
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == 'record' and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value == 'CGROUP-ATTACHED'):
                following = block[index + 1]
                testcase.assertIn(release_calls[0], list(ast.walk(following)))
                matches.append((statement.lineno, following.lineno))
    testcase.assertEqual(len(matches), 1)
    testcase.assertLess(matches[0][0], release_calls[0].lineno)
    return {'attachment_line': matches[0][0], 'release_line': release_calls[0].lineno,
            'release_calls': 1, 'evidence': 'static AST only; no native Provider execution'}


def exercise_ack(testcase, derived_common_raw, derived_journal_raw, provider_raw,
                 artifact_root=None, accounting=None):
    """Run one combined ACK scenario set inside the parent's sole test method.

    Args are a unittest.TestCase, three already authenticated bytes values, an
    optional path used only as an in-memory label, and an optional mutable dict.
    The dict is incremented with source-compile, synthetic metadata and wire-byte
    counters. Return value is JSON-serializable. No public source globals change.
    """
    testcase.assertTrue(all(type(raw) is bytes for raw in
                            (derived_common_raw, derived_journal_raw, provider_raw)))
    if accounting is None:
        accounting = {}
    testcase.assertIs(type(accounting), dict)
    def charge(key, count):
        accounting[key] = accounting.get(key, 0) + count
    charge('ack_source_compile_input_bytes',
           len(derived_common_raw) + len(derived_journal_raw) + len(provider_raw))
    provider_order = _provider_order(testcase, provider_raw)
    common_tree = ast.parse(derived_common_raw, filename='derived_owner/common.py')
    journal_tree = ast.parse(derived_journal_raw, filename='derived_owner/journal.py')
    selected_names = {'FRAME_CAP', 'JOURNAL_CAP', 'EVENT_CAP', 'CONDITIONS', 'need',
                      'encoded', 'pin', 'parse', 'descriptor', 'frame', 'extract', 'Channel'}
    selected_nodes = []
    actual_names = set()
    for node in common_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in selected_names:
            selected_nodes.append(node); actual_names.add(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in selected_names:
                selected_nodes.append(node); actual_names.add(target.id)
    testcase.assertEqual(actual_names, selected_names)
    common_code = compile(ast.Module(body=selected_nodes, type_ignores=[]),
                          'derived_owner/common.py', 'exec')
    journal_nodes = [n for n in journal_tree.body if
                     isinstance(n, ast.Assign) or isinstance(n, ast.ClassDef) and n.name == 'ParentJournal']
    testcase.assertEqual([n.name for n in journal_nodes if isinstance(n, ast.ClassDef)], ['ParentJournal'])
    journal_code = compile(ast.Module(body=journal_nodes, type_ignores=[]),
                           'derived_owner/journal.py', 'exec')
    phase = 'validation_reference'
    source_pins = {'derived_common': _pin(derived_common_raw),
                   'derived_journal': _pin(derived_journal_raw), 'retained_provider': _pin(provider_raw)}
    base = Path('/generated/ack-control') if artifact_root is None else Path(artifact_root)
    cases = []

    class Fixture:
        def __init__(self, mode):
            self.mode, self.trace, self.files = mode, [], {}
            self.now = 10.0
            self.pending = b''
            self.active_event = None
            self.attach_calls = self.releases = 0
            self.publish_attempts = 0
            clock = SimpleNamespace(monotonic=lambda: self.now)
            self.common = {'__name__': 'generated_ack_common_' + mode, 'Path': Path,
                           'json': json, 'hashlib': hashlib, 're': re,
                           'struct': struct, 'time': clock}
            exec(common_code, self.common)
            testcase.assertEqual(self.common['CONDITIONS'], (phase,))
            self.encode, self.pin = self.common['encoded'], self.common['pin']
            self.owner_root = base / mode / 'owner'
            self.output = base / mode / 'output'
            self.source = self.pin(b'explicit generated source authority')
            self.invocation = {'output': str(self.output), 'owner': str(self.owner_root),
                'protocol_path': str(base / mode / 'protocol/PROTOCOL.json'),
                'protocol_pin': self.pin(b'generated protocol'), 'source': self.source,
                'aggregate_nonce': 'a' * 32, 'deployment_pin': self.pin(b'generated unqualified deployment'),
                'clock': {'origin': 1.0, 'controller_deadline': 100.0, 'deadline': 160.0,
                          'outcome': 'restricted_validation_reference', 'clock_identity': 'linux:generated'}}
            self.invocation_pin = self.pin(self.encode(self.invocation))
            self.runtime = {'image': 'sha256:' + 'b' * 64}
            self.protocol = {'source': self.pin(b'generated selected VALID episode'),
                             'outcome': 'restricted_validation_reference'}
            self.limits = {'cpu_seconds': 60000, 'producer_seconds': 10800,
                           'memory_bytes': 8589934592, 'cpu_nanos': 6000000000,
                           'pids': 32, 'scratch_bytes': 536870912}
            legacy = SimpleNamespace(REQUEST_SCHEMA='smc_aggregate_phase_request_v1',
                JOURNAL_SCHEMA='smc_aggregate_transport_journal_v1',
                OWNERSHIP_SCHEMA='smc_aggregate_phase_ownership_v1', TRANSPORT_SHA='d' * 64,
                COMMAND=['/usr/local/bin/python', '-I', '-S', '-B', '/runner/worker.py'],
                admit_protocol=lambda *_: (self.protocol, self.runtime),
                resources=lambda *_: copy.deepcopy(self.limits), aggregate_plan=self.plan,
                read=self.read, validate_closed=lambda *_: None)
            names = ('CONDITIONS', 'EVENT_CAP', 'JOURNAL_CAP', 'descriptor', 'encoded', 'need', 'pin')
            scope = {name: self.common[name] for name in names}
            scope.update(__name__='generated_ack_journal_' + mode, Path=Path, re=re, time=clock,
                         ordinary=lambda p: Path(p), body=self.body, publish=self.publish,
                         OwnerWriter=object)
            exec(journal_code, scope)
            self.journal = scope['ParentJournal'](self.owner_root / 'events', self.invocation,
                self.invocation_pin, self.source, legacy,
                SimpleNamespace(capture=self.unexpected_capture), self, self)
            self.channel = self.common['Channel'](self, self.invocation_pin, 100.0)
            self.channel('CONTROLLER-READY', {'generated_controller': True})
            exposure = self.put(self.output / 'jobs' / phase / 'EXPOSURE.json', {'generated_phase': phase})
            self.request = {'schema': legacy.REQUEST_SCHEMA, 'phase_id': phase, 'action': 'held_attempt',
                'role': 'B', 'image': self.runtime['image'], 'command': legacy.COMMAND,
                'workdir': '/work', 'source': self.protocol['source'], 'exposure': exposure,
                'clock': {'origin': 1.0, 'phase_deadline': 100.0},
                'resources': copy.deepcopy(self.limits), 'aggregate': self.plan(),
                'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
            request_pin = self.put(self.output / 'jobs' / phase / 'REQUEST.json', self.request)
            self.channel('PREPARED', {'request': self.request, 'request_file': request_pin})
            prefix = 'osl-' + 'a' * 24
            resources = {key: {'kind': 'volume' if key == 'volume' else 'container',
                'name': prefix + '-' + key, 'owner': prefix + '/' + key,
                'attempted': False, 'acknowledged': False} for key in ('volume', 'holder', 'producer')}
            ownership = {'schema': legacy.OWNERSHIP_SCHEMA, 'phase_id': phase,
                'request_pin': request_pin, 'engine_source_pin': {'bytes': 1, 'sha256': legacy.TRANSPORT_SHA},
                'original_deadline': 160.0, 'phase_deadline': 90.0, 'attempt_prefix': prefix,
                'resources': resources, 'aggregate': self.request['aggregate']}
            self.event('OWNERSHIP', {'ownership': ownership, 'ownership_pin': self.pin(self.encode(ownership))})
            self.event('CGROUP-INTENT', {'plan': self.request['aggregate'], 'limits': self.request['resources']})
            producer = copy.deepcopy(resources['producer'])
            producer.update(attempted=True, acknowledged=True, id='c' * 64)
            self.event('RESOURCE-ACK', producer)
            self.before_attachment = len(self.trace)

        def plan(self, *_):
            name = 'smc-' + 'a' * 32 + '-b'
            return {'schema': 'smc_cgroup_plan_v1', 'phase_id': phase, 'name': name,
                    'parent': '/generated/cgroup', 'path': '/generated/cgroup/' + name,
                    'cgroup_parent': '/generated-delegation/' + name,
                    'deployment_pin': self.invocation['deployment_pin'],
                    'invocation_pin': self.invocation_pin}

        def unexpected_capture(self, *_):
            raise AssertionError('ACK fixture must never capture an actual process')

        def put(self, path, document):
            raw = self.encode(document)
            charge('ack_generated_metadata_write_bytes', len(raw))
            self.files[str(path)] = raw
            return self.pin(raw)

        def body(self, path, expected=None, cap=2 * 1024**2):
            raw = self.files[str(path)]
            charge('ack_generated_metadata_read_bytes', len(raw))
            testcase.assertLessEqual(len(raw), cap)
            if expected is not None:
                testcase.assertEqual(self.pin(raw), expected)
            return raw

        def read(self, path, expected=None, cap=2 * 1024**2):
            return self.common['parse'](self.body(path, expected, cap))

        def publish(self, path, document, **_):
            event = document.get('message', {}).get('event')
            self.publish_attempts += 1
            self.trace.append(('publish', event))
            if event == 'CGROUP-ATTACHED' and self.mode == 'publication_error':
                charge('ack_generated_metadata_write_bytes', len(self.encode(document)))
                raise OSError('generated parent publication failure')
            return self.put(path, document)

        def prepare(self, selected_phase, selected_plan, limits, *, intent_ref, request_pin):
            testcase.assertEqual(selected_phase, phase)
            persisted = self.read(intent_ref['path'], {k: intent_ref[k] for k in ('bytes', 'sha256')})
            testcase.assertEqual(persisted['message']['event'], 'CGROUP-INTENT')
            testcase.assertEqual(persisted['message']['value']['record']['value'],
                                 {'plan': selected_plan, 'limits': limits})
            testcase.assertEqual(request_pin, self.pin(self.encode(self.request)))
            self.trace.append(('prepare', selected_phase))

        def attach(self, selected_phase, value):
            self.attach_calls += 1
            testcase.assertEqual(selected_phase, phase)
            testcase.assertEqual(value['container_id'], 'c' * 64)
            self.trace.append(('attach', selected_phase))
            if self.mode == 'attach_error':
                raise ValueError('generated attachment observation failed')
            if self.mode == 'expired_after_attach':
                self.now = 100.0

        def settimeout(self, value):
            testcase.assertGreater(value, 0)

        def sendall(self, raw):
            charge('ack_wire_write_bytes', len(raw))
            buf = bytearray(raw)
            message = self.common['extract'](buf)
            testcase.assertEqual(buf, bytearray())
            testcase.assertIsInstance(message, dict)
            self.active_event = message['event']
            self.trace.append(('send', self.active_event))
            check = (lambda _: self.trace.append(('controller_check', 'generated'))) \
                    if self.active_event == 'CONTROLLER-READY' else None
            ack = self.journal.accept(message, controller_check=check)
            self.trace.append(('parent_ack', self.active_event))
            if self.active_event == 'CGROUP-ATTACHED' and self.mode == 'wrong_ack':
                ack = {**ack, 'sequence': ack['sequence'] + 1}
            reply = self.common['frame'](ack)
            charge('ack_wire_write_bytes', len(reply))
            if self.active_event == 'CGROUP-ATTACHED' and self.mode == 'missing_ack':
                reply = b''
            elif self.active_event == 'CGROUP-ATTACHED' and self.mode == 'partial_ack':
                reply = reply[:7]
            self.pending = reply

        def recv(self, maximum):
            if self.active_event == 'CGROUP-ATTACHED' and self.mode == 'late_ack':
                self.now = 100.0
            chunk, self.pending = self.pending[:maximum], self.pending[maximum:]
            charge('ack_wire_read_bytes', len(chunk))
            self.trace.append(('recv', self.active_event))
            return chunk

        def event(self, name, value):
            row = {'schema': 'smc_aggregate_transport_journal_v1', 'phase_id': phase,
                   'request_sha256': self.pin(self.encode(self.request))['sha256'],
                   'index': self.journal.indices[phase], 'event': name, 'value': value}
            self.channel(name, {'record': row, 'pin': self.pin(self.encode(row))})

        def attachment_then_simulated_release(self):
            self.event('CGROUP-ATTACHED', {'pid': 1234, 'container_id': 'c' * 64,
                                         'cgroup_parent': self.request['aggregate']['cgroup_parent']})
            self.trace.append(('simulated_release', phase))
            self.releases += 1

    positive = Fixture('good')
    positive.attachment_then_simulated_release()
    testcase.assertEqual(positive.releases, 1)
    testcase.assertEqual(positive.attach_calls, 1)
    tail = positive.trace[positive.before_attachment:]
    positions = {key: next(i for i, row in enumerate(tail) if row[0] == key)
                 for key in ('publish', 'attach', 'parent_ack', 'recv', 'simulated_release')}
    testcase.assertLess(positions['publish'], positions['attach'])
    testcase.assertLess(positions['attach'], positions['parent_ack'])
    testcase.assertLess(positions['parent_ack'], positions['recv'])
    testcase.assertLess(positions['recv'], positions['simulated_release'])
    with testcase.assertRaisesRegex(ValueError, 'Exact aggregate producer attachment'):
        positive.attachment_then_simulated_release()
    testcase.assertEqual(positive.releases, 1)
    testcase.assertEqual(positive.attach_calls, 1)
    cases.append({'case': 'good_then_duplicate', 'release_count': 1, 'attachment_count': 1})

    for mode, reason, attach_calls, acknowledged in (
            ('missing_ack', 'closed without acknowledgement', 1, True),
            ('partial_ack', 'closed without acknowledgement', 1, True),
            ('wrong_ack', 'Exact synchronous persisted', 1, True),
            ('late_ack', 'received before original cutoff', 1, True),
            ('expired_after_attach', 'Durable acknowledgement still inside', 1, False),
            ('attach_error', 'attachment observation failed', 1, False),
            ('publication_error', 'parent publication failure', 0, False)):
        with testcase.subTest(ack_case=mode):
            fixture = Fixture(mode)
            with testcase.assertRaisesRegex((ValueError, OSError), reason):
                fixture.attachment_then_simulated_release()
            testcase.assertEqual(fixture.releases, 0)
            testcase.assertEqual(fixture.attach_calls, attach_calls)
            tail = fixture.trace[fixture.before_attachment:]
            testcase.assertEqual(any(row == ('parent_ack', 'CGROUP-ATTACHED') for row in tail), acknowledged)
            cases.append({'case': mode, 'release_count': 0, 'attachment_count': attach_calls,
                          'parent_ack_returned': acknowledged})

    testcase.assertLessEqual(sum(accounting.get(key, 0) for key in
        ('ack_generated_metadata_write_bytes', 'ack_generated_metadata_read_bytes',
         'ack_wire_write_bytes', 'ack_wire_read_bytes')), 256 * 1024)
    return {'schema': 'smc_validation_ack_generated_control_v1', 'cases': cases,
            'source_pins': source_pins, 'provider_order': provider_order,
            'accounting': {k: v for k, v in accounting.items() if k.startswith('ack_')},
            'actual_production_bodies': ['common.Channel', 'common.frame', 'common.extract',
                                        'journal.ParentJournal'],
            'external_doubles': ['socket', 'monotonic clock', 'metadata store and publication',
                                 'cgroup prepare/attachment observations', 'legacy selection metadata'],
            'simulated_release_only': True, 'native_Provider_executed': False,
            'physical_publication_or_attachment_qualified': False,
            'fixture_files_written': 0, 'source_globals_mutated': False}

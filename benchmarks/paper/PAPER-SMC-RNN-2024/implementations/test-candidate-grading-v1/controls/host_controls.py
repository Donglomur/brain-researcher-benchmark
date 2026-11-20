"""Generated TEST-host controls; no original selection or native qualification.

The main suite separately exercises real core completed-VALID admission. Here
that original-authority boundary is explicit/generated, while host metadata
joins, custody publication, actor construction, ordering and outcome code remain
real. Native/image authority and numerical score/proof inputs are generated;
the actual REPORT/SCALE_PROOF validator also runs.
"""
import builtins
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
from types import ModuleType, SimpleNamespace, FunctionType


def _clone(module, changes):
    ns = dict(module.__dict__)
    # FunctionType captures __builtins__ at construction, so bind the isolated
    # import boundary before cloning the child main function.
    ns.update(changes)
    for name, value in tuple(module.__dict__.items()):
        if (name not in changes and isinstance(value, FunctionType)
                and value.__globals__ is module.__dict__):
            new = FunctionType(value.__code__, ns, value.__name__, value.__defaults__, value.__closure__)
            new.__kwdefaults__ = value.__kwdefaults__
            ns[name] = new
    return SimpleNamespace(**ns)


def exercise_host(testcase, host_module, child_module, artifact_root):
    """Exercise actual host guards and publication with bounded generated files.

    artifact_root must exist outside source/Git and outside /tmp, /proc, /sys and
    /dev, because the real actor guards are retained. This creates one fresh
    host-fixtures child. No target arrays, source-authority proof, sockets,
    processes, signals, resource limits or numerical operations are executed.
    """
    h, c = host_module, child_module
    root = Path(artifact_root) / 'host-fixtures'
    testcase.assertTrue(root.parent.is_dir())
    testcase.assertFalse(root.exists())
    root.mkdir(mode=0o700)
    counters = {'generated_write_bytes': 0, 'generated_read_bytes': 0,
                'exclusive_failed_write_charge_bytes': 0, 'native_calls': 0}
    limit_write = 512 * 1024
    limit_read = 2 * 1024 * 1024
    def charge_write(size, failed=False):
        counters['generated_write_bytes'] += size
        if failed:
            counters['exclusive_failed_write_charge_bytes'] += size
        testcase.assertLessEqual(counters['generated_write_bytes'], limit_write)
    def charge_read(size):
        counters['generated_read_bytes'] += size
        testcase.assertLessEqual(counters['generated_read_bytes'], limit_read)
    def pin(raw):
        return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    def encoded(value):
        return h.encoded(value)
    def save(path, value):
        data = value if type(value) is bytes else encoded(value)
        charge_write(len(data))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        return {'path': str(path), **pin(data)}
    testcase.assertEqual((h.GRADE_MEMORY, h.CPU_SOFT, h.CPU_HARD, h.WORK_SECONDS, h.CLEANUP_SECONDS),
                         (2147483648, 600, 605, 720, 60))
    cases = []
    positive = None

    class Fixture:
        def __init__(self, mode):
            self.mode, self.trace = mode, []
            self.path = root / mode
            self.path.mkdir()
            self.inputs = self.path / 'inputs'
            self.inputs.mkdir()
            self.output = self.path / 'run'
            self.endpoint = self.path / 'daemon.sock'
            self.created = self.started = self.waited = self.owner_instances = 0
            self.alarms = []
            self.report_calls = 0
            self.cid = 'c' * 64
            self.runtime_source = save(self.inputs / 'runtime-source.json', b'generated runtime authority')
            self.protected = set()
            self.original = {'predictions': {}, 'freezes': {}}
            for role in ('reference', 'candidate'):
                row = save(self.inputs / (role + '.h5'), b'generated opaque ' + role.encode())
                self.original['predictions'][role] = row
                self.protected.add(row['path'])
                self.original['freezes'][role] = save(self.inputs / (role + '-freeze.json'),
                                                       {'generated_role': role, 'method_id': 'generated-method-' + role})
            for key in ('panel', 'protocol', 'target', 'evaluator'):
                self.original[key] = save(self.inputs / (key + '.json'), {'generated': key})
                if key in ('target', 'evaluator'):
                    self.protected.add(self.original[key]['path'])
            core_files = {name: save(self.inputs / 'core' / name, ('generated core ' + name).encode())
                          for name in sorted(h.CORE_NAMES)}
            self.core_manifest = {'schema': 'smc_test_gain_source_v1',
                                  'files': {name: {k: row[k] for k in ('bytes', 'sha256')}
                                            for name, row in core_files.items()}}
            self.core_source = save(self.inputs / 'core/SOURCE.json', self.core_manifest)
            adapter_files = {name: save(self.inputs / 'grader' / name, ('generated adapter ' + name).encode())
                             for name in sorted(h.ADAPTER_NAMES)}
            self.adapter_manifest = {'schema': 'smc_test_gain_grade_source_v1',
                'files': {name: {k: row[k] for k in ('bytes', 'sha256')}
                          for name, row in adapter_files.items()}, 'test_kernel': h.CORE_PIN}
            self.adapter_source = save(self.inputs / 'grader/SOURCE.json', self.adapter_manifest)
            self.selection = {'selected_index': 1,
                'ordered_scores': [{'gain': [1, 1], 'generated_score': 0.1},
                                   {'gain': [11, 10], 'generated_score': 0.2}]}
            self.selection_descriptor = save(self.inputs / 'VALID_SELECTION.json', self.selection)
            self.lineage = {'generated_unqualified_prior_validation': True}
            selected_row = copy.deepcopy(self.selection['ordered_scores'][1])
            if mode == 'wrong_selected_row':
                selected_row['gain'] = [5, 4]
            self.method = {'source': self.core_source, 'grader_source': self.adapter_source,
                'runtime_source': self.runtime_source, 'selected_row': selected_row,
                'inputs': {'valid_selection': self.selection_descriptor}, 'lineage': self.lineage}
            self.method_descriptor = save(self.inputs / 'TEST_METHOD.json', self.method)
            self.baseline_inputs = copy.deepcopy(self.original)
            self.baseline_inputs['predictions'].pop('candidate')
            self.baseline_inputs['freezes'].pop('candidate')
            self.template = {'schema': 'smc_test_gain_grade_request_v1', 'source': self.adapter_source,
                'test_method': self.method_descriptor, 'host_custody': None,
                **copy.deepcopy(self.original), 'output_root': str(self.output / 'report/test-pair'),
                'scratch_bytes': 65536}
            if mode == 'caller_custody':
                self.template['host_custody'] = save(self.inputs / 'FAKE_CUSTODY.json', {'claims_complete': True})
            if mode == 'wrong_inputs':
                self.template['target'] = save(self.inputs / 'other-target.json', {'generated': 'wrong target'})
                self.protected.add(self.template['target']['path'])
            self.template_descriptor = save(self.inputs / 'TEMPLATE.json', self.template)
            self.provenance_documents = {key: {'generated_external_authority': key}
                                         for key in h.PROVENANCE_PINS}
            self.provenance_rows = {key: {'path': str(self.inputs / ('prior-' + key + '.json')), **expected}
                                    for key, expected in h.PROVENANCE_PINS.items()}
            self.virtual = {row['path']: encoded(self.provenance_documents[key])
                            for key, row in self.provenance_rows.items()}
            self.provenance = {'image': {'Id': h.IMAGE_ID, 'Architecture': 'arm64',
                'Config': {'Labels': {'generated_label': 'selected'}, 'Env': ['PATH=/usr/local/bin:/usr/bin:/bin']}},
                'container_base_labels': {'generated_label': 'selected'},
                'prior_scope': 'Explicit external original image authority double, not native qualification'}
            self.request = {'schema': 'smc_test_gain_grade_host_request_v1', 'source': self.runtime_source,
                'token': 'a' * 32, 'docker': save(self.inputs / 'docker-fixture', b'not executable'),
                'socket': 'unix://' + str(self.endpoint), 'provenance': self.provenance_rows,
                'core_source': self.core_source, 'adapter_source': self.adapter_source,
                'child_request': self.template_descriptor, 'output_root': str(self.output)}
            self.request_descriptor = save(self.inputs / 'HOST_INPUT.json', self.request)
            self.api = None

        def read(self, value, cap=h.META_CAP):
            p = str(value)
            testcase.assertNotIn(p, self.protected, 'Host must not read generated scientific bodies')
            raw = h.read(value, cap)
            charge_read(len(raw))
            return raw

        def checked(self, row, cap=h.META_CAP):
            if row['path'] in self.virtual:
                key = next(k for k, v in self.provenance_rows.items() if v['path'] == row['path'])
                testcase.assertEqual(row, self.provenance_rows[key])
                self.trace.append(('external_prior_metadata', key))
                raw = self.virtual[row['path']]
                charge_read(len(raw))
                return raw
            h.descriptor(row)
            raw = self.read(row['path'], cap)
            testcase.assertEqual(pin(raw), {k: row[k] for k in ('bytes', 'sha256')})
            return raw

        def write(self, path, value, cap=h.META_CAP):
            data = encoded(value)
            exists = Path(path).exists()
            charge_write(len(data), failed=exists)
            self.trace.append(('write', Path(path).name))
            return h.write(path, value, cap)

        def selected_sources(self, row, expected, schema, names):
            self.trace.append(('external_source_admission', schema))
            if row == self.core_source:
                testcase.assertEqual(expected, h.CORE_PIN)
                testcase.assertEqual(schema, 'smc_test_gain_source_v1')
                testcase.assertEqual(names, h.CORE_NAMES)
                return copy.deepcopy(self.core_manifest)
            testcase.assertEqual(row, self.adapter_source)
            testcase.assertEqual(expected, h.ADAPTER_PIN)
            testcase.assertEqual(schema, 'smc_test_gain_grade_source_v1')
            testcase.assertEqual(names, h.ADAPTER_NAMES)
            return copy.deepcopy(self.adapter_manifest)

        def admit_method(self, descriptor):
            testcase.assertEqual(descriptor, self.method_descriptor)
            self.trace.append(('external_completed_selection', descriptor['sha256']))
            method = h.decode(self.checked(descriptor))
            selection = h.decode(self.checked(self.selection_descriptor))
            return {'record': method, 'inputs': copy.deepcopy(self.baseline_inputs),
                    'selection': selection, 'lineage': copy.deepcopy(self.lineage)}

        def admit_candidate(self, prediction, freeze, method, admitted):
            self.trace.append(('external_candidate_metadata', freeze['sha256']))
            testcase.assertEqual(prediction, self.original['predictions']['candidate'])
            testcase.assertEqual(freeze, self.original['freezes']['candidate'])
            testcase.assertEqual(method, self.method_descriptor)
            testcase.assertEqual(admitted['record'], self.method)
            return {'prediction': prediction, 'freeze': freeze}

        def load_source(self, path, expected, name):
            p = Path(path)
            if p.name == 'test_core.py':
                testcase.assertEqual(expected, self.core_manifest['files']['test_core.py'])
                return SimpleNamespace(admit_test_method=self.admit_method,
                                       admit_candidate_metadata=self.admit_candidate)
            testcase.assertIn(p.name, h.HELPERS)
            testcase.assertEqual(expected, h.HELPERS[p.name])
            return SimpleNamespace(preflight=lambda: self.trace.append(('external_OS_preflight', p.name)))

        def ordinary(self, value):
            p = h.ordinary(value)
            if p != self.endpoint:
                return p
            class SocketOperand:
                def __fspath__(inner): return str(p)
                def __str__(inner): return str(p)
                def lstat(inner): return SimpleNamespace(st_mode=stat.S_IFSOCK)
                def is_relative_to(inner, other): return p.is_relative_to(other)
            return SocketOperand()

        def labels(self, image, base):
            testcase.assertEqual(image, self.provenance['image']['Config']['Labels'])
            testcase.assertEqual(base, self.provenance['container_base_labels'])
            return base

        def process_record(self, stdout, returncode=0):
            return {'pid': 1234, 'returncode': returncode, 'stdout': stdout, 'errors': [],
                'cleanup': {'cleanup_complete': True, 'reaped': True, 'group_absence_observed': True,
                            'error': None, 'pid': 1234, 'returncode': returncode},
                'capture': {'all_eof_observed': True, 'storage_truncated': False,
                            'read_ceiling_exhausted': False, 'closed_without_eof': False,
                            'stream_close_errors': []}}

        def owner(self, config, own, capture, start):
            self.owner_instances += 1
            self.trace.append(('owner', 'generated_OS'))
            testcase.assertTrue((self.output / 'HOST_VALID_CUSTODY.json').is_file())
            testcase.assertTrue((self.output / 'CHILD_REQUEST.json').is_file())
            testcase.assertTrue(any(row[0] == 'external_completed_selection' for row in self.trace))
            fixture = self
            class Owner:
                def __init__(inner): inner.calls = []
                def inspect(inner, identifier, deadline):
                    if identifier.startswith('smc-test-gain-'):
                        return None
                    testcase.assertEqual(identifier, fixture.cid)
                    return {'Id': fixture.cid, 'State': {'Status': 'exited' if fixture.waited else 'created',
                        'Running': False, 'ExitCode': 0, 'OOMKilled': False, 'Error': ''}}
                def cli(inner, argv, deadline, label, *args):
                    testcase.assertEqual(deadline, 100.0 + h.WORK_SECONDS)
                    fixture.trace.append(('cli', label))
                    if label == 'create_test_gain_grade':
                        fixture.created += 1
                        testcase.assertEqual(argv[:2], ['container', 'create'])
                        testcase.assertEqual(argv[argv.index('--memory') + 1], str(h.GRADE_MEMORY))
                        testcase.assertEqual(argv[argv.index('--memory-swap') + 1], str(h.GRADE_MEMORY))
                        testcase.assertEqual(argv[argv.index('--cpus') + 1], '1')
                        testcase.assertIn('cpu=600:605', argv)
                        testcase.assertIn('core=0:0', argv)
                        testcase.assertEqual(argv.count('--entrypoint'), 1)
                        testcase.assertIn(str(fixture.inputs / 'grader/test_pair_child.py'), argv)
                        record = fixture.process_record(fixture.cid + '\n',
                            1 if fixture.mode == 'creation_failure' else 0)
                        if fixture.mode == 'uncertain_process_closure':
                            record['capture']['all_eof_observed'] = False
                    elif label == 'start_test_gain_grade':
                        fixture.started += 1
                        testcase.assertEqual(argv, ['container', 'start', fixture.cid])
                        record = fixture.process_record(fixture.cid + '\n')
                    else:
                        testcase.assertEqual(label, 'wait_test_gain_grade')
                        testcase.assertEqual(argv, ['container', 'wait', fixture.cid])
                        testcase.assertEqual(args, (h.WORK_SECONDS,))
                        fixture.waited += 1
                        out = Path(fixture.template['output_root'])
                        out.mkdir()
                        actual_request = fixture.api.reference(fixture.output / 'CHILD_REQUEST.json')
                        actual_child = h.decode(fixture.checked(actual_request))
                        save(out / 'REPORT.json', fixture.make_report(actual_child, actual_request['sha256']))
                        record = fixture.process_record('0\n')
                    row = save(fixture.output / 'calls' / (str(len(inner.calls)) + '.json'), record)
                    inner.calls.append(row)
                    return record
            return Owner()

        def verify(self, value, actor, built):
            testcase.assertEqual(value['Id'], self.cid)
            testcase.assertEqual(actor['role'], 'grade')
            testcase.assertEqual(built['memory'], h.GRADE_MEMORY)
            testcase.assertEqual(built['cpu_seconds'], 600)
            testcase.assertTrue(built['private_grading'])
            return self.cid

        def make_report(self, child, request_sha256):
            """Generate metadata only; no array, scale or numerical result claim."""
            output = Path(child['output_root'])
            versions = {'numpy': '1.26.3', 'scipy': '1.12.0', 'scikit-learn': '1.5.0', 'h5py': '3.10.0'}
            shapes = {'train_rates_heldin': [2295, 35, 137], 'train_rates_heldout': [2295, 35, 45],
                'eval_rates_heldin': [574, 35, 137], 'eval_rates_heldout': [574, 35, 45],
                'eval_rates_heldin_forward': [574, 10, 137], 'eval_rates_heldout_forward': [574, 10, 45],
                'train_rates_heldin_forward': [2295, 10, 137], 'train_rates_heldout_forward': [2295, 10, 45]}
            gain = self.method['selected_row']['gain']
            executions = {}
            for index, name in enumerate(sorted(shapes)):
                small = index % 2 == 0
                scalar = float(gain[0]) / gain[1]
                if small:
                    scalar = h.struct.unpack('!f', h.struct.pack('!f', scalar))[0]
                executions[name] = {'gain': gain, 'dtype': '<f4' if small else '<f8',
                    'arithmetic_dtype': 'float32' if small else 'float64', 'value_hex': scalar.hex()}
            snapshots = {role: {'path': str(output / 'snapshots' / (role + '.h5')),
                **{key: child['predictions'][role][key] for key in ('bytes', 'sha256')}}
                for role in ('reference', 'candidate')}
            started = save(output / 'STARTED.json', {'schema': 'smc_test_gain_grade_started_v1',
                'request_sha256': request_sha256, 'source': child['source'],
                'host_custody': child['host_custody'], 'test_method': child['test_method'],
                'phase': 'test', 'inference_executed': False})
            proof = save(output / 'SCALE_PROOF.json', {'schema': 'smc_test_gain_scale_proof_v1',
                'gain': gain, 'reference': {key: child['predictions']['reference'][key] for key in ('bytes', 'sha256')},
                'candidate': {key: child['predictions']['candidate'][key] for key in ('bytes', 'sha256')},
                'rate_fields': sorted(shapes), 'shapes': shapes, 'metadata_sha256': 'a' * 64,
                'executed_gains': executions, 'all_eight_fields_exact': True,
                'identity_whole_file_equal': gain == [1, 1], 'target_accessed': False,
                'inference_execution_qualified': False})
            barrier = save(output / 'BOTH_SNAPSHOTS.json', {'schema': 'smc_test_gain_both_snapshots_v1',
                'request_sha256': request_sha256, 'source': child['source'],
                'host_custody': child['host_custody'], 'test_method': child['test_method'],
                'snapshots': snapshots, 'freezes': child['freezes'], 'scale_proof': proof,
                'both_complete_original_freezes_validated': True,
                'candidate_transform_verified': True, 'target_payload_accessed': False})
            values = {'reference': {'co-bps': 0.2, 'vel R2': 0.1, 'psth R2': 0.3, 'fp-bps': 0.4},
                      'candidate': {'co-bps': 0.25, 'vel R2': 0.12, 'psth R2': 0.32, 'fp-bps': 0.45}}
            source = h.decode(self.checked(child['source']))
            arms = {}
            for role in ('reference', 'candidate'):
                freeze = h.decode(self.checked(child['freezes'][role]))
                score = save(output / (role + '-score.json'), {'schema': 'smc_nlb_operator_score_v1',
                    'arm': 'noncausal', 'role': 'author_calibration' if role == 'reference' else 'candidate',
                    'method_id': freeze['method_id'], 'metrics': values[role],
                    'submission_sha256': child['predictions'][role]['sha256'],
                    'prediction_freeze_sha256': child['freezes'][role]['sha256'],
                    'panel_manifest_sha256': child['panel']['sha256'],
                    'protocol_sha256': child['protocol']['sha256'],
                    'reference_panel_sha256': source['files']['reference_panel.json']['sha256'],
                    'scorer_sha256': child['evaluator']['sha256'], 'target_sha256': child['target']['sha256'],
                    'dependency_versions': versions})
                arms[role] = {'metrics': values[role], 'snapshot': snapshots[role], 'score_report': score}
            return {'schema': 'smc_test_gain_pair_grade_v1', 'status': 'both_test_predictions_scored',
                'phase': 'test', 'dataset': 'mc_maze_20', 'request_sha256': request_sha256,
                'source': child['source'], 'host_custody': child['host_custody'],
                'test_method': child['test_method'], 'selected_row': self.method['selected_row'],
                'lineage': self.lineage, 'barrier': barrier, 'scale_proof': proof, 'started': started,
                'arms': arms, 'signed_candidate_minus_reference':
                    {key: values['candidate'][key] - values['reference'][key] for key in values['reference']},
                'dependency_versions': versions,
                'intentional_environment_variant': {'package': 'h5py', 'historical': '3.11.0', 'selected': '3.10.0'},
                'full_four_vectors': True, 'historical_noncausal_supervisor_success': False,
                'new_inference_executed': False, 'participant_episode_executed': False, 'AI_trial_executed': False,
                'scientific_equivalence': None, 'reproduction_claim': False, 'improvement_claim': False,
                'SOTA_claim': False, 'target_exposure': 'public_original_test_targets_released_2026_01'}

        def numerical_report(self, report, child, request_sha256):
            self.report_calls += 1
            self.trace.append(('real_report_validator', request_sha256))
            validator = _clone(h, {'read': self.read, 'checked': self.checked})
            testcase.assertIs(validator.validate_report.__code__, h.validate_report.__code__)
            result = validator.validate_report(report, child, request_sha256)
            self.validated_report = copy.deepcopy(report)
            self.validated_child = copy.deepcopy(child)
            self.validated_request_sha = request_sha256
            return result

        def report_refusals(self):
            """Real metadata validator, rehashed virtual corruptions, no data scan."""
            refusals = []
            for mode, reason in (
                    ('gain', 'all eight exact TEST/TRAIN field transformations'),
                    ('proof_shape', 'all eight exact TEST/TRAIN field transformations'),
                    ('score_source', 'unchanged original canonical per-role score joins'),
                    ('vector', 'complete finite canonical four-metric vector'),
                    ('delta', 'all four signed candidate-minus-reference metrics')):
                with testcase.subTest(host_report_case=mode):
                    report = copy.deepcopy(self.validated_report)
                    virtual = {}
                    def replace(row, value):
                        raw = encoded(value); charge_write(len(raw))
                        virtual[row['path']] = raw
                        return {'path': row['path'], **pin(raw)}
                    def checked(row, cap=h.META_CAP):
                        if row['path'] not in virtual:
                            return self.checked(row, cap)
                        h.descriptor(row); raw = virtual[row['path']]
                        testcase.assertLessEqual(len(raw), cap); charge_read(len(raw))
                        testcase.assertEqual(pin(raw), {key: row[key] for key in ('bytes', 'sha256')})
                        return raw
                    if mode in ('gain', 'proof_shape'):
                        proof = h.decode(self.checked(report['scale_proof']))
                        if mode == 'gain':
                            proof['gain'] = [5, 4]
                        else:
                            proof['shapes']['train_rates_heldin'][0] = 1721
                        report['scale_proof'] = replace(report['scale_proof'], proof)
                        barrier = h.decode(self.checked(report['barrier']))
                        barrier['scale_proof'] = report['scale_proof']
                        report['barrier'] = replace(report['barrier'], barrier)
                    elif mode == 'score_source':
                        row = report['arms']['reference']['score_report']
                        score = h.decode(self.checked(row)); score['scorer_sha256'] = 'f' * 64
                        report['arms']['reference']['score_report'] = replace(row, score)
                    elif mode == 'vector':
                        report['arms']['reference']['metrics'].pop('fp-bps')
                    else:
                        report['signed_candidate_minus_reference']['co-bps'] += 1
                    validator = _clone(h, {'read': self.read, 'checked': checked})
                    testcase.assertIs(validator.validate_report.__code__, h.validate_report.__code__)
                    with testcase.assertRaisesRegex(ValueError, reason):
                        validator.validate_report(report, self.validated_child, self.validated_request_sha)
                    refusals.append(mode)
            return refusals

        def cleanup(self, owner, profile, actor, built, cid, intended, deadline):
            self.trace.append(('external_cleanup', intended))
            testcase.assertTrue(intended)
            testcase.assertLessEqual(deadline, 100.0 + h.WORK_SECONDS + h.CLEANUP_SECONDS)
            return {'container_absent': self.mode != 'uncertain_container_closure', 'generated_OS_boundary': True}

        def make_api(self):
            signal_double = SimpleNamespace(ITIMER_REAL=0, SIGALRM=14,
                getitimer=lambda _: (0.0, 0.0), getsignal=lambda _: 'original_handler',
                signal=lambda *args: self.trace.append(('signal_double', args)),
                setitimer=lambda kind, value: self.alarms.append(value))
            self.api = _clone(h, {'source_selection': lambda: self.runtime_source,
                'read': self.read, 'checked': self.checked, 'write': self.write,
                'ordinary': self.ordinary, 'selected_sources': self.selected_sources,
                'load_source': self.load_source,
                'validate_provenance': lambda docs: self.provenance if docs == self.provenance_documents
                                       else (_ for _ in ()).throw(AssertionError('Exact external provenance')),
                'label_policy': lambda: SimpleNamespace(validate_label_maps=self.labels),
                'OwnedProcesses': self.owner, 'time': SimpleNamespace(monotonic=lambda: 100.0),
                'signal': signal_double,
                'check_daemon': lambda *args: self.trace.append(('external_daemon', None)),
                'inspect_image': lambda *args: self.trace.append(('external_image', None)),
                'verify_container': self.verify, 'cleanup_actor': self.cleanup,
                'validate_report': self.numerical_report})
            for name in ('run_grade', 'inspect_request', 'admit_inputs', 'prepare_child',
                         'validate_child_request', 'actor_for', 'build_create', 'completion'):
                testcase.assertIs(getattr(self.api, name).__code__, getattr(h, name).__code__)
            return self.api

    for mode in ('good', 'caller_custody', 'wrong_selected_row', 'wrong_inputs',
                 'creation_failure', 'uncertain_process_closure', 'uncertain_container_closure'):
        with testcase.subTest(host_case=mode):
            fixture = Fixture(mode)
            api = fixture.make_api()
            if mode in ('caller_custody', 'wrong_selected_row', 'wrong_inputs'):
                reason = {'caller_custody': 'caller-provided custody',
                          'wrong_selected_row': 'genuine selected VALID row',
                          'wrong_inputs': 'template inputs equal'}[mode]
                with testcase.assertRaisesRegex(ValueError, reason):
                    api.run_grade(fixture.request_descriptor['path'], fixture.request_descriptor['sha256'])
                testcase.assertFalse(fixture.output.exists())
                testcase.assertEqual(fixture.owner_instances, 0)
                testcase.assertEqual(fixture.created, 0)
                testcase.assertEqual(fixture.alarms, [])
                if mode == 'caller_custody':
                    testcase.assertFalse(any(x[0] == 'external_completed_selection' for x in fixture.trace))
                cases.append({'case': mode, 'refused_before_output_and_create': True})
                continue
            result = api.run_grade(fixture.request_descriptor['path'], fixture.request_descriptor['sha256'])
            testcase.assertEqual(fixture.owner_instances, 1)
            testcase.assertEqual(fixture.created, 1)
            testcase.assertEqual(fixture.alarms, [780.0, 0])
            testcase.assertEqual(result['bounds'], {'memory_bytes': 2147483648, 'cpu_soft_seconds': 600,
                'cpu_hard_seconds': 605, 'work_seconds': 720, 'cleanup_seconds': 60, 'threads': 1})
            testcase.assertTrue(result['test_reference_and_candidate_share_one_child_and_budget'])
            positions = {}
            for key, predicate in (
                    ('admit', lambda row: row[0] == 'external_completed_selection'),
                    ('custody', lambda row: row == ('write', 'HOST_VALID_CUSTODY.json')),
                    ('child_request', lambda row: row == ('write', 'CHILD_REQUEST.json')),
                    ('owner', lambda row: row[0] == 'owner'),
                    ('create', lambda row: row == ('cli', 'create_test_gain_grade'))):
                positions[key] = next(i for i, row in enumerate(fixture.trace) if predicate(row))
            testcase.assertLess(positions['admit'], positions['custody'])
            testcase.assertLess(positions['custody'], positions['child_request'])
            testcase.assertLess(positions['child_request'], positions['owner'])
            testcase.assertLess(positions['owner'], positions['create'])
            testcase.assertEqual(sum(row[0] == 'external_completed_selection' for row in fixture.trace), 1)
            child = h.decode(fixture.checked(result['child_request']))
            custody = h.decode(fixture.checked(result['host_custody']))
            testcase.assertEqual(custody['host_source'], fixture.runtime_source)
            testcase.assertEqual(custody['host_request'], fixture.request_descriptor)
            testcase.assertEqual(custody['core_source'], fixture.core_source)
            testcase.assertEqual(custody['grader_source'], fixture.adapter_source)
            testcase.assertEqual(custody['child_template']['descriptor'], fixture.template_descriptor)
            testcase.assertEqual(custody['child_template']['raw_json'], encoded(fixture.template).decode())
            testcase.assertEqual(custody['test_method']['descriptor'], fixture.method_descriptor)
            testcase.assertEqual(custody['test_method']['raw_json'], encoded(fixture.method).decode())
            testcase.assertEqual(custody['valid_selection']['descriptor'], fixture.selection_descriptor)
            testcase.assertEqual(custody['valid_selection']['raw_json'], encoded(fixture.selection).decode())
            testcase.assertEqual(custody['selected_row'], fixture.selection['ordered_scores'][1])
            testcase.assertEqual(custody['lineage'], fixture.lineage)
            testcase.assertEqual(custody['inputs'], fixture.original)
            testcase.assertEqual(child, {**fixture.template, 'host_custody': result['host_custody']})
            testcase.assertEqual(result['child_request']['path'], str(fixture.output / 'CHILD_REQUEST.json'))
            testcase.assertEqual(result['host_custody']['path'], str(fixture.output / 'HOST_VALID_CUSTODY.json'))
            if mode == 'good':
                testcase.assertTrue(result['success'])
                testcase.assertEqual(result['status'], 'graded')
                testcase.assertEqual((fixture.started, fixture.waited, fixture.report_calls), (1, 1, 1))
                admitted = {'record': fixture.method, 'selection_descriptor': fixture.selection_descriptor,
                            'selection_raw': encoded(fixture.selection).decode(),
                            'lineage': fixture.lineage, 'inputs': fixture.original}
                before = dict(result['host_custody'])
                with testcase.assertRaises(FileExistsError):
                    api.prepare_child(fixture.request, fixture.template, admitted, fixture.request_descriptor)
                testcase.assertEqual(h.reference(before['path']), before)
                charge_read(before['bytes'])
                report_refusals = fixture.report_refusals()
                positive = (fixture, child)
            else:
                testcase.assertFalse(result['success'])
                testcase.assertIsNone(result['report'])
                testcase.assertEqual(result['status'], 'failed' if mode == 'creation_failure' else 'closure_unknown')
            cases.append({'case': mode, 'create_calls': fixture.created, 'status': result['status'],
                          'success': result['success'], 'ordering': positions})

    # Actual child main executes once with fake limits/site/adapter boundaries.
    # The exact source roster and request hash checks remain active.
    fixture, paired_child = positive
    child_trace = []
    virtual = {}
    def child_row(path, raw):
        raw = raw if type(raw) is bytes else encoded(raw)
        charge_write(len(raw))
        virtual[str(path)] = raw
        return {'path': str(path), **pin(raw)}
    here = c.HERE
    adapter_raw = b'# explicitly injected numerical adapter boundary\n'
    child_source_raw = b'generated child authority body; actual main code remains unchanged\n'
    manifest = {'schema': 'smc_test_gain_grade_source_v1', 'test_kernel': h.CORE_PIN,
        'files': {name: pin((child_source_raw if name == 'test_pair_child.py' else
                            adapter_raw if name == 'test_pair_grade.py' else b'generated source'))
                  for name in h.ADAPTER_NAMES}}
    source = child_row(here / 'SOURCE.json', manifest)
    child_row(here / 'test_pair_child.py', child_source_raw)
    child_row(here / 'test_pair_grade.py', adapter_raw)
    child_request = {**paired_child, 'source': source}
    request = child_row(root / 'bounded-child-request.json', child_request)
    limits = {}
    def set_limit(kind, values):
        child_trace.append(('set_limit', kind, values)); limits[kind] = values
    resource_double = SimpleNamespace(RLIMIT_CPU='CPU', RLIMIT_CORE='CORE',
        setrlimit=set_limit, getrlimit=lambda kind: limits[kind])
    environment = {}
    def child_read(path, expected=None):
        key = str(path)
        testcase.assertIn(key, virtual)
        raw = virtual[key]; charge_read(len(raw)); child_trace.append(('read', Path(key).name))
        if expected is not None:
            testcase.assertEqual(pin(raw), {k: expected[k] for k in ('bytes', 'sha256')})
        return raw
    calls = []
    adapter = ModuleType('generated_numeric_adapter')
    def paired_run(path, sha):
        calls.append((path, sha)); child_trace.append(('paired_run', None))
        testcase.assertEqual((path, sha), (request['path'], request['sha256']))
        testcase.assertEqual(set(child_request['predictions']), {'reference', 'candidate'})
        testcase.assertEqual(set(child_request['freezes']), {'reference', 'candidate'})
        testcase.assertEqual(limits, {'CPU': (600, 605), 'CORE': (0, 0)})
        testcase.assertEqual(environment, {key: '1' for key in c.THREAD_KEYS})
    adapter.run = paired_run
    builtins_copy = dict(vars(builtins))
    real_import = builtins_copy['__import__']
    def safe_import(name, *args, **kwargs):
        if name == 'site':
            return SimpleNamespace(main=lambda: child_trace.append(('site_double', None)))
        return real_import(name, *args, **kwargs)
    builtins_copy['__import__'] = safe_import
    imported = SimpleNamespace(util=SimpleNamespace(
        spec_from_file_location=lambda name, path: SimpleNamespace(name=name, path=path),
        module_from_spec=lambda _: adapter))
    child_api = _clone(c, {'read': child_read, 'resource': resource_double,
        'os': SimpleNamespace(environ=environment, umask=lambda value: child_trace.append(('umask_double', value))),
        'sys': SimpleNamespace(dont_write_bytecode=False), 'importlib': imported,
        '__builtins__': builtins_copy, 'print': lambda value: child_trace.append(('completion', json.loads(value)))})
    testcase.assertIs(child_api.main.__code__, c.main.__code__)
    child_api.main(['--request', request['path'], '--sha256', request['sha256']])
    testcase.assertEqual(len(calls), 1)
    testcase.assertEqual([row for row in child_trace if row[0] == 'set_limit'],
                         [('set_limit', 'CPU', (600, 605)), ('set_limit', 'CORE', (0, 0))])
    first_read = next(i for i, row in enumerate(child_trace) if row[0] == 'read')
    site_at = next(i for i, row in enumerate(child_trace) if row[0] == 'site_double')
    run_at = next(i for i, row in enumerate(child_trace) if row[0] == 'paired_run')
    testcase.assertLess(1, first_read)
    testcase.assertLess(first_read, site_at)
    testcase.assertLess(site_at, run_at)
    completion = child_trace[-1][1]
    testcase.assertEqual(completion['schema'], 'smc_test_gain_grade_child_completion_v1')
    testcase.assertFalse(completion['inference_executed'])
    testcase.assertEqual(completion['role'], 'test_reference_candidate_gain_comparison')
    return {'schema': 'smc_test_gain_host_generated_controls_v1', 'cases': cases,
        'child_paired_delegate_calls': len(calls), 'child_resource_limit_sets': 2,
        'real_report_positive_calls': 2, 'real_report_refusals': report_refusals,
        'report_fixture_authority': 'Generated score/snapshot/scale metadata only; no actual array or evaluator qualification',
        'bounds': {'memory_bytes': 2147483648, 'cpu_soft_seconds': 600, 'cpu_hard_seconds': 605,
                   'work_seconds': 720, 'cleanup_seconds': 60, 'threads': 1},
        'accounting': counters, 'write_limit_bytes': limit_write, 'read_work_limit_bytes': limit_read,
        'actual_host_functions': ['inspect_request', 'admit_inputs', 'validate_child_request', 'prepare_child',
                                 'actor_for', 'build_create', 'run_grade', 'completion', 'validate_report'],
        'original_completed_VALID_authority': 'Explicit generated core double; actual core-to-selector call is tested separately by main suite',
        'external_doubles': ['original source/image/provenance/core authority', 'socket stat', 'signals and clock',
                             'process owner and Docker', 'container inspection/cleanup', 'generated numerical score and snapshot/scale proof inputs',
                             'child resource/site/numerical adapter'],
        'source_function_code_preserved': True, 'production_globals_mutated': False,
        'original_array_or_model_or_numerical_execution': False, 'native_qualification': False,
        'genuine_original_VALID_completion_established_by_this_helper': False}

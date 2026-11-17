"""Full original shape support, generated only; no native/provider/model execution."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run
import numpy as np

WRITTEN = 0


def written(filename, raw):
    global WRITTEN
    if WRITTEN + len(raw) > 128 * 1024**2:
        raise AssertionError('Prospective cumulative generated fixture limit')
    WRITTEN += len(raw)
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_bytes(raw)


def natural():
    return {'natural_exit': True, 'process_reaped': True, 'streams_closed': True, 'timed_out': False,
            'exit_code': 0, 'kill_sent': False, 'error_type': None}


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (HERE / 'SOURCE.json').read_bytes()
        import hashlib
        cls.source = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        cls.b = run.load_bridge(cls.source)
        cls.manifest, cls.captured = cls.b.source(cls.source)
        cls.original = cls.b.original(cls.captured)
        cls.scorer = HERE.parent / 'response-scorer-v1'
        cls.identities = {n: cls.b.pin(cls.captured[str(cls.scorer / (n + '.py'))]) for n in cls.b.NUMERICAL}
        cls.temp = tempfile.TemporaryDirectory(prefix='neural069-generated-')
        cls.root = Path(cls.temp.name).resolve()
        cls.packet = cls.root / 'packet'; cls.submission = cls.root / 'candidate/submission.json'
        cls.outputs, cls.original_bodies, cls.records, cls.truth = {}, {}, [], {}
        public_cases, private_cases = [], []
        rois = ('lV1v', 'rV1v', 'lV1d', 'rV1d', 'lMT', 'rMT', 'lSTS', 'rSTS')
        for index, row in enumerate(cls.original[3]['cases']):
            identifier, shape = row['id'], row['shape']
            subject, roi = identifier.split('/')
            truth = np.arange(102, dtype=np.float32)[:, None] + np.arange(shape[1], dtype=np.float32)[None, :] + index
            prediction = truth + 7 if roi in rois[:4] else np.ones(shape, dtype=np.float32) if roi in rois[4:6] else -truth
            stream = io.BytesIO(); np.save(stream, prediction, allow_pickle=False); body = stream.getvalue()
            name = 'prediction-%02d.npy' % index
            written(cls.submission.parent / name, body)
            cls.original_bodies[name] = body; cls.outputs[name] = cls.b.pin(body)
            cls.records.append({'id': identifier, 'path': name, **cls.b.pin(body)})
            stream = io.BytesIO(); np.save(stream, truth, allow_pickle=False); raw = stream.getvalue()
            target = 'private/targets/generated-%02d.npy' % index
            written(cls.packet / target, raw)
            private_cases.append({'id': identifier, 'target': {'path': target, **cls.b.pin(raw)}})
            public_cases.append({'id': identifier, 'subject': subject, 'roi': roi, 'voxels': shape[1],
                                 'coordinates': [[i, 0, 0] for i in range(shape[1])]})
            cls.truth.setdefault(subject, {})[roi] = truth
        roster = {'schema': 'boldmoments-public-roster-v1', 'subjects': ['sub-%02d' % i for i in range(1, 11)],
                  'families': {'V1': list(rois[:4]), 'MT': list(rois[4:6]), 'STS': list(rois[6:])},
                  'train_video_ids': ['vid%04d' % i for i in range(1, 1001)],
                  'query_video_ids': ['vid%04d' % i for i in range(1001, 1103)],
                  'training_repeats': 3, 'query_repeats': 10, 'cases': public_cases}
        raw = cls.b.encode(roster); written(cls.packet / 'public/input/ROSTER.json', raw); cls.roster_pin = cls.b.pin(raw)
        binding = {'schema': 'boldmoments-private-binding-v1', 'roster': {'path': 'public/input/ROSTER.json', **cls.roster_pin},
                   'cases': private_cases}
        raw = cls.b.encode(binding); written(cls.packet / 'private/DATA_BINDING.json', raw); cls.binding_pin = cls.b.pin(raw)
        cls.manifest_value = {'task_id': 'NEURAL-069', 'roster_sha256': cls.roster_pin['sha256'], 'predictions': cls.records}
        raw = cls.b.encode(cls.manifest_value); written(cls.submission, raw)
        cls.original_bodies['submission.json'] = raw; cls.outputs['submission.json'] = cls.b.pin(raw)
        print(json.dumps({'python': sys.version, 'numpy': np.__version__, 'scope': 'generated full original shapes',
                          'cases': 80, 'participants': 10, 'train_videos': 1000, 'query_videos': 102,
                          'prediction_bytes': sum(p['bytes'] for p in cls.outputs.values())}))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        print(json.dumps({'generated_fixture_write_bytes': WRITTEN, 'generated_fixture_retained_bytes': 0,
                          'authentic_payload_reads': 0, 'native_or_model_calls': 0}))

    def modules(self):
        return self.b.numerical_modules(self.scorer, self.identities)

    def case(self, name):
        path = self.root / name; path.mkdir(); return path

    def publish(self, filename, value):
        raw = value if type(value) is bytes else self.b.encode(value)
        written(filename, raw)
        return self.b.pin(raw)

    def test_source_recovery_and_original_full_panel(self):
        a, child, supervisor, lock = self.original
        self.assertEqual(a.REPO, HERE / 'recovered')
        self.assertEqual(a.DONOR_PIN, self.b.pin(self.captured[str(a.REPO / a.DONOR_REL / 'SOURCE_MANIFEST.json')]))
        self.assertEqual(a.bridge_bytes(self.captured[str(a.REPO / a.DONOR_REL / 'supervise.py')]),
                         self.captured[str(a.HERE / 'supervise_origin.py')])
        self.assertEqual((len(lock['cases']), len(lock['public_files']), lock['public_bytes'], lock['output_count']),
                         (80, 101, 219855316, 81))
        self.assertEqual([row['shape'] for row in lock['cases']], [list(self.truth[r['id'].split('/')[0]][r['id'].split('/')[1]].shape) for r in lock['cases']])

    def test_complete_public_validation_never_opens_target_and_preserves_captured_bytes(self):
        with self.modules() as modules:
            capture = modules['io_contract']._capture
            def only_public(value, *args, **kwargs):
                self.assertNotIn('/targets/', str(value))
                return capture(value, *args, **kwargs)
            with patch.object(modules['io_contract'], '_capture', side_effect=only_public):
                contract, bodies = self.b.validate_public(modules, self.packet, self.binding_pin['sha256'], self.submission, self.outputs)
        self.assertEqual(bodies, self.original_bodies)
        directory = self.root / 'validated'
        original = self.b.save
        def counted(filename, raw, mode=0o400):
            global WRITTEN
            WRITTEN += len(raw)
            return original(filename, raw, mode)
        # Candidate paths can change after capture: the published files are captured bytes, never rereads.
        saved = self.submission.read_bytes()
        written(self.submission, b'changed later')
        try:
            with patch.object(self.b, 'save', side_effect=counted):
                result = self.b.publish_public(directory, contract, bodies, self.outputs)
        finally:
            written(self.submission, saved)
        self.assertEqual(result['complete_cases'], 80)
        self.assertFalse(result['private_target_files_accessed'])
        self.assertEqual({n: (directory / n).read_bytes() for n in self.outputs}, self.original_bodies)

    def test_actual_current_score_full_shapes_and_historical_companion(self):
        with self.modules() as modules:
            calls = []
            def load(contract):
                calls.append('targets')
                return modules['score'].load_targets(contract)
            result = self.b.bound_score(modules, self.packet, self.binding_pin['sha256'], self.submission, self.outputs, loader=load)
        self.assertEqual(calls, ['targets'])
        self.assertEqual(result['status'], 'scored')
        self.assertAlmostEqual(result['score'], .25, places=12)
        self.assertAlmostEqual(result['analysis']['legacy_companion']['value'], 0., places=12)
        self.assertEqual(result['analysis']['panel'], {'participants': 10, 'rois_per_participant': 8, 'videos': 102})
        self.assertTrue(result['producer_custody']['complete_capture'])
        self.assertEqual(result['producer_custody']['captured_count'], 81)

    def test_both_actual_capture_sites_reject_changes_before_target_loader(self):
        for which in ('submission', 'last_array'):
            with self.subTest(which=which), self.modules() as modules:
                capture = modules['io_contract']._capture
                last = self.records[-1]['path']
                def changed(value, *args, **kwargs):
                    raw, digest = capture(value, *args, **kwargs)
                    if (which == 'submission' and Path(value) == self.submission) or (which == 'last_array' and str(value) == last):
                        raw = raw[:-1] + bytes([raw[-1] ^ 1])
                        digest = self.b.pin(raw)['sha256']
                    return raw, digest
                with patch.object(modules['io_contract'], '_capture', side_effect=changed):
                    result = self.b.bound_score(modules, self.packet, self.binding_pin['sha256'], self.submission,
                                               self.outputs, loader=lambda _: self.fail('Private targets reached'))
                self.assertEqual((result['status'], result['score']), ('invalid_submission', None))

    def test_malformed_last_array_is_candidate_refusal_without_target_access(self):
        last = self.records[-1]['path']
        with self.modules() as modules:
            capture = modules['io_contract']._capture
            # Use a shape-valid all-finite-prefix array with one nonfinite final element and authentic generated pins.
            data = np.load(io.BytesIO(self.original_bodies[last]), allow_pickle=False).copy(); data[-1, -1] = np.nan
            stream = io.BytesIO(); np.save(stream, data, allow_pickle=False); malformed = stream.getvalue()
            value = copy.deepcopy(self.manifest_value); value['predictions'][-1].update(self.b.pin(malformed))
            submission_raw = self.b.encode(value)
            outputs = copy.deepcopy(self.outputs); outputs[last] = self.b.pin(malformed); outputs['submission.json'] = self.b.pin(submission_raw)
            def fake_bytes(filename, *args, **kwargs):
                self.assertNotIn('/targets/', str(filename))
                if str(filename) == last: return malformed, self.b.pin(malformed)['sha256']
                if Path(filename) == self.submission: return submission_raw, self.b.pin(submission_raw)['sha256']
                return capture(filename, *args, **kwargs)
            with patch.object(modules['io_contract'], '_capture', side_effect=fake_bytes):
                with self.assertRaises(self.b.CandidateInvalid) as caught:
                    self.b.validate_public(modules, self.packet, self.binding_pin['sha256'], self.submission, outputs)
            self.assertEqual(caught.exception.result['status'], 'invalid_submission')
            self.assertIsNone(caught.exception.result['score'])

    def test_operator_metadata_error_is_not_candidate_refusal(self):
        with self.modules() as modules:
            with self.assertRaises(modules['score'].PacketError):
                self.b.validate_public(modules, self.packet, '0' * 64, self.submission, self.outputs)

    def test_missing_reordered_and_duplicate_full_panel_refused(self):
        with self.modules() as modules:
            capture = modules['io_contract']._capture
            variants = [self.records[:-1], list(reversed(self.records)), [self.records[0]] + self.records[:-1]]
            for rows in variants:
                value = {**self.manifest_value, 'predictions': rows}; raw = self.b.encode(value)
                outputs = {**self.outputs, 'submission.json': self.b.pin(raw)}
                def swapped(filename, *args, **kwargs):
                    self.assertNotIn('/targets/', str(filename))
                    return (raw, self.b.pin(raw)['sha256']) if Path(filename) == self.submission else capture(filename, *args, **kwargs)
                with patch.object(modules['io_contract'], '_capture', side_effect=swapped):
                    with self.assertRaises(self.b.CandidateInvalid):
                        self.b.validate_public(modules, self.packet, self.binding_pin['sha256'], self.submission, outputs)

    def test_nonzero_or_unclosed_outer_observer_cannot_admit(self):
        for key, value in [('exit_code', 1), ('exit_code', True), ('natural_exit', False), ('kill_sent', True),
                           ('streams_closed', False), ('process_reaped', False), ('timed_out', True)]:
            record = natural(); record[key] = value
            with self.assertRaises(ValueError):
                self.b.admit_producer(self.original, {}, b'{}', record)

    def test_no_numeric_provider_without_cli_or_complete_public_custody(self):
        with patch.object(self.b, 'transport', side_effect=AssertionError('Provider constructed too early')):
            with self.assertRaises(ValueError):
                run.score_native(self.b, {}, {}, {}, self.original, self.captured, {}, {}, self.root, 0, 1, self.source)
            with patch.object(run, 'CLI_ACTIVE', True), self.assertRaises(ValueError):
                run.score_native(self.b, {}, {}, {}, self.original, self.captured, {'outputs': self.outputs},
                                 {'receipt': {'outputs': self.outputs, 'private_target_files_accessed': False,
                                              'complete_cases': 79}}, self.root, 0, 1, self.source)

    def test_attempted_outer_writes_are_charged_even_on_failure(self):
        old_limit, old_written = self.b.WRITE_LIMIT, self.b.WRITTEN
        try:
            self.b.WRITE_LIMIT, self.b.WRITTEN = 5, 0
            with self.assertRaises(FileExistsError):
                self.b.save(self.submission, b'abc')
            self.assertEqual(self.b.WRITTEN, 3)
            with self.assertRaises(ValueError):
                self.b.save(self.root / 'never-created', b'abc')
            self.assertFalse((self.root / 'never-created').exists())
        finally:
            self.b.WRITE_LIMIT, self.b.WRITTEN = old_limit, old_written

    def closed_fixture(self, base):
        b = self.b
        a, child, supervisor, lock = self.original
        root = base / 'producer'; attempt = root / 'attempt'; donor = a.REPO / a.DONOR_REL
        source = {name: raw for filename, raw in self.captured.items()
                  if Path(filename).parent == donor and (name := Path(filename).name) != 'SOURCE_MANIFEST.json'}
        program = b'# Generated inert candidate; never executed.\n'
        commitment = {'schema': 'neural069_program_commit_v1', 'task_id': 'NEURAL-069', 'program': b.pin(program),
            'source_manifest': a.DONOR_PIN, 'lock': a.LOCK_PIN, 'image': a.IMAGE, 'candidate_seconds': 2,
            'memory_bytes': 536870912, 'cpu': 1, 'full_cases': [row['id'] for row in lock['cases']]}
        cp = self.publish(base / 'commit/COMMIT.json', commitment)
        self.publish(base / 'commit/program.py', program); self.publish(base / 'program.py', program)
        for name, raw in source.items(): self.publish(root / 'source' / name, raw)
        self.publish(root / 'source/SOURCE_MANIFEST.json', self.captured[str(donor / 'SOURCE_MANIFEST.json')])
        snapshots = {'program.py': program, **{n: source[n] for n in ('holder.py', 'entry.py', 'LOCK.json')}}
        for name, raw in snapshots.items(): self.publish(attempt / 'snapshot' / name, raw)
        outputs = []
        value = {**self.manifest_value, 'roster_sha256': lock['roster']['sha256']}
        raw = b.encode(value)
        outputs.append({'path': 'submission.json', **self.publish(attempt / 'captured/submission.json', raw)})
        for row in self.records:
            outputs.append({'path': row['path'], **self.publish(attempt / 'captured' / row['path'], self.original_bodies[row['path']])})
        public = {'files': 101, 'bytes': lock['public_bytes'], 'lock': a.LOCK_PIN}
        inp = {'commit': cp, 'source_manifest': a.DONOR_PIN, 'public_pre_pin': public,
               'snapshot': {n: b.pin(raw) for n, raw in snapshots.items()}, 'package': str(self.packet)}
        ip = self.publish(attempt / 'INPUT.json', inp)
        closures = []
        for role, kind in (('volume', 'volume'), ('holder', 'container'), ('candidate', 'container')):
            prefix = 'neural069-' + 'a' * 24; name = prefix + '-' + role
            self.publish(attempt / ('INTENT-' + role + '.json'), {'name': name, 'owner': prefix + '/' + role,
                         'kind': kind, 'attempted': False, 'acknowledged': False})
            closures.append({'name': name, 'kind': kind, 'removed': True, 'absence_observed': True,
                             'creation_outcome_unknown': False, 'closed': True})
        execution = {'schema': 'neural069_program_execution_v1', 'status': 'captured', 'program': b.pin(program),
            'commit': cp, 'source_manifest': a.DONOR_PIN, 'lock': a.LOCK_PIN, 'image': a.IMAGE,
            'full_cases': commitment['full_cases'], 'candidate_seconds': 2, 'memory_bytes': 536870912,
            'observed_candidate_seconds': .1, 'candidate_started': True, 'candidate_closed_before_capture': True,
            'all_resources_closed': True, 'cli_reaped': True, 'private_scoring_called': False, 'error_type': None,
            'natural_exit': {'Status': 'exited', 'Running': False, 'Dead': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False},
            'input_binding': ip, 'public_post_pin': public, 'closures': closures, 'outputs': outputs}
        ep = self.publish(attempt / 'EXECUTION.json', execution)
        self.publish(attempt / 'COMPLETE.json', {'schema': 'neural069_executor_complete_v1', 'outputs': 81,
            'private_scoring_called': False, 'limit_seconds': 422, 'worker_seconds': .2, 'execution': ep, 'input': ip})
        self.publish(root / 'INTENT.json', {'schema': 'neural069_supervisor_intent_v1', 'source_manifest': a.DONOR_PIN,
            'commit': cp, 'attempt': str(attempt), 'image': a.IMAGE, 'whole_seconds': 482,
            'private_scoring_called': False, 'package': str(self.packet)})
        joined = supervisor.closed_files(root, commitment, cp, a.DONOR_PIN, source)
        receipt = {'schema': 'neural069_host_exit_v1', 'status': 'closed', 'source_manifest': a.DONOR_PIN,
            'commit': cp, 'program': b.pin(program), 'image': a.IMAGE, 'attempt': str(attempt),
            'child': natural(), 'host_seconds_before_receipt': .4, 'whole_seconds': 482,
            'private_scoring_called': False, **joined}
        hp = self.publish(root / 'HOST_EXIT.json', receipt)
        review = {'schema': 'neural069_registration_review_v1', 'approved': True, 'task_id': 'NEURAL-069',
            'source': {'adapter_manifest': b.pin(self.captured[str(a.HERE / 'SOURCE_MANIFEST.json')]), 'original_manifest': a.DONOR_PIN},
            'program': {'path': str(base / 'program.py'), **b.pin(program)}, 'commit': {'path': str(base / 'commit'), 'metadata': cp},
            'package': str(self.packet), 'output': str(root), 'docker_socket': str(base / 'unused-socket'),
            'environment': {k: os.environ.get(k) for k in ('PATH', 'DOCKER_CONFIG', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')},
            'resources': {'candidate_seconds': 2, 'memory_bytes': 536870912, 'cpu': 1,
                'attempt_retained_and_write_bytes': 20000000, 'existing_commit_cap_bytes': 300000,
                'adapter_read_cap_bytes': 1048576, 'free_floor_bytes': 21474836480,
                'other_bytes': run.DISK_FLOOR - 21474836480 + run.EXTRA_BYTES}}
        rp = self.publish(base / 'review.json', review)
        args = types.SimpleNamespace(program=base / 'program.py', output=root, review=base / 'review.json',
                                     other_reserve_bytes=review['resources']['other_bytes'])
        prepared = a.prepare(args, time.monotonic())
        terminal = b.encode({'schema': 'neural069_review_bound_terminal_v1', 'status': 'closed',
            'original_host_exit': hp, 'review': rp, 'outputs': 81,
            'external_natural_zero_required': True, 'scientific_qualification': False})
        return prepared, terminal

    def test_actual_original_admission_complete_chain_and_corrupt_output_refusal(self):
        base = self.case('original-chain')
        prepared, terminal = self.closed_fixture(base)
        admitted = self.b.admit_producer(self.original, prepared, terminal, natural())
        self.assertEqual(len(admitted['outputs']), 81)
        self.assertTrue(admitted['descendant_absence_not_certified'])
        last = Path(admitted['submission']).parent / self.records[-1]['path']
        last.unlink()
        with self.assertRaises((ValueError, OSError)):
            self.b.admit_producer(self.original, prepared, terminal, natural())

    def numeric_case(self, name, closed=True):
        b = self.b; base = self.case(name); output = base / 'operator'; output.mkdir()
        control = base / 'control'; control.mkdir(mode=0o700)
        quarantine = base / 'quarantine'; quarantine.mkdir(mode=0o700)
        with self.modules() as modules:
            contract, bodies = b.validate_public(modules, self.packet, self.binding_pin['sha256'], self.submission, self.outputs)
        # This control exercises mounting and provider joins using already validated generated files.
        custody = {'receipt': {'outputs': self.outputs, 'private_target_files_accessed': False, 'complete_cases': 80},
                   'contract': contract, 'directory': self.submission.parent, 'numerical_sources': self.identities}
        admitted = {'outputs': self.outputs, 'packet': str(self.packet), 'docker_socket': str(base / 'unused-socket')}
        authority = {'image': self.original[0].IMAGE, 'image_inventory_sha256': 'a' * 64,
                     'docker_binary': str(base / 'unused-docker'), 'grade_resources': run.limits(2, 536870912)}
        cfg = {'grade_control_root': str(control), 'grade_quarantine_root': str(quarantine)}
        Provider, mount_identity, directory = b.transport(self.captured)
        transport_contract = sys.modules['neural069_trusted_grade_transport.contract']
        bounds = sys.modules['neural069_trusted_grade_transport.bounds']
        calls = []
        def execute(provider, request, mounts, deadline, journal):
            calls.append(request)
            provider.engine_auth(bounds.Meter(1048576, 1, deadline))
            transport_contract.validate_request(request, mounts, deadline)
            exposure = b.parse(b.read(next(iter(provider.exposures.values())), 2097152))
            transport_contract.validate_exposure(exposure, request, mounts)
            self.assertEqual(len([n for n in mounts if n.startswith('/submission/')]), 81)
            self.assertEqual(len([n for n in mounts if n.startswith('/packet/private/targets/')]), 80)
            self.assertFalse(any(n.endswith('/program.py') for n in mounts))
            invocation = b.parse(b.read(mounts['/invocation.json']['path'], 65536))
            score = {'status': 'scored', 'score': .25, 'binding_sha256': self.binding_pin['sha256'],
                'roster_sha256': self.roster_pin['sha256'], 'analysis': {'metric': 'participant_macro_roi_macro_voxel_pearson',
                    'legacy_companion': {'metric': 'participant_macro_family_macro_voxel_pearson'}},
                'producer_custody': {'outputs': invocation['outputs'], 'complete_capture': True, 'captured_count': 81}}
            phase = request['phase_id']; dest = quarantine / phase
            files = {'score.json': self.publish(dest / 'score.json', score),
                     'RESULT.json': self.publish(dest / 'RESULT.json', {'schema': 'neural069_response_grade_result_v1',
                         'status': 'scored', 'participant_code_executed': False, 'scientific_qualification': False})}
            request_sha = b.pin(b.encode(request))['sha256']
            header = {'schema': 'osl_transport_output_manifest_v1', 'phase_id': phase, 'request_sha256': request_sha,
                      'files': dict(files)}
            files['OUTPUTS.json'] = self.publish(dest / 'OUTPUTS.json', header)
            transport_contract.output_files(header, request, request_sha,
                {'files': [{'name': n, 'bytes': p['bytes']} for n, p in files.items()]})
            receipt = {'phase_id': phase, 'request_sha256': request_sha, 'timing': {'original_deadline': deadline},
                'status': 'captured', 'producer_closed_before_capture': closed, 'all_native_resources_closed': closed,
                'cli_reaped': True, 'error': None, 'natural_exit': {'ExitCode': 0, 'OOMKilled': False},
                'source': request['source'], 'image': request['image'], 'role': 'reference', 'exposure': request['exposure'],
                'input_before': mount_identity(mounts), 'input_after': mount_identity(mounts), 'quarantine_root': str(dest),
                'output_inventory': {'complete': True, 'files': files}}
            filename = control / phase / 'RECEIPT.json'
            return {'receipt_path': str(filename), 'receipt_pin': self.publish(filename, receipt)}
        saved = b.save
        def counted(filename, raw, mode=0o400):
            global WRITTEN
            WRITTEN += len(raw)
            return saved(filename, raw, mode)
        with patch.object(b, 'BINDING', self.binding_pin), patch.object(b, 'ROSTER', self.roster_pin), \
             patch.object(b, 'transport', return_value=(Provider, mount_identity, directory)), \
             patch.object(Provider, 'execute_phase', execute), patch.object(b, 'save', side_effect=counted), \
             patch.object(run, 'CLI_ACTIVE', True):
            if closed:
                result = run.score_native(b, cfg, authority, b.pin(b'generated authority'), self.original, self.captured,
                    admitted, custody, output, time.monotonic(), time.monotonic() + 120, self.source)
                self.assertEqual(result['status'], 'scored')
                self.assertFalse(result['scientific_qualification'])
            else:
                with self.assertRaisesRegex(ValueError, 'observed resource closure'):
                    run.score_native(b, cfg, authority, b.pin(b'generated authority'), self.original, self.captured,
                        admitted, custody, output, time.monotonic(), time.monotonic() + 120, self.source)
        self.assertEqual(len(calls), 1)

    def test_actual_provider_request_exposure_and_independent_receipt_join(self):
        self.numeric_case('numeric-complete')

    def test_unclosed_numeric_provider_cannot_publish_score(self):
        self.numeric_case('numeric-unclosed', closed=False)

    def test_real_main_invalid_final_array_never_dispatches_private_phase(self):
        base = self.case('invalid-main')
        cfg = {'operator_output': str(base / 'operator'), 'grade_control_root': str(base / 'control'),
               'grade_quarantine_root': str(base / 'quarantine')}
        authority = {'whole_seconds': 1000, 'outside_reserved_bytes': 0, 'public_validation_seconds': 30}
        prepared = {'review_pin': self.b.pin(b'generated review'), 'review': {'output': str(base / 'producer')}}
        last = self.records[-1]['path']; old = self.original_bodies[last]
        data = np.load(io.BytesIO(old), allow_pickle=False).copy(); data[-1, -1] = np.nan
        stream = io.BytesIO(); np.save(stream, data, allow_pickle=False); bad = stream.getvalue()
        value = copy.deepcopy(self.manifest_value); value['predictions'][-1].update(self.b.pin(bad))
        manifest_raw = self.b.encode(value)
        outputs = {**self.outputs, last: self.b.pin(bad), 'submission.json': self.b.pin(manifest_raw)}
        admitted = {'packet': str(self.packet), 'submission': str(self.submission), 'outputs': outputs}
        setup = (cfg, authority, self.b.pin(b'generated authority'), self.original, prepared, self.manifest, self.captured)
        saved = self.b.save
        def counted(filename, raw, mode=0o400):
            global WRITTEN
            WRITTEN += len(raw)
            return saved(filename, raw, mode)
        written(self.submission.parent / last, bad); written(self.submission, manifest_raw)
        try:
            with patch.object(run, 'load_bridge', return_value=self.b), patch.object(run, 'setup', return_value=setup), \
                 patch.object(run, 'runtime_check'), \
                 patch.object(run, 'observe_producer', return_value=admitted), patch.object(run, 'score_native') as score, \
                 patch.object(self.b, 'BINDING', self.binding_pin), patch.object(self.b, 'ROSTER', self.roster_pin), \
                 patch.object(self.b, 'save', side_effect=counted), \
                 patch.object(run.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=10**12)):
                result = run.main(['--source-pin', json.dumps(self.source), '--configuration', str(base / 'unused.json')],
                                  origin=time.monotonic())
                self.assertEqual(result, 2); score.assert_not_called()
            result = self.b.parse((base / 'operator/score.json').read_bytes())
            self.assertEqual((result['status'], result['score']), ('invalid_submission', None))
            complete = self.b.parse((base / 'operator/COMPLETE.json').read_bytes())
            self.assertFalse(complete['private_target_files_accessed'])
            self.assertFalse(complete['numeric_phase_dispatched'])
            self.assertFalse((base / 'operator/validated').exists())
        finally:
            written(self.submission.parent / last, old)
            written(self.submission, self.original_bodies['submission.json'])

    def test_original_review_and_separate_authority_and_full_budget_join(self):
        b = self.b; base = self.case('configuration')
        prepared, terminal = self.closed_fixture(base)
        selected = {'path': str(base / 'review.json'), **prepared['review_pin']}
        authority = {'schema': 'neural069_separate_numeric_authority_v1', 'source': self.source,
            'producer_review': prepared['review_pin'], 'approved': True, 'numeric_reference_calls': 1,
            'image': self.original[0].IMAGE, 'image_inventory_sha256': 'a' * 64,
            'docker_binary': str(base / 'unused-docker'), 'grade_resources': run.limits(2, 536870912),
            'holder_memory_bytes': 134217728, 'holder_cpu_nanos': 1000000000, 'outside_reserved_bytes': 0,
            'additional_artifact_bytes': run.EXTRA_BYTES, 'public_validation_seconds': 30,
            'host_memory_bytes': 1073741824, 'host_memory_enforcement': 'cooperative',
            'whole_seconds': 2 + 480 + 180 + 30 + 2 + 60 + 30,
            'runtime_versions': {'python': '3.12.8', 'numpy': '2.2.6'}, 'runtime_qualification_inherited': False}
        ap = self.publish(base / 'authority.json', authority)
        cfg = {'schema': 'neural069_programme_response_configuration_v1', 'source': self.source,
               'producer_review': selected, 'numeric_authority': {'path': str(base / 'authority.json'), **ap},
               'operator_output': str(base / 'operator'), 'grade_control_root': str(base / 'control'),
               'grade_quarantine_root': str(base / 'quarantine')}
        self.publish(base / 'configuration.json', cfg)
        accepted = run.setup(b, base / 'configuration.json', self.source, time.monotonic())
        self.assertEqual(accepted[4]['review']['resources']['other_bytes'], run.EXTRA_BYTES + run.DISK_FLOOR - 21474836480)
        for key, value in [('approved', False), ('additional_artifact_bytes', 1), ('whole_seconds', 1),
                           ('runtime_qualification_inherited', True), ('numeric_reference_calls', 2)]:
            changed = {**authority, key: value}
            ap = self.publish(base / 'authority.json', changed)
            cfg['numeric_authority'] = {'path': str(base / 'authority.json'), **ap}
            self.publish(base / 'configuration.json', cfg)
            with self.assertRaises(ValueError):
                run.setup(b, base / 'configuration.json', self.source, time.monotonic())

    def test_real_main_failed_outer_zero_never_reaches_public_or_private_stage(self):
        base = self.case('failed-observer-main'); b = self.b
        cfg = {'operator_output': str(base / 'operator'), 'grade_control_root': str(base / 'control'),
               'grade_quarantine_root': str(base / 'quarantine'), 'producer_review': {'path': str(base / 'review.json')}}
        authority = {'whole_seconds': 1000, 'outside_reserved_bytes': 0}
        review = {'output': str(base / 'producer'), 'program': {'path': str(base / 'program.py')},
            'resources': {'candidate_seconds': 2, 'other_bytes': run.EXTRA_BYTES + run.DISK_FLOOR - 21474836480},
            'environment': {k: os.environ.get(k) for k in ('PATH', 'DOCKER_CONFIG', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')}}
        prepared = {'review': review, 'review_pin': b.pin(b'generated review')}
        failed = natural(); failed['exit_code'] = 2
        original = list(self.original)
        original[1] = types.SimpleNamespace(child=lambda *args: (b'{}', failed), ChildFailure=RuntimeError)
        setup = (cfg, authority, b.pin(b'generated authority'), original, prepared, self.manifest, self.captured)
        saved = b.save
        def counted(filename, raw, mode=0o400):
            global WRITTEN
            WRITTEN += len(raw)
            return saved(filename, raw, mode)
        with patch.object(run, 'load_bridge', return_value=b), patch.object(run, 'setup', return_value=setup), \
             patch.object(run, 'runtime_check'), \
             patch.object(run, 'public_custody') as public, patch.object(run, 'score_native') as private, \
             patch.object(b, 'save', side_effect=counted), \
             patch.object(run.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=10**12)):
            with self.assertRaisesRegex(ValueError, 'natural zero'):
                run.main(['--source-pin', json.dumps(self.source), '--configuration', str(base / 'unused.json')],
                         origin=time.monotonic())
            public.assert_not_called(); private.assert_not_called()
        self.assertTrue((base / 'operator/FAILURE.json').is_file())
        self.assertFalse((base / 'operator/COMPLETE.json').exists())

    def test_wrong_production_runtime_is_refused(self):
        # Control flow tests stub this one production precondition; they do not qualify the CI runtime.
        with patch.object(run, 'sys', types.SimpleNamespace(version_info=(0, 0, 0))):
            with self.assertRaisesRegex(ValueError, 'selected Python'):
                run.runtime_check(self.b)


if __name__ == '__main__':
    unittest.main()

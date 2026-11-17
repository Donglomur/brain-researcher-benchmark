"""Generated full-scope grading composition, without native/model/data work.

All review records, model bytes, targets and closure records below are invented.
They are engineering inputs, never evidence of authentic authority or execution.
Real source policy, collection admission, protected grader and PER kernels run.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest

HERE = Path(__file__).resolve().parent
DONOR = HERE.parent / 'speech-programme'


def module(path, **bindings):
    raw = path.read_bytes()
    m = types.ModuleType(path.stem)
    m.__dict__.update(bindings)
    m.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), m.__dict__)
    return m, raw


class Memory:
    def __init__(self):
        self.files = {}; self.read_bytes = 0; self.gold_reads = 0

    def put(self, path, body):
        self.files[str(path)] = body
        return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

    def read(self, path, cap, expected=None):
        if str(path) == '/private/GOLD.json': self.gold_reads += 1
        body = self.files[str(path)]
        if not 0 < len(body) <= cap: raise ValueError('generated bounded read')
        pin = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        if expected is not None and pin != expected: raise ValueError('generated exact read pin')
        self.read_bytes += len(body)
        return body


class CompleteGrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        boot, _ = module(DONOR / 'transport/bootstrap.py')
        cls.c, _, cls.bodies, cls.source_read_charge = boot.load(DONOR, {'bytes': 3665, 'sha256': '2b30df42c6a15511f302a0acdc29a49708a8741e6c71edb16ce89e8724cfa8ea'}, time.monotonic() + 30)
        cls.adapter, raw = module(HERE / 'grade_completed.py')
        cls.adapter_pin = cls.c.pin(raw)
        cls.science = cls.c.module(cls.bodies, 'program/science.py', DONOR, c=cls.c)
        cls.packet = cls.c.module(cls.bodies, 'program/packet.py', DONOR, c=cls.c, science=cls.science)
        cls.outputs = cls.c.module(cls.bodies, 'program/outputs.py', DONOR, c=cls.c, packet=cls.packet, science=cls.science, policy=None)
        # Reuse the exact extracted generated complete45/54-row fixture function;
        # no controller tests, authentic arrays or numerical results are imported.
        fixture_module, fixture_raw = module(HERE / 'generated_fixture.py')
        if cls.c.pin(fixture_raw) != {'bytes': 862, 'sha256': '6cc4cd0afcebcb978b82b713ed09227e29b637f67289c29f7cfb4423f86579c0'}:
            raise ValueError('exact original generated fixture source')
        cls.fixture = staticmethod(fixture_module.fixture)
        cls.observed = []
        cls.fixture_read_bytes = 0
        cls.fixture_peak_body_bytes = 0

    def fixture_graph(self, candidate_tokens=None, heterogeneous=False):
        c, p, o = self.c, self.packet, self.outputs
        candidate_tokens = ['AA', '|', 'B'] if candidate_tokens is None else candidate_tokens
        fs = Memory(); public = self.fixture(); plan = p.admit(public)
        scalar = {k: plan[k] for k in p.PLAN_FIELDS}
        source = self.adapter.PRODUCER
        candidate = b'# wholly invented candidate; never executed\n'
        programs = {'candidate': c.pin(candidate), 'independent_reference': c.pin(self.bodies['reference/reference_program.py'])}
        def put(path, value): return fs.put(path, c.encoded(value))
        def descriptor(path, pin): return dict(path=path, **pin)
        public_pin = put('/input/PUBLIC.json', public)
        fs.put('/candidate.py', candidate)
        s = dict(schema='neural014-complete-selection-v1', task_id='NEURAL-014', execution_selected=True,
                 source=source, output='/attempt', public_root='/input',
                 public_manifest=descriptor('/input/PUBLIC.json', public_pin),
                 candidate_program=descriptor('/candidate.py', c.pin(candidate)),
                 image='sha256:' + 'd'*64, docker_binary='/generated/docker', docker_socket='/generated/docker.sock',
                 memory_bytes=1073741824, other_future_bytes=0, plan=scalar,
                 fit_seconds=2, adapt_seconds=2, infer_seconds=2, prior_seconds=2,
                 limits=p.limits(scalar, dict(fit=2, adapt=2, infer=2, prior=2)), private_grading_authorized=False)
        for name in ('input', 'method', 'runtime'):
            r = dict(schema=f'neural014-full45-{name}-review-v1', task_id='NEURAL-014', approved=True, source=source)
            if name == 'input':
                r.update(public_manifest=s['public_manifest'], plan=scalar, pins_alone_establish_source_lineage=False)
                flags = ('all45_sessions_and86_labeled_members', 'exact_archive_and_native_projection', 'global_sentence_priority_and_no_refill', 'all_required_partitions_supported', 'finite_full512_column_features', 'source_preprocessing_lineage', 'sanitized_tree_excludes_query_labels_and_identity_keys', 'all_query_permutations_independently_recomputed_numpy226', 'permutation_case_seed_length_and_raw_feature_identity_joined', 'projection_and_permutation_preparation_costs_retained')
            elif name == 'method':
                r.update(programs=programs, hashes_prove_chronology=False)
                flags = ('train_only_fitting_normalization', 'development_only_selection_no_refit', 'calibration_only_adaptation', 'same_full_adapted_model_for_three_ablations', 'no_query_fitting_or_cross_query_state', 'no_arm_dependent_inference_algorithm', 'no_external_lm_or_all_session_weights', 'source_exposure_history_declared', 'independent_reference_cannot_be_candidate_replaced')
            else:
                r.update(programs=programs, profile={k: s[k] for k in ('image', 'memory_bytes', 'fit_seconds', 'adapt_seconds', 'infer_seconds', 'prior_seconds', 'plan', 'limits')}, scientific_qualified=False, scoring_authorized=False)
                flags = ('cached_image_numpy226_torch260_cpu', 'native_and_cli_owned_resources_close', 'shared_sealed_model_custody', 'all_phases_original_clock_observed', 'full_resource_and_host_capacity_qualified')
            r.update({key: True for key in flags})
            path = '/reviews/' + name + '.json'
            s[name + '_review'] = descriptor(path, put(path, r))
        selection_pin = put('/selection.json', s)
        commitment = dict(schema='neural014-commitment-v1', source=source, programs=programs,
                          public_manifest=s['public_manifest'], image=s['image'], plan=s['plan'], limits=s['limits'], private_grading_authorized=False)
        commitment_pin = put('/attempt/COMMITMENT.json', commitment)
        for name, body in [('candidate', candidate), ('independent_reference', self.bodies['reference/reference_program.py'])]: fs.put('/attempt/programs/' + name + '.py', body)
        models = {}; values = {name: {} for name in p.PANELS}; schedule = p.phases(public, plan)
        for phase in schedule:
            d = '/attempt/phases/' + phase['phase_id']
            model = None if phase['model_key'] is None else models[phase['model_key']]
            req = dict(schema='neural014-phase-request-v1', source=source, phase=phase,
                       program=programs[phase['panel']], image=s['image'], seconds=2, model=model,
                       input=c.pin(c.encoded(p.request(public, phase, plan))), view_members=c.pin(b'invented exact view listing'))
            rp = put(d + '/REQUEST.json', req)
            native = dict(schema='neural014-native-phase-v1', kind=phase['kind'], ordinal=phase['ordinal'], source=source,
                          status='captured', all_native_resources_closed=True, producer_closed_before_capture=True, cli_reaped=True,
                          error_type=None, image=s['image'], memory_bytes=s['memory_bytes'], producer_seconds_limit=2,
                          private_scoring_called=False, producer_wall_seconds=0.1, elapsed_seconds=0.2,
                          natural_exit=dict(Status='exited', Running=False, Dead=False, Pid=0, ExitCode=0, OOMKilled=False),
                          command_metadata=[dict(phase='invented-command', returncode=0, error_type=None, observed_retained_bytes=0,
                                                seconds=0.1, client_reaped=True, cleanup_complete=True, cleanup_before_original_cutoff=True,
                                                owned_group_absence_observed=True, leader_exited_with_group_alive=False, group_probe_or_cleanup_error=None)],
                          closures=[dict(closed=True)]*3)
            if phase['kind'] in ('fit', 'adapt'):
                native['output'] = fs.put('/attempt/models/' + phase['phase_id'] + '.bin', ('invented-model-' + phase['phase_id']).encode())
                models[phase['result_key']] = native['output']
                created = dict(key=phase['result_key'], pin=native['output'])
            else:
                tokens = candidate_tokens if phase['panel'] == 'candidate' else ['AA', '|']
                raw = dict(tokens=tokens) if phase['kind'] == 'prior' else dict(id=phase['case_id'], tokens=tokens)
                native['output'] = put(d + '/prediction.json', raw); created = None
                ids = [r['id'] for r in plan['queries'] if r['session'] == phase['session']] if phase['kind'] == 'prior' else [phase['case_id']]
                for key in ids: values[phase['panel']][(phase['session'], phase['arm'], key)] = tokens
            np = put(d + '/NATIVE.json', native)
            if created:
                put(d + '/MODEL_SEAL.json', dict(schema='neural014-model-seal-v1', source=source, phase=phase,
                                                program=programs[phase['panel']], input_model=model, model=native['output'],
                                                native=np, input=req['input'], view_retired=True))
            put(d + '/CLOSED.json', dict(schema='neural014-phase-closed-v1', phase=phase, request=rp, native=np, model=created, view_retired=True))
        panels = {name: put('/attempt/' + name + '.json', o.assemble(public, value)) for name, value in values.items()}
        complete = dict(schema='neural014-complete-v1', status='complete_unqualified', source=source, commitment=commitment_pin,
                        phase_count=len(schedule), model_count=38, panels=panels, all_views_retired=True,
                        private_targets_opened=False, scoring_performed=False, runtime_qualified=False, scientific_qualified=False)
        cp = put('/attempt/COMPLETE.json', complete)
        result = dict(schema='neural014-worker-result-v1', status='complete_unqualified', source=source, complete=cp, phase_count=len(schedule))
        join = o.admit_collection(s, source, self.bodies, result, Path('/attempt'), fs.read)
        outer = dict(schema='neural014_complete_external_v1', status='complete_unqualified', source=source, selection=selection_pin,
                     attempt='/attempt', executing_outer_source=c.pin(self.bodies['transport/run.py']), executing_worker_source=c.pin(self.bodies['transport/worker.py']),
                     child=dict(natural_exit=True, exit_code=0, process_reaped=True, process_group_absent=True, streams_closed=True),
                     joined_collection=join, grading_performed=False, scientific_qualified=False, runtime_qualified=False,
                     error_type=None, nested_native_recovery_may_be_required=False, automatic_retry=False)
        outer_raw = c.encoded(outer); self.assertLessEqual(len(outer_raw), 8192)
        external_pin = fs.put('/external.json', outer_raw.ljust(8192, b' '))
        targets = [dict(id=r['id'], tokens=['B'] if heterogeneous and r['session'] == 'session-037' else ['AA', '|', 'B']) for r in plan['queries']]
        gold_pin = put('/private/GOLD.json', dict(schema='neural014-gold-v1', generation=public['generation'], targets=targets))
        authority = dict(schema='neural014-protected-grading-authority-v1', task_id='NEURAL-014', source=source,
                         external=external_pin, scientific_grading_authorized=True, private_gold=gold_pin, query_generation=public['generation'])
        auth_pin = put('/authority.json', authority)
        review = dict(schema='neural014-complete-outer-exit-review-v1', task_id='NEURAL-014', approved=True,
                      producer_source=source, selection=selection_pin, external=external_pin, attempt='/attempt',
                      executing_outer_source=c.pin(self.bodies['transport/run.py']), executing_worker_source=c.pin(self.bodies['transport/worker.py']),
                      natural_exit=True, exit_code=0, process_reaped=True, process_group_absent=True, streams_closed=True, forced_termination=False)
        review_pin = put('/outer-review.json', review)
        limit = dict(reads=8*1024*1024, output_bytes=65536, wall_seconds=30, cpu_seconds=10, host_memory_bytes=64*1024*1024)
        runtime = dict(schema='neural014-grade-runtime-review-v1', task_id='NEURAL-014', approved=True,
                       adapter_source=self.adapter_pin, producer_source=source, limits=limit, host_python=str(Path(sys.executable).resolve()),
                       bounded_owner_and_source_capture_qualified=True, complete_grade_dependency_and_resource_profile_qualified=True,
                       private_target_access_operator_only=True, scientific_qualified=False)
        runtime_pin = put('/grade-runtime.json', runtime)
        request = dict(schema='neural014-complete-grade-request-v1', task_id='NEURAL-014', execution_selected=True,
                       adapter_source=self.adapter_pin, producer_source=source,
                       selection=descriptor('/selection.json', selection_pin), external=descriptor('/external.json', external_pin),
                       outer_review=descriptor('/outer-review.json', review_pin), grade_runtime_review=descriptor('/grade-runtime.json', runtime_pin),
                       authority=descriptor('/authority.json', auth_pin), private_gold=descriptor('/private/GOLD.json', gold_pin), output='/graded.json', limits=limit)
        self.__class__.fixture_read_bytes += fs.read_bytes
        self.__class__.fixture_peak_body_bytes = max(self.__class__.fixture_peak_body_bytes, sum(len(b) for b in fs.files.values()))
        fs.read_bytes = 0
        return fs, request, schedule

    def execute(self, fs, request):
        try: return self.adapter.evaluate(request, self.adapter_pin, self.c, self.bodies, fs.read)
        finally: self.observed.append(dict(read_bytes=fs.read_bytes, gold_reads=fs.gold_reads))

    def test_complete_grade_and_reference(self):
        fs, req, phases = self.fixture_graph()
        result = self.execute(fs, req)
        self.assertEqual(len(phases), 164)
        self.assertEqual(result['result']['candidate']['primary_PER'], 0)
        self.assertAlmostEqual(result['result']['independent_reference']['primary_PER'], 1/3)
        self.assertAlmostEqual(result['result']['independent_reference_minus_candidate_full_adapt_PER'], 1/3)
        self.assertEqual(fs.gold_reads, 1)
        self.assertFalse(result['scientific_qualified'])

    def test_macro_denominator_and_separator(self):
        fs, req, _ = self.fixture_graph(heterogeneous=True)
        result = self.execute(fs, req)
        self.assertAlmostEqual(result['result']['candidate']['primary_PER'], 2/9)
        self.assertNotAlmostEqual(result['result']['candidate']['primary_PER'], 2/25)

    def test_empty_candidate_is_scored(self):
        fs, req, _ = self.fixture_graph(candidate_tokens=[])
        self.assertEqual(self.execute(fs, req)['result']['candidate']['primary_PER'], 1)
        self.assertEqual(fs.gold_reads, 1)

    def test_missing_prerequisites_before_gold(self):
        for field in ('execution_selected', 'source_preprocessing_lineage', 'runtime_approved', 'outer_natural', 'scientific_grading_authorized'):
            with self.subTest(field=field):
                fs, req, _ = self.fixture_graph()
                if field == 'execution_selected': req[field] = False
                else:
                    key, path, member = {
                        'source_preprocessing_lineage': (None, '/reviews/input.json', 'source_preprocessing_lineage'),
                        'runtime_approved': ('grade_runtime_review', '/grade-runtime.json', 'approved'),
                        'outer_natural': ('outer_review', '/outer-review.json', 'natural_exit'),
                        'scientific_grading_authorized': ('authority', '/authority.json', 'scientific_grading_authorized')}[field]
                    value = json.loads(fs.files[path]); value[member] = False; pp = fs.put(path, self.c.encoded(value))
                    if key: req[key].update(pp)
                    else:
                        sel = json.loads(fs.files['/selection.json']); sel['input_review'].update(pp)
                        req['selection'].update(fs.put('/selection.json', self.c.encoded(sel)))
                with self.assertRaises(ValueError): self.execute(fs, req)
                self.assertEqual(fs.gold_reads, 0)

    def test_malformed_candidate_and_reference_before_gold(self):
        for panel, duplicate in [('candidate', False), ('independent_reference', False), ('candidate', True)]:
            with self.subTest(panel=panel, duplicate=duplicate):
                fs, req, schedule = self.fixture_graph()
                phase = next(p for p in schedule if p['panel'] == panel and p['kind'] == 'infer')
                d = '/attempt/phases/' + phase['phase_id']
                raw = (b'{"id":"' + phase['case_id'].encode() + b'","tokens":["AA"],"tokens":["B"]}') if duplicate else self.c.encoded(dict(id=phase['case_id'], tokens=['AA1']))
                pred = fs.put(d + '/prediction.json', raw)
                native = json.loads(fs.files[d + '/NATIVE.json']); native['output'] = pred
                np = fs.put(d + '/NATIVE.json', self.c.encoded(native))
                closed = json.loads(fs.files[d + '/CLOSED.json']); closed['native'] = np
                fs.put(d + '/CLOSED.json', self.c.encoded(closed))
                with self.assertRaisesRegex(ValueError, 'Duplicate JSON field|unknown token'):
                    self.execute(fs, req)
                self.assertEqual(fs.gold_reads, 0)

    def test_missing_last_phase_before_gold(self):
        fs, req, schedule = self.fixture_graph()
        del fs.files['/attempt/phases/' + schedule[-1]['phase_id'] + '/CLOSED.json']
        with self.assertRaises(KeyError): self.execute(fs, req)
        self.assertEqual(fs.gold_reads, 0)

    def test_private_target_alias_refused_before_metadata_read(self):
        for role in ('selection', 'input_review'):
            with self.subTest(role=role):
                fs, req, _ = self.fixture_graph()
                if role == 'selection': req[role] = dict(req['private_gold'])
                else:
                    sel = json.loads(fs.files['/selection.json']); sel[role] = dict(req['private_gold'])
                    req['selection'].update(fs.put('/selection.json', self.c.encoded(sel)))
                with self.assertRaisesRegex(ValueError, 'private target cannot alias'):
                    self.execute(fs, req)
                self.assertEqual(fs.gold_reads, 0)

    def test_wrong_gold_generation_fails_after_single_capture(self):
        fs, req, _ = self.fixture_graph()
        gold = json.loads(fs.files['/private/GOLD.json']); gold['generation'] = 'f'*64
        pp = fs.put('/private/GOLD.json', self.c.encoded(gold)); req['private_gold'].update(pp)
        auth = json.loads(fs.files['/authority.json']); auth['private_gold'] = pp
        req['authority'].update(fs.put('/authority.json', self.c.encoded(auth)))
        with self.assertRaisesRegex(ValueError, 'Private generation join'): self.execute(fs, req)
        self.assertEqual(fs.gold_reads, 1)

    def test_captured_cli_disabled_request_has_no_output(self):
        fs, req, _ = self.fixture_graph(); req['execution_selected'] = False
        with tempfile.TemporaryDirectory(prefix='t15-generated-inert-', dir=HERE) as temp:
            req['output'] = str(Path(temp)/'never.json')
            path = Path(temp)/'request.json'; raw = self.c.encoded(req); path.write_bytes(raw)
            adapter, body = module(HERE/'grade_completed.py', _CAPTURED_LAUNCH_ORIGIN=time.monotonic(), _CAPTURED_ADAPTER_PIN=self.adapter_pin, _EARLY_SOURCE_READ_CHARGE=self.adapter_pin['bytes'] + 1)
            self.assertEqual(self.c.pin(body), self.adapter_pin)
            with self.assertRaisesRegex(ValueError, 'separate complete grading selection'):
                adapter.main(['--request', str(path), '--request-bytes', str(len(raw)), '--request-sha256', self.c.pin(raw)['sha256']])
            self.assertFalse(Path(req['output']).exists())

    def test_runtime_profile_numeric_aliases_before_gold(self):
        for bad in (True, 1.0):
            with self.subTest(bad=bad):
                fs, req, _ = self.fixture_graph(); req['limits']['cpu_seconds'] = 1
                runtime = json.loads(fs.files['/grade-runtime.json']); runtime['limits']['cpu_seconds'] = bad
                req['grade_runtime_review'].update(fs.put('/grade-runtime.json', self.c.encoded(runtime)))
                with self.assertRaisesRegex(ValueError, 'explicit finite whole grading limits'):
                    self.execute(fs, req)
                self.assertEqual(fs.gold_reads, 0)

    def test_captured_entry_charge_required(self):
        fs, req, _ = self.fixture_graph(); req['execution_selected'] = False
        with tempfile.TemporaryDirectory(prefix='t15-generated-charge-', dir=HERE) as temp:
            req['output'] = str(Path(temp)/'never.json'); path = Path(temp)/'request.json'
            raw = self.c.encoded(req); path.write_bytes(raw)
            for charge in (None, 0, self.adapter_pin['bytes']):
                with self.subTest(charge=charge):
                    adapter, _ = module(HERE/'grade_completed.py', _CAPTURED_LAUNCH_ORIGIN=time.monotonic(), _CAPTURED_ADAPTER_PIN=self.adapter_pin, _EARLY_SOURCE_READ_CHARGE=charge)
                    with self.assertRaisesRegex(ValueError, 'exact captured entry read reservation'):
                        adapter.main(['--request', str(path), '--request-bytes', str(len(raw)), '--request-sha256', self.c.pin(raw)['sha256']])
            self.assertFalse(Path(req['output']).exists())

    def test_captured_entry_is_debited_from_read_limit(self):
        fs, req, _ = self.fixture_graph(); req['execution_selected'] = False
        with tempfile.TemporaryDirectory(prefix='t15-generated-debit-', dir=HERE) as temp:
            req['output'] = str(Path(temp)/'never.json'); path = Path(temp)/'request.json'
            for _ in range(3):
                # Deliberately enough for every other initial source/request
                # read, but not the independently captured adapter itself.
                raw = self.c.encoded(req)
                req['limits']['reads'] = self.source_read_charge + self.adapter.BOOT['bytes'] + 1 + len(raw) + 1
            raw = self.c.encoded(req); path.write_bytes(raw)
            adapter, _ = module(HERE/'grade_completed.py', _CAPTURED_LAUNCH_ORIGIN=time.monotonic(), _CAPTURED_ADAPTER_PIN=self.adapter_pin, _EARLY_SOURCE_READ_CHARGE=self.adapter_pin['bytes'] + 1)
            with self.assertRaisesRegex(ValueError, 'whole source and grading read allowance'):
                adapter.main(['--request', str(path), '--request-bytes', str(len(raw)), '--request-sha256', self.c.pin(raw)['sha256']])
            self.assertFalse(Path(req['output']).exists())


    def test_literal_recipe_disabled_request_from_another_cwd(self):
        import subprocess
        fs, req, _ = self.fixture_graph(); req['execution_selected'] = False
        recipe_module, _ = module(HERE / 'launch_recipe.py')
        proposal = recipe_module.recipe(str(HERE / 'grade_completed.py'), self.adapter_pin)
        self.assertIs(proposal['selected'], False)
        self.assertIs(proposal['source_only'], True)
        with tempfile.TemporaryDirectory(prefix='t15-generated-recipe-', dir=HERE) as temp:
            req['output'] = str(Path(temp) / 'never.json')
            raw = self.c.encoded(req); path = Path(temp) / 'request.json'; path.write_bytes(raw)
            argv = [sys.executable, '-I', '-S', '-B', '-c', proposal['argv_template'][5],
                    '--request', str(path), '--request-bytes', str(len(raw)),
                    '--request-sha256', self.c.pin(raw)['sha256']]
            result = subprocess.run(argv, cwd=temp, capture_output=True, timeout=15)
            self.assertLessEqual(len(result.stdout) + len(result.stderr), 32768)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'separate complete grading selection required', result.stderr)
            self.assertFalse(Path(req['output']).exists())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--relocation-only', action='store_true')
    args = parser.parse_args()
    names = ('test_complete_grade_and_reference', 'test_captured_cli_disabled_request_has_no_output',
             'test_literal_recipe_disabled_request_from_another_cwd')
    suite = unittest.TestSuite(CompleteGrade(n) for n in names) if args.relocation_only else unittest.defaultTestLoader.loadTestsFromTestCase(CompleteGrade)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'generated_only': True, 'test_methods': result.testsRun,
                      'semantic_runs': len(CompleteGrade.observed), 'semantic_read_bytes': sum(x['read_bytes'] for x in CompleteGrade.observed),
                      'generated_fixture_read_bytes': CompleteGrade.fixture_read_bytes,
                      'generated_fixture_peak_body_bytes': CompleteGrade.fixture_peak_body_bytes,
                      'source_read_charge': CompleteGrade.source_read_charge,
                      'original_data_or_native_calls': 0, 'failures': len(result.failures), 'errors': len(result.errors)}, sort_keys=True))
    raise SystemExit(not result.wasSuccessful())

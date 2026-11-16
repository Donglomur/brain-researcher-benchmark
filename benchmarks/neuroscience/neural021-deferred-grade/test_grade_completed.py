"""Complete92 invented filesystem controls; never load authentic cases/targets.

The original observer admission, public validator and R2 scorer execute unchanged.
Only generated binding/data/receipt bytes replace authentic observations. They
are not source qualification, observed native closure or empirical performance.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
PRODUCER_ROOT = HERE / 'producer'
SCIENCE_ROOT = HERE / 'science'
SOURCE_READS = 0
GENERATED_WRITES = 0
FIXTURE_PEAK = 0


def source(path):
    global SOURCE_READS
    raw = path.read_bytes()
    SOURCE_READS += len(raw)
    return raw


def load(path):
    raw = source(path)
    spec = importlib.util.spec_from_loader(path.stem, loader=None)
    value = importlib.util.module_from_spec(spec)
    value.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value


g = load(HERE / 'grade_completed.py')
c = load(PRODUCER_ROOT / 'common.py')
manifest = c.parse(source(PRODUCER_ROOT / 'SOURCE_MANIFEST.json'))
BODIES = {name: source(PRODUCER_ROOT / name) for name in manifest['files']}
assert c.pin(c.encoded({}))  # imports do not open source data or execute observers
SCIENCE = {'interface.py': source(SCIENCE_ROOT / 'public/interface.py'),
           'scorer.py': source(SCIENCE_ROOT / 'private/scorer.py')}
ADAPTER = c.pin(source(HERE / 'grade_completed.py'))
LIMITS = dict(reads=67108864, output_bytes=65536, wall_seconds=60,
              cpu_seconds=30, host_memory_bytes=134217728)


def put(path, value, raw=False):
    global GENERATED_WRITES
    data = value if raw else c.encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    GENERATED_WRITES += len(data)
    return c.pin(data)


def row(path, value, raw=False):
    return dict(path=str(path), **put(path, value, raw))


def fixture(tmp, mode):
    """Build a full generated original observer chain, not a reduced query panel."""
    root = tmp / 'attempt'
    root.mkdir()
    bodies = dict(BODIES)
    binding = c.parse(BODIES['BINDINGS.json'])
    cases = dict(schema='neural021_public_cases_v1', task_id='NEURAL-021', time_bins=30,
                 queries=[dict(trial_id='q%04d' % i, condition='active' if i < 52 else 'passive') for i in range(92)])
    cases_row = row(tmp / 'public-cases.json', cases)
    truths = [[[float((i % 5) + t), float((i % 3) - t)] for t in range(30)] for i in range(92)]
    if mode == 'constant':
        truths = [[[0.0, 0.0] for _ in range(30)] for _ in range(92)]
    gold = dict(schema='neural021_private_targets_v1', cases_sha256=cases_row['sha256'],
                query_ids=[r['trial_id'] for r in cases['queries']], velocity_m_s=truths)
    if mode == 'bad_gold_generation':
        gold['cases_sha256'] = 'e' * 64
    gold_row = row(tmp / 'operator-only/targets.json', gold)
    predictions = copy.deepcopy(truths)
    if mode == 'negative':
        predictions = [[[1000.0, 1000.0] for _ in range(30)] for _ in range(92)]
    sub = dict(schema='neural021_trajectory_predictions_v1', task_id='NEURAL-021',
               cases_sha256=cases_row['sha256'], predictions=[dict(trial_id=r['trial_id'], velocity_m_s=p)
                    for r, p in zip(cases['queries'], predictions)])
    if mode == 'missing_last':
        sub['predictions'].pop()
    if mode == 'last_boolean':
        sub['predictions'][-1]['velocity_m_s'][-1][-1] = True
    if mode == 'missing_bin':
        sub['predictions'][-1]['velocity_m_s'].pop()
    for r in binding['files']:
        if r['target'] == 'public/cases.json':
            r.update(c.only_pin(cases_row))
        elif r['target'] == 'private/data/targets.json':
            r.update(c.only_pin(gold_row))
    binding['cases'] = c.only_pin(cases_row)
    bodies['BINDINGS.json'] = c.encoded(binding)
    public = {r['target']: c.only_pin(r) for r in binding['files'] if r['visibility'] == 'public'}
    program = row(tmp / 'candidate.py', b'# invented inert source; never executed\n', raw=True)
    put(root / 'commitment/program.py', b'# invented inert source; never executed\n', raw=True)
    selection = dict(schema='neural021_full92_program_selection_v1', execution_selected=True,
        task_id='NEURAL-021', repository=str(tmp / 'repo'), output=str(root), program=program,
        source=g.PRODUCER, docker_binary=str(tmp / 'unused-docker'), docker_socket=str(tmp / 'unused.sock'),
        image='sha256:' + 'a' * 64, fit_seconds=2, infer_seconds=2, memory_bytes=1073741824,
        other_future_bytes=0, scope=g.SCOPE, retained_bytes=c.RETAIN, managed_reads=c.READS + 64000000,
        managed_writes=c.WRITES + 16384, whole_seconds=1804, support_admission_authorized=True,
        numeric_grading_authorized=False)
    base = dict(task_id='NEURAL-021', approved=True, source=g.PRODUCER, program=c.only_pin(program),
                other_future_bytes=0, scope=g.SCOPE)
    method = dict(base, schema='neural021_full92_method_review_v1')
    for k in ('one_program_before_any_input','all272_train_92_queries_both_conditions',
              'fit_view_has_no_query_values_or_cases','same_frozen_program_and_sealed_state_before_query',
              'all_learned_transforms_models_tuning_use_training_only',
              'training_retention_and_training_only_lazy_computation_permitted',
              'full_query_batch_retrospective_not_streaming','all_null_negative_and_loss_dispositions_preserved',
              'time_template_baseline_interpretation_preserved','no_private_target_or_roster_exposure',
              'abi_and_prospective_state_budget_known_before_program_freeze'):
        method[k] = True
    for k in ('phase_isolation_proves_semantic_training_compliance','all_fitting_must_finish_before_seal',
              'scientific_or_baseline_outcome_already_measured','hashes_alone_prove_history'):
        method[k] = False
    runtime = dict(base, schema='neural021_runtime_profile_review_v1', image=selection['image'],
        fit_seconds=2, infer_seconds=2, memory_bytes=selection['memory_bytes'],
        runtime_versions={'python':'3.12.8','numpy':'2.2.6'}, state_cap_bytes=16777216,
        submission_cap_bytes=4194304, native_full_panel_qualification_required_before_campaign=True,
        qualification_inherited=False, independent_cli_groups_and_native_failure_recovery_acknowledged=True)
    selection['method_review'] = row(tmp / 'method.json', method)
    selection['runtime_review'] = row(tmp / 'runtime.json', runtime)
    selection_row = row(tmp / 'selection.json', selection)
    views = {}
    for phase in ('fit', 'infer', 'support'):
        names = binding['phase_public_members'][phase] if phase != 'support' else ['public/interface.py','public/cases.json']
        members = {Path(n).relative_to('public').as_posix(): public[n] for n in names}
        prep = put(root / ('VIEW_' + phase + '_PREPARED.json'), dict(schema='neural021_phase_view_v1',
            phase=phase, files=members, member_count=len(members), decoded=False))
        retired = put(root / ('VIEW_' + phase + '_RETIRED.json'), dict(schema='neural021_phase_retired_v1',
            phase=phase, member_count=len(members), absent=True, parent_fsynced=True))
        views[phase] = dict(prepared=prep, retired=retired)
    commitment = put(root / 'commitment/COMMITMENT.json', dict(source=g.PRODUCER,
        program=c.only_pin(program), scope=g.SCOPE, method_review=c.only_pin(selection['method_review']),
        before_any_public_signal_view=True))
    state = put(root / 'fit/state.bin', b'invented opaque training state', raw=True)
    submission = put(root / 'infer/submission.json', sub)
    support = put(root / 'admission/support.json', dict(task_id='NEURAL-021',
        status='public_format_admitted_ungraded', query_trials=92, active_queries=52,
        perturbation_queries=40, time_bins=30, velocity_axes=2, cases_sha256=cases_row['sha256'],
        private_target_calls=0, numerical_values_verified=False, scientific_qualification_added=False,
        operator_entrypoint='neural021_full92_public_support_v1', requires_observed_cli_exit_zero=True))
    command = dict(phase='capture', returncode=0, error_type=None, observed_retained_bytes=123,
        seconds=.1, client_reaped=True, cleanup_complete=True, cleanup_before_original_cutoff=True,
        owned_group_absence_observed=True, leader_exited_with_group_alive=False, group_probe_or_cleanup_error=None)
    natives = {}
    for i, (phase, name, artifact) in enumerate([('fit','state.bin',state),('infer','submission.json',submission),('admission','support.json',support)]):
        prefix = 'neural021-' + str(i + 1) * 24
        closure = [dict(kind=kind, name=prefix + '-' + suffix, removed=True, absence_observed=True,
                        creation_outcome_unknown=False, closed=True)
                   for kind,suffix in [('container',phase),('container','holder'),('volume','volume')]]
        if mode == 'unclosed_holder' and phase == 'infer':
            closure[1]['closed'] = False
        terminal = dict(Status='exited', Running=False, Dead=False, Pid=0, ExitCode=0, OOMKilled=False)
        if mode == 'boolean_native_exit' and phase == 'infer':
            terminal['ExitCode'] = False
        native = dict(schema='neural021_owned_phase_v1', phase=phase, source=g.PRODUCER,
            status='captured', attempt_prefix=prefix, closures=closure, all_native_resources_closed=True,
            cli_reaped=True, natural_exit=terminal, producer_closed_before_capture=True, error_type=None,
            command_metadata=[command], numerical_grading_called=False, recovery_may_be_required=False,
            outputs={name:artifact}, elapsed_seconds=.1)
        natives[phase] = put(root / phase / 'NATIVE.json', native)
    state_seal = put(root / 'STATE_COMMITTED.json', dict(schema='neural021_state_seal_v1',
        source=g.PRODUCER, program=c.only_pin(program), state=state, fit_native=natives['fit'],
        fit_retirement=views['fit']['retired'], before_any_query_view=True, readonly_owned_state=True,
        semantic_training_only_compliance_proven=False, training_only_lazy_computation_permitted=True))
    outputs = {'submission.json':submission}
    output_seal = put(root / 'SUBMISSION_COMMITTED.json', dict(source=g.PRODUCER,
        program=c.only_pin(program), state_commitment=state_seal, outputs=outputs,
        infer_native=natives['infer'], infer_retirement=views['infer']['retired'],
        public_format_not_yet_validated=True, numerically_validated=False))
    handoff = put(root / 'GRADE_HANDOFF.json', dict(task_id='NEURAL-021',
        submission=dict(path=str(root / 'infer/submission.json'), **submission),
        export_descriptor=binding['export_descriptor'], scope=g.SCOPE, execution_authorized=False,
        baselines_executed=False, semantic_training_compliance_proven=False,
        scientific_reasoning_or_causality_or_SOTA_established=False, new_budget_and_external_observer_required=True,
        private_target_calls_this_run=0, condition_R2_negative_null_and_loss_preserved=True,
        time_template_comparison_required_for_interpretation=True))
    complete = put(root / 'COMPLETE.json', dict(schema='neural021_full92_complete_v1',
        source=g.PRODUCER, program=c.only_pin(program), status='complete_unqualified', scope=g.SCOPE,
        all_public_views_retired=True, complete_public_format_validated=True, external_natural_zero_required=True,
        numerical_grading_performed=False, semantic_training_compliance_proven=False, runtime_qualified=False,
        scientific_qualified=False, views=views, native=natives, commitment=commitment, state=state,
        state_commitment=state_seal, outputs=outputs, outputs_commitment=output_seal,
        admission_output=support, grade_handoff=handoff))
    external_path = tmp / 'external.json'
    child = dict(natural_exit=True, exit_code=0, process_reaped=True, process_group_absent=True,
        streams_closed=True, timed_out=False, kill_sent=mode == 'forced_worker', error_type=None,
        timer_disable_error=None, timer_restore_error=None, pid=12345,
        combined_stream_bytes=1000, stdout_bytes=900, elapsed_seconds=10)
    argv = [str(Path(sys.executable).resolve()),'-I','-S','-B','-X',
        'pycache_prefix=' + str(external_path) + '.UNUSED-PYCACHE', str(PRODUCER_ROOT / 'worker.py'),
        '--source-pin',json.dumps(g.PRODUCER),'--selection',selection_row['path'],
        '--selection-pin',json.dumps(c.only_pin(selection_row)),'--origin','100.0','--worker-end','1884.0']
    external = dict(schema='neural021_full92_external_v1', status='complete_unqualified',
        source=g.PRODUCER, selection=c.only_pin(selection_row), attempt=str(root), argv=argv,
        child=child, error_type=None, outputs=outputs, complete=complete, origin_monotonic=100.0,
        whole_deadline=1904.0, outer_deadline=1964.0, elapsed_before_publication=11,
        full92_source_scope=True, scientific_qualified=False, runtime_qualified=False,
        numerical_grading_performed=False, nested_cli_and_native_recovery_may_be_required=False,
        automatic_retry=False)
    external_raw = c.encoded(external)
    external_row = row(external_path, external_raw + b' ' * (8192 - len(external_raw)), raw=True)
    outer = dict(schema='neural021_original_outer_exit_review_v1', task_id='NEURAL-021',
        producer_source=g.PRODUCER, observer_source=c.pin(BODIES['observe.py']),
        worker_source=c.pin(BODIES['worker.py']), selection=c.only_pin(selection_row),
        external=c.only_pin(external_row), attempt=str(root), original_origin_monotonic=100.0,
        original_whole_seconds=1804, elapsed_seconds=1804 if mode == 'late_outer' else 12,
        natural_exit=True, exit_code=0, process_reaped=True, process_group_absent=True,
        streams_closed=True, forced_termination=False, timer_cleanup_error=None)
    if mode == 'boolean_outer_exit':
        outer['exit_code'] = False
    outer_row = row(tmp / 'outer-review.json', outer)
    review = dict(schema='neural021_grade_runtime_review_v1', task_id='NEURAL-021',
        adapter_source=ADAPTER, producer_source=g.PRODUCER, limits=LIMITS,
        host_python=str(Path(sys.executable).resolve()), qualified_operator_only_target_boundary=True,
        original_input_method_runtime_reviews_independently_qualified=True,
        complete_grade_dependencies_and_external_CPU_RSS_enclosure_qualified=True,
        full_stdout_stderr_failure_cost_capture=True, scientific_qualified=False)
    review_row = row(tmp / 'grade-review.json', review)
    request = dict(schema='neural021_deferred_grade_request_v1', task_id='NEURAL-021', execution_selected=True,
        adapter_source=ADAPTER, producer_source=g.PRODUCER, producer_root=str(PRODUCER_ROOT),
        science_root=str(SCIENCE_ROOT), selection=selection_row, external=external_row,
        outer_review=outer_row, grade_review=review_row, cases=cases_row, private_targets=gold_row,
        output=str(tmp / 'score.json'), limits=LIMITS)
    authority = dict(schema='neural021_protected_grade_selection_v1', task_id='NEURAL-021',
        adapter_source=ADAPTER, producer_source=g.PRODUCER, selection=c.only_pin(selection_row),
        external=c.only_pin(external_row), outer_review=c.only_pin(outer_row), grade_review=c.only_pin(review_row),
        cases=c.only_pin(cases_row), private_targets=c.only_pin(gold_row), output=request['output'],
        limits=LIMITS, complete_scope=g.SCOPE, target_generation_independently_admitted=True,
        prior_target_exposure_disclosed=True, scientific_qualified=False)
    request['authority'] = row(tmp / 'authority.json', authority)
    if mode == 'target_alias':
        request['private_targets'] = copy.deepcopy(request['cases'])
    if mode == 'source_mismatch':
        request['producer_source'] = dict(g.PRODUCER, sha256='f'*64)
    if mode == 'postseal_prediction_change':
        (root / 'infer/submission.json').write_bytes(c.encoded(sub) + b' ')
    return request, bodies, tmp / 'operator-only/targets.json'


class MeteredBudget(g.Budget):
    def __init__(self, target):
        super().__init__(c, LIMITS, time.monotonic(), time.process_time())
        self.target = target
        self.observed_target_captures = 0

    def capture(self, path, cap, expected=None):
        if Path(path) == self.target:
            self.observed_target_captures += 1
        return super().capture(path, cap, expected)


class GradeTests(unittest.TestCase):
    def perform(self, mode):
        global FIXTURE_PEAK
        with tempfile.TemporaryDirectory(prefix='neural021-grade-invented-') as directory:
            tmp = Path(directory).resolve()
            request, bodies, target = fixture(tmp, mode)
            budget = MeteredBudget(target)
            try:
                value = g.evaluate(request, ADAPTER, c, bodies, SCIENCE, budget)
                return value, budget.observed_target_captures
            except (ValueError, KeyError, TypeError, TimeoutError) as error:
                return error, budget.observed_target_captures
            finally:
                FIXTURE_PEAK = max(FIXTURE_PEAK, sum(p.stat().st_size for p in tmp.rglob('*') if p.is_file()))

    def test_complete92_positive_negative_and_null(self):
        for mode in ('perfect', 'negative', 'constant'):
            with self.subTest(mode=mode):
                value, calls = self.perform(mode)
                self.assertIsInstance(value, dict, repr(value))
                self.assertEqual(calls, 1)
                self.assertEqual(value['complete_scope'], g.SCOPE)
                score = value['scientific_score']
                self.assertEqual(score['conditions']['active']['trials'], 52)
                self.assertEqual(score['conditions']['passive']['trials'], 40)
                self.assertEqual(score['conditions']['active']['trajectory_rows'], 1560)
                if mode == 'perfect':
                    self.assertEqual(score['mean_condition_r2'], 1.0)
                elif mode == 'negative':
                    self.assertLess(score['mean_condition_r2'], 0)
                else:
                    self.assertIsNone(score['mean_condition_r2'])
                    self.assertEqual(score['conditions']['active']['r2_status'], 'undefined_constant_target')
                self.assertFalse(value['scientific_qualified'])

    def test_all_public_and_closure_failures_before_targets(self):
        for mode in ('missing_last','last_boolean','missing_bin','unclosed_holder',
                     'boolean_native_exit','forced_worker','late_outer','boolean_outer_exit',
                     'target_alias','source_mismatch','postseal_prediction_change'):
            with self.subTest(mode=mode):
                value, calls = self.perform(mode)
                self.assertIsInstance(value, Exception)
                self.assertEqual(calls, 0)

    def test_wrong_target_generation_is_refused_after_one_capture(self):
        value, calls = self.perform('bad_gold_generation')
        self.assertIsInstance(value, ValueError)
        self.assertEqual(calls, 1)

    def test_isolated_cli_source_inspection(self):
        argv = [sys.executable,'-I','-S','-B',str(HERE / 'grade_completed.py'),'inspect',
                '--source-sha256',ADAPTER['sha256'],'--producer-root',str(PRODUCER_ROOT),
                '--science-root',str(SCIENCE_ROOT)]
        p = subprocess.run(argv,cwd=tempfile.gettempdir(),capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        value = json.loads(p.stdout)
        self.assertEqual(value['complete_scope'], g.SCOPE)
        self.assertEqual(value['private_target_captures'], 0)
        self.assertFalse(value['execution_selected'])

    def test_cli_refuses_changed_adapter_before_request(self):
        argv = [sys.executable,'-I','-S','-B',str(HERE / 'grade_completed.py'),'grade',
                '--source-sha256','f'*64,'--producer-root',str(PRODUCER_ROOT),
                '--science-root',str(SCIENCE_ROOT),'--request','/never-open-private-request',
                '--request-bytes','5','--request-sha256','a'*64]
        p = subprocess.run(argv,cwd=tempfile.gettempdir(),capture_output=True,text=True,timeout=20)
        self.assertEqual(p.returncode, 2)
        self.assertIn('stable authenticated bootstrap', p.stderr)
        failure = json.loads(p.stderr)
        self.assertEqual(failure['protected_target_captures'], 0)
        self.assertGreater(failure['read_reservations'], 0)
        self.assertGreaterEqual(failure['cpu_seconds'], 0)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GradeTests))
    print(json.dumps(dict(methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        source_read_bytes=SOURCE_READS,generated_write_bytes=GENERATED_WRITES,
        generated_fixture_peak_logical_bytes=FIXTURE_PEAK,authentic_data_or_target_reads=0,
        native_campaign_or_model_calls=0,generated_binding_overlay=True,
        unchanged_observer_validator_and_scorer_executed=True),sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)

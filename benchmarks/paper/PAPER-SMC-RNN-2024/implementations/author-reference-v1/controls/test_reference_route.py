"""Generated source controls for the protected author-reference route.

The scientific call is stubbed. ``offline.h5`` fixture bodies are deliberately
plain bytes, not neural arrays. These tests do not qualify model loading,
numerical predictions, scientific scoring, native custody, or runtime resources.
The complete suite is intended for one admission to the existing source pool.
"""
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace
import argparse
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

AUTHOR = Path(__file__).resolve().parents[1] / 'author'
sys.path.insert(0, str(AUTHOR))
import reference_core as core
import reference_adapter as adapter
import reference_worker as worker
import reference_episode as episode
import reference_overlay as overlay


HELPERS = ('author_predict.py', 'prepare.py', 'memory_reduction.py',
           'particle_reduction.patch', 'scorer.py', 'source_manifest.json',
           'reference_panel.json')
FAKE_OUTPUT = b'GENERATED NON-SCIENTIFIC OUTPUT; NOT HDF5\n'
TEST_PROFILE = core.reference_profile(36000)
SOURCE_PIN = core.pin(b'GENERATED REFERENCE OWNER SOURCE\n')
FIXTURE_PARENT = None
FIXTURE_CAP = 512 * 1024
FIXTURE_WRITTEN = 0
FIXTURE_RESERVATIONS = 0
REAL_WRITE_NEW = core.write_new


def reserve_fixture_bytes(size):
    """Precharge attempted writes; deleted fixtures never refund their charge."""
    global FIXTURE_WRITTEN, FIXTURE_RESERVATIONS
    if FIXTURE_PARENT is None or type(size) is not int or size < 0:
        raise ValueError('An explicit fixture parent and finite byte charge are required')
    if FIXTURE_WRITTEN + size > FIXTURE_CAP:
        raise ValueError('Cumulative generated-fixture byte cap exceeded before write')
    FIXTURE_WRITTEN += size
    FIXTURE_RESERVATIONS += 1


def fixture_path(filename):
    filename = Path(filename)
    if FIXTURE_PARENT is None or not filename.is_absolute() or not filename.is_relative_to(FIXTURE_PARENT):
        raise ValueError('Generated file escaped the selected controls fixture parent')
    return filename


def accounted_write_new(filename, raw, mode=0o400):
    fixture_path(filename)
    reserve_fixture_bytes(len(raw))
    return REAL_WRITE_NEW(filename, raw, mode)


def temporary_directory(prefix):
    if FIXTURE_PARENT is None:
        raise ValueError('Run this campaign with --fixture-parent; no system-temp fallback')
    return tempfile.TemporaryDirectory(prefix=prefix, dir=FIXTURE_PARENT)


def write(path, raw):
    path = fixture_path(path)
    reserve_fixture_bytes(len(raw))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return core.pin(raw)


def original_report(selected):
    return {'schema': 'smc_native_attempt_v1', 'mode': 'predict',
            'arm': selected['arm'], 'seed': selected['seed'], 'particles': 192,
            'source_requested_repeats': 32, 'smooth': False,
            'complete_source_prediction': True}


class AdapterFixture:
    """Only generated metadata and fake output, with real integrity primitives."""
    def __init__(self, root, phase):
        self.root = root
        self.phase = phase
        self.helpers = root / 'helpers'
        self.inputs = root / 'materials'
        self.output = root / 'output'
        for directory in (self.helpers, self.inputs, self.output):
            directory.mkdir()
        self.source = root / 'program.py'
        self.program_pin = write(self.source, b'# GENERATED ADAPTER IDENTITY; NEVER EXECUTED\n')
        bindings = {'schema': 'smc_author_reference_bindings_v1', 'helpers': {}}
        for name in HELPERS:
            bindings['helpers'][name] = write(
                self.helpers / name, ('# GENERATED HELPER IDENTITY: ' + name + '\n').encode())
        self.bindings = root / 'BINDINGS.json'
        self.bindings_pin = write(self.bindings, core.encode(bindings))
        self.plan = core.method_plan(phase, self.program_pin, self.bindings_pin, TEST_PROFILE)
        self.plan_path = root / 'declaration.json'
        self.plan_pin = write(self.plan_path, core.encode(self.plan))
        self.job = {
            'schema': 'smc_author_reference_execution_job_v2', 'route': core.ROUTE,
            'outcome': 'author_reference', 'condition': phase, 'phase_id': phase,
            'access_condition': 'paper_data_author_code_and_weights',
            'source': SOURCE_PIN, 'resource_profile': deepcopy(TEST_PROFILE),
            'submission_keys': ['offline'], 'program_sha256': self.program_pin['sha256'],
            'declaration_sha256': self.plan_pin['sha256'],
            'method_freeze_sha256': 'b' * 64, 'bindings': self.bindings_pin,
            'max_file_bytes': core.FILE_CAP}
        self.job_path = root / 'execution.json'
        self.save()

    def save(self):
        write(self.plan_path, core.encode(self.plan))
        write(self.job_path, core.encode(self.job))

    def run(self):
        return adapter.run(self.plan_path, self.job_path, self.source,
                           self.bindings, self.helpers, self.inputs, self.output)

    def stub_author(self, helper_root, selected, input_root, output, scratch, *, cpu_seconds):
        if cpu_seconds != TEST_PROFILE['cpu_seconds']:
            raise AssertionError('Selected reference CPU allowance was not forwarded')
        if helper_root != self.helpers or input_root != self.inputs or output != self.output:
            raise AssertionError('Adapter substituted a material/helper/output root')
        if not scratch.is_dir() or scratch == output:
            raise AssertionError('Author report must use distinct private scratch')
        write(output / 'offline.h5', FAKE_OUTPUT)
        return original_report(selected)


class GeneratedReferenceControls(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory('smc-reference-control-')
        # macOS /var is an alias; use its ordinary, canonical /private path.
        self.root = Path(self.temporary.name).resolve()
        self.case_number = 0

    def tearDown(self):
        self.temporary.cleanup()

    def fixture(self, phase='reference_causal'):
        self.case_number += 1
        root = self.root / ('case-' + str(self.case_number))
        root.mkdir()
        return AdapterFixture(root, phase)

    def test_both_original_recipes_preserve_model_arm_and_assisted_access(self):
        # Scientific constants are asserted independently of method_plan's output.
        for phase, arm, seed in [('reference_causal', 'causal', 20261117),
                                 ('reference_noncausal', 'noncausal', 20261118)]:
            with self.subTest(phase=phase):
                fixture = self.fixture(phase)
                with mock.patch.object(adapter, 'invoke_author',
                                       side_effect=fixture.stub_author) as invoke:
                    actual = fixture.run()
                self.assertEqual(invoke.call_count, 1)
                selected = invoke.call_args.args[1]
                self.assertEqual(selected, {
                    'arm': arm, 'seed': seed, 'particles': 192, 'repeats': 32,
                    'smooth': False, 'device': 'cpu', 'training': False,
                    'checkpoint_search': False,
                    'access_condition': 'paper_data_author_code_and_weights'})
                self.assertEqual(actual['role'], 'author_calibration')
                self.assertEqual(actual['phase_id'], phase)
                self.assertEqual(actual['access_condition'], 'paper_data_author_code_and_weights')
                self.assertEqual(actual['recipe'], selected)
                self.assertIs(actual['AI_attempt'], False)
                self.assertIs(actual['scientific_improvement'], False)
                self.assertIs(actual['training'], False)
                self.assertIs(actual['adaptation'], False)
                self.assertEqual({p.name for p in fixture.output.iterdir()},
                                 {'offline.h5', 'actual_declaration.json'})
                self.assertEqual((fixture.output / 'offline.h5').read_bytes(), FAKE_OUTPUT)
                self.assertEqual(json.loads((fixture.output / 'actual_declaration.json').read_bytes()), actual)

    def test_paper_only_or_inconsistent_model_plan_never_reaches_author(self):
        changes = [
            ('paper-only', lambda f: f.plan.update(access_condition='paper_data')),
            ('changed-model', lambda f: f.plan['recipe'].update(arm='noncausal')),
            ('changed-seed', lambda f: f.plan['recipe'].update(seed=20261118)),
            ('fewer-repeats', lambda f: f.plan['recipe'].update(repeats=1)),
            ('fewer-particles', lambda f: f.plan['recipe'].update(particles=16)),
            ('changed-output', lambda f: f.job.update(submission_keys=['causal', 'noncausal'])),
            ('candidate-outcome', lambda f: f.job.update(outcome='improvement')),
            ('extra-target-input', lambda f: f.job.update(target='/private/eval_target_20ms.h5')),
            ('declaration-drift', lambda f: f.job.update(declaration_sha256='c' * 64)),
        ]
        for label, change in changes:
            with self.subTest(case=label):
                fixture = self.fixture()
                change(fixture)
                fixture.save()
                with mock.patch.object(adapter, 'invoke_author') as invoke:
                    with self.assertRaises(ValueError):
                        fixture.run()
                invoke.assert_not_called()
                self.assertFalse((fixture.output / 'actual_declaration.json').exists())

    def test_helper_tampering_rejected_before_scientific_boundary(self):
        fixture = self.fixture()
        write(fixture.helpers / 'author_predict.py', b'# TAMPERED HELPER\n')
        with mock.patch.object(adapter, 'invoke_author') as invoke:
            with self.assertRaises(ValueError):
                fixture.run()
        invoke.assert_not_called()
        self.assertEqual(list(fixture.output.iterdir()), [])

    def test_original_test_target_path_is_refused_before_scientific_boundary(self):
        fixture = self.fixture()
        # Only a generated sentinel is written; no target array is obtained/read.
        target = fixture.inputs / 'inputs/mc_maze/test/eval_target_20ms.h5'
        write(target, b'GENERATED FORBIDDEN-TARGET SENTINEL\n')
        with mock.patch.object(adapter, 'invoke_author') as invoke:
            with self.assertRaises(ValueError):
                fixture.run()
        invoke.assert_not_called()
        self.assertFalse((fixture.output / 'actual_declaration.json').exists())

    def test_incomplete_or_wrong_author_report_cannot_be_promoted(self):
        changes = [
            ('wrong-arm', {'arm': 'noncausal'}),
            ('wrong-seed', {'seed': 20261118}),
            ('partial-prediction', {'complete_source_prediction': False}),
            ('characterization-only', {'mode': 'characterize'}),
            ('changed-particles', {'particles': 16}),
            ('changed-repeats', {'source_requested_repeats': 1}),
            ('smoothed-output', {'smooth': True}),
        ]
        for label, replacement in changes:
            with self.subTest(case=label):
                fixture = self.fixture()

                def bad_report(*args, **kwargs):
                    report = fixture.stub_author(*args, **kwargs)
                    report.update(replacement)
                    return report

                with mock.patch.object(adapter, 'invoke_author', side_effect=bad_report):
                    with self.assertRaises(ValueError):
                        fixture.run()
                # Failed scientific-boundary evidence is retained; no successful declaration.
                self.assertTrue((fixture.output / 'offline.h5').exists())
                self.assertFalse((fixture.output / 'actual_declaration.json').exists())

    def test_extra_or_linked_prediction_output_is_refused(self):
        for kind in ('extra-file', 'linked-prediction'):
            with self.subTest(kind=kind):
                fixture = self.fixture()

                def bad_output(helper_root, selected, input_root, output, scratch, *, cpu_seconds):
                    if kind == 'extra-file':
                        write(output / 'offline.h5', FAKE_OUTPUT)
                        write(output / 'unexpected.txt', b'GENERATED EXTRA OUTPUT\n')
                    else:
                        real = fixture.root / 'outside-prediction.bin'
                        write(real, FAKE_OUTPUT)
                        (output / 'offline.h5').symlink_to(real)
                    return original_report(selected)

                with mock.patch.object(adapter, 'invoke_author', side_effect=bad_output):
                    with self.assertRaises(ValueError):
                        fixture.run()
                self.assertFalse((fixture.output / 'actual_declaration.json').exists())

    def test_source_failure_is_preserved_without_retry(self):
        fixture = self.fixture()
        failure = RuntimeError('GENERATED AUTHOR FAILURE')
        with mock.patch.object(adapter, 'invoke_author', side_effect=failure) as invoke:
            with self.assertRaisesRegex(RuntimeError, 'GENERATED AUTHOR FAILURE'):
                fixture.run()
        self.assertEqual(invoke.call_count, 1)
        self.assertFalse((fixture.output / 'actual_declaration.json').exists())

    def worker_inputs(self, phase='reference_causal'):
        fixture = self.fixture(phase)
        job = deepcopy(fixture.job)
        request = {'schema': 'smc_aggregate_phase_request_v1', 'phase_id': phase,
                   'role': 'B', 'source': SOURCE_PIN,
                   'resources': {'cpu_seconds': 36000, 'producer_seconds': 10800,
                                 'memory_bytes': 8589934592, 'cpu_nanos': 6000000000,
                                 'pids': 32}}
        old = SimpleNamespace(JOB='generated-job', REQUEST='generated-request',
                              compact=core.encode, before_deadline=mock.Mock())

        def metadata(which):
            value = job if which == old.JOB else request
            return core.encode(value), value

        old.metadata = metadata
        return job, request, old

    def test_worker_requires_assisted_B_for_each_distinct_model_phase(self):
        observed = []
        for phase in ('reference_causal', 'reference_noncausal'):
            job, request, old = self.worker_inputs(phase)
            actual_job, raw, actual_request = worker.authenticated(old)
            self.assertEqual(actual_job, job)
            self.assertEqual(raw, core.encode(request))
            self.assertEqual(actual_request['role'], 'B')
            self.assertEqual(actual_job['access_condition'], 'paper_data_author_code_and_weights')
            observed.append(actual_job['phase_id'])
            old.before_deadline.assert_called_once_with(request)
        self.assertEqual(observed, ['reference_causal', 'reference_noncausal'])

    def test_worker_rejects_paper_only_role_arm_and_resource_drift(self):
        changes = [
            ('role-A', lambda j, r: r.update(role='A')),
            ('paper-only', lambda j, r: j.update(access_condition='paper_data')),
            ('swapped-phase', lambda j, r: r.update(phase_id='reference_noncausal')),
            ('unknown-arm', lambda j, r: j.update(phase_id='reference_third')),
            ('changed-source', lambda j, r: r.update(source=core.pin(b'different source'))),
            ('more-cpu', lambda j, r: r['resources'].update(cpu_seconds=75000)),
            ('more-memory', lambda j, r: r['resources'].update(memory_bytes=17179869184)),
            ('missing-scope', lambda j, r: r['resources'].update(pids=0)),
        ]
        for label, change in changes:
            with self.subTest(case=label):
                job, request, old = self.worker_inputs()
                change(job, request)
                with self.assertRaises(ValueError):
                    worker.authenticated(old)
                old.before_deadline.assert_not_called()

    def test_worker_rejects_noncanonical_wire_record(self):
        job, request, old = self.worker_inputs()
        old.metadata = lambda which: ((core.encode(job), job) if which == old.JOB
                                      else (core.encode(request) + b' ', request))
        with self.assertRaises(ValueError):
            worker.authenticated(old)
        old.before_deadline.assert_not_called()

    def mount_fixture(self):
        fixture = self.fixture()
        component = fixture.root / 'component'
        component.mkdir()
        for name in ('reference_worker.py', 'reference_core.py', 'BINDINGS.json'):
            write(component / name, ('GENERATED MOUNT SOURCE ' + name + '\n').encode())
        delivery = {'files': [
            {'path': 'official_source/vi_rnn/vae.py', **core.pin(b'generated source')},
            {'path': 'inputs/mc_maze/test/eval_input_20ms.h5', **core.pin(b'generated input')}]}
        programme = {'program': fixture.program_pin, 'declaration': fixture.plan_pin}
        protocol = {'pair_path': str(fixture.inputs / 'pair.json'),
                    'task_path': str(fixture.root / 'task.json'),
                    'programs': {phase: programme for phase in core.PHASES}}
        facade = object.__new__(episode.ReferenceEpisode)
        facade._protocol = protocol
        facade.HERE = component
        facade.repository_root = fixture.root / 'generated-repository'
        facade.bindings = json.loads(fixture.bindings.read_bytes())
        facade.public_context = mock.Mock(return_value=({}, {core.ACCESS: delivery}))
        facade.relative = mock.Mock()
        facade.file_mount = lambda origin, identity, purpose: {
            'source': str(origin), 'identity': identity, 'purpose': purpose}
        return fixture, facade, protocol, delivery

    def test_each_model_mounts_only_assisted_materials_with_historical_provenance(self):
        fixture, facade, protocol, _ = self.mount_fixture()
        for phase in core.PHASES:
            mounts = facade.mounts_for(fixture.root / 'PROTOCOL.json', protocol, phase,
                                      fixture.job_path, core.pin(core.encode(fixture.job)), {})
            self.assertEqual(mounts['/materials/official_source/vi_rnn/vae.py']['purpose'],
                             'historical_author_source')
            self.assertIn('/selected_artifacts/author_reference/author_predict.py', mounts)
            self.assertEqual(mounts['/selected_artifacts/author_reference/author_predict.py']['purpose'],
                             'historical_author_source')
            self.assertFalse(any('/test/eval_target' in destination for destination in mounts))
            self.assertFalse(any(destination.startswith('/private') for destination in mounts))
            self.assertIn('/runner/reference_core.py', mounts)
            self.assertIn(core.ACCESS, mounts['/materials/official_source/vi_rnn/vae.py']['source'])

    def test_target_entry_in_generated_delivery_is_refused(self):
        fixture, facade, protocol, delivery = self.mount_fixture()
        delivery['files'].append({'path': 'inputs/mc_maze/test/eval_target_20ms.h5',
                                  **core.pin(b'generated forbidden target descriptor')})
        with self.assertRaises(ValueError):
            facade.mounts_for(fixture.root / 'PROTOCOL.json', protocol, 'reference_causal',
                              fixture.job_path, core.pin(core.encode(fixture.job)), {})


def generated_closed_pair():
    return {'schema': 'smc_author_reference_closed_pair_v1', 'route': core.ROUTE,
            'outcome': 'author_reference', 'conditions': {phase: {} for phase in core.PHASES},
            'both_conditions_closed_before_private_grade': True,
            'all_programmes_frozen_before_execution': True, 'private_target_accessed': False,
            'AI_attribution_verified': False, 'scientific_success': None}


class GradeBoundaryControls(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory('smc-reference-grade-control-')
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_reference_pair_passes_only_metadata_gate(self):
        closed = generated_closed_pair()
        self.assertIs(episode.validate_reference_pair(closed), closed)
        # Passing this function supplies no parent/cgroup/actual model qualification.

    def test_partial_or_relabelled_pair_cannot_reach_the_scorer(self):
        changes = [
            ('missing-model', lambda c: c['conditions'].pop('reference_noncausal')),
            ('old-access-keys', lambda c: c.update(conditions={
                'paper_data': {}, 'paper_data_author_code_and_weights': {}})),
            ('early-target', lambda c: c.update(private_target_accessed=True)),
            ('open-scope', lambda c: c.update(both_conditions_closed_before_private_grade=False)),
            ('unfrozen-method', lambda c: c.update(all_programmes_frozen_before_execution=False)),
            ('AI-attribution', lambda c: c.update(AI_attribution_verified=True)),
            ('scientific-win', lambda c: c.update(scientific_success=True)),
            ('improvement-route', lambda c: c.update(outcome='improvement')),
        ]
        for number, (label, change) in enumerate(changes):
            with self.subTest(case=label):
                closed = generated_closed_pair()
                change(closed)
                raw = core.encode(closed)
                closed_path = self.root / ('closed-' + str(number) + '.json')
                write(closed_path, raw)
                facade = object.__new__(episode.ReferenceEpisode)
                facade.admit_protocol = mock.Mock(side_effect=AssertionError('Invalid pair admitted'))
                facade.benchmark = mock.Mock(side_effect=AssertionError('Scorer reached before closure'))
                with self.assertRaises(ValueError):
                    facade._grade_from_owned_pair(
                        closed_path, core.pin(raw)['sha256'],
                        self.root / 'UNAVAILABLE_TARGET', self.root / 'UNAVAILABLE_EVALUATOR',
                        self.root / ('result-' + str(number) + '.json'), 4096)
                facade.admit_protocol.assert_not_called()
                facade.benchmark.assert_not_called()

    def grade_fixture(self, name, fail_validation_number=None):
        root = self.root / name
        root.mkdir()
        public_root = root / 'public'
        protocol_root = root / 'protocol'
        owned_root = root / 'owned'
        private_root = root / 'private'
        for directory in (public_root, protocol_root, owned_root, private_root):
            directory.mkdir()
        # The actual grade method writes two temporary prediction snapshots.
        # Precharge both even when a negative case fails before either copy.
        reserve_fixture_bytes(2 * len(FAKE_OUTPUT))
        events = []
        closed = generated_closed_pair()
        protocol = {'source': SOURCE_PIN, 'pair_path': str(public_root / 'pair.json'),
                    'programs': {phase: {'fixture': phase} for phase in core.PHASES}}
        runtime = {'qualification': core.pin(b'GENERATED QUALIFICATION REFERENCE')}
        closed.update(protocol_path=str(protocol_root / 'PROTOCOL.json'), protocol_sha256='d' * 64,
                      source=SOURCE_PIN, runtime_qualification=runtime['qualification'])
        predictions = {}
        for phase in core.PHASES:
            receipt_path = owned_root / 'control' / phase / 'RECEIPT.json'
            receipt_pin = write(receipt_path, core.encode({
                'fixture_phase': phase, 'output_inventory': {
                    'complete': True, 'files': {'offline.h5': core.pin(FAKE_OUTPUT)}}}))
            selected = core.recipe(phase)
            freeze = {'role': 'author_calibration', 'arm': selected['arm'],
                      'seed': selected['seed'], 'particles': 192, 'repeats': 32}
            freeze_path = owned_root / 'freezes' / (phase + '.json')
            freeze_pin = write(freeze_path, core.encode(freeze))
            request = {'phase_id': phase, 'role': 'B', 'source': SOURCE_PIN}
            request_pin = write(owned_root / 'jobs' / phase / 'REQUEST.json', core.encode(request))
            predicted = owned_root / 'predictions' / phase / 'offline.h5'
            write(predicted, FAKE_OUTPUT)
            predictions[phase] = predicted
            closed['conditions'][phase] = {
                'receipt_path': str(receipt_path), 'receipt': receipt_pin,
                'freeze_path': str(freeze_path), 'freeze': freeze_pin, 'request': request_pin}
        closed_path = owned_root / 'PAIR_CLOSED.json'
        closed_pin = write(closed_path, core.encode(closed))
        target = root / 'operator' / 'target-sentinel.bin'
        write(target, b'GENERATED TARGET SENTINEL; NOT SCIENTIFIC DATA\n')
        validations = []

        def validate_freeze(prediction, panel, original_protocol, freeze):
            record = json.loads(Path(freeze).read_bytes())
            phase = 'reference_' + record['arm']
            stage = 'source' if Path(prediction) == predictions[phase] else 'snapshot'
            validations.append((phase, stage))
            events.append(('validate', phase, stage))
            if fail_validation_number == len(validations):
                raise ValueError('GENERATED INVALID COMPLETE FREEZE')
            self.assertEqual(Path(prediction).read_bytes(), FAKE_OUTPUT)

        def score_predictions(prediction, panel, original_protocol, freeze, selected_target,
                              target_sha, evaluator, report_path):
            record = json.loads(Path(freeze).read_bytes())
            phase = 'reference_' + record['arm']
            self.assertTrue(all((p, 'snapshot') in validations for p in core.PHASES))
            self.assertEqual(Path(prediction).read_bytes(), FAKE_OUTPUT)
            self.assertEqual(Path(selected_target), target)
            target.read_bytes()  # Generated sentinel, opened only at the stubbed target boundary.
            events.append(('score-target-read', phase))
            result = {'metrics': {metric: 0.0 for metric in ('co-bps', 'vel R2', 'psth R2', 'fp-bps')},
                      'generated_fixture_only': True}
            write(Path(report_path), core.encode(result))
            return result

        original = SimpleNamespace(validate_freeze=validate_freeze,
                                   score_predictions=score_predictions, TARGET_SHA256='f' * 64)
        facade = object.__new__(episode.ReferenceEpisode)
        facade.HERE = AUTHOR
        facade.admit_protocol = mock.Mock(return_value=(protocol, runtime))
        facade.benchmark = lambda: SimpleNamespace(original=lambda: original)
        facade.job_for = lambda selected_protocol, phase: {'fixture': phase}
        facade.request_bytes = core.encode
        facade.validate_closed = lambda request, receipt: events.append(('closed', request['phase_id']))
        facade.captured_predictions = lambda receipt, phase, outcome, programme: {
            'offline': predictions[phase]}
        return facade, closed_path, closed_pin, target, private_root, events

    def test_public_protocol_owned_or_source_output_is_rejected_before_scorer_load(self):
        for location in ('public', 'protocol', 'owned', 'source'):
            with self.subTest(location=location):
                fixture = self.grade_fixture('unsafe-output-' + location)
                facade, closed_path, closed_pin, target, private_root, events = fixture
                protocol = facade.admit_protocol.return_value[0]
                closed = json.loads(closed_path.read_bytes())
                folders = {'public': Path(protocol['pair_path']).parent,
                           'protocol': Path(closed['protocol_path']).parent,
                           'owned': closed_path.parent, 'source': facade.HERE}
                destination = folders[location] / ('GENERATED-FORBIDDEN-' + self.root.name + '.json')
                facade.benchmark = mock.Mock(side_effect=AssertionError('Scorer loaded for unsafe output'))
                with self.assertRaisesRegex(ValueError, 'outside public/protocol/owned/source'):
                    facade._grade_from_owned_pair(closed_path, closed_pin['sha256'], target,
                                                  private_root / 'EVALUATOR_NOT_EXECUTED',
                                                  destination, 4096)
                facade.benchmark.assert_not_called()
                self.assertFalse(any(event[0] == 'score-target-read' for event in events))
                self.assertFalse(destination.exists())

    def test_both_complete_snapshots_precede_any_target_read_and_all_metrics_survive(self):
        facade, closed_path, closed_pin, target, root, events = self.grade_fixture('complete')
        result = facade._grade_from_owned_pair(closed_path, closed_pin['sha256'], target,
                                               root / 'EVALUATOR_NOT_EXECUTED',
                                               root / 'results.json', 4096)
        first_score = next(i for i, event in enumerate(events) if event[0] == 'score-target-read')
        for phase in core.PHASES:
            self.assertIn(('closed', phase), events[:first_score])
            self.assertIn(('validate', phase, 'source'), events[:first_score])
            self.assertIn(('validate', phase, 'snapshot'), events[:first_score])
        self.assertEqual([event for event in events if event[0] == 'score-target-read'],
                         [('score-target-read', 'reference_causal'),
                          ('score-target-read', 'reference_noncausal')])
        self.assertEqual(set(result['models']), {'causal', 'noncausal'})
        for row in result['models'].values():
            self.assertEqual(set(row['metrics']), {'co-bps', 'vel R2', 'psth R2', 'fp-bps'})
        for flag in ('AI_attempt', 'scientific_improvement', 'independent_replication_established',
                     'inference_repeats_are_independent_models', 'SOTA_claim'):
            self.assertIs(result[flag], False)

    def test_second_reference_validation_failure_never_opens_target(self):
        # Failure at either the second original or second copied snapshot is fatal.
        for validation_number in (2, 4):
            with self.subTest(validation_number=validation_number):
                fixture = self.grade_fixture('failure-' + str(validation_number), validation_number)
                facade, closed_path, closed_pin, target, root, events = fixture
                with self.assertRaisesRegex(ValueError, 'GENERATED INVALID COMPLETE FREEZE'):
                    facade._grade_from_owned_pair(closed_path, closed_pin['sha256'], target,
                                                  root / 'EVALUATOR_NOT_EXECUTED',
                                                  root / 'results.json', 4096)
                self.assertFalse(any(event[0] == 'score-target-read' for event in events))
                self.assertFalse((root / 'results.json').exists())

    def test_bounded_snapshot_positive_preserves_the_exact_precharged_extent(self):
        source = self.root / 'generated-snapshot-source.bin'
        destination = self.root / 'generated-snapshot-copy.bin'
        expected = write(source, FAKE_OUTPUT)
        reserve_fixture_bytes(expected['bytes'])
        actual = episode.copy_snapshot(source, destination, expected, expected['bytes'])
        self.assertEqual(actual, expected)
        self.assertEqual(destination.stat().st_size, expected['bytes'])
        self.assertEqual(destination.read_bytes(), FAKE_OUTPUT)

    def test_source_growth_during_snapshot_never_exceeds_its_charge_or_reaches_scoring(self):
        facade, closed_path, closed_pin, target, root, events = self.grade_fixture('snapshot-growth')
        original_copy = episode.copy_snapshot
        original_open = os.open
        observed_failures = []
        growth = b'GENERATED OVERFLOW AFTER INITIAL FSTAT\n' * 8

        def copy_with_generated_growth(source, destination, expected, cap):
            if Path(source).parent.name != 'reference_noncausal':
                return original_copy(source, destination, expected, cap)

            def grow_when_destination_opens(filename, flags, *args, **kwargs):
                descriptor = original_open(filename, flags, *args, **kwargs)
                if Path(filename) == destination:
                    # The real helper has already authenticated initial source size.
                    # Append before its first read, without a thread/process or payload.
                    fixture_path(source)
                    reserve_fixture_bytes(len(growth))
                    with Path(source).open('ab') as stream:
                        stream.write(growth)
                return descriptor

            with mock.patch.object(episode.os, 'open', side_effect=grow_when_destination_opens):
                try:
                    return original_copy(source, destination, expected, cap)
                except ValueError:
                    observed_failures.append({
                        'copied_bytes': destination.stat().st_size,
                        'precharged_bytes': expected['bytes'],
                        'source_bytes_after_growth': Path(source).stat().st_size})
                    raise

        with mock.patch.object(episode, 'copy_snapshot', side_effect=copy_with_generated_growth):
            with self.assertRaisesRegex(ValueError, 'grew beyond precharged extent'):
                facade._grade_from_owned_pair(closed_path, closed_pin['sha256'], target,
                                              root / 'EVALUATOR_NOT_EXECUTED',
                                              root / 'results.json', 4096)
        self.assertEqual(len(observed_failures), 1)
        failure = observed_failures[0]
        self.assertLessEqual(failure['copied_bytes'], failure['precharged_bytes'])
        self.assertGreater(failure['source_bytes_after_growth'], failure['precharged_bytes'])
        self.assertFalse(any(event[0] == 'score-target-read' for event in events))
        self.assertFalse((root / 'results.json').exists())


class SerialReferenceOwnerControls(unittest.TestCase):
    """Execute retained owner sequencing with generated Provider/custody stubs."""
    @classmethod
    def setUpClass(cls):
        repository = AUTHOR.parents[5]
        owner_root = repository / overlay.OWNER_REL
        manifest_raw = (owner_root / 'SOURCE.json').read_bytes()
        if core.pin(manifest_raw) != overlay.OWNER_SOURCE:
            raise AssertionError('Original owner fixture source identity changed')
        cls.owner_manifest = json.loads(manifest_raw)
        cls.originals = {name: (owner_root / name).read_bytes()
                         for name in overlay.OWNER_FILES}
        cls.legacy_raw = (AUTHOR / 'reference_legacy.py').read_bytes()
        cls.derived, cls.changes = overlay.derive_owner_sources(
            cls.originals, cls.owner_manifest, cls.legacy_raw)

    def setUp(self):
        self.temporary = temporary_directory('smc-reference-owner-control-')
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def execute_generated_owner(self, fail_phase=None):
        events = []
        root = self.root
        protocol_folder = root / 'protocol'
        protocol_folder.mkdir()
        materials = root / 'materials'
        materials.mkdir()
        transport = root / 'transport'
        transport.mkdir()
        write(transport / 'SOURCE_MANIFEST.json', b'{"generated":true}\n')
        protocol = {'source': SOURCE_PIN, 'outcome': 'author_reference',
                    'pair_path': str(materials / 'pair.json'),
                    'task_path': str(materials / 'task.json'),
                    'programs': {phase: {'fixture': phase} for phase in core.PHASES}}
        protocol_path = protocol_folder / 'PROTOCOL.json'
        protocol_pin = write(protocol_path, core.encode(protocol))
        runtime = {'image': 'sha256:' + 'a' * 64,
                   'qualification': {**core.pin(b'generated qualification'), 'image_inventory_sha256': '1' * 64},
                   'docker_binary': 'NEVER_EXECUTED', 'docker_socket': 'NEVER_OPENED',
                   'source_read_bytes': 1048576, 'host_write_bytes': 1048576}
        now = time.monotonic()
        invocation = {'protocol_path': str(protocol_path), 'protocol_pin': protocol_pin,
                      'output': str(root / 'episode-output'),
                      'clock': {'origin': now, 'controller_deadline': now + 30, 'deadline': now + 60},
                      'deployment_pin': core.pin(b'generated deployment')}
        invocation_pin = core.pin(core.encode(invocation))

        def publish(path, raw, mode=0o400):
            return write(Path(path), raw)

        class Provider:
            def __init__(self, control, quarantine, *unused):
                self.control, self.quarantine = control, quarantine

            def execute_phase(self, request, mounts, deadline, journal):
                phase = request['phase_id']
                events.append(('execute', phase, request['role']))
                if request['role'] != 'B':
                    raise AssertionError('Historical author material incorrectly assigned paper-only wire A')
                if phase == fail_phase:
                    raise RuntimeError('GENERATED SECOND AUTHOR FAILURE')
                prediction = self.quarantine / phase / 'offline.h5'
                write(prediction, FAKE_OUTPUT)
                receipt = {'fixture_phase': phase, 'prediction': str(prediction)}
                receipt_path = self.control / phase / 'RECEIPT.json'
                receipt_pin = write(receipt_path, core.encode(receipt))
                return {'receipt': receipt, 'receipt_path': str(receipt_path), 'receipt_pin': receipt_pin}

        class Benchmark:
            def inspect_pair(self, *args, **kwargs):
                events.append(('inspect-generated-materials',))

            def freeze(self, *args, **kwargs):
                phase, destination = args[4], Path(args[8])
                events.append(('freeze', phase))
                return write(destination, core.encode({'generated_reference_freeze': phase}))

        benchmark = Benchmark()

        def observe_closed(provider, request, result, deadline):
            events.append(('closed', request['phase_id']))
            return result['receipt']

        facade = SimpleNamespace(
            admit_protocol=lambda *_: (protocol, runtime),
            qualify=lambda *_: {'image_inventory_sha256': '1' * 64},
            public_context=lambda *_: ({}, {}), benchmark=lambda: benchmark,
            PAIR_SHA='2' * 64, TASK_SHA='3' * 64, PAIR_CAP=1048576,
            path=core.path, publish=publish, encoded=core.encode, pin=core.pin,
            COMMAND=['GENERATED_NO_PROCESS'], TRANSPORT=transport,
            REQUEST_SCHEMA='smc_aggregate_phase_request_v1',
            CLOSED_SCHEMA='smc_author_reference_closed_pair_v1', ROUTE=core.ROUTE,
            job_for=lambda selected_protocol, phase: {'fixture_phase': phase},
            mounts_for=lambda *args: {'generated_assisted_mount': {'purpose': 'historical_author_source'}},
            mount_identity=lambda mounts: mounts,
            resources=lambda *_: deepcopy(TEST_PROFILE),
            aggregate_plan=lambda *args: {'fixture_phase': args[2]},
            request_bytes=core.encode, provider_class=lambda: Provider,
            observe_closed=observe_closed,
            captured_predictions=lambda receipt, *args: {'offline': Path(receipt['prediction'])})

        def journal(name, value):
            if name == 'PREPARED':
                events.append(('prepared', value['request']['phase_id'], value['request']['role']))
            elif name == 'CONTROLLER-DONE':
                events.append(('pair-closed',))
            else:
                events.append(('journal', name))

        common = ModuleType('common')
        common.CONDITIONS = core.PHASES
        common.body, common.encoded, common.need, common.pin = core.body, core.encode, core.need, core.pin
        common.publish = lambda filename, value: write(Path(filename), core.encode(value))
        owned = ModuleType('_generated_reference_owned_episode_control')
        owned.__file__ = str(root / 'derived-owned-episode.py')
        # This executes the exact occurrence-checked derived owner source, not a rewrite.
        with mock.patch.dict(sys.modules, {'common': common}):
            exec(compile(self.derived['owned_episode.py'], owned.__file__, 'exec'), owned.__dict__)
        try:
            result = owned.execute(invocation, invocation_pin, SOURCE_PIN, journal, facade)
            return result, events, Path(invocation['output'])
        except RuntimeError:
            return None, events, Path(invocation['output'])

    def test_both_preparations_and_serial_reference_closures_before_pair_completion(self):
        result, events, root = self.execute_generated_owner()
        expected = [
            ('prepared', 'reference_causal', 'B'),
            ('prepared', 'reference_noncausal', 'B'),
            ('execute', 'reference_causal', 'B'),
            ('closed', 'reference_causal'), ('freeze', 'reference_causal'),
            ('execute', 'reference_noncausal', 'B'),
            ('closed', 'reference_noncausal'), ('freeze', 'reference_noncausal'),
            ('pair-closed',)]
        self.assertEqual([event for event in events if event[0] != 'inspect-generated-materials'], expected)
        self.assertEqual(set(result['conditions']), {'reference_causal', 'reference_noncausal'})
        self.assertIs(result['private_target_accessed'], False)
        self.assertIs(result['AI_attribution_verified'], False)
        self.assertIsNone(result['scientific_success'])
        self.assertEqual(result['outcome'], 'author_reference')
        episode.validate_reference_pair(result)
        self.assertTrue((root / 'PAIR_CLOSED.json').exists())

    def test_second_author_failure_preserves_first_closure_and_blocks_pair_completion(self):
        result, events, root = self.execute_generated_owner('reference_noncausal')
        self.assertIsNone(result)
        self.assertIn(('closed', 'reference_causal'), events)
        self.assertIn(('freeze', 'reference_causal'), events)
        self.assertNotIn(('closed', 'reference_noncausal'), events)
        self.assertNotIn(('pair-closed',), events)
        self.assertFalse((root / 'PAIR_CLOSED.json').exists())
        failure = json.loads((root / 'FAILED.json').read_bytes())
        self.assertEqual(failure['conditions_closed'], ['reference_causal'])
        self.assertIs(failure['private_target_accessed'], False)
        self.assertIs(failure['automatic_retry'], False)

    def test_owner_derivation_refuses_changed_original_source(self):
        altered = dict(self.originals)
        altered['owned_episode.py'] += b'# GENERATED SOURCE DRIFT\n'
        with self.assertRaises(ValueError):
            overlay.derive_owner_sources(altered, self.owner_manifest, self.legacy_raw)


class ReferenceCPUControls(unittest.TestCase):
    """Real metadata/owner/worker/helper paths; scientific and OS calls are doubles."""
    setUp = GeneratedReferenceControls.setUp
    tearDown = GeneratedReferenceControls.tearDown
    fixture = GeneratedReferenceControls.fixture
    worker_inputs = GeneratedReferenceControls.worker_inputs

    def protocol_fixture(self, cpu_seconds=36000):
        fixture = self.fixture()
        facade = episode.ReferenceEpisode.__new__(episode.ReferenceEpisode)
        facade.HERE = fixture.root / 'component'
        facade.HERE.mkdir()
        write(facade.HERE / 'reference_adapter.py', b'# GENERATED FROZEN PROGRAM\n')
        write(facade.HERE / 'BINDINGS.json', core.encode({'generated': 'bindings'}))
        materials = fixture.root / 'pair'
        materials.mkdir()
        pair = materials / 'pair.json'
        task = materials / 'task.json'
        write(pair, core.encode({'generated': 'pair'}))
        write(task, core.encode({'generated': 'task'}))
        facade.bindings = {'sources': {'pair': {'sha256': 'a' * 64}}}
        facade.TASK_SHA = 'b' * 64
        facade._protocol = facade._protocol_path = None
        facade._captured_actual = {}
        facade.PROFILES = {}
        facade.public_context = mock.Mock(return_value=({}, {}))
        facade.source_identity = lambda: SOURCE_PIN
        deployment = {'binding_pin': core.pin(b'GENERATED DEPLOYMENT'), 'pid_limit': 32}
        facade.deployment_binding = lambda: deepcopy(deployment)
        facade.need = core.need
        facade.runtime_config = lambda value: {**value, 'deployment': deepcopy(deployment)}
        runtime = {'source_read_bytes': 1048576, 'host_write_bytes': 1048576}
        runtime_file = fixture.root / 'runtime.json'
        runtime_pin = write(runtime_file, core.encode(runtime))
        output = fixture.root / 'protocol'
        protocol = facade.instantiate(pair, task, runtime_file, runtime_pin['sha256'],
                                      output, cpu_seconds=cpu_seconds)
        protocol_file = output / 'PROTOCOL.json'
        return fixture, facade, protocol, protocol_file

    def test_explicit_cpu_profile_has_no_default_and_rejects_invalid_fixed_fields(self):
        with self.assertRaises(TypeError):
            core.reference_profile()
        for cpu in (1, 36000, 64800):
            self.assertEqual(core.validate_profile(core.reference_profile(cpu)),
                             {'cpu_seconds': cpu, 'wall_seconds': 10800,
                              'memory_bytes': 8589934592, 'threads': 6})
        for value in (None, True, False, 0, -1, 64801, 36000.0, '36000'):
            with self.subTest(cpu=value), self.assertRaises(ValueError):
                core.reference_profile(value)
        for key, value in [('cpu_seconds', True), ('cpu_seconds', 64801),
                           ('wall_seconds', 86400), ('wall_seconds', 10800.0),
                           ('memory_bytes', 17179869184), ('threads', 8), ('threads', 6.0)]:
            bad = core.reference_profile(36000)
            bad[key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                core.validate_profile(bad)
        for bad in ({}, {'cpu_seconds': 36000}, {**TEST_PROFILE, 'extra': 1}, None):
            with self.assertRaises(ValueError):
                core.validate_profile(bad)

    def test_freeze_protocol_jobs_and_real_owner_resources_share_selected_cpu(self):
        for cpu in (1, 36000, 64800):
            with self.subTest(cpu=cpu):
                fixture, facade, protocol, protocol_file = self.protocol_fixture(cpu)
                expected = core.reference_profile(cpu)
                self.assertEqual(protocol['schema'], 'smc_author_reference_protocol_v2')
                self.assertEqual(protocol['resource_profile'], expected)
                self.assertEqual(facade.PROFILES, {})
                admitted, runtime = facade.admit_protocol(protocol_file,
                    core.pin(protocol_file.read_bytes())['sha256'])
                self.assertEqual(facade.PROFILES, {'author_reference': expected})
                resources = facade.resources('author_reference', runtime)
                self.assertEqual(resources['cpu_seconds'], cpu)
                self.assertEqual(resources['producer_seconds'], 10800)
                self.assertEqual(resources['memory_bytes'], 8589934592)
                self.assertEqual(resources['cpu_nanos'], 6000000000)
                for phase in core.PHASES:
                    declaration = core.read(protocol_file.parent / phase / 'declaration.json')
                    freeze = core.read(protocol_file.parent / phase / 'METHOD.json')
                    self.assertEqual(declaration['resource_profile'], expected)
                    self.assertEqual(freeze['plan'], declaration)
                    self.assertEqual(freeze['schema'], 'smc_author_reference_method_freeze_v2')
                    job = facade.job_for(admitted, phase)
                    self.assertEqual(job['resource_profile'], expected)
                    self.assertEqual(core.validate_job(declaration, job,
                        protocol['programs'][phase]['program'], job['bindings']), core.recipe(phase))

    def test_profile_tamper_or_legacy_protocol_clears_prior_admission(self):
        fixture, facade, protocol, protocol_file = self.protocol_fixture()
        facade.admit_protocol(protocol_file, core.pin(protocol_file.read_bytes())['sha256'])
        self.assertTrue(facade.PROFILES)
        with self.assertRaises(ValueError):
            facade.admit_protocol(Path('relative-protocol.json'), '0' * 64)
        self.assertEqual(facade.PROFILES, {})
        self.assertIsNone(facade._protocol)
        self.assertIsNone(facade._protocol_path)
        facade.admit_protocol(protocol_file, core.pin(protocol_file.read_bytes())['sha256'])
        # A changed protocol CPU cannot rewrite already-frozen method declarations.
        protocol['resource_profile']['cpu_seconds'] = 36001
        protocol_file.chmod(0o600)  # generated adversarial mutation only
        write(protocol_file, core.encode(protocol))
        with self.assertRaises(ValueError):
            facade.admit_protocol(protocol_file, core.pin(protocol_file.read_bytes())['sha256'])
        self.assertEqual(facade.PROFILES, {})
        self.assertIsNone(facade._protocol)
        protocol['resource_profile']['cpu_seconds'] = 36000
        protocol['schema'] = 'smc_author_reference_protocol_v1'
        write(protocol_file, core.encode(protocol))
        with self.assertRaises(ValueError):
            facade.admit_protocol(protocol_file, core.pin(protocol_file.read_bytes())['sha256'])
        self.assertEqual(facade.PROFILES, {})
        # Required API argument refuses omission before creating any protocol leaf.
        with self.assertRaises(TypeError):
            facade.instantiate(None, None, None, None, self.root / 'not-created')
        self.assertFalse((self.root / 'not-created').exists())

    def test_plan_job_mismatch_and_boolean_wire_cpu_refuse_before_release(self):
        fixture = self.fixture()
        fixture.job['resource_profile']['cpu_seconds'] = 36001
        fixture.save()
        with mock.patch.object(adapter, 'invoke_author') as invoke:
            with self.assertRaises(ValueError):
                fixture.run()
            invoke.assert_not_called()
        fixture.job['resource_profile']['cpu_seconds'] = 36000
        fixture.job['schema'] = 'smc_author_reference_execution_job_v1'
        fixture.save()
        with self.assertRaises(ValueError):
            fixture.run()
        for value in (True, 1.0, 36001):
            job, request, old = self.worker_inputs()
            if value is True or type(value) is float:
                job['resource_profile']['cpu_seconds'] = 1
            request['resources']['cpu_seconds'] = value
            with self.subTest(wire_cpu=value), self.assertRaises(ValueError):
                worker.authenticated(old)
            old.before_deadline.assert_not_called()


    def test_captured_result_requires_strict_integer_cpu_profile(self):
        fixture, facade, protocol, protocol_file = self.protocol_fixture(1)
        facade.admit_protocol(protocol_file, core.pin(protocol_file.read_bytes())['sha256'])
        phase = core.PHASES[0]
        programme = protocol['programs'][phase]
        root = self.root / 'generated-capture'
        root.mkdir()
        profile = core.reference_profile(1)
        result = {'schema': 'smc_author_reference_program_result_v2', 'route': core.ROUTE,
                  'phase_id': phase, 'access_condition': core.ACCESS, 'outcome': core.OUTCOME,
                  'resource_profile': profile,
                  'program_sha256': programme['program']['sha256'],
                  'declaration_sha256': programme['declaration']['sha256'],
                  'method_freeze_sha256': programme['method']['sha256'],
                  'submission_keys': ['offline']}
        actual = {'schema': 'smc_author_reference_actual_v2', 'route': core.ROUTE,
                  'phase_id': phase, 'access_condition': core.ACCESS,
                  'resource_profile': profile, 'recipe': core.recipe(phase),
                  'role': 'author_calibration', 'AI_attempt': False,
                  'scientific_improvement': False,
                  'method_freeze_sha256': programme['method']['sha256'],
                  'program_sha256': programme['program']['sha256']}
        files = {'offline.h5': write(root / 'offline.h5', FAKE_OUTPUT),
                 'actual_declaration.json': write(root / 'actual_declaration.json', core.encode(actual)),
                 'RESULT.json': write(root / 'RESULT.json', core.encode(result)),
                 'OUTPUTS.json': core.pin(b'GENERATED OUTER-ADMITTED MANIFEST')}
        receipt = {'output_inventory': {'complete': True, 'files': files},
                   'quarantine_root': str(root)}
        self.assertEqual(facade.captured_predictions(receipt, phase, core.OUTCOME, programme),
                         {'offline': root / 'offline.h5'})
        for invalid in (True, 1.0):
            result['resource_profile']['cpu_seconds'] = invalid
            files['RESULT.json'] = write(root / 'RESULT.json', core.encode(result))
            with self.subTest(cpu=invalid), self.assertRaises(ValueError):
                facade.captured_predictions(receipt, phase, core.OUTCOME, programme)

    def test_runtime_qualification_rejects_equal_boolean_or_float_cpu(self):
        fixture, facade, protocol, protocol_file = self.protocol_fixture(1)
        facade.admit_protocol(protocol_file, core.pin(protocol_file.read_bytes())['sha256'])
        record = {'profiles': {'author_reference': core.reference_profile(1)}}
        # Retained native identity checks are explicit doubles; strict profile
        # admission after that boundary is the real new reference method.
        with mock.patch.object(episode._base.FullPanelEpisode, 'qualify', return_value=record):
            self.assertEqual(facade.qualify({}, SOURCE_PIN), record)
            for invalid in (True, 1.0):
                record['profiles']['author_reference']['cpu_seconds'] = invalid
                with self.subTest(cpu=invalid), self.assertRaises(ValueError):
                    facade.qualify({}, SOURCE_PIN)

    def test_selected_cpu_reaches_real_worker_limit_and_original_helper_argument(self):
        job, request, old = self.worker_inputs()
        old.READY, old.RELEASE = self.root / 'READY', self.root / 'RELEASE'
        old.marker = lambda *args: {'generated': True}
        old.publish_marker = mock.Mock(side_effect=RuntimeError('CONTROL STOP BEFORE RELEASE'))
        with mock.patch.object(worker, 'retained', return_value=old), \
             mock.patch.object(worker.resource, 'setrlimit') as limits, \
             mock.patch.object(worker.sys, 'argv', ['reference_worker.py']), \
             mock.patch.dict(os.environ, {}, clear=False):
            with self.assertRaisesRegex(RuntimeError, 'CONTROL STOP BEFORE RELEASE'):
                worker.main()
        self.assertIn(mock.call(worker.resource.RLIMIT_CPU, (36000, 36000)), limits.call_args_list)
        fixture = self.fixture()
        captured = []
        def fake_run(filename, run_name):
            captured.append(list(adapter.sys.argv))
            write(fixture.output / 'offline.h5', FAKE_OUTPUT)
        with mock.patch.object(adapter.runpy, 'run_path', side_effect=fake_run), \
             mock.patch.object(adapter, 'read', return_value=original_report(core.recipe(fixture.phase))):
            actual = fixture.run()
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][-2:], ['--cpu-seconds-remaining', '36000'])
        self.assertEqual(actual['resource_profile'], TEST_PROFILE)
        self.assertEqual(actual['schema'], 'smc_author_reference_actual_v2')


def main():
    global FIXTURE_PARENT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-parent', type=Path, required=True)
    args, unittest_args = parser.parse_known_args()
    selected = args.fixture_parent
    if not selected.is_absolute() or '..' in selected.parts:
        raise ValueError('Absolute ordinary selected fixture parent required')
    selected = core.path(selected)
    repository = AUTHOR.parents[5]
    if selected != selected.resolve() or not selected.parent.is_dir() or selected.exists():
        raise ValueError('Fresh canonical fixture leaf under an existing ordinary parent required')
    if selected.is_relative_to(repository) or repository.is_relative_to(selected):
        raise ValueError('Fixture output must be disjoint from the repository source tree')
    selected.mkdir(mode=0o700)
    FIXTURE_PARENT = selected
    os.environ['TMPDIR'] = str(selected)
    tempfile.tempdir = None
    # Accounting hooks preserve the real bounded writer and cover production
    # declaration/grade metadata writes; scientific execution remains separately stubbed.
    adapter.write_new = accounted_write_new
    episode.write_new = accounted_write_new
    result = unittest.main(argv=[sys.argv[0], *unittest_args], exit=False).result
    receipt = {
        'schema': 'smc_generated_reference_fixture_cost_v1',
        'fixture_parent': str(selected), 'cumulative_byte_cap': FIXTURE_CAP,
        'cumulative_precharged_bytes_including_deleted_and_failed': 0,
        'precharged_write_reservations_including_this_receipt': FIXTURE_RESERVATIONS + 1,
        'snapshot_copy_reservations_are_conservative': True,
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'scientific_payloads_read': False,
        'model_or_native_execution': False,
        'scientific_boundary': 'generated invoke_author/scorer/provider stubs only',
    }
    for _ in range(12):
        raw = core.encode(receipt)
        total = FIXTURE_WRITTEN + len(raw)
        if receipt['cumulative_precharged_bytes_including_deleted_and_failed'] == total:
            break
        receipt['cumulative_precharged_bytes_including_deleted_and_failed'] = total
    else:
        raise ValueError('Fixture cost receipt byte fixed point failed')
    write(selected / 'COST.json', raw)
    print(json.dumps({'fixture_cost_receipt': str(selected / 'COST.json'),
                      'cumulative_fixture_byte_charge': FIXTURE_WRITTEN,
                      'fixture_byte_cap': FIXTURE_CAP}, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())

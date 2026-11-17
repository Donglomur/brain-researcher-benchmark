"""Generated full140 controller controls with a scripted native boundary only.

Production controller.run, preparation, view retirement and observe.admit are
executed unchanged. Native processes/containers are never launched. All source
and export pin substitutions exist only in invented test objects/files.
"""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import platform
import signal
import tempfile
import time
import types

HERE = Path(__file__).absolute().parent
REPOSITORY = HERE.parents[4]


def local(name):
    module = types.ModuleType('_generated038_' + name)
    module.__file__ = str(HERE / (name + '.py'))
    exec(compile((HERE / (name + '.py')).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


def run_controls(fixtures=None, *, _base=None, _build_only=False):
    fixtures = local('generated_fixtures') if fixtures is None else fixtures
    start_writes = fixtures.snapshot()
    library = local('library')
    common, manifest, bodies, original_source = library.runtime(time.monotonic() + 30)
    _, transport, modules = library.evaluator(REPOSITORY, common)
    policy = common.module(bodies, 'policy.py', HERE / 'runtime', c=common)
    observer = common.module(bodies, 'observe.py', HERE / 'runtime')
    original_save = common.save

    def tracked_save(path, raw, cap, tick=lambda: None, charge=lambda n: None):
        return fixtures.publication(raw, lambda: original_save(path, raw, cap, tick, charge))

    common.save = tracked_save
    results = []
    calls = []
    attempt_details = {}

    def mark(name):
        results.append({'control': name, 'passed': True})

    def refuse(function):
        try:
            function()
        except (ValueError, AssertionError):
            return
        raise AssertionError('Expected generated refusal')

    def rewrite(path, raw):
        path.chmod(0o600)
        fixtures.write(path, raw)
        path.chmod(0o400)

    try:
        managed = (tempfile.TemporaryDirectory(prefix='neural038-invented-full140-') if _base is None
                   else nullcontext(str(Path(_base).resolve())))
        with managed as directory:
            base = Path(directory).resolve()
            repository = base / 'operator'; repository.mkdir()
            package = repository / 'package'; package.mkdir()
            public = package / 'public'; public.mkdir()
            panel, inputs, correct_report = fixtures.fixture(public, modules)
            # Match the complete original transport extent, not its real bytes.
            # Padding applies only to invented documents/JSON whitespace.
            metadata = {
                'TASK.md': (b'GENERATED FULL140 SOFTWARE CONTROL; NO AUTHENTIC OBSERVATIONS\n', 8043),
                'CANDIDATE.md': (b'GENERATED FROZEN PROGRAM INTERFACE\n', 2537),
                'DEPENDENCIES.md': (b'GENERATED NUMPY FIXTURE\n', 1598),
                'submission.schema.json': (b'{"generated_fixture_only":true}\n', 6839),
                'requirements.txt': (b'numpy==2.2.6\n', 13),
                'input.json': (transport.canonical(inputs), 6506),
                'panel.json': (transport.canonical(panel), 8367),
            }
            for name, (raw, size) in metadata.items():
                if len(raw) > size:
                    raise AssertionError('Generated complete JSON exceeds original transport extent: ' + name)
                fixtures.write(public / name, raw + b' ' * (size - len(raw)))
            names = list(metadata) + [record['path'] for block in inputs['blocks']
                                      for record in block['arrays'].values()]
            rows = [{'target': 'public/' + name, **common.pin((public / name).read_bytes()),
                     'role': 'generated_complete_public', 'visibility': 'public'} for name in names]
            assert len(rows) == 25 and sum(row['bytes'] for row in rows) == 938607
            assert len([r for r in rows if r['target'].endswith('.npy')]) == 18
            # Private descriptors are invented and deliberately have no files.
            for index in range(40):
                name = 'reference.json' if index == 0 else 'unopened_%02d.txt' % index
                rows.append({'target': 'private/' + name, **common.pin(b'UNOPENED GENERATED PLACEHOLDER'),
                             'role': 'generated_private_metadata_only', 'visibility': 'private'})
            source_raw = common.encoded({'task_ids': ['NEURAL-038'], 'files': rows})
            fixtures.write(repository / 'source.json', source_raw)
            source_descriptor = {'path': 'source.json', **common.pin(source_raw)}
            export_raw = common.encoded({'task_ids': ['NEURAL-038'], 'source_manifest': source_descriptor, 'files': rows})
            fixtures.write(package / 'DELIVERY_MANIFEST.json', export_raw)
            binding = copy.deepcopy(common.parse(bodies['BINDINGS.json']))
            binding.update(files=rows, package='package', source_descriptor=source_descriptor,
                           export_descriptor={'path': 'package/DELIVERY_MANIFEST.json', **common.pin(export_raw)})
            generated_bodies = dict(bodies)
            generated_bodies['BINDINGS.json'] = common.encoded(binding)
            generated_manifest = copy.deepcopy(manifest)
            generated_manifest['files']['BINDINGS.json'] = common.pin(generated_bodies['BINDINGS.json'])
            source = common.pin(common.encoded(generated_manifest))
            assert source != original_source
            assert binding['scope'] == policy.SCOPE
            fixture_public = {r['target']: common.only_pin(r) for r in rows if r['visibility'] == 'public'}

            def attempt(name, change=None):
                output = base / ('attempt-' + name)
                program = base / (name + '.py')
                program_raw = b'# GENERATED PROGRAM; SCRIPTED NATIVE BOUNDARY DOES NOT EXECUTE THIS\n'
                fixtures.write(program, program_raw)
                program_pin = common.pin(program_raw)
                method = {'schema': 'neural038_full140_method_review_v1', 'task_id': 'NEURAL-038',
                          'approved': True, 'source': source, 'program': program_pin,
                          'scope': policy.SCOPE, 'other_future_bytes': 0, 'generated_control_only': True}
                method.update({key: True for key in (
                    'all140_memberships_and_four_blocks', 'one_program_before_public_input_access',
                    'full_public_covariates_intentionally_visible', 'fixed_native_frames_and_separate_revision',
                    'all_null_and_support_dispositions_preserved', 'complete_report_before_feedback', 'no_private_answer_exposure')})
                method.update({key: False for key in (
                    'numeric_agreement_proves_neural_understanding', 'heldout_generalization_or_paper_parity',
                    'hashes_alone_prove_chronology')})
                runtime = {'schema': 'neural038_runtime_profile_review_v1', 'task_id': 'NEURAL-038',
                           'approved': True, 'source': source, 'program': program_pin,
                           'scope': policy.SCOPE, 'other_future_bytes': 0, 'generated_control_only': True,
                           'image': 'sha256:' + 'b' * 64, 'candidate_seconds': 600, 'memory_bytes': 1073741824,
                           'docker_binary': '/INVENTED_NOT_EXECUTED_DOCKER', 'docker_socket': '/INVENTED_NOT_OPENED_SOCKET',
                           'runtime_versions': {'python': '3.12', 'numpy': '2.2.6'},
                           'native_full_panel_qualification_required_before_campaign': True, 'qualification_inherited': False,
                           'independent_cli_groups_and_native_failure_recovery_acknowledged': True}
                reviews = {}
                for kind, value in [('method_review', method), ('runtime_review', runtime)]:
                    path = base / (name + '-' + kind + '.json'); raw = common.encoded(value)
                    fixtures.write(path, raw); reviews[kind] = {'path': str(path), **common.pin(raw)}
                selection = {'schema': 'neural038_full140_program_selection_v1', 'execution_selected': True,
                             'task_id': 'NEURAL-038', 'repository': str(repository), 'output': str(output),
                             'program': {'path': str(program), **program_pin}, 'source': source,
                             'docker_binary': runtime['docker_binary'], 'docker_socket': runtime['docker_socket'],
                             'image': runtime['image'], 'candidate_seconds': 600, 'memory_bytes': 1073741824,
                             'other_future_bytes': 0, 'scope': policy.SCOPE, 'retained_bytes': 96000000,
                             'managed_reads': 240000000, 'managed_writes': 64016384, 'whole_seconds': 1800,
                             'support_admission_authorized': True, 'numeric_grading_authorized': False, **reviews}
                policy.selection(selection, source)
                attempt_details[name] = {'selection': selection}

                def scripted_phase(selected, here, mount_input, program_or_report, phase_dir, role,
                                   phase_source, budget, deadline, export_sha):
                    assert selected == selection and phase_source == source
                    assert (output / 'commitment/COMMITMENT.json').is_file()
                    assert export_sha == binding['export_descriptor']['sha256']
                    common.before(deadline)
                    calls.append((name, role))
                    if role == 'candidate':
                        present, _, _ = common.inventory(mount_input, 2000000, 70)
                        assert set(present) == {Path(r).relative_to('public').as_posix() for r in fixture_public}
                        for relative, expected in fixture_public.items():
                            common.capture(mount_input / Path(relative).relative_to('public'), 2000000, expected)
                        result_report = copy.deepcopy(correct_report)
                        if change == 'wrong_number':
                            result_report['blocks'][0]['cells'][0]['context_interaction'] += 1
                        if change == 'missing_membership':
                            result_report['blocks'][0]['cells'].pop()
                        raw = common.encoded(result_report)
                        if change == 'view_mutation':
                            path = mount_input / inputs['blocks'][0]['arrays']['visF1']['path']
                            rewrite(path, path.read_bytes() + b'GENERATED CHANGE')
                    else:
                        assert role == 'admission' and not (output / 'current').exists()
                        report = transport.decode(common.capture(program_or_report, 16000000))
                        # Exact original structural validator; never numerical score/recompute.
                        modules['scorer_core'].admit(panel, report)
                        raw = common.encoded({'task_id': 'NEURAL-038',
                              'status': 'public_structure_consistent_artifact_only', 'memberships': 140,
                              'blocks': 4, 'declared_numeric_operands': 866, 'private_reference_calls': 0,
                              'numeric_comparison_performed': False, 'scientific_qualification_added': False,
                              'operator_entrypoint': 'neural038_exact_scorer_core_admit_v1',
                              'export_manifest_sha256': export_sha, 'requires_observed_cli_exit_zero': True})
                    output_pin = common.save(phase_dir / 'report.json', raw,
                                             16000000 if role == 'candidate' else 65536, budget.tick, budget.write)
                    prefix = 'invented-' + name + '-' + role
                    record = {'schema': 'neural038_owned_phase_v1', 'phase': role, 'source': source,
                              'status': 'captured', 'attempt_prefix': prefix, 'output': output_pin,
                              'closures': [{'kind': kind, 'name': prefix + '-' + label, 'closed': True}
                                           for kind, label in [('container', 'producer'), ('container', 'holder'), ('volume', 'volume')]],
                              'all_native_resources_closed': True, 'cli_reaped': True,
                              'natural_exit': {'Status': 'exited', 'Running': False, 'Dead': False,
                                               'Pid': 0, 'ExitCode': 0, 'OOMKilled': False},
                              'producer_closed_before_capture': True, 'error_type': None,
                              'command_metadata': [{'phase': 'invented_complete_phase', 'returncode': 0,
                                  'error_type': None, 'observed_retained_bytes': len(raw), 'seconds': 0.001,
                                  'client_reaped': True, 'cleanup_complete': True,
                                  'cleanup_before_original_cutoff': True, 'owned_group_absence_observed': True,
                                  'leader_exited_with_group_alive': False, 'group_probe_or_cleanup_error': None}],
                              'numerical_grading_called': False, 'recovery_may_be_required': False,
                              'elapsed_seconds': 0.001}
                    common.save(phase_dir / 'NATIVE.json', common.encoded(record), 262144, budget.tick, budget.write)
                    return record

                controller = common.module(generated_bodies, 'controller.py', HERE / 'runtime',
                                           c=common, policy=policy, native=types.SimpleNamespace(phase=scripted_phase))
                if signal.getitimer(signal.ITIMER_REAL) != (0., 0.):
                    raise ValueError('Generated original-controller call requires no inherited timer')
                old = signal.getsignal(signal.SIGALRM)
                signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Generated controller deadline')))
                origin = time.monotonic()
                try:
                    if change in ('view_mutation', 'missing_membership'):
                        refuse(lambda: controller.run(selection, source, generated_bodies, generated_manifest, origin, origin + 1780))
                        assert (output / 'FAILURE.json').is_file() and not (output / 'COMPLETE.json').exists()
                        return output, None
                    terminal = controller.run(selection, source, generated_bodies, generated_manifest, origin, origin + 1780)
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, old)
                before_reads = []
                report_pin, complete_pin = observer.admit(common, output, terminal, source, binding,
                                                          time.monotonic() + 30, before_reads.append)
                assert report_pin == common.pin((output / 'candidate/report.json').read_bytes())
                assert complete_pin == terminal['complete'] and not (output / 'current').exists()
                complete = common.parse((output / 'COMPLETE.json').read_bytes())
                assert complete['numerical_grading_performed'] is False
                assert complete['costs']['native_cases_reserved'] == ['candidate', 'admission']
                assert not (package / 'private').exists()
                attempt_details[name].update(report_pin=report_pin, complete_pin=complete_pin,
                                             observer_admit_read_charges=before_reads,
                                             origin=origin, worker_end=origin + 1780)
                return output, terminal

            successful, terminal = attempt('complete')
            assert calls == [('complete', 'candidate'), ('complete', 'admission')]
            mark('Original controller prepares and retires all 25 files, preserves full 140-membership support and original observer admits closed scripted phases')
            if _build_only:
                return {'common': common, 'manifest': generated_manifest, 'bodies': generated_bodies,
                        'source': source, 'original_source': original_source, 'binding': binding,
                        'selection': attempt_details['complete']['selection'], 'root': successful,
                        'terminal': terminal, 'operator_repository': repository, 'package': package,
                        'public_root': public, 'panel': panel, 'inputs': inputs, 'report': correct_report,
                        'modules': modules, 'transport': transport, 'observer': observer,
                        'observer_admission': attempt_details['complete'], 'scripted_native_calls': list(calls),
                        'writes_before': start_writes, 'writes_after': fixtures.snapshot(),
                        'caller_owns_fixture_cleanup': True, 'native_execution': False}
            original_native = (successful / 'candidate/NATIVE.json').read_bytes()
            original_complete = (successful / 'COMPLETE.json').read_bytes()
            for change in ('producer_not_closed', 'numeric_false_cli_flag'):
                record = common.parse(original_native)
                if change == 'producer_not_closed': record['producer_closed_before_capture'] = False
                else: record['command_metadata'][0]['cleanup_complete'] = 1
                raw = common.encoded(record); rewrite(successful / 'candidate/NATIVE.json', raw)
                completed = common.parse(original_complete); completed['candidate_native'] = common.pin(raw)
                raw = common.encoded(completed); rewrite(successful / 'COMPLETE.json', raw)
                changed_terminal = {**terminal, 'complete': common.pin(raw)}
                refuse(lambda: observer.admit(common, successful, changed_terminal, source, binding,
                                              time.monotonic() + 30, lambda n: None))
                rewrite(successful / 'candidate/NATIVE.json', original_native)
                rewrite(successful / 'COMPLETE.json', original_complete)
                mark('Original observer refuses ' + change + ' despite re-bound invented receipt hashes')
            report_path = successful / 'candidate/report.json'; original_report = report_path.read_bytes()
            altered = common.parse(original_report); altered['blocks'][0]['cells'][0]['context_interaction'] += 1
            rewrite(report_path, common.encoded(altered))
            refuse(lambda: observer.admit(common, successful, terminal, source, binding,
                                          time.monotonic() + 30, lambda n: None))
            rewrite(report_path, original_report)
            mark('Original observer refuses valid report replacement after closed capture')
            attempt('view-changed', 'view_mutation')
            assert ('view-changed', 'admission') not in calls
            mark('Prepared generated array mutation fails original retirement and prevents structural admission')
            attempt('row-missing', 'missing_membership')
            mark('Exact original structural admission refuses an incomplete 140-membership report; no COMPLETE is published')
            wrong_root, _ = attempt('wrong-number', 'wrong_number')
            wrong = transport.decode((wrong_root / 'candidate/report.json').read_bytes())
            assert wrong['blocks'][0]['cells'][0]['context_interaction'] != correct_report['blocks'][0]['cells'][0]['context_interaction']
            mark('Well-shaped wrong numeric report remains structural-only and does not fabricate numerical correctness')
    finally:
        common.save = original_save
    after_writes = fixtures.snapshot()
    return {'schema': 'neural038_generated_full140_producer_controls_v1', 'passed': True,
            'groups': len(results), 'results': results, 'native_boundary': 'scripted native.phase, no process/container execution',
            'production_functions_exercised': ['controller.run', 'controller.prepare', 'controller.retire', 'observe.admit', 'scorer_core.admit'],
            'scope': {'public_files': 25, 'public_bytes': 938607, 'array_files': 18,
                      'memberships': 140, 'blocks': [9, 13, 10, 108], 'frames': [300, 300, 300, 200]},
            'writes_before': start_writes, 'writes_after': after_writes,
            'writes_this_call': {key: after_writes[key] - start_writes[key] for key in after_writes},
            'write_accounting': 'Requested and completed logical payload writes only; failed charges retained; metadata, allocation and physical kernel I/O not measured.',
            'temporary_fixtures_removed': True, 'native_execution': False, 'authentic_payload_reads': 0,
            'model_calls': 0, 'runtime_qualified': False, 'scientific_qualified': False}


def build_attempt(base, fixtures=None):
    """Build one successful generated original-controller attempt for bridge tests.

    `base` must be an existing empty caller-owned directory; this function does
    not remove it. Pass the same fixture module used by other tests to retain
    cumulative write accounting. Returned closure claims are explicitly scripted
    test data, never authentic native/process observations.
    """
    base = Path(base).resolve()
    if not base.is_dir() or any(base.iterdir()):
        raise ValueError('Existing empty caller-owned generated fixture directory')
    return run_controls(fixtures, _base=base, _build_only=True)


if __name__ == '__main__':
    fixtures = local('generated_fixtures')
    print(json.dumps({'python': platform.python_version(), 'numpy': fixtures.np.__version__}))
    try:
        print(json.dumps(run_controls(fixtures), indent=2))
    finally:
        print(json.dumps({'generated_write_counter_final': fixtures.snapshot()}))

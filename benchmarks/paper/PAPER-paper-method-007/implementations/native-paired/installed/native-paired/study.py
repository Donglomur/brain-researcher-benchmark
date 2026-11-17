"""Complete native + five-mouse A/B UnitMatch entry; execution is a future gate.

There is no --baseline path and no provider callback. The operational route owns
the MATLAB launch, both frozen-program fold runners and target-last comparison.
"""
import argparse
import copy
import os
from pathlib import Path
import signal
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from support import (Budget, MICE, SIZES, OFFICIAL_COMMIT, capture, encoded, full_cohort,
                     executable, identity, module, need, ordinary, parse, process, relative, save)
import functional

PACKET = {'bytes': 1320185, 'sha256': '8f361ac6074f5306ba4cf0c07e6593ec4eaefe6d5a4e0851448a89fa73917a89'}
COHORT = {'bytes': 532569, 'sha256': '7ed4a18626ca53c13d97beb12182e2240dbd6e8131dd9bdceecd696985b904f1'}
RUNNER_MANIFEST = {'bytes': 5972, 'sha256': '63b6dbcf7ec94f44045cfa76b2f8132f05ab865c1e82d6dfeb2fa6c96f65c479'}
RUNNER = 'authoring/delivery-20261105/unitmatch-program-interface-deadline-v2'
SOURCE = 'authoring/delivery-20261105/unitmatch'


def source_closure(repository, expected, budget):
    raw = capture(HERE/'SOURCE_BINDING.json', 65536, budget=budget)
    need(identity(raw)['sha256'] == expected, 'Explicit accepted source binding')
    lock = parse(raw)
    own = {row['path']: capture(HERE/relative(row['path']), 1048576, row, budget) for row in lock['own']}
    deps = {row['path']: capture(repository/relative(row['path']), 1048576, row, budget) for row in lock['dependencies']}
    # Fixed original modules are compiled only from authenticated captured bodies.
    io = module('io_utils', deps[SOURCE+'/private/io_utils.py'], repository/SOURCE/'private/io_utils.py')
    interface = module('_unitmatch_original_interface', deps[SOURCE+'/private/interface.py'], repository/SOURCE/'private/interface.py')
    metrics = module('_unitmatch_original_metrics', deps[SOURCE+'/private/metrics.py'], repository/SOURCE/'private/metrics.py')
    bank = module('_unitmatch_independent_bank', own['reference-bank-v1/reference_bank.py'], HERE/'reference-bank-v1/reference_bank.py')
    native = module('_unitmatch_native_component', own['native-component-v1/native.py'], HERE/'native-component-v1/native.py')
    return lock, own, deps, io, interface, metrics, bank, native


def packet_cohort(package, budget):
    packet = parse(capture(package/'private/PACKET_MAP.json', PACKET['bytes'], PACKET, budget))
    cohort = full_cohort(parse(capture(package/'public/cohort.json', COHORT['bytes'], COHORT, budget)))
    rows = packet['files']
    need(len(rows) == 4000 and len({r['target'] for r in rows}) == 4000, 'Original complete packet census')
    need(sum(r['arm'] == 'B' for r in rows) == 140 and sum('validation_mouse' in r for r in rows) == 10,
         'Original code and ten protected functional descriptors')
    for r in rows:
        relative(r['source']); relative(r['target'])
        need(type(r['bytes']) is int and r['bytes'] > 0 and r['arm'] in ('both', 'B'), 'Exact ordinary packet row')
    protected = {s['source_prepared'] for m in cohort['mice'] for s in m['sessions']}
    need(len(protected) == 10 and {r['source'] for r in rows if 'validation_mouse' in r} == protected,
         'Exact ten functional sources; no inferred alias')
    return packet, cohort


def native_stage(package, out, packet, cohort, budget):
    """Full waveform/channel and official-code snapshot; no functional data copy."""
    need(not out.exists(), 'Fresh native stage')
    selected = [r for r in packet['files'] if 'validation_mouse' not in r and
                (r['source'].startswith('public/data/') or r['arm'] == 'B')]
    need(len({r['source'] for r in selected}) == len(selected), 'No source aliases in native stage')
    need(sum(r['source'].endswith('_RawSpikes.npy') for r in selected) == 3836
         and sum(r['source'].endswith('/channel_positions.npy') for r in selected) == 10,
         'All original 3836 waveforms and ten channel arrays')
    need(all(r['source'].startswith(('public/data/', 'private/author_source/'))
             and 'PreparedData' not in r['source'] for r in selected), 'Only native scientific/code inputs')
    need(sum(r['arm'] == 'B' for r in selected) == 140, 'Complete pinned official code access')
    sanitized = copy.deepcopy(cohort)
    for mouse in sanitized['mice']:
        for session in mouse['sessions']:
            del session['source_prepared']
            del session['prepared_sha256']
    out.mkdir()
    files = []
    for row in selected:
        body = capture(package/row['source'], row['bytes'], row, budget)
        pin = save(out/row['source'], body, budget)
        files.append({'path': row['source'], **pin})
    body = encoded(sanitized)
    pin = save(out/'public/cohort.json', body, budget)
    files.append({'path': 'public/cohort.json', **pin})
    descriptor = {'schema': 'unitmatch_native_stage_v1', 'official_commit': OFFICIAL_COMMIT,
                  'files': files, 'cohort_original': COHORT, 'cohort_sanitized': pin,
                  'packet_map': PACKET, 'functional_files_staged': 0,
                  'cohort_transform': 'Remove only source_prepared and prepared_sha256 from all ten sessions.'}
    for parent, dirs, names in os.walk(out, topdown=False):
        Path(parent).chmod(0o555)
    return descriptor


def freeze_methods(out, programs, methods, policies, budget):
    """Both arms commit before native or the first candidate fold, with no feedback."""
    need(set(programs) == set(methods) == set(policies) == {'A', 'B'}, 'Both complete method specifications')
    rows = {}
    for arm in ('A', 'B'):
        need(type(methods[arm]) is str and 1 <= len(methods[arm]) <= 160, 'Bounded method name')
        policy = policies[arm]
        need(type(policy) is dict and set(policy) == {'fitting', 'hyperparameter_selection', 'allowed_development_support', 'non_code_resources'},
             'Predeclared full fitting and selection policies')
        need(all(type(policy[k]) is str and policy[k].strip() and not policy[k].startswith('REPLACE:')
                 for k in policy), 'Explicit completed policy descriptions')
        body = capture(programs[arm], 65536, budget=budget)
        pin = save(out/('program_'+arm+'.py'), body, budget)
        rows[arm] = {'program': pin, 'method_name': methods[arm], 'policy': policy}
    need(policies['A']['non_code_resources'] == policies['B']['non_code_resources'], 'Equal declared non-code resources')
    # This is a committed declaration; code semantics and prior public exposure
    # are not authenticated by a statement of policy.
    seal = {'schema': 'unitmatch_paired_method_seal_v1', 'methods': rows, 'mice': list(MICE),
            'sealed_before_any_execution_or_target_read': True,
            'same_non_code_runtime_profile': RUNNER_MANIFEST, 'code_B_commit': OFFICIAL_COMMIT,
            'policy_declarations_are_not_independent_proof': True, 'public_data_exposure_remains': True}
    save(out/'PAIRED_METHOD_SEAL.json', encoded(seal), budget)
    return seal


def runner_snapshot(out, deps, budget):
    out.mkdir()
    prefix = RUNNER+'/'
    for path, body in deps.items():
        if path.startswith(prefix):
            save(out/path[len(prefix):], body, budget)
    manifest = parse(capture(out/'SOURCE_MANIFEST.json', RUNNER_MANIFEST['bytes'], RUNNER_MANIFEST, budget))
    need({r['path'] for r in manifest['files']} <= {p[len(prefix):] for p in deps if p.startswith(prefix)},
         'Complete original candidate runner closure')


def candidate_products(out, arm, method, program_pin, cohort, interface, budget):
    """Inspect actual internal five-fold chain, not just a success marker."""
    attempt_raw = capture(out/'ATTEMPT.json', 100000, budget=budget)
    attempt = parse(attempt_raw)
    completion = parse(capture(out/'COMPLETION.json', 32768, budget=budget))
    seal_raw = capture(out/'SEAL.json', 32768, budget=budget)
    seal = parse(seal_raw)
    need(completion['attempt'] == identity(attempt_raw) and completion['seal'] == identity(seal_raw), 'Captured completion operand pins')
    need(attempt['success'] is True and attempt['all_five_jobs_closed'] is True
         and attempt['folds_committed'] == 5 and attempt['all_transient_views_retired'] is True, 'All five actual candidate jobs closed')
    need(seal['program'] == program_pin and seal['access_view'] == arm and seal['method_name'] == method
         and seal['source_manifest_sha256'] == RUNNER_MANIFEST['sha256'] and seal['packet_pins'] ==
         {'private/PACKET_MAP.json': PACKET, 'public/cohort.json': COHORT}, 'Exact frozen arm source/input/program')
    need(completion['full_cohort'] == list(MICE), 'Complete original cohort completion')
    previous, commits, folds = None, [], []
    for mouse in MICE:
        job = out/mouse
        raw = capture(job/'unit/commit.json', 65536, budget=budget)
        commit = parse(raw)
        need(commit['candidate_id'] == 'PAPER-paper-method-007' and commit['unit_id'] == mouse
             and commit['program_sha256'] == program_pin['sha256'] and commit['previous_commit_sha256'] == previous
             and commit['producer_removed_before_capture'] is True
             and commit['all_candidate_holder_volume_absent'] is True, 'Complete internal producer and absence chain')
        absence = parse(capture(job/'ABSENCE.json', 65536, budget=budget))
        need(len(absence) == 3 and all(r['absence_verified'] is True for r in absence), 'All owned candidate resources absent')
        retired = parse(capture(job/'RETIRED.json', 65536, budget=budget))
        need(retired['owned_view_retired_after_job_absence'] is True and not (job/'view').exists(), 'No surviving candidate input stage')
        fold = parse(capture(job/'unit/fold.json', 16000000, commit['output'], budget))
        need(fold['program_sha256'] == program_pin['sha256'] and fold['access_view'] == arm and fold['method_name'] == method
             and fold['held_out_mouse'] == mouse and fold['development_mice'] == [m for m in MICE if m != mouse],
             'Every fold has the same sealed method and original development support')
        folds.append({k: fold[k] for k in ('held_out_mouse', 'development_mice', 'probabilities')})
        previous = identity(raw)['sha256']
        need(retired['commit_sha256'] == previous, 'Retirement binds the exact unit commit')
        commits.append(previous)
    need(commits == attempt['commit_chain'] == completion['trusted_job_commit_chain'], 'Exact five-commit chain')
    raw = capture(out/'submission.json', 100000000, attempt['submission'], budget)
    document = parse(raw)
    interface.validate(document, cohort, arm)
    need(document['folds'] == folds and document['method_name'] == method
         and completion['submission'] == identity(raw), 'Assembled submission equals every captured fold')
    return document, {'submission': identity(raw), 'completion': identity(capture(out/'COMPLETION.json', 32768, budget=budget)),
                      'commit_chain': commits}


def close_products(native, arms, cohort, interface):
    """No target capability is released for a partial native/A/B product census."""
    need(set(arms) == {'A', 'B'}, 'Both arms before target access')
    interface.validate(native['submission'], cohort, 'B')
    need(native['receipt']['natural_zero'] is True, 'Actual source-owned native natural-zero process')
    for arm in ('A', 'B'):
        interface.validate(arms[arm][0], cohort, arm)
    need(sum(len(f['probabilities'])**2 for f in native['submission']['folds']) == 526890,
         'All native directed pairs')
    return {'native': native['submission'], 'A': arms['A'][0], 'B': arms['B'][0]}


def execute(args):
    repository, package, out = ordinary(args.repository), ordinary(args.package), ordinary(args.output)
    need(not out.exists() and out.parent.is_dir() and not out.is_relative_to(package), 'Fresh owned study outside package')
    limits = parse(capture(args.limits, 65536))
    budget = Budget(limits)
    lock, own, deps, io, interface, metrics, bank, native_module = source_closure(repository, args.source_sha256, budget)
    packet, cohort = packet_cohort(package, budget)
    policies = parse(capture(args.policies, 65536, budget=budget))
    out.mkdir(mode=0o700)
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'No preexisting host alarm ownership')
    def cutoff(*unused):
        raise TimeoutError('Whole paired study deadline; retain failure products')
    previous_alarm = signal.signal(signal.SIGALRM, cutoff)
    signal.setitimer(signal.ITIMER_REAL, max(.001, budget.end-time.monotonic()))
    result = {'success': False, 'functional_targets_opened': False, 'completed_mouse_grades': 0,
              'runtime_qualified': False, 'scientific_qualification': False, 'count_promotion': False}
    try:
        seal = freeze_methods(out, {'A': args.program_a, 'B': args.program_b},
                              {'A': args.method_a, 'B': args.method_b}, policies, budget)
        save(out/'SOURCE_LOCK.json', encoded(lock), budget)
        save(out/'LIMITS.json', encoded(limits), budget)
        snapshot = out/'candidate_runner'
        runner_snapshot(snapshot, deps, budget)
        descriptor = native_stage(package, out/'native_input', packet, cohort, budget)
        save(out/'NATIVE_STAGE.json', encoded(descriptor), budget)
        # Reserve the COMPLETE child native envelope, independently of two arm
        # envelopes. Success does not imply the supplied limits are adequate.
        nl = limits['native']
        budget.charge(read=nl['max_total_read_bytes'], write=nl['max_total_write_bytes'],
                      retained=nl['max_total_write_bytes'])
        native = native_module.run_native(out/'native_input', out/'native', args.matlab,
                                          limits['matlab_executable'], descriptor, nl,
                                          expected_source_pin=identity(own['native-component-v1/native.py']))
        arms = {}
        for arm in ('A', 'B'):
            budget.charge(read=40000000000, write=13000000000, retained=3000000000)
            execution_binaries = {name: executable(path, limits[name+'_executable'], budget)
                                  for name, path in [('python', args.python), ('docker', args.docker)]}
            save(out/('EXECUTABLES_'+arm+'.json'), encoded(execution_binaries), budget)
            command = [str(ordinary(args.python)), '-I', '-B', str(snapshot/'run_program.py'), 'run',
                       '--package', str(package), '--source-sha256', RUNNER_MANIFEST['sha256'],
                       '--view', arm, '--program', str(out/('program_'+arm+'.py')),
                       '--method-name', seal['methods'][arm]['method_name'], '--output', str(out/('arm_'+arm)),
                       '--other-bytes', str(limits['other_bytes']+budget.retained),
                       '--docker', str(ordinary(args.docker)), '--docker-host', args.docker_host,
                       '--docker-config', str(ordinary(args.docker_config))]
            process(command, out, out/('process_'+arm), 1800, budget)
            for name, path in [('python', args.python), ('docker', args.docker)]:
                need(executable(path, limits[name+'_executable'], budget) == execution_binaries[name],
                     'Candidate runtime executable unchanged through actual process')
            arms[arm] = candidate_products(out/('arm_'+arm), arm, seal['methods'][arm]['method_name'],
                                          seal['methods'][arm]['program'], cohort, interface, budget)
        documents = close_products(native, arms, cohort, interface)
        for arm in ('A', 'B'):
            capture(out/('program_'+arm+'.py'), 65536, seal['methods'][arm]['program'], budget)
        barrier = {'schema': 'unitmatch_target_last_barrier_v1', 'native': native['receipt'],
                   'A': arms['A'][1], 'B': arms['B'][1], 'candidate_outputs': 10,
                   'directed_entries_per_method': 526890, 'functional_targets_opened': False}
        save(out/'TARGET_LAST_BARRIER.json', encoded(barrier), budget)
        # This is the sole operational private-functional read site, reached only
        # after actual native process and both complete candidate executions.
        result['functional_targets_opened'] = True
        target_out = out/'functional_products'; target_out.mkdir()
        rows = []
        for i, mouse in enumerate(cohort['mice']):
            matrices = {label: doc['folds'][i]['probabilities'] for label, doc in documents.items()}
            rows.append(functional.grade_mouse(package, target_out/mouse['mouse_id'], mouse, matrices,
                                               io, metrics, bank, budget))
            result['completed_mouse_grades'] = len(rows)
        report = functional.summarize(rows)
        report['rows'] = rows
        report['source_binding'] = args.source_sha256
        report['target_last_barrier'] = identity(capture(out/'TARGET_LAST_BARRIER.json', 1048576, budget=budget))
        save(out/'COMPARISON.json', encoded(report), budget)
        result['success'] = True
    except BaseException as error:
        result['error_type'] = type(error).__name__
        result['error'] = str(error)[:1000]
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_alarm)
        result.update(budget.record())
        # A reserved closing receipt is a small explicit exception to expired
        # execution time; never delete failed products or invent completion.
        result_body = encoded(result)
        need(len(result_body) <= 4096, 'Prepaid study closing receipt extent')
        save(out/'STUDY_ATTEMPT.json', result_body)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('repository', 'package', 'output', 'limits', 'policies', 'program-a', 'program-b',
                 'python', 'matlab', 'docker', 'docker-config'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('source-sha256', 'method-a', 'method-b', 'docker-host'):
        p.add_argument('--'+name, required=True)
    args = p.parse_args()
    need(args.docker_host.startswith('unix://'), 'Explicit local Docker daemon')
    execute(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

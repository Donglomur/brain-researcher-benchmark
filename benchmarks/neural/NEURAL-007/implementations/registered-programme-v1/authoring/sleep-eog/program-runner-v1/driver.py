"""Same-group controller: frozen program, fresh cases, then trusted grader."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import stat
import time
import uuid
from sleep_common import HERE, ROOT, HostBudget, need, ordinary, save, units, opaque, run_unit, digest
from grade_profile import GradeEngine, mounts_for


def grade(attempt, committed, program_sha, budget, end):
    folder = attempt / 'grade'
    folder.mkdir(mode=0o700)
    invocation = {'parts': {row['unit_id']: row['output'] for row in committed},
                  'producer_resources_absent': True, 'same_program_sha256': program_sha}
    save(folder / 'invocation.json', invocation, budget)
    # Candidate/holder/volume removal has already succeeded for both cases.
    # The host only stats the private files; hashes/values are read by the worker
    # after both candidate schemas and every fixed comparator pass.
    mounts = mounts_for(attempt)
    for destination, source in mounts.items():
        path = Path(source)
        info = path.lstat()
        need(all(not p.is_symlink() for p in (path, *path.parents)) and stat.S_ISREG(info.st_mode) and
             info.st_nlink == 1 and bool(info.st_mode & 4), 'Ordinary readable exact file bind')
        if destination.startswith('/private/'):
            assets = json.loads(ordinary(ROOT / 'benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/operator_assets.json', 16_384))
            need(info.st_size == assets['private_files'][path.name]['bytes'], 'Private stat-only expected size')
    engine = GradeEngine(min(end, time.monotonic() + 16), folder, budget)
    name = 'sleep-score-' + uuid.uuid4().hex
    receipt = {'status': 'started', 'container': name}
    try:
        inspected, receipt['boundary'] = engine.create_grade(name, mounts)
        # Attached stdout is bounded; no independent host process group is created.
        reply = engine.run(['start', '-a', name], timeout=10, cap=65_536)
        receipt['attached_result'] = {'returncode': reply.returncode, 'stdout': reply.stdout.decode(errors='replace'),
                                      'stderr': reply.stderr.decode(errors='replace')}
        need(len(reply.stdout) <= 32_768 and not reply.stderr, 'Bounded complete trusted scoring output')
        state = engine.inspect('container', name)['State']
        receipt['exit_state'] = state
        need(reply.returncode == 0 and state['Status'] == 'exited' and state['Running'] is False and
             state['Pid'] == 0 and state['ExitCode'] == 0 and state['OOMKilled'] is False, 'Trusted grader normal exit')
        result = json.loads(reply.stdout)
        need(result['status'] in ('scored', 'invalid_submission'), 'Separate operator errors')
        need(result['private_loader_calls'] == (1 if result['status'] == 'scored' else 0), 'Schema-before-private boundary')
        save(folder / 'score.json', result, budget, cap=32_768)
        receipt['status'] = 'completed'
        return result
    finally:
        receipt['cleanup'] = engine.cleanup('container', name) if engine.owned else {'absence_verified': True, 'not_created': True}
        engine.write('receipt.json', receipt, cap=100_000)
        need(receipt['cleanup']['absence_verified'], 'Trusted grader absent')


def attempt(program, run, budget, work_end, whole_end):
    run.mkdir(mode=0o700)
    body = ordinary(program, 200_000)
    body.decode('utf-8', errors='strict')
    budget.write(run / 'program.py', body, mode=0o444)
    sha = hashlib.sha256(body).hexdigest()
    save(run / 'program_commit.json', {'program_sha256': sha, 'bytes': len(body),
         'frozen_before_any_case_release': True, 'mode': 'fixed_program_feature_condition'}, budget)
    result = {'status': 'started', 'program_sha256': sha, 'units': [], 'private_grader_dispatched': False}
    try:
        previous = None
        for unit in units():
            value = run_unit(run / 'program.py', sha, unit, run / unit['unit_id'], budget,
                             work_end, whole_end, previous, 'NEURAL-007', opaque)
            result['units'].append(value)
            need(value['all_owned_absent'], 'Each unit fully absent before next release')
            if value['status'] != 'unit_committed':
                result['status'] = value['status']
                return result
            previous = value['commit_sha256']
        need(digest(run / 'program.py') == sha, 'Same frozen program across all cases')
        result['private_grader_dispatched'] = True
        score = grade(run, result['units'], sha, budget, work_end)
        result.update(status=score['status'], score=score['score'], private_loader_calls=score['private_loader_calls'])
        return result
    finally:
        # Unit execution receipts preserve details; compact attempt avoids duplicating them.
        compact = {key: value for key, value in result.items() if key != 'units'}
        compact['units'] = [{key: row.get(key) for key in ('unit_id', 'status', 'commit_sha256', 'all_owned_absent')}
                            for row in result['units']]
        save(run / 'attempt.json', compact, budget)


def expected(label, value, folder):
    if label == 'private_probe':
        need(value['status'] == 'output_boundary_rejected' and len(value['units']) == 1 and
             value['private_grader_dispatched'] is False and not (folder / 'grade').exists(), 'Probe stops before private grade/second case')
        return
    need(len(value['units']) == 2 and all(x['status'] == 'unit_committed' for x in value['units']), 'Two sequential committed outputs')
    score = json.loads(ordinary(folder / 'grade/score.json', 32_768))
    if label == 'malformed':
        need(score['status'] == 'invalid_submission' and score['score'] is None and score['private_loader_calls'] == 0,
             'Malformed complete artifacts rejected before private targets')
        return
    need(score['status'] == 'scored' and score['private_loader_calls'] == 1 and score['scientific_success'] is None,
         'Valid continuous result with no binary promotion')
    metrics = score['result']
    if label == 'reference':
        need(metrics['candidate'] == metrics['comparators']['YASA'] and
             math.isclose(score['score'], .7318258224249081, rel_tol=0, abs_tol=1e-14), 'Exact saved YASA descriptive parity')
        for unit in value['units']:
            logs = unit['candidate_logs']
            need(not logs['capture_truncated'] and logs['captured_stderr_bytes'] == 0, 'Complete join-control evidence')
            facts = json.loads(logs['stdout'])
            need(facts['training_people'] == 6 and facts['training_full_epochs'] == 16290 and
                 facts['three_way_training_join_checked'] and facts['fresh_marker_absent_before_start'] and facts['fits'] == 0,
                 'All training joins/fresh state checked in each invocation')
    elif label == 'constant':
        for row in metrics['candidate']['per_person']:
            support = row['true_support']
            total = sum(support)
            want = (2 * support[0] / (total + support[0]) if total + support[0] else 0) / 5
            need(row['predicted_support'] == [total, 0, 0, 0, 0] and
                 math.isclose(row['macro_f1_fixed_five'], want, rel_tol=0, abs_tol=1e-15), 'Independent uniform/all-wake arithmetic')


def main(args):
    started = time.monotonic()
    budget = HostBudget(args.run, 11_000_000, 5_000_000)
    result = {'status': 'started', 'candidate_id': 'NEURAL-007', 'controls': [],
              'new_fits': 0 if args.mode == 'qualify' else None,
              'new_model_calls': 0 if args.mode == 'qualify' else None,
              'external_model_service_calls': 0, 'reserved_person_reads': 0, 'full_scientific_contract_complete': False}
    try:
        if args.mode == 'qualify':
            controls = [('reference', HERE / 'reference_program.py'), ('constant', HERE / 'constant_program.py'),
                        ('malformed', HERE / 'malformed_program.py'), ('private_probe', HERE / 'private_probe_program.py')]
        else:
            need(args.program is not None, 'One submitted program')
            controls = [('submission', args.program)]
        for label, source in controls:
            value = attempt(source, args.run / label, budget, args.work_deadline, args.whole_deadline)
            if args.mode == 'qualify':
                expected(label, value, args.run / label)
                if label == 'reference':
                    import guards
                    result['generated_guards'] = guards.check(args.run / label)
            result['controls'].append({'name': label, 'status': value['status'], 'score': value.get('score'),
                                       'private_loader_calls': value.get('private_loader_calls', 0), 'checked': args.mode == 'qualify'})
        result['status'] = 'passed' if args.mode == 'qualify' else result['controls'][0]['status']
    except BaseException as error:
        result.update(status='failed', error=repr(error)[:1024])
    finally:
        result.update(controller_wall_seconds=time.monotonic() - started,
                      controller_process_cpu_seconds=time.process_time(),
                      controller_maxrss_macos_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        save(args.run / 'result.json', result, budget)
    return int(result['status'] == 'failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('qualify', 'submission'), required=True)
    parser.add_argument('--program', type=Path)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--work-deadline', type=float, required=True)
    parser.add_argument('--whole-deadline', type=float, required=True)
    raise SystemExit(main(parser.parse_args()))

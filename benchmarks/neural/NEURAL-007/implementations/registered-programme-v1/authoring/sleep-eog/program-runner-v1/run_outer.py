#!/usr/bin/env python3
"""Reviewed bounded submission/qualification, with durable ownership recovery."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
sys.dont_write_bytecode = True
STARTED = time.monotonic()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEADLINE = None


def need(ok, message):
    if not ok:
        raise ValueError(message)


def terminal(*unused):
    try:
        pass
    finally:
        os._exit(124)


def cleanup_alarm():
    signal.signal(signal.SIGALRM, terminal)
    signal.setitimer(signal.ITIMER_REAL, max(.001, DEADLINE - time.monotonic()))


def work_alarm(*unused):
    cleanup_alarm()
    raise TimeoutError('Work interval ended; only owned cleanup remains')


def read(path, cap):
    # Pre-import source guard. All task data reads happen after reviewed closure.
    import stat
    p = Path(path).absolute()
    need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'Canonical unlinked file')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded ordinary file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields), 'Stable exact bytes')
        return body
    finally:
        os.close(fd)


def durable(path, value):
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    need(len(body) <= 300_000 and not path.exists(), 'Fresh bounded receipt')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def bind_endpoint(review):
    endpoint = review['docker_host']
    need(type(endpoint) is str and endpoint.startswith('unix://'), 'Explicit reviewed local Docker endpoint')
    socket_path = endpoint[7:]
    need(socket_path.startswith('/') and Path(socket_path).as_posix() == socket_path and
         '..' not in Path(socket_path).parts and not any(c in socket_path for c in ('\0', '\n', '\r', ',')),
         'Literal absolute local Docker socket path')
    os.environ['NEURAL007_DOCKER_HOST'] = endpoint


def amount(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    need(valid, 'Finite nonnegative non-boolean accounting value')
    return value


def latest_prior(review, plan, mode, freeze_sha):
    """Carry closed history into either mode; historical floors are not a grant."""
    prior_pin = review['prior_receipt']
    need(type(prior_pin) is dict and set(prior_pin) == {'path', 'bytes', 'sha256'} and
         not Path(prior_pin['path']).is_absolute() and '..' not in Path(prior_pin['path']).parts,
         'Exact reviewed prior cost receipt')
    prior_body = read(ROOT / prior_pin['path'], 300_000)
    need(len(prior_body) == prior_pin['bytes'] and hashlib.sha256(prior_body).hexdigest() == prior_pin['sha256'],
         'Exact current cost evidence bytes')
    prior = json.loads(prior_body)
    for key in ('known_wall_seconds_after', 'prior_known_wall_seconds', 'charged_seconds',
                'conservative_YASA_associated_allocation_seconds_after'):
        amount(prior[key])
    amount(review['prior_known_wall_seconds'])
    need(Path(prior_pin['path']).is_relative_to('artifacts-build') and Path(prior_pin['path']).name == 'outer_receipt.json' and
         prior.get('candidate_id') == 'NEURAL-007' and prior.get('mode') in ('qualify', 'submission') and
         prior.get('all_owned_absent') is True and prior.get('all_activated_groups_absent') is True and
         prior.get('known_wall_seconds_after') == review['prior_known_wall_seconds'] and
         prior['known_wall_seconds_after'] == prior['prior_known_wall_seconds'] + prior['charged_seconds'] and
         prior['known_wall_seconds_after'] >= 2270.025864832016 and
         prior['known_wall_seconds_after'] >= plan['qualification_after_full_charge_seconds'],
         'Latest closed post-qualification cost required in both modes; recorded floor is not the latest total')
    if mode == 'submission':
        qualification_pin = review['qualified_outer_receipt']
        need(type(qualification_pin) is dict and set(qualification_pin) == {'path', 'bytes', 'sha256'} and
             not Path(qualification_pin['path']).is_absolute() and '..' not in Path(qualification_pin['path']).parts and
             Path(qualification_pin['path']).is_relative_to('artifacts-build') and
             Path(qualification_pin['path']).name == 'outer_receipt.json', 'Exact operator artifact qualification receipt')
        qbody = read(ROOT / qualification_pin['path'], 300_000)
        need(len(qbody) == qualification_pin['bytes'] and hashlib.sha256(qbody).hexdigest() == qualification_pin['sha256'],
             'Actual qualification receipt bound before arbitrary submission')
        qualified = json.loads(qbody)
        need(qualified['status'] == 'passed' and qualified['mode'] == 'qualify' and
             qualified['source_freeze_sha256'] == freeze_sha and
             qualified['all_owned_absent'] and qualified['all_activated_groups_absent'], 'Same source closure independently qualified')
    return prior['conservative_YASA_associated_allocation_seconds_after']


def execute(args, freeze, review, plan):
    sys.path.insert(0, str(HERE))
    from sleep_common import BaseEngine, HostBudget, owner, ordinary, save, load_module
    recovery = load_module(HERE / 'recovery.py', '_sleep_outer_recovery')
    # Reuse the qualified generic wait/storage helpers, not another task's dispatch.
    helpers = load_module(ROOT / 'authoring/paper-language-project/phase1-numerical-v1/run_outer.py', '_sleep_outer_helpers')
    run = args.output.absolute()
    budget = HostBudget(run, 12_000_000, 5_000_000)
    stage = plan['modes'][args.mode]
    work_end = STARTED + stage['work_seconds']
    result = {'candidate_id': 'NEURAL-007', 'mode': args.mode, 'status': 'started',
              'allocation_seconds': stage['whole_seconds'], 'prior_known_wall_seconds': review['prior_known_wall_seconds'],
              'source_freeze_sha256': hashlib.sha256(read(HERE / 'FREEZE.json', 100_000)).hexdigest(),
              'all_owned_absent': False, 'all_activated_groups_absent': False,
              'external_model_service_calls': 0,
              'new_fits_in_qualification': 0 if args.mode == 'qualify' else None, 'reserved_person_reads': 0}
    processes = {}
    old_handlers = {}
    try:
        associated_before = latest_prior(review, plan, args.mode, result['source_freeze_sha256'])
        amount(review['conservative_YASA_associated_allocation_seconds_before'])
        amount(review['conservative_YASA_associated_allocation_seconds_after'])
        need(review['conservative_YASA_associated_allocation_seconds_before'] == associated_before and
             review['conservative_YASA_associated_allocation_seconds_after'] == associated_before + stage['whole_seconds'],
             'Explicit conservative associated-work accounting; no double addition to global')
        result['conservative_YASA_associated_allocation_seconds_before'] = associated_before
        result['storage'] = helpers.storage(plan, 12_000_000, args.other_reserve_bytes, work_end)
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, lambda unused, frame: (_ for _ in ()).throw(InterruptedError('Outer interrupted')))
        descriptor = lambda rel: {'path': rel, **freeze['files'][rel]}
        if args.mode == 'qualify':
            fixture = descriptor('authoring/shared-program-ownership-v3/interrupt_fixture.py')
            folder = run / 'fixture-controller'
            folder.mkdir(mode=0o700)
            command = [sys.executable, str(ROOT / fixture['path']), 'test', '--out', str(run / 'interrupted_wrapper')]
            processes['fixture-controller'] = owner.launch(command, folder, 8, fixture)
            done = helpers.completed(folder, min(work_end, time.monotonic() + 7), owner)
            stopped = owner.stop(folder, min(work_end, time.monotonic() + 2), processes.pop('fixture-controller'))
            need(done['returncode'] == 0 and stopped['absence_verified'], 'Actual owned wrapper interruption recovered')
            value = json.loads(ordinary(run / 'interrupted_wrapper/fixture.json', 16_384))
            need(value['status'] == 'passed' and value['late_write_absent'] is True, 'No late fixture write')
            result['interruption_fixture'] = value
        controller = descriptor('authoring/sleep-eog/program-runner-v1/driver.py')
        command = [sys.executable, str(ROOT / controller['path']), '--mode', args.mode, '--run', str(run),
                   '--work-deadline', str(work_end), '--whole-deadline', str(DEADLINE)]
        if args.mode == 'submission':
            # Copy before the owned controller opens any case; all later reads use this sealed source.
            body = ordinary(args.program, 200_000)
            body.decode('utf-8', errors='strict')
            budget.write(run / 'submitted_program.py', body, mode=0o444)
            result['submitted_program_sha256'] = hashlib.sha256(body).hexdigest()
            command += ['--program', str(run / 'submitted_program.py')]
        folder = run / 'controller'
        folder.mkdir(mode=0o700)
        need(work_end > time.monotonic() + 2, 'Whole-stage work remains')
        processes['controller'] = owner.launch(command, folder, work_end - time.monotonic() + 1, controller)
        done = helpers.completed(folder, work_end, owner)
        stopped = owner.stop(folder, min(DEADLINE - 5, time.monotonic() + 2), processes.pop('controller'))
        need(stopped['absence_verified'], 'Stop owned group before outer Docker recovery')
        value = json.loads(ordinary(run / 'result.json', 100_000))
        need(done['returncode'] == 0, 'Completed task controller')
        result.update(status=value['status'], result_sha256=hashlib.sha256(ordinary(run / 'result.json', 100_000)).hexdigest())
    except BaseException as error:
        result.update(status='failed', error=repr(error)[:1024])
    finally:
        cleanup_alarm()
        groups = []
        for label in ('controller', 'fixture-controller', 'interrupted_wrapper/owned'):
            folder = run / label
            if folder.exists():
                try:
                    value = owner.stop(folder, min(DEADLINE - 2, time.monotonic() + 2), processes.pop(label, None))
                    value['owner_folder'] = label
                except BaseException as error:
                    value = {'owner_folder': label, 'absence_verified': False, 'error': repr(error)[:512]}
                groups.append(value)
        result['owned_process_groups'] = groups
        result['all_activated_groups_absent'] = all(x['absence_verified'] for x in groups)
        cleanup = []
        try:
            need(result['all_activated_groups_absent'], 'All activated groups absent before any Docker recovery')
            labels = ('reference', 'constant', 'malformed', 'private_probe') if args.mode == 'qualify' else ('submission',)
            owned = [(run / label, folder, item) for label in labels if (run / label).exists()
                     for folder, item in recovery.inventory(run / label)]
            need(len(owned) <= (24 if args.mode == 'qualify' else 7) and
                 len({item['name'] for attempt, folder, item in owned}) == len(owned), 'Exact bounded owned inventory')
            engine = BaseEngine(DEADLINE - .5, run, budget)
            for attempt, folder, item in reversed(owned):
                try:
                    value = recovery.recover(attempt, folder, item, engine, budget)
                except BaseException as error:
                    value = {'name': item['name'], 'kind': item['kind'], 'absence_verified': False, 'error': repr(error)[:512]}
                cleanup.append(value)
            result['all_owned_absent'] = len(cleanup) == len(owned) and all(x['absence_verified'] for x in cleanup)
            if args.mode == 'qualify' and result['status'] == 'passed':
                need(len(owned) == 24 and len(groups) == 3, 'All declared qualification resources/groups accounted')
        except BaseException as error:
            result['cleanup_error'] = repr(error)[:1024]
            result['all_owned_absent'] = False
        result['cleanup'] = cleanup
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        elapsed = time.monotonic() - STARTED
        result.update(wall_seconds=elapsed, charged_seconds=max(stage['whole_seconds'], elapsed),
                      known_wall_seconds_after=review['prior_known_wall_seconds'] + max(stage['whole_seconds'], elapsed),
                      outer_process_cpu_seconds=time.process_time(),
                      outer_process_maxrss_macos_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      retained_bytes_before_final_receipt=budget.used(), lifetime_cost_complete=False,
                      cpu_is_separate_from_wall=True)
        if 'conservative_YASA_associated_allocation_seconds_before' in result:
            result['conservative_YASA_associated_allocation_seconds_after'] = \
                result['conservative_YASA_associated_allocation_seconds_before'] + result['charged_seconds']
        if not result['all_owned_absent'] or not result['all_activated_groups_absent']:
            result['status'] = 'cleanup_unverified'
        if elapsed >= stage['whole_seconds']:
            result['status'] = 'deadline_exceeded'
        save(run / 'outer_receipt.json', result, budget, cap=300_000)
    print(json.dumps({'status': result['status'], 'charged_seconds': result['charged_seconds']}))
    return int(result['status'] not in ('passed', 'scored', 'invalid_submission', 'output_boundary_rejected', 'candidate_program_failed'))


def dispatch():
    global DEADLINE
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('qualify', 'submission'), required=True)
    parser.add_argument('--program', type=Path)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--other-reserve-bytes', type=int, required=True)
    args = parser.parse_args()
    seconds, work = (180, 110) if args.mode == 'qualify' else (100, 70)
    DEADLINE = STARTED + seconds
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'No preexisting alarm')
    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, work_alarm)
    signal.setitimer(signal.ITIMER_REAL, max(.001, STARTED + work - time.monotonic()))
    run = args.output.absolute()
    started = False
    error_text = None
    try:
        need('..' not in run.parts and run.is_relative_to(ROOT / 'artifacts-build') and run != ROOT / 'artifacts-build' and
             not run.exists() and run.parent.is_dir() and all(not p.is_symlink() for p in (run, *run.parents)), 'Fresh exact attempt folder')
        run.mkdir(mode=0o700)
        durable(run / 'preflight_started.json', {'candidate_id': 'NEURAL-007', 'mode': args.mode,
            'full_stage_charge_seconds': seconds, 'authorization_validated': False,
            'status': 'attempt_dispatched_preflight_pending', 'automatic_retry': False})
        started = True
        review = json.loads(read(args.review, 32_768))
        freeze_body = read(HERE / 'FREEZE.json', 100_000)
        freeze_sha = hashlib.sha256(freeze_body).hexdigest()
        need(review['decision'] == 'authorize_one_sleep_program_' + args.mode and review['freeze_sha256'] == freeze_sha and
             review['whole_seconds'] == seconds and review['artifact_reserve_bytes'] == 12_000_000 and
             review['other_reserve_bytes'] == args.other_reserve_bytes and review['output_path'] == str(run.relative_to(ROOT)),
             'Explicit exact root review before source imports or data reads')
        freeze = json.loads(freeze_body)
        for relative, pin in freeze['files'].items():
            need(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'Canonical frozen source path')
            body = read(ROOT / relative, 1_000_000)
            need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'Exact source freeze: ' + relative)
        plan = json.loads(read(HERE / 'PLAN.json', 32_768))
        for key in ('prior_known_wall_seconds', 'prospective_known_wall_seconds_after',
                    'candidate_cumulative_ceiling_seconds'):
            amount(review[key])
        need(plan['modes'][args.mode] == {'whole_seconds': seconds, 'work_seconds': work} and
             review['prospective_known_wall_seconds_after'] == review['prior_known_wall_seconds'] + seconds and
             review['prospective_known_wall_seconds_after'] <= review['candidate_cumulative_ceiling_seconds'], 'Explicit prospective cumulative allocation')
        need((args.mode == 'submission') == (args.program is not None), 'Program only in submission mode')
        bind_endpoint(review)
        return execute(args, freeze, review, plan)
    except BaseException as error:
        error_text = repr(error)[:1024]
        raise
    finally:
        cleanup_alarm()
        if started and not (run / 'outer_receipt.json').exists():
            durable(run / 'preflight_or_outer_failure.json', {'status': 'failed_attempt_preserved', 'mode': args.mode,
                'full_stage_charge_seconds': seconds, 'charged_seconds': max(seconds, time.monotonic() - STARTED),
                'wall_seconds': time.monotonic() - STARTED, 'error': error_text,
                'cleanup_claim': 'Incomplete outer receipt; inspect exact ownership journals, never infer absence.', 'automatic_retry': False})
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == '__main__':
    raise SystemExit(dispatch())

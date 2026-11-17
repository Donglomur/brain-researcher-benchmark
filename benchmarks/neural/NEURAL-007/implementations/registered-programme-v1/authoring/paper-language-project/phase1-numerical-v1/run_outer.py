#!/usr/bin/env python3
"""One reviewed language stage; reuse frozen ownership and Docker lifecycle.

No input rows are opened before a root review binds the source freeze. Stage A
allows exactly the public manifest; stage B allows its sealed generated bundle.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
STARTED = time.monotonic()
CPU_STARTED = time.process_time()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEADLINE = None


def need(value, text):
    if not value:
        raise ValueError(text)


def terminal_deadline(*unused):
    try:
        pass
    finally:
        os._exit(124)


def begin_cleanup():
    signal.signal(signal.SIGALRM, terminal_deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, DEADLINE - time.monotonic()))


def work_deadline(*unused):
    begin_cleanup()
    raise TimeoutError('Absolute work deadline; only owned cleanup remains')


def ordinary(path, cap):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked canonical file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded ordinary file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields), 'Stable file bytes')
        return body
    finally:
        os.close(fd)


def pinned(pin, cap=1_000_000):
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'Exact descriptor')
    relative = pin['path']
    need(type(relative) is str and not Path(relative).is_absolute() and '..' not in Path(relative).parts,
         'Project relative descriptor')
    need(type(pin['bytes']) is int and 0 < pin['bytes'] <= cap and
         type(pin['sha256']) is str and re.fullmatch('[a-f0-9]{64}', pin['sha256']), 'Bounded file identity')
    body = ordinary(ROOT / relative, pin['bytes'])
    need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'Pinned bytes: ' + relative)
    return body


def completed(folder, end, owner):
    while not (folder / 'process_completion.json').exists():
        need(time.monotonic() < end, 'Owned controller completion deadline')
        time.sleep(.01)
    done = owner.read(folder / 'process_completion.json')
    identity = owner.read(folder / 'process_owner.json')
    need(done['token'] == identity['token'] and done['group_leader_waits_for_owner_stop'] is True,
         'Exact completed controller with retained leader')
    return done


def storage(plan, reserve, other, end):
    need(type(other) is int and 0 <= other <= 2_000_000_000, 'Explicit aggregate pending reservations')
    proc = subprocess.run(['/usr/bin/du', '-sk', str(ROOT)], capture_output=True, text=True,
                          timeout=min(3, max(.001, end - time.monotonic())), check=True)
    need(len(proc.stdout) <= 1024 and len(proc.stderr) <= 1024, 'Bounded allocated-storage measurement')
    allocated = int(proc.stdout.split()[0]) * 1024
    free = shutil.disk_usage(ROOT).free
    images = plan['existing_images_bytes']
    need(free - reserve - other >= 10_000_000_000, 'Ten GB free after all pending reservations')
    need(allocated + images + reserve + other <= 12_000_000_000, 'Project, images, and reservations under twelve GB')
    return {'project_allocated_bytes': allocated, 'free_bytes': free, 'existing_images_bytes': images,
            'own_reserve_bytes': reserve, 'other_reserve_bytes': other, 'new_downloads': 0}


def validate_prior(review, plan, freeze_sha, stage):
    prior = plan['prior_history']
    ledger = json.loads(pinned(prior['ledger'], 32_768))
    for key in ('known_scientific_wall_seconds', 'known_scientific_process_cpu_seconds', 'separate_verification_wall_seconds'):
        need(ledger[key] == prior[key], 'Retained historical ledger category')
    before = prior['known_nonoverlapping_wall_sum_seconds']
    need(math.isclose(before, ledger['known_scientific_wall_seconds'] + ledger['separate_verification_wall_seconds'],
                      rel_tol=0, abs_tol=1e-10), 'Only nonoverlapping historical wall categories summed')
    if stage == 'build':
        need(review.get('build_result') is None and review.get('build_outer_receipt') is None, 'No fabricated prior build')
        return before, None
    receipt_pin, result_pin = review['build_outer_receipt'], review['build_result']
    need(Path(receipt_pin['path']).name == 'outer_receipt.json' and Path(result_pin['path']).name == 'result.json' and
         Path(receipt_pin['path']).parent == Path(result_pin['path']).parent and
         Path(receipt_pin['path']).is_relative_to('artifacts-build'), 'Paired exact build evidence')
    receipt, result = json.loads(pinned(receipt_pin, 300_000)), json.loads(pinned(result_pin, 32_768))
    need(receipt['status'] == result['status'] == 'passed' and receipt['stage'] == result['stage'] == 'build' and
         receipt['candidate_id'] == result['candidate_id'] == plan['candidate_id'] and
         receipt['source_freeze_sha256'] == freeze_sha and receipt['result_sha256'] == result_pin['sha256'] and
         receipt['all_owned_absent'] is True and receipt['all_activated_groups_absent'] is True,
         'Successful exact source-frozen build and complete cleanup')
    need(receipt['prior_known_wall_seconds'] == before and receipt['allocation_seconds'] == 15 and
         type(receipt['charged_seconds']) in (int, float) and math.isfinite(receipt['charged_seconds']) and
         receipt['charged_seconds'] >= 15 and receipt['known_wall_seconds_after'] == before + receipt['charged_seconds'],
         'Prior full builder allocation retained, never reset')
    reference = result['reference']
    need(reference['path'] == str(Path(result_pin['path']).parent / 'unit/reference.json') and
         result['protected_outcome_reads'] == result['new_fits'] == 0, 'Exact public-only derived reference path')
    # Verify its bytes now; the trusted controller independently verifies them again.
    pinned(reference, 500_000)
    return receipt['known_wall_seconds_after'], ROOT / result_pin['path']


def execute(args, freeze, freeze_sha, review_body, review, plan, preflight_sha):
    sys.path.insert(0, str(ROOT / 'authoring/shared-summary-runner-v1'))
    from common import BaseEngine, HostBudget, owner, save
    sys.path.insert(0, str(HERE))
    import recovery_guard
    stage = plan['stages'][args.stage]
    run = args.output.absolute()
    need('..' not in run.parts and run.is_relative_to(ROOT / 'artifacts-build') and run != ROOT / 'artifacts-build' and run.is_dir() and
         run.parent.is_dir() and all(not p.is_symlink() for p in (run, *run.parents)), 'Fresh artifact directory')
    need(set(path.name for path in run.iterdir()) == {'preflight_started.json'} and
         hashlib.sha256(ordinary(run / 'preflight_started.json', 16_384)).hexdigest() == preflight_sha,
         'Exactly the same fresh outer-owned preflight directory')
    budget = HostBudget(run, stage['reserve_bytes'], stage['receipt_reserve_bytes'])
    record = {'candidate_id': plan['candidate_id'], 'stage': args.stage, 'status': 'started',
              'source_freeze_sha256': freeze_sha, 'review_sha256': hashlib.sha256(review_body).hexdigest(),
              'allocation_seconds': stage['whole_seconds'], 'all_owned_absent': False,
              'all_activated_groups_absent': False, 'new_fits': 0, 'new_model_calls': 0, 'protected_outcome_reads': 0}
    processes, handlers = {}, {}
    build_result_value = None
    try:
        before, build_result = validate_prior(review, plan, freeze_sha, args.stage)
        if build_result is not None:
            build_result_value = json.loads(ordinary(build_result, 32_768))
        record['prior_known_wall_seconds'] = before
        need(review.get('decision') == 'authorize_one_language_phase1_' + args.stage and
             review.get('candidate_id') == plan['candidate_id'] and review.get('freeze_sha256') == freeze_sha and
             review.get('stage') == args.stage and review.get('whole_seconds') == stage['whole_seconds'] and
             review.get('prior_known_wall_seconds') == before and
             review.get('prospective_known_wall_seconds_after') == before + stage['whole_seconds'] and
             review.get('artifact_reserve_bytes') == stage['reserve_bytes'] and
             review.get('other_reserve_bytes') == args.other_reserve_bytes and
             review.get('output_path') == str(run.relative_to(ROOT)), 'Exact prospective stage review')
        record['storage'] = storage(plan, stage['reserve_bytes'], args.other_reserve_bytes, STARTED + stage['work_seconds'])
        for signum in (signal.SIGINT, signal.SIGTERM):
            handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, lambda sig, frame: (_ for _ in ()).throw(InterruptedError('Outer interrupted')))
        def source_descriptor(relative):
            return {'path': relative, **freeze['files'][relative]}
        if args.stage == 'qualify':
            fixture = source_descriptor(plan['interruption_controller'])
            folder = run / 'fixture-controller'; folder.mkdir(mode=0o700)
            command = [sys.executable, str(ROOT / fixture['path']), 'test', '--out', str(run / 'interrupted_wrapper')]
            processes['fixture-controller'] = owner.launch(command, folder, 8, fixture)
            done = completed(folder, min(STARTED + 9, time.monotonic() + 6), owner)
            stopped = owner.stop(folder, min(STARTED + 11, time.monotonic() + 1), processes.pop('fixture-controller'))
            need(stopped['absence_verified'] and done['returncode'] == 0, 'Actual interrupted owned controller recovered')
            fixture_result = json.loads(ordinary(run / 'interrupted_wrapper/fixture.json', 16_384))
            need(fixture_result['status'] == 'passed' and fixture_result['late_write_absent'] is True, 'No late fixture write')
            record['interruption_fixture'] = fixture_result
        controller = source_descriptor(plan['controller'])
        work_end = STARTED + stage['work_seconds']
        remaining = work_end - time.monotonic()
        need(remaining >= 2, 'Remaining bounded stage work')
        command = [sys.executable, str(ROOT / controller['path']), '--stage', args.stage, '--run', str(run),
                   '--work-deadline', str(work_end), '--whole-deadline', str(DEADLINE)]
        if build_result is not None:
            command += ['--reference', str(build_result)]
        folder = run / 'controller'; folder.mkdir(mode=0o700)
        record['controller_argv'] = command
        processes['controller'] = owner.launch(command, folder, remaining + 1, controller)
        done = completed(folder, work_end, owner)
        stopped = owner.stop(folder, min(DEADLINE - stage['docker_cleanup_reserve_seconds'], time.monotonic() + 1),
                             processes.pop('controller'))
        need(stopped['absence_verified'], 'Owned host group absent before daemon recovery')
        record['controller_stop'] = stopped
        record['controller_returncode'] = done['returncode']
        body = ordinary(run / 'result.json', 100_000)
        result = json.loads(body)
        record.update(result_sha256=hashlib.sha256(body).hexdigest(), result_status=result['status'])
        record['status'] = 'passed' if done['returncode'] == 0 and result['status'] == 'passed' else 'failed'
    except BaseException as error:
        record.update(status='failed', error=repr(error)[:1024])
    finally:
        begin_cleanup()
        groups = []
        for label in ('controller', 'fixture-controller', 'interrupted_wrapper/owned'):
            folder = run / label
            if folder.exists():
                try:
                    row = owner.stop(folder, min(DEADLINE - stage['docker_cleanup_reserve_seconds'], time.monotonic() + 1),
                                     processes.pop(label, None))
                    row['owner_folder'] = label
                except BaseException as error:
                    row = {'owner_folder': label, 'absence_verified': False, 'error': repr(error)[:1024]}
                groups.append(row)
        record['owned_process_groups'] = groups
        record['all_activated_groups_absent'] = all(row['absence_verified'] for row in groups)
        cleanup = []
        try:
            need(record['all_activated_groups_absent'], 'Stop every durably activated host group before Docker recovery')
            if args.stage == 'build':
                journals = [run / 'unit/resource_ownership.json']
                cap, count = 65_536, 3
            else:
                journals = [run / 'metadata' / label / 'resource_ownership.json' for label in plan['case_labels']]
                cap, count = 16_384, len(plan['case_labels'])
            owned = []
            for path in journals:
                if path.exists():
                    rows = json.loads(ordinary(path, cap))['owned']
                    need(type(rows) is list and len(rows) <= (3 if args.stage == 'build' else 1), 'Bounded journal')
                    if args.stage == 'build' and rows:
                        suffix = rows[0]['name'].rsplit('-', 1)[-1]
                        need([(row['kind'], row['name']) for row in rows] ==
                             [('volume', 'dmfc-prog-volume-' + suffix), ('container', 'dmfc-prog-holder-' + suffix),
                              ('container', 'dmfc-prog-worker-' + suffix)][:len(rows)], 'Exact builder creation sequence and shared suffix')
                    owned.extend((path.parent, row) for row in rows)
            need(len(owned) <= count and len({row['name'] for folder, row in owned}) == len(owned), 'Unique bounded owned inventory')
            for folder, row in owned:
                need(row.get('attempted_before_dispatch') is True, 'Ownership preceded creation')
                if args.stage == 'build':
                    need((row['kind'] == 'volume' and re.fullmatch('dmfc-prog-volume-[a-f0-9]{32}', row['name'])) or
                         (row['kind'] == 'container' and re.fullmatch('dmfc-prog-(holder|worker)-[a-f0-9]{32}', row['name'])),
                         'Exact builder resource identity')
                else:
                    need(row['kind'] == 'container' and re.fullmatch('summary-score-[a-f0-9]{12}', row['name']),
                         'Exact summary worker identity')
            recovery = BaseEngine(DEADLINE - .25, run, budget)
            for folder, row in reversed(owned):
                try:
                    value = recovery_guard.recover(args.stage, run, folder, row, recovery, ordinary, budget, build_result_value)
                except BaseException as error:
                    value = {'kind': row['kind'], 'name': row['name'], 'absence_verified': False, 'error': repr(error)[:1024]}
                cleanup.append(value)
            record['all_owned_absent'] = len(cleanup) == len(owned) and all(row['absence_verified'] for row in cleanup)
        except BaseException as error:
            record['cleanup_error'] = repr(error)[:1024]
        record['cleanup'] = cleanup
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        elapsed = time.monotonic() - STARTED
        record.update(wall_seconds=elapsed, charged_seconds=max(stage['whole_seconds'], elapsed),
                      outer_process_cpu_seconds=time.process_time() - CPU_STARTED,
                      outer_process_maxrss_macos_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      retained_bytes_before_final_receipt=budget.used(), exhaustive_lifetime_cost_known=False,
                      cpu_is_separate_from_wall=True)
        if 'prior_known_wall_seconds' in record:
            record['known_wall_seconds_after'] = record['prior_known_wall_seconds'] + record['charged_seconds']
        if not record['all_owned_absent'] or not record['all_activated_groups_absent']:
            record['status'] = 'cleanup_unverified'
        elif elapsed > stage['whole_seconds']:
            record['status'] = 'deadline_exceeded'
        save(run / 'outer_receipt.json', record, budget, cap=300_000)
    print(json.dumps({'status': record['status'], 'outer_receipt': str(run / 'outer_receipt.json')}))
    return int(record['status'] != 'passed')


def dispatch():
    global DEADLINE
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['build', 'qualify'], required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--other-reserve-bytes', type=int, required=True)
    args = parser.parse_args()
    # The independent alarm precedes all source hashing, imports, and metadata/data reads.
    seconds, work = (15, 9) if args.stage == 'build' else (60, 45)
    DEADLINE = STARTED + seconds
    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, work_deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, STARTED + work - time.monotonic()))
    run = args.output.absolute()
    preflight_started = False
    error_text = None
    def durable_small(name, value):
        body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
        need(len(body) <= 16_384, 'Small durable attempt metadata')
        fd = os.open(run / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(run, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return hashlib.sha256(body).hexdigest()
    try:
        need('..' not in run.parts and run.is_relative_to(ROOT / 'artifacts-build') and run != ROOT / 'artifacts-build' and
             not run.exists() and run.parent.is_dir() and all(not path.is_symlink() for path in (run, *run.parents)),
             'Fresh canonical attempt directory before source preflight')
        run.mkdir(mode=0o700)
        preflight_sha = durable_small('preflight_started.json', {
            'candidate_id': 'PAPER-ROOT-ADD-003', 'stage': args.stage, 'status': 'attempt_dispatched_preflight_pending',
            'full_stage_charge_seconds': seconds, 'whole_deadline_monotonic': DEADLINE,
            'review_path': str(args.review.absolute()), 'authorization_validated': False,
            'resources_dispatched_before_this_record': 0,
            'accounting': 'This fresh attempted stage retains its full charge even if review, freeze, import, or storage preflight fails. No historical budget reset.'})
        preflight_started = True
        review_body = ordinary(args.review, 32_768)
        review = json.loads(review_body)
        freeze_body = ordinary(HERE / 'FREEZE.json', 100_000)
        freeze_sha = hashlib.sha256(freeze_body).hexdigest()
        need(review.get('decision') == 'authorize_one_language_phase1_' + args.stage and
             review.get('freeze_sha256') == freeze_sha, 'Explicit root review before imports or data reads')
        freeze = json.loads(freeze_body)
        for relative, pin in freeze['files'].items():
            pinned({'path': relative, **pin}, 1_000_000)
        plan = json.loads(ordinary(HERE / 'RUNTIME_PLAN.json', 65_536))
        need(plan['candidate_id'] == 'PAPER-ROOT-ADD-003' and plan['stages'][args.stage]['whole_seconds'] == seconds and
             plan['stages'][args.stage]['work_seconds'] == work, 'Fixed task and absolute stage limits')
        return execute(args, freeze, freeze_sha, review_body, review, plan, preflight_sha)
    except BaseException as error:
        error_text = repr(error)[:1024]
        raise
    finally:
        begin_cleanup()
        if preflight_started and not (run / 'outer_receipt.json').exists():
            elapsed = time.monotonic() - STARTED
            durable_small('preflight_or_outer_failure.json', {
                'candidate_id': 'PAPER-ROOT-ADD-003', 'stage': args.stage, 'status': 'failed_attempt_preserved',
                'full_stage_charge_seconds': seconds, 'charged_seconds': max(seconds, elapsed),
                'wall_seconds': elapsed, 'error': error_text,
                'cleanup_claim': 'No complete outer receipt. Inspect durable ownership journals; absence is not inferred.',
                'lifetime_total_known': False, 'automatic_retry': False})
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == '__main__':
    raise SystemExit(dispatch())

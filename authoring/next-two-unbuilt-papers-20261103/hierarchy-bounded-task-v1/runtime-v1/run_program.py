#!/usr/bin/env python3
"""One root-reviewed complete hierarchy program; source-only successor until granted."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from files import HERE, ROOT, ID, RUNTIME_ID, json_read, need, pin, read, write
from admission import admit, WHOLE, WORK as WORK_SECONDS, CLEANUP

START = time.monotonic()
WORK = START + WORK_SECONDS
END = START + WHOLE
sys.dont_write_bytecode = True


def terminal(*unused):
    os._exit(124)


def cleanup_alarm():
    signal.signal(signal.SIGALRM, terminal)
    signal.setitimer(signal.ITIMER_REAL, max(.001, END - time.monotonic()))


def work_alarm(*unused):
    cleanup_alarm()
    raise TimeoutError('720-second work boundary; owned cleanup only')


def execute(args, run, frozen, review, program, admitted, capacity):
    from support import api, packet, save
    from panel_recovery import inventory, recover
    lib = api()
    budget = lib['HostBudget'](run, 22000000, 8000000)
    process = None
    handlers = {}
    result = {'candidate_id': ID, 'runtime_id':RUNTIME_ID, 'status': 'operator_error', 'source_freeze_sha256': review['freeze_sha256'],
              'program_sha256': pin(program)['sha256'], 'all_owned_absent': False,
              'all_activated_groups_absent': False, 'private_reference_reads': 0,
              'private_grade_dispatched': False, 'candidate_program_executed': False,
              'new_model_calls': 0, 'new_reference_fits': 0, 'candidate_fit_count': None,
              'controller_process_reaped':True, 'controller_launch_attempted':False,
              'scientific_success': None, 'full_contract_complete': False, 'research_qualified': False}
    try:
        disk = subprocess.run(['/usr/bin/du', '-sk', str(ROOT)], capture_output=True, text=True, timeout=10, check=True)
        need(len(disk.stdout) <= 1024 and len(disk.stderr) <= 1024, 'Bounded live capacity metadata')
        allocated = int(disk.stdout.split()[0]) * 1024
        fs = os.statvfs(ROOT)
        result['capacity'] = capacity.storage(admitted, allocated, fs.f_bavail * fs.f_frsize)
        result['dynamic_capacity_admission'] = admitted
        # Commit source before packet byte hashing, query release or resource creation.
        budget.write(run / 'program.py', program, mode=0o444)
        save(run / 'source_commit.json', {'program': pin(program), 'before_empirical_session_read': True,
             'review_sha256': pin(read(args.review))['sha256']}, budget)
        unit = packet()
        manifest = {'candidate_id': ID, 'unit': unit, 'program_path': str((run / 'program.py').relative_to(ROOT)),
                    'program_sha256': result['program_sha256'], 'source_freeze_sha256':review['freeze_sha256']}
        save(run / 'runtime_manifest.json', manifest, budget)
        save(run / 'runtime_manifest_commit.json', {'manifest': pin(read(run / 'runtime_manifest.json')),
             'before_any_Docker_resource_creation': True}, budget)
        for sig in (signal.SIGINT, signal.SIGTERM):
            handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, lambda *_: (_ for _ in ()).throw(InterruptedError('Outer interrupted')))
        folder = run / 'controller'
        folder.mkdir(mode=0o700)
        relative = str((HERE / 'controller.py').relative_to(ROOT))
        source = {'path': relative, **frozen['files'][relative]}
        need(time.monotonic() < WORK - 690, 'Full producer and grader allowances remain')
        result.update(controller_launch_attempted=True, controller_process_reaped=False,
                      candidate_program_executed=None)
        process = lib['owner'].launch([sys.executable, str(HERE / 'controller.py'), '--run', str(run),
                                     '--work-end', str(WORK)], folder, WORK - time.monotonic() + 1, source)
        while not (folder / 'process_completion.json').exists():
            need(time.monotonic() < WORK and process.poll() is None, 'Bounded owned controller')
            time.sleep(.01)
        completion = lib['owner'].read(folder / 'process_completion.json')
        identity = lib['owner'].read(folder / 'process_owner.json')
        need(completion['token'] == identity['token'] and completion['group_leader_waits_for_owner_stop'], 'Exact group completion')
        stopped = lib['owner'].stop(folder, min(END - .5, time.monotonic() + 6), process)
        result['controller_stop'] = stopped
        result['controller_process_reaped'] = 'bootstrap_returncode' in stopped
        process = None
        need(stopped['absence_verified'] and completion['returncode'] == 0, 'Handled pipeline and absent group')
        child = json_read(run / 'controller_result.json')
        need(child['candidate_id'] == ID and child['handled_candidate_outcome'] and child['all_workers_absent'], 'Complete producer outcome')
        score = json_read(run / 'score.json', 1000000)
        need(pin(read(run / 'score.json', 1000000))['sha256'] == child['result_sha256'], 'Full score already durable')
        result.update(status='passed', result_status=child['status'], result_sha256=child['result_sha256'],
                      unit_status=child['unit_status'], outcome_commit_sha256=child['outcome_commit_sha256'],
                      private_grade_dispatched=child['private_grade_dispatched'], private_reference_reads=child['private_reference_reads'],
                      candidate_program_executed=child['candidate_program_executed'])
    except BaseException as error:
        result.update(status='operator_error', error=repr(error)[:2000])
        # Dispatch may have happened even if the controller could not return.
        if (run / 'metadata/ordinary/resource_ownership.json').exists():
            result['private_grade_dispatched'] = True
            result['private_reference_reads'] = None
    finally:
        cleanup_alarm()
        try:
            group = lib['owner'].stop(run / 'controller', min(END - .5, time.monotonic() + 6), process) if (run / 'controller').exists() else {'absence_verified': True, 'never_activated': True}
        except BaseException as error:
            group = {'absence_verified': False, 'error': repr(error)[:2000]}
        if 'bootstrap_returncode' in group: result['controller_process_reaped'] = True
        result['group'] = group
        result['all_activated_groups_absent'] = group['absence_verified']
        try:
            need(group['absence_verified'], 'Stop group before exact owned-resource recovery')
            owned, errors = inventory(run)
            result['inventory_errors'] = errors
            cleanup = []
            for folder, item in owned:
                try:
                    cleanup.append(recover(run, folder, item, lib['BaseEngine'](END - .2, folder, budget), budget))
                except BaseException as error:
                    cleanup.append({'name': item.get('name'), 'absence_verified': False, 'error': repr(error)[:2000]})
            result['cleanup'] = cleanup
            result['all_owned_absent'] = not errors and all(row['absence_verified'] for row in cleanup)
            if result['status'] == 'passed':
                need(len(cleanup) == (4 if result['private_grade_dispatched'] else 3), 'Exact three/four owned resources')
        except BaseException as error:
            result.update(status='operator_error', cleanup_error=repr(error)[:2000])
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        elapsed = time.monotonic() - START
        charge = max(WHOLE, elapsed)
        if not result['all_owned_absent'] or not result['all_activated_groups_absent'] or not result['controller_process_reaped']:
            result['status'] = 'cleanup_unverified'
        elif elapsed >= WHOLE:
            result['status'] = 'deadline_exceeded'
        result.update(wall_seconds=elapsed, wall_seconds_scope='through cleanup before receipt write',
                      charged_seconds=charge, prior_known_seconds=review['prior_known_seconds'],
                      known_after_seconds=review['prior_known_seconds'] + charge,
                      lifetime_cost_complete=False, automatic_retry=False,
                      retained_bytes_before_receipt=budget.used())
        save(run / 'outer_receipt.json', result, budget, 150000)
    print(json.dumps({'status': result['status'], 'result_status': result.get('result_status'),
                      'known_after_seconds': result['known_after_seconds']}), flush=True)
    return 0 if result['status'] == 'passed' else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--program', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--other-reserve-bytes', type=int, required=True)
    args = p.parse_args()
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'No conflicting outer timer')
    old = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, work_alarm)
    signal.setitimer(signal.ITIMER_REAL, max(.001, WORK - time.monotonic()))
    run = args.output.absolute()
    started = False
    prior = None
    error = None
    execution_entered = False
    admitted_state = {}
    try:
        need('..' not in run.parts and run == run.resolve() and run.is_relative_to(ROOT / 'artifacts-build') and run != ROOT / 'artifacts-build' and run.parent.is_dir()
             and not run.exists() and all(not q.is_symlink() for q in (run, *run.parents)), 'Fresh canonical output')
        run.mkdir(mode=0o700)
        started = True
        write(run / 'started.json', {'candidate_id': ID, 'whole_seconds': WHOLE, 'status': 'preflight_started'})
        review, frozen, program, admitted, capacity = admit(args, run, admitted_state)
        prior = review['prior_known_seconds']
        execution_entered = True
        return execute(args, run, frozen, review, program, admitted, capacity)
    except BaseException as failure:
        error = repr(failure)[:2000]
        raise
    finally:
        cleanup_alarm()
        if started and not (run / 'outer_receipt.json').exists():
            prior = admitted_state.get('prior_known_seconds', prior)
            charge = max(WHOLE, time.monotonic() - START)
            write(run / ('finalization_failure.json' if execution_entered else 'preflight_failure.json'),
                {'candidate_id': ID, 'runtime_id':RUNTIME_ID, 'status': 'failed_attempt_preserved',
                 'error': error, 'charged_seconds': charge, 'prior_known_seconds': prior,
                 'known_after_seconds': None if prior is None else prior + charge,
                 'execution_entered':execution_entered, 'dispatch_extent_unknown':execution_entered,
                 'source_freeze_sha256':admitted_state.get('source_freeze_sha256'),
                 'root_authority_and_prior_admitted':admitted_state.get('root_authority_and_prior_admitted',False),
                 'never_activated':not execution_entered, 'controller_process_reaped':not execution_entered,
                 'candidate_program_executed': None if execution_entered else False,
                 'private_reference_reads': None if execution_entered else 0,
                 'all_owned_absent':not execution_entered, 'all_activated_groups_absent':not execution_entered})
        # Keep the absolute hard timer through terminal emission and return.
        need(time.monotonic() < END, 'Whole-stage deadline through final return')


if __name__ == '__main__':
    raise SystemExit(main())

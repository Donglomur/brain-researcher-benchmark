#!/usr/bin/env python3
"""One separately granted sequential program attempt over existing ERP lifecycle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode = True
from common import HERE, ROOT, Engine, HostBudget, owner, module, need, regular, pin, lock, strict, save, sync, assets, pinned
import choice_recovery as recovery

START = time.monotonic(); WHOLE = 180; WORK = 150; END = START + WHOLE
RESERVE = 16000000; MANAGED = 15000000


def terminal(*unused): os._exit(124)
def cleanup_alarm():
    signal.signal(signal.SIGALRM, terminal); signal.setitimer(signal.ITIMER_REAL, max(.001, END - time.monotonic()))
def work_alarm(*unused):
    cleanup_alarm(); raise TimeoutError('Work deadline; exact cleanup only')


def method(body):
    value = strict(body)
    need(type(value) is dict and set(value) == {'schema_version', 'method_id', 'method_description', 'training_policy', 'limitations'}
         and type(value['schema_version']) is int and value['schema_version'] == 1, 'Exact method declaration')
    need(all(type(v) is str and 0 < len(v) <= 4096 for k, v in value.items() if k != 'schema_version'), 'Bounded method text')
    return value


def source_gate(args):
    raw = regular(HERE / 'FREEZE.json', 500000); freeze = strict(raw)
    need(regular(HERE / 'SOURCE_CLOSURE_PROPOSAL.json', 500000) == raw, 'Exact reviewed held source proposal')
    review = strict(regular(args.review, 65536)); digest = hashlib.sha256(raw).hexdigest()
    run = args.output.absolute()
    need(review['decision'] == 'authorize_one_neural059_sequential_program_attempt' and review['execution_authority'] is True
         and review['freeze_sha256'] == digest and review['whole_seconds'] == WHOLE and review['work_seconds'] == WORK
         and review['cleanup_seconds'] == 30 and review['artifact_reserve_bytes'] == RESERVE
         and review['control'] == args.control and review['other_reserve_bytes'] == args.other_reserve_bytes
         and review['output_path'] == str(run.relative_to(ROOT)), 'Exact prospective single-attempt root authority')
    need(type(args.other_reserve_bytes) is int and args.other_reserve_bytes >= 102000000, 'Standing unrelated reservation retained')
    need(run.parent == ROOT / 'artifacts-build' and not run.exists() and '..' not in run.parts
         and all(not p.is_symlink() for p in (run, *run.parents)), 'Fresh exact direct output')
    for relative, expected in freeze['files'].items():
        need(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'Relative source closure')
        need(pin(ROOT / relative, 3000000) == expected, 'Exact source closure: ' + relative)
    peer = pinned(review['independent_source_review'], 300000)
    need(peer['decision'] == 'go_for_neural059_sequential_open_prediction_v1' and peer['source_proposal_sha256'] == digest,
         'Independent causal-boundary/source review of exact successor')
    if args.control == 'ordinary':
        from qualification import validate
        qualification = validate(pinned(review['accepted_qualification'], 65536), digest)
        need(type(review['prior_known_seconds']) in (int, float)
             and review['prior_known_seconds'] >= qualification['latest_control_known_seconds'],
             'Ordinary attempt retains every qualification control charge')
    return review, freeze


def prior_gate(review, freeze_sha):
    prior = review['prior_receipt']; value = pinned(prior, 300000)
    initial = assets()['reference_admission']
    if prior == initial:
        need(value['decision'] == 'admit_one_bounded_development_reference_from_independently_verified_saved_outputs'
             and value['known_family_allowances_seconds_after'] == 2100 and value['historical_lifetime_complete'] is False,
             'Exact independently admitted reference after preserved outer failure')
        previous = 2100
    else:
        need(value['candidate_id'] == 'NEURAL-059' and value['task_family'] == 'brainwide_prechoice_sequential_open_prediction'
             and value['source_freeze_sha256'] == freeze_sha and value['historical_lifetime_complete'] is False
             and value['all_owned_absent'] is True and value['all_activated_groups_absent'] is True
             and value['charged_seconds'] >= WHOLE, 'Actual immediately preceding closed attempt, including failures')
        previous = value['known_family_allowances_seconds_after']
    need(review['prior_known_seconds'] == previous and review['prospective_after_seconds'] == previous + WHOLE,
         'No allowance reset or free control attempt')
    allocation = pinned(review['budget_allocation'], 65536)
    need(all(allocation.get(k) == v for k, v in {'candidate_id': 'NEURAL-059', 'authorized': True,
         'whole_seconds': WHOLE, 'work_seconds': WORK, 'cleanup_seconds': 30, 'own_reserve_bytes': RESERVE,
         'other_reserve_bytes': review['other_reserve_bytes'], 'prior_known_seconds': previous,
         'prospective_after_seconds': previous + WHOLE, 'historical_lifetime_complete': False}.items()),
         'Separately allocated full control/ordinary attempt')
    return previous


def storage(review, deadline):
    policy = pinned(review['capacity_policy'], 65536)
    need(policy['scope_id'] == 'neural059_sequential_open_prediction_v1' and policy['execution_authority'] is False
         and policy['allocation'] is False and policy['own_reserve_bytes'] == RESERVE
         and policy['free_after_reserves_floor_bytes'] == 15000000000
         and policy['other_reserve_bytes_minimum'] == 102000000
         and policy['managed_file_bytes_cap'] == MANAGED
         and policy['filesystem_rounding_reserve_bytes'] == 1000000
         and policy['maximum_managed_entries'] == 200 and policy['filesystem_fragment_bytes_cap'] == 4096
         and policy['whole_seconds'] == WHOLE and policy['work_seconds'] == WORK and policy['cleanup_seconds'] == 30
         and policy['fixed_existing_image_metadata_bytes'] == 1339047331
         and type(policy['aggregate_ceiling_bytes']) is int and policy['aggregate_ceiling_bytes'] >= 18000000000,
         'Exact root-pinned prospective task policy with invariant time/resources; never inherited from another stage')
    reply = subprocess.run(['/usr/bin/du', '-sk', str(ROOT)], capture_output=True, text=True,
                           timeout=min(5, max(.001, deadline - time.monotonic())), check=True)
    need(len(reply.stdout) < 1024 and len(reply.stderr) < 1024, 'Bounded current capacity snapshot')
    project = int(reply.stdout.split()[0]) * 1024; fs = os.statvfs(ROOT); free = fs.f_bavail * fs.f_frsize
    need(0 < fs.f_frsize <= 4096, 'One-megabyte stage rounding reserve for at most200 entries')
    reserve = RESERVE + review['other_reserve_bytes']
    need(project + 1339047331 + reserve <= policy['aggregate_ceiling_bytes'] and free - reserve >= 15000000000,
         'Fresh measured capacity gate including full reservations')
    return {'project_allocated_bytes': project, 'free_bytes': free, 'image_metadata_bytes': 1339047331,
            'image_metadata_is_not_physical_Docker_disk_measurement': True, 'own_reserve_bytes': RESERVE,
            'other_reserve_bytes': review['other_reserve_bytes'], 'aggregate_ceiling_bytes': policy['aggregate_ceiling_bytes'],
            'fragment_bytes': fs.f_frsize, 'capacity_policy': review['capacity_policy']}


def control_check(label, child, run):
    if label == 'ordinary': return None
    score = strict(regular(run / 'grade/stdout.json', 131072))
    if label == 'malformed':
        need(child['status'] == 'invalid_submission' and child['committed_prediction_count'] == 0
             and score['private_label_decodes'] == score['reference_probability_decodes'] == 0,
             'Malformed boolean rejected publicly before private reads')
    else:
        need(child['status'] == 'scored' and child['committed_prediction_count'] == 93
             and child['candidate_chronology_verified'] is True, 'Complete arbitrary valid control')
        if label in ('uniform', 'private_probe'):
            need(abs(score['metrics']['logloss'] - 0.6931471805599453) <= 1e-15
                 and score['metrics']['brier'] == 0.25, 'Analytic uniform control, no success floor')
        if label == 'private_probe':
            need(regular(run / 'candidate/stderr.bin', 32768) == b'NEURAL059_EXACT_CALIBRATION_AND_CURRENT_STREAM_ONLY\n',
                 'Physical private/future-path exclusion probe')
        if label == 'reference':
            # The disclosed source fresh-fits public data. Exact fit counters are
            # checked against its terminal diagnostic, not inferred for arbitrary programs.
            records = [strict(body) for body in regular(run / 'candidate/stderr.bin', 32768).splitlines()]
            need(records and all(r['control'] == 'fresh_SBHN_reference' for r in records), 'Exact disclosed reference diagnostics')
            diagnostic = records[-1]; operations = diagnostic['operations']
            need(diagnostic['stage'] == 'complete' and operations['logistic_fits_attempted'] == operations['logistic_fits_completed'] == 4
                 and operations['scalers_attempted'] == operations['scalers_completed'] == 2
                 and operations['query_predictions'] == 93 and len(diagnostic['fits']) == 4
                 and all(row['status'] == 'accepted' for row in diagnostic['fits']),
                 'Fresh public calibration reference reconstruction')
    return {'label': label, 'passed': True, 'candidate_fits': 4 if label == 'reference' else 0,
            'ordinary_accuracy_floor': False, 'implementation_familiar_control': True}


def execute(args, review, freeze):
    run = args.output.absolute(); budget = HostBudget(run, MANAGED, 2000000)
    folder = run / 'controller'; process = None; work_end = START + WORK
    freeze_sha = pin(HERE / 'FREEZE.json', 500000)['sha256']; previous = prior_gate(review, freeze_sha)
    result = {'candidate_id': 'NEURAL-059', 'task_family': 'brainwide_prechoice_sequential_open_prediction',
              'status': 'started', 'source_freeze_sha256': freeze_sha, 'control': args.control,
              'prior_known_seconds': previous, 'private_targets_decoded': False,
              'trusted_count_decode_extent_unknown': False, 'private_read_extent_unknown': False,
              'candidate_source': review['program'], 'candidate_method': review['method'],
              'all_owned_absent': False, 'all_activated_groups_absent': False, 'candidate_fit_count': None,
              'new_reference_fits': 0, 'model_API_calls': 0, 'host_neural_array_decodes': 0,
              'historical_lifetime_complete': False, 'historical_total_seconds': None,
              'automatic_retry': False, 'new_benchmark_IDs': 0, 'research_qualified': False}
    try:
        result['storage'] = storage(review, work_end)
        for name, path, cap in (('program.py', args.program, 65536), ('method.json', args.method, 16384)):
            body = regular(path, cap); need(lock(body) == review[name.split('.')[0]], 'Exact precommitted program/method')
            if name == 'method.json': method(body)
            budget.write(run / name, body, mode=0o444)
            fd = os.open(run / name, os.O_RDONLY | os.O_NOFOLLOW)
            try: os.fsync(fd)
            finally: os.close(fd)
        sync(run)
        save(run / 'source_commit.json', {'program': review['program'], 'method': review['method'],
                                          'before_trusted_projection': True}, budget)
        if args.control != 'ordinary':
            expected = assets()['controls'][args.control]
            need(review['program'] == {k: expected['program'][k] for k in ('bytes', 'sha256')}
                 and review['method'] == {k: expected['method'][k] for k in ('bytes', 'sha256')}, 'Exact disclosed control')
        folder.mkdir(mode=0o700)
        relative = str((HERE / 'controller.py').relative_to(ROOT))
        source = {'path': relative, **freeze['files'][relative]}
        need(work_end - time.monotonic() >= 135, 'Full130seconds phase allowances plus controller setup')
        # Once controller activation is attempted, absence of its final receipt
        # cannot establish that trusted data decoding never happened.
        result.update(private_targets_decoded=None, private_read_extent_unknown=True,
                      trusted_count_decode_extent_unknown=True)
        process = owner.launch([sys.executable, str(HERE / 'controller.py'), '--run', str(run), '--deadline', str(work_end)],
                               folder, min(160, work_end - time.monotonic() + 1), source)
        helper = module(ROOT / 'authoring/paper-language-project/phase1-numerical-v1/run_outer.py', '_choice_open_wait')
        done = helper.completed(folder, work_end, owner)
        stopped = owner.stop(folder, min(END - 5, time.monotonic() + 2), process); process = None
        need(stopped['absence_verified'], 'Controller group absent before final resource recovery')
        child = strict(regular(run / 'result.json', 65536))
        result.update(status=child['status'], controller_result=pin(run / 'result.json', 65536),
                      private_targets_decoded=child['private_targets_decoded'], score=child.get('score'),
                      private_read_extent_unknown=child['private_targets_decoded'] is None,
                      trusted_count_decode_extent_unknown=child['trusted_count_decode_extent_unknown'],
                      candidate_chronology_verified=child.get('candidate_chronology_verified', False))
        need(done['returncode'] == 0, 'Completed controller disposition, all failure evidence retained')
        checked = control_check(args.control, child, run)
        if checked is not None: result.update(control_checks=checked, candidate_fit_count=checked['candidate_fits'])
    except BaseException as error:
        result.update(status='failed_preserved', error=repr(error)[:1500])
    finally:
        cleanup_alarm()
        try: stopped = owner.stop(folder, min(END - 4, time.monotonic() + 3), process) if folder.exists() else {'absence_verified': True, 'never_activated': True}
        except BaseException as error: stopped = {'absence_verified': False, 'error': repr(error)[:1000]}
        result['all_activated_groups_absent'] = stopped['absence_verified']
        # Keep potentially two65KB captured streams in one separate bounded
        # record, never duplicated inside the compact outer receipt.
        try:
            result['group_cleanup'] = save(run / 'group_cleanup.json', stopped, budget, 150000)
        except BaseException as error:
            result['group_cleanup_retention_error'] = repr(error)[:1000]
            result['status'] = 'failed_preserved'
        try:
            need(stopped['absence_verified'], 'Controller absence before exact independent Docker recovery')
            rows = recovery.recover_all(run, Engine(END - .5, run, budget), budget)
            result['cleanup'] = rows; result['all_owned_absent'] = all(r['absence_verified'] for r in rows)
            result['cleanup_evidence_retention_failed'] = any(r.get('evidence_retention_failed', False) for r in rows)
            if result['cleanup_evidence_retention_failed']: result['status'] = 'failed_preserved'
            if result['status'] in ('scored', 'invalid_submission'): need(len(rows) == 3, 'Exactly preparation/candidate/grade resources')
        except BaseException as error: result.update(all_owned_absent=False, cleanup_error=repr(error)[:1000])
        elapsed = time.monotonic() - START; charge = max(WHOLE, elapsed)
        result.update(wall_seconds_before_receipt=elapsed, charged_seconds=charge,
                      known_family_allowances_seconds_after=previous + charge, retained_bytes_before_receipt=budget.used())
        entries = list(run.rglob('*'))
        need(len(entries) + 2 <= 200 and all(not p.is_symlink() for p in entries),
             'Declared200entry scope reserves original outer receipt and possible failure record')
        if not result['all_owned_absent'] or not result['all_activated_groups_absent']: result['status'] = 'cleanup_unverified'
        if elapsed >= WHOLE: result['status'] = 'deadline_exceeded'
        save(run / 'outer_receipt.json', result, budget, 131072)
    print(json.dumps({'status': result['status'], 'charged_seconds': result['charged_seconds']}), flush=True)
    return int(result['status'] not in ('scored', 'invalid_submission'))


def main():
    parser = argparse.ArgumentParser()
    for name in ('program', 'method', 'review', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--other-reserve-bytes', type=int, required=True)
    parser.add_argument('--control', choices=('ordinary', 'reference', 'uniform', 'malformed', 'private_probe'), default='ordinary')
    args = parser.parse_args(); need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'No inherited timer')
    signal.signal(signal.SIGALRM, work_alarm); signal.setitimer(signal.ITIMER_REAL, max(.001, START + WORK - time.monotonic()))
    started = False; finalized = False
    try:
        review, freeze = source_gate(args)
        run = args.output.absolute(); run.mkdir(mode=0o700); started = True
        budget = HostBudget(run, MANAGED, 2000000)
        save(run / 'charge_intent.json', {'candidate_id': 'NEURAL-059', 'whole_seconds': WHOLE,
                                        'prior_known_seconds': review['prior_known_seconds'], 'automatic_retry': False}, budget, 16384)
        for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'NUMBA_NUM_THREADS'):
            os.environ[key] = '2'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        code = execute(args, review, freeze); finalized = True
        return code
    finally:
        cleanup_alarm()
        if started and not finalized:
            save(args.output / 'outer_failure.json', {'status': 'failed_preserved', 'charged_seconds': max(WHOLE, time.monotonic() - START),
                 'prior_known_seconds': review['prior_known_seconds'], 'cleanup_claim': 'unknown; inspect owned journals',
                 'original_outer_path_present': (args.output / 'outer_receipt.json').exists(),
                 'original_outer_completion_or_durability_not_assumed': True,
                 'historical_lifetime_complete': False, 'automatic_retry': False}, HostBudget(args.output, MANAGED, 2000000), 16384)


if __name__ == '__main__':
    raise SystemExit(main())

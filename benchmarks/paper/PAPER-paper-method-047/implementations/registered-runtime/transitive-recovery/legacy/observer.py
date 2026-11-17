"""Owned whole-command observer for the immutable released117 controller."""
import time
ORIGIN = time.monotonic()
import signal
import sys
FINAL_ENDPOINT = ORIGIN + 60


def expired(*_):
    raise TimeoutError('original whole-command endpoint')


def terminated(*_):
    raise InterruptedError('owned observer termination')


def enter_startup():
    # Only time/signal/sys are imported before the active startup enclosure.
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError('no inherited timer')
    saved = (signal.getsignal(signal.SIGALRM), signal.getsignal(signal.SIGTERM))
    signal.signal(signal.SIGALRM, expired)
    signal.signal(signal.SIGTERM, terminated)
    remaining = ORIGIN + 60 - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('original startup endpoint')
    signal.setitimer(signal.ITIMER_REAL, remaining)
    return saved


STARTUP = enter_startup() if __name__ == '__main__' else None
import argparse
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).absolute().parent))
import common as U
import adapter as A


def space(control, output, other):
    used = control.inventory(output, U.TOTAL, 30000)[2] if output.exists() else 0
    available = control.shutil.disk_usage(output if output.exists() else output.parent).free
    U.need(available >= control.FLOOR + other + U.TOTAL - used, 'full33.02GB plus floor and OTHER')
    if (output / 'observer').exists():
        control.inventory(output / 'observer', U.META - 1000000, 256)


def execute(plan, binding, control, process, capture, expected, origin, owned):
    end = origin + plan['whole']
    U.need(time.monotonic() < origin + 60, 'source capture and startup inside original preflight')
    normal_end, cleanup_end = end - 120, end - 60
    U.need(time.monotonic() < normal_end, 'remaining original child interval')
    capture.end = end
    signal.setitimer(signal.ITIMER_REAL, end - time.monotonic())
    space(control, plan['output'], plan['selection']['other_reserved_bytes'])
    plan['output'].mkdir(mode=0o700)
    owned['output'] = plan['output']
    (plan['output'] / 'observer').mkdir(mode=0o700)
    metadata = plan['output'] / 'observer'
    start_pin = capture.write(metadata / 'START.json', {'schema': 'gcamp8_full117_outer_start_v1', 'task_id': U.TASK,
        'adapter_source': expected, 'controller_source': plan['cfg']['source'], 'programs': plan['programs'],
        'owned_attempt_output': str(plan['output']), 'controller_output': str(plan['output'] / 'controller'),
        'controller_selection': {'path': str(plan['controller_operand'][0]), **plan['controller_operand'][1]},
        'selected_metadata': [{'path': str(path), **operand_pin} for path, operand_pin in plan['operands']],
        'pair_descriptor': plan['bundle'], 'whole_seconds': plan['whole'], 'origin_monotonic': origin,
        'normal_child_endpoint': normal_end, 'owned_cleanup_endpoint': cleanup_end, 'final_endpoint': end,
        'child_internal_origin_forwarded': False, 'outer_original_clock_enforced': True,
        'observer_reserve_bytes': U.META, 'total_retention_bytes': U.TOTAL,
        'private_grading_authorized': True, 'qualification_inherited': False,
        'failure_custody_complete': False,
        'transitive_host_groups_and_daemon_resources_require_separate_failure_qualification': True})
    argv = A.child_argv(plan, binding)
    capture.reads += 65536  # Reserve the supervisor's complete combined pipe cap.
    U.need(capture.reads <= U.READ_CAP, 'whole metadata plus child stream reserve')
    try:
        stdout, observed = process.run(argv, normal_end, cleanup_end,
            {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'})
    except process.ChildFailure as error:
        capture.write(metadata / 'CHILD_FAILURE.json', {'schema': 'gcamp8_owned_child_failure_v1',
            'process': error.record, 'collection_accepted': False,
            'owned_attempt_output': str(plan['output']), 'controller_output_retained': str(plan['output'] / 'controller'),
            'resource_identity_evidence_retained': 'controller/cases/NNNN/INTENT-ROLE.json and available CASE_CLOSED/OUTCOME records; no fabricated missing identities',
            'daemon_owned_resources': 'unknown_after_failed_outer_child; never inferred absent',
            'independent_host_process_groups': 'unknown_after_failed_outer_child; controller_PGID_absence_is_insufficient',
            'failure_custody_complete': False,
            'automatic_retry': False, 'unrelated_resources_may_not_be_stopped': True})
        raise
    U.need(time.monotonic() < cleanup_end, 'child closure inside original cleanup endpoint')
    alarm = signal.getitimer(signal.ITIMER_REAL)
    U.need(alarm[1] == 0 and 0 < alarm[0] <= max(0, end - time.monotonic()) + .05,
           'original alarm resumed after owned cleanup')
    process_pin = capture.write(metadata / 'CHILD_EXIT.json', observed)
    completed = A.accept(plan, capture, stdout, observed)
    for path, expected_operand in plan['operands']:
        capture.read(path, 65536, expected_operand)
    A.sources(capture, expected)
    space(control, plan['output'], plan['selection']['other_reserved_bytes'])
    return capture.write(metadata / 'OBSERVED_COLLECTION.json', {
        'schema': 'gcamp8_full117_outer_collection_v1', 'task_id': U.TASK,
        'status': 'child_natural_zero_observed_pending_external_wrapper_exit',
        'adapter_source': expected, 'controller_source': plan['cfg']['source'],
        'start_record': start_pin, 'child_exit': process_pin, **completed,
        'neurons': 117, 'outputs_per_arm': 234, 'total_outputs': 468,
        'whole_seconds': plan['whole'], 'elapsed_before_publication': time.monotonic() - origin,
        'child_internal_origin_forwarded': False, 'outer_original_clock_enforced': True,
        'observer_reads_reserved_bytes': capture.reads, 'observer_writes_before_publication': capture.writes,
        'historical105_reproduced': False, 'runtime_qualification_added': False,
        'scientific_qualification_added': False, 'external_wrapper_natural_exit_required': True,
        'failure_custody_complete': False})


def main(argv=None):
    global FINAL_ENDPOINT
    owned, capture, saved = {}, None, STARTUP
    end = ORIGIN + 60
    code = 1
    try:
        if saved is None:
            saved = enter_startup()
        U.need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'isolated no-site nonwriting wrapper')
        U.need(type(sys.pycache_prefix) is str and bool(sys.pycache_prefix), 'explicit disabled cache prefix')
        cache = U.literal(sys.pycache_prefix)
        U.need(not os.path.lexists(cache), 'absent disabled cache')
        U.need(signal.getsignal(signal.SIGALRM) is expired and signal.getsignal(signal.SIGTERM) is terminated,
               'startup handlers still owned')
        U.need(time.monotonic() < end, 'original startup endpoint')
        signal.setitimer(signal.ITIMER_REAL, end - time.monotonic())
        p = argparse.ArgumentParser(description=__doc__)
        for k in ('program', 'output', 'review', 'source-sha256'):
            p.add_argument('--' + k, required=True)
        for k in ('source-bytes', 'other-reserve-bytes'):
            p.add_argument('--' + k, type=int, required=True)
        args = p.parse_args(argv)
        capture = U.Capture(end)
        expected = U.descriptor({'bytes': args.source_bytes, 'sha256': args.source_sha256}, 65536)
        binding, control, process = A.sources(capture, expected)
        plan = A.bind(args, capture, expected, binding, control)
        end = ORIGIN + plan['whole']
        FINAL_ENDPOINT = end
        result = execute(plan, binding, control, process, capture, expected, ORIGIN, owned)
        U.need(signal.getsignal(signal.SIGALRM) is expired and signal.getsignal(signal.SIGTERM) is terminated,
               'same owned outer signal handlers')
        U.need(not os.path.lexists(cache) and sys.pycache_prefix == str(cache), 'cache stayed absent')
        capture.tick()
        print(U.encoded(result).decode(), end='', flush=True)
        capture.tick()
        code = 0
    except BaseException as error:
        if capture is not None and owned.get('output') is not None:
            try:
                capture.write(owned['output'] / 'observer' / 'FAILURE.json', {
                    'error_type': type(error).__name__, 'collection_accepted': False,
                    'partial_artifacts_and_costs_preserved': True, 'automatic_retry': False,
                    'owned_attempt_output': str(owned['output']),
                    'controller_output_retained': str(owned['output'] / 'controller'),
                    'resource_intent_and_closure_records_preserved': True,
                    'observer_reads_reserved_bytes': capture.reads,
                    'observer_writes_reserved_bytes': capture.writes,
                    'daemon_owned_resources': 'unknown_unless_full_natural_child_admission',
                    'independent_host_process_groups': 'unknown_unless_full_natural_child_admission',
                    'failure_custody_complete': False})
            except BaseException:
                pass
    finally:
        if saved is not None:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, saved[0])
                signal.signal(signal.SIGTERM, saved[1])
            except BaseException:
                code = 1
    return code if time.monotonic() < end else 1


if __name__ == '__main__':
    result = main()
    raise SystemExit(result if time.monotonic() < FINAL_ENDPOINT else 1)

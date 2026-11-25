"""Operator-only numerical grade of an already closed complete NEURAL-021 run.

No candidate, container, model, signal preparation or reference run is launched.
Original full92 observer admission is retained; current scoring has a pinned numerical guard.
External operator selection and independent observed exit evidence are mandatory;
hashes identify their bytes and do not establish who authored those observations.
"""
import time
ORIGIN = time.monotonic()
CPU_ORIGIN = time.process_time()
SOURCE_READ_RESERVATIONS = 0
CURRENT_BUDGET = None
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import sys
import types

PRODUCER = {'bytes': 1799, 'sha256': 'df2bb2080cb2112b159fe93b05ff288bf2cf8dee6ab701f89a3ff03168ef0e35'}
COMMON = {'bytes': 7829, 'sha256': 'fbeddddac17fe9c4e55344858222c4a55b0fa1c12bc4902b35a3922b2db2c654'}
ORIGINAL_SCORER = {'bytes': 3290, 'sha256': '4438468f22511986c71fda03621b207cf82c523ee910e8bc6760c174cb16bcf4'}
SCORER = {'bytes': 3567, 'sha256': '320234c9e89a6c8c282d88e273a629d82217b35a8714244dee52097625e60f01'}
INTERFACE = {'bytes': 3533, 'sha256': 'c748bdb0386713d505e1d5d79bec51645263b859471011df81f205168a6e61e2'}
SCOPE = {'training_trials': 272, 'query_trials': 92, 'active_queries': 52,
         'perturbation_queries': 40, 'units': 65, 'time_bins': 30,
         'history_bins': 6, 'velocity_axes': 2}
CAPS = {'selection': 32768, 'external': 8192, 'outer_review': 32768,
        'grade_review': 32768, 'authority': 32768, 'cases': 32768,
        'private_targets': 1048576}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def ordinary(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts and str(p) == str(path),
         'canonical absolute operator path')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'no symlink operands')
    return p


def initial_capture(path, expected, cap, deadline):
    """Bounded ordinary-file bootstrap, before executing frozen common.py."""
    global SOURCE_READ_RESERVATIONS
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= cap
         and type(expected['sha256']) is str
         and re.fullmatch('[0-9a-f]{64}', expected['sha256']), 'bootstrap pin')
    need(time.monotonic() < deadline, 'bootstrap deadline')
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1
             and a.st_size == expected['bytes'], 'bootstrap ordinary exact extent')
        SOURCE_READ_RESERVATIONS += a.st_size + 1
        parts = []
        left = a.st_size + 1
        while left:
            need(time.monotonic() < deadline, 'bootstrap capture deadline')
            part = os.read(fd, min(65536, left))
            if not part:
                break
            parts.append(part)
            left -= len(part)
        raw = b''.join(parts)
        z = os.fstat(fd)
        n = p.lstat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size',
                  'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(a, k) == getattr(z, k) == getattr(n, k) for k in fields)
             and pin(raw) == expected, 'stable authenticated bootstrap')
        return raw
    finally:
        os.close(fd)


def module(raw, path, **bindings):
    value = types.ModuleType('neural021_grade_' + Path(path).stem)
    value.__file__ = str(path)
    value.__dict__.update(bindings)
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value


def profile(c, value):
    fields = {'reads', 'output_bytes', 'wall_seconds', 'cpu_seconds', 'host_memory_bytes'}
    c.need(type(value) is dict and set(value) == fields
           and all(type(x) is int and x > 0 for x in value.values()),
           'exact finite grading resource profile')
    c.need(value['reads'] <= 67108864 and value['output_bytes'] <= 65536
           and value['wall_seconds'] <= 600 and value['cpu_seconds'] <= 120
           and value['host_memory_bytes'] == 134217728,
           'bounded grading interface ceilings; not measured feasibility')
    return value


class Budget:
    def __init__(self, c, limits, origin, cpu_origin, already_read=0):
        self.c = c
        self.limits = limits
        self.deadline = origin + limits['wall_seconds']
        self.cpu_origin = cpu_origin
        self.reads = already_read
        self.target_captures = 0
        self.read(0)

    def tick(self):
        self.c.before(self.deadline)
        self.c.need(time.process_time() - self.cpu_origin <= self.limits['cpu_seconds'],
                    'whole grading CPU elapsed bound')

    def read(self, size):
        self.c.need(type(size) is int and size >= 0
                    and self.reads + size <= self.limits['reads'], 'whole grading read ceiling')
        self.reads += size
        self.tick()

    def capture(self, path, cap, expected=None):
        return self.c.capture(path, cap, expected, self.tick, self.read)


def descriptor(c, value, cap):
    c.need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'},
           'exact operator content descriptor')
    pp = c.only_pin(value)
    c.need(pp['bytes'] <= cap and type(value['path']) is str, 'bounded descriptor')
    ordinary(value['path'])
    return pp


def finite(c, value, label, minimum=0):
    try:
        okay = type(value) in (int, float) and math.isfinite(value) and value >= minimum
    except OverflowError:
        okay = False
    c.need(okay, label)
    return value


def admit_external(c, external, selection, request, bodies, root):
    """Require exact original worker closure and an independently selected outer exit."""
    c.need(type(external) is dict and external.get('schema') == 'neural021_full92_external_v1'
           and external.get('status') == 'complete_unqualified'
           and external.get('source') == PRODUCER
           and external.get('selection') == c.only_pin(request['selection'])
           and external.get('attempt') == str(root), 'same completed original observer')
    for key in ('scientific_qualified', 'runtime_qualified', 'numerical_grading_performed',
                'nested_cli_and_native_recovery_may_be_required', 'automatic_retry'):
        c.need(external.get(key) is False, 'unchanged unqualified closed producer status')
    c.need(external.get('full92_source_scope') is True and external.get('error_type') is None,
           'complete source panel without observer failure')
    origin = finite(c, external['origin_monotonic'], 'original monotonic origin')
    whole = finite(c, external['whole_deadline'], 'original whole deadline')
    outer = finite(c, external['outer_deadline'], 'original outer deadline')
    c.need(whole == origin + selection['whole_seconds'] and outer == whole + 60,
           'original immutable producer deadlines')
    elapsed = finite(c, external['elapsed_before_publication'], 'original publication elapsed')
    c.need(elapsed < selection['whole_seconds'], 'no success in failure-only reserve')
    child = external['child']
    c.need(type(child) is dict, 'original worker process record')
    for key in ('natural_exit', 'process_reaped', 'process_group_absent', 'streams_closed'):
        c.need(child.get(key) is True, 'natural complete worker closure')
    for key in ('timed_out', 'kill_sent'):
        c.need(child.get(key) is False, 'no timed-out or forced worker')
    for key in ('error_type', 'timer_disable_error', 'timer_restore_error'):
        c.need(child.get(key) is None, 'error-free worker and timer cleanup')
    c.need(type(child.get('exit_code')) is int and child['exit_code'] == 0
           and type(child.get('pid')) is int and child['pid'] > 0,
           'integer natural worker exit and identity')
    ce = finite(c, child['elapsed_seconds'], 'worker elapsed')
    c.need(ce < selection['whole_seconds'] - 20, 'worker closed before original endpoint')
    for key in ('combined_stream_bytes', 'stdout_bytes'):
        c.need(type(child.get(key)) is int and 0 <= child[key] <= 65536,
               'original bounded complete streams')
    c.need(child['stdout_bytes'] <= child['combined_stream_bytes'], 'stream extent join')
    argv = external.get('argv')
    c.need(type(argv) is list and len(argv) == 17 and all(type(v) is str for v in argv),
           'complete original worker invocation')
    c.need(argv[1:5] == ['-I', '-S', '-B', '-X']
           and argv[5] == 'pycache_prefix=' + request['external']['path'] + '.UNUSED-PYCACHE'
           and argv[6] == str(Path(request['producer_root']) / 'worker.py')
           and argv[7] == '--source-pin' and c.parse(argv[8]) == PRODUCER
           and argv[9:12] == ['--selection', request['selection']['path'], '--selection-pin']
           and c.parse(argv[12]) == c.only_pin(request['selection'])
           and argv[13] == '--origin' and float(argv[14]) == origin
           and argv[15] == '--worker-end' and float(argv[16]) == whole - 20,
           'exact original worker source, selection and clock invocation')
    return child


def evaluate(request, adapter_pin, c, bodies, science_bodies, budget):
    """Complete grade path. Tests use invented files/bindings, unchanged validators/math.

    Production calls this only after fixed-manifest source capture; there is no CLI
    switch to substitute test bindings, targets or a source manifest.
    """
    required = {'schema', 'task_id', 'execution_selected', 'adapter_source', 'producer_source',
                'producer_root', 'science_root', 'selection', 'external', 'outer_review',
                'grade_review', 'authority', 'cases', 'private_targets', 'output', 'limits'}
    c.need(type(request) is dict and set(request) == required
           and request['schema'] == 'neural021_deferred_grade_request_v1'
           and request['task_id'] == 'NEURAL-021' and request['execution_selected'] is True,
           'separately selected complete numerical grade')
    c.need(request['adapter_source'] == c.exact_pin(adapter_pin)
           and request['producer_source'] == PRODUCER, 'exact grade and producer source')
    c.need(c.encoded(profile(c, request['limits'])) == c.encoded(budget.limits),
           'selected grading budget')
    producer_root = ordinary(request['producer_root'])
    science_root = ordinary(request['science_root'])
    for name, cap in CAPS.items():
        descriptor(c, request[name], cap)
    c.need(request['external']['bytes'] == 8192, 'complete original observer slot')
    target = ordinary(request['private_targets']['path'])
    tp = c.only_pin(request['private_targets'])
    output = ordinary(request['output'])
    early = [request[n] for n in CAPS if n != 'private_targets']
    c.need(all(target != ordinary(row['path']) and tp != c.only_pin(row) for row in early),
           'private targets cannot alias an early operand')
    c.need(not os.path.lexists(output) and output.parent.is_dir(), 'fresh existing-parent result')
    c.need(all(output != ordinary(request[n]['path']) for n in CAPS), 'output disjoint from inputs')
    c.need(not output.is_relative_to(producer_root) and not output.is_relative_to(science_root),
           'output cannot change source namespace')
    binding = c.parse(bodies['BINDINGS.json'])
    c.need(c.encoded(binding['scope']) == c.encoded(SCOPE), 'complete original geometry')
    by_name = {row['target']: row for row in binding['files']}
    c.need(c.only_pin(request['cases']) == binding['cases']
           and c.only_pin(request['private_targets']) == c.only_pin(by_name['private/data/targets.json'])
           and binding['interface'] == INTERFACE
           and c.only_pin(by_name['private/scorer.py']) == ORIGINAL_SCORER,
           'original exact public roster, private target and scientific source generation')
    c.need(pin(science_bodies['interface.py']) == INTERFACE
           and pin(science_bodies['scorer.py']) == SCORER, 'original validation and corrected current R2 core')
    policy = c.module(bodies, 'policy.py', producer_root, c=c)
    observer = c.module(bodies, 'observe.py', producer_root)
    interface = module(science_bodies['interface.py'], science_root / 'public/interface.py')
    scorer = module(science_bodies['scorer.py'], science_root / 'private/scorer.py')

    def metadata(name):
        row = request[name]
        return c.parse(budget.capture(row['path'], CAPS[name], c.only_pin(row)))

    selection = policy.selection(metadata('selection'), PRODUCER)
    root = ordinary(selection['output'])
    package = ordinary(str(Path(selection['repository']) / binding['package']))
    c.need(not target.is_relative_to(root) and not target.is_relative_to(package / 'public')
           and not output.is_relative_to(root) and not output.is_relative_to(package),
           'private target/output disjoint from candidate and public trees')
    for name in ('program', 'method_review', 'runtime_review'):
        row = selection[name]
        c.need(target != ordinary(row['path']) and tp != c.only_pin(row),
               'private target cannot alias a producer prerequisite')
    policy.reviews(selection, budget)
    grade_review = metadata('grade_review')
    expected_review = dict(schema='neural021_grade_runtime_review_v1', task_id='NEURAL-021',
        adapter_source=adapter_pin, producer_source=PRODUCER, limits=budget.limits,
        host_python=str(Path(sys.executable).resolve()), qualified_operator_only_target_boundary=True,
        original_input_method_runtime_reviews_independently_qualified=True,
        complete_grade_dependencies_and_external_CPU_RSS_enclosure_qualified=True,
        full_stdout_stderr_failure_cost_capture=True, scientific_qualified=False)
    c.need(c.encoded(grade_review) == c.encoded(expected_review),
           'independently selected exact grade runtime review')
    external = metadata('external')
    admit_external(c, external, selection, request, bodies, root)
    outer_review = metadata('outer_review')
    elapsed = finite(c, outer_review.get('elapsed_seconds'), 'independent outer elapsed')
    expected_outer = dict(schema='neural021_original_outer_exit_review_v1', task_id='NEURAL-021',
        producer_source=PRODUCER, observer_source=pin(bodies['observe.py']),
        worker_source=pin(bodies['worker.py']), selection=c.only_pin(request['selection']),
        external=c.only_pin(request['external']), attempt=str(root),
        original_origin_monotonic=external['origin_monotonic'],
        original_whole_seconds=selection['whole_seconds'], elapsed_seconds=elapsed,
        natural_exit=True, exit_code=0, process_reaped=True, process_group_absent=True,
        streams_closed=True, forced_termination=False, timer_cleanup_error=None)
    c.need(c.encoded(outer_review) == c.encoded(expected_outer)
           and external['elapsed_before_publication'] <= elapsed < selection['whole_seconds'],
           'independent natural original observer exit within unchanged success bound')
    authority = metadata('authority')
    expected_authority = dict(schema='neural021_protected_grade_selection_v1', task_id='NEURAL-021',
        adapter_source=adapter_pin, producer_source=PRODUCER,
        selection=c.only_pin(request['selection']), external=c.only_pin(request['external']),
        outer_review=c.only_pin(request['outer_review']), grade_review=c.only_pin(request['grade_review']),
        cases=c.only_pin(request['cases']), private_targets=tp, output=str(output),
        limits=budget.limits, complete_scope=SCOPE, target_generation_independently_admitted=True,
        prior_target_exposure_disclosed=True, scientific_qualified=False)
    c.need(c.encoded(authority) == c.encoded(expected_authority),
           'separately selected exact whole grade and target generation')
    terminal = dict(schema='neural021_full92_worker_v1', status='complete_unqualified',
                    source=PRODUCER, scope=SCOPE, complete=external['complete'])
    outputs, complete = observer.admit(c, root, terminal, PRODUCER, binding, selection,
                                      budget.deadline, budget.read)
    c.need(external['outputs'] == outputs and external['complete'] == complete,
           'original observer and complete artifact join')
    prediction = budget.capture(root / 'infer/submission.json', 4194304, outputs['submission.json'])
    cases_raw = budget.capture(request['cases']['path'], CAPS['cases'], c.only_pin(request['cases']))
    cases = interface.strict_json(cases_raw)
    rows = interface.validate_queries(cases)
    c.need(len(rows) == 92 and sum(r['condition'] == 'active' for r in rows) == 52
           and sum(r['condition'] == 'passive' for r in rows) == 40,
           'complete92 query roster and both exact condition counts')
    # Validate all final predictions once more before entering the private callback.
    interface.validate_submission(interface.strict_json(prediction), cases, binding['cases']['sha256'])
    opened = 0

    def load_targets():
        nonlocal opened
        c.need(opened == 0, 'exactly one protected target callback')
        budget.tick()
        opened += 1
        budget.target_captures += 1
        return interface.strict_json(budget.capture(target, CAPS['private_targets'], tp))

    result = scorer.score(prediction, cases_raw, load_targets, interface)
    c.need(opened == 1, 'complete score captured targets exactly once')
    budget.tick()
    return dict(schema='neural021_deferred_grade_result_v1', task_id='NEURAL-021',
        adapter_source=adapter_pin, producer_source=PRODUCER, complete_scope=SCOPE,
        original_selection=c.only_pin(request['selection']), original_external=c.only_pin(request['external']),
        original_complete=complete, submission=outputs['submission.json'],
        cases=c.only_pin(request['cases']), private_targets=tp, protected_target_captures=opened,
        scientific_score=result, read_reservations=budget.reads,
        requires_independent_natural_grader_exit_zero=True, runtime_qualified=False,
        scientific_qualified=False, submission_ready=False, baselines_executed=False,
        interpretation='One-session retrospective trajectory score; public-target exposure disclosed; no causal, generalization, reasoning or SOTA inference.')


def main(argv=None):
    global SOURCE_READ_RESERVATIONS, CURRENT_BUDGET
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'grade'))
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--producer-root', required=True)
    parser.add_argument('--science-root', required=True)
    parser.add_argument('--request')
    parser.add_argument('--request-bytes', type=int)
    parser.add_argument('--request-sha256')
    args = parser.parse_args(argv)
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
         'isolated no-site bytecode-free CLI required')
    deadline = ORIGIN + 120
    previous = {}
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    need(old_timer == (0.0, 0.0), 'standalone CLI; no inherited alarm')
    def stop(*_):
        raise TimeoutError('original grading clock expired or stopped')
    try:
        for number in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
            previous[number] = signal.signal(number, stop)
        signal.setitimer(signal.ITIMER_REAL, deadline - time.monotonic())
        here = ordinary(str(Path(__file__).absolute()))
        size = here.stat().st_size
        own = initial_capture(here, {'bytes': size, 'sha256': args.source_sha256}, 65536, deadline)
        adapter_pin = pin(own)
        producer_root = ordinary(args.producer_root)
        science_root = ordinary(args.science_root)
        common_raw = initial_capture(producer_root / 'common.py', COMMON, 100000, deadline)
        c = module(common_raw, producer_root / 'common.py')
        # The unchanged loader has a one-million-byte whole source ceiling.
        # Reserve it before the call so partial source failures retain a bound.
        SOURCE_READ_RESERVATIONS += 1000000
        _, bodies, source_cost = c.load(producer_root / 'SOURCE_MANIFEST.json', PRODUCER, deadline)
        c.need(pin(bodies['common.py']) == COMMON, 'same authenticated common source')
        science_bodies = {
            'interface.py': initial_capture(science_root / 'public/interface.py', INTERFACE, 100000, deadline),
            'scorer.py': initial_capture(science_root / 'private/scorer.py', SCORER, 100000, deadline)}
        cost = SOURCE_READ_RESERVATIONS
        if args.command == 'inspect':
            need(args.request is None and args.request_bytes is None and args.request_sha256 is None,
                 'inspection has no data or authority operands')
            print(json.dumps(dict(schema='neural021_grade_source_inspection_v1',
                adapter_source=adapter_pin, producer_source=PRODUCER, complete_scope=SCOPE,
                source_read_reservations=cost, private_target_captures=0,
                execution_selected=False, scientific_qualified=False), sort_keys=True))
            return 0
        need(args.request is not None and args.request_bytes is not None and args.request_sha256 is not None,
             'grade requires exact externally selected request')
        request_pin = c.exact_pin({'bytes': args.request_bytes, 'sha256': args.request_sha256})
        c.need(request_pin['bytes'] <= 65536, 'bounded grade request')
        raw = initial_capture(args.request, request_pin, 65536, deadline)
        request = c.parse(raw)
        c.need(request.get('producer_root') == str(producer_root)
               and request.get('science_root') == str(science_root), 'selected source-root operands')
        limits = profile(c, request['limits'])
        budget = Budget(c, limits, ORIGIN, CPU_ORIGIN, SOURCE_READ_RESERVATIONS)
        CURRENT_BUDGET = budget
        budget.tick()
        signal.setitimer(signal.ITIMER_REAL, budget.deadline - time.monotonic())
        value = evaluate(request, adapter_pin, c, bodies, science_bodies, budget)
        encoded = c.encoded(value)
        c.need(len(encoded) <= limits['output_bytes'], 'whole compact score result bound')
        c.save(request['output'], encoded, limits['output_bytes'], budget.tick)
        budget.tick()
        print(json.dumps({'status': 'graded_provisional_until_original_cli_exit',
                          'output': pin(encoded), 'protected_target_captures': 1,
                          'read_reservations': budget.reads}, sort_keys=True))
        return 0
    finally:
        errors = []
        for action in [lambda: signal.setitimer(signal.ITIMER_REAL, 0)] + [
                lambda n=n, h=h: signal.signal(n, h) for n, h in previous.items()]:
            try:
                action()
            except BaseException as error:
                errors.append(type(error).__name__)
        if errors:
            raise RuntimeError('signal cleanup uncertainty:' + ','.join(errors))


if __name__ == '__main__':
    try:
        code = main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__,
                          'reason': str(error), 'scientific_qualified': False,
                          'read_reservations': CURRENT_BUDGET.reads if CURRENT_BUDGET else SOURCE_READ_RESERVATIONS,
                          'protected_target_captures': CURRENT_BUDGET.target_captures if CURRENT_BUDGET else 0,
                          'elapsed_seconds': time.monotonic() - ORIGIN,
                          'cpu_seconds': time.process_time() - CPU_ORIGIN,
                          'physical_IO_or_peak_RSS_measured': False}), file=sys.stderr)
        code = 2
    raise SystemExit(code)

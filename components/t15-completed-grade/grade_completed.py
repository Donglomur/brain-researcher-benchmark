"""Operator-only successor: grade an already closed complete T15 collection.

The existing producer, collection admission and scientific kernels are unchanged.
This module launches no candidate or native work. A root-captured invocation and
separate pinned authentic-input, method, runtime, outer-exit and grading authority
are mandatory. Source construction or generated checks grant none of them.
"""
import time
ORIGIN = globals().get('_CAPTURED_LAUNCH_ORIGIN')
CAPTURED = globals().get('_CAPTURED_ADAPTER_PIN')
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import types

PRODUCER_ROOT = Path(__file__).absolute().parents[2] / 'authoring/delivery-20261105/common/remaining-builds-wave17/neural014-complete-program'
PRODUCER = {'bytes': 3665, 'sha256': '2b30df42c6a15511f302a0acdc29a49708a8741e6c71edb16ce89e8724cfa8ea'}
BOOT = {'bytes': 1734, 'sha256': '3ea5f30575fec2df46e7b815329c572f1738bada1475b5bdaca30f252eb6476c'}
REQUEST_CAP = 65536
REVIEW_CAP = 65536


def descriptor(c, row, cap):
    c.need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'exact operator operand')
    pp = c.only_pin(row)
    c.need(pp['bytes'] <= cap and type(row['path']) is str and Path(row['path']).is_absolute()
           and str(c.path(row['path'])) == row['path'], 'bounded canonical operator operand')
    return pp


def limits(c, value):
    fields = {'reads', 'output_bytes', 'wall_seconds', 'cpu_seconds', 'host_memory_bytes'}
    c.need(type(value) is dict and set(value) == fields and all(type(x) is int and x > 0 for x in value.values()), 'explicit finite whole grading limits')
    c.need(value['reads'] <= 10**12 and value['output_bytes'] <= 64_000_000
           and value['wall_seconds'] <= 31_536_000 and value['cpu_seconds'] <= 31_536_000
           and value['host_memory_bytes'] <= 2**40, 'finite interface ceilings; not feasibility evidence')
    return value


def evaluate(request, adapter_pin, c, bodies, read):
    """Composition seam; read must enforce exact pins and the selected owner budget.

    Production uses unchanged c.capture. Generated controls use invented bytes
    through the same exact-pin contract; no scientific function is replaced.
    """
    fields = {'schema', 'task_id', 'execution_selected', 'adapter_source', 'producer_source',
              'selection', 'external', 'outer_review', 'grade_runtime_review', 'authority',
              'private_gold', 'output', 'limits'}
    c.need(type(request) is dict and set(request) == fields
           and request['schema'] == 'neural014-complete-grade-request-v1'
           and request['task_id'] == 'NEURAL-014' and request['execution_selected'] is True,
           'separate complete grading selection required')
    c.need(request['adapter_source'] == c.exact_pin(adapter_pin)
           and request['producer_source'] == PRODUCER, 'exact successor and unchanged producer source')
    profile = limits(c, request['limits'])
    caps = {'selection': 32768, 'external': 8192, 'outer_review': REVIEW_CAP,
            'grade_runtime_review': REVIEW_CAP, 'authority': REVIEW_CAP, 'private_gold': 64_000_000}
    for name, cap in caps.items(): descriptor(c, request[name], cap)
    c.need(request['external']['bytes'] == 8192, 'complete original durable observer slot')
    gold_path = c.path(request['private_gold']['path'])
    gold_pin = c.only_pin(request['private_gold'])
    c.need(all(gold_path != c.path(request[name]['path']) and gold_pin != c.only_pin(request[name])
               for name in caps if name != 'private_gold'), 'private target cannot alias an early metadata operand')
    output = c.path(request['output'])
    c.need(type(request['output']) is str and Path(request['output']).is_absolute()
           and str(output) == request['output'], 'canonical grading output')
    science = c.module(bodies, 'program/science.py', PRODUCER_ROOT, c=c)
    packet = c.module(bodies, 'program/packet.py', PRODUCER_ROOT, c=c, science=science)
    policy = c.module(bodies, 'program/policy.py', PRODUCER_ROOT, c=c, packet=packet)
    outputs = c.module(bodies, 'program/outputs.py', PRODUCER_ROOT, c=c, packet=packet, policy=policy, science=science)
    scoring = c.module(bodies, 'program/scoring.py', PRODUCER_ROOT, c=c, packet=packet, outputs=outputs)

    def metadata(name):
        row = request[name]
        return c.parse(read(row['path'], caps[name], c.only_pin(row)))

    s = policy.selection(metadata('selection'), PRODUCER)
    root = c.path(s['output'])
    public_root = c.path(s['public_root'])
    c.need(all(gold_path != c.path(s[name]['path']) and gold_pin != c.only_pin(s[name])
               for name in ('public_manifest', 'candidate_program', 'input_review', 'method_review', 'runtime_review')),
           'private target cannot alias a producer prerequisite')
    c.need(not gold_path.is_relative_to(root) and not gold_path.is_relative_to(public_root), 'private targets outside producer and public trees')
    c.need(output != gold_path and not output.is_relative_to(root) and not output.is_relative_to(public_root), 'disjoint private grading output')
    c.need(all(output != c.path(request[name]['path']) for name in caps), 'output cannot replace an operand')
    # Existing full-pool, method and producer-runtime requirements are not
    # inferred from a completed file or the root grading flag.
    policy.reviews(s, PRODUCER, c.pin(bodies['reference/reference_program.py']), read)
    runtime = metadata('grade_runtime_review')
    c.need(type(runtime) is dict and set(runtime) == {'schema', 'task_id', 'approved', 'adapter_source', 'producer_source', 'limits', 'host_python', 'bounded_owner_and_source_capture_qualified', 'complete_grade_dependency_and_resource_profile_qualified', 'private_target_access_operator_only', 'scientific_qualified'}
           and runtime['schema'] == 'neural014-grade-runtime-review-v1' and runtime['task_id'] == 'NEURAL-014'
           and runtime['approved'] is True and runtime['adapter_source'] == adapter_pin
           and runtime['producer_source'] == PRODUCER and limits(c, runtime['limits']) == profile
           and runtime['host_python'] == str(Path(sys.executable).resolve())
           and all(runtime[k] is True for k in ('bounded_owner_and_source_capture_qualified', 'complete_grade_dependency_and_resource_profile_qualified', 'private_target_access_operator_only'))
           and runtime['scientific_qualified'] is False, 'separate exact grading runtime and complete resource admission')
    external = read(request['external']['path'], 8192, c.only_pin(request['external']))
    outer = c.parse(external)
    review = metadata('outer_review')
    expected = dict(schema='neural014-complete-outer-exit-review-v1', task_id='NEURAL-014', approved=True,
                    producer_source=PRODUCER, selection=c.only_pin(request['selection']),
                    external=c.only_pin(request['external']), attempt=str(root),
                    executing_outer_source=c.pin(bodies['transport/run.py']),
                    executing_worker_source=c.pin(bodies['transport/worker.py']),
                    natural_exit=True, exit_code=0, process_reaped=True, process_group_absent=True,
                    streams_closed=True, forced_termination=False)
    c.need(c.encoded(review) == c.encoded(expected), 'independent natural outer exit review; internal worker report is insufficient')
    c.need(outer.get('selection') == c.only_pin(request['selection'])
           and outer.get('runtime_qualified') is False and outer.get('error_type') is None
           and outer.get('nested_native_recovery_may_be_required') is False
           and outer.get('automatic_retry') is False, 'closed unchanged producer selection and failure status')
    authority = metadata('authority')
    c.need(authority.get('private_gold') == c.only_pin(request['private_gold']), 'selected protected target content identity')
    opened = 0

    def private_gold():
        nonlocal opened
        c.need(opened == 0, 'one protected target capture')
        opened += 1
        return read(str(gold_path), packet.JSON_CAP, c.only_pin(request['private_gold']))

    result = scoring.grade(s, PRODUCER, bodies, external, c.only_pin(request['external']), root, read, private_gold, authority)
    c.need(opened == 1, 'complete grade must capture exact private targets once')
    return dict(schema='neural014-complete-graded-result-v1', task_id='NEURAL-014',
                adapter_source=adapter_pin, producer_source=PRODUCER,
                selection=c.only_pin(request['selection']), external=c.only_pin(request['external']),
                private_gold=c.only_pin(request['private_gold']), protected_target_captures=opened,
                result=result, requires_independent_natural_adapter_exit_zero=True,
                scientific_qualified=False, submission_ready=False)


def main(argv=None):
    if ORIGIN is None or CAPTURED is None:
        raise ValueError('root-captured adapter bytes and original owner clock required')
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise ValueError('isolated no-site bytecode-free entry')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-bytes', required=True, type=int)
    parser.add_argument('--request-sha256', required=True)
    args = parser.parse_args(argv)
    deadline = ORIGIN + 120
    previous = {n: signal.getsignal(n) for n in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM)}

    def stop(*_): raise TimeoutError('original grading owner deadline or stop')
    for n in previous: signal.signal(n, stop)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
    try:
        # Reuse the frozen producer bootstrap and its complete source loader.
        path = PRODUCER_ROOT / 'transport/bootstrap.py'
        if any(p.is_symlink() for p in (path, *path.parents)): raise ValueError('ordinary frozen bootstrap')
        with path.open('rb') as stream: raw = stream.read(BOOT['bytes'] + 1)
        if len(raw) != BOOT['bytes'] or hashlib.sha256(raw).hexdigest() != BOOT['sha256']: raise ValueError('frozen bootstrap pin')
        module = types.ModuleType('t15_original_bootstrap'); module.__file__ = str(path)
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        c, _, bodies, source_cost = module.load(PRODUCER_ROOT, PRODUCER, deadline)
        entry_charge = globals().get('_EARLY_SOURCE_READ_CHARGE')
        c.need(type(entry_charge) is int and entry_charge == c.exact_pin(CAPTURED)['bytes'] + 1,
               'exact captured entry read reservation')
        cost = source_cost + len(raw) + 1 + entry_charge
        rp = c.exact_pin({'bytes': args.request_bytes, 'sha256': args.request_sha256})
        c.need(rp['bytes'] <= REQUEST_CAP, 'bounded exact request')
        request = c.parse(c.capture(args.request, REQUEST_CAP, rp, lambda: c.before(deadline)))
        cost += rp['bytes'] + 1
        profile = limits(c, request['limits'])
        deadline = ORIGIN + profile['wall_seconds']
        c.before(deadline)
        signal.setitimer(signal.ITIMER_REAL, deadline - time.monotonic())

        def charge(n):
            nonlocal cost
            c.need(type(n) is int and n >= 0 and cost + n <= profile['reads'], 'whole source and grading read allowance')
            cost += n

        charge(0)
        def read(path, cap, expected=None):
            return c.capture(path, cap, expected, lambda: c.before(deadline), charge)

        output = c.path(request['output'])
        c.need(not os.path.lexists(output) and output.parent.is_dir(), 'fresh existing-parent grade output')
        value = evaluate(request, CAPTURED, c, bodies, read)
        value['read_reservations'] = cost
        raw = c.encoded(value)
        c.need(len(raw) <= profile['output_bytes'], 'whole grade result extent')
        c.save(output, raw, profile['output_bytes'], lambda: c.before(deadline))
        c.before(deadline)
        return 0
    finally:
        failures = []
        for action in [lambda: signal.setitimer(signal.ITIMER_REAL, 0)] + [lambda n=n,h=h: signal.signal(n,h) for n,h in previous.items()]:
            try: action()
            except BaseException as exc: failures.append(type(exc).__name__)
        if failures: raise RuntimeError('grading signal cleanup uncertainty:' + ','.join(failures))


if __name__ == '__main__':
    raise SystemExit(main())

"""Source-selected NEURAL083 operator composition; no default execution grant.

External root selection pins this entry and SOURCE.json before invocation.
Every operative source member is captured before the integration runs. No
inspection operation accepts a data operand, and producing metadata never
replaces independent authentic-input/method/native admissions.
"""
import time
ENTRY = time.monotonic()
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import types


def bootstrap_read(path, expected, cap):
    p = Path(path)
    if not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('ordinary source path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink != 1 or not 0 < a.st_size <= cap:
            raise ValueError('bounded ordinary source')
        raw = os.read(fd, a.st_size + 1)
        z, n = os.fstat(fd), p.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if len(raw) != a.st_size or any(getattr(a, k) != getattr(z, k) or getattr(z, k) != getattr(n, k) for k in keys):
            raise ValueError('stable complete bootstrap source')
        if dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) != expected:
            raise ValueError('externally selected source identity')
        return raw
    finally:
        os.close(fd)


def load(root, source_pin, limits, deadline):
    raw = bootstrap_read(root / 'SOURCE.json', source_pin, 131_072)
    # Root-selected manifest is authenticated before selecting the bootstrap body.
    initial = json.loads(raw)
    expected = initial['files']['integration_io.py']
    body = bootstrap_read(root / 'integration_io.py', expected, 65_536)
    io = types.ModuleType('neural083_integration_io')
    io.__file__ = str(root / 'integration_io.py')
    exec(compile(body, io.__file__, 'exec'), io.__dict__)
    budget = io.Budget(limits, deadline)
    budget.read(len(raw) + len(body) + 2)
    table, bodies = io.source(root, dict(path=str(root / 'SOURCE.json'), **source_pin), budget)
    io.need(bodies['integration_io.py'] == body, 'same captured bootstrap')
    owner = io.module(bodies['process_owner.py'], root / 'process_owner.py')
    bridge = io.module(bodies['integration.py'], root / 'integration.py', io=io, owner=owner)
    return io, budget, table, bodies, owner, bridge


def authorize(io, value, request_spec, source_pin, command):
    io.exact(value, ('schema', 'operation', 'configuration', 'source', 'execution_authorized'))
    io.need(value['schema'] == 'neural083_integration_root_authority_v1'
            and value['operation'] == command and value['configuration'] == io.only_pin(request_spec)
            and value['source'] == source_pin and value['execution_authorized'] is True,
            'exact separately supplied root operation authority')


def failure_payload(error, command, budget, bridge):
    result = dict(schema='neural083_integration_failure_v1', error_type=type(error).__name__,
                  error=str(error)[:2048], automatic_retry=False,
                  native_resources_may_need_exact_independent_recovery=command == 'run',
                  costs=budget.record())
    record = bridge.child_failure_record(error)
    if record is not None:
        result['actual_child_record'] = record
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('command', choices=('inspect', 'compose', 'prepare-project', 'prepare-finalize', 'run', 'grade'))
    parser.add_argument('--source-pin', required=True)
    parser.add_argument('--request')
    parser.add_argument('--authority')
    parser.add_argument('--whole-seconds', type=int, required=True)
    parser.add_argument('--read-limit', type=int, required=True)
    parser.add_argument('--write-limit', type=int, required=True)
    parser.add_argument('--retained-limit', type=int, required=True)
    parser.add_argument('--grade-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--origin', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    origin = ENTRY if args.origin is None else args.origin
    if not (1 <= args.whole_seconds <= 604800 and origin <= ENTRY < origin + args.whole_seconds):
        raise ValueError('finite original owner interval')
    if args.grade_worker and (args.command != 'grade' or args.origin is None):
        raise ValueError('only separately owned grade worker accepts inherited origin')
    if not args.grade_worker and args.origin is not None:
        raise ValueError('operator origin is captured by this actual entry')
    limits = dict(read_bytes=args.read_limit, write_bytes=args.write_limit, retained_bytes=args.retained_limit)
    deadline = origin + args.whole_seconds
    active_deadline = deadline - 15 if args.grade_worker else deadline
    # A timer bounds ordinary Python work; the separate process owner supplies
    # child/group cleanup. This does not qualify native CPU/RAM or kernel I/O.
    def stop(*_):
        raise TimeoutError('original integration interval or stop')
    old = {}
    output = budget = io = None
    try:
        for number in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
            old[number] = signal.getsignal(number)
            signal.signal(number, stop)
        signal.setitimer(signal.ITIMER_REAL, max(0.000001, active_deadline-time.monotonic()))
        source_pin = json.loads(args.source_pin)
        io, budget, table, bodies, owner, bridge = load(root, source_pin, limits, active_deadline)
        budget.read(len(bodies['entry.py']) + 1)
        io.need(bodies['entry.py'] == bootstrap_read(root / 'entry.py', table['files']['entry.py'], 65_536),
                'same selected operator source')
        io.need(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1,
                'isolated no-bytecode operator entry required')
        if args.command == 'inspect':
            io.need(args.request is None and args.authority is None and not args.grade_worker,
                    'inspection accepts no operation/data operand')
            print(json.dumps(dict(status='source_only_unqualified', source=source_pin,
                                  records=108, conditions=2592, native_phases=5184,
                                  execution_authorized=False, source_members=len(bodies))))
            return 0
        request_spec = io.descriptor(io.parse(args.request.encode()))
        request = bridge.read_json(request_spec, budget, 262_144)
        io.exact(request, ('schema', 'operation', 'source', 'output', 'limits', 'whole_seconds', 'inputs'))
        io.need(request['schema'] == 'neural083_integration_operation_v1'
                and request['operation'] == args.command and request['source'] == source_pin
                and request['limits'] == limits and request['whole_seconds'] == args.whole_seconds,
                'exact selected operation and metadata resources')
        if args.command != 'compose':
            io.need(args.authority is not None, 'separate root authority required')
            auth_spec = io.descriptor(io.parse(args.authority.encode()))
            authorize(io, bridge.read_json(auth_spec, budget, 32_768), request_spec, source_pin, args.command)
        else:
            io.need(args.authority is None, 'compose is a configuration draft, not execution admission')
        target = io.path(request['output'])
        if args.grade_worker:
            s = target.lstat()
            io.need(stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid() and s.st_mode & 0o077 == 0,
                    'already owned protected grade directory')
            output = target
        else:
            output = io.fresh_directory(target)
        inputs = request['inputs']
        if args.command.startswith('prepare-'):
            io.exact(inputs, ('preparation_request',))
            result = bridge.prepare(args.command.removeprefix('prepare-'), inputs['preparation_request'],
                                    root, bodies, output, budget, origin, deadline-15, deadline-5)
            name = 'PREPARATION_CLOSURE.json'
        elif args.command in ('compose', 'run', 'grade'):
            if args.command == 'grade' and not args.grade_worker:
                # The complete scoring/target callback stays in a separate trusted
                # child. Never score in the process that schedules the candidate.
                original = bodies['entry.py']
                extra = sys.argv[1:] + ['--grade-worker', '--origin', repr(origin)]
                child = bridge.launch(root / 'entry.py', original, extra, origin,
                                      deadline-15, deadline-5, output, budget)
                terminal = io.parse(base64.b64decode(child['stdout_base64'], validate=True))
                io.exact(terminal, ('schema', 'grade'))
                io.need(terminal['schema'] == 'neural083_integration_grade_worker_v1'
                        and terminal['grade']['path'] == str(output / 'GRADE.json'), 'exact owned grade result')
                grade_body = io.capture(terminal['grade'], budget)
                result = dict(schema='neural083_integration_grade_closure_v1', grade=io.pin(grade_body),
                              child=child, scientific_qualified=False, submission_ready=False,
                              candidate_or_model_execution_in_grade=False)
                name = 'GRADE_CLOSURE.json'
            else:
                joined = bridge.prepared_inputs(inputs['preparation_complete'], inputs['preparation_closure'],
                                                 root, bodies, budget)
                if args.command == 'compose':
                    io.exact(inputs, ('preparation_complete', 'preparation_closure', 'configuration'))
                    values = dict(inputs['configuration'])
                    io.need(values['repository'] == str(root / 'scientific-source'), 'captured original scorer root')
                    config = bridge.configuration(joined['value'], values, joined['contracts'])
                    # Independent method review must reference this exact encoding.
                    config_spec = io.put(output / 'CONFIGURATION.json', io.encoded(config), budget)
                    result = dict(schema='neural083_integration_configuration_v1', configuration=config_spec,
                                  execution_selected=False, independent_method_review_required=True,
                                  next='Supply the independent method_review descriptor as the sole additional selection field.')
                    name = 'COMPOSITION.json'
                elif args.command == 'run':
                    io.exact(inputs, ('preparation_complete', 'preparation_closure', 'selection'))
                    result = bridge.run(joined, inputs['selection'], str(output / 'EXTERNAL.json'),
                                        root, bodies, output, budget, origin)
                    name = 'PROGRAMME_CLOSURE.json'
                else:
                    result = bridge.grade(joined, inputs, root, bodies, budget)
                    spec = io.put(output / 'GRADE.json', io.encoded(result), budget)
                    print(json.dumps(dict(schema='neural083_integration_grade_worker_v1', grade=spec)))
                    budget.tick()
                    return 0
        result['integration_source'] = source_pin
        result['operation_request'] = io.only_pin(request_spec)
        result['metadata_costs_before_publication'] = budget.record()
        spec = io.put(output / name, io.encoded(result), budget)
        budget.tick()
        print(json.dumps(dict(status='complete_unqualified', product=spec)))
        return 0
    except BaseException as error:
        if output is not None and io is not None and budget is not None:
            try:
                failure = failure_payload(error, args.command, budget, bridge)
                io.put(output / ('WORKER_FAILURE.json' if args.grade_worker else 'FAILURE.json'),
                       io.encoded(failure), budget)
            except BaseException as secondary:
                error.add_note('Failure publication also failed: ' + type(secondary).__name__)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for number, previous in old.items():
            signal.signal(number, previous)


if __name__ == '__main__':
    raise SystemExit(main())

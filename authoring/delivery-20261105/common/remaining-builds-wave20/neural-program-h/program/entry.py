"""Root-only entry; no qualification or scientific execution is supplied here."""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import types


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('observe', 'worker', 'grade'))
    parser.add_argument('--repo', required=True)
    parser.add_argument('--bootstrap-bytes', required=True, type=int)
    parser.add_argument('--bootstrap-sha256', required=True)
    parser.add_argument('--manifest-bytes', required=True, type=int)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--authority', required=True)
    parser.add_argument('--authority-bytes', required=True, type=int)
    parser.add_argument('--authority-sha256', required=True)
    parser.add_argument('--original-origin', required=True, type=float)
    parser.add_argument('--journal-fd', type=int)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    # The root launcher authenticates this entry independently. Bootstrap has an
    # explicit invocation pin so reading its own mutable manifest is not trust.
    bootstrap_path = root/'bootstrap.py'
    fd = os.open(bootstrap_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        import stat
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != args.bootstrap_bytes:
            raise ValueError('exact ordinary bootstrap file')
        raw = os.read(fd, args.bootstrap_bytes+1)
        after = os.fstat(fd)
        if len(raw) != args.bootstrap_bytes or hashlib.sha256(raw).hexdigest() != args.bootstrap_sha256:
            raise ValueError('bootstrap source pin mismatch')
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('bootstrap changed while captured')
    finally:
        os.close(fd)
    bootstrap = types.ModuleType('neural060_captured_bootstrap')
    bootstrap.__file__ = str(bootstrap_path)
    exec(compile(raw, str(bootstrap_path), 'exec'), bootstrap.__dict__)
    sources = bootstrap.Sources(root, {'bytes': args.manifest_bytes, 'sha256': args.manifest_sha256})
    if sources.pins['bootstrap.py'] != {'bytes': args.bootstrap_bytes, 'sha256': args.bootstrap_sha256}:
        raise ValueError('manifest bootstrap join')
    authority_raw = bootstrap.capture(args.authority, {'bytes': args.authority_bytes, 'sha256': args.authority_sha256}, 2097152)
    authority = bootstrap.parse(authority_raw)
    core, gate = sources.module('core'), sources.module('authority')
    if args.operation == 'grade':
        # Distinct protected grading authority; producer/provider paths cannot
        # mint it or call this branch through an action. Original producer clock
        # algebra is independently retained by grader.admit during readback.
        core.need(authority.get('schema') == 'neural060_protected_grade_authority_v1'
                  and authority.get('active') is True and authority.get('role') == 'root_protected_grader'
                  and authority.get('runtime_source') == sources.pin and authority.get('evaluation_selected') is True,
                  'not qualified: separate protected grading authority required')
        core.need(authority['original_origin'] == args.original_origin and args.journal_fd is None,
                  'separately selected grading clock and no producer journal capability')
        budget = core.Budget(args.original_origin, authority['deadline'], authority['read_bytes'], authority['write_bytes'])
        budget.reserve_read(sources.read_bytes+len(authority_raw)+len(raw))
        grader = sources.module('grader')
        guard = grader.AdmissionCapture(authority['target']['path'])
        # Even independently selected metadata cannot alias the private target
        # root before admission. The same guard is applied again inside execute.
        proof_raw, _ = guard.read(authority['independent_admission']['path'],
                                   authority['independent_admission']['pin'], 1048576, budget, readonly=True)
        proof = core.parse(proof_raw)
        core.need(proof.get('schema') == 'neural060_root_grading_admission_v1'
                  and proof.get('issuer') == authority['operator_identity'] and proof.get('admitted') is True
                  and proof.get('runtime_source') == sources.pin
                  and proof.get('producer') == authority['producer']['pin']
                  and proof.get('outer') == authority['outer']['pin']
                  and proof.get('projection') == authority['projection']['pin'],
                  'independent actual producer/input/observer grading admission')
        projection_raw, _ = guard.read(authority['projection']['path'], authority['projection']['pin'],
                                         authority['limits']['projection_bytes'], budget, readonly=True)
        budget.reserve_read(17391)
        projection_module = sources.module('projection')
        projected = projection_module.admit_projection(core.parse(projection_raw), projection_module.admit_sources(bootstrap.roster(args.repo)))
        core.need(projected['producer_sources'] == {name: sources.pins['preparation/'+name]
                  for name in ('prepare.py', 'native.py', 'projection.py')}, 'same qualified preparation source')
        result = grader.execute(producer_path=authority['producer']['path'],
                  producer_pin=authority['producer']['pin'], outer_path=authority['outer']['path'],
                  outer_pin=authority['outer']['pin'], projection=projected, projection_pin=authority['projection']['pin'],
                  runtime_pin=sources.pin, source_pins=sources.pins, target_path=authority['target']['path'],
                  target_pin=authority['target']['pin'], limits=authority['limits'], budget=budget)
        core.publish(authority['output'], core.encoded(result), budget, readonly=True)
        return result
    # This precedes packet/candidate/provider/credential/output operands.
    gate.selected(authority, sources.pin, args.original_origin)
    prefix = 'observer_' if args.operation == 'observe' else ''
    budget = core.Budget(args.original_origin, authority['whole_deadline'],
                         authority['resources'][prefix+'read_bytes'], authority['resources'][prefix+'write_bytes'])
    budget.reserve_read(sources.read_bytes+len(authority_raw)+len(raw))
    qualification = gate.qualify(authority, sources.pin, args.original_origin, budget)
    if args.operation == 'observe':
        if args.journal_fd is not None:
            raise ValueError('observer may not inherit candidate-selected journal')
        return sources.module('outer').observe(args, sources, authority, qualification, budget)
    if args.journal_fd is None or args.journal_fd < 3:
        raise ValueError('independent outer journal descriptor required')
    sequence = 0
    def record(value):
        nonlocal sequence
        sequence += 1
        body = core.encoded({'sequence': sequence, 'event': value}) + b'\n'
        budget.reserve_write(len(body))
        view = memoryview(body)
        while view:
            budget.tick()
            count = os.write(args.journal_fd, view)
            if count <= 0:
                raise OSError('short durable event journal write')
            view = view[count:]
        os.fsync(args.journal_fd)
    record({'kind': 'worker_started', 'source': sources.pin, 'original_origin': budget.origin,
            'deadline': budget.deadline, 'qualifications': qualification})
    try:
        budget.reserve_read(17391)
        result = sources.module('controller').run(authority, sources.bodies, sources.pins,
                                                  bootstrap.roster(args.repo), sources.pin, budget, record)
        budget.reserve_read(sum(x['bytes'] for x in sources.pins.values()))
        sources.recheck()
        record({'kind': 'worker_completed', 'producer': result, 'observed_end': budget.tick()})
    except BaseException as error:
        # An expired journal allowance may itself refuse. Durable prior intent
        # plus the independent outer process observation still exposes failure;
        # no always-written terminal journal or clean resource claim is made.
        try:
            record({'kind': 'worker_failed', 'error_type': type(error).__name__, 'error': str(error)})
        except BaseException:
            pass
        raise


if __name__ == '__main__':
    main()

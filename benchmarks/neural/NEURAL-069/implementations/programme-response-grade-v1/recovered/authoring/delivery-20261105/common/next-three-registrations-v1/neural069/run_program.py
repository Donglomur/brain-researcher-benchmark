"""Review-bound NEURAL069 registration; no authority is inferred from this file."""
import time
ORIGIN = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import sys
import types
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
DONOR_REL = 'authoring/delivery-20261105/neural069/program-transport-v1'
DONOR_PIN = {'bytes': 990, 'sha256': '5b98869fe04a30a0a22156f9214b959c119fc6c50a5dc3047c648b5ee04a08d3'}
LOCK_PIN = {'bytes': 30815, 'sha256': 'd6aee67a4e2d67974a64dee2b2407a8bdd2545c80f960f1c794ef5f85daed95d'}
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
OWN_MEMBERS = {'run_program.py', 'supervise_origin.py', 'test_adapter.py', 'CONTRACT.json', 'README.md'}
DONOR_MEMBERS = {'runtime.py', 'child.py', 'holder.py', 'entry.py', 'executor.py', 'supervise.py', 'LOCK.json'}
READ_CAP = 1048576


def need(ok, message):
    if not ok:
        raise ValueError(message)


def before(end):
    if time.monotonic() >= end:
        raise TimeoutError('Original registration deadline')


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def parse(body):
    def pairs(rows):
        out = {}
        for k, v in rows:
            need(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(body, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def fields(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'Exact metadata fields')


def descriptor(value, cap):
    fields(value, ('bytes', 'sha256'))
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap, 'Exact bounded integer extent')
    need(type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']) is not None, 'SHA256')
    return value


def literal(value):
    need(type(value) is str and 0 < len(value) <= 4096, 'Absolute literal path')
    p = Path(value)
    need(p.is_absolute() and str(p) == value and '..' not in p.parts
         and not any(c in value for c in ',\n\r\0'), 'Canonical unambiguous path')
    return p


def ordinary(value):
    p = literal(str(value))
    need(not any(q.is_symlink() for q in (p, *p.parents)), 'Unlinked path')
    return p


class Reader:
    def __init__(self, end):
        self.end, self.charged = end, 0

    def capture(self, value, cap, expected=None):
        before(self.end)
        need(type(cap) is int and 0 < cap <= 200000, 'Capture extent cap')
        need(self.charged+cap+1 <= READ_CAP, 'Cumulative adapter read cap')
        self.charged += cap+1
        p = ordinary(value)
        before(self.end)
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            a = os.fstat(fd)
            keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            identity = lambda s: tuple(getattr(s, k) for k in keys)
            need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'Ordinary bounded source')
            need(identity(a) == identity(p.lstat()), 'Named file and FD join')
            if expected is not None:
                need(a.st_size == expected['bytes'], 'Pinned extent before read')
            before(self.end)
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                body = stream.read(cap+1)
            before(self.end)
            need(len(body) == a.st_size and identity(a) == identity(os.fstat(fd)) == identity(p.lstat()), 'Stable captured bytes')
            if expected is not None:
                need(pin(body) == expected, 'Exact content identity')
            return body
        finally:
            os.close(fd)


def validate_review(v, *, program, output, other):
    fields(v, ('schema', 'approved', 'task_id', 'source', 'program', 'commit', 'package',
               'output', 'docker_socket', 'environment', 'resources'))
    need(v['schema'] == 'neural069_registration_review_v1' and v['approved'] is True
         and v['task_id'] == 'NEURAL-069', 'Explicit task review')
    fields(v['source'], ('adapter_manifest', 'original_manifest'))
    descriptor(v['source']['adapter_manifest'], 32768)
    descriptor(v['source']['original_manifest'], 40000)
    need(v['source']['original_manifest'] == DONOR_PIN, 'Fixed original source')
    fields(v['program'], ('path', 'bytes', 'sha256'))
    pp = descriptor({k: v['program'][k] for k in ('bytes', 'sha256')}, 131072)
    need(literal(v['program']['path']) == literal(str(program)) and literal(v['output']) == literal(str(output)), 'Exact CLI operands')
    fields(v['commit'], ('path', 'metadata'))
    literal(v['commit']['path']); descriptor(v['commit']['metadata'], 10000)
    literal(v['package']); literal(v['docker_socket'])
    fields(v['resources'], ('candidate_seconds', 'memory_bytes', 'cpu', 'attempt_retained_and_write_bytes',
                            'existing_commit_cap_bytes', 'adapter_read_cap_bytes', 'free_floor_bytes', 'other_bytes'))
    z = v['resources']
    need(type(z['candidate_seconds']) is int and 1 <= z['candidate_seconds'] <= 7200, 'Prospective candidate clock')
    need(type(z['memory_bytes']) is int and 536870912 <= z['memory_bytes'] <= 4294967296, 'Prospective memory')
    fixed = {'cpu': 1, 'attempt_retained_and_write_bytes': 20000000, 'existing_commit_cap_bytes': 300000,
             'adapter_read_cap_bytes': READ_CAP, 'free_floor_bytes': 21474836480}
    need(all(type(z[k]) is int and z[k] == x for k, x in fixed.items()), 'Unchanged bounds plus explicit adapter read allowance')
    need(type(other) is int and other >= 0 and type(z['other_bytes']) is int and z['other_bytes'] == other, 'Current reservation')
    fields(v['environment'], ('PATH', 'DOCKER_CONFIG', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'))
    env = v['environment']
    need(type(env['PATH']) is str and 0 < len(env['PATH']) <= 8192 and not any(c in env['PATH'] for c in '\n\r\0'), 'Reviewed executable search path')
    if env['DOCKER_CONFIG'] is not None:
        literal(env['DOCKER_CONFIG'])
    need(env['DOCKER_TLS_VERIFY'] is None and env['DOCKER_CERT_PATH'] is None, 'No inherited TLS override for selected local socket')
    return pp


def bridge_bytes(original):
    text = original.decode('utf-8')
    replacements = (
        ('def supervise(package,commit,commit_pin,source_pin,output,other,socket):',
         'def supervise(package,commit,commit_pin,source_pin,output,other,socket,*,started):'),
        ("    start=time.monotonic();record={'status':'failed','resource_recovery_may_be_required':False};owned=None;end=None;committed=False",
         "    start=started;need(type(start)in(int,float)and 0<=start<=time.monotonic()<start+60,'Original startup deadline');record={'status':'failed','resource_recovery_may_be_required':False};owned=None;end=None;committed=False"),
        ("timer=signal.setitimer(signal.ITIMER_REAL,60)\n    try:\n        need(timer==(0.0,0.0),'Standalone supervisor')",
         "timer=signal.setitimer(signal.ITIMER_REAL,max(.001,start+60-time.monotonic()))\n    try:\n        need(timer==(0.0,0.0),'Standalone supervisor')"))
    for old, new in replacements:
        need(text.count(old) == 1, 'Exact single source timing edit')
        text = text.replace(old, new)
    return text.encode()


def validate_commit(c, review, lock):
    fields(c, ('schema', 'task_id', 'program', 'source_manifest', 'lock', 'image', 'candidate_seconds',
               'memory_bytes', 'cpu', 'full_cases'))
    pp = descriptor(c['program'], 131072)
    descriptor(c['source_manifest'], 40000); descriptor(c['lock'], 100000)
    need(c['schema'] == 'neural069_program_commit_v1' and c['task_id'] == 'NEURAL-069'
         and pp == {k: review['program'][k] for k in ('bytes', 'sha256')}
         and c['source_manifest'] == DONOR_PIN and c['lock'] == LOCK_PIN and c['image'] == IMAGE,
         'Program and original source commitment')
    need(len(lock['cases']) == 80 and c['full_cases'] == [x['id'] for x in lock['cases']], 'Complete ordered80-case commitment')
    need(all(type(c[k]) is int and c[k] == review['resources'][k] for k in ('candidate_seconds', 'memory_bytes', 'cpu')), 'Unchanged precommitted resources')
    return c


def prepare(args, origin, *, reader=None, here=HERE, repo=REPO):
    reader = Reader(origin+60) if reader is None else reader
    review_raw = reader.capture(args.review, 32768)
    review = parse(review_raw)
    pp = validate_review(review, program=args.program, output=args.output, other=args.other_reserve_bytes)
    before(origin+60)
    manifest_raw = reader.capture(here/'SOURCE_MANIFEST.json', review['source']['adapter_manifest']['bytes'], review['source']['adapter_manifest'])
    manifest = parse(manifest_raw)
    fields(manifest, ('schema', 'task_id', 'files', 'original_dependency', 'execution_selected'))
    need(manifest['schema'] == 'neural069_registration_source_v1' and manifest['task_id'] == 'NEURAL-069'
         and manifest['execution_selected'] is False and set(manifest['files']) == OWN_MEMBERS, 'Exact adapter closure')
    need(manifest['original_dependency'] == {'path': DONOR_REL+'/SOURCE_MANIFEST.json', **DONOR_PIN}, 'Donor pointer')
    need(sum(descriptor(p, 200000)['bytes'] for p in manifest['files'].values()) <= 200000, 'Bounded adapter closure')
    own = {n: reader.capture(here/n, p['bytes'], p) for n, p in manifest['files'].items()}
    donor = repo/DONOR_REL
    original_raw = reader.capture(donor/'SOURCE_MANIFEST.json', DONOR_PIN['bytes'], DONOR_PIN)
    original = parse(original_raw)
    need(original['schema'] == 'neural069_transport_source_v1' and set(original['runtime_files']) == DONOR_MEMBERS, 'Exact original closure')
    source = {n: reader.capture(donor/n, descriptor(p, 200000)['bytes'], p) for n, p in original['runtime_files'].items()}
    need(pin(source['LOCK.json']) == LOCK_PIN, 'Fixed full input/output lock')
    need(own['supervise_origin.py'] == bridge_bytes(source['supervise.py']), 'Only declared clock bridge edits')
    lock = parse(source['LOCK.json'])
    need(lock['task_id'] == 'NEURAL-069' and len(lock['public_files']) == 101 and lock['output_count'] == 81, 'Full selected scope')
    commit_path = literal(review['commit']['path'])
    commit_raw = reader.capture(commit_path/'COMMIT.json', review['commit']['metadata']['bytes'], review['commit']['metadata'])
    c = validate_commit(parse(commit_raw), review, lock)
    program_raw = reader.capture(args.program, pp['bytes'], pp)
    program_raw.decode('utf-8')
    need(reader.capture(commit_path/'program.py', pp['bytes'], pp) == program_raw, 'Same precommitted source file')
    before(origin+60)
    return {'review': review, 'review_pin': pin(review_raw), 'commit': c, 'reader': reader,
            'bridge': own['supervise_origin.py'], 'original_manifest': original,
            'donor': donor, 'origin': origin, 'output': Path(args.output)}


def compile_bridge(p):
    before(p['origin']+60)
    m = types.ModuleType('neural069_origin_bound_supervisor')
    # Preserve authenticated donor bootstrap/snapshot locations. This source is
    # independently bound by the new manifest; donor snapshots alone do not bind it.
    m.__file__ = str(p['donor']/'supervise.py')
    exec(compile(p['bridge'], str(HERE/'supervise_origin.py'), 'exec'), m.__dict__)
    before(p['origin']+60)
    return m


def validate_return(result, receipt, p):
    fields(result, ('status', 'receipt', 'outputs', 'worker_natural_exit'))
    descriptor(result['receipt'], 40000)
    need(result['status'] == 'closed' and type(result['outputs']) is int and result['outputs'] == 81
         and result['worker_natural_exit'] is True, 'Original complete supervisor terminal')
    review, c = p['review'], p['commit']
    need(receipt['schema'] == 'neural069_host_exit_v1' and receipt['status'] == 'closed'
         and receipt['source_manifest'] == DONOR_PIN and receipt['commit'] == review['commit']['metadata']
         and receipt['program'] == c['program'] and receipt['image'] == IMAGE
         and receipt['attempt'] == str(p['output']/'attempt') and receipt['private_scoring_called'] is False,
         'Original receipt identity and task joins')
    observed = receipt['child']
    need(observed['natural_exit'] is True and observed['process_reaped'] is True and observed['streams_closed'] is True
         and observed['timed_out'] is False and type(observed['exit_code']) is int and observed['exit_code'] == 0
         and observed['error_type'] is None, 'Observed original executor closure')
    need(receipt['whole_seconds'] == c['candidate_seconds']+480
         and type(receipt['host_seconds_before_receipt']) in (int, float)
         and 0 <= receipt['host_seconds_before_receipt'] < receipt['whole_seconds'], 'Original whole clock')
    need(type(receipt['outputs']) is list and len(receipt['outputs']) == 81, 'Complete81-file descriptor receipt')


def execute_prepared(p, *, compiler=compile_bridge):
    before(p['origin']+60)
    for key, expected in p['review']['environment'].items():
        need(os.environ.get(key) == expected, 'Exact reviewed inherited environment')
    module = compiler(p)
    v = p['review']; end = p['origin']+v['resources']['candidate_seconds']+480
    before(p['origin']+60)
    # Preparation and compilation share the original startup alarm. Only the
    # donor's standalone call boundary receives a disabled timer.
    signal.setitimer(signal.ITIMER_REAL, 0)
    result = module.supervise(Path(v['package']), Path(v['commit']['path']), v['commit']['metadata'],
                              DONOR_PIN, p['output'], v['resources']['other_bytes'], Path(v['docker_socket']),
                              started=p['origin'])
    before(end)
    signal.setitimer(signal.ITIMER_REAL, max(.001, end-time.monotonic()))
    descriptor(result.get('receipt'), 40000)
    p['reader'].end = end
    receipt = parse(p['reader'].capture(p['output']/'HOST_EXIT.json', result['receipt']['bytes'], result['receipt']))
    validate_return(result, receipt, p)
    p['reader'].capture(p['donor']/'SOURCE_MANIFEST.json', DONOR_PIN['bytes'], DONOR_PIN)
    for n, expected in p['original_manifest']['runtime_files'].items():
        p['reader'].capture(p['donor']/n, expected['bytes'], expected)
    before(end)
    return result, end


def terminal(value, end):
    body = encoded(value); need(len(body) <= 2048, 'Bounded terminal')
    before(end); prior = os.get_blocking(1); os.set_blocking(1, False)
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(1, selectors.EVENT_WRITE); pending = memoryview(body)
            while pending:
                before(end)
                if not ready.select(min(.1, end-time.monotonic())):
                    continue
                before(end)
                try:
                    n = os.write(1, pending)
                except BlockingIOError:
                    continue
                need(n > 0, 'Terminal progress'); pending = pending[n:]
    finally:
        os.set_blocking(1, prior)
    before(end)


def main(argv=None, *, origin=ORIGIN):
    a = argparse.ArgumentParser()
    for key in ('program', 'output', 'review'):
        a.add_argument('--'+key, type=Path, required=True)
    a.add_argument('--other-reserve-bytes', type=int, required=True)
    args = a.parse_args(argv)
    end = origin+60; entered = False; old = None; code = 2
    def alarm(*_):
        raise TimeoutError('Original startup deadline')
    try:
        before(end)
        old = signal.signal(signal.SIGALRM, alarm)
        remaining = end-time.monotonic(); need(remaining > 0, 'Remaining startup')
        prior = signal.setitimer(signal.ITIMER_REAL, remaining)
        need(prior == (0.0, 0.0), 'Standalone registration')
        p = prepare(args, origin)
        end = origin+p['review']['resources']['candidate_seconds']+480
        entered = True
        result, end = execute_prepared(p)
        terminal({'schema': 'neural069_review_bound_terminal_v1', 'status': 'closed',
                  'original_host_exit': result['receipt'], 'review': p['review_pin'], 'outputs': 81,
                  'external_natural_zero_required': True, 'scientific_qualification': False}, end)
        code = 0
    except BaseException as exc:
        try:
            terminal({'schema': 'neural069_review_bound_terminal_v1', 'status': 'failed',
                      'error_type': type(exc).__name__ if type(exc).__name__ in ('ValueError', 'TimeoutError', 'OSError', 'TypeError', 'MemoryError') else 'Exception',
                      'resource_recovery_may_be_required': entered, 'external_natural_zero_required': True}, end)
        except BaseException:
            pass
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if old is not None:
            signal.signal(signal.SIGALRM, old)
    return code if time.monotonic() < end else 2


if __name__ == '__main__':
    raise SystemExit(main())

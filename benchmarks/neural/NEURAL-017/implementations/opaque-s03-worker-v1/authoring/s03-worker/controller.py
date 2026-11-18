"""Repository S03 orchestration using the retained ownership/Docker primitives.

Only the original full-support S03 projection is permitted. Existing arrays
and seed are consumed once for production; no export, fit, score or seed draw.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

COMPONENT = Path(__file__).resolve().parents[2]
SELECT = None
NATIVE = None
OPERATION_ROOT = None
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
NAME = 'neural017-owned-s03-001'
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'NUMBA_NUM_THREADS',
           'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')
TMPFS = {'/tmp': 'rw,noexec,nosuid,nodev,size=65536,mode=1777'}
ULIMITS = {'cpu': (160, 161), 'core': (0, 0), 'nofile': (128, 128),
           'fsize': (536870912, 536870912)}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def capture(path, expected=None, cap=262144):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No linked metadata/source role')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
         'Bounded ordinary source/metadata')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(identity(before) == identity(after) == identity(path.lstat()) and len(body) == before.st_size,
         'Captured source/metadata stability')
    need(expected is None or pin(body) == expected, 'Exact captured identity')
    return body


def decode(body):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Unique JSON fields')
            out[key] = value
        return out
    value = json.loads(body, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Finite JSON')))
    encode(value)
    return value


def write_once(path, value, cap=16384):
    body = encode(value)
    need(len(body) <= cap, 'Bounded private result')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        need(stream.write(body) == len(body), 'Complete private record')
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def module(path, expected, name):
    body = capture(path, expected)
    result = types.ModuleType(name)
    result.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), result.__dict__)
    return result


def selection(expected_sha):
    body = capture(SELECT, cap=65536)
    need(pin(body)['sha256'] == expected_sha, 'Frozen selection identity')
    value = decode(body)
    need(value['schema'] == 'NLB017_owned_S03_selection_v1'
         and value['destination'] == str(OPERATION_ROOT) and value['image'] == IMAGE
         and value['container_name'] == NAME and value['attempts'] == 1, 'Exact selected S03 operation')
    need(type(value['uid']) is int and value['uid'] > 0 and type(value['gid']) is int and value['gid'] >= 0,
         'Selected nonroot owner')
    for row in value['component_files']:
        path = Path(row['path'])
        need(not path.is_absolute() and '..' not in path.parts, 'Selected relative component source')
        capture(COMPONENT / path, {'bytes':row['bytes'],'sha256':row['sha256']})
    core_row = next(r for r in value['component_files'] if r['path'] == 'core.py')
    core = module(COMPONENT / 'core.py', {k:core_row[k] for k in ('bytes','sha256')}, '_n017_s03_controller_core')
    bindings = core.decode(core.snapshot(COMPONENT / 'SOURCE_BINDINGS.json', core.BINDINGS_PIN, 65536))
    need(value['dependencies'] == bindings['source_files'], 'Exact seven-file numerical dependency closure')
    for row in value['dependencies']:
        capture(Path(value['dependency_root']) / row['path'], {'bytes':row['bytes'],'sha256':row['sha256']})
    compiled = decode(capture(value['compilation_file'], value['compilation'], 65536))
    need(core.compilation(compiled) == value['input_descriptors'] and set(value['input_files']) == core.INPUT_NAMES,
         'Exact actual S03 recipe and11source files')
    for name, row in value['input_files'].items():
        need({k:row[k] for k in ('bytes','sha256')} == {k:value['input_descriptors'][name][k] for k in ('bytes','sha256')},
             'Exact host operand pin')
    return value


def dependencies(value):
    rows = {r['path']: {k:r[k] for k in ('bytes','sha256')} for r in value['component_files']}
    bank = module(COMPONENT / 'runtime/bank_launcher.py', rows['runtime/bank_launcher.py'], '_n017_s03_docker')
    legacy = module(COMPONENT / 'runtime/legacy_runtime.py', rows['runtime/legacy_runtime.py'], '_n017_s03_absence')
    host = value['host']
    need(set(host) == {'docker','docker_endpoint'} and Path(host['docker']).is_absolute()
         and host['docker_endpoint'].startswith('unix:///') and not any(c in host['docker_endpoint'] for c in '\r\n'),
         'Explicit existing local Docker executable/socket')
    bank.DOCKER, bank.ENDPOINT = host['docker'], host['docker_endpoint']
    owner_dir = COMPONENT / 'authoring/runtime/retained/ownership_long_v2'
    sys.path.insert(0, str(owner_dir))
    import process_owner
    return bank, legacy, process_owner


def mapping(value):
    mounts = {'/selection.json':[str(SELECT),True], '/compilation.json':[value['compilation_file'],True],
              '/out':[str(NATIVE / 'output'),False]}
    for relative in ('core.py','SOURCE_BINDINGS.json','authoring/s03-worker/worker.py'):
        mounts['/component/' + relative] = [str(COMPONENT / relative),True]
    for row in value['dependencies']:
        mounts['/dependencies/' + row['path']] = [str(Path(value['dependency_root']) / row['path']),True]
    for name,row in value['input_files'].items():
        mounts['/inputs/' + value['input_descriptors'][name]['path']] = [row['path'],True]
    need(len(mounts) == 24, 'Exact24single-role mounts, no source/data parents or target/export key')
    return mounts


def create_args(mounts, owner, value):
    argv = ['create', '--pull', 'never', '--name', NAME, '--network', 'none', '--read-only',
            '--user', str(value['uid']) + ':' + str(value['gid']), '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--memory', '2147483648', '--memory-swap', '2147483648', '--cpus', '1',
            '--pids-limit', '32', '--shm-size', '65536', '--log-driver', 'none',
            '--workdir', '/tmp', '--entrypoint', 'python', '--tmpfs', '/tmp:' + TMPFS['/tmp'],
            '--label', 'codex.neural017.owner=' + owner]
    for name, limits in ULIMITS.items():
        argv += ['--ulimit', f'{name}={limits[0]}:{limits[1]}']
    for name in THREADS:
        argv += ['--env', name + '=1']
    argv += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
    for target, (source, readonly) in sorted(mounts.items()):
        need(',' not in source and ',' not in target, 'Unambiguous fixed mounts')
        argv += ['--mount', 'type=bind,source=' + source + ',target=' + target + (',readonly' if readonly else '')]
    return argv + [IMAGE, '-I', '-B', '/component/authoring/s03-worker/worker.py', '--selection-sha256', owner]


def owned(info, owner):
    need(info.get('Name') == '/' + NAME and info.get('Image') == IMAGE
         and info.get('Config', {}).get('Labels') == {'codex.neural017.owner': owner}
         and re.fullmatch('[a-f0-9]{64}', info.get('Id', '')), 'Exact selected owned container')
    return info['Id']


def verify_profile(info, owner, mounts, base_env, value):
    owned(info, owner)
    h, c, s = info['HostConfig'], info['Config'], info['State']
    need(c['Image'] == IMAGE and c['User'] == str(value['uid']) + ':' + str(value['gid']) and c['Entrypoint'] == ['python']
         and c['Cmd'] == ['-I', '-B', '/component/authoring/s03-worker/worker.py', '--selection-sha256', owner] and c['WorkingDir'] == '/tmp'
         and not c.get('Volumes') and c['Tty'] is False and c['OpenStdin'] is False,
         'Exact trusted worker command')
    need(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and h['Privileged'] is False
         and h['CapDrop'] == ['ALL'] and not h.get('CapAdd')
         and h['SecurityOpt'] == ['no-new-privileges:true'] and not h.get('Devices')
         and not h.get('DeviceRequests') and not h.get('DeviceCgroupRules') and not h.get('PortBindings')
         and h['PidMode'] != 'host' and h['IpcMode'] != 'host'
         and h.get('RestartPolicy', {}).get('Name') in ('no', ''), 'Selected isolated configuration')
    need(h['Memory'] == h['MemorySwap'] == 2147483648 and h['NanoCpus'] == 1000000000
         and h['PidsLimit'] == 32 and h['ShmSize'] == 65536 and h['Tmpfs'] == TMPFS
         and h['LogConfig'] == {'Type': 'none', 'Config': {}}, 'Exact resource configuration')
    need(len(h['Ulimits']) == len(ULIMITS) and
         {r['Name']: (r['Soft'], r['Hard']) for r in h['Ulimits']} == ULIMITS, 'Exact CPU/file limits')
    expected_env = dict(base_env, **{name: '1' for name in THREADS}, PYTHONDONTWRITEBYTECODE='1')
    env = dict(v.split('=', 1) for v in c['Env'])
    need(len(env) == len(c['Env']) and env == expected_env, 'Exact inherited and selected environment')
    for rows, key, effective in ((h.get('Mounts', []), 'Target', False),
                                ([r for r in info['Mounts'] if r['Type'] != 'tmpfs'], 'Destination', True)):
        need(len(rows) == len(mounts) and {r[key] for r in rows} == set(mounts), 'Exact complete mount inventory')
        for row in rows:
            source, readonly = mounts[row[key]]
            alias = row['Source'] == source or (source.startswith('/Users/') and row['Source'] == '/host_mnt' + source)
            need(row['Type'] == 'bind' and alias and not row.get('VolumeOptions')
                 and (row['RW'] is (not readonly) if effective else row.get('ReadOnly', False) is readonly),
                 'Exact source and access roles')
    need(len({r['Destination'] for r in info['Mounts']}) == len(info['Mounts'])
         and all(r['Destination'] in TMPFS and r['RW'] for r in info['Mounts'] if r['Type'] == 'tmpfs'),
         'No extra effective mounts')
    need(s['Status'] == 'created' and s['Running'] is False and s['Pid'] == 0, 'Fresh unstarted container')


def recover(docker, legacy, owner, end, known_id=None):
    result = {'absence_verified': False, 'id': known_id, 'diagnostic_publication_errors': []}
    def retain_errors(reply):
        result['diagnostic_publication_errors'].extend(reply.get('diagnostic_publication_errors', []))
        result['evidence_complete'] = not result['diagnostic_publication_errors']
    inspected = docker.call(['inspect', '--type', 'container', known_id or NAME], end, 32768, cleanup=True)
    retain_errors(inspected)
    if legacy.absent(inspected, known_id or NAME):
        result['absence_verified'] = True
        return result
    need(inspected['returncode'] == 0 and not inspected['stderr'], 'Complete successful recovery inspection')
    rows = decode(inspected['stdout'])
    need(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, 'One exact recovery object')
    identity = owned(rows[0], owner)
    need(known_id is None or known_id == identity, 'No recovery identity substitution')
    result['id'] = identity
    removed = docker.call(['rm', '--force', identity], end, 2048, cleanup=True)
    retain_errors(removed)
    absent = docker.call(['inspect', '--type', 'container', identity], end, 2048, cleanup=True)
    retain_errors(absent)
    result['remove_returncode'] = removed['returncode']
    result['absence_verified'] = legacy.absent(absent, identity) and docker.quiescent
    return result


def child(value, sha, started):
    bank, legacy, process_owner = dependencies(value)
    owner_record, _ = process_owner.expected(NATIVE / 'watchdog')
    need(os.getppid() == os.getpgrp() == owner_record['pid']
         and owner_record['child_argv'] == [sys.executable, str(Path(__file__).resolve()), 'child',
                '--selection',str(SELECT),'--operation-root',str(OPERATION_ROOT),
                '--selection-sha256',sha,'--started',str(started)],
         'Exact independently activated owned group')
    journal = bank.Journal(NATIVE / 'control')
    docker = bank.Docker(journal, bank.stop_cli_leader)
    active_end, cleanup_end = started + 160, started + 168
    output = None
    cleanup = {'absence_verified': False}
    created = False
    confirmed_create = False
    known_id = None
    error = None
    try:
        mounts = mapping(value)
        image = bank.row(docker.call(['image', 'inspect', IMAGE], active_end, 16384))
        need(image['Id'] == IMAGE, 'Exact already-local immutable image')
        base_list = image['Config']['Env']
        base_env = dict(v.split('=', 1) for v in base_list)
        need(len(base_list) == len(base_env), 'Unique image environment')
        initial = docker.call(['inspect', '--type', 'container', NAME], active_end, 2048)
        need(legacy.absent(initial, NAME), 'Fresh selected name; no borrowing existing container')
        argv = create_args(mounts, sha, value)
        journal.write('create-intent.json', {'owner': sha, 'argv': argv}, 16384)
        created = True
        made = docker.call(argv, active_end, 2048)
        need(made['returncode'] == 0 and not made['stderr'] and re.fullmatch('[a-f0-9]{64}\n', made['stdout']),
             'One confirmed immutable created identity')
        confirmed_create = True
        info = bank.row(docker.call(['inspect', '--type', 'container', NAME], active_end, 32768))
        known_id = owned(info, sha)
        need(made['stdout'].strip() == known_id, 'Created and inspected identities agree')
        verify_profile(info, sha, mounts, base_env, value)
        reply = docker.call(['start', '--attach', known_id], active_end, 18432)
        need(reply['returncode'] == 0 and not reply['stderr'], 'Natural successful worker and complete bounded response drain')
        output = decode(reply['stdout'])
        need(output.get('schema') == 'NLB017_owned_S03_worker_result_v1'
             and output.get('status') == 'all_original_S03_products_validated'
             and output.get('benchmark_ready') is False and output.get('participant_executed') is False,
             'Exact preparation-only result')
        ended = bank.row(docker.call(['inspect', '--type', 'container', known_id], active_end, 32768))
        need(owned(ended, sha) == known_id, 'Same ended identity')
        state = ended['State']
        need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
             and state['ExitCode'] == 0 and not state.get('OOMKilled') and not state.get('Error'),
             'Natural zero exit without OOM or daemon error')
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)[:500]
    finally:
        if created:
            try:
                cleanup = recover(docker, legacy, sha, cleanup_end, known_id)
                cleanup['create_return_confirmed'] = confirmed_create
                cleanup['cli_leaders_reaped'] = docker.quiescent
            except BaseException as exc:
                cleanup['error'] = type(exc).__name__
        else:
            cleanup = {'absence_verified': True, 'evidence_complete': True, 'no_create_attempt': True}
    qualified = (error is None and output is not None and cleanup['absence_verified']
                 and cleanup.get('evidence_complete') is True and confirmed_create and docker.quiescent)
    pending = {'schema': 'NLB017_owned_S03_child_v1', 'qualified_pending_owned_group_closure': qualified,
               'error': error, 'cleanup': cleanup, 'worker': output, 'benchmark_ready': False}
    need(time.monotonic() < cleanup_end, 'Child publication within original cleanup deadline')
    write_once(NATIVE / 'CHILD_RESULT.json', pending, 32768)


def root(value, sha, release_path, release_sha, started):
    release_body = capture(release_path, cap=16384)
    release = decode(release_body)
    need(pin(release_body)['sha256'] == release_sha and release.get('schema') == 'NLB017_owned_S03_release_v1'
         and release.get('approved') is True and release.get('selection') == pin(capture(SELECT)), 'Exact root native release')
    need(os.getuid() == value['uid'] and os.getgid() == value['gid'], 'Selected host custody identity')
    for name in THREADS:
        os.environ[name] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    bank, legacy, process_owner = dependencies(value)
    # Metadata-only role checks; authentic byte capture remains in the worker.
    for row in value['input_files'].values():
        operand = Path(row['path'])
        need(all(not p.is_symlink() for p in (operand, *operand.parents)), 'Literal metadata source path')
        info = operand.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == row['bytes'],
             'Exact selected metadata file extent')
    for name in ('output', 'watchdog', 'control', 'recovery'):
        (NATIVE / name).mkdir(mode=0o700)
    write_once(NATIVE / 'OPERATION_INTENT.json', {'selection': pin(capture(SELECT)), 'started': started,
        'whole_deadline': started + 180, 'attempts': 1, 'selected_failure_inclusive_write_envelope': 512*2**20,
        'unchanged_original_store_write_guard': 6*2**30,
        'enumerated_capture_read_envelope': 2*2**30, 'seed_draw_limit': 0, 'existing_seed_bytes': 32,
        'original_S03_only': True, 'protected_export_key_reads': 0})
    descriptor = next(r for r in value['component_files'] if r['path'] == 'authoring/s03-worker/controller.py')
    argv = [sys.executable,str(Path(__file__).resolve()),'child','--selection',str(SELECT),
            '--operation-root',str(OPERATION_ROOT),'--selection-sha256',sha,'--started',str(started)]
    proc = None
    pending = None
    stopped = {'absence_verified': False}
    recovered = None
    error = None
    try:
        need(time.monotonic() < started + 10, 'Bounded preparation before launch')
        proc = process_owner.launch(argv, NATIVE / 'watchdog', 169, descriptor)
        completion = NATIVE / 'watchdog/process_completion.json'
        while not completion.exists():
            need(time.monotonic() < started + 169, 'Original normal completion deadline')
            need(proc.poll() is None, 'Owned bootstrap survives until explicit close')
            time.sleep(.02)
        done = process_owner.read(completion)
        need(done['returncode'] == 0, 'Trusted controller natural completion')
        pending = decode(capture(NATIVE / 'CHILD_RESULT.json', cap=32768))
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)[:500]
    finally:
        try:
            stopped = process_owner.stop(NATIVE / 'watchdog', started + 172, proc)
        except BaseException as exc:
            stopped['error'] = type(exc).__name__
        # An independently stopped group cannot leave late Docker clients.
        # Recover only the exact selection-labelled container, never by name alone.
        if stopped.get('absence_verified'):
            try:
                docker = bank.Docker(bank.Journal(NATIVE / 'recovery'), bank.stop_cli_leader)
                recovered = recover(docker, legacy, sha, started + 178)
            except BaseException as exc:
                recovered = {'absence_verified': False, 'error': type(exc).__name__}
    qualified = (error is None and pending is not None and pending.get('qualified_pending_owned_group_closure') is True
                 and stopped.get('absence_verified') is True and recovered is not None
                 and recovered.get('absence_verified') is True and recovered.get('evidence_complete') is True)
    commitment = None
    if qualified:
        try:
            worker = pending['worker']
            receipt_body = capture(NATIVE / 'output/S03_RECEIPT.json', worker['receipt'], 2*2**20)
            receipt = decode(receipt_body)
            need(receipt['schema'] == 'NLB017_owned_S03_result_v1' and receipt['selection_sha256'] == sha
                 and receipt['support'] == value['support'] and receipt['seed_generated'] is False
                 and receipt['runtime']['numpy'] == '2.2.6' and receipt['opaque_fingerprint'] == value['opaque_fingerprint']
                 and receipt['physical_fingerprint'] == value['physical_fingerprint']
                 and receipt['validation']['same_seed_and_donor_relation'] is True
                 and receipt['validation']['full_support'] is True and receipt['benchmark_ready'] is False,
                 'Independently retained complete original S03 receipt')
            expected = {c+'_'+k:c+'_'+k+'.npz' for c in ('intact','within_condition_shuffle','context_only','training_rate_only','metadata_neutral') for k in ('training','query')}
            expected.update(support='support.json',protected_map='protected_map.npz')
            need(set(receipt['products']) == set(expected) and receipt['products'] == worker['products'],
                 'Exactly12full-support original products')
            for name,row in receipt['products'].items():
                need(row['path'] == expected[name], 'Exact operator output filename')
                capture(NATIVE / 'output' / row['path'], {k:row[k] for k in ('bytes','sha256')}, 536870912)
            commitment = write_once(NATIVE / 'PRIVATE_COMMITMENT.json', {
                'schema':'NLB017_owned_S03_commitment_v1','selection':pin(capture(SELECT)),
                'receipt':worker['receipt'],'products':receipt['products'],
                'physical_fingerprint':value['physical_fingerprint'],'opaque_fingerprint':value['opaque_fingerprint'],
                'support':value['support'],'same_existing_seed_and_export':True,'seed_generated':False,
                'participant_execution_admitted':False,'scientific_score_produced':False,
                'external_outer_group_and_lease_closure_still_required':True})
        except BaseException as exc:
            qualified = False
            error = type(exc).__name__ + ': ' + str(exc)[:500]
    need(time.monotonic() < started + 180, 'Original whole-operation publication deadline')
    result = {'schema': 'NLB017_owned_S03_root_result_v1', 'qualified': False,
              'candidate_qualified_pending_outer_group_and_lease_closure': qualified, 'error': error,
              'selection': pin(capture(SELECT)), 'process_cleanup': stopped, 'container_cleanup': recovered,
              'private_commitment': commitment, 'worker_result': pending,
              'wall_seconds': time.monotonic() - started, 'benchmark_ready': False,
              'qualification_scope': 'one full-support original S03 projection with12validated products; no scientific score',
              'outer_exit_and_lease_closure_require_independent_root_observation': True}
    write_once(NATIVE / 'OPERATION_RESULT.json', result, 49152)
    need(time.monotonic() < started + 180, 'Publication finished within original deadline')
    print(json.dumps({'candidate_qualified_pending_outer_group_and_lease_closure': qualified,
                      'result': str(NATIVE / 'OPERATION_RESULT.json')}), flush=True)
    return 0 if qualified else 1


def main():
    started_here = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('root', 'child'))
    parser.add_argument('--selection-sha256', required=True)
    parser.add_argument('--selection', required=True)
    parser.add_argument('--operation-root', required=True)
    parser.add_argument('--release')
    parser.add_argument('--release-sha256')
    parser.add_argument('--started', type=float)
    args = parser.parse_args()
    global SELECT,NATIVE,OPERATION_ROOT
    SELECT=Path(args.selection).absolute();OPERATION_ROOT=Path(args.operation_root).absolute()
    need(str(SELECT)==args.selection and str(OPERATION_ROOT)==args.operation_root, 'Absolute explicit operator paths')
    NATIVE=OPERATION_ROOT/'native'
    value = selection(args.selection_sha256)
    if args.mode == 'root':
        need(args.release is not None and args.release_sha256 is not None and args.started is None, 'Root release operands')
        return root(value, args.selection_sha256, args.release, args.release_sha256, started_here)
    need(args.started is not None and args.release is None and args.release_sha256 is None, 'Child owned operands')
    child(value, args.selection_sha256, args.started)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

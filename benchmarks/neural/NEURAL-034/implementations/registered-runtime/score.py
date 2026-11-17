#!/usr/bin/env python3
"""Operator CLI: hash a finished numerical file, score in an isolated container.

This does not execute candidate programs or attest how predictions were obtained.
Exact local artifacts are lazy dependencies. Only standard library on the host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCKER = '/usr/local/bin/docker'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'NUMBA_NUM_THREADS')
TMPFS = {'/tmp': 'rw,noexec,nosuid,nodev,size=16777216,mode=1777'}
ULIMITS = {'cpu': (10, 11), 'core': (0, 0), 'nofile': (1024, 1024),
           'fsize': (262144, 262144)}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def lock(path, cap=4_000_000):
    path = Path(os.path.abspath(path))
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'linked input or parent')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
             'bounded ordinary single-link file required')
        h = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            b = os.read(fd, min(131072, remaining))
            need(bool(b), 'truncated input')
            h.update(b); remaining -= len(b)
        after = os.fstat(fd)
        need(not os.read(fd, 1) and (before.st_dev, before.st_ino, before.st_size,
             before.st_mtime_ns, before.st_ctime_ns, before.st_nlink) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
              after.st_ctime_ns, after.st_nlink), 'input changed while hashing')
        return {'bytes': before.st_size, 'sha256': h.hexdigest()}
    finally:
        os.close(fd)


def write(path, value):
    artifact_root=path.parent.parent if path.parent.name=='operator'else path.parent
    total=0
    for child in artifact_root.rglob('*'):
        need(not child.is_symlink(),'linked output artifact')
        if child.is_file(): total+=child.stat().st_size
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    need(len(body) <= 150000 and total+len(body)<=500000 and not path.exists(), 'new bounded receipt/call500KB limit required')
    with path.open('xb') as f:
        f.write(body)
    path.chmod(0o644)


def docker(args, deadline, cap=300000):
    env = dict(os.environ, DOCKER_CONFIG=str(ROOT / '.cache-build/docker-config'),
               DOCKER_HOST='unix:///Users/nicholas/.docker/run/docker.sock')
    need(time.monotonic() < deadline, 'command deadline')
    p = subprocess.Popen([DOCKER, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=env)
    sel = selectors.DefaultSelector()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    for name, stream in (('stdout', p.stdout), ('stderr', p.stderr)):
        os.set_blocking(stream.fileno(), False); sel.register(stream, selectors.EVENT_READ, name)
    try:
        while sel.get_map():
            need(time.monotonic() < deadline, 'Docker command timed out')
            for key, _ in sel.select(min(.05, max(0, deadline-time.monotonic()))):
                b = os.read(key.fileobj.fileno(), 32768)
                if not b:
                    sel.unregister(key.fileobj)
                else:
                    buffers[key.data].extend(b)
                    need(sum(map(len, buffers.values())) <= cap, 'Docker output cap')
        rc = p.wait(timeout=max(.001, deadline-time.monotonic()))
        return {'returncode': rc, **{k: bytes(v).decode('utf-8') for k, v in buffers.items()}}
    finally:
        sel.close()
        if p.poll() is None:
            p.kill(); p.wait(timeout=.4)
        p.stdout.close(); p.stderr.close()


def absent(result, name):
    if result['returncode'] != 1 or result['stdout'].strip() not in ('', '[]'):
        return False
    text = result['stderr'].strip()
    body = {f'No such container: {name}', f'no such container: {name}'}
    if text in {f'Error: No such object: {name}', f'error: no such object: {name}'} | {
            p+m for p in ('Error response from daemon: ', 'error response from daemon: ') for m in body}:
        return True
    def unique(pairs):
        d = {}
        for k, v in pairs:
            need(k not in d, 'duplicate Docker error key'); d[k] = v
        return d
    try:
        prefix = 'Error response from daemon: '
        if text.startswith(prefix):
            value = json.loads(text[len(prefix):], object_pairs_hook=unique)
            return type(value) is dict and set(value) == {'message'} and value['message'] in body
    except (ValueError, TypeError):
        pass
    return False


def cleanup(name, deadline):
    result = {'name': name, 'absent': False}
    try:
        result['remove'] = docker(['rm', '--force', name], min(deadline, time.monotonic()+1.5))
    except Exception as exc:
        result['remove_error'] = repr(exc)
    try:
        result['inspect'] = docker(['inspect', '--type', 'container', name], deadline)
        result['absent'] = absent(result['inspect'], name)
    except Exception as exc:
        result['inspect_error'] = repr(exc)
    return result


def verify(info, name, mounts, environment):
    h, c, s = info['HostConfig'], info['Config'], info['State']
    need(info['Name'] == '/'+name and info['Image'] == c['Image'] == IMAGE
         and c['User'] == '65534:65534' and c['Entrypoint'] == ['python']
         and c['Cmd'] == ['-I', '-B', '/source/grader.py'] and c['WorkingDir'] == '/tmp'
         and not c.get('Volumes') and not c['Tty'] and not c['OpenStdin'], 'worker identity')
    need(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and not h['Privileged']
         and h['CapDrop'] == ['ALL'] and not h.get('CapAdd')
         and h['SecurityOpt'] == ['no-new-privileges:true'] and not h.get('Devices')
         and not h.get('DeviceRequests') and not h.get('DeviceCgroupRules')
         and not h.get('PortBindings') and h['PidMode'] != 'host' and h['IpcMode'] != 'host'
         and h.get('RestartPolicy', {}).get('Name') in ('no', ''), 'offline nonroot isolation')
    need(h['Memory'] == h['MemorySwap'] == 4*1024**3 and h['NanoCpus'] == 2_000_000_000
         and h['PidsLimit'] == 32 and h['ShmSize'] == 1048576, 'exact resource limits')
    need(h['Tmpfs'] == TMPFS and h['LogConfig'] == {'Type': 'none', 'Config': {}}, 'bounded scratch/logging')
    need(len(h['Ulimits']) == len(ULIMITS) and
         {r['Name']: (r['Soft'], r['Hard']) for r in h['Ulimits']} == ULIMITS, 'ulimits')
    env = dict(v.split('=', 1) for v in c['Env'])
    need(len(env) == len(c['Env']) and env == environment, 'exact environment')
    for rows, key, effective in ((h.get('Mounts', []), 'Target', False),
                                 ([r for r in info['Mounts'] if r['Type'] != 'tmpfs'], 'Destination', True)):
        need(len(rows) == len(mounts) and {r[key] for r in rows} == set(mounts), 'exact mount inventory')
        for row in rows:
            want = mounts[row[key]]
            alias = row['Source'] == want or (want.startswith('/Users/') and row['Source'] == '/host_mnt'+want)
            need(row['Type'] == 'bind' and alias and
                 (row['RW'] is False if effective else row.get('ReadOnly') is True), 'exact readonly source/alias')
    need(len({r['Destination'] for r in info['Mounts']}) == len(info['Mounts']) and
         all(r['Destination'] in TMPFS and r['RW'] for r in info['Mounts'] if r['Type'] == 'tmpfs'), 'extra mounts')
    need(s['Status'] == 'created' and not s['Running'] and s['Pid'] == 0, 'inspection before start')


def run_child(submission, run, name):
    start = time.monotonic(); work = start+7
    evidence = {'status': 'preparing', 'container': name, 'candidate_code_executed': False}
    owned = False
    try:
        # Parent records the dedicated group before this child may create resources.
        anchor=run/'child_ownership.json'
        while not anchor.exists():
            need(time.monotonic()<start+1,'parent ownership journal absent');time.sleep(.005)
        own=json.loads(anchor.read_text());need(own['pid']==os.getpid()and own['process_group']==os.getpgrp()and own['container']==name,'dedicated child ownership')
        freeze = json.loads((HERE/'execution_pins.json').read_text())
        for pin in freeze['files']:
            need(lock(ROOT/pin['path']) == {k: pin[k] for k in ('bytes', 'sha256')}, 'changed execution source')
        plan = json.loads((HERE/'operator_assets.json').read_text())
        submission = Path(os.path.abspath(submission))
        invocation = {'submission': lock(submission, plan['max_submission_bytes']),
                      'producer_stopped_attested': False,
                      'scope': 'Static numerical-file scoring, not candidate-program replay.'}
        write(run/'invocation.json', invocation)
        mounts = {'/source/grader.py': str(HERE/'grader.py'),
                  '/source/operator_assets.json': str(HERE/'operator_assets.json'),
                  '/source/invocation.json': str(run/'invocation.json'),
                  '/submission/probabilities.json': str(submission)}
        for name_, pin in plan['source_files'].items():
            need(lock(ROOT/pin['path']) == {k: pin[k] for k in ('bytes', 'sha256')}, 'trusted helper pin')
            mounts['/source/'+name_] = str(ROOT/pin['path'])
        # Host integrity hashing reads bytes; private target/reference JSON decoding
        # happens only after the worker has validated the entire public submission.
        for key,destination in [('public_panel','/public/cases.json'),('private_targets','/private/targets.json'),('private_references','/private/reference_grade.json')]:
            value=plan[key];need(lock(ROOT/value['path'])=={k:value[k]for k in('bytes','sha256')},'pinned asset integrity');mounts[destination]=str(ROOT/value['path'])
        for src in mounts.values():
            need(not any(c in src for c in ',\r\n') and Path(src).stat().st_mode & 4,
                 'mount source must be literal and readable by nonroot worker')
        initial = docker(['inspect', '--type', 'container', name], work)
        evidence['precreate_absence'] = initial
        need(absent(initial, name), 'unique container name was not absent')
        image = docker(['image', 'inspect', IMAGE], work)
        need(image['returncode'] == 0, 'existing pinned image required')
        base = json.loads(image['stdout'])[0]
        need(base['Id'] == IMAGE, 'immutable image identity')
        env = dict(v.split('=', 1) for v in base['Config']['Env'])
        env.update({k: '2' for k in THREADS}, PYTHONDONTWRITEBYTECODE='1')
        args = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only', '--user', '65534:65534',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', str(4*1024**3),
                '--memory-swap', str(4*1024**3), '--cpus', '2', '--pids-limit', '32', '--shm-size', '1048576',
                '--log-driver', 'none', '--workdir', '/tmp', '--entrypoint', 'python',
                '--tmpfs', '/tmp:'+TMPFS['/tmp']]
        for k, (a, b) in ULIMITS.items(): args += ['--ulimit', f'{k}={a}:{b}']
        for k in THREADS: args += ['--env', k+'=2']
        args += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
        for dst, src in mounts.items(): args += ['--mount', f'type=bind,src={src},dst={dst},readonly']
        args += [IMAGE, '-I', '-B', '/source/grader.py']
        # Literal CLI is constructed only from the exact mapping inspected below.
        write(run/'ownership.json', {'container': name, 'intent_before_create': True,
                                     'mounts': mounts, 'create_argv': [DOCKER, *args]})
        owned = True
        created = docker(args, work); evidence['create'] = created
        need(created['returncode'] == 0, 'container create failed')
        inspected = docker(['inspect', '--type', 'container', name], work)
        need(inspected['returncode'] == 0, 'inspect failed')
        info = json.loads(inspected['stdout'])[0]
        write(run/'inspection.json', info)
        verify(info, name, mounts, env)
        outcome = docker(['start', '--attach', name], work)
        evidence['worker'] = outcome
        report = json.loads(outcome['stdout'])
        need(not outcome['stderr'] and outcome['returncode'] in (0, 1, 2), 'unexpected worker exit')
        need((outcome['returncode'] == 0) == (report['status'] == 'scored'), 'exit/result consistency')
        evidence['result'] = report; evidence['status'] = report['status']
    except Exception as exc:
        evidence['status'] = 'operator_error'; evidence['error'] = repr(exc)
    finally:
        if owned:
            evidence['cleanup'] = cleanup(name, start+8.5)
        else:
            evidence['cleanup'] = {'absent': True, 'resource_create_not_dispatched': True}
        evidence['wall_seconds'] = time.monotonic()-start
        write(run/'child_receipt.json', evidence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--submission', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--_child', action='store_true')
    parser.add_argument('--_name')
    args = parser.parse_args()
    if args._child:
        run_child(args.submission, Path(args.output), args._name); return 0
    start = time.monotonic()
    child_holder=[None]
    def hard_stop(_signum,_frame):
        try:
            if child_holder[0] is not None:
                try:os.killpg(child_holder[0].pid,signal.SIGKILL)
                except ProcessLookupError:pass
        finally:os._exit(124)  # Journal remains; no inferred cleanup success.
    signal.signal(signal.SIGALRM,hard_stop);signal.setitimer(signal.ITIMER_REAL,12)
    out = Path(os.path.abspath(args.output))
    need(all(not p.is_symlink() for p in (out, *out.parents)), 'output linked path')
    need(not out.exists(), 'output must be a fresh directory')
    out.mkdir(parents=True, mode=0o755)
    run = out/'operator'; run.mkdir(mode=0o755)
    name = 'neural034-score-'+uuid.uuid4().hex[:16]
    write(run/'outer_intent.json', {'container': name, 'whole_call_seconds': 12,
                                   'operator_numerical_scoring_only': True})
    p=None;timed_out=False;controller_errors=[];final_cleanup={'absent':False}
    try:
        p = subprocess.Popen([sys.executable, '-B', str(HERE/'score.py'), '--_child', '--_name', name,
                              '--submission', os.path.abspath(args.submission), '--output', str(run)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        child_holder[0]=p
        write(run/'child_ownership.json',{'pid':p.pid,'process_group':p.pid,'container':name,'argv_source':'exact frozen score.py --_child','journal_before_child_resource_dispatch':True})
        try:p.wait(timeout=max(.001,start+9-time.monotonic()))
        except subprocess.TimeoutExpired:timed_out=True
    except Exception as exc:controller_errors.append(repr(exc))
    finally:
        # Cleanup cannot depend on parsing a worker receipt, including on startup,
        # truncation, timeout or unexpected wait failures.
        if p is not None:
            try:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.wait(timeout=.4)
            except Exception as exc:controller_errors.append('child cleanup:'+repr(exc))
        try:final_cleanup=cleanup(name,start+11.5)
        except Exception as exc:controller_errors.append('container cleanup:'+repr(exc))
    try:
        path=run/'child_receipt.json';lock(path,150000);receipt=json.loads(path.read_text())
        need(type(receipt)is dict and receipt.get('status')in('scored','invalid_submission','operator_error'),'typed worker receipt')
    except Exception as exc:
        controller_errors.append('receipt:'+repr(exc));receipt={'status':'operator_error'}
    child_returncode=p.returncode if p is not None else None
    valid=not timed_out and not controller_errors and child_returncode==0 and final_cleanup['absent']
    status=receipt['status']if valid else'operator_error'
    result=receipt.get('result',{'status':status,'score':None})
    if not valid:result={'status':'operator_error','score':None,'reason':'controller/receipt/cleanup failure'}
    write(out/'score.json', result)
    write(out/'receipt.json', {'status': status, 'result_path': 'score.json', 'worker_receipt': 'operator/child_receipt.json',
         'container': name, 'timed_out': timed_out, 'child_returncode': child_returncode,'controller_errors':controller_errors,
         'independent_final_cleanup': final_cleanup, 'wall_seconds': time.monotonic()-start,
         'no_candidate_code_execution': True, 'model_calls': 0, 'fits': 0,
         'scientific_success_threshold': None, 'score_pin': lock(out/'score.json')})
    print(json.dumps({'status': status, 'score': result.get('score'), 'output': str(out)}))
    signal.setitimer(signal.ITIMER_REAL,0)
    return 0 if status == 'scored' else 2 if status == 'invalid_submission' else 1


if __name__ == '__main__':
    raise SystemExit(main())

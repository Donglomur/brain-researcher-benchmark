"""SOURCE ONLY: 240s protected-owner observer plus bounded30s cleanup grace."""
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


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def bytes_under(path):
    total = 0
    for member in path.rglob('*'):
        info = member.lstat()
        require(not stat.S_ISLNK(info.st_mode), 'private_output_symlink')
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
        else:
            require(stat.S_ISDIR(info.st_mode), 'private_output_special_file')
    return total


def main():
    os.umask(0o077)
    require(len(sys.argv) == 3, 'plan_and_pin_required')
    raw = Path(sys.argv[1]).read_bytes()
    require(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == sys.argv[2], 'plan_identity')
    plan = json.loads(raw)
    require(plan['schema'] == 'nider_protected_outer_plan_v1' and plan['wall_seconds'] == 240 and
            plan['maximum_attempts'] == 1 and plan['whole_private_limit_bytes'] == 16777216, 'plan_scope')
    root = Path(plan['owner_root'])
    require(root.is_dir() and not any(x.is_symlink() for x in (root, *root.parents)), 'owner_root')
    for entry in plan['pins']:
        path = Path(entry['path'])
        require(path.is_absolute() and not any(x.is_symlink() for x in (path, *path.parents)), 'pin_path')
        require(path.stat().st_size == entry['bytes'] and entry['bytes'] <= 8388608, 'pin_size')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'pin_identity')
    work = root / 'execution'
    work.mkdir(mode=0o700)
    (work / 'ATTEMPT_GUARD.json').write_text(json.dumps({'attempt': 1, 'maximum': 1, 'plan_sha256': sys.argv[2]}) + '\n')
    start = time.monotonic()
    child = None
    poller = selectors.DefaultSelector()
    status = {'schema': 'nider_protected_outer_lifecycle_v1', 'plan_sha256': sys.argv[2],
              'argv': plan['argv'], 'attempts': 0, 'pipe_EOF': [], 'reaped': False,
              'termination_reason': None, 'original_streams_complete': True, 'signals': []}
    written = 0
    stopping = None

    def stop(reason):
        nonlocal stopping
        if status['termination_reason'] is None:
            status['termination_reason'] = reason
        if stopping is None:
            stopping = time.monotonic()
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                    status['signals'].append('SIGTERM_owned_process_group')
                except ProcessLookupError:
                    pass

    try:
        with (work / 'stdout.bin').open('xb') as out, (work / 'stderr.bin').open('xb') as err:
            status['attempts'] = 1
            child = subprocess.Popen(plan['argv'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            handles = {'stdout': out, 'stderr': err}
            poller.register(child.stdout, selectors.EVENT_READ, 'stdout')
            poller.register(child.stderr, selectors.EVENT_READ, 'stderr')
            while poller.get_map() or child.poll() is None:
                now = time.monotonic()
                if now - start >= 240:
                    stop('wall_limit')
                if bytes_under(root) > 16777216 - 262144:
                    stop('private_retention_limit')
                if bytes_under(root / 'owner' / 'logs') > 2097152:
                    stop('private_owner_log_extent')
                if stopping is not None and now - stopping > 25:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                        if 'SIGKILL_owned_process_group' not in status['signals']:
                            status['signals'].append('SIGKILL_owned_process_group')
                    except ProcessLookupError:
                        pass
                if stopping is not None and now - stopping > 30:
                    status['original_streams_complete'] = False
                    break
                for event, _ in poller.select(.05):
                    chunk = os.read(event.fileobj.fileno(), 65536)
                    if not chunk:
                        status['pipe_EOF'].append(event.data)
                        poller.unregister(event.fileobj)
                        event.fileobj.close()
                        continue
                    available = 131072 - written
                    if len(chunk) > available:
                        stop('stream_limit')
                        status['original_streams_complete'] = False
                        chunk = chunk[:max(available, 0)]
                    handles[event.data].write(chunk)
                    handles[event.data].flush()
                    written += len(chunk)
            if child.poll() is None:
                stop('incomplete_process')
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            status['exit_code'] = child.wait(timeout=3)
            status['reaped'] = True
    except BaseException as exc:
        stop('observer_failure')
        status['exception_type'] = type(exc).__name__
        status['exception_message'] = str(exc)
        status['original_streams_complete'] = False
        if child is not None:
            grace_remaining = max(0, 25 - (time.monotonic() - stopping)) if stopping is not None else 25
            try:
                status['exit_code'] = child.wait(timeout=grace_remaining)
                status['reaped'] = True
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                    status['signals'].append('SIGKILL_owned_group_after_exception_cleanup_grace')
                except ProcessLookupError:
                    pass
                try:
                    status['exit_code'] = child.wait(timeout=3)
                    status['reaped'] = True
                except subprocess.TimeoutExpired:
                    pass
    finally:
        for item in list(poller.get_map().values()):
            poller.unregister(item.fileobj)
            item.fileobj.close()
        poller.close()
        status['elapsed_seconds'] = time.monotonic() - start
        status['deadline_scope'] = '240s active plus30s cleanup grace, followed by bounded final reap/hash/receipt preservation; not a hard270s total process guarantee'
        status['owned_container_cleanup_verified'] = False
        status['all_four_cases_closed'] = False
        owner_lifecycle = root / 'owner' / 'LIFECYCLE.json'
        if owner_lifecycle.is_file() and owner_lifecycle.stat().st_size <= 1048576:
            owner = json.loads(owner_lifecycle.read_bytes())
            status['owned_container_cleanup_verified'] = bool(owner.get('all_owned_containers_removed') and all(x.get('removed_and_absence_verified') for x in owner.get('cleanup', [])))
            status['all_four_cases_closed'] = bool(owner.get('all_four_closed'))
        status['cleanup_missing_is_failure_not_permission_to_stop_other_jobs'] = True
        status['retained_stream_bytes'] = written
        status['files'] = []
        for path in sorted(root.rglob('*')):
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= 8388608:
                body = path.read_bytes()
                status['files'].append({'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
        body = (json.dumps(status, indent=2) + '\n').encode()
        require(len(body) <= 262144 and bytes_under(root) + len(body) <= 16777216, 'final_retention_limit')
        (work / 'LIFECYCLE.json').write_bytes(body)
        print(json.dumps({'lifecycle': str(work / 'LIFECYCLE.json'), 'bytes': len(body),
                          'sha256': hashlib.sha256(body).hexdigest(), 'exit_code': status.get('exit_code'),
                          'termination_reason': status['termination_reason'], 'reaped': status['reaped'],
                          'both_EOF': set(status['pipe_EOF']) == {'stdout', 'stderr'}}))
    return 0 if status.get('exit_code') == 0 and status['owned_container_cleanup_verified'] and status['all_four_cases_closed'] and status['termination_reason'] is None and status['reaped'] and set(status['pipe_EOF']) == {'stdout', 'stderr'} else 1


if __name__ == '__main__':
    raise SystemExit(main())

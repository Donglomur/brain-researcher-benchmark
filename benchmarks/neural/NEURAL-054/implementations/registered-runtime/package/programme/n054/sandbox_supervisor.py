"""Trusted Linux supervisor; native execution remains unqualified/unexecuted.
Both this file and process_custody.py are separately read-only host mounts.
"""
import importlib.util
import json
import os
import pathlib
import resource
import signal
import time


def main():
    spec = importlib.util.spec_from_file_location('n054_trusted_process_custody', '/process_custody.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    plan = json.loads(pathlib.Path('/input/launch.json').read_text())
    out = pathlib.Path('/work'); out.mkdir(exist_ok=True)
    os.chown(out, 65534, 65534); os.chmod(out, 0o700)
    observations = pathlib.Path('/observed'); observations.mkdir(exist_ok=True)
    def limits():
        os.setsid(); os.setgroups([]); os.setgid(65534); os.setuid(65534)
        resource.setrlimit(resource.RLIMIT_CPU, (plan['cpu_s'], plan['cpu_s']))
        resource.setrlimit(resource.RLIMIT_FSIZE, (plan['output_bytes'], plan['output_bytes']))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128)); os.umask(0o077)
    child = module.OwnedProcess(plan['argv'], plan['wall_s'], plan['collection_wall_s'])
    primary = None; io = None; errors = []
    try:
        with (observations / 'stdout').open('xb') as stdout, (observations / 'stderr').open('xb') as stderr:
            with child:
                proc = child.start(cwd='/work', stdin=-3, stdout=stdout, stderr=stderr, env=plan['env'], preexec_fn=limits)
                forced_deadline = None
                # Keep the original exited actor for /proc IO before wait4 reaps it.
                while os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                    if time.monotonic() - child.started > plan['wall_s']:
                        child.observation['timeout'] = True
                        if forced_deadline is None:
                            child._kill(); forced_deadline = time.monotonic() + plan['collection_wall_s']
                        if time.monotonic() >= forced_deadline:
                            raise RuntimeError('Bounded supervisor readiness wait exhausted')
                    time.sleep(.02)
                try:
                    io = dict((k, int(v)) for k, v in
                              (line.split(':') for line in pathlib.Path(f'/proc/{proc.pid}/io').read_text().splitlines()))
                except (OSError, ValueError) as error:
                    errors.append('Original /proc IO unavailable: ' + str(error))
                child.wait()
    except BaseException as error:
        primary = error
    finally:
        # Even an event/read error cannot bypass termination and the original wait.
        if not child.settled:
            try: child.wait(force=True)
            except BaseException as error:
                errors.append(type(error).__name__ + ': ' + str(error))
                if primary is None: primary = error
        try:
            for p in pathlib.Path('/proc').iterdir():
                if p.name.isdecimal() and int(p.name) not in (1, os.getpid()):
                    try: os.kill(int(p.name), signal.SIGKILL)
                    except ProcessLookupError: pass
        except BaseException as error:
            errors.append('Descendant cleanup: ' + str(error))
            if primary is None: primary = error
    record = {**child.observation, 'io': io, 'argv': plan['argv'], 'cwd': '/work', 'uid': 65534,
              'failure': type(primary).__name__ + ': ' + str(primary) if primary else None,
              'additional_observation_errors': errors,
              'custody_status': 'ORIGINAL_WAIT_AND_GROUP_COMPLETE' if child.settled else 'UNRESOLVED_HOLD',
              'later_container_cleanup': {'attempted': True, 'original_wait_or_group_hold_repaired': False,
                                          'scope': 'separate /proc kill requests, not descendant waits or proved quiescence'},
              'memory_scope': 'wait4 actor and waited descendants; aggregate container memory bounded separately',
              'descendant_accounting': 'UNQUALIFIED until cgroup aggregate CPU/IO/peak evidence is supplied'}
    try:
        with (observations / 'receipt.json').open('x') as stream:
            json.dump(record, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    except BaseException as error:
        # No success marker when receipt custody failed; preserve the first cause.
        record['receipt_retention_error'] = type(error).__name__ + ': ' + str(error)
        if primary is None: primary = error
        primary.original_observation = record
        raise primary
    print('N054_OBSERVED_COMPLETION', flush=True)
    # Host reads the explicit failed/held record too; it never treats this marker as success.
    time.sleep(3 * plan['collection_wall_s'] + 10)


if __name__ == '__main__': main()

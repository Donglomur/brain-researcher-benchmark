"""Inherited trusted barrier leader with an absolute, nonrenewable SMC clock."""
from pathlib import Path
import argparse
import os
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from process_owner import atomic, expected, read, validate_grant, FIXTURE_MODE
from trusted_controller import validate_controller


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--owner', type=Path, required=True)
    p.add_argument('--token', required=True)
    p.add_argument('--channel-fd', type=int, required=True)
    a = p.parse_args()
    pid, pgid, sid = os.getpid(), os.getpgrp(), os.getsid(0)
    if pid <= 1 or pid != pgid or pid != sid:
        raise ValueError('Isolated owned session/group leader required')
    def stop(*unused):
        try:
            os.killpg(pgid, signal.SIGKILL)
        finally:
            os._exit(124)
    try:
        folder = a.owner.parent
        intent = read(folder / 'process_intent.json')
        fixture = intent['mode'] == FIXTURE_MODE
        grant = validate_grant(intent['grant'], fixture=fixture)
        if intent['token'] != a.token or intent['channel_fd'] != a.channel_fd:
            raise ValueError('Bootstrap bound to original intent and channel')
        # Subtract elapsed startup; never grant another full duration here.
        signal.signal(signal.SIGALRM, stop)
        signal.setitimer(signal.ITIMER_REAL, max(.000001, grant['controller_deadline'] - time.monotonic()))
        gate = folder / 'process_gate.json'
        ready_end = min(grant['controller_deadline'], time.monotonic() + 5)
        atomic(folder / 'process_ready.json', {'token': a.token, 'pid': pid, 'pgid': pgid,
                'python_initialized_before_identity_snapshot': True})
        while not gate.exists():
            if time.monotonic() >= ready_end:
                return 3
            time.sleep(.01)
        owner, args = expected(folder, require_remaining=True)
        if (owner['pid'] != pid or owner['token'] != a.token or owner['grant'] != grant
                or read(gate) != {'token': a.token, 'activate': True}):
            raise ValueError('Activation binds exact owned group and original clock')
        argv = owner['child_argv']
        validate_controller(owner['controller'], argv, fixture=fixture)
        child = subprocess.Popen(argv, close_fds=True, pass_fds=(a.channel_fd,))
        atomic(folder / 'process_child.json', {'token': a.token, 'child_pid': child.pid,
                'controller_pgid': pgid, 'observed_birth_identity_claimed': False})
        os.close(a.channel_fd)  # Only the actual controller retains this endpoint.
        code = child.wait()
        atomic(folder / 'process_completion.json', {'token': a.token, 'returncode': code,
                'child_pid': child.pid, 'group_leader_waits_for_owner_stop': True,
                'controller_deadline': grant['controller_deadline']})
        while True:
            time.sleep(.1)
    except BaseException:
        import traceback
        traceback.print_exc()
    finally:
        stop()


if __name__ == '__main__':
    main()

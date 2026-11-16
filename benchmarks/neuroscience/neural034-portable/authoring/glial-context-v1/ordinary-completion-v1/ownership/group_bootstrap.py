"""Trusted barrier/group leader. No work starts before durable activation.

The leader deliberately remains alive after child completion so recovery can
identify the exact group before killing it. It never creates a new subgroup.
"""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from process_owner import atomic,expected,read
from trusted_controller import validate_controller


def main():
    p=argparse.ArgumentParser();p.add_argument('--owner',type=Path,required=True);p.add_argument('--token',required=True);p.add_argument('--seconds',type=float,required=True);a=p.parse_args()
    def stop(*unused):
        try:os.killpg(os.getpgrp(),signal.SIGKILL)
        finally:os._exit(124)
    if not 1<=a.seconds<=470 or os.getpid()!=os.getpgrp():raise ValueError('Isolated bounded group leader required')
    signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,a.seconds)
    folder=a.owner.parent;gate=folder/'process_gate.json';deadline=time.monotonic()+min(5,a.seconds)
    # This Python-level readiness happens only after any framework launcher exec.
    # It authorizes no work: owner+activation remain separate mandatory gates.
    atomic(folder/'process_ready.json',{'token':a.token,'pid':os.getpid(),'pgid':os.getpgrp(),'python_initialized_before_identity_snapshot':True})
    while not gate.exists():
        if time.monotonic()>=deadline:return 3
        time.sleep(.01)
    owner,args=expected(folder)
    if owner['pid']!=os.getpid()or owner['token']!=a.token or read(gate)!={'token':a.token,'activate':True}:raise ValueError('Activation binds exact group')
    argv=owner['child_argv']
    validate_controller(owner['controller'],argv)
    child=subprocess.Popen(argv) # Deliberately stays in our owned process group.
    code=child.wait()
    atomic(folder/'process_completion.json',{'token':a.token,'returncode':code,'child_pid':child.pid,'group_leader_waits_for_owner_stop':True})
    while True:time.sleep(.1)

if __name__=='__main__':
    try:main()
    except BaseException:
        import traceback
        traceback.print_exc()
    finally:
        # No descendant may survive an exceptional leader exit.
        try:os.killpg(os.getpgrp(),signal.SIGKILL)
        finally:os._exit(124)

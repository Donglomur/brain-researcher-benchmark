"""One <=5s trusted process-topology check, with no Docker/data/candidate code."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from process_owner import launch,stop,read
from trusted_controller import descriptor_for


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['test','wrapper','toy']);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.mode=='toy':
        (a.out/'toy_ready').write_text('trusted toy started\n')
        time.sleep(1.25)
        (a.out/'forbidden_late_write').write_text('unrecovered descendant\n')
        return 0
    if a.mode=='wrapper':
        launch([sys.executable,str(HERE/'interrupt_fixture.py'),'toy','--out',str(a.out)],a.out/'owned',4,descriptor_for('authoring/shared-program-ownership-v3/interrupt_fixture.py'))
        while True:time.sleep(.05)
    start=time.monotonic();end=start+5;wrapper=None;result={'status':'started','docker_calls':0,'empirical_reads':0}
    if a.out.exists():raise ValueError('Fresh fixture path')
    a.out.mkdir(mode=0o700);(a.out/'owned').mkdir(mode=0o700)
    def timeout(*unused):raise TimeoutError('Five-second process fixture deadline')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,5)
    try:
        wrapper=subprocess.Popen([sys.executable,'-I','-B',str(HERE/'interrupt_fixture.py'),'wrapper','--out',str(a.out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        while not(a.out/'toy_ready').exists():
            if time.monotonic()>start+2 or wrapper.poll()is not None:raise ValueError('Bounded actual descendant readiness')
            time.sleep(.01)
        owner=read(a.out/'owned'/'process_owner.json')
        if not(a.out/'owned'/'process_gate.json').exists():raise ValueError('Durable activation gate')
        wrapper.kill();stdout,stderr=wrapper.communicate(timeout=.5)
        if len(stdout)>65536 or len(stderr)>65536:raise ValueError('Fixture log cap')
        result['wrapper']={'pid':wrapper.pid,'returncode':wrapper.returncode,'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')}
        row=stop(a.out/'owned',min(end-.5,time.monotonic()+1));result['recovery']=row
        if not row['absence_verified']:raise ValueError('Interrupted wrapper group recovery')
        time.sleep(1.35)
        if(a.out/'forbidden_late_write').exists():raise ValueError('Descendant executed after recovery')
        result.update(status='passed',actual_wrapper_interrupted=True,owned_group_pid=owner['pid'],late_write_absent=True)
    finally:
        if wrapper is not None and wrapper.poll()is None:
            wrapper.kill();wrapper.communicate(timeout=.5)
        result['final_recovery']=stop(a.out/'owned',min(end-.1,time.monotonic()+.5))
        result['elapsed_seconds']=time.monotonic()-start
        (a.out/'fixture.json').write_text(json.dumps(result,indent=2)+'\n')
        signal.setitimer(signal.ITIMER_REAL,0)
    if not result['final_recovery']['absence_verified']:raise ValueError('Fixture final process absence')
    print(json.dumps(result));return 0

if __name__=='__main__':raise SystemExit(main())

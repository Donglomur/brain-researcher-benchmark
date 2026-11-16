"""Root-reviewed sevenfold ordinary program; existing science, task-local lifecycle repair."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,sys,time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from admission import ROOT,ID,RUNTIME_ID,SECONDS,need,ordinary,decode,descriptor,authority
from runtime import load,recover_unit

def recover_run(api,out,end,budget):
    attempt=out/'attempt';rows=[];errors=[];units=api.profile.load()['schedule']['units'];journal=attempt/'units.json'
    values=[]
    try:
        if journal.exists():
            values=decode(ordinary(journal,16384))['units'];need(type(values)is list and len(values)<=7 and [x['unit_id']for x in values]==[f'fold-{i:02d}'for i in range(len(values))],'Fixed ordered attempted units')
        else:need(not attempt.exists()or not any(attempt.glob('fold-*')),'No resources without durable unit intent')
    except BaseException as e:
        errors.append('unit roster: '+repr(e));values=[{'unit_id':u['unit_id'],'output':str(attempt/u['unit_id'])}for u in units if(attempt/u['unit_id']).exists()]  # Fixed paths only; each recovery still authenticates its own create journal.
    for value in reversed(values):
        try:
            need(value['output']==str(attempt/value['unit_id']),'Exact unit path')
            rows.extend(recover_unit(api,Path(value['output']),end-.5,budget,attempt/'program.py',units))
        except BaseException as e:errors.append(value['unit_id']+': '+repr(e))
    try:
        if(attempt/'grade_attempted.json').exists():need((attempt/'grade').is_dir(),'Attempted grader directory missing is unresolved')
        grade=api.grader.recover_grade(attempt/'grade',min(end-.5,time.monotonic()+8))
    except BaseException as e:grade={'absence_verified':False,'error':repr(e)}
    return {'resources':rows,'grade':grade,'errors':errors,'all_owned_absent':not errors and all(x['absence_verified']for x in rows)and grade['absence_verified']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--program',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--other-reserve-bytes',type=int,required=True);a=p.parse_args()
    start=time.monotonic();end=start+SECONDS;proc=None;api=None;out=a.out.absolute();result={'candidate_id':ID,'runtime_id':RUNTIME_ID,'cost_family_id':'astrocyte_source_family','status':'execution_failed_preserved','charged_seconds':SECONDS,'historical_lifetime_complete':False,'all_owned_absent':False,'all_process_groups_absent_and_reaped':False,'all_owned_cli_processes_absent':False,'controller_direct_handle_reaped':False,'descendant_handle_reaping_extent':'not_individually_observed'}
    def hard(*unused):
        try:
            if proc is not None and proc.poll()is None:os.killpg(proc.pid,signal.SIGKILL)
        finally:os._exit(124)
    def interrupted(signum,*unused):raise InterruptedError('Outer signal '+str(signum))
    need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'No conflicting whole timer');signal.signal(signal.SIGALRM,hard);signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted);signal.setitimer(signal.ITIMER_REAL,SECONDS)
    # Admission failure has no task activation or newly owned output; the root observer
    # retains any failed allocation separately. Once admitted, the full480 is recorded.
    admission,bodies,capacity=authority(a.review,a.program,out,a.other_reserve_bytes);api=load(bodies)
    result.update(admission);out.mkdir(mode=0o700);budget=api.HostBudget(out,limit=14000000,reserve=2000000)
    def save(name,v):
        b=(json.dumps(v,indent=2,allow_nan=False)+'\n').encode();need(len(b)<=300000,'Bounded outer metadata');budget.write(out/name,b,receipt=True)
    save('outer_started.json',{'candidate_id':ID,'runtime_id':RUNTIME_ID,'whole_seconds':480,'work_seconds':420,'cleanup_seconds':60,'candidate_seconds_per_fold':20,'folds':7,**admission})
    try:
        du=subprocess.run(['du','-sk',str(ROOT)],capture_output=True,text=True,timeout=min(10,end-time.monotonic()))
        need(du.returncode==0 and not du.stderr and len(du.stdout)<=4096,'Complete fresh project extent');project=int(du.stdout.split()[0])*1024
        st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize;result['storage']=capacity.storage(admission['dynamic_capacity'],project,free)
        argv=[sys.executable,str(HERE/'scheduler.py'),'--program',str(a.program.absolute()),'--out',str(out/'attempt'),'--review',str(a.review.absolute()),'--review-sha256',admission['review_pin']['sha256'],'--parent-work-deadline',str(start+420)]
        need(end-time.monotonic()>=450,'Full ownedgroup/outer cleanup window remains before activation');budget.check(50000,receipt=True);proc=api.owner.launch(argv,out,450,descriptor(HERE/'scheduler.py'))
        while not(out/'process_completion.json').exists():
            need(time.monotonic()<start+420 and proc.poll()is None,'Complete controller within fixedwork window');time.sleep(.02)
        completion=api.owner.read(out/'process_completion.json');owner=api.owner.read(out/'process_owner.json')
        need(completion['token']==owner['token']and completion['group_leader_waits_for_owner_stop']is True,'Exact controller completion');result['returncode']=completion['returncode']
    except BaseException as e:result.update(returncode=-1,error=repr(e))
    finally:
        try:
            group=api.owner.stop(out,min(end-45,time.monotonic()+10),proc);result['controller_group']=group
            need(group['absence_verified'],'Controller group absent before Docker recovery')
            result['all_process_groups_absent_and_reaped']=group['absence_verified']and(proc is None or proc.returncode is not None)
            result['controller_direct_handle_reaped']=proc is None or proc.returncode is not None
            result['all_owned_cli_processes_absent']=group['absence_verified']
            result['cli_absence_basis']='Every owned CLI remains inside the exact controller group; absence is not individual wait-handle reaping evidence.'
            result['cleanup']=recover_run(api,out,end-2,budget);result['all_owned_absent']=result['cleanup']['all_owned_absent']
            execution=out/'attempt/execution.json'
            if execution.exists():
                b=ordinary(execution,300000);v=decode(b);result['inner_execution_sha256']=hashlib.sha256(b).hexdigest()
                if result.get('returncode')in(0,2)and result['all_owned_absent']and v.get('all_owned_absent')is True and v.get('status')in('program_scored','invalid_unit_submission','output_boundary_rejected','candidate_program_failed'):result['status']=v['status']
        except BaseException as e:result['cleanup_or_receipt_error']=repr(e)
        result['elapsed_before_receipt_seconds']=time.monotonic()-start;save('outer_execution.json',result)
    print(json.dumps({'status':result['status'],'output':str(out)}),flush=True);need(time.monotonic()<end,'Terminal return withinwhole allocation')
    return 0 if result['status']=='program_scored'else 2

if __name__=='__main__':raise SystemExit(main())

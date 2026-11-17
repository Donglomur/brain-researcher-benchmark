"""Seven frozen, isolated fold calls; complete public validation before private grade."""
from pathlib import Path
import argparse,hashlib,json,math,os,signal,sys,time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from admission import ROOT,need,ordinary,decode,descriptor,source_gate,runtime_environment
from runtime import load,recover_unit

def main():
    p=argparse.ArgumentParser();p.add_argument('--program',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--review-sha256',required=True);p.add_argument('--parent-work-deadline',type=float,required=True);a=p.parse_args()
    start=time.monotonic();need(math.isfinite(a.parent_work_deadline)and start<a.parent_work_deadline<=start+420,'Bounded parent absolutework deadline');end=min(start+410,a.parent_work_deadline);out=a.out.absolute();result={'candidate_id':'NEURAL-034','status':'started','units':[],'private_grade_dispatched':False,'same_program_frozen_before_any_fold':True};attempted=[]
    def hard(*unused):os._exit(124)
    def stopwork(*unused):
        signal.signal(signal.SIGALRM,hard);signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()));raise TimeoutError('Controller work deadline with cleanup reserve')
    def interrupted(signum,*unused):raise InterruptedError('Controller signal '+str(signum))
    need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'No conflicting timer');signal.signal(signal.SIGALRM,stopwork);signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted);signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()-15))
    body=ordinary(a.review,131072);need(hashlib.sha256(body).hexdigest()==a.review_sha256,'Root review exact parent argument');review=decode(body)
    runtime_environment(review)
    freeze,bodies=source_gate(review['source_freeze']);api=load(bodies)
    owner,_=api.owner.expected(out.parent);need(owner['child_argv']==[sys.executable,*sys.argv]and owner['controller']==descriptor(HERE/'scheduler.py'),'Exact activated v4 controller identity')
    need(not out.exists()and out.is_relative_to(ROOT/'artifacts-build')and all(not x.is_symlink()for x in(out,*out.parents)),'Fresh operator attempt');out.mkdir(mode=0o700)
    budget=api.HostBudget(out.parent,limit=14000000,reserve=2000000);profile=api.profile.load();units=profile['schedule']['units'];program=out/'program.py'
    def save(name,v):
        raw=(json.dumps(v,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=300000,'Bounded controller metadata');budget.write(out/name,raw,receipt=True)
    try:
        body=api.snapshot(a.program);need({'path':a.program.absolute().relative_to(ROOT).as_posix(),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}==review['program_source'],'Reviewed program snapshot')
        budget.write(program,body,mode=0o444);program_sha=hashlib.sha256(body).hexdigest()
        save('program_commit.json',{'candidate_id':'NEURAL-034','bytes':len(body),'sha256':program_sha,'committed_before_first_fold_release':True,'source_freeze':review['source_freeze']});result['program_sha256']=program_sha
        previous=None;packets=[]
        for unit in units:
            need(end-time.monotonic()>=73,'Full48s unit plus25s grade/finalization reserve')
            destination=out/unit['unit_id'];attempted.append({'unit_id':unit['unit_id'],'output':str(destination),'previous_commit_sha256':previous})
            budget.check(20000,receipt=True);api.owner.atomic(out/'units.json',{'units':attempted})
            record=api.unit.run_unit(program,program_sha,unit,destination,budget,end-25,end,previous,profile['id'],lambda b,u:api.assembler.validate(b,u['expected_ids']))
            result['units'].append({'unit_id':unit['unit_id'],'status':record['status'],'all_owned_absent':record['all_owned_absent'],'execution_sha256':api.digest(destination/'execution.json')})
            need(record['all_owned_absent'],'No release before prior resources absent')
            if record['status']!='unit_committed':result['status']=record['status'];return 2
            raw=ordinary(destination/'commit.json',100000);output=ordinary(destination/unit['output_filename'],100000);previous=hashlib.sha256(raw).hexdigest();need(previous==record['commit_sha256'],'Exact commit')
            packets.append({'commit_bytes':raw,'output_bytes':output})
        aggregate=api.assembler.assemble(packets,units,program_sha);submission=out/'probabilities.json';budget.write(submission,aggregate,mode=0o444)
        save('aggregate_commit.json',{'status':'all_seven_removed_producers_committed','candidate_id':'NEURAL-034','program_sha256':program_sha,'unit_commit_sha256':[hashlib.sha256(x['commit_bytes']).hexdigest()for x in packets],'submission_sha256':hashlib.sha256(aggregate).hexdigest(),'source_freeze':review['source_freeze'],'all_units_absent_before_private_grade':True,'last_commit_sha256':previous})
        need(end-time.monotonic()>=25,'Complete private grade allowance');save('grade_attempted.json',{'attempted':True,'output':str(out/'grade')});result['private_grade_dispatched']=True
        result['grade']=api.grader.grade(submission,out/'grade',budget);need(result['grade']['status']=='scored','Full valid aggregate scored');result['status']='program_scored';return 0
    except BaseException as e:result.update(status='execution_failed_preserved',error=repr(e));return 2
    finally:
        signal.signal(signal.SIGALRM,hard);signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()));cleanup=[]
        try:
            if(out/'grade_attempted.json').exists():need((out/'grade').is_dir(),'Attempted grader missing directory is unresolved')
            result['grader_cleanup']=api.grader.recover_grade(out/'grade',min(end-.5,time.monotonic()+5))
        except BaseException as e:result['grader_cleanup']={'absence_verified':False,'error':repr(e)}
        for item in reversed(attempted):
            try:cleanup.extend(recover_unit(api,Path(item['output']),end-.5,budget,program,units))
            except BaseException as e:result.setdefault('cleanup_errors',[]).append(repr(e))
        result['owned_cleanup']=cleanup;result['all_owned_absent']=all(x['absence_verified']for x in cleanup)and result['grader_cleanup']['absence_verified']and not result.get('cleanup_errors')
        if not result['all_owned_absent']:result['status']='failed_cleanup'
        result['wall_seconds_before_receipt']=time.monotonic()-start;save('execution.json',result)

if __name__=='__main__':raise SystemExit(main())

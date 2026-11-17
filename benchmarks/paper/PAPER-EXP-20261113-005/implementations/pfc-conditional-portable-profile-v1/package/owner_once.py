"""Reusable PFC two-program delivery and protected unchanged scoring."""
import time
START=time.monotonic()
import json
import os
from pathlib import Path
import signal
import sys
sys.path.insert(0,str(Path(__file__).absolute().parent))
from route_binding import (HERE,MIB,IMAGE,PYTHON,DEADLINES,OUTPUT_CAPS,MANAGED_CAP,RETAINED_CAP,
    ordinary,exact,extent,module,need,write_new,load_request,candidate_mounts,validate_runtime,stream_candidate)

class Failures:
    """The primary failure survives secondary receipt/cleanup errors."""
    def __init__(self):
        self.first=None;self.work=None;self.cleanup_errors=[];self.publication_errors=[];self.other_errors=[]
    def record(self,error,phase,kind,stage):
        row={'class':type(error).__name__,'message':str(error)[:4000],'phase':phase,'active_stage':stage}
        if hasattr(error,'stream_failure_custody'):row['stream_failure_custody']=error.stream_failure_custody
        if self.first is None:self.first=row
        if kind=='work' and self.work is None:self.work=row
        if kind=='cleanup':self.cleanup_errors.append(row)
        elif kind=='publication':self.publication_errors.append(row)
        elif kind!='work':self.other_errors.append(row)
        return row
    def publish(self,writer,name,value,stage):
        try:writer(name,value);return True
        except BaseException as error:self.record(error,'publish:'+str(name),'publication',stage);return False
    def snapshot(self):
        return {'first_failure':self.first,'primary_work_failure':self.work,'cleanup_errors':list(self.cleanup_errors),
                'publication_errors':list(self.publication_errors),'other_errors':list(self.other_errors)}

def main():
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,'isolated no-site owner')
    need(len(sys.argv)==4,'request path/bytes/hash')
    pin,r,p,root=load_request(sys.argv[1],int(sys.argv[2]),sys.argv[3])
    from deployment import authenticate_source_graph, authenticate_deployment, preflight_reservation, configure_client, limits
    from compatibility import inspect_score, hash_owned
    authenticate_source_graph(r,HERE)
    authenticate_deployment(r,p)
    identity_user=str(r['deployment']['uid'])+':'+str(r['deployment']['gid'])
    for source in list(r['source_files'].values())+list(r['programs'].values())+list(p['scorer_sources'].values())+[p['inherited_owner'],p['inherited_outer'],p['negative_source']]:exact(source)
    for source in p['common_assistance'].values():exact(source)
    for source in p['additional_B_assistance'].values():exact(source)
    engine=module(p['inherited_owner'],'_accepted_pfc_lifecycle')
    selected=limits(r);DEADLINES=selected['deadlines'];OUTPUT_CAPS=selected['output_caps']
    MANAGED_CAP=selected['managed_cap'];RETAINED_CAP=selected['retained_cap']
    engine.START=START;engine.END=START+selected['owner_seconds'];engine.WORK_END=engine.END-30
    engine.IMAGE=IMAGE;engine.OWNER='pfc-participant-'+r['attempt'];engine.HOST_READ=0;engine.HOST_CAP=6*MIB
    ordinary(root);root.mkdir(mode=0o700,exist_ok=False)
    (root/'owner').mkdir(mode=0o700);(root/'artifacts').mkdir(mode=0o700)
    failures=Failures();completed=[];submissions={};active=None;managed=preflight_reservation(r);retained=16*MIB
    def cancelled(*unused):raise TimeoutError('original selected owner deadline/cancelled')
    signal.signal(signal.SIGTERM,cancelled);signal.signal(signal.SIGINT,cancelled)
    signal.signal(signal.SIGALRM,cancelled);signal.setitimer(signal.ITIMER_REAL,max(.001,engine.END-time.monotonic()))
    write_new(root/'OWNER_INTENT.json',{'request':pin,'start':START,'end':engine.END,'one_attempt':True,'science_unchanged':True})
    stage_names=['binding_and_participant_controls','participant_A','participant_B','score_A','score_B']
    compatibility={};negative_submission=None
    if r['compatibility']:stage_names+=['negative_submission','negative_score']
    try:
        engine.OUT=root/'owner'/'runtime-preflight';engine.OUT.mkdir(mode=0o700)
        configure_client(engine,r,root)
        daemon=engine.call(['info','--format','{{.ID}}'])[1].strip()
        need(daemon==r['deployment']['daemon_id'],'selected Docker daemon identity')
        for index,name in enumerate(stage_names):
            active=index
            need(time.monotonic()+DEADLINES[index]+30<engine.END,'original remaining bound before dispatch')
            managed += selected['managed_stages'][index]*MIB
            retained += OUTPUT_CAPS[index]
            need(managed<=MANAGED_CAP and retained<=RETAINED_CAP,'complete selected budget reservation')
            stage_root=root/'owner'/name;stage_root.mkdir(mode=0o700)
            output=root/'artifacts'/name;output.mkdir(mode=0o700)
            engine.OUT=stage_root;engine.EVENTS=[];engine.CID=None;engine.NAME=None
            engine.PROFILE={'worker_retention_bytes':OUTPUT_CAPS[index]}
            extra_env=[]
            if index==0:
                mounts=[(str(HERE/'route_binding.py'),'/control/route_binding.py',False),
                        (str(HERE/'route_controls.py'),'/control/route_controls.py',False)]
                mounts += [(str(HERE/n),'/control/'+n,False) for n in ('deployment.py','profile.py')]
                code="import runpy,sys;sys.path.insert(0,'/control');assert sys.version.split()[0]=='3.12.8'\nfor f in ['route_controls.py']:\n sys.argv=[f]\n try:runpy.run_path('/control/'+f,run_name='__main__')\n except SystemExit as e:\n  assert e.code in (None,0),f+' failed'\n"
                argv=['-B','-c',code]
            elif index in (1,2):
                arm='A' if index==1 else 'B'
                # Complete packet was authenticated before any container creation.
                exact(r['programs'][arm])
                mounts=candidate_mounts(r,p,arm)
                argv=['-I','-B','/candidate/solution.py','--packet','/input/participant-packet.json','--output','-']
            elif index==5:
                need(set(compatibility)=={'A','B'},'both complete positive compatibility checks before negative')
                mounts=[(p['negative_source']['path'],'/negative/make_negative_submission.py',False),
                        (p['scorer_sources']['endpoint_cli.py']['path'],'/negative/endpoint_cli.py',False),
                        (p['scorer_sources']['conditional_kernel.py']['path'],'/negative/conditional_kernel.py',False),
                        (submissions['A']['path'],'/input/reference.jsonl',False),(str(output),'/output',True)]
                argv=['-B','/negative/make_negative_submission.py','--reference','/input/reference.jsonl','--output','/output/negative.jsonl']
            else:
                arm='A' if index==3 else 'B' if index==4 else 'negative'
                need(set(submissions)=={'A','B'},'both participants closed before target scoring')
                binding={'schema':'PFC_ONE_PROTECTED_SCORE_V1','arm':arm,'packet':p['packet'],
                         'submission':negative_submission if index==6 else submissions[arm],'scorer_sources':p['scorer_sources']}
                binding_pin=write_new(stage_root/'SCORE_INPUT_BINDING.json',binding)
                mounts=[(pin0['path'],'/scoring/'+n,False) for n,pin0 in p['scorer_sources'].items()]
                mounts += [(str(HERE/'score_entry.py'),'/binding/score_entry.py',False),
                           (binding_pin['path'],'/binding/score-input.json',False),
                           (p['packet']['path'],'/input/participant-packet.json',False),
                           (binding['submission']['path'],'/submission/submission.jsonl',False),
                           (str(output),'/output',True)]
                extra_env=['--env','PFC_SCORE_BINDING_SHA256='+binding_pin['sha256']]
                argv=['-B','/binding/score_entry.py']
            for source,destination,writable in mounts:
                ordinary(source)
                if not writable:extent(source,128*MIB)
            engine.save('STAGE_INTENT.json',{'index':index,'name':name,'request':pin,'argv':argv,'mounts':mounts,
                        'seconds':DEADLINES[index],'managed_reserved':managed,'retention_reserved':retained})
            clean=None;creation=False;submission=None
            try:
                engine.NAME='nb-pfc-participant-'+r['attempt']+'-'+str(index+1)
                need(engine.inspect(engine.NAME,absent=True) is None,'fresh exact container name')
                engine.save('CREATE_INTENT.json',{'name':engine.NAME,'image':IMAGE,'owner':engine.OWNER,'argv':argv,'attempts':1})
                command=['create','--name',engine.NAME,'--label','org.neurobench.owner='+engine.OWNER,
                         '--pull=never','--network=none','--user',identity_user,'--memory=4g','--memory-swap=4g',
                         '--cpus=2','--pids-limit=64','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                         '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=256m']
                for source,destination,writable in mounts:
                    command+=['--mount','type=bind,src='+source+',dst='+destination+('' if writable else ',readonly')]
                command+=['--env','OPENBLAS_NUM_THREADS=1','--env','OMP_NUM_THREADS=1','--env','PYTHONDONTWRITEBYTECODE=1',*extra_env,
                          '--entrypoint',PYTHON,IMAGE,*argv]
                creation=True
                identity=engine.call(command)[1].strip();need(engine.sha(identity),'immutable created CID')
                engine.CID=identity;engine.save('CID.json',{'cid':identity,'name':engine.NAME})
                before=engine.inspect(identity);engine.save('PRESTART.json',before)
                need(engine.owned(before)==identity,'owned immutable CID')
                validate_runtime(before,argv,mounts)
                user=json.loads(engine.call(['inspect','--type=container','--format','{{json .Config.User}}',identity])[1])
                need(user==identity_user,'actual nonroot identity')
                if index in (1,2):
                    submission,event=stream_candidate(engine,['start','-a',identity],DEADLINES[index],output/'submission.jsonl')
                else:engine.call(['start','-a',identity],timeout=DEADLINES[index])
                after=engine.inspect(identity);engine.save('POSTRUN.json',after)
                need(engine.owned(after)==identity and after['state']['Status']=='exited' and
                     after['state']['ExitCode']==0 and after['state']['OOMKilled'] is False,'natural zero/no OOM')
                inventory=engine.output_inventory(output);engine.save('OUTPUT_INVENTORY.json',inventory)
                if index in (1,2):
                    need(inventory=={'entries':1,'bytes':submission['bytes']},'only complete captured participant file')
                    exact(r['programs'][arm])
                elif index==5:
                    need(inventory['entries']==1 and extent(output/'negative.jsonl',128*MIB)==inventory['bytes'],'one complete negative submission')
                    os.chmod(output/'negative.jsonl',0o400)
                    negative_submission=hash_owned(output/'negative.jsonl',128*MIB)
                elif index in (3,4,6):
                    need(inventory['entries']==1 and extent(output/'score.json',64*MIB)==inventory['bytes'],'one complete private score report')
                    os.chmod(output/'score.json',0o400)
                    if r['compatibility']:
                        compatibility[arm]=inspect_score(output/'score.json',binding['submission']['sha256'],negative=index==6)
            except BaseException as error:
                error_row=failures.record(error,'stage_work','work',index)
                failures.publish(engine.save,'FAILURE.json',error_row,index)
            finally:
                try:
                    clean=engine.cleanup_owned() if creation else {'status':'NO_CREATE_ATTEMPTED','removed':False}
                    failures.publish(engine.save,'CLEANUP.json',clean,index)
                except BaseException as error:
                    row=failures.record(error,'owned_cleanup','cleanup',index)
                    failures.publish(engine.save,'CLEANUP_FAILURE.json',row,index)
            need(failures.first is None and clean and clean.get('removed') is True,'preserved stage failure; stop without retry')
            if index in (1,2):
                submissions[arm]=submission
                engine.save('FROZEN_SUBMISSION.json',{'submission':submission,'program':r['programs'][arm],
                            'arm':arm,'candidate_closed_before_assessment':True,'no_reference_or_scorer_mount':True})
            stage_result={'index':index,'name':name,'natural_zero':True,'cleanup':clean,'inventory':inventory,
                          'managed_reserved':managed,'retention_reserved':retained}
            engine.save('STAGE_RESULT.json',stage_result);completed.append(stage_result);active=None
        exact(p['packet'],16*MIB)
        authenticate_deployment(r,p,postflight=True)
        need(len(completed)==len(stage_names) and set(submissions)=={'A','B'},'complete protected operation')
        if r['compatibility']:need(set(compatibility)=={'A','B','negative'},'complete compatible positive and negative cases')
        authenticate_source_graph(r,HERE)
    except BaseException as error:failures.record(error,'owner_sequence','other',active)
    result={'schema':'PFC_PROTECTED_PARTICIPANT_OWNER_RESULT_V1','request':pin,'complete':failures.first is None and len(completed)==len(stage_names),
            'stages':completed,'submissions':submissions,'compatibility_checks':compatibility,'negative_submission':negative_submission,'failure':failures.first,'failure_custody':failures.snapshot(),
            'managed_reserved':managed,'retention_reserved':retained,'seconds':time.monotonic()-START,
            'local_ready_admission':False,'model_performance':'unmeasured','historical_equivalence':False,'retry':False}
    published=failures.publish(write_new,root/'OWNER_RESULT.json',result,active)
    if not published:result['complete']=False
    print(json.dumps({'complete':result['complete'],'stages':len(completed),'failure_custody':failures.snapshot(),
                      'owner_result_published':published,'result':str(root/'OWNER_RESULT.json')}),flush=True)
    need(time.monotonic()<engine.END,'original owner bound before return')
    return 0 if result['complete'] else 1

if __name__=='__main__':raise SystemExit(main())

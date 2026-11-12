"""Shared one-unit adapter around the inherited qualified transport lifecycle."""
from pathlib import Path
import base64,hashlib,json,time,uuid
from qualified_core import regular,digest
from engine_profile import ProfileEngine
from profile import need,runtime
from ordinary_support import admit_unit, verified_input_mounts
HERE=Path(__file__).resolve().parents[3]/'shared-large-npz-runner-v1';ROOT=HERE.parents[1]


def run_unit(program,program_sha,unit,out,budget,work_end,whole_end,previous,candidate_id,validate_output):
    started=time.monotonic();out.mkdir(mode=0o700);engine=ProfileEngine(min(work_end,started+40),out,budget,runtime(unit));clean={};candidate=None
    result={'candidate_id':candidate_id,'unit_id':unit['unit_id'],'status':'started','program_sha256':program_sha,'timeline':[]}
    def event(name):result['timeline'].append({'event':name,'monotonic':time.monotonic()})
    def cleanup():
        for row in reversed(engine.owned):
            key=(row['kind'],row['name']);prior=clean.get(key)
            if not prior or not prior['absence_verified']:
                clean[key]=engine.cleanup(*key)
                if prior:clean[key]['previous_attempt']=prior
        return len(clean)==len(engine.owned)and all(x['absence_verified']for x in clean.values())
    try:
        need(digest(program)==program_sha,'Same committed program before unit release')
        admit_unit(unit, program_sha)
        inputs=verified_input_mounts(unit,program_sha)
        event('active_unit_release')
        suffix=uuid.uuid4().hex;vol='dmfc-prog-volume-'+suffix;holder='dmfc-prog-holder-'+suffix;candidate='dmfc-prog-worker-'+suffix
        engine.volume(vol)
        hm={'/trusted/holder.py':{'type':'bind','source':str(HERE/'holder_profile.py'),'rw':False},'/capture':{'type':'volume','source':vol,'rw':False}}
        _,boundary=engine.create(holder,'holder',hm);result['holder_boundary']=boundary
        need(engine.run(['start',holder]).returncode==0,'Holder start');ready=min(engine.end,time.monotonic()+8)
        while True:
            need(time.monotonic()<ready,'Bounded holder ready');logs=engine.run(['logs',holder],timeout=2,cap=65536)
            need(engine.inspect('container',holder)['State']['Running'],'Holder preserves output tmpfs')
            if logs.stdout==b'HOLDER_READY\n':break
            time.sleep(.05)
        cm={'/program/program.py':{'type':'bind','source':str(program),'rw':False},'/output':{'type':'volume','source':vol,'rw':True}}
        cm.update({dest:{'type':'bind','source':str(path),'rw':False}for dest,path in inputs.items()})
        info,boundary=engine.create(candidate,'candidate',cm);result.update(candidate_boundary=boundary,candidate_requested_mounts=cm,producer={'name':candidate,'container_id':info['Id']})
        need(engine.end-time.monotonic()>=23,'Full20-second producer window plus3-second capture/cleanup reserve before start')
        start=time.monotonic();event('candidate_start_requested')
        try:
            need(engine.run(['start',candidate]).returncode==0,'Candidate start')
            left=20-(time.monotonic()-start);need(left>0,'Candidate20s work allowance')
            waited=engine.run(['wait',candidate],timeout=left);need(waited.returncode==0,'Candidate wait')
            need(time.monotonic()-start<20,'Original20-second producer deadline after wait')
        except BaseException:
            requested=time.monotonic();event('candidate_stop_requested_after_wait_failure')
            try:
                call=engine.run(['kill','--signal','KILL',candidate],timeout=2)
                result['deadline_stop']={'returncode':call.returncode,'request_latency_seconds':time.monotonic()-requested,'requested_after_start_seconds':requested-start}
            except BaseException as e:result['deadline_stop']={'error':repr(e)}
            raise
        state=engine.inspect('container',candidate)['State'];result['candidate_stopped_state']=state
        need(not state['Running']and state['Pid']==0 and not state['OOMKilled'],'Candidate stopped before log/capture')
        result['candidate_logs']=engine.logs(candidate);event('candidate_stopped')
        clean[('container',candidate)]=engine.cleanup('container',candidate);need(clean[('container',candidate)]['absence_verified'],'Producer absent before capture');event('candidate_removed_and_absent')
        if state['ExitCode']!=0:result.update(status='candidate_program_failed',exit_code=state['ExitCode']);return result
        args=['exec',holder,'python','-I','/trusted/holder.py','capture','--output-name',unit['output_filename'],'--max-output-bytes',str(unit['max_output_bytes'])]
        captured=engine.run(args,timeout=8,cap=22000000);need(captured.returncode==0 and len(captured.stderr)<=65536,'Trusted bounded capture')
        obj=json.loads(captured.stdout)
        if obj.get('status')=='output_boundary_rejected':result.update(status='output_boundary_rejected',capture=obj);return result
        need(set(obj)=={'status','name','bytes','sha256','base64'}and obj['status']=='captured'and obj['name']==unit['output_filename']and type(obj['bytes'])is int and 0<obj['bytes']<=unit['max_output_bytes']and type(obj['base64'])is str and len(obj['base64'])<=4*((unit['max_output_bytes']+2)//3),'Exact bounded capture schema')
        raw=base64.b64decode(obj['base64'],validate=True);need(len(raw)==obj['bytes']and hashlib.sha256(raw).hexdigest()==obj['sha256'],'Opaque captured identity')
        output=out/unit['output_filename'];budget.write(output,raw,mode=0o444);result['output']={k:obj[k]for k in('bytes','sha256')};event('opaque_output_captured')
        need(cleanup(),'All candidate/holder/volume absent before public validation or next release');event('unit_resources_removed')
        try:validate_output(raw,unit)
        except Exception as e:result.update(status='invalid_unit_submission',validation_error=str(e));return result
        need(digest(program)==program_sha,'Program unchanged across unit')
        commit={'status':'removed_producer_output_committed','candidate_id':candidate_id,'unit_id':unit['unit_id'],'program_sha256':program_sha,'previous_commit_sha256':previous,'producer':result['producer'],'public_inputs':unit['public_inputs'],'output':result['output'],'producer_removed_before_capture':True,'all_candidate_holder_volume_absent':True,'timeline':result['timeline']}
        commitpath=engine.write('commit.json',commit);result['commit_sha256']=digest(commitpath);event('unit_committed_before_next_release');result['status']='unit_committed';return result
    except BaseException as e:result.update(status='execution_failed_preserved',error=repr(e));return result
    finally:
        engine.end=min(whole_end-.5,time.monotonic()+8)
        if candidate is not None and not clean.get(('container',candidate),{}).get('absence_verified'):
            requested=time.monotonic()
            try:
                engine.run(['kill','--signal','KILL',candidate],timeout=2);state=engine.inspect('container',candidate)['State']
                result['final_stop']={'latency_seconds':time.monotonic()-requested,'state':state}
                if not state['Running']and state['Pid']==0:engine.write('failed_candidate_logs.json',engine.logs(candidate))
            except Exception as e:result['final_stop_error']=repr(e)
        result['all_owned_absent']=cleanup();result['cleanup']=list(clean.values());result['commands']=engine.commands;result['elapsed_before_receipt_seconds']=time.monotonic()-started
        if not result['all_owned_absent']:result['status']='failed_cleanup'
        engine.write('execution.json',result,cap=250000)

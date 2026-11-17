"""One committed program, all650 independent native contexts, no private grading."""
import os,re,signal,sys,time
from pathlib import Path
from common import need,before,path,capture,decode,encode,short,write,syncdir,inventory,identity,KEYS,FILES,PRED,VIEW,PHASE,RETAIN,READS,WRITES,FLOOR,MIB,Budget

def whole_seconds(seconds):return 650*(seconds+840)+7320

def validate_selection(s,source,bodies):
    need(type(s)is dict and set(s)=={'schema','execution_selected','task_id','source','collection','output','program','program_review','runtime_qualification','image','docker_binary','docker_socket','candidate_seconds','memory_bytes','other_future_bytes','whole_seconds','retained_bytes','managed_reads','managed_writes'},'exact root selection')
    need(s['schema']=='neural076_full650_selection_v1'and s['execution_selected']is True and s['task_id']=='NEURAL-076'and s['source']==source,'explicit exact full650 selection')
    need(type(s['candidate_seconds'])is int and 1<=s['candidate_seconds']<=7200 and type(s['memory_bytes'])is int and 512*MIB<=s['memory_bytes']<=4*2**30 and s['memory_bytes']%MIB==0,'preselected candidate resources')
    need(s['whole_seconds']==whole_seconds(s['candidate_seconds'])and s['retained_bytes']==RETAIN+MIB and s['managed_reads']==READS and s['managed_writes']==WRITES and type(s['other_future_bytes'])is int and s['other_future_bytes']>=0,'complete resource envelope')
    need(type(s['image'])is str and re.fullmatch('sha256:[a-f0-9]{64}',s['image']),'existing immutable image')
    for name in('collection','output','docker_binary','docker_socket'):need(type(s[name])is str and len(s[name].encode())<=256 and Path(s[name]).is_absolute(),'bounded absolute root operand');path(s[name])
    for name in('program','program_review','runtime_qualification'):
        row=s[name];need(type(row)is dict and set(row)=={'path','bytes','sha256'}and type(row['bytes'])is int and 0<row['bytes']<=(131072 if name=='program'else 65536)and re.fullmatch('[a-f0-9]{64}',row['sha256']),'bounded fixed operand');need(Path(row['path']).is_absolute(),'absolute operand')
    lock=decode(bodies['LOCK.json']);need(lock['task_id']=='NEURAL-076'and lock['full_scope']['contexts']==650,'fixed full scope')
    raw,_=capture(s['program_review']['path'],65536,s['program_review']);review=decode(raw)
    need(review=={'schema':'neural076_program_procedural_review_v1','program':{k:s['program'][k]for k in('bytes','sha256')},'source':source,'training_only_transforms':True,'pointwise_query_prediction':True,'no_cross_context_state':True,'max_voxels_per_unit':316,'reviewed':True,'input_dependence_empirically_proven':False},'source-bound procedural review; not empirical proof')
    raw,_=capture(s['runtime_qualification']['path'],65536,s['runtime_qualification']);qualification=decode(raw)
    need(qualification=={'schema':'neural076_full650_runtime_qualification_v1','source':source,'image':s['image'],'python':'3.11.13','dependencies':lock['expected_dependencies'],'host_python':str(Path(sys.executable).resolve()),'docker_binary':s['docker_binary'],'docker_socket':s['docker_socket'],'source_directory':str(Path(__file__).absolute().parent),'candidate_seconds':s['candidate_seconds'],'candidate_memory_bytes':s['memory_bytes'],'staging_candidate_collection_capabilities_qualified':True,'scientific_performance_qualified':False,'exclusive_operator_owned_source_collection_output':True,'same_filesystem_no_concurrent_writers':True,'candidate_has_no_host_or_socket_access':True},'exact separately supplied runtime qualification')
    return lock

def freeze(s,source,root,budget):
    raw,p=capture(s['program']['path'],131072,s['program'],tick=budget.tick);raw.decode('utf-8');program=root/'program';budget.mkdir(program,0o755);budget.check(len(raw)+65536);write(program/'program.py',raw,131072)
    commit={'schema':'neural076_frozen_program_v1','source':source,'program':p,'keys':list(KEYS),'image':s['image'],'candidate_seconds':s['candidate_seconds'],'memory_bytes':s['memory_bytes'],'procedural_review':s['program_review'],'runtime_qualification':s['runtime_qualification'],'condition':'full650_feature_recovery','feedback_before_commitment':False}
    cp=budget.save(program/'COMMIT.json',commit,131072);program.chmod(0o555);syncdir(program);syncdir(root);return cp

def child_closed(record):
    need(record['natural_exit']is True and record['exit_code']==0 and record['process_reaped']is True and record['process_group_absent']is True and record['streams_closed']is True and record['streams_eof']is True and record['timed_out']is False and record['error_type']is None and record.get('timer_disable_error')is None and record.get('timer_restore_error')is None,'observed natural zero and full owned process closure')

def phase(mode,key,s,source,root,commit,budget,loader,here,ordinal):
    seconds=300 if mode=='stage'else(s['candidate_seconds']+480 if mode=='candidate'else 7200);end=min(budget.end-30,time.monotonic()+seconds);need(end>time.monotonic()+60,'complete phase allowance')
    folder=root/'phases'/f'{ordinal:04d}-{mode}';view=root/'current'/key.replace('/','__')if key else root/'submission'
    # Reservations are charged before dispatch, including failed or unused work.
    reads,writes=(1_100_000_000,280_000_000)if mode=='stage'else((1_300_000_000,PHASE)if mode=='candidate'else(80_000_000_000,2*MIB))
    budget.charge(mode,key,reads,writes)
    req={'schema':'neural076_owned_phase_request_v1','source':source,'selection':s,'mode':mode,'key':key,'folder':str(folder),'view':str(view),'end':end,'other':budget.other_for_phase(PHASE if mode=='candidate'else (2*MIB+VIEW+65536 if mode=='stage'else 2*MIB)),'commit':commit}
    request=root/'requests'/f'{ordinal:04d}-{mode}.json';rp=budget.save(request,req,131072)
    argv=[str(Path(sys.executable).resolve()),'-I','-S','-B',str(here/'phase.py'),'--source-sha256',source['sha256'],'--request',str(request),'--request-sha256',rp['sha256']]
    process=loader('process');failure=None;streams=None;record=None
    try:streams,record=process.run(argv,end-10,end,{'PATH':'/usr/bin:/bin:/usr/local/bin','LANG':'C','LC_ALL':'C','PYTHONNOUSERSITE':'1'},cwd=str(here),cap=8192,accepted=(0,))
    except process.ChildFailure as exc:record=exc.record;failure='owned_phase_failure'
    obs={'schema':'neural076_outer_phase_observer_v1','request':rp,'source':source,'mode':mode,'key':key,'lifecycle':record,'failure':failure,'end':end,'observed':time.monotonic()}
    op=budget.save(root/'observations'/f'{ordinal:04d}-{mode}.json',obs,16384);need(failure is None,'closed phase required');child_closed(record);before(end)
    term=decode(streams['stdout']);need(set(term)=={'completion','folder'}and term['folder']==str(folder),'exact phase terminal')
    raw,p=capture(folder/'COMPLETE.json',262144,term['completion'],tick=lambda:before(end));value=decode(raw)
    need(value['schema']=='neural076_phase_complete_v1'and value['source']==source and value['mode']==mode and value['key']==key and value['private_gold_opened']is False and value['scientific_scoring']is False,'same closed full-context phase')
    budget.check();return value['result'],{'observer':op,'completion':p,'folder':str(folder)}

def move_prediction(key,result,evidence,root,source,commit,budget):
    need(result['key']==key and result['commit']==commit and result['all_resources_closed']is True and result['producer_removed_before_capture']is True,'same complete candidate result')
    src=path(evidence['folder'])/'predictions.npz';dst=root/'submission'/(key.replace('/','__')+'.npz');need(not os.path.lexists(dst)and src.stat().st_dev==dst.parent.stat().st_dev,'same-filesystem fresh final leaf')
    _,p=capture(src,PRED,result['prediction'],body=False,tick=budget.tick);held=identity(src.lstat())
    intent=budget.save(root/'moves'/(key.replace('/','__')+'.intent.json'),{'source':source,'commit':commit,'key':key,'prediction':p,'from':str(src),'to':str(dst),'owned_closed_phase':evidence},16384)
    need(identity(src.lstat())==held,'unchanged owned leaf');os.rename(src,dst);syncdir(src.parent);syncdir(dst.parent)
    need(not os.path.lexists(src)and dst.stat().st_ino==held[1]and dst.stat().st_dev==held[0],'exact durable move');capture(dst,PRED,p,body=False,tick=budget.tick)
    ack=budget.save(root/'moves'/(key.replace('/','__')+'.ack.json'),{'key':key,'intent':intent,'prediction':p,'path':dst.name,'same_inode':True,'copied':False},8192)
    return {'key':key,'path':dst.name,'prediction':p,'move':ack,'closed_phase':evidence}

def retire_view(key,binding,candidate,root,budget):
    view=root/'current'/key.replace('/','__');need(candidate['input']==binding and candidate['key']==key,'same closed view authority');files,dirs,_=inventory(view,8);need(set(files)==FILES and dirs==[view],'exact owned retirement set')
    for name,p in binding['files'].items():capture(view/name,VIEW,p,body=False,tick=budget.tick)
    custody={n:identity((view/n).lstat())for n in FILES};dirstat=identity(view.lstat());end=min(budget.end,time.monotonic()+30)
    intent=budget.save(root/'retirements'/(key.replace('/','__')+'.intent.json'),{'key':key,'files':binding['files'],'all_native_and_owned_processes_closed':True,'failed_views_deleted':False},16384)
    before(end);need(identity(view.lstat())==dirstat,'owned directory custody');view.chmod(0o700)
    for n in sorted(FILES):before(end);need(identity((view/n).lstat())==custody[n],'owned leaf custody');(view/n).unlink()
    syncdir(view);view.rmdir();syncdir(view.parent);before(end);need(not os.path.lexists(view),'retired absence')
    return budget.save(root/'retirements'/(key.replace('/','__')+'.ack.json'),{'key':key,'intent':intent,'absent':True,'spent_costs_refunded':False},8192)

def run(s,source,loader,bodies,origin,end):
    lock=validate_selection(s,source,bodies);root=path(s['output']);collection=path(s['collection']);need(not os.path.lexists(root)and root.parent.is_dir()and root!=collection and root not in collection.parents and collection not in root.parents,'fresh disjoint complete output')
    need(origin<end<=origin+s['whole_seconds'],'original full-run deadline');budget=Budget(root,s['other_future_bytes']+MIB,end);budget.check();budget.mkdir(root)
    for name in('traffic','requests','observations','phases','current','submission','moves','retirements'):budget.mkdir(root/name)
    commit=freeze(s,source,root,budget);here=Path(__file__).absolute().parent;closed=[]
    try:
        # No stage, query, result or target is opened before this fixed commitment.
        for i,key in enumerate(KEYS):
            need(not any((root/'current').iterdir()),'only one context at a time')
            prepared,prep=phase('stage',key,s,source,root,commit,budget,loader,here,2*i)
            candidate,observed=phase('candidate',key,s,source,root,commit,budget,loader,here,2*i+1)
            need(candidate['input']==prepared['binding'],'same staged input used')
            moved=move_prediction(key,candidate,observed,root,source,commit,budget)
            moved['retirement']=retire_view(key,prepared['binding'],candidate,root,budget);moved['preparation']=prep;closed.append(moved)
        need(len(closed)==650 and [x['key']for x in closed]==list(KEYS)and not any((root/'current').iterdir()),'all650 closed; no subset')
        validated,proof=phase('collect',None,s,source,root,commit,budget,loader,here,1300)
        need(validated['source_design_sha256']==lock['source_design_sha256']and validated['gold_opened']is False and validated['scientific_scoring']is False,'public-only complete validation')
        need(validated['parts']==[{k:x[k]for k in('key','path','prediction')}for x in closed],'all650 validation pins join closed predictions')
        for row in closed:capture(root/'submission'/row['path'],PRED,row['prediction'],body=False,tick=budget.tick)
        submission={'schema':'neural076_predictions_v1','source_design_sha256':lock['source_design_sha256'],'parts':[{'key':x['key'],'path':x['path']}for x in closed]};sub=budget.save(root/'submission/submission.json',submission,131072)
        complete={'schema':'neural076_full650_collection_v1','status':'complete_pending_external_natural_exit','source':source,'commit':commit,'submission':sub,'contexts':closed,'public_validation':proof,'context_count':650,'private_gold_opened':False,'scientific_scoring':False,'feedback_released':False,'runtime_qualified':False,'scientific_qualified':False,'budget':budget.record(),'whole_seconds':s['whole_seconds'],'elapsed_before_publication':time.monotonic()-origin}
        p=budget.save(root/'COMPLETE.json',complete,2*MIB);budget.tick();return p
    except BaseException as exc:
        try:budget.save(root/'FAILURE.json',{'schema':'neural076_full650_failure_v1','error_type':type(exc).__name__,'completed_contexts':len(closed),'total_contexts':650,'budget':budget.record(),'partial_evidence_preserved':True,'automatic_retry':False,'scientific_scoring':False},16384)
        except BaseException:pass
        raise

def main(args,loader,bodies,manifest,source,origin):
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--source-sha256',required=True);a.add_argument('--selection',required=True);a.add_argument('--selection-sha256',required=True);a.add_argument('--outer-end',required=True,type=float);v=a.parse_args(args)
    raw,_=capture(v.selection,131072);need(short(raw)['sha256']==v.selection_sha256,'root selection identity');s=decode(raw);validate_selection(s,source,bodies)
    end=min(origin+s['whole_seconds'],v.outer_end-30);before(end);need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'fresh standalone owner');old=signal.getsignal(signal.SIGALRM);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('whole650deadline')));signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
    try:result=run(s,source,loader,bodies,origin,end)
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        finally:signal.signal(signal.SIGALRM,old)
    before(end);print(encode({'complete':result,'runtime_qualified':False,'scientific_scoring':False}).decode(),end='',flush=True);return 0

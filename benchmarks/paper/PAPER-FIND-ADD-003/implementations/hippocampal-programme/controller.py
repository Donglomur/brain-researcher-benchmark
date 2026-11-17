"""Complete H operation graph using the concrete owned Docker provider.

This module has no import-time operation and no default policy/images/data. The
external host supervisor owns its original clock, termination and terminal closure.
"""
import argparse
import copy
import os
import hashlib
import stat
from pathlib import Path
import time
from budget import Budget
from core import ROLES,cases,encoded,identity,job,model_key,need,planned_jobs
from operation import validate_operation,runtime_binding
from safe_io import capture,child,new_json,pin,strict,sync_parent,cleanup_note
from staging import materialize,verify,retire
from transport import Provider
from transport.bounds import mount_identity


def descriptor_file(path):
    b=capture(path,1048576);return pin(b)


def mount(view,purpose):
    return {'path':view['root'],'kind':'directory','purpose':purpose,'files':{**view['files'],'VIEW.json':view['manifest']}}


def direct(root,files,purpose):
    return {'path':str(Path(root).absolute()),'kind':'directory','purpose':purpose,'files':copy.deepcopy(files)}



def readable_owned(root,files,owned_parent):
    """Harden only our complete closed output tree, never external originals."""
    root=Path(root);need(root.resolve().is_relative_to(Path(owned_parent).resolve()) and root!=Path(owned_parent),'Exact owned private subtree')
    observed=set()
    paths=list(root.rglob('*'));need(not any(p.is_symlink() for p in [root,*paths]),'No replaced symlink in owned view')
    for p in paths:
        if p.is_file():observed.add(str(p.relative_to(root)))
        else:need(p.is_dir(),'Only owned regular files/directories')
    need(observed==set(files),'Exact complete owned readable-view inventory')
    for name,d in files.items():
        p=child(root,name);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
        try:
            s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==d['bytes'],'Unchanged owned file extent before hardening')
            os.fchmod(fd,0o444);os.fsync(fd)
        except BaseException as error:primary=error;raise
        finally:
            try:os.close(fd)
            except BaseException as error:
                if primary is None:raise
                cleanup_note(primary,'owned_view.close',error)
    for p in sorted([root,*[p for p in paths if p.is_dir()]],key=lambda p:len(p.parts),reverse=True):
        os.chmod(p,0o555);sync_parent(p)
    return root


def captured_file(record,name,budget,cap):
    need(name in record['files'],'Complete independently captured artifact '+name)
    return budget.read_file(child(record['root'],name),record['files'][name],cap)


def result(record,budget,cap):return strict(captured_file(record,'RESULT.json',budget,cap))


def phase_source(op,role):
    return identity({'role':role,'program':op['programs'].get(role),'source_families':{k:v['files'] for k,v in op['sources'].items() if k in ('runner','contract') or role in ('operator','reference') or k=='paper' or role=='B' and k=='author'}})


def write_job_files(root,request,command,budget,cap):
    root.mkdir(mode=0o700)
    files={}
    for name,value in [('REQUEST.json',request),('JOB.json',{'schema':'h_public_launcher_job_v1','command':command})]:
        raw=encoded(value);need(len(raw)<=cap,'Bounded complete producer request metadata');files[name]=budget.save(root/name,raw)
    return files


def all_slot_roster():
    from native.bridge import FAMILIES,VARIANTS
    # Only source-derived shape metadata is generated here, never fitted values.
    for variant in VARIANTS:
        for family,(n,m,unit) in FAMILIES.items():
            for a in range(n):
                for e in range(m):yield {'variant':variant,'family':family,'animal_ordinal':a,'index':e,'units':unit}


def run(operation,work,origin,operation_read_bytes=0):
    op=validate_operation(copy.deepcopy(operation));work=Path(work);need(not work.exists(),'Fresh private controller namespace');work.mkdir(mode=0o700)
    (work/'journal').mkdir(mode=0o700);(work/'phases').mkdir(mode=0o700)
    limits={k:v-(op['outer_'+k] if k in ('read_bytes','write_bytes','retained_bytes') else 0) for k,v in op['limits'].items()}
    budget=Budget(limits,origin,work/'journal');budget.work_end=budget.end-op['outer_cleanup_seconds'];budget.tick();budget.read(operation_read_bytes);records={};models={};folds={};native={};evaluations=[];preparation=None;graded=None;report=None
    cap=op['preparation_limits']['max_metadata_bytes'];stopped=None
    from reservation import derive
    reservation=derive(op);budget.max_event_bytes=op['recovery_limits']['max_record_bytes'];budget.max_events=reservation['event_count_bound'];budget.max_view_manifest_bytes=op['controller_metadata_bytes']
    budget.save(work/'RETENTION_ADMISSION.json',encoded(reservation))
    runtime=strict(budget.read_file(op['runtime_audit']['path'],{k:op['runtime_audit'][k] for k in ('bytes','sha256')},cap))
    need(runtime.get('schema')=='h_runtime_admission_v1' and runtime.get('operation_binding_sha256')==runtime_binding(op) and runtime.get('resource_policy_prospectively_reviewed') is True and runtime.get('independent_image_source_boundary_verified') is True,'Independent complete runtime/image/shape admission is a missing authentic prerequisite until separately reviewed')
    from source_admission import admit as admit_sources
    source_receipt=admit_sources(op,budget,cap);budget.save(work/'SOURCE_ADMISSION.json',encoded(source_receipt))
    need(budget.tick()+reservation['whole_phase_seconds']<=budget.work_end,'Complete remaining phase envelopes fit after actual host admission time')
    randomization=work/'randomization';randomization.mkdir(mode=0o700)
    seed=os.urandom(32) # future authorized operation only; never invoked by source construction
    seed_pin=budget.save(randomization/'SEED',seed)
    budget.event({'event':'randomization_precommitment','sha256':seed_pin['sha256'],'bytes':32,'domain':'h_private_conditional_atom_shuffle_v2','before_any_original_label_access':True,'automatic_reseed':False})
    os.chmod(randomization/'SEED',0o444);os.chmod(randomization,0o555);del seed
    # A runtime admission names operation excluding itself to avoid a cyclic
    # hash. The exact rule is defined in operation.runtime_binding below.
    for planned in planned_jobs():
        phase=work/'phases'/planned['id'];phase.mkdir(mode=0o700)
        request_id=None;closure=None;views=[];terminal_journaled=False;started=False;custody_confirmed=False;status='unstarted';outputs=None;reason=None;phase_record=None
        try:
            need(stopped is None,'Original graph stopped: '+str(stopped));budget.tick()
            action=planned['action'];role=planned['role']
            if action=='native_attempt':need(preparation is not None,'Full authenticated original preparation before native reproduction')
            if action in ('train_model','analytic_prior'):need(identity(planned['case']) in folds,'Full exact fold before training; refuse before source staging')
            if action=='evaluate_model':need(len(models)==9240,'Complete sealed model set before any evaluation source staging')
            if action=='report':need(graded is not None,'Private full-support grading before report staging')
            profile=copy.deepcopy(op['phase_resources'][action]);phase_start=budget.tick()
            transport_span=sum(profile[k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))
            host_cutoff=phase_start+op['host_setup_seconds'][action]
            transport_deadline=host_cutoff+transport_span
            deadline=transport_deadline+op['host_finish_seconds'][action]
            budget.phase_deadline=deadline
            need(deadline<=budget.work_end,'Full phase and cleanup must fit original remaining clock')
            science={**planned,'deadline':transport_deadline,'container_elapsed_seconds':profile['producer_seconds'],'model_limits':op['model_limits'],'preparation_limits':op['preparation_limits'],'output_root':'/output'}
            mounts={};inputs=[]
            # Per-producer mutable /work and /output are supplied fresh by the
            # provider. No prior fold/family artifacts or caches are mounted.
            source_names=['runner','paper','contract']
            if role=='B':source_names+=['author']
            if role in ('reference','operator'):source_names+=['reference']
            for name in source_names:
                source=op['sources'][name];view=materialize(phase/('source_'+name),source['root'],source['files'],budget);views.append(view)
                target={'runner':'/runner','paper':'/paper','contract':'/contract','author':'/historical_author','reference':'/operator'}[name]
                purpose='historical_author_source' if name=='author' else 'operator_reference' if name=='reference' else 'paper' if name=='paper' else 'contract' if name=='contract' else 'program'
                mounts[target]=mount(view,purpose)
            if action in ('prepare_originals','native_attempt'):
                mounts['/originals']=direct(op['originals']['root'],op['originals']['files'],'input')
                science.update(schema='h_native_request_v2',operation='prepare' if action=='prepare_originals' else 'reference',originals=[{'filename':name,'path':'/originals/'+name,**d} for name,d in op['originals']['files'].items()])
                # The original tuple order is part of the pinned native ABI.
                science['originals'].sort(key=lambda x:['all23behavior.mat','rawtrialsstand2torev2_n11.mat','rawtrialsstand2torev2_nosmoothnoflooring_n11.mat'].index(x['filename']))
                if role in ('reference','operator'):
                    source=op['sources']['native_reference'];v=materialize(phase/'native_source',source['root'],source['files'],budget);views.append(v);mounts['/author']=mount(v,'operator_reference')
                    # Exact standalone MATLAB bridge subtree, independently pinned.
                    bridge={name.removeprefix('native/'):d for name,d in op['sources']['reference']['files'].items() if name.startswith('native/')}
                    v=materialize(phase/'bridge',Path(op['sources']['reference']['root'])/'native',bridge,budget);views.append(v);mounts['/bridge']=mount(v,'operator_reference')
                if action=='prepare_originals':
                    e=op['identity_evidence'];body=budget.read_file(e['path'],{k:e[k] for k in ('bytes','sha256')},cap);identity_dir=phase/'identity';identity_dir.mkdir(mode=0o700);d=budget.save(identity_dir/'EVIDENCE.json',body)
                    readable_owned(identity_dir,{'EVIDENCE.json':d},work);mounts['/identity']=direct(identity_dir,{'EVIDENCE.json':d},'input');science['identity_sha256']=e['sha256']
            elif action=='prepare_fold':
                need(preparation is not None,'Complete originals/identity before every fold')
                mounts['/input']=direct(preparation['root'],preparation['files'],'input')
                mounts['/randomization']=direct(randomization,{'SEED':seed_pin},'input');science['randomization_seed_pin']=seed_pin
            elif action in ('train_model','analytic_prior'):
                key=identity(planned['case']);need(key in folds,'Complete exact fold before training')
                f=folds[key];family=planned['family'];entry=f['result']['families'][family]
                inputroot=Path(f['root'])/'fold'/entry['directory'];v=materialize(phase/'training_view',inputroot,entry['files'],budget);views.append(v);mounts['/input']=mount(v,'input')
                manifest=strict(budget.read_file(inputroot/'TRAINING.json',entry['manifest'],cap));science['channels']=manifest['channels']
                if action=='train_model':need(manifest['both_classes'] is True,'Training admission requires both classes; no fold/cohort rescue')
                if role=='reference' and action=='train_model':
                    science.update(operation='fit',training_path='/input/TRAINING.json')
                    bridge={name.removeprefix('native/'):d for name,d in op['sources']['reference']['files'].items() if name.startswith('native/')}
                    v=materialize(phase/'bridge',Path(op['sources']['reference']['root'])/'native',bridge,budget);views.append(v);mounts['/bridge']=mount(v,'operator_reference')
            elif action=='evaluate_model':
                need(len(models)==9240,'Seal every admitted model before any private query evaluation')
                key=model_key(planned['case'],planned['producer_role'],planned['family']);m=models[key];f=folds[identity(planned['case'])];q=f['result']['private_query']
                v=materialize(phase/'model_view',m['root'],m['model_files'],budget);views.append(v);mounts['/model']=mount(v,'input');science.update(model_files=m['model_files'],channels=m['channels'])
                v=materialize(phase/'query_view',Path(f['root'])/'fold'/q['directory'],q['files'],budget);views.append(v);mounts['/query']=mount(v,'input')
            elif action=='grade':
                index={'prospective':[],'truth':[],'native':{'slot_roster':list(all_slot_roster())}};grade_root=phase/'grading_input';grade_root.mkdir(mode=0o700);all_files={}
                # Exact artifact copies after all producers are closed; private only.
                for fold_key,f in folds.items():
                    name='truth/'+fold_key+'.json';relative='fold/'+f['result']['private_query']['directory']+'/QUERIES.json'
                    body=captured_file(f,relative,budget,cap);target=grade_root/name;target.parent.mkdir(exist_ok=True);d=budget.save(target,body);all_files[name]=d
                    index['truth'].append({'case':f['job']['case'],'path':name,'pin':d})
                for e in evaluations:
                    name='predictions/'+e['job']['id']+'.json';body=captured_file(e,'PREDICTIONS.json',budget,op['preparation_limits']['grade_limits']['max_prediction_bytes']);target=grade_root/name;target.parent.mkdir(exist_ok=True);d=budget.save(target,body);all_files[name]=d
                    index['prospective'].append({'case':e['job']['case'],'role':e['job']['producer_role'],'family':e['job']['family'],'path':name,'pin':d})
                for r,e in native.items():
                    name='native/'+r+'.json';body=captured_file(e,'native-dispositions.json',budget,op['preparation_limits']['grade_limits']['max_native_bytes']);target=grade_root/name;target.parent.mkdir(exist_ok=True);d=budget.save(target,body);all_files[name]=d;index['native'][r]={'path':name,'pin':d}
                index_raw=encoded(index);need(len(index_raw)<=op['preparation_limits']['max_grade_index_bytes'],'Complete private grade index allocation');all_files['INDEX.json']=budget.save(grade_root/'INDEX.json',index_raw);readable_owned(grade_root,all_files,work);mounts['/input']=direct(grade_root,all_files,'input')
            elif action=='report':
                need(graded is not None,'Private complete-support report dependency');mounts['/input']=direct(graded['root'],graded['files'],'input')
            if action=='analytic_prior':command=['/usr/local/bin/python','/runner/prior.py']
            elif role in ('A','B'):
                p=op['programs'][role];v=materialize(phase/'candidate_program',p['root'],p['files'],budget);views.append(v);mounts['/program']=mount(v,'program');command=p['native_argv' if action=='native_attempt' else 'train_argv']
            else:command=['/usr/local/bin/python','/operator/phase.py']
            job_files=write_job_files(phase/'job',science,command,budget,op['controller_metadata_bytes']);readable_owned(phase/'job',job_files,work);mounts['/job']=direct(phase/'job',job_files,'input')
            image=op['images'][role];source={'bytes':len(encoded({'job':planned,'source':phase_source(op,role)})),'sha256':identity({'job':planned,'source':phase_source(op,role)})}
            argv=['/usr/local/bin/python','/runner/run.py']
            exposure={'schema':'h_transport_exposure_v1','role':role,'image':image['image'],'source':source,'command':argv,'mounts':mount_identity(mounts),'approved_image_inventory_sha256':image['inventory_sha256'],'boundary_audit':image['boundary_audit'],'role_boundary_verified':True}
            exposure_raw=encoded(exposure);need(len(exposure_raw)<=min(op['controller_metadata_bytes'],2097152),'Complete bounded exposure metadata')
            exposure_pin=budget.save(phase/'EXPOSURE.json',exposure_raw)
            request={'schema':'h_owned_phase_request_v1','phase_id':planned['id'],'action':action,'role':role,'image':image['image'],'command':argv,'workdir':'/work','source':source,'exposure':exposure_pin,'clock':{'origin':origin,'phase_deadline':transport_deadline},'resources':profile,'output':{'kind':'generic','manifest':'OUTPUTS.json'}}
            request_raw=encoded(request);need(len(request_raw)<=op['controller_metadata_bytes'],'Complete bounded transport request')
            request_pin=budget.save(phase/'REQUEST.json',request_raw);request_id=request_pin['sha256']
            (phase/'control').mkdir(mode=0o700);(phase/'quarantine').mkdir(mode=0o700)
            provider=Provider(phase/'control',phase/'quarantine',op['docker']['binary'],op['docker']['socket'],op['engine_source_pin'],{exposure_pin['sha256']:str(phase/'EXPOSURE.json')},profile['source_read_bytes'],profile['host_write_bytes'])
            budget.reserve_producer(planned['id'],profile['source_read_bytes'],profile['host_write_bytes'],profile['host_write_bytes'])
            budget.event({'event':'attempt_start','job':planned,'request_id':request_id});started=True;need(budget.tick()<host_cutoff and budget.last+transport_span<=transport_deadline,'Host staging and complete transport fit original fixed phase cutoff')
            closure=provider.execute_phase(copy.deepcopy(request),copy.deepcopy(mounts),budget.end,lambda name,value:budget.event({'event':'transport','job':planned,'request_id':request_id,'name':name,'value':value}))
            observed=provider.observe(planned['id'],request_id,closure['receipt_pin'],budget.end);budget.tick()
            receipt=observed['receipt'];need(receipt==closure['receipt'],'Independent exact source receipt join')
            need(receipt['status']=='captured' and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True and receipt['producer_closed_before_capture'] is True and closure['finished_after_receipt']<=transport_deadline and closure['finished_after_receipt']<=budget.tick()<=deadline,'Complete independently closed bounded phase')
            custody_confirmed=True
            need(Path(receipt['quarantine_root'])==phase/'quarantine'/planned['id'],'Exact owned captured-output namespace')
            readable_owned(receipt['quarantine_root'],receipt['output_inventory']['files'],work)
            outputs={'root':receipt['quarantine_root'],'files':receipt['output_inventory']['files'],'job':planned,'capture_pin':closure['receipt_pin']};phase_record=outputs
            # Scientific metadata admission is distinct from transport custody.
            if action=='prepare_originals':
                value=result(outputs,budget,cap);need(value['status']=='complete_structural_and_bound_identity' and 'admitted-preparation.json' in outputs['files'],'Full original identity/preparation gate')
                from admission import full_shape_plan
                census=strict(captured_file(outputs,'admitted-preparation.json',budget,cap))
                plan=full_shape_plan(census,op['model_limits'],op['preparation_limits'],op['retention_reservation'],budget.work_end)
                budget.save(work/'FULL_SHAPE_ADMISSION.json',encoded(plan));preparation=outputs
            elif action=='prepare_fold':
                value=strict(captured_file(outputs,'fold/RESULT.json',budget,cap));need(value['case']==planned['case'] and value['full_support'] is True,'Complete selected fold');folds[identity(planned['case'])]={**outputs,'result':value}
            elif action in ('train_model','analytic_prior'):
                from models import admit
                budget.read(op['model_limits']['max_model_bytes']) # conservative complete model admission read upper
                model,admission=admit(outputs['root'],outputs['files'],planned['family'],science['channels'],op['model_limits'],deadline)
                model_files={'MODEL.json':outputs['files']['MODEL.json'],**{d['path']:{k:d[k] for k in ('bytes','sha256')} for d in model['arrays'].values()}}
                models[model_key(planned['case'],role,planned['family'])]={**outputs,'channels':science['channels'],'model_files':model_files,'admission':admission}
            elif action=='native_attempt':
                need('native-dispositions.json' in outputs['files'],'Complete typed native output');native[role]=outputs
            elif action=='evaluate_model':evaluations.append(outputs)
            elif action=='grade':graded=outputs
            elif action=='report':report=outputs
            status='completed';reason=None
            # Keep all outputs through terminal reporting; never reclaim an
            # unresolved producer's retained reservation.
        except Exception as error:
            status='failed' if started else 'unstarted';reason=type(error).__name__+': '+str(error)[:1000]
            budget.phase_deadline=budget.end # failure evidence only; never grants retry/work after a failed phase
            if not started and stopped is None:stopped='Pre-dispatch admission/staging/publication failed; retain every charged partial view and forbid another phase construction'
            if started and not custody_confirmed:stopped='Unknown or unadmitted producer custody; no later dispatch is authorized'
            if stopped is None and planned['action'] in ('prepare_originals','prepare_fold'):stopped='Complete original/fold preparation gate failed; no later scientific producer may start'
            if closure is not None:
                try:
                    budget.event({'event':'unadmitted_external_attempt','job':planned,'request_id':request_id,'error_type':type(error).__name__,'returned_closure':closure});terminal_journaled=True
                except Exception:stopped='failure evidence publication or original budget exhausted'
            if budget.clock()>budget.end:stopped='original whole-program deadline exceeded'
        finally:
            externally_closed=custody_confirmed or not started # proven no backend invocation on a pre-dispatch refusal
            for view in views:
                try:
                    if externally_closed:retire(view,True,budget)
                except Exception as error:status='failed';reason=(reason or '')+'; source retirement '+type(error).__name__;stopped='Owned view retirement failed; retain charge and forbid another concurrent view'
            record={'job':planned,'request_id':request_id,'status':status,'reason':reason,'capture_pin':None if closure is None else closure.get('receipt_pin'),'cost':None if closure is None else closure.get('final_transport_counters'),'outputs':None if outputs is None else {'root':outputs['root'],'files':outputs['files']}}
            records[planned['id']]=record
            event_index_before=len(budget.events)
            try:
                if not terminal_journaled:budget.event({'event':'attempt_disposition' if started else 'not_started',**record})
            except Exception as error:
                stopped='Durable disposition unavailable, late, or original budget exhausted';record['status']='failed';record['reason']=(record['reason'] or '')+'; terminal publication '+type(error).__name__
                budget.phase_deadline=budget.end
                if started:
                    try:
                        if terminal_journaled or len(budget.events)>event_index_before:budget.event({'event':'attempt_invalidation',**record})
                        else:budget.event({'event':'unadmitted_external_attempt','job':planned,'request_id':request_id,'error_type':type(error).__name__,'returned_closure':closure})
                    except Exception:pass # outer independently reports unavailable/contradictory terminal evidence
            finally:budget.phase_deadline=budget.end
    final={'schema':'h_inner_return_v1','numerical_complete':report is not None and graded is not None and result(graded,budget,cap).get('numerical_complete') is True and all(r['status']=='completed' for r in records.values()),'records':list(records.values()),'budget':budget.snapshot(),'scientific_qualification':False,'runtime_qualification':False,'original_scope':'23behavior/11imaging/44sessions/twovariants;56868native dispositions per role;9240models;924000predictions','report':None if report is None else {'root':report['root'],'files':report['files']},'stopped':stopped,'randomization_public_commitment':seed_pin['sha256'],'seed_and_permutations_private':True}
    final_raw=encoded(final);need(len(final_raw)<=op['recovery_limits']['max_metadata_bytes'],'Complete bounded final return; no roster truncation')
    budget.save(work/'INNER_RETURN.json',final_raw);budget.tick();return final


def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);p.add_argument('--operation-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--origin',required=True,type=float);a=p.parse_args()
    raw=capture(a.operation,1048576);need(pin(raw)['sha256']==a.operation_sha256,'Pinned original operation');run(strict(raw),a.output,a.origin,len(raw))


if __name__=='__main__':main()

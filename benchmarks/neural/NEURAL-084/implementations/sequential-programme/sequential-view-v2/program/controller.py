"""Full54 sequential fit/seal/infer, with all three unfitted references."""
import os
from pathlib import Path

def write(p,v,budget,cap=262144):return c.save(p,c.encoded(v),cap,budget.tick,budget.write)

def run(s,source,bodies,origin,worker_end,startup_reads=0):
    root=c.path(s['output']);c.need(not os.path.lexists(root) and root.parent.is_dir(),'fresh owned sequential attempt')
    c.need(worker_end==origin+s['limits']['whole_seconds']-s['limits']['observer_seconds'],'original selected worker clock')
    budget=c.Budget(root,s['other_future_bytes'],worker_end,s['limits']);budget.capacity(65536);budget.read(startup_reads);root.mkdir(mode=0o700);c.sync_dir(root.parent,budget.tick)
    completed=[];last='startup';current=None
    try:
        binding=c.parse(bodies['BINDING.json'])
        for row in binding['sources'].values():c.capture(c.path(s['repository'])/row['path'],row['bytes'],c.only_pin(row),budget.tick,budget.read)
        policy.reviews(s,source,binding,lambda p,cap,pp:c.capture(p,cap,pp,budget.tick,budget.read))
        program=c.capture(s['program']['path'],131072,c.only_pin(s['program']),budget.tick,budget.read);program.decode('utf-8')
        committed=root/'program.py';c.save(committed,program,131072,budget.tick,budget.write);c.readable(committed,budget.tick)
        write(root/'COMMITMENT.json',dict(schema='neural084-sequential-commitment-v2',source=source,program=c.pin(program),pool=s['pool'],plan=s['plan'],origin=origin,worker_end=worker_end,program_fixed_before_operator_labels_and_candidate_views=True),budget)
        canonical=store.load(s,budget);c.need(canonical['canonical_bytes']==s['plan']['canonical_total_bytes'],'complete canonical measured plan')
        trusted=root/'trusted';trusted.mkdir(mode=0o700)
        for name in ('holder.py','candidate_entry.py','reference_program.py'):c.save(trusted/name,bodies[name],100000,budget.tick,budget.write);c.readable(trusted/name,budget.tick)
        os.chmod(trusted,0o555);c.sync_dir(trusted,budget.tick)
        phases=root/'phases';phases.mkdir(mode=0o700);predictions=root/'predictions';predictions.mkdir(mode=0o700)
        for mode in policy.MODES:(predictions/mode).mkdir(mode=0o700)
        c.sync_dir(predictions,budget.tick);c.sync_dir(root,budget.tick)
        for ordinal,person in enumerate(range(1,55)):
            fold='fold%03d'%person;folder=phases/fold;folder.mkdir(mode=0o700);c.sync_dir(phases,budget.tick)
            current=root/'current';last=fold+'/fit-stage';training,train=store.stage(canonical,person,'fit',current,budget);stamps=store.verify(current,training,budget)
            fitdir=folder/'fit';fitdir.mkdir(mode=0o700);c.sync_dir(folder,budget.tick)
            budget.read(sum(x['bytes'] for x in training.values()));budget.native('fit',ordinal);last=fold+'/fit'
            c.capture(committed,131072,c.pin(program),budget.tick,budget.read)
            fit=native.phase(s,trusted,current,committed,None,fitdir,'fit',ordinal,source,budget,worker_end)
            c.need(fit['status']=='captured' and fit['all_native_resources_closed']is True,'closed fit before any query view')
            model=folder/'model.bin';modelpin=fit['output'];modelstamp=store.seal_model(fitdir/'model.bin',model,modelpin,budget)
            fitnative=c.pin(c.capture(fitdir/'NATIVE.json',262144,None,budget.tick,budget.read))
            seal=write(folder/'MODEL_SEAL.json',dict(schema='neural084-model-seal-v2',source=source,program=c.pin(program),person=person,model=modelpin,model_stamp=list(modelstamp),fit_native=fitnative,fit_closed=True,query_exposed=False,single_model_body=True),budget)
            last=fold+'/train-retirement';stamps=store.verify(current,training,budget);store.retire(current,training,stamps,budget);current=None
            train_retired=write(folder/'TRAIN_RETIRED.json',dict(schema='neural084-train-retired-v2',person=person,training=training,seal=seal,absent=True,parent_fsynced=True,query_exposed=False),budget)
            c.need(not os.path.lexists(root/'current'),'train absence before query staging')
            current=root/'current';last=fold+'/query-stage';query,meta=store.stage(canonical,person,'query',current,budget,training);stamps=store.verify(current,query,budget)
            foldpin=write(folder/'FOLD.json',meta,budget)
            outputs={};nativepins={'fit':fitnative}
            for kind in ('infer','cca','constant','frequency-permuted'):
                mode='candidate' if kind=='infer' else kind;attempt=folder/kind;attempt.mkdir(mode=0o700);c.sync_dir(folder,budget.tick);last=fold+'/'+kind
                selected=committed if kind=='infer' else trusted/'reference_program.py';selectedpin=c.pin(program) if kind=='infer' else c.pin(bodies['reference_program.py'])
                c.capture(selected,131072,selectedpin,budget.tick,budget.read)
                c.need(c.stamp(model.lstat())==modelstamp,'same sealed model before each query phase')
                budget.read(sum(x['bytes'] for x in query.values())+(modelpin['bytes'] if kind=='infer' else 0));budget.native(kind,ordinal)
                result=native.phase(s,trusted,current,selected,model if kind=='infer' else None,attempt,kind,ordinal,source,budget,worker_end)
                c.need(result['status']=='captured' and result['all_native_resources_closed']is True,'closed query phase')
                raw=c.capture(attempt/'predictions.json',262144,result['output'],budget.tick,budget.read);contracts.prediction(raw,meta)
                outputs[mode]=c.save(predictions/mode/(fold+'.json'),raw,262144,budget.tick,budget.write);c.readable(predictions/mode/(fold+'.json'),budget.tick)
                nativepins[kind]=c.pin(c.capture(attempt/'NATIVE.json',262144,None,budget.tick,budget.read));stamps=store.verify(current,query,budget)
            last=fold+'/query-retirement';store.retire(current,query,stamps,budget);current=None
            query_retired=write(folder/'QUERY_RETIRED.json',dict(schema='neural084-query-retired-v2',person=person,query=query,fold=foldpin,absent=True,parent_fsynced=True,all_query_native_closed=True),budget)
            c.need(not os.path.lexists(fitdir/'model.bin'),'no duplicate original model body')
            last=fold+'/model-retirement';store.retire_model(model,modelpin,modelstamp,budget)
            model_retired=write(folder/'MODEL_RETIRED.json',dict(schema='neural084-model-retired-v2',person=person,model=modelpin,seal=seal,fit_native=fitnative,infer_native=nativepins['infer'],model_stamp=list(modelstamp),absent=True,parent_fsynced=True,fit_copy_absent=True),budget)
            store.unchanged(canonical,budget);budget.capacity()
            record=dict(person=person,ordinal=ordinal,fold=fold,fold_metadata=foldpin,model=modelpin,seal=seal,train_retired=train_retired,query_retired=query_retired,model_retired=model_retired,native=nativepins,outputs=outputs,all_current_and_model_absent=True)
            write(folder/'CLOSED.json',record,budget);completed.append(record)
        c.need(len(completed)==54 and [r['person'] for r in completed]==list(range(1,55)),'all54folds and270native closures')
        store.unchanged(canonical,budget)
        bundle=write(root/'submission.json',dict(schema='neural084-sequential-submission-v2',pool=c.only_pin(s['pool']),modes=list(policy.MODES),folds=completed),budget)
        handoff=write(root/'GRADE_HANDOFF.json',dict(schema='neural084-sequential-grade-handoff-v2',task_id='NEURAL-084',prediction_directories={m:'predictions/'+m for m in policy.MODES},scorer=binding['sources']['score.py'],pool=s['pool'],preparation=s['preparation'],all54_required_per_mode=True,execution_authorized=False,new_selection_and_external_closure_required=True,metric='equal_person_session_phase_class_balanced_accuracy'),budget)
        done=write(root/'COMPLETE.json',dict(schema='neural084-sequential-complete-v2',status='complete_unqualified',source=source,program=c.pin(program),pool=s['pool'],preparation=s['preparation'],plan=s['plan'],folds=completed,submission=bundle,grade_handoff=handoff,all_views_and_models_retired=True,canonical_store_unchanged=True,labels_opened_for_trusted_staging=True,canonical_store_or_private_gold_candidate_mounted=False,identity_keys_opened=False,private_scoring_performed=False,runtime_qualified=False,scientific_qualified=False,costs=budget.record()),budget)
        budget.tick();return dict(schema='neural084-sequential-worker-v2',status='complete_unqualified',source=source,complete=done,submission=bundle,query_count=21600)
    except BaseException as exc:
        try:write(root/'FAILURE.json',dict(schema='neural084-sequential-failure-v2',source=source,status='failed',last_phase=last,completed_folds=len(completed),expected_folds=54,current_view_may_remain=current is not None,model_or_native_recovery_may_be_required=True,automatic_retry=False,error_type=type(exc).__name__,costs=budget.record()),budget)
        except BaseException:pass
        raise

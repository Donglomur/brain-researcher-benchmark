"""Full54 candidate plus fixed CCA and both diagnostics; no private scoring."""
import os
from pathlib import Path

def run(s,source,bodies,origin,worker_end,startup_reads=0):
    root=c.path(s['output']);c.need(not os.path.lexists(root) and root.parent.is_dir(),'fresh owned attempt')
    c.need(worker_end==origin+s['limits']['whole_seconds']-s['limits']['observer_seconds'],'same original worker endpoint')
    budget=c.Budget(root,s['other_future_bytes'],worker_end,s['limits']);budget.capacity(65536);root.mkdir(mode=0o700);c.sync_dir(root.parent,budget.tick);budget.read(startup_reads)
    completed=[];current=None;last='initial'
    try:
        binding=c.parse(bodies['BINDING.json'])
        for row in binding['sources'].values():c.capture(c.path(s['repository'])/row['path'],row['bytes'],c.only_pin(row),budget.tick,budget.read)
        policy.reviews(s,source,binding,lambda p,cap,pp:c.capture(p,cap,pp,budget.tick,budget.read))
        program=c.capture(s['program']['path'],131072,c.only_pin(s['program']),budget.tick,budget.read);program.decode('utf-8')
        committed=root/'program.py';c.save(committed,program,131072,budget.tick,budget.write);c.readable(committed,budget.tick)
        raw=c.capture(s['public_manifest']['path'],131072,c.only_pin(s['public_manifest']),budget.tick,budget.read)
        index,rows,plan=packet.inspect_index(raw,budget)
        c.need(plan==s['plan'],'same full54 index plan; separate reviews bind index')
        for row in rows:c.need(not root.is_relative_to(row['root']) and not row['root'].is_relative_to(root),'public sources outside output')
        c.save(root/'COMMITMENT.json',c.encoded(dict(schema='neural084-program-commitment-v1',source=source,program=c.pin(program),input_index=c.only_pin(s['public_manifest']),plan=plan,origin=origin,worker_end=worker_end,all54_policy_fixed_before_exposure=True)),32768,budget.tick,budget.write)
        trusted=root/'trusted';trusted.mkdir(mode=0o700)
        for name in ('holder.py','candidate_entry.py','reference_program.py'):c.save(trusted/name,bodies[name],100000,budget.tick,budget.write);c.readable(trusted/name,budget.tick)
        os.chmod(trusted,0o555);c.sync_dir(trusted,budget.tick)
        phases=root/'phases';phases.mkdir(mode=0o700)
        predictions=root/'predictions';predictions.mkdir(mode=0o700)
        for kind in policy.MODES:(predictions/kind).mkdir(mode=0o700)
        c.sync_dir(predictions,budget.tick);c.sync_dir(root,budget.tick)
        final=[]
        for i,row in enumerate(rows):
            folder=phases/row['fold']['fold'];folder.mkdir(mode=0o700);c.sync_dir(phases,budget.tick)
            packet.unchanged(row,budget);current=root/'current';expected=packet.view(current,row,{},budget);stamps=packet.verify_view(current,expected,budget)
            outputs={};native_pins={}
            for kind in policy.MODES:
                last=f'{kind}-{i}';attempt=folder/kind;attempt.mkdir(mode=0o700);c.sync_dir(folder,budget.tick)
                budget.read(sum(p["bytes"] for p in expected.values())) # one-pass logical mounted-input reserve; not measured native I/O
                budget.native(kind,i)
                selected_program=committed if kind=='candidate' else trusted/'reference_program.py'
                c.capture(selected_program,131072,c.pin(program) if kind=='candidate' else c.pin(bodies['reference_program.py']),budget.tick,budget.read)
                result=native.phase(s,trusted,current,selected_program,None,attempt,kind,i,source,budget,worker_end)
                c.need(result['status']=='captured' and result['all_native_resources_closed']is True,'natural closed native phase')
                output=c.capture(attempt/'predictions.json',packet.PRED_CAP,result['output'],budget.tick,budget.read);packet.prediction(output,row['fold'])
                native_pins[kind]=c.pin(c.capture(attempt/'NATIVE.json',packet.NATIVE_CAP,None,budget.tick,budget.read))
                outputs[kind]=c.save(predictions/kind/(row['fold']['fold']+'.json'),output,packet.PRED_CAP,budget.tick,budget.write)
                c.readable(predictions/kind/(row['fold']['fold']+'.json'),budget.tick)
                stamps=packet.verify_view(current,expected,budget)
            packet.retire(current,expected,stamps,budget);current=None;packet.unchanged(row,budget)
            record=dict(ordinal=i,person=row['person'],fold=row['fold']['fold'],outputs=outputs,native=native_pins,view_retired=True)
            c.save(folder/'CLOSED.json',c.encoded(record),32768,budget.tick,budget.write);completed.append(record);final.append(record)
        c.need(len(completed)==54 and [r['person'] for r in completed]==list(range(1,55)),'all54 original people')
        for row in rows:packet.unchanged(row,budget)
        c.capture(s['public_manifest']['path'],131072,c.only_pin(s['public_manifest']),budget.tick,budget.read)
        bundle=c.save(root/'submission.json',c.encoded(dict(schema='neural084-complete-prediction-files-v1',input_index=c.only_pin(s['public_manifest']),modes=list(policy.MODES),folds=final)),262144,budget.tick,budget.write)
        c.save(root/'GRADE_HANDOFF.json',c.encoded(dict(schema='neural084-separate-grade-handoff-v1',task_id='NEURAL-084',prediction_directories={kind:'predictions/'+kind for kind in policy.MODES},scorer=binding['sources']['score.py'],input_index=s['public_manifest'],preparation=s['preparation'],all54_required_per_mode=True,private_gold_or_pool_opened=False,execution_authorized=False,new_selection_and_external_closure_required=True,metric='equal_person_session_phase_class_balanced_accuracy',retain216_phase_confusions_and54_person_scores=True)),32768,budget.tick,budget.write)
        complete=dict(schema='neural084-full54-complete-v1',status='complete_unqualified',source=source,program=c.pin(program),public_manifest=c.only_pin(s['public_manifest']),preparation=s['preparation'],plan=plan,folds=completed,submission=bundle,all_views_retired=True,source_packet_unchanged=True,all54_policy_fixed_before_exposure=True,private_targets_or_keys_opened=False,private_scoring_performed=False,scientific_qualified=False,runtime_qualified=False,costs=budget.record())
        done=c.save(root/'COMPLETE.json',c.encoded(complete),packet.JSON_CAP,budget.tick,budget.write);budget.tick()
        return dict(schema='neural084-worker-result-v1',status='complete_unqualified',source=source,complete=done,submission=bundle,query_count=21600)
    except BaseException as exc:
        failure=dict(schema='neural084-full54-failure-v1',source=source,status='failed',last_phase=last,completed_folds=len(completed),expected_folds=54,current_view_may_remain=current is not None,automatic_retry=False,native_recovery_may_be_required=True,error_type=type(exc).__name__,costs=budget.record())
        try:c.save(root/'FAILURE.json',c.encoded(failure),packet.JSON_CAP,budget.tick,budget.write)
        except BaseException:pass
        raise

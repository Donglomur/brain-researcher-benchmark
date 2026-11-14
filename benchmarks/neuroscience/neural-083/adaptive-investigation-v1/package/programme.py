"""Full original support; new pointwise actor ownership, unchanged data/science."""
import os
from pathlib import Path


def one_query(c,store,full_view,metadata,index,destination,budget):
    """Copy one unchanged row from the trusted full query view, with no maths."""
    c.need(0<=index<100 and len(metadata['query'])==100,'original complete query roster')
    root=c.path(destination);c.need(not os.path.lexists(root),'fresh single-query view')
    root.mkdir(mode=0o700)
    shape=list(metadata['query_shape']);c.need(shape[0]==100,'full query geometry')
    row_bytes=4
    for n in shape[1:]:row_bytes*=n
    p=c.path(full_view)/'query.npy';fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=c.stamp(os.fstat(fd))
        with os.fdopen(os.dup(fd),'rb') as handle:offset=store.npy_header(handle,shape,budget.read)
        budget.read(row_bytes);raw=os.pread(fd,row_bytes,offset+index*row_bytes)
        c.need(len(raw)==row_bytes and c.stamp(os.fstat(fd))==before==c.stamp(p.lstat()),
               'exact original immutable query row')
    finally:os.close(fd)
    shape[0]=1
    pin=c.save(root/'query.npy',store.header(shape)+raw,row_bytes+2048,budget.tick,budget.write)
    c.readable(root/'query.npy',budget.tick)
    meta=dict(metadata,query=[metadata['query'][index]],query_shape=shape,query_pin=pin)
    mp=c.save(root/'case.json',c.encoded(meta),65536,budget.tick,budget.write)
    c.readable(root/'case.json',budget.tick);os.chmod(root,0o555);c.sync_dir(root,budget.tick)
    pins={'query.npy':pin,'case.json':mp}
    return pins,meta,store.verify(root,pins,budget)


def run(ctx,selection,source,bodies,provider_config,prompt,frozen_program,origin,deadline):
    c=ctx['c'];store=ctx['store'];contracts=ctx['contracts'];native_module=ctx['native']
    actor=ctx['actor'];native_tools=ctx['native_tools'];provider=ctx['provider']
    root=c.path(selection['output']);c.need(not os.path.lexists(root),'fresh full adaptive attempt')
    budget=ctx['budget']
    c.need(budget.root==root and budget.end==deadline,'same source/configuration and execution allowance')
    budget.capacity(65536);root.mkdir(mode=0o700);c.sync_dir(root.parent,budget.tick)
    def save(path,value,cap=2000000):return c.save(path,c.encoded(value),cap,budget.tick,budget.write)
    config_pin=c.pin(c.encoded(selection))
    save(root/'COMMITMENT.json',dict(schema='neural083_case_adaptive_commitment_v1',source=source,
        configuration=config_pin,provider=c.pin(c.encoded(provider_config)),prompt=c.pin(prompt.encode()),
        frozen_program=c.pin(frozen_program.encode()) if frozen_program is not None else None,
        native_tool_worker=c.pin(bodies['tool_worker.py']),origin=origin,deadline=deadline,
        policy_and_training_constructor_fixed_before_all_queries=True))
    canonical=store.load(selection,budget);save(root/'PANEL.json',canonical['panel'])
    trusted=root/'trusted';trusted.mkdir(mode=0o700)
    for name in ('holder.py','candidate_entry.py'):
        p=trusted/name;c.save(p,ctx['programme_bodies'][name],131072,budget.tick,budget.write);c.readable(p,budget.tick)
    os.chmod(trusted,0o555)
    native_module.IMAGE=selection['image']
    native=native_tools.NativeTools(c,native_module,selection,source,trusted,
        ctx['reference_core'],bodies['tool_worker.py'],budget,deadline)
    costs=provider.TokenCostCollector(selection['model_input_token_budget'],
        selection['model_output_token_budget'],selection['model_request_budget'])
    parent=root/'conditions';parent.mkdir(mode=0o700)
    completed=[];current=None;active=None
    try:
        for item in contracts.schedule(canonical['panel']):
            budget.tick();active=item;native.records=[]
            folder=parent/('condition%04d'%item['ordinal']);folder.mkdir(mode=0o700)
            current=root/'current'
            training,fit_meta=store.stage(canonical,item['case'],item['setting'],item['arm'],'fit',current,budget)
            stamps=store.verify(current,training,budget)
            training_retirement=budget.register_retirement(current,training)
            if item['panel']=='reference':
                body=ctx['programme_bodies']['reference_program.py']
                fitted=native.dispatch('fit',current,None,folder/'fit',item['ordinal'],body)
            else:
                fitted=native.construct(current,folder/'fit',item['ordinal'],selection['tool_mode'])
                body=native_tools.assembled(ctx['reference_core'],bodies['tool_worker.py'],
                    selection['tool_mode'],'construct_training_state')
            model=folder/'model.bin';old=c.path(fitted['output_path'])
            c.capture(old,536870912,fitted['output'],budget.tick,budget.read)
            os.rename(old,model);c.readable(model,budget.tick);c.sync_dir(old.parent,budget.tick);c.sync_dir(folder,budget.tick)
            model_stamp=c.stamp(model.lstat());model_pin=fitted['output'];program_pin=c.pin(body)
            model_retirement=budget.register_retirement(folder,{'model.bin':model_pin})
            seal=save(folder/'MODEL_SEAL.json',dict(condition=item,model=model_pin,program=program_pin,
                fit=fitted,query_exposed=False,immutable_training_state=True))
            store.verify(current,training,budget);store.retire(current,training,stamps,budget)
            budget.retired(training_retirement);current=None
            train_retired=save(folder/'TRAIN_RETIRED.json',dict(condition=item,model_seal=seal,absent=True,
                query_exposed=False,training=training))
            current=root/'current'
            query,metadata=store.stage(canonical,item['case'],item['setting'],item['arm'],'infer',current,budget,
                                      model_binding=dict(model=model_pin,program=program_pin))
            query_stamps=store.verify(current,query,budget);query_meta=save(folder/'QUERY_METADATA.json',metadata)
            query_retirement=budget.register_retirement(current,query)
            actors=[];reference_infer=None
            if item['panel']=='reference':
                reference_infer=native.dispatch('infer',current,model,folder/'reference-infer',item['ordinal'],body)
                prediction=c.parse(c.capture(reference_infer['output_path'],100000,reference_infer['output'],budget.tick,budget.read))
                contracts.prediction(prediction,metadata)
            else:
                predicted=[];abstained=[]
                for i,trial in enumerate(metadata['query']):
                    c.need(c.stamp(model.lstat())==model_stamp,'same frozen training-derived state before each query')
                    small=folder/'single-query-input'
                    pins,meta,snapshots=one_query(c,store,current,metadata,i,small,budget)
                    single_retirement=budget.register_retirement(small,pins)
                    answer,receipt=actor.investigate(c=c,provider=provider,provider_config=provider_config,
                        cost_collector=costs,prompt=prompt,mode=selection['tool_mode'],entrant=selection['entrant'],
                        frozen_program=frozen_program,metadata=meta,view=small,model=model,
                        folder=folder/('query%03d'%i),ordinal=item['ordinal'],native=native,budget=budget,
                        deadline=deadline,max_model_calls=selection['max_model_calls_per_query'],
                        max_tool_calls=selection['max_tool_calls_per_query'],
                        query_budget=ctx['query_budget'].QueryBudget(selection['infer_seconds'],
                            selection['max_tool_calls_per_query'],selection['entrant'],
                            selection['query_seconds'],deadline))
                    actors.append(dict(query=trial,actor=receipt))
                    if answer['status']=='complete':predicted.append(dict(trial=trial,p_right=answer['p_right']))
                    else:abstained.append(dict(trial=trial,reason=answer['reason']))
                    store.verify(small,pins,budget);store.retire(small,pins,snapshots,budget)
                    budget.retired(single_retirement)
                    c.need(c.stamp(model.lstat())==model_stamp,'query cannot replace frozen training state')
                prediction=dict(schema='neural083_case_prediction_v1',
                    generation=metadata['generation'],case=item['case'],setting=item['setting'],arm=item['arm'])
                if abstained:prediction.update(status='abstain',reason='One or more independently investigated queries explicitly abstained.')
                else:prediction.update(status='complete',predictions=predicted)
                contracts.prediction(prediction,metadata)
            out=save(folder/'predictions.json',prediction,100000)
            store.verify(current,query,budget);store.retire(current,query,query_stamps,budget)
            budget.retired(query_retirement);current=None
            c.need(c.stamp(model.lstat())==model_stamp,'same sole model before retirement')
            model.unlink();c.sync_dir(folder,budget.tick);budget.retired(model_retirement)
            store.unchanged(canonical,budget)
            closed=save(folder/'CLOSED.json',dict(schema='neural083_case_adaptive_condition_v1',
                source=source,configuration=config_pin,condition=item,model_seal=seal,fit=fitted,
                train_retired=train_retired,query_metadata=query_meta,actors=actors,
                reference_infer=reference_infer,output=out,model=model_pin,
                training_query_model_retired=True,all_actual_native_calls_closed=True))
            completed.append(dict(condition=item,closed=closed))
        c.need(len(completed)==2592,'unchanged complete two-panel schedule')
        store.unchanged(canonical,budget)
        submission=save(root/'submission.json',dict(schema='neural083_case_adaptive_submission_v1',
            source=source,configuration=config_pin,conditions=completed))
        cost_pin=save(root/'MODEL_COSTS.json',costs.snapshot(),selection['model_cost_record_cap_bytes'])
        result=dict(schema='neural083_case_adaptive_complete_v1',source=source,configuration=config_pin,
            submission=submission,model_costs=cost_pin,conditions=2592,conditions_per_panel=1296,
            candidate_queries=129600,independent_reference_queries=129600,
            source_unique_online_queries=10800,entrant=selection['entrant'],tool_mode=selection['tool_mode'],
            counts_are_not_independent_biological_observations=True,origin=origin,worker_deadline=deadline,
            scientific_qualified=False,grading_authorized=False,costs=budget.record())
        complete=save(root/'COMPLETE.json',result,selection['completion_record_cap_bytes'])
        budget.tick();return dict(complete=complete,submission=submission,model_costs=cost_pin)
    except BaseException as error:
        actual_actor_failure=getattr(error,'adaptive_actual_failure',None)
        failed_costs=None
        try:failed_costs=save(root/'FAILED_MODEL_COSTS.json',costs.snapshot(),selection['model_cost_record_cap_bytes'])
        except BaseException as secondary:error.add_note('Actual model cost ledger publication failed: '+type(secondary).__name__)
        failed=dict(schema='neural083_case_adaptive_failure_v1',source=source,active_condition=active,
            completed_conditions=len(completed),expected_conditions=2592,error_type=type(error).__name__,
            error=str(error)[:2048],current_view_may_remain=current is not None,
            native_recovery_may_be_required=True,automatic_retry=False,
            model_costs=failed_costs,model_cost_summary=actor.cost_summary(costs),costs=budget.record(),
            actual_actor_failure=actual_actor_failure)
        error.adaptive_actual_failure=failed
        try:save(root/'FAILURE.json',failed,selection['completion_record_cap_bytes'])
        except BaseException as secondary:error.add_note('Programme failure publication failed: '+type(secondary).__name__)
        raise

"""Concrete source-owned consumers. Called only by the captured-source bootstrap."""
from .artifact_io import Store,strict_json,json_bytes
from .nomad_math import (need,closed,identity,array_identity,Budget,condition_means,fit_dpca,
    transfer_dpca,nomad_distance_grid,fit_pcr)
from .nomad_artifacts import Catalog,Output,resolve_profile,read_trials,read_state
from .nomad_products import decode_checkpoint,integrate_position
from .nomad_t11 import intended_reach,complete_sequences,derive_recenter_intervals,ChronologicalRelease,METHODS
from .nomad_nwb import read_physical_fields,physical_trial_rows
from .nomad_archive import close_archive
from .nomad_windows import T11Windows


DPCA_KEYS=('numpy_version','condition_weighting','marginal_groups','lambda','components',
    'rank_relative_threshold','boundary_tie_relative_threshold','residual_relative_limit',
    'profile_id','source_profile_pin')
PCR_KEYS=('numpy_version','profile_id','source_profile_pin','shared_dimension','centering',
    'rank_relative_threshold','boundary_tie_relative_threshold','residual_relative_limit')
POSITION_KEYS=('numpy_version','rule','velocity_units','position_units','time_units',
    'velocity_to_position_per_time','profile_id','source_profile_pin')
TARGET_KEYS=('numpy_version','time_units','position_units','velocity_units',
    'early_acquisition','tail','profile_id','source_profile_pin')
EVENT_KEYS=('numpy_version','gradient_metric','jump_threshold','center','center_tolerance',
    'center_match','minimum_start_index','source_profile_pin','profile_id')


def publish_tree(value,output,prefix='result'):
    """Serialize real numerical products without converting large arrays to JSON."""
    if type(value) is dict:return {k:publish_tree(v,output,prefix+'.'+str(i)) for i,(k,v) in enumerate(value.items())}
    if type(value) in (list,tuple):return [publish_tree(v,output,prefix+'.'+str(i)) for i,v in enumerate(value)]
    if hasattr(value,'dtype') and hasattr(value,'shape'):
        return output.array(prefix+'.f64',value)
    need(value is None or type(value) in (str,int,float,bool),'closed ordinary/numerical product')
    return value


def consume(request,catalog,output,budget):
    op=request['operation'];args=request['arguments'];selection=request['profile_selection']
    if op=='dpca_fit':
        closed(args,['trajectories'],'dPCA source trajectories')
        profile,lineage=resolve_profile(catalog,selection,DPCA_KEYS)
        arrays,support=read_trials(catalog,args['trajectories'],profile['numpy_version'])
        means=condition_means(arrays,support,profile,budget)
        state=fit_dpca(means,profile,budget)
        return {'state':output.state('dpca',state),'profile_lineage':lineage}
    if op=='pcr_fit':
        closed(args,['session_trajectories'],'PCR complete joint trajectory roster')
        profile,lineage=resolve_profile(catalog,selection,PCR_KEYS)
        need(type(args['session_trajectories']) is dict and len(args['session_trajectories'])==2,
             'original S11 exactly two selected sessions')
        means={}
        for sid,s in args['session_trajectories'].items():
            arrays,support=read_trials(catalog,s,profile['numpy_version'])
            means[sid]=condition_means(arrays,support,profile,budget)
        state=fit_pcr(means,profile,budget)
        return {'state':output.state('pcr',state),'profile_lineage':lineage,
                'native_three_model_training':'still requires original profile/producer'}
    if op=='dpca_transfer_distance':
        closed(args,['fitted_state','reference_trajectories','query_trajectories','component_selection'],
               'complete fixed-reference transfer selection')
        profile,lineage=resolve_profile(catalog,selection,['numpy_version'])
        state=read_state(catalog,args['fitted_state'],profile['numpy_version'])
        need(state['kind']=='regularized_dpca_v1','actual computed dPCA state')
        rs,rmeta=read_trials(catalog,args['reference_trajectories'],profile['numpy_version'])
        qs,qmeta=read_trials(catalog,args['query_trajectories'],profile['numpy_version'])
        need(identity(rmeta)==state['support_pin'],'reference trajectory support matches fitted Day0')
        need({k:array_identity(v) for k,v in rs.items()}==state['input_data_pins'],
             'actual reference trajectory values match fitted source state')
        reference=transfer_dpca(state,state['identity'],rs,rmeta,budget)
        query=transfer_dpca(state,state['identity'],qs,qmeta,budget)
        result=nomad_distance_grid(reference,query,state,catalog.document(args['component_selection']),budget)
        return {'reference':publish_tree(reference,output,'reference'),
                'query':publish_tree(query,output,'query'),
                'grid':publish_tree(result,output,'grid'),'profile_lineage':lineage}
    if op=='checkpoint_trace':
        closed(args,['states','state_shape','support','decoder','checkpoint','selected_checkpoint','inference'],
               'complete source-bound checkpoint and decoder')
        profile,lineage=resolve_profile(catalog,selection,['numpy_version','fixed_reference_coordinate_pin',
                                                          'decoder_fit_support_pin','decoder_artifact_pin'])
        support=catalog.document(args['support']);decoder=catalog.document(args['decoder'])
        closed(decoder,['method','reference_session','feature_ids','lag_offsets','axes','units',
            'weights','weights_shape','weights_descriptor','weights_value_pin','fit_support_pin','state_coordinates_pin'],
            'captured decoder metadata')
        weight_name=decoder.pop('weights')
        need(decoder.pop('weights_descriptor')==catalog.artifacts[weight_name], 'fixed decoder binds exact coefficient artifact')
        weights=catalog.array(weight_name,decoder.pop('weights_shape'),profile['numpy_version'])
        decoder['weights']=weights
        # The decoder document does not contain its own digest. Its independently
        # captured descriptor exists first; only the in-memory consumer adds it.
        decoder['decoder_pin']=catalog.artifacts[args['decoder']]['sha256']
        states=catalog.array(args['states'],args['state_shape'],profile['numpy_version'])
        checkpoint=catalog.document(args['checkpoint']);selected=catalog.document(args['selected_checkpoint'])
        inference=catalog.document(args['inference'])
        closed(inference,['scientific_binding','checkpoint_descriptor','states_descriptor','support_descriptor','inputs'],
               'acyclic inference capture document')
        need(inference['checkpoint_descriptor']==catalog.artifacts[args['checkpoint']]
             and inference['states_descriptor']==catalog.artifacts[args['states']]
             and inference['support_descriptor']==catalog.artifacts[args['support']], 'actual checkpoint/state/support artifacts joined before product')
        inputs=inference['inputs'];need(type(inputs) is dict and inputs, 'explicit actual inference input archive')
        for name,desc in inputs.items():
            need(name in catalog.artifacts and catalog.artifacts[name]==desc, 'actual inference input descriptor')
            catalog.raw(name)
        need(inference['scientific_binding']['input_pins']==inputs, 'scientific inference input identities')
        result=decode_checkpoint(states,support,decoder,checkpoint,selected,inference['scientific_binding'],profile,budget)
        return {'trace':publish_tree(result,output,'trace'),'profile_lineage':lineage}
    if op=='position':
        closed(args,['velocity','shape','timestamps','initial_position'],'full velocity/time/origin support')
        profile,lineage=resolve_profile(catalog,selection,POSITION_KEYS)
        velocity=catalog.array(args['velocity'],args['shape'],profile['numpy_version'])
        times=catalog.document(args['timestamps']);origin=catalog.document(args['initial_position'])
        result=integrate_position(velocity,times,origin,profile,budget)
        return {'position':publish_tree(result,output,'position'),'profile_lineage':lineage}
    if op=='t11_intended_target':
        closed(args,['movement'],'complete protected movement source')
        profile,lineage=resolve_profile(catalog,selection,TARGET_KEYS)
        movement=catalog.document(args['movement'])
        closed(movement,['times','center','target','acquired_at'],'exact protected target source fields')
        result=intended_reach(**movement,profile=profile,budget=budget)
        return {'target':publish_tree(result,output,'target'),'profile_lineage':lineage,
                'exposure_role':'trusted evaluation only; never current candidate query'}
    if op=='t11_events':
        closed(args,['cursor','shape','timestamps'],'complete source cursor/clock')
        profile,lineage=resolve_profile(catalog,selection,EVENT_KEYS)
        cursor=catalog.array(args['cursor'],args['shape'],profile['numpy_version'])
        result=derive_recenter_intervals(cursor,catalog.document(args['timestamps']),profile,budget)
        return {'events':result,'profile_lineage':lineage,'exposure_role':'trusted evaluation only'}
    if op=='t11_sequences':
        closed(args,['nwb','physical_schema','trial_identity_selection'],'actual physical trial and full sequence identities')
        profile,lineage=resolve_profile(catalog,selection,['success_value','trial_ids','sequence_ids','sequence_source_pin'])
        physical=read_physical_fields(catalog,args['nwb'],catalog.document(args['physical_schema']),budget)
        rows=physical_trial_rows(physical,catalog.document(args['trial_identity_selection']))
        result=complete_sequences(rows['trial_rows'],rows['sequence_members'],profile)
        return {'sequences':result,'profile_lineage':lineage,'exposure_role':'trusted evaluation only'}
    if op=='t11_chronology':
        return chronology_from_artifacts(args,catalog,selection,output,budget)
    raise ValueError('unknown operator; no generic native/scientific callback')


def chronology_from_artifacts(args,catalog,selection,output,budget,*,defer_physical=False):
    """Produce actual staged views from an exact captured block/prediction archive.

    The numerical predictions are captured products, never recomputed from target
    context here. Native generation/custody and model competence stay separately
    unqualified. This is an executable release operator, not a provider callback.
    """
    closed(args,['sessions','blocks','calibrations','predictions','query_schema','historical_fields','physical_sessions'],
           'complete source-owned chronological replay')
    profile,lineage=resolve_profile(catalog,selection,['numpy_version'])
    sessions=catalog.document(args['sessions']);blocks_meta=catalog.document(args['blocks'])
    query_schema=catalog.document(args['query_schema']);private={};physical_sessions={}
    if not defer_physical:
        physical_selection=catalog.document(args['physical_sessions'])
        need(type(physical_selection) is list and len(physical_selection)==2, 'both actual physical T11 session selections')
        for selected in physical_selection:
            closed(selected,['nwb','physical_schema','trial_identity_selection'], 'complete physical session source selection')
            schema=catalog.document(selected['physical_schema']);mapping=catalog.document(selected['trial_identity_selection'])
            physical=read_physical_fields(catalog,selected['nwb'],schema,budget)
            trial_rows=physical_trial_rows(physical,mapping);sid=physical['session_id']
            need(sid not in physical_sessions,'one actual physical file per T11 session')
            physical_sessions[sid]=(physical,trial_rows,mapping)
        need(set(physical_sessions)=={r['session_id'] for r in sessions}, 'all actual T11 sessions joined')
        for session in sessions:
            physical,trials,mapping=physical_sessions[session['session_id']]
            calibration=trials['offline_calibration_mapping']
            need(calibration['calibration_blocks']==[session['calibration_block']]
                 and calibration['evaluation_blocks']==session['postcalibration_blocks'],
                 'applied physical flags map to exactly selected calibration/evaluation order')
    need(type(blocks_meta) is list,'complete physical block artifact list')
    for row in blocks_meta:
        closed(row,['session_id','block_id','metadata','arrays','physical_lineage'],
               'physical block source selection')
        key=(row['session_id'],row['block_id']);need(key not in private,'unique exact source block')
        meta=catalog.document(row['metadata']);physical=catalog.document(row['physical_lineage'])
        if defer_physical:
            closed(physical,['session_id','block_id','metadata_pin','array_pins'],'pre-barrier public block lineage only')
        need(physical['session_id']==key[0] and physical['block_id']==key[1]
             and physical['metadata_pin']=={k:catalog.artifacts[row['metadata']][k] for k in ('bytes','sha256')},
             'source block lineage joins actual metadata')
        need(type(meta) is dict and meta['session_id']==key[0] and meta['block_id']==key[1],
             'physical block metadata identity')
        for field,a in row['arrays'].items():
            closed(a,['artifact','shape'],'complete physical array selection')
            need(field not in meta,'no overwritten private field')
            need(physical['array_pins'][field]=={k:catalog.artifacts[a['artifact']][k] for k in ('bytes','sha256')},
                 'actual original block array source')
            meta[field]=catalog.array(a['artifact'],a['shape'],profile['numpy_version'])
        if not defer_physical:
            original,trials,mapping=physical_sessions[key[0]];fields=original['fields']
            codes=fields['acquisition/block_num'];need(codes.ndim==1,'one actual physical block code per neural sample')
            indices=[]
            for i,value in enumerate(codes):
                code=str(value.item());need(code in mapping['block_labels'],'every actual neural block code mapped')
                if mapping['block_labels'][code]==key[1]:indices.append(i)
            need(indices and meta['timestamps']==[float(fields['timestamps'][i]) for i in indices],
                 'complete block neural clock equals actual converted physical clock, no omitted samples')
            for field in ('binned_spikes','cursor_pos','target_pos','cursor_vel','cond_id'):
                if field not in meta:
                    need(field!='binned_spikes','actual full physical neural field required');continue
                actual=fields['acquisition/'+field];selected=meta[field]
                need(hasattr(selected,'shape') and selected.shape==(len(indices),)+actual.shape[1:], 'actual full block field geometry')
                budget.reserve('T11.physical_compare.'+field,{'comparison_elements':selected.size})
                for j,i in enumerate(indices):
                    for left,right in zip(selected[j:j+1].flat,actual[i:i+1].flat):
                        a=right.item();b=left.item()
                        need((int(b)==a and b==int(b)) if type(a) in (int,bool) else b==a,
                             'archive field exactly matches original physical values')
            selected_trials=[r for r in trials['trial_rows'].values() if r['block_id']==key[1]]
            for name,field in (('trial_start','start_time'),('trial_stop','stop_time'),('result','result')):
                if name in meta:need(meta[name]==[r[field] for r in selected_trials],'actual physical historical trial field')
            if 'sequence_members' in meta:
                seq={k:v for k,v in trials['sequence_members'].items() if v and trials['trial_rows'][v[0]]['block_id']==key[1]}
                need(meta['sequence_members']==seq,'actual complete physical block sequence membership')
        else:
            closed(meta,['session_id','block_id','timestamps','binned_spikes'],'pre-barrier neural-only block archive')
            need(set(row['arrays'])=={'binned_spikes'},'no protected context array in pre-barrier replay')
        private[key]=meta
    release=ChronologicalRelease(sessions,private,query_schema,profile,budget)
    calibration=catalog.document(args['calibrations']);predictions=catalog.document(args['predictions'])
    expected_cal={(s['session_id'],m) for s in sessions for m in METHODS}
    need(len(calibration)==len(expected_cal) and
         {(r['session_id'],r['method']) for r in calibration}==expected_cal,'all eight exact calibration uses')
    for row in calibration:
        closed(row,['session_id','method','artifact','shape','state_pin'],'captured calibration product')
        release.register_calibration(row['session_id'],row['method'],
            catalog.array(row['artifact'],row['shape'],profile['numpy_version']),row['state_pin'])
    expected={(r['session_id'],r['block_id'],r['method']) for r in release.roster['slots']}
    need(type(predictions) is list and len(predictions)==len(expected) and
         {(r['session_id'],r['block_id'],r['method']) for r in predictions}==expected,
         'all method/block products or explicit retained failed attempts')
    table={(r['session_id'],r['block_id'],r['method']):r for r in predictions}
    published=[]
    for si,session in enumerate(sessions):
        sid=session['session_id'];blocks=session['postcalibration_blocks']
        for bi,block in enumerate(blocks):
            prefix='session'+str(si)+'.block'+str(bi)
            view=release.query_view(sid,block)
            query=output.document(prefix+'.query.json',publish_tree(view,output,prefix+'.query'))
            for method in METHODS:
                row=table[(sid,block,method)]
                closed(row,['session_id','block_id','method','status','artifact','shape','state_pin','failure'],
                       'closed captured attempt disposition')
                if row['status']=='complete':
                    need(row['failure'] is None,'no contradictory successful failure')
                    release.record_prediction(sid,block,method,
                        catalog.array(row['artifact'],row['shape'],profile['numpy_version']),row['state_pin'])
                else:
                    need(row['status']=='failed' and row['artifact'] is None and row['shape'] is None,
                         'retained unsuccessful source product')
                    prefix_record=catalog.document(row['failure'])
                    need(prefix_record['session_id']==sid and prefix_record['block_id']==block
                         and prefix_record['method']==method,'actual source attempt identity')
                    error=ValueError('captured failed original attempt: '+str(prefix_record['exception_type']))
                    release.record_failure(sid,block,method,error,catalog.artifacts[row['failure']]['sha256'])
            seal=release.seal_block(sid,block);history=None
            if bi+1<len(blocks):
                permitted=args['historical_fields'] if not defer_physical else [k for k in args['historical_fields'] if k in ('timestamps','binned_spikes')]
                context=release.historical_context(sid,blocks[bi+1],permitted) if permitted else []
                history=output.document(prefix+'.released_history.json',publish_tree(context,output,prefix+'.history'))
            published.append({'query':query,'seal':seal,'history_after_seal':history})
    return {'logical_closure':release.finish(),'ordered_view_products':published,
            'profile_lineage':lineage,'physical_validation_deferred_until_full_barrier':defer_physical,
            'deferred_task_context_fields':args['historical_fields'] if defer_physical else [],
            'scope':'captured-product chronology; no original native/provider run is asserted'}


def statistical_grade(request,catalog,target_catalog,output,budget):
    from .statistics import Budget as StatisticalBudget,capture_facts,compile_statistical_roster,score_prediction,reduce_statistical_study
    from .statistics.nomad_statistics import SUPPORT_KEYS
    from .statistics.nomad_stat_math import pin as statistical_pin
    args=request['arguments']
    closed(args,['fact_documents','fact_selection','statistic_documents','statistic_selection',
                 'products','statistical_limits','archive_selection','t11_replay','t11_evaluation'],'complete statistical source/array selection')
    limits=StatisticalBudget(args['statistical_limits'])
    facts=capture_facts({name:catalog.raw(artifact) for name,artifact in args['fact_documents'].items()},
                        catalog.document(args['fact_selection']),limits)
    roster=compile_statistical_roster(facts,limits)
    policy=capture_facts({name:catalog.raw(artifact) for name,artifact in args['statistic_documents'].items()},
                         catalog.document(args['statistic_selection']),limits)
    selection=catalog.document(args['archive_selection']);t11=None
    if args['t11_replay'] is not None:
        replay=args['t11_replay'];closed(replay,['arguments','profile_selection'],'complete source-owned T11 replay selection')
        t11=chronology_from_artifacts(replay['arguments'],catalog,replay['profile_selection'],output,budget,defer_physical=True)['logical_closure']
    need(type(args['products']) is list,'complete captured product selector')
    captured=[];seen=set()
    # Complete every selected prediction capture before ANY protected target body.
    for row in args['products']:
        closed(row,['support','prediction','shape','target','target_support','lineage','status','failure'],
               'exact complete prediction/target/lineage pair')
        support=catalog.document(row['support']);closed(support,SUPPORT_KEYS,'closed actual prediction/failed-slot support')
        for key in ('method_profile_pin','source_pin','target_support_pin'):statistical_pin(support[key])
        need(support['product_id'] not in seen,'one actual product per ID');seen.add(support['product_id'])
        if row['status']=='failed':
            need(row['prediction'] is None and row['shape'] is None and row['lineage'] is None,
                 'failed slot cannot fabricate a prediction array')
            need(support['prediction_artifact_pin'] is None,'failed slot has no invented prediction artifact')
            need(support['target_artifact_pin']=={k:target_catalog.artifacts[row['target']][k] for k in ('bytes','sha256')}
                 and support['target_support_pin']=={k:target_catalog.artifacts[row['target_support']][k] for k in ('bytes','sha256')},
                 'failed slot retains independent target descriptors without reading target bodies')
            need(support['prediction_lineage_pin']=={k:catalog.artifacts[row['failure']][k] for k in ('bytes','sha256')}, 'actual failed prefix lineage pin')
            failure=catalog.document(row['failure'])
            closed(failure,['schema','product_id','method','session_id','block_id','reference_id','query_id','role','exception_type'],
                   'closed captured failed-attempt prefix')
            need(failure['schema']=='nomad_captured_failed_attempt_v2' and failure['session_id']==support['task']
                 and failure['block_id']==support['query_id'] and type(failure['exception_type']) is str and failure['exception_type'],
                 'actual failed slot/source identity')
            for key in ('product_id','method','reference_id','query_id','role'):
                need(failure[key]==support[key],'failed attempt matches expected support')
            captured.append(({**row,'failure_descriptor':catalog.artifacts[row['failure']]},support,None,failure));continue
        need(row['status']=='complete' and row['failure'] is None,'exact complete/failed archive disposition')
        need(support['prediction_artifact_pin']=={k:catalog.artifacts[row['prediction']][k] for k in ('bytes','sha256')},
             'actual prediction source pin')
        need(support['prediction_lineage_pin']=={k:catalog.artifacts[row['lineage']][k] for k in ('bytes','sha256')},
             'actual source/native/state/decoder lineage pin')
        lineage=catalog.document(row['lineage'])
        need(lineage['method']==support['method'] and lineage['reference_id']==support['reference_id']
             and lineage['query_id']==support['query_id'],'captured scientific identity matches score slot')
        prediction=catalog.array(row['prediction'],row['shape'],support['expected_numpy_version'])
        captured.append((row,support,prediction,lineage))
    closure=close_archive(roster.body(limits),selection,captured,t11)
    barrier=output.document('PRETARGET_CAPTURE.json',{'schema':'nomad_recovered_operator_prediction_capture_v1',
        'roster_pin':roster.pin,'fact_pin':facts.pin,'policy_pin':policy.pin,
        'prediction_product_ids':sorted(seen),'captures':list(catalog.captures),'local_archive_closure':closure,
        'actual_process_closure_independently_verified':False,
        'scope':'immutable supplied-product analysis; no original-process or study qualification inferred'})
    windows=None
    if t11 is not None:
        need(type(args['t11_evaluation']) is str and args['t11_evaluation'], 'protected physical evaluation selection required')
        windows=T11Windows(closure,captured,target_catalog,args['t11_evaluation'],budget)
    else:need(args['t11_evaluation'] is None,'no unselected T11 protected evaluation')
    products=[];evaluation_views=[]
    for row,support,prediction,lineage in captured:
        if row['status']=='failed':continue
        need(support['target_artifact_pin']=={k:target_catalog.artifacts[row['target']][k] for k in ('bytes','sha256')}
             and support['target_support_pin']=={k:target_catalog.artifacts[row['target_support']][k] for k in ('bytes','sha256')},
             'independently selected protected target and support bytes')
        ts=target_catalog.document(row['target_support'])
        closed(ts,['sample_ids','axis_ids','axis_units'],'full target support/units')
        view=windows.project(support,prediction,lineage) if windows is not None and support['task'] in windows.sessions else None
        sample_ids=support['sample_ids'] if view is None else view['sample_ids']
        need(ts['sample_ids']==sample_ids and ts['axis_ids']==support['axis_ids']
             and ts['axis_units']==lineage['axis_units'],'exact evaluator-selected prediction/target/unit support')
        shape=row['shape'] if view is None else list(view['prediction'].shape)
        target=target_catalog.array(row['target'],shape,support['expected_numpy_version'])
        if view is not None:
            need(array_identity(target)==array_identity(view['target']), 'supplied protected targets equal constructed intended targets on exact eligible rows')
            name='evaluation-'+str(len(evaluation_views))
            projected=output.array(name+'.prediction.f64',view['prediction'])
            proof=output.document(name+'.support.json',{'product_id':support['product_id'],
                'full_prediction_artifact_pin':support['prediction_artifact_pin'],'full_seal':view['full_seal'],
                'selected_rows':view['selected_rows'],'sample_ids':view['sample_ids'],'evaluation_source':view['evaluation_source'],
                'movement_dispositions':view['movement_dispositions']})
            support={**support,'sample_ids':sample_ids,'prediction_artifact_pin':{k:projected['artifact'][k] for k in ('bytes','sha256')},
                'prediction_lineage_pin':{k:proof[k] for k in ('bytes','sha256')}}
            prediction=view['prediction'];evaluation_views.append({'prediction':projected,'support':proof})
        products.append(score_prediction(prediction,target,support,limits))
    result=reduce_statistical_study(roster,products,policy,limits)
    return {'pretarget_capture':barrier,'local_archive_closure':closure,'statistical_outputs':result,
            'protected_target_captures':list(target_catalog.captures),'evaluator_selected_views':evaluation_views,
            'statistical_work_after_reduction':limits.snapshot(),
            'original_native_reproduction_or_superiority_qualified':False,
            'process_custody_limitation':'This archive consumer does not establish original owned-process closure; existing native lifecycle must supply that separately.'}


def run(request,environment):
    closed(request,['schema','action','operation','arguments','profile_selection','input_root','artifacts',
        'protected_target_root','protected_target_artifacts','destination','io_limits','array_limits',
        'numeric_limits'],'closed recovered operator request')
    need(request['schema']=='nomad_recovered_operator_request_v1','selected request schema')
    closed(request['io_limits'],['read_bytes','write_bytes','max_member_bytes'],'explicit whole source/array I/O limits')
    closed(request['array_limits'],['max_array_elements'],'explicit complete array limit')
    closed(request['numeric_limits'],['max_array_elements','cumulative_elements','cumulative_matmul_products'],
           'explicit numerical work preflight')
    store=Store(request['io_limits']['read_bytes'],request['io_limits']['write_bytes'])
    need(environment['bootstrap_read_bytes']<=store.read_limit,'startup source reads included')
    store.read_reserved=environment['bootstrap_read_bytes']
    data=environment['source_data']
    if request['action']=='plan':
        need(request['operation'] is None and request['arguments']=={} and request['profile_selection']=={},
             'metadata plan performs no hidden operation')
        return {'schema':'nomad_recovered_operator_plan_v1','source_manifest_pin':environment['source_manifest_pin'],
            'obligations':strict_json(data['OBLIGATIONS_V3.json']),
            'statistics':strict_json(data['STATISTICAL_ENDPOINTS.json']),
            'unresolved':strict_json(data['UNRESOLVED_V3.json']),
            'actual_scientific_runs':0,'whole_original_study_complete':False}
    need(request['action'] in ('consume','grade'),'known explicit action')
    catalog=Catalog(request['input_root'],request['artifacts'],store,
                    request['io_limits']['max_member_bytes'],request['array_limits']['max_array_elements'])
    budget=Budget(**request['numeric_limits']);output=None;failure=None;result=None;targets=None
    try:
        output=Output(request['destination'],store,request['array_limits']['max_array_elements'],budget)
        if request['action']=='consume':
            need(request['protected_target_root'] is None and request['protected_target_artifacts']=={},
                 'ordinary operators have no implicit private target catalogue')
            result=consume(request,catalog,output,budget)
        else:
            need(request['operation']=='statistics' and request['profile_selection']=={},'exact protected statistical action')
            targets=Catalog(request['protected_target_root'],request['protected_target_artifacts'],store,
                request['io_limits']['max_member_bytes'],request['array_limits']['max_array_elements'])
            result=statistical_grade(request,catalog,targets,output,budget)
        terminal={'schema':'nomad_recovered_operator_result_v1','operation':request['operation'],
            'source_manifest_pin':environment['source_manifest_pin'],'result':result,
            'captured_inputs':catalog.captures,'logical_read_reserved':store.read_reserved,
            'logical_write_reserved_before_terminal':store.write_reserved,'numerical_work':budget.report(),
            'whole_original_study_complete':False,'historical_parity':False,'runtime_qualified':False}
        desc=output.document('RESULT.json',terminal)
        return {'result':desc,'products':output.files,'historical_parity':False,'runtime_qualified':False}
    except BaseException as error:
        failure=error
        prefix={'schema':'nomad_recovered_operator_failure_v1','type':type(error).__name__,
            'message':str(error),'captured_inputs':catalog.captures,'logical_read_reserved':store.read_reserved,
            'protected_target_captures':[] if targets is None else list(targets.captures),
            'logical_write_reserved':store.write_reserved,'numerical_work':budget.report(),
            'products':{} if output is None else output.files}
        setattr(error,'nomad_failure_prefix',prefix)
        if output is not None:
            try:output.document('FAILURE.json',prefix)
            except BaseException as secondary:setattr(error,'nomad_failure_publication_secondary',type(secondary).__name__)
        raise

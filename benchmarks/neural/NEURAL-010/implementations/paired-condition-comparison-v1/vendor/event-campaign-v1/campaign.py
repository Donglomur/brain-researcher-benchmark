"""Full held-person event campaign and unchanged protected scorer composition.

This is an actual source-owned exchange driver. External deployment receipts are
operator trust inputs, not evidence manufactured by this source. No candidate
callback, model import, reference fit or scientific package runs on module import.
"""
from pathlib import Path
import common as u
import compatibility as compat
import provider
import exchange

CONTRACT_FIELDS=('method_sha256','learning_policy_sha256','training_policy_sha256',
    'tool_policy_sha256','tuning_policy_sha256','resource_policy_sha256')
MODES=('typed_viewer','frozen_program')


def library(root,io):
    """Pinned frozen interface closure is loaded by entry before any operations."""
    import types
    p=Path(root)/'vendor/detection-interface-v1/interface.py'
    raw=io.capture({'path':str(p),**compat.DETECTION_PIN},'detector_source',20531)
    m=types.ModuleType('neural010_event_campaign_detection');m.__file__=str(p)
    exec(compile(raw,str(p),'exec'),m.__dict__)
    return m


def reserve_interface(io):
    # The unchanged interface/scorer reopen only their pinned small source files.
    # Reserve a conservative16 scorer+event source captures before each call.
    io.budget.charge('read_bytes',16*(13274+100001))


def exact_policy(policy,mode):
    u.exact(policy,('training','max_actions_per_fold','max_samples_per_request',
        'max_channels_per_request','frame_bytes','delivery','display_half_range_microvolts'))
    u.need(mode in MODES,'one explicit campaign mode')
    u.c.integer(policy['max_actions_per_fold'],1,100000)
    u.c.integer(policy['max_samples_per_request'],1,4096)
    u.c.integer(policy['max_channels_per_request'],1,16)
    u.c.integer(policy['frame_bytes'],1024,u.CAP)
    if mode=='typed_viewer':
        u.need(u.c.finite(policy['display_half_range_microvolts'])>0,'operator-selected fixed display gain')
        u.need(policy['training']=='none'and policy['delivery']=='rendered_pixels','zero-shot viewer has no training/raw-array capability')
    else:u.need(policy['training']in ('none','other22')and policy['delivery']=='calibrated_windows'and policy['display_half_range_microvolts']is None,'explicit programme training and numerical access')


def selection(value,source_pin):
    u.exact(value,('schema','source','preparation','mode','candidate_contract','policy','contexts','limits','evaluation'))
    u.need(value['schema']=='neural010-event-campaign-request-v1'and u.c.same(value['source'],source_pin),'selected event-campaign source')
    u.exact(value['candidate_contract'],CONTRACT_FIELDS)
    for v in value['candidate_contract'].values():u.c.digest(v)
    exact_policy(value['policy'],value['mode'])
    u.c.descriptor(value['evaluation'],True)
    u.need(value['candidate_contract']['tool_policy_sha256']==u.pin(u.encoded({'mode':value['mode'],'policy':value['policy']}))['sha256'],'actual tool/observation/display policy binding')
    u.need(value['candidate_contract']['resource_policy_sha256']==u.pin(u.encoded(value['limits']))['sha256'],'exact candidate resource policy binding')
    u.need(value['candidate_contract']['training_policy_sha256']==u.pin(u.encoded({'training':value['policy']['training']}))['sha256'],'exact training policy binding')
    u.need(type(value['contexts'])is dict and len(value['contexts'])==23,'23 separately selected outer contexts')
    roots=[];ids=[]
    for pid,row in value['contexts'].items():
        u.c.ident(pid);u.exact(row,('context_id','participant_exchange','custody_exchange','renderer_exchange'))
        u.c.digest(row['context_id']);ids.append(row['context_id'])
        for k in ('participant_exchange','custody_exchange'):
            roots.append(u.c.absolute(row[k]))
        if value['mode']=='typed_viewer':roots.append(u.c.absolute(row['renderer_exchange']))
        else:u.need(row['renderer_exchange']is None,'programme has no viewer transport')
    u.need(len(ids)==len(set(ids)),'fresh unique external context identity for each person')
    for i,a in enumerate(roots):
        for b in roots[i+1:]:
            aa,bb=Path(str(a).casefold()),Path(str(b).casefold())
            u.need(aa!=bb and not aa.is_relative_to(bb)and not bb.is_relative_to(aa),'disjoint casefold-safe participant/custody/renderer namespaces across all folds')
    return value


def execution_authority(raw,selected_pin,request_raw,source_pin):
    u.need(u.c.same(u.pin(raw),selected_pin),'independently selected operator authority bytes')
    a=u.parse(raw)
    u.exact(a,('schema','request','source','evidence_class','deployment_receipt','context_ids'))
    u.need(a['schema']=='neural010-event-campaign-authority-v1'and u.c.same(a['request'],u.pin(request_raw))
        and u.c.same(a['source'],source_pin),'operator authority binds exact request/source')
    u.need(a['evidence_class']in ('generated_control','operator_selected_deployment'),'explicit evidence class')
    u.c.descriptor(a['deployment_receipt'],True)
    u.need(type(a['context_ids'])is list and len(a['context_ids'])==23 and len(set(a['context_ids']))==23,'full independent context selection')
    return a


def admit_deployment(io,authority,request):
    body=io.capture(authority['deployment_receipt'],'operator_selected_deployment',1048576)
    d=u.parse(body)
    u.exact(d,('schema','campaign_request','source','evidence_class','context_ids','mode','capabilities'))
    u.need(d['schema']=='neural010-event-deployment-binding-v1'and u.c.same(d['campaign_request'],authority['request'])
        and u.c.same(d['source'],request['source'])and d['evidence_class']==authority['evidence_class']
        and d['mode']==request['mode'],'same externally selected deployment contract')
    wanted=sorted(c['context_id']for c in request['contexts'].values())
    u.need(d['context_ids']==authority['context_ids']==wanted,'same complete fresh context identities')
    required=['fresh_context_per_person','only_current_fold_allowlist','no_controller_filesystem',
        'no_cross_fold_memory','independent_launch_and_close','read_only_signals',request['policy']['delivery']]
    if request['mode']=='typed_viewer':required+=['no_code_execution','no_raw_array_or_svg_export','no_task_specific_detector_tools','visual_observation_only']
    u.need(d['capabilities']==required,'complete explicit physical custody obligations')
    return u.pin(body)


def intake(request,io,root,detector):
    prepared=compat.admit(request['preparation'],io,require_all_views=False)
    projected=compat.export_detection(prepared,Path(root)/'vendor/detection-interface-v1',io)['projection']
    support,rows=detector.support_rows(projected['support'])
    u.need(set(request['contexts'])=={r['patient_id']for r in rows.values()},'all23 biological people including source alias join')
    private=u.parse(projected['private_bindings'])
    return prepared,projected,rows,private


def scoped_rows(rows,person,training):
    return {r['signal_handle']:r for r in rows.values()if (r['patient_id']!=person if training else r['patient_id']==person)}


def closure(reply, *, operation, context, request_pin, state=None, submission=None):
    fields=('schema','operation','context_id','request_sha256','status','fold_state_sha256','submission')
    u.exact(reply,fields)
    u.need(reply['schema']=='neural010-external-context-receipt-v1'and reply['operation']==operation
        and reply['context_id']==context and reply['request_sha256']==request_pin['sha256']
        and reply['status']==('isolated_context_started'if operation=='launch'else'natural_exit_and_context_retired'),
        'selected external lifecycle receipt; no self-issued process proof')
    u.need(reply['fold_state_sha256']==state and u.c.same(reply['submission'],submission),'closure binds exact state and submitted bytes')


def run(request_raw,authority_raw,authority_pin,*,source_pin,source_root,output_root,io,
        signal_factory=provider.H5Signals,exchange_factory=exchange.Exchange):
    request=selection(u.parse(request_raw),source_pin)
    u.need(u.c.same(io.budget.limits,request['limits']),'actual original budget equals selected resource policy')
    authority=execution_authority(authority_raw,authority_pin,request_raw,source_pin)
    deployment=admit_deployment(io,authority,request)
    separated_namespaces(request,output_root,source_root,authority['deployment_receipt']['path'])
    evaluation_raw=io.capture(request['evaluation'],'preselected_reference_evaluation',1048576)
    evaluation=evaluation_spec(u.parse(evaluation_raw),request)
    root=io.directory(output_root)
    reservation_pin=io.create(root/'WHOLE_RUN_RESERVATION.json',u.encoded({'request':u.pin(request_raw),'limits':request['limits'],
        'origin_monotonic':io.budget.origin,'deadline_monotonic':io.budget.end,'entire_reservation_retained_on_failure':True}))
    frozen_request=io.create(root/'SELECTED_REQUEST.json',request_raw)
    io.create(root/'SELECTED_AUTHORITY.json',authority_raw)
    io.create(root/'SELECTED_EVALUATION.json',evaluation_raw)
    d=library(source_root,io)
    prepared,projected,rows,private=intake(request,io,source_root,d)
    evaluation_preparation(evaluation,prepared)
    support_pin=io.create(root/'SUPPORT.json',projected['support'])
    io.create(root/'SCIENTIFIC_PANEL.json',projected['scientific_panel'])
    io.create(root/'PRIVATE_BINDINGS.json',projected['private_bindings'])
    signals=signal_factory(io,prepared['public_root'],private['signals'],rows)
    queries,submissions,folds={},{},[]
    total_raw_events=0
    method=request['candidate_contract']['method_sha256'];mode=request['mode'];policy=request['policy']
    for person in sorted(request['contexts']):
        ctx=request['contexts'][person];fold=io.directory(root/person)
        # Full per-person transcripts remain operator-private. The external
        # custody service exposes only this fold's participant exchange.
        worker=exchange_factory(io,ctx['participant_exchange'],ctx['context_id'],'participant',policy['frame_bytes'])
        keeper=exchange_factory(io,ctx['custody_exchange'],ctx['context_id'],'custody',policy['frame_bytes'])
        display=None
        if mode=='typed_viewer':
            renderer=exchange_factory(io,ctx['renderer_exchange'],ctx['context_id'],'renderer',policy['frame_bytes'])
            display=exchange.Display(renderer)
        observations=provider.Observations(signals,policy,io.budget,display)
        train=None
        if policy['training']=='other22':
            desc=prepared['views'][person+'/final']['TRAIN.json']
            raw=io.capture_training(desc,u.CAP)
            reserve_interface(io)
            train=d.project_training_view(raw,u.c.bare(desc),projected['support'],held_person=person)
        launch={'operation':'launch','held_person':person,'mode':mode,'candidate_contract':request['candidate_contract'],
            'policy':policy,'participant_exchange':ctx['participant_exchange'],'renderer_exchange':ctx['renderer_exchange'],
            'deployment':deployment,'controller_and_other_folds_excluded':True,
            'controller_origin_monotonic':io.budget.origin,'controller_deadline_monotonic':io.budget.end,
            'aggregate_limits':request['limits'],'terminate_on_controller_loss_or_deadline':True}
        started,started_raw,start_request=keeper.request(launch)
        closure(started,operation='launch',context=ctx['context_id'],request_pin=start_request)
        launch_pin=io.create(fold/'LAUNCH.json',started_raw)
        io.create(fold/'LAUNCH_REQUEST.json',io.capture(start_request,'original_source_launch_request',policy['frame_bytes']))
        initial={'operation':'initialize','context_id':ctx['context_id'],'method_sha256':method,'mode':mode,
            'training':None if train is None else u.parse(train),'policy':policy}
        action,raw,reqpin=worker.request(initial)
        io.create(fold/'ACTION-000000.json',raw)
        state=None;query=None;actions=0
        while True:
            actions+=1
            u.need(actions<=policy['max_actions_per_fold'],'finite full fold action budget; no implicit empty fallback')
            u.need(type(action)is dict and type(action.get('kind'))is str,'structured participant action')
            if action['kind']=='observe':
                u.need(state is not None or train is not None,'no pre-query observation in zero-shot condition')
                allowed=scoped_rows(rows,person,state is None)
                response=observations.observe(action,allowed,mode)
                io.create(fold/f'OBSERVATION-{actions:06d}.json',u.encoded(response))
                action,raw,reqpin=worker.request({'operation':'observation','value':response})
                io.create(fold/f'ACTION-{actions:06d}.json',raw)
            elif action['kind']=='ready':
                u.exact(action,('kind','method_sha256','fold_state_sha256'))
                u.need(state is None and action['method_sha256']==method,'one method-bound pre-query state freeze')
                state=u.c.digest(action['fold_state_sha256'])
                frozen_state,frozen_state_raw,freeze_request=keeper.request({'operation':'freeze_state',
                    'context_id':ctx['context_id'],'candidate_contract':request['candidate_contract'],
                    'fold_state_sha256':state,'held_person':person,'training':policy['training'],
                    'held_query_not_delivered':True})
                u.exact(frozen_state,('schema','context_id','request_sha256','candidate_contract','fold_state_sha256',
                    'training_complete','held_query_not_delivered','state_immutable_for_query'))
                u.need(frozen_state['schema']=='neural010-external-state-freeze-v1'
                    and frozen_state['context_id']==ctx['context_id']and frozen_state['request_sha256']==freeze_request['sha256']
                    and u.c.same(frozen_state['candidate_contract'],request['candidate_contract'])and frozen_state['fold_state_sha256']==state
                    and frozen_state['training_complete']is True and frozen_state['held_query_not_delivered']is True
                    and frozen_state['state_immutable_for_query']is True,'independently bound pre-query freeze acknowledgement')
                external_state_pin=io.create(fold/'EXTERNAL_STATE_FREEZE.json',frozen_state_raw)
                io.create(fold/'STATE_REQUEST.json',io.capture(freeze_request,'original_source_state_request',policy['frame_bytes']))
                state_pin=io.create(fold/'STATE_FREEZE.json',u.encoded({'context_id':ctx['context_id'],
                    'held_person':person,'candidate_contract':request['candidate_contract'],'policy':policy,'fold_state_sha256':state}))
                reserve_interface(io)
                query=d.make_query(projected['support'],held_person=person,mode=mode,method_sha256=method,fold_state_sha256=state)
                u.need(sum(len(v)for v in queries.values())+len(query)<=d.CAP,'full aggregate query byte cap before retention')
                io.create(fold/'QUERY.json',query);queries[person]=query
                action,raw,reqpin=worker.request({'operation':'held_person_query','state_freeze':u.c.bare(state_pin),'query':u.parse(query)})
                io.create(fold/f'ACTION-{actions:06d}.json',raw)
            else:
                u.need(action['kind']=='submit'and state is not None,'only explicit final submission after state/query freeze')
                u.exact(action,('kind','submission'))
                submission=u.encoded(action['submission'])
                # Original interface performs the final full-campaign check;
                # reject per-fold missing/extra support before asking for closure.
                sub=u.parse(submission);u.exact(sub,('schema','query_sha256','records'))
                u.need(sub['schema']=='neural010-detection-submission-v1'and sub['query_sha256']==d.pin(query)['sha256'],'actual held query output binding')
                expected={r['recording_id']:r for r in rows.values()if r['patient_id']==person}
                found=d._by_id(sub['records'],len(expected));u.need(set(found)==set(expected),'every held recording explicitly submitted')
                reserve_interface(io);scorer=d.scorer()
                for rid,row in found.items():
                    u.exact(row,('recording_id','events'));u.need(type(row['events'])is list,'explicit participant interval list')
                    total_raw_events+=len(row['events'])
                    u.need(total_raw_events<=d.RAW_EVENT_CAP,'complete raw-event cap before storing fold output')
                    scorer.intervals(row['events'],expected[rid]['duration_seconds'])
                u.need(sum(len(v)for v in submissions.values())+len(submission)<=d.CAP,'full aggregate submitted byte cap before retention')
                submitted=io.create(fold/'SUBMISSION.json',submission)
                done,done_raw,close_request=keeper.request({'operation':'close','context_id':ctx['context_id'],
                    'fold_state_sha256':state,'submission':u.c.bare(submitted),'no_reuse_of_context':True})
                closure(done,operation='close',context=ctx['context_id'],request_pin=close_request,state=state,submission=u.c.bare(submitted))
                close_pin=io.create(fold/'CLOSURE.json',done_raw)
                io.create(fold/'CLOSE_REQUEST.json',io.capture(close_request,'original_source_close_request',policy['frame_bytes']))
                submissions[person]=submission
                folds.append({'person':person,'context_id':ctx['context_id'],'query':d.pin(query),
                    'submission':d.pin(submission),'closure':u.c.bare(close_pin),'launch':u.c.bare(launch_pin),
                    'state_freeze':u.c.bare(external_state_pin),'launch_request':u.c.bare(start_request),
                    'state_request':u.c.bare(freeze_request),'close_request':u.c.bare(close_request),'actions':actions})
                break
    reserve_interface(io)
    frozen=d.freeze_candidate(support_bytes=projected['support'],queries=queries,submissions=submissions,mode=mode,method_sha256=method)
    candidate=io.create(root/'CANDIDATE.json',frozen['candidate']);freeze=io.create(root/'FREEZE.json',frozen['freeze'])
    receipt={'schema':'neural010-event-campaign-complete-v1','request':u.c.bare(frozen_request),'source':source_pin,
        'reservation':u.c.bare(reservation_pin),'support':u.c.bare(support_pin),'candidate':u.c.bare(candidate),'freeze':u.c.bare(freeze),'folds':folds,
        'records':686,'people':23,'evidence_class':authority['evidence_class'],'deployment':deployment,
        'assessment_opened':False,'source_or_physical_qualification_created':False,'costs':dict(io.budget.used)}
    return io.create(root/'CAMPAIGN.json',u.encoded(receipt))


def separated_namespaces(request, output_root, source_root, deployment_path):
    protected=[u.c.absolute(str(output_root)),u.c.absolute(str(source_root)),
        u.c.absolute(request['preparation']['private_root']),u.c.absolute(request['preparation']['public_root']),
        u.c.absolute(request['evaluation']['path']).parent,u.c.absolute(deployment_path).parent]
    for key in ('workspace_root','anchor_root'):
        if key in request['preparation']:protected.append(u.c.absolute(request['preparation'][key]))
    for ctx in request['contexts'].values():
        for name in ('participant_exchange','custody_exchange','renderer_exchange'):
            if ctx[name]is None:continue
            p=u.c.absolute(ctx[name])
            for q in protected:
                pp,qq=Path(str(p).casefold()),Path(str(q).casefold())
                u.need(pp!=qq and not pp.is_relative_to(qq)and not qq.is_relative_to(pp),'exchange cannot contain or overlap operator/source/preparation data')


def evaluation_spec(v,request):
    u.exact(v,('schema','references','reference_provenance','interpretation','candidate_contract','original_panel','original_assessment'))
    u.need(v['schema']=='neural010-event-evaluation-selection-v1','exact preselected evaluation schema')
    u.need(v['interpretation']in ('fixed_reference_comparison','matched_ablation_requested'),'explicit comparator interpretation')
    u.need(u.c.same(v['candidate_contract'],request['candidate_contract']),'evaluation bound to actual candidate method and access/tuning/resource contract')
    u.exact(v['references'],('matched_no_eeg','signal_reference','montage_only'))
    for x in v['references'].values():u.c.descriptor(x,True)
    u.c.descriptor(v['reference_provenance'],True)
    for k in ('original_panel','original_assessment'):u.c.descriptor(v[k])
    return v


def evaluation_preparation(evaluation,prepared):
    u.need(u.c.same(evaluation['original_panel'],u.c.bare(prepared['panel_pin']))
        and u.c.same(evaluation['original_assessment'],prepared['assessment_pin']),'original panel and assessment selection frozen before candidate exposure')


def reference_binding(io,evaluation,evidence_class,people,training):
    raw=io.capture(evaluation['reference_provenance'],'independent_reference_provenance',1048576)
    proof=u.parse(raw)
    u.exact(proof,('schema','evidence_class','reference_pins','candidate_contract','interpretation','reference_runs','matching_evidence'))
    u.need(proof['schema']=='neural010-independent-reference-binding-v1'and proof['evidence_class']==evidence_class
        and proof['interpretation']==evaluation['interpretation']and u.c.same(proof['candidate_contract'],evaluation['candidate_contract']),
        'independently selected comparator provenance and actual candidate contract')
    pins={arm:u.c.bare(v)for arm,v in evaluation['references'].items()}
    u.need(u.c.same(proof['reference_pins'],pins),'exact independently supplied reference stream bytes')
    u.exact(proof['reference_runs'],pins)
    for arm,desc in proof['reference_runs'].items():
        u.c.descriptor(desc,True)
        run=u.parse(io.capture(desc,'independent_'+arm+'_run_binding',1048576))
        u.exact(run,('schema','arm','stream','held_people','source_identity','training_protocol','tuning_protocol','resource_protocol','closure_evidence'))
        u.need(run['schema']=='neural010-reference-run-binding-v1'and run['arm']==arm
            and u.c.same(run['stream'],pins[arm])and run['held_people']==sorted(people),'complete independent reference run/held-person binding')
        for key in ('source_identity','training_protocol','tuning_protocol','resource_protocol'):u.c.descriptor(run[key])
        u.c.descriptor(run['closure_evidence'],True)
        # Exact independently selected provenance is retained; opaque process
        # proof is not turned into qualified execution by reading its bytes.
        io.capture(run['closure_evidence'],'independent_reference_closure',1048576)
    if evaluation['interpretation']=='matched_ablation_requested':
        u.c.descriptor(proof['matching_evidence'],True)
        matching=u.parse(io.capture(proof['matching_evidence'],'independent_matched_ablation_binding',1048576))
        u.exact(matching,('schema','candidate_contract','no_eeg_stream','fold_training_people','matching_dimensions','issuer_evidence'))
        u.need(matching['schema']=='neural010-candidate-matched-control-binding-v1'
            and u.c.same(matching['candidate_contract'],evaluation['candidate_contract'])
            and u.c.same(matching['no_eeg_stream'],pins['matched_no_eeg'])
            and u.c.same(matching['fold_training_people'],{p:[]if training=='none'else[q for q in sorted(people)if q!=p]for p in sorted(people)})
            and matching['matching_dimensions']==['learner','training','tuning','metadata','tools','compute','signal_access_only_difference'],
            'actual candidate-specific matched-control binding; historical fixed learner cannot be relabelled')
        u.c.descriptor(matching['issuer_evidence'],True)
        io.capture(matching['issuer_evidence'],'independent_matching_issuer_evidence',1048576)
    else:u.need(proof['matching_evidence']is None,'fixed comparator does not imply matched ablation')
    return u.pin(raw)


def score(request_raw,authority_raw,authority_pin,*,source_pin,source_root,output_root,io):
    request=u.parse(request_raw)
    u.exact(request,('schema','source','campaign','campaign_request','limits'))
    u.need(request['schema']=='neural010-event-score-request-v1'and u.c.same(request['source'],source_pin),'exact selected score route')
    u.need(u.c.same(u.pin(authority_raw),authority_pin),'selected protected release authority')
    authority=u.parse(authority_raw)
    u.exact(authority,('schema','request','campaign','source','evidence_class','assessment'))
    u.need(authority['schema']=='neural010-event-score-authority-v1'and u.c.same(authority['request'],u.pin(request_raw))
        and u.c.same(authority['campaign'],request['campaign'])and u.c.same(authority['source'],source_pin),'independent protected score selection')
    u.need(u.c.same(io.budget.limits,request['limits']),'actual selected scoring resource policy')
    u.c.descriptor(request['campaign'],True);u.c.descriptor(request['campaign_request'],True)
    root=u.c.absolute(request['campaign']['path']).parent
    u.need(request['campaign']['path']==str(root/'CAMPAIGN.json')and request['campaign_request']['path']==str(root/'SELECTED_REQUEST.json'),'literal frozen campaign operands before capture')
    complete_raw=io.capture(request['campaign'],'complete_frozen_campaign',1048576)
    complete=u.parse(complete_raw)
    u.exact(complete,('schema','request','source','reservation','support','candidate','freeze','folds','records','people','evidence_class','deployment','assessment_opened','source_or_physical_qualification_created','costs'))
    u.need(complete['schema']=='neural010-event-campaign-complete-v1'and type(complete['records'])is int and complete['records']==686
        and type(complete['people'])is int and complete['people']==23 and complete['assessment_opened']is False
        and complete['source_or_physical_qualification_created']is False and complete['evidence_class']==authority['evidence_class'],
        'complete source campaign only; generated evidence cannot become authentic at score')
    root=u.c.absolute(request['campaign']['path']).parent
    u.need(request['campaign']['path']==str(root/'CAMPAIGN.json')and request['campaign_request']['path']==str(root/'SELECTED_REQUEST.json'),'literal frozen campaign operands')
    original_raw=io.capture(request['campaign_request'],'frozen_original_request',1048576)
    u.need(u.c.same(complete['request'],u.pin(original_raw))and u.c.same(complete['source'],source_pin),'same actual original request/source')
    original=selection(u.parse(original_raw),source_pin)
    reservation=u.parse(io.capture(u.c.located(root,'WHOLE_RUN_RESERVATION.json',complete['reservation']),'original_whole_run_reservation',1048576))
    u.exact(reservation,('request','limits','origin_monotonic','deadline_monotonic','entire_reservation_retained_on_failure'))
    origin=u.c.finite(reservation['origin_monotonic']);end=u.c.finite(reservation['deadline_monotonic'])
    u.need(u.c.same(reservation['request'],u.pin(original_raw))and u.c.same(reservation['limits'],original['limits'])
        and end==origin+original['limits']['seconds']and reservation['entire_reservation_retained_on_failure']is True,'same original fixed campaign clock and resource reservation')
    evaluation_raw=io.capture(u.c.located(root,'SELECTED_EVALUATION.json',u.c.bare(original['evaluation'])),'frozen_evaluation_selection',1048576)
    evaluation=evaluation_spec(u.parse(evaluation_raw),original)
    d=library(source_root,io)
    prepared,projected,rows,private=intake(original,io,source_root,d)
    evaluation_preparation(evaluation,prepared)
    support=io.capture(u.c.located(root,'SUPPORT.json',complete['support']),'frozen_support')
    u.need(support==projected['support'],'same original complete participant support')
    people=sorted({r['patient_id']for r in rows.values()})
    u.need(type(complete['folds'])is list and len(complete['folds'])==23 and [f['person']for f in complete['folds']]==people,'all23 original completed contexts')
    queries,submissions={},{}
    for fold in complete['folds']:
        u.exact(fold,('person','context_id','query','submission','closure','launch','state_freeze','launch_request','state_request','close_request','actions'))
        person=fold['person'];u.need(fold['context_id']==original['contexts'][person]['context_id'],'same fresh original outer context')
        for field,name,destination in [('query','QUERY.json',queries),('submission','SUBMISSION.json',submissions)]:
            u.need(sum(len(b)for b in destination.values())+fold[field]['bytes']<=d.CAP,'aggregate frozen input cap before read')
            destination[person]=io.capture(u.c.located(root/person,name,fold[field]),'frozen_'+field)
        q=u.parse(queries[person]);state=q['fold_state_sha256']
        expected_requests={
            'launch_request':{'operation':'launch','held_person':person,'mode':original['mode'],
                'candidate_contract':original['candidate_contract'],'policy':original['policy'],
                'participant_exchange':original['contexts'][person]['participant_exchange'],
                'renderer_exchange':original['contexts'][person]['renderer_exchange'],'deployment':complete['deployment'],
                'controller_and_other_folds_excluded':True,'controller_origin_monotonic':origin,'controller_deadline_monotonic':end,
                'aggregate_limits':original['limits'],'terminate_on_controller_loss_or_deadline':True},
            'state_request':{'operation':'freeze_state','context_id':fold['context_id'],'candidate_contract':original['candidate_contract'],
                'fold_state_sha256':state,'held_person':person,'training':original['policy']['training'],'held_query_not_delivered':True},
            'close_request':{'operation':'close','context_id':fold['context_id'],'fold_state_sha256':state,
                'submission':fold['submission'],'no_reuse_of_context':True}}
        for sequence,(field,name)in enumerate([('launch_request','LAUNCH_REQUEST.json'),('state_request','STATE_REQUEST.json'),('close_request','CLOSE_REQUEST.json')],1):
            packet=u.parse(io.capture(u.c.located(root/person,name,fold[field]),'original_source_owned_custody_request',1048576))
            u.exact(packet,('schema','context_id','role','sequence','body'))
            u.need(packet['schema']=='neural010-service-request-v1'and packet['context_id']==fold['context_id']and packet['role']=='custody'
                and type(packet['sequence'])is int and packet['sequence']==sequence and u.c.same(packet['body'],expected_requests[field]),
                'exact source-owned prequery/request/retirement chronology')
        launch_raw=io.capture(u.c.located(root/person,'LAUNCH.json',fold['launch']),'original_external_launch',1048576)
        close_raw=io.capture(u.c.located(root/person,'CLOSURE.json',fold['closure']),'original_external_context_closure',1048576)
        state_raw=io.capture(u.c.located(root/person,'EXTERNAL_STATE_FREEZE.json',fold['state_freeze']),'original_external_state_freeze',1048576)
        def service(raw,sequence,expected):
            v=u.parse(raw);u.exact(v,('schema','context_id','role','sequence','request_sha256','body'))
            u.need(v['schema']=='neural010-service-response-v1'and v['context_id']==fold['context_id']and v['role']=='custody'
                and type(v['sequence'])is int and v['sequence']==sequence and v['request_sha256']==expected['sha256'],'exact retained independent custody response')
            return v['body']
        closure(service(launch_raw,1,fold['launch_request']),operation='launch',context=fold['context_id'],request_pin=fold['launch_request'])
        closure(service(close_raw,3,fold['close_request']),operation='close',context=fold['context_id'],request_pin=fold['close_request'],state=state,submission=fold['submission'])
        ack=service(state_raw,2,fold['state_request'])
        u.exact(ack,('schema','context_id','request_sha256','candidate_contract','fold_state_sha256','training_complete','held_query_not_delivered','state_immutable_for_query'))
        u.need(ack['schema']=='neural010-external-state-freeze-v1'and ack['context_id']==fold['context_id']
            and ack['request_sha256']==fold['state_request']['sha256']and u.c.same(ack['candidate_contract'],original['candidate_contract'])
            and ack['fold_state_sha256']==state and ack['training_complete']is True and ack['held_query_not_delivered']is True
            and ack['state_immutable_for_query']is True,'same original pre-query custody acknowledgement')
    frozen={name:io.capture(u.c.located(root,filename,complete[name]),'frozen_'+name)for name,filename in [('candidate','CANDIDATE.json'),('freeze','FREEZE.json')]}
    reserve_interface(io)
    u.need(frozen==d.freeze_candidate(support_bytes=support,queries=queries,submissions=submissions,mode=original['mode'],
        method_sha256=original['candidate_contract']['method_sha256']),'replayed full candidate freeze before references or assessment')
    provenance=reference_binding(io,evaluation,complete['evidence_class'],people,original['policy']['training'])
    references={arm:io.capture(desc,'independently_supplied_reference')for arm,desc in evaluation['references'].items()}
    pins={arm:u.c.bare(desc)for arm,desc in evaluation['references'].items()}
    # Never access the authority's assessment descriptor before the preserved
    # interface has admitted the whole freeze and every independent stream.
    def assessment_loader():
        desc=authority['assessment'];u.c.descriptor(desc,True)
        u.need(desc['path']==str(prepared['private_root']/'assessment.json')and u.c.same(u.c.bare(desc),prepared['assessment_pin']),
            'exact separately protected original assessment')
        return io.capture_assessment(desc)
    reserve_interface(io)
    result=d.grade_frozen(records_bytes=prepared['records_raw'],panel_bytes=projected['scientific_panel'],support_bytes=support,
        queries=queries,submissions=submissions,frozen=frozen,mode=original['mode'],method_sha256=original['candidate_contract']['method_sha256'],
        reference_bytes=references,operator_reference_pins=pins,original_panel_pin=evaluation['original_panel'],
        original_assessment_pin=evaluation['original_assessment'],assessment_loader=assessment_loader)
    result['campaign_route']={'campaign':u.c.bare(request['campaign']),'reference_provenance':provenance,
        'requested_comparator_interpretation':evaluation['interpretation'],'evidence_class':complete['evidence_class'],
        'qualification_created':False,'interpretation':'Signed comparator arithmetic. External hashes/receipts do not prove matching, superiority, clinical validity or participant isolation.'}
    out=io.directory(output_root)
    return io.create(out/'RESULT.json',u.encoded(result))

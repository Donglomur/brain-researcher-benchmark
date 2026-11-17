"""Independent complete replay of the locked declared-catalogue study.

No supplied score, generic backend, model execution or NumPy operation is accepted.
The parent scorer remains authoritative for every metric, weighting and uncertainty
calculation. Original predictions are admitted only through terminal-bound custody.
"""
from __future__ import annotations

#Direct task-local script entry. Only this pinned package directory is mounted;
#there is no import of private authoring history or dynamically named backend.
if __package__ in (None, ''):
    import importlib.util as _iu
    import pathlib as _pl
    import sys as _sys
    _sys.dont_write_bytecode=True
    _root=_pl.Path(__file__).resolve().parent
    _spec=_iu.spec_from_file_location('_n073_central_task',_root/'__init__.py',submodule_search_locations=[str(_root)])
    _module=_iu.module_from_spec(_spec);_sys.modules[_spec.name]=_module;_spec.loader.exec_module(_module)
    __package__=_spec.name
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from .evidence import (EvidenceError, EvidenceLimits, load_evidence, _closed,
                       _nonnegative, FINAL_STATUSES)
from .runtime import scoring
from .runtime.core.custody import canonical,digest,require_digest,VerifiedAuthority
from .runtime.core.plan import StudyPlan,CandidateContext,CONDITIONS,ARMS,REPETITIONS,FAMILIES,PEOPLE
from .runtime.core.resources import CandidateCaps
from .runtime.core.outcomes import classify_process,classify_aggregate
from .runtime.runner.candidate import context_inference_records
from .runtime.runner.policy import Policy
from .integrated_study import serialize_panel_key


CLAIM_LIMIT = ('Declared-catalogue label recovery under documented whole-support controls; no '
    'causal/native-neural-understanding/population-validity or SOTA inference.')
SCOPE={'records':9532,'people':13,'protocols':25,'cells':300,'contexts':234}


def require_reference_source(contract, code_closure_digest):
    """The accepted engine identity is Hraw(B), never a component source pin."""
    require_digest(code_closure_digest)
    if contract.get('reference_source_digest')!=code_closure_digest:
        raise EvidenceError('reference source is not exact complete B closure')


def _equal(left,right,message):
    if canonical(left)!=canonical(right):raise EvidenceError(message)


def _hash(row,key='receipt_digest'):
    if type(row) is not dict or row.get(key)!=digest({k:v for k,v in row.items() if k!=key}):
        raise EvidenceError('original '+key+' mismatch')


def _views(condition):return ('C',) if condition=='C_only' else ('N','C','NC')


def _full_contexts(contexts):
    contexts=tuple(contexts)
    if (len(contexts)!=234 or any(type(c) is not CandidateContext for c in contexts)
        or len({c.context_id for c in contexts})!=234
        or {(c.outer_person,c.condition,c.arm,c.repetition) for c in contexts}!=
           {(p,c,a,r) for p in PEOPLE for c in CONDITIONS for a in ARMS for r in REPETITIONS}):
        raise EvidenceError('complete exact234 distinct contexts required')
    return contexts


def assemble_full_results(*,records,constructions,contexts,candidate_results,reference_results,
                          best_families,priors,closure_digest,reference_receipt,score_authority):
    """Actual full production scorer assembly; no callback or supplied panels.

    Callers must already authenticate original source/candidate/reference lineage.
    This function additionally enforces complete rosters and authority bindings.
    Reference results are the exact stored {descriptor,raw_query_scores,
    query_probabilities} objects; no model body is needed for replay.
    """
    records=tuple(records);scoring.validate_full_scope(records);contexts=_full_contexts(contexts)
    ids={r.case_id for r in records};by_person={p:{r.case_id for r in records if r.person==p} for p in PEOPLE}
    require_digest(closure_digest)
    if type(score_authority) is not VerifiedAuthority:raise EvidenceError('verified score authority required')
    score_authority.require(role='score',domain='authentic',bindings={
        'records_digest':scoring.records_digest(records),'closure_digest':closure_digest,
        'construction_digest':digest(constructions)})
    if set(candidate_results)!={c.context_id for c in contexts}:raise EvidenceError('all234 originals required')
    expected={(p,c,v,f) for p in PEOPLE for c in CONDITIONS for v in _views(c) for f in FAMILIES}
    if set(reference_results)!=expected or len(expected)!=455:raise EvidenceError('all455 selected references required')
    if set(best_families)!={(p,c,v) for p in PEOPLE for c in CONDITIONS for v in _views(c)}:
        raise EvidenceError('all91 training-selected family aliases required')
    if set(priors)!={(p,c) for p in PEOPLE for c in CONDITIONS}:raise EvidenceError('all39 training priors required')
    for key,result in reference_results.items():
        _closed(result,('descriptor','raw_query_scores','query_probabilities'),'reference result')
        if set(result['query_probabilities'])!=by_person[key[0]]:raise EvidenceError('whole held-person reference required')
    for context in contexts:
        part=candidate_results[context.context_id]
        if part.get('context')!=context.private_dict() or set(part['submission']['probabilities'])!=by_person[context.outer_person]:
            raise EvidenceError('candidate private scope/context differs')
    def panel(values):
        if set(values)!=ids:raise EvidenceError('full9532 panel required, including failures')
        return scoring.score_panel(records,values,authority=score_authority,
            closure_digest=closure_digest,construction_by_case=constructions)
    candidate={};reference={};summaries={};comparisons={}
    for condition in CONDITIONS:
        for arm in ARMS:
            panels=[]
            for repetition in REPETITIONS:
                values={}
                for c in contexts:
                    if (c.condition,c.arm,c.repetition)==(condition,arm,repetition):
                        part=candidate_results[c.context_id]['submission']['probabilities']
                        if set(values)&set(part):raise EvidenceError('overlapping held-person predictions')
                        values.update(part)
                p=panel(values);candidate[(condition,arm,repetition)]=p;panels.append(p)
            summaries[(condition,arm)]=scoring.aggregate_repetitions(panels)
        comparisons[(condition,'I_minus_F')]=scoring.paired_comparison(
            [candidate[(condition,'F',r)] for r in REPETITIONS],
            [candidate[(condition,'I',r)] for r in REPETITIONS])
        for view in _views(condition):
            for family in FAMILIES+('training_selected_family',):
                values={}
                for person in PEOPLE:
                    actual=family if family!='training_selected_family' else best_families[(person,condition,view)]['family']
                    values.update(reference_results[(person,condition,view,actual)]['query_probabilities'])
                rp=panel(values);reference[(condition,view,family)]=rp
                for arm in ARMS:
                    comparisons[(condition,arm,view,family)]=scoring.compare_reference(
                        [candidate[(condition,arm,r)] for r in REPETITIONS],rp)
        for baseline in ('uniform','weighted_prior'):
            values={}
            for person in PEOPLE:
                vector=[1/25]*25 if baseline=='uniform' else priors[(person,condition)]['probabilities']
                vector=scoring.probability_vector(vector)
                values.update({rid:vector for rid in by_person[person]})
            reference[(condition,baseline)]=panel(values)
    for arm in ARMS:
        for control in ('spatial_scrambled','C_only'):
            base=summaries[('original',arm)];other=summaries[(control,arm)]
            acc={p:base['people'][p]['accuracy']-other['people'][p]['accuracy'] for p in PEOPLE}
            bri={p:other['people'][p]['brier_with_failure_penalty']-base['people'][p]['brier_with_failure_penalty'] for p in PEOPLE}
            comparisons[(arm,'original_minus_'+control)]={
                'accuracy':scoring.person_uncertainty(acc),'brier':scoring.person_uncertainty(bri),
                'interpretation':'conditional declared-label comparison; C is nuisance-enriched and supports may fingerprint acquisition'}
    if tuple(map(len,(candidate,reference,summaries,comparisons)))!=(18,48,6,91):
        raise EvidenceError('complete18/48/6/91 locked result required')
    flatten=lambda d:{serialize_panel_key(k):v for k,v in d.items()}
    return {'schema':'n073_full_declared_label_study_v1','scope':dict(SCOPE),
        'closure_digest':closure_digest,'reference_receipt':reference_receipt,
        'candidate_panels':flatten(candidate),'reference_panels':flatten(reference),
        'three_repetition_summaries':flatten(summaries),'paired_comparisons':flatten(comparisons),
        'claim_limit':CLAIM_LIMIT}


def validate_phase_events(context,result,policy,original_processes,snapshots):
    events=result['phase_events']
    if type(events) is not list or not 4<=len(events)<=7:raise EvidenceError('complete bounded phase history required')
    state='allocated';previous='0'*64;program=None;submitted=False
    prediction=digest(result['submission']);failure=result['candidate_failure']
    for i,e in enumerate(events):
        _closed(e,('context','index','state','action','binding','previous','event_digest'),'phase event')
        if e['context']!=context.context_id or type(e['index']) is not int or e['index']!=i or e['previous']!=previous:
            raise EvidenceError('phase context/chronology mismatch')
        _hash(e,'event_digest');require_digest(e['binding']);action=e['action'];expected=None
        if action=='prepare' and state=='allocated':state='prepared'
        elif action=='authoring' and state=='prepared':state='authoring';expected=policy.binding_digest
        elif action=='seal' and state=='authoring' and context.arm=='F':
            if len(snapshots)!=1:raise EvidenceError('actual single F freeze required')
            state='sealed';program=digest(snapshots[0]['snapshot']);expected=program
            snap=snapshots[0]['snapshot'];binding=snapshots[0]['binding']
            if (snap.get('schema')!='n073-frozen-program-snapshot-v1' or snap.get('context_digest')!=digest(context.context_id)
                or snap.get('program_manifest_digest')!=digest(snap.get('members'))
                or binding.get('snapshot_digest')!=program or binding.get('context_id')!=context.context_id
                or any(binding.get(k)!=snap.get(k) for k in ('program_manifest_digest','entry_relative_path','entry_digest','runtime_digest'))):
                raise EvidenceError('actual F snapshot binding differs')
        elif action=='query' and ((context.arm=='F' and state=='sealed') or (context.arm=='I' and state=='authoring')):
            state='query_open'
        elif action=='submit' and state=='query_open' and failure is None:
            state='submitted';submitted=True;expected=prediction
        elif action=='candidate_failure' and state in ('prepared','authoring','sealed','query_open') and type(failure) is str and failure:
            expected=digest({'previous':state,'prediction':prediction,'reason':failure,'original_outcome':digest(original_processes)})
            state='submitted';submitted=True
        elif action=='close' and state=='submitted':state='closed';expected=result['resources']['receipt_digest']
        else:raise EvidenceError('forbidden or repeated phase transition')
        if e['state']!=state or (expected is not None and e['binding']!=expected):
            raise EvidenceError('phase binding/state differs from actual original')
        previous=e['event_digest']
    if state!='closed' or not submitted or (context.arm=='I' and snapshots):raise EvidenceError('complete arm-specific phase closure required')
    actual=digest({'context':context.binding_digest,'program':program,'prediction':prediction,'failure':failure,'events':events})
    if actual!=result['closure_digest']:raise EvidenceError('candidate closure differs from exact phase history')
    return actual


def validate_usage(usage,expected_evidence):
    keys={'uncached_input_tokens','cached_input_tokens','visible_output_tokens','reasoning_output_tokens',
          'total_input_tokens','total_output_tokens','usage_evidence_digest','provider_usage_digest','provider_usage_record'}
    _closed(usage,keys,'actual usage')
    for key in keys-{'usage_evidence_digest','provider_usage_digest','provider_usage_record'}:_nonnegative(usage[key])
    if (usage['usage_evidence_digest']!=expected_evidence or type(usage['provider_usage_record']) is not dict
        or not usage['provider_usage_record'] or usage['provider_usage_digest']!=digest(usage['provider_usage_record'])
        or usage['total_input_tokens']!=usage['uncached_input_tokens']+usage['cached_input_tokens']
        or usage['total_output_tokens']!=usage['visible_output_tokens']+usage['reasoning_output_tokens']):
        raise EvidenceError('original cached/reasoning usage identity or totals mismatch')
    return usage


def join_generation_usage(*,context,policy,contract,generation_records,journal_results,
                          usage_projection,transport,resources,extraction_source_digest):
    """Pure original usage join; caller must first authenticate native custody.

    This function never issues authority, classifies a native run or computes a
    scientific score. It exposes the exact metadata operation to tiny controls.
    """
    if any(r['failed'] for r in generation_records):raise EvidenceError('provider failure remains infrastructure-invalid')
    from .transport_evidence import validate_usage_projection
    projection=validate_usage_projection(usage_projection,context_id=context.context_id,
        provider_admission_digest=contract['provider_admission_digest'],
        transport_receipt_digest=transport['receipt_digest'],generation_records=generation_records,
        extraction_source_digest=extraction_source_digest)
    if projection['source_receipts_event_digest']!=transport['events_digest']:
        raise EvidenceError('usage projection receipt chain differs from original transport')
    tail=projection['unmetered_terminal_tokenize_tail']
    if tail is not None:
        failures=transport.get('original_failures')
        if (transport.get('schema')!='n073_model_transport_exhaustion_close_v2' or not transport.get('exhaustion_evidence')
            or type(failures) is not list or not failures
            or tail['original_failure_digest']!=digest(failures[-1])
            or tail['original_partial_protocol_kind']!=transport.get('partial_protocol_kind')):
            raise EvidenceError('terminal tokenize tail differs from actual exhausted transport original')
    extracted={r['request_id']:r for r in projection['generation_records']}
    by_request={r['request_id']:r for r in generation_records};usage_rows={}
    for m in journal_results:
        _closed(m,('response','failed','usage','original_result_digest','event_digest','inference_record'),'original model result')
        r=m['inference_record'];rid=r['request_id']
        if rid not in by_request or rid in usage_rows or r!=by_request[rid] or m['failed'] is not False:
            raise EvidenceError('model originals missing/duplicate/failed or inference differs')
        for k in ('original_result_digest','event_digest'):require_digest(m[k])
        u=extracted.get(rid)
        if u is None or u['inference_record']!=r or u['original_result_digest']!=m['original_result_digest']:
            raise EvidenceError('journal result differs from actual original transport frame')
        _equal(u['usage'],m['usage'],'journal usage differs from original captured response')
        usage_rows[rid]=validate_usage(m['usage'],contract['usage_evidence_digest'])
    #The only allowed missing journal result is the final settled overflow
    #response, preserved in the exact original transport capture and generation
    #list before ResourceLedger.complete_model raised. Never infer zero usage.
    missing=set(by_request)-set(usage_rows)
    if missing:
        if (len(missing)!=1 or list(by_request)[-1] not in missing or tail is not None
            or transport.get('schema')!='n073_model_transport_exhaustion_close_v2'
            or not transport.get('exhaustion_evidence') or not transport.get('original_failures')
            or resources.get('violation') is None):
            raise EvidenceError('unexplained original model result journal omission')
        rid=next(iter(missing));u=extracted[rid]
        if u['inference_record']!=by_request[rid]:raise EvidenceError('overflow generation identity differs')
        usage_rows[rid]=validate_usage(u['usage'],contract['usage_evidence_digest'])
    if set(usage_rows)!=set(by_request):raise EvidenceError('complete settled original usage required')
    remaining_output=CandidateCaps().output_tokens
    for rid in by_request:
        u=extracted[rid]
        if (type(u['max_output_tokens']) is not int or u['max_output_tokens']!=min(policy.max_response_tokens,remaining_output) or u['max_output_tokens']<=0
            or type(u['reserved_input_tokens']) is not int or not 0<=u['reserved_input_tokens']<=usage_rows[rid]['total_input_tokens']):
            raise EvidenceError('original provider token reservation differs from fixed candidate policy')
        remaining_output-=usage_rows[rid]['total_output_tokens']
    return usage_rows


def validate_submission_process_link(result,processes):
    """Join actual parser provenance; _empty is the sole legitimate absence."""
    submission=result['submission'];identity=submission.get('original_process_outcome_digest')
    if 'original_process_outcome_digest' not in submission:
        if (not result['candidate_failure'] or any(p is not None for p in submission['probabilities'].values())):
            raise EvidenceError('parsed submission lacks original final query-process identity')
        return
    require_digest(identity)
    query=[p for p in processes if p.get('phase')=='query']
    if not query or identity!=query[-1].get('receipt_digest'):
        raise EvidenceError('parsed submission differs from last actual query process')


def validate_query_barrier_link(context,phase_events,barriers):
    """I query occurrence and its original native barrier must agree exactly."""
    queries=sum(e.get('action')=='query' for e in phase_events)
    if context.arm=='I' and (queries not in (0,1) or len(barriers)!=queries):
        raise EvidenceError('I query phase lacks or duplicates its actual original barrier')
    if context.arm=='F' and barriers:raise EvidenceError('interactive barrier in F context')


def validate_context_original(context,result,*,plan,policy,contract,events,seen_draw_ids,usage_projection,extraction_source_digest):
    _closed(result,('schema','context','submission','resources','phase_events','closure_digest',
                   'candidate_failure','feedback_returned_to_candidate','inference_binding','generation_inference_records'),'candidate original')
    if result['schema']!='n073_candidate_context_original_v1' or result['context']!=context.private_dict() or result['feedback_returned_to_candidate'] is not False:
        raise EvidenceError('actual private context/no-feedback identity required')
    _equal(result['inference_binding'],policy.inference_policy.binding_for(context.repetition),'fixed inference binding differs')
    actual,seen=context_inference_records(context,policy,result['generation_inference_records'],seen_draw_ids=seen_draw_ids)
    if any(r['failed'] for r in actual):raise EvidenceError('provider failure is infrastructure-invalid, including settled exhaustion')
    query=set(plan.fold(context.outer_person).query_ids);submission=result['submission']
    if (set(submission['probabilities'])!=query or set(submission['failures'])!={k for k,v in submission['probabilities'].items() if v is None}
        or submission['mapping_role']!='trusted_private_only' or submission['private_mapping_digest']!=contract['private_mapping_digest']
        or submission['expected_cases']!=len(query) or submission['valid_cases']!=sum(v is not None for v in submission['probabilities'].values())):
        raise EvidenceError('complete original private query mapping/parser support differs')
    require_digest(submission['parser_receipt_digest'])
    from .runtime.scoring.core import accepted_probability_vector
    for value in submission['probabilities'].values():
        if value is not None:accepted_probability_vector(value)
    process=[];aggregates=[];brokers=[];model=[];snapshots=[];failures=[];interactive_barriers=[]
    query_open=False;broker_closed=False;guard_closed=False
    for e in events:
        kind=e['kind'];p=e['payload']
        if guard_closed:raise EvidenceError('context originals after actual aggregate close')
        if kind=='candidate_process_original':
            outcome=classify_process(p['original_receipt'],context_id=context.context_id).require_scoreable()
            _equal(p,outcome.to_dict(),'changed original process classification')
            raw=outcome.original_receipt
            if raw.get('phase')!=('query' if query_open else 'prequery'):
                raise EvidenceError('actual process/query barrier chronology differs')
            process.append(raw)
        elif kind=='guard_original_close':
            outcome=classify_aggregate(p['original_receipt'],context_id=context.context_id).require_scoreable()
            if not broker_closed:raise EvidenceError('aggregate closed before original broker closure')
            _equal(p,outcome.to_dict(),'changed aggregate classification');aggregates.append(outcome.original_receipt);guard_closed=True
        elif kind=='broker_original_close':
            brokers.append(p);broker_closed=True
        elif kind=='candidate_model_original':
            if broker_closed or (context.arm=='F' and query_open):raise EvidenceError('model call after actual F/transport closure')
            model.append(p)
        elif kind=='f_actual_snapshot':
            if context.arm!='F' or query_open or not broker_closed:raise EvidenceError('actual F freeze chronology differs')
            snapshots.append(p);query_open=True
        elif kind=='i_prequery_barrier':
            _hash(p)
            if (context.arm!='I' or query_open or broker_closed or p.get('populated')!=0
                or p.get('phase_outcomes_digest')!=digest(process)):
                raise EvidenceError('actual I query barrier differs')
            interactive_barriers.append(p);query_open=True
        elif kind=='candidate_failure':failures.append(p)
    if len(aggregates)!=1 or len(brokers)!=1:raise EvidenceError('one actual aggregate/broker close required')
    if len({x.get('request_id') for x in process})!=len(process):raise EvidenceError('duplicate original process request')
    aggregate=aggregates[0];broker=brokers[0];transport=broker['transport_receipt']
    _equal(aggregate['broker_closure'],broker,'broker and aggregate custody differ')
    if aggregate['candidate_original_outcomes_digest']!=digest(process):raise EvidenceError('original process list incomplete')
    if broker['provider_admission_digest']!=contract['provider_admission_digest']:
        raise EvidenceError('provider closure differs from independently admitted context')
    _equal(transport['generation_inference_records'],actual,'transport and candidate generation originals differ')
    _equal(transport['inference_binding'],result['inference_binding'],'transport inference differs')
    usage_rows=join_generation_usage(context=context,policy=policy,contract=contract,generation_records=actual,
        journal_results=model,usage_projection=usage_projection,transport=transport,resources=result['resources'],
        extraction_source_digest=extraction_source_digest)
    resources=result['resources'];_hash(resources)
    caps=CandidateCaps()
    if (resources.get('schema')!='n073_resource_receipt_v1' or resources.get('context_id')!=context.context_id
        or resources.get('caps_digest')!=caps.binding_digest or resources.get('final_meter_digest')!=aggregate['receipt_digest']
        or resources.get('model_calls')!=len(actual) or resources.get('tool_calls')!=len(process)
        or resources.get('input_tokens')!=sum(u['total_input_tokens'] for u in usage_rows.values())
        or resources.get('output_tokens')!=sum(u['total_output_tokens'] for u in usage_rows.values())):
        raise EvidenceError('original resource token/count/cap/final-meter join differs')
    require_digest(resources['events_digest'])
    final=aggregate['final_observation']
    if (resources['cpu_ns']!=final['total_context_cpu_ns'] or resources['peak_private_rss']<final['memory_peak_bytes']
        or resources['peak_writable']<final['allocated_scratch_bytes']):
        raise EvidenceError('final native cumulative counters differ')
    for name in ('model_calls','input_tokens','output_tokens','tool_calls','wall_ns','cpu_ns','peak_private_rss','peak_writable'):
        _nonnegative(resources[name])
    if resources['violation'] is not None:
        from .runtime.core.outcomes import valid_violation
        if not valid_violation(resources['violation']):raise EvidenceError('unqualified original resource violation')
    if resources['violation'] is not None and not result['candidate_failure']:
        raise EvidenceError('qualified resource violation must retain candidate failure')
    if failures and (len(failures)!=1 or failures[0]['reason']!=result['candidate_failure'] or failures[0]['full_expected_query_cases']!=len(query)):
        raise EvidenceError('original candidate failure differs')
    validate_submission_process_link(result,process)
    validate_query_barrier_link(context,result['phase_events'],interactive_barriers)
    validate_phase_events(context,result,policy,process,snapshots)
    return seen,{'model_calls':resources['model_calls'],'input_tokens':resources['input_tokens'],
        'output_tokens':resources['output_tokens'],'tool_calls':resources['tool_calls'],
        'rawledger_event_replay_available':False,'ledger_events_digest':resources['events_digest']}


def expected_reference_counts():
    S=13;N=9532
    return {'inner_base_fit_bundles':S*(S-1)*353,'outer_base_fit_bundles':S*35,'calibrators':S*35,
        'PCA_fits':S*S*8,'N_scaler_fits':S*S*8,'C_scaler_fits':S*S*5,'PCA_score_scaler_fits':S*S*16,
        'RBF_Gram_banks':S*S*57,'linear_Gram_banks':S*S*11,'prior_aggregations':S*3,
        'raw_prediction_vectors':((S-1)*353+35)*N,
        'base_training_record_exposures':((S-1)*(S-2)*353+(S-1)*35)*N,
        'temperature_bank_passes':S*35*17,'calibration_training_record_exposures':(S-1)*35*N,
        'temperature_loss_row_evaluations':17*(S-1)*35*N}


def validate_numeric_evidence(family,evidence):
    """Validate original certificate bounds; do not claim to rerun a fit."""
    if family in ('linear_ovr_svm','rbf_ovr_svm'):
        if type(evidence) is not list or len(evidence)!=25:raise EvidenceError('all25 SVM certificates required')
        for x in evidence:
            _closed(x,('primal','dual','absolute_gap','relative_gap','equality_residual','box_violation','iterations','converged'),'SVM certificate')
            if type(x['iterations']) is not int or not 0<=x['iterations']<=100000 or x['converged'] is not True:
                raise EvidenceError('uncertified SVM convergence')
            for key in ('primal','dual','absolute_gap','relative_gap','equality_residual','box_violation'):
                if type(x[key]) not in (float,int) or not math.isfinite(x[key]):raise EvidenceError('nonfinite SVM certificate')
            scale=max(abs(x['primal']),abs(x['dual']),1e-12);gap=max(x['primal']-x['dual'],0.)
            if (x['primal']<0 or x['absolute_gap']<0 or not 0<=x['relative_gap']<=1e-5
                or not 0<=x['equality_residual']<=1e-10 or not 0<=x['box_violation']<=1e-12
                or x['dual']>x['primal']+1e-10*scale or abs(x['absolute_gap']-gap)>1e-12*scale
                or abs(x['relative_gap']-gap/scale)>1e-12):raise EvidenceError('inconsistent original SVM certificate')
    elif family=='extra_trees':
        if type(evidence) is not dict or evidence.get('tree_count')!=256 or type(evidence.get('node_count')) is not int or evidence['node_count']<256:
            raise EvidenceError('all256 concrete fitted trees required')
    elif type(evidence) is not dict or not evidence:
        raise EvidenceError('original ridge/centroid numerical metadata required')


def _job(plan,source,person,condition,view,family,cfg,fit_ids,validation_person):
    outer=plan._opaque(['reference',person,condition])
    rows=tuple(plan._opaque(['reference-row',person,condition,rid]) for rid in fit_ids)
    subset=plan._opaque(['subset',person,condition,view,rows])
    kind='outer' if validation_person is None else 'inner'
    role=plan._opaque(['outer-fit',person,condition,view] if kind=='outer' else ['inner-fit',person,condition,view,validation_person])
    context={'opaque_reference_context_token':outer,'condition':condition,'view':view,
             'configuration_index':cfg['index'],'fit_role':role}
    return digest([source,context,family,cfg,subset,kind]),subset,rows,context,kind


def _join_job(bundle,plan,source,person,condition,view,family,cfg,fit_ids,validation_person,state,consumed):
    key,subset,rows,context,kind=_job(plan,source,person,condition,view,family,cfg,fit_ids,validation_person)
    if key in consumed or key not in bundle.reference_jobs:raise EvidenceError('missing/reused exact scientific fit job')
    j=bundle.reference_jobs[key];p=j['parents'];counts=j['counts']
    if (j.get('status')!='complete' or j.get('result_digest')!=state or p.get('configuration')!=cfg
        or p.get('fit_context')!=context or p.get('source')!=source or p.get('kind')!=kind
        or p.get('subset_token')!=subset or p.get('training_rows')!=digest(rows)
        or counts.get('training_records')!=len(fit_ids)):
        raise EvidenceError('fit/source/fold/config/state lineage mismatch')
    expected_view=digest(['view-bank',context['opaque_reference_context_token'],condition,view,subset,cfg['representation'],source])
    if p['view_bank']!=expected_view:raise EvidenceError('original fit transform dependency differs')
    evidence=counts['numerical_evidence'];validate_numeric_evidence(family,evidence)
    if family in ('ridge','centroid'):
        _closed(evidence,('dependency_key','fit_record_ids','weight_digest','work','certificate'),'numeric fit metadata')
        if evidence['dependency_key']!=digest(['estimator',key]) or tuple(evidence['fit_record_ids'])!=rows or evidence['work'].get('fit_rows')!=len(fit_ids):
            raise EvidenceError('numerical fit metadata differs from exact training subset')
        require_digest(evidence['weight_digest'])
        cert=evidence['certificate']
        if family=='ridge':
            residual=cert.get('normalized_optimality_residual');objective=cert.get('objective')
            if (type(residual) not in (int,float) or not 0<=residual<=1e-8 or type(objective) not in (int,float)
                or not math.isfinite(objective) or objective<0 or cert.get('lambda')!=cfg['lambda']
                or evidence['work'].get('output_coordinates')!=25 or counts.get('ridge_shared_solves')!=1):
                raise EvidenceError('original ridge certificate/work differs')
        elif cert!={'all_classes_present':True,'weighted_class_mean':True} or counts.get('class_template_aggregations')!=25:
            raise EvidenceError('all25 weighted centroid means required')
    elif family=='extra_trees':
        if evidence.get('deterministic_context')!=context or counts.get('trees')!=256:
            raise EvidenceError('deterministic256-tree context/work differs')
    elif counts.get('binary_SVM_optimizations')!=25:raise EvidenceError('all25 certified binary optimizations required')
    consumed.add(key);return subset,rows


def replay_references(bundle,plan,records,contract,receipt):
    """Read every original OOF bank and replay selection/calibration; no fitting."""
    source=contract['reference_source_digest'];require_digest(source)
    if (receipt.get('domain')!='authentic' or receipt.get('plan_digest')!=plan.binding_digest
        or receipt.get('reference_models')!=455 or receipt.get('additional_linear_Gram_banks')!=1859
        or receipt.get('no_candidate_or_scoring_execution_inferred') is not True):
        raise EvidenceError('complete reference receipt identity differs')
    _hash(receipt,'completion_digest');work=receipt['work']
    for name,n in expected_reference_counts().items():
        if type(work['counts'].get(name)) is not int or work['counts'][name]!=n:
            raise EvidenceError('complete reference count mismatch: '+name)
    if (work.get('jobs')!=55523 or work.get('job_statuses')!={'reserved':0,'complete':55523,'failed':0}
        or len(bundle.reference_jobs)!=55523 or work.get('event_digest')!=bundle.reference_events_digest):
        raise EvidenceError('complete original55523 fit job/event closure required')
    byid={r.case_id:r for r in records};grid=scoring.grid();results={};best={};priors={};consumed=set();oof_used=set()
    declared=set(bundle.manifest['roles']['reference_oof']);outer_declared=bundle.manifest['roles']['outer_references']
    for person in PEOPLE:
        fold=plan.fold(person);training=tuple(byid[i] for i in fold.training_ids)
        for condition in CONDITIONS:
            priors[(person,condition)]=scoring.weighted_prior(training)
            for view in _views(condition):
                bundle.meter.check();blocks=[b for b in grid if b['condition']==condition and b['view']==view]
                jobs=[]
                for val,fit_people in fold.inner_people():
                    fit_ids=tuple(r.case_id for r in plan.records_for(fit_people))
                    for b in blocks:
                        for cfg in b['configurations']:
                            _,subset,_,_,_=_job(plan,source,person,condition,view,b['family'],cfg,fit_ids,val)
                            key='oof_'+digest([subset,b['family'],cfg])
                            if key not in declared or key in oof_used:raise EvidenceError('original full OOF support differs')
                            jobs.append((val,fit_ids,b['family'],cfg,key))
                reservation=64*sum(bundle.manifest['artifacts'][j[-1]]['bytes'] for j in jobs)+4096*len(jobs)
                with bundle.meter.workspace(reservation):
                    banks={b['family']:{cfg['index']:{} for cfg in b['configurations']} for b in blocks}
                    for val,fit_ids,family,cfg,key in jobs:
                        with bundle.artifact(key) as value:
                            _closed(value,('outer_person','condition','view','family','configuration','validation_person','fit_state_digest','rows'),'original OOF')
                            if (value['outer_person'],value['condition'],value['view'],value['family'],value['validation_person'])!=(person,condition,view,family,val) or value['configuration']!=cfg:
                                raise EvidenceError('original OOF fold/config identity differs')
                            validation={r.case_id for r in plan.records_for((val,))}
                            if set(value['rows'])!=validation:raise EvidenceError('complete whole-person OOF validation required')
                            _join_job(bundle,plan,source,person,condition,view,family,cfg,fit_ids,val,value['fit_state_digest'],consumed)
                            target=banks[family][cfg['index']]
                            if set(target)&validation:raise EvidenceError('duplicate OOF validation rows')
                            target.update(value['rows']);oof_used.add(key)
                    selections={b['family']:scoring.select_configuration(training,banks[b['family']],
                        expected_indices=[c['index'] for c in b['configurations']]) for b in blocks}
                    best[(person,condition,view)]=scoring.select_family(selections)
                    for b in blocks:
                        family=b['family'];selection=selections[family];cfg=b['configurations'][selection['index']]
                        calibration=scoring.calibrate_temperature(training,banks[family][cfg['index']])
                        tkey=(person,condition,view,family);role='|'.join(tkey);key='outer_'+digest(list(tkey))
                        if outer_declared.get(role)!=key:raise EvidenceError('outer reference role identity differs')
                        artifact=bundle.manifest['artifacts'][key];bundle.meter.retain(64*artifact['bytes']+4096)
                        with bundle.artifact(key) as value:
                            _closed(value,('descriptor','raw_query_scores','query_probabilities'),'outer reference')
                            desc=value['descriptor']
                            _closed(desc,('outer_person','condition','view','family','configuration','calibration','selection',
                                'training_rows_digest','fitted_state_digest','raw_query_digest','probability_digest','numerical_certificate'),'outer descriptor')
                            if tuple(desc[k] for k in ('outer_person','condition','view','family'))!=tkey or desc['configuration']!=cfg:
                                raise EvidenceError('outer reference scientific identity differs')
                            _,rows=_join_job(bundle,plan,source,person,condition,view,family,cfg,fold.training_ids,None,
                                            desc['fitted_state_digest'],consumed)
                            if desc['training_rows_digest']!=digest(rows):raise EvidenceError('outer training identity differs')
                            _equal(desc['selection'],selection,'training-only configuration selection differs')
                            _equal(desc['calibration'],calibration,'training-only OOF temperature differs')
                            if (set(value['raw_query_scores'])!=set(fold.query_ids)
                                or desc['raw_query_digest']!=digest(value['raw_query_scores'])
                                or desc['probability_digest']!=digest(value['query_probabilities'])):
                                raise EvidenceError('original complete query predictions differ')
                            applied=scoring.apply_temperature(value['raw_query_scores'],calibration)
                            _equal(applied['probabilities'],value['query_probabilities'],'original fixed calibration probabilities differ')
                            _equal(applied['numerical_ordering_certificate'],desc['numerical_certificate'],'query numerical ordering differs')
                            results[tkey]=value
    if consumed!=set(bundle.reference_jobs) or oof_used!=declared or len(results)!=455:
        raise EvidenceError('original full reference graph not consumed exactly')
    if receipt['reference_result_descriptors_digest']!=digest([results[k]['descriptor'] for k in sorted(results)]):
        raise EvidenceError('reference descriptors differ from actual completion')
    return results,best,priors


def _trusted_inputs(plan,catalogue,policy,identities):
    from .runtime import admission
    if type(plan) is not StudyPlan or plan.domain!='authentic' or type(policy) is not Policy or type(catalogue) is not admission.Catalogue:
        raise EvidenceError('independently admitted exact authentic plan/catalogue/policy required')
    catalogue.require_valid()
    if catalogue.domain!=admission.SOURCE_DOMAIN:raise EvidenceError('authentic frozen source catalogue required')
    normalize={'dir-ap':'AP','dir-pa':'PA','ffx':'FFX','AP':'AP','PA':'PA','FFX':'FFX'}
    rebuilt=[{'case_id':r.record_id,'person':r.person,'label':r.label,'construction':normalize[r.construction]} for r in catalogue.records]
    if rebuilt!=[r.to_dict() for r in plan.records]:raise EvidenceError('plan differs from independently admitted private catalogue')
    if (identities['plan_digest']!=plan.binding_digest or identities['assessment_digest']!=plan.assessment_digest
        or identities['runtime_policy_digest']!=policy.binding_digest):raise EvidenceError('selected original plan/assessment/policy differs')
    records=tuple(scoring.Record(r.case_id,r.person,r.label) for r in plan.records)
    scoring.validate_full_scope(records)
    return records,{r.case_id:r.construction for r in plan.records}


def grade_instance(*,run_root,manifest_pin,terminal,trusted_plan,catalogue,policy,score_authority,limits):
    """Production-only complete grade. An exception is infrastructure-invalid."""
    with load_evidence(run_root,manifest_pin,terminal=terminal,limits=limits) as bundle:
        m=bundle.manifest;records,constructions=_trusted_inputs(trusted_plan,catalogue,policy,m['identities'])
        contexts=_full_contexts(trusted_plan.contexts());candidate={};seen=set();usage={}
        with bundle.artifact(m['roles']['run_contract']) as contract:
            _closed(contract,('schema','domain','identities','reference_source_digest','context_contracts','rawledger_event_replay_available','usage_extraction_source_digest','attempt_binding'),'run contract')
            if contract['schema']!='n073_run_contract_v2' or contract['domain']!='authentic' or contract['identities']!=m['identities'] or contract['rawledger_event_replay_available'] is not False:
                raise EvidenceError('actual selected run contract differs')
            if contract['attempt_binding']!=bundle.terminal_claims['attempt_binding']:
                raise EvidenceError('original attempt identity differs from independently verified terminal')
            require_reference_source(contract,m['identities']['code_closure_digest'])
            if set(contract['context_contracts'])!={c.context_id for c in contexts}:raise EvidenceError('complete context contracts required')
            for c in contexts:
                ccontract=contract['context_contracts'][c.context_id]
                _closed(ccontract,('provider_admission_digest','usage_evidence_digest','private_mapping_digest'),'context contract')
                for value in ccontract.values():require_digest(value)
                key=m['roles']['candidate_contexts'].get(c.context_id)
                if key!='candidate_'+c.context_id:raise EvidenceError('candidate artifact identity differs')
                artifact=m['artifacts'][key];bundle.meter.retain(64*artifact['bytes']+4096)
                with bundle.artifact(key) as result:
                    usagekey=m['roles']['provider_usage'].get(c.context_id)
                    if usagekey!='usage_'+c.context_id:raise EvidenceError('exact usage artifact identity required')
                    with bundle.artifact(usagekey) as projection:
                        seen,usage[c.context_id]=validate_context_original(c,result,plan=trusted_plan,policy=policy,
                            contract=ccontract,events=bundle.context_events[c.context_id],seen_draw_ids=seen,
                            usage_projection=projection,extraction_source_digest=contract['usage_extraction_source_digest'])
                    candidate[c.context_id]=result
            closure=trusted_plan.assert_complete_closure({k:v['closure_digest'] for k,v in candidate.items()})
            with bundle.artifact(m['roles']['full_locked_closure']) as locked:
                _closed(locked,('plan_digest','closure_digest','reference_receipt','contexts'),'locked closure')
                if (locked['plan_digest']!=trusted_plan.binding_digest or locked['closure_digest']!=closure
                    or locked['contexts']!={k:v['closure_digest'] for k,v in candidate.items()}):
                    raise EvidenceError('actual all234 locked closure differs')
                receipt=locked['reference_receipt']
                references,best,priors=replay_references(bundle,trusted_plan,records,contract,receipt)
                if type(score_authority) is not VerifiedAuthority:raise EvidenceError('independently verified original score capability required')
                score_authority.require(role='score',domain='authentic',bindings={
                    'records_digest':scoring.records_digest(records),'closure_digest':closure,'construction_digest':digest(constructions)})
                with bundle.artifact(m['roles']['full_score_capability'],text=True) as envelope:
                    from .evidence import parse_json
                    signed=parse_json(envelope,limits=limits)
                    _closed(signed,('claims','mac'),'original score capability envelope')
                    if digest(signed['claims'])!=score_authority.authority_digest:
                        raise EvidenceError('admitted score capability differs from original stored envelope')
                #All outputs plus scorer temporary rows and 10,000-draw arrays are
                #reserved before the unchanged production scorer is invoked.
                finalkey=m['roles']['full_study_results'];finalsize=m['artifacts'][finalkey]['bytes']
                with bundle.meter.workspace(128*finalsize+64*9532*25*8+16*1024*1024):
                    bundle.meter.check()
                    replay=assemble_full_results(records=records,constructions=constructions,contexts=contexts,
                        candidate_results=candidate,reference_results=references,best_families=best,priors=priors,
                        closure_digest=closure,reference_receipt=receipt,score_authority=score_authority)
                    bundle.meter.check()
                    with bundle.artifact(finalkey) as captured:
                        _equal(replay,captured,'recomputed complete original study differs; no replacement score')
                    execution_failures=sum(bool(x['candidate_failure']) for x in candidate.values())
                    prediction_failures=sum(any(v is None for v in x['submission']['probabilities'].values()) for x in candidate.values())
                    failure_count=sum(bool(x['candidate_failure']) or any(v is None for v in x['submission']['probabilities'].values()) for x in candidate.values())
                    expected='complete_with_candidate_failures' if failure_count else 'complete'
                    if m['status']!=expected:raise EvidenceError('terminal candidate failure status differs')
                    projection=public_projection(replay)
                    return {'schema':'n073_complete_grade_v1','status':m['status'],'qualified':True,
                        'run_digest':digest(m['run_id']),'manifest_sha256':manifest_pin['sha256'],
                        'scope':dict(SCOPE),'result_digest':digest(replay),'closure_digest':closure,
                        'candidate_failure_contexts':failure_count,'execution_failure_contexts':execution_failures,
                        'contexts_with_failed_predictions':prediction_failures,'projection':projection,
                        'metering':{'rawledger_event_replay_available':False,
                            'model_calls':sum(x['model_calls'] for x in usage.values()),
                            'input_tokens':sum(x['input_tokens'] for x in usage.values()),
                            'output_tokens':sum(x['output_tokens'] for x in usage.values()),
                            'tool_calls':sum(x['tool_calls'] for x in usage.values()),
                            'ledger_event_commitment_digest':digest({k:v['ledger_events_digest'] for k,v in usage.items()})},
                        'evidence':{'artifacts':len(m['artifacts']),'journal_events':len(m['journal']),
                            'reference_jobs':len(bundle.reference_jobs),'tool_preparations':len(bundle.tool_events),'independent_draw_ids':len(seen),
                            'opaque_identity_bodies_rehashed':False,'receipt':bundle.meter.receipt()},
                        'claim_limit':CLAIM_LIMIT}


def public_projection(final):
    """No private IDs, held labels, per-case predictions or source paths."""
    panel_keys=('accuracy','accuracy_exact','brier_with_failure_penalty','probability_metric_label',
        'weighted_coverage','weighted_coverage_exact','unweighted_coverage','valid_row_weighted_brier',
        'valid_records','failed_records')
    summaries={k:{n:v for n,v in x.items() if n not in ('rows','people','records_digest','closure_digest')}
               for k,x in final['three_repetition_summaries'].items()}
    #Per-person uncertainty is prespecified. Replace original participant IDs by
    #stable enumeration solely in this public projection, never in scoring.
    aliases={p:'person_'+str(i+1).zfill(2) for i,p in enumerate(PEOPLE)}
    def clean(x):
        if type(x) is dict:return {aliases.get(k,k):clean(v) for k,v in x.items()}
        if type(x) is list:return [clean(v) for v in x]
        return x
    for key,x in final['three_repetition_summaries'].items():summaries[key]['people']=clean(x['people'])
    return {'candidate_panels':{k:{n:v[n] for n in panel_keys} for k,v in final['candidate_panels'].items()},
        'reference_panels':{k:{n:v[n] for n in panel_keys} for k,v in final['reference_panels'].items()},
        'three_repetition_summaries':summaries,'paired_comparisons':clean(final['paired_comparisons']),
        'person_alias_interpretation':'stable within this declared-source study; not an anonymization guarantee'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('submission','output','deployment','deployment-sha256','review'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--other-reserve-bytes',required=True,type=int)
    args=parser.parse_args(argv)
    if args.other_reserve_bytes<0:parser.error('other-reserve-bytes must be nonnegative')
    from .authority import load_grade_context
    task_root=os.path.dirname(os.path.abspath(__file__))
    context=load_grade_context(task_root,args.deployment,args.deployment_sha256,args.review,args.submission,
        other_reserve_bytes=args.other_reserve_bytes)
    result=grade_instance(**{k:context[k] for k in ('run_root','manifest_pin','terminal','trusted_plan','catalogue','policy','score_authority','limits')})
    from .observe import write_projection_exclusive
    write_projection_exclusive(args.output,result,limit=context['limits'].max_file_bytes)
    return 0


if __name__=='__main__':
    raise SystemExit(main())

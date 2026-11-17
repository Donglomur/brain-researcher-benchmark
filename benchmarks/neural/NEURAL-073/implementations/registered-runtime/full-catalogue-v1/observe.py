"""Explicit terminal observation without model execution or score feedback.

This terminal consumer never infers a latest run and does not publish metrics.
A running/incomplete run has no terminal acceptance; optional live progress is a
separate authenticated writer interface, not simulated by examining directory names.
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
import os
from .evidence import EvidenceError,load_evidence,_closed
from .runtime.core.custody import digest
from .runtime.private_store.store import bounded_json


def observe_instance(*,run_root,manifest_pin,terminal,trusted_plan,catalogue,policy,limits):
    from .grade import _trusted_inputs,_full_contexts,validate_context_original,expected_reference_counts,_hash
    with load_evidence(run_root,manifest_pin,terminal=terminal,limits=limits) as bundle:
        m=bundle.manifest
        _trusted_inputs(trusted_plan,catalogue,policy,m['identities'])
        contexts=_full_contexts(trusted_plan.contexts());closures={};draws=set();failures=0;execution_failures=0;prediction_failures=0
        with bundle.artifact(m['roles']['run_contract']) as contract:
            if contract.get('schema')!='n073_run_contract_v2' or contract.get('attempt_binding')!=bundle.terminal_claims['attempt_binding'] or contract.get('reference_source_digest')!=m['identities']['code_closure_digest'] or contract.get('identities')!=m['identities'] or set(contract.get('context_contracts',{}))!={c.context_id for c in contexts}:
                raise EvidenceError('complete original invocation/context contracts required')
            for context in contexts:
                key=m['roles']['candidate_contexts'][context.context_id]
                with bundle.artifact(key) as original:
                    usagekey=m['roles']['provider_usage'][context.context_id]
                    if usagekey!='usage_'+context.context_id:raise EvidenceError('exact original usage artifact identity required')
                    with bundle.artifact(usagekey) as projection:
                        draws,_=validate_context_original(context,original,plan=trusted_plan,policy=policy,
                            contract=contract['context_contracts'][context.context_id],
                            events=bundle.context_events[context.context_id],seen_draw_ids=draws,
                            usage_projection=projection,extraction_source_digest=contract['usage_extraction_source_digest'])
                    closures[context.context_id]=original['closure_digest']
                    failed_prediction=any(v is None for v in original['submission']['probabilities'].values())
                    execution_failures+=bool(original['candidate_failure']);prediction_failures+=failed_prediction
                    failures+=bool(original['candidate_failure']) or failed_prediction
        closure=trusted_plan.assert_complete_closure(closures)
        with bundle.artifact(m['roles']['full_locked_closure']) as locked:
            _closed(locked,('plan_digest','closure_digest','reference_receipt','contexts'),'locked closure')
            if locked['plan_digest']!=trusted_plan.binding_digest or locked['closure_digest']!=closure or locked['contexts']!=closures:
                raise EvidenceError('whole234 original closure differs')
            reference=locked['reference_receipt'];_hash(reference,'completion_digest')
            if reference['domain']!='authentic' or reference['plan_digest']!=trusted_plan.binding_digest or reference['reference_models']!=455:
                raise EvidenceError('reference completion identity differs')
            for key,value in expected_reference_counts().items():
                if reference['work']['counts'].get(key)!=value:raise EvidenceError('reference completion missing full work')
            if (reference['work']['jobs']!=55523 or reference['work']['job_statuses']!={'reserved':0,'complete':55523,'failed':0}
                or reference['work']['event_digest']!=bundle.reference_events_digest
                or len(bundle.reference_jobs)!=55523 or any(x['status']!='complete' for x in bundle.reference_jobs.values())):
                raise EvidenceError('reference jobs not completely closed')
        expected='complete_with_candidate_failures' if failures else 'complete'
        if expected!=m['status']:raise EvidenceError('original failure-status mismatch')
        return {'schema':'n073_terminal_observation_v1','status':m['status'],
            'terminal_originals_verified':True,'scientific_score_qualified':False,'metrics':None,
            'next_required_step':'independent full OOF selection/calibration and production score replay',
            'run_digest':digest(m['run_id']),'manifest_sha256':manifest_pin['sha256'],
            'completed_contexts':234,'candidate_failure_contexts':failures,'execution_failure_contexts':execution_failures,
            'contexts_with_failed_predictions':prediction_failures,'reference_jobs':55523,
            'reference_models':455,'tool_preparations':len(bundle.tool_events),'original_OOF_artifacts':55068,'journal_events':len(m['journal']),
            'committed_artifacts':len(m['artifacts']),'rawledger_event_replay_available':False,
            'opaque_identity_bodies_rehashed':False,'read_receipt':bundle.meter.receipt()}


def write_projection_exclusive(path,value,*,limit):
    """Bounded exact output, no overwrite or symlink traversal; partials retained."""
    if type(path) is not str or not path.startswith('/') or os.path.normpath(path)!=path or path=='/':
        raise EvidenceError('canonical explicit absolute output required')
    body=bounded_json(value,limit-1)+b'\n'
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    filefd=None
    try:
        parts=path.split('/')[1:]
        for name in parts[:-1]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
        filefd=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
        offset=0
        while offset<len(body):
            written=os.write(filefd,body[offset:offset+65536])
            if written<=0:raise EvidenceError('short projection write; original partial retained')
            offset+=written
        os.fsync(filefd);os.close(filefd);filefd=None;os.fsync(fd)
    finally:
        if filefd is not None:os.close(filefd)
        os.close(fd)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('submission','output','deployment','deployment-sha256','review'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--other-reserve-bytes',required=True,type=int)
    args=parser.parse_args(argv)
    if args.other_reserve_bytes<0:parser.error('other-reserve-bytes must be nonnegative')
    from .authority import load_grade_context
    context=load_grade_context(os.path.dirname(os.path.abspath(__file__)),args.deployment,args.deployment_sha256,
        args.review,args.submission,other_reserve_bytes=args.other_reserve_bytes)
    #The independently admitted loader already performed this exact observation
    #and debited its reads/wall time. Never repeat it with a reset allowance.
    result=context['observation']
    write_projection_exclusive(args.output,result,limit=context['limits'].max_file_bytes)
    return 0


if __name__=='__main__':raise SystemExit(main())

"""Trusted complete construction/run route; never imports a scientific library eagerly."""
from pathlib import Path
from .common import capture,parse,encoded,sha,require,FailureCarrier
from .budget import Budget
from .journal import Journal
from .source import Sources
from .authority import Authority
from .plan import admit
from .programmes import Programmes
from .inputs import OriginalInputs
from .views import Views
from .native import DockerHost
from .process import ProcessRunner
from .campaign import Campaign
from .protected import Protected
from .registry import campaign,PEOPLE,SEEDS
from .banks import expected_training_cells
from .learning import expected_jobs

def inspect_source(source):
    from .participant_contract import interface_identity
    expected=campaign('INSPECTION_ONLY_SYSTEM')
    jobs=sum(len(expected_jobs(c['evaluated_system'],c['outer_person'],c['arm'],c['seed'],[p for p in PEOPLE if p!=c['outer_person']])) for c in expected_training_cells())
    require(jobs==8520,'full original8520 reference fitting jobs')
    return {'schema':'neural055-complete-source-inspection-v1','source_identity':source.identity,
            'cells':len(expected),'participant_cells':600,'reference_cells':360,'panels':96,
            'logical_phase_envelopes':1920,'independent_training_banks':150,'reference_training_jobs':jobs,
            'primary_contrasts':32,'open_scientific_gates':30,'scientific_execution':False,
            'deployment_qualified':False,'primary_or_authentic_inputs_opened':False,
            'public_participant_interface':interface_identity(source),'feature_preparation_entry':'prepare-features'}

def execute(mode,plan,operator_root,source_root,manifest_descriptor,output,origin,cpu_origin,bootstrap_read_bytes=0):
    if mode=='prepare-features':
        from .features import execute as feature_execute
        return feature_execute(plan,operator_root,source_root,manifest_descriptor,output,origin,cpu_origin,bootstrap_read_bytes)
    require(mode in ('inspect','prepare','run'),'closed complete command')
    budget=Budget(origin,plan['limits'],cpu_origin=cpu_origin)
    budget.read(bootstrap_read_bytes)
    carrier=FailureCarrier();journal=Journal(output,budget,carrier)
    source=None;authority=None;programmes=None;inputs=None;workflow=None;result=None;first=None;postscore_context=None
    try:
        source=Sources(source_root,manifest_descriptor,budget)
        contracts={n:source.bodies['contracts/'+n] for n in ('ISOLATION_CONTRACT.json','MODE_PERMISSIONS.json','REPORT_HIERARCHY.json','CONTRASTS.json')}
        _,plan_id=admit(plan,source,contracts)
        from .resource_policy import bind as bind_resource_policy
        bind_resource_policy(plan,source,budget)
        authority=Authority(operator_root,plan['trust'],budget)
        require(authority.trust['source_identity']==source.identity and authority.trust['deployment_identity']==plan['native_profile']['deployment_identity'],'exact external deployment/source trust')
        if mode=='inspect':
            result=inspect_source(source)
        else:
            authority.verify(plan['runtime_environment']['qualification'],'native_runtime_qualification',
                             {'source':source.identity,'native_profile':plan['native_profile'],'environment':plan['runtime_environment']['identity'],'limits':plan['limits'],'phase_limits':plan['phase_limits']})
            if mode=='run':
                from .postscore_dispatch import prepare_dispatcher
                postscore_context=prepare_dispatcher(plan,source,operator_root,authority,journal,budget,carrier)
            authority.verify(plan['input_qualification'],'full_neural_input_qualification',
                             {'input_index':plan['input_index'],'dimensions':plan['dimensions'],'source':source.identity,
                              'fixed_feature_order_and_checkpoint':plan['runtime_environment']['feature_identity']})
            with budget.action(budget.action_deadline(plan['phase_limits']['prepare'])):
                inputs=OriginalInputs(source,budget).inspect(operator_root,plan['input_index'])
                programmes=Programmes(plan,source,operator_root,authority,journal,budget)
                source.stage_actor_runtime(journal)
                result={'schema':'neural055-complete-preparation-v1','plan_sha256':plan_id,
                        'original_full_public_plan':inputs.original_plan,'input_index':inputs.identity,
                        'source':source.identity,'pre_exposure_programmes':programmes.subject,
                        'scientific_execution':False,'private_target_opened':False,
                        'qualification_receipts':authority.used}
                journal.json('PREPARATION.json',result)
            if mode=='run':
                runner=ProcessRunner(budget,journal,carrier)
                host=DockerHost(plan['native_profile'],runner,journal,budget,carrier)
                from .participant_contract import selected_documents
                public_docs=selected_documents(source)
                views=Views(inputs,journal,budget,plan['native_profile'],public_docs)
                workflow=Campaign(plan,operator_root,source,inputs,programmes,views,host,runner,authority,journal,budget)
                workflow.run()
                with budget.action(budget.action_deadline(plan['phase_limits']['grade_report'])):
                    consumer=Protected(plan,operator_root,source,inputs,programmes,workflow.collection,workflow.banks,authority,journal,budget,postscore_context=postscore_context)
                    carrier.retain(consumer)
                    publication=consumer.run()
                    result={'schema':'neural055-complete-campaign-result-v1','plan_sha256':plan_id,'report':publication,
                            'cells':960,'panels':96,'phase_envelopes':1920,'complete_scientific_comparison':all(t['status'] in ('complete_valid','complete_valid_calibration_uninformative') for t in workflow.collection.terminals.values()),
                            'open_scientific_gates':30,'scientific_qualification_claim':False}
        budget.check('before original complete entry completion')
    except BaseException as exc:
        first=exc;carrier.fail(exc,'complete_entry')
    # Original error ownership precedes final clock, source, metadata and output.
    try:
        if source is not None:source.current()
        costs=journal.json('ORIGINAL_COSTS.json',budget.snapshot())
        budget.check('after complete original source and cost finalization')
    except BaseException as exc:
        carrier.fail(exc,'entry_finalization');costs={'status':'unavailable','original_counters_retained':True}
        if first is None:first=exc
    terminal={'schema':'neural055-original-complete-terminal-v1','status':'complete' if first is None else 'unavailable',
              'mode':mode,'result':result,'errors':carrier.document(),'costs':costs,
              'all_original_objects_retained':True,'no_failure_replaced_with_success':True}
    durable=journal.terminal(terminal)
    if first is not None or not durable:
        failure=CompleteFailure(carrier,workflow,terminal,journal)
        if first is not None:raise failure from first
        raise failure
    return terminal

class CompleteFailure(Exception):
    def __init__(self,carrier,workflow,terminal,journal):
        self.carrier=carrier;self.workflow=workflow;self.terminal=terminal;self.journal=journal
        super().__init__('complete original N055 operation unavailable')


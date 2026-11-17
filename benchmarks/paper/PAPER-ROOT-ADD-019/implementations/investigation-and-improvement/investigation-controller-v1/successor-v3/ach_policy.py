"""Immutable global investigation policy and matched A/B capability contract."""
from ach_util import need,integer,token,require_pin,pin,pin_bytes,encode,exact_fields

PROGRAMS=('A/native','B/native','A/improvement','B/improvement')
ARMS=('A_clarified','B_author_code')
TOOLS=('analysis','fit','validate','seal')
LIMITS=('provider_calls','input_tokens','output_tokens','analysis_processes','fit_processes',
        'validation_processes','generated_code_bytes','model_bytes','result_bytes','conversation_bytes')

SELECTION_RULE={
    'schema':'ach_adaptive_outer_training_selection_rule_v1',
    'chooser':'immutable global investigator policy with fresh outer-training adaptation',
    'permitted_feedback':'this complete outer-training realm only',
    'inner_metrics':'adaptive selection diagnostics, not unbiased investigator evaluation',
    'final_fit':'all original outer-training animals and four heads',
    'final_seal':'generated source, configuration, selection and learned state before outer queries',
    'forbidden_feedback':['native outputs','reference results','outer targets','other contexts'],
    'outer_updates':'none'}

def validate_policy(policy,arm):
    exact_fields(policy,('schema','task','access','global_program_pin','controller_source_pin','model',
        'system_prompt','task_prompt','tool_specs','limits','method_interface','randomization',
        'selection_interpretation'),'complete immutable investigation policy')
    need(policy['schema']=='ach_adaptive_training_policy_v1' and policy['task']=='PAPER-ROOT-ADD-019' and
         policy['access']==arm and arm in ARMS,'fixed task/access policy')
    for k in ('global_program_pin','controller_source_pin'):require_pin(policy[k])
    exact_fields(policy['model'],('provider','model','version','parameters'),'exact model configuration')
    for k in ('provider','model','version'):token(policy['model'][k])
    need(type(policy['model']['parameters']) is dict,'declared model inference parameters')
    for k in ('system_prompt','task_prompt'):
        need(type(policy[k]) is str and 0<len(policy[k].encode('utf-8'))<=65536,'bounded fixed prompt')
    need(type(policy['tool_specs']) is dict and set(policy['tool_specs'])==set(TOOLS),'complete fixed scientific tools')
    for k,v in policy['tool_specs'].items():require_pin(v)
    exact_fields(policy['limits'],LIMITS,'complete investigator call/search/source/state limits')
    for v in policy['limits'].values():integer(v,1)
    need(policy['method_interface']=='ach_generated_four_head_program_v1','four-head generated method protocol')
    exact_fields(policy['randomization'],('seed','retries','selection_rule_pin'),'declared randomization/retry/selection')
    integer(policy['randomization']['seed']);integer(policy['randomization']['retries'])
    require_pin(policy['randomization']['selection_rule_pin'])
    need(policy['randomization']['selection_rule_pin']==pin(SELECTION_RULE),
         'exact source-owned adaptive selection semantics, no opaque unenforced selector')
    need(policy['selection_interpretation']=='adaptive_outer_training_inner_metrics_are_selection_diagnostics',
         'no claim inner diagnostics independently evaluate the whole investigator')
    return pin(policy)

def committed_policy_body(policy):
    """The improvement programme is canonical policy bytes; its external pin
    is attached after capture, preventing a self-referential embedded digest.
    """
    return encode({k:v for k,v in policy.items() if k!='global_program_pin'})

def validate_global(programs,policies,controller_source_pin,commitment):
    need(type(programs) is dict and set(programs)==set(PROGRAMS),'same original four global programmes')
    for record in programs.values():
        exact_fields(record,('path','bytes','sha256'),'committed programme descriptor')
        require_pin({k:record[k] for k in ('bytes','sha256')})
        need(type(record['path']) is str and record['path'],'committed programme source path')
    need(type(policies) is dict and set(policies)==set(ARMS),'both improvement investigation policies')
    for arm,short in zip(ARMS,('A','B')):
        policy=policies[arm];validate_policy(policy,arm)
        need(policy['controller_source_pin']==controller_source_pin and
             policy['global_program_pin']=={k:programs[short+'/improvement'][k] for k in ('bytes','sha256')},
             'same presealed global policy and exact controller source')
        need(pin_bytes(committed_policy_body(policy))==policy['global_program_pin'],
             'exact source-owned interpretation of committed improvement programme bytes')
    a,b=(policies[x] for x in ARMS)
    need(a['randomization']['retries']==b['randomization']['retries'],'matched A/B failed-proposal retry ceiling')
    for name in ('model','tool_specs','limits','method_interface','selection_interpretation'):
        need(a[name]==b[name],'matched A/B '+name+'; authenticated author code is the access difference')
    need(type(commitment) is dict and commitment.get('programs_pin')==pin(programs) and
         commitment.get('policies_pin')==pin(policies) and
         all(commitment.get(k) is True for k in ('before_numeric_exposure','independent_four_policy_history',
             'authoring_views_verified','no_native_or_cross_context_feedback')),
         'independently observed complete four-policy commitment')
    require_pin(commitment['observation_pin'])
    # Receipt authenticity is established by the concrete separate observer
    # transport and deployment gate, not these dictionaries or Boolean fields.
    return {'programs_pin':pin(programs),'policies_pin':pin(policies),'commitment_pin':pin(commitment),
            'author_contexts':4,'candidate_method_may_adapt_on_outer_training':True,
            'inner_diagnostics_are_independent_evaluation':False}

def investigation_key(spec):
    return '|'.join((spec['realization'],spec['actor'],spec['cohort'],spec['animal'],spec['variant']))

class InvestigationState:
    """Fresh adaptive fit state; no state crosses bundle/realization boundaries."""
    def __init__(self,policy,spec,training_view_pin):
        validate_policy(policy,spec['actor']);require_pin(training_view_pin)
        self.key=investigation_key(spec);self.policy_pin=pin(policy);self.training_view_pin=training_view_pin
        self.limits=dict(policy['limits']);self.used={k:0 for k in LIMITS}
        self.revisions={};self.events=[];self.sealed=None;self.failed=False;self.round=0

    def reserve(self,charges,kind):
        need(not self.failed and self.sealed is None,'only active unsealed investigation')
        need(set(charges)<=set(self.used),'known investigation resource dimensions')
        for amount in charges.values():integer(amount)
        for k,v in charges.items():self.used[k]+=v
        exceeded=[k for k in charges if self.used[k]>self.limits[k]]
        if exceeded:
            self.failed=True;self.events.append({'kind':'resource_failure','operation':kind,'charges':charges,
                                                'exceeded':exceeded,'attempted':dict(self.used)})
            need(False,'complete investigator resource ceiling exceeded')

    def record(self,event):
        need(not self.failed and self.sealed is None,'active investigation log')
        need(type(event) is dict and 'kind' in event,'typed investigation event')
        self.events.append({'ordinal':len(self.events),'bundle_key':self.key,'event':event})

    def fail(self,error):
        self.failed=True
        self.events.append({'kind':'failure','error_type':type(error).__name__,'attempted':dict(self.used)})

    def seal(self,artifact):
        need(not self.failed and self.sealed is None,'seal once after successful training selection')
        exact_fields(artifact,('bundle_key','policy_pin','training_view_pin','revision_pin','model_pin',
             'selection_pin','head_manifest_pin'),'complete generated source and four-head seal')
        need(artifact['bundle_key']==self.key and artifact['policy_pin']==self.policy_pin and
             artifact['training_view_pin']==self.training_view_pin,'same fresh fit scope')
        for k in ('revision_pin','model_pin','selection_pin','head_manifest_pin'):require_pin(artifact[k])
        self.sealed=dict(artifact)
        return {'seal':self.sealed,'seal_pin':pin(self.sealed),'events':list(self.events),
                'attempted':dict(self.used),'inner_metrics':'selection_diagnostics_only'}

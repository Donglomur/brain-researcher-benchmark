"""Full original population/role compiler; identities are metadata, not acquisition authority."""
from .domain import Refusal, MissingDefinition, Pin, closed, unique, CONDITIONS

REQUIRED_ROLES = {'brainwide_choice_prior':433, 'main_comparison':10, 'multi_backbone_comparison':30,
                  'unaligned_training':50, 'unaligned_evaluation':10,
                  'allen_training':58, 'allen_evaluation':10, 'allen_lick':7,
                  'primate_rtt':1}

def validate_cohort(document, plan):
    closed(document, ('schema','profile','source','sessions','regions','roles','session_region_support',
                      'excluded_sessions','animal_identity_source','panel_identity_source'), 'cohort')
    if document['schema']!='trial_session_cohort_v1' or document['profile']!=plan.profile: raise Refusal('cohort schema/profile')
    for k in ('source','animal_identity_source','panel_identity_source'): Pin.parse(document[k])
    sessions={}
    for row in document['sessions']:
        closed(row,('session','animal','dataset','source_identity','acquisition_revision'),'session')
        if row['session'] in sessions: raise Refusal('duplicate session')
        Pin.parse(row['source_identity']); sessions[row['session']]=row
    unique(document['regions'],'region roster')
    role_names=set()
    for role in document['roles']:
        closed(role,('name','sessions','source','selection_rule'),'cohort role')
        if role['name'] in role_names: raise Refusal('duplicate role')
        role_names.add(role['name']);unique(role['sessions'],'role sessions');Pin.parse(role['source'])
        if not set(role['sessions'])<=set(sessions): raise Refusal('unknown role session')
        if plan.profile=='paper433' and role['name'] in REQUIRED_ROLES and len(role['sessions'])!=REQUIRED_ROLES[role['name']]:
            raise Refusal('full original role population '+role['name'])
    if plan.profile=='paper433' and role_names!=set(REQUIRED_ROLES): raise Refusal('full main/external cohort roles')
    support={}
    for row in document['session_region_support']:
        closed(row,('session','region','unit_identity_source','status','reason'),'session-region support')
        key=(row['session'],row['region'])
        if key in support or row['session'] not in sessions or row['region'] not in document['regions']:
            raise Refusal('session-region identity')
        if row['status']=='observed': Pin.parse(row['unit_identity_source'])
        elif row['status']!='unavailable' or row['reason'] is None: raise Refusal('region support disposition')
        support[key]=row
    for case in plan.cases:
        actual=sessions.get(case.session)
        if actual is None or actual['animal']!=case.animal or actual['dataset']!=case.dataset: raise Refusal('case biological unit')
        if case.region!='all' and (case.session,case.region) not in support: raise Refusal('case regional support')
    return document

def validate_paired_views(a,b,plan):
    fields=('schema','condition','cohort','splits','public_inputs','training_targets','author_source',
            'limits','protected_targets','query_labels')
    closed(a,fields,'A view');closed(b,fields,'B view')
    if a['schema']!='trial_session_view_v1' or b['schema']!='trial_session_view_v1': raise Refusal('view version')
    if (a['condition'],b['condition'])!=CONDITIONS: raise Refusal('paired arm order')
    if a['author_source'] is not None or b['author_source'] is None: raise Refusal('sole author-code condition difference')
    for k in ('cohort','splits','public_inputs','training_targets','limits'):
        if a[k]!=b[k]: raise Refusal('unequal paired resource '+k)
    if any(x[k] is not None for x in (a,b) for k in ('protected_targets','query_labels')):
        raise Refusal('query/protected target leak')
    if a['limits']!=plan.limits.__dict__: raise Refusal('same original resource budget')
    # This validation never establishes actual mount/process isolation or secret exclusion.
    return True

def reconcile_complete_jobs(plan,cohort):
    validate_cohort(cohort,plan)
    for case in plan.cases:
        if case.availability!='available': continue
        candidates=[j for j in plan.jobs if j.role=='candidate' and case.case_id in j.case_ids]
        if {j.condition for j in candidates}!=set(CONDITIONS): raise Refusal('case missing paired invocation')
        required=({'linear','multi_region_rrr'} if case.region!='all' else
                  {'linear','single_rrr','mlp'} if case.dataset=='primate' else
                  {'linear','single_rrr','multi_rrr'})
        if not required<={j.method for j in candidates}:
            raise Refusal('core original decoder output roster')
    if plan.profile=='paper433':
        methods={j.method for j in plan.jobs}
        required={'linear','mlp','single_rrr','multi_rrr','multi_region_rrr','multi_linear','multi_mlp',
                  'hmm','bmm_hmm','empirical_bmm_hmm','lg_ar1','empirical_lg_ar1','rrr_bmm_hmm','rrr_lg_ar1'}
        if not required<=methods: raise Refusal('full original comparator family census')
    return {'jobs':len(plan.jobs),'cases':len(plan.cases),'qualified':False}

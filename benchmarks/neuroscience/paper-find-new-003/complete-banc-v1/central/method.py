"""One closed full-paper method for one explicit paired evaluation condition."""
from banc_runtime.codec import need,descriptor,encode,pin
from banc_runtime.construct import DATA_ROLES
from .io import exact_fields,digest
from .source import PROFILE,SCOPE,CONDITIONS,STAGES,programme

FIELDS=('schema','task_id','profile','scope','condition','source_manifest_sha256','annotation_profile','operator_branch',
 'graph_variant','data','paper','reference_plan','actor_plan','assessment_plan')

def validate_method(method,source):
    exact_fields(method,FIELDS,'complete method')
    need(method['schema']=='banc_complete_method_v1' and method['task_id']=='PAPER-FIND-NEW-003' and
      method['profile']==PROFILE and method['scope']==SCOPE and method['condition'] in CONDITIONS,'canonical full programme/condition')
    need(method['source_manifest_sha256']==source['manifest_identity']['sha256'],'method binds actual portable source')
    need(method['operator_branch'] is not None,'execution method must explicitly select a specification/native/wrapper branch')
    for name in ('paper','reference_plan','actor_plan','assessment_plan'):descriptor(method[name])
    program=programme(source,method)
    need(not program.missing_roles,'complete method must declare all20 original data roles; missing bodies remain gated')
    return program

def method_identity(method):return pin(encode(method))['sha256']

def validate_reference_plan(value,source):
    exact_fields(value,('schema','families','jobs','projection','qualification_evidence'),'reference plan')
    need(value['schema']=='banc_complete_reference_plan_v1','reference plan schema')
    families=tuple(x['id'] for x in source['contracts']['WORKFLOW']['families'])
    need(type(value['families']) is list and tuple(value['families'])==families,'all18 reference family obligations')
    need(type(value['jobs']) is list and value['jobs'],'concrete full reference jobs')
    from banc_runtime.construct import FAMILY_SCRIPTS
    seen=set();kinds={f:set() for f in families}
    for job in value['jobs']:
        exact_fields(job,('id','family','kind','request','dependencies','output','limits'),'reference job')
        need(type(job['id']) is str and job['id'] and job['id'] not in seen and job['family'] in families,'unique reference job')
        need(type(job['dependencies']) is list and set(job['dependencies'])<=seen,'complete topological producer order')
        need(job['kind'] in ('admission','original_figure','influence_python','influence_R_wire','sensory_R_wires','sensory_python','native_statistics','centrality','evaluation_pending'),'closed concrete producers')
        descriptor(job['request']);descriptor(job['output']) if job['output'] is not None else None
        need(job['output'] is None,'future output content cannot be supplied as a precomputed reference descriptor')
        from .authority import LIMIT_FIELDS
        from .io import integer
        exact_fields(job['limits'],LIMIT_FIELDS,'explicit subordinate job allocation')
        for key,n in job['limits'].items():integer(n,key,1)
        seen.add(job['id']);kinds[job['family']].add(job['kind'])
    need(kinds['D00']=={'admission'} and kinds['D17']=={'evaluation_pending'},'admission/protected evaluation owned by controller')
    need(kinds['D04'] and kinds['D04']<= {'influence_python','influence_R_wire'},'actual selected native influence producers')
    need(kinds['D06'] in ({'sensory_R_wires','original_figure'},{'sensory_python','original_figure'}),'full3x17x19 explicit native sensory producer and original display')
    need('native_statistics' in kinds['D16'],'native statistical source producer required')
    for f,names in FAMILY_SCRIPTS.items():
        if names:need('original_figure' in kinds[f],'all original family producers required: '+f)
    from banc_runtime.codec import relative
    descriptor(value['projection']);relative(value['qualification_evidence'])
    return value

def validate_requests(plan,requests,source):
    """Every original script, full family DAG and selected native path are joined."""
    from banc_runtime.construct import FAMILY_SCRIPTS
    support={f:set() for f in FAMILY_SCRIPTS};jobs={j['id']:j for j in plan['jobs']}
    ancestors={}
    for job in plan['jobs']:
        q=requests[job['id']]
        exact_fields(q,('schema','kind','family','inputs','parameters','source_context','execution_authority'),'producer request')
        need(q['schema']=='banc_producer_request_v1' and q['kind']==job['kind'] and q['family']==job['family'],'request/producer identity')
        need(type(q['inputs']) is dict and type(q['parameters']) is dict and type(q['source_context']) is list,'closed request data')
        ancestors[job['id']]=set(job['dependencies'])
        for dep in job['dependencies']:ancestors[job['id']]|=ancestors[dep]
        if job['kind']=='original_figure':
            name=q['parameters'].get('script')
            need(name in FAMILY_SCRIPTS[job['family']],'exact family original figure script')
            support[job['family']].add(name)
    for f,names in FAMILY_SCRIPTS.items():need(support[f]==set(names),'complete original script coverage:'+f)
    for f in source['contracts']['WORKFLOW']['families']:
        relevant=[j for j in jobs.values() if j['family']==f['id']]
        need(relevant,'every scientific family has concrete jobs')
        for dep in f['dependencies']:
            required={j['id'] for j in jobs.values() if j['family']==dep}
            need(required and all(required<=ancestors[j['id']] for j in relevant),'full family DAG dependency:'+f['id']+'/'+dep)
    return requests

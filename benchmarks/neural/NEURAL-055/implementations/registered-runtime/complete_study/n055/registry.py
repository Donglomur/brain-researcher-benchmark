"""Complete prespecified scientific units, not task-count aliases."""
import itertools
from .common import encoded, sha, require, keys

PEOPLE=tuple('sub-%02d'%i for i in range(1,11))
ARMS=('FULL','IMAGE_ONLY','PRE_ONLY','POST_ONLY','ALIGN_SHUFFLE')
SEEDS=(55055,55056,55057)
FIELDS=('task_id','protocol_version','evaluated_system','mode','tool_setting','seed','arm','outer_person')
VERSION='complete-scientific-api-design-s3'
VALID=('complete_valid','complete_valid_calibration_uninformative')

def cell(system,mode,tool,seed,arm,person):
    return dict(zip(FIELDS,('NEURAL-055',VERSION,system,mode,tool,seed,arm,person)))

def token(value):
    return sha(encoded(value))

def panel_key(c):
    keys(c,FIELDS)
    return {k:c[k] for k in FIELDS[:-1]}

def campaign(system):
    result=[]
    for mode,tool,seed,arm in itertools.product(('F','I'),('T0','T1'),SEEDS,ARMS):
        result.extend(cell(system,mode,tool,seed,arm,p) for p in PEOPLE)
    for ref in ('R0','R1','R2','R3'):
        for arm in ARMS:
            seeds=SEEDS if ref=='R3' or arm=='ALIGN_SHUFFLE' else ('DETERMINISTIC',)
            for seed in seeds:result.extend(cell(ref,'REFERENCE','REFERENCE',seed,arm,p) for p in PEOPLE)
    require(len(result)==960 and len({token(c) for c in result})==960,'full960 registry')
    return result

def training_key(c):
    return {'reference':c['evaluated_system'],'outer_person':c['outer_person'],
            'mask':c['arm'] if c['arm'] in ('PRE_ONLY','POST_ONLY') else 'FULL',
            'seed':c['seed'] if c['evaluated_system']=='R3' else 'DETERMINISTIC'}

def envelope(c,phase,disposition,execution='unattempted',original=None,cause=None):
    require(phase in ('FIT','INFER'),'phase')
    return dict(cell_key=c,phase=phase,disposition=disposition,execution_kind=execution,
                original_operation_ids=[] if original is None else [original['id']],reuse_relation=None,
                first_error=cause,secondary_errors=[],original_costs=None if original is None else original.get('costs'),
                attributable_costs=None,closure_disposition='not_observed' if original is None else original['closure'])

def terminal(c,status,phases,case=None,cause=None):
    require(len(phases)==2 and [p['phase'] for p in phases]==['FIT','INFER'] and all(p['cell_key']==c for p in phases),'same two original phase slots')
    return dict(cell_key=c,panel_key=panel_key(c),public_case_identity=case,status=status,expected_queries=200,
                admissible_queries=200 if status in VALID else 0,unavailable_queries=0 if status in VALID else 200,
                phase_envelope_keys=[dict(c,phase=p) for p in ('FIT','INFER')],source_input_output_qualification_bindings={},
                first_error=cause,secondary_errors=[],failed_phase=next((p['phase'] for p in phases if p['disposition']!='complete'),None),
                original_costs=None,attributable_costs=None,numerical_disposition={'status':'unavailable_before_protected_grade'},
                interpretation_disposition={'status':'not_observed'})

def panels(expected,terminals):
    require(len(terminals)==960 and set(terminals)=={token(c) for c in expected},'all expected original cell dispositions')
    grouped={}
    for c in expected:grouped.setdefault(token(panel_key(c)),[]).append(c)
    require(len(grouped)==96,'full96 panels')
    output=[]
    for cs in grouped.values():
        require([c['outer_person'] for c in cs]==list(PEOPLE),'ordered all-ten panel')
        ts=[terminals[token(c)] for c in cs]
        for c,t in zip(cs,ts):
            require(t['cell_key']==c and t['panel_key']==panel_key(c) and t['expected_queries']==200,'exact200 person cell')
            require(t['admissible_queries']==(200 if t['status'] in VALID else 0),'all-or-zero structural support')
            require(t['unavailable_queries']==200-t['admissible_queries'],'complement support')
        statuses={s:sum(t['status']==s for t in ts) for s in {t['status'] for t in ts}}
        good=all(t['status'] in VALID for t in ts)
        state='complete_valid_calibration_uninformative' if good and 'complete_valid_calibration_uninformative' in statuses else ('complete_valid' if good else 'incomplete')
        support=sum(t['admissible_queries'] for t in ts)
        output.append(dict(panel_key=panel_key(cs[0]),child_cell_keys=cs,state=state,child_status_counts=statuses,
                           child_failure_references=[{'cell_key':t['cell_key'],'failed_phase':t['failed_phase'],'first_error':t['first_error']} for t in ts if t['status'] not in VALID],
                           expected_queries=2000,admissible_queries=support,unavailable_queries=2000-support,
                           primary_numerical_disposition={'status':'unavailable_before_protected_grade'},
                           diagnostic_bounds_disposition={'status':'not_authorized','correct_completed':None},
                           interpretation_disposition={'status':'not_observed'},physical_cost_links=[],attributable_cost_links=[]))
    return output

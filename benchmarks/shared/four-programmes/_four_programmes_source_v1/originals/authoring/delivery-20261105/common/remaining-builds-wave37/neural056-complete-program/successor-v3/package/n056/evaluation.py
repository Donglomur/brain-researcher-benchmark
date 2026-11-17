"""Complete admission before private scoring; actor scores are never accepted."""
from pathlib import Path
from .core import need,capture,read_json,save,digest
from .protocol import PEOPLE,ARMS,ROLES
from .arrays import decode
from .bank_a import correlation,macro
from .runtime import check_tree

def prediction(outcome,rows,budget):
    need(outcome['complete'] and outcome['exit_code']==0 and not outcome['forced']
         and outcome['cleanup_empty'] and all(outcome['stream_eof'].values()),'complete original process required')
    tree=outcome['outputs'];need({x['relative'] for x in tree['members']}=={'prediction.npz'},'exact prediction product')
    check_tree(tree,budget);row=tree['members'][0]
    raw=capture(Path(tree['root'])/'prediction.npz',row['bytes'],row,budget)
    return decode(raw,{'prediction':(rows,17,100)},max(4000000,rows*1700*16+65536))['prediction'].reshape(rows,1700)

def paired_lifetime(train,query):
    need(train['complete'] and query['complete'],'complete train/query chain')
    need(train['completed_ns']<=query['started_ns'],'fitted model frozen before query start')
    need(query['model']==train['outputs'],'query readonly model is exact training product')
    need(train['source']==query['source'],'same original program in training/query')
    need(len(train['inputs'])==len(query['inputs'])==1,'one selected context at a time')
    need(train['inputs'][0]['root']!=query['inputs'][0]['root'],'distinct training/query contexts')

def development(panel,records,budget):
    need(len(records)==27,'all nine inner people times three arms before any targets')
    keys={(r['packet']['inner_person'],r['packet']['arm']) for r in records}
    held=records[0]['packet']['person'];expected={(p,a) for p in PEOPLE if p!=held for a in ARMS}
    need(keys==expected,'complete distinct inner person-arm roster')
    predicted={}
    for r in records:
        paired_lifetime(r['train'],r['query']);predicted[(r['packet']['inner_person'],r['packet']['arm'])]=prediction(r['query'],3300,budget)
    # No target callback has run before complete artifact admission above.
    from .packets import inner_target
    scores={a:{} for a in ARMS}
    for r in records:
        p=r['packet'];key=(p['inner_person'],p['arm'])
        scores[p['arm']][p['inner_person']]=correlation(inner_target(panel,p),predicted[key])['mean']
    return {'score':macro([scores['representation'][p] for p in PEOPLE if p!=held]),
       'all_arm_person_means':scores,'targets':'training partition only','outer_targets_opened':False}

def collect(records,protocol,budget):
    expected={(role,p,a) for role in ROLES for p in PEOPLE for a in ARMS}
    need(len(records)==120 and {(r['role'],r['person'],r['arm']) for r in records}==expected,
         'all four roles, ten people and three arms required before scoring')
    admitted={}
    identities={}
    for r in records:
        paired_lifetime(r['train'],r['query'])
        need(r['protocol_id']==digest(protocol),'exact full protocol')
        key=(r['role'],r['person'],r['arm'])
        casekey=(r['role'],r['person'])
        if casekey in identities:need(identities[casekey]==r['method_id'],'same code/config across all three arms')
        identities[casekey]=r['method_id']
        admitted[key]=prediction(r['query'],200,budget)
    return admitted

def grade(panel,records,protocol,budget):
    admitted=collect(records,protocol,budget);scores={role:{a:{} for a in ARMS} for role in ROLES};reliability={}
    for person in PEOPLE:
        target=panel.outer_target(person);mean=target['mean'].reshape(200,1700)
        for role in ROLES:
            for arm in ARMS:scores[role][arm][person]=correlation(mean,admitted[(role,person,arm)])
        rel=correlation(target['half_odd'].reshape(200,1700),target['half_even'].reshape(200,1700))
        reliability[person]={'raw':rel['raw'],'mean':None if rel['constant_target'] or rel['constant_prediction'] else rel['mean']}
    result={}
    for role in ROLES:
        means={a:macro([scores[role][a][p]['mean'] for p in PEOPLE]) for a in ARMS}
        effects={}
        for control in ('low_level','response_permuted'):
            by={p:None if scores[role]['representation'][p]['mean'] is None or scores[role][control][p]['mean'] is None
                else scores[role]['representation'][p]['mean']-scores[role][control][p]['mean'] for p in PEOPLE}
            effects[control]={'by_person':by,'mean':macro(list(by.values()))}
        result[role]={'participant_coordinate_results':scores[role],'primary_equal_person_mean':means,'paired_controls':effects}
    return {'schema':'neural056_complete_grade_v1','protocol_id':digest(protocol),'roles':result,
      'split_half_reliability':reliability,'correction_applied':False,'all_final_blocks':120,
      'conditions_are_not_new_benchmarks':True,'population_scope':'ten exposed people conditional on200shared concepts',
      'historical_score_reproduction':False,'scientifically_qualified':False,
      'source_note':'Original endpoint is retained; native numerical/environment/reference qualifications remain external.'}


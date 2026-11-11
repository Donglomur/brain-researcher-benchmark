"""Full-panel identities and finite development before outer refit."""
from collections import Counter
import hashlib
from .core import need,digest
PEOPLE=tuple('sub-'+str(i).zfill(2) for i in range(1,11))
ARMS=('representation','low_level','response_permuted')
ROLES=('reference_fixed','reference_tuned','F','I')
SHAPE=(200,17,100)
ALPHAS=(0.0001,0.01,1.0,100.0,10000.0)

def validate_roster(roster):
    need(roster.get('schema')=='neural056_roster_v1','original roster schema')
    train=roster['train'];test=roster['test']
    need(len(train)==16540 and len(test)==200,'all images required')
    for rows,n in ((train,16540),(test,200)):
        need(all(type(x)is dict and set(x)=={'image_id','concept_id'} for x in rows),'exact identity rows')
        need(len({x['image_id'] for x in rows})==n,'unique image identities')
    groups=Counter(x['concept_id'] for x in train)
    need(len(groups)==1654 and set(groups.values())=={10},'1654 complete ten-exemplar concepts')
    need(len({x['concept_id'] for x in test})==200 and not(set(groups)&{x['concept_id'] for x in test}),'disjoint unseen concepts')
    need(not({x['image_id'] for x in train}&{x['image_id'] for x in test}),'disjoint images')
    # Recompute the predecessor's exact opaque-ID development rule.
    token=lambda s:hashlib.sha256(('NEURAL056/v1/development/'+s).encode()).hexdigest()[:24]
    dev=set(sorted(groups,key=lambda c:(token(c),c))[:330])
    di=[i for i,x in enumerate(train) if x['concept_id'] in dev]
    fi=[i for i,x in enumerate(train) if x['concept_id'] not in dev]
    need(roster['development_indices']==di and roster['fit_indices']==fi,'exact original 330/1324 concept partition')
    expected=[{'held_person':p,'training_people':[s for s in PEOPLE if s!=p],
               'inner_person_folds':[{'held':q,'fit':[s for s in PEOPLE if s not in(p,q)]} for q in PEOPLE if q!=p]} for p in PEOPLE]
    need(roster['folds']==expected,'all ten outer and nine inner folds')
    return roster

def permutation(concepts, expected_groups):
    groups={}
    for i,c in enumerate(concepts):groups.setdefault(c,[]).append(i)
    order=sorted(groups)
    need(len(order)==expected_groups and expected_groups>=2 and all(len(x)==10 for x in groups.values()),'complete concept groups')
    mapping=[None]*len(concepts)
    for j,c in enumerate(order):
        for a,b in zip(groups[c],groups[order[(j+1)%len(order)]]):mapping[a]=b
    need(all(i!=j for i,j in enumerate(mapping)) and len(set(mapping))==len(mapping),'whole-group derangement')
    return mapping

def compile_programme(roster, design_id, trials, nonce):
    validate_roster(roster);need(type(trials)is int and 1<=trials<=8,'finite equal F/I trial count')
    need(type(nonce)is bytes and len(nonce)==32,'operator-only alias seed')
    token=lambda value:hashlib.sha256(nonce+str(value).encode()).hexdigest()
    cases=[]
    for p in PEOPLE:
        cases.append({'person':p,'case_id':token(('outer',p)),'training_people':[x for x in PEOPLE if x!=p],
          'inner':[{'held':q,'training_people':[x for x in PEOPLE if x not in(p,q)],
                    'context_id':token(('inner',p,q))} for q in PEOPLE if q!=p],
          'arms':{a:token(('arm',p,a)) for a in ARMS},
          'matched_rng_seed':int(token(('rng',p))[:8],16)})
    return {'schema':'neural056_complete_protocol_v1','design_id':design_id,'roster_id':digest(roster),
      'cases':cases,'roles':list(ROLES),'arms':list(ARMS),'candidate_trials':trials,
      'reference_alphas':list(ALPHAS),'inner_image_count':3300,'fit_image_count':13240,
      'refit_image_count':16540,'outer_image_count':200,'coordinate_count':1700,
      'outputs_per_role':30,'total_final_blocks':120,
      'reference_inner_jobs':10*9*3*len(ALPHAS),
      'candidate_inner_jobs':2*10*9*3*trials,
      'final_fit_predict_jobs':4*10*3,
      'investigator_contexts':10*3*(9*trials+1),
      'provider_calls':'one frozen authoring call plus at most R per fresh investigator context',
      'external_fit_predict_processes':2*(10*9*3*len(ALPHAS)+2*10*9*3*trials+4*10*3),
      'all_jobs_are_one_canonical_task':True,'new_benchmarks':0}

def choose(trials):
    """Common winner for all arms. Missing scores refuse; stable earliest tie."""
    need(type(trials)is list and len(trials)>0,'nonempty complete development roster')
    for row in trials:
        need(type(row['score'])in(int,float) and row['score']==row['score'] and -1<=row['score']<=1,
             'undefined or nonfinite development selection')
    return max(range(len(trials)),key=lambda j:(trials[j]['score'],-j))


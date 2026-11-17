"""One-corpus exposure, animal-disjoint folds and explicit prediction clocks."""
from reward_common import need, finite_number, object_sha256, unique_records
from observations import CONDITIONS

ENDPOINT_CLOCK={'L':'cue','C':'cue','Qminus':'cue','F':'cue','M':'cue','V':'cue',
                'R':'consumption','O':'known_omission'}
ALLOWED_FEATURES={'B','condition_descriptor','cue_descriptor','elapsed_conditioning_seconds',
                  'past_cue_count','past_delivered_reward_count','past_omission_count','past_lick_count',
                  'past_neural_summary','past_freezing_summary','past_motion_summary',
                  'reward_identity','outcome_known','consumption_onset_descriptor'}


def public_case(case,features):
    """Project an explicit allowlist, never strip a few known answer fields."""
    endpoint=case['endpoint'];clock=ENDPOINT_CLOCK[endpoint]
    need(case['prediction_clock']==clock,'Endpoint information clock')
    public={'case_id':case['case_id'],'endpoint':endpoint,'prediction_clock':clock,'features':{}}
    for f in features:
        need(set(f)=={'name','value','available_at','source_kind'},'Feature provenance')
        need(f['name'] in ALLOWED_FEATURES,'Forbidden or unregistered feature')
        need(f['name'] not in public['features'],'Duplicate feature')
        available=finite_number(f['available_at']);query=finite_number(case['prediction_time'])
        if f['name'] in ('B','condition_descriptor','cue_descriptor','reward_identity','outcome_known','consumption_onset_descriptor'):
            need(available<=query,'Current descriptor boundary')
        else:need(available<query,'Strict past history')
        need(f['source_kind'] in ('prequery_observation','training_fit','current_descriptor'),'Unregistered feature source kind')
        if f['name'] in ('reward_identity','outcome_known','consumption_onset_descriptor'):
            need(endpoint in ('R','O'),'Current outcome only at outcome-origin clock')
        need(f['source_kind'] not in ('current_target','future_target','whole_animal_normalization',
                                      'test_fitted_preprocessing'),'Target-derived feature')
        public['features'][f['name']]=f['value']
    if endpoint in ('L','Qminus'):need(public['features'].get('B')==case['B'],'Known pre-cue count')
    if endpoint in ('C','R','O','V'):
        public['prediction_times']=case['times'];public['prediction_window']=case['window']
    return public


def check_fold(registry,fold):
    rows=unique_records(registry,['animal_id']);keys={k[0] for k in rows}
    sets={r:set(fold[r]) for r in ('train','validation','test')}
    need(all(len(fold[r])==len(sets[r]) for r in sets),'Unique fold membership')
    need(not any(sets[a]&sets[b] for a,b in [('train','test'),('train','validation'),('validation','test')]),
         'Animal-disjoint fit, selection and test')
    need(set.union(*sets.values())<=keys,'Verified biological registry')
    aliases={}
    for role,members in sets.items():
        for aid in members:
            for alias in rows[(aid,)]['source_aliases']:
                need(alias not in aliases or aliases[alias]==role,'Source alias crosses partition')
                aliases[alias]=role
    if fold['type']=='held_schedule':
        held=set(fold['held_conditions']);need(held,'Held schedule set')
        need(all(rows[(a,)]['condition'] in held for a in sets['test']),'Test schedule support')
        need(all(rows[(a,)]['condition'] not in held for a in sets['train']|sets['validation']),'Held schedule leakage')
    else:need(fold['type']=='held_animal','Declared extrapolation type')
    return {'fold_sha256':object_sha256(fold),'animal_disjoint':True,'source_alias_disjoint':True}


def exposure_status(ledger,actor,corpus,requested_claim):
    events=[e for e in ledger if e['actor']==actor and e['corpus']==corpus]
    exposed=any(e['kind'] in ('paper','author_code','reproduction','public_data','protected_targets') for e in events)
    if requested_claim=='confirmatory':
        need(not exposed,'Cross-track corpus exposure forbids protected claim for same actor')
        need(any(e['kind']=='custodian_independent_replication' for e in events),'Protected replication absent')
    return {'actor':actor,'corpus':corpus,'prior_exposure':events,
            'claim':'exploratory' if exposed or requested_claim!='confirmatory' else 'requires_remaining_gates',
            'independent_datasets_added':0,'scientific_qualification':False}


def paired_access_plan(common_public_pins,author_code_pins,budget,actor_a,actor_b):
    need(actor_a!=actor_b,'Independent A/B contexts')
    need(common_public_pins and author_code_pins,'Paired data/paper vs code source views')
    return {'A':{'actor':actor_a,'public_pins':common_public_pins,'ordinary_author_code':[],'budget':budget},
            'B':{'actor':actor_b,'public_pins':common_public_pins,'ordinary_author_code':author_code_pins,'budget':budget},
            'contrast':'B minus A across paired task instances and independent agent seeds',
            'same_corpus':True,'required_receipts':['source commitment','access trace','termination','output commitment'],
            'execution_authority':False,'qualification':False}

"""Precommitted scientific query universe, horizons and availability ledger."""
import copy
from reward_common import need,integer,object_sha256,unique_records
from observations import CONDITIONS,D_CONDITIONS
from provenance import digest

HORIZONS={c:(12 if c=='60s-50percent' else 32 if c=='60s-10percent' else 3 if c.startswith('FC-') else 8)
          for c in CONDITIONS}
HORIZON_CONTRACT={'id':'accepted_documented_session_horizons_v2','limits':HORIZONS,
                 'accepted_population_contract_sha256':'3283bd4e67f62d4d0990fc4bef01151f155e20b3e565d396b4a6865aaf7ff46f',
                 'trials':'all source-observed trials, including first exposures; no learned/outcome trims',
                 'session_order':'custodian documented chronology, not rank among surviving recordings'}
AVAILABILITY_POLICY={'id':'source_availability_v2','allowed_reasons':[
    'source_trial_record_absent','missing_count_window','invalid_count_support','missing_video_or_calibration',
    'missing_native_target_support','not_consumed','incomplete_interval','no_observed_response_sample',
    'modality_absent','retrospective_preprocessing_cannot_satisfy_prospective_information_boundary'],
    'forbidden_exclusions':['nonlearning','negative_signed_D','weak_DA','late_onset','candidate_failure'],
    'score_interpretation':'available observations under a fixed source mask; incomplete full-source support is disclosed'}
KEYS=('animal_id','condition','session','session_ordinal','trial_id','trial_ordinal','endpoint')


def endpoints(kind,condition,neural):
    if kind=='CS_plus':
        need(not condition.startswith('FC-'),'Appetitive cue source condition')
        out=['L']+(['C','R'] if neural else [])
        if neural and condition in ('60s-50percent','60s-10percent'):out.append('O')
        return out
    if kind=='CS_minus':
        need(condition=='60s-CSminus','CS minus source condition');return ['Qminus']
    if kind=='milk':
        need(condition=='600s-bgdmilk','Milk source condition');return ['CONSUMPTION_CONTEXT']
    need(kind=='shock' and condition.startswith('FC-'),'Aversive event condition')
    return ['F','M']+(['V'] if neural else [])


def population_manifest(registry):
    expected={};paired={};bo={}
    for a in registry:
        aid=a['animal_id'];c=a['condition'];neural=a['neural_designated']
        ep=['F','M','V'] if c.startswith('FC-') else ['L']
        if c=='60s-CSminus':ep.append('Qminus')
        if neural and not c.startswith('FC-'):
            ep+=['C','R'];paired.setdefault(c,[]).append(aid)
            if c in ('60s-50percent','60s-10percent'):ep.append('O')
        if not neural:bo.setdefault(c,[]).append(aid)
        for name in ep:expected.setdefault(name+':'+c,[]).append(aid)
    return {'expected_animals_by_endpoint_condition':{k:sorted(v) for k,v in expected.items()},
            'paired_animals_by_condition':{k:sorted(v) for k,v in paired.items()},
            'behavior_only_animals_by_condition':{k:sorted(v) for k,v in bo.items()}}


def source_inventory(registry):
    """Use complete source metadata, not an inventory inferred from scored rows."""
    animals=unique_records(registry,['animal_id'])
    need({a['condition'] for a in animals.values()}==set(CONDITIONS),'Full13 source registry')
    records=[];session_order=[]
    for a in animals.values():
        aid=a['animal_id'];condition=a['condition'];neural=a['neural_designated']
        need(type(neural) is bool and (not neural or condition in D_CONDITIONS),'Source modality designation')
        need(type(a.get('documented_sessions')) is list,'Complete documented source-session registry required')
        sessions=unique_records(a['documented_sessions'],['session_number']);ordinals=[]
        for s in sessions.values():
            integer(s['session_number'],'source session number',1);ordinal=integer(s['ordinal'],'documented session ordinal',1)
            ordinals.append(ordinal);pin=s['source_pin']
            need(set(pin)=={'bytes','sha256'},'Source session asset pin');integer(pin['bytes'],'source bytes',1);digest(pin['sha256'])
            session_order.append({'animal_id':aid,'condition':condition,'session':s['session_number'],
                                  'session_ordinal':ordinal,'source_pin':pin})
            trials=unique_records(s['trials'],['trial_id']);trial_ord=[]
            for t in trials.values():
                integer(t['ordinal'],'source trial ordinal',1);trial_ord.append(t['ordinal'])
                need(type(t['trial_id']) is str and t['trial_id'] and type(t['delivered']) is bool,'Source trial identity/delivery')
                for ep in endpoints(t['kind'],condition,neural):
                    key=dict(zip(KEYS,(aid,condition,s['session_number'],ordinal,t['trial_id'],t['ordinal'],ep)))
                    reason=None;status='eligible_pending'
                    if ordinal>HORIZONS[condition]:status='out_of_horizon';reason='beyond_documented_session_horizon'
                    elif ep=='R' and not t['delivered']:status='inapplicable';reason='omission_has_no_reward_endpoint'
                    elif ep=='O' and t['delivered']:status='inapplicable';reason='delivered_trial_has_no_omission_endpoint'
                    elif ep=='CONSUMPTION_CONTEXT':status='inapplicable';reason='context_diagnostic_has_no_registered_prediction_target'
                    records.append(dict(key,case_id=object_sha256(key),kind=t['kind'],delivered=t['delivered'],
                                        source_pin=pin,behavior_only_designated=not neural,status=status,reason=reason))
            need(sorted(trial_ord)==list(range(1,len(trial_ord)+1)),'Complete source trial order; no selective trimming')
        need(sorted(ordinals)==list(range(1,len(ordinals)+1)),'Complete documented session order, including unavailable recordings')
    records=sorted(records,key=lambda r:tuple(r[k] for k in KEYS));unique_records(records,['case_id'])
    return {'schema':'reward_source_query_inventory_v2','source_registry_sha256':object_sha256(registry),
            'horizon_contract':copy.deepcopy(HORIZON_CONTRACT),
            'session_order':sorted(session_order,key=lambda r:(r['animal_id'],r['session_ordinal'])),'records':records,
            'populations':population_manifest(registry)}


def finish_support(inventory,records):
    expected=unique_records(inventory['records'],['case_id']);actual=unique_records(records,['case_id'])
    need(set(expected)==set(actual),'Entire source query universe retained')
    for key,r in actual.items():
        original=expected[key];fixed=[k for k in original if k not in ('status','reason')]
        need(all(r[k]==original[k] for k in fixed),'Stable source query identity and chronology')
        if original['status']!='eligible_pending':
            need(r['status']==original['status'] and r['reason']==original['reason'],'Immutable source horizon/applicability mask')
        else:
            need(r['status'] in ('available','source_unavailable'),'Declared eligible-case availability')
            need((r['status']=='available' and r['reason'] is None) or
                 (r['status']=='source_unavailable' and r['reason'] in AVAILABILITY_POLICY['allowed_reasons']),
                 'Source-grounded preregistered availability reason')
    return {'schema':'reward_support_manifest_v2','source_inventory':copy.deepcopy(inventory),
            'source_inventory_sha256':object_sha256(inventory),'availability_policy':copy.deepcopy(AVAILABILITY_POLICY),
            'records':copy.deepcopy(records)}


def commit_support(manifest,source_commit_sha256):
    """Trusted controller calls before candidate predictions, never after scoring."""
    digest(source_commit_sha256)
    validate_support(manifest)
    return {'schema':'reward_support_precommit_v2','support_manifest_sha256':object_sha256(manifest),
            'source_commit_sha256':source_commit_sha256,'before_candidate_prediction':True,
            'horizon_contract_sha256':object_sha256(HORIZON_CONTRACT)}


def validate_support(manifest):
    need(manifest['schema']=='reward_support_manifest_v2','Required full support manifest')
    inventory=manifest['source_inventory'];need(inventory['schema']=='reward_source_query_inventory_v2','Inventory schema')
    need(manifest['source_inventory_sha256']==object_sha256(inventory),'Immutable source universe')
    need(inventory['horizon_contract']==HORIZON_CONTRACT,'Exact accepted session/trial horizon')
    need(manifest['availability_policy']==AVAILABILITY_POLICY,'Exact source availability policy')
    order=unique_records(inventory['session_order'],['animal_id','session'])
    for r in inventory['records']:
        integer(r['trial_ordinal'],'source trial ordinal',1)
        key=tuple(r[k] for k in KEYS);need(r['case_id']==object_sha256(dict(zip(KEYS,key))),'Stable source case key')
        s=order[(r['animal_id'],r['session'])]
        need(r['condition']==s['condition'] and r['session_ordinal']==s['session_ordinal'] and r['source_pin']==s['source_pin'],
             'Documented source session ordering and pin')
        outside=r['session_ordinal']>HORIZONS[r['condition']]
        need((r['status']=='out_of_horizon')==outside,'No out-of-horizon source query admission')
        if not outside:
            inapplicable=(r['endpoint']=='R' and not r['delivered']) or (r['endpoint']=='O' and r['delivered']) or r['endpoint']=='CONSUMPTION_CONTEXT'
            need((r['status']=='inapplicable')==inapplicable,'Source endpoint applicability')
    # finish_support performs immutable row-by-row comparison and mask validation.
    reconstructed=finish_support(inventory,manifest['records'])
    need(reconstructed==manifest,'Exact support schema and no undeclared selection fields')
    return True


def validate_scoring_support(cases,registered,manifest):
    validate_support(manifest);commit=registered['support_precommit']
    need(set(commit)=={'schema','support_manifest_sha256','source_commit_sha256','before_candidate_prediction','horizon_contract_sha256'},
         'Typed preregistered support commitment')
    need(commit['schema']=='reward_support_precommit_v2' and commit['before_candidate_prediction'] is True,'Pre-prediction support registration')
    digest(commit['source_commit_sha256'])
    need(commit['support_manifest_sha256']==object_sha256(manifest) and
         commit['horizon_contract_sha256']==object_sha256(HORIZON_CONTRACT),'Precommitted support and horizon identity')
    populations=manifest['source_inventory']['populations']
    for name,values in populations.items():need(registered[name]==values,'Source-bound population registration: '+name)
    rows=unique_records(manifest['records'],['case_id']);observed=unique_records(cases,['case_id'])
    need(set(observed)=={k for k,r in rows.items() if r['status']=='available'},
         'All and only registered available cases; candidate omission is not source missingness')
    for key,c in observed.items():
        r=rows[key]
        need(all(c[k]==r[k] for k in KEYS),'Score case source identity/horizon mismatch')
        need(c['behavior_only_designated']==r['behavior_only_designated'],'Immutable source modality designation')
        need(c['support_row_sha256']==object_sha256(r),'Scoring case bound to availability row')
    return manifest['records']


def coverage(records,endpoint,conditions,expected_animals,behavior_only=False):
    selected=[r for r in records if r['endpoint']==endpoint and r['condition'] in conditions and
              r['animal_id'] in expected_animals and (not behavior_only or r['behavior_only_designated'])]
    counts={s:sum(r['status']==s for r in selected) for s in ('available','source_unavailable','out_of_horizon','inapplicable')}
    available=sorted({r['animal_id'] for r in selected if r['status']=='available'})
    eligible=sorted({r['animal_id'] for r in selected if r['status'] in ('available','source_unavailable')})
    source_full=bool(expected_animals) and set(eligible)==set(expected_animals) and counts['source_unavailable']==0
    return {'expected_source_cases':len(selected),'eligible_cases':counts['available']+counts['source_unavailable'],
            'available_and_scored_cases':counts['available'],'eligible_unavailable_cases':counts['source_unavailable'],
            'out_of_horizon_cases':counts['out_of_horizon'],'inapplicable_cases':counts['inapplicable'],
            'expected_animals':sorted(expected_animals),'eligible_animals':eligible,'observed_animals':available,
            'full_source_support':source_full,'population_observed':bool(expected_animals) and set(available)==set(expected_animals),
            'missingness':[{'case_id':r['case_id'],'animal_id':r['animal_id'],'session':r['session'],
                           'trial_id':r['trial_id'],'status':r['status'],'reason':r['reason']} for r in selected if r['status']!='available']}

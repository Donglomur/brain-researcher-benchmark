"""Trusted target-last scoring: submitted predictions never supply their scores."""
import math
import random
import statistics as st
from reward_common import need, integer, finite_number, unique_records, native_integral
from observations import CONDITIONS

WEIGHT_SETS={
 "primary_paired_appetitive":["60s","600s","3600s","60s-few","60s-50percent","60s-10percent"],
 "all_appetitive_behavior":list(CONDITIONS[:11]),
 "wholly_behavior_only":["30s","300s","60s-few-ctxt","60s-CSminus","600s-bgdmilk"],
 "behavior_only_subgroups_of_mixed":["60s","600s","60s-few","60s-50percent"],
 "aversive_each_endpoint_separately":["FC-45s","FC-135s"],
 "omission_neural":["60s-50percent","60s-10percent"]}



def nb2_log_probability(a, mu, kappa):
    integer(a,'anticipatory count');mu=finite_number(mu,'NB mean');kappa=finite_number(kappa,'NB dispersion')
    need(mu>0 and kappa>0,'Strictly positive NB parameters')
    logden=math.log(kappa+mu)
    value=(math.lgamma(a+kappa)-math.lgamma(kappa)-math.lgamma(a+1)
           +kappa*(math.log(kappa)-logden)+a*(math.log(mu)-logden))
    need(math.isfinite(value),'Finite NB log probability')
    return value


def continuous_log_density(y,mean,scale,family='normal',df=None):
    y,mean,scale=[finite_number(x) for x in (y,mean,scale)]
    need(scale>0,'Positive density scale');z=(y-mean)/scale
    if family=='normal':value=-.5*math.log(2*math.pi)-math.log(scale)-.5*z*z
    else:
        need(family=='student_t','Registered density family');df=finite_number(df,'t df');need(df>0,'Positive df')
        value=math.lgamma((df+1)/2)-math.lgamma(df/2)-.5*math.log(df*math.pi)-math.log(scale)-(df+1)/2*math.log1p(z*z/df)
    need(math.isfinite(value),'Finite density');return value


def score_prediction(case,prediction):
    endpoint=case['endpoint'];target=case['target']
    if endpoint in ('L','Qminus'):
        need(set(prediction)=={'mu','kappa'},'Exact count prediction schema')
        integer(case['B'],'permitted baseline count');integer(target,'anticipatory target')
        value=nb2_log_probability(target,prediction['mu'],prediction['kappa'])
        return {'score':value,'D':target-case['B'],'predicted_D':prediction['mu']-case['B']}
    if endpoint in ('C','R','O'):
        need(set(prediction)=={'mean','scale'},'Exact neural density prediction schema')
        times=case['times'];means=prediction['mean'];scales=prediction['scale']
        need(len(times)==len(target)==len(means)==len(scales),'Native prediction shape')
        logp=[continuous_log_density(y,m,s,case['density_family'],case.get('density_df'))
              for y,m,s in zip(target,means,scales)]
        integral=native_integral(times,logp,*case['window'],case['max_gap'],case.get('valid'))
        need(integral['covered_seconds']>0,'No observed target support')
        return {'score':integral['mean'],'covered_seconds':integral['covered_seconds'],
                'requested_seconds':integral['requested_seconds']}
    if endpoint in ('F','M'):
        need(set(prediction)=={'mean'},'Exact behavioral point prediction schema')
        y=finite_number(target);mu=finite_number(prediction['mean'])
        need(mu>=0 and y>=0,'Nonnegative physical response')
        if endpoint=='F':need(mu<=1 and y<=1,'Freezing fractions')
        return {'score':-(mu-y)**2,'target_units':'fraction' if endpoint=='F' else 'pixels_per_frame'}
    if endpoint=='V':
        need(set(prediction)=={'mean'},'Exact aversive neural prediction schema')
        need(len(prediction['mean'])==len(target)==len(case['times']),'Aversive native grid')
        errors=[(finite_number(a)-finite_number(b))**2 for a,b in zip(target,prediction['mean'])]
        integral=native_integral(case['times'],errors,*case['window'],case['max_gap'],case.get('valid'))
        need(integral['covered_seconds']>0,'Aversive support')
        truth_auc=native_integral(case['times'],target,*case['window'],case['max_gap'],case.get('valid'))['integral']
        prediction_auc=native_integral(case['times'],prediction['mean'],*case['window'],case['max_gap'],case.get('valid'))['integral']
        return {'score':-integral['mean'],'covered_seconds':integral['covered_seconds'],
                'requested_seconds':integral['requested_seconds'],'raw_native_target_auc':truth_auc,
                'raw_native_prediction_auc':prediction_auc,'raw_native_auc_error':prediction_auc-truth_auc}
    raise ValueError('Unknown endpoint')


def percentile(values,q):
    values=sorted(values);pos=(len(values)-1)*q;a=int(pos);b=min(a+1,len(values)-1)
    return values[a]+(values[b]-values[a])*(pos-a)


def animal_interval(values,replicates=1000,alpha=.05,seed=0):
    need(type(replicates) is int and 1<=replicates<=100000,'Bounded bootstrap')
    need(0<alpha<1,'Interval level')
    if len(values)<2:return {'status':'insufficient_animals','interval':None}
    rng=random.Random(seed);draws=[st.mean(rng.choice(values) for _ in values) for _ in range(replicates)]
    return {'status':'computed','interval':[percentile(draws,alpha/2),percentile(draws,1-alpha/2)],
            'resampling_unit':'whole_animal_paired_difference','conditional_on_frozen_fit':True,
            'replicates':replicates,'alpha':alpha,'seed':seed}


def score_cases(cases,predictions,registered,bootstrap=1000,support_manifest=None):
    """Scores on a fixed source mask, with the full scientific support ledger.

    Candidate omissions are errors. Source-unavailable eligible observations stay
    in denominators and claim limits, but do not invalidate every available-case
    descriptive score. `complete` always means full registered source support.
    """
    from support import validate_scoring_support,coverage
    need(support_manifest is not None,'Precommitted full support manifest is required')
    need(registered['conditions']==list(CONDITIONS),'Full13 condition contract')
    need(registered['weight_sets']==WEIGHT_SETS,'Fixed accepted weights; no posthoc narrowing')
    support_rows=validate_scoring_support(cases,registered,support_manifest)
    case_map=unique_records(cases,['case_id']);pred_map=unique_records(predictions,['case_id'])
    need(set(case_map)==set(pred_map),'Exact prediction keys, no omitted available cases')
    need(registered.get('baseline_selected_without_outer_targets') is True,'Frozen training-selected baseline')
    integer(bootstrap,'bootstrap replicates',1);need(bootstrap<=100000,'Bounded engineering/scientific registration')
    rows=[];animals={};animal_metadata={}
    for key,c in case_map.items():
        p=pred_map[key];need(set(p)=={'case_id','prediction'},'No self-reported score or target')
        allowed=(WEIGHT_SETS['all_appetitive_behavior'] if c['endpoint']=='L' else
                 ['60s-CSminus'] if c['endpoint']=='Qminus' else
                 WEIGHT_SETS['primary_paired_appetitive'] if c['endpoint'] in ('C','R') else
                 WEIGHT_SETS['omission_neural'] if c['endpoint']=='O' else
                 WEIGHT_SETS['aversive_each_endpoint_separately'] if c['endpoint'] in ('F','M','V') else [])
        need(c['condition'] in allowed,'Endpoint condition applicability')
        need(c['prediction_clock']==c['allowed_prediction_clock'],'Declared endpoint clock')
        identity=(c['condition'],c['animal_id']);meta=c['behavior_only_designated']
        need(type(meta) is bool,'Source modality designation')
        if identity in animal_metadata:need(animal_metadata[identity]==meta,'Consistent animal designation')
        animal_metadata[identity]=meta
        got=score_prediction(c,p['prediction']);base=score_prediction(c,c['baseline_prediction'])
        row={'case_id':key[0],'condition':c['condition'],'animal_id':c['animal_id'],'endpoint':c['endpoint'],
             'candidate':got,'baseline':base,'gain':got['score']-base['score']}
        rows.append(row);animals.setdefault((c['endpoint'],*identity),[]).append(row['gain'])
    animal_rows=[{'endpoint':ep,'condition':cond,'animal_id':aid,'gain':st.mean(v),'n_available_trials':len(v),
                 'behavior_only_designated':animal_metadata[(cond,aid)]} for (ep,cond,aid),v in sorted(animals.items())]
    expected_map=registered['expected_animals_by_endpoint_condition']
    def condition_result(ep,cond,expected,behavior_only=False,seed=0):
        chosen=[r for r in animal_rows if r['endpoint']==ep and r['condition']==cond and r['animal_id'] in expected
                and (not behavior_only or r['behavior_only_designated'])]
        values=[r['gain'] for r in chosen];actual={r['animal_id'] for r in chosen}
        need(len(expected)==len(set(expected)),'Unique registered biological population')
        cov=coverage(support_rows,ep,[cond],expected,behavior_only)
        pop_complete=bool(expected) and actual==set(expected)
        interval=(animal_interval(values,bootstrap,registered.get('interval_alpha',.05),seed) if values else
                  {'status':'no_available_animals','interval':None})
        interval['conditional_on_registered_source_mask']=True
        margin_key=('L_BO' if behavior_only else ep)+':'+cond
        margin=registered.get('noninferiority_margins',{}).get(margin_key)
        if margin is not None:need(finite_number(margin)>=0,'Nonnegative registered margin')
        available_pass=(interval['interval'][0]>-margin) if pop_complete and margin is not None and interval['interval'] is not None else None
        return {'endpoint':ep,'condition':cond,'n_observed_animals':len(values),'observed_animal_mean_gain':st.mean(values) if values else None,
                'gain':st.mean(values) if pop_complete else None,'population_complete':pop_complete,
                'available_case_score_complete':pop_complete,'full_source_support':cov['full_source_support'],
                'complete':pop_complete and cov['full_source_support'],'coverage':cov,'interval':interval,
                'margin_key':margin_key,'noninferiority_margin':margin,
                'available_case_noninferiority_passed':available_pass,
                'noninferiority_passed':available_pass if cov['full_source_support'] else None}
    effects=[]
    for i,(key,expected) in enumerate(sorted(expected_map.items())):
        ep,cond=key.split(':',1);effects.append(condition_result(ep,cond,expected,seed=registered.get('seed',0)+i))
    def fixed_summary(ep,conditions,behavior_only=False):
        results={};means={}
        for i,cond in enumerate(conditions):
            expected=(registered['behavior_only_animals_by_condition'].get(cond,[]) if behavior_only else
                      expected_map.get(ep+':'+cond,[]))
            result=condition_result(ep,cond,expected,behavior_only,registered.get('seed',0)+i+100)
            results[cond]=result
            if result['population_complete']:means[cond]=result['gain']
        pop_complete=len(means)==len(conditions)
        source_full=all(v['full_source_support'] for v in results.values())
        return {'endpoint':ep,'conditions':conditions,'condition_means':means,'condition_results':results,
                'population_complete':pop_complete,'available_case_score_complete':pop_complete,
                'full_source_support':source_full,'complete':pop_complete and source_full,
                'gain':st.mean(means.values()) if pop_complete else None,'renormalized_missing_conditions_or_animals':False,
                'score_scope':'registered available cases; full-source support is reported separately'}
    sets=registered['weight_sets'];summaries={}
    summaries['all_appetitive_behavior']=fixed_summary('L',sets['all_appetitive_behavior'])
    summaries['wholly_behavior_only']=fixed_summary('L',sets['wholly_behavior_only'])
    summaries['mixed_behavior_only']=fixed_summary('L',sets['behavior_only_subgroups_of_mixed'],True)
    summaries['reward_neural']=fixed_summary('R',sets['primary_paired_appetitive'])
    summaries['omission_neural']=fixed_summary('O',sets['omission_neural'])
    summaries['negative_cue_diagnostic']=fixed_summary('Qminus',['60s-CSminus'])
    for ep in ('F','M','V'):summaries['aversive_'+ep]=fixed_summary(ep,sets['aversive_each_endpoint_separately'])
    paired={};groups=[]
    for cond in sets['primary_paired_appetitive']:
        L={r['animal_id']:r['gain'] for r in animal_rows if r['condition']==cond and r['endpoint']=='L'}
        C={r['animal_id']:r['gain'] for r in animal_rows if r['condition']==cond and r['endpoint']=='C'}
        expected=registered['paired_animals_by_condition'].get(cond,[])
        need(expected==expected_map.get('C:'+cond,[]),'Paired neural population binding')
        available=[a for a in expected if a in L and a in C]
        pop_complete=bool(expected) and set(available)==set(expected) and set(C)==set(expected)
        cov={ep:coverage(support_rows,ep,[cond],expected) for ep in ('L','C')}
        source_full=all(v['full_source_support'] for v in cov.values())
        values=[.5*L[a]+.5*C[a] for a in available];groups.append(values)
        paired[cond]={'expected':expected,'available':available,'population_complete':pop_complete,
                      'full_source_support':source_full,'complete':pop_complete and source_full,'coverage':cov,
                      'gain':st.mean(values) if pop_complete else None}
    primary_pop_complete=all(x['population_complete'] for x in paired.values())
    primary_full=all(x['full_source_support'] for x in paired.values())
    primary_interval={'status':'insufficient_available_animals_or_missing_population','interval':None,
                      'conditional_on_registered_source_mask':True}
    if primary_pop_complete and all(len(g)>=2 for g in groups):
        rng=random.Random(registered.get('seed',0)+1000)
        draws=[st.mean(st.mean(rng.choice(g) for _ in g) for g in groups) for _ in range(bootstrap)]
        alpha=registered.get('interval_alpha',.05)
        primary_interval.update(status='computed',interval=[percentile(draws,alpha/2),percentile(draws,1-alpha/2)],
                                resampling_unit='paired animal within each fixed condition',conditional_on_frozen_fit=True,
                                replicates=bootstrap,alpha=alpha)
    primary={'name':'paired_appetitive_cue','condition_results':paired,'population_complete':primary_pop_complete,
             'available_case_score_complete':primary_pop_complete,'full_source_support':primary_full,
             'complete':primary_pop_complete and primary_full,
             'gain':st.mean(x['gain'] for x in paired.values()) if primary_pop_complete else None,'interval':primary_interval,
             'score_scope':'registered available cases; eligible unavailability is retained, not treated as candidate failure'}
    byanimal=[]
    for key,expected in sorted(expected_map.items()):
        ep,cond=key.split(':',1)
        for aid in expected:byanimal.append({'animal_id':aid,'condition':cond,'endpoint':ep,
                                             'coverage':coverage(support_rows,ep,[cond],[aid])})
    q=summaries['negative_cue_diagnostic'];L=summaries['all_appetitive_behavior']
    return {'schema':'reward_improvement_score_v2','case_scores':rows,'animal_scores':animal_rows,
            'condition_effects':effects,'separate_summaries':summaries,'primary':primary,
            'support':{'precommit':registered['support_precommit'],'records':support_rows,'per_animal_endpoint':byanimal,
                       'expected_source_cases':len(support_rows),'scored_available_cases':len(cases),
                       'eligible_unavailable_cases':sum(r['status']=='source_unavailable' for r in support_rows),
                       'out_of_horizon_cases':sum(r['status']=='out_of_horizon' for r in support_rows),
                       'inapplicable_cases':sum(r['status']=='inapplicable' for r in support_rows),
                       'candidate_available_case_omissions':0},
            'claim_limits':{'paired_cue_available_case_score_supported':primary_pop_complete,
                            'paired_cue_full_source_support':primary['complete'],
                            'both_cue_types_available_case_score_supported':L['available_case_score_complete'] and q['available_case_score_complete'],
                            'both_cue_types_full_source_support':L['complete'] and q['complete'],
                            'complete13_condition_full_source_support':all(v['complete'] for v in summaries.values()) and primary['complete'],
                            'consumption_identity_trajectory_improvement':'not registered; CS+ score alone cannot support it',
                            'missing_observations':'Describe scores conditional on frozen availability mask; do not generalize silently to unavailable observations'},
            'claim_status':'exploratory_only','scientific_qualification':False,
            'remaining_gates':['registered practical margins and multiplicity','protected replication',
                               'full source and physiological information boundary','independent reference qualification']}


def flatten_numeric(value,path=()):
    """Keep every numeric leaf keyed by its complete object/list position."""
    if type(value) in (int,float):return {path:finite_number(value)}
    if type(value) is dict:
        out={}
        for k,v in value.items():out.update(flatten_numeric(v,path+(k,)))
        return out
    if type(value) is list:
        out={}
        for i,v in enumerate(value):out.update(flatten_numeric(v,path+(i,)))
        return out
    return {}


def score_panels(reference,candidate,expected_ids,tolerances=None,artifacts=None,artifact_validators=None):
    """Exact166-key coverage, candidate-sensitive numeric discrepancies.

    Tolerances are an independently registered input, never invented here.
    Non-numeric leaves must match as well, including scientific identity keys.
    """
    ref=unique_records(reference,['panel_id']);cand=unique_records(candidate,['panel_id'])
    need(set(ref)=={(x,) for x in expected_ids},'Complete protected reference status ledger')
    need(set(cand)==set(ref),'All166 candidate panels required, including unavailable obligations')
    results=[]
    def structure(v):
        if type(v) in (int,float):return '<number>'
        if isinstance(v,dict):return {k:structure(x) for k,x in v.items()}
        if isinstance(v,list):return [structure(x) for x in v]
        return v
    for key,r in ref.items():
        c=cand[key]
        if r['status']!='computed':
            results.append({'panel_id':key[0],'status':'required-unscorable','reference_reason':r.get('reason'),
                            'unsupported_candidate_completion':c.get('status')=='computed'});continue
        need(c.get('status')=='computed','Candidate omitted computable panel')
        from provenance import validate_panel_provenance
        provenance=validate_panel_provenance(r,c,artifacts,artifact_validators)
        need(structure(r['value'])==structure(c['value']),'Exact scientific keys, units and categorical support')
        a=flatten_numeric(r['value']);b=flatten_numeric(c['value']);need(set(a)==set(b),'Exact numeric support')
        errors=[abs(a[k]-b[k]) for k in a]
        tol=(tolerances or {}).get(key[0]);passed=None
        if tol is not None:
            absolute=finite_number(tol['absolute']);relative=finite_number(tol['relative']);need(min(absolute,relative)>=0,'Positive tolerances')
            passed=all(abs(a[k]-b[k])<=absolute+relative*abs(a[k]) for k in a)
        results.append({'panel_id':key[0],'status':'compared','numeric_leaves':len(a),
                        'max_absolute_error':max(errors,default=0),'rmse':math.sqrt(st.mean(e*e for e in errors)) if errors else 0,
                        'calibrated_tolerance_pass':passed,'scientific_provenance':provenance})
    return {'panels':results,'expected_count':len(expected_ids),'scientific_qualification':False,
            'full_completion':False,'completion_reason':'All scientific gates and calibrated reference still required'}


def score_reproduction_submission(reference,collected,expected_ids,tolerances=None,artifact_validators=None):
    """Collected is created by the trusted stopped-output bundle collector."""
    return score_panels(reference,collected['panels'],expected_ids,tolerances,
                        collected['artifacts'],artifact_validators)


def score_improvement_submission(private,collected,bootstrap=1000):
    """Closed-controller grade entry point; support cannot be omitted en route."""
    need({'cases','registered','support_manifest','source_commit_sha256'}<=set(private),'Complete evaluator grade package')
    need(private['registered']['support_precommit']['source_commit_sha256']==private['source_commit_sha256'],
         'Availability precommit bound to the trusted run source commitment')
    if type(collected) is dict:
        need(set(collected)=={'schema','predictions'} and collected['schema']=='reward_improvement_submission_v2',
             'Typed improvement prediction submission')
        predictions=collected['predictions']
    else:predictions=collected
    need(type(predictions) is list,'Prediction rows, never reported score')
    return score_cases(private['cases'],predictions,private['registered'],bootstrap,private['support_manifest'])

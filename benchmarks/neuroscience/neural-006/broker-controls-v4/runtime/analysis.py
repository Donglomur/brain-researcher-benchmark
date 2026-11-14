"""Exact complete-cohort arithmetic. No cached predictions stand in for a refitted replicate."""
import math
import statistics
from protocol import TARGETS, ARMS, ACTIVE, RESERVE, need, finite

BASE=('offer','exp_valence','exp_arousal','trialLocal','trialGlobal','abs_A')
FORMULAS={'N':BASE,'R':BASE+('abs_R',),'V':BASE+('abs_V',),'J':BASE+('abs_R','abs_V')}

def agree(actual,expected,reason):
    need(finite(actual) and finite(expected) and abs(actual-expected)<=1e-8+1e-9*abs(expected),reason)

def audit_reference(case,reference):
    """Original base-R QR rule plus independent arithmetic/status reconstruction; no optimizer refit."""
    need(reference['schema']=='neural006-reference-v1' and reference['participant']==case['participant'],'reference_identity')
    need(reference['status'] in ('complete','incomplete'),'reference_status')
    train=case['training'];query=case['query'];groups={r['participant'] for r in train}
    need(len(groups)==len(case['clusters']) and len(train)>1,'reference_training_support')
    scaling={}
    for feature in BASE+('abs_R','abs_V'):
        center=math.fsum(r[feature] for r in train)/len(train)
        spread=math.sqrt(math.fsum((r[feature]-center)**2 for r in train)/(len(train)-1))
        constant=spread==0
        if constant:spread=1.0
        observed=reference['scaling'][feature]
        agree(observed['center'],center,'training_scaling_center');agree(observed['scale'],spread,'training_scaling_sd')
        need(observed['constant'] is constant,'training_scaling_constant');scaling[feature]=(center,spread)
    keys=[r['source_row'] for r in query];need(reference['source_rows']==keys,'reference_source_rows')
    calls=0;statuses=[]
    def array(value):
        return value if type(value) is list else [value]
    def finite_tree(value):
        if type(value) is dict:return all(finite_tree(v) for v in value.values())
        if type(value) is list:return all(finite_tree(v) for v in value)
        return finite(value)
    for target in TARGETS:
        by_group={p:[r[target] for r in train if r['participant']==p] for p in groups}
        prior=math.fsum(math.fsum(v)/len(v) for v in by_group.values())/len(groups)
        variance=math.fsum(math.fsum((y-prior)**2 for y in v)/len(v) for v in by_group.values())/len(groups)
        entry=reference['results'][target];norm=entry['normalizer']
        agree(norm['training_equal_person_mean'],prior,'reference_training_mean')
        agree(norm['training_equal_person_variance'],variance,'reference_training_variance');need(variance>0,'training_variance_positive')
        mean=entry['arms']['mean'];need(mean['status']=='fit_completed' and len(mean['prediction'])==len(query),'mean_prediction_shape')
        for prediction in mean['prediction']:agree(prediction,prior,'mean_prediction')
        for arm,features in FORMULAS.items():
            fitted=entry['arms'][arm];d=fitted['diagnostic'];terms=['(Intercept)',*features];status=d['status']
            need(status in ('fit_completed','rank_deficient','fit_error','postfit_error','nonconverged',
                'prediction_failed','invalid_fit_structure') and fitted['status']==status,'reference_fit_status')
            statuses.append(status)
            need(d['n']==len(train) and d['people']==len(groups) and d['columns']==len(terms),'reference_planned_support')
            need(d['REML'] is False and d['fixed_terms']==terms,'reference_model_structure')
            need(''.join(d['formula'].split())==target+'~'+'+'.join(features)+'+(1|sub)','exact_random_intercept_formula')
            independent=reference['independent_design_audits'][target][arm]
            need(independent['method']=='manual_cbind_base_R_qr' and independent['tolerance']==1e-10 and
                independent['columns']==len(terms) and independent['terms']==terms,'original_independent_design_rule')
            rank=independent['rank'];need(type(rank) is int and 0<=rank<=len(terms) and d['rank']==rank,'independent_fixed_design_rank')
            need(type(d['fit_called']) is bool and d['fit_called']==(status!='rank_deficient'),'rank_call_policy')
            calls+=int(d['fit_called']);need((rank<len(terms))==(status=='rank_deficient'),'rank_disposition')
            if status in ('fit_error','postfit_error'):
                need(type(d['error']) is str and bool(d['error']),'fit_failure_evidence')
            if status in ('fit_completed','nonconverged','prediction_failed','invalid_fit_structure','postfit_error'):
                codes=array(d['optimizer_code'])
                convergence=array(d['convergence_messages'])
                need(all(type(v) is str for v in convergence),'convergence_messages')
                conv_ok=bool(codes) and all(finite(v) and v==0 for v in codes) and all(
                    v=="boundary (singular) fit: see help('isSingular')" for v in convergence)
                if status=='nonconverged':need(not conv_ok,'nonconvergence_has_failed_diagnostic')
                if status=='prediction_failed':
                    need(conv_ok and type(d['prediction_error']) is str and bool(d['prediction_error']),'prediction_failure_evidence')
                if status=='invalid_fit_structure':
                    invalid=(d['observed_nobs']!=len(train) or d['observed_people']!=len(groups) or
                        d['observed_fixed_columns']!=len(terms) or len(array(d['dropped_coefficients']))>0 or
                        not finite_tree(d['coefficients']) or not finite_tree(d['covariance']))
                    need(invalid,'invalid_fit_structure_has_evidence')
            if status!='fit_completed':
                need(fitted['prediction'] is None,'failed_fit_has_no_predictions')
                continue
            need(conv_ok and d['observed_nobs']==len(train) and d['observed_people']==len(groups) and
                d['observed_fixed_columns']==len(terms) and array(d['dropped_coefficients'])==[],'successful_fit_structure')
            need(type(d['singular']) is bool and finite(d['random_intercept_sd']) and d['random_intercept_sd']>=0 and
                finite(d['sigma']) and d['sigma']>0,'successful_variance_parameters')
            b=d['coefficients'];need(set(b)==set(terms) and all(finite(v) for v in b.values()),'reference_coefficients')
            need(len(fitted['prediction'])==len(query),'reference_prediction_shape')
            for row,prediction in zip(query,fitted['prediction']):
                expected=b['(Intercept)']+math.fsum(b[name]*(row[name]-scaling[name][0])/scaling[name][1] for name in features)
                agree(prediction,expected,'manual_fixed_effect_prediction')
            covariance=d['covariance'];need(d['covariance_terms']==terms and len(covariance)==len(terms) and
                all(len(row)==len(terms) and all(finite(v) for v in row) for row in covariance),'covariance_shape')
            for i in range(len(terms)):
                for j in range(len(terms)):agree(covariance[i][j],covariance[j][i],'covariance_symmetry')
            if arm=='J':
                i=terms.index('abs_V');j=terms.index('abs_R');v=covariance[i][i]+covariance[j][j]-2*covariance[i][j]
                need(v>=0,'coefficient_variance_nonnegative');contrast=reference['predictive_coefficient_contrasts'][target]
                agree(contrast['contrast'],b['abs_V']-b['abs_R'],'coefficient_contrast')
                agree(contrast['variance'],v,'coefficient_full_covariance');agree(contrast['standard_error'],math.sqrt(v),'coefficient_se')
    need(reference['actual_fit_calls']==calls,'reference_fit_call_consistency')
    complete=all(status=='fit_completed' for status in statuses)
    need((reference['status']=='complete')==complete,'reference_complete_disposition')
    return {'status':'passed_arithmetic' if complete else 'passed_incomplete_diagnostic_audit',
        'optimizer_independently_refitted':False,'private_query_targets_used':False,
        'fixed_design_rank_method':'original_manual_cbind_base_R_qr_tol_1e-10'}

def predictions(value, case):
    need(type(value) is dict and set(value)=={'status','predictions'}, 'prediction_fields')
    need(value['status']=='complete', 'candidate_abstained_or_failed')
    rows = value['predictions']
    keys = [row['source_row'] for row in case['query']]
    need(type(rows) is list and len(rows)==len(keys), 'complete_queries')
    table = {}
    for row in rows:
        need(type(row) is list and len(row)==3 and type(row[0]) is int, 'prediction_row')
        need(row[0] in keys and row[0] not in table and all(finite(v) for v in row[1:]), 'prediction_values')
        table[row[0]] = row[1:]
    need(set(table)==set(keys), 'prediction_membership')
    return table

def score_case(case, truth, reference, candidates):
    need(reference['schema']=='neural006-reference-v1' and reference['participant']==case['participant'], 'reference_identity')
    need(reference['status']=='complete', 'reference_incomplete_no_subset_score')
    keys = [r['source_row'] for r in case['query']]
    need(reference['source_rows']==keys, 'reference_query_order')
    need(set(candidates)=={'frozen_program','adaptive_investigation'}, 'matched_candidate_modes')
    parsed = {mode:predictions(value,case) for mode,value in candidates.items()}
    scores = {}
    for component_index,target in enumerate(TARGETS):
        r = reference['results'][target]
        variance = r['normalizer']['training_equal_person_variance']
        need(finite(variance) and variance > 0, 'training_variance')
        vectors = {}
        for arm in ARMS:
            arm_result = r['arms'][arm]
            need(arm_result['status']=='fit_completed' and len(arm_result['prediction'])==len(keys), 'reference_arm_complete')
            vectors[arm] = dict(zip(keys,arm_result['prediction']))
        vectors.update({mode:{key:row[component_index] for key,row in table.items()} for mode,table in parsed.items()})
        component = {}
        for name,vector in vectors.items():
            need(all(finite(v) for v in vector.values()), 'finite_predictions')
            squared = [(truth[key][target]-vector[key])**2 for key in truth]
            absolute = [abs(truth[key][target]-vector[key]) for key in truth]
            mse = math.fsum(squared)/len(squared);mae = math.fsum(absolute)/len(absolute)
            normalized = mse/variance
            need(all(finite(v) for v in (mse,mae,normalized)), 'unsupported_derived_numerics')
            component[name]={'mse':mse,'mae':mae,'normalized_mse':normalized}
        scores[target]=component
    return {'participant':case['participant'],'paired_scored_rows':len(truth),'components':scores}

def aggregate(plan, replicate, records):
    people = ACTIVE if plan['stage']=='development_lopo33' else tuple(sorted(RESERVE))
    need([r['participant'] for r in records]==list(people), 'full_ordered_cohort_required')
    need(all(r['status']=='complete' for r in records), 'failed_case_prevents_macro')
    weights = [replicate['draw'].count(p) if replicate['kind']=='bootstrap' else 1 for p in people]
    denominator = sum(weights);need(denominator>0, 'positive_participant_mass')
    macro = {};contrasts = {};loss_descriptive = {}
    for target in TARGETS:
        macro[target] = {};loss_descriptive[target] = {}
        for arm in ARMS+('frozen_program','adaptive_investigation'):
            macro[target][arm] = {metric:math.fsum(weight*r['score']['components'][target][arm][metric]
                for weight,r in zip(weights,records))/denominator for metric in ('mse','mae','normalized_mse')}
            values=[r['score']['components'][target][arm]['normalized_mse']
                    for weight,r in zip(weights,records) for _ in range(weight)]
            need(values and all(finite(v) for v in values),'finite_participant_normalized_losses')
            loss_descriptive[target][arm]={'n':len(values),'mean':math.fsum(values)/len(values),
                'median':statistics.median(values),'minimum':min(values),'maximum':max(values)}
        losses={arm:item['normalized_mse'] for arm,item in macro[target].items()}
        contrast={'reward_increment':losses['V']-losses['J'],'valence_increment':losses['R']-losses['J'],
            'valence_vs_reward':losses['R']-losses['V'],'joint_vs_nuisance':losses['N']-losses['J'],
            'adaptive_minus_frozen_gain':losses['frozen_program']-losses['adaptive_investigation']}
        for mode in ('frozen_program','adaptive_investigation'):
            for arm in ARMS:
                contrast[arm+'_minus_'+mode]=losses[arm]-losses[mode]
        need(all(finite(v) for v in contrast.values()), 'finite_contrasts')
        contrasts[target]=contrast
    contrasts['P3b_minus_FRN_valence_vs_reward']=contrasts['P3b_offer']['valence_vs_reward']-contrasts['FRN_N2_offer']['valence_vs_reward']
    paired={};descriptive={}
    for target in TARGETS:
        rows=[]
        for person,weight,record in zip(people,weights,records):
            loss={name:record['score']['components'][target][name]['normalized_mse']
                  for name in ARMS+('frozen_program','adaptive_investigation')}
            values={'reward_increment':loss['V']-loss['J'],'valence_increment':loss['R']-loss['J'],
                'valence_vs_reward':loss['R']-loss['V'],'joint_vs_nuisance':loss['N']-loss['J'],
                'adaptive_minus_frozen_gain':loss['frozen_program']-loss['adaptive_investigation']}
            rows.append({'participant':person,'multiplicity':weight,'values':values})
        paired[target]=rows
    paired['P3b_minus_FRN']=[{'participant':person,'multiplicity':weight,'values':{
        'valence_vs_reward':paired['P3b_offer'][i]['values']['valence_vs_reward']-
                           paired['FRN_N2_offer'][i]['values']['valence_vs_reward']}}
        for i,(person,weight) in enumerate(zip(people,weights))]
    for component,rows in paired.items():
        descriptive[component]={}
        for name in rows[0]['values']:
            values=[row['values'][name] for row in rows for _ in range(row['multiplicity'])]
            need(values and all(finite(v) for v in values),'finite_paired_values')
            descriptive[component][name]={'n':len(values),'mean':math.fsum(values)/len(values),
                'median':statistics.median(values),'minimum':min(values),'maximum':max(values)}
    return {'status':'complete','kind':replicate['kind'],'replicate':replicate['replicate'],
        'macro':macro,'contrasts':contrasts,'participant_weights':dict(zip(people,weights)),
        'paired_participant_contrasts':paired,'descriptive':descriptive,
        'participant_normalized_loss_descriptive':loss_descriptive,
        'descriptive_support':'participant copies under bootstrap multiplicity; original distinct-person rows all retained',
        'population_calibration_established':False,'paper_reproduction':False}

def summarize_replicates(plan, schedule, outputs):
    need(len(outputs)==len(schedule), 'complete_replicate_inventory')
    for expected,actual in zip(schedule,outputs):
        need((actual['kind'],actual['replicate'])==(expected['kind'],expected['replicate']), 'replicate_identity')
    failures=[{'kind':r['kind'],'replicate':r['replicate'],'status':r['status']} for r in outputs if r['status']!='complete']
    # Linear empirical quantiles are descriptive sensitivity bands, with no nominal coverage claim.
    bands=None
    bootstrap=[row for row in outputs if row['kind']=='bootstrap']
    if not failures and bootstrap:
        quantiles=plan['resampling']['bootstrap']['quantiles']
        def band(values):
            values=sorted(values);result=[]
            for probability in quantiles:
                position=(len(values)-1)*probability;lower=math.floor(position);upper=math.ceil(position)
                value=values[lower]+(values[upper]-values[lower])*(position-lower)
                need(finite(value),'finite_sensitivity_band');result.append(value)
            return {'quantiles':quantiles,'values':result,'coverage':'unestablished'}
        bands={target:{name:band([row['contrasts'][target][name] for row in bootstrap])
            for name in bootstrap[0]['contrasts'][target]} for target in TARGETS}
        bands['P3b_minus_FRN_valence_vs_reward']=band([row['contrasts']['P3b_minus_FRN_valence_vs_reward'] for row in bootstrap])
    return {'status':'complete' if not failures else 'incomplete','replicates':outputs,
        'failed_replicates':failures,'calibrated_intervals':None,'p_values':None,
        'participant_resampling_sensitivity_bands':bands,
        'exchangeability':plan['resampling']['trajectory_permutation'],
        'development_tuning':plan['development_tuning'],
        'interpretation':'Uncalibrated participant-resampling sensitivity and within-declared-block participant alignment diagnostics only.',
        'original_full_41_task_complete':False,'scientifically_qualified':False}

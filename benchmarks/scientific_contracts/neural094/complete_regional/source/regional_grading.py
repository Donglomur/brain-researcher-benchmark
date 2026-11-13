"""Target-last complete grading with unchanged whole primary and independent reductions.

All required predictions/references are reauthenticated and numerically admitted
before opening the first private mapping. Query targets are never candidate
tools. No callback accepts predictions, labels, scores or fitted model states.
"""
import math
from regional_custody import need, read, pin, encoded, parsed, write
from regional_controller import ClosedBatch, _BATCH_KEY, prediction_rows, reference_rows, REFERENCES, REF
from regional_scope import bundles, bundle_key
import regional_mode_contrasts as modes


def expected_keys(scope):
    for b in bundles(scope):
        for mode in ('F','I'):
            yield mode+':'+b['key'], b['ordinal'], False
        if b['kind'] == 'regional' or b['side'] == 'joint':
            yield 'reference:'+b['key'], b['ordinal'], True


def _rows(batch, key, is_reference, budget, core, np, *, submitted=False):
    item = batch.bank[key]
    raw = read(batch.root,item['path'],{k:item[k] for k in ('bytes','sha256')},budget)
    values = (reference_rows if is_reference else prediction_rows)(raw,item['tokens'])
    if submitted:
        return values
    if is_reference:
        return {name:core.probabilities(np.asarray(rows,dtype=np.float64),np) for name,rows in values.items()}
    return core.probabilities(np.asarray(values,dtype=np.float64),np)


def admit_complete(batch, budget, modules, np):
    """Actual complete admission loop; no private data argument or callback."""
    need(type(batch) is ClosedBatch and batch._key is _BATCH_KEY, 'Actual completed producer capability')
    modules['score_adapter'].roster_contract(batch.cohort.roster)
    expected = set()
    for key, ordinal, is_reference in expected_keys(batch.scope):
        need(key in batch.bank and key not in expected, 'Every planned candidate/reference output')
        expected.add(key)
        need(batch.bank[key]['tokens'] == batch.cohort.roster[ordinal-1]['query_tokens'],
             'Exact full original query support before protected access')
        _rows(batch,key,is_reference,budget,modules['metric_core'],np)
    need(set(batch.bank) == expected and batch.closure['all_producers_closed'] is True
         and batch.closure['all_predictions_admitted'] is True and batch.closure['query_target_reads'] == 0,
         'No extra output, early target use, or missing native closure')
    return len(expected)


def _whole_records(batch, mode, targets, budget, mods, arithmetic, catalog, np):
    adapter, core = mods['score_adapter'],mods['metric_core']
    rows = []; independent = arithmetic.WholePrimary(catalog,mode)
    candidate_sha = batch.sources[mode]['sha256']
    for row,y in zip(batch.cohort.roster,targets,strict=True):
        ordinal = row['ordinal']; tokens = row['query_tokens']
        context_key = mode+':'+bundle_key('whole',ordinal,side='context')
        joint_key = mode+':'+bundle_key('whole',ordinal,side='joint')
        reference_key = 'reference:'+bundle_key('whole',ordinal,side='joint')
        supplied = {'candidate:context_wheel':_rows(batch,context_key,False,budget,core,np,submitted=True),
                    'candidate:context_wheel_neural':_rows(batch,joint_key,False,budget,core,np,submitted=True)}
        supplied.update({'trusted:'+name:p for name,p in _rows(batch,reference_key,True,budget,core,np,submitted=True).items()})
        independent.add_session(ordinal,tokens,y,{name:{'tokens':tokens,'probabilities':p}
                                                for name,p in supplied.items()})
        matrices={name:core.probabilities(np.asarray(p,dtype=np.float64),np) for name,p in supplied.items()}
        matrices['analytic:uniform'] = np.full((len(y),3),1/3,dtype=np.float64)
        losses = {name:adapter.trial_losses(p,y,np) for name,p in matrices.items()}
        metrics = {name:adapter.metrics(p,y,core,np) for name,p in matrices.items()}
        metrics['analytic:uniform']['natural_log_loss'] = core.extended(math.log(3))
        contrasts = {name:adapter.paired_effect(losses[left],losses[right],core,np)
                     for name,(left,right) in adapter.CONTRASTS.items()}
        rows.append({'schema':'neural094-choice-session-score-v1','status':'complete_paired_choice_session',
                     **{k:row[k] for k in ('ordinal','session','mouse','session_token')},
                     'candidate_sha256':candidate_sha,'reference_sha256':REF,'query_rows':len(y),
                     'class_counts':[int(v) for v in np.bincount(y,minlength=3)],'class_order':['right','NoGo','left'],
                     'metrics':metrics,'contrasts':contrasts,'public_manifest_commitments':row['public_manifests'],
                     'private_mapping_commitment':row['private_mapping'],
                     'prediction_commitments':{'context_wheel':batch.bank[context_key],
                                               'context_wheel_neural':batch.bank[joint_key]},
                     'trusted_reference_commitment':batch.bank[reference_key],
                     'candidate_models_deserialized_by_grader':False,
                     'case_removal_for_probability_or_performance':False})
    original = adapter.aggregate_reports(rows,batch.cohort.roster,candidate_sha,REF,core)
    check = independent.finish()
    disagreements = []
    for name,value in original['contrasts'].items():
        try:
            arithmetic.assert_engineering_equivalent(value,check['metrics']['contrasts'][name])
        except ValueError as exc:
            disagreements.append({'contrast':name,'original':value,'independent':check['metrics']['contrasts'][name],
                                  'reason':str(exc)})
    # The original whole primary remains the reported primary even when an
    # independent numerical/sign disagreement needs investigation. No tolerance
    # converts a zero/sign discrepancy into scientific agreement.
    return {'original':original,'independent':check,'arithmetic_disagreements':disagreements,
            'numerical_parity_qualified':False}


def _regional_oracle(tokens,y,views,mods,arithmetic,np):
    """Actual original metric kernels versus independently computed trial bank."""
    adapter,core = mods['score_adapter'],mods['metric_core']
    independent = arithmetic.paired_trial_metrics(tokens,y,views,regional=True)['metrics']
    matrices = {name:core.probabilities(np.asarray(v['probabilities'],dtype=np.float64),np) for name,v in views.items()}
    losses = {name:adapter.trial_losses(p,y,np) for name,p in matrices.items()}
    observations = []
    for name,p in matrices.items():
        actual = adapter.metrics(p,y,core,np)
        for metric in arithmetic.ABSOLUTE:
            value = actual[metric] if metric == 'natural_log_loss' else core.extended(actual[metric])
            try:
                arithmetic.assert_engineering_equivalent(value,independent['absolute'][name][metric])
            except ValueError as exc:
                observations.append({'field':name+'/'+metric,'original':value,
                    'independent':independent['absolute'][name][metric],'reason':str(exc)})
    for name,(metric,left,right,sign) in arithmetic._contrast_specs(True).items():
        if metric == 'natural_log_loss':
            value = adapter.paired_effect(losses[left],losses[right],core,np)
        else:
            def per_trial(p):
                if metric == 'top1_accuracy':
                    return (np.argmax(p,axis=1)==y).astype(np.float64)
                return np.square(p-np.eye(3,dtype=np.float64)[y]).sum(axis=1)
            value = adapter.paired_effect(sign*per_trial(matrices[left]),sign*per_trial(matrices[right]),core,np)
        try:
            arithmetic.assert_engineering_equivalent(value,independent['contrasts'][name])
        except ValueError as exc:
            observations.append({'field':name,'original':value,'independent':independent['contrasts'][name],
                                  'reason':str(exc)})
    return observations


def grade_complete(batch, private_root, output_root, *, budget, modules, arithmetic, canonical_bytes, np):
    """Production entry; requires future exact stack, fixed source and fresh authority.

    No bootstrap/significance inference or scalar improvement reward is emitted.
    Large result streams are written per mode/pair under the same explicit budget.
    A failed output reservation retains failure and never changes the cohort.
    """
    need(np.__version__ == '2.2.6', 'Original numerical stack; no local substitute')
    return _admit_then_grade(batch,private_root,output_root,budget,modules,arithmetic,canonical_bytes,np)


def _admit_then_grade(batch,private_root,output_root,budget,modules,arithmetic,canonical_bytes,np):
    """Shared target-last path; an inert final grade leaf is a control only."""
    admitted = admit_complete(batch,budget,modules,np)
    return _grade_admitted(batch,private_root,output_root,budget,modules,arithmetic,canonical_bytes,np,admitted)


def _grade_admitted(batch,private_root,output_root,budget,modules,arithmetic,canonical_bytes,np,admitted):
    """Internal numerical/control seam; callers must use complete admission above."""
    catalog = arithmetic.catalog_from_canonical(canonical_bytes)
    targets = []
    for row in batch.cohort.roster:
        descriptor = row['private_mapping']
        raw = read(private_root,descriptor['path'],{k:descriptor[k] for k in ('bytes','sha256')},budget)
        targets.append(modules['score_adapter'].private_targets(raw,row,np))
    whole = {mode:_whole_records(batch,mode,targets,budget,modules,arithmetic,catalog,np) for mode in ('F','I')}
    whole_mode_sessions=[]
    for row,y in zip(batch.cohort.roster,targets,strict=True):
        views={}
        for mode in ('F','I'):
            for side,arm in (('left','context'),('right','joint')):
                views[mode+'_'+side]=_rows(batch,mode+':'+bundle_key('whole',row['ordinal'],side=arm),
                                          False,budget,modules['metric_core'],np,submitted=True)
        whole_mode_sessions.append({'ordinal':row['ordinal'],'mouse':row['mouse'],
                                    'contrasts':modes.trials(y,views,arithmetic)})
    whole_mode_mice=[{'mouse':mouse,'contrasts':modes.mean(
        [r['contrasts'] for r in whole_mode_sessions if r['mouse']==mouse],arithmetic)} for mouse in catalog.mice]
    whole_mode={'session_records':whole_mode_sessions,'mouse_records':whole_mode_mice,
                'contrasts':modes.mean([r['contrasts'] for r in whole_mode_mice],arithmetic),
                'left_is_context_right_is_joint':True,'interaction_is_candidate_context_dependent_diagnostic':True,
                'original_primary_unchanged':True,'causal_or_significance_claim':False}
    output_pins = []
    for mode in ('F','I'):
        def reports():
            for pair in range(2628):
                support = batch.scope.plan.pair(pair)
                reducer = arithmetic.RegionalPair(catalog,support,mode)
                disagreements = []
                for session in support['session_roster']:
                    if session['K'] == 0:
                        continue
                    ordinal = session['ordinal']; tokens = batch.cohort.roster[ordinal-1]['query_tokens']
                    y = targets[ordinal-1]
                    common = _rows(batch,'reference:'+bundle_key('whole',ordinal,side='joint'),True,
                                   budget,modules['metric_core'],np,submitted=True)['selected_context']
                    for seed in support['fixed_seeds']:
                        views = {'common_context':{'tokens':tokens,'probabilities':common}}
                        for side in ('left','right'):
                            key = bundle_key('regional',ordinal,pair=pair,seed=seed,side=side)
                            views['candidate_'+side] = {'tokens':tokens,'probabilities':
                                _rows(batch,mode+':'+key,False,budget,modules['metric_core'],np,submitted=True)}
                            refs = _rows(batch,'reference:'+key,True,budget,modules['metric_core'],np,submitted=True)
                            views['regional_reference_'+side] = {'tokens':tokens,'probabilities':refs['matched_joint_logistic']}
                        disagreements.extend({'ordinal':ordinal,'seed':seed,**d} for d in
                            _regional_oracle(tokens,y,views,modules,arithmetic,np))
                        reducer.add_seed(ordinal,seed,tokens,y,views)
                result = reducer.finish()
                # Keep arithmetic evidence beside the exact helper report so its
                # complete-pair schema remains byte-for-byte interpretable.
                name = f'{mode}-pair-{pair:04d}.json'
                descriptor = write(output_root,name,encoded({'report':result,'arithmetic_disagreements':disagreements}),budget)
                output_pins.append({'path':name,**descriptor})
                yield result
        # Draining this exact selector verifies all2628 reports including every
        # structurally unavailable cell; it does not filter by effect or p-value.
        for _ in arithmetic.iter_complete_pairs(catalog,reports(),mode=mode):
            pass
    for pair in range(2628):
        support=batch.scope.plan.pair(pair);observations={}
        for session in support['session_roster']:
            if session['K']==0:
                continue
            ordinal=session['ordinal'];y=targets[ordinal-1]
            for seed in support['fixed_seeds']:
                views={}
                for mode in ('F','I'):
                    for side in ('left','right'):
                        key=mode+':'+bundle_key('regional',ordinal,pair=pair,seed=seed,side=side)
                        views[mode+'_'+side]=_rows(batch,key,False,budget,modules['metric_core'],np,submitted=True)
                observations[ordinal,seed]=modes.trials(y,views,arithmetic)
        report=modes.regional_pair(support,observations,arithmetic)
        name=f'paired-strategy-{pair:04d}.json'
        output_pins.append({'path':name,**write(output_root,name,encoded(report),budget)})
    result = {'schema':'neural094_complete_regional_comparison_v1','whole_primary':whole,
              'whole_paired_strategy_diagnostics':whole_mode,
              'regional_reports':output_pins,'producer_closure':batch.closure,
              'predictions_admitted_before_private_mapping':admitted,'private_mapping_reads':39,
              'scope':{'sessions':39,'mice':10,'literal_labels':73,'pairs':2628,'seeds':5,'modes':['F','I']},
              'deployment_strategy_comparison':True,'equal_per_stage_model_access':False,
              'regional_difference_is_improvement_reward':False,'causal_or_significance_claim':False,
              'uncertainty':'descriptive support only; no bootstrap or population coverage claim',
              'native_qualification':False,'scientific_qualification':False,'benchmark_count_delta':0}
    write(output_root,'COMPLETE_REPORT.json',encoded(result),budget)
    return result

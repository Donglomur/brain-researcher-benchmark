"""Fixed094 true-choice references: public fit/validation only, then sealed inference.

No I/O or numerical imports. Dependencies are supplied by the future isolated
trusted worker. Fit accepts no query parameter; runtime must hide query access
until all four returned final states are saved and committed.
"""
import math
import warnings

C_VALUES = (0.01, 0.1, 1.0, 10.0)
REFERENCES = ('training_prior', 'selected_context', 'matched_context_logistic', 'matched_joint_logistic')
CLASS_ORDER = ('right', 'NoGo', 'left')
CONTEXT_COLUMNS = ('stimulus_left', 'stimulus_right', 'stimulus_difference',
    'stimulus_absolute_difference', 'stimulus_sum', 'stimulus_product', 'u',
    'u_squared', 'previous_stimulus_left', 'previous_stimulus_right', 'first_source_row')
VERSIONS = {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def menu():
    return ([{'family': 'training_prior'}]
            + [{'family': 'logistic', 'C': c} for c in C_VALUES]
            + [{'family': 'hist_gradient_boosting', 'max_leaf_nodes': leaf, 'l2_regularization': l2}
               for leaf in (7, 15) for l2 in (0.0, 1.0)])


def parameter_dict(recipe):
    if recipe == {'family': 'training_prior'}:
        return None
    if type(recipe) is dict and set(recipe) == {'family', 'C'} and recipe['family'] == 'logistic':
        need(type(recipe['C']) in (int, float) and recipe['C'] in C_VALUES, 'Exact four-C menu')
        # Pinned1.6.1 default dispatch with all3 classes is multinomial. Omit
        # deprecated multi_class; missing-class cases never reach this fit.
        return dict(penalty='l2', C=float(recipe['C']), solver='lbfgs', max_iter=2000, tol=1e-6,
                    fit_intercept=True, class_weight=None, warm_start=False, n_jobs=1, random_state=20261104)
    need(type(recipe) is dict and set(recipe) == {'family', 'max_leaf_nodes', 'l2_regularization'}
         and recipe['family'] == 'hist_gradient_boosting' and type(recipe['max_leaf_nodes']) is int
         and recipe['max_leaf_nodes'] in (7, 15) and type(recipe['l2_regularization']) in (int, float)
         and recipe['l2_regularization'] in (0, 1), 'Exact four-HGB menu')
    return dict(loss='log_loss', max_iter=200, learning_rate=.05,
        max_leaf_nodes=recipe['max_leaf_nodes'], min_samples_leaf=10,
        l2_regularization=float(recipe['l2_regularization']), early_stopping=False,
        random_state=20261104, categorical_features=None, class_weight=None, warm_start=False)


def stack_versions(versions):
    need(type(versions) is dict and versions == VERSIONS, 'Exact prospective pinned numerical stack')


def fields(values, expected, np):
    need(type(values) is dict and set(values) == set(expected), 'Exact native public fields')
    length = None
    for key, dtype in expected.items():
        value = values[key]
        need(type(value) is np.ndarray and value.ndim == 1 and value.dtype == np.dtype(dtype),
             'Exact native numeric vector dtype')
        if length is None:
            length = len(value)
        need(len(value) == length, 'Aligned complete native rows')
        if value.dtype.kind == 'f':
            need(bool(np.isfinite(value).all()), 'Finite native features')
    return length


def feature_blocks(packet, manifest, *, np, choice, validator, tick):
    """No labels used in feature construction; phase determines only strict file ABI."""
    validator.validate_manifest(manifest)
    need(manifest['arm'] == 'context_wheel_neural' and manifest['phase'] in ('fitval', 'query'),
         'Trusted reference uses exact joint public packet; context branch selects only allowed blocks')
    phase = manifest['phase']; n = len(manifest['case_tokens']); u = manifest['unit_count']
    expected = {'context.npz', 'wheel.npz', 'neural.npz', 'units.npz'} | ({'labels.npz'} if phase == 'fitval' else set())
    need(type(packet) is dict and set(packet) == expected and u >= 1, 'Complete fixed public packet, no private/query labels')
    context = packet['context.npz']; need(tuple(choice.CONTEXT_COLUMNS) == CONTEXT_COLUMNS, 'Exact11 allowed context columns')
    need(choice.validate_context(context, np=np) == n, 'Complete11-column source context')
    units = packet['units.npz']
    fields(units, {'unit': 'uint32', 'source_qc_code': 'uint8'}, np)
    need(len(units['unit']) == u and np.array_equal(units['unit'], np.arange(u, dtype=np.uint32))
         and bool(np.isin(units['source_qc_code'], [2, 3]).all()), 'Full dense source-QC2/3 unit roster')
    wheel = packet['wheel.npz']
    fields(wheel, {'trial_index': 'uint32', 'bin_id': 'uint8', 'within_bin_seconds': 'float64',
                  'position_relative_to_first_trial_sample': 'float64'}, np)
    need(bool((wheel['trial_index'] < n).all()) and bool((wheel['bin_id'] < 5).all())
         and bool((wheel['within_bin_seconds'] >= 0).all()), 'Authoritative trial/bin wheel membership')
    signed = np.empty((n, 5), dtype=np.float64); cursor = 0
    for trial in range(n):
        tick()
        for bin_id in range(5):
            start = cursor
            while cursor < len(wheel['trial_index']) and int(wheel['trial_index'][cursor]) == trial and int(wheel['bin_id'][cursor]) == bin_id:
                cursor += 1
            need(cursor - start >= 2, 'Complete unchanged wheel support: two observations per bin')
            offsets = wheel['within_bin_seconds'][start:cursor]
            need(bool((offsets[1:] > offsets[:-1]).all()), 'Preserved original within-bin wheel order')
            values = wheel['position_relative_to_first_trial_sample'][start:cursor]
            signed[trial, bin_id] = values[-1] - values[0]
    need(cursor == len(wheel['trial_index']), 'No extra, reordered or unconsumed wheel sample')
    absolute = np.abs(signed)
    X = np.column_stack([context[k] for k in CONTEXT_COLUMNS] + [signed[:, k] for k in range(5)]
                        + [absolute[:, k] for k in range(5)] + [absolute.sum(axis=1), absolute.max(axis=1)])
    neural = packet['neural.npz']
    fields(neural, {'trial_index': 'uint32', 'unit': 'uint32', 'bin_id': 'uint8', 'within_bin_seconds': 'float64'}, np)
    need(bool((neural['trial_index'] < n).all()) and bool((neural['unit'] < u).all())
         and bool((neural['bin_id'] < 5).all()) and bool((neural['within_bin_seconds'] >= 0).all()),
         'Complete source event aliases; bin_id is authoritative, no time rebinning')
    counts = np.zeros((n, u * 5), dtype=np.float64)
    tick()
    np.add.at(counts, (neural['trial_index'], neural['unit'].astype(np.int64) * 5 + neural['bin_id']), 1.)
    need(float(counts.sum()) == len(neural['trial_index']), 'Every event counted exactly once, including silent-unit columns')
    np.log1p(counts, out=counts)
    joint = np.column_stack((X, counts))
    need(X.shape == (n, 23) and joint.shape == (n, 23 + 5 * u)
         and bool(np.isfinite(X).all()) and bool(np.isfinite(joint).all()), 'Finite exact fixed feature geometry')
    return {'context': X, 'joint': joint, 'unit_ids': units['unit'].copy(),
            'unit_qc': units['source_qc_code'].copy(), 'phase': phase, 'case_tokens': list(manifest['case_tokens'])}


def scaler_fit(X, np):
    constant = np.all(X == X[0:1], axis=0); active = ~constant
    mean = np.zeros(X.shape[1], dtype=np.float64); scale = np.ones(X.shape[1], dtype=np.float64)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        if bool(active.any()):
            mean[active] = X[:, active].mean(axis=0)
            scale[active] = X[:, active].std(axis=0, ddof=0)
    need(bool(np.isfinite(mean).all()) and bool(np.isfinite(scale).all()) and bool((scale > 0).all()),
         'Finite fit-only population moments; exact constants retain zero mapping')
    return {'constant': constant.copy(), 'mean': mean, 'scale': scale}


def scaler_apply(X, state, np):
    need(X.ndim == 2 and X.shape[1] == len(state['mean']), 'Saved feature/scaler shape')
    Z = np.zeros(X.shape, dtype=np.float64); active = ~state['constant']
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        Z[:, active] = (X[:, active] - state['mean'][active]) / state['scale'][active]
    need(bool(np.isfinite(Z).all()), 'Finite transformed values; no query-adaptive scaling')
    return Z


def warning_evidence(caught, record, phase, ConvergenceWarning):
    rows = [{'category': w.category.__name__, 'message': str(w.message)[:2048],
             'truncated': len(str(w.message)) > 2048} for w in caught[:16]]
    record[phase + '_warnings'] = rows; record[phase + '_warning_count'] = len(caught)
    need(len(caught) <= 16, 'Bounded complete warning evidence')
    need(not any(issubclass(w.category, (ConvergenceWarning, RuntimeWarning)) for w in caught),
         'Nonconvergence or numerical RuntimeWarning refuses complete reference stage')


def probability_admission(p, rows, np):
    p = np.asarray(p)
    need(p.shape == (rows, 3) and p.dtype.kind == 'f' and bool(np.isfinite(p).all())
         and bool(((p >= 0) & (p <= 1)).all()), 'Finite complete3class output')
    p = np.array(p, dtype=np.float64, copy=True); sums = p.sum(axis=1)
    need(bool((np.abs(sums - 1) <= 1e-8).all()), 'Fixed probability sum tolerance; no clipping/floor')
    p /= sums[:, None]
    return p


def fitted_parameter_admission(model, family, features, np):
    need(np.array_equal(np.asarray(model.classes_), np.asarray([0, 1, 2])), 'All3 explicit fitted classes')
    if family == 'logistic':
        need(np.asarray(model.coef_).shape == (3, features) and np.asarray(model.intercept_).shape == (3,)
             and bool(np.isfinite(model.coef_).all()) and bool(np.isfinite(model.intercept_).all()),
             'Finite exact multinomial parameters')
        it = np.asarray(model.n_iter_)
        need(it.shape == (1,) and it.dtype.kind in 'iu' and bool(((it >= 0) & (it <= 2000)).all()),
             'Exact admitted logistic iteration metadata')
    else:
        need(type(model.n_iter_) is int and model.n_iter_ == 200 and model.do_early_stopping_ is False,
             'All200 declared HGB iterations, no implicit early stopping')
        need(bool(np.isfinite(model._baseline_prediction).all()) and len(model._predictors) == 200,
             'Finite fixed HGB baseline and all iteration states')
        for iteration in model._predictors:
            need(len(iteration) == 3, 'Three class trees per HGB iteration')
            for predictor in iteration:
                need(bool(np.isfinite(predictor.nodes['value']).all())
                     and bool(np.isfinite(predictor.nodes['num_threshold']).all()), 'Finite HGB leaf/threshold state')
        need(all(bool(np.isfinite(x).all()) for x in model._bin_mapper.bin_thresholds_), 'Finite fitted histogram cutpoints')


def fit_recipe(X, y, recipe, *, np, LogisticRegression, HistGradientBoostingClassifier,
               ConvergenceWarning, tick, counters, phase):
    """Fit only: no query or validation feature argument is accepted."""
    params = parameter_dict(recipe); tick()
    need(X.ndim == 2 and len(X) > 0 and X.shape[1] > 0 and X.dtype.kind == 'f'
         and bool(np.isfinite(X).all()) and y.shape == (len(X),) and y.dtype.kind in 'iu'
         and bool(np.isin(y, [0, 1, 2]).all()), 'Complete finite training-only data')
    counts = np.bincount(y, minlength=3); prior = (counts.astype(np.float64) + 1) / (len(y) + 3)
    record = {'phase': phase, 'recipe': dict(recipe), 'status': 'in_progress', 'training_rows': len(y),
              'features': X.shape[1], 'class_counts': [int(x) for x in counts], 'estimator_fit_attempted': False}
    counters.setdefault('records', []).append(record)
    try:
        missing = bool((counts == 0).any())
        if params is None or missing:
            record.update(status='completed',method='laplace_prior',fallback_for_missing_class=missing and params is not None,
                          estimator_fit_attempted=False)
            return {'kind': 'prior', 'prior': prior.copy(), 'recipe': dict(recipe), 'record': record, 'features': X.shape[1]}
        family = recipe['family']; scale = scaler_fit(X, np) if family == 'logistic' else None
        Z = scaler_apply(X, scale, np) if scale is not None else X
        cls = LogisticRegression if family == 'logistic' else HistGradientBoostingClassifier
        model = cls(**params); record['parameters'] = params; record['estimator_fit_attempted'] = True
        counters['estimator_fit_attempts'] = counters.get('estimator_fit_attempts', 0) + 1; tick()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                model.fit(Z, y)
                counters['estimator_fit_returns'] = counters.get('estimator_fit_returns', 0) + 1
            finally:
                warning_evidence(caught, record, 'fit', ConvergenceWarning)
        tick(); fitted_parameter_admission(model, family, X.shape[1], np)
        record.update(status='completed',method=family,fallback_for_missing_class=False)
        return {'kind': family, 'model': model, 'scaler': scale, 'recipe': dict(recipe),
                'record': record, 'features': X.shape[1]}
    except BaseException as exc:
        record.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:2048])
        raise


def predict_state(state, X, *, np, ConvergenceWarning, tick, counters, phase):
    tick(); need(X.ndim == 2 and len(X) > 0 and X.shape[1] == state['features']
                 and bool(np.isfinite(X).all()), 'Complete finite inference feature support')
    record = {'phase': phase, 'recipe': state['recipe'], 'rows': len(X), 'status': 'in_progress'}
    counters.setdefault('predictions', []).append(record)
    try:
        if state['kind'] == 'prior':
            p = np.broadcast_to(state['prior'], (len(X), 3)).copy()
        else:
            Z = scaler_apply(X, state['scaler'], np) if state['kind'] == 'logistic' else X
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    p = state['model'].predict_proba(Z)
                finally:
                    warning_evidence(caught, record, 'predict', ConvergenceWarning)
        tick(); p = probability_admission(p, len(X), np); record['status'] = 'completed'; return p
    except BaseException as exc:
        record.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:2048]); raise


def validation_loss(p, y, np):
    need(p.shape == (len(y), 3), 'Exact validation pairing')
    chosen = p[np.arange(len(y)), y]
    # Valid exact0 is not invalid/nonfinite probability; its objective is +inf.
    return math.inf if bool((chosen == 0).any()) else float(-np.log(chosen).mean())


def stable_choice(rows):
    need(type(rows) is list and rows and all(type(r['loss']) in (int, float)
         and not math.isnan(r['loss']) and r['loss'] >= 0 for r in rows), 'Complete valid menu objectives including infinity')
    winner = 0
    for i in range(1, len(rows)):
        if rows[i]['loss'] < rows[winner]['loss']:
            winner = i
    return dict(rows[winner]['recipe'])


def fit_references(fitval_packet, fitval_manifest, reference_sha256, *, versions, np, choice, validator,
                   LogisticRegression, HistGradientBoostingClassifier, ConvergenceWarning, tick, counters):
    """Public fit/validation only. No query arrays, targets, callback or path argument."""
    stack_versions(versions)
    need(type(reference_sha256) is str and len(reference_sha256) == 64
         and set(reference_sha256) <= set('0123456789abcdef'), 'Frozen reference source identity')
    need(fitval_manifest['phase'] == 'fitval', 'Query packet forbidden during reference fitting')
    blocks = feature_blocks(fitval_packet, fitval_manifest, np=np, choice=choice, validator=validator, tick=tick)
    labels = fitval_packet['labels.npz']; need(set(labels) == {'target'}, 'Only supplied public fit/validation labels')
    y = labels['target']; n = len(fitval_manifest['case_tokens']); splits = fitval_manifest['case_splits']
    nfit = splits.count('fit'); nval = splits.count('validation')
    need(type(y) is np.ndarray and y.dtype == np.dtype('int8') and y.shape == (n,)
         and bool(np.isin(y, [0, 1, 2]).all()) and nfit >= 40 and nval >= 10
         and splits == ['fit'] * nfit + ['validation'] * nval and nfit + nval == n,
         'Original complete chronological blocks; no target stratification/eligibility change')
    context_rows = []; joint_rows = []
    kwargs = dict(np=np,LogisticRegression=LogisticRegression,HistGradientBoostingClassifier=HistGradientBoostingClassifier,
                  ConvergenceWarning=ConvergenceWarning,tick=tick,counters=counters)
    def evaluate(recipe, block, phase):
        state = fit_recipe(block[:nfit], y[:nfit], recipe, phase=phase, **kwargs)
        p = predict_state(state, block[nfit:], np=np, ConvergenceWarning=ConvergenceWarning,
                          tick=tick, counters=counters, phase=phase+'_validation')
        loss = validation_loss(p, y[nfit:], np)
        row = {'recipe': dict(recipe), 'loss': loss, 'selection_fit_method': state['kind'],
               'selection_missing_class_fallback': state['record'].get('fallback_for_missing_class', False)}
        return row
    for recipe in menu():
        context_rows.append(evaluate(recipe, blocks['context'], 'context_selection'))
    for c in C_VALUES:
        joint_rows.append(evaluate({'family': 'logistic', 'C': c}, blocks['joint'], 'joint_selection'))
    recipes = {'training_prior': {'family': 'training_prior'}, 'selected_context': stable_choice(context_rows),
        'matched_context_logistic': stable_choice(context_rows[1:5]), 'matched_joint_logistic': stable_choice(joint_rows)}
    states = {}
    for key in REFERENCES:
        block = blocks['joint'] if key == 'matched_joint_logistic' else blocks['context']
        states[key] = fit_recipe(block, y, recipes[key], phase='final_refit_'+key, **kwargs)
    def scalar_row(row):
        return {**{k:v for k,v in row.items() if k!='loss'},
            'validation_natural_log_loss': {'status':'positive_infinity','value':None} if math.isinf(row['loss'])
                else {'status':'finite','value':float(row['loss'])}}
    report = {'schema':'neural094_trusted_reference_fit_report_v1','status':'all_four_final_states_fitted_before_query',
        'reference_sha256':reference_sha256,'session_token':fitval_manifest['session_token'],
        'class_order':list(CLASS_ORDER),'fit_rows':nfit,'validation_rows':nval,'final_refit_rows':n,
        'feature_counts':{'context_wheel':23,'context_wheel_neural':blocks['joint'].shape[1]},
        'context_menu':[scalar_row(r) for r in context_rows],'joint_logistic_menu':[scalar_row(r) for r in joint_rows],
        'selected_recipes':recipes,'final_states':{k:dict(states[k]['record']) for k in REFERENCES},
        'context_logistic_selection_evaluations_reused_for_matched_context':True,
        'maximum_selection_estimator_fits':12,'maximum_final_estimator_fits':3,
        'fit_query_argument_present':False,'query_accessed':False,'query_targets_used':False,
        'fit_only_scaling_then_fresh_merged_refit_scaling':True,'models_committed':False,
        'runtime_artifact_sealing_required_before_query':True,'execution_authority':False}
    bundle = {'schema':'neural094_trusted_reference_fitted_bundle_v1','reference_sha256':reference_sha256,
        'session_token':fitval_manifest['session_token'],'fitval_case_tokens':list(fitval_manifest['case_tokens']),
        'unit_ids':blocks['unit_ids'],'unit_qc':blocks['unit_qc'],'states':states,'fit_report':report}
    return bundle, report


def infer_references(saved_bundle, query_packet, query_manifest, commitment, *, versions, np, choice,
                     validator, ConvergenceWarning, tick, counters):
    """Caller must reload exact sealed trusted artifact after its fit process closes."""
    stack_versions(versions)
    need(saved_bundle['schema']=='neural094_trusted_reference_fitted_bundle_v1'
         and set(saved_bundle['states'])==set(REFERENCES)
         and commitment['schema']=='neural094_trusted_reference_model_commit_v1'
         and commitment['reference_sha256']==saved_bundle['reference_sha256']
         and commitment['session_token']==saved_bundle['session_token']
         and commitment['all_four_states_committed_before_query'] is True
         and commitment['fit_process_closed'] is commitment['sealed_readonly'] is True
         and commitment['artifact_sha256_verified_by_loader'] is True,
         'Actual trusted saved/reloaded4-state commitment; runtime authenticates evidence')
    artifact=commitment['artifact']
    need(type(artifact) is dict and set(artifact)=={'path','bytes','sha256'}
         and type(artifact['path']) is str and bool(artifact['path'])
         and type(artifact['bytes']) is int and artifact['bytes']>0
         and type(artifact['sha256']) is str and len(artifact['sha256'])==64
         and set(artifact['sha256'])<=set('0123456789abcdef'), 'Exact saved-artifact descriptor, no serialization here')
    need(query_manifest['phase']=='query' and query_manifest['session_token']==saved_bundle['session_token']
         and set(query_manifest['case_tokens']).isdisjoint(saved_bundle['fitval_case_tokens']),
         'Separate label-hidden query after all final states commit')
    blocks=feature_blocks(query_packet,query_manifest,np=np,choice=choice,validator=validator,tick=tick)
    need(np.array_equal(blocks['unit_ids'],saved_bundle['unit_ids'])
         and np.array_equal(blocks['unit_qc'],saved_bundle['unit_qc']), 'Complete same QC-unit features at query')
    result={}
    for key in REFERENCES:
        X=blocks['joint'] if key=='matched_joint_logistic' else blocks['context']
        result[key]=predict_state(saved_bundle['states'][key],X,np=np,ConvergenceWarning=ConvergenceWarning,
                                 tick=tick,counters=counters,phase='query_'+key)
    return result, {'schema':'neural094_trusted_reference_inference_report_v1','status':'complete_four_reference_predictions',
        'reference_sha256':saved_bundle['reference_sha256'],'session_token':saved_bundle['session_token'],
        'class_order':list(CLASS_ORDER),'query_rows':len(query_manifest['case_tokens']),
        'model_artifact_commitment':commitment,'query_targets_read':0,'query_fits':0,
        'query_adaptive_scaling':False,'execution_authority':False}

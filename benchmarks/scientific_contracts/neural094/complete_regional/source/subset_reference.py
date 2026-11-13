"""Exact regional projection and three-reused/one-new trusted reference composition.

No CLI, I/O, dependency loading, execution grant, candidate code or private query
target access. The parent captures these sources and provides its capture-owned
WholeFit type. Numerical operations belong inside the future trusted worker.
"""
import hashlib
import io
import json
import math

REFERENCE_SHA = '4b361baf14ae689344e389b4bb45fb822c0283a401d6271fefc56115efc2a28d'
REUSED = ('training_prior', 'selected_context', 'matched_context_logistic')
JOINT = 'matched_joint_logistic'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    need(type(raw) is bytes, 'Immutable captured bytes required')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate metadata key')
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    need(type(raw) is bytes, 'Captured metadata bytes')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _matches(raw, descriptor):
    return type(descriptor) is dict and all(descriptor.get(k) == v for k, v in pin(raw).items())


def _decode(members, manifest, *, np, validator, worker, tick):
    """Authenticate actual archive bodies, then call the original header gate."""
    validator.validate_manifest(manifest)
    need(type(members) is dict and set(members) == set(manifest['files']), 'Exact complete members')
    need(sum(len(b) for b in members.values()) <= validator.PUBLIC_PACKET_CAP, 'Original complete packet byte cap')
    arrays = {}
    for name, descriptor in manifest['files'].items():
        raw = members[name]
        need(_matches(raw, descriptor), 'Actual member bytes differ: ' + name)
        worker.archive_contract(raw, np)
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            arrays[name] = {key: archive[key] for key in archive.files}
        tick()
    return arrays


def _encode(arrays, *, np, validator, worker):
    """Serialize projected numeric arrays, then validate the actual NPZ body."""
    with io.BytesIO() as out:
        np.savez(out, **arrays)
        raw = out.getvalue()
    need(0 < len(raw) <= validator.PUBLIC_PACKET_CAP, 'Complete projected archive cap')
    worker.archive_contract(raw, np)
    return raw


def project(plan, pair_index, ordinal, seed, side, members, manifest, *,
            support, np, ref, choice, validator, worker, tick):
    """Production selection uses the exact full canonical support-plan object.

    The parent must authenticate the full inventory/source-session-to-token join
    before constructing plan. Its private labels/aliases never enter public
    members or manifests. Returned selection_private remains operator-only.
    """
    need(type(plan) is support._Plan and plan._canonical_sha == support.CANONICAL_SHA256,
         'Actual frozen full support plan, not invented selection metadata')
    summary = plan.summary()
    need((summary['sessions'], summary['mice'], summary['literal_labels'],
          summary['unordered_pairs'], summary['recording_unit_rows_accounted']) == (39, 10, 73, 2628, 33997),
         'Complete canonical cohort and literal-label scope')
    need(type(ordinal) is int and 1 <= ordinal <= 39 and side in ('left', 'right'), 'Exact ordinal and side')
    need(manifest['unit_count'] == plan._sessions[ordinal - 1][3], 'Original full session inventory')
    selection = plan.select(pair_index, ordinal, seed)
    return _project_selected(selection, side, members, manifest, np=np, ref=ref,
                             choice=choice, validator=validator, worker=worker, tick=tick)


def _project_selected(selection, side, members, manifest, *, np, ref, choice, validator, worker, tick):
    """Internal tiny-control seam; production callers must use project()."""
    need(side in ('left', 'right') and selection['K'] > 0 and selection[side] is not None,
         'Structurally unavailable pairs have no numerical projection')
    original = _decode(members, manifest, np=np, validator=validator, worker=worker, tick=tick)
    original_blocks = ref.feature_blocks(original, manifest, np=np, choice=choice, validator=validator, tick=tick)
    chosen = selection[side]
    aliases = chosen['original_session_local_unit_aliases']
    k = selection['K']; u = manifest['unit_count']
    need(type(k) is int and type(aliases) is list and len(aliases) == k
         and all(type(x) is int and 0 <= x < u for x in aliases)
         and aliases == sorted(set(aliases)) and chosen['selected_count'] == k,
         'Exact unique selected aliases in original source order')
    index = np.asarray(aliases, dtype=np.int64)
    qc = original['units.npz']['source_qc_code'][index].copy()
    need([int((qc == code).sum()) for code in (2, 3)] == chosen['selected_QC2_QC3'],
         'Selected QC inventory agrees with frozen metadata, including silent units')
    old = original['neural.npz']; membership = np.zeros(u, dtype=np.bool_); membership[index] = True
    keep = membership[old['unit']]
    mapping = np.zeros(u, dtype=np.uint32); mapping[index] = np.arange(k, dtype=np.uint32)
    neural = {name: values[keep].copy() for name, values in old.items()}
    neural['unit'] = mapping[neural['unit']]
    units = {'unit': np.arange(k, dtype=np.uint32), 'source_qc_code': qc}
    output = dict(members)  # common immutable bytes are reused, never decoded/re-encoded
    output['neural.npz'] = _encode(neural, np=np, validator=validator, worker=worker)
    output['units.npz'] = _encode(units, np=np, validator=validator, worker=worker)
    projected_manifest = {**manifest, 'unit_count': k, 'files': {key: dict(value) for key, value in manifest['files'].items()}}
    for name in ('neural.npz', 'units.npz'):
        projected_manifest['files'][name].update(pin(output[name]))
    projected = _decode(output, projected_manifest, np=np, validator=validator, worker=worker, tick=tick)
    blocks = ref.feature_blocks(projected, projected_manifest, np=np, choice=choice, validator=validator, tick=tick)
    need(np.array_equal(blocks['context'], original_blocks['context']), 'Exact original context/wheel feature values')
    columns = [23 + 5 * alias + offset for alias in aliases for offset in range(5)]
    need(np.array_equal(blocks['joint'][:, 23:], original_blocks['joint'][:, columns]),
         'Exact selected count features, source order, no event or silent-unit thinning')
    private = {'schema': 'neural094_selected_projection_lineage_v1', 'selection': selection, 'side': side,
               'original_unit_count': u, 'projected_unit_count': k,
               'source_member_pins': {name: pin(raw) for name, raw in members.items()},
               'projected_member_pins': {name: pin(raw) for name, raw in output.items()},
               'source_event_count': len(old['unit']), 'selected_event_count': len(neural['unit']),
               'common_bytes_unchanged': True, 'stable_event_order': True, 'silent_units_retained': True,
               'source_inventory_authentication_performed_here': False}
    return {'members': output, 'manifest': projected_manifest, 'selection_private': private}


def _whole(whole_fit, *, custody, worker, validator, ref):
    """Use the parent's capture-only capability; never grant trust from flags."""
    need(type(whole_fit) is custody.WholeFit, 'Capture-owned WholeFit capability required')
    for name in ('model_bytes', 'commitment_bytes', 'fit_manifest_bytes', 'fit_request_bytes', 'closed_producer_bytes'):
        need(type(getattr(whole_fit, name)) is bytes, 'Immutable whole-fit captured bytes: ' + name)
    manifest = strict(whole_fit.fit_manifest_bytes); validator.validate_manifest(manifest)
    request = strict(whole_fit.fit_request_bytes); closed = strict(whole_fit.closed_producer_bytes)
    commitment = strict(whole_fit.commitment_bytes)
    need(manifest['phase'] == 'fitval' and manifest['arm'] == 'context_wheel_neural', 'Whole fit-only joint packet')
    need(request['phase_name'] == request['kind'] == 'reference_fit'
         and set(request['payload']) == {'fitval_manifest'}
         and _matches(whole_fit.fit_manifest_bytes, request['payload']['fitval_manifest']), 'Actual closed whole-fit request and manifest bytes')
    need(closed['phase_name'] == 'reference_fit' and closed['status'] == 'complete_closed_phase'
         and _matches(whole_fit.fit_request_bytes, closed['request']), 'Captured request belongs to closed whole producer')
    need(commitment['schema'] == 'neural094_trusted_reference_model_commit_v1'
         and commitment['reference_sha256'] == REFERENCE_SHA
         and commitment['session_token'] == manifest['session_token'] == request['session_token']
         and all(commitment[key] is True for key in ('all_four_states_committed_before_query', 'fit_process_closed',
                                                    'sealed_readonly', 'artifact_sha256_verified_by_loader')),
         'Original authenticated four-state whole fit closure')
    terminal = closed['evidence']['trusted_worker_terminal']
    need(terminal['status'] == 'complete_trusted_reference_fit' and terminal['query_features_read'] is False
         and terminal['query_targets_read'] == 0 and terminal['models_committed'] is False
         and type(terminal['empirical_estimator_fit_attempts']) is int
         and 0 <= terminal['empirical_estimator_fit_attempts'] <= 15,
         'Original complete whole fit terminal, no query-dependent fit')
    need(closed['evidence']['artifacts']['model_artifact'] == commitment['artifact'], 'Same closed producer and sealed model')
    saved = worker.deserialize_trusted(whole_fit.model_bytes, commitment['artifact'])
    need(saved['schema'] == 'neural094_trusted_reference_fitted_bundle_v1'
         and saved['reference_sha256'] == REFERENCE_SHA and saved['session_token'] == manifest['session_token']
         and saved['fitval_case_tokens'] == manifest['case_tokens'] and set(saved['states']) == set(ref.REFERENCES),
         'Actual unchanged whole reference identity and complete fitting cases')
    report = saved['fit_report']
    need(report['schema'] == 'neural094_trusted_reference_fit_report_v1'
         and report['status'] == 'all_four_final_states_fitted_before_query'
         and report['reference_sha256'] == REFERENCE_SHA and report['session_token'] == manifest['session_token']
         and report['class_order'] == list(ref.CLASS_ORDER)
         and report['fit_rows'] == manifest['case_splits'].count('fit')
         and report['validation_rows'] == manifest['case_splits'].count('validation')
         and report['final_refit_rows'] == len(manifest['case_tokens'])
         and report['feature_counts'] == {'context_wheel': 23, 'context_wheel_neural': 23 + 5 * manifest['unit_count']}
         and report['query_accessed'] is report['query_targets_used'] is report['models_committed'] is False,
         'Exact original whole fit method, rows, feature geometry and no query')
    for name in REUSED:
        state = saved['states'][name]
        need(state['features'] == 23 and state['record']['status'] == 'completed'
             and state['record']['training_rows'] == len(manifest['case_tokens'])
             and state['record'] == report['final_states'][name]
             and state['recipe'] == report['selected_recipes'][name], 'Completed original nuisance state: ' + name)
    return saved, manifest


def fit_regional(projected, whole_fit, *, custody, versions, np, ref, choice, validator, worker,
                 LogisticRegression, HistGradientBoostingClassifier, ConvergenceWarning, tick, counters):
    """Fit four joint C candidates + one refit; reuse three sealed nuisance states.

    No query argument. Only trusted worker code may invoke this with a genuinely
    admitted WholeFit. No numerical dependency is imported or version replaced.
    """
    ref.stack_versions(versions)
    need(tuple(ref.C_VALUES) == (.01, .1, 1., 10.) and tuple(ref.REFERENCES) == REUSED + (JOINT,), 'Exact unchanged method menu')
    saved, whole_manifest = _whole(whole_fit, custody=custody, worker=worker, validator=validator, ref=ref)
    manifest = projected['manifest']; need(manifest['phase'] == 'fitval', 'Regional fitting has no query access')
    for key in ('schema', 'candidate_id', 'arm', 'phase', 'session_token', 'case_tokens', 'case_splits', 'observation'):
        need(manifest[key] == whole_manifest[key], 'Exact whole/regional fit support: ' + key)
    for name in ('context.npz', 'wheel.npz', 'labels.npz'):
        need(manifest['files'][name] == whole_manifest['files'][name], 'Byte-identical whole fit common input: ' + name)
    packet = _decode(projected['members'], manifest, np=np, validator=validator, worker=worker, tick=tick)
    blocks = ref.feature_blocks(packet, manifest, np=np, choice=choice, validator=validator, tick=tick)
    n = len(manifest['case_tokens']); nfit = manifest['case_splits'].count('fit'); nval = n - nfit
    y = packet['labels.npz']['target']
    need(set(packet['labels.npz']) == {'target'} and type(y) is np.ndarray and y.dtype == np.dtype('int8')
         and y.shape == (n,) and bool(np.isin(y, [0, 1, 2]).all()), 'Original public training/validation targets only')
    start_attempts = counters.get('estimator_fit_attempts', 0)
    need(type(start_attempts) is int and start_attempts >= 0, 'Nonnegative starting estimator accounting')
    kwargs = dict(np=np, LogisticRegression=LogisticRegression, HistGradientBoostingClassifier=HistGradientBoostingClassifier,
                  ConvergenceWarning=ConvergenceWarning, tick=tick, counters=counters)
    rows = []
    for c in ref.C_VALUES:
        recipe = {'family': 'logistic', 'C': c}
        state = ref.fit_recipe(blocks['joint'][:nfit], y[:nfit], recipe, phase='regional_joint_selection', **kwargs)
        probabilities = ref.predict_state(state, blocks['joint'][nfit:], np=np, ConvergenceWarning=ConvergenceWarning,
                                          tick=tick, counters=counters, phase='regional_joint_selection_validation')
        rows.append({'recipe': recipe, 'loss': ref.validation_loss(probabilities, y[nfit:], np),
                     'selection_fit_method': state['kind'],
                     'selection_missing_class_fallback': state['record'].get('fallback_for_missing_class', False)})
    recipe = ref.stable_choice(rows)
    joint = ref.fit_recipe(blocks['joint'], y, recipe, phase='regional_final_refit_matched_joint_logistic', **kwargs)
    attempts = counters.get('estimator_fit_attempts', 0) - start_attempts
    need(0 <= attempts <= 5, 'At most four regional selection fits and one final refit')
    states = {name: saved['states'][name] for name in REUSED}; states[JOINT] = joint
    def scalar(row):
        return {**{key: value for key, value in row.items() if key != 'loss'}, 'validation_natural_log_loss':
                {'status': 'positive_infinity', 'value': None} if math.isinf(row['loss'])
                else {'status': 'finite', 'value': float(row['loss'])}}
    report = {'schema': 'neural094_regional_reference_composition_v1', 'status': 'three_whole_nuisance_states_reused_one_regional_joint_fitted',
              'reference_sha256': REFERENCE_SHA, 'session_token': manifest['session_token'], 'class_order': list(ref.CLASS_ORDER),
              'fit_rows': nfit, 'validation_rows': nval, 'final_refit_rows': n,
              'feature_counts': {'context_wheel': 23, 'context_wheel_neural': blocks['joint'].shape[1]},
              'reused_states': list(REUSED), 'new_state': JOINT, 'new_estimator_fit_attempts': attempts,
              'maximum_new_selection_estimator_fits': 4, 'maximum_new_final_estimator_fits': 1,
              'joint_logistic_menu': [scalar(row) for row in rows], 'selected_regional_recipe': recipe,
              'final_states': {name: dict(states[name]['record']) for name in ref.REFERENCES},
              'original_whole_lineage': {name: pin(getattr(whole_fit, name)) for name in
                   ('model_bytes', 'commitment_bytes', 'fit_manifest_bytes', 'fit_request_bytes', 'closed_producer_bytes')},
              'selection_private': projected['selection_private'], 'query_accessed': False, 'query_targets_used': False,
              'models_committed': False, 'all_four_newly_fitted_claim': False,
              'separate_regional_fit_process_closure_and_seal_required': True, 'execution_authority': False}
    bundle = {'schema': 'neural094_trusted_reference_fitted_bundle_v1', 'reference_sha256': REFERENCE_SHA,
              'session_token': manifest['session_token'], 'fitval_case_tokens': list(manifest['case_tokens']),
              'unit_ids': blocks['unit_ids'], 'unit_qc': blocks['unit_qc'], 'states': states, 'fit_report': report}
    raw = worker.serialize_trusted(bundle)
    reloaded = worker.deserialize_trusted(raw, pin(raw))
    need(set(reloaded['states']) == set(ref.REFERENCES) and reloaded['fit_report']['schema'] == report['schema']
         and np.array_equal(reloaded['unit_ids'], bundle['unit_ids'])
         and np.array_equal(reloaded['unit_qc'], bundle['unit_qc']), 'Actual unchanged trusted codec roundtrip')
    return {'model_bytes': raw, 'model_pin': pin(raw), 'composition': report}


def infer_regional(model_bytes, commitment, projected, *, versions, np, ref, choice, validator, worker,
                   ConvergenceWarning, tick, counters):
    """Unchanged numerical four-state inference after parent's regional seal."""
    saved = worker.deserialize_trusted(model_bytes, commitment['artifact'])
    need(saved['fit_report']['schema'] == 'neural094_regional_reference_composition_v1', 'Regional composition, not relabelled whole fit')
    need(projected['manifest']['phase'] == 'query', 'Query-only inference')
    fit_selection = saved['fit_report']['selection_private']
    query_selection = projected['selection_private']
    need(fit_selection['selection'] == query_selection['selection'] and fit_selection['side'] == query_selection['side'],
         'Same exact regional membership and seed at fit/query')
    packet = _decode(projected['members'], projected['manifest'], np=np, validator=validator, worker=worker, tick=tick)
    return ref.infer_references(saved, packet, projected['manifest'], commitment, versions=versions, np=np,
                                choice=choice, validator=validator, ConvergenceWarning=ConvergenceWarning,
                                tick=tick, counters=counters)

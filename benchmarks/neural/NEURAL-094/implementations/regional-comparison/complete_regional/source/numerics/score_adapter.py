"""Source-only094 all39 final-choice scalar scorer; no I/O, model or runtime.

The future trusted grader supplies captured core/validator modules and NumPy.
Both arms for all39 sessions validate before any private callback. Runtime must
independently authenticate all host commitments, roster and callback sources.
"""
import hashlib
import json
import math
import re

ARMS = ('context_wheel', 'context_wheel_neural')
REFERENCES = ('training_prior', 'selected_context', 'matched_context_logistic', 'matched_joint_logistic')
CLASS_ORDER = ('right', 'NoGo', 'left')
MAX_PREDICTION_BYTES = 4 * 1024 * 1024
MAX_REFERENCE_BYTES = 16 * 1024 * 1024
CONTRASTS = {
    'primary_trusted_context_minus_candidate_joint': ('trusted:selected_context', 'candidate:context_wheel_neural'),
    'candidate_context_minus_candidate_joint': ('candidate:context_wheel', 'candidate:context_wheel_neural'),
    'matched_reference_context_minus_joint': ('trusted:matched_context_logistic', 'trusted:matched_joint_logistic'),
    'trusted_selected_context_minus_matched_joint': ('trusted:selected_context', 'trusted:matched_joint_logistic'),
}
PRIMARY = 'primary_trusted_context_minus_candidate_joint'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def short_pin(raw):
    need(type(raw) is bytes, 'Exact captured bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def strict_json(raw, cap):
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'Bounded captured JSON')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON literal'))


def descriptor(pin):
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}
         and type(pin['path']) is str and pin['path'] and not pin['path'].startswith('/')
         and '..' not in pin['path'].split('/') and type(pin['bytes']) is int
         and pin['bytes'] > 0 and digest(pin['sha256']), 'Exact trusted relative descriptor')
    return pin


def roster_contract(roster):
    need(type(roster) is list and len(roster) == 39, 'All39 original source sessions')
    for ordinal, row in enumerate(roster, 1):
        need(type(row) is dict and set(row) == {'ordinal', 'session', 'mouse', 'session_token',
             'query_tokens', 'query_source_rows', 'public_manifests', 'private_mapping'}
             and type(row['ordinal']) is int and row['ordinal'] == ordinal
             and type(row['session']) is str and bool(row['session'])
             and type(row['mouse']) is str and bool(row['mouse']) and digest(row['session_token']),
             'Exact trusted source-bound ordered scoring roster')
        tokens, ids = row['query_tokens'], row['query_source_rows']
        need(type(tokens) is list and 10 <= len(tokens) <= 10000 and all(digest(t) for t in tokens)
             and len(set(tokens)) == len(tokens) and type(ids) is list and len(ids) == len(tokens)
             and all(type(i) is int and i >= 0 for i in ids)
             and all(a < b for a, b in zip(ids, ids[1:])), 'Complete original query support and order')
        need(type(row['public_manifests']) is dict and set(row['public_manifests']) == set(ARMS),
             'Both exact public query manifest descriptors')
        for pin in row['public_manifests'].values():
            descriptor(pin)
        descriptor(row['private_mapping'])
    need(len({r['session'] for r in roster}) == len({r['session_token'] for r in roster}) == 39
         and len({r['mouse'] for r in roster}) == 10, 'Original39 unique sessions nested in10 mice')
    need(sum(len(r['query_tokens']) for r in roster) <= 10050
         and len({t for r in roster for t in r['query_tokens']}) == sum(len(r['query_tokens']) for r in roster),
         'Opaque query identities unique across complete cohort')
    return True


def parse_rows(rows, required_tokens):
    """Pure public syntax checks; numerical normalization is a separate exact kernel."""
    need(type(rows) is list and len(rows) == len(required_tokens), 'Complete required output rows')
    allowed = set(required_tokens); by_token = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'token', 'probabilities'}, 'No candidate scores/extra fields')
        token, values = row['token'], row['probabilities']
        need(type(token) is str and token in allowed and token not in by_token,
             'No missing, duplicate, extra or cross-session token')
        need(type(values) is list and len(values) == 3
             and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values),
             'Three finite nonboolean right/NoGo/left probabilities')
        need(abs(sum(values) - 1) <= 1e-8, 'Exact inherited fixed probability sum tolerance')
        by_token[token] = values
    return [by_token[t] for t in required_tokens]


def prediction_rows(raw, arm, row, candidate_sha256, core, np):
    doc = strict_json(raw, MAX_PREDICTION_BYTES)
    need(type(doc) is dict and set(doc) == {'schema', 'arm', 'session_token', 'candidate_sha256',
         'class_order', 'predictions'} and doc['schema'] == 'neural094-candidate-predictions-v1'
         and arm in ARMS and doc['arm'] == arm and doc['session_token'] == row['session_token']
         and doc['candidate_sha256'] == candidate_sha256 and doc['class_order'] == list(CLASS_ORDER),
         'Exact094 final-choice output identity and fixed class order')
    values = parse_rows(doc['predictions'], row['query_tokens'])
    return core.probabilities(np.asarray(values, dtype=np.float64), np)


def commit_contract(commit, public_sessions, roster, candidate_sha256, reference_sha256):
    """Commit object is trusted host evidence, never a candidate assertion."""
    roster_contract(roster)
    need(digest(candidate_sha256) and digest(reference_sha256), 'Frozen candidate/reference source hashes')
    need(type(commit) is dict and set(commit) == {'schema', 'status', 'candidate_sha256',
         'reference_sha256', 'private_grading_started', 'all_candidate_producers_stopped',
         'all_candidate_owned_resources_absent', 'sessions'}
         and commit['schema'] == 'neural094-all39-both-arm-prediction-commit-v1'
         and commit['status'] == 'all78_predictions_committed_before_private_grading'
         and commit['candidate_sha256'] == candidate_sha256 and commit['reference_sha256'] == reference_sha256
         and commit['private_grading_started'] is False
         and commit['all_candidate_producers_stopped'] is True
         and commit['all_candidate_owned_resources_absent'] is True,
         'All78 complete candidate predictions closed and committed before private grading')
    need(type(public_sessions) is list and len(public_sessions) == 39
         and type(commit['sessions']) is list and len(commit['sessions']) == 39,
         'Exact full39 paired public/commit support')
    for source, supplied, saved in zip(roster, public_sessions, commit['sessions'], strict=True):
        need(type(supplied) is dict and set(supplied) == {'ordinal', 'session_token', 'query_packets', 'predictions'}
             and type(saved) is dict and set(saved) == {'ordinal', 'session_token', 'models_committed_before_either_query',
                  'arms', 'trusted_reference_prediction', 'trusted_reference_closed_before_private_grading'}
             and type(supplied['ordinal']) is type(saved['ordinal']) is int
             and source['ordinal'] == supplied['ordinal'] == saved['ordinal']
             and source['session_token'] == supplied['session_token'] == saved['session_token']
             and saved['models_committed_before_either_query'] is True
             and saved['trusted_reference_closed_before_private_grading'] is True,
             'Ordered exact source identity and both model commits before either query')
        need(type(supplied['query_packets']) is dict and set(supplied['query_packets']) == set(ARMS)
             and type(supplied['predictions']) is dict and set(supplied['predictions']) == set(ARMS)
             and type(saved['arms']) is dict and set(saved['arms']) == set(ARMS), 'Both mandatory physical arms')
        descriptor(saved['trusted_reference_prediction'])
        for arm in ARMS:
            pin = saved['arms'][arm]
            need(type(pin) is dict and set(pin) == {'prediction', 'public_manifest', 'sealed_readonly',
                 'captured_after_producer_absence', 'producer_closed'}
                 and pin['sealed_readonly'] is pin['captured_after_producer_absence'] is pin['producer_closed'] is True,
                 'Actual post-closure readonly arm output')
            descriptor(pin['prediction'])
            need(short_pin(supplied['predictions'][arm]) == {k: pin['prediction'][k] for k in ('bytes', 'sha256')}
                 and pin['public_manifest'] == source['public_manifests'][arm], 'Exact committed candidate/public bytes')
    return True


def public_validation(public_sessions, commit, roster, candidate_sha256, reference_sha256, core, validator, np):
    commit_contract(commit, public_sessions, roster, candidate_sha256, reference_sha256)
    probabilities = []
    for row, supplied in zip(roster, public_sessions, strict=True):
        matrices = {}; manifests = {}
        for arm in ARMS:
            packet = supplied['query_packets'][arm]
            need(type(packet) is dict and set(packet) == {'pin', 'body'}
                 and packet['pin'] == row['public_manifests'][arm]
                 and short_pin(packet['body']) == {k: packet['pin'][k] for k in ('bytes', 'sha256')},
                 'Exact trusted public manifest bytes before any private callback')
            doc = strict_json(packet['body'], 1048576)
            validator.validate_manifest(doc)
            need(doc['arm'] == arm and doc['phase'] == 'query'
                 and doc['session_token'] == row['session_token'] and doc['case_tokens'] == row['query_tokens'],
                 'Exact source-bound full query cases and original order')
            manifests[arm] = doc
            matrices[arm] = prediction_rows(supplied['predictions'][arm], arm, row, candidate_sha256, core, np)
        left, right = (manifests[a] for a in ARMS)
        need(all(left[k] == right[k] for k in ('session_token', 'case_tokens', 'case_splits', 'observation'))
             and all(left['files'][k] == right['files'][k] for k in ('context.npz', 'wheel.npz')),
             'Identical case/context/wheel support across physically separated arms')
        probabilities.append(matrices)
    return probabilities


def private_targets(raw, row, np):
    need(short_pin(raw) == {k: row['private_mapping'][k] for k in ('bytes', 'sha256')},
         'Exact separately committed private exporter mapping')
    doc = strict_json(raw, 4 * 1024 * 1024)
    need(doc['schema'] == 'neural094-candidate-private-session-v1' and doc['candidate_id'] == 'NEURAL-094'
         and doc['execution_authority'] is False and type(doc['ordinal']) is int
         and all(doc[k] == row[k] for k in ('ordinal', 'session', 'mouse', 'session_token'))
         and doc['source_row_or_unit_filtering_for_export_size'] is False
         and doc['source_integrity']['choice_eligibility_unchanged_from093_source_geometry'] is True
         and doc['source_integrity']['all39_support_passed'] is True,
         'Exact094 full-support private mapping; no093 target or subset substitution')
    need(all(doc['public_manifests'][a]['query'] == row['public_manifests'][a] for a in ARMS),
         'Private mapping joins already admitted public manifests')
    query = doc['query']
    need(type(query) is list and len(query) == len(row['query_tokens'])
         and all(type(q) is dict and set(q) == {'token', 'source_row', 'target'} for q in query)
         and [q['token'] for q in query] == row['query_tokens']
         and [q['source_row'] for q in query] == row['query_source_rows']
         and all(type(q['source_row']) is int and type(q['target']) is int and 0 <= q['target'] <= 2 for q in query),
         'Every exact original source row has its true three-class final choice')
    return np.asarray([q['target'] for q in query], dtype=np.int64)


def reference_predictions(raw, pin, row, reference_sha256, core, np):
    need(short_pin(raw) == {k: pin[k] for k in ('bytes', 'sha256')}, 'Exact frozen fresh094 reference prediction bytes')
    doc = strict_json(raw, MAX_REFERENCE_BYTES)
    need(type(doc) is dict and set(doc) == {'schema', 'reference_sha256', 'ordinal', 'session_token',
         'class_order', 'query_tokens', 'query_source_rows', 'views', 'fresh094_choice_reference',
         'selected_on_fit_validation_only', 'refit_on_fit_validation_only', 'query_targets_used_for_fit_or_selection'}
         and doc['schema'] == 'neural094-trusted-reference-predictions-v1'
         and doc['reference_sha256'] == reference_sha256 and type(doc['ordinal']) is int
         and doc['ordinal'] == row['ordinal'] and doc['session_token'] == row['session_token']
         and doc['class_order'] == list(CLASS_ORDER) and doc['query_tokens'] == row['query_tokens']
         and type(doc['query_source_rows']) is list and all(type(i) is int for i in doc['query_source_rows'])
         and doc['query_source_rows'] == row['query_source_rows']
         and doc['fresh094_choice_reference'] is doc['selected_on_fit_validation_only'] is doc['refit_on_fit_validation_only'] is True
         and doc['query_targets_used_for_fit_or_selection'] is False
         and type(doc['views']) is dict and set(doc['views']) == set(REFERENCES),
         'Exact four fresh094 fixed-reference views; old093 predictions are not choice evidence')
    return {key: core.probabilities(np.asarray(parse_rows(doc['views'][key], row['query_tokens']), dtype=np.float64), np)
            for key in REFERENCES}


def trial_losses(p, y, np):
    chosen = p[np.arange(len(y)), y]
    with np.errstate(divide='ignore'):
        losses = -np.log(chosen)
    need(bool((~np.isnan(losses)).all()) and bool((losses >= 0).all()), 'Nonnegative loss including exact positive infinity')
    return losses


def metrics(p, y, core, np):
    counts = np.bincount(y, minlength=3); predicted = np.argmax(p, axis=1)
    confusion = np.zeros((3, 3), dtype=np.int64)
    np.add.at(confusion, (y, predicted), 1)
    recalls = [float((predicted[y == k] == k).mean()) if counts[k] else None for k in range(3)]
    return {'natural_log_loss': core.extended(core.mean_log_loss(p, y, np)),
        'multiclass_Brier_mean_sum3': float(np.square(p - np.eye(3, dtype=np.float64)[y]).sum(axis=1).mean()),
        'top1_accuracy': float((predicted == y).mean()), 'class_recall': recalls,
        'macro_recall': core.extended(sum(recalls) / 3) if bool((counts > 0).all())
            else {'status': 'undefined_missing_query_class', 'value': None},
        'confusion_true_rows_predicted_columns': [[int(v) for v in row] for row in confusion],
        'zero_true_class_probability_rows': int((p[np.arange(len(y)), y] == 0).sum()),
        'top1_tie_break': 'first class in right,NoGo,left order'}


def paired_effect(left, right, core, np):
    # Trial pairing is normative: inf-inf on even one required trial remains undefined.
    with np.errstate(invalid='ignore'):
        delta = left - right
        value = float(delta.mean())
    return core.extended(value)


def aggregate_reports(records, roster, candidate_sha256, reference_sha256, core):
    roster_contract(roster)
    need(type(records) is list and len(records) == 39, 'All39 complete session scalars; no favorable subset')
    keys = ['candidate:' + a for a in ARMS] + ['trusted:' + k for k in REFERENCES] + ['analytic:uniform']
    for row, result in zip(roster, records, strict=True):
        need(result['schema'] == 'neural094-choice-session-score-v1' and result['status'] == 'complete_paired_choice_session'
             and all(result[k] == row[k] for k in ('ordinal', 'session', 'mouse', 'session_token'))
             and result['candidate_sha256'] == candidate_sha256 and result['reference_sha256'] == reference_sha256
             and result['query_rows'] == len(row['query_tokens'])
             and result['case_removal_for_probability_or_performance'] is False
             and set(result['metrics']) == set(keys) and set(result['contrasts']) == set(CONTRASTS),
             'Same complete original support, sources and contrast roster in every session')
    mice = sorted({r['mouse'] for r in roster}); mouse_rows = []
    def avg(values):
        return core.extended(sum(core.number(v) for v in values) / len(values))
    for mouse in mice:
        rows = [r for r in records if r['mouse'] == mouse]
        mouse_rows.append({'mouse': mouse, 'sessions': [r['session'] for r in rows], 'session_count': len(rows),
            'absolute_logloss': {k: avg([r['metrics'][k]['natural_log_loss'] for r in rows]) for k in keys},
            'absolute_Brier': {k: sum(r['metrics'][k]['multiclass_Brier_mean_sum3'] for r in rows) / len(rows) for k in keys},
            'absolute_accuracy': {k: sum(r['metrics'][k]['top1_accuracy'] for r in rows) / len(rows) for k in keys},
            'contrasts': {k: avg([r['contrasts'][k] for r in rows]) for k in CONTRASTS}})
    for item in mouse_rows:
        item['absolute_logloss']['analytic:uniform'] = core.extended(math.log(3.0))
    absolute = {k: avg([r['absolute_logloss'][k] for r in mouse_rows]) for k in keys}
    absolute['analytic:uniform'] = core.extended(math.log(3.0))
    return {'schema': 'neural094-choice-all39-score-v1', 'status': 'complete_all39_paired_choice_evaluation',
        'candidate_sha256': candidate_sha256, 'reference_sha256': reference_sha256,
        'required_sessions': 39, 'required_mice': 10, 'class_order': list(CLASS_ORDER),
        'session_records': records, 'mouse_records': mouse_rows,
        'equal_mouse_absolute_logloss': absolute,
        'equal_mouse_absolute_Brier': {k: sum(r['absolute_Brier'][k] for r in mouse_rows) / 10 for k in keys},
        'equal_mouse_absolute_accuracy': {k: sum(r['absolute_accuracy'][k] for r in mouse_rows) / 10 for k in keys},
        'contrasts': {k: avg([r['contrasts'][k] for r in mouse_rows]) for k in CONTRASTS},
        'primary_contrast': PRIMARY, 'paired_trial_differences_before_session_averaging': True,
        'equal_sessions_within_mouse_then_equal10mice': True, 'subset_renormalization': False,
        'nonfinite_or_negative_effects_filtered': False, 'candidate_supplied_scores_used': False,
        'uncertainty': {'status': 'deferred_separate_bounded_stage', 'bootstrap_performed': False},
        'interpretation': {'positive_primary': 'Lower joint-candidate log loss than fixed competent trusted context baseline',
            'candidate_arm_contrast': 'Diagnostic; depends on candidate context quality and cannot alter primary',
            'public_development_data': True, 'untouched_confirmation': False,
            'held_out_mouse_transfer': False, 'premovement_or_causal_claim': False,
            'unmeasured_behavior_controlled': False, 'regional_or_full_original_catalog_completion': False},
        'automatic_benchmark_admission': False, 'execution_authority': False}


def score_cohort(public_sessions, commit, roster, candidate_sha256, reference_sha256,
                 private_mapping_loader, trusted_reference_loader, core, validator, np):
    """Private loaders are trusted pin-verifying isolated-grader callbacks, never candidates."""
    predictions = public_validation(public_sessions, commit, roster, candidate_sha256, reference_sha256, core, validator, np)
    # No private callback above this point: all39 x both arms are complete and valid.
    records = []
    for row, candidate, saved in zip(roster, predictions, commit['sessions'], strict=True):
        y = private_targets(private_mapping_loader(row['private_mapping']), row, np)
        refs = reference_predictions(trusted_reference_loader(saved['trusted_reference_prediction']),
                                    saved['trusted_reference_prediction'], row, reference_sha256, core, np)
        matrices = {'candidate:' + a: candidate[a] for a in ARMS}
        matrices.update({'trusted:' + k: refs[k] for k in REFERENCES})
        matrices['analytic:uniform'] = np.full((len(y), 3), 1 / 3, dtype=np.float64)
        losses = {k: trial_losses(p, y, np) for k, p in matrices.items()}
        metrics_by_view = {k: metrics(p, y, core, np) for k, p in matrices.items()}
        # Preserve the exact descriptive constant independently of class frequency.
        metrics_by_view['analytic:uniform']['natural_log_loss'] = core.extended(math.log(3.0))
        counts = np.bincount(y, minlength=3)
        records.append({'schema': 'neural094-choice-session-score-v1', 'status': 'complete_paired_choice_session',
            'ordinal': row['ordinal'], 'session': row['session'], 'mouse': row['mouse'], 'session_token': row['session_token'],
            'candidate_sha256': candidate_sha256, 'reference_sha256': reference_sha256,
            'query_rows': len(y), 'class_counts': [int(v) for v in counts], 'class_order': list(CLASS_ORDER),
            'metrics': metrics_by_view,
            'contrasts': {k: paired_effect(losses[a], losses[b], core, np) for k, (a, b) in CONTRASTS.items()},
            'public_manifest_commitments': row['public_manifests'], 'private_mapping_commitment': row['private_mapping'],
            'prediction_commitments': {a: saved['arms'][a]['prediction'] for a in ARMS},
            'trusted_reference_commitment': saved['trusted_reference_prediction'],
            'candidate_models_deserialized_by_grader': False, 'case_removal_for_probability_or_performance': False})
    result = aggregate_reports(records, roster, candidate_sha256, reference_sha256, core)
    result['public_predictions_validated_before_any_private_callback'] = 78
    result['private_mapping_callbacks'] = 39; result['trusted_reference_callbacks'] = 39
    result['arrays_or_trial_losses_exported'] = False
    return result

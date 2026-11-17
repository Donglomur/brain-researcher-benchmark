"""Real full-person reference graph. Yields computation artifacts, never accepts scores."""
import math
from .protocol import Refusal, require, ids, identity, candidate_specs, specification, feature_order, pin
from .features import array, geometry, behavior_features, waveform_features, build_features, np_module
from .models import fit, predict, lineage_admit
from .selection import select
from .budget import failure, is_fatal

BASE_FIELDS = {'person_id', 'trial_ids', 'rt_seconds', 'instruction', 'sample_count', 'waveforms'}


def person_admit(person, training, budget):
    require(type(person) is dict and set(person) == BASE_FIELDS | ({'target'} if training else set()), 'person_schema_training_or_target_free_held')
    identity(person['person_id'])
    require(type(person['trial_ids']) in (list, tuple), 'trial_list')
    n = len(person['trial_ids'])
    require(n > 0, 'empty_person')
    ids(person['trial_ids'], n)
    for k in ('rt_seconds', 'instruction'):
        require(geometry(person[k], budget) == (n,), 'person_covariate_shape')
    require(type(person['sample_count']) in (list, tuple) and len(person['sample_count']) == n and all(type(x) is int and x >= 8 for x in person['sample_count']), 'sample_count')
    require(type(person['waveforms']) in (list, tuple) and len(person['waveforms']) == n, 'person_waveform_count')
    total = 0
    for count, trial in zip(person['sample_count'], person['waveforms']):
        require(geometry(trial, budget) == (32, count), 'native_waveform_count_join')
        total += 32 * count
    budget.stage(elements=total, live=total * 8, work=total)
    if training:
        require(geometry(person['target'], budget) == (n,), 'person_target_shape')
    return n


def fold_admit(fold, budget):
    require(type(fold) is dict and set(fold) == {'outer_index', 'training', 'held', 'channel_order', 'lineage'}, 'fold_schema')
    require(type(fold['outer_index']) is int and 0 <= fold['outer_index'] < 26, 'outer_index')
    require(type(fold['training']) is list and len(fold['training']) == 25, 'outer_training_people')
    channel_order = ids(fold['channel_order'], 32)
    lineage_admit(fold['lineage'])
    require(fold['lineage']['channel_order'] == channel_order, 'fold_channel_lineage')
    names = []
    counts = []
    for p in fold['training']:
        counts.append(person_admit(p, True, budget))
        names.append(p['person_id'])
    counts.append(person_admit(fold['held'], False, budget))
    names.append(fold['held']['person_id'])
    require(len(set(names)) == 26, 'outer_person_disjointness')
    return names, counts


def _cache_person(person, channels, budget):
    B = behavior_features(person['rt_seconds'], person['instruction'], budget)
    waveform_failure = None
    try:
        G, C = waveform_features(person['waveforms'], channels, budget)
    except Exception as exc:
        if is_fatal(exc):
            raise
        G = C = None
        waveform_failure = failure(exc, 'raw_waveform_descriptors', budget)
    out = {'person_id': person['person_id'], 'trial_ids': list(person['trial_ids']),
           'rt_seconds': array(person['rt_seconds'], budget, 1),
           'instruction': array(person['instruction'], budget, 1), 'B': B, 'G': G, 'C': C,
           'waveform_failure': waveform_failure}
    if 'target' in person:
        target = array(person['target'], budget, 1)
        require(bool(((target > 0.025) & (target < 1)).all()), 'target_range')
        out['target'] = target
    return out


def _join(rows, family, channels, budget, with_targets):
    np = np_module()
    require(type(rows) is list and len(rows) > 0, 'empty_join')
    if family != 'B':
        failed = [p['person_id'] for p in rows if p['waveform_failure'] is not None]
        if failed:
            raise Refusal('waveform_feature_dependency_failed', {'people': failed})
    n = sum(len(p['trial_ids']) for p in rows)
    width = len(feature_order(family, channels))
    budget.stage(live=8 * n * (width * 4 + 1120), work=n * width * 5)
    B = np.concatenate([p['B'] for p in rows], axis=0)
    G = np.concatenate([p['G'] for p in rows], axis=0) if family in ('G', 'GC') else None
    C = np.concatenate([p['C'] for p in rows], axis=0) if family in ('C', 'GC') else None
    r = np.concatenate([p['rt_seconds'] for p in rows])
    a = np.concatenate([p['instruction'] for p in rows])
    design = {'matrix': build_features(B, G, C, a, family, budget), 'rt_seconds': r,
              'instruction': a, 'feature_order': feature_order(family, channels)}
    people = [p['person_id'] for p in rows for _ in p['trial_ids']]
    trials = [t for p in rows for t in p['trial_ids']]
    y = np.concatenate([p['target'] for p in rows]) if with_targets else None
    budget.tick()
    return design, y, people, trials


def _lineage(fold, stage, train_people, query_person=None):
    out = dict(fold['lineage'])
    out['view'] = {'upstream': fold['lineage']['view'], 'outer_index': fold['outer_index'],
                   'stage': stage, 'fit_people': list(train_people), 'query_person': query_person}
    return out


def _event(kind, fold, body, budget):
    budget.stage(records=1)
    return {'schema': 'neural004_reference_event_v1', 'kind': kind, 'outer_index': fold,
            'body': body, 'costs': budget.snapshot()}


def iter_outer_reference(fold, budget):
    """Consume through outer_completed; early consumer termination is not completion."""
    cache_bytes = 0
    cache_held = False
    attempts = []
    final = []
    entered = None
    outer = fold.get('outer_index') if type(fold) is dict else None
    order = [s['id'] for s in candidate_specs()]
    inner_people = []
    try:
        names, counts = fold_admit(fold, budget)
        inner_people = names[:25]
        # Source-owned raw descriptive cache; no fitted scaling or target selection.
        cache_bytes = sum(counts) * (70 + 512 + 528 + 3) * 8
        budget.hold(cache_bytes)
        cache_held = True
        train = [_cache_person(p, fold['channel_order'], budget) for p in fold['training']]
        held = _cache_person(fold['held'], fold['channel_order'], budget)
        yield _event('outer_admitted', outer, {'fit_people': inner_people, 'held_person': names[-1],
                                             'trial_counts': counts, 'candidate_order': order,
                                             'raw_descriptor_failures': [{'person_id': p['person_id'], 'failure': p['waveform_failure']}
                                                                         for p in train + [held] if p.get('waveform_failure') is not None]}, budget)
        for validation in train:
            person = validation['person_id']
            fitting = [p for p in train if p['person_id'] != person]
            require(len(fitting) == 24, 'inner_fit_people')
            for spec in candidate_specs():
                entered = {'inner_person': person, 'candidate': spec['id']}
                yield _event('inner_entered', outer, dict(entered), budget)
                try:
                    family = spec['family']
                    design, target, people, trials = _join(fitting, family, fold['channel_order'], budget, True)
                    fit_lineage = _lineage(fold, 'inner_fit', [p['person_id'] for p in fitting])
                    state = fit(spec['id'], design, target, people, trials, fit_lineage, budget)
                    # Every state, including unselected settings, is emitted for retention.
                    yield _event('inner_state', outer, {**entered, 'state': state, 'state_pin': pin(state)}, budget)
                    query, yv, _, tv = _join([validation], family, fold['channel_order'], budget, True)
                    qlineage = _lineage(fold, 'inner_validation', [p['person_id'] for p in fitting], person)
                    prediction = predict(state, query, query['rt_seconds'], query['instruction'], tv, qlineage, budget)
                    np = np_module()
                    values = array(prediction['prediction'], budget, 1)
                    loss = float(np.mean((values - yv) ** 2))
                    require(math.isfinite(loss) and 0 <= loss <= 1, 'inner_mse')
                    budget.tick()
                    row = {**entered, 'status': 'completed', 'loss': loss, 'state_pin': pin(state), 'prediction_pin': pin(prediction)}
                    event = _event('inner_completed', outer, {'record': row, 'prediction': prediction}, budget)
                    attempts.append(row)
                    entered = None
                    yield event
                except Exception as exc:
                    row = {**entered, 'status': 'failed', 'failure': failure(exc, 'inner_fit_predict', budget)}
                    attempts.append(row)
                    entered = None
                    # Failure yield itself requires no fresh capacity: emergency bounded record.
                    yield {'schema': 'neural004_reference_failure_v1', 'outer_index': outer, 'record': row}
                    if is_fatal(exc):
                        raise
                entered = None
        chosen = select({'inner_people': inner_people, 'attempts': attempts})
        yield _event('selection', outer, chosen, budget)
        # Reserve both slots before knowing/relying on exact immutable reuse.
        budget.stage(records=2)
        retained_final = {}
        for role in ('B', 'N'):
            candidate = chosen[role]
            entered = {'final_role': role, 'candidate': candidate}
            yield _event('final_entered', outer, dict(entered), budget)
            if candidate is None:
                row = {**entered, 'status': 'failed', 'failure': {'error_code': 'no_eligible_candidate'}}
                event = _event('final_failed', outer, row, budget)
                final.append(row)
                entered = None
                yield event
                continue
            try:
                if candidate in retained_final:
                    previous = retained_final[candidate]
                    # Identical source/support/query and immutable pins; no second fit claim.
                    row = {**entered, 'status': 'completed', 'reused_role': previous['role'],
                           'state_pin': previous['state_pin'], 'prediction_pin': previous['prediction_pin']}
                    event = _event('final_reused', outer, row, budget)
                    final.append(row)
                    entered = None
                    yield event
                    continue
                spec = specification(candidate)
                design, target, people, trials = _join(train, spec['family'], fold['channel_order'], budget, True)
                fit_lineage = _lineage(fold, 'final_fit', inner_people)
                state = fit(candidate, design, target, people, trials, fit_lineage, budget)
                state_pin = pin(state)
                yield _event('final_state', outer, {**entered, 'state': state, 'state_pin': state_pin}, budget)
                query, _, _, tq = _join([held], spec['family'], fold['channel_order'], budget, False)
                qlineage = _lineage(fold, 'outer_prediction', inner_people, held['person_id'])
                prediction = predict(state, query, query['rt_seconds'], query['instruction'], tq, qlineage, budget)
                prediction_pin = pin(prediction)
                row = {**entered, 'status': 'completed', 'reused_role': None, 'state_pin': state_pin, 'prediction_pin': prediction_pin}
                event = _event('final_completed', outer, {'record': row, 'prediction': prediction}, budget)
                final.append(row)
                entered = None
                retained_final[candidate] = {'role': role, 'state_pin': state_pin, 'prediction_pin': prediction_pin}
                yield event
            except Exception as exc:
                row = {**entered, 'status': 'failed', 'failure': failure(exc, 'final_fit_predict', budget)}
                final.append(row)
                entered = None
                yield {'schema': 'neural004_reference_failure_v1', 'outer_index': outer, 'record': row}
                if is_fatal(exc):
                    raise
            entered = None
        complete = len(attempts) == 575 and len(final) == 2 and all(r['status'] == 'completed' for r in final)
        yield _event('outer_completed', outer, {'attempts': attempts, 'final_slots': final,
                    'selection_deficiencies': chosen['deficiencies'], 'all_attempts_accounted': len(attempts) == 575,
                    'all_final_forecasts_complete': complete, 'scientifically_qualified': False}, budget)
    except Exception as exc:
        completed_pairs = {(r['inner_person'], r['candidate']) for r in attempts}
        unentered = [{'inner_person': p, 'candidate': c} for p in inner_people for c in order
                     if (p, c) not in completed_pairs and {'inner_person': p, 'candidate': c} != entered]
        record = {'outer_index': outer, 'failure': failure(exc, 'outer_reference', budget),
                  'attempt_records': attempts, 'final_slots': final, 'entered_incomplete': entered,
                  'unentered_inner': unentered,
                  'unentered_final_roles': [role for role in ('B', 'N') if role not in {r['final_role'] for r in final}
                                            and (entered is None or entered.get('final_role') != role)],
                  'complete': False}
        # Bounded metadata only, caller must retain exceptions even if its sink fails.
        raise Refusal('outer_reference_incomplete', record) from exc
    finally:
        if cache_held:
            budget.release(cache_bytes)


def fit_full_reference(folds, budget):
    """Exactly 26 explicit folds; no scientific results or finished-output callbacks."""
    require(type(folds) in (list, tuple) and len(folds) == 26, 'complete_26_fold_inputs')
    require([f.get('outer_index') if type(f) is dict else None for f in folds] == list(range(26)), 'ordered_outer_indices')
    # Admission of identity geometry precedes any calculation; body access stays per fold.
    held = [identity(f['held']['person_id']) for f in folds]
    require(len(set(held)) == 26, 'full_held_people_unique')
    for f in folds:
        require(type(f.get('training')) is list and len(f['training']) == 25 and
                {p['person_id'] for p in f['training']} == set(held) - {f['held']['person_id']}, 'full_outer_partition')
    outer_records = []
    try:
        for f in folds:
            last = None
            for event in iter_outer_reference(f, budget):
                if event.get('kind') == 'outer_completed':
                    last = event
                yield event
            require(last is not None, 'missing_outer_closure')
            outer_records.append({'outer_index': f['outer_index'], 'closure_pin': pin(last),
                                  'forecasts_complete': last['body']['all_final_forecasts_complete']})
        yield _event('full_completed', None, {'outer_records': outer_records, 'outer_contexts': 26,
                    'inner_contexts': 650, 'inner_attempts': 14950, 'final_slots': 52,
                    'all_forecasts_complete': all(x['forecasts_complete'] for x in outer_records),
                    'scientifically_qualified': False}, budget)
    except Exception as exc:
        raise Refusal('full_reference_incomplete', {'completed_outer': outer_records,
                     'next_outer': len(outer_records), 'unentered_outer': list(range(len(outer_records) + 1, 26)),
                     'failure': failure(exc, 'full_reference', budget),
                     'nested_failure': exc.record if isinstance(exc, Refusal) else None}) from exc

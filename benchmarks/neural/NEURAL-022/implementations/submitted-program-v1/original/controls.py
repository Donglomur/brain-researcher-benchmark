"""Invented scalar/array controls, executed only by a future admitted trusted worker."""
import copy
import hashlib
import json
import math
import numpy as np
import candidate
import held_scorer
import packet
import io_support

NAMES = (
    'complete_candidate_zero_scored', 'valid_poor_candidate_retained',
    'candidate_never_relabels_active_reference', 'all_seven_signed_comparisons',
    'equal_trial_not_direction_macro', 'missing_last_rejected_before_private',
    'extra_row_rejected_before_private', 'duplicate_id_rejected_before_private',
    'reordered_id_rejected_before_private', 'unknown_id_rejected_before_private',
    'boolean_velocity_rejected_before_private', 'nonfinite_velocity_rejected_before_private',
    'wrong_shape_rejected_before_private', 'extra_field_rejected_before_private',
    'wrong_schema_rejected_before_private', 'duplicate_json_rejected_before_private',
    'trailing_json_rejected_before_private', 'finite_extreme_not_clipped_or_good_score',
    'full_support_projection', 'source_row_metadata_removed', 'public_fields_exclude_private_labels',
    'private_reference_identity_preserved', 'missing65th_unit_rejected',
    'target_id_mismatch_rejected', 'negative_spike_count_rejected',
    'private_reference_member_missing_rejected', 'passive_train_packet_unavailable',
    'bounded_archive_roundtrip', 'archive_extra_member_rejected',
    'archive_wrong_dtype_rejected', 'archive_wrong_shape_rejected',
    'archive_object_dtype_rejected', 'reference_scalar_mismatch_is_operator_failure',
    'negative_candidate_gap_preserves_original_reference_primary',
)


def run():
    done = []
    def check(name, ok):
        candidate.need(ok, 'Generated control: ' + name); done.append(name)
    rows = []
    for mode, counts in (('passive', [5, 3, 3, 6, 3, 6, 6, 8]),
                         ('active', [10, 7, 8, 6, 4, 11, 3, 3])):
        for d, n in zip(candidate.DIRECTIONS, counts):
            start = len(rows)
            rows.extend({'id': f'{start+i:024x}', 'mode': mode, 'direction': d} for i in range(n))
    public = {'schema': 'neural022_public_cases_v1', 'cases': rows}
    ids = [r['id'] for r in rows]
    private = {'ids': ids, 'velocity': [[0., 0.] for _ in ids],
               'references': {m: [[0., 0.] for _ in ids] for m in candidate.METHODS}}
    truth = [{'id': i, 'velocity': v} for i, v in zip(ids, private['velocity'])]
    expected = held_scorer.score(rows, truth, {m: truth for m in candidate.METHODS})
    def submission(value=0.):
        return {'schema': candidate.SCHEMA,
                'predictions': [{'id': i, 'velocity': [value, 0.]} for i in ids]}
    def encoded(obj):
        return json.dumps(obj, separators=(',', ':')).encode()
    calls = []
    def loader():
        calls.append(True); return copy.deepcopy(private)
    def evaluate(obj):
        calls.clear()
        return candidate.evaluate(obj if type(obj) is bytes else encoded(obj), public,
                                  loader, held_scorer.score, expected)
    good = evaluate(submission())
    check(NAMES[0], good['status'] == 'scored_exposed_transfer_candidate'
          and good['primary_score'] == 0 and calls == [True])
    poor = evaluate(submission(1000.))
    check(NAMES[1], poor['status'] == 'scored_exposed_transfer_candidate'
          and poor['primary_score'] == 1000000. and poor['candidate_minus_fixed_passive_neural'] == 1000000.)
    check(NAMES[2], poor['candidate_identity'] == 'candidate_program'
          and poor['original_reference_diagnostic']['value'] == 0.
          and poor['original_reference_diagnostic']['candidate_is_not_active_neural'] is True
          and poor['method_provenance_verified'] is False)
    check(NAMES[3], all(set(poor['metrics'][m]['candidate_minus_fixed_reference'])
                       == set(candidate.METHODS) for m in ('passive', 'active')))
    uneven = submission()
    for out, row in zip(uneven['predictions'], rows):
        out['velocity'][0] = 1. if row['direction'] == 45 else 2.
    unequal = evaluate(uneven)
    check(NAMES[4], unequal['primary_score'] == (3 + 37 * 4) / 40
          and unequal['primary_score'] != (1 + 7 * 4) / 8)
    mutations = []
    v = submission(); v['predictions'].pop(); mutations.append(v)
    v = submission(); v['predictions'].append(copy.deepcopy(v['predictions'][0])); mutations.append(v)
    v = submission(); v['predictions'][-1]['id'] = ids[0]; mutations.append(v)
    v = submission(); v['predictions'].reverse(); mutations.append(v)
    v = submission(); v['predictions'][-1]['id'] = 'f' * 24; mutations.append(v)
    v = submission(); v['predictions'][-1]['velocity'][0] = True; mutations.append(v)
    v = submission(); v['predictions'][-1]['velocity'][0] = float('nan'); mutations.append(v)
    v = submission(); v['predictions'][-1]['velocity'].pop(); mutations.append(v)
    v = submission(); v['predictions'][-1]['target'] = 0.; mutations.append(v)
    v = submission(); v['schema'] = 'active_neural'; mutations.append(v)
    mutations += [encoded(submission()).replace(b'"schema":', b'"schema":"duplicate","schema":', 1),
                  encoded(submission()) + b'{}']
    for name, changed in zip(NAMES[5:17], mutations):
        result = evaluate(changed)
        check(name, result['status'] == 'invalid_submission'
              and result['private_target_loads'] == 0 and calls == [])
    huge = evaluate(submission(1e308))
    check(NAMES[17], huge['status'] == 'unsupported_numerical_result'
          and huge['primary_score'] is None and calls == [True])
    active = {'ids': np.array([f'{i+1000:024x}' for i in range(141)], dtype='<U24'),
              'counts': np.zeros((141, 390), dtype='<i8'), 'velocity': np.zeros((141, 2), dtype='<f8'),
              'source_rows': np.arange(141, dtype='<i8'),
              'directions': np.array([45*(i % 8) for i in range(141)], dtype='<i8')}
    query = {'ids': np.array(ids, dtype='<U24'), 'counts': np.zeros((92, 390), dtype='<i8'),
             'directions': np.array([r['direction'] for r in rows], dtype='<i8'),
             'modes': np.array([r['mode'] for r in rows], dtype='<U7')}
    target = {'ids': query['ids'].copy(), 'velocity': np.zeros((92, 2), dtype='<f8')}
    refs = {'ids': query['ids'].copy(), **{m: np.zeros((92, 2), dtype='<f8') for m in candidate.METHODS}}
    train, queries, roster, sealed = packet.sanitize(active, query, target, refs)
    check(NAMES[18], train['counts'].shape == (141, 390) and queries['counts'].shape == (92, 390)
          and roster == public)
    check(NAMES[19], 'source_rows' not in train and 'source_rows' not in queries)
    check(NAMES[20], set(train) == {'ids', 'counts', 'velocity', 'directions'}
          and set(queries) == {'ids', 'counts', 'directions', 'modes'})
    check(NAMES[21], all(np.array_equal(sealed[m], refs[m]) for m in candidate.METHODS)
          and np.array_equal(sealed['velocity'], target['velocity']))
    def reject(name, args):
        try:
            packet.sanitize(*args)
        except ValueError:
            check(name, True); return
        check(name, False)
    bad = copy.deepcopy(query); bad['counts'] = bad['counts'][:, :-1]
    reject(NAMES[22], (active, bad, target, refs))
    bad = copy.deepcopy(target); bad['ids'][-1] = 'f'*24
    reject(NAMES[23], (active, query, bad, refs))
    bad = copy.deepcopy(active); bad['counts'][0, 0] = -1
    reject(NAMES[24], (bad, query, target, refs))
    bad = copy.deepcopy(refs); del bad['zero']
    reject(NAMES[25], (active, query, target, bad))
    check(NAMES[26], set(sealed) == {'ids', 'velocity', *candidate.METHODS}
          and not any('passive_training' in k for value in (train, queries, sealed) for k in value))
    schema = io_support.schema('target', candidate.METHODS)
    parsed = io_support.npz(io_support.encoded_npz(target), schema)
    check(NAMES[27], all(np.array_equal(parsed[k], target[k]) for k in target))
    changed = [dict(target, hidden=np.zeros(1)), dict(target, velocity=target['velocity'].astype('<f4')),
               dict(target, velocity=target['velocity'][:-1]),
               dict(target, velocity=target['velocity'].astype(object))]
    for name, value in zip(NAMES[28:32], changed):
        try:
            io_support.npz(io_support.encoded_npz(value), schema)
        except ValueError:
            check(name, True)
        else:
            check(name, False)
    wrong = copy.deepcopy(expected); wrong['losses']['passive']['zero'] = 1.
    try:
        candidate.evaluate(encoded(submission()), public, loader, held_scorer.score, wrong)
    except ValueError:
        check(NAMES[32], True)
    else:
        check(NAMES[32], False)
    distinct = copy.deepcopy(private)
    distinct['references']['active_neural'] = [[2., 0.] for _ in ids]
    distinct['references']['passive_neural'] = [[1., 0.] for _ in ids]
    distinct_expected = held_scorer.score(rows, truth, {
        m: [{'id': i, 'velocity': v} for i, v in zip(ids, distinct['references'][m])]
        for m in candidate.METHODS})
    signed = candidate.evaluate(encoded(submission()), public, lambda: distinct,
                                held_scorer.score, distinct_expected)
    check(NAMES[33], signed['candidate_minus_fixed_passive_neural'] == -1.
          and signed['original_reference_diagnostic']['value'] == 3.
          and signed['candidate_identity'] == 'candidate_program')
    candidate.need(done == list(NAMES), 'Complete fixed generated control list')
    return dict(status='passed', count=len(done), names=done,
                names_sha256=hashlib.sha256('\n'.join(done).encode()).hexdigest(),
                empirical_reads=0, empirical_fits=0, controls_use_only_invented_inputs=True)

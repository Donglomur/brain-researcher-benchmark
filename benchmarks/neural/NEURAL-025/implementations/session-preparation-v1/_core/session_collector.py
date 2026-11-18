"""Complete fixed-census collection for the existing NEURAL-025 angle condition.

Pure orchestration: callers own authenticated input handles and bounded exports.
Fail-fast retains an explicit disposition for every original record. A partial
export is never a completed session. No split, fit, score or new endpoint exists.
"""
import hashlib
import math
import re
import numpy as np


STAGES = ('neural_padded', 'neural_smoothed_padded', 'neural_prepared',
          'joint_smoothed_full', 'joint_prepared', 'neural_eval', 'joint_eval')


class CollectionRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise CollectionRefusal(message)


def payload_hash(value):
    return hashlib.sha256(value.astype('<f8', copy=False).tobytes(order='C')).hexdigest()


def check_contract(c):
    require(type(c) is dict and set(c) == {'schema', 'session_id', 'source_sha256',
        'metadata_sha256', 'roi_indices', 'joint_labels', 'shared_camera_step_ms',
        'first_camera_ordinal', 'first_neural_ordinal', 'cycle_ms', 'trials',
        'raw_trial_count', 'eligible_trial_count', 'author_excluded_trial_count'}, 'Exact session contract')
    require(c['schema'] == 'calcium-session-pair-contract-v1' and
            type(c['session_id']) is str and 0 < len(c['session_id']) <= 128, 'Session identity')
    require(all(type(c[k]) is str and re.fullmatch('[0-9a-f]{64}', c[k])
                for k in ('source_sha256', 'metadata_sha256')), 'Source/metadata hashes')
    rois, labels, rows = c['roi_indices'], c['joint_labels'], c['trials']
    require(type(rois) is list and 1 <= len(rois) <= 565 and
            all(type(x) is int and 0 < x <= 1000000 for x in rois) and len(set(rois)) == len(rois),
            'Unique ordered session-local ROI indices')
    require(type(labels) is list and len(labels) == 24 and
            all(type(x) is str and 0 < len(x) <= 64 for x in labels) and len(set(labels)) == 24,
            'Exactly 24 ordered source labels')
    require(type(rows) is list and 0 < len(rows) <= 416, 'Bounded complete census')
    ids, eligible = set(), []
    for ordinal, row in enumerate(rows, 1):
        require(type(row) is dict and set(row) == {'ordinal', 'trial_number', 'eligible',
                    'exclusion_reasons', 'frame_rows', 'camera_rows', 'LR'}, 'Exact original trial record')
        require(type(row['ordinal']) is int and row['ordinal'] == ordinal and
                type(row['trial_number']) is int and row['trial_number'] > 0 and
                row['trial_number'] not in ids, 'Complete ordered ordinals and unique original IDs')
        ids.add(row['trial_number'])
        require(type(row['eligible']) is bool and type(row['exclusion_reasons']) is list and
                all(type(x) is str and 0 < len(x) <= 128 for x in row['exclusion_reasons']),
                'Explicit eligibility and source exclusions')
        if row['eligible']:
            require(not row['exclusion_reasons'] and type(row['frame_rows']) is int and
                    2 <= row['frame_rows'] <= 20000 and row['frame_rows'] * len(rois) <= 1000000 and
                    type(row['camera_rows']) is int and 2 <= row['camera_rows'] <= 20000 and
                    row['camera_rows'] * 24 <= 480000 and type(row['LR']) is int and row['LR'] in (1, 2),
                    'Eligible shape/target contract')
            eligible.append(row)
        else:
            require(bool(row['exclusion_reasons']), 'Excluded trial requires original reasons')
    require(eligible and len(eligible) <= 372, 'Nonempty bounded eligible set')
    require(type(c['raw_trial_count']) is int and c['raw_trial_count'] == len(rows) and
            type(c['eligible_trial_count']) is int and c['eligible_trial_count'] == len(eligible) and
            type(c['author_excluded_trial_count']) is int and
            c['author_excluded_trial_count'] == len(rows) - len(eligible), 'Frozen source support counts differ')
    eligible_ordinals = {r['ordinal'] for r in eligible}
    require(type(c['first_camera_ordinal']) is int and c['first_camera_ordinal'] in eligible_ordinals and
            type(c['first_neural_ordinal']) is int and c['first_neural_ordinal'] in eligible_ordinals,
            'Shared reference trials must be source eligible')
    require(type(c['shared_camera_step_ms']) in (int, float) and
            math.isfinite(c['shared_camera_step_ms']) and c['shared_camera_step_ms'] >= 15 / 16 and
            type(c['cycle_ms']) in (int, float) and math.isfinite(c['cycle_ms']) and c['cycle_ms'] >= 10,
            'Fixed shared source time bases')
    return eligible


def collect_session(contract, read_trial, pair_trial, reference_pair, sink):
    eligible = check_contract(contract)
    nroi = len(contract['roi_indices'])
    dispositions = [dict(row, status='pending' if row['eligible'] else 'author_excluded')
                    for row in contract['trials']]
    receipt = {'schema': 'calcium-session-pair-collection-v1', 'completed': False,
               'session_id': contract['session_id'], 'source_sha256': contract['source_sha256'],
               'metadata_sha256': contract['metadata_sha256'],
               'roi_indices': list(contract['roi_indices']), 'joint_labels': list(contract['joint_labels']),
               'joint_labels_are_author_loader_assigned': True,
               'cached_anatomical_lineage_verified': False,
               'first_camera_ordinal': contract['first_camera_ordinal'],
               'first_neural_ordinal': contract['first_neural_ordinal'],
               'shared_camera_step_ms': contract['shared_camera_step_ms'],
               'cycle_ms': contract['cycle_ms'],
               'padded_grid_ms': list(range(-270, 871, 10)),
               'prepared_grid_ms': list(range(-200, 801, 10)),
               'evaluation_grid_ms': list(range(-100, 401, 10)),
               'dispositions': dispositions, 'paired_trials': 0,
               'failure_policy': 'fail_fast_with_all_remaining_eligible_trials_not_attempted',
               'native_matlab_parity': False, 'scientific_score': False,
               'fit_or_split_selected': False, 'whole_mouse_endpoint_complete': False}
    current = None
    try:
        for output_index, row in enumerate(eligible):
            current = dispositions[row['ordinal'] - 1]
            item = read_trial(row['ordinal'])
            require(type(item) is dict and 'inputs' in item and 'projection' in item, 'Projection record required')
            identity, inputs = item['projection'], item['inputs']
            require(identity.get('session_id') == contract['session_id'] and
                    identity.get('original_trial_number') == row['trial_number'] and
                    identity.get('raw_ordinal_one_based') == row['ordinal'] and
                    identity.get('all_session_local_roi_columns') == nroi and
                    identity.get('joint_columns_preserved') == 24, 'Projection original identity mismatch')
            require(type(inputs) in (tuple, list) and len(inputs) == 9, 'Complete pairing inputs')
            require(inputs[5] == contract['cycle_ms'] and
                    inputs[8] == contract['shared_camera_step_ms'], 'Shared source time base changed')
            input_shapes = ((row['frame_rows'], nroi), (row['camera_rows'], 24),
                            (row['camera_rows'],), (row['frame_rows'],), (nroi,))
            for value, shape in zip(inputs[:5], input_shapes):
                require(type(value) is np.ndarray and value.dtype == np.dtype('float64') and
                        value.shape == shape and bool(np.isfinite(value).all()), 'Exact finite projected arrays')
            current['input_hashes'] = [payload_hash(v) for v in inputs[:5]]
            actual, expected = pair_trial(*inputs), reference_pair(*inputs)
            exact = (('padded_grid_ms', 'padded_times_ms'), ('prepared_grid_ms', 'prepared_times_ms'),
                     ('evaluation_grid_ms', 'evaluation_times_ms'),
                     ('early_frame_indices_one_based', 'neural_early_frames_one_based'),
                     ('late_frame_indices_one_based', 'neural_late_frames_one_based'))
            require(all(np.array_equal(actual[left], expected[right]) for left, right in exact),
                    'Reference grid or source frame indices differ')
            require(np.array_equal(actual['padded_grid_ms'], receipt['padded_grid_ms']) and
                    np.array_equal(actual['prepared_grid_ms'], receipt['prepared_grid_ms']) and
                    np.array_equal(actual['evaluation_grid_ms'], receipt['evaluation_grid_ms']),
                    'Canonical source grids changed')
            coords, refcoords = actual['frame_coordinates_one_based'], expected['neural_frame_coordinates_one_based']
            require(coords.shape == refcoords.shape == (115, nroi) and
                    np.isfinite(coords).all() and np.isfinite(refcoords).all() and
                    np.allclose(coords, refcoords, rtol=1e-12, atol=1e-12), 'Reference coordinates differ')
            shapes = ((115, nroi), (115, nroi), (101, nroi),
                      (row['camera_rows'], 24), (101, 24), (51, nroi), (51, 24))
            stage_rows = {}
            for name, shape in zip(STAGES, shapes):
                left, right = actual[name], expected[name]
                require(type(left) is np.ndarray and type(right) is np.ndarray and
                        left.dtype == right.dtype == np.dtype('float64') and left.shape == right.shape == shape and
                        np.isfinite(left).all() and np.isfinite(right).all() and
                        np.allclose(left, right, rtol=1e-12, atol=1e-12), 'Reference stage mismatch: ' + name)
                stage_rows[name] = {'shape': list(shape), 'dtype': '<f8', 'order': 'C',
                    'values_sha256': payload_hash(left),
                    'reference_maximum_absolute_error': float(np.abs(left - right).max())}
            written = sink.write_trial(output_index, actual['neural_eval'], actual['joint_eval'])
            require(type(written) is dict and written.get('index') == output_index and
                    written.get('neural_values_sha256') == stage_rows['neural_eval']['values_sha256'] and
                    written.get('joint_values_sha256') == stage_rows['joint_eval']['values_sha256'] and
                    written.get('payload_bytes') == 51 * (nroi + 24) * 8, 'Export row acknowledgement mismatch')
            current.update(status='paired', output_trial_index_zero_based=output_index,
                           stage_hashes=stage_rows, frame_coordinates_sha256=payload_hash(coords),
                           frame_coordinates_maximum_absolute_error=float(np.abs(coords - refcoords).max()),
                           export=written)
            receipt['paired_trials'] += 1
            current = None
            # No collection of full stage arrays, projections or reference scratch.
            del actual, expected, item, inputs, coords, refcoords
        exported = sink.finish()
        require(type(exported) is dict and exported.get('completed') is True and
                exported.get('trial_count') == len(eligible), 'Complete export census required')
        for name, width in (('neural', nroi), ('joint', 24)):
            value = exported.get(name, {})
            require(value.get('shape') == [len(eligible), 51, width] and
                    type(value.get('bytes')) is int and value['bytes'] > len(eligible) * 51 * width * 8 and
                    type(value.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
                    'Complete export shape and identity required')
        receipt.update(completed=True, exports=exported)
    except BaseException as exc:
        if current is not None:
            current.update(status='failed', failure={'kind': type(exc).__name__, 'detail': str(exc)[:512]})
        receipt['failure'] = {'kind': type(exc).__name__, 'detail': str(exc)[:512],
                              'stage': 'eligible_trial' if current is not None else 'export_finalization'}
        for row in dispositions:
            if row['status'] == 'pending':
                row['status'] = 'not_attempted_after_failure'
        try:
            receipt['partial_exports'] = sink.abort()
        except BaseException as abort_error:
            receipt['partial_export_cleanup_error'] = {'kind': type(abort_error).__name__,
                                                       'detail': str(abort_error)[:512]}
    receipt['counts'] = {status: sum(row['status'] == status for row in dispositions)
                        for status in ('author_excluded', 'paired', 'failed', 'not_attempted_after_failure')}
    require(sum(receipt['counts'].values()) == len(dispositions), 'Every original record requires a disposition')
    require(not receipt['completed'] or receipt['counts']['paired'] == len(eligible), 'Complete eligible support')
    return receipt

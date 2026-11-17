"""Pure acceptance checks for the full-panel, nonlearning ratio-one control.

These checks describe one exposed engineering control. They do not turn a
successful arbitrary programme into a matched-method scientific comparison.
"""
import math


def need(condition, message):
    if not condition:
        raise ValueError(message)


def validate_probe(value):
    keys = {'schema', 'python', 'numpy', 'uid', 'gid',
            'fresh_tmp_marker_before_creation', 'empty_output_before_prediction',
            'write_denial_errnos', 'network_denial_errno',
            'network_probe_timeout_seconds', 'scope'}
    need(type(value) is dict and set(value) == keys,
         'Exact fixed-control runtime report required')
    need(value['schema'] == 'neural031_fixed_control_runtime_probe_v1'
         and value['python'] == '3.12.8' and value['numpy'] == '2.2.6'
         and type(value['uid']) is int and value['uid'] == 65534
         and type(value['gid']) is int and value['gid'] == 65534,
         'Selected immutable Linux image package and user profile')
    need(value['fresh_tmp_marker_before_creation'] is True
         and value['empty_output_before_prediction'] is True,
         'Every selected context must report fresh temporary and output state')
    denials = value['write_denial_errnos']
    # Linux errno values are explicit: this verifier may run on a macOS host.
    need(type(denials) is dict and set(denials) == {'root', 'data', 'manifest', 'program'}
         and all(type(v) is int and v in {1, 13, 30} for v in denials.values()),
         'All four fixed writes must fail with an explicit Linux permission denial')
    need(type(value['network_denial_errno']) is int
         and value['network_denial_errno'] in {1, 13, 100, 101, 113}
         and type(value['network_probe_timeout_seconds']) in (int, float)
         and value['network_probe_timeout_seconds'] == 0.25,
         'Documented bounded network probe must explicitly deny access')
    need(value['scope'] == 'observed_fixed_probes_not_universal_isolation_proof',
         'Keep the limited meaning of fixed runtime probes')
    return value


def validate_constant_predictions(endpoint, bundle, support):
    predictions = endpoint.validate_all(bundle, support)
    expected = {(fold, view) for fold in range(20) for view in ('baseline', 'neural')}
    need(set(predictions) == expected
         and sum(len(rows) for rows in predictions.values()) == 1548
         and all(value == 1.0 for rows in predictions.values() for value in rows),
         'All 774 requests in both conditions require the exact fixed ratio-one prediction')
    return {'contexts': 40, 'predictions': 1548, 'requests_per_condition': 774,
            'constant_ratio': 1.0}


def validate_constant_score(score):
    need(type(score) is dict and score.get('schema') == 'neural031_ratio_score_v1'
         and score.get('candidate_id') == 'NEURAL-031'
         and score.get('raw_rows') == 1143 and score.get('request_rows') == 774
         and score.get('scored_rows') == 731 and score.get('unavailable_rows') == 43,
         'Unchanged complete observed-ratio scoring support')
    need(score.get('primary_metric') == 'equal_mouse_baseline_minus_neural_mae'
         and type(score.get('primary')) in (int, float) and score.get('primary') == 0.0
         and type(score.get('positive_mouse_differences')) is int
         and score.get('positive_mouse_differences') == 0,
         'The identical fixed methods have exactly zero paired gain')
    rows = score.get('mice')
    need(type(rows) is list and len(rows) == 20,
         'Every original mouse must appear in the control result')
    for fold, row in enumerate(rows):
        need(type(row) is dict and type(row.get('fold')) is int and row.get('fold') == fold
             and row.get('baseline_minus_neural_mae') == 0.0,
             'Every original mouse has zero fixed-control gain')
    for row in rows + [score.get('macro')]:
        need(type(row) is dict, 'Complete per-mouse and macro control scores')
        need(type(row.get('baseline_minus_neural_mae')) in (int, float)
             and row['baseline_minus_neural_mae'] == 0.0,
             'Every saved mouse and macro gain equals zero')
        values = [row.get(k) for k in ('baseline_mae', 'neural_mae', 'no_change_mae')]
        need(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values)
             and values[0] == values[1] == values[2],
             'Both fixed arms equal the unchanged no-change reference')
    return {'observed_rows': 731, 'requested_unavailable_rows': 43,
            'paired_gain': 0.0, 'matched_constant_control_only': True,
            'AI_result': False, 'native_neural_understanding_result': False}

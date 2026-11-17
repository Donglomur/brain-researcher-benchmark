"""Eight invented grader guard groups. Authored source; no empirical inputs."""
import copy
import hashlib
import json
import math

NAMES = [
    'complete17_34_envelope',
    'strict_utf8_and_surrogates',
    'nonfinite_bool_range_literals',
    'complete_public_support',
    'constant_perfect_and_tied_metrics',
    'fixed_support_mismatch_penalty',
    'macro34_and_orientation',
    'lazy_private_gate_and_output_bounds',
]


def encoded(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def fixture():
    manifest = {'schema': 'thalamus_figure3C_reconstruction_sessions_v1', 'panel': '3C',
                'session_count': 17, 'condition_count': 34,
                'conditions': ['Laser_OFF', 'Laser_ON'], 'sessions': []}
    expected = {'actual_index': {'fixture': 'index'}, 'joined_scalars': {'fixture': 'scalars'},
                'image': {'fixture': 'image'}, 'protocol': {'fixture': 'protocol'}, 'cells': []}
    reference = {'schema': 'thalamus_figure3C_fixed_reference_v1',
                 'source_actual_index': expected['actual_index'],
                 'source_joined_scalars': expected['joined_scalars'],
                 'reference_image': expected['image'], 'protocol': expected['protocol'],
                 'native_model_fits': 0, 'assembled_from_saved_outputs': True, 'cells': []}
    pairs = []
    for index in range(1, 18):
        identity = 'invented_session_' + str(index)
        session = {'cohort_index': index, 'experiment_id': identity, 'condition_specs': {}}
        pair = {'schema': 'thalamus_figure3C_candidate_pair_v1', 'cohort_index': index,
                'experiment_id': identity, 'conditions': []}
        for condition in manifest['conditions']:
            # Explicit odd143-row test support without any empirical values.
            test_count = 143 if index == 17 and condition == 'Laser_OFF' else 4
            positives = test_count // 2
            labels = ['Randomised'] * positives + ['Regular'] * (test_count - positives)
            session['condition_specs'][condition] = {
                'trial_rows': test_count + 4, 'training_rows': 4, 'test_rows': test_count,
                'feature_count_upper_bound': 2,
                'test_class_counts': {'Randomised': positives, 'Regular': test_count - positives}}
            cell = {'condition': condition, 'feature_order': ['uuid_invented'],
                    'training_rows': [1, 2, 3, 4], 'test_rows': list(range(5, test_count + 5)),
                    'probability_randomised': [.75 if label == 'Randomised' else .25 for label in labels]}
            source = {'predictions': {'fixture': [index, condition, 'predictions']},
                      'split': {'fixture': [index, condition, 'split']}}
            expected['cells'].append(source)
            reference['cells'].append(dict(copy.deepcopy(cell), cohort_index=index,
                experiment_id=identity, labels=labels,
                source_predictions=source['predictions'], source_split=source['split']))
            pair['conditions'].append(cell)
        manifest['sessions'].append(session)
        pairs.append(pair)
    return manifest, expected, reference, pairs


def run(core):
    manifest, expected, reference, pairs = fixture()
    raw = [encoded(pair) for pair in pairs]
    records = []; assertions = 0; synthetic_calls = 0

    def check(ok, message):
        nonlocal assertions
        assertions += 1
        if not ok:
            raise ValueError('Invented grader guard: ' + message)

    def grade(payload, fixed=None):
        nonlocal synthetic_calls
        calls = []
        def loader():
            nonlocal synthetic_calls
            calls.append(True); synthetic_calls += 1
            return copy.deepcopy(reference if fixed is None else fixed)
        result = core.score(payload, manifest, expected, loader)
        check(result['private_loader_calls'] == len(calls), 'Synthetic private callback accounting')
        return result, len(calls)

    def reject(payload, reason):
        result, calls = grade(payload)
        check(result['status'] == 'invalid_submission' and result['primary_metric'] is None
              and calls == 0 and result['private_reference_reads'] == 0, reason)

    def altered(change):
        value = copy.deepcopy(pairs)
        change(value)
        return [encoded(x) for x in value]

    def end(name, before):
        records.append({'name': name, 'status': 'passed', 'assertions': assertions - before})

    before = assertions
    result, calls = grade(raw)
    check(result['status'] == 'scored' and calls == 1 and result['primary_metric'] == 0
          and result['primary_denominator'] == 34 and len(result['cells']) == 34
          and len(result['sessions']) == 17 and result['comparable_cells'] == 34,
          'Complete invented reference agreement')
    check(len(result['_statistics_input']['candidate']) == 17
          and len(result['_statistics_input']['reference']) == 17
          and result['cells'][32]['reference_test_rows'] == 143,
          'Complete statistical input and odd test count')
    reject(raw[:-1], 'No omitted seventeenth session')
    reject(altered(lambda p: p[0]['conditions'].pop()), 'No omitted condition')
    reject(altered(lambda p: p.reverse()), 'No reordered sessions')
    end(NAMES[0], before)

    before = assertions
    for bad in (raw[0].decode('utf-8').encode('utf-16'), b'\xff' + raw[0],
                raw[0].replace(b'uuid_invented', b'uuid_\\ud800')):
        reject([bad] + raw[1:], 'Strict UTF8 and no lone surrogate')
    reject([b'{"schema":"duplicate",' + raw[0][1:]] + raw[1:], 'Duplicate key rejected')
    reject([raw[0] + b'{}'] + raw[1:], 'Trailing JSON rejected')
    end(NAMES[1], before)

    before = assertions
    for value in (True, False, -0.1, 1.1, 10**400):
        reject(altered(lambda p, value=value: p[0]['conditions'][0]['probability_randomised'].__setitem__(0, value)),
               'Probability type and range')
    for literal in (b'NaN', b'Infinity', b'-Infinity', b'1e309', b'1e-999'):
        reject([raw[0].replace(b'0.75', literal, 1)] + raw[1:], 'Invalid or destructive numeric literal')
    end(NAMES[2], before)

    before = assertions
    reject(altered(lambda p: p[0]['conditions'][0]['test_rows'].__setitem__(0, 1)), 'Partition overlap')
    reject(altered(lambda p: p[0]['conditions'][0]['training_rows'].__setitem__(0, True)), 'Boolean row ID')
    reject(altered(lambda p: p[0]['conditions'][0]['probability_randomised'].pop()), 'Missing probability')
    reject(altered(lambda p: p[0]['conditions'][0]['feature_order'].append('uuid_invented')), 'Duplicate feature')
    reject(altered(lambda p: p[0].__setitem__('claimed_score', 0)), 'No candidate metric injection')
    reject(altered(lambda p: p[0]['conditions'].reverse()), 'Condition order')
    reject([b' ' * (core.PAIR_CAP + 1)] + raw[1:], 'Per-pair byte cap')
    end(NAMES[3], before)

    before = assertions
    labels = ['Randomised', 'Randomised', 'Regular', 'Regular']
    constant, prediction = core.metrics([.5] * 4, labels)
    perfect, _ = core.metrics([1., 1., 0., 0.], labels)
    reversed_metrics, _ = core.metrics([0., 0., 1., 1.], labels)
    tied, _ = core.metrics([.5, .8, .5, .2], labels)
    check(constant['fixed_auc'] == constant['source_auto_auc'] == constant['accuracy'] == .5
          and constant['source_auto_direction'] == '<'
          and prediction == ['Randomised'] * 4, 'Constant ties and threshold')
    check(perfect['fixed_auc'] == perfect['accuracy'] == 1.
          and reversed_metrics['fixed_auc'] == 0. and reversed_metrics['source_auto_auc'] == 1.,
          'Perfect and inverted orientation remain distinct')
    check(tied['fixed_auc'] == .875 and sum(x['count'] for x in tied['confusion']) == 4,
          'Tie-aware AUC and full confusion count')
    constant_payload = altered(lambda p: [c.__setitem__('probability_randomised', [.5]*len(c['test_rows'])) for x in p for c in x['conditions']])
    constant_score, _ = grade(constant_payload)
    perfect_payload = altered(lambda p: [c.__setitem__('probability_randomised', [1. if q > .5 else 0. for q in c['probability_randomised']]) for x in p for c in x['conditions']])
    perfect_score, _ = grade(perfect_payload)
    check(constant_score['primary_metric'] == perfect_score['primary_metric'] == .25,
          'AUC1 receives no reproduction bonus over equal-error constant')
    end(NAMES[4], before)

    before = assertions
    mismatch, _ = grade(altered(lambda p: p[0]['conditions'][0].__setitem__('feature_order', ['uuid_other'])))
    check(mismatch['primary_metric'] == 1/34 and mismatch['support_mismatch_cells'] == 1
          and mismatch['cells'][0]['primary_cell_error'] == 1.
          and mismatch['cells'][0]['candidate_metrics'] is None
          and mismatch['primary_denominator'] == 34 and '_statistics_input' not in mismatch
          and mismatch['whole17_statistics_status'] == 'not_computed_incomplete_fixed_support',
          'Valid support mismatch retained with worst cell penalty and no subset statistics')
    check(mismatch['sessions'][0]['contrasts'] is None and len(mismatch['sessions']) == 17,
          'Mismatch session retained')
    end(NAMES[5], before)

    before = assertions
    def invert_one(p):
        c = p[16]['conditions'][0]
        c['probability_randomised'] = [1-v for v in c['probability_randomised']]
    one, _ = grade(altered(invert_one))
    check(one['primary_metric'] == .5/34 and one['cells'][32]['primary_cell_error'] == .5,
          'Equal cell weight for143-row cell')
    check(one['cells'][32]['fixed_auc_absolute_error'] == 1.
          and one['cells'][32]['source_auto_auc_absolute_error'] == 0.
          and one['cells'][32]['accuracy_absolute_error_percentage_points'] == 100.,
          'Auto direction does not hide fixed orientation or accuracy disagreement')
    check(one['sessions'][16]['contrasts']['accuracy']['candidate_ON_minus_OFF'] == 100.
          and one['sessions'][16]['contrasts']['accuracy']['reference_ON_minus_OFF'] == 0.,
          'Signed ON-minus-OFF and percentage-point units')
    check(one['whole17_statistics_status'] == 'pending_R431'
          and len(one['_statistics_input']['candidate']) == 17, 'Whole17 retained without significance threshold')
    end(NAMES[6], before)

    before = assertions
    reject(raw[:16] + [b'{}'], 'Last-pair invalidity blocks all private callbacks')
    tiny_reference = copy.deepcopy(reference)
    tiny_reference['cells'][0]['probability_randomised'] = [0.] * 4
    tiny_pairs = copy.deepcopy(pairs)
    tiny_pairs[0]['conditions'][0]['probability_randomised'] = [5e-324, 0., 0., 0.]
    tiny, _ = grade([encoded(x) for x in tiny_pairs], tiny_reference)
    check(tiny['status'] == 'scored' and tiny['primary_metric'] is None
          and tiny['cells'][0]['primary_cell_error'] is None
          and tiny['primary_unavailable_reason'] == 'cell_destructive_float_underflow',
          'Nonzero cell discrepancy never becomes exact agreement')
    tiny_pairs[0]['conditions'][0]['probability_randomised'] = [5e-324] * 4
    tiny_macro, _ = grade([encoded(x) for x in tiny_pairs], tiny_reference)
    check(tiny_macro['primary_metric'] is None and tiny_macro['cells'][0]['primary_cell_error'] == 5e-324
          and tiny_macro['primary_unavailable_reason'] == 'aggregate_destructive_float_underflow',
          'Nonzero macro discrepancy never becomes exact agreement')
    body = encoded(result)
    check(len(body) <= core.SCORE_CAP and json.loads(body)['primary_metric'] == 0.,
          'Full invented score strict serializes below cap')
    check(result['scientific_success'] is None and not result['research_qualified']
          and not result['full_paper_complete'] and result['new_reference_fits'] == 0,
          'No scientific-success composite or fit')
    check([row['name'] for row in records] == NAMES[:-1], 'Exact preceding guard order')
    end(NAMES[7], before)
    return {'status': 'thalamus_generated_checks_passed', 'cases': 8, 'count': 8,
            'names': NAMES, 'assertions': assertions, 'invented_only': True,
            'empirical_inputs_opened': 0, 'model_fits': 0,
            'scope': 'invented_full_cohort_admission_metrics_and_private_gate',
            'synthetic_loader_calls': synthetic_calls, 'records': records,
            'exact_fixture_score_sha256': hashlib.sha256(body).hexdigest()}

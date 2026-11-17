"""Eight invented scoring guards. Authored source only; no checks run on import."""
import copy


def run(np, reference_core, core, spec):
    names = []

    def check(ok, message):
        if not ok:
            raise AssertionError(message)

    def finite_lists(array):
        return [[float(v) if np.isfinite(v) else None for v in row] for row in array]

    def fixture(z=None, leaves=None, labels=None):
        z = np.asarray([[0., 1., 1., 2.], [2., 3., 2., 2.], [4., 5., 4., 4.]]) if z is None else z
        leaves = [[0, i] for i in range(4)] if leaves is None else leaves
        labels = np.asarray([[0, 0, row[1]] for row in leaves], dtype=np.int8) if labels is None else labels
        curve = reference_core.curves(np, z, labels)
        submitted = []; refs = []
        for sid in core.SESSION_IDS:
            n = 50 if sid == core.SESSION_IDS[0] else 40
            row = {'id': sid, 'training_row_ids': list(range(n)), 'probe_row_ids': list(range(n, n + 4)),
                   'p1_cluster_ids': [2, 5], 'leaf_row_ids': copy.deepcopy(leaves),
                   'excluded_primary_row_ids': [[t, b] for t in range(40) for b in range(9) if [t, b] not in leaves],
                   'linkage': z.tolist(), 'raw_curve': finite_lists(curve['arrays']['raw_curve']),
                   'normalized_curve': finite_lists(curve['arrays']['normalized_curve']),
                   'normalization': copy.deepcopy(curve['report']['normalization'])}
            submitted.append(row)
            ref = {k: copy.deepcopy(row[k]) for k in ('id', 'training_row_ids', 'probe_row_ids',
                    'p1_cluster_ids', 'leaf_row_ids', 'excluded_primary_row_ids')}
            ref.update(linkage=z.copy(), raw_labels=labels.copy(), raw_curve=curve['arrays']['raw_curve'].copy(),
                       normalized_curve=curve['arrays']['normalized_curve'].copy(),
                       normalization=copy.deepcopy(curve['report']['normalization']))
            refs.append(ref)
        return {'schema_version': 1, 'candidate_id': core.CANDIDATE_ID, 'sessions': submitted}, {
            'sessions': refs, 'private_reference_reads': 0}

    base, reference = fixture()

    def grade(value, ref=reference, raw=False):
        calls = 0
        def loader():
            nonlocal calls
            calls += 1
            return ref
        result = core.grade(value if raw else core.json_bytes(value), spec, loader, np, reference_core)
        return result, calls

    def invalid(body):
        result, calls = grade(body, raw=True)
        check(result['status'] == 'invalid_submission' and calls == result['private_loader_calls'] == 0
              and result['private_reference_reads'] == 0, 'Malformed public output never calls private loader')

    # 1. Complete exact output and child orientation both pass without node-row equality.
    result, calls = grade(base)
    check(result['status'] == 'scored' and calls == 1 and result['sessions_scored'] == 25 and
          result['labels_scored'] == 75 and result['primary_equal_session_label_curve_error'] == 0 and
          result['cophenetic_nmae']['full25_equal_session_mean'] == 0, 'Full25 exact outcome')
    check(result['candidate_pooled_display']['session_slots'] == 25 and
          result['candidate_pooled_display']['complete_full_cohort_pool'], 'Complete candidate descriptive pool')
    oriented = copy.deepcopy(base)
    for session in oriented['sessions']:
        for row in session['linkage']:
            row[0], row[1] = row[1], row[0]
    flipped, calls = grade(oriented)
    check(calls == 1 and flipped['primary_equal_session_label_curve_error'] == 0 and
          flipped['cophenetic_nmae']['full25_equal_session_mean'] == 0, 'Left/right orientation invariant')
    names.append('complete_valid_and_orientation_invariant_scoring')

    # 2. Syntax, numeric and structural errors must fail before any callback.
    valid_body = core.json_bytes(base)
    invalid(b'{"schema_version":1,' + valid_body[1:])
    malformed = copy.deepcopy(base); malformed['sessions'][0]['linkage'][0][2] = float('nan')
    nonfinite_body = core.json.dumps(malformed, allow_nan=True).encode()
    invalid(nonfinite_body)
    try:
        core.strict_json(nonfinite_body)
    except ValueError:
        pass
    else:
        raise AssertionError('Nonfinite literal accepted by strict JSON parser')
    invalid(valid_body + b' ' * (core.SUBMISSION_CAP + 1 - len(valid_body)))
    malformed = copy.deepcopy(base); malformed['sessions'][0]['linkage'][0][0] = False
    invalid(core.json_bytes(malformed))
    malformed = copy.deepcopy(base); malformed['sessions'][0]['linkage'][0][0] = 5
    invalid(core.json_bytes(malformed))
    malformed = copy.deepcopy(base); malformed['sessions'][0]['raw_curve'][0].pop()
    invalid(core.json_bytes(malformed))
    names.append('malformed_nonfinite_oversized_and_invalid_tree_zero_private_callback')

    # 3. Partial cohort or nonpartitioned support is invalid, not a favorable subset.
    missing = copy.deepcopy(base); missing['sessions'].pop()
    invalid(core.json_bytes(missing))
    missing = copy.deepcopy(base); missing['sessions'][0]['excluded_primary_row_ids'].pop()
    invalid(core.json_bytes(missing))
    names.append('missing_session_and_public_support_partition_zero_private_callback')

    # 4. A wrong positive normalizer is scientifically scored; it is not malformed.
    wrong = copy.deepcopy(base)
    wrong['sessions'][0]['normalization'][2]['denominator'] *= 2
    wrong['sessions'][0]['normalized_curve'][2] = [v / 2 for v in wrong['sessions'][0]['normalized_curve'][2]]
    result, calls = grade(wrong)
    label = result['sessions'][0]['labels'][2]
    check(calls == 1 and result['status'] == 'scored' and label['primary_error'] == 1 and
          not label['tree_curve_consistent'] and 'denominator' in label['normalization_mismatched_fields'] and
          np.isclose(result['primary_equal_session_label_curve_error'], 1/75), 'Wrong denominator cannot hide behind correct tree')
    names.append('wrong_normalizer_scores_full_label_consistency_penalty')

    # 5. A coherent alternate topology remains valid, with continuous curve/tree error.
    alternate = copy.deepcopy(base)
    z = np.asarray([[0., 1., 1., 2.], [4., 2., 2., 3.], [5., 3., 4., 4.]])
    calculated = reference_core.curves(np, z, reference['sessions'][0]['raw_labels'])
    alternate['sessions'][0].update(linkage=z.tolist(), raw_curve=finite_lists(calculated['arrays']['raw_curve']),
        normalized_curve=finite_lists(calculated['arrays']['normalized_curve']),
        normalization=copy.deepcopy(calculated['report']['normalization']))
    result, calls = grade(alternate)
    check(calls == 1 and result['status'] == 'scored' and
          0 < result['primary_equal_session_label_curve_error'] < 1 and
          result['cophenetic_nmae']['full25_equal_session_mean'] > 0 and
          all(v['tree_curve_consistent'] for v in result['sessions'][0]['labels']) and
          result['performance_floor'] is None, 'Alternate topology is a scored scientific discrepancy')
    check([v['height_states'] for v in result['sessions'][0]['labels']] == ['BBR', 'BBR', 'CCR'] and
          all(v['union_height_count'] == 3 for v in result['sessions'][0]['labels']) and
          np.allclose([v['primary_error'] for v in result['sessions'][0]['labels']], [1/3, 1/3, 1/2]) and
          np.isclose(result['sessions'][0]['primary_error'], 7/18) and
          np.isclose(result['primary_equal_session_label_curve_error'], 7/450) and
          np.isclose(result['cophenetic_nmae']['full25_equal_session_mean'], 1/100),
          'Exact union-height penalty and independent hand cophenetic comparison')
    names.append('alternate_topology_consistent_curves_union_heights_and_no_floor')

    # 6. A different occupancy split is structurally complete but scientifically wrong.
    reduced = copy.deepcopy(base); row = reduced['sessions'][0]
    moved = row['leaf_row_ids'].pop(); row['excluded_primary_row_ids'].append(moved)
    row['excluded_primary_row_ids'].sort()
    z = np.asarray([[0., 1., 1., 2.], [3., 2., 4., 3.]])
    calculated = reference_core.curves(np, z, reference['sessions'][0]['raw_labels'][:3])
    row.update(linkage=z.tolist(), raw_curve=finite_lists(calculated['arrays']['raw_curve']),
               normalized_curve=finite_lists(calculated['arrays']['normalized_curve']),
               normalization=copy.deepcopy(calculated['report']['normalization']))
    result, calls = grade(reduced)
    check(calls == 1 and result['status'] == 'scored' and result['sessions_scored'] == 25 and
          result['sessions'][0]['primary_error'] == 1 and
          result['sessions'][0]['cophenetic']['reason'] == 'reference_support_mismatch' and
          result['cophenetic_nmae']['comparable_session_count'] == 24 and
          result['cophenetic_nmae']['full25_equal_session_mean'] is None and
          np.isclose(result['primary_equal_session_label_curve_error'], 1/25), 'Private support mismatch never becomes zero-read invalid')
    check(result['candidate_pooled_display']['session_slots'] == 25 and
          result['candidate_pooled_display']['unavailable_support_slots'] == 1 and
          not result['candidate_pooled_display']['complete_full_cohort_pool'], 'Unavailable pool slot retained and disclosed')
    names.append('missing_reference_support_full_session_penalty_complete25_outcomes')

    # 7. Undefined source normalizers include zero-position raw nulls, not imputed zeros.
    undefined, undef_ref = fixture(leaves=[[i, 0] for i in range(4)])
    result, calls = grade(undefined, undef_ref)
    check(calls == 1 and result['primary_equal_session_label_curve_error'] == 0 and
          result['uncapped_comparable_curve_mae']['comparable_label_count'] == 0 and
          result['uncapped_comparable_curve_mae']['full75_label_mean'] is None and
          result['cophenetic_nmae']['full25_equal_session_mean'] == 0, 'Both undefined agree without fabricated finite MAE')
    names.append('undefined_normalizers_raw_nulls_and_explicit_comparison_denominators')

    # 8. Equivalent internal IDs pass; distance-only errors remain visible without overflow.
    renumbered = copy.deepcopy(base)
    renumbered['sessions'][0]['linkage'] = [[2., 3., 2., 2.], [0., 1., 1., 2.], [5., 4., 4., 4.]]
    result, calls = grade(renumbered)
    check(calls == 1 and result['primary_equal_session_label_curve_error'] == 0 and
          result['cophenetic_nmae']['full25_equal_session_mean'] == 0, 'Equivalent internal-node IDs preserve cophenetic result')
    huge = copy.deepcopy(base)
    for row in huge['sessions'][0]['linkage']:
        row[2] = 1e308
    result, calls = grade(huge)
    check(calls == 1 and result['primary_equal_session_label_curve_error'] == 0 and
          result['cophenetic_nmae']['full25_equal_session_mean'] > 1e300,
          'Finite huge distances are scored uncapped, not rejected or clipped')
    check(len(core.json_bytes(result)) <= core.SCORE_CAP, 'Extreme finite score remains bounded')
    overflow_ref = copy.deepcopy(reference)
    overflow_ref['sessions'][0]['linkage'][:, 2] *= 1e-308
    result, calls = grade(huge, overflow_ref)
    check(calls == 1 and result['sessions'][0]['cophenetic']['nmae'] is None and
          'overflow' in result['sessions'][0]['cophenetic']['reason'] and
          result['cophenetic_nmae']['full25_equal_session_mean'] is None,
          'Unrepresentable uncapped metric is explicit, never a dropped or perfect session')
    check(len(core.json_bytes(result)) <= core.SCORE_CAP, 'Explicit overflow report remains bounded')
    # Maximum legal support/height across all25, with nontrivial differences in
    # every label: exercise report extent, not a new empirical control or Ward fit.
    def chain(order):
        n = len(order)
        rows = [[order[0], order[1], 1, 2]]
        rows.extend([n + j - 2, order[j], j, j + 1] for j in range(2, n))
        return np.asarray(rows, dtype=np.float64)
    leaves = [[t, b] for t in range(40) for b in range(9)]
    labels = np.asarray([[t % 2, (t // 2) % 2, b] for t, b in leaves], dtype=np.int8)
    maximum, max_reference = fixture(chain(list(range(360))), leaves, labels)
    alternative = chain([(17 * i) % 360 for i in range(360)])
    max_curves = reference_core.curves(np, alternative, labels)
    for row in maximum['sessions']:
        row.update(linkage=alternative.tolist(), raw_curve=finite_lists(max_curves['arrays']['raw_curve']),
                   normalized_curve=finite_lists(max_curves['arrays']['normalized_curve']),
                   normalization=copy.deepcopy(max_curves['report']['normalization']))
    check(len(core.json_bytes(maximum)) <= core.SUBMISSION_CAP, 'Maximum-shape guard is a legal complete submission')
    result, calls = grade(maximum, max_reference)
    check(calls == 1 and result['sessions_scored'] == 25 and result['labels_scored'] == 75 and
          all(v['union_height_count'] == 359 for session in result['sessions'] for v in session['labels']) and
          len(core.json_bytes(result)) <= core.SCORE_CAP - 16384,
          'Complete maximum-height report fits1MB with16KB for grader guards/counters')
    names.append('equivalent_internal_ids_and_finite_extreme_distance_metrics')
    check(len(names) == len(set(names)) == 8, 'Exactly eight meaningful invented groups')
    return {'status': 'central_generated_checks_passed', 'cases': 8, 'count': 8, 'names': names,
            'invented_only': True, 'empirical_inputs_opened': 0, 'model_fits': 0, 'ward_optimizations': 0,
            'scope': 'Invented structural/scoring controls only; no candidate or protected empirical body read'}

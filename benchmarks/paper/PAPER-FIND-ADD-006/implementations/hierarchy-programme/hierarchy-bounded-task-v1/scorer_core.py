"""Complete-support hierarchy scoring. No I/O or scientific imports at import time."""
import io
import json
import math
import zipfile

CANDIDATE_ID = 'PAPER-FIND-ADD-006'
SUBMISSION_CAP = 4000000
SCORE_CAP = 1000000
MEMBER_CAPS = {'linkages.npz': 4000000, 'report.json': 2000000}
LABELS = ('Context', 'Direction', 'Position')
SESSION_IDS = tuple(a + '/' + d for a, dates in (
    ('jc233', ('170220', '180220', '190220', '200220', '210220')),
    ('jc243', ('240820', '260820', '270820', '280820', '310820')),
    ('jc250', ('010221', '020221', '030221', '050221', '060221')),
    ('jc253', ('160321', '170321', '180321', '190321', '210321')),
    ('jc259', ('210421', '220421', '230421', '240421', '260421'))) for d in dates)
SESSION_KEYS = {'id', 'training_row_ids', 'probe_row_ids', 'p1_cluster_ids', 'leaf_row_ids',
                'excluded_primary_row_ids', 'linkage', 'raw_curve', 'normalized_curve', 'normalization'}
REASONS = {'no_nonroot_curve', 'nonfinite_last_nonroot_denominator',
           'zero_last_nonroot_denominator', 'nonfinite_normalized_curve'}
ATOL, RTOL = 1e-10, 1e-8


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def floating(text):
        value = float(text)
        need(math.isfinite(value), 'Finite JSON numeric literal')
        return value
    def constant(unused):
        raise ValueError('No nonfinite JSON constant')
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                      parse_float=floating, parse_constant=constant)


def json_bytes(value):
    return (json.dumps(value, separators=(',', ':'), sort_keys=True, allow_nan=False) + '\n').encode()


def invalid_submission(reason):
    return {'status': 'invalid_submission', 'submission_valid': False, 'reason': reason[:512],
            'sessions_scored': 0, 'labels_scored': 0, 'private_loader_calls': 0,
            'private_reference_reads': 0, 'performance_floor': None, 'scientific_success': None}


def validate_schema(spec):
    need(type(spec) is dict and spec.get('schema_version') == 1 and
         spec.get('candidate_id') == CANDIDATE_ID and spec.get('ordered_session_ids') == list(SESSION_IDS)
         and set(spec.get('top_level_keys', [])) == {'schema_version', 'candidate_id', 'sessions'}
         and set(spec.get('session_keys', [])) == SESSION_KEYS and spec.get('label_names') == list(LABELS)
         and spec.get('submission_max_bytes') == SUBMISSION_CAP and spec.get('max_leaves') == 360
         and spec.get('max_p1_columns') == 92 and spec.get('atol') == ATOL and spec.get('rtol') == RTOL
         and spec.get('scoring_version') == 'hierarchy_source_defined_full25_v1', 'Exact public scoring schema')


def _integers(values, low, high, count=None):
    need(type(values) is list and (count is None or len(values) == count) and
         all(type(v) is int and low <= v <= high for v in values) and
         values == sorted(set(values)), 'Sorted unique bounded literal integer IDs')


def _pairs(values, trials):
    need(type(values) is list and len(values) <= 360 and
         all(type(row) is list and len(row) == 2 and type(row[0]) is int and type(row[1]) is int
             and row[0] in trials and 0 <= row[1] < 9 for row in values), 'Bounded original trial/bin pairs')
    pairs = [tuple(row) for row in values]
    need(pairs == sorted(set(pairs)), 'Canonical unique trial-major/bin-major support')
    return set(pairs)


def tree_structure(linkage, n):
    need(type(linkage) is list and len(linkage) == n - 1, 'Complete linkage row count')
    height, size, used = [0] * n, [1] * n, set()
    for i, row in enumerate(linkage):
        need(type(row) is list and len(row) == 4 and all(number(v) for v in row), 'Four finite linkage fields')
        need(row[0] == int(row[0]) and row[1] == int(row[1]) and row[3] == int(row[3])
             and row[2] >= 0, 'Integer-valued children/counts and nonnegative distance')
        left, right = int(row[0]), int(row[1])
        need(0 <= left < n + i and 0 <= right < n + i and left != right and
             left not in used and right not in used, 'Each preceding child used once')
        need(row[3] == size[left] + size[right], 'Exact descendant support count')
        used.update((left, right))
        height.append(1 + max(height[left], height[right])); size.append(size[left] + size[right])
    need(used == set(range(2 * n - 2)) and size[-1] == n, 'Single root covers every leaf')
    return height[-1]


def validate_submission(value):
    need(type(value) is dict and set(value) == {'schema_version', 'candidate_id', 'sessions'} and
         type(value['schema_version']) is int and value['schema_version'] == 1 and
         value['candidate_id'] == CANDIDATE_ID, 'Exact submission envelope')
    need(type(value['sessions']) is list and len(value['sessions']) == 25, 'All25 sessions required')
    for sid, session in zip(SESSION_IDS, value['sessions']):
        need(type(session) is dict and set(session) == SESSION_KEYS and session['id'] == sid,
             'Exact ordered session IDs and fields')
        count = 50 if sid == SESSION_IDS[0] else 40
        train, probe = session['training_row_ids'], session['probe_row_ids']
        _integers(train, 0, count + 3, count); _integers(probe, 0, count + 3, 4)
        need(not set(train) & set(probe) and set(train) | set(probe) == set(range(count + 4)),
             'Complete disjoint training/probe ordinal partition')
        _integers(session['p1_cluster_ids'], 2, 4096)
        need(1 <= len(session['p1_cluster_ids']) <= 92, 'All submitted p1 column IDs bounded')
        leaves = _pairs(session['leaf_row_ids'], train[:40])
        excluded = _pairs(session['excluded_primary_row_ids'], train[:40])
        need(not leaves & excluded and leaves | excluded == {(t, b) for t in train[:40] for b in range(9)},
             'Leaf/excluded support partitions all360 primary trial/bin identities')
        need(2 <= len(leaves) <= 360, 'At least2 and at most360 submitted leaves')
        height = tree_structure(session['linkage'], len(leaves))
        need(type(session['normalization']) is list and len(session['normalization']) == 3,
             'Three ordered normalization records')
        for field in ('raw_curve', 'normalized_curve'):
            matrix = session[field]
            need(type(matrix) is list and len(matrix) == 3 and
                 all(type(row) is list and len(row) == height and
                     all(v is None or number(v) for v in row) for row in matrix),
                 'Three curves of exact candidate root-height length with finite numbers/null')
        for label, record in enumerate(session['normalization']):
            need(type(record) is dict and set(record) == {'label', 'status', 'reason', 'denominator'} and
                 record['label'] == LABELS[label] and record['status'] in ('defined', 'undefined'),
                 'Exact normalization record identity')
            denominator = record['denominator']
            need(denominator is None or (number(denominator) and denominator >= 0),
                 'Finite nonnegative or null denominator')
            if record['status'] == 'defined':
                need(record['reason'] is None and denominator is not None and denominator > 0 and
                     all(v is not None for v in session['raw_curve'][label]) and
                     all(v is not None for v in session['normalized_curve'][label]), 'Defined normalization fields')
            else:
                need(record['reason'] in REASONS and all(v is None for v in session['normalized_curve'][label]),
                     'Undefined reason and entirely null normalized row')
    return value


def close_number(claimed, expected):
    if claimed is None:
        return not math.isfinite(float(expected))
    if not math.isfinite(float(expected)):
        return False
    return abs(float(claimed) - float(expected)) <= ATOL + RTOL * abs(float(expected))


def _cophenetic(np, linkage, n):
    matrix = np.zeros((n, n), dtype=np.float64)
    members = [[i] for i in range(n)]
    for row in linkage:
        left, right = members[int(row[0])], members[int(row[1])]
        matrix[np.ix_(left, right)] = row[2]; matrix[np.ix_(right, left)] = row[2]
        members.append(left + right)
    return matrix[np.triu_indices(n, 1)]


def _tree_error(np, candidate, reference, n):
    left = _cophenetic(np, candidate, n); right = _cophenetic(np, reference, n)
    root = float(reference[-1, 2]); scale = root if root != 0 else 1.0
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        differences = np.abs(left - right)
        maximum = float(np.max(differences))
        mean = 0.0 if maximum == 0 else float(np.mean(differences / maximum)) * maximum
        value = mean / scale
    reason = None if math.isfinite(value) else 'finite_precision_overflow_uncapped_metric_unavailable'
    return {'nmae': value if reason is None else None, 'reason': reason,
            'compared_pairs': len(left), 'different_pairs': int(np.count_nonzero(differences > ATOL + RTOL * np.abs(right))),
            'reference_root_distance': root, 'normalization_scale': scale}


def _label_error(np, claimed, computed, reference, label):
    current = computed['arrays']; norm = current['normalized_curve'][label]
    target = reference['normalized_curve'][label]
    raw_mask = ''.join('0' if close_number(v, e) else '1'
                       for v, e in zip(claimed['raw_curve'][label], current['raw_curve'][label]))
    norm_mask = ''.join('0' if close_number(v, e) else '1'
                        for v, e in zip(claimed['normalized_curve'][label], norm))
    declaration, actual = claimed['normalization'][label], computed['report']['normalization'][label]
    fields = [k for k in ('label', 'status', 'reason') if declaration[k] != actual[k]]
    if not ((declaration['denominator'] is None and actual['denominator'] is None) or
            (declaration['denominator'] is not None and actual['denominator'] is not None and
             close_number(declaration['denominator'], actual['denominator']))):
        fields.append('denominator')
    consistent = '1' not in raw_mask + norm_mask and not fields
    states, absolute, penalties = [], [], []
    for h in range(max(len(norm), len(target))):
        if h >= len(norm):
            state, error, penalty = 'M', None, 1.0
        elif h >= len(target):
            state, error, penalty = 'R', None, 1.0
        else:
            c, r = float(norm[h]), float(target[h])
            if math.isfinite(c) and math.isfinite(r):
                state, error = 'C', abs(c - r); penalty = min(error, 1.0)
            elif not math.isfinite(c) and not math.isfinite(r):
                state, error, penalty = 'B', None, 0.0
            else:
                state, error, penalty = 'X', None, 1.0
        states.append(state); absolute.append(error); penalties.append(penalty)
    finite = [v for v in absolute if v is not None]
    curve_error = math.fsum(penalties) / len(penalties)
    return {'label': LABELS[label], 'primary_error': curve_error if consistent else 1.0,
            'recomputed_curve_error_before_consistency_penalty': curve_error,
            'tree_curve_consistent': consistent, 'raw_consistency_mask': raw_mask,
            'normalized_consistency_mask': norm_mask, 'normalization_mismatched_fields': fields,
            'height_states': ''.join(states), 'uncapped_absolute_errors': absolute,
            'union_height_count': len(states), 'comparable_finite_heights': len(finite),
            'uncapped_comparable_mae': math.fsum(finite) / len(finite) if finite else None,
            'computed_normalization': actual}


def score(np, reference_core, submission, reference):
    need(type(reference) is dict and len(reference.get('sessions', [])) == 25, 'Complete private reference sessions')
    outcomes = []; comparable_labels = []; tree_values = []; pool_slots = []; support_matches = 0
    for claimed, target, sid in zip(submission['sessions'], reference['sessions'], SESSION_IDS):
        need(target['id'] == sid, 'Exact private session order')
        support_fields = ('training_row_ids', 'probe_row_ids', 'p1_cluster_ids',
                          'leaf_row_ids', 'excluded_primary_row_ids')
        mismatch = [key for key in support_fields if claimed[key] != target[key]]
        if mismatch:
            pool_slots.append(np.full((3, len(claimed['normalized_curve'][0])), np.nan, dtype=np.float64))
            labels = [{'label': label, 'primary_error': 1.0, 'reason': 'reference_support_mismatch',
                       'comparable_finite_heights': 0, 'uncapped_comparable_mae': None} for label in LABELS]
            tree = {'nmae': None, 'reason': 'reference_support_mismatch', 'compared_pairs': 0}
            result = {'id': sid, 'primary_error': 1.0, 'support_match': False,
                      'support_mismatched_fields': mismatch, 'labels': labels, 'cophenetic': tree}
        else:
            support_matches += 1
            candidate_tree = np.asarray(claimed['linkage'], dtype=np.float64)
            computed = reference_core.curves(np, candidate_tree, target['raw_labels'])
            pool_slots.append(computed['arrays']['normalized_curve'])
            labels = [_label_error(np, claimed, computed, target, i) for i in range(3)]
            tree = _tree_error(np, candidate_tree, target['linkage'], len(target['leaf_row_ids']))
            result = {'id': sid, 'primary_error': math.fsum(v['primary_error'] for v in labels) / 3,
                      'support_match': True, 'support_mismatched_fields': [], 'labels': labels, 'cophenetic': tree}
        outcomes.append(result)
        comparable_labels.extend(v['uncapped_comparable_mae'] for v in labels if v['uncapped_comparable_mae'] is not None)
        if tree['nmae'] is not None:
            tree_values.append(tree['nmae'])
    def stable_mean(values):
        if not values:
            return None
        maximum = max(values)
        return 0.0 if maximum == 0 else math.fsum(v / maximum for v in values) / len(values) * maximum
    pooled = reference_core.pool(np, pool_slots)
    def finite_rows(array):
        return [[float(v) if math.isfinite(float(v)) else None for v in row] for row in array]
    display = {'session_slots': 25, 'reference_support_matched_sessions': support_matches,
               'unavailable_support_slots': 25 - support_matches,
               'complete_full_cohort_pool': support_matches == 25,
               'support_scope': 'full25 matched support' if support_matches == 25 else
                                'reference-support-conditioned; unmatched sessions retain all-NaN slots',
               'status': pooled['report']['status'], 'label_order': list(LABELS),
               'display_index': pooled['arrays']['display_index'].tolist(),
               'mean_display': finite_rows(pooled['arrays']['mean_display']),
               'sem_display': finite_rows(pooled['arrays']['sem_display']),
               'contributing_sessions_display': pooled['arrays']['contributing_sessions_display'].tolist(),
               'convention': 'Right-pad then equal-session mean/sample SEM, finally reverse; descriptive, not animal inference'}
    return {'status': 'scored', 'submission_valid': True, 'candidate_id': CANDIDATE_ID,
            'sessions_scored': 25, 'labels_scored': 75,
            'primary_equal_session_label_curve_error': math.fsum(v['primary_error'] for v in outcomes) / 25,
            'primary_direction': 'lower_is_better', 'performance_floor': None, 'scientific_success': None,
            'uncapped_comparable_curve_mae': {'comparable_label_count': len(comparable_labels),
                'full75_label_mean': stable_mean(comparable_labels) if len(comparable_labels) == 75 else None,
                'mean_over_comparable_labels_only': stable_mean(comparable_labels)},
            'cophenetic_nmae': {'comparable_session_count': len(tree_values),
                'full25_equal_session_mean': stable_mean(tree_values) if len(tree_values) == 25 else None,
                'mean_over_comparable_sessions_only': stable_mean(tree_values)},
            'candidate_pooled_display': display,
            'sessions': outcomes, 'height_state_legend': {'C': 'finite comparable', 'B': 'both undefined',
                'X': 'finite/undefined mismatch', 'M': 'missing candidate height', 'R': 'missing reference height'},
            'consistency_mask_legend': '0 within1e-10+1e-8*abs(reconstructed);1 mismatch; position=bottom-up height',
            'figure3f_enabled': False, 'model_fits': 0, 'ward_optimizations': 0,
            'private_reference_reads': reference.get('private_reference_reads', 0)}


def grade(body, spec, loader, np, reference_core):
    validate_schema(spec)
    try:
        need(type(body) is bytes and 0 < len(body) <= SUBMISSION_CAP, 'Submission byte cap')
        submission = validate_submission(strict_json(body))
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        return invalid_submission(type(error).__name__ + ': ' + str(error))
    reference = loader()
    result = score(np, reference_core, submission, reference)
    result['private_loader_calls'] = 1
    return result


def decode_reference(np, bodies):
    """Only the lazy private callback may invoke this on captured authenticated bytes."""
    need(set(bodies) == set(MEMBER_CAPS), 'Exactly two private reference bodies')
    report = strict_json(bodies['report.json'])
    need(report['schema'] == 'hierarchy_source_curves_report_v1' and report['complete'] is True and
         report['paper_fig3f_reconstructed'] is False and len(report['sessions']) == 25 and
         len(report['arrays']) == 693, 'Complete fixed source reference metadata')
    stream = io.BytesIO(bodies['linkages.npz'])
    with zipfile.ZipFile(stream) as archive:
        infos = archive.infolist()
        need(len(infos) == 693 and len({v.filename for v in infos}) == 693 and
             {v.filename for v in infos} == set(report['arrays']) and
             all(v.compress_type == zipfile.ZIP_STORED and not v.flag_bits & 1 and
                 not v.is_dir() and v.file_size <= 1000000 for v in infos) and
             sum(v.file_size for v in infos) <= 4000000, 'Exact bounded stored numeric reference members')
    stream.seek(0); sessions = []
    with np.load(stream, allow_pickle=False) as loaded:
        for sid, entry in zip(SESSION_IDS, report['sessions']):
            need(entry['session'] == sid and entry['source']['tree_status'] == 'available', 'Exact available reference session')
            prefix = sid.replace('/', '_') + '__'
            def array(key):
                value = loaded[prefix + key]; meta = report['arrays'][prefix + key + '.npy']
                need(not value.dtype.hasobject and value.dtype.kind in 'biuf' and value.dtype.str == meta['dtype'] and
                     list(value.shape) == meta['shape'] and value.nbytes == meta['data_bytes'], 'Exact reference array schema')
                return value
            row = {'id': sid}
            for key in ('training_row_ids', 'probe_row_ids', 'p1_cluster_ids', 'leaf_row_ids', 'excluded_primary_row_ids'):
                row[key] = array(key).tolist()
            row.update(linkage=array('source_linkage'), raw_curve=array('source_raw_curve'),
                       normalized_curve=array('source_normalized_curve'), raw_labels=array('raw_labels'),
                       normalization=entry['source']['normalization'])
            need(row['raw_labels'].shape == (len(row['leaf_row_ids']), 3) and
                 np.array_equal(row['raw_labels'][:, 2], np.asarray(row['leaf_row_ids'])[:, 1]), 'Raw-derived reference label/bin join')
            sessions.append(row)
    return {'sessions': sessions, 'private_reference_reads': 2}

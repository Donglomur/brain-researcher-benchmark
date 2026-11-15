"""Pure long-input envelope adapter; no file I/O, fits or candidate execution.

Pass the unchanged qualified scalar scorer as `scalar`. Only grade() calls the
operator loader, after full public admission. Public fingerprints are identities,
not proof that a submitted program computed anything.
"""
import hashlib
import json
import math

TASK = 'PAPER-FIND-003'
PHASES = ('stimulus', 'feedback', 'interval')
LABELS = ('source99_excluded',) + PHASES
MAX_RAW_ROWS = 24246
MAX_WIDE_ROW_ID = 8082
MAX_BYTES = 262144
MAX_ARTIFACT_BYTES = 32768
MAX_REPORT_BYTES = 163840
RAW_FILENAME = 'dd_ripple_during_learning_raw.csv'
DENOMINATORS = {'coefficients': 12, 'covariance_entries': 48, 'variance_components': 9}


class AdmissionError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise AdmissionError(message)


def exact(value, keys, where):
    need(type(value) is dict and set(value) == set(keys), where + ': exact fields')


def sha(value):
    need(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Lowercase SHA256')


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def public_identity(public):
    exact(public, ('schema_version', 'task_id', 'raw_filename', 'input_raw_bytes', 'input_raw_sha256',
                  'raw_rows', 'preprocessing_spec_sha256', 'derived_wide_sha256', 'max_wide_row_id'), 'public identity')
    need(type(public['schema_version']) is int and public['schema_version'] == 1 and public['task_id'] == TASK,
         'Public schema/task identity')
    need(public['raw_filename'] == RAW_FILENAME, 'Fixed public raw filename')
    for key, upper in (('input_raw_bytes', 1200000), ('raw_rows', MAX_RAW_ROWS)):
        need(type(public[key]) is int and 0 < public[key] <= upper, 'Bounded public ' + key)
    for key in ('input_raw_sha256', 'preprocessing_spec_sha256', 'derived_wide_sha256'):
        sha(public[key])
    need(type(public['max_wide_row_id']) is int and public['max_wide_row_id'] == MAX_WIDE_ROW_ID,
         'Fixed public ID ceiling, not an actual row count')
    return public


def scalar_public(public):
    # The frozen scalar API calls this field wide_rows, but uses it only as an
    # admission bound. The actual count/subject/contact membership stays private.
    return {'task_id': TASK, 'input_sha256': public['derived_wide_sha256'],
            'wide_rows': public['max_wide_row_id']}


def decode(body):
    need(type(body) is bytes and 0 < len(body) <= MAX_BYTES, 'Bounded nonempty UTF8 JSON envelope')
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    def real(token):
        # Inspect the original JSON token BEFORE binary64 conversion. A later
        # serialization of an already underflowed float cannot recover this fact.
        mantissa = token.lower().split('e', 1)[0]
        lexical_nonzero = any(c in '123456789' for c in mantissa)
        value = float(token)
        need(math.isfinite(value), 'Nonfinite numeric token')
        need(value != 0 or not lexical_nonzero, 'Destructive numeric underflow')
        return value
    def integer(token):
        need(len(token) <= 18, 'Bounded integer token')
        return int(token)
    def constant(_):
        raise AdmissionError('Non-JSON numeric constant')
    try:
        value = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                           parse_float=real, parse_int=integer, parse_constant=constant)
        nodes = 0
        def walk(x, depth=0):
            nonlocal nodes
            nodes += 1
            need(depth <= 12 and nodes <= 50000, 'Bounded envelope structure')
            if type(x) is dict:
                need(len(x) <= 20, 'Bounded object')
                for key, item in x.items():
                    need(type(key) is str and len(key) <= 96, 'Bounded key')
                    key.encode('utf-8', errors='strict'); walk(item, depth + 1)
            elif type(x) is list:
                need(len(x) <= MAX_RAW_ROWS, 'Bounded source-row array')
                for item in x:
                    walk(item, depth + 1)
            elif type(x) is str:
                need(len(x) <= 512, 'Bounded text'); x.encode('utf-8', errors='strict')
        walk(value)
        return value
    except (UnicodeError, ValueError, OverflowError, RecursionError) as error:
        raise AdmissionError('Strict envelope JSON: ' + str(error)[:160]) from None


def partition(value, n):
    exact(value, ('phase_source_row_ids', 'source99_excluded_row_ids'), 'preprocessing partition')
    exact(value['phase_source_row_ids'], PHASES, 'all phase memberships')
    lists = [value['source99_excluded_row_ids']] + [value['phase_source_row_ids'][p] for p in PHASES]
    assignment = [-1] * n
    for code, ids in enumerate(lists):
        need(type(ids) is list and len(ids) <= n, 'Bounded explicit source-row list')
        for i in ids:
            need(type(i) is int and 1 <= i <= n, 'Integer source-row identity in active scope')
            need(assignment[i - 1] == -1, 'Source row occurs only once in entire partition')
            assignment[i - 1] = code
    need(all(x >= 0 for x in assignment), 'Every active raw row assigned exactly once')
    return assignment


def admit(value, public, scalar):
    exact(value, ('schema_version', 'task_id', 'mode', 'input_raw_sha256', 'preprocessing_spec_sha256',
                  'derived_wide_sha256', 'submission_status', 'preprocessing', 'model_artifact'), 'envelope')
    need(type(value['schema_version']) is int and value['schema_version'] == 1 and
         value['task_id'] == TASK and value['mode'] == 'long_input_reconstruction', 'Envelope mode and identity')
    for key in ('input_raw_sha256', 'preprocessing_spec_sha256', 'derived_wide_sha256'):
        sha(value[key]); need(value[key] == public[key], 'Active ' + key)
    artifact_bytes = compact(value['model_artifact'])
    need(len(artifact_bytes) <= MAX_ARTIFACT_BYTES, 'Nested scalar artifact32KiB cap')
    artifact = scalar.validate(scalar.decode(artifact_bytes), scalar_public(public))
    need(value['submission_status'] == artifact['submission_status'], 'Outer/inner coverage status agrees')
    if artifact['submission_status'] == 'abstained':
        need(value['preprocessing'] is None, 'Whole abstention makes no membership claim')
        assignment = None
    else:
        assignment = partition(value['preprocessing'], public['raw_rows'])
    return artifact, artifact_bytes, assignment


def reference_bundle(value, public, scalar):
    """Validate the operator projection; no raw table/preprocessing or fitting."""
    exact(value, ('schema_version', 'task_id', 'identity', 'preprocessing', 'raw_row_to_wide', 'models'), 'private bundle')
    need(type(value['schema_version']) is int and value['schema_version'] == 1 and value['task_id'] == TASK,
         'Private schema/task')
    public_identity(value['identity']); need(value['identity'] == public, 'Private raw/spec/derived identity chain')
    assignment = partition(value['preprocessing'], public['raw_rows'])
    mapping = value['raw_row_to_wide']
    need(type(mapping) is list and len(mapping) == public['raw_rows'], 'Complete canonical raw-to-wide map')
    for code, wid in zip(assignment, mapping):
        need((wid is None) if code == 0 else
             (type(wid) is int and 1 <= wid <= public['max_wide_row_id']), 'Excluded null / retained canonical wide ID')
    projected = scalar.project_reference(value['models'], scalar_public(public))
    for phase, row in zip(PHASES, projected['models']):
        code = LABELS.index(phase)
        mapped = [wid for c, wid in zip(assignment, mapping) if c == code]
        need(len(set(mapped)) == len(mapped), 'Qualified unique raw cell per phase/wide row')
        ids = sorted(mapped)
        saved = value['models']['phases'][phase]
        need(ids == saved['row_ids'] and len(ids) == row['fit']['support']['n_obs'],
             'Full private phase membership equals saved model support, including phasewise missingness')
    return assignment, mapping


def membership_report(candidate, expected):
    matrix = [[0] * 4 for _ in range(4)]
    for claimed, truth in zip(candidate, expected):
        matrix[truth][claimed] += 1
    n = len(expected); wrong = sum(matrix[i][j] for i in range(4) for j in range(4) if i != j)
    rows = []
    for i, label in enumerate(LABELS):
        expected_n = sum(matrix[i]); claimed_n = sum(row[i] for row in matrix)
        rows.append({'disposition': label, 'expected_rows': expected_n, 'claimed_rows': claimed_n,
                     'matched_rows': matrix[i][i], 'missing_rows': expected_n - matrix[i][i],
                     'extra_rows': claimed_n - matrix[i][i]})
    return {'status': 'compared', 'expected_raw_rows': n, 'claimed_raw_rows': len(candidate),
            'complete_input_partition': True, 'all_assignments_agree': wrong == 0,
            'misassigned_rows': wrong, 'misassigned_fraction': wrong / n,
            'confusion_axes': list(LABELS), 'confusion_rows_expected_columns_claimed': matrix,
            'dispositions': rows, 'scope': 'All active raw rows; fixed reference denominator; counts do not certify actual program use'}


def support_consistency(artifact, assignment, mapping):
    reports = []
    for phase, row in zip(PHASES, artifact['models']):
        code = LABELS.index(phase)
        mapped = [wid for c, wid in zip(assignment, mapping) if c == code]
        missing = sum(wid is None for wid in mapped)
        ids = sorted({wid for wid in mapped if wid is not None})
        digest = hashlib.sha256(''.join(str(i) + '\n' for i in ids).encode('ascii')).hexdigest()
        one = {'phase': phase, 'claimed_raw_rows': len(mapped), 'unmappable_claimed_rows': missing,
               'duplicate_canonical_wide_rows': len(mapped) - missing - len(ids),
               'reported_model': row['status'] == 'reported', 'n_obs_matches_claimed_raw_membership': None,
               'row_digest_matches_mapped_claim': None}
        if row['status'] == 'reported':
            support = row['fit']['support']
            one['n_obs_matches_claimed_raw_membership'] = support['n_obs'] == len(mapped)
            one['row_digest_matches_mapped_claim'] = missing == 0 and len(ids) == len(mapped) and support['row_ids_sha256'] == digest
        reports.append(one)
    return {'phases': reports, 'mapping_basis': 'Trusted active canonical lineage; never overwrites candidate support or numeric fields',
            'subject_contact_counts': 'Compared with private reference by unchanged scalar scorer; not inferred from row ordinals'}


def grade(body, public, load_reference, scalar):
    """One private bundle callback after admission; zero for invalid/abstain.

    Callback counts do not describe a trusted caller's earlier setup I/O."""
    base = {'task_id': TASK, 'mode': 'long_input_reconstruction', 'expected_scalar_denominators': dict(DENOMINATORS),
            'scientific_success': None, 'blended_reward': None, 'program_execution_verified': False}
    try:
        public_identity(public)
    except (AdmissionError, KeyError, TypeError) as error:
        return {**base, 'status': 'operator_public_identity_error', 'reason': str(error)[:200], 'private_bundle_reads': 0}
    try:
        artifact, artifact_bytes, assignment = admit(decode(body), public, scalar)
    except (AdmissionError, scalar.AdmissionError, KeyError, TypeError, ValueError, OverflowError, RecursionError) as error:
        return {**base, 'status': 'invalid_submission', 'reason': str(error)[:200], 'private_bundle_reads': 0}
    cache = {}; calls = 0
    def loader():
        nonlocal calls
        calls += 1
        need(calls == 1, 'Exactly one private bundle read')
        value = load_reference()
        expected, mapping = reference_bundle(value, public, scalar)
        cache.update(expected=expected, mapping=mapping)
        return value['models']
    scored = scalar.grade(artifact_bytes, scalar_public(public), loader)
    result = {**base, 'status': scored['status'], 'private_bundle_reads': calls, 'scalar_score': scored,
              'membership': None, 'raw_membership_scalar_support_consistency': None}
    if scored['status'] == 'scored':
        if calls != 1 or not cache:
            return {**base, 'status': 'operator_reference_error', 'private_bundle_reads': calls}
        result['membership'] = membership_report(assignment, cache['expected'])
        result['raw_membership_scalar_support_consistency'] = support_consistency(artifact, assignment, cache['mapping'])
    elif scored['status'] == 'abstained':
        need(calls == 0 and assignment is None, 'Whole abstention has zero private callback')
    if len(compact(result)) > MAX_REPORT_BYTES:
        return {**base, 'status': 'operator_report_bound_error', 'private_bundle_reads': calls,
                'complete_report_retained': False, 'reason': 'Complete report exceeds prospective163840-byte cap; not a scored outcome'}
    return result

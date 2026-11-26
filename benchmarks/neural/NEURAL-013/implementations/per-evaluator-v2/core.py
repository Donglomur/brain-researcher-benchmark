"""Recovered NEURAL-013 evaluator with the complete 27/9/9 session contract.

Source lineage is recorded in SOURCE_PINS.json. No candidate code runs here.
"""
import hashlib
import json
import math
import re

SCHEMA = 'neural013-predictions-v1'
PUBLIC_SCHEMA = 'neural013-public-v1'
MAX_CASES = 50000
MAX_TOKENS = 2048
MAX_DP_CELLS = 128000000
# Factual ordered label inventory from evaluate_model_helpers.py at the pinned
# official commit. Index zero is CTC blank/padding, not a scored sequence token.
SOURCE_CLASSES = ('BLANK', 'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'B', 'CH',
                  'D', 'DH', 'EH', 'ER', 'EY', 'F', 'G', 'HH', 'IH', 'IY',
                  'JH', 'K', 'L', 'M', 'N', 'NG', 'OW', 'OY', 'P', 'R',
                  'S', 'SH', 'T', 'TH', 'UH', 'UW', 'V', 'W', 'Y', 'Z',
                  'ZH', ' | ')
TOKENS = tuple(x.strip() for x in SOURCE_CLASSES[1:])
TOKEN_SET = frozenset(TOKENS)
HEX = re.compile(r'[0-9a-f]{64}\Z')
SESSION = re.compile(r'session-[0-9]{3}\Z')
SESSION_ROLES = tuple(
    ('session-%03d' % i, 'train' if i <= 27 else 'development' if i <= 36 else 'query')
    for i in range(1, 46))


class ContractError(ValueError):
    pass


def need(ok, why):
    if not ok:
        raise ContractError(why)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def normalize_tokens(value):
    """Formatting only: ASCII case and whitespace. No stress/CTC/LM repair."""
    if type(value) is str:
        need(len(value) <= MAX_TOKENS * 8 and value.isascii(), 'bounded ASCII token string')
        parts = value.split()
    else:
        need(type(value) is list and len(value) <= MAX_TOKENS, 'token list or whitespace string')
        parts = value
    need(len(parts) <= MAX_TOKENS, 'token count exceeds declared interface bound')
    result = []
    for token in parts:
        need(type(token) is str and len(token) <= 8 and token.isascii(), 'ASCII token required')
        token = token.strip().upper()
        need(token in TOKEN_SET, 'unknown token, stress suffix or CTC blank')
        result.append(token)
    return result


def labels_from_source(ids, seq_len):
    need(type(seq_len) is int and 0 < seq_len <= len(ids) <= MAX_TOKENS,
         'positive bounded source seq_len')
    need(all(type(x) is int for x in ids), 'integer source class IDs')
    need(all(1 <= x < len(SOURCE_CLASSES) for x in ids[:seq_len]),
         'source target prefix must contain only classes1..40')
    need(all(x == 0 for x in ids[seq_len:]), 'nonzero values beyond source seq_len')
    return [SOURCE_CLASSES[x].strip() for x in ids[:seq_len]]


def public_queries(public):
    need(type(public) is dict and set(public) == {
        'schema', 'packet_id', 'protocol_id', 'sessions', 'cases', 'training_labels'},
        'exact public manifest fields')
    need(public['schema'] == PUBLIC_SCHEMA and public['protocol_id'] == 'neural013-chronological-v1',
         'public schema/protocol')
    need(type(public['packet_id']) is str and HEX.fullmatch(public['packet_id']), 'packet ID')
    need(digest({k: v for k, v in public.items() if k != 'packet_id'}) == public['packet_id'],
         'public manifest fingerprint')
    sessions = public['sessions']
    need(type(sessions) is list and len(sessions) == 45, 'all 45 declared sessions required')
    roles = {}
    for row in sessions:
        need(type(row) is dict and set(row) == {'session_id', 'role'}, 'public session fields')
        need(type(row['session_id']) is str and SESSION.fullmatch(row['session_id']) and
             row['session_id'] not in roles, 'unique opaque session alias')
        need(type(row['role']) is str and row['role'] in ('train', 'development', 'query'), 'session role')
        roles[row['session_id']] = row['role']
    need(list(roles.items()) == list(SESSION_ROLES),
         'fixed chronological 27 training / 9 development / 9 query sessions required')
    rows = public['cases']
    need(type(rows) is list and 0 < len(rows) <= MAX_CASES, 'bounded public case list')
    all_ids, queries = set(), {}
    for row in rows:
        need(type(row) is dict and set(row) == {'case_id', 'session_id', 'role', 'n_time_steps', 'features'},
             'no transcript/target/source identity in public case')
        key = row['case_id']
        need(type(key) is str and HEX.fullmatch(key) and key not in all_ids, 'unique opaque case ID')
        all_ids.add(key)
        need(type(row['session_id']) is str and row['session_id'] in roles and
             row['role'] == roles[row['session_id']], 'case/session role join')
        need(type(row['n_time_steps']) is int and 0 < row['n_time_steps'] <= 100000, 'neural length')
        pin = row['features']
        need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'feature descriptor')
        need(pin['path'] == 'features/' + key + '.npy' and type(pin['bytes']) is int and
             0 < pin['bytes'] <= 512 * 100000 * 8 + 1024 and
             type(pin['sha256']) is str and HEX.fullmatch(pin['sha256']), 'safe feature binding')
        if row['role'] == 'query':
            queries[key] = row['session_id']
    need(queries and set(queries.values()) == {s for s, r in roles.items() if r == 'query'},
         'every declared query session has support')
    need({row['role'] for row in rows} == {'train', 'development', 'query'},
         'retained observations required in each partition')
    pin = public['training_labels']
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'} and
         pin['path'] == 'training_labels.json' and type(pin['bytes']) is int and
         0 < pin['bytes'] <= 64000000 and type(pin['sha256']) is str and HEX.fullmatch(pin['sha256']),
         'training labels descriptor')
    return queries


def validate_submission(public, submission):
    queries = public_queries(public)
    need(type(submission) is dict and set(submission) == {'schema', 'packet_id', 'predictions'},
         'exact submission fields')
    need(submission['schema'] == SCHEMA and submission['packet_id'] == public['packet_id'],
         'submission/public packet join')
    rows = submission['predictions']
    need(type(rows) is list and len(rows) == len(queries), 'complete query support required')
    predictions = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'case_id', 'tokens'}, 'prediction fields')
        key = row['case_id']
        need(type(key) is str and key in queries and key not in predictions, 'duplicate/unknown case ID')
        predictions[key] = normalize_tokens(row['tokens'])
    need(set(predictions) == set(queries), 'missing query prediction')
    return queries, predictions


def edit_counts(reference, prediction):
    """Unit-cost Levenshtein; tie order diagonal, deletion, insertion.

    Only total distance is unique in general. I/D/S are a deterministic minimum
    alignment decomposition, not independently observed phonetic events.
    """
    previous = [(j, 0, 0, j) for j in range(len(prediction) + 1)]
    for i, ref in enumerate(reference, 1):
        current = [(i, 0, i, 0)]
        for j, pred in enumerate(prediction, 1):
            d, s, deletion, insertion = previous[j - 1]
            sub = int(ref != pred)
            diagonal = (d + sub, s + sub, deletion, insertion)
            d, s, deletion, insertion = previous[j]
            drop = (d + 1, s, deletion + 1, insertion)
            d, s, deletion, insertion = current[-1]
            add = (d + 1, s, deletion, insertion + 1)
            current.append(min((diagonal, drop, add), key=lambda x: x[0]))
        previous = current
    d, s, deletion, insertion = previous[-1]
    return {'distance': d, 'substitutions': s, 'deletions': deletion, 'insertions': insertion}


def _private_targets(public, queries, private):
    """Validate one complete operator target packet; never discard a query."""
    need(type(private) is dict and set(private) == {'schema', 'packet_id', 'targets'} and
         private['schema'] == 'neural013-targets-v1' and private['packet_id'] == public['packet_id'],
         'private/public packet binding')
    rows = private['targets']
    need(type(rows) is list and len(rows) == len(queries), 'complete private target support')
    targets = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'case_id', 'tokens'}, 'private target fields')
        key = row['case_id']
        need(type(key) is str and key in queries and key not in targets, 'private target join')
        target = normalize_tokens(row['tokens'])
        need(target, 'empty target is unsupported; never silently drop a trial')
        targets[key] = target
    need(set(targets) == set(queries), 'complete private IDs')
    return targets


def _dp_cells(queries, predictions, targets):
    return sum((len(targets[k]) + 1) * (len(predictions[k]) + 1) for k in queries)


def _score_admitted(public, queries, predictions, targets):
    """Original absolute calculation, after complete admission and DP preflight."""
    sessions = {}
    for key, session in sorted(queries.items()):
        out = sessions.setdefault(session, dict(trials=0, exact_matches=0,
                                               reference_tokens=0, distance=0,
                                               substitutions=0, deletions=0, insertions=0))
        counts = edit_counts(targets[key], predictions[key])
        out['trials'] += 1
        out['exact_matches'] += int(targets[key] == predictions[key])
        out['reference_tokens'] += len(targets[key])
        for name, value in counts.items():
            out[name] += value
    for out in sessions.values():
        out['PER'] = out['distance'] / out['reference_tokens']
        out['sequence_exact_match'] = out['exact_matches'] / out['trials']
    sessions = dict(sorted(sessions.items()))
    pooled = {name: sum(out[name] for out in sessions.values())
              for name in ('trials', 'exact_matches', 'reference_tokens', 'distance',
                           'substitutions', 'deletions', 'insertions')}
    pooled['sequence_exact_match'] = pooled['exact_matches'] / pooled['trials']
    macro = math.fsum(v['PER'] for v in sessions.values()) / len(sessions)
    return {'status': 'scored', 'metric': 'later_session_macro_phoneme_error_rate', 'direction': 'lower',
            'packet_id': public['packet_id'], 'score': macro, 'sessions': sessions,
            'query_trials': len(queries), 'query_sessions': len(sessions),
            'pooled_counts_secondary': pooled,
            'session_macro_sequence_exact_match_secondary':
                math.fsum(v['sequence_exact_match'] for v in sessions.values()) / len(sessions),
            'pooled_PER_secondary': sum(v['distance'] for v in sessions.values()) /
                sum(v['reference_tokens'] for v in sessions.values()),
            'participant_count': 1, 'word_boundary_token_included': True,
            'complete_manifest_query_coverage': True,
            'source_panel_authentication': 'not_established_by_scoring',
            'scientific_success': None, 'performance_threshold': None}


def score(public, submission, load_private):
    """Validate complete public output before the single private callback."""
    queries, predictions = validate_submission(public, submission)
    targets = _private_targets(public, queries, load_private())
    cells = _dp_cells(queries, predictions, targets)
    if cells > MAX_DP_CELLS:
        return {'status': 'unsupported_complexity', 'score': None,
                'packet_id': public['packet_id'],
                'reason': 'complete panel exceeds declared DP cell budget', 'cells': cells}
    return _score_admitted(public, queries, predictions, targets)


def compare(public, candidate, comparator, load_private):
    """Operator-only paired PER from two complete outputs and one target capture.

    The existing absolute grades remain unchanged. Canonical operand fingerprints
    belong only to this private report; they do not authenticate source data,
    comparator selection, freeze chronology or execution. No participant feedback
    or observation transport is provided here.
    """
    queries, candidate_predictions = validate_submission(public, candidate)
    _, comparator_predictions = validate_submission(public, comparator)
    # Snapshot admitted inputs before the protected callback. The normalized
    # prediction lists are already detached by validate_submission.
    bound_public = {'packet_id': public['packet_id']}
    identities = {
        'candidate_submission_canonical_sha256': digest(candidate),
        'comparator_submission_canonical_sha256': digest(comparator),
    }
    private = load_private()
    targets = _private_targets(bound_public, queries, private)
    cells = (_dp_cells(queries, candidate_predictions, targets) +
             _dp_cells(queries, comparator_predictions, targets))
    result = {
        'schema': 'neural013-joint-per-comparison-v1',
        'status': 'unsupported_complexity', 'packet_id': bound_public['packet_id'],
        **identities, 'private_targets_canonical_sha256': digest(private),
        'candidate_grade': None, 'comparator_grade': None,
        'session_PER_differences': None, 'macro_PER_difference': None,
        'difference_direction': 'comparator_minus_candidate',
        'comparison_available': False, 'cells': cells, 'participant_count': 1,
        'scientific_success': None, 'confidence_intervals': None, 'p_values': None,
    }
    # The whole pair shares the original one-panel cell ceiling. Preflight the
    # sum before either DP calculation; no partial grade or selected sessions.
    if cells > MAX_DP_CELLS:
        result['reason'] = 'complete pair exceeds declared DP cell budget'
        return result
    a = _score_admitted(bound_public, queries, candidate_predictions, targets)
    b = _score_admitted(bound_public, queries, comparator_predictions, targets)
    differences = {s: b['sessions'][s]['PER'] - a['sessions'][s]['PER']
                   for s in a['sessions']}
    result.update(status='scored', candidate_grade=a, comparator_grade=b,
                  session_PER_differences=differences,
                  macro_PER_difference=math.fsum(differences.values()) / len(differences),
                  comparison_available=True)
    return result

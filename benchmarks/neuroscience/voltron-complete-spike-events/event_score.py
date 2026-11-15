"""Complete Voltron event scoring on independently prepared integer clocks.

Pure scientific library: no files, acquisition, optical extraction, fitting or
candidate execution. The trusted caller owns preparation and target protection.
Invented source controls cannot authenticate animals, traces or measured clocks.
"""
from bisect import bisect_right
import hashlib
import json
import math
from statistics import median

TASK = 'NEURAL-DISC-20261114-VOLTRON-SPIKES'
ROLES = ('candidate', 'optical_mad', 'optical_matched_filter', 'metadata_rate')
MAX_MOVIES = 4096
MAX_TILES = 200000
MAX_EVENTS_PER_ROLE = 1000000
MAX_TICK = 2**63 - 1


class ContractError(ValueError):
    pass


class SubmissionError(ValueError):
    pass


class ReferenceError(ValueError):
    pass


def need(ok, text, error=ContractError):
    if not ok:
        raise error(text)


def fields(value, keys, text, error=ContractError):
    need(type(value) is dict and set(value) == set(keys), text, error)


def name(value, error=ContractError):
    need(type(value) is str and 1 <= len(value) <= 96 and
         all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in value), 'opaque identifier', error)
    return value


def digest(value, error=ContractError):
    need(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'SHA-256 identity', error)
    return value


def integer(value, lo, hi, error=ContractError):
    need(type(value) is int and lo <= value <= hi, 'bounded literal integer', error)
    return value


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def public_contract(value):
    fields(value, ('schema', 'task_id', 'release_manifest_sha256', 'cells', 'expected_animals', 'movies'), 'public fields')
    need(value['schema'] == 'voltron-complete-events-public/v1' and value['task_id'] == TASK, 'task schema')
    digest(value['release_manifest_sha256'])
    # Seven is the paper's reported cohort; the six title tokens are unresolved.
    # A measured census inconsistent with seven must trigger an explicit amendment.
    need(value['expected_animals'] == 7 and type(value['expected_animals']) is int, 'reported seven-animal scope')
    cells = value['cells']
    need(type(cells) is list and len(cells) == 12 and all(type(c) is str for c in cells) and len(set(cells)) == 12, 'complete twelve-cell roster')
    cells = tuple(name(c) for c in cells)
    movies = value['movies']
    need(type(movies) is dict and 12 <= len(movies) <= MAX_MOVIES, 'complete bounded movie roster')
    captured = {}; tile_index = {}; seen_cells = set()
    for key, row in sorted(movies.items()):
        name(key)
        fields(row, ('cell_id', 'fold_id', 'clock_hz', 'optical_rate_hz', 'start_tick', 'end_tick',
                     'input_disposition', 'optical_valid_intervals', 'tiles'), 'movie fields')
        need(row['cell_id'] in cells, 'rostered cell'); seen_cells.add(row['cell_id'])
        name(row['fold_id']); hz = integer(row['clock_hz'], 1, 10**9)
        rate = integer(row['optical_rate_hz'], 400, 1000)
        need(rate in (400, 1000) and hz % rate == 0, 'exact 400/1000 Hz optical clock grid')
        start = integer(row['start_tick'], 0, MAX_TICK); end = integer(row['end_tick'], start + 1, MAX_TICK)
        need(row['input_disposition'] in ('ready', 'optical_extraction_failed'), 'declared optical extraction disposition')
        optical = _intervals(row['optical_valid_intervals'], start, end, ContractError)
        need(bool(optical) == (row['input_disposition'] == 'ready'), 'failed extraction retains explicit empty optical support')
        need(type(row['tiles']) is list and 1 <= len(row['tiles']) <= MAX_TILES, 'complete bounded cores')
        at = start; tiles = []
        for tile in row['tiles']:
            fields(tile, ('tile_id', 'start_tick', 'end_tick'), 'tile fields')
            tile_id = name(tile['tile_id'])
            left = integer(tile['start_tick'], start, end - 1); right = integer(tile['end_tick'], left + 1, end)
            need(left == at and tile_id not in tile_index, 'unique contiguous half-open cores')
            tile_index[tile_id] = (key, left, right); tiles.append((tile_id, left, right)); at = right
        need(at == end and len(tile_index) <= MAX_TILES, 'full movie duration, no gap or truncated tail')
        captured[key] = {'cell_id': row['cell_id'], 'fold_id': row['fold_id'], 'clock_hz': hz,
                         'optical_rate_hz': rate, 'start_tick': start, 'end_tick': end, 'tiles': tuple(tiles),
                         'input_disposition': row['input_disposition'], 'optical_valid_intervals': optical}
    need(seen_cells == set(cells), 'no omitted cell')
    return {'identity': identity(value), 'cells': cells, 'movies': captured, 'tiles': tile_index,
            'release_manifest_sha256': value['release_manifest_sha256'], 'expected_animals': 7}


def events(value, lo, hi, error):
    need(type(value) is list and len(value) <= MAX_EVENTS_PER_ROLE, 'bounded event list', error)
    out = []; previous = None
    for tick in value:
        integer(tick, lo, hi - 1, error)
        need(previous is None or tick > previous, 'strict sorted unique event ticks', error)
        out.append(tick); previous = tick
    return tuple(out)


def capture_predictions(value, contract):
    fields(value, ('schema', 'task_id', 'public_sha256', 'roles'), 'prediction fields', SubmissionError)
    need(value['schema'] == 'voltron-complete-events-predictions/v1' and value['task_id'] == TASK and
         value['public_sha256'] == contract['identity'], 'prediction task/source identity', SubmissionError)
    need(type(value['roles']) is dict and set(value['roles']) == set(ROLES), 'all four matched roles', SubmissionError)
    captured = {}; commitments = {}
    for role in ROLES:
        row = value['roles'][role]
        fields(row, ('program_sha256', 'calibration_sha256', 'tiles'), 'role fields', SubmissionError)
        commitments[role] = {k: digest(row[k], SubmissionError) for k in ('program_sha256', 'calibration_sha256')}
        need(type(row['tiles']) is dict and set(row['tiles']) == set(contract['tiles']), 'complete identical core support', SubmissionError)
        by_movie = {}; total = 0
        for movie_id, movie in contract['movies'].items():
            whole = []
            for tile_id, start, end in movie['tiles']:
                ticks = events(row['tiles'][tile_id], start, end, SubmissionError)
                total += len(ticks)
                need(total <= MAX_EVENTS_PER_ROLE, 'whole-role event budget', SubmissionError)
                whole.extend(ticks)
            by_movie[movie_id] = tuple(whole)
        captured[role] = by_movie
    return captured, commitments


def _intervals(value, start, end, error=ReferenceError):
    need(type(value) is list and len(value) <= MAX_TILES, 'bounded validity intervals', error)
    merged = []
    for pair in value:
        need(type(pair) is list and len(pair) == 2, 'validity interval pair', error)
        left = integer(pair[0], start, end - 1, error)
        right = integer(pair[1], left + 1, end, error)
        need(not merged or left >= merged[-1][1], 'sorted nonoverlapping validity', error)
        if merged and left == merged[-1][1]: merged[-1] = (merged[-1][0], right)
        else: merged.append((left, right))
    return tuple(merged)


def _contains(tick, spans):
    i = bisect_right(spans, (tick, MAX_TICK)) - 1
    return i >= 0 and spans[i][0] <= tick < spans[i][1]


def _covered(left, right, spans):
    i = bisect_right(spans, (left, MAX_TICK)) - 1
    return i >= 0 and spans[i][0] <= left < right <= spans[i][1]


def capture_reference(value, contract):
    fields(value, ('schema', 'task_id', 'public_sha256', 'census_evidence_sha256', 'mapping_evidence_sha256',
                   'cell_to_animal', 'outer_folds', 'movies'), 'reference fields', ReferenceError)
    need(value['schema'] == 'voltron-complete-events-reference/v1' and value['task_id'] == TASK and
         value['public_sha256'] == contract['identity'], 'reference source identity', ReferenceError)
    digest(value['census_evidence_sha256'], ReferenceError); digest(value['mapping_evidence_sha256'], ReferenceError)
    mapping = value['cell_to_animal']
    need(type(mapping) is dict and set(mapping) == set(contract['cells']), 'complete cell/animal mapping', ReferenceError)
    mapping = {c: name(a, ReferenceError) for c, a in mapping.items()}
    animals = set(mapping.values())
    need(len(animals) == contract['expected_animals'], 'seven resolved biological groups required', ReferenceError)
    folds = value['outer_folds']
    need(type(folds) is dict and len(folds) == len(animals), 'complete leave-one-animal-out folds', ReferenceError)
    query_animals = set()
    for fid, row in folds.items():
        name(fid, ReferenceError)
        fields(row, ('query_animal', 'train_cells'), 'fold fields', ReferenceError)
        a = name(row['query_animal'], ReferenceError)
        need(a in animals and a not in query_animals, 'one query fold per animal', ReferenceError); query_animals.add(a)
        train = row['train_cells']
        need(type(train) is list and all(type(x) is str for x in train) and len(set(train)) == len(train) and
             set(train) == {c for c in mapping if mapping[c] != a}, 'whole-animal training/query separation', ReferenceError)
    need(query_animals == animals, 'all animals evaluated', ReferenceError)
    need(type(value['movies']) is dict and set(value['movies']) == set(contract['movies']), 'complete gold movie coverage', ReferenceError)
    captured = {}; total = 0
    for mid, public in contract['movies'].items():
        fid = public['fold_id']
        need(fid in folds and folds[fid]['query_animal'] == mapping[public['cell_id']], 'every movie follows its animal fold', ReferenceError)
        row = value['movies'][mid]; fields(row, ('valid_intervals', 'spikes'), 'gold movie fields', ReferenceError)
        spans = _intervals(row['valid_intervals'], public['start_tick'], public['end_tick'])
        need(all(_covered(a, b, public['optical_valid_intervals']) for a, b in spans),
             'scored intervals must be within optical validity', ReferenceError)
        spikes = events(row['spikes'], public['start_tick'], public['end_tick'], ReferenceError); total += len(spikes)
        need(total <= MAX_EVENTS_PER_ROLE and all(_contains(t, spans) for t in spikes), 'truth only in declared valid support', ReferenceError)
        captured[mid] = {'valid_intervals': spans, 'spikes': spikes}
    return captured, mapping


def match_events(predictions, truth, clock_hz):
    """Maximum-cardinality ordered matching, inclusive exactly 1/200 second.

    Earliest-compatible greedy matching attains maximum cardinality for sorted
    points under an equal interval tolerance. Ties use chronological order;
    latency is descriptive under this matching, not minimum-latency assignment.
    """
    i = j = 0; latency_ticks = []
    while i < len(predictions) and j < len(truth):
        delta = predictions[i] - truth[j]
        if delta * 200 < -clock_hz: i += 1
        elif delta * 200 > clock_hz: j += 1
        else:
            latency_ticks.append(delta); i += 1; j += 1
    tp = len(latency_ticks)
    return tp, len(predictions) - tp, len(truth) - tp, tuple(latency_ticks)


def metric(tp, fp, fn, duration, latency):
    return {'tp': tp, 'fp': fp, 'fn': fn,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            'valid_duration_seconds': duration,
            'false_events_per_minute': 60 * fp / duration if duration > 0 else None,
            'matched_latency_mean_ms': math.fsum(latency) / len(latency) if latency else None,
            'matched_latency_median_ms': median(latency) if latency else None,
            'matched_absolute_latency_mean_ms': math.fsum(abs(v) for v in latency) / len(latency) if latency else None}


def score_movie(predicted, gold, public):
    # Match across tile boundaries after the complete movie is reassembled.
    # Never match across an invalid electrical/optical interval.
    p = q = 0; tp = fp = fn = 0; latency = []; valid_predictions = 0
    for left, right in gold['valid_intervals']:
        while p < len(predicted) and predicted[p] < left: p += 1
        p0 = p
        while p < len(predicted) and predicted[p] < right: p += 1
        while q < len(gold['spikes']) and gold['spikes'][q] < left: q += 1
        q0 = q
        while q < len(gold['spikes']) and gold['spikes'][q] < right: q += 1
        a, b, c, ticks = match_events(predicted[p0:p], gold['spikes'][q0:q], public['clock_hz'])
        tp += a; fp += b; fn += c; valid_predictions += p - p0
        latency.extend(t * 1000 / public['clock_hz'] for t in ticks)
    valid_ticks = sum(b - a for a, b in gold['valid_intervals']); hz = public['clock_hz']
    result = metric(tp, fp, fn, valid_ticks / hz, latency)
    result.update(total_duration_seconds=(public['end_tick'] - public['start_tick']) / hz,
                  valid_duration_fraction=valid_ticks / (public['end_tick'] - public['start_tick']),
                  predictions_outside_valid_support=len(predicted) - valid_predictions,
                  support_disposition='unscorable' if valid_ticks == 0 else ('partial_validity' if valid_ticks < public['end_tick'] - public['start_tick'] else 'complete_validity'),
                  optical_rate_hz=public['optical_rate_hz'], cell_id=public['cell_id'],
                  input_disposition=public.get('input_disposition', 'ready'),
                  matching_rule='earliest_compatible_max_cardinality_inclusive_5ms')
    return result, latency


def role_result(by_movie, reference, contract, animals):
    movies = {}; cells = {}; latency_by_cell = {c: [] for c in contract['cells']}
    for mid, public in contract['movies'].items():
        movies[mid], latency = score_movie(by_movie[mid], reference[mid], public)
        latency_by_cell[public['cell_id']].extend(latency)
    for c in contract['cells']:
        rows = [r for r in movies.values() if r['cell_id'] == c]
        scored = metric(*(sum(r[k] for r in rows) for k in ('tp', 'fp', 'fn')),
                        math.fsum(r['valid_duration_seconds'] for r in rows), latency_by_cell[c])
        complete_validity = all(r['support_disposition'] == 'complete_validity' for r in rows)
        scored.update(movie_count=len(rows), complete_validity=complete_validity,
                      total_duration_seconds=math.fsum(r['total_duration_seconds'] for r in rows),
                      predictions_outside_valid_support=sum(r['predictions_outside_valid_support'] for r in rows))
        cells[c] = scored
    grouped = {}
    for animal in sorted(set(animals.values())):
        members = sorted(c for c in cells if animals[c] == animal)
        defined = [cells[c]['f1'] for c in members if cells[c]['f1'] is not None]
        grouped[animal] = {'cells': members, 'cell_count': len(members), 'defined_cell_count': len(defined),
                           'equal_cell_f1': math.fsum(defined) / len(members) if len(defined) == len(members) else None,
                           'observed_only_equal_cell_f1': math.fsum(defined) / len(defined) if defined else None,
                           'complete_validity': all(cells[c]['complete_validity'] for c in members)}
    strata = {}
    for rate in (400, 1000):
        rows = [r for r in movies.values() if r['optical_rate_hz'] == rate]
        strata[str(rate)] = {'movie_count': len(rows), 'tp': sum(r['tp'] for r in rows),
                             'fp': sum(r['fp'] for r in rows), 'fn': sum(r['fn'] for r in rows),
                             'valid_duration_seconds': math.fsum(r['valid_duration_seconds'] for r in rows)}
    return {'movies': movies, 'cells': cells, 'animals': grouped, 'sampling_rate_strata': strata}


def grade(public, predictions, private_loader):
    """Admit all roles/tiles before the trusted caller's one private callback.

    No candidate code runs here. The callback belongs to the trusted evaluator,
    not the candidate. This pure scorer is not a process-isolation mechanism.
    """
    contract = public_contract(public)
    try:
        captured, commitments = capture_predictions(predictions, contract)
    except SubmissionError as error:
        return {'status': 'invalid_submission', 'reason': str(error), 'private_reference_loads': 0,
                'task_id': TASK, 'scientific_qualified': False, 'new_benchmark_ids': 0}
    reference, animals = capture_reference(private_loader(), contract)
    results = {role: role_result(captured[role], reference, contract, animals) for role in ROLES}
    contrasts = {}
    for baseline in ROLES[1:]:
        contrasts[baseline] = {'candidate_minus_baseline_animal_f1': {
            a: (results['candidate']['animals'][a]['equal_cell_f1'] - results[baseline]['animals'][a]['equal_cell_f1']
                if results['candidate']['animals'][a]['equal_cell_f1'] is not None and
                results[baseline]['animals'][a]['equal_cell_f1'] is not None else None)
            for a in results['candidate']['animals']}}
    return {'status': 'scored_source_component', 'task_id': TASK, 'private_reference_loads': 1,
            'public_sha256': contract['identity'], 'commitments': commitments, 'roles': results,
            'contrasts': contrasts, 'primary': 'seven animal-specific equal-cell F1 values; no cross-animal headline',
            'no_empty_empty_perfect_score': True, 'partial_validity_is_disclosed': True,
            'primary_support': 'declared valid optical/electrical intersection only; partial validity is not full-duration success',
            'mapping_and_clock_authenticity_established_by_this_code': False,
            'scientific_qualified': False, 'new_benchmark_ids': 0}

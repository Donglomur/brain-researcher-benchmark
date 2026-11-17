"""Trusted, pure preparation/projection seams for the NEURAL-099 condition.

No files are opened and no code executes at import. Supplied source arrays must
be authenticated by a separately admitted preparer. This module does not provide
that authentication, a process sandbox, or verified physiological observation.
"""
from bisect import bisect_left
from copy import deepcopy
import hashlib
import math


REGIONS = ('BIC', 'MGd', 'MGm', 'MGv', 'MZMG', 'SG')
ASSUMPTION = (
    'Eligible deposited source clusters cover each prespecified response and '
    'permitted history window without unrepresented interruption that materially '
    'changes the endpoint. This is an explicit benchmark assumption, not a '
    'source-declared or verified fact and not whole-session continuity.'
)
FOLD_NAMESPACE = 'NEURAL-099|condition-b|outer-v1|'


def finite(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(name + ' must be a finite real number')
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(name + ' must be an integer >= ' + str(minimum))
    return value


def text(value, name):
    if type(value) is not str or not value or len(value) > 256 or '\0' in value:
        raise ValueError(name + ' must be nonempty bounded text without NUL')
    return value


def selected_protocol():
    """Return construction choices; this is not an authenticated data binding."""
    return {
        'schema': 'neural099-assumed-support-protocol/v1',
        'condition_id': 'processed-regional-early-response-assumed-support-v1',
        'response_edges_microseconds': list(range(0, 100001, 1000)),
        'history_edges_microseconds': list(range(-100000, 1, 1000)),
        'cluster_policy': 'source_good_and_mua_with_literal_named_region',
        'observation_assumption': ASSUMPTION,
        'query_delivery': 'chronological_prediction_locked_before_later_history',
        'fold_namespace': FOLD_NAMESPACE,
        'outer_folds': 5,
        'secondary_coarsening_factor': 5,
        'state_policy': 'permitted_past_within_animal_reset_between_animals_and_outer_folds',
        'final_refit': 'one_frozen_refit_all_four_nonquery_folds_after_selection',
        'biological_identity_qualified': False,
        'actual_timing_qualified': False,
        'verified_physiological_coverage': False,
    }


def validate_protocol(protocol):
    # An explicit exact profile prevents a caller silently changing this endpoint.
    if type(protocol) is not dict or protocol != selected_protocol():
        raise ValueError('Unselected or modified construction protocol')
    # Python equality treats bool and int as equal; retain strict numeric types.
    for name in ('response_edges_microseconds', 'history_edges_microseconds'):
        if type(protocol[name]) is not list or any(type(v) is not int for v in protocol[name]):
            raise ValueError('Protocol edges must be integer microseconds')
    for name in ('outer_folds', 'secondary_coarsening_factor'):
        integer(protocol[name], name, 1)
    for name in ('biological_identity_qualified', 'actual_timing_qualified',
                 'verified_physiological_coverage'):
        if protocol[name] is not False:
            raise ValueError('Construction profile cannot promote qualification')
    return deepcopy(protocol)


def declared_folds(source_subject_ids, *, biological_identity_review):
    """Freeze declared source-ID membership; biological review is not inferred.

    The review records exact subject groups and any known aliases. No equality
    between file count and biological sample size is assumed. A separate caller
    may qualify the reviewed groups, but this function never does so itself.
    """
    if type(source_subject_ids) is not list or not source_subject_ids:
        raise ValueError('Nonempty source subject roster required')
    for subject in source_subject_ids:
        text(subject, 'source_subject_id')
    if len(set(source_subject_ids)) != len(source_subject_ids):
        raise ValueError('Supply unique source subjects, not one entry per file')
    required = {'source_to_animal', 'evidence', 'status'}
    if type(biological_identity_review) is not dict or set(biological_identity_review) != required:
        raise ValueError('Explicit biological identity review required')
    mapping = biological_identity_review['source_to_animal']
    if type(mapping) is not dict or set(mapping) != set(source_subject_ids):
        raise ValueError('Identity mapping must cover the exact source roster')
    for animal in mapping.values():
        text(animal, 'animal_id')
    if biological_identity_review['status'] not in ('declared_source_identity_only', 'reviewed_identity_groups'):
        raise ValueError('Unknown identity status')
    if type(biological_identity_review['evidence']) is not list or not biological_identity_review['evidence']:
        raise ValueError('Identity evidence references are required')
    for evidence in biological_identity_review['evidence']:
        text(evidence, 'identity evidence reference')
    groups = {}
    for subject, animal in mapping.items():
        groups.setdefault(animal, []).append(subject)
    if len(groups) < 5:
        raise ValueError('Five-fold condition needs at least five identity groups')
    # Bind authenticated animal identifiers before applying this fixed rule.
    # No source-value tuning or implicit file-as-animal inference is performed.
    digests = {animal: hashlib.sha256((FOLD_NAMESPACE + animal).encode()).hexdigest()
               for animal in groups}
    order = sorted(groups, key=lambda animal: (digests[animal], animal))
    membership = {animal: rank % 5 for rank, animal in enumerate(order)}
    folds = []
    for query in range(5):
        validation = (query + 1) % 5
        folds.append({
            'outer_fold': query,
            'query_animals': [a for a in order if membership[a] == query],
            'validation_animals': [a for a in order if membership[a] == validation],
            'initial_train_animals': [a for a in order if membership[a] not in (query, validation)],
            'final_refit_animals': [a for a in order if membership[a] != query],
        })
    return {'schema': 'neural099-declared-folds/v1', 'namespace': FOLD_NAMESPACE,
            'identity_status': biological_identity_review['status'],
            'identity_evidence': deepcopy(biological_identity_review['evidence']),
            'source_to_animal': deepcopy(mapping), 'group_hashes': digests,
            'folds': folds, 'biological_independence_verified': False,
            'runtime_fold_isolation_qualified': False}


def _times(values, name):
    if type(values) not in (list, tuple):
        raise ValueError(name + ' must be a sequence')
    result = [finite(v, name) for v in values]
    if any(b < a for a, b in zip(result, result[1:])):
        raise ValueError(name + ' must be ordered')
    return result


def _edges(anchor, offsets):
    edges = [anchor + offset / 1000000 for offset in offsets]
    if any(not math.isfinite(v) for v in edges) or any(b <= a for a, b in zip(edges, edges[1:])):
        raise ValueError('Clock magnitude cannot represent selected bin edges')
    return edges


def _intervals_disjoint(left, right):
    i = j = 0
    while i < len(left) and j < len(right):
        a, b = left[i]
        c, d = right[j]
        if max(a, c) < min(b, d):
            return False
        if b <= d:
            i += 1
        else:
            j += 1
    return True


def _covered(window, intervals):
    start, stop = window
    cursor = start
    for lower, upper in intervals:
        if upper <= cursor:
            continue
        if lower > cursor:
            return False
        cursor = max(cursor, upper)
        if cursor >= stop:
            return True
    return False


def _counts(spikes, cluster_ids, edges):
    counts = [0] * (len(edges) - 1)
    for cluster in cluster_ids:
        positions = [bisect_left(spikes[cluster], edge) for edge in edges]
        for i, (left, right) in enumerate(zip(positions, positions[1:])):
            counts[i] += right - left
    return counts


def prepare_asset(support_asset, *, animal_id, protocol, trials, spikes_by_cluster,
                  known_observation_intervals=None):
    """Count authenticated caller-supplied events; generated fixtures only so far.

    The caller must later authenticate source bytes, clock/anchor semantics and
    trial values. Returned gold is evaluator-private. No coverage is inferred
    from first/last events, trial stops, histology clocks or missing intervals.
    """
    validate_protocol(protocol)
    text(animal_id, 'animal_id')
    if type(support_asset) is not dict:
        raise ValueError('Support asset required')
    asset_id = text(support_asset.get('asset_id'), 'asset_id')
    text(support_asset.get('source_subject_id'), 'source_subject_id')
    expected = integer(support_asset.get('source_trial_rows'), 'source_trial_rows', 1)
    regions = support_asset.get('regions')
    if type(regions) is not list or not regions:
        raise ValueError('At least one supported named region required')
    region_ids, eligible, seen_regions = {}, set(), set()
    for row in regions:
        if type(row) is not dict or row.get('region') not in REGIONS or row['region'] in seen_regions:
            raise ValueError('Invalid or duplicate supported named region')
        region = row['region']
        seen_regions.add(region)
        ids = row.get('cluster_ids')
        if type(ids) is not list or not ids:
            raise ValueError('Unsupported zero-denominator region cannot be prepared')
        for cluster in ids:
            integer(cluster, 'cluster_id')
        if len(ids) != len(set(ids)) or eligible.intersection(ids):
            raise ValueError('Duplicate source cluster assignment')
        if integer(row.get('cluster_count'), 'cluster_count', 1) != len(ids):
            raise ValueError('Cluster denominator differs from frozen support')
        eligible.update(ids)
        region_ids[region] = ids
    if type(spikes_by_cluster) is not dict or any(type(k) is not int for k in spikes_by_cluster):
        raise ValueError('Spike arrays must be keyed by asset-scoped integer cluster IDs')
    if set(spikes_by_cluster) != eligible:
        raise ValueError('Spike arrays must cover exactly the eligible source clusters')
    spikes = {key: _times(values, 'source spike times') for key, values in spikes_by_cluster.items()}
    if type(trials) is not list or len(trials) != expected:
        raise ValueError('All declared source trial rows must be retained')
    anchors, ids, stops = [], set(), []
    for trial in trials:
        if type(trial) is not dict or set(trial) != {'source_trial_id', 'start_seconds', 'stop_seconds'}:
            raise ValueError('Exact authenticated trial fields required')
        trial_id = trial['source_trial_id']
        if type(trial_id) is not int or not -(2**63) <= trial_id < 2**63:
            raise ValueError('Source trial ID must preserve the signed int64 identifier')
        if trial_id in ids:
            raise ValueError('Duplicate source trial ID')
        ids.add(trial_id)
        start = finite(trial['start_seconds'], 'click start')
        stop = finite(trial['stop_seconds'], 'click stop')
        if stop <= start or (anchors and start <= anchors[-1]):
            raise ValueError('Clicks need positive duration and strictly chronological source rows')
        anchors.append(start)
        stops.append(stop)
    response_edges = [_edges(a, protocol['response_edges_microseconds']) for a in anchors]
    history_edges = [_edges(a, protocol['history_edges_microseconds']) for a in anchors]
    response_windows = [(e[0], e[-1]) for e in response_edges]
    history_windows = [(e[0], e[-1]) for e in history_edges]
    if not _intervals_disjoint(history_windows, response_windows):
        raise ValueError('Permitted histories intersect a scored response window; reconsider protocol')
    if known_observation_intervals is not None:
        if type(known_observation_intervals) is not dict or set(known_observation_intervals) != eligible:
            raise ValueError('Known observation support must cover every eligible cluster')
        for cluster, intervals in known_observation_intervals.items():
            if type(cluster) is not int or type(intervals) is not list:
                raise ValueError('Invalid known observation interval representation')
            previous = -math.inf
            for interval in intervals:
                if type(interval) not in (list, tuple) or len(interval) != 2:
                    raise ValueError('Known observation intervals must be pairs')
                lower, upper = [finite(t, 'observation boundary') for t in interval]
                if upper <= lower or lower < previous:
                    raise ValueError('Known observation intervals must be ordered nonoverlapping intervals')
                previous = upper
            if not all(_covered(w, intervals) for w in response_windows + history_windows):
                raise ValueError('Known observation gap intersects selected support; no zero imputation')
    cases, gold, observations, provenance = [], [], [], []
    for ordinal, anchor in enumerate(anchors):
        for region in sorted(region_ids):
            clusters = region_ids[region]
            case_id = asset_id + ':' + str(ordinal) + ':' + region
            case = {'case_id': case_id, 'animal_id': animal_id, 'asset_id': asset_id,
                    'region': region, 'source_trial_row': ordinal,
                    'source_cluster_count': len(clusters)}
            cases.append(case)
            gold.append({'case': deepcopy(case),
                         'counts': _counts(spikes, clusters, response_edges[ordinal])})
            history_counts = _counts(spikes, clusters, history_edges[ordinal])
            observation = {
                'case': deepcopy(case),
                'timing': {'click_duration_seconds': stops[ordinal] - anchor,
                           'elapsed_since_first_click_seconds': anchor - anchors[0],
                           'previous_click_interval_seconds': None if ordinal == 0 else anchor - anchors[ordinal-1]},
                'history_rates': [count / (len(clusters) * 0.001) for count in history_counts],
            }
            observations.append(observation)
            provenance.append({'case_id': case_id, 'source_trial_id': trials[ordinal]['source_trial_id'],
                               'source_start_seconds': anchor, 'source_stop_seconds': stops[ordinal]})
    return {'schema': 'neural099-prepared-source-seam/v1', 'cases': cases,
            'private_gold': gold, 'permitted_observations': observations,
            'private_source_trial_provenance': provenance,
            'source_authentication_performed_by_this_function': False,
            'verified_physiological_coverage': False,
            'known_observation_intervals_checked': known_observation_intervals is not None,
            'observation_assumption': ASSUMPTION}


def project(observation, *, view):
    """Both presentation arms receive this exact semantic observation record."""
    from scoring import validate_cases
    if view not in ('timing', 'timing_history'):
        raise ValueError('Unknown information condition')
    if type(observation) is not dict or set(observation) != {'case', 'timing', 'history_rates'}:
        raise ValueError('Observation must use the preparation seam schema')
    validate_cases([observation['case']])
    timing = observation['timing']
    if type(timing) is not dict or set(timing) != {'click_duration_seconds',
            'elapsed_since_first_click_seconds', 'previous_click_interval_seconds'}:
        raise ValueError('Exact permitted timing fields required')
    if finite(timing['click_duration_seconds'], 'click duration') <= 0:
        raise ValueError('Click duration must be positive')
    if finite(timing['elapsed_since_first_click_seconds'], 'elapsed click time') < 0:
        raise ValueError('Elapsed click time must be nonnegative')
    previous = timing['previous_click_interval_seconds']
    if previous is not None and finite(previous, 'previous click interval') <= 0:
        raise ValueError('Previous click interval must be positive')
    # Deliberate allowlist: gold, response counts and private source fields never
    # pass through, even if a future caller changes its upstream representation.
    result = {'case': deepcopy(observation['case']), 'timing': deepcopy(observation['timing'])}
    if view == 'timing_history':
        history = observation['history_rates']
        if type(history) is not list or len(history) != 100:
            raise ValueError('Exactly 100 permitted history bins required')
        if any(finite(v, 'history rate') < 0 for v in history):
            raise ValueError('Negative deposited-event history rate')
        result['history_rates'] = list(history)
    return result


def score_selected(cases, predictions, gold):
    """Bind the reusable scorer to the selected endpoint, not a caller's bins."""
    from scoring import score
    return score(cases, predictions, gold,
                 edges_seconds=[i / 1000 for i in range(101)], coarsening_factor=5)


def baseline_selected(training_cases, training_gold, query_cases):
    """Final training partition is supplied by the isolated outer-fold operator."""
    from scoring import training_mean_baseline
    return training_mean_baseline(training_cases, training_gold, query_cases,
                                  edges_seconds=[i / 1000 for i in range(101)])


class ChronologicalQuery:
    """Cooperative trusted-evaluator state seam, not candidate containment.

    Keep this object outside participant processes. A runtime must separately
    enforce process/filesystem isolation and fresh outer-fold state. Future
    input records are intentionally not returned until current predictions lock.
    """
    def __init__(self, observations, *, view, edges_seconds):
        from scoring import validate_cases
        canonical_edges = [i / 1000 for i in range(101)]
        if (type(edges_seconds) is not list or
                any(type(v) not in (int, float) for v in edges_seconds) or
                edges_seconds != canonical_edges):
            raise ValueError('Query predictions must use selected 100 one-millisecond response bins')
        if type(observations) is not list or not observations:
            raise ValueError('Nonempty query observations required')
        cases = [row.get('case') if type(row) is dict else None for row in observations]
        validate_cases(cases)
        if len({case['animal_id'] for case in cases}) != 1:
            raise ValueError('Create fresh query state for each animal')
        if len({case['asset_id'] for case in cases}) != 1:
            raise ValueError('Multi-session animal chronology requires a separately qualified source schedule')
        self._groups = []
        self._predictions = []
        self._index = 0
        self._edges = deepcopy(edges_seconds)
        self._view = view
        seen_groups, last_row = set(), {}
        for observation in observations:
            # Validate projections before recording any state; no future content
            # is emitted by this constructor.
            projected = project(observation, view=view)
            case = projected['case']
            key = (case['animal_id'], case['asset_id'], case['source_trial_row'])
            if not self._groups or self._groups[-1][0] != key:
                if key in seen_groups:
                    raise ValueError('Trial regions must be contiguous')
                asset = (case['animal_id'], case['asset_id'])
                if asset in last_row and case['source_trial_row'] <= last_row[asset]:
                    raise ValueError('Query rows must be chronological within source asset')
                last_row[asset] = case['source_trial_row']
                seen_groups.add(key)
                self._groups.append((key, []))
            self._groups[-1][1].append(projected)

    def current(self):
        if self._index == len(self._groups):
            return None
        return deepcopy(self._groups[self._index][1])

    def commit(self, predictions):
        from scoring import admit_predictions
        if self._index == len(self._groups):
            raise ValueError('All query predictions are already locked')
        cases = [row['case'] for row in self._groups[self._index][1]]
        admit_predictions(cases, predictions, edges_seconds=self._edges)
        self._predictions.extend(deepcopy(predictions))
        self._index += 1
        return {'locked_trials': self._index, 'complete': self._index == len(self._groups)}

    def locked_predictions(self):
        if self._index != len(self._groups):
            raise ValueError('Full prediction set unavailable until all trials lock')
        return deepcopy(self._predictions)

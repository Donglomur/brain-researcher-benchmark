"""Trusted paired-view adapter for the first stateless, zero-label condition.

Constructing this adapter validates metadata only. Candidate observations contain
all available regions for one trial; neither source trial IDs nor absolute clocks
are exposed. The trusted history callback is invoked only for timing_history.

This is a cooperative evaluator interface, not candidate authentication or process
containment. The caller/session enforces current-trial release and a fresh context
for every trial. Complete source membership and identity are authenticated outside
this adapter; internal consistency cannot recover wholly omitted source records.
"""

import math


CASE_FIELDS = frozenset((
    'case_id', 'asset_id', 'animal_id', 'source_trial_row', 'source_trial_id',
    'trial_start_seconds', 'trial_stop_seconds', 'region', 'source_cluster_count'))
VISIBLE_FIELDS = ('case_id', 'animal_id', 'asset_id', 'region',
                  'source_trial_row', 'source_cluster_count')
REGIONS = frozenset(('BIC', 'MGd', 'MGm', 'MGv', 'MZMG', 'SG'))


class ObservationError(ValueError):
    """Metadata or its exact requested projection violates the view contract."""


def _require(condition, message):
    if not condition:
        raise ObservationError(message)


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= 256
             and all(ord(c) >= 32 for c in value), 'Invalid ' + label)
    return value


def _integer(value, label, minimum=None):
    _require(type(value) is int and (minimum is None or value >= minimum),
             'Invalid ' + label)
    return value


def _clock(value, label):
    _require(type(value) in (int, float), 'Invalid ' + label)
    try:
        result = float(value)
    except OverflowError as exc:
        raise ObservationError('Nonfinite ' + label) from exc
    _require(math.isfinite(result), 'Nonfinite ' + label)
    return result


class ObservationAdapter:
    """Expose matched timing/timing_history observations from private metadata.

    ``history_projection(case_id, *, released_case_id)`` must return exactly
    ``{'case': six_visible_fields, 'history_rates': 100_float_values}``, as the
    retained count codec does. Its rates are copied without re-normalization,
    rounding, smoothing, or substitutions. A failed/missing history refuses the
    whole requested observation group; it never downgrades to timing-only.
    """

    def __init__(self, private_cases, history_projection):
        _require(type(private_cases) is list and private_cases,
                 'A nonempty private case metadata list is required')
        _require(callable(history_projection), 'A trusted history callback is required')
        groups, trials, asset_animals, denominators = {}, {}, {}, {}
        ids, coordinates, trial_ids = set(), set(), {}
        for original in private_cases:
            _require(type(original) is dict and set(original) == CASE_FIELDS,
                     'Expected the exact nine private metadata fields')
            case = {name: _text(original[name], name)
                    for name in ('case_id', 'asset_id', 'animal_id', 'region')}
            _require(case['region'] in REGIONS, 'Unsupported or unassigned source region')
            row = _integer(original['source_trial_row'], 'source trial row', 0)
            source_id = _integer(original['source_trial_id'], 'source trial ID')
            count = _integer(original['source_cluster_count'], 'source cluster count', 1)
            start = _clock(original['trial_start_seconds'], 'trial start')
            stop = _clock(original['trial_stop_seconds'], 'trial stop')
            duration = _clock(stop - start, 'click duration')
            _require(duration > 0, 'Click duration must be positive')
            case.update(source_trial_row=row, source_cluster_count=count)
            asset, region = case['asset_id'], case['region']
            key, coordinate = (asset, row), (asset, row, region)
            _require(case['case_id'] not in ids and coordinate not in coordinates,
                     'Duplicate case identity or asset/trial/region coordinate')
            ids.add(case['case_id'])
            coordinates.add(coordinate)
            if asset in asset_animals:
                _require(asset_animals[asset] == case['animal_id'], 'Conflicting asset animal identity')
            asset_animals[asset] = case['animal_id']
            cell = (asset, region)
            if cell in denominators:
                _require(denominators[cell] == count, 'Source cluster denominator changes across trials')
            denominators[cell] = count
            timing_identity = (source_id, start, stop)
            if key in trials:
                _require(trials[key] == timing_identity, 'Regions disagree on source trial identity or clocks')
            trials[key] = timing_identity
            id_key = (asset, source_id)
            if id_key in trial_ids:
                _require(trial_ids[id_key] == row, 'Source trial ID refers to multiple row ordinals')
            trial_ids[id_key] = row
            groups.setdefault(key, []).append(case)
        visible_groups, relative_timing = {}, {}
        for asset in sorted(asset_animals):
            rows = sorted(row for owner, row in groups if owner == asset)
            _require(rows == list(range(len(rows))), 'Source trial row ordinals must be complete from zero')
            available_regions = {region for owner, region in denominators if owner == asset}
            first_start, previous_start = trials[(asset, 0)][1], None
            for row in rows:
                key = (asset, row)
                cases = sorted(groups[key], key=lambda case: case['region'])
                _require({case['region'] for case in cases} == available_regions,
                         'A source trial omits an available region')
                _, start, stop = trials[key]
                elapsed = _clock(start - first_start, 'elapsed time since first click')
                interval = None if previous_start is None else _clock(
                    start - previous_start, 'previous click interval')
                _require(elapsed >= 0 and (interval is None or interval > 0),
                         'Source trial starts must be strictly chronological')
                relative_timing[key] = {
                    'click_duration_seconds': stop - start,
                    'elapsed_since_first_click_seconds': elapsed,
                    'previous_click_interval_seconds': interval,
                }
                visible_groups[key] = tuple({field: case[field] for field in VISIBLE_FIELDS}
                                            for case in cases)
                previous_start = start
        # Only candidate-visible metadata and relative timing survive construction.
        self.__groups = visible_groups
        self.__timing = relative_timing
        self.__keys = tuple(sorted(visible_groups))
        self.__history_projection = history_projection

    def keys(self):
        """Return asset-sorted keys, in original chronological row order per asset."""
        return self.__keys

    def _key(self, key):
        _require(type(key) is tuple and len(key) == 2, 'Expected an (asset_id, source_trial_row) key')
        _text(key[0], 'asset ID')
        _integer(key[1], 'source trial row', 0)
        _require(key in self.__groups, 'Unknown source trial group')
        return key

    def group_cases(self, key):
        """Return fresh six-field metadata dictionaries, sorted by literal region."""
        return [dict(case) for case in self.__groups[self._key(key)]]

    def observations(self, asset_id, source_trial_row, *, view):
        """Return all current-trial regions in the selected exact access view."""
        _require(type(view) is str and view in ('timing', 'timing_history'), 'Unknown observation view')
        key = self._key((asset_id, source_trial_row))
        result = []
        for case in self.__groups[key]:
            observation = {'case': dict(case), 'timing': dict(self.__timing[key])}
            if view == 'timing_history':
                projection = self.__history_projection(case['case_id'], released_case_id=case['case_id'])
                _require(type(projection) is dict and set(projection) == {'case', 'history_rates'},
                         'Required current-trial history projection is absent or malformed')
                projected_case = projection['case']
                _require(type(projected_case) is dict and set(projected_case) == set(VISIBLE_FIELDS)
                         and all(type(projected_case[field]) is type(case[field])
                                 and projected_case[field] == case[field] for field in VISIBLE_FIELDS),
                         'History projection does not match the exact released case')
                rates = projection['history_rates']
                _require(type(rates) is list and len(rates) == 100
                         and all(type(rate) is float and math.isfinite(rate) and rate >= 0 for rate in rates),
                         'Required history must contain exactly 100 finite nonnegative codec float rates')
                observation['history_rates'] = list(rates)
            result.append(observation)
        return result

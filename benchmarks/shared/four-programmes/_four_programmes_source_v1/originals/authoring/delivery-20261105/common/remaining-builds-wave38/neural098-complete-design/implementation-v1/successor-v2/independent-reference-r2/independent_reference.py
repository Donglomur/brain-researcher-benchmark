"""Independent NEURAL-098 R2 pipeline, authored from written public contracts.

Import is standard-library only. The operator must qualify and authorize the entire
native runtime BEFORE calling derive. This module is not a runtime authorizer.
No estimator callback is accepted: derive calls sklearn LogisticRegression itself.
Pipeline independence does not provide an independent liblinear numerical solver.
"""
from collections import Counter
from itertools import product
import math
import hashlib
import warnings

PARTICIPANTS = (
    'SA102', 'SA103', 'SA104', 'SA111', 'SA114', 'SA118', 'SA121', 'SA123',
    'SA125', 'SA132', 'SA133', 'SA134', 'SA136', 'SA138', 'SA139', 'SA140',
    'SA144', 'SA145', 'SA146', 'SA147', 'SA148', 'SA150', 'SA151', 'SA154',
    'SA158', 'SA163', 'SA166', 'SA167', 'SA169', 'SA170', 'SA173', 'SA174', 'SA176',
)
WINDOWS = ('pre', 'onset', 'middle', 'late', 'post')
DURATIONS = (500, 1000, 1500)
RELEVANCE = ('Irrelevant', 'Relevant non-target')
ORIENTATIONS = ('Center', 'Left', 'Right')
CONTRAST_NAMES = ('middle_duration_interaction', 'late_duration_interaction',
                  'long_late_minus_onset', 'long_post_minus_late')
ROW_FIELDS = frozenset(('participant', 'trial_id', 'stim_trigger', 'category',
                        'duration_ms', 'relevance', 'orientation'))
# Explicit constructor ABI for sklearn 1.6.1. Qualification must additionally pin
# NumPy, SciPy, the sklearn wheel/liblinear, interpreter and transitive runtime.
ESTIMATOR_PARAMETERS = {
    'penalty': 'l2', 'dual': False, 'tol': 1e-8, 'C': 1.0,
    'fit_intercept': True, 'intercept_scaling': 1, 'class_weight': None,
    'random_state': 98098, 'solver': 'liblinear', 'max_iter': 2000,
    'multi_class': 'deprecated', 'verbose': 0, 'warm_start': False,
    'n_jobs': None, 'l1_ratio': None,
}


class ReferenceUnavailable(ValueError):
    """No partial report is valid; preserve fit_records on failed construction."""
    def __init__(self, reason, fit_records=()):
        super().__init__(reason)
        self.fit_records = [dict(record) for record in fit_records]


def _roster(participants):
    result = tuple(participants)
    if (not result or any(type(p) is not str or not p for p in result)
            or len(set(result)) != len(result)):
        raise ValueError('participant roster must contain distinct nonempty strings')
    return result


def identity_half(row):
    trigger = row['stim_trigger']
    if type(trigger) is not int or not 1 <= trigger <= 40:
        raise ValueError('stim_trigger must be an integer in 1..40')
    return ((trigger - 1) % 20) % 2


def available_windows(duration_ms):
    if type(duration_ms) is not int or duration_ms not in DURATIONS:
        raise ValueError('unknown duration')
    return WINDOWS[:{500: 3, 1000: 4, 1500: 5}[duration_ms]]


def mappings(duration_ms):
    available = available_windows(duration_ms)
    return tuple((w, w) for w in available) + tuple(
        ('onset', w) for w in available if w != 'onset')


def support_keys(participants):
    """For tiny controls any roster is allowed; derive requires all fixed 33."""
    return frozenset(product(_roster(participants), (0, 1), (0, 1), DURATIONS,
                             RELEVANCE, ORIENTATIONS))


def check_support(rows, participants):
    people = _roster(participants)
    expected = support_keys(people)
    if not 1 <= len(rows) <= 100000:
        raise ValueError('row count is outside 1..100000')
    counts = Counter()
    trial_ids = set()
    for row in rows:
        if type(row) is not dict or set(row) != ROW_FIELDS:
            raise ValueError('row fields do not equal the written packet schema')
        if row['participant'] not in people:
            raise ValueError('row participant is not in selected roster')
        trial = row['trial_id']
        if type(trial) is not str or not 1 <= len(trial) <= 100:
            raise ValueError('trial_id must be a 1..100 character string')
        trial_key = (row['participant'], trial)
        if trial_key in trial_ids:
            raise ValueError('duplicate participant/trial_id')
        trial_ids.add(trial_key)
        half = identity_half(row)
        category = row['category']
        if type(category) is not int or category not in (0, 1):
            raise ValueError('category must be integer zero or one')
        if category != int(row['stim_trigger'] > 20):
            raise ValueError('category disagrees with identity')
        available_windows(row['duration_ms'])
        if row['relevance'] not in RELEVANCE or row['orientation'] not in ORIENTATIONS:
            raise ValueError('unknown relevance or orientation')
        counts[(row['participant'], half, category, row['duration_ms'],
                row['relevance'], row['orientation'])] += 1
    if set(counts) != expected:
        raise ValueError('complete participant/half/category/duration/relevance/orientation support required')
    return counts


def split_indices(rows, held_participant, query_half):
    if type(query_half) is not int or query_half not in (0, 1):
        raise ValueError('query_half must be zero or one')
    training, query = [], []
    for index, row in enumerate(rows):
        half = identity_half(row)
        if row['participant'] == held_participant:
            if half == query_half:
                query.append(index)
        elif row['duration_ms'] == 1500 and half != query_half:
            training.append(index)
    if not training or not query:
        raise ValueError('empty training or query split')
    return training, query


def index_roster_sha256(indices):
    """SHA256 of ordered decimal indices, each followed by one LF byte."""
    digest = hashlib.sha256()
    for index in indices:
        if type(index) is not int or index < 0:
            raise ValueError('roster index must be a nonnegative integer')
        digest.update((str(index) + '\n').encode('ascii'))
    return digest.hexdigest()


def training_weights(rows, indices):
    """Mass N/G in each participant/category/relevance/orientation group."""
    if not indices or len(set(indices)) != len(indices):
        raise ValueError('training indices must be nonempty and unique')
    groups = [(rows[i]['participant'], rows[i]['category'], rows[i]['relevance'],
               rows[i]['orientation']) for i in indices]
    counts = Counter(groups)
    size, group_count = len(groups), len(counts)
    return [size / (group_count * counts[group]) for group in groups], counts


def training_moments(vectors):
    """Unweighted population moments; this same helper is used by derive."""
    count = len(vectors)
    if count == 0:
        raise ValueError('empty training matrix')
    width = len(vectors[0])
    if width == 0:
        raise ValueError('empty feature vector')
    for vector in vectors:
        if len(vector) != width or any(not math.isfinite(float(x)) for x in vector):
            raise ValueError('training matrix must be rectangular and finite')
    means, scales = [], []
    for column in range(width):
        mean = math.fsum(float(vector[column]) for vector in vectors) / count
        variance = math.fsum((float(vector[column]) - mean) ** 2
                             for vector in vectors) / count
        scale = math.sqrt(variance)
        if not math.isfinite(mean) or not math.isfinite(scale):
            raise ValueError('nonfinite training moment')
        means.append(mean)
        scales.append(scale if scale else 1.0)
    return means, scales


def cell_keys():
    return tuple(f'{r}|{d}|{a}>{b}' for r in RELEVANCE for d in DURATIONS
                 for a, b in mappings(d))


def contrasts(cells):
    if set(cells) != set(cell_keys()):
        raise ValueError('exactly all 42 accuracy cells are required')
    if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
           for x in cells.values()):
        raise ValueError('accuracy must be finite in [0,1]')
    result = {}
    for relevance, mode in product(RELEVANCE, ('diagonal', 'onset_transfer')):
        def accuracy(duration, window):
            source = window if mode == 'diagonal' else 'onset'
            return cells[f'{relevance}|{duration}|{source}>{window}']
        values = (
            (accuracy(1500, 'middle') - accuracy(500, 'middle'))
            - (accuracy(1500, 'onset') - accuracy(500, 'onset')),
            (accuracy(1500, 'late') - accuracy(1000, 'late'))
            - (accuracy(1500, 'onset') - accuracy(1000, 'onset')),
            accuracy(1500, 'late') - accuracy(1500, 'onset'),
            accuracy(1500, 'post') - accuracy(1500, 'late'),
        )
        result.update({f'{relevance}|{mode}|{name}': value
                       for name, value in zip(CONTRAST_NAMES, values)})
    for mode, name in product(('diagonal', 'onset_transfer'), CONTRAST_NAMES):
        result[f'relevance_modulation|{mode}|{name}'] = (
            result[f'Relevant non-target|{mode}|{name}']
            - result[f'Irrelevant|{mode}|{name}'])
    return result


def object_decision(probabilities):
    if len(probabilities) != 2:
        raise ValueError('complete two-class probabilities are required')
    p0, p1 = probabilities
    if (any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
            for p in (p0, p1)) or abs((p0 + p1) - 1.0) > 1e-12):
        raise ValueError('probabilities must be finite, bounded and normalized')
    return int(p1 >= 0.5)


class PredictionAccumulator:
    """Bounded sufficient counts plus one nine-bit completeness mask per row.

    Both image halves contribute trials to the same six recall groups. There is
    no unrequested equal-half average. Every admissible row/mapping is required
    once, including incorrect predictions and negative resulting contrasts.
    """
    def __init__(self, rows, participants):
        self.participants = _roster(participants)
        check_support(rows, self.participants)
        self.rows = rows
        self.seen = [0] * len(rows)
        self.bits = {mapping: 1 << i for i, mapping in enumerate(mappings(1500))}
        self.required = {d: sum(self.bits[m] for m in mappings(d)) for d in DURATIONS}
        self.groups = {}
        self.prediction_count = 0

    def add(self, row_index, training_window, query_window, probabilities):
        if type(row_index) is not int or not 0 <= row_index < len(self.rows):
            raise ValueError('prediction row index outside selected packet')
        row = self.rows[row_index]
        mapping = (training_window, query_window)
        if mapping not in mappings(row['duration_ms']):
            raise ValueError('unavailable or undeclared mapping')
        bit = self.bits[mapping]
        if self.seen[row_index] & bit:
            raise ValueError('duplicate row/mapping prediction')
        prediction = object_decision(probabilities)
        self.seen[row_index] |= bit
        cell = f"{row['relevance']}|{row['duration_ms']}|{training_window}>{query_window}"
        key = (row['participant'], cell, row['category'], row['orientation'])
        correct, count = self.groups.get(key, (0, 0))
        self.groups[key] = (correct + int(prediction == row['category']), count + 1)
        self.prediction_count += 1

    def finish(self):
        if any(mask != self.required[row['duration_ms']]
               for mask, row in zip(self.seen, self.rows)):
            raise ValueError('missing one or more required row/mapping predictions')
        participants = {}
        for person in self.participants:
            cells = {}
            for cell in cell_keys():
                recalls = []
                for category, orientation in product((0, 1), ORIENTATIONS):
                    correct, count = self.groups[(person, cell, category, orientation)]
                    recalls.append(correct / count)
                cells[cell] = math.fsum(recalls) / 6
            participants[person] = {'cells': cells, 'contrasts': contrasts(cells)}
        return {'schema': 'neural098-analysis-v1', 'participants': participants}


def aggregate_cells(rows, predictions, participants):
    """predictions iterable: (row_index, training_window, query_window, [p0,p1])."""
    accumulator = PredictionAccumulator(rows, participants)
    for record in predictions:
        accumulator.add(*record)
    return accumulator.finish()


def derive(features, rows, participants):
    """Future operator-only complete 330-fit scientific producer.

    Call only after separate runtime/source/input authority has been selected and
    qualified by the owner. The build controls never call this function. Returned
    report is ordinary written submission schema; fit_records is separate audit
    evidence. On fitting/aggregation failure, ReferenceUnavailable carries all
    completed and attempted fit records, and no report is returned.
    """
    people = _roster(participants)
    if len(people) != 33 or set(people) != set(PARTICIPANTS):
        raise ReferenceUnavailable('the exact fixed 33-person cohort is required')
    try:
        check_support(rows, people)
    except (ValueError, TypeError, KeyError) as error:
        raise ReferenceUnavailable(str(error)) from error
    # Deliberately delayed native imports. An import is not a qualification check.
    import numpy as np
    import sklearn
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    if sklearn.__version__ != '1.6.1':
        raise ReferenceUnavailable('qualified sklearn 1.6.1 ABI required')
    if (not isinstance(features, np.ndarray) or features.shape != (len(rows), 5, 6)
            or features.dtype.str != '<f8' or not features.flags.c_contiguous):
        raise ReferenceUnavailable('features must be C-order little-endian float64 (N,5,6)')
    for index, row in enumerate(rows):
        available = len(available_windows(row['duration_ms']))
        if not np.isfinite(features[index, :available, :]).all():
            raise ReferenceUnavailable('required features must be finite')
        if not np.isnan(features[index, available:, :]).all():
            raise ReferenceUnavailable('all unavailable features must be structural NaN')
    accumulator = PredictionAccumulator(rows, people)
    fit_records = []
    try:
        for person, half in product(people, (0, 1)):
            training, query = split_indices(rows, person, half)
            training_hash = index_roster_sha256(training)
            query_hash = index_roster_sha256(query)
            weights, group_counts = training_weights(rows, training)
            expected_groups = set(product(tuple(p for p in people if p != person),
                                          (0, 1), RELEVANCE, ORIENTATIONS))
            if set(group_counts) != expected_groups or len(group_counts) != 384:
                raise ValueError('each fold must contain exactly 384 training groups')
            labels = np.asarray([rows[i]['category'] for i in training], dtype=np.int64)
            for window_index, training_window in enumerate(WINDOWS):
                record = {'participant': person, 'query_half': half,
                          'training_window': training_window, 'status': 'started',
                          'training_rows': len(training), 'query_rows': len(query),
                          'training_indices_sha256': training_hash,
                          'query_indices_sha256': query_hash,
                          'training_groups': len(group_counts), 'prediction_count': 0}
                fit_records.append(record)
                matrix = features[training, window_index, :]
                means, scales = training_moments(matrix)
                standardized = (matrix - np.asarray(means)) / np.asarray(scales)
                if not np.isfinite(standardized).all():
                    raise ValueError('nonfinite standardized training features')
                estimator = LogisticRegression(**ESTIMATOR_PARAMETERS)
                with warnings.catch_warnings(record=True) as observed_warnings:
                    warnings.simplefilter('always', ConvergenceWarning)
                    estimator.fit(standardized, labels, sample_weight=np.asarray(weights))
                record['warnings'] = [str(w.message) for w in observed_warnings]
                record['n_iter'] = [int(n) for n in np.asarray(estimator.n_iter_).ravel()]
                if (not record['n_iter'] or any(n >= 2000 for n in record['n_iter'])
                        or any(issubclass(w.category, ConvergenceWarning) for w in observed_warnings)):
                    raise ValueError('a convergence warning or reached iteration limit invalidates R2')
                if [int(c) for c in estimator.classes_] != [0, 1]:
                    raise ValueError('fitted class ordering differs from [face=0, object=1]')
                targets = WINDOWS if training_window == 'onset' else (training_window,)
                for target in targets:
                    eligible = [i for i in query if target in available_windows(rows[i]['duration_ms'])]
                    target_index = WINDOWS.index(target)
                    query_matrix = (features[eligible, target_index, :] - np.asarray(means)) / np.asarray(scales)
                    if not np.isfinite(query_matrix).all():
                        raise ValueError('nonfinite standardized query features')
                    probabilities = estimator.predict_proba(query_matrix)
                    if probabilities.shape != (len(eligible), 2):
                        raise ValueError('estimator did not produce complete two-column probabilities')
                    for row_index, pair in zip(eligible, probabilities):
                        accumulator.add(row_index, training_window, target,
                                        (float(pair[0]), float(pair[1])))
                    record['prediction_count'] += len(eligible)
                record['status'] = 'complete'
        if len(fit_records) != 330 or any(r['status'] != 'complete' for r in fit_records):
            raise ValueError('complete 330-fit roster was not produced')
        report = accumulator.finish()
    except Exception as error:
        if fit_records and fit_records[-1]['status'] == 'started':
            fit_records[-1]['status'] = 'failed'
            fit_records[-1]['failure_type'] = type(error).__name__
            fit_records[-1]['failure'] = str(error)
        raise ReferenceUnavailable(str(error), fit_records) from error
    return {'report': report, 'fit_records': fit_records,
            'prediction_count': accumulator.prediction_count,
            'estimator_parameters': dict(ESTIMATOR_PARAMETERS),
            'native_versions': {'numpy': np.__version__, 'sklearn': sklearn.__version__},
            'independence': 'independent pipeline; shared sklearn/liblinear numerical backend',
            'method_execution_authenticated': False}

"""Fixed prospective reference bridge; no arbitrary candidate method labels.

This source is captured separately from the candidate. It executes only after a
root-reviewed full dependency/input/runtime admission. The historical NB path
is deliberately unavailable without a disclosed compatible initialization.
"""
import hashlib
import importlib
import json
import random
import sys
from collections import deque
from pathlib import Path

CONFIG_SHA = '7800325597792c88a95078aa7084a0f518b1d67ca6579dac2de5dbafe90d850b'
POLICY = 'published_hyperparameters_prospective_seeds_standard_kalman20_v1'
NB_POLICY = 'glaser_res50_quadratic_training_mean_anchor_v1'
PINS = {
    'bci-decoders/src/decoders.py': (23370, 'deb15f3d491503b13018cb3119f759b8b3fd73089dc85ec1f8e732282e45b31f'),
    'bci-decoders/src/utils.py': (7736, '8c020e18bd58aeb7c1f4245f07f4dda8959f3943ef780265e2fefee481643db9'),
    'Glaser/Neural_Decoding/decoders.py': (59370, 'd7b26438101b393e91a4d09726034e01d878470c69fe234f787839809b33730f'),
}


def checked(path, size, expected):
    if path.is_symlink():
        raise ValueError('reference dependency symlink')
    with path.open('rb') as stream:
        body = stream.read(size + 1)
    if len(body) != size or hashlib.sha256(body).hexdigest() != expected:
        raise ValueError('reference dependency mismatch')
    return body


def create(case, config, seed, dataset):
    if config.get('reference_policy') != POLICY or seed != 20261107 + case['run_slot']:
        raise ValueError('fixed prospective reference policy and seed required')
    context = Path('/context')
    with (context / 'REFERENCE_CONFIG.json').open('rb') as stream:
        raw = stream.read(20032)
    if len(raw) != 20031 or hashlib.sha256(raw).hexdigest() != CONFIG_SHA:
        raise ValueError('published configuration pin')
    settings = json.loads(raw)['datasets'][case['dataset']]
    if case['method'] == 'MINT':
        raise RuntimeError('MINT uses separate mint_reference_entry.m native source route; Cycle mapping and native/raw parity remain unqualified')
    if case['method'] == 'Naive_Bayes_regression' and config.get('naive_bayes_policy') != NB_POLICY:
        raise RuntimeError('historical Naive Bayes requires disclosed compatible initialization; no test behavior is available in this packet')
    for relative, (size, pin) in PINS.items():
        if relative.startswith('Glaser/') and case['method'] != 'Naive_Bayes_regression':
            continue
        checked(context / relative, size, pin)
    sys.path.insert(0, str(context / 'bci-decoders'))
    sys.path.insert(0, str(context / 'Glaser'))
    # No dependencies imported by metadata checks or invented controls.
    import numpy as np
    import tensorflow as tf
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    bci = importlib.import_module('src.decoders')
    glaser = importlib.import_module('Neural_Decoding.decoders') if case['method'] == 'Naive_Bayes_regression' else None
    return Reference(case, dataset, settings, seed, np, tf, bci, glaser)


class Reference:
    def __init__(self, case, dataset, settings, seed, np, tf, bci, glaser):
        self.case, self.dataset, self.settings, self.seed = case, dataset, settings, seed
        self.np, self.tf, self.bci, self.glaser = np, tf, bci, glaser
        self.training = []
        self.current = None
        self.models = []

    def train_chunk(self, segment, start, neural, behavior, auxiliary, final):
        if start == 0:
            if self.current is not None:
                raise ValueError('unfinished training segment')
            self.current = {'id': segment['id'], 'neural': [], 'behavior': [], 'auxiliary': []}
        if self.current['id'] != segment['id'] or start != len(self.current['neural']):
            raise ValueError('ordered training segments')
        for field, rows in [('neural', neural), ('behavior', behavior), ('auxiliary', auxiliary)]:
            self.current[field].extend(rows)
        if final:
            self.training.append(self.current)
            self.current = None

    def fit(self):
        np = self.np
        S = [np.asarray(t['neural'], dtype=float).T for t in self.training]
        Z = [np.asarray(t['behavior'], dtype=float).T for t in self.training]
        auxiliary = [np.asarray(t['auxiliary'], dtype=float).T for t in self.training]
        method = self.case['method']
        groups = self.case['groups']
        # Exact public output dimension map is fixed by the captured panel,
        # included in the slot config by the trusted reference manifest builder.
        dims = self.dataset['output_group_dimensions']
        if method == 'Kalman_filter':
            model = self.bci.KalmanFilter(self.settings[method]['parameters'])
            model.fit(S, auxiliary)
            self.models = [(None, model, 20)]
        else:
            for ordinal, group in enumerate(groups):
                seed = self.seed + 1000 * ordinal
                random.seed(seed)
                np.random.seed(seed)
                self.tf.random.set_seed(seed)
                target = [z[dims[group], :] for z in Z]
                rule = self.settings[method][group]
                if method == 'Naive_Bayes_regression':
                    width = rule['bin_ms']
                    model = self.glaser.NaiveBayesRegression(encoding_model='quadratic', res=50)
                    spikes, targets = [], []
                    for s, z in zip(S, target):
                        for end in range(width, s.shape[1] + 1, width):
                            spikes.append(s[:, end - width:end].sum(axis=1))
                            targets.append(z[:, end - 1])
                    targets = np.asarray(targets)
                    # Original source may fail on zero rounded grid increments;
                    # preserve that failure, do not silently alter grid extent.
                    model.fit(np.asarray(spikes), targets)
                    model.prospective_training_anchor = targets.mean(axis=0)
                    self.models.append((group, model, width))
                else:
                    cls = {'Wiener_filter': self.bci.WienerFilter,
                           'feedforward': self.bci.FeedforwardNetwork, 'GRU': self.bci.GRU}[method]
                    model = cls(rule['parameters'])
                    model.fit(S, target)
                    self.models.append((group, model, rule['history_ms']))
        self.training.clear()

    def start_trial(self, trial):
        self.trial, self.seen = trial, 0
        largest = max(x[2] for x in self.models)
        self.history = deque(maxlen=largest)
        self.last = {}
        self.initialized = False
        if self.case['method'] == 'Kalman_filter':
            model = self.models[0][1]
            self.state = model.z0.copy()
            self.covariance = model.P0.copy()
            self.delay = deque()
            self.kf_held = None
        if self.case['method'] == 'Naive_Bayes_regression':
            self.nb_anchor = {group: model.prospective_training_anchor.copy() for group, model, _ in self.models}

    def history_chunk(self, start, neural):
        if start != self.seen:
            raise ValueError('exact source bin origin')
        for row in neural:
            self._advance(row)

    def _advance(self, neural):
        np = self.np
        self.history.append(neural)
        self.seen += 1
        method = self.case['method']
        if method == 'Kalman_filter':
            model = self.models[0][1]
            if self.seen % 20:
                return
            observed = np.asarray(self.history).sum(axis=0)
            # Equations S10-S14, first update starts from training-derived z0/P0.
            if self.initialized:
                self.state = model.A @ self.state
                self.covariance = model.A @ self.covariance @ model.A.T + model.Q
            gain = self.covariance @ model.C.T @ np.linalg.pinv(model.C @ self.covariance @ model.C.T + model.R)
            self.state = self.state + gain @ (observed - model.C @ self.state)
            self.covariance = self.covariance - gain @ model.C @ self.covariance
            self.initialized = True
            self.delay.append(self.state[:4].copy())
            lag = self.settings[method]['parameters']['lag'] // 20
            if len(self.delay) > lag:
                self.kf_held = self.delay.popleft()
            return
        for group, model, history_ms in self.models:
            delta = history_ms if method == 'Naive_Bayes_regression' else 20
            if self.seen < history_ms or self.seen % delta:
                continue
            window = np.asarray(list(self.history)[-history_ms:], dtype=float).T
            if method == 'Naive_Bayes_regression':
                # One-bin recurrence is source-equivalent after the explicitly
                # changed training-only initial anchor; no test target is read.
                counts = window.sum(axis=1).reshape(1, -1)
                if not np.isfinite(counts).all() or (counts < 0).any() or not (counts == np.floor(counts)).all():
                    raise ValueError('Naive Bayes requires authentic integer spike counts')
                counts = counts.astype('int64')
                answer = model.predict(counts, self.nb_anchor[group].reshape(1, 2))[0]
                self.nb_anchor[group] = answer.copy()
            else:
                # These author predictors are independent finite-window maps.
                # Call only at the original bin boundary and retain the last
                # value between boundaries. No growing-prefix recomputation.
                answer = model.predict([window])[0][:, -1]
            self.last[group] = answer

    def predict(self, index, neural):
        if self.seen != self.trial['history_samples'] + index:
            raise ValueError('source prefix continuity')
        self._advance(neural)
        if self.case['method'] == 'Kalman_filter':
            if self.kf_held is None:
                raise ValueError('insufficient real Kalman prefix')
            selection = [i for group in self.case['groups'] for i in ({'position': [0, 1], 'velocity': [2, 3]}[group])]
            return [float(self.kf_held[i]) for i in selection]
        if any(group not in self.last for group in self.case['groups']):
            raise ValueError('insufficient real decoder prefix')
        return [float(value) for group in self.case['groups'] for value in self.last[group]]

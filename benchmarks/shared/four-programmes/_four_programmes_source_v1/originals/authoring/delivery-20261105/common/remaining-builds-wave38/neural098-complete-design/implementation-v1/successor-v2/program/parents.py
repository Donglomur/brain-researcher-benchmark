"""Exact legacy function adapters. No parent main or native import at load."""
import ast
import math
from pathlib import Path
from .custody import capture, encode, need, parse, pin, read_pin


class Parents:
    def __init__(self, root, bindings, budget):
        self.root, self.bindings, self.budget = Path(root), bindings, budget
        self.bodies = {}
        for role, d in bindings['roles'].items():
            self.bodies[role] = read_pin(root, d, 1_048_576, budget)
        self.people = parse(self.bodies['cohort'])['participants']
        need(len(self.people) == 33 and len(set(self.people)) == 33, 'exact full33 source cohort')
        self.protocol = {'__name__': '_neural098_pinned_protocol'}
        exec(compile(self.bodies['protocol'], '<exact pinned protocol>', 'exec'), self.protocol)
        self.reference = dict(self.protocol)
        self.reference.update({'__name__': '_neural098_pinned_reference'})
        self.extract('reference', {'validate_features', 'predict_all', 'aggregate'}, self.reference)
        self.scorer = dict(self.protocol, math=math, __name__='_neural098_pinned_score')
        self.extract('score', {'grade'}, self.scorer)
        self.io = {'__name__': '_neural098_pinned_feature_reader'}
        import io
        self.io['io'] = io
        def metered_capture(path, limit, expected=None):
            raw, actual = capture(path, limit, budget)
            need(expected is None or actual['sha256'] == expected, 'legacy captured SHA256')
            return raw, actual['sha256']
        self.io['capture'] = metered_capture
        self.extract('io_utils', {'read_features'}, self.io)
        need(len(self.protocol['CELL_KEYS']) == 42 and len(self.protocol['CONTRAST_KEYS']) == 24,
             'full scientific output domain')

    def extract(self, role, names, namespace):
        tree = ast.parse(self.bodies[role])
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        need({n.name for n in nodes} == names and len(nodes) == len(names), 'exact function closure')
        # Original nodes compile without edits. Only explicit module-global
        # dependencies are supplied; top-level sys.path mutation/main is absent.
        selected = ast.Module(body=nodes, type_ignores=[])
        exec(compile(selected, '<exact pinned ' + role + ' functions>', 'exec'), namespace)

    def packet(self, packet_pin, *, native_qualified):
        need(native_qualified is True, 'independently qualified native analysis before feature access')
        raw = read_pin(self.root, packet_pin, 4_000_000, self.budget)
        doc = parse(raw)
        self.protocol['validate_packet'](doc, self.people)
        path = Path(packet_pin['path'])
        if not path.is_absolute():
            path = self.root / path
        features = self.io['read_features'](path.with_name('features.npy'), doc['features_sha256'], len(doc['rows']))
        self.reference['validate_features'](features, doc['rows'])
        return doc, features

    def reference_r1(self, packet, features):
        """Actual frozen source and actual fixed library, no configurable model callback."""
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        trace = []
        schedule = [(person, half, window) for person in self.people for half in (0, 1)
                    for window in self.protocol['WINDOWS']]
        def native_factory():
            need(len(trace) < 330, 'no extra reference fit')
            person, half, window = schedule[len(trace)]
            train, query = self.protocol['split'](packet['rows'], person, half)
            record = {'held_participant': person, 'query_half': half, 'train_window': window,
                      'training_rows': {'count': len(train), **pin(encode(train))},
                      'query_rows': {'count': len(query), **pin(encode(query))}, 'fit_completed': False}
            trace.append(record)
            class AuditedFixedEstimator:
                def __init__(self):
                    self.native = LogisticRegression(C=1., solver='liblinear', tol=1e-8,
                                                     max_iter=2000, random_state=98098)
                def fit(self, x, y, sample_weight):
                    need(len(x) == len(y) == len(sample_weight) == len(train), 'complete selected training rows')
                    record['scaled_training_features'] = pin(np.asarray(x, dtype='<f8').tobytes())
                    record['training_labels'] = pin(np.asarray(y, dtype='<i8').tobytes())
                    record['training_weights'] = pin(np.asarray(sample_weight, dtype='<f8').tobytes())
                    self.native.fit(x, y, sample_weight=sample_weight)
                    record['iterations'] = [int(v) for v in self.native.n_iter_]
                    record['fit_completed'] = True
                    self.classes_, self.n_iter_ = self.native.classes_, self.native.n_iter_
                    return self
                def predict_proba(self, x):
                    return self.native.predict_proba(x)
            return AuditedFixedEstimator()
        try:
            probabilities = self.reference['predict_all'](features, packet['rows'], self.people,
                                                          model_factory=native_factory)
            report = self.reference['aggregate'](probabilities, packet['rows'], self.people)
            need(len(trace) == 330 and all(r['fit_completed'] and max(r['iterations']) < 2000 for r in trace),
                 'complete330 converged reference fits')
            self.protocol['validate_report'](report, self.people)
            return {'report': report, 'fit_records': trace, 'pipeline': 'R1_exact_parent',
                    'shared_native_solver': 'qualified sklearn liblinear', 'scientific_qualification': False}
        except BaseException as error:
            error.completed_fit_records = trace
            raise

    def score(self, candidate, reference_pin):
        invoked = []
        def protected_loader():
            invoked.append(True)
            return parse(read_pin(self.root, reference_pin, 4_000_000, self.budget))
        try:
            result = self.scorer['grade'](candidate, self.people, protected_loader)
            result['reference_invoked'] = bool(invoked)
            return result
        except BaseException as error:
            error.reference_invoked = bool(invoked)
            raise

    def unchanged(self):
        for role, d in self.bindings['roles'].items():
            need(read_pin(self.root, d, 1_048_576, self.budget) == self.bodies[role], 'parent source drift')

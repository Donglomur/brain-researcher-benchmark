"""Full ALM scientific caller composition, inactive pending genuine deployment.

This object owns its source call sequence and retained raw failure. It is NOT an
issuer of native isolation, source provenance, model execution or target rights.
Only a future admitted host may call these private APIs with original operands.
No external programme is launched here; central run/score remain unavailable.
"""
from pathlib import Path
import hashlib
from .contracts import require, TASKS, readiness
from . import programme, experiment, storage, grading

ARMS = ('frozen_program', 'case_adaptive')
TRACKS = ('held_block', 'held_mouse')


class Operator:
    def __init__(self, task):
        require(task in TASKS, 'fixed ALM task')
        self.task = task
        self.first = None
        self.secondary = []
        self.events = []
        self.state = 'new'
        self.effects = []
        self._packets = []
        self._publications = []
        self._truth = None
        self._cap = None
        self._scored = False
        self._case_roots = ()

    def _call(self, phase, function, *args):
        if self.first is not None:
            raise self.first
        self.events.append((phase, 'started'))
        try:
            result = function(*args)
        except BaseException as error:
            self.first = error
            self.state = 'failed'
            self.events.append((phase, 'failed'))
            raise
        self.events.append((phase, 'returned'))
        return result

    def _write(self, path, value):
        row = {'path': str(path), 'attempted': True, 'returned': False}
        self.effects.append(row)
        pin = self._call('publish', storage.write_new, path, value, self._cap)
        row.update(returned=True, pin=pin)
        return pin

    def _begin(self, task, cap):
        require(self.task == task and self.state == 'new', 'single original task preparation')
        require(type(cap) is int and cap > 0, 'positive original artifact cap')
        self._cap = cap
        self.state = 'preparing'

    def _root_geometry(self, public_roots, private_roots, private_paths):
        public = [Path(p).resolve() for p in public_roots]
        private = [Path(p).resolve() for p in private_roots]
        roots = public + private
        require(len(set(roots)) == len(roots), 'distinct case roots')
        require(all(a not in b.parents and b not in a.parents
                    for i, a in enumerate(roots) for b in roots[i+1:]), 'isolated root geometry')
        require(all(any(r in Path(p).resolve().parents for r in private)
                    for p in private_paths), 'truth and preparation receipt stay private')
        self._case_roots = tuple(roots)

    def _publish(self, packets, public_root, private_root):
        # Original publisher owns its file operations and closes before return.
        # Distinct full case sets have separately provisioned roots. No mkdir or
        # mount here pretends to establish a protected provider boundary.
        publication = self._call('publish_cases', experiment.publish_cases,
                                 packets, public_root, private_root, self._cap)
        require(len(publication['cases']) == len(packets['cases']), 'publication inverse')
        self._packets.extend(packets['cases'])
        for case, row in zip(packets['cases'], publication['cases']):
            require(row['case_id'] == case['public']['case_id'], 'same published case')
            self._publications.append({'public_path': Path(public_root)/(row['case_id']+'.json'),
                'private_path': Path(private_root)/(row['case_id']+'.json'),
                'private_pin': row['private']})
        return publication

    def prepare_prediction(self, root, manifest, mappings, budget, protocol,
                           feature_kind, private_key, limits, public_roots,
                           private_roots, receipt_path, artifact_cap):
        def operation():
            self._begin('NEURAL-043', artifact_cap)
            require(set(public_roots) == set(private_roots) == set(TRACKS), 'both complete prediction tracks')
            require(feature_kind in ('neural', 'history_time', 'neural_history_time'), 'original feature family')
            self._root_geometry(public_roots.values(), private_roots.values(), [receipt_path])
            records, population = self._call('load_population', programme.load_population,
                                            root, manifest, mappings, budget)
            constructions = {}; publications = {}
            for track in TRACKS:
                construction = self._call('construct_'+track, programme.construct_prediction,
                                           records, protocol, track)
                packets = self._call('prepare_'+track, experiment.prepare_prediction_cases,
                                     construction, feature_kind, private_key, limits)
                publications[track] = self._publish(packets, public_roots[track], private_roots[track])
                constructions[track] = construction
            # All exclusions/references remain in the protected original return;
            # this is not a model input view or a native completion receipt.
            result = {'task': self.task, 'population': population,
                'constructions': constructions, 'publications': publications,
                'source_only': True, 'provider_verified': False}
            self._write(receipt_path, {'task': self.task, 'tracks': list(TRACKS),
                'publications': publications, 'source_only': True, 'provider_verified': False})
            self.state = 'prepared'
            return result
        return self._call('prepare_prediction', operation)

    def prepare_perturbation(self, root, manifest, mappings, budget, protocol,
                             private_key, limits, public_root, private_root,
                             truth_path, source_digest, receipt_path, artifact_cap):
        def operation():
            self._begin('NEURAL-044', artifact_cap)
            self._root_geometry([public_root], [private_root], [truth_path, receipt_path])
            records, population = self._call('load_population', programme.load_population,
                                            root, manifest, mappings, budget)
            construction = self._call('construct_perturbation', programme.construct_perturbation,
                                       records, protocol)
            packets = self._call('prepare_response_cases', experiment.prepare_response_cases,
                                 construction, private_key, limits)
            publication = self._publish(packets, public_root, private_root)
            truth = self._call('investigation_truth', experiment.investigation_truth,
                               construction, source_digest)
            pin = self._write(truth_path, truth)
            self._truth = (truth_path, pin)
            self._write(receipt_path, {'task': self.task, 'publication': publication,
                'truth_pin': pin, 'source_only': True, 'provider_verified': False})
            self.state = 'prepared'
            return {'task': self.task, 'population': population, 'construction': construction,
                'publication': publication, 'truth_pin': pin, 'source_only': True,
                'provider_verified': False}
        return self._call('prepare_perturbation', operation)

    def _commit_all(self, submissions, commits, case_ids):
        require(self.state == 'prepared' and not self._scored, 'prepared original one-shot evaluation')
        require(type(submissions) is dict and type(commits) is dict and
                set(submissions) == set(commits) == set(ARMS), 'both matched arms')
        require(case_ids and len(case_ids) == len(set(case_ids)), 'complete unique case IDs')
        for arm in ARMS:
            require(type(submissions[arm]) is dict and type(commits[arm]) is dict and
                    set(submissions[arm]) == set(commits[arm]) == set(case_ids), 'full arm/case inverse')
        # The future host's output/capture directories must be separate from all
        # query and protected case roots. A caller-supplied target pathname must
        # never become the precommit submission read. This checks geometry only;
        # immutable mounts, no-follow capture and origin authority are unissued.
        paths = [Path(table[arm][k]).resolve() for table in (submissions, commits)
                 for arm in ARMS for k in case_ids]
        require(len(paths) == len(set(paths)), 'distinct per-arm submissions and commitments')
        require(self._case_roots and all(p != root and root not in p.parents
                    for p in paths for root in self._case_roots), 'no case-root submission/commit alias')
        self._scored = True
        found = {}; pins = {}
        # No target read is reachable until every original submission in BOTH
        # arms has returned from exclusive write/fsync/readback/retirement.
        for arm in ARMS:
            found[arm] = {}; pins[arm] = {}
            for case_id in case_ids:
                value = self._call('capture_submission', storage.load_json,
                                   submissions[arm][case_id], self._cap)
                found[arm][case_id] = value
                pins[arm][case_id] = self._write(commits[arm][case_id],
                    {'task': self.task, 'arm': arm, 'case_id': case_id,
                     'submission_sha256': hashlib.sha256(storage.encode(value)).hexdigest()})
        return found, pins

    def _private(self, path, pin):
        value = self._call('protected_target', storage.load_json, path, self._cap)
        raw = storage.encode(value)
        require(pin == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
                'exact original published protected target')
        return value

    def score_predictions(self, submissions, commits):
        def operation():
            require(self.task == 'NEURAL-043', 'prediction cohort task')
            ids = [r['public']['case_id'] for r in self._packets]
            found, pins = self._commit_all(submissions, commits, ids)
            public = [r['public'] for r in self._packets]
            private = [self._private(r['private_path'], r['private_pin']) for r in self._publications]
            scores = {}
            for arm in ARMS:
                values = [found[arm][case_id] for case_id in ids]
                # Preserve original within-mouse pooling before class recall;
                # no average of block-level balanced accuracies is invented.
                scores[arm] = self._call('score_prediction_cohort', grading.score_prediction_cohort,
                                         values, public, private)
            self.state = 'scored'
            return {'task': self.task, 'scores': scores, 'commitments': pins,
                    'scientific_qualification': False, 'provider_verified': False}
        return self._call('score_predictions', operation)

    def evaluate_perturbation(self, submissions, commits, tolerances):
        def operation():
            require(self.task == 'NEURAL-044' and self._truth is not None, 'original investigation truth')
            ids = [r['public']['case_id'] for r in self._packets]
            require('investigation' not in ids, 'reserved investigation channel')
            found, pins = self._commit_all(submissions, commits, ids + ['investigation'])
            public = [r['public'] for r in self._packets]
            private = [self._private(r['private_path'], r['private_pin']) for r in self._publications]
            truth = self._private(*self._truth)
            scores = {}
            for arm in ARMS:
                scores[arm] = {'held_response': [self._call('score_responses', grading.score_responses,
                    found[arm][case_id], p, q) for case_id, p, q in zip(ids, public, private)],
                    'investigation': self._call('grade_investigation', grading.grade_investigation,
                     found[arm]['investigation'], truth, tolerances)}
            self.state = 'scored'
            return {'task': self.task, 'scores': scores, 'commitments': pins,
                    'scientific_qualification': False, 'provider_verified': False}
        return self._call('evaluate_perturbation', operation)

    def status(self):
        return {**readiness(), 'task': self.task, 'state': self.state,
                'original_failure_retained': self.first is not None,
                'effects_attempted': len(self.effects), 'physical_costs': 'UNKNOWN',
                'missing_host': ['native isolation', 'original source/mapping and target authority',
                                 'model process/capture owner', 'whole resource measurement']}

"""Operator-owned processed-summary observations; no participant code or provider."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import types
import uuid

HERE = Path(__file__).resolve().parent
VIEWS = ('history', 'prestimulus', 'all_erp')


def need(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(body):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def ordinary(path):
    path = Path(os.path.abspath(path))
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No linked path or parent')
    return path


def read(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary single-link input')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields),
             'Stable complete input')
        need(expected is None or pin(body) == expected, 'Exact input identity')
        return body
    finally:
        os.close(fd)


def publish(path, body):
    fd = os.open(ordinary(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def source():
    raw = read(HERE / 'SOURCE.json', 32768)
    manifest = decode(raw)
    need(manifest['schema'] == 'neural005_sequential_source_v1', 'Exact source identity')
    for name, expected in manifest['files'].items():
        path = Path(name)
        need(not path.is_absolute() and '..' not in path.parts, 'Repository-relative source member')
        read(HERE.parents[4] / path, 1048576, expected)
    return pin(raw)


def dependency(name, relative):
    path = HERE.parent / relative
    manifest = decode(read(HERE / 'SOURCE.json', 32768))
    expected = manifest['files'][str(path.relative_to(HERE.parents[4]))]
    return execute_source(name, path, expected)


def execute_source(name, path, expected):
    body = read(path, 1048576, expected)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def configuration():
    identity = source()
    features = dependency('neural005_observation_features', 'pinned-source-preparation-v1/features.py')
    contribution = dependency('neural005_observation_schedule', 'predictive-contribution/scientific_contribution.py')
    pins = decode(read(HERE.parent / 'pinned-source-preparation-v1/SOURCE_PINS.json', 16384))
    panel = decode(read(HERE.parent / 'registered-runtime/public/cases.json', 100000, pins['public_panel']))
    return identity, features, contribution, pins, panel


def case_key(row):
    pieces = row['case_id'].split(':')
    need(len(pieces) == 3 and pieces[0] == row['participant'], 'Matching participant/case identity')
    return int(pieces[1]), int(pieces[2])


class Study:
    """Trusted operator object. Never pass it or the complete query list to a participant."""
    def __init__(self, train, development, panel, features, schedule_validator, identity):
        self.features, self.identity = features, copy.deepcopy(identity)
        people = sorted({row['participant'] for row in panel['cases']}, key=int)
        schedule_validator({'participants': people, 'cases': panel['cases']})
        need(set(train) == {'rows', 'feature_names', 'participant_ids', 'cv_fold_by_id'}
             and train['feature_names'] == {k: list(v) for k, v in features.ARMS.items()}, 'Exact historical training schema')
        need(len(train['rows']) == 3254 and len(train['participant_ids']) == 26
             and len(set(train['participant_ids'])) == 26
             and not set(train['participant_ids']) & set(people), 'Complete disjoint original people and training support')
        need(set(train['cv_fold_by_id']) == set(train['participant_ids'])
             and all(type(v) is int and v in (0, 1, 2) for v in train['cv_fold_by_id'].values()), 'Original training-only folds')
        seen = set()
        for row in train['rows']:
            need(set(row) == {'participant', 'case_id', 'target', 'features'}
                 and row['participant'] in train['participant_ids'] and row['case_id'] not in seen,
                 'Unique complete training row')
            episode, current = case_key(row)
            need(1 <= episode <= 36 and 1 <= current <= 4 and type(row['target']) is int and row['target'] in (0, 1),
                 'Original training identity and binary supervision')
            need(type(row['features']) is list and len(row['features']) == 57
                 and all(v is None or (type(v) in (int, float) and math.isfinite(v)) for v in row['features'])
                 and all(v is not None for v in row['features'][50:]), 'Full finite seven-ERP-complete training support')
            seen.add(row['case_id'])
        need({r['participant'] for r in train['rows']} == set(train['participant_ids']), 'Every training person contributes')
        need(set(development) == {'cases', 'participant_ids', 'coverage'} and len(development['cases']) == 816
             and set(development['participant_ids']) == set(people), 'Complete original development schema')
        expected = {(r['participant'], r['case_id']) for r in panel['cases']}
        self.queries = {p: [] for p in people}
        seen = set()
        for pair in development['cases']:
            need(set(pair) == {'request', 'target', 'source_current', 'source_target'}, 'Exact protected query record')
            request = pair['request']
            need(set(request) == {'participant', 'case_id', 'prefix'}, 'Exact current-prefix record')
            key = request['participant'], request['case_id']
            need(key in expected and key not in seen, 'Every original query exactly once')
            need(type(pair['target']) is int and pair['target'] in (0, 1), 'Protected target coding')
            episode, current = case_key(request)
            features.validate_prefix(request['prefix'])
            need(len(request['prefix']) == current and request['prefix'][-1]['episode'] == episode, 'Case matches prefix')
            # Validate common support before any arm can mask an ERP column.
            features.vector(request['prefix'], 'all_erp')
            self.queries[request['participant']].append(copy.deepcopy(request))
            seen.add(key)
        need(seen == expected, 'Complete fixed 816-case support')
        for person, rows in self.queries.items():
            rows.sort(key=case_key)
            clocks = [r['prefix'][-1]['trial_global'] for r in rows]
            need(clocks == sorted(set(clocks)), 'Original chronological person schedule')
            previous = None
            for request in rows:
                if previous and previous['prefix'][-1]['episode'] == request['prefix'][-1]['episode']:
                    n = len(previous['prefix'])
                    need(previous['prefix'] == request['prefix'][:n], 'Later lawful prefix preserves earlier observations')
                previous = request
        self.train = copy.deepcopy(train)
        self.people = people

    def training(self, view):
        need(view in VIEWS, 'Exact feature view')
        names = self.features.ARMS[view]
        indexes = [self.features.ARMS['all_erp'].index(name) for name in names]
        return {'feature_names': list(names), 'participant_ids': list(self.train['participant_ids']),
                'cv_fold_by_id': dict(self.train['cv_fold_by_id']),
                'rows': [{'participant': r['participant'], 'case_id': r['case_id'], 'target': r['target'],
                          'features': [r['features'][i] for i in indexes]} for r in self.train['rows']]}


def load_study(train_path, development_path):
    identity, features, contribution, pins, panel = configuration()
    expected = pins['expected_numerical_outputs']
    # Operator-only decode includes protected target-containing source records.
    train = decode(read(train_path, 2000000, expected['train.json']))
    development = decode(read(development_path, 1000000, expected['development_private.json']))
    identity = {'source': identity, 'inputs': expected, 'public_panel': pins['public_panel']}
    return Study(train, development, panel, features, contribution.schedule_counts, identity)


class Session:
    """One person/view broker state; external participant isolation is separate."""
    def __init__(self, study, person, view, method, directory):
        need(person in study.people and view in VIEWS, 'Declared person and feature view')
        need(type(method) is bytes and 0 < len(method) <= 32768, 'Bounded predeclared method document')
        description = decode(method)
        need(type(description) is dict and set(description) == {'schema_version', 'method_id', 'description', 'training_policy', 'limitations'}
             and type(description['schema_version']) is int and description['schema_version'] == 1
             and all(type(description[k]) is str and 0 < len(description[k]) <= 4096
                     for k in ('method_id', 'description', 'training_policy', 'limitations')), 'Exact method declaration')
        directory = ordinary(directory)
        need(not directory.exists() and directory.parent.is_dir(), 'Fresh operator session directory')
        directory.mkdir(mode=0o700)
        self.study, self.person, self.view, self.directory = study, person, view, directory
        self.index, self.pending, self.failed, self.closed = 0, None, False, False
        self.rows, self.nonces = [], set()
        self.method = publish(directory / 'METHOD.json', method)
        self.session_id = uuid.uuid4().hex
        self.training = study.training(view)
        self.start = {'schema': 'neural005_observation_session_v1', 'session_id': self.session_id,
                      'participant': person, 'view': view, 'identity': study.identity, 'method': self.method,
                      'training': pin(encode(self.training)), 'expected_cases': len(study.queries[person])}
        self.previous = publish(directory / 'START.json', encode(self.start))
        self.journal = (directory / 'commits.jsonl').open('xb')
        self.journal_bytes = 0

    def training_message(self):
        need(not self.failed and not self.closed and self.index == 0 and self.pending is None,
             'Training is available only before this session opens queries')
        return {'schema': 'neural005_training_observation_v1', 'session_id': self.session_id,
                'participant': self.person, 'view': self.view, 'training': copy.deepcopy(self.training)}

    def offer(self):
        need(not self.failed and not self.closed and self.pending is None, 'Commit the pending response before next reveal')
        need(self.index < len(self.study.queries[self.person]), 'No remaining query')
        request = self.study.queries[self.person][self.index]
        nonce = uuid.uuid4().hex
        need(nonce not in self.nonces, 'Fresh response nonce')
        self.nonces.add(nonce)
        self.pending = {'schema': 'neural005_numeric_observation_v1', 'session_id': self.session_id,
                        'nonce': nonce, 'participant': self.person, 'view': self.view,
                        'case_id': request['case_id'], 'index': self.index,
                        'feature_names': list(self.study.features.ARMS[self.view]),
                        'features': self.study.features.vector(request['prefix'], self.view)}
        return copy.deepcopy(self.pending)

    def commit(self, body):
        need(not self.failed and not self.closed and self.pending is not None, 'Exactly one pending response')
        try:
            need(type(body) is bytes and 0 < len(body) <= 4096, 'Bounded typed answer')
            answer = decode(body)
            need(type(answer) is dict and set(answer) == {'session_id', 'nonce', 'participant', 'view', 'case_id', 'probability'},
                 'Exact probability response fields')
            need(all(type(answer[k]) is str and answer[k] == self.pending[k]
                     for k in ('session_id', 'nonce', 'participant', 'view', 'case_id')), 'Current response identity')
            probability = answer['probability']
            need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
                 'Finite probability in [0,1], not boolean')
            record = {'index': self.index, 'observation': pin(encode(self.pending)), 'answer': answer,
                      'previous': self.previous}
            raw = encode(record)
            need(self.journal_bytes + len(raw) <= 262144, 'Bounded complete session journal')
            self.journal.write(raw)
            self.journal.flush()
            os.fsync(self.journal.fileno())
            # Only a successful durable commit advances the release state.
            self.journal_bytes += len(raw)
            self.previous = pin(raw)
            self.rows.append({k: answer[k] for k in ('participant', 'case_id', 'probability')})
            self.index += 1
            self.pending = None
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        need(not self.failed and not self.closed and self.pending is None
             and self.index == len(self.study.queries[self.person]), 'Complete committed person before closure')
        self.journal.close()
        (self.directory / 'commits.jsonl').chmod(0o400)
        output = publish(self.directory / 'probabilities.json', encode({'schema_version': 1, 'probabilities': self.rows}))
        report = {'schema': 'neural005_session_complete_v1', 'start': pin(read(self.directory / 'START.json', 16384)),
                  'journal': pin(read(self.directory / 'commits.jsonl', 262144)), 'last_commit': self.previous,
                  'probabilities': output, 'committed': self.index, 'software_release_order_complete': True,
                  'external_participant_reset_verified': False, 'no_tools_enforced': False,
                  'model_or_provider_calls_by_broker': 0, 'scientific_qualification': False}
        publish(self.directory / 'COMPLETE.json', encode(report))
        self.closed = True
        return report

    def abort(self):
        self.failed = True
        if not self.journal.closed:
            self.journal.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('train', 'development-private', 'method', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--participant', required=True)
    parser.add_argument('--view', choices=VIEWS, required=True)
    args = parser.parse_args(argv)
    study = load_study(args.train, args.development_private)
    session = Session(study, args.participant, args.view, read(args.method, 32768), args.output)
    try:
        sys.stdout.buffer.write(encode(session.training_message()))
        sys.stdout.buffer.flush()
        while session.index < len(study.queries[args.participant]):
            sys.stdout.buffer.write(encode(session.offer()))
            sys.stdout.buffer.flush()
            body = sys.stdin.buffer.readline(4097)
            need(body.endswith(b'\n'), 'One complete response line required')
            session.commit(body)
        session.finish()
        # Do not send labels, grade, paths or operator-only receipts to participant.
        sys.stdout.buffer.write(encode({'status': 'complete', 'session_id': session.session_id}))
        sys.stdout.buffer.flush()
    except BaseException:
        session.abort()
        raise


if __name__ == '__main__':
    main()

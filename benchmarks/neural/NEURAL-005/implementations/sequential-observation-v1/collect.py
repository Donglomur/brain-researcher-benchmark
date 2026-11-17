"""Collect all 21 source-bound sessions into three original scorer submissions."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
# This entry point executes the source bytes it verifies, never a cached .pyc.
manifest = json.loads((HERE / 'SOURCE.json').read_bytes())
broker_path = HERE / 'broker.py'
if any(p.is_symlink() for p in (broker_path, *broker_path.parents)):
    raise ValueError('Linked broker source')
expected = manifest['files'][str(broker_path.relative_to(HERE.parents[4]))]
fd = os.open(broker_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
with os.fdopen(fd, 'rb') as stream:
    before = os.fstat(stream.fileno())
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= 1048576:
        raise ValueError('Bounded ordinary broker source')
    body = stream.read(1048577)
    after = os.fstat(stream.fileno())
if (before.st_nlink != 1 or len(body) != before.st_size
        or (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
           (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        or {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} != expected):
    raise ValueError('Exact stable broker source required')
_broker = types.ModuleType('neural005_collector_broker')
_broker.__file__ = str(broker_path)
exec(compile(body, str(broker_path), 'exec'), _broker.__dict__)
for _name in ('VIEWS', 'decode', 'encode', 'load_study', 'need', 'ordinary', 'pin', 'publish', 'read'):
    globals()[_name] = getattr(_broker, _name)


def session_rows(study, directory, person, view):
    directory = ordinary(directory)
    need(directory.is_dir() and {p.name for p in directory.iterdir()} ==
         {'METHOD.json', 'START.json', 'commits.jsonl', 'probabilities.json', 'COMPLETE.json'}, 'Complete exact session inventory')
    complete_raw = read(directory / 'COMPLETE.json', 16384)
    complete = decode(complete_raw)
    need(set(complete) == {'schema', 'start', 'journal', 'last_commit', 'probabilities', 'committed',
                          'software_release_order_complete', 'external_participant_reset_verified', 'no_tools_enforced',
                          'model_or_provider_calls_by_broker', 'scientific_qualification'}
         and complete['schema'] == 'neural005_session_complete_v1'
         and complete['software_release_order_complete'] is True
         and complete['external_participant_reset_verified'] is False
         and complete['no_tools_enforced'] is False and complete['scientific_qualification'] is False
         and type(complete['model_or_provider_calls_by_broker']) is int and complete['model_or_provider_calls_by_broker'] == 0,
         'Exact software-only completion; no runtime promotion')
    start = decode(read(directory / 'START.json', 16384, complete['start']))
    need(set(start) == {'schema', 'session_id', 'participant', 'view', 'identity', 'method', 'training', 'expected_cases'}
         and start['schema'] == 'neural005_observation_session_v1'
         and start['participant'] == person and start['view'] == view and start['identity'] == study.identity
         and type(start['session_id']) is str and re.fullmatch('[a-f0-9]{32}', start['session_id']), 'Exact source/session binding')
    method = read(directory / 'METHOD.json', 32768, start['method'])
    need(start['training'] == pin(encode(study.training(view))), 'Complete exact matched training view')
    requests = study.queries[person]
    need(type(start['expected_cases']) is int and start['expected_cases'] == len(requests)
         and type(complete['committed']) is int and complete['committed'] == len(requests), 'Complete original person support')
    journal = read(directory / 'commits.jsonl', 262144, complete['journal'])
    lines = journal.splitlines(keepends=True)
    need(len(lines) == len(requests) and all(line.endswith(b'\n') for line in lines), 'Complete durable response records')
    previous, rows, nonces = complete['start'], [], set()
    for index, (line, request) in enumerate(zip(lines, requests)):
        record = decode(line)
        need(set(record) == {'index', 'observation', 'answer', 'previous'} and type(record['index']) is int
             and record['index'] == index and record['previous'] == previous, 'Ordered immutable commit chain')
        answer = record['answer']
        need(type(answer) is dict and set(answer) == {'session_id', 'nonce', 'participant', 'view', 'case_id', 'probability'}
             and answer['session_id'] == start['session_id'] and answer['participant'] == person
             and answer['view'] == view and answer['case_id'] == request['case_id'], 'Complete current case/view identity')
        need(type(answer['nonce']) is str and re.fullmatch('[a-f0-9]{32}', answer['nonce'])
             and answer['nonce'] not in nonces, 'Unique exact response nonce')
        probability = answer['probability']
        need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
             'Finite probability in [0,1]')
        expected_observation = {'schema': 'neural005_numeric_observation_v1', 'session_id': start['session_id'],
            'nonce': answer['nonce'], 'participant': person, 'view': view, 'case_id': request['case_id'],
            'index': index, 'feature_names': list(study.features.ARMS[view]),
            'features': study.features.vector(request['prefix'], view)}
        need(record['observation'] == pin(encode(expected_observation)), 'Exact permitted numeric observation')
        rows.append({k: answer[k] for k in ('participant', 'case_id', 'probability')})
        nonces.add(answer['nonce'])
        previous = pin(line)
    need(previous == complete['last_commit'], 'Complete final response commitment')
    submission = decode(read(directory / 'probabilities.json', 100000, complete['probabilities']))
    need(submission == {'schema_version': 1, 'probabilities': rows}, 'Unmodified captured probability values')
    return rows, pin(method), start['session_id'], pin(complete_raw)


def collect(study, sessions, output):
    sessions, output = ordinary(sessions), ordinary(output)
    expected = {view + '-' + person for view in VIEWS for person in study.people}
    need(sessions.is_dir() and {p.name for p in sessions.iterdir()} == expected, 'All 21 and only the required person/view sessions')
    need(not output.exists() and output.parent.is_dir(), 'Fresh operator collection directory')
    panels, receipts, methods, session_ids = {}, {}, set(), set()
    for view in VIEWS:
        panels[view] = []
        for person in study.people:
            name = view + '-' + person
            rows, method, identity, receipt = session_rows(study, sessions / name, person, view)
            need(identity not in session_ids, 'Independent broker session identities')
            session_ids.add(identity)
            methods.add(method['sha256'])
            panels[view].extend(rows)
            receipts[name] = receipt
        need(len(panels[view]) == 816, 'Every original query in every view')
    need(len(methods) == 1 and len(session_ids) == 21, 'Same declared method across 21 complete broker sessions')
    # No output is published unless all complete session chains validate first.
    output.mkdir(mode=0o700)
    files = {}
    for view in VIEWS:
        files[view + '.probabilities.json'] = publish(output / (view + '.probabilities.json'),
            encode({'schema_version': 1, 'probabilities': panels[view]}))
    report = {'schema': 'neural005_complete_observation_collection_v1', 'status': 'complete_software_collection',
              'identity': study.identity, 'method_sha256': next(iter(methods)), 'sessions': receipts, 'files': files,
              'protocols': 21, 'predictions': 2448, 'queries_per_view': 816, 'training_rows': 3254, 'training_people': 26,
              'development_people': 7, 'protected_target_packets_decoded_by_operator': True,
              'private_grade_feedback_supplied': False, 'delayed_behavioral_feedback_in_later_prefixes': True,
              'model_or_provider_calls_by_collector': 0, 'external_participant_reset_verified': False,
              'no_tools_enforced': False, 'native_EEG_representation': False, 'scientific_qualification': False}
    publish(output / 'COLLECTION.json', encode(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('train', 'development-private', 'sessions', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    study = load_study(args.train, args.development_private)
    report = collect(study, args.sessions, args.output)
    print(encode({'status': report['status'], 'protocols': 21, 'predictions': 2448}).decode(), end='')


if __name__ == '__main__':
    main()

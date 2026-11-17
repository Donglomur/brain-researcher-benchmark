"""Operator-only reconstruction from pinned public author tables; no candidate runs."""
import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat

from features import ARMS, BEHAVIOR, ERP, need, vector

HERE = Path(__file__).resolve().parent
SEED = 'NEURAL-005-processed-ERP-development-v1'
ERP_FILES = {key: 'df_' + key.replace('_base_offer', '_base') + '.csv' for key in ERP}
SOURCE_ROWS = 7380
MAX_FILE_BYTES = 5_000_000


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encode(value):
    return (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()


def exact_integer(value):
    need(type(value) is str, 'integer source token')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('integer source token') from exc
    need(number.is_finite() and number == number.to_integral_value(), 'exact integer')
    need(abs(number) <= 1_000_000, 'bounded identity integer')
    return int(number)


def number(value):
    if value in ('', 'NA', 'NaN'):
        return None
    result = float(value)
    need(math.isfinite(result), 'finite source measurement')
    return result


def read_pinned(path, pin):
    """Hash the same bounded, ordinary bytes that will be decoded."""
    need(type(pin['bytes']) is int and 0 < pin['bytes'] <= MAX_FILE_BYTES, 'source size bound')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == pin['bytes'], 'ordinary exact-size input')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            body = handle.read(MAX_FILE_BYTES + 1)
        after = os.fstat(fd)
        need(all(getattr(before, k) == getattr(after, k) for k in
                 ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'source changed while reading')
        need(len(body) == pin['bytes'] and digest(body) == pin['sha256'], 'source hash mismatch')
        return body
    finally:
        os.close(fd)


def parse_csv(body):
    reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig'), newline=''))
    names = reader.fieldnames
    need(names is not None and len(names) == len(set(names)), 'unique CSV column names')
    rows = list(reader)
    need(len(rows) == SOURCE_ROWS, 'all 7380 original rows required')
    need(all(None not in r and all(v is not None for v in r.values()) for r in rows),
         'rectangular CSV rows')
    return rows


def fixed_split(behavior):
    people = [str(exact_integer(r['sub'])) for r in behavior]
    counts = Counter(people)
    need(len(counts) == 41 and all(n == 180 for n in counts.values()), '41 complete source participants')
    ordered = sorted(counts, key=lambda p: (digest((SEED + ':' + p).encode()), int(p)))
    return {'training': ordered[:26], 'development': ordered[26:33], 'reserved': ordered[33:],
            'folds': {p: i % 3 for i, p in enumerate(ordered[:26])}}


def join_active(tables, active):
    """Join by original position before grouping; never sort a lone ERP table."""
    episodes = {}
    errors = {'reward': 0., 'valence': 0., 'arousal': 0.}
    for index, source in enumerate(tables['BEH_ug.csv']):
        person = str(exact_integer(source['sub']))
        if person not in active:
            continue  # Reserved numerical values are not converted or exported.
        row = {k: number(source[k]) for k in BEHAVIOR}
        row.update(round=exact_integer(source['trialLocal']),
                   trial_global=exact_integer(source['trialGlobal']),
                   episode=exact_integer(source['block']), partner=exact_integer(source['partnerID']),
                   choice=exact_integer(source['choice_num']))
        need((source['choice'], row['choice']) in (('A', 0), ('R', 1)), 'source choice coding')
        for key, filename in ERP_FILES.items():
            row[key] = number(tables[filename][index][key])
        for label, field, left, right in (
                ('reward', 'rpe', 'offer', 'rp'),
                ('valence', 'epe_valence', 'exp_valence', 'ep_valence'),
                ('arousal', 'epe_arousal', 'exp_arousal', 'ep_arousal')):
            actual = number(source[field])
            expected = None if row[left] is None or row[right] is None else row[left] - row[right]
            need((actual is None) == (expected is None), 'source error missingness')
            if actual is not None:
                delta = abs(actual - expected)
                need(delta < 1e-8, 'source error equation')
                errors[label] = max(errors[label], delta)
        episodes.setdefault((person, row['episode']), []).append((index + 1, row))
    return episodes, errors


def episode_pairs(person, episode, rows):
    """Current eligibility only; no skipping missing rounds or cross-partner joins."""
    need(type(episode) is int and 1 <= episode <= 36, 'original episode 1..36')
    need(len(rows) == 5 and [r['round'] for _, r in rows] == [1, 2, 3, 4, 5], 'five original rounds')
    need(len({r['partner'] for _, r in rows}) == 1, 'one partner per episode')
    first_global = rows[0][1]['trial_global']
    need(type(first_global) is int and 1 <= first_global <= 176
         and [r['trial_global'] for _, r in rows] == list(range(first_global, first_global + 5)),
         'consecutive source trials within original episode')
    need(all(type(r['choice']) is int and r['choice'] in (0, 1) for _, r in rows), 'binary choices')
    pairs = []
    for j in range(4):
        current_source, current = rows[j]
        target_source, target = rows[j + 1]
        if any(current[k] is None for k in ERP):
            continue
        prefix = [r for _, r in rows[:j + 1]]
        # Validate every observed prefix, including target-free current ERP support.
        vector(prefix, 'history')
        pairs.append({'request': {'participant': person, 'case_id': f'{person}:{episode}:{j + 1}',
                                  'prefix': prefix}, 'target': target['choice'],
                      'source_current': current_source, 'source_target': target_source})
    return pairs


def convert(tables, panel):
    split = fixed_split(tables['BEH_ug.csv'])
    training, development = set(split['training']), set(split['development'])
    episodes, errors = join_active(tables, training | development)
    need(set(episodes) == {(p, e) for p in training | development for e in range(1, 37)},
         'all 36 episodes for each active participant')
    train, dev, row_manifest, coverage = [], [], [], {}
    for (person, episode), rows in sorted(episodes.items(), key=lambda item: (int(item[0][0]), item[0][1])):
        pairs = episode_pairs(person, episode, rows)
        counts = coverage.setdefault(person, {'structural': 0, 'eligible': 0, 'missing_current_ERP': 0})
        counts['structural'] += 4
        counts['eligible'] += len(pairs)
        counts['missing_current_ERP'] += 4 - len(pairs)
        for pair in pairs:
            request = pair['request']
            row_manifest.append([person, pair['source_current'], pair['source_target']])
            if person in training:
                train.append({'participant': person, 'case_id': request['case_id'],
                              'target': pair['target'], 'features': vector(request['prefix'], 'all_erp')})
            else:
                dev.append(pair)
    need(len(train) == 3254 and len(dev) == 816, 'exact historical training/development support')
    expected = [(r['participant'], r['case_id']) for r in panel['cases']]
    got = [(r['request']['participant'], r['request']['case_id']) for r in dev]
    need(len(expected) == len(set(expected)) == 816 and set(got) == set(expected), 'exact public case panel')
    return {
        'train.json': {'rows': train, 'feature_names': ARMS, 'participant_ids': sorted(training),
                       'cv_fold_by_id': split['folds']},
        'development_private.json': {'cases': dev, 'participant_ids': sorted(development),
                                     'coverage': {p: c for p, c in coverage.items() if p in development}},
        'preparation.json': {'schema': 'neural005-source-preparation-v1', 'training_rows': len(train),
            'development_rows': len(dev), 'training_people': 26, 'development_people': 7,
            'reserved_people_excluded': 8, 'coverage': coverage, 'max_source_equation_errors': errors,
            'paired_row_manifest_sha256': digest(json.dumps(row_manifest, separators=(',', ':')).encode()),
            'source_join': 'author_original_row_order_conditional',
            'independent_ERP_trial_identity_verified': False, 'model_fits': 0,
            'candidate_runs': 0, 'candidate_delivery_qualified': False}}


def prepare(source_dir, output_dir):
    pins = json.loads((HERE / 'SOURCE_PINS.json').read_text())
    # All source authentication precedes any source table decode.
    bodies = {name: read_pinned(Path(source_dir) / name, pin) for name, pin in pins['files'].items()}
    panel_body = read_pinned(HERE.parent / 'registered-runtime/public/cases.json', pins['public_panel'])
    tables = {name: parse_csv(body) for name, body in bodies.items()}
    outputs = convert(tables, json.loads(panel_body))
    payloads = {name: encode(value) for name, value in outputs.items()}
    # Numerical artifacts reproduce the exact historical artifacts or fail closed.
    for name, pin in pins['expected_numerical_outputs'].items():
        need(len(payloads[name]) == pin['bytes'] and digest(payloads[name]) == pin['sha256'],
             'historical numerical artifact parity: ' + name)
    need(sum(map(len, payloads.values())) <= 10_000_000, 'bounded preparation output')
    output_dir = Path(output_dir).resolve()
    need(not output_dir.is_relative_to(HERE.parents[4]), 'operator outputs must be outside this repository')
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, body in payloads.items():
        fd = os.open(output_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    return {'status': 'source_prepared', 'training_rows': 3254, 'development_rows': 816,
            'files': {name: {'bytes': len(body), 'sha256': digest(body)} for name, body in payloads.items()},
            'model_fits': 0, 'candidate_runs': 0, 'independent_ERP_trial_identity_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--output', required=True, help='fresh operator directory outside repository')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_dir, args.output), allow_nan=False))

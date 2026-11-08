"""OSL complete program identity, before any observations or outcomes."""
import hashlib
import json
import math

TASK = 'PAPER-paper-signal-add-004'
REVISION = 'cded3b2ea95efef7b6c089c5e111fd565b716922'
BRANCHES = ('ctf_bursts', 'elekta_ae', 'elekta_tde', 'ctf_tde', 'ctf_dynemo', 'ctf_static')
HMM = {'ctf_bursts': (21, 3, 100), 'elekta_ae': (38, 8, 250),
       'elekta_tde': (80, 8, 250), 'ctf_tde': (80, 8, 250)}
ROLES = ('A', 'B', 'reference')
CONTROLS = ('real', 'common_phase', 'independent_phase')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def identity(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def people(branch):
    need(branch in BRANCHES, 'Exact original branch')
    return ([f'sub{i:02d}' for i in range(1, 20)] if branch.startswith('elekta')
            else [f'subject{i:02d}' for i in range(65)])


def fold_map(branch):
    cohort = 'elekta' if branch.startswith('elekta') else 'ctf'
    ids = people(branch)
    order = sorted(ids, key=lambda x: (hashlib.sha256(
        ('osl-full-paper-fold-v1:' + cohort + ':' + x).encode()).digest(), x))
    return {person: i % 5 for i, person in enumerate(order)}


def runs(branch, fold=None, split='all'):
    need(split in ('all', 'train', 'query'), 'Exact split')
    need((split == 'all' and fold is None) or
         (split != 'all' and type(fold) is int and 0 <= fold < 5), 'Fold identity')
    mapping = fold_map(branch)
    ids = [x for x in people(branch) if split == 'all' or
           (mapping[x] != fold if split == 'train' else mapping[x] == fold)]
    return [(person, run) for person in ids
            for run in (range(1, 7) if branch.startswith('elekta') else (1,))]


def validate_runs(rows, branch, fold=None, split='all'):
    need(type(rows) is list, 'Ordered complete run list')
    got = [(r['person'], r['run']) for r in rows]
    need(got == runs(branch, fold, split), 'Complete ordered original people/runs; no subset')
    return rows


def seed_for(*parts):
    """Prospective reproducibility schedule, never historical RNG recovery."""
    return int.from_bytes(hashlib.sha256(encoded(['osl-wave19-seed-v1', *parts])).digest()[:4], 'big')


def native_jobs(role):
    need(role in ROLES, 'Separate A/B/reference role')
    jobs = []
    for branch in BRANCHES:
        slots = [(None, None)] if branch == 'ctf_static' else [(s, a) for s in range(3) for a in range(10)]
        for fit_set, attempt in slots:
            job = {'phase': 'native', 'role': role, 'branch': branch,
                   'fit_set': fit_set, 'attempt': attempt,
                   'seed': seed_for('native', role, branch, fit_set, attempt)}
            jobs.append({**job, 'id': identity(job)})
    need(len(jobs) == 151, '150 native fits plus one static analysis')
    return jobs


def held_jobs(role):
    need(role in ROLES, 'Separate A/B/reference role')
    jobs = []
    for branch in HMM:
        for fold in range(5):
            for control in CONTROLS:
                for fit_set in range(3):
                    for attempt in range(10):
                        job = {'phase': 'held_hmm', 'role': role, 'branch': branch,
                               'fold': fold, 'control': control, 'fit_set': fit_set,
                               'attempt': attempt,
                               'seed': seed_for('fit', role, branch, fold, control, fit_set, attempt)}
                        jobs.append({**job, 'id': identity(job)})
    need(len(jobs) == 1800, 'Every branch/fold/control/set/attempt')
    return jobs


def select_sets(records):
    """Original minimum training free-energy selection; every failure retained."""
    need(type(records) is list and len(records) == 30, 'All three sets of ten dispositions')
    need({(r['fit_set'], r['attempt']) for r in records} ==
         {(s, a) for s in range(3) for a in range(10)}, 'Exact unique set/attempt support')
    for r in records:
        need(set(r) == {'fit_set', 'attempt', 'status', 'training_free_energy', 'capture_pin'},
             'Training-only selection fields; no query score')
        need(r['status'] in ('completed', 'failed'), 'Explicit terminal disposition')
        need((r['status'] == 'completed' and finite(r['training_free_energy']) and
              type(r['capture_pin']) is str and len(r['capture_pin']) == 64) or
             (r['status'] == 'failed' and r['training_free_energy'] is None),
             'A failed/uncaptured attempt is never a fitted model')
    selected = []
    for s in range(3):
        usable = [r for r in records if r['fit_set'] == s and r['status'] == 'completed']
        selected.append(None if not usable else min(usable,
                        key=lambda r: (r['training_free_energy'], r['attempt'])))
    return {'sets': selected, 'complete': all(r is not None for r in selected),
            'all_attempts': records, 'selection_uses_query': False}


def plan():
    return {'task_id': TASK, 'source_revision': REVISION,
            'native': {r: native_jobs(r) for r in ROLES},
            'held_hmm': {r: held_jobs(r) for r in ROLES},
            'native_attempts': 453, 'held_hmm_attempts': 5400,
            'execution_authorized': False, 'scientific_qualification': False}

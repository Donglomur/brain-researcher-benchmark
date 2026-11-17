"""NEURAL-058 fixed scientific metadata contracts; no input or numerical imports."""
from core import need, integer, descriptor, capture, parse, pin, encoded

TASK = 'NEURAL-058'
COHORT_PIN = {'bytes': 146662, 'sha256': 'f61c86a32bf6d6a46f516061fa527cf8538c5e3f0f05ba359addcdc9b3257db5'}
HEADS = ('velocity', 'speed')
ROLES = ('C', 'J')
MODES = ('F', 'I')
TOOLS = ('T0', 'T1')
REPLICATES = (1, 2, 3)
SOURCE_COMMIT = '6fbd666fe8170a2165f5198c1f490911424a654d'
LIBRARIES = {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.7.2',
             'torch': '2.10.0', 'torch_brain': '0.2.0a0'}


def cohort(doc):
    need(type(doc) is dict and doc.get('schema') == 'neural058_complete_official_animal_join_v1'
         and doc.get('source_commit') == SOURCE_COMMIT, 'exact biological source schema')
    groups = (('source_sessions', 423), ('evaluation_sessions', 29), ('excluded_extra_sessions', 7))
    seen = set(); by_role = {}; animals = {}; probes = set(); labs = {}
    for name, count in groups:
        rows = doc.get(name)
        need(type(rows) is list and len(rows) == count, 'complete original session cohort')
        out = {}
        for row in rows:
            need(type(row) is dict and set(row) == {'eid','animal','lab','role','probes','wheel_qc_values'},
                 'complete literal cohort row')
            need(all(type(row[k]) is str and row[k] for k in ('eid','animal','lab','role')), 'literal public source identifiers')
            need(row['eid'] not in seen, 'unique session across corpus roles'); seen.add(row['eid'])
            need(type(row['probes']) is list and row['probes'] and len(set(row['probes'])) == len(row['probes']), 'complete unique probe metadata')
            need(not probes.intersection(row['probes']), 'probe belongs to one session'); probes.update(row['probes'])
            need(row['wheel_qc_values'] == ['PASS'], 'exact source QC metadata, not numeric qualification')
            need(row['animal'] not in labs or labs[row['animal']] == row['lab'], 'one source lab per animal')
            labs[row['animal']] = row['lab']; out[row['eid']] = row
        by_role[name] = out; animals[name] = {r['animal'] for r in rows}
    need(len(animals['source_sessions']) == 126 and len(animals['evaluation_sessions']) == 13,
         'complete biological animals')
    need(not animals['source_sessions'] & animals['evaluation_sessions'], 'zero evaluation-animal source overlap')
    need(animals['excluded_extra_sessions'] <= animals['evaluation_sessions'], 'all seven extra sessions are banned evaluation-animal lineage')
    folds = doc.get('source_animal_folds')
    need(type(folds) is dict and set(folds) == animals['source_sessions'], 'complete source-animal folds')
    need(all(type(v) is int and 0 <= v < 5 for v in folds.values()), 'ordinary five-fold IDs')
    need([list(folds.values()).count(i) for i in range(5)] == [26,25,25,25,25], 'fixed full source folds')
    return {'source': by_role['source_sessions'], 'evaluation': by_role['evaluation_sessions'],
            'excluded': by_role['excluded_extra_sessions'], 'source_animals': sorted(animals['source_sessions']),
            'eval_animals': sorted(animals['evaluation_sessions']), 'folds': dict(folds)}


def load_cohort(path, budget):
    raw, stamp = capture(path, COHORT_PIN, COHORT_PIN['bytes'], budget, readonly=True)
    return cohort(parse(raw)), {'source': COHORT_PIN, 'stamp': stamp}


def source_animal_split(roster, fold):
    need(fold == 'full' or type(fold) is int and 0 <= fold < 5, 'source fold or full refit')
    train = sorted(e for e,r in roster['source'].items() if fold == 'full' or roster['folds'][r['animal']] != fold)
    val = [] if fold == 'full' else sorted(e for e,r in roster['source'].items() if roster['folds'][r['animal']] == fold)
    ta = {roster['source'][e]['animal'] for e in train}; va = {roster['source'][e]['animal'] for e in val}
    need(not ta & va and ta | va == set(roster['source_animals']), 'whole-animal source partition')
    need(not (ta | va) & set(roster['eval_animals']), 'no evaluation-animal fitting or selection')
    return train, val


def training_lineage(record, roster, fold, role):
    need(role in ROLES and type(record) is dict, 'explicit fitted role')
    train, val = source_animal_split(roster, fold)
    need(record.get('task') == TASK and record.get('role') == role and record.get('fold') == fold,
         'same task role and source fold')
    need(record.get('training_sessions') == train and record.get('validation_sessions') == val,
         'exact complete source session lineage')
    need(record.get('training_animals') == sorted({roster['source'][e]['animal'] for e in train}),
         'exact training animal lineage')
    need(record.get('external_neural_pretraining') == [] and record.get('evaluation_wheel_access') is False,
         'strict source-only reference training, no hidden checkpoint')
    need(record.get('transform_fit_sessions') == train, 'transforms never fitted on validation animals')
    return record


def positive_limits(row):
    need(type(row) is dict, 'resource profile')
    for k in ('provider_calls','tokens','read_bytes','write_bytes','native_cpu_ns','retained_bytes','memory_bytes','concurrency'):
        integer(row[k], 1)
    for k in ('wall_seconds','gpu_device_seconds','money'):
        from core import finite
        value = finite(row[k]); need(value >= 0 and (k != 'wall_seconds' or value > 0), 'finite nonnegative full-panel cap')
    return row


def matched_panel_limits(profiles):
    need(type(profiles) is dict, 'complete matched panel resource selection')
    expected = {f'{m}/{r}/{t}/r{k}' for m in MODES for r in ROLES for t in TOOLS for k in REPLICATES}
    need(set(profiles) == expected, 'all24 complete panel profiles')
    for role in ROLES:
        for tool in TOOLS:
            for rep in REPLICATES:
                f = positive_limits(profiles[f'F/{role}/{tool}/r{rep}'])
                i = positive_limits(profiles[f'I/{role}/{tool}/r{rep}'])
                need(f == i, 'equal complete-panel F/I caps, never13 independent I budgets')
    return profiles


def metadata_pin(value):
    return pin(encoded(value))

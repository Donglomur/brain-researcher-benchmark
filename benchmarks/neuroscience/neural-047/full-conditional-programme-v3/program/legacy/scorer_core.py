"""Absolute held-out-worm predictions; all arms admitted before private access."""
import hashlib
import math
import random
import re
from .delivery_io import canonical, exact, need
from .history import ARMS

FLOOR = 1e-15
KEY = re.compile(r'case_[a-f0-9]{32}\Z')


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def public_contract(public):
    exact(public, ['schema', 'packet_id', 'input_generation', 'split_unit', 'arms', 'folds'])
    need(type(public['input_generation']) is str and re.fullmatch('[a-f0-9]{64}', public['input_generation']),
         'Opaque complete normalized-input generation binding')
    need(public['schema'] == 'neural047-panel-v1' and public['split_unit'] == 'animal' and
         public['arms'] == list(ARMS) and type(public['folds']) is list and 3 <= len(public['folds']) <= 256,
         'Exact task, arms and independent grouping contract')
    need(public['packet_id'] == fingerprint({k: v for k, v in public.items() if k != 'packet_id'}),
         'Exact public panel fingerprint')
    all_keys = set(); groups = set()
    for i, fold in enumerate(public['folds']):
        exact(fold, ['fold_id', 'test_group', 'case_keys'])
        need(fold['fold_id'] == 'fold_%03d' % i and type(fold['test_group']) is str and
             re.fullmatch('group_[a-f0-9]{24}', fold['test_group']) and fold['test_group'] not in groups,
             'Every biological group held out once')
        groups.add(fold['test_group'])
        need(type(fold['case_keys']) is list and 0 < len(fold['case_keys']) <= 50000, 'All eligible events')
        for key in fold['case_keys']:
            need(type(key) is str and KEY.fullmatch(key) and key not in all_keys, 'Unique complete event support')
            all_keys.add(key)
    need(len(all_keys) <= 50000, 'Complete panel event cap')
    return all_keys


def admit(public, submission):
    public_contract(public)
    exact(submission, ['schema', 'packet_id', 'outcomes'])
    need(submission['schema'] == 'neural047-predictions-v1' and
         submission['packet_id'] == public['packet_id'] and type(submission['outcomes']) is list and
         len(submission['outcomes']) == len(public['folds']) * 3, 'All three arms for every held-out group')
    wanted = {(f['fold_id'], arm): f for f in public['folds'] for arm in ARMS}
    admitted = {}; abstained = []
    for outcome in submission['outcomes']:
        need(type(outcome) is dict and outcome.get('status') in ('complete', 'abstain'), 'Complete or explicit abstention')
        tail = 'predictions' if outcome['status'] == 'complete' else 'reason'
        exact(outcome, ['fold_id', 'arm', 'status', tail])
        need(type(outcome['fold_id']) is str and type(outcome['arm']) is str, 'Typed fold and arm')
        key = (outcome['fold_id'], outcome['arm'])
        need(key in wanted and key not in admitted, 'Exact unique fold/arm join')
        if outcome['status'] == 'abstain':
            need(type(outcome['reason']) is str and 0 < len(outcome['reason']) <= 256, 'Explicit bounded abstention')
            admitted[key] = None; abstained.append(key); continue
        rows = outcome['predictions']; expected = set(wanted[key]['case_keys']); probabilities = {}
        need(type(rows) is list and len(rows) == len(expected), 'Complete shared event support, no favorable subset')
        for row in rows:
            exact(row, ['case_key', 'p_dorsal'])
            case = row['case_key']; probability = row['p_dorsal']
            need(type(case) is str and case in expected and case not in probabilities, 'Exact prediction case join')
            need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
                 'One finite dorsal probability, no boolean or renormalization')
            probabilities[case] = probability
        admitted[key] = probabilities
    need(set(admitted) == set(wanted), 'Every fold and arm submitted')
    return admitted, abstained


def logloss(y, probability):
    return -math.log(max(FLOOR, probability if y else 1 - probability))


def interval(values):
    """Fixed paired group bootstrap, pointwise/descriptive under overlapping CV."""
    rng = random.Random(47047); n = len(values)
    means = sorted(math.fsum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(10000))
    def percentile(q):
        index = (len(means) - 1) * q; lower = int(index); fraction = index - lower
        return means[lower] * (1 - fraction) + means[min(lower + 1, len(means) - 1)] * fraction
    return [percentile(.025), percentile(.975)]


def score(public, submission, load_private):
    predictions, abstained = admit(public, submission)
    if abstained:
        return {'status': 'abstained', 'metrics': None, 'private_target_callbacks': 0,
                'reason': 'At least one required group/arm abstained; no subset score.'}
    private = load_private()
    exact(private, ['schema', 'packet_id', 'targets'])
    need(private['schema'] == 'neural047-targets-v1' and private['packet_id'] == public['packet_id'], 'Bound private target generation')
    expected = public_contract(public); truth = {}
    need(type(private['targets']) is list and len(private['targets']) == len(expected), 'Complete private targets')
    for row in private['targets']:
        exact(row, ['case_key', 'dorsal'])
        need(type(row['case_key']) is str and row['case_key'] in expected and row['case_key'] not in truth and
             type(row['dorsal']) is int and row['dorsal'] in (0, 1), 'Private target join and binary orientation')
        truth[row['case_key']] = row['dorsal']
    groups = []; total = {a: [] for a in ARMS}
    for fold in public['folds']:
        row = {'fold_id': fold['fold_id'], 'test_group': fold['test_group'], 'events': len(fold['case_keys']),
               'class_counts': [sum(truth[k] == y for k in fold['case_keys']) for y in (0, 1)], 'arms': {}}
        for arm in ARMS:
            losses = [logloss(truth[k], predictions[(fold['fold_id'], arm)][k]) for k in fold['case_keys']]
            total[arm].extend(losses)
            recall = [sum((predictions[(fold['fold_id'], arm)][k] >= .5) == bool(y)
                          for k in fold['case_keys'] if truth[k] == y) / row['class_counts'][y]
                      if row['class_counts'][y] else None for y in (0, 1)]
            row['arms'][arm] = {'log_loss': math.fsum(losses) / len(losses),
                                'class_recalls': recall,
                                'balanced_accuracy': math.fsum(recall) / 2 if None not in recall else None}
        groups.append(row)
    macro_loss = {a: math.fsum(g['arms'][a]['log_loss'] for g in groups)/len(groups) for a in ARMS}
    complete_ba = all(all(g['arms'][a]['balanced_accuracy'] is not None for g in groups) for a in ARMS)
    macro_ba = {a: math.fsum(g['arms'][a]['balanced_accuracy'] for g in groups)/len(groups)
                if complete_ba else None for a in ARMS}
    return {'schema':'neural047-grade-v1','status':'scored','packet_id':public['packet_id'],
        'private_target_callbacks':1,'aggregation_unit':'animal','animals':len(groups),'groups':groups,
        'primary':'N_worm_macro_balanced_accuracy','primary_value':macro_ba['N'],'direction':'higher',
        'co_primary_N_worm_macro_log_loss':macro_loss['N'],
        'absolute_group_macro_log_loss':macro_loss,'absolute_group_macro_balanced_accuracy':macro_ba,
        'log_loss_descriptive_95pct_whole_worm_bootstrap':{a:interval([g['arms'][a]['log_loss'] for g in groups]) for a in ARMS},
        'balanced_accuracy_descriptive_95pct_whole_worm_bootstrap':
            {a:interval([g['arms'][a]['balanced_accuracy'] for g in groups]) if complete_ba else None for a in ARMS},
        'primary_defined_for_every_worm':complete_ba,
        'undefined_primary_reason':None if complete_ba else 'At least one worm has a single observed direction; no worm dropped and no subset BA.',
        'pooled_event_log_loss_secondary':{a:math.fsum(v)/len(v) for a,v in total.items()},
        'log_floor':FLOOR,'scientific_success':None,'causal_effect':False,'runtime_verified':False,
        'matched_method_compliance':'Requires isolated program execution and training-only transform provenance; predictions alone do not prove it.',
        'uncertainty_limit':'Descriptive whole-worm bootstrap; overlapping training folds and exposed source do not establish population performance.',
        'negative_control_qualified':False}

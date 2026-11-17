"""MindBridge numerical endpoint and paired calibration comparison.

Independent implementation of published/source mathematical metrics. This module
never loads models, downloads weights, authenticates exposure receipts, or declares
scientific qualification. See the adjacent source/protocol documentation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

TASK = 'PAPER-paper-method-033'
ARMS = ('single', 'bridge', 'neural_free', 'shuffled_neural')
METRICS = {'alexnet2': 'two_way', 'alexnet5': 'two_way', 'inception': 'two_way',
           'clip': 'two_way', 'effnet_b': 'distance', 'swav': 'distance',
           'pixcorr': 'correlation'}
GATES = ['target_subject_primary_metric_and_budget_not_canonically_frozen',
         'authentic_complete_NSD_image_subject_session_mapping_unverified',
         'feature_extraction_preprocessing_weights_and_payloads_unverified',
         'pretraining_exposure_receipts_and_equal_access_not_independently_authenticated',
         'native_MindBridge_single_bridge_and_control_execution_not_run',
         'source_best_of_eight_target_aware_selection_not_protected',
         'upstream_code_license_NSD_agreement_and_stimulus_rights_unresolved',
         'protected_replay_baseline_competence_and_scientific_review_not_qualified']

class ContractError(ValueError):
    """Reject an input rather than silently change the scientific denominator."""


def need(ok, message):
    if not ok:
        raise ContractError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def ids(values, name, minimum=0):
    need(isinstance(values, list), name + ' must be a list')
    need(all(isinstance(x, str) and x.strip() == x and x for x in values),
         name + ' requires nonempty canonical string identities')
    need(len(values) >= minimum and len(values) == len(set(values)),
         name + ' has insufficient or duplicate identities')
    return values


def text(value, name):
    need(isinstance(value, str) and bool(value.strip()), name + ' must be nonempty')


def hash_id(value, name):
    need(isinstance(value, str) and len(value) == 64 and
         all(c in '0123456789abcdef' for c in value), name + ' must be SHA256')


def matrix(value, name):
    try:
        x = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ContractError(name + ' must be numeric') from exc
    need(x.ndim == 2 and x.shape[0] >= 2 and x.shape[1] >= 2,
         name + ' requires >=2 images and >=2 features')
    need(bool(np.isfinite(x).all()), name + ' has nonfinite values')
    return x


def score_features(reference, prediction, metric):
    """Source-identical Pearson matrix, predicted columns and strict tie rule.

    The full correlation matrix is deliberate: alternate normalization and block
    arithmetic can perturb exact ties. At the paper's 982-image test size the
    float64 correlation matrix occupies approximately 31 MB.
    """
    need(metric in METRICS, 'unsupported metric')
    r, p = matrix(reference, 'reference'), matrix(prediction, 'prediction')
    need(r.shape == p.shape, 'reference/prediction shape mismatch')
    need(bool(np.all(np.ptp(r, axis=1) > 0) and np.all(np.ptp(p, axis=1) > 0)),
         'zero-variance feature row')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        corr = np.corrcoef(r, p)[:len(r), len(r):]
    need(bool(np.isfinite(corr).all()), 'undefined numerical correlation')
    paired = np.diag(corr)
    mode = METRICS[metric]
    if mode == 'distance':
        return 1.0 - paired
    if mode == 'correlation':
        return paired.copy()
    return np.sum(corr < paired, axis=0) / (len(r) - 1)


def validate_protocol(protocol):
    need(protocol.get('task_id') == TASK and protocol.get('schema_version') == 1,
         'wrong task/protocol schema')
    need(protocol.get('status') == 'prospective_unqualified',
         'protocol must retain prospective unqualified status')
    target = protocol.get('target_subject'); text(target, 'target_subject')
    test = ids(protocol.get('test_image_ids'), 'test_image_ids', 2)
    observations = protocol.get('test_measurements')
    need(isinstance(observations, list) and observations, 'test measurement roster required')
    measurement_ids = []
    for obs in observations:
        need(obs.get('subject_id') == target, 'wrong held-out measurement subject')
        text(obs.get('session_id'), 'held-out session id')
        text(obs.get('image_id'), 'held-out image id')
        measurement_ids.append(obs.get('measurement_id'))
    ids(measurement_ids, 'held-out measurement ids', 2)
    need({o['image_id'] for o in observations} == set(test), 'held-out observation coverage differs')
    metrics = ids(protocol.get('metrics'), 'metrics', 1)
    need(set(metrics) <= METRICS.keys(), 'unsupported metric requested')
    need(protocol.get('primary_metric') in metrics, 'primary metric absent')
    sel = protocol.get('selection', {})
    need(sel.get('mode') == 'fixed_candidate_index', 'target-aware selection forbidden')
    need(type(sel.get('candidate_count')) is int and sel['candidate_count'] > 0,
         'candidate count must be positive integer')
    need(type(sel.get('candidate_index')) is int and
         0 <= sel['candidate_index'] < sel['candidate_count'], 'invalid candidate index')
    text(sel.get('freeze_receipt'), 'selection freeze_receipt')
    hash_id(protocol.get('access_manifest_sha256'), 'access_manifest_sha256')
    hash_id(protocol.get('image_prior_sha256'), 'image_prior_sha256')
    feats = protocol.get('feature_provenance', {})
    need(set(feats) == set(metrics), 'feature provenance must cover exactly all metrics')
    for metric in metrics:
        hash_id(feats[metric].get('extractor_receipt_sha256'), metric+' extractor receipt')
        text(feats[metric].get('representation'), metric+' representation')
    exposures = protocol.get('noncalibration_exposures')
    need(isinstance(exposures, list), 'all noncalibration exposures required')
    seen = set()
    for e in exposures:
        need(e.get('stage') in ('shared_training', 'development', 'image_prior_training'),
             'unknown exposure stage')
        text(e.get('source'), 'exposure source')
        text(e.get('subject_id'), 'exposure subject_id; image priors use not_applicable')
        key = (e['stage'], e['source'], e['subject_id'])
        need(key not in seen, 'duplicate exposure ledger entry'); seen.add(key)
        exposed = ids(e.get('image_ids'), 'exposure image_ids')
        need(not set(exposed) & set(test), 'held-out image exposed in any subject/stage')
        hash_id(e.get('membership_receipt_sha256'), 'membership receipt')
        if e['stage'] == 'shared_training':
            need(e['subject_id'] != target, 'target cannot be a shared-training subject')
    need(any(e['stage']=='shared_training' and e['image_ids'] for e in exposures),
         'bridge comparison needs declared shared-subject training exposure')
    need(any(e['stage']=='image_prior_training' for e in exposures),
         'image-prior exposure membership must be declared even if empty')
    budgets = protocol.get('budgets')
    need(isinstance(budgets, list) and len(budgets) >= 2,
         'calibration curve requires at least two budgets')
    previous = set(); previous_measurements = set(); last = 0
    for b in budgets:
        n = b.get('budget')
        need(type(n) is int and n > last, 'budgets must be increasing positive integers')
        rows = b.get('calibration')
        need(isinstance(rows, list) and len(rows) == n, 'budget counts unique images')
        im = ids([r.get('image_id') for r in rows], 'calibration image ids', 1)
        all_m = []
        for row in rows:
            need(row.get('subject_id') == target, 'calibration subject differs from target')
            all_m.extend(ids(row.get('measurement_ids'), 'measurement ids', 1))
        ids(all_m, 'budget measurement ids', 1)
        need(not set(im) & set(test), 'calibration/test image overlap')
        need(not set(all_m) & set(measurement_ids), 'held-out measurement reused for calibration')
        need(previous <= set(im) and previous_measurements <= set(all_m),
             'calibration budgets must retain previous images and measurements')
        # Prevent a repeated measurement changing its underlying image identity.
        mapping = {m:r['image_id'] for r in rows for m in r['measurement_ids']}
        if last:
            need(all(mapping[m] == old_mapping[m] for m in old_mapping),
                 'measurement/image identity changed between budgets')
        old_mapping = mapping
        previous, previous_measurements, last = set(im), set(all_m), n
    return protocol


def aligned_features(packet, test, metrics, provenance, candidates=None, index=None):
    got = ids(packet.get('image_ids'), 'packet image ids', 2)
    need(set(got) == set(test), 'packet does not cover the complete fixed test roster')
    need(packet.get('feature_provenance') == provenance, 'feature extraction receipt mismatch')
    values = packet.get('features', {})
    need(set(values) == set(metrics), 'packet features must match requested metrics')
    lookup = {im:i for i,im in enumerate(got)}
    order = [lookup[im] for im in test]
    result = {}
    for metric in metrics:
        try:
            x = np.asarray(values[metric], dtype=float)
        except (TypeError, ValueError) as exc:
            raise ContractError('malformed features') from exc
        if candidates is not None:
            need(x.ndim == 3 and x.shape[:2] == (len(got), candidates),
                 'prediction needs image x fixed-candidate x feature array')
            need(bool(np.isfinite(x).all()), 'nonfinite candidate features')
            x = x[:,index,:]
        else:
            need(x.ndim == 2 and len(x) == len(got), 'reference feature shape mismatch')
        result[metric] = matrix(x[order], metric)
    return result


def evaluate(protocol, reference, submission, bootstrap_samples=2000, seed=0):
    """Score complete paired arms; bootstrap focal images conditional on the gallery."""
    validate_protocol(protocol)
    need(type(bootstrap_samples) is int and 100 <= bootstrap_samples <= 100000,
         'bootstrap_samples must be integer in [100,100000]')
    need(type(seed) is int and 0 <= seed < 2**32, 'invalid seed')
    binding = digest(protocol)
    need(reference.get('protocol_sha256') == binding and
         submission.get('protocol_sha256') == binding, 'protocol binding mismatch')
    test, metrics = protocol['test_image_ids'], protocol['metrics']
    expected_target = protocol['target_subject']
    need(reference.get('target_subject') == expected_target, 'wrong reference subject')
    ref = aligned_features(reference, test, metrics, protocol['feature_provenance'])
    runs = submission.get('runs'); need(isinstance(runs, list), 'runs must be a list')
    expected = {(b['budget'], arm) for b in protocol['budgets'] for arm in ARMS}
    indexed = {}
    for run in runs:
        key = (run.get('budget'), run.get('arm'))
        need(key in expected and key not in indexed, 'unknown/duplicate arm or budget')
        need(run.get('target_subject') == expected_target, 'target subject changed')
        need(run.get('test_measurements_sha256') == digest(protocol['test_measurements']),
             'test session/repetition membership changed')
        need(run.get('access_manifest_sha256') == protocol['access_manifest_sha256'],
             'unequal authorized data access')
        need(run.get('image_prior_sha256') == protocol['image_prior_sha256'],
             'unequal image priors')
        budget = next(b for b in protocol['budgets'] if b['budget'] == key[0])
        need(run.get('calibration_sha256') == digest(budget['calibration']),
             'unequal calibration labels/repeats')
        need(run.get('noncalibration_exposures_sha256') ==
             digest(protocol['noncalibration_exposures']), 'unequal exposure accounting')
        need(run.get('selection') == protocol['selection'], 'selection changed')
        hash_id(run.get('execution_receipt_sha256'), 'execution receipt')
        expected_intervention = {'single':'exposure_matched_single_subject_decoder', 'bridge':'bridge_neural',
                                 'neural_free':'no_neural_input',
                                 'shuffled_neural':'within_target_image_derangement'}[key[1]]
        need(run.get('intervention') == expected_intervention, 'wrong control intervention')
        if key[1] == 'shuffled_neural':
            donors = ids(run.get('neural_donor_image_ids'), 'neural donor image ids', 2)
            packet_ids = run.get('image_ids')
            need(set(donors) == set(test) and len(packet_ids) == len(donors),
                 'shuffle must preserve complete target image roster')
            need(all(a != b for a,b in zip(donors,packet_ids)), 'shuffle has fixed points')
        pred = aligned_features(run, test, metrics, protocol['feature_provenance'],
                                protocol['selection']['candidate_count'],
                                protocol['selection']['candidate_index'])
        indexed[key] = {m:score_features(ref[m], pred[m], m) for m in metrics}
    need(set(indexed) == expected, 'missing required arm/budget; no partial scoring')
    # Reuse image bootstrap draws for all arms and budgets to retain pairing.
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(test), size=(bootstrap_samples, len(test)))
    budget_outputs = []
    primary_effects = []
    for b in protocol['budgets']:
        n = b['budget']; arm_out = {}
        for arm in ARMS:
            arm_out[arm] = {m:{'mean':float(v.mean()), 'per_image':v.tolist(),
                               'direction':'lower' if METRICS[m]=='distance' else 'higher'}
                            for m,v in indexed[n,arm].items()}
        comparisons = {}
        for comparator in ('single','neural_free','shuffled_neural'):
            row = {}
            for m in metrics:
                sign = -1 if METRICS[m] == 'distance' else 1
                d = sign * (indexed[n,'bridge'][m] - indexed[n,comparator][m])
                ci = np.quantile(d[draws].mean(axis=1), [0.025,0.975])
                row[m] = {'benefit':float(d.mean()), 'paired_image_ci95':ci.tolist()}
                if comparator == 'single' and m == protocol['primary_metric']:
                    primary_effects.append(d)
            comparisons['bridge_vs_'+comparator] = row
        budget_outputs.append({'budget_unique_images':n,
                               'measurement_count':sum(len(r['measurement_ids']) for r in b['calibration']),
                               'arms':arm_out, 'comparisons':comparisons})
    x = np.array([b['budget'] for b in protocol['budgets']],dtype=float)
    # Explicit trapezoidal integration avoids version-dependent np.trapz removal.
    effects = np.stack(primary_effects)
    per_image_auc = np.sum((effects[:-1]+effects[1:])*.5*np.diff(x)[:,None],axis=0)/(x[-1]-x[0])
    return {'task_id':TASK, 'protocol_sha256':binding, 'reference_sha256':digest(reference),
            'submission_sha256':digest(submission),
            'scientific_qualification':'unknown', 'full_contract_complete':False,
            'endpoint_status':'prospective_feature_endpoint_evaluated',
            'target_subject':expected_target, 'test_image_ids':test,
            'primary_metric':protocol['primary_metric'], 'budgets':budget_outputs,
            'calibration_efficiency':{'definition':'normalized trapezoidal bridge benefit over single versus unique-image budget',
                'benefit_auc':float(per_image_auc.mean()),
                'paired_image_ci95':np.quantile(per_image_auc[draws].mean(axis=1),[.025,.975]).tolist()},
            'uncertainty':{'unit':'unique held-out image', 'gallery':'fixed complete gallery',
                           'scope':'conditional on target, fitted models, seeds and fixed gallery; not subject or training variability',
                           'bootstrap_samples':bootstrap_samples, 'seed':seed},
            'preserved_gates':GATES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol', type=Path); parser.add_argument('reference', type=Path)
    parser.add_argument('submission', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--bootstrap-samples', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    try:
        data = [json.loads(p.read_text()) for p in (args.protocol,args.reference,args.submission)]
        out = evaluate(*data,bootstrap_samples=args.bootstrap_samples,seed=args.seed)
    except (ContractError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, 'rejected: '+str(exc)+'\n')
    args.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')

if __name__ == '__main__':
    main()

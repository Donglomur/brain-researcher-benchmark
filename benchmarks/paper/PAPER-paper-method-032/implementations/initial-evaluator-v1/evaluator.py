"""MindEye2 frozen-pool feature evaluator. No model execution or qualification."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from statistics import NormalDist
import numpy as np

TASK = 'PAPER-paper-method-032'
CODE_REVISION = '76a2609243ba1bacb450e47e3dc78de1f78a9c00'
DATA_REVISION = '26421f100e4c6012a35ecadb272a0ec1d999202d'
CONTRACT_SHA256 = 'be0baca5eebb4c64fa0d6096fdbd9df12aa16e4abf9342c6d16ab0aa433ac9ff'
HOLDS = [
    'Authentic full population and repeated-trial aggregation require independent verification.',
    'Native feature extraction, checkpoints, image preprocessing and numeric parity are unverified.',
    'Full reconstruction endpoint (SSIM, pixel and all image-model metrics) remains incomplete.',
    'Paper prose versus notebook two-way orientation and historical RNG-state parity remain unresolved.',
    'Protected candidate execution, reference acquisition and baseline competence are unverified.',
    'NSD/stimulus/component rights and actual pretraining exposure require qualification.',
    'Released-weight adaptation is not a rerun of full shared-subject pretraining/scaling.',
]


def digest(value):
    """Canonical JSON commitment used for identity-bearing manifests, not raw file hashes."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _ids(values, name, minimum=1):
    if not isinstance(values, list) or len(values) < minimum:
        raise ValueError(f'{name}: expected at least {minimum} identities')
    if any(not isinstance(x, str) or not x for x in values) or len(set(values)) != len(values):
        raise ValueError(f'{name}: identities must be unique nonempty strings')
    return values


def _matrix(values, name, n=None):
    raw = np.asarray(values)
    if raw.dtype.kind not in 'fiu' or raw.dtype.kind == 'b':
        raise ValueError(f'{name}: real numeric array required')
    x = np.asarray(values, dtype=np.float64)
    if x.ndim < 2 or (n is not None and len(x) != n):
        raise ValueError(f'{name}: first dimension must match identities')
    x = x.reshape(len(x), -1)
    if not len(x) or x.shape[1] < 2 or not np.isfinite(x).all():
        raise ValueError(f'{name}: finite nonempty feature vectors required')
    return x


def _normalize(x, centered=False):
    if centered:
        x = x - x.mean(axis=1, keepdims=True)
    # Scale before norm to avoid overflow for large valid input features.
    scale = np.max(np.abs(x), axis=1, keepdims=True)
    if np.any(scale == 0) or not np.isfinite(scale).all():
        raise ValueError('undefined similarity: zero vector or constant Pearson features')
    z = x / scale
    return z / np.sqrt(np.sum(z * z, axis=1, keepdims=True))


def retrieval_draw(brain, images):
    """Corrected labels: brain rows -> image columns, then reverse queries."""
    b, i = _matrix(brain, 'brain'), _matrix(images, 'images')
    if b.shape != i.shape or len(b) < 2:
        raise ValueError('paired retrieval feature shapes must agree')
    sim = _normalize(b) @ _normalize(i).T
    answers = np.arange(len(b))
    scores = {}
    for label, mat in [('image_retrieval', sim), ('brain_retrieval', sim.T)]:
        top = mat.max(axis=1, keepdims=True)
        # The upstream GPU argsort does not define stable tie ordering across devices.
        if np.any(np.sum(mat == top, axis=1) != 1):
            raise ValueError(f'{label}: tied maximum; native tie parity is unresolved')
        scores[label] = float(np.mean(np.argmax(mat, axis=1) == answers))
    return scores


def reconstruction_identification(real, reconstructed):
    """Feature-only strict two-way Pearson identification, upstream column semantics."""
    r, p = _matrix(real, 'real'), _matrix(reconstructed, 'reconstructed')
    if r.shape != p.shape or len(r) < 2:
        raise ValueError('paired reconstruction feature shapes must agree; N >= 2')
    correlations = _normalize(r, centered=True) @ _normalize(p, centered=True).T
    hits = correlations < np.diag(correlations)[None, :]
    np.fill_diagonal(hits, False)
    per_image = hits.sum(axis=0) / (len(r) - 1)
    return {'mean': float(per_image.mean()), 'per_image': per_image.tolist(),
            'distractors_per_image': len(r) - 1, 'tie_policy': 'strict_loss'}


def paired_pearson(real, reconstructed):
    """Mean paired Pearson for already preprocessed features/pixels; no resizing."""
    r, p = _matrix(real, 'real'), _matrix(reconstructed, 'reconstructed')
    if r.shape != p.shape:
        raise ValueError('paired feature shapes must agree')
    per_image = np.sum(_normalize(r, True) * _normalize(p, True), axis=1)
    return {'mean': float(per_image.mean()), 'per_image': per_image.tolist()}


def freeze_pools(image_ids, seed=42):
    """Prospective reproducible local RNG; not a reconstruction of historical RNG state."""
    ids = _ids(image_ids, 'image_ids', 300)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('seed must be a uint32 integer')
    rng = np.random.RandomState(seed)
    return [[ids[j] for j in rng.choice(len(ids), 300, replace=False)] for _ in range(30)]


def validate_pools(ids, pools):
    if not isinstance(pools, list) or len(pools) != 30:
        raise ValueError('author retrieval endpoint requires exactly 30 frozen draws')
    allowed = set(ids)
    for pool in pools:
        _ids(pool, 'draw', 300)
        if len(pool) != 300 or not set(pool) <= allowed:
            raise ValueError('each draw must contain exactly 300 distinct declared identities')


def _summary(values):
    x = np.asarray(values, dtype=np.float64)
    mean = float(x.mean())
    sem = float(x.std(ddof=0) / np.sqrt(len(x)))
    half = NormalDist().inv_cdf(0.975) * sem
    return {'mean': mean, 'draw_values': x.tolist(), 'draw_sem': sem,
            'draw_normal_95_interval': [mean - half, mean + half],
            'uncertainty_unit': 'repeated retrieval subset; not independent subjects/images'}


def validate_reference(ref):
    if ref.get('task_id') != TASK or ref.get('contract_sha256') != CONTRACT_SHA256:
        raise ValueError('wrong task or canonical contract commitment')
    if ref.get('code_revision') != CODE_REVISION or ref.get('dataset_revision') != DATA_REVISION:
        raise ValueError('source revisions must match frozen task')
    if type(ref.get('subject')) is not int or ref['subject'] not in (1, 2, 5, 7):
        raise ValueError('paper evaluation cohort comprises subjects 1,2,5,7')
    ids = _ids(ref.get('image_ids'), 'reference image_ids', 1000)
    if len(ids) != 1000:
        raise ValueError('complete paper population requires 1000 shared image identities per subject')
    validate_pools(ids, ref.get('retrieval_pools'))
    if ref.get('feature_space') != 'openclip:ViT-bigG-14:laion2b_s39b_b160k:256x1664-tokens':
        raise ValueError('unexpected retrieval feature space')
    _sha(ref.get('image_features_sha256'), 'image_features_sha256')
    _sha(ref.get('population_manifest_sha256'), 'population_manifest_sha256')
    _sha(ref.get('feature_extraction_receipt_sha256'), 'feature_extraction_receipt_sha256')
    return ids


def _sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(f'{name}: lowercase SHA-256 required')
    return value


def evaluate(ref, candidate, image_features, brain_features):
    """Caller authenticates the reference. CLI additionally verifies all file commitments."""
    ids = validate_reference(ref)
    if candidate.get('reference_manifest_digest') != digest(ref):
        raise ValueError('candidate is not bound to this reference manifest')
    candidate_ids = _ids(candidate.get('image_ids'), 'candidate image_ids', 300)
    if set(candidate_ids) != set(ids) or type(candidate.get('subject')) is not int or candidate.get('subject') != ref['subject']:
        raise ValueError('candidate population/subject differs from frozen reference')
    if candidate.get('feature_space') != ref['feature_space']:
        raise ValueError('candidate feature space mismatch')
    _sha(candidate.get('brain_features_sha256'), 'brain_features_sha256')
    _sha(candidate.get('checkpoint_sha256'), 'checkpoint_sha256')
    _sha(candidate.get('exposure_ledger_sha256'), 'exposure_ledger_sha256')
    b = _matrix(brain_features, 'brain_features', len(candidate_ids))
    i = _matrix(image_features, 'image_features', len(ids))
    if i.shape != b.shape:
        raise ValueError('feature dimension mismatch')
    # Feature dimensionality is externally admitted, not inferred from a metadata label.
    if i.shape[1] != 256 * 1664:
        raise ValueError('native retrieval token features require 256*1664 coordinates')
    order = {key: pos for pos, key in enumerate(candidate_ids)}
    b = b[[order[key] for key in ids]]
    result = score_aligned_features(ids, ref['retrieval_pools'], b, i)
    return {'task_id': TASK, 'scope': 'frozen_feature_retrieval_component',
            'reference_manifest_digest': digest(ref), 'candidate_manifest_digest': digest(candidate),
            'population_manifest_sha256': ref['population_manifest_sha256'],
            'subject': ref['subject'], 'n_images': len(ids),
            'pool_digest': digest(ref['retrieval_pools']), 'metrics': result,
            'scientific_qualification': False, 'full_contract_complete': False,
            'native_parity_verified': False, 'holds': HOLDS.copy()}


def score_aligned_features(ids, pools, brain, images):
    """Numerical kernel; small-coordinate controls do not establish native feature parity."""
    ids = _ids(ids, 'image_ids', 300)
    validate_pools(ids, pools)
    b, i = _matrix(brain, 'brain', len(ids)), _matrix(images, 'images', len(ids))
    if b.shape != i.shape:
        raise ValueError('paired features must agree')
    locations = {key: pos for pos, key in enumerate(ids)}
    result = {'image_retrieval': [], 'brain_retrieval': []}
    for pool in pools:
        selected = [locations[key] for key in pool]
        draw = retrieval_draw(b[selected], i[selected])
        for key, value in draw.items():
            result[key].append(value)
    return {key: _summary(value) for key, value in result.items()}


def paired_comparison(candidate_result, baseline_result):
    """Compare only same-reference results. Exposure equality needs the separate audit."""
    for key in ('reference_manifest_digest', 'pool_digest', 'subject', 'population_manifest_sha256'):
        if candidate_result.get(key) != baseline_result.get(key) or key not in candidate_result:
            raise ValueError(f'comparison mismatch: {key}')
    delta = {}
    for metric in ('image_retrieval', 'brain_retrieval'):
        a = np.asarray(candidate_result['metrics'][metric]['draw_values'], dtype=float)
        b = np.asarray(baseline_result['metrics'][metric]['draw_values'], dtype=float)
        if a.shape != (30,) or b.shape != (30,) or not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError('comparison requires thirty finite draw results per method')
        if np.any((a < 0) | (a > 1) | (b < 0) | (b > 1)):
            raise ValueError('retrieval accuracy outside [0,1]')
        delta[metric] = _summary(a - b)
    return {'candidate_minus_baseline': delta, 'equal_exposure_verified': False,
            'scientific_improvement_claim_supported': False}


def exposure_audit(ledger):
    """Audit declarations; cannot certify checkpoint contents or unreported exposure."""
    target = ledger.get('target_subject')
    if type(target) is not int or target not in range(1, 9):
        raise ValueError('target_subject must be integer 1..8')
    if type(ledger.get('calibration_session_zero_based')) is not int or ledger.get('calibration_session_zero_based') != 0:
        raise ValueError('one-session protocol uses first session (train/0.tar)')
    train = set(_ids(ledger.get('calibration_image_ids'), 'calibration_image_ids'))
    test = set(_ids(ledger.get('protected_image_ids'), 'protected_image_ids'))
    sessions = ledger.get('protected_sessions_zero_based')
    if not isinstance(sessions, list) or not sessions or any(type(s) is not int or s <= 0 for s in sessions):
        raise ValueError('protected sessions must exclude calibration session zero')
    subjects = ledger.get('checkpoint_pretraining_subjects')
    regime = ledger.get('training_regime')
    if regime not in ('released_shared_adaptation', 'single_subject_from_scratch'):
        raise ValueError('explicit training_regime required')
    expected = [x for x in range(1, 9) if x != target] if regime == 'released_shared_adaptation' else []
    if not isinstance(subjects, list) or any(type(x) is not int for x in subjects) or subjects != expected:
        raise ValueError('pretraining subject declaration conflicts with training regime')
    _sha(ledger.get('checkpoint_sha256'), 'checkpoint_sha256')
    _sha(ledger.get('image_model_resources_sha256'), 'image_model_resources_sha256')
    _sha(ledger.get('calibration_trial_manifest_sha256'), 'calibration_trial_manifest_sha256')
    _sha(ledger.get('protected_trial_manifest_sha256'), 'protected_trial_manifest_sha256')
    if 'checkpoint_pretraining_image_ids' not in ledger:
        raise ValueError('checkpoint_pretraining_image_ids must be declared or explicit null')
    pretrain = ledger.get('checkpoint_pretraining_image_ids')
    if pretrain is not None:
        pretrain = set(_ids(pretrain, 'checkpoint_pretraining_image_ids', 0))
        if regime == 'single_subject_from_scratch' and pretrain:
            raise ValueError('from-scratch neural pretraining image inventory must be empty')
    overlap = sorted(train & test)
    if overlap:
        raise ValueError('calibration/protected image leakage: ' + ','.join(overlap[:5]))
    return {'task_id': TASK, 'ledger_digest': digest(ledger),
            'calibration_test_overlap': [],
            'checkpoint_test_image_overlap': None if pretrain is None else sorted(pretrain & test),
            'pretraining_images_complete_declaration': pretrain is not None,
            'training_regime': regime,
            'shared_target_subject_absent_by_declaration': True,
            'actual_checkpoint_exposure_verified': False,
            'scientific_qualification': False,
            'holds': HOLDS.copy()}


def aggregate_repeat_embeddings(image_indices, embeddings):
    """Source recon_inference rule: average outputs, repeat missing trials to three.

    This accepts outputs after the neural model. Averaging neural inputs before the
    nonlinear model is a different operation and is never performed here.
    """
    raw = np.asarray(image_indices)
    if raw.ndim != 1 or raw.dtype.kind not in 'iu' or len(raw) == 0 or np.any(raw < 0):
        raise ValueError('NSD image indices must be a nonempty nonnegative integer vector')
    x = _matrix(embeddings, 'repeat embeddings', len(raw))
    unique = np.unique(raw)
    result = []
    for key in unique:
        locs = np.flatnonzero(raw == key)
        if len(locs) > 3:
            raise ValueError('source repeat aggregation expects one to three presentations')
        padded = np.tile(locs, 3)[:3]
        result.append(x[padded].mean(axis=0))
    return unique.tolist(), np.stack(result)


def compare_exposure(candidate, baseline):
    """Require equal declared target data and image-model resources; report neural pretraining separately."""
    ca, ba = exposure_audit(candidate), exposure_audit(baseline)
    for key in ('target_subject', 'calibration_session_zero_based',
                'protected_sessions_zero_based', 'image_model_resources_sha256',
                'calibration_trial_manifest_sha256', 'protected_trial_manifest_sha256'):
        if candidate.get(key) != baseline.get(key):
            raise ValueError('comparison exposure mismatch: ' + key)
    for key in ('calibration_image_ids', 'protected_image_ids'):
        if set(candidate[key]) != set(baseline[key]):
            raise ValueError('comparison exposure mismatch: ' + key)
    return {'target_data_and_image_resources_match_by_declaration': True,
            'checkpoint_identity_equal': candidate['checkpoint_sha256'] == baseline['checkpoint_sha256'],
            'candidate_audit': ca, 'baseline_audit': ba,
            'equal_total_neural_exposure_verified': False,
            'causal_code_benefit_claim_supported': False}


def required_adaptation_assets(subject):
    """Exact neural/index/image inputs for one-session retrieval branch, not full inference."""
    if type(subject) is not int or subject not in range(1, 9):
        raise ValueError('subject must be 1..8')
    return {'dataset_revision': DATA_REVISION, 'scope': 'one-session retrieval adaptation inputs',
            'required_paths': [f'betas_all_subj{subject:02d}_fp32_renorm.hdf5',
                               'coco_images_224_float16.hdf5',
                               f'wds/subj{subject:02d}/train/0.tar',
                               f'wds/subj{subject:02d}/new_test/0.tar',
                               f'train_logs/final_multisubject_subj{subject:02d}/last.pth'],
            'acquired': False, 'asset_content_hashes_verified': False,
            'full_native_inference_manifest_complete': False}


def _read_json(path):
    return json.loads(Path(path).read_text())


def _load_array(path, expected):
    _sha(expected, 'array_sha256')
    # NPY, not pickle or a downloaded model. Hash the exact bytes before parsing.
    with open(path, 'rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('array content SHA-256 mismatch')
    return np.load(path, allow_pickle=False, mmap_mode='r')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    score = sub.add_parser('score')
    for arg in ('reference', 'reference-sha256', 'candidate', 'image-features', 'brain-features'):
        score.add_argument('--' + arg, required=True)
    audit = sub.add_parser('audit-exposure')
    audit.add_argument('ledger')
    assets = sub.add_parser('required-assets')
    assets.add_argument('subject', type=int)
    args = parser.parse_args()
    if args.command == 'score':
        raw = Path(args.reference).read_bytes()
        if hashlib.sha256(raw).hexdigest() != _sha(args.reference_sha256, 'reference_sha256'):
            raise ValueError('trusted reference SHA-256 mismatch')
        ref, candidate = json.loads(raw), _read_json(args.candidate)
        result = evaluate(ref, candidate,
                          _load_array(args.image_features, ref['image_features_sha256']),
                          _load_array(args.brain_features, candidate['brain_features_sha256']))
    elif args.command == 'audit-exposure':
        result = exposure_audit(_read_json(args.ledger))
    else:
        result = required_adaptation_assets(args.subject)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

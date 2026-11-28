"""NeuroPictor prepared-tensor arithmetic panel; never a scientific admission grader.

Inputs are operator-produced, identity-bound image/feature exports. No downloads,
models, native transforms, or candidate code are executed. See the companion docs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from scipy.ndimage import gaussian_filter

TASK_ID = 'PAPER-paper-method-043'
SOURCE_COMMIT = 'b676b5be320ebb1b12919afd4cf6152e2c45db5d'
FEATURES = ('alexnet2', 'alexnet5', 'inception', 'clip', 'effnet', 'swav')
METRICS = ('pixcorr', 'ssim_2d_prospective', *FEATURES)
DISTANCES = ('effnet', 'swav')
ARRAYS = ('pixels425', *FEATURES)
HOLDS = [
    'Exact protected NSD image/session membership and exposure not independently qualified.',
    'Operator feature extraction, model weights, resizing and historical SSIM parity require native validation.',
    'Checkpoint ancestry, UKB/raw pretraining provenance, participant and stimulus overlap unresolved.',
    'NSD, COCO, encoder and diffusion model rights remain separate from deposit license.',
    'Primary grading metric, tolerance, competent reference, equal-access replay and full population admission remain unfrozen.',
    'No authentic data, model training, native campaign, baseline or scientific qualification established.',
]


class ValidationError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def _sha(value, name):
    _require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None,
             f'{name} must be a lowercase SHA-256')


def _numeric(x, name):
    a = np.asarray(x)
    _require(a.dtype.kind in 'fiu', f'{name}: real numeric array required')
    a = np.asarray(a, dtype=np.float64)
    _require(np.isfinite(a).all(), f'{name}: nonfinite data')
    return a


def _unit_rows(x):
    a = _numeric(x, 'features')
    _require(a.ndim == 2 and a.shape[0] >= 1 and a.shape[1] >= 2, 'features need [N,D>=2]')
    # Remove a row offset before scaling: scaling raw large values can round
    # away representable variation and turn equal Pearson features into wins.
    # Nearby finite values subtract accurately, including subnormal spreads.
    with np.errstate(over='ignore'):
        shifted = a - a[:, :1]
    overflow = ~np.isfinite(shifted).all(axis=1)
    if np.any(overflow):
        # Only rows spanning opposite finite extremes need this fallback.
        # A common positive factor cancels from Pearson correlation.
        shifted[overflow] = a[overflow] * .5 - a[overflow, :1] * .5
    scale = np.max(np.abs(shifted), axis=1, keepdims=True)
    a = shifted / np.where(scale == 0, 1, scale)
    a = a - a.mean(axis=1, keepdims=True)
    norm = np.linalg.norm(a, axis=1, keepdims=True)
    _require(np.all(norm > 0), 'constant row: Pearson correlation is undefined')
    return a / norm


def paired_correlation(real, pred):
    _require(np.shape(real) == np.shape(pred), 'paired feature shapes differ')
    return np.clip(np.sum(_unit_rows(real) * _unit_rows(pred), axis=1), -1, 1)


def two_way_identification(real, pred, block_size=128):
    """Per prediction j: fraction of other real i with corr(i,j) < corr(j,j).

    All distractors in the declared subject pool participate. Ties fail. Blocks
    bound temporary NxN storage without subsampling the reference population.
    """
    _require(np.shape(real) == np.shape(pred), 'paired feature shapes differ')
    r, p = _unit_rows(real), _unit_rows(pred)
    n = len(r)
    _require(n >= 2, 'two-way identification needs at least two stimuli')
    _require(type(block_size) is int and block_size > 0, 'invalid block size')
    scores = np.empty(n)
    for start in range(0, n, block_size):
        stop = min(n, start + block_size)
        similarities = np.clip(r @ p[start:stop].T, -1, 1)
        # Derive congruents from this same matrix to preserve exact tie semantics.
        congruents = similarities[np.arange(start, stop), np.arange(stop - start)]
        success = similarities < congruents[None, :]
        success[np.arange(start, stop), np.arange(stop - start)] = False
        scores[start:stop] = success.sum(axis=0) / (n - 1)
    return scores


def ssim_2d(real, pred):
    """Prospective explicit 2D grayscale SSIM, not legacy multichannel parity.

    Gaussian sigma=1.5, truncate=3.5 (11 pixels), population covariance,
    data_range=1, K1=.01, K2=.03, valid interior averaging (5-pixel crop).
    """
    x, y = _numeric(real, 'SSIM real'), _numeric(pred, 'SSIM pred')
    _require(x.shape == y.shape and x.ndim == 2 and min(x.shape) >= 11, 'SSIM needs matching 2D images >=11')
    _require(np.all((x >= 0) & (x <= 1)) and np.all((y >= 0) & (y <= 1)), 'SSIM range must be [0,1]')
    def blur(z):
        return gaussian_filter(z, sigma=1.5, truncate=3.5, mode='reflect')
    ux, uy = blur(x), blur(y)
    vx, vy, cov = blur(x*x)-ux*ux, blur(y*y)-uy*uy, blur(x*y)-ux*uy
    score = ((2*ux*uy + .01**2) * (2*cov + .03**2)) / ((ux*ux+uy*uy+.01**2) * (vx+vy+.03**2))
    return float(score[5:-5, 5:-5].mean())


def _samples(rows):
    _require(isinstance(rows, list) and len(rows) >= 2, 'samples must contain at least two records')
    keys, compound = [], set()
    for row in rows:
        _require(isinstance(row, dict), 'sample must be an object')
        for key in ('sample_id', 'subject_id', 'stimulus_id'):
            _require(isinstance(row.get(key), str) and row[key], f'missing {key}')
        sessions = row.get('session_ids')
        _require(isinstance(sessions, list) and len(sessions) > 0 and all(isinstance(s,str) and s for s in sessions)
                 and len(set(sessions)) == len(sessions), 'nonempty unique session_ids required')
        _require(row['sample_id'] not in keys, 'duplicate sample_id')
        pair = (row['subject_id'], row['stimulus_id'])
        _require(pair not in compound, 'duplicate subject/stimulus: only one reconstruction permitted')
        compound.add(pair)
        keys.append(row['sample_id'])
    return keys


def validate_protocol(protocol):
    _require(protocol.get('task_id') == TASK_ID, 'wrong task ID')
    _require(protocol.get('policy') == 'prospective-prepared-panel-v1', 'unsupported policy')
    _require(protocol.get('scope') in ('declared_subjects', 'paper_four_subjects'), 'explicit scope required')
    _sha(protocol.get('protected_pool_receipt_sha256'), 'protected pool receipt')
    _sha(protocol.get('exposure_ledger_sha256'), 'exposure ledger')
    _sha(protocol.get('rights_review_sha256'), 'rights review')
    _require(protocol.get('generation_policy') == 'one_sample_per_subject_stimulus', 'oracle/sample selection prohibited')
    _samples(protocol.get('samples'))
    groups = {}
    for row in protocol['samples']:
        groups.setdefault(row['subject_id'], set()).add(row['stimulus_id'])
    _require(all(len(g) >= 2 for g in groups.values()), 'each subject needs >=2 stimuli')
    if protocol['scope'] == 'paper_four_subjects':
        _require(set(groups) == {'1','2','5','7'}, 'paper scope requires subjects 1,2,5,7')
        _require(all(len(g) == 982 for g in groups.values()), 'paper scope requires 982 stimuli per subject')
        first = groups['1']
        _require(all(g == first for g in groups.values()), 'paper scope requires the same shared stimulus pool')
    extraction = protocol.get('extraction')
    _require(isinstance(extraction, dict), 'extraction receipts required')
    _require(extraction.get('pixel_policy') == 'source256_then425_rgb_chw_01', 'incorrect pixel preparation policy')
    _require(extraction.get('ssim_policy') == 'explicit_2d_gaussian_v1', 'SSIM policy required')
    for key in ('preprocessing_sha256', *[f'{f}_extractor_sha256' for f in FEATURES]):
        _sha(extraction.get(key), key)
    return groups


def _load_bundle(base, spec, samples, extraction):
    _require(isinstance(spec, dict), 'bundle spec must be an object')
    _sha(spec.get('sha256'), 'bundle hash')
    _require(spec.get('extraction') == extraction, 'extraction recipes differ')
    _require(isinstance(spec.get('path'), str) and spec['path'], 'bundle path required')
    path = (base / spec['path']).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            digest.update(chunk)
    _require(digest.hexdigest() == spec['sha256'], 'bundle bytes do not match hash')
    keys = _samples(spec.get('samples'))
    expected_keys = _samples(samples)
    _require(set(keys) == set(expected_keys), 'bundle population differs from protected pool')
    expected = {r['sample_id']: r for r in samples}
    _require(all(r == expected[r['sample_id']] for r in spec['samples']), 'subject/stimulus/session identity mismatch')
    order = [keys.index(k) for k in expected_keys]
    with np.load(path, allow_pickle=False) as data:
        _require(set(data.files) == set(ARRAYS), 'bundle needs exactly pixels425 and six feature arrays')
        arrays = {key: _numeric(data[key], key)[order] for key in ARRAYS}
        _require(all(len(data[key]) == len(keys) for key in ARRAYS), 'array row count mismatch')
    images = arrays['pixels425']
    _require(images.shape == (len(keys), 3, 425, 425), 'pixels425 must be [N,3,425,425]')
    _require(np.all((images >= 0) & (images <= 1)), 'pixels must already be clamped/scaled to [0,1]')
    for key in FEATURES:
        _unit_rows(arrays[key])
    return arrays


def metric_panel(real, pred):
    """One subject only. Returns all metric values per stimulus, never pooled IDs."""
    _require(all(np.shape(real[k]) == np.shape(pred[k]) for k in ARRAYS), 'real/pred shape mismatch')
    n = len(real['pixels425'])
    pixels = paired_correlation(real['pixels425'].reshape(n, -1), pred['pixels425'].reshape(n, -1))
    weights = np.array([.2125, .7154, .0721])
    rg = np.einsum('nchw,c->nhw', real['pixels425'], weights)
    pg = np.einsum('nchw,c->nhw', pred['pixels425'], weights)
    result = {'pixcorr': pixels, 'ssim_2d_prospective': np.array([ssim_2d(x,y) for x,y in zip(rg,pg)])}
    for key in FEATURES:
        result[key] = 1-paired_correlation(real[key],pred[key]) if key in DISTANCES else two_way_identification(real[key],pred[key])
    return result


def evaluate(manifest, base=Path('.')):
    protocol = manifest['protocol']
    groups = validate_protocol(protocol)
    base = Path(base)
    samples, extraction = protocol['samples'], protocol['extraction']
    reference = _load_bundle(base, manifest['reference'], samples, extraction)
    conditions = manifest.get('conditions')
    _require(isinstance(conditions, list) and len(conditions) == 3, 'three conditions required: pretrained,target_only,neural_free')
    _require({c.get('role') for c in conditions} == {'pretrained','target_only','neural_free'}, 'condition roles differ')
    names = [c.get('name') for c in conditions]
    _require(all(isinstance(n,str) and n for n in names) and len(set(names))==3, 'unique condition names required')
    matched = ('target_training_membership_sha256','diffusion_prior_sha256','tuning_budget_sha256','generation_budget_sha256','encoder_initialization_sha256')
    anchor = conditions[0]
    for c in conditions:
        for k in matched:
            _sha(c.get(k), k)
            _require(c[k] == anchor[k], f'unmatched comparator {k}')
        _sha(c.get('checkpoint_sha256'), 'checkpoint')
        _sha(c.get('initialization_exposure_sha256'), 'initialization exposure')
        _require(c.get('encoder_route') in ('released_encoder','raw_pretrained_encoder','random_init'), 'encoder route missing')
        _require(c['encoder_route'] == anchor['encoder_route'], 'encoder route differs; multi-subject effect confounded')
        route = c.get('image_pretraining_route')
        if c['role'] == 'pretrained':
            _require(route in ('raw_multi_subject','released_multi_subject_checkpoint'), 'pretrained route missing')
        else:
            _require(route == 'none', 'target-only/neural-free cannot use multi-subject checkpoint')
        _require(c.get('neural_input') == (c['role'] != 'neural_free'), 'neural-free control declaration mismatch')
    outputs = {}
    for c in conditions:
        prediction = _load_bundle(base, c['bundle'], samples, extraction)
        by_subject = {}
        for subject in sorted(groups):
            idx = [i for i,r in enumerate(samples) if r['subject_id'] == subject]
            panel = metric_panel({k:v[idx] for k,v in reference.items()}, {k:v[idx] for k,v in prediction.items()})
            by_subject[subject] = {'n':len(idx), 'sample_ids':[samples[i]['sample_id'] for i in idx],
                'mean':{k:float(v.mean()) for k,v in panel.items()}, 'per_stimulus':{k:v.tolist() for k,v in panel.items()}}
        outputs[c['role']] = {'name': c['name'], 'by_subject':by_subject,
            'macro_subject_mean':{k:float(np.mean([s['mean'][k] for s in by_subject.values()])) for k in METRICS},
            'image_pretraining_route':c['image_pretraining_route'], 'encoder_route':c['encoder_route']}
    deltas = {}
    for comparator in ('target_only','neural_free'):
        deltas[comparator] = {k:outputs['pretrained']['macro_subject_mean'][k]-outputs[comparator]['macro_subject_mean'][k] for k in METRICS}
    return {'task_id':TASK_ID, 'source_commit':SOURCE_COMMIT, 'status':'engineering_panel_only',
        'scope':protocol['scope'], 'n_subjects':len(groups), 'n_subject_stimuli':len(samples),
        'conditions':outputs, 'pretrained_minus_comparator':deltas,
        'directions':{k:'lower' if k in DISTANCES else 'higher' for k in METRICS},
        'research_qualified':False, 'native_equivalence_verified':False, 'full_contract_complete':False,
        'holds':HOLDS, 'receipt_limit':'Hashes and declarations bind supplied evidence; they do not independently verify its truth.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        content = args.manifest.read_bytes()
        result = evaluate(json.loads(content), args.manifest.resolve().parent)
        result['input_manifest_sha256'] = hashlib.sha256(content).hexdigest()
        result['runtime'] = {'numpy':np.__version__, 'scipy':__import__('scipy').__version__}
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    except (ValidationError, KeyError, OSError, ValueError, TypeError, IndexError) as exc:
        parser.exit(2, f'evaluation rejected: {exc}\n')


if __name__ == '__main__':
    main()

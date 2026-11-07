"""Bounded arbitrary-prediction parser and joint NLB forward-BPS scorer.

No candidate code executes. Public validation has no private-target loader.
Archive parsing adapts NEURAL-017's investigation/grade.py at SHA256
68d44651fee45d9eeb2632d8b94b9807f95faf40303c0bf73c260097adf63021.
The require/real_array/poisson_bits_per_spike functions below are copied unchanged
from authoring/nlb-cosmoothing/metrics.py, SHA256
f3552f46e7a684da0f9b7e49c0b28d22734c43a87d5f1151a305086c76c182b8.
The equation applies jointly to all forecast units, not only held-out units.
"""
from __future__ import annotations
import ast
import hashlib
import logging
import math
import os
from pathlib import Path
import stat
import zipfile
import numpy as np

MAX_PREDICTIONS = 34 * 1024**2
FIELDS = {'expected_counts', 'trial_ids', 'forecast_unit_ids', 'bin_left_edges_ms',
          'prediction_units', 'panel_fingerprint'}
PUBLIC_FIELDS = FIELDS - {'expected_counts'}
OFFICIAL_COMMIT = '42f8410b88e12db136910fa2f888b025ea0aa2ae'
OFFICIAL_SHA256 = '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'
OFFICIAL_URL = ('https://raw.githubusercontent.com/neurallatents/nlb_tools/'
                + OFFICIAL_COMMIT + '/nlb_tools/evaluation.py')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def real_array(value, name):
    array = np.asarray(value)
    require(array.dtype.kind in 'fiu', name+' must be real numeric, not bool/complex/object')
    return array.astype(np.float64, copy=False)


def poisson_bits_per_spike(target_counts, expected_counts, valid_mask=None):
    """Official co-bps equation, with strict declared submission-domain checks.

Rates mean expected spikes per bin, not Hz. The official null is the per-neuron
EVALUATION mean over valid trial/time bins; it is a scorer normalization, not a
trainable baseline. Exactly-zero null means are replaced by1e-9 as in nlb_tools.
Unlike upstream, zero/nonfinite predictions are rejected, never silently clipped.
All-zero observed target totals return a documented undefined score, not NaN/0.
"""
    y = real_array(target_counts, 'targets')
    lam = real_array(expected_counts, 'expected counts')
    require(y.ndim == 3 and all(n > 0 for n in y.shape) and y.shape == lam.shape,
            'Expected matching nonempty trial x bin x heldout-unit arrays')
    require(np.isfinite(lam).all() and (lam > 0).all(), 'Predictions must be finite and strictly positive')
    mask = np.ones(y.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    require(mask.dtype == np.bool_ and mask.shape == y.shape, 'Mask must be fixed boolean target shape')
    require(np.any(mask) and np.all(mask.sum(axis=(0,1)) > 0), 'No valid targets for at least one unit')
    observed = y[mask]
    require(np.isfinite(observed).all() and (observed >= 0).all() and
            (observed == np.floor(observed)).all() and (observed <= 2**53).all(),
            'Observed targets must be finite nonnegative integer spike counts')
    safe = np.where(mask, y, 0.0)
    totals = safe.sum(axis=(0,1),dtype=np.float64)
    means = totals / mask.sum(axis=(0,1))
    means[means == 0] = 1e-9
    nspikes = float(totals.sum())
    require(math.isfinite(nspikes), 'Target sum overflow')
    if nspikes == 0:
        return {'status':'undefined_zero_target_spikes','co_bps':None,'target_spikes':0.0,
                'valid_cells':int(mask.sum()),'null_policy':'evaluation_per_neuron_mean'}
    # Factorial terms cancel in log-likelihood ratio. Avoid lambda/mu overflow.
    mu = np.broadcast_to(means,y.shape)
    with np.errstate(over='ignore',invalid='ignore'):
        terms = observed * (np.log(lam[mask]) - np.log(mu[mask])) + mu[mask] - lam[mask]
        improvement_nats = float(np.sum(terms,dtype=np.float64))
    require(math.isfinite(improvement_nats), 'Likelihood ratio overflow/nonfinite')
    value = improvement_nats / (nspikes * math.log(2.0))
    require(math.isfinite(value), 'Nonfinite bits per spike')
    return {'status':'scored','co_bps':value,'target_spikes':nspikes,
            'valid_cells':int(mask.sum()),'null_policy':'evaluation_per_neuron_mean',
            'log_likelihood_improvement_nats':improvement_nats}


def regular(path, cap=MAX_PREDICTIONS):
    p = Path(path).absolute(); info = p.lstat()
    require(all(not q.is_symlink() for q in (p, *p.parents))
            and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and 0 < info.st_size <= cap, 'Bounded unlinked regular file required')
    return p


def _geometry(n_trials, n_units):
    require(type(n_trials) is int and 1 <= n_trials <= 574
            and type(n_units) is int and 1 <= n_units <= 182, 'Invalid task geometry')
    return {'expected_counts.npy': (n_trials, 40, n_units),
            'trial_ids.npy': (n_trials,), 'forecast_unit_ids.npy': (n_units,),
            'bin_left_edges_ms.npy': (40,), 'prediction_units.npy': (),
            'panel_fingerprint.npy': ()}


def _scalar_text(value, name):
    if isinstance(value, str):
        require(0 < len(value) <= 64, 'Invalid bounded scalar ' + name)
        return value
    a = np.asarray(value)
    require(a.shape == () and a.dtype.kind == 'U' and 0 < a.dtype.itemsize <= 256,
            'Invalid Unicode scalar ' + name)
    return _scalar_text(a.item(), name)


def candidate_npz(path, n_trials=574, n_units=182):
    """Validate all headers, lengths and CRCs before any NumPy payload allocation.

    The trusted wrapper must freeze/hash a private read-only candidate copy before
    calling. Test geometry is explicit; real dispatch must keep defaults574/182.
    """
    shapes = _geometry(n_trials, n_units)
    path = regular(path)
    before = path.stat()
    with path.open('rb') as source:
        opened = os.fstat(source.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                and opened.st_nlink == 1, 'Candidate changed while opening')
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            require(len(entries) == len(shapes)
                    and {e.filename for e in entries} == set(shapes),
                    'Wrong, duplicate or extra NPZ inventory')
            require(sum(e.file_size for e in entries) <= MAX_PREDICTIONS,
                    'Expanded prediction cap exceeded')
            for entry in entries:
                kind = stat.S_IFMT(entry.external_attr >> 16)
                require(not entry.is_dir() and kind in (0, stat.S_IFREG)
                        and not entry.flag_bits & 1
                        and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        'Linked, encrypted or unsupported ZIP member')
                with archive.open(entry) as member:
                    version = np.lib.format.read_magic(member)
                    require(version in ((1, 0), (2, 0)), 'Unsupported NPY version')
                    reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                              else np.lib.format.read_array_header_2_0)
                    shape, _, dtype = reader(member, max_header_size=10000)
                    require(shape == shapes[entry.filename] and not dtype.hasobject,
                            'Wrong NPY shape or object dtype')
                    if entry.filename == 'expected_counts.npy':
                        require(dtype.kind == 'f' and dtype.itemsize in (4, 8),
                                'Predictions must be float32 or float64')
                    elif entry.filename == 'bin_left_edges_ms.npy':
                        require(dtype.kind in 'fiu' and 0 < dtype.itemsize <= 8,
                                'Grid must be bounded real numeric')
                    else:
                        require(dtype.kind == 'U' and 0 < dtype.itemsize <= 256,
                                'IDs and metadata must be bounded Unicode')
                    remaining = math.prod(shape) * dtype.itemsize
                    require(member.tell() + remaining == entry.file_size,
                            'NPY declared payload length differs')
                    # Stream without ndarray creation to reject truncated payloads
                    # and CRC failures before any complete prediction allocation.
                    while remaining:
                        block = member.read(min(65536, remaining))
                        require(bool(block), 'Truncated NPY payload')
                        remaining -= len(block)
                    require(member.read(1) == b'', 'Trailing NPY member bytes')
        source.seek(0)
        with np.load(source, allow_pickle=False) as bundle:
            values = {name: bundle[name] for name in bundle.files}
        after = os.fstat(source.fileno())
        require((opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns, opened.st_nlink)
                == (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_nlink),
                'Candidate changed during validation')
    values['prediction_units'] = _scalar_text(values['prediction_units'], 'prediction units')
    values['panel_fingerprint'] = _scalar_text(values['panel_fingerprint'], 'panel fingerprint')
    return values


def _ids(value, count, name):
    a = np.asarray(value)
    require(a.shape == (count,) and a.dtype.kind == 'U' and 0 < a.dtype.itemsize <= 256,
            'Invalid bounded ' + name)
    items = a.tolist()
    require(all(items) and len(set(items)) == count, 'Empty or duplicate ' + name)
    return items


def validate_candidate(candidate, public, n_trials=574, n_units=182):
    """Public-only validation. Contains no target loading or private references."""
    _geometry(n_trials, n_units)
    require(set(candidate) == FIELDS and set(public) == PUBLIC_FIELDS, 'Wrong public/candidate schema')
    require(_scalar_text(candidate['prediction_units'], 'candidate units')
            == _scalar_text(public['prediction_units'], 'public units')
            == 'expected_spikes_per_bin', 'Wrong prediction units')
    fingerprint = _scalar_text(public['panel_fingerprint'], 'public panel')
    require(len(fingerprint) == 64 and all(x in '0123456789abcdef' for x in fingerprint),
            'Public fingerprint must be a SHA256 hex digest')
    require(_scalar_text(candidate['panel_fingerprint'], 'candidate panel') == fingerprint,
            'Wrong panel fingerprint')
    for field, count in (('trial_ids', n_trials), ('forecast_unit_ids', n_units)):
        require(set(_ids(candidate[field], count, 'candidate ' + field))
                == set(_ids(public[field], count, 'public ' + field)), 'Identity set differs: ' + field)
    canonical_grid = np.arange(450, 650, 5, dtype=np.int64)
    for name, value in (('candidate', candidate), ('public', public)):
        grid = np.asarray(value['bin_left_edges_ms'])
        require(grid.dtype.kind in 'fiu' and grid.dtype.itemsize <= 8
                and grid.shape == (40,) and np.isfinite(grid).all()
                and np.array_equal(grid, canonical_grid), name + ': wrong future grid')
    rates = np.asarray(candidate['expected_counts'])
    require(rates.dtype.kind == 'f' and rates.dtype.itemsize in (4, 8)
            and rates.shape == (n_trials, 40, n_units)
            and np.isfinite(rates).all() and np.all(rates > 0),
            'Finite strictly positive float32/64 rates required')
    return candidate


def load_validated_submission(path, public, n_trials=574, n_units=182):
    return validate_candidate(candidate_npz(path, n_trials, n_units), public, n_trials, n_units)


def _aligned(candidate, public, n_trials, n_units):
    validate_candidate(candidate, public, n_trials, n_units)
    rows = {identity: i for i, identity in enumerate(candidate['trial_ids'].tolist())}
    units = {identity: i for i, identity in enumerate(candidate['forecast_unit_ids'].tolist())}
    return candidate['expected_counts'][np.ix_(
        [rows[x] for x in public['trial_ids'].tolist()], np.arange(40),
        [units[x] for x in public['forecast_unit_ids'].tolist()])]


def evaluate(candidate, gold, fixed_condition, metric=None):
    """Score already-public-validated predictions after separate private loading.

    Any valid rate tensor is accepted, regardless of method family or gain sign.
    The caller owns pre-feedback freezing, source hashes and target isolation.
    """
    require(set(gold) == {'target_counts', 'trial_ids', 'unit_ids', 'bin_left_edges_ms',
                         'valid_mask', 'panel_fingerprint'}, 'Wrong private target schema')
    shape = np.shape(gold['target_counts'])
    require(len(shape) == 3 and shape[1] == 40, 'Wrong private forecast geometry')
    n_trials, _, n_units = shape; _geometry(n_trials, n_units)
    public = {'trial_ids': gold['trial_ids'], 'forecast_unit_ids': gold['unit_ids'],
              'bin_left_edges_ms': gold['bin_left_edges_ms'],
              'panel_fingerprint': gold['panel_fingerprint'],
              'prediction_units': 'expected_spikes_per_bin'}
    aligned = _aligned(candidate, public, n_trials, n_units)
    fixed_aligned = _aligned(fixed_condition, public, n_trials, n_units)
    fn = poisson_bits_per_spike if metric is None else metric
    scored = []
    for values in (aligned, fixed_aligned):
        item = dict(fn(gold['target_counts'], values, gold['valid_mask']))
        item['fp_bps'] = item.pop('co_bps')
        scored.append(item)
    left, right = scored
    defined = left['status'] == right['status'] == 'scored'
    delta = left['fp_bps'] - right['fp_bps'] if defined else None
    require(delta is None or math.isfinite(delta), 'Signed comparison overflow')
    return {'schema_version': 1,
            'status': 'scored_development_candidate' if defined else 'undefined_zero_target_spikes',
            'prediction_contract_valid': True, 'positive_gain_required': False,
            'reference_family_required': False, 'candidate': left,
            'fixed_condition_time': right, 'candidate_minus_condition_fp_bps': delta,
            'panel_fingerprint': _scalar_text(gold['panel_fingerprint'], 'gold panel'),
            'metric': 'Joint forward bits per spike across all forecast units/trials/bins',
            'candidate_code_executed_by_grader': False,
            'candidate_replay_verified': False, 'training_only_selection_verified': False,
            'scope': {'development_only': True, 'independent_animals': 1,
                      'animal_population_claim': False, 'causal_claim': False,
                      'neural_information_proven': False, 'benchmark_admission_claim': False},
            'interpretation': 'Continuous signed comparison on exposed single-session development; no significance or neural-understanding claim.'}


def scalar_bits_per_spike(target_counts, expected_counts, valid_mask=None):
    """Independent whole-vector scalar math.fsum likelihood-ratio calculation."""
    y = np.asarray(target_counts); rates = np.asarray(expected_counts)
    require(y.ndim == 3 and y.shape == rates.shape and all(x > 0 for x in y.shape)
            and y.dtype.kind in 'fiu' and rates.dtype.kind in 'fiu', 'Wrong scalar-check arrays')
    mask = np.ones(y.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    require(mask.dtype == np.bool_ and mask.shape == y.shape, 'Wrong scalar-check mask')
    require(np.isfinite(rates).all() and np.all(rates > 0), 'Invalid scalar-check rates')
    means, totals = [], []
    for unit in range(y.shape[-1]):
        values = y[:, :, unit][mask[:, :, unit]]
        require(len(values) > 0, 'Empty scalar-check unit')
        require(np.isfinite(values).all() and np.all(values >= 0)
                and np.all(values == np.floor(values)) and np.all(values <= 2**53),
                'Invalid scalar-check spike count')
        total = math.fsum(float(x) for x in values)
        totals.append(total); means.append(total / len(values) if total else 1e-9)
    total_spikes = math.fsum(totals)
    if total_spikes == 0:
        return {'status': 'undefined_zero_target_spikes', 'fp_bps': None,
                'target_spikes': 0.0, 'valid_cells': int(mask.sum())}
    log_means = [math.log(x) for x in means]; n_units = y.shape[-1]
    improvement = math.fsum(
        float(count) * (math.log(float(rate)) - log_means[i % n_units])
        + means[i % n_units] - float(rate)
        for i, (count, rate, valid) in enumerate(zip(y.flat, rates.flat, mask.flat)) if valid)
    value = improvement / (total_spikes * math.log(2.0))
    require(math.isfinite(value), 'Scalar-check nonfinite likelihood ratio')
    return {'status': 'scored', 'fp_bps': value, 'target_spikes': total_spikes,
            'valid_cells': int(mask.sum()), 'log_likelihood_improvement_nats': improvement,
            'summation': 'whole-vector math.fsum; independent scalar math.log'}


def official_functions(source_path, expected_sha=OFFICIAL_SHA256):
    """Extract only the two exact pinned official functions, without module import.

    Provenance: nlb_tools/evaluation.py at42f8410b88e12db136910fa2f888b025ea0aa2ae,
    lines209–276. Operator supplies the cached source; no network access occurs.
    scipy.special is an existing runtime dependency, imported only on this call.
    """
    require(expected_sha == OFFICIAL_SHA256, 'Only declared official source pin allowed')
    raw = regular(source_path, 100000).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, 'Official source hash differs')
    tree = ast.parse(raw)
    names = ('neg_log_likelihood', 'bits_per_spike')
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require(len(functions) == 2 and {x.name for x in functions} == set(names), 'Official function inventory differs')
    from scipy.special import gammaln
    namespace = {'np': np, 'gammaln': gammaln, 'logger': logging.getLogger('nlb-official-parity')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                 'pinned:nlb_tools/evaluation.py', 'exec'), namespace)
    return {name: namespace[name] for name in names}

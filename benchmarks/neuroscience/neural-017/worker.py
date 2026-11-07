"""Trusted isolated NPZ validator/scorer; never execute candidate code."""
from pathlib import Path
import hashlib, json, os, platform, resource, sys, tempfile, time
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'engine' / 'investigation'))
import grade


def public_axes(assets):
    item = assets['public']['packet']
    p = grade.regular('/input/public.npz', item['bytes'])
    grade.require(p.stat().st_size == item['bytes'] and grade.sha(p) == item['sha256'], 'Public asset changed')
    with np.load(p, allow_pickle=False) as z:
        grade.require(set(z.files) == set(item['fields']), 'Public field allowlist changed')
        return {k: z[k] for k in ('eval_trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'panel_fingerprint')}


def validate(path, axes, metric):
    candidate = grade.candidate_npz(path, 574, 45)
    grade.require(candidate['prediction_units'] == 'expected_spikes_per_bin', 'Wrong prediction units')
    grade.require(candidate['panel_fingerprint'] == grade.text(axes['panel_fingerprint'], 'public fingerprint'), 'Wrong panel fingerprint')
    for submitted, supplied in [('trial_ids', 'eval_trial_ids'), ('heldout_unit_ids', 'heldout_unit_ids')]:
        grade.require(set(metric.axis_ids(candidate[submitted], submitted)) == set(metric.axis_ids(axes[supplied], supplied)), 'Public trial/unit identity mismatch')
    grid = candidate['bin_left_edges_ms']
    grade.require(np.isfinite(grid).all() and np.array_equal(grid, axes['bin_left_edges_ms']), 'Wrong bin grid')
    rates = candidate['expected_counts']
    grade.require(np.isfinite(rates).all() and (rates > 0).all(), 'Expected counts must be finite and strictly positive')
    return candidate


def comparator(source):
    return {'expected_counts': source['rates_condition_psth'],
            'trial_ids': source['trial_ids'], 'heldout_unit_ids': source['heldout_unit_ids'],
            'bin_left_edges_ms': source['bin_left_edges_ms'],
            'prediction_units': grade.text(source['prediction_units'], 'comparator units'),
            'panel_fingerprint': grade.text(source['panel_fingerprint'], 'comparator fingerprint')}


def main():
    start = time.monotonic()
    action = sys.argv[1]
    assets = json.loads((HERE / 'assets.json').read_text())
    result = {'benchmark_id': 'NEURAL-017', 'status': 'started', 'target_loader_invocations': 0,
              'candidate_code_executed': False, 'model_fits': 0, 'scientific_success_threshold': None}
    try:
        grade.require(platform.python_version() == '3.12.8' and np.__version__ == '2.2.6', 'Runtime version differs')
        metric = grade.metric_module(assets['source_pins']['metrics.py']['sha256'])
        axes = public_axes(assets)
        checks = []
        if action == 'verify':
            with tempfile.TemporaryDirectory(dir='/tmp') as temp:
                empty = Path(temp) / 'empty.npz'; empty.write_bytes(b'')
                invalid = Path(temp) / 'invalid.npz'
                np.savez(invalid, expected_counts=np.ones((1, 1, 1)), trial_ids=np.array(['invalid']),
                         heldout_unit_ids=np.array(['invalid']), bin_left_edges_ms=np.array([0]),
                         prediction_units=np.array('expected_spikes_per_bin'), panel_fingerprint=np.array('invalid'))
                for name, path in [('empty', empty), ('invalid_shape', invalid)]:
                    try:
                        validate(path, axes, metric)
                    except (ValueError, OSError) as exc:
                        checks.append({'case': name, 'rejected': True, 'reason': str(exc), 'target_loader_invocations': 0})
                    else:
                        raise ValueError('Malformed fixture accepted: ' + name)
        else:
            # Freeze once into bounded private scratch before parsing or target access.
            frozen = Path('/tmp/submission.npz')
            consumed = 0; sha = hashlib.sha256()
            with Path('/input/submission.npz').open('rb') as src, frozen.open('xb') as dst:
                while block := src.read(1048576):
                    consumed += len(block); grade.require(consumed <= grade.MAX_PREDICTIONS, 'Submission grew past cap')
                    sha.update(block); dst.write(block)
            frozen.chmod(0o400)
            grade.require(sha.hexdigest() == os.environ['EXPECTED_SUBMISSION_SHA256'], 'Submission changed after operator binding')
            candidate = validate(frozen, axes, metric)
            result['submission_sha256'] = sha.hexdigest()
            if action == 'validate':
                result.update(status='valid_prediction_contract', prediction_contract_valid=True,
                              scientific_score_computed=False, scientific_success=None)
                return result, 0
        ref = assets['private']['comparator']
        keys = ['rates_condition_psth', 'trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'prediction_units', 'panel_fingerprint']
        if action == 'verify': keys.append('rates_glm')
        source = grade.pinned_operator('/input/reference.npz', ref['sha256'], keys, ref['bytes'])
        fixed = comparator(source)
        if action == 'verify':
            with tempfile.TemporaryDirectory(dir='/tmp') as temp:
                path = Path(temp) / 'reference_submission.npz'
                bundle = dict(fixed, expected_counts=source['rates_glm'])
                np.savez(path, **bundle)
                candidate = validate(path, axes, metric)
                result['reference_submission_sha256'] = grade.sha(path)
                result['temporary_submission_bytes'] = path.stat().st_size
        gold_item = assets['private']['targets']
        result['target_loader_invocations'] += 1
        gold = grade.pinned_operator('/input/gold.npz', gold_item['sha256'],
            ['counts_heldout', 'trial_ids', 'unit_ids', 'valid_mask', 'panel_fingerprint'], gold_item['bytes'])
        score = grade.evaluate(candidate, gold, fixed, metric)
        result.update(status='scored', score=score, scientific_score_computed=True, scientific_success=None,
                      primary_metric=score['candidate']['co_bps'], metric_name='co_bps', higher_is_better=True,
                      comparator_delta=score['candidate_minus_condition_co_bps'])
        if action == 'verify':
            expected = assets['verification_expected']
            for got, key in [(result['primary_metric'], 'glm_co_bps'),
                             (score['fixed_condition_time']['co_bps'], 'condition_co_bps'),
                             (result['comparator_delta'], 'glm_minus_condition_co_bps')]:
                grade.require(abs(got - expected[key]) <= expected['absolute_tolerance'], 'Stored reference score parity failed: ' + key)
            result.update(status='reference_and_rejection_verification_passed', cases=checks,
                          reference_score_parity=True, old_reference_outputs_reused=True,
                          no_candidate_attempt=True, biological_unit='one Jenkins macaque recording session')
        return result, 0
    except Exception as exc:
        result.update(status='rejected_no_score' if action != 'verify' else 'verification_failed_no_retry',
                      error=type(exc).__name__ + ': ' + str(exc), scientific_score_computed=False)
        return result, 2
    finally:
        u = resource.getrusage(resource.RUSAGE_SELF)
        result['worker_resources'] = {'elapsed_seconds': time.monotonic() - start,
            'cpu_seconds_including_imports': u.ru_utime + u.ru_stime,
            'peak_rss_bytes_linux': u.ru_maxrss * 1024,
            'cgroup_memory_peak_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text())}


if __name__ == '__main__':
    result, code = main()
    print(json.dumps(result, allow_nan=False, separators=(',', ':')))
    raise SystemExit(code)

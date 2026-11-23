"""Complete four-method empirical producer; authentic admission is external.

Importing this module uses only the standard library. Scientific dependencies
and the pinned author's code are loaded only by AuthorBackend's constructor.
"""
import argparse
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
import types

METHODS = ('acf_full', 'isttc_full', 'pearsonr_trial_avg', 'sttc_trial_concat')
FS = 30000
SIGNAL_TICKS = 30 * 60 * FS
TRIAL_TICKS = FS
N_TRIALS = 40
N_UNITS = 5775
N_MICE = 26
COMMIT = 'e78cfd2b2ea79b7a7e707db7b79e218212497e43'
BRIDGE_SHA256 = '63d41e13b7300f6ba1dc845be9c7fb7dba167c4b44c99b2f869930f42522dd40'
SOURCE_HASHES = {
    'src/isttc/scripts/calculate_acf.py': 'e19fa6241c3ac8a7a9de5c4eb03d1791f0cc57a8bd2e3fd11ec041f864d575c9',
    'src/isttc/scripts/calculate_tau.py': 'cf8f6488f1af1f92815b117603de947939211d4e5a68fa30c9f5b9aa0a7072e0',
    'src/isttc/scripts/spike_train_utils.py': '6a7ba6ac8d4eda4a9c3c4e1cdd8a49642224129398a7d2cecfbd43c48dc77668',
}
MAX_METADATA_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024 * 1024
WINDOW_SCOPE = 'prospective_published_protocol_not_historical_rng_recovery'


class BackendProtocolError(ValueError):
    """Source/interface mismatch: stop, rather than masquerade as a failed fit."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError('nonfinite JSON literal')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=bad_constant)


def exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(label + ': exact fields required')


def _verified_module(path, sha256, name):
    """Execute precisely the verified bytes; never import a mutable reread."""
    path = Path(path)
    with path.open('rb') as stream:
        body = stream.read(MAX_METADATA_BYTES + 1)
    if len(body) > MAX_METADATA_BYTES or hashlib.sha256(body).hexdigest() != sha256:
        raise ValueError('source bytes differ: ' + str(path))
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def bridge():
    path = Path(__file__).resolve().parent.parent / 'empirical-diagnostics' / 'empirical_bridge.py'
    return _verified_module(path, BRIDGE_SHA256, '_isttc_empirical_contract')


class AuthorBackend:
    """Pinned official helpers, paper-specific calls, observed dependencies.

    Construction imports scientific dependencies. It does not download, install,
    acquire data, import notebook state, or invoke the upstream driver script.
    """
    def __init__(self, checkout):
        import importlib.metadata
        import numpy
        from statsmodels.tsa.stattools import acf
        root = Path(checkout)
        # Verify every selected file before executing any author module.
        for relative, expected in SOURCE_HASHES.items():
            with (root / relative).open('rb') as stream:
                body = stream.read(MAX_METADATA_BYTES + 1)
            if len(body) > MAX_METADATA_BYTES or hashlib.sha256(body).hexdigest() != expected:
                raise ValueError('author source differs: ' + relative)
        self.np = numpy
        self.acf = acf
        self.curves = _verified_module(root / 'src/isttc/scripts/calculate_acf.py',
                                      SOURCE_HASHES['src/isttc/scripts/calculate_acf.py'], '_isttc_curves')
        self.fitter = _verified_module(root / 'src/isttc/scripts/calculate_tau.py',
                                      SOURCE_HASHES['src/isttc/scripts/calculate_tau.py'], '_isttc_fitter')
        self.spikes = _verified_module(root / 'src/isttc/scripts/spike_train_utils.py',
                                      SOURCE_HASHES['src/isttc/scripts/spike_train_utils.py'], '_isttc_spikes')
        self.identity = {
            'kind': 'pinned_official_helpers', 'commit': COMMIT,
            'source_sha256': dict(SOURCE_HASHES),
            'dependency_versions': {name: importlib.metadata.version(name) for name in
                                    ('numpy', 'scipy', 'scikit-learn', 'statsmodels')},
        }

    def fit(self, method, spike_ticks, trials):
        """Return tau in 50-ms lag bins, R-squared, upstream fit message."""
        if method == 'acf_full':
            binned = self.spikes.bin_spike_train_fixed_len(
                spike_ticks, 50, FS, SIGNAL_TICKS, verbose_=False)
            curve = self.acf(binned, nlags=20)
        elif method == 'isttc_full':
            curve = self.curves.acf_sttc(self.np.asarray(spike_ticks), 20,
                lag_shift_=1500, sttc_dt_=750, signal_length_=SIGNAL_TICKS, verbose_=False)
        elif method == 'pearsonr_trial_avg':
            binned = self.spikes.bin_trials(trials, TRIAL_TICKS, 1500)
            _, curve = self.curves.acf_pearsonr_trial_avg(binned, 20, verbose_=False)
        elif method == 'sttc_trial_concat':
            curve = self.curves.acf_sttc_trial_concat(
                [self.np.asarray(trial) for trial in trials], n_lags_=20,
                lag_shift_=1500, sttc_dt_=750, trial_len_=TRIAL_TICKS,
                zero_padding_len_=90000, verbose_=False)
        else:
            raise ValueError('unknown method')
        expected = 21 if method in METHODS[:2] else 20
        if len(curve) != expected:
            raise BackendProtocolError('upstream ACF support differs from selected source')
        fit = self.fitter.fit_single_exp(curve, start_idx_=1, exp_fun_=self.fitter.func_single_exp)
        if len(fit) != 7:
            raise BackendProtocolError('upstream fitter return shape')
        return fit[2], fit[4], fit[6]


def validate_windows(cohort, rows):
    if type(rows) is not list or len(rows) != N_UNITS:
        raise ValueError('complete 5775-unit windows required')
    result = {}
    seed = None
    for unit, row in zip(cohort['units'], rows):
        exact(row, ('unit_id', 'replicate', 'windows_ticks', 'fs_hz', 'signal_ticks',
                    'draw_scope', 'seed'), 'window record')
        if row['unit_id'] != unit['unit_id'] or row['unit_id'] in result:
            raise ValueError('window population/order differs')
        if (type(row['replicate']) is not int or row['replicate'] != 0 or
                type(row['fs_hz']) is not int or row['fs_hz'] != FS or
                type(row['signal_ticks']) is not int or row['signal_ticks'] != SIGNAL_TICKS or
                row['draw_scope'] != WINDOW_SCOPE):
            raise ValueError('window scope or clock differs')
        if type(row['seed']) is not int or not 0 <= row['seed'] < 2**64:
            raise ValueError('window seed must be uint64')
        if seed is None:
            seed = row['seed']
        if row['seed'] != seed:
            raise ValueError('one frozen prospective seed required')
        windows = row['windows_ticks']
        if type(windows) is not list or len(windows) != N_TRIALS:
            raise ValueError('exactly 40 windows required')
        for window in windows:
            if (type(window) is not list or len(window) != 2 or
                    any(type(v) is not int for v in window) or window[0] < 0 or
                    window[1] - window[0] != TRIAL_TICKS or window[1] > SIGNAL_TICKS):
                raise ValueError('one-second half-open window outside recording')
        result[row['unit_id']] = windows
    return result


def validate_recording(row, unit):
    exact(row, ('schema', 'unit_id', 'fs_hz', 'signal_ticks', 'spike_ticks'), 'recording')
    if (row['schema'] != 'isttc_empirical_spikes_v1' or row['unit_id'] != unit['unit_id'] or
            type(row['fs_hz']) is not int or row['fs_hz'] != FS or
            type(row['signal_ticks']) is not int or row['signal_ticks'] != SIGNAL_TICKS):
        raise ValueError('recording unit, clock or extent differs')
    values = row['spike_ticks']
    if type(values) is not list or any(type(v) is not int or not 0 <= v < SIGNAL_TICKS for v in values):
        raise ValueError('spikes require integer ticks inside half-open recording')
    if any(a > b for a, b in zip(values, values[1:])):
        raise ValueError('spike timestamps must be sorted')
    # Empty signals and repeated timestamps remain scientific inputs, not exclusions.
    return values


def _fit_row(unit_id, method, backend, ticks, trials):
    try:
        result = backend.fit(method, ticks, trials)
        if type(result) not in (tuple, list) or len(result) != 3:
            raise BackendProtocolError('backend fit requires exactly three outputs')
        tau, r_squared, message = result
        # Preserve partial/failed fields, zero/negative R2 and finite tau unchanged.
        values = []
        for value, scale in ((tau, 50), (r_squared, 1)):
            if isinstance(value, bool) or not isinstance(value, Real):
                raise BackendProtocolError('real numeric fit output required')
            number = float(value)
            values.append(number if math.isfinite(number) and math.isfinite(number * scale) else None)
        tau, r_squared = values
        reason = None if all(v is not None for v in values) else ('nonfinite fit: ' + str(message))[:1024]
    except BackendProtocolError:
        raise
    except (ValueError, RuntimeError, OverflowError, FloatingPointError, ZeroDivisionError) as exc:
        tau = r_squared = None
        reason = ('backend ' + type(exc).__name__ + ': ' + str(exc))[:1024]
    return {'unit_id': unit_id, 'method': method, 'tau_bins': tau,
            'r_squared': r_squared, 'failure_reason': reason}


def produce(cohort, recordings, windows, backend):
    """Consume the complete ordered recording stream; return all 23,100 fits.

    No output is returned if a recording is malformed, missing, extra or reordered.
    Backend scientific failures remain explicit rows and do not remove units.
    """
    contract = bridge()
    units = contract.cohort(cohort)
    by_unit = validate_windows(cohort, windows)
    # Validate the claimed prospective sampling realization as well as its
    # extent; arbitrary favorable windows cannot inherit the seed's identity.
    for supplied, expected in zip(windows, contract.window_rows(cohort, windows[0]['seed'])):
        if supplied != expected:
            raise ValueError('windows differ from the declared prospective seed')
    iterator = iter(recordings)
    rows = []
    input_hashes = []
    for unit in units:
        try:
            recording = next(iterator)
        except StopIteration as exc:
            raise ValueError('recording population incomplete') from exc
        ticks = validate_recording(recording, unit)
        input_hashes.append({'unit_id': unit['unit_id'], 'sha256': digest(recording)})
        trials = contract.slice_trials(ticks, by_unit[unit['unit_id']])
        for method in METHODS:
            rows.append(_fit_row(unit['unit_id'], method, backend, ticks, trials))
    try:
        next(iterator)
    except StopIteration:
        pass
    else:
        raise ValueError('extra recording outside assigned population')
    estimates = {'schema': 'isttc_empirical_estimates_v1', 'rows': rows}
    contract.estimate_rows(estimates, units)
    receipt = {
        'schema': 'isttc_empirical_producer_receipt_v1', 'task_id': 'PAPER-paper-method-add-004',
        'cohort_sha256': digest(cohort), 'windows_sha256': digest(windows),
        'normalized_recordings': input_hashes, 'estimates_sha256': digest(estimates),
        'backend': backend.identity, 'units': N_UNITS, 'mice': N_MICE,
        'fit_coordinates': len(rows), 'fit_rows_with_missing_fields': sum(row['failure_reason'] is not None for row in rows),
        'authentic_cohort_qualified': False, 'historical_rng_recovered': False,
        'native_numerical_parity_qualified': False, 'paper_reproduction_pass': None,
        'scope': 'complete_four_estimator_fig7c_fit_production_not_glms_or_entire_paper',
    }
    return estimates, receipt


def read_json(path, limit=MAX_METADATA_BYTES):
    with Path(path).open('rb') as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError('input byte bound exceeded')
    return strict_json(body)


def read_jsonl(path, limit):
    with Path(path).open('rb') as stream:
        for line in iter(lambda: stream.readline(limit + 1), b''):
            if len(line) > limit:
                raise ValueError('JSONL record byte bound exceeded')
            if not line.strip():
                raise ValueError('blank JSONL record')
            yield strict_json(line)


def read_windows(path):
    rows = []
    for row in read_jsonl(path, 32768):
        if len(rows) == N_UNITS:
            raise ValueError('extra window outside assigned population')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', required=True, type=Path)
    parser.add_argument('--recordings-jsonl', required=True, type=Path)
    parser.add_argument('--windows-jsonl', required=True, type=Path)
    parser.add_argument('--author-checkout', required=True, type=Path)
    parser.add_argument('--output-directory', required=True, type=Path)
    args = parser.parse_args()
    if args.output_directory.exists():
        raise ValueError('output directory must be absent')
    cohort = read_json(args.cohort)
    windows = read_windows(args.windows_jsonl)
    # Reject malformed declarations before loading any scientific dependency.
    bridge().cohort(cohort)
    validate_windows(cohort, windows)
    estimates, receipt = produce(cohort,
        read_jsonl(args.recordings_jsonl, MAX_RECORD_BYTES), windows, AuthorBackend(args.author_checkout))
    args.output_directory.mkdir()
    for name, value in (('estimates.json', estimates), ('receipt.json', receipt)):
        with (args.output_directory / name).open('x') as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.write('\n')
    # Both files and successful process termination are required. Existence of
    # either file alone is not an atomic publication or durability guarantee.


if __name__ == '__main__':
    main()

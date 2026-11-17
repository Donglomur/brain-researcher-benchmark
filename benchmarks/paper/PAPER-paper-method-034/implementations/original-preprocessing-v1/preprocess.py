"""Explicit released MARBLE preprocessing, without a fitted MARBLE/CEBRA model.

The default smoothing path calls Elephant itself. No Gaussian approximation or
paper-recipe repair is substituted when that dependency is unavailable.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import inspect
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA

from inputs import (CONSISTENCY, DECODING, LAYOUTS, PAPER, RATS, SOURCE_SHA256,
                    InputError, SourceViews, array_pin, is_sha, read_bytes, read_json,
                    read_release, recipe_support, require, save_array, sha256,
                    source_rows, write_json)


class ElephantBackend:
    """Exact published calls under an explicitly frozen installed runtime."""

    PACKAGES = ('elephant', 'neo', 'quantities', 'numpy', 'scipy', 'scikit-learn')

    def __init__(self, expected_versions):
        require(type(expected_versions) is dict and set(expected_versions) == set(self.PACKAGES)
                and all(type(v) is str and v for v in expected_versions.values()),
                'explicit complete installed runtime version map required')
        actual = {name: importlib.metadata.version(name) for name in self.PACKAGES}
        require(actual == expected_versions, 'installed numerical runtime differs from frozen versions')
        from elephant.kernels import GaussianKernel
        from elephant.statistics import instantaneous_rate
        from quantities import ms
        import neo
        self.ms, self.neo, self.instantaneous_rate = ms, neo, instantaneous_rate
        self.kernel = GaussianKernel(10 * ms)
        defaults = {name: repr(parameter.default) for name, parameter in inspect.signature(instantaneous_rate).parameters.items()
                    if parameter.default is not inspect.Parameter.empty and name not in ('kernel', 'sampling_period')}
        self.provenance = {'implementation': 'installed-elephant-original-call', 'versions': actual,
            'instantaneous_rate_signature': str(inspect.signature(instantaneous_rate)),
            'GaussianKernel_signature': str(inspect.signature(GaussianKernel)),
            'instantaneous_rate_module_sha256': sha256(read_bytes(inspect.getfile(instantaneous_rate), 4 * 1024**2)),
            'GaussianKernel_module_sha256': sha256(read_bytes(inspect.getfile(GaussianKernel), 4 * 1024**2)),
            'inherited_runtime_defaults': defaults, 'historical_paper_runtime_verified': False,
            'sampling_period_ms': 1.0, 'sigma_ms': 10.0,
            'rate_unit': 'Hz on source helper pseudo-millisecond clock, not physical recording Hz'}

    def __call__(self, event_indices, length):
        train = self.neo.SpikeTrain(event_indices, units='ms', t_stop=length)
        return self.instantaneous_rate(train, kernel=self.kernel,
                                       sampling_period=1.0 * self.ms).magnitude


def source_rates(neural, backend):
    """One event per nonzero bin; time×neuron input, time×neuron output."""
    neural = np.asarray(neural)
    require(neural.ndim == 2 and 2 <= len(neural) <= 10000 and 1 <= neural.shape[1] <= 120
            and neural.dtype.kind in 'fiu' and np.isfinite(neural).all(), 'finite time×neuron source activity required')
    require(callable(backend) and type(getattr(backend, 'provenance', None)) is dict,
            'named rate backend with explicit provenance required')
    # Ensure provenance cannot smuggle arrays/nonfinite objects into receipts.
    import json
    json.dumps(backend.provenance, allow_nan=False)
    values = []
    event_counts = []
    for column in range(neural.shape[1]):
        events = np.flatnonzero(neural[:, column])
        result = np.asarray(backend(events, len(neural)))
        require(result.shape == (len(neural), 1) and result.dtype.kind == 'f'
                and np.isfinite(result).all(), 'rate backend changed original time support or returned invalid rates')
        values.append(result.T)
        event_counts.append(len(events))
    rates = np.vstack(values).T
    diagnostic = {'input_shape_time_neuron': list(neural.shape),
        'nonzero_events_per_neuron': event_counts,
        'negative_values': int(np.count_nonzero(neural < 0)),
        'nonintegral_values': int(np.count_nonzero(neural != np.trunc(neural))),
        'nonzero_values_with_magnitude_other_than_one': int(np.count_nonzero((neural != 0) & (neural != 1))),
        'magnitude_policy': 'all nonzero values create exactly one event; no spike-count expansion',
        'native_elephant_backend_used': type(backend) is ElephantBackend,
        'backend': backend.provenance, 'rates': array_pin(rates)}
    return rates, diagnostic


def project_segment(rates, row_ids, pca_components, pca=None):
    """Preserve source PCA defaults and the forward-difference terminal loss."""
    rates = np.asarray(rates)
    require(rates.ndim == 2 and 2 <= len(rates) <= 10000 and 1 <= rates.shape[1] <= 120
            and rates.dtype.kind == 'f' and np.isfinite(rates).all(), 'finite rate matrix with derivative support required')
    require(type(row_ids) is list and len(row_ids) == len(rates) and len(set(row_ids)) == len(row_ids)
            and all(type(x) is str and x for x in row_ids), 'complete unique ordered source row IDs required')
    require(type(pca_components) is int and 1 <= pca_components <= min(rates.shape), 'invalid source PCA dimension')
    fitting = pca is None
    if fitting:
        pca = PCA(n_components=pca_components)
        coordinates = pca.fit_transform(rates)
    else:
        require(type(pca) is PCA and pca.n_components_ == pca_components
                and pca.n_features_in_ == rates.shape[1] and pca.whiten is False,
                'query requires the unchanged source-trained PCA')
        coordinates = pca.transform(rates)
    require(coordinates.shape == (len(row_ids), pca_components) and np.isfinite(coordinates).all(),
            'PCA changed source row support')
    anchor, vector = coordinates[:-1], np.diff(coordinates, axis=0)
    return {'anchor': anchor, 'vector': vector, 'row_ids': row_ids[:-1],
            'forward_partner_row_ids': row_ids[1:], 'input_row_ids': list(row_ids),
            'omitted_terminal_anchor': row_ids[-1], 'pca_fitted_here': fitting,
            'source_difference': 'next coordinate minus current coordinate; no division by time'}, pca


def pca_receipt(pca, fit_row_ids):
    require(type(pca) is PCA and pca.whiten is False and pca.n_samples_ == len(fit_row_ids),
            'PCA fit membership mismatch')
    return {'class': 'sklearn.decomposition.PCA', 'components': int(pca.n_components_),
            'whiten': False, 'requested_solver': pca.svd_solver,
            'realized_solver': pca._fit_svd_solver, 'random_state_parameter': pca.random_state,
            'fit_row_ids': list(fit_row_ids), 'mean': array_pin(pca.mean_),
            'components_matrix': array_pin(pca.components_),
            'explained_variance': array_pin(pca.explained_variance_),
            'singular_values': array_pin(pca.singular_values_),
            'runtime_sklearn': importlib.metadata.version('scikit-learn'),
            'historical_seed_or_PCA_state_verified': False}


def graph_arguments(segment):
    """The exact released helper call; graph construction is separately run."""
    anchor, vector = np.asarray(segment['anchor']), np.asarray(segment['vector'])
    require(anchor.ndim == 2 and anchor.shape == vector.shape and len(anchor) == len(segment['row_ids'])
            and np.isfinite(anchor).all() and np.isfinite(vector).all(), 'invalid source graph support')
    return {'anchor': anchor, 'vector': vector, 'k': 15, 'delta': 1.5}


def construct_source_graph(segment, construct_dataset):
    """Trusted operator callback; does not claim an installed MARBLE runtime."""
    require(callable(construct_dataset), 'source graph constructor required')
    return construct_dataset(**graph_arguments(segment))


def released_decoding(neural, row_ids, backend):
    require(np.shape(neural) == (10000, 120) and row_ids == source_rows('achilles', 0, 10000),
            'complete original Achilles decoding input required')
    train_rates, train_log = source_rates(neural[:8000], backend)
    test_rates, test_log = source_rates(neural[8000:], backend)
    training, pca = project_segment(train_rates, row_ids[:8000], 20)
    query, applied_pca = project_segment(test_rates, row_ids[8000:], 20, pca)
    require(applied_pca is pca, 'query unexpectedly replaced the trained PCA')
    return {'recipe': recipe_support(DECODING), 'segments': {'training': training, 'query': query},
            'rate_diagnostics': {'training': train_log, 'query': test_log},
            'pca': pca, 'pca_receipt': pca_receipt(pca, row_ids[:8000]),
            'figure5d_bridge_refusal': 'Released MARBLE produces 1999 query anchors; original Figure5d requires 2000.'}


def released_consistency(neural, row_ids, backend, rat):
    n, channels = LAYOUTS[rat]['neural'][0]
    require(np.shape(neural) == (n, channels) and row_ids == source_rows(rat, 0, n),
            'complete original consistency input required')
    rates, diagnostic = source_rates(neural, backend)
    whole, pca = project_segment(rates, row_ids, 10)
    return {'recipe': recipe_support(CONSISTENCY, rat), 'segments': {'whole': whole},
            'rate_diagnostics': {'whole': diagnostic}, 'pca': pca,
            'pca_receipt': pca_receipt(pca, row_ids),
            'figure5d_bridge_refusal': 'Four-rat PCA10 consistency is the distinct Figure5e population.'}


def export_preprocessed(result, destination, *, source_authentication):
    """Retain anchors, differences, source IDs, PCA state and complete support."""
    require(source_authentication in ('publisher_sha256', 'generated_control_views'), 'explicit source authentication scope required')
    destination = Path(destination)
    require(not destination.exists(), 'fresh preprocessing destination required')
    destination.mkdir(mode=0o700)
    record = {'schema': 'marble-released-preprocessing/v1', 'source_sha256': SOURCE_SHA256,
              'source_authentication': source_authentication, 'recipe': result['recipe'],
              'segments': {}, 'rate_diagnostics': result['rate_diagnostics'],
              'pca': result['pca_receipt'], 'pca_arrays': {},
              'figure5d_bridge_refusal': result['figure5d_bridge_refusal'],
              'qualification': 'preprocessing_adapter_not_native_runtime_or_original_paper_admission',
              'native_smoothing_executed': all(row['native_elephant_backend_used'] for row in result['rate_diagnostics'].values()),
              'PCA_fit_run': True, 'MARBLE_or_CEBRA_model_fit_run': False}
    for name, segment in result['segments'].items():
        record['segments'][name] = {key: value for key, value in segment.items() if key not in ('anchor', 'vector')}
        record['segments'][name]['arrays'] = {key: save_array(destination / f'{name}-{key}.npy', segment[key])
                                            for key in ('anchor', 'vector')}
    for name in ('mean_', 'components_', 'explained_variance_', 'singular_values_'):
        record['pca_arrays'][name] = save_array(destination / f'pca-{name}.npy', getattr(result['pca'], name))
    write_json(destination / 'preprocessing.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pickle', type=Path, required=True)
    parser.add_argument('--runtime-versions', type=Path, required=True)
    parser.add_argument('--recipe', choices=(DECODING, CONSISTENCY, PAPER), required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    # Refuse the unresolved paper route before imports, payload intake or output.
    recipe_support(args.recipe)
    versions, _ = read_json(args.runtime_versions)
    backend = ElephantBackend(versions)
    release = read_release(args.source_pickle)
    require(type(release) is SourceViews and not args.output_root.exists(), 'fresh verified preparation required')
    args.output_root.mkdir(mode=0o700)
    rats = ('achilles',) if args.recipe == DECODING else RATS
    for rat in rats:
        neural = release[rat]['neural']
        rows = source_rows(rat, 0, len(neural))
        result = released_decoding(neural, rows, backend) if args.recipe == DECODING else released_consistency(neural, rows, backend, rat)
        export_preprocessed(result, args.output_root / rat, source_authentication='publisher_sha256')


if __name__ == '__main__':
    main()

"""Native notebook result extraction and strict original Figure5d connection.

Notebook metrics remain source-specific diagnostics. The complete paper endpoint
keeps its unchanged 2000-query requirement; no last-row padding or reindexing.
"""
from __future__ import annotations

import math
from pathlib import Path
import types

import numpy as np
from sklearn.metrics import r2_score
from sklearn.neighbors import KNeighborsRegressor
from scipy.stats import sem

from inputs import (CONSISTENCY, DECODING, SOURCE_SHA256, InputError, array_pin,
                    is_sha, read_bytes, require, row_index, sha256, source_rows)

SCORER_SHA256 = '010ac03e477ef4c1e27eec88bc30e16e61ad91c6c2affcee9b7252b6f7469674'
METHODS = ('cebra-time', 'cebra-behaviour', 'marble')


def native_array(value):
    """Read an already-live NumPy/Torch result; never deserialize a checkpoint."""
    if hasattr(value, 'detach'):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def graph_embedding(graph, segment, dimension=32):
    """Bind native data.emb to every source graph node; no inferred reordering."""
    require(type(dimension) is int and dimension in (3, 32), 'source embedding dimension must be 3 or 32')
    rows = segment['row_ids']
    indices = native_array(graph.sample_ind)
    require(indices.dtype.kind in 'iu' and indices.shape == (len(rows),)
            and np.array_equal(indices, np.arange(len(rows))), 'source graph dropped or reordered original nodes')
    position, vector = native_array(graph.pos), native_array(graph.x)
    with np.errstate(over='ignore', invalid='ignore'):
        expected_position = np.asarray(segment['anchor'], dtype=np.float32)
        expected_vector = np.asarray(segment['vector'], dtype=np.float32)
    require(position.dtype == vector.dtype == np.dtype('float32')
            and np.isfinite(expected_position).all() and np.isfinite(expected_vector).all()
            and np.array_equal(position, expected_position) and np.array_equal(vector, expected_vector),
            'native graph anchors/differences differ from frozen preprocessing')
    embedding = finite_matrix(native_array(graph.emb), len(rows), dimension, 'native graph embedding')
    return {'row_ids': list(rows), 'embedding': embedding, 'embedding_numeric_pin': array_pin(embedding),
            'forward_partner_row_ids': list(segment['forward_partner_row_ids'])}


def source_scorer():
    path = Path(__file__).parent.parent / 'figure5d-endpoint-v1/score.py'
    body = read_bytes(path, 65536)
    require(sha256(body) == SCORER_SHA256, 'retained Figure5d scorer changed')
    module = types.ModuleType('retained_marble_figure5d')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def finite_matrix(value, rows, columns, name):
    array = np.asarray(value)
    require(array.ndim == 2 and array.shape == (rows, columns) and array.dtype.kind == 'f'
            and np.isfinite(array).all(), name + ' must preserve complete finite numeric support')
    return array


def sequences(direction):
    require(len(direction) > 0, 'empty source direction sequence')
    boundaries = np.flatnonzero(direction[1:] != direction[:-1]) + 1
    starts = np.r_[0, boundaries]
    stops = np.r_[boundaries - 1, len(direction) - 1]
    return [(int(start), int(stop)) for start, stop in zip(starts, stops)]


def native_summary(prediction, labels):
    """All six helper outputs, including its endpoint-only sequence indexing."""
    labels = finite_matrix(labels, len(prediction), 3, 'source labels')
    prediction = finite_matrix(prediction, len(labels), 2, 'position/direction prediction')
    with np.errstate(over='ignore', invalid='ignore'):
        errors = abs(prediction[:, 0] - labels[:, 0])
    require(np.isfinite(errors).all(), 'absolute position error overflow')
    pairs = sequences(labels[:, 1])
    # The pinned helper uses prediction[seq,0], where seq is a (start,end)
    # tuple: this selects two endpoint rows, not the intervening slice.
    with np.errstate(over='ignore', invalid='ignore'):
        endpoint_errors = np.array([np.median(errors[list(pair)]) for pair in pairs])
        metrics = (float(r2_score(labels[:, :2], prediction)), float(np.median(errors)),
                   float(r2_score(labels[:, 0], prediction[:, 0])))
    require(all(math.isfinite(value) for value in metrics) and np.isfinite(endpoint_errors).all(),
            'source helper metric overflow or undefined value')
    return (*metrics, prediction, errors, endpoint_errors)


def decode_notebook_pair(training_embedding, query_embedding, training_labels, query_labels):
    """Released 36-neighbor cosine position and direction decoders; no truncation."""
    train = finite_matrix(training_embedding, len(training_labels), 32, 'training embedding')
    query = finite_matrix(query_embedding, len(query_labels), 32, 'query embedding')
    labels = finite_matrix(training_labels, len(train), 3, 'training labels')
    require(len(train) >= 36 and len(query) >= 2, 'complete decoder support is too short')
    predicted = []
    for column in (0, 1):
        decoder = KNeighborsRegressor(n_neighbors=36, metric='cosine', n_jobs=1)
        predicted.append(decoder.fit(train, labels[:, column]).predict(query))
    return native_summary(np.stack(predicted, axis=1), query_labels)


def validate_provenance(provenance):
    require(type(provenance) is dict and set(provenance) == {
        'embedding_producer_sha256', 'preprocessing_receipt_sha256',
        'model_or_fit_receipt_sha256', 'upstream_exposure', 'historical_checkpoint_lineage'},
        'explicit producer/preprocessing/model/exposure provenance required')
    require(all(is_sha(provenance[key]) for key in (
        'embedding_producer_sha256', 'preprocessing_receipt_sha256', 'model_or_fit_receipt_sha256')),
        'exact declared artifact digests required')
    require(provenance['upstream_exposure'] in (
        'unknown', 'complete_recording_neural', 'complete_recording_neural_and_behavior',
        'training_only_with_query_neural_transform'), 'explicit upstream exposure condition required')
    require(provenance['historical_checkpoint_lineage'] in ('unresolved', 'operator_reviewed_external_evidence'),
            'checkpoint lineage must remain explicit')


def adapt_notebook_outputs(outputs, labels, provenance):
    """Retain all native rows and reproduce the notebook's two distinct plots.

This operator-side report contains protected prediction/error arrays. It is not
candidate material and is never a Figure5d score or a four-rat aggregate.
"""
    labels = finite_matrix(labels, 10000, 3, 'complete Achilles labels')
    require(type(outputs) is dict and set(outputs) == set(METHODS)
            and type(provenance) is dict and set(provenance) == set(METHODS),
            'all three original notebook method outputs required')
    native, pointplot = {}, {}
    for method in METHODS:
        validate_provenance(provenance[method])
        output = outputs[method]
        require(type(output) in (list, tuple) and len(output) == 6, 'all six original helper outputs required')
        n = 1999 if method == 'marble' else 2000
        selected = labels[8000:8000 + n]
        prediction = finite_matrix(output[3], n, 2, method + ' prediction')
        expected = native_summary(prediction, selected)
        for index in (3, 4, 5):
            require(np.array_equal(np.asarray(output[index]), expected[index]),
                    'helper prediction/error/sequence output is inconsistent with exact original rows')
        require(all(type(output[i]) in (float, int, np.float32, np.float64) and math.isfinite(float(output[i]))
                    and float(output[i]) == expected[i] for i in (0, 1, 2)),
                'helper scalar metrics disagree with source arithmetic under this runtime')
        errors = expected[4]
        numeric_errors = np.asarray(errors, dtype=np.float64)
        with np.errstate(over='ignore', invalid='ignore'):
            mean_error = float(numeric_errors.mean())
            population_sd, sample_sd = float(numeric_errors.std(ddof=0)), float(numeric_errors.std(ddof=1))
            source_sem = float(sem(errors))
        require(all(math.isfinite(value) for value in (mean_error, population_sd, sample_sd, source_sem)),
                'notebook summary overflow or undefined value')
        pairs = sequences(selected[:, 1])
        native[method] = {'query_row_ids': source_rows('achilles', 8000, 8000 + n),
            'query_rows': n, 'prediction_position_direction': prediction.tolist(),
            'absolute_position_errors_m': errors.tolist(),
            'joint_position_direction_r2': expected[0], 'median_absolute_position_error_m': expected[1],
            'position_r2': expected[2], 'mean_absolute_position_error_m': mean_error,
            'absolute_error_sd_population_m': population_sd,
            'absolute_error_sd_sample_m': sample_sd,
            'median_plot_errorbar_sem_of_mean_errors_m': source_sem,
            'sequence_endpoint_pairs_query_local': [list(pair) for pair in pairs],
            'sequence_endpoint_median_errors_m': expected[5].tolist(), 'provenance': provenance[method]}
        # Plot cell15 drops the last CEBRA error only. Preserve it above and
        # describe this 1999-row plotting support as the released notebook view.
        common = numeric_errors if method == 'marble' else numeric_errors[:-1]
        pointplot[method] = {'errors_m': common.tolist(), 'mean_error_m': float(common.mean()),
                            'discarded_final_native_error_from_this_plot_only': None if method == 'marble' else float(numeric_errors[-1])}
    return {'schema': 'marble-released-notebook-results/v1', 'source_sha256': SOURCE_SHA256,
        'animal': 'achilles', 'native_method_results': native,
        'cell15_pointplot': {'query_row_ids': source_rows('achilles', 8000, 9999), 'rows': 1999,
            'methods': pointplot, 'paired_comparison_requests': [['cebra-time', 'marble'], ['cebra-behaviour', 'marble']],
            'requested_test': 'Wilcoxon via statannotations; historical runtime and p-values not supplied'},
        'cell16_barplot': 'Native helper medians with SEM of per-row errors; differing native counts remain explicit',
        'companion_summary_precision': 'Means/SD and pointplot companion means recomputed in float64; SEM uses scipy.stats.sem on original error dtype. This is not historical plotting-library bit parity.',
        'sequence_statistic': 'Median of each direction sequence endpoint pair, not the median over its whole interval',
        'historical_checkpoint_or_training_exposure_verified': False,
        'figure5d_eligible': False, 'scientific_improvement_awarded': None,
        'qualification': 'complete_released_notebook_extraction_not_published_2000_query_endpoint'}


def figure5_inputs(support, support_sha256, training, query, labels, provenance):
    """Join independently supplied complete source outputs; never repair support.

Support pinning authenticates the operator's declaration, not historical truth.
Embedding order must already equal that declaration. Only source label lookup
uses the explicit original row identities; embeddings are never reindexed.
"""
    import json
    validate_provenance(provenance)
    require(is_sha(support_sha256), 'explicit frozen support pin required')
    # Canonical bytes are defined by this API; CLI callers should retain exactly
    # this encoding or bind their parsed input separately before calling.
    canonical = json.dumps(support, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    require(sha256(canonical) == support_sha256, 'frozen support changed')
    scorer = source_scorer()
    train_ids, query_ids = scorer.support_check(support)
    require(support['source_sha256'] == SOURCE_SHA256, 'support source differs from original release')
    labels = finite_matrix(labels, 10000, 3, 'complete source labels')
    require(type(training) is dict and set(training) == {'row_ids', 'embedding'}
            and type(query) is dict and set(query) == {'row_ids', 'embedding'}, 'unexpected embedding fields')
    require(training['row_ids'] == train_ids and query['row_ids'] == query_ids, 'embedding order differs from frozen support')
    train_array = finite_matrix(training['embedding'], len(train_ids), 32, 'training embedding')
    query_array = finite_matrix(query['embedding'], 2000, 32, 'query embedding')
    train_indices = [row_index(identity) for identity in train_ids]
    query_indices = [row_index(identity) for identity in query_ids]
    return {'support': support,
            'training': {'row_ids': train_ids, 'embedding': train_array.tolist(),
                         'position_m': labels[train_indices, 0].tolist()},
            'query': {'row_ids': query_ids, 'embedding': query_array.tolist()},
            'targets': {'row_ids': query_ids, 'position_m': labels[query_indices, 0].tolist()},
            'provenance': provenance, 'scorer_sha256': SCORER_SHA256,
            'historical_original_support_verified': False}


def score_complete(bound):
    require(bound['scorer_sha256'] == SCORER_SHA256 and bound['historical_original_support_verified'] is False,
            'component cannot promote source qualification')
    scorer = source_scorer()
    result = scorer.score(**{key: bound[key] for key in ('support', 'training', 'query', 'targets')})
    result['upstream_provenance_declarations'] = bound['provenance']
    result['retained_scorer_sha256'] = SCORER_SHA256
    return result

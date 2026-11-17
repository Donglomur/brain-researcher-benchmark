"""Original Figure 3b reduction and distinct companion summaries.

The source notebook selects fixed layer index 5 and lags -300,-200,-100 ms.
This module never selects a favorable layer/time from candidate outcomes.
It does not fit models, inspect neural targets, or declare a paper win.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from source_panel import SESSION_UNITS, SOURCE_FILES, load_panel, validate_panel


def finite_json(value):
    """Preserve undefined entries as null, never silently exclude them."""
    if isinstance(value, np.ndarray):
        return finite_json(value.tolist())
    if isinstance(value, dict):
        return {str(key): finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def stats(values):
    """Equal-session descriptive statistics; undefined sessions propagate."""
    values = np.asarray(values, dtype=np.float64)
    return {'session_values': values, 'mean': values.mean(axis=0),
            'defined_sessions': np.isfinite(values).sum(axis=0),
            'session_count': len(values),
            'descriptive_sem_ddof0': values.std(axis=0, ddof=0) / np.sqrt(len(values))}


def summarize(panel):
    validate_panel(panel)
    stack = lambda field: np.stack([panel[s][field] for s in SESSION_UNITS])
    # Figure3.ipynb cell 5: ss=0, ee=3; context[:,ss+17:ee+17,5].mean(1).
    figure3b = {field: stats(stack(field)[:, 17:20, 5].mean(axis=1))
                for field in ('population', 'time_shuffle')}
    figure3b.update({field: stats(stack(field)[:, 0:3, 0].mean(axis=1))
                    for field in ('syn', 'syn_shuffle', 'word2vec',
                                  'word2vec_shuffle', 'sem_syn', 'sem_syn_shuffle')})
    # Cell 9 flattens fourteen sessions x three lags for its permutation test;
    # preserve those observations separately, without treating 42 as people.
    permutation_inputs = {field: stack(field)[:, 17:20, 5].reshape(-1)
                          for field in ('population', 'time_shuffle')}
    permutation_inputs.update({field: stack(field)[:, 0:3, 0].reshape(-1)
                               for field in ('syn', 'syn_shuffle', 'word2vec',
                                             'word2vec_shuffle', 'sem_syn', 'sem_syn_shuffle')})
    figure3c = {}
    for n in (1, 3, 5, 7, 10):
        field = f'ngram{n}'
        values = stack(field)
        # Source cell 15 selects one group-mean maximum layer per n-gram.
        # Undefined input prevents a fabricated maximum-layer choice.
        layer = int(values.mean(axis=0).argmax()) if np.isfinite(values).all() else None
        figure3c[field] = {'source_selected_layer_index': layer,
                           'summary': stats(values[:, layer]) if layer is not None else None,
                           'all_layer_session_values': values}
    population = stack('population')
    units = np.concatenate([panel[s]['unit'] for s in SESSION_UNITS])
    counts = np.isfinite(units).sum(axis=0)
    # Cell 27 uses nanmean across released unit rows. Retain the per-cell
    # denominator so its omission policy cannot become an invisible exclusion.
    unit_mean = np.divide(np.nansum(units, axis=0), counts,
                          out=np.full((40, 33), np.nan), where=counts != 0)
    population_mean = population.mean(axis=0)
    def normalized(value):
        maximum = value.max()
        return value / maximum if np.isfinite(maximum) and maximum != 0 else np.full_like(value, np.nan)
    output = {
        'schema': 'language_original_figure3_reduction_v1',
        'sessions': list(SESSION_UNITS), 'participants': 8,
        'released_fr_matrix_unit_columns': sum(SESSION_UNITS.values()),
        'figure3b': figure3b,
        'figure3b_selection': {'layer_index_zero_based': 5,
                              'lag_indices': [17, 18, 19],
                              'lag_milliseconds': [-300, -200, -100],
                              'aggregation': 'time mean within session; equal fourteen-session mean',
                              'sem_scope': 'descriptive ddof0; Figure3b notebook does not calculate its reported SEM'},
        'source_permutation_observations': permutation_inputs,
        'source_permutation_tests_executed': False,
        'figure3c': figure3c,
        'figure3d': {field: stats(stack(field)) for field in ('random_token', 'sentence_swap')},
        'figure3e': {
            'unweighted_population_mean': population_mean,
            'unweighted_population_normalized': normalized(population_mean),
            'unit_nanmean': unit_mean,
            'unit_normalized': normalized(unit_mean),
            'unit_defined_count_per_lag_layer': counts,
            'weighted_population_status': 'not_computed_requires_self_FR_aligned2word_counts',
        },
        'figure3f_status': 'not_computed_requires_579_selectivity_rows_and_authenticated_trans_ind',
        'full_panel_fields_present': list(SOURCE_FILES),
        'scientific_win': None,
        'method_execution_authenticated': False,
    }
    return finite_json(output)


def compare(candidate, reference):
    """Reproduction discrepancies and improvement deltas are separate outputs."""
    c, r = summarize(candidate), summarize(reference)
    cc = np.array([candidate[s]['population'][17:20, 5].mean() for s in SESSION_UNITS])
    rr = np.array([reference[s]['population'][17:20, 5].mean() for s in SESSION_UNITS])
    delta = cc - rr
    people = {p: [i for i,s in enumerate(SESSION_UNITS) if s.split('_')[0] == p]
              for p in (f'p{i}' for i in range(1, 9))}
    reproduction = {}
    for session in SESSION_UNITS:
        reproduction[session] = {}
        for field in SOURCE_FILES:
            a, b = candidate[session][field], reference[session][field]
            valid = np.isfinite(a) & np.isfinite(b)
            matched = np.array_equal(np.isfinite(a), np.isfinite(b))
            reproduction[session][field] = {
                'same_defined_support': bool(matched),
                'defined_pairs': int(valid.sum()), 'total_cells': int(a.size),
                'mae_on_defined_pairs': float(np.abs(a[valid]-b[valid]).mean()) if valid.any() else None,
                'max_absolute_error_on_defined_pairs': float(np.abs(a[valid]-b[valid]).max()) if valid.any() else None,
            }
    return finite_json({
        'schema': 'language_original_figure3_comparison_v1',
        'candidate_summary': c, 'reference_summary': r,
        'reproduction': {'full_panel_discrepancies': reproduction,
                         'threshold_admission': None},
        'improvement': {'figure3b_paired_session_delta': delta,
                        'figure3b_equal_session_mean_delta': delta.mean(),
                        'participant_clusters': {p: delta[indices] for p,indices in people.items()},
                        'participant_mean_delta_diagnostic': {p: delta[indices].mean() for p,indices in people.items()},
                        'uncertainty_test': None, 'scientific_win': None},
        'scope': 'same fixed source reduction; supplied output provenance is not execution authentication',
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-root', required=True, help='Original result_llm directory')
    parser.add_argument('--reference-root', help='Optional original author result_llm comparator')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error('output already exists')
    panel, receipts = load_panel(args.result_root)
    if args.reference_root:
        reference, reference_receipts = load_panel(args.reference_root)
        result = compare(panel, reference)
        result['reference_input_receipts'] = reference_receipts
    else:
        result = summarize(panel)
    result['input_receipts'] = receipts
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()

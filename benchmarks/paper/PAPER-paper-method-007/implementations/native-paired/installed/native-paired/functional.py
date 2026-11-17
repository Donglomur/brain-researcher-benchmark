"""Target-last ISI product capture and two arithmetic banks.

The producer preserves the recorded UnitMatch benchmark's NumPy histogram and
centered correlation recipe. Its score/decoder/AUC module is byte-exact original
source. The reference bank was separately authored from MATH_CONTRACT_V1.md.
This module is never called by source construction against authentic operands.
"""
import math
from pathlib import Path
from support import capture, encoded, identity, need, ordinary, relative, save


def close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a-b) <= 1e-12 + 1e-10 * max(abs(a), abs(b))


def clean_matrix(values):
    return [[float(v) if math.isfinite(float(v)) else None for v in row] for row in values]


def producer_products(spikes, edges):
    """Exact original half-spike slicing; added count products, no inferred labels."""
    import numpy as np
    first, second, products = [], [], []
    for values in spikes:
        a = np.asarray(values, dtype=np.float64)
        n = len(a)
        need(np.isfinite(a).all() and not np.any(np.diff(a) < 0), 'Finite ordered recorded spikes')
        if n < 2:
            first.append(np.full(41, np.nan))
            second.append(np.full(41, np.nan))
            products.append({'first': None, 'second': None, 'n_spikes': n})
            continue
        halves = (a[:n//2], a[(n+1)//2-1:])
        h = [np.histogram(np.diff(part), edges)[0] for part in halves]
        first.append(h[0]); second.append(h[1])
        counts = []
        for part, hist in zip(halves, h):
            intervals = np.diff(part)
            below = int(np.count_nonzero(intervals < edges[0]))
            above = int(np.count_nonzero(intervals > edges[-1]))
            counts.append({'intervals': len(intervals), 'in_range': int(hist.sum()),
                           'below_range': below, 'above_range': above, 'outside': below+above})
        products.append({'first': h[0].tolist(), 'second': h[1].tolist(), 'n_spikes': n,
                         'counts': dict(zip(('first', 'second'), counts))})
    a, b = np.asarray(first, float), np.asarray(second, float)
    a -= a.mean(axis=1, keepdims=True)
    b -= b.mean(axis=1, keepdims=True)
    denom = np.linalg.norm(a, axis=1)[:, None] * np.linalg.norm(b, axis=1)[None, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        corr = (a @ b.T) / denom
    return products, np.clip(corr, -1., 1.)


def validate_banks(spikes, edges, producer, correlations, bank):
    references = [bank.histograms(values, edges) for values in spikes]
    need(len(references) == len(producer), 'All unit products')
    for p, r in zip(producer, references):
        for key in ('first', 'second', 'n_spikes'):
            need(p[key] == r[key], 'Independent exact histogram/extent agreement')
        if p['n_spikes'] >= 2:
            need(p['counts'] == r['counts'], 'Independent interval mass accounting')
    other = bank.correlations([r['first'] for r in references], [r['second'] for r in references])
    canonical = clean_matrix(correlations)
    need(len(other) == len(canonical), 'Independent all-row extent')
    for left, right in zip(canonical, other):
        need(len(left) == len(right) and all(close(a, b) for a, b in zip(left, right)),
             'Independent directed correlation/undefinedness agreement')
    return references, other


def paired_score(matrix, mouse, correlations, reference_correlations, metrics, bank):
    producer = metrics.score(matrix, mouse, correlations)
    independent = bank.score(matrix, mouse['units'], reference_correlations)
    need(metrics.decode(matrix, mouse['units']) == bank.decode(matrix, mouse['units']),
         'Independent complete greedy pair identities')
    for key, value in producer.items():
        other = independent[key]
        if type(value) in (int, bool) or value is None:
            need(value == other and (value is not None or other is None), 'Independent exact score support: '+key)
        else:
            need(type(other) in (float, int) and close(float(value), float(other)), 'Independent score arithmetic: '+key)
    return {'producer': producer, 'reference': independent}


def read_sessions(package, mouse, io_utils, budget):
    """Verify the same open HDF5 object; retain the shared raw dependency explicitly.

    Finite integral cluster-template values are an additional fail-closed input
    admission rule, not a repair, cluster renumbering, or paper claim.
    """
    import h5py
    import numpy as np
    sessions = []
    producer_units, independent_units = [], []
    remaining = budget.limits['functional_spikes']
    need(remaining * 256 + len(mouse['units'])**2 * 160 <= budget.limits['live_bytes'],
         'Prospective full-mouse arrays, joins, JSON and both-bank payload envelope')
    for session in mouse['sessions']:
        source = ordinary(package / relative(session['source_prepared']))
        need(source.is_relative_to(package), 'Private operand inside selected package')
        size = source.stat().st_size
        # Hash read plus conservative complete HDF5 read envelope, before open.
        budget.charge(read=3*(size+1))
        with io_utils.VerifiedSource(source, session['prepared_sha256']) as verified:
            with h5py.File(verified.file, 'r') as file:
                st, clusters = file['sp/st'], file['sp/spikeTemplates']
                count = math.prod(st.shape)
                need(count == math.prod(clusters.shape) and count <= remaining, 'Full spike-array extent envelope')
                need(st.dtype.kind in 'fiu' and clusters.dtype.kind in 'fiu'
                     and st.dtype.itemsize <= 8 and clusters.dtype.itemsize <= 8,
                     'Bounded ordinary numeric spike dtypes before array allocation')
                times = np.asarray(st).reshape(-1)
                templates = np.asarray(clusters).reshape(-1)
            verified.assert_stable()
            need(np.isfinite(times).all() and np.isfinite(templates).all()
                 and np.equal(templates, np.floor(templates)).all(), 'Finite times and integral recorded templates')
            raw_times = times.astype(np.float64, copy=False).tolist()
            raw_templates = [int(v) for v in templates]
            record = {'session': session['session'], 'prepared_sha256': session['prepared_sha256'],
                      'sp_st': raw_times, 'sp_spikeTemplates': raw_templates,
                      'good_cluster_ids': session['good_cluster_ids']}
            sessions.append(record)
            for cid in session['good_cluster_ids']:
                selected = times[templates == cid].astype(np.float64, copy=False).tolist()
                # A separately expressed scalar join detects an indexing/selection
                # implementation error; both still share the captured HDF5 arrays.
                alternate = [t for t, label in zip(raw_times, raw_templates) if label == cid]
                need(selected == alternate, 'Exact raw-array to original unit identity join')
                producer_units.append(selected)
                independent_units.append(alternate)
            verified.assert_stable()
        remaining -= count
    return sessions, producer_units, independent_units


def grade_mouse(package, output, mouse, submissions, io_utils, metrics, bank, budget):
    """Called only after the study's native+A+B product barrier closes."""
    import numpy as np
    output.mkdir()
    raw_sessions, spikes, reference_spikes = read_sessions(package, mouse, io_utils, budget)
    edges = np.r_[0., 5.*10.**np.linspace(-4., 0., 41)]
    edge_values = edges.tolist()
    products, corr = producer_products(spikes, edges)
    references, refcorr = validate_banks(reference_spikes, edge_values, products, corr, bank)
    records = {
        'raw_sessions.json': {'mouse_id': mouse['mouse_id'], 'units': mouse['units'], 'sessions': raw_sessions},
        'functional_products.json': {'mouse_id': mouse['mouse_id'], 'units': mouse['units'], 'edges': edge_values,
                                    'producer_histograms': products, 'reference_histograms': references,
                                    'producer_correlations': clean_matrix(corr), 'reference_correlations': refcorr},
    }
    # Encode and admit all complete products before writing; never truncate a mouse.
    bodies = {name: encoded(value) for name, value in records.items()}
    need(sum(map(len, bodies.values())) <= budget.limits['functional_product_bytes'], 'Full functional product cap')
    pins = {name: save(output/name, body, budget) for name, body in bodies.items()}
    scores = {label: paired_score(matrix, mouse, corr, refcorr, metrics, bank)
              for label, matrix in submissions.items()}
    save(output/'SCORES.json', encoded(scores), budget)
    return {'mouse_id': mouse['mouse_id'], 'products': pins, 'scores': scores}


def summarize(rows):
    """Equal-mouse estimands only; no incomplete-cohort average or identity claim."""
    from support import MICE
    need(tuple(r['mouse_id'] for r in rows) == MICE, 'All five ordered mouse endpoints')
    scores = {arm: [r['scores'][arm]['producer'] for r in rows] for arm in ('native', 'A', 'B')}
    result = {'schema': 'unitmatch_native_paired_comparison_v1', 'mice': list(MICE),
              'endpoint': 'yield-constrained directed split-half ISI AUC proxy',
              'is_neuron_identity_accuracy': False, 'whole_16_mouse_paper_reproduction': False,
              'runtime_qualified': False, 'scientific_qualification': False, 'comparisons': {}}
    for arm in ('A', 'B'):
        native, candidate = scores['native'], scores[arm]
        eligible = all(x['isi_auc_eligible'] is True for x in native+candidate)
        support = all(c['matches'] >= n['matches'] and c['finite_cross_match_directions'] >= n['finite_cross_match_directions']
                      for c, n in zip(candidate, native))
        nc = sum(x['isi_auc'] for x in native)/5 if eligible else None
        cc = sum(x['isi_auc'] for x in candidate)/5 if eligible else None
        result['comparisons'][arm+'_vs_native'] = {
            'all_five_eligible': eligible, 'per_mouse_match_and_finite_support_nondecreasing': support,
            'native_equal_mouse_mean': nc, 'candidate_equal_mouse_mean': cc,
            'auc_difference': cc-nc if eligible else None,
            'declared_endpoint_improved': bool(eligible and support and cc > nc),
            'per_mouse_auc_differences': [c['isi_auc']-n['isi_auc'] if eligible else None for c, n in zip(candidate, native)]}
    eligible_ab = all(s['isi_auc_eligible'] is True for arm in ('A', 'B') for s in scores[arm])
    differences = [b['isi_auc']-a['isi_auc'] for a, b in zip(scores['A'], scores['B'])] if eligible_ab else None
    mean = sum(differences)/5 if differences is not None else None
    sd = math.sqrt(sum((x-mean)**2 for x in differences)/4) if differences is not None else None
    result['comparisons']['B_minus_A'] = {
        'all_five_eligible': eligible_ab, 'per_mouse_auc_differences': differences,
        'equal_mouse_mean_difference': mean, 'sample_standard_deviation_across_five_mice': sd,
        'descriptive_standard_error': sd/math.sqrt(5) if sd is not None else None,
        'significance_claim': False, 'uncertainty_scope': 'descriptive five-mouse paired dispersion; no neuron pooling',
        'per_mouse_match_differences': [b['matches']-a['matches'] for a, b in zip(scores['A'], scores['B'])],
        'per_mouse_finite_match_direction_differences': [b['finite_cross_match_directions']-a['finite_cross_match_directions']
                                                       for a, b in zip(scores['A'], scores['B'])]}
    return result

"""Full original-output comparison, after complete primitive-array admission.

The operator supplies the two assembled records and loaders already bound to
their artifact hashes. This module never accepts candidate-provided reference
arrays or aligns frequencies, NNMF components, people, samples or queries.
"""
from core import identity, need
from correspondence import match, permute
from native_score import field, aggregate


def compare(candidate, reference, load_candidate, load_reference, scales, scale_identity):
    import numpy as np
    need(identity(scales) == scale_identity, 'Scale policy frozen outside candidate control')
    need(candidate['schema'] == reference['schema'] == 'osl19_complete_literal_output_v1'
         and candidate['branch'] == reference['branch'], 'Exact admitted native branch')
    cc, rc = candidate['context'], reference['context']
    need(cc['role'] in ('A', 'B') and rc['role'] == 'reference'
         and cc['attempt_id'] != rc['attempt_id'], 'Separate candidate and operator fits')
    need([(r['person_id'], r['run_id']) for r in cc['runs']] ==
         [(r['person_id'], r['run_id']) for r in rc['runs']], 'Identical full original run roster')
    cf = [x for x in candidate['ordered_fields'] if x['comparison']]
    rf = [x for x in reference['ordered_fields'] if x['comparison']]
    schema_keys = ('key', 'shape', 'axes', 'units', 'state_axes', 'run_axis', 'run_index', 'panel', 'aggregation')
    need([{k: x[k] for k in schema_keys} for x in cf] ==
         [{k: x[k] for k in schema_keys} for x in rf], 'Complete literal fields and equal axes; no crop')
    keys = [x['key'] for x in cf]
    need(set(scales) == set(keys), 'Scale for every full field, including metadata/axes')
    need({k: v for k, v in candidate['native_axes'].items() if k in ('spectra.f', 'event.t')} ==
         {k: v for k, v in reference['native_axes'].items() if k in ('spectra.f', 'event.t')},
         'Literal complete frequency/event grids; no resampling')
    lookup_c, lookup_r = {r['key']: r for r in cf}, {r['key']: r for r in rf}
    correspondence = None
    if candidate['branch'] != 'ctf_static':
        correspondence = match(load_reference(lookup_r['model.covs']),
                               load_candidate(lookup_c['model.covs']),
                               reference['coordinate_signature'], candidate['coordinate_signature'])
    else:
        need(candidate['coordinate_signature'] == reference['coordinate_signature'],
             'Identical original static input coordinates')
    rows, roster = [], []
    for c, r in zip(cf, rf):
        x, y = np.asarray(load_candidate(c)), np.asarray(load_reference(r))
        need(list(x.shape) == c['shape'] and list(y.shape) == r['shape'], 'Bound loader full shape')
        if c['state_axes']:
            need(correspondence is not None, 'One fixed state assignment')
            x = permute(x, correspondence['order'], c['state_axes'])
        if c['run_axis'] is not None:
            pieces = [(i, np.take(x, i, axis=c['run_axis']), np.take(y, i, axis=r['run_axis']))
                      for i in range(len(cc['runs']))]
        else:
            pieces = [(c['run_index'], x, y)]
        for index, a, b in pieces:
            person = '__full_group_or_model__' if index is None else cc['runs'][index]['person_id']
            item = c['key'] if index is None else c['key'] + ':run=' + cc['runs'][index]['run_id']
            row = {'panel': c['panel'], 'person': person, 'item': item,
                   'error': field(a.ravel().tolist(), b.ravel().tolist(), scales[c['key']])}
            rows.append(row)
            roster.append((row['panel'], person, item))
    result = aggregate(rows, roster)
    return {**result, 'branch': candidate['branch'], 'role': cc['role'],
            'candidate_attempt': cc['attempt_id'], 'reference_attempt': rc['attempt_id'],
            'scale_identity': scale_identity, 'correspondence': correspondence,
            'nnmf_peak_observations': {'candidate': candidate['native_axes'].get('nnmf_peak_indices'),
                                       'reference': reference['native_axes'].get('nnmf_peak_indices')},
            'literal_outputs_changed': False, 'all_fields_compared': keys,
            'auxiliary_fields_admitted_but_not_scored': [x['key'] for x in candidate['ordered_fields'] if not x['comparison']],
            'independent_execution_requires_external_closures': True,
            'metric': 'full_native_normalized_absolute_error', 'whole_paper_reproduced': False}

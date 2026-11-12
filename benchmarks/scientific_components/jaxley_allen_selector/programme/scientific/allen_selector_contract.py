"""Explicit J11 output-layout amendment, before the unchanged campaign compiler.

Does not increase a grant, change source pins or launch anything. The caller must
rebind the prospective source tree and provide all original resource operands.
The unchanged compiler checks the new layout-derived extents against those caps.
"""
from copy import deepcopy
from .allen_source_selector import PRODUCTS, require, integer
from .json_extent import layout_bytes


def amended_outputs(outputs, *, max_candidates, max_path_bytes, max_job_id_bytes):
    for v in (max_candidates, max_path_bytes, max_job_id_bytes):
        integer(v, 'explicit finite layout cap', 1)
    require(max_candidates >= 2000, 'full high-GD best plus terminal support')
    require([x['artifact_id'] for x in outputs] == list(PRODUCTS), 'ordered original seven products')
    S = lambda n: {'kind': 'string', 'max_utf8_bytes': n}
    I = lambda n: {'kind': 'integer', 'minimum': 0, 'maximum': n}
    A = lambda item, low, high: {'kind': 'array', 'minimum_count': low, 'maximum_count': high, 'items': item}
    O = lambda fields: {'kind': 'object', 'fields': fields}
    number = {'kind': 'number'}; boolean = {'kind': 'boolean'}
    idx = I(max_candidates - 1); indices = A(idx, 0, max_candidates)
    pin = O({'artifact_id': S(64), 'path': S(max_path_bytes), 'bytes': I(2**63-1), 'sha256': S(64)})
    context = O({'job_id': S(max_job_id_bytes), 'condition': S(3),
                 'source_tree_sha256': S(64), 'source_profile_sha256': S(64),
                 'producer_source_sha256': S(64), 'config_sha256': S(64),
                 'inputs': A(O({'logical': S(max_path_bytes), 'path': S(max_path_bytes),
                                'bytes': I(2**63-1), 'sha256': S(64)}), 5, 5)})
    support = O({'key': O({'specimen': S(9), 'algorithm': S(2), 'budget': S(4),
                          'seed': I(42), 'particles': I(1000), 'steps': I(50), 'profile': S(32)}),
                 'context': context, 'candidate_count': I(max_candidates),
                 **{k: S(64) for k in ('candidate_order_sha256', 'fit_clock_sha256', 'long_clock_sha256',
                                       'fit_projection_sha256', 'long_projection_sha256')},
                 'fit_samples': I(50000), 'long_samples': I(50000)})
    selection = O({'schema': S(64), 'status': S(64), 'support': support,
                   'capture_pins': A(pin, 6, 6), 'source_recipe_commit': S(40),
                   'weights': A(number, 5, 5), 'target_features': A(number, 5, 5),
                   'eligible_indices': indices, 'eligible_absolute_errors': A(A(number, 5, 5), 0, max_candidates),
                   'eligible_weighted_errors': A(number, 0, max_candidates),
                   'ranked_global_indices': indices, 'equal_minimum_global_indices': indices,
                   'selected_global_index': {'kind': 'union', 'variants': [idx, {'kind': 'null'}]},
                   'short_ranked_best_indices': indices, 'short_equal_minimum_indices': indices,
                   'numpy_version': S(128), 'sort_call': S(128),
                   'historical_tie_identity_verified': boolean, 'protected_improvement_ready': boolean,
                   'protected_status': S(128), 'figure_aggregation_status': S(128), 'voltage_access': S(128)})
    def amend_row(layout, lineage):
        if layout['kind'] == 'union':
            for variant in layout['variants']:
                amend_row(variant, lineage)
            return
        require(layout['kind'] == 'object', 'original per-job object layout')
        fields = layout['fields']
        require('source_selector_join' not in fields and 'source_selection' not in fields,
                'once-only explicit layout amendment')
        fields['source_selector_join'] = S(64)
        if lineage:
            fields['source_selection'] = deepcopy(selection)
    result = deepcopy(outputs)
    for product in result:
        require(product['format'] == 'json' and product['extent']['kind'] == 'upper_bound',
                'variable-size full JSON products need admitted upper bounds')
        layout = product['extent']['derivation']['layout']
        require(layout['kind'] == 'array' and layout['minimum_count'] == layout['maximum_count'] == 52,
                'original full52 job layout retained')
        amend_row(layout['items'], product['artifact_id'] == 'best_final_hof_lineage')
        product['extent']['bytes'] = layout_bytes(layout) + 1
    return result

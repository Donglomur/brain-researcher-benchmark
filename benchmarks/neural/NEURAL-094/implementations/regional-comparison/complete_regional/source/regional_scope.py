"""Full-cohort, target-free G1 projection and prospective allocation geometry.

This module never opens files. The fixed mapping contains anatomical/unit
metadata, not SESSION.json (which contains protected query choices). Future
caller acquisition and map provenance remain separately admitted operations.
"""
import hashlib
import json
import math
import zlib

CANONICAL = (15678, '27a86a0d3065c06f9d2b7b509bc0ee3b0775cf3b58b810a917c4aba37d7f2e66')
CATALOG = (25926, '55745fc5f68ae31979487f21c23296bafa13551bfffacf75f07d53451e46ef63')
MAPPING = (705230, 'f35e4a93fab3d4374409c8db30b9f9cdbceb106e53ac72677d05a6764a872a35')
# The full logical digest is deliberately a literal source identity, not a
# newly inferred mapping; source review checks it against the original worker.
LOGICAL_MAPPING = (14173033, '6449b74f83d5948b3fd5059e25be4ebe0e6baafdb8c24ee7892d83d60bf8b21d')
SEEDS = tuple(range(2026110700, 2026110705))
MODES = ('F', 'I')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(raw):
    need(type(raw) is bytes, 'Immutable bytes required')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def exact_bytes(raw, expected):
    need(pin(raw) == {'bytes': expected[0], 'sha256': expected[1]}, 'Exact retained source identity')


def strict(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'Duplicate JSON field')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def decode_mapping(raw):
    exact_bytes(raw, MAPPING)
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = decoder.decompress(raw, LOGICAL_MAPPING[0] + 1)
    need(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
         'Complete single gzip member without trailing data')
    exact_bytes(out, LOGICAL_MAPPING)
    return out


class StudyScope:
    """Source-owned geometry; constructing from arbitrary counts is not admission."""
    __slots__ = ('plan', 'canonical', 'lineage', '_key')

    def __init__(self, key, plan, canonical, lineage):
        need(key is _SCOPE_KEY, 'Use authenticated G1 admission')
        self.plan, self.canonical, self.lineage, self._key = plan, canonical, lineage, key


_SCOPE_KEY = object()


def admit_scope(mapping_gzip, catalog_raw, canonical_raw, *, census, support):
    """Authenticate all target-free bodies and complete units before any output.

    `census` and `support` are exact captured project source modules, not plugins.
    Caller source loader binds their bodies. G1 anatomical validity is still a
    scientific hold even after bytes and guarded mapping semantics pass.
    """
    exact_bytes(catalog_raw, CATALOG)
    exact_bytes(canonical_raw, CANONICAL)
    decoded = decode_mapping(mapping_gzip)
    mapping, catalog, canonical = strict(decoded), strict(catalog_raw), strict(canonical_raw)
    census.summarize_full_cohort(mapping, catalog)
    projected = [{'ordinal': row['ordinal'], 'units': [
        {'unit': u['unit'], 'source_qc_code': u['source_qc_code'], 'raw_label': u['allen_ontology_raw']}
        for u in row['units']]} for row in mapping['sessions']]
    compiled = support.plan(canonical_raw, projected)
    return StudyScope(_SCOPE_KEY, compiled, canonical,
                      {'mapping': pin(mapping_gzip), 'logical_mapping': pin(decoded),
                       'catalog': pin(catalog_raw), 'canonical': pin(canonical_raw),
                       'target_bodies_read': 0, 'anatomical_ground_truth_established': False})


def bundle_key(kind, ordinal, *, pair=None, seed=None, side=None):
    need(type(ordinal) is int and 1 <= ordinal <= 39, 'Original session ordinal')
    if kind == 'whole':
        need(pair is seed is None and side in ('context', 'joint'), 'Whole two-arm identity')
        return f'w-{ordinal:02d}-{side}'
    need(kind == 'regional' and type(pair) is int and 0 <= pair < 2628
         and type(seed) is int and seed in SEEDS and side in ('left', 'right'), 'Regional identity')
    return f'r-{pair:04d}-{ordinal:02d}-{seed}-{side}'


def bundles(scope):
    """Canonical order, no outcome-dependent filtering or extra task IDs."""
    need(type(scope) is StudyScope and scope._key is _SCOPE_KEY, 'Admitted full scope')
    for ordinal in range(1, 40):
        for side in ('context', 'joint'):
            yield {'key': bundle_key('whole', ordinal, side=side), 'kind': 'whole',
                   'ordinal': ordinal, 'side': side, 'pair': None, 'seed': None}
    for pair in range(2628):
        row = scope.plan.pair(pair)
        for session in row['session_roster']:
            if session['structural_status'] != 'supported_pending_execution':
                continue
            for seed in SEEDS:
                for side in ('left', 'right'):
                    yield {'key': bundle_key('regional', session['ordinal'], pair=pair, seed=seed, side=side),
                           'kind': 'regional', 'ordinal': session['ordinal'], 'side': side,
                           'pair': pair, 'seed': seed}


def geometry(scope):
    need(type(scope) is StudyScope and scope._key is _SCOPE_KEY, 'Admitted full scope')
    S = 0
    selected_unit_occurrences = 0
    for pair in range(2628):
        row = scope.plan.pair(pair)
        need(len(row['session_roster']) == 39 and len(row['mouse_roster']) == 10, 'Full structural support')
        for item in row['session_roster']:
            if item['structural_status'] == 'supported_pending_execution':
                S += 1
                selected_unit_occurrences += 10 * item['K']
    need(0 <= S <= 102492, 'Full structural upper bound')
    return {'sessions': 39, 'mice': 10, 'labels': 73, 'unordered_pairs': 2628,
            'structural_session_cells': 102492, 'structural_seed_cells': 512460,
            'co_recorded_pair_session_cells': S,
            'candidate_bundles_per_mode': 78 + 10*S, 'candidate_bundles_both_modes': 156 + 20*S,
            'candidate_stage_launches': 312 + 40*S,
            'whole_reference_bundles': 39, 'regional_reference_bundles': 10*S,
            'whole_reference_maximum_estimator_fits': 585,
            'regional_reference_maximum_estimator_fits': 50*S,
            'regional_selected_unit_occurrences': selected_unit_occurrences,
            'exact_duplicate_reuse_budgeted': False, 'scientific_execution': False}


def capacity(scope, extents, limits):
    """Exact admitted serialized extents, conservative explicit stage envelopes.

    No donor matrix is manufactured to derive capacity. Extents must come from
    future complete projection admission before allocation; authenticating this
    caller-supplied record remains the source-owned staging boundary's duty.
    """
    g = geometry(scope)
    need(type(limits) is dict and set(limits) == {'fit', 'query', 'reference_fit', 'reference_query', 'grade'},
         'All candidate/reference phase operands')
    fields = {'wall_seconds', 'cpu_seconds', 'memory_bytes', 'storage_bytes', 'model_bytes',
              'prediction_bytes', 'metadata_bytes'}
    for value in limits.values():
        need(type(value) is dict and set(value) == fields, 'Exact capacity phase fields')
        for k, v in value.items():
            need(type(v) in (int, float) and math.isfinite(v) and v > 0, 'Explicit positive phase operand')
            if k.endswith('_bytes'):
                need(type(v) is int, 'Exact byte operand')
    expected = (x['key'] for x in bundles(scope))
    total_input = reference_input = total_feature = maximum_input = 0
    count = 0
    for key in expected:
        try:
            row = next(extents)
        except StopIteration:
            raise ValueError('Missing complete bundle extent') from None
        need(type(row) is dict and set(row) == {'key', 'fit_bytes', 'query_bytes', 'feature_bytes'}
             and row['key'] == key, 'Exact complete extent schedule')
        for k in ('fit_bytes', 'query_bytes', 'feature_bytes'):
            need(type(row[k]) is int and row[k] > 0, 'Positive real serialized/projected extent')
        count += 1
        total_input += row['fit_bytes'] + row['query_bytes']
        if key.startswith('r-') or key.endswith('-joint'):
            reference_input += row['fit_bytes'] + row['query_bytes']
        total_feature += row['feature_bytes']
        maximum_input = max(maximum_input, row['fit_bytes'], row['query_bytes'])
    need(next(extents, None) is None and count == g['candidate_bundles_per_mode'], 'No extra extent')
    ref_count = g['whole_reference_bundles'] + g['regional_reference_bundles']
    stage_counts = {'fit': 2*count, 'query': 2*count,
                    'reference_fit': ref_count, 'reference_query': ref_count, 'grade': 1}
    return {'schema': 'neural094_complete_capacity_v1', 'geometry': g,
            'input_bytes_per_candidate_mode': total_input,
            'feature_bytes_per_candidate_mode': total_feature,
            'maximum_single_input_bytes': maximum_input,
            'grade_prediction_file_reads':585+92*g['co_recorded_pair_session_cells'],
            'grade_private_mapping_file_reads':39,'regional_result_files':7884,
            'grade_prediction_bytes_upper_bound':(585+92*g['co_recorded_pair_session_cells'])*
                 max(limits['query']['prediction_bytes'],limits['reference_query']['prediction_bytes']),
            'projected_archive_bytes_are_not_inferred_from_compressed_input':True,
            'projection_peak_memory_requires_separate_native_admission':True,
            'phase_launches': stage_counts, 'phase_limits': limits,
            'reserved_wall_seconds': sum(stage_counts[k]*v['wall_seconds'] for k, v in limits.items()),
            'reserved_cpu_seconds': sum(stage_counts[k]*v['cpu_seconds'] for k, v in limits.items()),
            'retained_input_capture_bytes_upper':2*total_input+reference_input,
            'regional_whole_fit_transfer_bytes_upper':10*g['co_recorded_pair_session_cells']*
                 (limits['reference_fit']['model_bytes']+4*limits['reference_fit']['metadata_bytes']),
            'reserved_retained_bytes':sum(stage_counts[k]*(v['storage_bytes']+v['model_bytes']+
                 v['prediction_bytes']+3*v['metadata_bytes']) for k,v in limits.items())+
                 2*total_input+reference_input+10*g['co_recorded_pair_session_cells']*
                 (limits['reference_fit']['model_bytes']+4*limits['reference_fit']['metadata_bytes'])+
                 7885*limits['grade']['metadata_bytes'],
            'native_capacity_qualified': False, 'source_projection_authenticated': False}

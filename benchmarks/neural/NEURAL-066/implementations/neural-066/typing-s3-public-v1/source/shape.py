"""Full-support shape admission from actual admitted metadata, never fixture caps."""
from core import COUNTS, need
from preparation import eligible, key, projection_live_floor

def admit_actual_shapes(op, membership, logs, projected, joined, policy):
    """Runs only after all143 authentic projections; no estimated census repair."""
    need(len(projected) == 143 and len(membership['cases']) == 78, 'Full prepared shape support')
    records = {key(r): r for r in logs['records'] if eligible(r, policy)}
    projection = sum((a['bytes'] for q in projected for a in q['arrays'].values()))
    reference = candidate = 0
    largest_view = largest_projection = 0
    largest_array = 0
    largest_sentence = 0
    largest_attention = 0
    largest_native_floor = 0
    for q in projected:
        largest_projection = max(largest_projection, sum((a['bytes'] for a in q['arrays'].values())))
        largest_array = max(largest_array, max((a['bytes'] for a in q['arrays'].values())))
        floor = projection_live_floor({a: d['shape'] for a, d in q['arrays'].items()}, COUNTS[q['record']['modality']]['channels'], len(q['eog_names']))
        need(q['known_array_memory_floor'] == floor, 'Exact native known-array arithmetic join')
        largest_native_floor = max(largest_native_floor, floor['live_array_bytes'])
    for case in membership['cases']:
        n = sum((len(records[k]['keys']) for k in case['train_keys']))
        m = sum((len(records[k]['keys']) for k in case['query_keys']))
        channels = COUNTS[case['modality']]['channels']
        eog = len(joined['eog_names'][case['modality']])
        for d in (3, 25 * eog, 25 * channels, 25 * channels, 25 * channels, 25 * channels):
            train = 4 * n * (d + 2) + 1024
            query = 4 * m * d + 1024
            extent = train + query
            reference += extent
            candidate += 2 * extent
            largest_view = max(largest_view, extent)
            largest_array = max(largest_array, train, query)
        reference += 4 * n * (25 * channels + 2) + 1024
        length = max((len(records[k]['keys']) for k in case['train_keys'] + case['query_keys']))
        largest_sentence = max(largest_sentence, length)
        largest_attention = max(largest_attention, 4 * (4 * 2 * length * length + 12 * length * 2048))
    need(largest_sentence <= 256, 'Existing complete sentence support; never crop')
    shape = op['full_shape_reservation']
    required = {'projection_bytes': projection, 'reference_view_bytes': reference, 'candidate_view_bytes': candidate, 'largest_live_array_bytes': max(largest_view + largest_projection + 2 * largest_array, largest_native_floor), 'largest_attention_bytes': largest_attention}
    for k, n in required.items():
        need(shape[k] >= n, 'Full actual shape reservation ' + k)
    for a in ('case_plan', 'candidate_view'):
        need(op['phase_limits'][a]['array_bytes'] >= largest_array and op['phase_limits'][a]['live_array_bytes'] >= largest_view + largest_projection, 'Complete view allocation/native source array support')
    need(op['phase_limits']['native_project']['live_array_bytes'] >= largest_native_floor, 'Complete five-family output and known scratch support')
    need(shape['concurrent_stage_bytes'] >= 3 * largest_view + largest_projection, 'Full concurrent role-copy reservation')
    return {'schema': 'neural066_actual_shape_join_v1', 'required_arithmetic_floors': required, 'largest_native_known_array_floor_bytes': largest_native_floor, 'largest_complete_sentence': largest_sentence, 'largest_array_bytes': largest_array, 'actual_runtime_peak_measured': False, 'native_feasibility_qualified': False}

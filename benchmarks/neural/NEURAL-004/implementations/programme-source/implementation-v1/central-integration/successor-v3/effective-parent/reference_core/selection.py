"""Complete inner-person selection; never reads outer answers."""
import math
from .protocol import candidate_specs, require, ids, safe_metadata


def select(candidate_by_inner_person_records):
    table = candidate_by_inner_person_records
    require(type(table) is dict and set(table) == {'inner_people', 'attempts'}, 'selection_schema')
    people = ids(table['inner_people'], 25)
    attempts = table['attempts']
    require(type(attempts) is list and len(attempts) == 25 * 23, 'selection_complete_grid')
    order = [s['id'] for s in candidate_specs()]
    grid = {}
    for row in attempts:
        safe_metadata(row)
        require(type(row) is dict and {'candidate', 'inner_person', 'status'} <= set(row), 'selection_row')
        pair = (row['candidate'], row['inner_person'])
        require(pair[0] in order and pair[1] in people and pair not in grid, 'selection_identity')
        require(row['status'] in ('completed', 'failed'), 'selection_status')
        if row['status'] == 'completed':
            require(set(row) == {'candidate', 'inner_person', 'status', 'loss', 'state_pin', 'prediction_pin'}, 'selection_success_schema')
            require(type(row['loss']) in (int, float) and math.isfinite(row['loss']) and 0 <= row['loss'] <= 1, 'selection_loss')
        else:
            require(set(row) == {'candidate', 'inner_person', 'status', 'failure'}, 'selection_failure_schema')
        grid[pair] = row
    candidate_rows = []
    for candidate in order:
        vector = [grid[candidate, person] for person in people]
        complete = all(r['status'] == 'completed' for r in vector)
        # fsum retains a deterministic accurate arithmetic mean, no weighting by rows.
        score = math.fsum(float(r['loss']) for r in vector) / 25 if complete else None
        candidate_rows.append({'candidate': candidate, 'eligible': complete, 'person_records': vector, 'person_macro_mse': score})
    def best(candidates):
        allowed = [r for r in candidate_rows if r['eligible'] and r['candidate'] in candidates]
        return min(allowed, key=lambda r: (r['person_macro_mse'], order.index(r['candidate'])))['candidate'] if allowed else None
    deficient = []
    if not any(r['eligible'] for r in candidate_rows[1:11]):
        deficient.append('B_no_complete_flexible_candidate')
    for family, start in (('G', 11), ('C', 15), ('GC', 19)):
        if not any(r['eligible'] for r in candidate_rows[start:start + 4]):
            deficient.append(f'{family}_no_complete_setting')
    return {'schema': 'neural004_reference_selection_v1', 'inner_people': people,
            'candidate_order': order, 'candidates': candidate_rows,
            'B': best(order[:11]), 'N': best(order), 'deficiencies': deficient,
            'selection_uses_outer_answers': False}

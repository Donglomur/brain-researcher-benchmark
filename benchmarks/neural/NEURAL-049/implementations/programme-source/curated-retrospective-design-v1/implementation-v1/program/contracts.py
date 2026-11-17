"""Fixed full-study identities and positive actor contracts. No input effects."""
from core import need, integer, descriptor, pin, encoded

TASK = 'NEURAL-049'
PROFILE = 'curated_retrospective_full_v1'
PEOPLE = tuple(f'{i:02d}' for i in range(1, 13))
DAY_COUNTS = (4, 4, 4, 5, 3, 5, 5, 5, 5, 5, 5, 5)
ENDPOINTS = ('angle', 'magnitude', 'speed')
VIEWS = ('C', 'N', 'NC')
FAMILIES = ('R', 'B', 'T')
CONFIGS = tuple([f'R{i:02d}' for i in range(9)] + [f'B{i:02d}' for i in range(8)] + [f'T{i:02d}' for i in range(8)])
GATES = ('source_membership', 'event_census', 'cue_target_provenance', 'clock', 'channel_identity',
         'mask_semantics', 'upstream_exposure', 'licensing_privacy', 'mathematics',
         'independent_reference_agreement', 'reference_competence', 'resource_feasibility',
         'mode_semantics', 'physical_isolation', 'runtime_completion', 'target_last_scoring',
         'tool_custody', 'assignment_feasibility', 'reference_cache_custody', 'root_selection')


def modules(value):
    need(type(value) is list and value and value[0] == 'core' and len(value) == len(set(value))
         and value == [x for x in ('core', 'T1', 'D') if x in value], 'explicit ordered complete modules')
    return tuple(value)


def cells(selected):
    modules(list(selected))
    rows = [{'id': mode + '_' + view, 'mode': mode, 'view': view, 'tool': False, 'disrupted': False,
             'policy': mode + '_' + view} for mode in ('F', 'I') for view in VIEWS]
    if 'T1' in selected:
        rows += [{'id': mode + '_NC_T1', 'mode': mode, 'view': 'NC', 'tool': True, 'disrupted': False,
                  'policy': mode + '_NC_T1'} for mode in ('F', 'I')]
    if 'D' in selected:
        rows += [{'id': mode + '_NC_D', 'mode': mode, 'view': 'NC', 'tool': False, 'disrupted': True,
                  'policy': mode + '_NC'} for mode in ('F', 'I')]
    return rows


def identity(parts):
    need(type(parts) in (list, tuple), 'structured operation identity')
    return pin(encoded(list(parts)))['sha256']


def roster(value):
    """Owner normalized PRIVATE metadata; never an actor-visible manifest."""
    need(type(value) is dict and tuple(sorted(value)) == PEOPLE, 'all twelve source people')
    all_ids = set()
    for person, count in zip(PEOPLE, DAY_COUNTS):
        rows = value[person]
        need(type(rows) is list and len(rows) == count, 'all released day dispositions')
        days = [integer(row['day'], 1) for row in rows]
        need(days == sorted(set(days)), 'original positive day ordinals, gaps retained')
        axis = rows[0]['axis']
        need(type(axis) is list and axis and len(axis) == len(set(axis))
             and all(type(x) is str and x for x in axis), 'complete person channel union')
        for row in rows:
            ids = row['ids']
            need(row['axis'] == axis and type(ids) is list and all(type(x) is str and x for x in ids)
                 and len(ids) == len(set(ids)) and not all_ids.intersection(ids), 'complete unique original row order')
            all_ids.update(ids)
            need(row['empty'] is (not ids), 'explicit empty day')
            descriptor(row['source'])
    return value


def recipe(value):
    """F may author general Python before data. Later replies have this grammar."""
    need(type(value) is dict and set(value) == {'schema', 'provider_slots', 'state_array_cap',
         'state_array_bytes', 'state_metadata_bytes'}, 'exact candidate recipe')
    need(value['schema'] == 'neural049_candidate_recipe_v1', 'candidate recipe schema')
    for k in ('state_array_cap', 'state_array_bytes', 'state_metadata_bytes'):
        integer(value[k], 1)
    need(value['state_array_cap'] <= 4096, 'bounded safe state members')
    slots = value['provider_slots']
    need(type(slots) is list and len(slots) <= 16, 'finite predeclared provider slots')
    names = set()
    for slot in slots:
        need(type(slot) is dict and set(slot) == {'name', 'prompt', 'input_width', 'output_width', 'axis'}, 'positive typed slot')
        need(type(slot['name']) is str and slot['name'] and slot['name'] not in names, 'unique slot')
        names.add(slot['name'])
        need(type(slot['prompt']) is str and 0 < len(slot['prompt'].encode()) <= 32768
             and slot['axis'] in ('training', 'query', 'one'), 'frozen prompt and complete declared row axis')
        integer(slot['input_width'], 1); integer(slot['output_width'], 1)
    return value

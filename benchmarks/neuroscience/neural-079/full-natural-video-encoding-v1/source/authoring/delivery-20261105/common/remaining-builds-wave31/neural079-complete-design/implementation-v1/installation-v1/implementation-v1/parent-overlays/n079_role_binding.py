"""Closed pure binding of original observed role identities, never live guesses.

H remains historical after a one-shot completes. Concrete callers retain original
wait/EOF/product evidence and separately recheck only required-live identities.
No source, files, clock, identity, permission or scientific effect is acquired here.
"""
import copy

ROLE_ORDER = ('observer', 'issuer', 'supervisor', 'provider', 'features', 'assembler',
              'grams', 'references', 'controller', 'grader')
H_ORDER = ROLE_ORDER + ('finalizer',)
CALLERS = {'observer': ('finalizer',) + ROLE_ORDER[1:],
           'issuer': ('finalizer',) + ROLE_ORDER[2:],
           'supervisor': ('finalizer', 'controller'), 'provider': ('finalizer', 'controller')}
SERVICES = {'observer': ('listen',), 'issuer': ('listen', 'observer'),
            'supervisor': ('listen',), 'provider': ('listen',),
            'features': (), 'assembler': (), 'grams': (), 'references': (),
            'controller': ('observer', 'supervisor', 'provider'), 'grader': ()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names), 'exact binding fields')


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'non-Boolean observed integer')


def _pin(value):
    fields(value, ('bytes', 'sha256')); integer(value['bytes'])
    require(type(value['sha256']) is str and len(value['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in value['sha256']), 'exact source pin')


def _identity(value):
    fields(value, ('pid', 'uid', 'gid', 'start_ticks', 'boot_id', 'executable', 'namespaces', 'cgroup'))
    for key in ('pid', 'uid', 'gid', 'start_ticks'):
        integer(value[key], 1 if key in ('pid', 'start_ticks') else 0)
    require(type(value['boot_id']) is str and value['boot_id'] and
            type(value['cgroup']) is str and value['cgroup'].startswith('0::/') and
            value['cgroup'].endswith('\n') and value['cgroup'].count('\n') == 1,
            'actual boot and unified membership form')
    fields(value['executable'], ('device', 'inode'))
    integer(value['executable']['device']); integer(value['executable']['inode'], 1)
    fields(value['namespaces'], ('mnt', 'pid', 'user', 'net', 'ipc', 'uts', 'cgroup'))
    for pair in value['namespaces'].values():
        require(type(pair) is list and len(pair) == 2, 'actual namespace inode pair')
        integer(pair[0]); integer(pair[1], 1)


def _H(value):
    fields(value, H_ORDER)
    for item in value.values():
        _identity(item)
    require(len({(x['boot_id'], x['pid'], x['start_ticks']) for x in value.values()}) == 11,
            'eleven distinct original processes')
    require(len({x['boot_id'] for x in value.values()}) == 1, 'one original host boot')


def role_map(finalizer_admission, blocked_roles):
    fields(finalizer_admission, ('selection', 'receipts', 'observed_identity', 'source_pin'))
    selected = finalizer_admission['selection']
    require(type(selected) is dict and selected.get('role') == 'finalizer' and
            selected.get('role_identity') == finalizer_admission['observed_identity'] and
            selected.get('source_manifest_pin') == finalizer_admission['source_pin'],
            'actual authenticated finalizer observation supplied by outer')
    fields(blocked_roles, ROLE_ORDER)
    H = {}
    for role in ROLE_ORDER:
        fields(blocked_roles[role], ('initial_identity', 'blueprint_pin'))
        _pin(blocked_roles[role]['blueprint_pin'])
        H[role] = copy.deepcopy(blocked_roles[role]['initial_identity'])
    H['finalizer'] = copy.deepcopy(finalizer_admission['observed_identity'])
    _H(H)
    return H


def _marker(role):
    require(role in H_ORDER, 'closed source role reference')
    return {'$n079_role': role}


def _participant_roles(all_templates, budget_transport):
    fields(all_templates, ROLE_ORDER)
    fields(budget_transport, ('socket', 'endpoint', 'participant'))
    mapping = {}
    for role in ROLE_ORDER[1:]:
        budget = all_templates[role]['budget']
        fields(budget, ('socket', 'peer', 'participant', 'allocation_pin', 'endpoint', 'source_pin'))
        participant = budget['participant']
        require(type(participant) is str and participant and participant not in mapping,
                'one unique actual charged participant per non-observer role')
        mapping[participant] = role
    participant = budget_transport['participant']
    require(type(participant) is str and participant and participant not in mapping,
            'distinct actual finalizer cost participant')
    mapping[participant] = 'finalizer'
    participants = all_templates['observer']['role_payload']['participants']
    fields(participants, mapping)
    for participant, record in participants.items():
        fields(record, ('identity', 'source_pin', 'work_ids', 'dimensions'))
        _pin(record['source_pin'])
        for name in ('work_ids', 'dimensions'):
            require(type(record[name]) is list and record[name] and
                    all(type(x) is str and x for x in record[name]) and
                    len(set(record[name])) == len(record[name]), 'fixed unique participant ownership')
    return mapping


def _slots(role, value, participant_roles):
    require(role in ROLE_ORDER and type(value) is dict, 'one complete selected role template')
    require(value['context']['role'] == role, 'role/template identity')
    fields(value['services'], SERVICES[role])
    slots = [(value['authority'], 'peer', 'issuer')]
    if role == 'observer':
        require(value['budget'] is None, 'observer owns the actual local authoritative budget')
    else:
        slots.append((value['budget'], 'peer', 'observer'))
    for service in SERVICES[role]:
        if service == 'listen':
            continue
        slots.append((value['services'][service], 'peer', service))
    if role == 'observer':
        participants = value['role_payload']['participants']
        fields(participants, participant_roles)
        slots += [(participants[name], 'identity', target) for name, target in participant_roles.items()]
    return slots


def bind_identity_slots(role, template, all_templates, budget_transport, H):
    _H(H); participants = _participant_roles(all_templates, budget_transport)
    require(template == all_templates[role], 'original exact selected role template')
    result = copy.deepcopy(template)
    for parent, key, target in _slots(role, result, participants):
        require(parent.get(key) == _marker(target), 'exact source-owned symbolic identity slot')
        parent[key] = copy.deepcopy(H[target])
    if role in CALLERS:
        listen = result['services']['listen']
        require(listen['peers'] == [_marker(x) for x in CALLERS[role]], 'exact closed caller-role roster')
        listen['peers'] = [copy.deepcopy(H[x]) for x in CALLERS[role]]
    # Closed whole-value comparison is performed by the caller after its only
    # permitted data-derived metadata composition. This step touches identities only.
    return result


def validate_identity_slots(role, config, all_templates, budget_transport, H):
    _H(H); participants = _participant_roles(all_templates, budget_transport)
    for parent, key, target in _slots(role, config, participants):
        require(parent.get(key) == H[target], 'actual original identity at every fixed destination')
    if role in CALLERS:
        require(config['services']['listen']['peers'] == [H[x] for x in CALLERS[role]],
                'actual exact caller identity roster')
    if role == 'observer':
        original = all_templates['observer']['role_payload']['participants']
        for name, item in config['role_payload']['participants'].items():
            require({k: v for k, v in item.items() if k != 'identity'} ==
                    {k: v for k, v in original[name].items() if k != 'identity'},
                    'participant source/work/dimension ownership unchanged')
    return config


def binding_contract():
    """Canonical source-owned contract identity; no operator extensibility."""
    return {'schema': 'n079_closed_identity_binding_contract_v1',
            'roles': list(ROLE_ORDER), 'H_order': list(H_ORDER),
            'listener_callers': {k: list(v) for k, v in CALLERS.items()},
            'services': {k: list(v) for k, v in SERVICES.items()},
            'destinations': ['authority.peer', 'nonobserver.budget.peer',
                'named_service.peer', 'daemon.services.listen.peers', 'observer.participants.identity'],
            'projection_exceptions': ['context.source_admission', 'context.effect_admission.issuer_evidence'],
            'lifecycle': 'original_creation_roster; prior_one_shots_require_original_completion_not_live_PID'}

"""Build finite source/configuration payloads; never issue an execution grant."""
import copy
import hashlib
import json
from pathlib import Path

import configuration as c
import runtime_binding as r

ROOT, HERE = c.ROOT, c.HERE
PREFIX = HERE.relative_to(ROOT).as_posix()
Q = 'authoring/delivery-20261105/common/remaining-builds-wave40'
SHARED = Q + '/isolated-offline-actor-source-20261115-v1'
MODULES = {name: PREFIX + '/' + filename for name, filename in (
    ('configuration', 'configuration.py'), ('operation_owner', 'operation_owner.py'),
    ('producer', 'adaptive_producer.py'), ('actor_backend', 'actor_backend.py'),
    ('controller', 'controller.py'), ('entrypoint', 'entrypoint.py'))}
MODULES.update({name: SHARED + '/' + name + '.py'
                for name in ('actor_contract', 'actor_stream', 'actor_runtime', 'actor_service')})
MODULES.update(wire=Q + '/neural017-interactive-transport-source-20261115-v1/docker_wire.py',
               live=Q + '/dmfc-live-four-cell-transport-20261115-v1/live_adapter.py')
SHARED_PINS = {
    'actor_contract': (8207, '1a063e19f21a5d03808db87ae1437046813f1a57368d13d90415c26792797c4c'),
    'actor_stream': (10311, '1af9488f933be4a67cfc065d513c5298a27b3fcc2d953ad16ec9bfe437ce652b'),
    'actor_runtime': (16268, '3622321088d2356a3055258950e393e6327c192f3915900ad5fca7c2e69a7eef'),
    'actor_service': (4735, '6d6144eaeb94c40b68a53b2d2e1774a5aa47622a3f07f07b481c4d274c9dd199')}


def descriptor(path):
    path = Path(path); body = c.capture(path, 1048576)
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest()}


def source_freeze():
    names = set(r.required_sources()) | set(MODULES.values()) | {
        PREFIX + '/runtime_binding.py', PREFIX + '/OPERATION_PROFILE.json',
        PREFIX + '/offline_actor.py', PREFIX + '/numerical-policy/program.py',
        PREFIX + '/numerical-policy/METHOD.json',
        Q + '/neural017-interactive-transport-source-20261115-v1/unix_arm.py',
        Q + '/neural017-adaptive-protocol-source-20261114-v1/revision-v2/adaptive_protocol.py',
        Q + '/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'}
    names.update(PREFIX + '/actor-configs/' + key + '.json' for key in c.CONTEXTS)
    files = {name: {k: v for k, v in descriptor(ROOT / name).items() if k != 'path'} for name in sorted(names)}
    for name, expected in SHARED_PINS.items():
        c.need((files[MODULES[name]]['bytes'], files[MODULES[name]]['sha256']) == expected,
               'exact independently reviewed shared actor source')
    return {'schema': 'dmfc-complete-four-cell-source/v1', 'execution_authority': False,
        'entrypoint': {'path': MODULES['entrypoint'], **files[MODULES['entrypoint']]},
        'modules': dict(MODULES), 'files': files,
        'scientific_scope': {'candidate_id': 'NEURAL-095', 'train': 748, 'cases_per_cell': 258,
            'views': ['cue_only', 'neural'], 'modes': list(c.MODES), 'reference_count': 5,
            'maximum_numerical_units': 46, 'new_reference_fits': 0}}


def configuration_payload(output_root, freeze_pin, runtime_identity):
    """Return the exact payload a separately issued root request must bind."""
    out = Path(output_root).absolute()
    actor = descriptor(HERE / 'offline_actor.py')
    return {'schema': 'dmfc-complete-four-cell-config/v1', 'repository_root': str(ROOT),
        'output_root': str(out), 'successor_freeze': freeze_pin,
        'runtime_identity': copy.deepcopy(runtime_identity),
        'host_budget': {'artifact_bytes': 1073741824, 'receipt_bytes': 268435456, 'read_bytes': 8589934592},
        'limits': copy.deepcopy(c.LIMITS), 'reservation_policy': copy.deepcopy(c.RESERVATIONS),
        'numerical_tool': descriptor(HERE / 'numerical-policy/program.py'),
        'method': descriptor(HERE / 'numerical-policy/METHOD.json'),
        'actor': {'arms': {key: {'actor_context': key, 'context_dir': str(out / 'actors' / key),
            'program': dict(actor), 'config': descriptor(HERE / 'actor-configs' / (key + '.json'))}
            for key in c.CONTEXTS}}}


def attach_request(payload, request_pin):
    """Verify an existing root request; this function cannot create one."""
    c.need('request' not in payload, 'unattached payload')
    request = c.decode(c.checked(ROOT, request_pin))
    c.need(request['configuration_payload_sha256'] == hashlib.sha256(c.encode(payload)).hexdigest(),
           'existing root request binds this entire payload')
    return {**copy.deepcopy(payload), 'request': dict(request_pin)}


def write_json(path, value):
    """Source/operator authoring helper; no overwrite or dispatch."""
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    c.need(len(body) <= 262144, 'bounded authored metadata')
    with Path(path).open('xb') as f:
        f.write(body)
    return descriptor(Path(path))

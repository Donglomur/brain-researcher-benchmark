"""Explicit root-policy capacity admission from a pinned complete image census.

Standalone stdlib only. No filesystem measurement, daemon/process invocation,
allocation, source approval or execution authority is provided by this module.
The four inventory helpers below are exact source extracts from the held reader.
"""
from datetime import datetime, timezone
import json
import math
import re
from pathlib import PurePosixPath

REUSED_SOURCE = {
    'path': 'authoring/cerebellar-finite-task-v1/capacity-complete-inventory-v1/capacity.py',
    'bytes': 6751,
    'sha256': '42163ba0071e3c1752e16ff097466dca730d708b4fba61b7ce53970fa42d0bb1',
}
MAX_AGE_SECONDS=900
IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'

def need(ok,message):
    if not ok:raise ValueError(message)

def positive(v):return type(v) is int and 0<v<=1000000000000

def strict_json(raw):
    def pairs(items):
        result={}
        for k,v in items:
            need(k not in result,'Unambiguous inventory JSON keys')
            result[k]=v
        return result
    def nonfinite(value):raise ValueError('Nonfinite inventory JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)

def inventory(value,now):
    """Validate actual pinned root census; now is explicit for deterministic controls."""
    need(value['complete_image_inventory_argv']==['docker','image','ls','--all','--no-trunc','--quiet'],
         'Complete inventory includes untagged and intermediate images')
    ids=value['image_ids']; rows=strict_json(value['image_inspect_stdout']); compact=value['image_sizes']
    need(type(ids) is list and 1<=len(ids)<=256 and all(type(x) is str and re.fullmatch(r'sha256:[0-9a-f]{64}',x) for x in ids)
         and ids==sorted(set(ids)) and IMAGE in ids,'Bounded unique complete immutable image IDs')
    need(value['image_inspect_argv']==['docker','image','inspect',*ids] and
         type(value['image_inspect_returncode']) is int and value['image_inspect_returncode']==0 and
         value['image_inspect_stderr']=='','Successful inspection of every enumerated image')
    need(type(rows) is list and type(compact) is list and len(rows)==len(compact)==len(ids)
         and [r['Id'] for r in rows]==ids and [r['id'] for r in compact]==ids,'Complete ordered inventory/inspection joins')
    for a,b in zip(rows,compact,strict=True):
        need(positive(a['Size']) and type(b['size']) is int and a['Size']==b['size'],'Exact complete per-ID size join')
    total=sum(x['Size'] for x in rows)
    need(positive(total) and type(value['all_image_metadata_bytes']) is int and total==value['all_image_metadata_bytes'],
         'Recomputed full image sum, never a selected tagged subtotal')
    measured=datetime.fromisoformat(value['measured_utc'])
    need(measured.tzinfo is not None and now.tzinfo is not None,'Explicit timezone for census freshness')
    age=(now-measured).total_seconds()
    need(math.isfinite(age) and 0<=age<=MAX_AGE_SECONDS,'Fresh complete root inventory within15 minutes; future/stale rejected')
    need(positive(value['project_allocated_bytes']) and positive(value['free_bytes']) and
         type(value['fragment_bytes']) is int and 0<value['fragment_bytes']<=4096,'Finite measured host extents')
    return {'image_metadata_bytes':total,'image_count':len(ids),'measured_utc':value['measured_utc'],
            'inventory_age_seconds':age,'image_metadata_not_physical_Docker_usage':True}


DYNAMIC_KEYS = frozenset((
    'policy', 'inventory', 'aggregate_ceiling_bytes', 'minimum_free_bytes',
    'image_metadata_bytes', 'own_reserve_bytes', 'other_reserve_bytes',
    'current_inventory_attested', 'justification',
))
POLICY_KEYS = frozenset((
    'schema_version', 'candidate_id', 'prospective', 'execution_authority',
    'allocation_authority', 'dynamic_capacity',
))
MINIMUM_CEILING = 26000000000
MAXIMUM_BYTES = 1000000000000
MINIMUM_FREE = 15000000000


def _same(left, right):
    """JSON-value equality that never equates bool/int or int/float tokens."""
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _descriptor(value, maximum):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'},
         'Exact capacity metadata descriptor')
    path = value['path']
    need(type(path) is str and 0 < len(path) <= 512 and '\\' not in path
         and '\x00' not in path and '\n' not in path and '\r' not in path,
         'Bounded ordinary repository-relative metadata path')
    parts = PurePosixPath(path)
    need(not parts.is_absolute() and '..' not in parts.parts and str(parts) == path
         and parts.suffix == '.json', 'Canonical capacity JSON path')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= maximum
         and type(value['sha256']) is str
         and re.fullmatch(r'[0-9a-f]{64}', value['sha256']) is not None,
         'Bounded capacity metadata bytes and SHA256')
    return dict(value)


def storage(admitted, project, free):
    """Check caller-measured live allocated project bytes and available bytes.

    Measurement and its freshness are route-owned. This function performs no I/O
    and never changes the explicitly admitted ceiling, floor or reservations.
    """
    need(type(admitted) is dict and positive(project) and positive(free),
         'Finite integer live project/free measurements')
    ceiling = admitted['aggregate_ceiling_bytes']
    floor = admitted['minimum_free_bytes']
    images = admitted['image_metadata_bytes']
    own = admitted['own_reserve_bytes']
    other = admitted['other_reserve_bytes']
    need(type(ceiling) is int and MINIMUM_CEILING <= ceiling <= MAXIMUM_BYTES
         and type(floor) is int and floor == MINIMUM_FREE
         and positive(images) and positive(own)
         and type(other) is int and 0 <= other <= ceiling
         and type(admitted['reserve_bytes']) is int
         and admitted['reserve_bytes'] == own + other,
         'Exact admitted ceiling, image total, floor and reservations')
    reserve = own + other
    aggregate = project + images + reserve
    available = free - reserve
    need(aggregate <= ceiling and available >= floor,
         'Complete-image reserved capacity within explicit ceiling and 15GB free floor')
    return {
        'project_allocated_bytes': project, 'free_bytes': free,
        'image_metadata_bytes': images, 'own_reserve_bytes': own,
        'other_reserve_bytes': other, 'reserve_bytes': reserve,
        'aggregate_planning_bytes': aggregate,
        'free_after_reserves_bytes': available,
        'aggregate_ceiling_bytes': ceiling, 'minimum_free_bytes': floor,
    }


def validate(review, allocation, pinned, *, candidate_id, own_reserve,
             minimum_other, now=None):
    """Admit explicit matching capacity metadata; never authorize a run.

    ``pinned(descriptor)`` must authenticate exact bounded bytes, ordinary file
    identity/path and strict JSON before returning a dict. The caller separately
    authenticates review/allocation authority, candidate/output/timing identity,
    current cost, source closure and independent source review.
    """
    need(type(review) is dict and type(allocation) is dict and callable(pinned),
         'Root review/allocation metadata and authenticated JSON reader')
    need(type(candidate_id) is str and 0 < len(candidate_id) <= 128
         and candidate_id.strip() == candidate_id and positive(own_reserve)
         and type(minimum_other) is int and 0 <= minimum_other <= MAXIMUM_BYTES,
         'Route-fixed candidate and unchanged reservation requirements')
    value = review['dynamic_capacity']
    need(type(value) is dict and set(value) == DYNAMIC_KEYS,
         'Exactly nine dynamic capacity fields')
    policy_pin = _descriptor(value['policy'], 32768)
    inventory_pin = _descriptor(value['inventory'], 2000000)
    ceiling = value['aggregate_ceiling_bytes']
    other = value['other_reserve_bytes']
    need(type(ceiling) is int and MINIMUM_CEILING <= ceiling <= MAXIMUM_BYTES
         and type(value['minimum_free_bytes']) is int
         and value['minimum_free_bytes'] == MINIMUM_FREE
         and positive(value['image_metadata_bytes'])
         and type(value['own_reserve_bytes']) is int
         and value['own_reserve_bytes'] == own_reserve
         and type(other) is int and minimum_other <= other <= ceiling
         and value['current_inventory_attested'] is True
         and type(value['justification']) is str
         and 1 <= len(value['justification']) <= 2000
         and bool(value['justification'].strip()),
         'Explicit bounded root ceiling, 15GB floor, full image total and unchanged reserves')
    need(type(allocation.get('dynamic_capacity')) is dict
         and _same(allocation['dynamic_capacity'], value),
         'Allocation and review bind identical typed dynamic capacity')
    policy = pinned(policy_pin)
    need(type(policy) is dict and set(policy) == POLICY_KEYS
         and type(policy['schema_version']) is int and policy['schema_version'] == 1
         and policy['candidate_id'] == candidate_id
         and policy['prospective'] is True
         and policy['execution_authority'] is False
         and policy['allocation_authority'] is False,
         'Candidate-bound prospective policy provides no execution or allocation authority')
    expected_policy = {key: item for key, item in value.items() if key != 'policy'}
    need(type(policy['dynamic_capacity']) is dict
         and _same(policy['dynamic_capacity'], expected_policy),
         'Policy binds exactly the same dynamic object except its own descriptor')
    measured = pinned(inventory_pin)
    need(type(measured) is dict, 'Pinned complete image census object')
    need(type(measured.get('measured_utc')) is str
         and 1 <= len(measured['measured_utc']) <= 64,
         'Bounded census timestamp in returned scalar metadata')
    clock = datetime.now(timezone.utc) if now is None else now
    need(type(clock) is datetime, 'Explicit datetime for capacity freshness')
    census = inventory(measured, clock)
    need(value['image_metadata_bytes'] == census['image_metadata_bytes'],
         'Root image amount equals the complete recomputed census sum')
    census = dict(census, project_allocated_bytes=measured['project_allocated_bytes'],
                  free_bytes=measured['free_bytes'], fragment_bytes=measured['fragment_bytes'])
    admitted = {
        'candidate_id': candidate_id, 'aggregate_ceiling_bytes': ceiling,
        'minimum_free_bytes': MINIMUM_FREE,
        'image_metadata_bytes': census['image_metadata_bytes'],
        'own_reserve_bytes': own_reserve, 'other_reserve_bytes': other,
        'reserve_bytes': own_reserve + other, 'policy': policy_pin,
        'inventory': inventory_pin, 'census': census,
        'justification': value['justification'],
    }
    storage(admitted, census['project_allocated_bytes'], census['free_bytes'])
    need(len(json.dumps(admitted, sort_keys=True, separators=(',', ':'),
                        allow_nan=False).encode('ascii')) < 8000,
         'Admitted scalar capacity metadata remains below 8000 serialized bytes')
    return admitted

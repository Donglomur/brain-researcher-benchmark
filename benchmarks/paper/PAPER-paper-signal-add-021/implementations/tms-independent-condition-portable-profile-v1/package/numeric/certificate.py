"""Strict inert certificate format; authentic source authority is NOT implemented.

The common exact interval/schema path is exercised using an explicit fixture
profile. Production admission stays closed until a separately qualified source
constructor, runtime, owned result and private custody path exists.
"""
from dataclasses import dataclass
import hashlib
import json
import re
from kernel import D, P, MAX_WIDTH, Interval, Window, Refusal, require

FIXTURE_PROFILE = 'tms_real_interval_248_inert_fixture_v1'
MAPS = ('NT.delay1', 'NT.delay2', 'T.delay1', 'T.delay2')
LABELS = tuple('fixture-channel-%02d' % i for i in range(62))
MAX_BODY = 262144
INTEGER_TEXT = re.compile(r'(?:0|-?[1-9][0-9]*)\Z', re.ASCII)


def sha(body):
    require(type(body) is bytes, 'exact byte body')
    return hashlib.sha256(body).hexdigest()


def hash_text(value):
    require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'canonical SHA256')
    return value


def pin(body):
    return {'bytes': len(body), 'sha256': sha(body)}


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), 'closed schema keys')


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n').encode()


def decode(body):
    require(type(body) is bytes and 0 < len(body) <= MAX_BODY, 'bounded exact certificate bytes')
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    def constant(value):
        raise Refusal('nonfinite JSON constant')
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, Refusal):
            raise
        raise Refusal('invalid bounded JSON') from exc


def endpoint(value):
    require(type(value) is str and 1 <= len(value) <= 235 and INTEGER_TEXT.fullmatch(value) is not None, 'canonical bounded integer endpoint text')
    result = int(value)
    require(result.bit_length() <= P + 1 and -D <= result <= D, 'proved endpoint range')
    return result


@dataclass(frozen=True)
class FixtureContext:
    fixture_sha256: str
    source_lock_sha256: str
    runtime_sha256: str
    attempt: str

    def __post_init__(self):
        hash_text(self.fixture_sha256); hash_text(self.source_lock_sha256); hash_text(self.runtime_sha256)
        require(type(self.attempt) is str and re.fullmatch(r'[a-z0-9-]{1,64}', self.attempt) is not None, 'finite fixture attempt')

    def binding(self):
        return {'fixture_sha256': self.fixture_sha256, 'source_lock_sha256': self.source_lock_sha256,
                'runtime_sha256': self.runtime_sha256, 'attempt': self.attempt,
                'source_authority': 'inert_fixture_only_no_authentic_source'}


@dataclass(frozen=True)
class AdmittedFixture:
    slots: tuple
    body_pin: dict
    context: FixtureContext


def admit_fixture_reference(body, expected_pin, context):
    require(type(context) is FixtureContext, 'explicit fixture context')
    require(type(body) is bytes and 0 < len(body) <= MAX_BODY, 'bounded exact certificate bytes before hashing')
    keys(expected_pin, {'bytes', 'sha256'})
    require(type(expected_pin['bytes']) is int and expected_pin['bytes'] > 0, 'strict reference byte count')
    hash_text(expected_pin['sha256'])
    require(pin(body) == expected_pin, 'reference byte/hash join')
    doc = decode(body)
    keys(doc, {'schema', 'authentic_source', 'fractional_bits', 'domain_bound', 'map_order', 'labels', 'binding', 'slots'})
    require(doc['schema'] == FIXTURE_PROFILE and type(doc['schema']) is str, 'explicit fixture profile')
    require(doc['authentic_source'] is False, 'fixture never authentic')
    require(type(doc['fractional_bits']) is int and doc['fractional_bits'] == P, 'fixed strict fractional bits')
    require(type(doc['domain_bound']) is int and doc['domain_bound'] == 1000, 'fixed strict prospective domain')
    require(type(doc['map_order']) is list and doc['map_order'] == list(MAPS), 'exact map order')
    require(type(doc['labels']) is list and all(type(x) is str for x in doc['labels']) and doc['labels'] == list(LABELS), 'exact fixture labels')
    keys(doc['binding'], set(context.binding()))
    require(all(type(x) is str for x in doc['binding'].values()) and doc['binding'] == context.binding(), 'fixture source/runtime/attempt binding')
    rows = doc['slots']
    require(type(rows) is list and len(rows) == 248, 'all248 fixed slots')
    slots = []
    for i, row in enumerate(rows):
        keys(row, {'index', 'map', 'channel', 'undefined', 'lo', 'hi', 'time_counts', 'frequency_count'})
        require(type(row['index']) is int and row['index'] == i, 'strict ordered slot index')
        require(type(row['map']) is str and row['map'] == MAPS[i // 62], 'slot map identity')
        require(type(row['channel']) is str and row['channel'] == LABELS[i % 62], 'slot channel identity')
        require(type(row['undefined']) is bool, 'strict undefined Boolean')
        tc = row['time_counts']
        require(type(tc) is list and len(tc) == 7 and all(type(x) is int and 0 <= x <= 28 for x in tc), 'exact nested time support')
        fc = row['frequency_count']
        require(type(fc) is int and 0 <= fc <= 7 and fc == sum(x > 0 for x in tc), 'exact nested frequency support')
        if row['undefined']:
            require(row['lo'] is None and row['hi'] is None and fc == 0, 'undefined has no numeric endpoints or support')
            interval = None
        else:
            require(fc > 0, 'defined map has support')
            lo, hi = endpoint(row['lo']), endpoint(row['hi'])
            require(lo <= hi and hi - lo <= MAX_WIDTH, 'ordered final certificate diameter')
            interval = Interval(lo, hi)
        slots.append(Window(interval, tuple(tc), fc))
    return AdmittedFixture(tuple(slots), dict(expected_pin), context)


def pack_fixture_reference(windows, context):
    require(type(context) is FixtureContext and type(windows) in (tuple, list) and len(windows) == 248, 'complete explicit fixture construction')
    rows = []
    for i, value in enumerate(windows):
        require(type(value) is Window, 'exact window result')
        iv = value.interval
        require(iv is None or type(iv) is Interval, 'exact window interval')
        rows.append({'index': i, 'map': MAPS[i // 62], 'channel': LABELS[i % 62],
                     'undefined': iv is None, 'lo': None if iv is None else str(iv.lo),
                     'hi': None if iv is None else str(iv.hi), 'time_counts': list(value.time_counts),
                     'frequency_count': value.frequency_count})
    body = encode({'schema': FIXTURE_PROFILE, 'authentic_source': False, 'fractional_bits': P,
                   'domain_bound': 1000, 'map_order': list(MAPS), 'labels': list(LABELS),
                   'binding': context.binding(), 'slots': rows})
    admit_fixture_reference(body, pin(body), context)
    return body


def admit_production_reference(*args, **kwargs):
    """No fallback from fixture validity to authentic authority, and no data access.

    A separate authentic constructor/receipt/custody implementation is required.
    This explicit closed gate must remain until that path is independently qualified.
    """
    raise Refusal('production source custody is not qualified; fixtures are never production references')

"""Exact continuous interval scores; fixture integration only, production stays closed."""
import math
import struct
from kernel import RAW_UNIT, P, Rat, add, mul, exact_float, require
from certificate import admit_fixture_reference, admit_production_reference, MAPS

SLOTS = 248
CANDIDATE_BYTES = SLOTS * 9


def candidate_bytes(values):
    require(type(values) in (tuple, list) and len(values) == SLOTS and all(type(v) is float for v in values), 'all248 binary64 candidate values')
    require(all(not math.isinf(v) for v in values), 'candidate infinity refused')
    return struct.pack('<248d', *values) + bytes(int(math.isnan(v)) for v in values)


def decode_candidate(body):
    require(type(body) is bytes and len(body) == CANDIDATE_BYTES, 'complete fixed candidate bytes')
    values = struct.unpack('<248d', body[:SLOTS * 8])
    flags = body[SLOTS * 8:]
    require(all(v in (0, 1) for v in flags), 'candidate mask bytes')
    require(all(not math.isinf(v) and bool(flag) == math.isnan(v) for v, flag in zip(values, flags)), 'candidate value/category coherence')
    return values, tuple(bool(x) for x in flags)


def rational(n, d):
    value = Rat(n, d)
    return {'numerator': str(value.n), 'denominator': str(value.d)}


def metrics(rows):
    finite = [x for x in rows if x is not None]
    if not finite:
        return {'finite_slots': 0, 'MAE': None, 'Linf': None}
    lower_sum = upper_sum = 0
    for lo, hi in finite:
        lower_sum = add(lower_sum, lo)
        upper_sum = add(upper_sum, hi)
    return {'finite_slots': len(finite),
            'MAE': {'lower': rational(lower_sum, mul(RAW_UNIT, len(finite))),
                    'upper': rational(upper_sum, mul(RAW_UNIT, len(finite)))},
            'Linf': {'lower': rational(max(x[0] for x in finite), RAW_UNIT),
                     'upper': rational(max(x[1] for x in finite), RAW_UNIT)}}


def score_fixture(*, candidate_body, reference_body, reference_pin, context):
    """Trusted inert integration; this confers no authentic reference authority."""
    reference = admit_fixture_reference(reference_body, reference_pin, context)
    values, flags = decode_candidate(candidate_body)
    require(all(flag == (slot.interval is None) for flag, slot in zip(flags, reference.slots)), 'reference category mismatch; no slot filtering')
    scale = 1 << (1074 - P)
    errors, details = [], []
    outside_range = 0
    for i, (value, flag, slot) in enumerate(zip(values, flags, reference.slots)):
        if flag:
            errors.append(None)
            details.append({'index': i, 'category': 'source_undefined', 'signed': None, 'absolute': None})
            continue
        z = exact_float(value)
        coordinate = mul(z.n, RAW_UNIT // z.d)
        lo = add(coordinate, -mul(slot.interval.hi, scale))
        hi = add(coordinate, -mul(slot.interval.lo, scale))
        low_abs = 0 if lo <= 0 <= hi else min(abs(lo), abs(hi))
        high_abs = max(abs(lo), abs(hi))
        errors.append((low_abs, high_abs))
        outside_range += int(abs(value) > 1.0)
        details.append({'index': i, 'category': 'finite',
                        'signed': {'lower': rational(lo, RAW_UNIT), 'upper': rational(hi, RAW_UNIT)},
                        'absolute': {'lower': rational(low_abs, RAW_UNIT), 'upper': rational(high_abs, RAW_UNIT)}})
    return {'schema': 'tms_real_interval_248_inert_score_v1', 'authentic_source': False,
            'reference_pin': reference_pin, 'all248_categories_match': True,
            'undefined_slots': sum(flags), 'finite_slots': SLOTS - sum(flags),
            'informative': not all(flags), 'out_of_proved_range_candidate_values': outside_range,
            'pooled': metrics(errors), 'maps': {name: metrics(errors[i * 62:(i + 1) * 62]) for i, name in enumerate(MAPS)},
            'slots': details, 'binary_threshold': None, 'scientific_tolerance': None,
            'native_parity_claimed': False, 'production_authority_claimed': False}


def score_production(*args, **kwargs):
    # Every production entry takes the closed authority gate; fixture APIs cannot
    # become a production fallback by changing a manifest's profile/hash string.
    admit_production_reference(*args, **kwargs)
    raise AssertionError('unreachable unqualified production scorer')

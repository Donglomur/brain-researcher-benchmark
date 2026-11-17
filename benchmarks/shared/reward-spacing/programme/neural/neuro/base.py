"""Neural caller bridge to the immutable paper-owned shared runtime."""
from pathlib import Path
from .reward_common import (ContractError, need as require,
                            finite_number as finite, strict_json_loads as loads,
                            canonical_json_bytes as encode, object_sha256 as digest,
                            native_integral, native_error, sha256, read_member,
                            safe_member, receipt)


def read_json(path, cap=8 * 1024 * 1024):
    path = Path(path)
    return loads(read_member(path.parent, path.name, cap), cap)


def write_json(path, obj, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb' if exclusive else 'wb') as stream:
        stream.write(encode(obj))


def observed_window(times, values, start, stop, max_gap):
    """Trim BEFORE common integration: observed samples only; no edge interpolation."""
    require(len(times) == len(values), 'window_shape')
    require(all(finite(b) > finite(a) for a, b in zip(times, times[1:])), 'clock_order')
    selected = [i for i, t in enumerate(times) if start <= finite(t) < stop]
    require(len(selected) >= 2, 'insufficient_native_span')
    t = [times[i] for i in selected]
    y = [finite(values[i]) for i in selected]
    result = native_integral(t, y, t[0], t[-1], max_gap)
    require(result['covered_seconds'] > 0, 'no_observed_span')
    return {'indices': selected, 'times': t, 'values': y, **result}


def native_loss(times, truth, prediction, max_gap):
    require(len(times) >= 2, 'native_span')
    result = native_error(times, truth, prediction, times[0], times[-1], max_gap)
    for key in ('mse', 'mae', 'bias'):
        finite(result[key], 'native_' + key)
    return result

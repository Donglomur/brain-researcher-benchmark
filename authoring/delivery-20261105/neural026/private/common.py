"""NEURAL-025 bounded numerical interchange; never unpickle candidate content."""
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import zipfile

MICE = ('cfa17', 'cfa19', 'cfa20', 'cfa22', 'cfa24')
SESSIONS = (
    ('cfa17', '200825', 'M1'), ('cfa17', '200827', 'S1'),
    ('cfa19', '200820', 'M1'), ('cfa19', '200826', 'S1'),
    ('cfa20', '201114', 'M1'), ('cfa20', '201118', 'S1'),
    ('cfa22', '220605', 'M1'), ('cfa22', '220611', 'S1'),
    ('cfa24', '220727', 'M1'), ('cfa24', '220724', 'S1'))
JOINTS = ('SHDRf', 'SHDRa', 'SHDRr', 'ELBOf', 'WRSTf', 'WRSTd', 'WRSTr',
          'MCP1f', 'MCP2f', 'MCP3f', 'MCP4f', 'MCP1a', 'MCP2a', 'MCP3a',
          'MCP4a', 'MCP1o', 'MCP4o', 'P1P2', 'P2P3', 'P3P4',
          'PIP1f', 'PIP2f', 'PIP3f', 'PIP4f')
TIME_MS = tuple(range(-100, 401, 10))
MAX_TRIALS, MAX_ROIS = 4096, 4096
MAX_FILE_BYTES = 2 * 1024**3
PREDICTION_BYTES = 100 * 1024**2
COMMIT = '815b610b3beddfed5a3abf611d3a465ab9e4ce5c'


def need(value, message):
    if not value:
        raise ValueError(message)


def context_id(mouse, date, area):
    need((mouse, date, area) in SESSIONS, 'Exact imaging cohort/session')
    return f'{mouse}_{date}_{area}'


def json_load(path, cap=1024**2):
    raw = regular_bytes(path, cap)
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Finite JSON numbers'))


def regular_bytes(path, cap):
    p = Path(path)
    need(not p.is_symlink(), 'No linked input file')
    st = p.stat()
    need(stat.S_ISREG(st.st_mode) and 0 < st.st_size <= cap, 'Bounded regular file')
    with p.open('rb') as f:
        raw = f.read(cap + 1)
    need(len(raw) == st.st_size <= cap, 'Complete bounded read')
    return raw


def npz_load(np, path, keys, cap=MAX_FILE_BYTES):
    """Reject objects, extra/duplicate members and expansion before NumPy load."""
    raw = regular_bytes(path, cap)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        need(len(members) == len(keys) and {x.filename for x in members} ==
             {k + '.npy' for k in keys}, 'Exact unique NPZ members')
        need(sum(x.file_size for x in members) <= cap, 'NPZ expanded bound')
        for x in members:
            need(not x.is_dir() and not x.flag_bits & 1 and
                 x.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                 not stat.S_ISLNK(x.external_attr >> 16), 'Ordinary bounded NPY member')
            # Verify shape/product against the member extent before NumPy allocation.
            with z.open(x) as member:
                version = np.lib.format.read_magic(member)
                if version == (1, 0):
                    shape, order, dtype = np.lib.format.read_array_header_1_0(member, max_header_size=4096)
                elif version == (2, 0):
                    shape, order, dtype = np.lib.format.read_array_header_2_0(member, max_header_size=4096)
                else:
                    raise ValueError('NPY version1/2 only')
                need(dtype.kind in 'iuf' and dtype.fields is None and len(shape) <= 3
                     and all(type(n) is int and 0 < n <= 10000000 for n in shape),
                     'Bounded primitive numeric header')
                count = math.prod(shape) * dtype.itemsize
                need(count <= cap and member.tell() + count == x.file_size,
                     'NPY header shape matches exact member byte extent')
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=4096) as archive:
        result = {key: archive[key] for key in keys}
    for array in result.values():
        need(array.dtype.kind in 'iuf' and array.dtype.fields is None,
             'Primitive real numeric arrays only')
    return result


def trial_ids(np, ids):
    need(ids.ndim == 1 and ids.dtype.kind in 'iu' and
         20 <= len(ids) <= MAX_TRIALS and (ids > 0).all() and
         len(np.unique(ids)) == len(ids), 'Positive unique whole-trial IDs')
    need((np.diff(ids.astype(np.int64)) > 0).all(), 'Original chronological trial order')


def split_trials(np, ids):
    trial_ids(np, ids)
    # Prospective explicit calibration budget; no labels enter this decision.
    n = max(10, (len(ids) + 4) // 5)
    need(len(ids) - n >= 10, 'At least ten full query trials')
    return np.arange(n), np.arange(n, len(ids))


def normalized_scale(np, calibration_y):
    need(calibration_y.ndim == 3 and calibration_y.shape[1:] == (51, 48)
         and len(calibration_y) >= 10 and np.isfinite(calibration_y).all(),
         'Complete finite calibration trajectories')
    flat = calibration_y.reshape(-1, 48)
    scale = np.std(flat, axis=0, ddof=0)
    need(np.isfinite(scale).all() and (scale > 0).all(),
         'Every calibration target must have positive finite variance; do not drop targets')
    return scale


def validate_public(np, packet):
    need(set(packet) == {'train_x', 'train_y', 'train_trial_id', 'query_x', 'query_trial_id'},
         'Exact candidate packet arrays')
    tx, ty, qx = packet['train_x'], packet['train_y'], packet['query_x']
    ti, qi = packet['train_trial_id'], packet['query_trial_id']
    need(tx.ndim == qx.ndim == ty.ndim == 3 and tx.shape[1] == qx.shape[1] == 51
         and 1 <= tx.shape[2] <= MAX_ROIS and tx.shape[2] == qx.shape[2]
         and ty.shape == (len(tx), 51, 48), 'Complete session-aligned shapes')
    need(10 <= len(tx) <= MAX_TRIALS and 10 <= len(qx) <= MAX_TRIALS,
         'Complete bounded calibration/query support')
    for ids, length in ((ti, len(tx)), (qi, len(qx))):
        need(ids.ndim == 1 and ids.dtype.kind in 'iu' and len(ids) == length
             and len(np.unique(ids)) == length and (ids > 0).all(), 'Unique trial IDs')
    need(not np.intersect1d(ti, qi).size and ti.max() < qi.min(),
         'Whole trials in earlier calibration versus later query')
    need(all(np.isfinite(a).all() for a in (tx, ty, qx)), 'Finite complete public trajectories')


def validate_predictions(np, packet, expected_ids):
    need(set(packet) == {'trial_id', 'predictions'}, 'Exact arbitrary-prediction schema')
    ids, y = packet['trial_id'], packet['predictions']
    need(ids.dtype.kind in 'iu' and ids.ndim == 1 and np.array_equal(ids, expected_ids),
         'All query trial IDs once in frozen order')
    need(y.dtype.kind == 'f' and y.shape == (len(ids), 51, 48)
         and np.isfinite(y).all(), 'Finite full 51-timepoint/48-target predictions')
    return y.astype(np.float64, copy=False)


def pin(path):
    """For operator construction outputs, not a live readiness assertion."""
    p = Path(path)
    digest = hashlib.sha256()
    total = 0
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024**2), b''):
            total += len(part)
            digest.update(part)
    return {'path': p.name, 'bytes': total, 'sha256': digest.hexdigest()}


def save_json(path, value):
    p = Path(path)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')

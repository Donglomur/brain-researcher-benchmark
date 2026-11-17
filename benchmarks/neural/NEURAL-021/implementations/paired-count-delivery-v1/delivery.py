"""Exact-count visual delivery of the existing NEURAL-021 full trajectory task.

Operator-side source, not a participant sandbox. No raw NWB/private target reads,
fitting, scoring, or model calls. Only load_public authenticates the actual packet;
Packet.from_arrays is also usable for explicitly generated software controls.
"""
import hashlib
import html
import io
import json
import math
from pathlib import Path
import os
import stat
import types
import zipfile
from dataclasses import dataclass

# Resolve the unchanged companion by exact bytes, not an ambient module name.
_interface_path = Path(__file__).with_name('interface.py')
_interface_raw = _interface_path.read_bytes()
if hashlib.sha256(_interface_raw).hexdigest() != 'c748bdb0386713d505e1d5d79bec51645263b859471011df81f205168a6e61e2':
    raise ValueError('unchanged original public interface required')
interface = types.ModuleType('neural021_visual_interface')
exec(compile(_interface_raw, str(_interface_path), 'exec'), interface.__dict__)

MODES = ('direct_observation', 'typed_viewer')
CONDITIONS = ('active', 'passive')
MAX_VIEWS = 2048
PINS = {
    'cases.json': (4075, 'f5fc38ca363db9367e259c466fc017af9e8e216726b302cc6f757857554c34c0'),
    'training.npz': (497917, '5fae3b5cf74edbf99d5d4c5a4fa80d8ee1f02c55f92aa91de58d60714fe4159b'),
    'queries.npz': (127544, '64d29c93749d7b66f22d7112e7fdbe3764ffecef4b1989464f2af89801090047'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def collapse_histories(history):
    """Invert X[target_bin, history_bin, unit] = C[target_bin+history_bin, unit]."""
    require(type(history) in (list, tuple) and len(history) == 30, '30 target histories required')
    cells = [None] * 35
    for t, block in enumerate(history):
        require(type(block) in (list, tuple) and len(block) == 6, 'six history bins required')
        for h, row in enumerate(block):
            require(type(row) in (list, tuple) and len(row) == 65, 'all 65 units required')
            require(all(type(v) is int and 0 <= v <= 2**63 - 1 for v in row),
                    'nonnegative int64-domain counts required; no Boolean counts')
            row = tuple(row)
            require(cells[t + h] is None or cells[t + h] == row,
                    'overlapping histories disagree; cannot collapse without information loss')
            cells[t + h] = row
    return tuple(cells)


def expand_counts(counts):
    """Exact inverse for the selected whole-batch observations; no causal claim."""
    require(len(counts) == 35 and all(len(row) == 65 for row in counts), '35 by 65 counts required')
    return tuple(tuple(counts[t + h] for h in range(6)) for t in range(30))


def trajectory(value):
    require(type(value) in (list, tuple) and len(value) == 30, 'complete 30-bin trajectory required')
    result = []
    for pair in value:
        require(type(pair) in (list, tuple) and len(pair) == 2, 'source x/y pair required')
        require(all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 1e6 for v in pair),
                'finite nonboolean velocities within original m/s envelope required')
        result.append(tuple(pair))
    return tuple(result)


@dataclass(frozen=True)
class Trial:
    trial_id: str
    condition: str
    counts: tuple
    training_velocity: tuple | None = None


@dataclass(frozen=True)
class Packet:
    cases_bytes: bytes
    training: tuple
    queries: tuple
    observation_sha256: str

    @classmethod
    def from_arrays(cls, training, queries, cases_bytes):
        """Validate complete prepared values. Does not authenticate their origin."""
        cases = interface.strict_json(cases_bytes)
        roster = interface.validate_queries(cases)
        require(len(roster) == 92 and [r['condition'] for r in roster].count('active') == 52
                and [r['condition'] for r in roster].count('passive') == 40, 'exact 52 active / 40 perturbation scope')
        require(set(cases) == {'schema', 'task_id', 'time_bins', 'feature_shape', 'units', 'conditions', 'queries'}
                and cases['feature_shape'] == [30, 6, 65] and cases['units'] == 'm/s'
                and cases['conditions'] == {'0': 'active', '1': 'passive'}, 'exact prepared public metadata')
        require(set(training) == {'spike_counts', 'condition', 'velocity_m_s'}
                and set(queries) == {'spike_counts', 'condition'}, 'public-only packet keys required')
        output = []
        for packet, n, is_train in ((training, 272, True), (queries, 92, False)):
            require(len(packet['spike_counts']) == n and len(packet['condition']) == n, 'complete 272/92 scope')
            require(all(type(c) is int and c in (0, 1) for c in packet['condition'])
                    and set(packet['condition']) == {0, 1}, 'both typed integer conditions required')
            if is_train:
                require(len(packet['velocity_m_s']) == n, '272 complete training labels required')
            rows = []
            for i, (history, condition) in enumerate(zip(packet['spike_counts'], packet['condition'])):
                condition = CONDITIONS[condition]
                if not is_train:
                    require(condition == roster[i]['condition'], 'query row / roster condition mismatch')
                rows.append(Trial(f't{i:04d}' if is_train else roster[i]['trial_id'], condition,
                                  collapse_histories(history),
                                  trajectory(packet['velocity_m_s'][i]) if is_train else None))
            output.append(tuple(rows))
        # The same complete canonical observation identity binds both delivery arms.
        content = {'cases_sha256': sha(cases_bytes), 'training': [r.__dict__ for r in output[0]],
                   'queries': [r.__dict__ for r in output[1]]}
        return cls(cases_bytes, output[0], output[1], sha(encode(content)))

    @property
    def cases_sha256(self):
        return sha(self.cases_bytes)


def _capture(path, size, digest):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == size, 'exact ordinary public file required')
        raw = stream.read(size + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(identity(before) == identity(after) and len(raw) == size and sha(raw) == digest,
            'public bytes changed or disagree with original producer pin')
    return raw


def _arrays(raw, keys, np):
    """Bound NPY allocation before loading the already authenticated bytes."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(len(infos) == len(keys) and {x.filename for x in infos} == {k + '.npy' for k in keys}
                and not any(x.flag_bits & 1 for x in infos)
                and sum(x.file_size for x in infos) <= 32 * 1024**2, 'bounded exact public NPZ members')
        for info in infos:
            with archive.open(info) as member:
                version = np.lib.format.read_magic(member)
                require(version in ((1, 0), (2, 0)), 'supported NPY header required')
                reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, fortran, dtype = reader(member, max_header_size=16384)
                require(not dtype.hasobject and dtype.fields is None and dtype.kind in 'iuf'
                        and 1 <= len(shape) <= 4 and all(type(n) is int and 1 <= n <= 272 for n in shape)
                        and not fortran and math.prod(shape) * dtype.itemsize <= 32 * 1024**2
                        and member.tell() + math.prod(shape) * dtype.itemsize == info.file_size,
                        'bounded plain numeric array required')
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=16384) as source:
        return {k: source[k].tolist() for k in keys}


def load_public(public_root, np):
    """Read only three exact historical public files; no private/root discovery."""
    public_root = Path(public_root)
    raw = {name: _capture(public_root / name, *pin) for name, pin in PINS.items()}
    train = _arrays(raw['training.npz'], {'spike_counts', 'condition', 'velocity_m_s'}, np)
    query = _arrays(raw['queries.npz'], {'spike_counts', 'condition'}, np)
    return Packet.from_arrays(train, query, raw['cases.json'])


def render_svg(trial, *, unit_start=0, unit_stop=65, bin_start=0, bin_stop=35):
    """All cells have literal count text; no contrast rescaling or lossy bitmap."""
    for a, b, n in ((unit_start, unit_stop, 65), (bin_start, bin_stop, 35)):
        require(type(a) is int and type(b) is int and 0 <= a < b <= n, 'typed half-open viewport bounds')
    require(trial.condition in CONDITIONS, 'known condition')
    max_digits = max(len(str(trial.counts[b][u])) for b in range(bin_start, bin_stop)
                     for u in range(unit_start, unit_stop))
    # Keep long integer counts readable instead of clipping or silently saturating.
    cell_width = max(46, max_digits * 9 + 8)
    width = max(1300, 100 + (bin_stop - bin_start) * cell_width)
    height = 280 + (unit_stop - unit_start) * 22 + (710 if trial.training_velocity is not None else 0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g font-family="monospace" font-size="13" fill="#111">']
    def text(x, y, value, extra=''):
        parts.append(f'<text x="{x}" y="{y}" {extra}>{html.escape(str(value))}</text>')
    label = 'active' if trial.condition == 'active' else 'perturbation (source: passive)'
    text(20, 24, f'{trial.trial_id} | {label} | NEURAL-021')
    text(20, 46, 'Each cell = exact spike count in one 20 ms half-open interval; units U01..U65 preserve source column order.')
    text(20, 68, 'Columns show interval start in ms from released onset. Bin k = [-220+20k, -200+20k), k=0..34.')
    text(20, 90, 'Response j=0..29: velocity x/y in m/s over [-100+20j, -80+20j); no additional unit conversion.')
    text(20, 112, 'History for response j consists of count columns j..j+5. Full batch context is available; retrospective task.')
    text(20, 134, 'Source onset uses future acceleration. Extended perturbation trajectory may include voluntary correction.')
    text(20, 156, f'View: unit indices [{unit_start},{unit_stop}), count-bin indices [{bin_start},{bin_stop}).')
    for b in range(bin_start, bin_stop):
        x = 92 + (b - bin_start) * cell_width
        text(x, 184, f'k{b:02d}')
        text(x, 204, f'{-220 + 20*b:+d}')
    for u in range(unit_start, unit_stop):
        y = 230 + (u - unit_start) * 22
        text(20, y, f'U{u+1:02d}')
        for b in range(bin_start, bin_stop):
            x = 92 + (b - bin_start) * cell_width
            text(x, y, trial.counts[b][u], f'data-unit="{u}" data-bin="{b}"')
    if trial.training_velocity is not None:
        y = 260 + (unit_stop - unit_start) * 22
        text(20, y, 'TRAINING LABELS ONLY: bin j | target interval ms | x m/s | y m/s')
        for j, pair in enumerate(trial.training_velocity):
            text(20, y + (j + 1) * 22,
                 f'{j:02d} | [{-100+20*j:+d},{-80+20*j:+d}) | {pair[0]!r} | {pair[1]!r}')
    parts.append('</g></svg>')
    return ''.join(parts)


class Session:
    """Restricted visual API + irreversible full-trajectory response collection.

    Keep this object in a trusted service. Giving a Python object or filesystem to
    a participant provides computational access and is not a no-tools condition.
    """
    def __init__(self, packet, mode):
        require(mode in MODES, 'identify direct_observation or typed_viewer arm')
        self._packet, self.mode = packet, mode
        self._queries = {r.trial_id: r for r in packet.queries}
        self._answers, self._opened, self._events = {}, set(), []
        self._view_count = 0
        self._final = False

    def _event(self, operation, payload):
        event = {'sequence': len(self._events), 'operation': operation, **payload,
                 'previous_sha256': self._events[-1]['sha256'] if self._events else '0'*64}
        event['sha256'] = sha(encode(event))
        self._events.append(event)

    def _live(self):
        require(not self._final, 'session is sealed')

    def _view_ready(self):
        self._live()
        require(self._view_count < MAX_VIEWS, '2048-view cumulative budget exhausted')

    def calibration(self, index):
        self._view_ready()
        require(type(index) is int and 0 <= index < 272, 'training index in [0,272)')
        rendered = render_svg(self._packet.training[index])
        self._view_count += 1
        self._event('training_view', {'training_index': index, 'svg_sha256': sha(rendered.encode())})
        return rendered

    def view(self, trial_id, **viewport):
        self._view_ready()
        require(type(trial_id) is str and trial_id in self._queries and trial_id not in self._answers,
                'unanswered query identity required')
        allowed = {'unit_start', 'unit_stop', 'bin_start', 'bin_stop'}
        require(set(viewport) <= allowed, 'only typed unit/time viewport actions admitted')
        require(self.mode == 'typed_viewer' or not viewport, 'direct observation admits only the fixed complete view')
        # The first view is always complete, preventing an unnoticed partial-case delivery.
        require(trial_id in self._opened or not viewport, 'open the complete query before requesting a crop')
        rendered = render_svg(self._queries[trial_id], **viewport)
        self._view_count += 1
        self._opened.add(trial_id)
        self._event('query_view', {'trial_id': trial_id, 'viewport': viewport, 'svg_sha256': sha(rendered.encode())})
        return rendered

    def answer(self, trial_id, velocity_m_s):
        self._live()
        require(type(trial_id) is str and trial_id in self._opened and trial_id not in self._answers,
                'view once before one immutable answer')
        values = trajectory(velocity_m_s)
        self._answers[trial_id] = values
        self._event('answer', {'trial_id': trial_id, 'answer_sha256': sha(encode(values))})
        return {'accepted': True, 'completed': len(self._answers), 'required': 92}

    def finish(self):
        self._live()
        require(set(self._answers) == set(self._queries), 'all 92 complete trajectories required; no subset result')
        submission = {'schema': interface.SCHEMA, 'task_id': interface.TASK,
                      'cases_sha256': self._packet.cases_sha256,
                      'predictions': [{'trial_id': r.trial_id, 'velocity_m_s': [list(p) for p in self._answers[r.trial_id]]}
                                      for r in self._packet.queries]}
        interface.validate_submission(submission, interface.strict_json(self._packet.cases_bytes), self._packet.cases_sha256)
        raw = encode(submission)
        require(len(raw) <= interface.MAX_JSON, 'original submission byte cap')
        receipt = {'schema': 'neural021_visual_delivery_receipt_v1', 'mode': self.mode,
                   'cases_sha256': self._packet.cases_sha256,
                   'observation_sha256': self._packet.observation_sha256,
                   'submission_sha256': sha(raw), 'query_count': 92,
                   'events': self._events.copy(), 'runtime_qualified': False,
                   'note': 'Local hash lineage is not independent authentication or participant isolation.'}
        self._final = True
        return raw, encode(receipt)

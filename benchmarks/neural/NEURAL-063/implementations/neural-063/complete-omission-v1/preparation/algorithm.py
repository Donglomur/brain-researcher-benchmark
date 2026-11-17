"""Pure, full-support metadata/window algorithms; no native or network imports."""
from bisect import bisect_left
import hashlib
import math
from owner.io import ContractError, canonical
from owner.scoring import stable_mean

CONTEXT = ('cre_line', 'targeted_structure', 'imaging_depth', 'image_set',
           'passive', 'experience_level', 'session_number')
COUNTS = {'mice': 107, 'sessions': 703, 'experiments': 1936, 'published_roi_rows': 133066}
SPLITS = {'fit': 73, 'validation': 15, 'query': 19}


def number(x):
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ContractError('finite scalar required')
    return float(x)


def text_id(x):
    if type(x) not in (int, str) or not str(x) or (isinstance(x, str) and not x.isdigit()):
        raise ContractError('nonnegative decimal source identity required')
    if int(x) < 0:
        raise ContractError('negative source identity')
    return str(int(x))


def split_mice(cre_by_mouse):
    groups = {}
    for mouse, cre in cre_by_mouse.items():
        groups.setdefault(cre, []).append(mouse)
    result = {}
    for mice in groups.values():
        ranked = sorted(mice, key=lambda m: (hashlib.sha256(('allen-visual-behavior-v1:' + m).encode()).hexdigest(), m))
        nfit, nval = int(.70 * len(ranked)), int(.15 * len(ranked))
        for i, mouse in enumerate(ranked):
            result[mouse] = 'fit' if i < nfit else 'validation' if i < nfit + nval else 'query'
    return result


def combine(tables):
    """Every qualifying table, including empty tables; no artificial min length."""
    records = []
    groups = set()
    for table in tables:
        group = table['group']
        if not isinstance(group, str) or not group or group in groups:
            raise ContractError('duplicate/invalid presentation group')
        groups.add(group)
        columns = [table[k] for k in ('ids', 'starts', 'omitted', 'image_names')]
        if len({len(x) for x in columns}) != 1:
            raise ContractError('presentation column length mismatch')
        for ident, start, omitted, image in zip(*columns):
            if type(omitted) not in (bool, int, float) or omitted not in (0, 1):
                raise ContractError('ambiguous omitted coding')
            if not isinstance(image, str) or len(image.encode()) > 512:
                raise ContractError('invalid image name')
            records.append({'key': group + ':' + text_id(ident), 'start': number(start),
                            'omitted': bool(omitted), 'image': image})
    if not groups:
        raise ContractError('no qualifying native presentation table')
    records.sort(key=lambda x: x['start'])
    if len({r['key'] for r in records}) != len(records) or any(a['start'] >= b['start'] for a,b in zip(records, records[1:])):
        raise ContractError('duplicate/nonmonotonic presentation start or identity')
    return records


def schedule(records):
    selected, exclusions, last = [], [], None
    for k, event in enumerate(records):
        if not event['omitted']:
            continue
        t = event['start']; category = 'timing_excluded'; reason = None
        if k < 3 or k + 1 == len(records):
            reason = 'missing_neighbor_presentations'
        elif any(not .70 <= records[i+1]['start'] - records[i]['start'] <= .80 for i in range(k-3, k)):
            reason = 'irregular_preceding_cadence'
        elif records[k+1]['start'] < t + .6:
            reason = 'next_stimulus_enters_target_window'
        elif last is not None and (t < last + 3.0 or t - 2.4 < last + .6):
            reason, category = 'fixed_three_second_schedule_thinning', 'thinning_excluded'
        if reason:
            exclusions.append({'key': event['key'], 'category': category, 'reason': reason})
        else:
            selected.append(k); last = t
    return {'selected': selected, 'exclusions': exclusions,
            'original_omissions': sum(r['omitted'] for r in records),
            'timing_excluded': sum(r['category'] == 'timing_excluded' for r in exclusions),
            'thinning_excluded': sum(r['category'] == 'thinning_excluded' for r in exclusions),
            'scheduled': len(selected)}


def validate_clock(timestamps):
    if len(timestamps) < 2:
        raise ContractError('full clock needs at least two samples')
    prior = number(timestamps[0])
    for t in timestamps[1:]:
        current = number(t)
        if current <= prior:
            raise ContractError('invalid full native increasing clock')
        prior = current


class ClockUnsupported(ContractError):
    """Only per-window support failure; invalid full clocks are hard failures."""


def support(timestamps, onset):
    # Full-clock validation is S03's mandatory prerequisite; repeat to make this
    # independently callable pure entry point safe on invented controls.
    validate_clock(timestamps)
    return native_bins(timestamps, onset)


def native_bins(timestamps, onset):
    """Bin lookup after the mandatory whole-clock validation, once per plane."""
    edges = [onset + j / 5 for j in range(-12, 4)]
    if not all(math.isfinite(e) for e in edges):
        raise ContractError('nonfinite window edges')
    if timestamps[0] > edges[0] or timestamps[-1] < edges[-1]:
        raise ClockUnsupported('window_not_bracketed')
    indices = [bisect_left(timestamps, e) for e in edges]
    spans = []
    for left, right in zip(indices, indices[1:]):
        if right <= left:
            raise ClockUnsupported('empty_required_bin')
        a, b = max(0, left - 1), min(len(timestamps), right + 1)
        if b-a < 2 or any(timestamps[i+1] - timestamps[i] > .15 for i in range(a, b-1)):
            raise ClockUnsupported('native_gap_exceeds_150ms')
        spans.append([left, right])
    return spans


def intersections(histories, targets):
    """Actual half-open frame-index sweep, never nominal time comparison."""
    hh, tt = sorted(histories), sorted(targets)
    i = j = 0
    while i < len(hh) and j < len(tt):
        a,b = hh[i]; c,d = tt[j]
        if max(a,c) < min(b,d):
            raise ContractError('visible history intersects held target frames')
        if b <= d: i += 1
        else: j += 1


def population(read_rows, columns, spans):
    if not columns or len(set(columns)) != len(columns) or len(spans) != 15:
        raise ContractError('complete unique published ROI columns and 15 bins required')
    values = []
    for left, right in spans:
        rows = read_rows(left, right)
        if len(rows) != right-left or right <= left:
            raise ContractError('native response slice shape mismatch')
        means = []
        for col in columns:
            means.append(stable_mean([number(row[col]) for row in rows]))
        values.append(stable_mean(means))
    baseline = values[11]
    history, target = [v-baseline for v in values[:12]], [v-baseline for v in values[12:]]
    if any(not math.isfinite(x) for x in history + target):
        raise ContractError('nonrepresentable baseline-subtracted response')
    if history[11] != 0:
        raise ContractError('baseline last-bin invariant failed')
    return history, target


def view(row, information, labeled):
    if information not in ('T', 'N'):
        raise ContractError('exact information view required')
    keys = ('id','mouse','session','experiment','split','previous','context')
    out = {k: row[k] for k in keys}
    if set(out['context']) != set(CONTEXT) or len(out['previous']) != 3:
        raise ContractError('exact allowed predictor structure required')
    if information == 'N': out['history'] = row['history']
    if labeled: out['target'] = row['target']
    return out

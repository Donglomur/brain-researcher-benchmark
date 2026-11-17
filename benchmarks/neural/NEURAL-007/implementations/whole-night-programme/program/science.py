"""Mathematical contracts shared by private scoring and independent references.

Only pure functions execute on import. NumPy/SciPy are imported inside explicitly
called reference functions; construction never calls them on authentic inputs.
The Welch specification follows the separately pinned adapted sleep reference,
not the literal MNE tutorial's oracle-window two-person demonstration.
"""
import math
from decimal import Decimal, localcontext
import re
from .common import CLASSES, need

BANDS = ((.5, 4.5), (4.5, 8.5), (8.5, 11.5), (11.5, 15.5), (15.5, 30.))
STAGES = {'Sleep stage W': 0, 'Sleep stage 1': 1, 'Sleep stage 2': 2,
          'Sleep stage 3': 3, 'Sleep stage 4': 3, 'Sleep stage R': 4,
          'Sleep stage ?': -1, 'Movement time': -1}


def full_clock_labels(epochs, annotations):
    """Operator-only labels. Every epoch remains in the public query geometry.

    Annotation operands are exact onset/duration strings and known stage text.
    Multiple overlapping intervals of the same merged stage do not conflict;
    gaps, movement or mixed merged stages mask only the evaluator target.
    """
    need(type(epochs) is int and epochs > 0, 'Positive complete epoch count')
    intervals = []
    for row in annotations:
        need(type(row) is dict and set(row) == {'onset', 'duration', 'text'}, 'Exact annotation fields')
        need(row['text'] in STAGES and type(row['onset']) is str and type(row['duration']) is str, 'Known annotation taxonomy')
        need(all(len(row[k]) <= 64 and re.fullmatch(r'[+-]?\d+(?:\.\d+)?', row[k]) for k in ('onset', 'duration')), 'Bounded ordinary exact decimal interval text')
        a, duration = Decimal(row['onset']), Decimal(row['duration'])
        need(a.is_finite() and duration.is_finite() and duration > 0, 'Finite positive annotation interval')
        with localcontext() as context:
            context.prec = 256  # >128 significant digits across two bounded64-char operands.
            end = a + duration
        intervals.append((a, end, STAGES[row['text']]))
    stages, dispositions = [], []
    for e in range(epochs):
        left, right = Decimal(30 * e), Decimal(30 * (e + 1))
        hits = [(max(a, left), min(b, right), stage) for a, b, stage in intervals if a < right and b > left]
        edges = sorted({left, right, *(a for a, _, _ in hits), *(b for _, b, _ in hits)})
        seen, reason = set(), None
        for a, b in zip(edges, edges[1:]):
            if a == b:
                continue
            labels = {stage for x, y, stage in hits if x <= a and y >= b}
            if not labels:
                reason = 'annotation_gap'; break
            if -1 in labels:
                reason = 'unknown_or_movement'; break
            if len(labels) != 1:
                reason = 'conflicting_merged_stage'; break
            seen.update(labels)
        if reason is None and len(seen) != 1:
            reason = 'stage_boundary_inside_epoch'
        stages.append(next(iter(seen)) if reason is None else -1)
        dispositions.append('eligible' if reason is None else reason)
    return stages, dispositions


def shift_epochs(values):
    need(len(values) >= 2, 'At least two epochs for complete shift contract')
    k = max(1, len(values) // 3)
    return values[-k:] + values[:-k]


def contextual_rows(rows, radius=5):
    """Pure reference implementation for boundary/shift engineering controls."""
    need(rows and type(radius) is int and radius >= 0, 'Nonempty contextual sequence')
    width = len(rows[0]); need(width > 0 and all(len(r) == width for r in rows), 'Fixed feature width')
    need(all(type(v) in (int, float) and math.isfinite(v) for r in rows for v in r), 'Finite feature rows')
    result = []
    for i, row in enumerate(rows):
        span = rows[max(0, i - radius):min(len(rows), i + radius + 1)]
        means = [math.fsum(r[j] for r in span) / len(span) for j in range(width)]
        sd = [math.sqrt(math.fsum((r[j] - means[j]) ** 2 for r in span) / len(span)) for j in range(width)]
        result.append(list(row) + means + sd)
    return result


def probabilities(rows, epochs):
    need(type(rows) is list and len(rows) == epochs, 'All full-clock probability rows')
    for row in rows:
        need(type(row) is list and len(row) == 5, 'Five probability columns')
        need(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in row), 'Finite nonboolean probabilities')
        need(abs(math.fsum(row) - 1) <= 1e-6, 'Probability simplex, no repair')
    return rows


def confusion(rows, labels):
    probabilities(rows, len(labels)); result = [[0] * 5 for _ in range(5)]
    for row, stage in zip(rows, labels):
        need(type(stage) is int and stage in range(-1, 5), 'Exact stage/mask domain')
        if stage < 0:
            continue
        predicted = max(range(5), key=lambda i: (row[i], -i))
        result[stage][predicted] += 1
    return result


def combine_confusions(items):
    out = [[0] * 5 for _ in range(5)]
    for item in items:
        need(len(item) == 5 and all(len(r) == 5 for r in item), 'Five-by-five confusion')
        for a in range(5):
            for b in range(5):
                value = item[a][b]; need(type(value) is int and value >= 0, 'Nonnegative confusion count')
                out[a][b] += value
    return out


def metrics(matrix):
    m = combine_confusions([matrix]); f1, recall = [], []
    support = [sum(r) for r in m]
    for stage in range(5):
        tp = m[stage][stage]
        denom = support[stage] + sum(r[stage] for r in m)
        f1.append(2 * tp / denom if denom else 0.)
        recall.append(tp / support[stage] if support[stage] else None)
    return {'confusion': m, 'support': support, 'eligible_epochs': sum(support),
            'class_f1': f1, 'class_recall': recall, 'fixed_five_macro_f1': math.fsum(f1) / 5,
            'supported_balanced_accuracy': (math.fsum(x for x in recall if x is not None) /
                                           sum(x is not None for x in recall)) if any(support) else None}


def person_macro(person_confusions, required_people=78):
    need(type(person_confusions) is dict and len(person_confusions) == required_people, 'Complete biological-person panel')
    by_person = {p: metrics(m) for p, m in person_confusions.items()}
    need(all(x['eligible_epochs'] > 0 for x in by_person.values()), 'No person without an eligible endpoint; full panel incomplete')
    return {'primary': math.fsum(x['fixed_five_macro_f1'] for x in by_person.values()) / required_people,
            'people': by_person, 'independent_people': required_people,
            'metric': 'equal_person_fixed_five_class_macro_f1'}


def signal_features(epochs_volts):
    import numpy as np
    from scipy.signal import welch
    x = np.asarray(epochs_volts, dtype=np.float64)
    need(x.ndim == 2 and x.shape[1] == 3000 and len(x) > 0 and np.isfinite(x).all(), 'Complete finite channel epochs')
    f, psd = welch(x, fs=100., window='hann', nperseg=400, noverlap=200, nfft=400,
                   detrend='constant', return_onesided=True, scaling='density', axis=-1, average='mean')
    keep = (f >= .5) & (f <= 30)
    f, psd = f[keep], psd[..., keep]
    total = psd.sum(axis=-1, keepdims=True)
    rel = np.divide(psd, total, out=np.zeros_like(psd), where=total > 0)
    cols = [rel[..., (f >= lo) & (f < hi)].mean(axis=-1) for lo, hi in BANDS]
    cols.append(np.log(np.maximum(np.var(x, axis=-1), 1e-24)))
    result = np.stack(cols, axis=-1)
    need(np.isfinite(result).all(), 'Finite declared epoch features')
    return result


def contextual_array(base, radius=5):
    import numpy as np
    base = np.asarray(base, dtype=np.float64)
    need(base.ndim == 2 and len(base) and np.isfinite(base).all(), 'Finite base feature array')
    # Window width is fixed11. Explicit local centered sums avoid cumulative
    # squared-sum cancellation, and exactly truncate at each night boundary.
    out = np.empty((len(base), 3 * base.shape[1]), dtype=np.float64)
    for i in range(len(base)):
        window = base[max(0, i - radius):min(len(base), i + radius + 1)]
        out[i] = np.concatenate((base[i], window.mean(axis=0), window.std(axis=0, ddof=0)))
    return out


def training_sequence_statistics(night_labels):
    import numpy as np
    counts = np.zeros(5, dtype=np.float64)
    transitions = np.ones((5, 5), dtype=np.float64)
    for values in night_labels:
        y = np.asarray(values)
        need(y.ndim == 1 and np.isin(y, [-1, 0, 1, 2, 3, 4]).all(), 'Full clock training stages')
        counts += np.bincount(y[y >= 0], minlength=5)
        for a, b in zip(y[:-1], y[1:]):
            if a >= 0 and b >= 0:
                transitions[int(a), int(b)] += 1
    need(counts.sum() > 0, 'Training target support')
    return counts / counts.sum(), transitions / transitions.sum(axis=1, keepdims=True)


def sequence_posterior(posterior, prior, transition, power):
    import numpy as np
    p = np.asarray(posterior, dtype=np.float64)
    prior = np.asarray(prior, dtype=np.float64)
    transition = np.asarray(transition, dtype=np.float64)
    need(p.ndim == 2 and p.shape[1] == 5 and len(p) and np.isfinite(p).all() and (p >= 0).all(), 'Complete emission posterior')
    need(prior.shape == (5,) and transition.shape == (5, 5) and power in (0, .5, 1), 'Frozen sequence state/grid')
    emission = np.maximum(p / np.maximum(prior, 1e-12), 1e-12)
    t = transition ** power; t /= t.sum(axis=1, keepdims=True)
    forward = np.empty_like(emission)
    forward[0] = prior * emission[0]; forward[0] /= forward[0].sum()
    for i in range(1, len(p)):
        forward[i] = (forward[i - 1] @ t) * emission[i]
        forward[i] /= forward[i].sum()
    backward = np.ones_like(emission)
    for i in range(len(p) - 2, -1, -1):
        backward[i] = t @ (emission[i + 1] * backward[i + 1])
        backward[i] /= backward[i].sum()
    result = forward * backward; result /= result.sum(axis=1, keepdims=True)
    need(np.isfinite(result).all(), 'Finite sequence posterior')
    return result

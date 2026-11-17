"""Source-declared row=previous, column=next transition orientation."""
from bisect import bisect_right
from dataclasses import dataclass
from .core import Refusal

TRANSITIONS = {
    'random': ((.25, .25, .25, .25),) * 4,
    'midminus': ((.25, 0, .37, .38), (.38, .25, 0, .37),
                 (.37, .38, .25, 0), (0, .37, .38, .25)),
    'midplus': ((.25, 0, .15, .60), (.60, .25, 0, .15),
                (.15, .60, .25, 0), (0, .15, .60, .25)),
    'ordered': ((.25, 0, 0, .75), (.75, .25, 0, 0),
                (0, .75, .25, 0), (0, 0, .75, .25)),
}


def most_likely_labels(labels, condition):
    """Preserve the retained-sequence predecessor convention of author base.py.

    First retained trial keeps its actual label, as in that source. This differs
    from claiming that a predecessor was observed before the selected sequence.
    """
    import numpy as np
    if condition == 'random':
        return labels.copy()
    matrix = TRANSITIONS[condition]
    result = labels.copy()
    for i in range(1, len(labels)):
        previous = int(labels[i - 1])
        result[i] = 1 + max(range(4), key=lambda j: matrix[previous - 1][j])
    return np.asarray(result, dtype=int)


@dataclass(frozen=True)
class LagCell:
    target_event: int
    test_offset_samples: int
    context_event: int
    event_lag: int
    context_offset_samples: int
    context_code: int


def observed_lags(event_samples, event_codes, target_indices, offsets):
    """Map from actual complete stimulus chain, never from an array dimension.

    Non-stimulus trigger markers must already be removed with an explicit input
    disposition. Omission events remain in this chain and are identified here.
    """
    if len(event_samples) != len(event_codes) or not event_samples:
        raise Refusal('complete stimulus chain required')
    if any(a >= b for a, b in zip(event_samples, event_samples[1:])):
        raise Refusal('stimulus samples must be strictly increasing')
    if not set(event_codes).issubset({1, 2, 3, 4, 10, 20, 30, 40}):
        raise Refusal('unknown stimulus code in lag chain')
    result = []
    for target in target_indices:
        if not 0 <= target < len(event_samples) or event_codes[target] not in (1, 2, 3, 4):
            raise Refusal('theoretical target must be an actual sound event')
        row = []
        for offset in offsets:
            absolute = event_samples[target] + offset
            context = bisect_right(event_samples, absolute) - 1
            if not 0 <= context < len(event_samples) - 1:
                raise Refusal('actual bracketing stimulus onset unavailable')
            row.append(LagCell(target, offset, context, target - context,
                               absolute - event_samples[context], event_codes[context]))
        result.append(tuple(row))
    return tuple(result)


def theoretical_accuracy(confusion, confusion_times, lags, condition):
    """Transition×OOF confusion null, with full explicit lag/support provenance.

    The paper's model assumes uniform marginal class probability (1/4) and the
    fixed time-homogeneous first-order transition chain. All selected matrices
    are doubly stochastic. For a future context n+d, Bayes' rule gives the
    reverse conditional as (T**d).T under precisely that uniform-marginal model;
    this is NOT a matrix inverse, empirical stationarity proof, or silently
    estimated transition from held labels. Context-before-target uses T**d.

    An omission-context response is not manufactured from a sound confusion
    matrix. That unresolved context refuses this complete endpoint, not a subset
    of participants or time cells. No fixed 135/141 relabeling or interpolation.
    """
    import numpy as np
    matrix = np.asarray(TRANSITIONS[condition], dtype=float)
    samples = np.rint(confusion_times * 100).astype(int)
    if not np.allclose(samples / 100, confusion_times, atol=1e-12, rtol=0):
        raise Refusal('confusion times do not map exactly to observed 100 Hz samples')
    indices = {int(sample): i for i, sample in enumerate(samples)}
    if len(indices) != len(samples) or not lags:
        raise Refusal('ambiguous/empty theoretical support')
    rows = []
    for trial in lags:
        output = []
        for cell in trial:
            if cell.context_code not in (1, 2, 3, 4):
                raise Refusal('sound-confusion model has no observed omission-context response')
            if cell.context_offset_samples not in indices:
                raise Refusal('actual context offset outside OOF confusion support')
            cm = confusion[:, indices[cell.context_offset_samples], :, :]
            if cell.event_lag == 0:
                value = np.trace(cm, axis1=-2, axis2=-1) / 4
            else:
                transition = np.linalg.matrix_power(matrix, abs(cell.event_lag))
                if cell.event_lag < 0:
                    transition = transition.T
                value = (cm * transition).sum(axis=(-2, -1)) / 4
            output.append(value)
        rows.append(np.stack(output, axis=1))
    return np.stack(rows).mean(axis=0)


def lag_coverage(event_samples, event_codes, target_indices, offsets, confusion_offsets):
    """Deterministic full planned-cell coverage. No missing cell is pruned/imputed.

    All reason records remain protected analysis output, never prediction inputs.
    Counts include every planned target/offset, including structurally unsupported
    omission contexts, so a file-complete input cannot masquerade as full theory.
    """
    if len(event_samples) != len(event_codes) or not event_samples:
        raise Refusal('complete stimulus chain required')
    if any(a >= b for a, b in zip(event_samples, event_samples[1:])):
        raise Refusal('stimulus samples must be strictly increasing')
    if not set(event_codes).issubset({1, 2, 3, 4, 10, 20, 30, 40}):
        raise Refusal('unknown event code')
    allowed = set(confusion_offsets)
    rows, reasons, counts = [], [], {}
    for target in target_indices:
        if not 0 <= target < len(event_samples) or event_codes[target] not in (1,2,3,4):
            raise Refusal('theoretical target must be an actual sound')
        row = []
        for offset in offsets:
            absolute = event_samples[target] + offset
            q = bisect_right(event_samples, absolute) - 1
            reason = None
            cell = None
            if not 0 <= q < len(event_samples)-1:
                reason = 'no_actual_bracketing_onsets'
            else:
                cell = LagCell(target, offset, q, target-q, absolute-event_samples[q], event_codes[q])
                if event_codes[q] not in (1,2,3,4):
                    reason = 'omission_context_has_no_sound_confusion_model'
                elif cell.context_offset_samples not in allowed:
                    reason = 'observed_offset_outside_confusion_support'
            row.append(cell)
            category = reason or 'supported'
            counts[category] = counts.get(category, 0) + 1
            if reason:
                reasons.append({'target_event': target, 'test_offset_samples': offset,
                                'context_event': q if cell is not None else None, 'reason': reason})
        rows.append(tuple(row))
    return {'complete': not reasons, 'planned_cells': len(target_indices)*len(offsets),
            'reason_counts': counts, 'reasons': tuple(reasons), 'cells': tuple(rows)}

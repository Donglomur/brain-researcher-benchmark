"""Public event and own-submission arithmetic; no source I/O or hidden targets."""
from bisect import bisect_right
import numpy as np


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def ledger(source_rows, method):
    roles = method['events']['description_to_role']
    annotations = [dict(r, event_role=roles.get(r['description'], 'unmapped'),
                        paired_stimulus_annotation_index=None, disposition='unmapped')
                   for r in source_rows]
    mapped = [r for r in annotations if r['event_role'] != 'unmapped']
    require(len({r['event_sample'] for r in mapped}) == len(mapped), 'mapped sample tie')
    stimuli = sorted((r for r in mapped if r['event_role'].startswith('stimulus_')),
                     key=lambda r: r['event_sample'])
    responses = sorted((r for r in mapped if r['event_role'].startswith('response_')),
                       key=lambda r: r['event_sample'])
    samples = [r['event_sample'] for r in responses]
    for r in responses:
        r['disposition'] = ('orphan_response' if not stimuli or
                            r['event_sample'] < stimuli[0]['event_sample'] else 'extra_response')
    first = method['input']['first_sample']
    end = first + method['input']['n_samples']
    lo, hi = method['processing']['sample_offset_inclusive']
    trials = []
    for i, s in enumerate(stimuli):
        stop = stimuli[i + 1]['event_sample'] if i + 1 < len(stimuli) else end
        j = bisect_right(samples, s['event_sample'])
        r = responses[j] if j < len(responses) and samples[j] < stop else None
        s['disposition'] = 'unanswered_stimulus'
        t = dict(stimulus_annotation_index=s['annotation_index'], stimulus_sample=s['event_sample'],
                 response_annotation_index=None, response_sample=None,
                 target_hand=s['event_role'].rsplit('_', 1)[1], response_hand=None,
                 compatibility='incompatible' if '_incompatible_' in s['event_role'] else 'compatible',
                 is_error=None, rt_s=None, pair_status='unanswered', epoch_status='unpaired',
                 baseline_mean_uv=None, window_mean_prebaseline_uv=None, window_mean_uv=None)
        if r is not None:
            hand = r['event_role'].rsplit('_', 1)[1]
            t.update(response_annotation_index=r['annotation_index'], response_sample=r['event_sample'],
                     response_hand=hand, is_error=int(hand != t['target_hand']), pair_status='paired',
                     rt_s=(r['event_sample'] - s['event_sample']) / method['input']['sfreq_hz'],
                     epoch_status='retained' if first <= r['event_sample'] + lo and
                     r['event_sample'] + hi < end else 'outside_record')
            s['disposition'], r['disposition'] = 'paired_stimulus', 'paired_response'
            s['paired_stimulus_annotation_index'] = s['annotation_index']
            r['paired_stimulus_annotation_index'] = s['annotation_index']
        trials.append(t)
    return annotations, trials


def derive(x, trial_ids, offsets, annotations, source_trials, method):
    x = np.asarray(x, dtype=np.float64)
    offsets = np.asarray(offsets)
    require(x.shape == (len(trial_ids), len(offsets)) and np.isfinite(x).all(), 'epoch shape/finite')
    retained = {t['stimulus_annotation_index']: t for t in source_trials if t['epoch_status'] == 'retained'}
    require(len(set(map(int, trial_ids))) == len(trial_ids) and set(map(int, trial_ids)) == set(retained),
            'complete retained trial identity')
    p = method['processing']
    b0, b1 = p['baseline_offsets_inclusive']; w0, w1 = p['measurement_offsets_inclusive']
    bmask = (offsets >= b0) & (offsets <= b1)
    wmask = (offsets >= w0) & (offsets <= w1)
    require(int(bmask.sum()) == p['baseline_samples'] and int(wmask.sum()) == p['measurement_samples'],
            'baseline/measurement support')
    baseline = x[:, bmask].mean(axis=1)
    y = x - baseline[:, None]
    pre = x[:, wmask].mean(axis=1)
    window = y[:, wmask].mean(axis=1)
    require(all(np.isfinite(v).all() for v in (baseline, y, pre, window)), 'derived finite')
    row_index = {int(key): i for i, key in enumerate(trial_ids)}
    trials = [dict(t) for t in source_trials]
    for t in trials:
        if t['epoch_status'] == 'retained':
            i = row_index[t['stimulus_annotation_index']]
            t.update(baseline_mean_uv=float(baseline[i]), window_mean_prebaseline_uv=float(pre[i]),
                     window_mean_uv=float(window[i]))
    labels = np.array([retained[int(key)]['is_error'] for key in trial_ids], dtype=int)
    curves, means, counts = {}, {}, {}
    for name, label in [('error', 1), ('correct', 0)]:
        mask = labels == label
        counts[name] = int(mask.sum())
        curves[name] = y[mask].mean(axis=0) if mask.any() else None
        means[name] = float(window[mask].mean()) if mask.any() else None
    both = all(counts.values())
    waves = []
    for j, offset in enumerate(offsets):
        a, b = curves['error'], curves['correct']
        waves.append(dict(sample_offset=int(offset), time_s=float(offset / method['input']['sfreq_hz']),
                          error_uv=None if a is None else float(a[j]),
                          correct_uv=None if b is None else float(b[j]),
                          difference_uv=None if not both else float(a[j] - b[j])))
    result = dict(status='ok' if both else 'insufficient_condition', subject=method['subject'],
                  electrode=method['estimand']['channel'], units=method['estimand']['units'],
                  contrast=method['estimand']['contrast'], n_annotations=len(annotations),
                  n_stimuli=len(trials), n_paired_trials=sum(t['pair_status'] == 'paired' for t in trials),
                  n_error_trials=counts['error'], n_correct_trials=counts['correct'],
                  n_retained_trials=len(trial_ids), measurement_offsets_inclusive=[w0, w1],
                  measurement_samples=int(wmask.sum()), error_mean_uv=means['error'],
                  correct_mean_uv=means['correct'],
                  ern_amplitude_uv=None if not both else means['error'] - means['correct'])
    return dict(trials=trials, waveforms=waves, results=result)

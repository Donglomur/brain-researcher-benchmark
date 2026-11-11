"""Exposure- and preprocessing-support-aware features; no whole-session scaling."""
from .contracts import require

def frame_window(plane, left, right):
    import numpy as np
    require(left < right, 'empty window')
    # Full input support lies inside the window. This also rejects acausal
    # smoothing/deconvolution that consumes any sample outside the allowed view.
    mask = ((plane['exposure_start'] >= left) & (plane['exposure_end'] < right) &
            (plane['support_start'] >= left) & (plane['support_end'] < right) &
            (plane['artifact'] == 0))
    require(np.any(mask), 'no uncontaminated fully supported exposure')
    return mask

def window_mean(plane, left, right, minimum_frames):
    import numpy as np
    mask = frame_window(plane, left, right)
    require(int(mask.sum()) >= minimum_frames, 'insufficient exposure count')
    duration = plane['exposure_end'][mask] - plane['exposure_start'][mask]
    require(np.all(duration > 0), 'zero-duration frames require explicit exposure producer')
    return np.average(plane['values'][mask], axis=0, weights=duration)

def neural_trial(recording, trial, window, minimum_frames, representation, atlas_bins):
    import numpy as np
    left, right = (trial['move_onset'] + x for x in window)
    require(window[1] < 0 and left >= trial['start'] and right <= trial['stop'], 'premovement boundary')
    require(trial['history_end']<=left,'history baseline consumes current/future interval')
    selected = [p for p in recording['planes'] if p['epoch'] == trial['epoch']]
    require(selected, 'trial epoch has no imaging plane')
    pairs = []
    for plane in selected:
        value = window_mean(plane, left, right, minimum_frames)
        for roi, v in zip(plane['roi'], value):
            if roi['qc_keep'] == 1:  # Geometry/segmentation QC only, not task tuning.
                pairs.append(((plane['id'], roi['roi_id']), roi['atlas_bin'], float(v)))
    require(pairs, 'no geometry-QC cells')
    if representation == 'session_rois':
        pairs.sort(key=lambda x: x[0])
        return np.asarray([x[2] for x in pairs]), [list(x[0]) for x in pairs]
    require(representation == 'anatomical_bins' and atlas_bins, 'explicit new-mouse representation required')
    # Atlas bins are established from anatomy outside outcome data. No tuning
    # alignment or test-mouse normalization is fitted here.
    require(set(x[1] for x in pairs) <= set(atlas_bins), 'unmapped anatomical cell')
    values = []
    for key in atlas_bins:
        members = [x[2] for x in pairs if x[1] == key]
        require(members, 'missing anatomical bin; do not zero-impute absent tissue')
        values.append(float(np.mean(members)))
    return np.asarray(values), list(atlas_bins)

def prediction_rows(recording, protocol, representation):
    rows, exclusions = [], []
    from .contracts import Refusal
    for t in recording['trials']:
        try:
            value, features = neural_trial(recording, t, protocol['window'],
                protocol['minimum_frames'], representation, protocol['atlas_bins'])
        except Refusal as error:
            exclusions.append({'trial_id': t['trial_id'], 'reason': str(error)})
            continue
        rows.append({'mouse': recording['mouse'], 'session': recording['session'],
                     'trial_id': t['trial_id'], 'block': t['block_id'],
                     'layout': recording['grid']['id'], 'classes': recording['grid']['classes'],
                     'features': features, 'x': value, 'y': t['direction'],
                     'time': t['start'], 'previous_direction': t['previous_direction'],
                     'previous_reward': t['previous_reward'], 'history_speed': t['history_speed']})
    require(len(rows) + len(exclusions) == len(recording['trials']), 'trial disposition inverse')
    return rows, exclusions

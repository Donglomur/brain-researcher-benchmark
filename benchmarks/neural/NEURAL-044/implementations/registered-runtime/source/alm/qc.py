"""Whole population and within-recording identity checks, with explicit disposition."""
from .contracts import require, unique, finite

def validate_recording(r):
    trials = r['trials']
    require(trials, 'no behavior trials')
    unique([t['trial_id'] for t in trials], 'trial')
    required = {'trial_id', 'block_id', 'epoch', 'start', 'stop', 'go', 'move_onset',
                'contact', 'direction', 'previous_direction', 'previous_reward',
                'history_speed', 'history_end', 'regular_reward', 'onset_method'}
    for t in trials:
        require(required <= set(t), 'missing trial columns')
        require(t['onset_method'] == 'tracking_tongue_onset', 'contact/cue is not movement onset')
        require(t['start'] <= t['go'] <= t['move_onset'] <= t['contact'] <= t['stop'], 'event chronology')
        require(t['direction'] in r['grid']['classes'], 'direction outside fixed layout')
        require(t['previous_direction'] in r['grid']['classes'] + ['NONE'], 'history class')
    require(r['grid']['shape'] in ([4, 4], [5, 5]), 'unrecognized layout; separate review needed')
    require(len(r['grid']['classes']) == r['grid']['shape'][0] * r['grid']['shape'][1], 'layout classes')
    unique(r['grid']['classes'], 'direction class')
    last = None
    for t in sorted(trials, key=lambda x: x['start']):
        require(last is None or t['start'] >= last, 'overlapping trials')
        last = t['stop']
    ids = []
    for p in r['planes']:
        require(p['epoch'] in r['epoch_bounds'], 'unbound plane epoch')
        for roi in p['roi']:
            require({'roi_id', 'x', 'y', 'z', 'qc_keep', 'atlas_bin'} <= set(roi), 'ROI metadata')
            ids.append((p['epoch'], p['id'], roi['roi_id']))
            for key in ('x', 'y', 'z'):
                finite(roi[key])
    unique(ids, 'epoch/plane/ROI')
    unique([s['stim_id'] for s in r['stimuli']], 'stimulus event')
    for s in r['stimuli']:
        require({'stim_id', 'epoch', 'on', 'off', 'target_id', 'power_mw',
                 'condition', 'block_id', 'movement', 'assignment_probability'} <= set(s), 'stimulation fields')
        require(s['on'] < s['off'] and s['power_mw'] >= 0, 'stimulus duration/power')
        require(s['condition'] in ('neuron_target', 'nonresponding_site', 'true_sham'), 'control class')
        require(s['epoch'] in r['epoch_bounds'], 'stimulus epoch')
    links = r['cell_links']
    unique([x['cell_id'] for x in links], 'cross-epoch cell identity')
    unique([tuple(x['behavior_roi']) for x in links], 'behavior cell occurrence')
    unique([tuple(x['rest_roi']) for x in links], 'rest cell occurrence')
    for link in links:
        require(link['identity_evidence'], 'unverified cross-epoch cell identity')
        require(tuple(link['behavior_roi']) in ids, 'missing tuning cell')
        require(tuple(link['rest_roi']) in ids, 'missing rest cell')
        require(tuple(link['baseline_roi']) in ids, 'missing independent baseline cell')
        require(not any(s['epoch']==link['baseline_roi'][0] for s in r['stimuli']), 'baseline contains stimulation')
    targets = r['targets']
    unique([x['target_id'] for x in targets], 'target site')
    require({s['target_id'] for s in r['stimuli']} <= {x['target_id'] for x in targets}, 'unmapped stimulus target')
    for target in targets:
        require(target['classification_evidence'], 'site classification provenance')
        require(target['cell_id'] is None or target['cell_id'] in {x['cell_id'] for x in links}, 'target cell identity')
        for key in ('x','y','z'):
            finite(target[key])
    return {'mouse': r['mouse'], 'session': r['session'], 'trials': len(trials),
            'stimuli': len(r['stimuli']), 'roi_occurrences': len(ids), 'status': 'source_contract_pass'}

def inventory_dispositions(manifest, loaded):
    require(len(loaded) == sum(x['disposition'] == 'include' for x in manifest['recordings']),
            'silent recording loss')
    return [{'asset_id': x['asset_id'], 'mouse': x['mouse'], 'session': x['session'],
             'disposition': x['disposition'], 'reason': x['reason']} for x in manifest['recordings']]

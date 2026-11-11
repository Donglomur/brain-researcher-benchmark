"""Behavior-only tuning, disjoint from stimulation responses and test blocks."""
from .contracts import require
from .features import window_mean

def tuning_maps(recording, allowed_blocks, held_blocks, window, minimum_frames):
    import numpy as np
    require(set(allowed_blocks).isdisjoint(held_blocks), 'tuning/test block overlap')
    selected = [t for t in recording['trials'] if t['block_id'] in allowed_blocks and t['regular_reward']==1]
    require(selected and set(t['block_id'] for t in selected)==set(allowed_blocks), 'missing tuning blocks')
    classes = recording['grid']['classes']
    aggregate = {}
    for t in selected:
        for p in recording['planes']:
            if p['epoch'] != t['epoch']:
                continue
            left, right = (t['contact']+x for x in window)
            require(left >= t['start'] and right <= t['stop'], 'tuning window crosses trial')
            values = window_mean(p,left,right,minimum_frames)
            for roi,v in zip(p['roi'],values):
                key = (p['epoch'],p['id'],roi['roi_id'])
                aggregate.setdefault(key,{c:[] for c in classes})[t['direction']].append(float(v))
    result, dispositions = {}, []
    for link in recording['cell_links']:
        source = aggregate.get(tuple(link['behavior_roi']))
        if source is None or not all(source[c] for c in classes):
            dispositions.append({'cell_id':link['cell_id'],'status':'missing_direction_tuning'})
            continue
        vector = np.asarray([np.mean(source[c]) for c in classes])
        centered = vector-vector.mean()
        norm = np.linalg.norm(centered)
        if norm == 0:
            dispositions.append({'cell_id':link['cell_id'],'status':'constant_tuning'})
            continue
        result[link['cell_id']] = centered/norm
        dispositions.append({'cell_id':link['cell_id'],'status':'estimable'})
    return result, dispositions

"""Exact six-arm tagged feature ABI; no fabricated sensor geometry."""
from core import CONDITIONS, R2_ARMS, COUNTS, need
TIMING_FEATURES = ('duration_seconds', 'previous_onset_interval_seconds', 'first_key_indicator')
WINDOWS = {'NEURAL_PRE': [-0.7, -0.2], 'NEURAL': [-0.2, 0.3], 'NEURAL_POST': [0.3, 0.8], 'SHUFFLE': [-0.2, 0.3], 'EOG': [-0.2, 0.3]}

def feature_spec(arm, modality, names, types):
    need(arm in CONDITIONS and modality in COUNTS, 'Selected six-arm modality')
    if arm == 'TIMING':
        need(names == [] and types == [], 'Timing has no sensor aliases')
        return {'kind': 'timing3', 'dimensions': 3, 'features': list(TIMING_FEATURES), 'units': ['seconds', 'seconds', 'indicator'], 'samples_per_key': 1, 'geometry': None}
    need(type(names) is list and names and (len(names) == len(set(names))) and all((type(n) is str and n for n in names)), 'Exact unique actual channel names/order')
    need(type(types) is list and len(types) == len(names) and all((type(n) is str and n for n in types)), 'Actual channel type/order')
    if arm in R2_ARMS:
        need(len(names) == COUNTS[modality]['channels'], 'All actual neural channels')
    else:
        need(1 <= len(names) <= 8, 'Complete actual ocular channel schema')
    return {'kind': 'channel_window', 'dimensions': len(names) * 25, 'channel_names': list(names), 'channel_types': list(types), 'samples_per_key': 25, 'window_seconds': WINDOWS[arm], 'geometry': 'source_authenticated_neural' if arm in R2_ARMS else None}

def validate(spec, arm, modality):
    names = [] if arm == 'TIMING' else spec.get('channel_names')
    types = [] if arm == 'TIMING' else spec.get('channel_types')
    need(spec == feature_spec(arm, modality, names, types), 'Complete exact typed feature schema')
    return spec['dimensions']

"""NEURAL047: deterministic fixed-time windows, adapted from reviewed048.

The WB-field mapper requires an external verified physical clock/animal binding.
No nominal frame rate or unidentified neuron is invented. Odor is not a047 predictor.
"""
import bisect
import hashlib
import math
from .delivery_io import need, exact

ARMS = ('N', 'B', 'NB')
HISTORY_SECONDS = 4.8
LANDMARK_SECONDS = 2.4
MAX_FRAMES = 1000000
MAX_EVENTS = 50000


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def validate_record(record):
    exact(record, ['recording_id', 'split_group', 'split_unit', 'source_pin', 'evidence',
                   'time_seconds', 'native_frame0', 'velocity', 'dv', 'saav',
                   'reversal_state', 'events'])
    need(all(type(record[k]) is str and 0 < len(record[k]) <= 128 for k in
             ('recording_id', 'split_group')), 'Exact bounded source/group identity')
    need(record['split_unit'] == 'animal', 'Explicit independently supported animal unit')
    evidence = record['evidence']
    exact(evidence, ['time_mapping', 'dv_orientation', 'saav_identity',
                     'group_identity', 'processed_signal_support'])
    for key, value in evidence.items():
        need(type(value) is str and 0 < len(value) <= 4000, 'Nonempty source evidence; no guessed defaults')
    need(evidence['dv_orientation'].startswith('dorsal_positive:') and
         evidence['saav_identity'].startswith('SAAV:'),
         'Verified orientation and exact neuron required')
    n = len(record['time_seconds'])
    need(3 <= n <= MAX_FRAMES, 'Bounded full native recording')
    for key in ('time_seconds', 'native_frame0', 'velocity', 'dv', 'saav', 'reversal_state'):
        need(type(record[key]) is list and len(record[key]) == n, 'Every aligned native channel required')
    times, frames = record['time_seconds'], record['native_frame0']
    need(all(finite(t) for t in times) and all(a < b for a, b in zip(times, times[1:])), 'Strict physical clock')
    need(all(type(i) is int and i >= 0 for i in frames) and all(a < b for a, b in zip(frames, frames[1:])),
         'Explicit increasing original frame mapping')
    for key in ('velocity', 'dv', 'saav'):
        need(all(v is None or finite(v) for v in record[key]), 'Missingness must be explicit, not nonfinite JSON')
    need(all(type(v) is int and v in (0, 1) for v in record['reversal_state']), 'Native reversal observation')
    need(type(record['events']) is list and len(record['events']) <= MAX_EVENTS, 'Bounded complete reversal roster')
    seen = set(); previous_end = -1
    for event in record['events']:
        exact(event, ['event_id', 'onset_index0', 'end_index0'])
        need(type(event['event_id']) is str and 0 < len(event['event_id']) <= 128 and
             event['event_id'] not in seen, 'Unique source event ID')
        seen.add(event['event_id'])
        start, end = event['onset_index0'], event['end_index0']
        need(type(start) is int and type(end) is int and previous_end < start <= end < n,
             'Ordered disjoint inclusive native reversal episodes')
        previous_end = end
        need(all(x == 1 for x in record['reversal_state'][start:end + 1]),
             'Event endpoints agree with source reversal state')
    # The normalized contract declares complete maximal episodes, not a list of
    # retrospectively selected favorable events. Raw-source mapping is separate.
    state = record['reversal_state']
    starts = [i for i, value in enumerate(state) if value and (i == 0 or not state[i - 1])]
    ends = [i for i, value in enumerate(state) if value and (i == n - 1 or not state[i + 1])]
    need([(e['onset_index0'], e['end_index0']) for e in record['events']] == list(zip(starts, ends)),
         'Complete maximal observed reversal roster; no omitted or truncated episode')


def consecutive(frames):
    return all(b == a + 1 for a, b in zip(frames, frames[1:]))


def extract(record):
    """Return all eligible landmark cases and reason-coded source exclusions."""
    validate_record(record)
    times = record['time_seconds']; frames = record['native_frame0']; cases = []; excluded = []
    for event in record['events']:
        onset, end = event['onset_index0'], event['end_index0']
        landmark = bisect.bisect_left(times, times[onset] + LANDMARK_SECONDS)
        reason = None
        if landmark >= len(times):
            reason = 'landmark_outside_recording'
        elif landmark > end or record['reversal_state'][landmark] != 1:
            reason = 'not_observed_reversing_at_landmark'
        elif times[0] > times[landmark] - HISTORY_SECONDS:
            reason = 'incomplete_pre_landmark_recording'
        else:
            lo = bisect.bisect_left(times, times[landmark] - HISTORY_SECONDS)
            indices = list(range(lo, landmark + 1))
            if len(indices) < 2 or not consecutive(frames[max(0, lo - 1):landmark + 1]):
                reason = 'missing_native_history_frames'
            elif any(record[key][i] is None for key in ('velocity', 'dv', 'saav') for i in indices):
                reason = 'missing_behavior_or_neural_history'
            elif end + 2 >= len(times) or not consecutive(frames[onset:end + 3]):
                reason = 'censored_post_reversal_endpoint'
            elif any(record['dv'][i] is None for i in (end + 1, end + 2)):
                reason = 'missing_post_reversal_orientation'
            else:
                label_value = record['dv'][end + 1] / 2 + record['dv'][end + 2] / 2
                if label_value == 0:
                    reason = 'zero_direction_endpoint'
        if reason is not None:
            excluded.append({'event_id': event['event_id'], 'reason': reason})
            continue
        times_view = {'time_offset_seconds': [times[i] - times[landmark] for i in indices]}
        behavior = {**times_view, 'velocity': [record['velocity'][i] for i in indices],
                    'dv': [record['dv'][i] for i in indices]}
        neural = {**times_view, 'saav_history': [record['saav'][i] for i in indices]}
        cases.append({'event_id': event['event_id'], 'split_group': record['split_group'],
                      'recording_id': record['recording_id'], 'landmark_index0': landmark,
                      'source_indices0': indices, 'label': int(label_value > 0),
                      'views': {'N': neural, 'B': behavior, 'NB': {**behavior, 'saav_history': neural['saav_history']}}})
    return cases, excluded


def safe_key(secret, recording, event):
    import hmac
    need(type(secret) is bytes and len(secret) == 32, 'Exact private32byte token key')
    message = (recording + '\x00' + event).encode('utf-8')
    return 'case_' + hmac.new(secret, message, hashlib.sha256).hexdigest()[:32]


def summaries(view, arm):
    """Declared trailing summaries for one matched logistic reference family."""
    need(arm in ARMS, 'Fixed arm')
    channels = {'N': ('saav_history',), 'B': ('velocity', 'dv'),
                'NB': ('velocity', 'dv', 'saav_history')}[arm]
    exact(view, ['time_offset_seconds', *channels])
    times = view['time_offset_seconds']; result = []
    need(type(times) is list and 2 <= len(times) <= MAX_FRAMES and
         all(finite(t) and -4.8 <= t <= 0 for t in times) and times[-1] == 0 and
         all(a < b for a, b in zip(times, times[1:])), 'Past-only strictly ordered physical histories')
    n = len(times); tm = math.fsum(times) / n
    denominator = math.fsum((t - tm) ** 2 for t in times)
    need(denominator > 0 and math.isfinite(denominator), 'Representable time variation')
    for channel in channels:
        values = view[channel]
        need(type(values) is list and len(values) == n and all(finite(v) for v in values),
             'Every observed channel is finite and aligned')
        try:
            mean = math.fsum(values) / n
            centered = [v - mean for v in values]
            variance = math.fsum(v * v for v in centered) / n
            slope = math.fsum((t - tm) * v for t, v in zip(times, centered)) / denominator
            result.extend([values[-1], mean, math.sqrt(variance), min(values), max(values), slope])
        except (OverflowError, ValueError) as error:
            raise ValueError('Unrepresentable declared summaries') from error
    need(all(finite(x) for x in result), 'Finite declared summaries')
    return result

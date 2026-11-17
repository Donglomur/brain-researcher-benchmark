"""Bounded fixed-spline cue-time replay, distinct from the offline array interface.

No arbitrary function execution. Candidate numeric state is committed before the
later timestamp batch exists in this API; only that frozen state is evaluated.
This establishes an engineering information boundary, not a causal target pipeline.
"""
from .base import require, digest, write_json, read_json
from .trajectory import evaluate_frozen_state


class CueReplay:
    def __init__(self, path): self.path = path

    def commit(self, states):
        require(states and all(v['case_id'] == k for k, v in states.items()), 'cue_state_identity')
        for state in states.values():
            require(set(state) == {'schema', 'model', 'case_id', 'animal', 'features_at_cue'}, 'cue_state_keys')
            require('concurrent_lick_rate' not in state['features_at_cue'], 'cue_future_behavior')
        # Canonical encoding rejects nonfinite and nonnumeric exotic objects.
        write_json(self.path, {'schema': 'frozen_cue_commit_v1', 'states': states,
                              'digest': digest(states), 'coordinates_seen': False}, True)
        return digest(states)

    def evaluate_once(self, coordinates, expected_commitment):
        state = read_json(self.path)
        require(not state['coordinates_seen'] and state['digest'] == expected_commitment and
                digest(state['states']) == expected_commitment, 'cue_commitment_changed_or_consumed')
        require(set(coordinates) == set(state['states']), 'cue_coordinate_identity')
        for times in coordinates.values():
            require(times and all(0 <= t < 4.25 for t in times) and
                    all(a < b for a, b in zip(times, times[1:])), 'cue_native_coordinate_range')
        state['coordinates_seen'] = True
        state['coordinate_digest'] = digest(coordinates)
        write_json(self.path, state)
        predictions = {k: evaluate_frozen_state(state['states'][k], times)
                       for k, times in coordinates.items()}
        return {'predictions': predictions, 'commitment': expected_commitment,
                'coordinate_digest': digest(coordinates), 'refit': False,
                'target_processing': 'released_retrospective', 'causal_online_qualified': False}

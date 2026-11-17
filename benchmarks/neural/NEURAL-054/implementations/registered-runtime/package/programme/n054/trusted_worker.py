"""Actual reference/projection worker. Scientific route only; not used by inert controls."""
import argparse
import json
import os
from pathlib import Path
import sys
# This file is executed from a sealed package source root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from n054.common import load, put, need, digest, probabilities
from n054 import references


def main():
    p = argparse.ArgumentParser(); p.add_argument('--request', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--state', type=Path)
    p.add_argument('--build', type=Path); a = p.parse_args()
    request_cap = int(os.environ['N054_REQUEST_BYTES']); state_cap = int(os.environ['N054_STATE_BYTES'])
    need(0 < request_cap <= 8 << 30 and 0 < state_cap <= 8 << 30, 'Admitted bounded worker transport')
    r = load(a.request, request_cap)
    phase = r['phase']; out = a.output
    if phase == 'build':
        put(out / 'result.json', {'status': 'built', 'scientific_worker': 'N054_FIXED_V1'}); return
    if phase == 'family_prepare':
        result = {'status': 'prepared_family', 'transform': references.family_preparation(r['family'], r['values'])}
    elif phase in ('reference_prepare', 'summary_prepare'):
        parts = r['view']['families']; labels = r['view']['labels']
        if phase == 'reference_prepare':
            state = ({'family': 'R4', 'probabilities': [.5] * 27} if r['family'] == 'R4' else references.fit(parts, labels, r['family'], r['solve'], r.get('prepared')))
        else: state = references.summary_fit(parts, labels)
        put(out / 'state/state.json', state, state_cap)
        result = {'status': 'prepared', 'state': 'state'}
        if phase == 'summary_prepare': result['summary'] = state['summary']
    elif phase == 'summary_control_prepare':
        state = {'family': r['family'], 'summary': r['summary'], 'summary_id': digest(r['summary']),
                 'floor': 1e-8, 'temperature': 1}
        put(out / 'state/state.json', state); result = {'status': 'prepared', 'state': 'state'}
    elif phase == 'summary_query':
        state = load(a.state / 'state.json', state_cap)
        result = {'status': 'summary', 'payload': references.summary_query(r['query']['families'], state)}
    elif phase == 'reference_predict':
        state = load(a.state / 'state.json', state_cap)
        result = {'status': 'complete', 'probabilities': probabilities(references.predict(r['query']['families'], state))}
    elif phase == 'summary_predict':
        state = load(a.state / 'state.json', state_cap); payload = r['payload']
        need(state['summary_id'] == digest(payload['classes']), 'Exact serialized summary state')
        result = {'status': 'complete', 'probabilities': probabilities(references.summary_predict(payload, r['family']))}
    else: raise ValueError('Unknown scientific worker phase')
    put(out / 'result.json', result, state_cap)

if __name__ == '__main__': main()

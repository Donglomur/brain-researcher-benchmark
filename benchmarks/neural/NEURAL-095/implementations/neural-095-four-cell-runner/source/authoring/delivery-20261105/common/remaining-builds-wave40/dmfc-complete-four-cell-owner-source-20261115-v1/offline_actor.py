"""Deterministic competent-program client; no data/daemon/other-arm mounts."""
import json
from pathlib import Path
import sys


def call(value):
    print(json.dumps(value, separators=(',', ':'), allow_nan=False), flush=True)
    line = sys.stdin.buffer.readline(262145)
    if not line or len(line) > 262144:
        raise ValueError('bounded complete host response')
    result = json.loads(line)
    if value['op'] == 'freeze':
        if set(result) != {'status', 'controller_sha256'} or result['status'] != 'committed':
            raise ValueError('exact committed-source response')
        return {'controller_sha256': result['controller_sha256']}
    if set(result) != {'status', 'payload'} or result['status'] != 'ok':
        raise ValueError('exact public response')
    return result['payload']


def public(value):
    return call({'op': 'public', 'request': value})


def main():
    line = sys.stdin.buffer.readline(65537)
    if not line or len(line) > 65536:
        raise ValueError('bounded actor config')
    config = json.loads(line)
    if set(config) != {'schema', 'mode', 'tool_id', 'policy'} or config['schema'] != 'dmfc-offline-reference/v1':
        raise ValueError('exact task config')
    if config['policy'] != 'single_frozen_fit_batch/v1':
        raise ValueError('fixed admitted reference policy')
    call({'op': 'freeze', 'source': Path('/actor/program.py').read_text()})
    public({'kind': 'prepare'})
    predictions = None
    for index in range(258):
        context = public({'kind': 'next'})
        if context['completed_cases'] != index:
            raise ValueError('complete ordered cases')
        if predictions is None:
            action = {'action': 'tool', 'tool_id': config['tool_id'], 'arguments': {}}
            public({'kind': 'action', 'action': action})
            result = public({'kind': 'tool', 'tool_id': config['tool_id'], 'arguments': {}})
            if len(result['case_id']) != 258 or len(result['prediction_ms']) != 258 or len(set(result['case_id'])) != 258:
                raise ValueError('complete numerical batch')
            predictions = dict(zip(result['case_id'], result['prediction_ms']))
            again = public({'kind': 'next'})
            if again != context:
                raise ValueError('tool does not advance case')
        public({'kind': 'action', 'action': {'action': 'predict', 'case_id': context['case_id'],
                                            'prediction_ms': predictions[context['case_id']]}})
    print('{"op":"finish"}', flush=True)  # relay gives no terminal response


if __name__ == '__main__':
    main()

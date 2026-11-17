"""Trusted container worker; exact output capture precedes original reference work."""
import hashlib
import json
from pathlib import Path
import sys
import types


def main():
    invocation = json.loads(Path('/invocation.json').read_bytes())
    body = Path('/library/bridge.py').read_bytes()
    if {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} != invocation['bridge_source']:
        raise ValueError('Pinned bridge source')
    bridge = types.ModuleType('neural052_grade_bridge')
    bridge.__file__ = '/library/bridge.py'
    exec(compile(body, bridge.__file__, 'exec'), bridge.__dict__)
    bridge.need(invocation['schema'] == 'neural052_separate_numerical_invocation_v1', 'Exact grade invocation')
    import numpy
    bridge.need(sys.version_info[:3] == (3, 12, 8) and numpy.__version__ == '2.2.6',
                'Original Python3.12.8 and NumPy2.2.6 numerical environment')
    request_raw = bridge.read('/request.json', 32768)
    request = bridge.parse(request_raw)
    bridge.need(request['source'] == invocation['source'], 'Same frozen numerical source request')
    bridge.need(not list(Path('/output').iterdir()), 'Fresh trusted output volume')
    with bridge.numerical_modules('/library/scorer', invocation['numerical_sources']) as modules:
        result = bridge.bound_score(modules, '/packet', '/submission/result.json',
                                    '/submission/METHODS.md', invocation['outputs'])
    bridge.need(result['status'] in ('scored', 'invalid_submission'), 'Original numerical score or public refusal')
    score = bridge.encode(result)
    bridge.need(len(score) <= 262144, 'Original bounded numerical report')
    Path('/output/score.json').write_bytes(score)
    terminal = bridge.encode({'schema': 'neural052_separate_numerical_result_v1', 'status': result['status'],
                              'scientific_qualification': False, 'participant_code_executed': False})
    Path('/output/RESULT.json').write_bytes(terminal)
    manifest = {'schema': 'osl_transport_output_manifest_v1', 'phase_id': request['phase_id'],
                'request_sha256': hashlib.sha256(request_raw).hexdigest(),
                'files': {'score.json': bridge.pin(score), 'RESULT.json': bridge.pin(terminal)}}
    Path('/output/OUTPUTS.json').write_bytes(bridge.encode(manifest))


if __name__ == '__main__':
    main()

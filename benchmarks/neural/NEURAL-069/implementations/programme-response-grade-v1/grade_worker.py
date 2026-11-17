"""Trusted worker: original complete validation and current ROI-macro response score."""
import hashlib
import json
from pathlib import Path
import sys
import types


def main():
    with Path('/invocation.json').open('rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('Bounded trusted invocation')
    invocation = json.loads(raw)
    body = Path('/library/bridge.py').read_bytes()
    if {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} != invocation['bridge_source']:
        raise ValueError('Pinned bridge source')
    b = types.ModuleType('neural069_grade_bridge')
    b.__file__ = '/library/bridge.py'
    exec(compile(body, b.__file__, 'exec'), b.__dict__)
    b.need(invocation['schema'] == 'neural069_response_grade_invocation_v1'
           and invocation['public_validation']['outputs'] == invocation['outputs']
           and invocation['public_validation']['complete_cases'] == 80
           and invocation['public_validation']['private_target_files_accessed'] is False,
           'Original complete public validation before protected phase')
    import numpy
    b.need(sys.version_info[:3] == (3, 12, 8) and numpy.__version__ == '2.2.6',
           'Original selected Python3.12.8/NumPy2.2.6 runtime')
    request_raw = b.read('/request.json', 32768)
    request = b.parse(request_raw)
    b.need(request['source'] == invocation['source'], 'Same frozen source request')
    b.need(not list(Path('/output').iterdir()), 'Fresh trusted output')
    with b.numerical_modules('/library/scorer', invocation['numerical_sources']) as modules:
        result = b.bound_score(modules, '/packet', invocation['binding_sha256'],
                               '/submission/submission.json', invocation['outputs'])
    b.need(result['status'] in ('scored', 'undefined_required_support', 'invalid_submission'), 'Original score disposition')
    score = b.encode(result)
    b.need(len(score) <= 1000000, 'Bounded current scientific report')
    Path('/output/score.json').write_bytes(score)
    terminal = b.encode({'schema': 'neural069_response_grade_result_v1', 'status': result['status'],
                        'participant_code_executed': False, 'scientific_qualification': False})
    Path('/output/RESULT.json').write_bytes(terminal)
    manifest = {'schema': 'osl_transport_output_manifest_v1', 'phase_id': request['phase_id'],
                'request_sha256': hashlib.sha256(request_raw).hexdigest(),
                'files': {'score.json': b.pin(score), 'RESULT.json': b.pin(terminal)}}
    Path('/output/OUTPUTS.json').write_bytes(b.encode(manifest))


if __name__ == '__main__':
    main()

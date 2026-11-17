"""Build one actual local-model-authored F and fixed I submission source bundle.

An explicitly invoked genuine request performs local model generation. This
entry does not launch a neural campaign or provide independent qualification.
"""
import time
ORIGINAL_ORIGIN = time.monotonic()
ORIGINAL_CPU = time.process_time()
import argparse
import json
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).absolute().parent

def require_fresh_bytecode_prefix():
    prefix = sys.pycache_prefix
    if type(prefix) is not str or not Path(prefix).is_absolute():
        raise ValueError('supply -X pycache_prefix=ABSOLUTE_FRESH_PATH with -B')
    path = Path(prefix)
    if (not sys.dont_write_bytecode or path.exists() or path.is_symlink()
            or '..' in path.parts or any(p.is_symlink() for p in path.parents)):
        raise ValueError('bytecode prefix must remain absent and source execution must use -B')

if __name__ == '__main__':
    require_fresh_bytecode_prefix()

sys.path.insert(0, str(HERE))
from source_closure import absolute, need, parse, read_exact
from runtime_session import RuntimeSession, module_file
from authoring import build_submission, keys

MODEL_HOST_PIN = {'bytes': 32226, 'sha256': '295e96a5fc77da341d5a10dada304c0fb26e22e22d68e20a2bb66d3227f434f4'}
RENDERER_PIN = {'bytes': 3259, 'sha256': '2564400f4396bc1d46eee0daf1899e8672f02f590c01d18401764ced5259053f'}
TEMPLATE_PIN = {'bytes': 45281, 'sha256': '3de58f28fef84cc183501349c30d4b36f220f2ff681af4ac451c07242f6f0a3d'}


def validate_request(request):
    keys(request, ('schema', 'runtime', 'author', 'investigator'))
    need(request['schema'] == 'neural055-f-i-system-request-v1', 'explicit paired system request')
    spec = request['runtime']
    keys(spec, ('source_root', 'operator_root', 'output', 'limits', 'trust', 'native_profile',
                'provider_id', 'runtime_qualification', 'environment_identity', 'phase_limits'))
    for key in ('source_root', 'operator_root', 'output'):
        absolute(spec[key])
    output = Path(spec['output']); operator_root = Path(spec['operator_root'])
    need(output != operator_root and output.is_relative_to(operator_root),
         'actual source descriptors must be under the one operator root')
    keys(spec['limits'], ('wall_seconds', 'cpu_seconds', 'read_bytes', 'write_bytes',
                         'live_bytes', 'files', 'model_calls', 'stream_bytes'))
    need(type(spec['provider_id']) is str and spec['provider_id'], 'explicit local model provider ID')
    keys(spec['phase_limits'], ('offline_authoring',))
    need(spec['phase_limits']['offline_authoring'] == spec['limits']['wall_seconds'],
         'one explicit offline phase uses the same complete original lifetime')
    return request


def main(argv=None):
    require_fresh_bytecode_prefix()
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-bytes', type=int, required=True)
    parser.add_argument('--request-sha256', required=True)
    args = parser.parse_args(argv)
    reads = 0
    def charge(n):
        nonlocal reads
        need(reads + n <= 1048577, 'bounded exact initial system request')
        reads += n
    raw = read_exact(absolute(args.request), {'bytes': args.request_bytes, 'sha256': args.request_sha256},
                     1048576, charge)
    request = validate_request(parse(raw))
    session = None; first = None; result = None; terminal = None; modules = []
    try:
        session = RuntimeSession(request['runtime'], ORIGINAL_ORIGIN, ORIGINAL_CPU, bootstrap_reads=reads)
        model_name = '_n055_fi_model_job_' + uuid.uuid4().hex
        model = module_file(model_name, HERE / 'model-job/model_job.py',
                            expected=MODEL_HOST_PIN, charge=session.budget.read); modules.append(model_name)
        renderer_name = '_n055_fi_i_renderer_' + uuid.uuid4().hex
        renderer = module_file(renderer_name, HERE / 'i_renderer.py',
                               expected=RENDERER_PIN, charge=session.budget.read); modules.append(renderer_name)
        session.attach_host(model.ModelJobHost)
        def render(spec, interface):
            return renderer.render_i_program(spec, interface, read_source=lambda path:
                read_exact(path, TEMPLATE_PIN, 131072, session.budget.read))
        result = build_submission(session, request['author'], request['investigator'], render)
    except BaseException as error:
        first = error
    finally:
        if session is not None:
            try:
                terminal = session.finish(result, first)
            except BaseException as error:
                if first is None:
                    first = error
                else:
                    session.carrier.fail(error, 'offline-caller-finalization')
        for name in reversed(modules):
            sys.modules.pop(name, None)
    if first is not None:
        raise first
    print(json.dumps({'status': 'complete_source_bundle', 'output': request['runtime']['output'],
                      'submission': result['submission'], 'actual_closed_costs': terminal['actual_closed_costs'],
                      'pre_exposure_review': 'not_created; independently supplied before campaign',
                      'scientific_qualification_claimed': False, 'postscore_implemented': False},
                     sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

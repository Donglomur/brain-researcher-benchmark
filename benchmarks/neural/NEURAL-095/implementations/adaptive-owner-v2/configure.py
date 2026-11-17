"""Render a reviewed stateful actor into the actual four-cell owner closure.

Source construction only: no scientific input, candidate import or execution grant.
Original packages remain immutable. The deployed owner retains its runtime gate.
"""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
IMPLEMENTATIONS = HERE.parent
BASE_PACKAGE = IMPLEMENTATIONS / 'neural-095-four-cell-runner'
PINS = {
    'neural-095-four-cell-runner/configure.py': (13187, 'f6d94662cba01373ffec136c71b354952e806edab4915a14adad604f9aee90f9'),
    'neural-095-four-cell-runner/SOURCE_MANIFEST.json': (12343, '1c99da5b2c48aa98e233461c76232ac434b302fb364bd545239293df2e7ed082'),
    'case-investigator-v1/actor.py': (13945, '063df6a6320e784ba13b675c6363f12c460e68cc6b59821b0a5752b87b90c145'),
    'case-investigator-v1/assemble.py': (4179, '13b9d5c65bff0dcc92a7196691356d87b73011c0400a364e014fbb9d0e0f5c6c'),
    'paired-arithmetic-v2/paired.py': (5429, 'b32ec1e62c08019b3e9942a6af6abd0461c3dd1c7c96c41f6dbf61f1fbae9c55'),
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def source(relative):
    import os
    import stat
    path = IMPLEMENTATIONS / relative
    need('..' not in Path(relative).parts and all(not p.is_symlink() for p in (path, *path.parents)), 'ordinary source')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd); size, expected = PINS[relative]
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == size, 'finite source pin')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(size + 1)
        z = os.fstat(fd)
        need(len(body) == size and hashlib.sha256(body).hexdigest() == expected and
             all(getattr(a, k) == getattr(z, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
             'stable pinned source')
        return body
    finally:
        os.close(fd)


def module(name, path, body):
    result = types.ModuleType(name); result.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), result.__dict__)
    return result


def helpers():
    source('neural-095-four-cell-runner/SOURCE_MANIFEST.json')
    c = module('_adaptive_owner_source_helpers', BASE_PACKAGE / 'configure.py',
               source('neural-095-four-cell-runner/configure.py'))
    a = module('_adaptive_owner_assembler', IMPLEMENTATIONS / 'case-investigator-v1/assemble.py',
               source('case-investigator-v1/assemble.py'))
    return c, a


def replace_once(body, old, new):
    need(body.count(old) == 1, 'one exact pinned successor seam')
    return body.replace(old, new)


def exact_pair_worker(worker, paired):
    """Retain every non-arithmetic statement in the original isolated scorer."""
    nodes = [n for n in ast.parse(worker).body if isinstance(n, ast.FunctionDef) and
             n.name in ('pair_difference', 'verify_paired_arithmetic')]
    need(len(nodes) == 2, 'two original paired arithmetic functions')
    lines = worker.decode().splitlines(keepends=True)
    for node in sorted(nodes, key=lambda n: n.lineno, reverse=True):
        del lines[node.lineno - 1:node.end_lineno]
    # Full, exact accepted arithmetic source is inserted before run/main. Its
    # need() has identical fail-closed behavior; no private scorer code changes.
    remaining = ''.join(lines).encode()
    return replace_once(remaining, b'\ndef run(root, out):', b'\n' + paired + b'\n\ndef run(root, out):')


def configure(operator, destination, *, callback, program, method, review, expected):
    c, assembler = helpers()
    destination = c.ordinary(destination)
    c.need(not destination.exists() and destination.parent.is_dir(), 'fresh deployment')
    selected = c.validate_operator(operator, destination)
    manifest, bodies, manifest_pin = c.source_templates(BASE_PACKAGE)
    need(tuple(manifest_pin[k] for k in ('bytes', 'sha256')) ==
         PINS['neural-095-four-cell-runner/SOURCE_MANIFEST.json'], 'same independently pinned source manifest')
    operands = {}
    for name, path, cap in (('callback', callback, 65536), ('program', program, 65536),
                            ('method', method, 32768), ('review', review, 32768)):
        raw = c.capture(path, cap)
        need(c.pin(raw)['sha256'] == expected[name], 'explicit selected ' + name + ' SHA256')
        operands[name] = raw
    template = source('case-investigator-v1/actor.py')
    actor = assembler.assemble(template, operands['callback'])
    q, base = c.Q, c.BASE
    prefix = q + '/dmfc-adaptive-owner-v2'
    paths = {name: prefix + '/' + filename for name, filename in (
        ('callback', 'decision.py'), ('program', 'numerical.py'), ('method', 'METHOD.json'),
        ('review', 'REVIEW.json'), ('actor_template', 'actor_template.py'), ('assembled_actor', 'investigator.py'))}
    for name, raw in {**operands, 'actor_template': template, 'assembled_actor': actor}.items():
        bodies[paths[name]] = raw
    binding = {'schema': 'dmfc-stateful-investigator-admission/v2',
               'execution_authority': False, 'matched_method_proven_by_grader': False,
               **{name: {'path': path, **c.pin(bodies[path])} for name, path in paths.items()}}
    gate_body = c.capture(HERE / 'configuration_gate.py')
    reader = bodies['authoring/dmfc-timing/paired-program-cli-v1/admission.py']
    config_path = base + '/configuration.py'
    old = b"need(actor_config == {'schema': 'dmfc-offline-reference/v1', 'mode': key,\n             'tool_id': 'dmfc_predict@' + value['numerical_tool']['sha256'],\n             'policy': 'single_frozen_fit_batch/v1'}, 'only sanitized task config reaches actor')"
    new = b"need(actor_config == {'schema': ('dmfc-case-investigator/v1' if key.startswith('case_adaptive__') else 'dmfc-offline-reference/v1'), 'mode': key,\n             'tool_id': 'dmfc_predict@' + value['numerical_tool']['sha256'],\n             'policy': ('stateful_case_decisions/v1' if key.startswith('case_adaptive__') else 'single_frozen_fit_batch/v1')}, 'only mode-specific sanitized task config reaches actor')"
    bodies[config_path] = replace_once(bodies[config_path], old, new)
    bodies[config_path] = replace_once(bodies[config_path], b'    request_body = checked(ROOT, value[\'request\'], 262144)',
        b'    validate_adaptive_binding(value, captured, freeze)\n    request_body = checked(ROOT, value[\'request\'], 262144)')
    bodies[config_path] += b'\n' + reader + b'\n' + gate_body
    # Exact accepted paired arithmetic enters the actual mounted worker, and
    # every downstream delivery/producer/live-source pin is prospectively joined.
    pair_path = 'authoring/dmfc-timing/paired-investigation-v1/pair_worker.py'
    bodies[pair_path] = exact_pair_worker(bodies[pair_path], source('paired-arithmetic-v2/paired.py'))
    delivery_path = q + '/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'
    delivery = c.decode(bodies[delivery_path])
    delivery['evaluator_sources']['pair_worker'] = {'path': pair_path, **c.pin(bodies[pair_path])}
    bodies[delivery_path] = c.encode(delivery)
    producer_path = base + '/adaptive_producer.py'
    bodies[producer_path] = c.assignment(bodies[producer_path], 'MANIFEST',
        {'path': 'dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json', **c.pin(bodies[delivery_path])})
    live_path = q + '/dmfc-live-four-cell-transport-20261115-v1/live_adapter.py'
    bodies[live_path] = c.assignment(bodies[live_path], 'PRODUCER_PIN',
                                     tuple(c.pin(bodies[producer_path])[k] for k in ('bytes', 'sha256')))
    transport = selected['runtime_identity']['transport']; env = transport['environment']
    old = ("ENV=dict(os.environ,DOCKER_CONFIG='__DMFC_DOCKER_CONFIG__',DOCKER_HOST='__DMFC_DOCKER_HOST__')\n"
           "DOCKER='__DMFC_DOCKER_EXECUTABLE__'").encode()
    new = ('ENV=dict(os.environ,DOCKER_CONFIG=' + repr(env['DOCKER_CONFIG']) + ',DOCKER_HOST=' +
           repr(env['DOCKER_HOST']) + ')\nDOCKER=' + repr(transport['docker'])).encode()
    bodies[c.ENGINE] = replace_once(bodies[c.ENGINE], old, new)
    qualified = c.decode(bodies[c.QUALIFIED])
    qualified['files']['engine.py'] = {'path': c.ENGINE, **c.pin(bodies[c.ENGINE])}
    bodies[c.QUALIFIED] = c.encode(qualified)
    out = destination / selected['output_relative']
    arms = {}
    for key in ('frozen_program__cue_only', 'frozen_program__neural', 'case_adaptive__cue_only', 'case_adaptive__neural'):
        adaptive = key.startswith('case_adaptive__')
        config = {'schema': 'dmfc-case-investigator/v1' if adaptive else 'dmfc-offline-reference/v1',
                  'mode': key, 'tool_id': 'dmfc_predict@' + binding['program']['sha256'],
                  'policy': 'stateful_case_decisions/v1' if adaptive else 'single_frozen_fit_batch/v1'}
        path = base + '/actor-configs/' + key + '.json'; bodies[path] = c.encode(config)
        actor_path = paths['assembled_actor'] if adaptive else base + '/offline_actor.py'
        arms[key] = {'actor_context': key, 'context_dir': str(out / 'actors' / key),
                     'program': {'path': actor_path, **c.pin(bodies[actor_path])},
                     'config': {'path': path, **c.pin(bodies[path])}}
    freeze_path = base + '/SOURCE_FREEZE.json'
    freeze = c.decode(bodies[freeze_path])
    # Include original scorer/method sources as well as the full reviewed actor
    # assembly. Retain the old gate as historical source only, outside this gate.
    names = set(freeze['files']) | set(paths.values()) | {
        pair_path, 'benchmarks/neuroscience/neural-095/validator.py',
        'benchmarks/neuroscience/neural-095/metrics.py', 'benchmarks/neuroscience/neural-095/assets.json',
        'authoring/dmfc-timing/paired-program-cli-v1/admission.py',
        'authoring/dmfc-timing/paired-investigation-v1/PUBLIC_CONTRACT.json'}
    freeze['files'] = {name: c.pin(bodies[name]) for name in sorted(names)}
    freeze['entrypoint'] = {'path': freeze['entrypoint']['path'], **freeze['files'][freeze['entrypoint']['path']]}
    freeze['adaptive_admission'] = binding
    bodies[freeze_path] = c.encode(freeze)
    cm = module('_adaptive_owner_rendered_configuration', destination / config_path, bodies[config_path])
    payload = {'schema': 'dmfc-complete-four-cell-config/v1', 'repository_root': str(destination),
        'output_root': str(out), 'successor_freeze': {'path': freeze_path, **c.pin(bodies[freeze_path])},
        'runtime_identity': copy.deepcopy(selected['runtime_identity']),
        'host_budget': {'artifact_bytes': 1073741824, 'receipt_bytes': 268435456, 'read_bytes': 8589934592},
        'limits': copy.deepcopy(cm.LIMITS), 'reservation_policy': copy.deepcopy(cm.RESERVATIONS),
        'numerical_tool': binding['program'], 'method': binding['method'],
        'actor': {'arms': arms}, 'adaptive_admission': binding}
    # Pure capture replacement validates only already captured source operands;
    # no arbitrary candidate source or scientific input is executed by this check.
    original = cm.checked
    def captured_checked(root, descriptor, cap=262144):
        need(root == destination and descriptor['path'] in bodies, 'captured source only')
        raw = bodies[descriptor['path']]
        need(0 < len(raw) <= cap and c.pin(raw) == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'captured operand pin')
        return raw
    cm.checked = captured_checked
    try:
        cm.validate_adaptive_binding(payload, bodies, freeze)
    finally:
        cm.checked = original
    payload_body = c.encode(payload)
    result = {'schema': 'dmfc-stateful-owner-deployment/v2', 'execution_authority': False,
        'request_created': False, 'scientific_data_accessed': False, 'candidate_source_executed': False,
        'runtime_qualified': False, 'historical_runs_relabelled': False, 'source_templates': manifest_pin,
        'source_dependencies': {name: {'bytes': pin[0], 'sha256': pin[1]} for name, pin in PINS.items()},
        'configuration_gate': c.pin(gate_body), 'closure_members': len(freeze['files']),
        'rendered_sources': {n: c.pin(b) for n, b in sorted(bodies.items())},
        'payload': {'path': 'CONFIGURATION_PAYLOAD.json', **c.pin(payload_body)},
        'payload_sha256_for_operator_request': c.pin(c.canonical(payload))['sha256']}
    destination.mkdir(mode=0o700)
    for name, raw in {**bodies, 'CONFIGURATION_PAYLOAD.json': payload_body, 'DEPLOYMENT.json': c.encode(result)}.items():
        path = destination / name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            need(stream.write(raw) == len(raw), 'complete source write')
        path.chmod(0o444)
    (destination / 'artifacts-build').mkdir(mode=0o700)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', required=True); parser.add_argument('--destination', required=True)
    for name in ('callback', 'program', 'method', 'review'):
        parser.add_argument('--' + name, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    args = parser.parse_args(argv)
    c, unused = helpers()
    result = configure(c.decode(c.capture(args.operator)), args.destination,
        **{name: getattr(args, name) for name in ('callback', 'program', 'method', 'review')},
        expected={name: getattr(args, name + '_sha256') for name in ('callback', 'program', 'method', 'review')})
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

"""Bind finite DMFC source templates to an explicit deployment; never run them.

No Docker probe, data access, fit, candidate import, capacity observation or
execution-request creation is performed. The original owner admits execution.
"""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import types

HERE = Path(__file__).resolve().parent
Q = 'authoring/delivery-20261105/common/remaining-builds-wave40'
BASE = Q + '/dmfc-complete-four-cell-owner-source-20261115-v1'
GATE = Q + '/dmfc-external-candidate-admission-source-20261115-v1'
ENGINE = 'authoring/dmfc-timing/program-runner-v2/engine.py'
QUALIFIED = 'authoring/shared-program-runner-v2/QUALIFIED_IMPORTS.json'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
ENV_KEYS = {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DOCKER_HOST', 'DOCKER_CONFIG'}
REFERENCES = ['nominal_sample_interval', 'exact_condition_training_median',
              'cue_clock_ridge', 'cue_clock_total_spike_ridge', 'cue_clock_temporal_spike_ridge']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(body):
    def unique(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def ordinary(path):
    p = Path(path).absolute()
    need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'unlinked ordinary path')
    return p


def capture(path, cap=262144):
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded single-link source metadata')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        b = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(b, k) for k in fields), 'complete stable capture')
        return body
    finally:
        os.close(fd)


def relative(value):
    need(type(value) is str and value and not Path(value).is_absolute()
         and Path(value).as_posix() == value and '..' not in Path(value).parts
         and not any(ord(c) < 32 for c in value), 'canonical relative source path')
    return value


def absolute(value):
    need(type(value) is str and value and Path(value).is_absolute()
         and Path(value).as_posix() == value and '..' not in Path(value).parts
         and not any(ord(c) < 32 for c in value) and '__DMFC_' not in value
         and 'REPLACE_' not in value, 'explicit absolute deployment path')
    return value


def assignment(body, name, value):
    """Change one reviewed top-level constant, never a function body."""
    text = body.decode('utf-8')
    nodes = [n for n in ast.parse(text).body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    need(len(nodes) == 1, 'one explicit binding assignment')
    node = nodes[0]; lines = text.splitlines(keepends=True)
    return (''.join(lines[:node.lineno - 1]) + name + ' = ' + repr(value) + '\n'
            + ''.join(lines[node.end_lineno:])).encode()


def validate_operator(value, destination):
    need(type(value) is dict and set(value) == {'schema', 'output_relative', 'runtime_identity'}
         and value['schema'] == 'dmfc-portable-deployment/v1', 'exact operator declaration; no authority fields')
    output = relative(value['output_relative'])
    need(output.startswith('artifacts-build/') and len(Path(output).parts) == 2, 'one existing owner output namespace')
    identity = value['runtime_identity']
    need(type(identity) is dict and set(identity) == {'transport', 'server', 'image'}, 'explicit complete runtime identity')
    transport = identity['transport']
    need(type(transport) is dict and set(transport) == {'docker', 'environment'}, 'explicit transport only')
    absolute(transport['docker'])
    env = transport['environment']
    need(type(env) is dict and set(env) == ENV_KEYS and all(type(v) is str and v and
         not any(ord(c) < 32 for c in v) and '__DMFC_' not in v and 'REPLACE_' not in v
         for v in env.values()), 'all seven explicit sanitized environment bindings; no inherited values')
    for key in ('HOME', 'TMPDIR', 'DOCKER_CONFIG'):
        absolute(env[key])
    for item in env['PATH'].split(':'):
        absolute(item)
    need(env['DOCKER_HOST'].startswith('unix://'), 'explicit local Unix Docker socket')
    absolute(env['DOCKER_HOST'][7:])
    server = identity['server']; image = identity['image']
    need(type(server) is dict and set(server) == {'ID', 'Name', 'ServerVersion', 'OSType', 'Architecture'}
         and all(type(v) is str and v and 'REPLACE_' not in v and not any(ord(c) < 32 for c in v)
                 for v in server.values()) and server['OSType'] == 'linux', 'recorded exact Linux daemon identity')
    need(type(image) is dict and image == {'reference': IMAGE, 'Id': IMAGE, 'Os': 'linux', 'Architecture': 'arm64'},
         'unchanged exact linux/arm64 image; no tag, fallback or successor admission')
    need(server['Architecture'] in ('arm64', 'aarch64'), 'matching ARM64 daemon architecture')
    for key in ('frozen_program__cue_only', 'frozen_program__neural', 'case_adaptive__cue_only', 'case_adaptive__neural'):
        need(len(os.fsencode(destination / output / 'arms' / key / 'arm.sock')) < 100, 'original Unix socket length bound')
    return copy.deepcopy(value)


def source_templates(package=HERE):
    package = ordinary(package)
    manifest_body = capture(package / 'SOURCE_MANIFEST.json')
    manifest = decode(manifest_body)
    need(manifest['schema'] == 'dmfc-portable-source-templates/v1' and manifest['execution_authority'] is False
         and manifest['data_included'] is False and manifest['core_member_count'] == 45
         and manifest['external_candidate_member_count'] == 52, 'finite source-only package')
    members = manifest['files']
    need(type(members) is dict and 45 <= len(members) <= 80, 'finite explicitly selected source inventory')
    bodies = {}; total = 0
    for name, expected in members.items():
        relative(name)
        need(name.endswith(('.py', '.json')), 'source and metadata only')
        body = capture(package / 'source' / name)
        need(pin(body) == expected, 'exact source template: ' + name)
        total += len(body); need(total <= 2 * 1024**2, 'source-only byte bound')
        bodies[name] = body
    freeze = decode(bodies[BASE + '/SOURCE_FREEZE.json'])
    need(len(freeze['files']) == 45 and all(pin(bodies[n]) == p for n, p in freeze['files'].items()), 'exact 45-member core')
    scope = freeze['scientific_scope']
    need(scope == {'candidate_id': 'NEURAL-095', 'train': 748, 'cases_per_cell': 258,
         'views': ['cue_only', 'neural'], 'modes': ['frozen_program', 'case_adaptive'],
         'reference_count': 5, 'maximum_numerical_units': 46, 'new_reference_fits': 0}, 'unchanged finite scientific scope')
    delivery = decode(bodies[Q + '/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'])
    need(delivery['scientific_scope']['training_trials'] == 748 and
         delivery['scientific_scope']['assessment_cases_per_view'] == 258 and
         delivery['scientific_scope']['references'] == REFERENCES, 'complete original cohort and five references')
    return manifest, bodies, pin(manifest_body)


def configure(operator, destination, package=HERE):
    """Create a fresh source deployment and payload without a request or data."""
    destination = ordinary(destination)
    need(not destination.exists() and destination.parent.is_dir(), 'fresh destination with existing parent')
    selected = validate_operator(operator, destination)
    inventory, bodies, inventory_pin = source_templates(package)
    identity = selected['runtime_identity']; transport = identity['transport']; env = transport['environment']
    old = ("ENV=dict(os.environ,DOCKER_CONFIG='__DMFC_DOCKER_CONFIG__',DOCKER_HOST='__DMFC_DOCKER_HOST__')\n"
           "DOCKER='__DMFC_DOCKER_EXECUTABLE__'")
    text = bodies[ENGINE].decode()
    need(text.count(old) == 1, 'one closed engine deployment template')
    new = 'ENV=dict(os.environ,DOCKER_CONFIG=' + repr(env['DOCKER_CONFIG']) + ',DOCKER_HOST=' + repr(env['DOCKER_HOST']) + ')\nDOCKER=' + repr(transport['docker'])
    bodies[ENGINE] = text.replace(old, new).encode()
    qualified = decode(bodies[QUALIFIED])
    qualified['files']['engine.py'] = {'path': ENGINE, **pin(bodies[ENGINE])}
    bodies[QUALIFIED] = encode(qualified)
    freeze = decode(bodies[BASE + '/SOURCE_FREEZE.json'])
    freeze['files'] = {n: pin(bodies[n]) for n in freeze['files']}
    freeze['entrypoint'] = {'path': freeze['entrypoint']['path'], **freeze['files'][freeze['entrypoint']['path']]}
    bodies[BASE + '/SOURCE_FREEZE.json'] = encode(freeze)
    freeze_pin = {'path': BASE + '/SOURCE_FREEZE.json', **pin(bodies[BASE + '/SOURCE_FREEZE.json'])}
    gate = GATE + '/candidate_admission.py'
    bodies[gate] = assignment(bodies[gate], 'BASE_FREEZE', freeze_pin)
    review_path = GATE + '/REVIEW_TEMPLATE.json'
    review = decode(bodies[review_path])
    need(review['decision'] == 'UNREVIEWED_TEMPLATE' and review['execution_authority'] is False
         and review['matched_method_proven_by_grader'] is False and review['reviewer'] == ''
         and review['findings'] == '' and all(v is None for v in review['checks'].values())
         and all(v == '' for v in review['method_field_findings'].values()), 'unapproved review template only')
    review['base_owner_freeze'] = freeze_pin
    bodies[review_path] = encode(review)
    # Reuse the exact accepted payload constructor. No candidate or runtime module
    # executes here; the configuration module only defines pure capture helpers.
    c = types.ModuleType('_dmfc_deployment_configuration'); c.__file__ = str(destination / BASE / 'configuration.py')
    exec(compile(bodies[BASE + '/configuration.py'], c.__file__, 'exec'), c.__dict__)
    tree = ast.parse(bodies[BASE + '/bundle.py'])
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'configuration_payload']
    need(len(nodes) == 1, 'one accepted payload constructor')
    def descriptor(path):
        name = Path(path).relative_to(destination).as_posix()
        return {'path': name, **pin(bodies[name])}
    namespace = {'Path': Path, 'copy': copy, 'ROOT': destination, 'HERE': destination / BASE,
                 'c': c, 'descriptor': descriptor}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<accepted-configuration-payload>', 'exec'), namespace)
    payload = namespace['configuration_payload'](destination / selected['output_relative'], freeze_pin, identity)
    need('request' not in payload, 'no execution authority may be emitted')
    payload_body = encode(payload)
    prepared = {'schema': 'dmfc-portable-source-deployment/v1', 'execution_authority': False,
        'runtime_compatibility_verified': False, 'data_accessed': False, 'request_created': False,
        'core_member_count': 45, 'external_candidate_member_count': 52,
        'source_templates': inventory_pin,
        'operator_declaration_sha256': pin(canonical(selected))['sha256'],
        'rendered_sources': {n: pin(b) for n, b in sorted(bodies.items())},
        'payload': {'path': 'CONFIGURATION_PAYLOAD.json', **pin(payload_body)},
        'payload_sha256_for_operator_request': pin(canonical(payload))['sha256'],
        'operation_output': payload['output_root']}
    # All validation/rendering happens before the one fresh destination is created.
    destination.mkdir(mode=0o700)
    for name, body in {**bodies, 'CONFIGURATION_PAYLOAD.json': payload_body,
                       'DEPLOYMENT.json': encode(prepared)}.items():
        target = destination / name; target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            need(stream.write(body) == len(body), 'complete finite source write')
        target.chmod(0o444)
    (destination / 'artifacts-build').mkdir(mode=0o700)
    return prepared


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args(argv)
    result = configure(decode(capture(args.operator)), args.destination)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

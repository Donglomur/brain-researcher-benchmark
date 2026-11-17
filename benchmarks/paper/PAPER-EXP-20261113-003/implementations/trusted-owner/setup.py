"""NIDER120 owner-only metadata setup. No asset reads, imports or execution.

The existing authenticated owner performs actual operand/runtime admission.
This helper only emits its unchanged request schemas; output is never candidate input.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

MANIFEST_BYTES = 5764
MANIFEST_SHA = 'f25629720985aacb0ab588dc2b73aeeaf657357d7ee3ed7e7b1e4fcfac718aab'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite_json')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def plain(value):
    require(type(value) is str, 'path_string')
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and '\x00' not in value,
            'absolute_ordinary_path_required')
    require(str(path) == value and not value.startswith('//'), 'canonical_path_required')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink_path')
    return path


def read_metadata(path, maximum=65536):
    path = plain(str(path))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            before.st_size <= maximum, 'ordinary_bounded_metadata_required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(maximum + 1)
        closed = os.fstat(stream.fileno())
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    require(all(getattr(before, k) == getattr(v, k) for k in fields
                for v in (opened, closed, after)), 'metadata_changed')
    require(len(raw) == before.st_size, 'metadata_extent')
    return raw


def pin(path, raw):
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def pin_shape(value, maximum):
    require(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'pin_keys')
    plain(value['path'])
    require(type(value['bytes']) is int and 0 < value['bytes'] <= maximum, 'pin_extent')
    require(type(value['sha256']) is str and len(value['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in value['sha256']), 'pin_digest')
    return copy.deepcopy(value)


def verify_engine(package):
    raw = read_metadata(package / 'ENGINE_MANIFEST.json')
    require(len(raw) == MANIFEST_BYTES and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA,
            'engine_manifest_identity')
    manifest = decode(raw)
    bodies = {}
    for row in manifest['files']:
        relative = Path(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts and
                relative.parts[0] == 'engine', 'engine_relative_path')
        body = read_metadata(package / relative, maximum=262144)
        require(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'],
                'engine_source_identity:' + row['path'])
        bodies[row['path']] = body
    actual = {str(p.relative_to(package)) for p in (package / 'engine').rglob('*')
              if p.is_file() or p.is_symlink()}
    require(actual == set(bodies) and len(bodies) == 32, 'engine_source_membership')
    return bodies


def policy(value):
    keys = {'schema', 'comparison_id', 'wall_seconds', 'command_seconds', 'command_limit',
            'total_input_bytes', 'total_output_bytes', 'network', 'tools', 'model_execution'}
    require(type(value) is dict and set(value) == keys, 'policy_keys')
    require(value['schema'] == 'nider_local_authoring_policy_v1' and
            type(value['comparison_id']) is str and 1 <= len(value['comparison_id']) <= 128,
            'policy_identity')
    for key, ceiling in [('wall_seconds', 3600), ('command_seconds', 30), ('command_limit', 128),
                         ('total_input_bytes', 1048576), ('total_output_bytes', 1048576)]:
        require(type(value[key]) is int and 1 <= value[key] <= ceiling, 'policy_extent')
    require(value['command_seconds'] <= value['wall_seconds'] and value['network'] == 'none' and
            value['tools'] == ['exec', 'submit'] and value['model_execution'] is False,
            'policy_surface')
    return copy.deepcopy(value)


def plans(config, package, output, asset_template, owner_template):
    require(type(config) is dict and set(config) == {'schema', 'assets', 'delivery_basis',
            'full120_reference', 'python', 'runtime_policy', 'policy'}, 'locations_keys')
    require(config['schema'] == 'nider120_portable_setup_locations_v1', 'locations_schema')
    package = plain(str(package)); output = plain(str(output))
    require(not output.is_relative_to(package), 'output_must_be_outside_source_package')
    assets = copy.deepcopy(asset_template)
    names = {k for k in assets['assets'] if not k.startswith('doc_') and k != 'delivery_basis'}
    require(len(names) == 17 and type(config['assets']) is dict and set(config['assets']) == names,
            'exactly_17_external_asset_locations_required')
    for name, value in assets['assets'].items():
        if name == 'delivery_basis':
            assets['assets'][name] = pin_shape(config['delivery_basis'], 8192)
        elif name.startswith('doc_'):
            value['path'] = str(package / 'engine/participant' / name[4:])
        else:
            value['path'] = str(plain(config['assets'][name]))
    full_owner = copy.deepcopy(owner_template)
    full_owner['comparator_root'] = str(package / 'engine/comparator')
    full_owner['reference']['path'] = str(plain(config['full120_reference']))
    full_owner['python'] = pin_shape(config['python'], 8388608)
    runtime = pin_shape(config['runtime_policy'], 1048576)
    selected_policy = policy(config['policy'])
    paths = [v['path'] for v in assets['assets'].values()] + [full_owner['reference']['path'],
             full_owner['python']['path'], runtime['path']]
    require(len(paths) == len(set(paths)), 'duplicate_operand_path')
    require(not any(Path(v).is_relative_to(output) for v in paths), 'operand_inside_new_output')
    asset_raw = encoded(assets); owner_raw = encoded(full_owner)
    products = {'ASSET_MANIFEST.json': asset_raw, 'FULL120_OWNER.json': owner_raw}
    for arm in ('A', 'B'):
        request = {'operation': 'prepare', 'configuration_anchor': str(package / 'engine/configuration'),
                   'source_anchor': str(package / 'engine/runtime'),
                   'asset_manifest': pin(output / 'ASSET_MANIFEST.json', asset_raw),
                   'runtime_policy': runtime, 'arm': arm, 'policy': selected_policy,
                   'output_root': str(output / ('run-' + arm)),
                   'full120_owner': pin(output / 'FULL120_OWNER.json', owner_raw)}
        products['PREPARE_' + arm + '.json'] = encoded(request)
    return products, full_owner['python']


def write_new(path, raw):
    path = plain(str(path))
    require(stat.S_ISDIR(path.parent.stat().st_mode) and
            path.parent.stat().st_mode & 0o077 == 0, 'owner_private_parent_required')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as out:
        out.write(raw)
    return pin(path, raw)


def bind(config, package, output):
    bodies = verify_engine(package)
    products, python = plans(config, package, output,
        decode(bodies['engine/ASSET_MANIFEST.template.json']),
        decode(bodies['engine/FULL120_OWNER.template.json']))
    output.mkdir(mode=0o700)
    written = {name: write_new(output / name, raw) for name, raw in products.items()}
    commands = {arm: [python['path'], '-B', str(package / 'engine/owner/owner_package.py'),
                     written['PREPARE_' + arm + '.json']['path'],
                     written['PREPARE_' + arm + '.json']['sha256']] for arm in ('A', 'B')}
    result = {'schema': 'nider120_metadata_setup_result_v1', 'products': written,
              'prepare_argv': commands, 'execution_selected': False,
              'authentic_operands_read': False, 'runtime_admitted': False,
              'warning': 'Owner-only metadata. Existing owner must authenticate all operands and runtime. Never expose this directory to candidates.'}
    receipt = write_new(output / 'SETUP_RESULT.json', encoded(result))
    return {'receipt': receipt, **result}


def followup(operation, operand, digest, output):
    raw = read_metadata(operand, maximum=1048576)
    require(hashlib.sha256(raw).hexdigest() == digest, 'operand_identity')
    value = decode(raw)
    expected = {'prepare_assessment': ('nider_owner_package_session_v1', 'session'),
                'summarize': ('nider_owner_package_assessment_v1', 'assessment')}
    schema, field = expected[operation]
    require(type(value) is dict and value.get('schema') == schema, 'operand_schema')
    request = {'operation': operation, field: pin(operand, raw)}
    return {'request': write_new(output, encoded(request)), 'execution_selected': False}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    b = commands.add_parser('bind')
    b.add_argument('--locations', required=True); b.add_argument('--output', required=True)
    f = commands.add_parser('followup')
    f.add_argument('--operation', choices=['prepare_assessment', 'summarize'], required=True)
    f.add_argument('--operand', required=True); f.add_argument('--sha256', required=True)
    f.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'bind':
        result = bind(decode(read_metadata(plain(args.locations))),
                      plain(str(Path(__file__).absolute().parent)), plain(args.output))
    else:
        result = followup(args.operation, plain(args.operand), args.sha256, plain(args.output))
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()

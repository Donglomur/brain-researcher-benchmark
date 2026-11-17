"""Prepare one explicit N059 selection without opening data/model/host operands.

Future source/configuration operation only. This never starts the benchmark,
qualifies a runtime, downloads assets, or synthesizes a measured cost record.
Usage: python3 -I -B prepare_selection.py SPEC MODEL_CONFIG NATIVE_PROFILE OUTPUT
All four operands must be absolute ordinary paths. OUTPUT must not exist.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types


MANIFEST_SHA256 = 'f2ff8dae17f93ce10a4986f69f73bf86800f4863e21c0279edc4f243d6d6b56b'
MEMBERS_SHA256 = '2d7b37af47a41fceedef09c4591984b942ee40ab2d3ea5530827e8f7dd32db58'
JSON_CAP = 8 * 1024 * 1024
SELECTION_CAP = 1024 * 1024  # unchanged operator_entry.capture ceiling
SOURCE_CAP = 2 * 1024 * 1024
HEX = frozenset('0123456789abcdef')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical_path(value):
    need(type(value) is str and value.startswith('/') and '\x00' not in value,
         'absolute explicit path required')
    p = Path(value)
    need(str(p) == value and '..' not in p.parts, 'canonical path required')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'no symbolic path ancestry')
    return p


def read(path, maximum):
    p = canonical_path(str(path))
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= maximum, 'bounded ordinary single-link source/configuration')
        body = bytearray()
        while len(body) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(body)))
            body.extend(chunk)
            if not chunk:
                break
        after = os.fstat(fd)
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k)
             for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')),
             'stable complete configuration/source read')
        return bytes(body)
    finally:
        os.close(fd)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def parse(body):
    def unique(rows):
        out = {}
        for k, v in rows:
            need(k not in out, 'duplicate configuration key')
            out[k] = v
        return out
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode()


def resolved(value, path='$'):
    need(value is not None, 'unselected operand at ' + path)
    if type(value) is dict:
        for k, v in value.items():
            resolved(v, path + '.' + k)
    elif type(value) is list:
        for i, v in enumerate(value):
            resolved(v, path + '[' + str(i) + ']')


def digest(value):
    need(type(value) is str and len(value) == 64 and set(value) <= HEX,
         'full lowercase SHA256 required')


def lexical_absolute(value):
    # Pure syntax only: never stat a described input, checkpoint or host operand.
    p = PurePosixPath(value) if type(value) is str else None
    need(p is not None and p.is_absolute() and str(p) == value and
         '..' not in p.parts and '\x00' not in value, 'literal absolute operand path')
    return p


def descriptor(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'},
         'exact operand descriptor')
    lexical_absolute(value['path'])
    need(type(value['bytes']) is int and value['bytes'] > 0, 'positive operand extent')
    digest(value['sha256'])


def positive(value):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0,
         'positive finite ceiling')


def bootstrap(root):
    manifest_body = read(root / 'SOURCE_MANIFEST.json', SOURCE_CAP)
    need(pin(manifest_body)['sha256'] == MANIFEST_SHA256, 'exact accepted source manifest')
    manifest = parse(manifest_body)
    rows = manifest['files']
    need(len(rows) == 41 and sum(x['bytes'] for x in rows) < SOURCE_CAP,
         'finite accepted source closure')
    matches = [x for x in rows if x['path'] == 'captured_loader.py']
    need(len(matches) == 1, 'one captured loader')
    row = matches[0]
    body = read(root / row['path'], row['bytes'])
    need(pin(body) == {k: row[k] for k in ('bytes', 'sha256')}, 'exact loader source')
    module = types.ModuleType('n059_public_captured_loader')
    module.__file__ = str(root / row['path'])
    exec(compile(body, module.__file__, 'exec'), module.__dict__)
    loader = module.install(root, MANIFEST_SHA256)
    return loader


def validate_extra(spec, config, profile):
    from n059_owned.core import keys, integer
    from n059_owned.scientific.lifecycle import cost
    from n059_owned.native_profile import validate_profile
    keys(spec['preparation_limits'], ('max_input_bytes', 'max_output_bytes',
         'max_trials', 'max_units', 'max_spikes', 'max_work'))
    for v in spec['preparation_limits'].values():
        integer(v)
    keys(spec['stage_caps'], ('root_metadata', 'calibration', 'prediction_grade'))
    for v in spec['stage_caps'].values():
        integer(v)
    for name in ('paired_cost_limits', 'global_cost_limits', 'measured_global_F'):
        cost(spec[name])
    need(type(spec['global_F_evidence']) is dict and bool(spec['global_F_evidence']),
         'explicit actual F-development evidence; never generated by this command')
    for k in ('members', 'raw_inputs', 'native_profile'):
        descriptor(spec[k])
    for condition in ('SH', 'SHN', 'SBH', 'SBHN'):
        for arm in ('F', 'I'):
            descriptor(spec['actors'][condition][arm]['policy'])
    for k in ('docker', 'dockerd'):
        descriptor(spec['deployment'][k])
    descriptor(spec['model']['configuration'])
    keys(config, ('kind', 'request_bytes', 'maximum_input_tokens',
                  'maximum_output_tokens', 'seed', 'system_prompt'))
    need(config['kind'] == 'local_transformers_text_v1' and type(config['seed']) is int,
         'supported fixed local greedy generation policy')
    for k in ('request_bytes', 'maximum_input_tokens', 'maximum_output_tokens'):
        integer(config[k])
    need(type(config['system_prompt']) is str, 'explicit common system prompt')
    validate_profile(profile)
    need(profile['image_id'] == spec['deployment']['reference_role']['image'],
         'native profile and reference image must agree')
    checkpoints = spec['model']['checkpoint_files']
    need(type(checkpoints) is list and bool(checkpoints), 'complete checkpoint descriptor list')
    names = []
    for row in checkpoints:
        keys(row, ('path', 'bytes', 'sha256'))
        need(type(row['path']) is str, 'checkpoint relative path')
        p = PurePosixPath(row['path'])
        need(not p.is_absolute() and str(p) == row['path'] and p.parts and
             '..' not in p.parts and '\x00' not in row['path'], 'canonical checkpoint member')
        need(type(row['bytes']) is int and row['bytes'] >= 0, 'checkpoint extent')
        digest(row['sha256']); names.append(row['path'])
    need(len(names) == len(set(names)), 'distinct complete checkpoint descriptors')
    lexical_absolute(spec['output_root'])
    lexical_absolute(spec['model']['checkpoint_root'])
    for k in ('docker_config', 'daemon_root', 'whole_cgroup', 'controller_leaf', 'daemon_leaf'):
        lexical_absolute(spec['deployment'][k])
    lexical_absolute(spec['deployment']['docker_host'][7:])
    roles = [spec['model']['role'], spec['deployment']['reference_role'],
             spec['deployment']['grade_role']]
    roles += [spec['actors'][c][a]['role'] for c in ('SH', 'SHN', 'SBH', 'SBHN') for a in ('F', 'I')]
    for role in roles:
        lexical_absolute(role['python'])
        digest(role['image'][7:])
    # Descriptor/shape acceptance never authenticates the described files or host.


def write_exclusive(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            n = os.write(fd, view)
            need(n > 0, 'configuration output write progress')
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv):
    need(sys.dont_write_bytecode and sys.flags.isolated, 'invoke with -I -B')
    need(len(argv) == 5, 'usage: prepare_selection.py SPEC MODEL_CONFIG NATIVE_PROFILE OUTPUT')
    spec_path, model_path, profile_path, output = [canonical_path(x) for x in argv[1:]]
    root = canonical_path(str(Path(__file__).absolute().parent.parent / 'complete-process-v1'))
    need(not output.exists(), 'exclusive new selection output')
    need(not output.is_relative_to(root), 'selection is outside immutable source capsule')
    need(output.parent.is_dir(), 'existing selected configuration output directory')
    loader = bootstrap(root)
    from n059_owned.selection import validate
    bodies = [read(p, JSON_CAP) for p in (spec_path, model_path, profile_path)]
    spec, config, profile = map(parse, bodies)
    need(type(spec) is dict and type(spec.get('deployment')) is dict and
         type(spec.get('model')) is dict, 'filled selection template')
    auto = [('source_sha256', spec), ('code_root', spec['deployment']), ('members', spec),
            ('native_profile', spec), ('configuration', spec['model'])]
    need(all(container.get(key) is None for key, container in auto),
         'leave exactly the five documented derived operands null')
    spec['source_sha256'] = MANIFEST_SHA256
    spec['deployment']['code_root'] = str(root)
    spec['model']['configuration'] = {'path': str(model_path), **pin(bodies[1])}
    spec['native_profile'] = {'path': str(profile_path), **pin(bodies[2])}
    members_path = root.parent / 'complete-process-public-v1' / 'members.json'
    members_body = read(members_path, 8148)
    need(pin(members_body) == {'bytes': 8148, 'sha256': MEMBERS_SHA256},
         'exact public 29-session ordinary asset roster')
    from n059_owned.scientific.contracts import member_map
    member_map(parse(members_body))
    spec['members'] = {'path': str(members_path), **pin(members_body)}
    resolved(spec); resolved(config); resolved(profile)
    validate(spec); validate_extra(spec, config, profile)
    body = encode(spec)
    need(len(body) <= SELECTION_CAP, 'prepared selection fits exact operator bootstrap ceiling')
    write_exclusive(output, body)
    # This is an instruction record, not an execution or closure receipt.
    result = {'schema': 'n059_public_prepared_selection_v1', 'selection':
        {'path': str(output), **pin(body)}, 'source_manifest_sha256': MANIFEST_SHA256,
        'loader_captured_source_bytes': loader.bytes,
        'future_operator_argv': [sys.executable, '-I', '-B', str(root / 'operator_entry.py'),
                                 str(output), pin(body)['sha256'], MANIFEST_SHA256],
        'operator_python_is_current_preparation_interpreter_not_deployment_qualification': True,
        'external_supervisor_required': True, 'started': False, 'qualified': False,
        'data_model_binaries_and_host_operands_opened': False,
        'public_ordinary_member_metadata_opened': True}
    sys.stdout.buffer.write(encode(result))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))

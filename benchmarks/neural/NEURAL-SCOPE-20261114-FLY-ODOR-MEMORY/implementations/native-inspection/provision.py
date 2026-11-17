"""Create an inert, source-authenticated Fly operator directory; never inspect data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat

ROOT = Path(__file__).resolve().parent
RUNTIME = {
    'owner.py', 'worker.py', 'outer_closure.py', 'base_owner.py',
    'process_owner.py', 'donor_process_closure.py', 'audit_values.py',
    'inspector/value_consumer.py', 'inspector/structural_stream.py',
    'inspector/optional_inputs.py', 'inspector/diagnostics.py',
}
INPUT_KEYS = {'python', 'archive', 'operand_plan', 'optional_plan'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(items):
    value = {}
    for key, item in items:
        need(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def read(path, cap=262144):
    """Only source/config metadata passes here, never the three external operands."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
             'ordinary bounded source/config file required')
        data = handle.read(cap + 1)
        after = os.fstat(handle.fileno())
    keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(data) == before.st_size <= cap and
         all(getattr(before, k) == getattr(after, k) == getattr(Path(path).lstat(), k) for k in keys),
         'source/config changed during read')
    return data


def decode(data):
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def absolute(value):
    need(type(value) is str and value and '\x00' not in value and '\n' not in value and '\r' not in value,
         'ordinary absolute path string required')
    p = Path(value)
    need(p.is_absolute() and str(p) == os.path.normpath(value), 'normalized absolute path required')
    return p


def contains(parent, child):
    return parent == child or parent in child.parents


def verify_package():
    manifest = decode(read(ROOT / 'SOURCE_MANIFEST.json'))
    need(set(manifest) == {'schema', 'files'} and manifest['schema'] == 'fly-portable-source-manifest-v1',
         'source manifest schema')
    rows = manifest['files']
    need(type(rows) is list and 0 < len(rows) <= 32, 'bounded source manifest')
    bodies = {}
    total = 0
    for row in rows:
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'source row schema')
        name = row['path']
        need(type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts
             and str(Path(name)) == name and name not in bodies, 'unique relative source path')
        need(type(row['bytes']) is int and 0 < row['bytes'] <= 262144, 'source byte extent')
        data = read(ROOT / name)
        need(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'],
             'source identity mismatch: ' + name)
        bodies[name] = data
        total += len(data)
        need(total <= 1048576, 'package byte ceiling')
    expected = {'runtime/' + name for name in RUNTIME}
    expected |= {'provision.py', 'test_portable.py', 'README.md',
                 'templates/REQUEST_TEMPLATE.json', 'templates/INERT_DISPATCH.template.sh'}
    need(set(bodies) == expected, 'complete exact package member set')
    return bodies


def write_new(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def provision(config, destination):
    need(type(config) is dict and set(config) == INPUT_KEYS, 'exact four config keys required')
    external = {name: absolute(config[name]) for name in INPUT_KEYS}
    need(len(set(external.values())) == len(external), 'external paths must be distinct')
    target = absolute(str(destination))
    # Resolve only the output parent, never a dataset or descriptor path.
    need(target.parent.is_dir() and target.parent.resolve() == target.parent,
         'existing canonical output parent required')
    need(not contains(ROOT, target) and not contains(target, ROOT), 'output overlaps package')
    need(all(not contains(target, p) and not contains(p, target) for p in external.values()),
         'external operand/output overlap')
    need(not target.exists() and not target.is_symlink(), 'fresh output directory required')
    bodies = verify_package()
    request = decode(bodies['templates/REQUEST_TEMPLATE.json'])
    runtime = target / 'runtime'
    selection = target / 'selection'
    for row in request['sources'] + [request[k] for k in
            ('base_owner', 'process_owner', 'process_closer', 'worker', 'auditor', 'outer_closure')]:
        name = row['path']
        need(name in bodies and name.startswith('runtime/'), 'source request member')
        need(row['bytes'] == len(bodies[name]) and row['sha256'] == hashlib.sha256(bodies[name]).hexdigest(),
             'source request identity')
        row['path'] = str(target / name)
    for name in ('archive', 'operand_plan', 'optional_plan'):
        request[name]['path'] = str(external[name])
    request['python'] = str(external['python'])
    request['output'] = str(target / 'products')
    request['owner_output'] = str(target / 'owner')
    need(request['selected'] is False and request['root_decision'] is None and
         all(request[k] is None for k in ('selected_at_unix_ns', 'outside_host_bytes',
                                          'outside_disk_bytes', 'other_selected_cpu_slots')),
         'template must remain inert')
    bound = json_bytes(request)
    dispatch = bodies['templates/INERT_DISPATCH.template.sh'].decode()
    substitutions = {
        '__PYTHON_EXECUTABLE__': shlex.quote(str(external['python'])),
        '__SELECTION_DIR_LITERAL__': repr(str(selection)),
        '__RUNTIME_DIR_LITERAL__': repr(str(runtime)),
        '__TEMPLATE_BYTES__': str(len(bound)),
        '__TEMPLATE_SHA_LITERAL__': repr(hashlib.sha256(bound).hexdigest()),
    }
    for marker, replacement in substitutions.items():
        need(dispatch.count(marker) == 1, 'single dispatch substitution: ' + marker)
        dispatch = dispatch.replace(marker, replacement)
    # All validation precedes this create-only publication boundary. Failed writes
    # retain the private partial directory; no overwrite, rollback deletion or retry.
    target.mkdir(mode=0o700)
    runtime.mkdir(mode=0o700)
    (runtime / 'inspector').mkdir(mode=0o700)
    selection.mkdir(mode=0o700)
    for name in sorted(RUNTIME):
        write_new(runtime / name, bodies['runtime/' + name], 0o400)
    write_new(runtime / 'REQUEST_TEMPLATE.json', bound, 0o400)
    write_new(selection / 'REQUEST_TEMPLATE.json', bound)
    write_new(selection / 'INERT_DISPATCH.sh', dispatch.encode())
    result = {'schema': 'fly-portable-inert-provision-v1', 'selected': False,
              'external_bodies_opened': 0, 'runtime_qualified': False,
              'scientific_admission': False, 'source_files': len(RUNTIME),
              'request_template_sha256': hashlib.sha256(bound).hexdigest(),
              'runtime': str(runtime), 'selection': str(selection),
              'dispatch': str(selection / 'INERT_DISPATCH.sh')}
    write_new(target / 'PROVISION.json', json_bytes(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(provision(decode(read(Path(args.config), 16384)), args.output), sort_keys=True))


if __name__ == '__main__':
    main()

"""Create an inert, relocated CONSENSUS35 operator graph; never execute it."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat

HERE = Path(__file__).resolve().parent
MIB = 1048576
EXTERNAL = {
    'operands': (35572, 'bccf874d4c4a53cba7e6510c7e2cae1b2b96c24210e5dcc045f0c459048fdc73'),
    'targets': (30354, '5d69395ad44ae8f3a6a0fcfca756d2c795b6379886ca8bcb9c2d9daa8fb2490b'),
}
ROLES = {
    'closer': 'donor_process_closure.py', 'engine': 'process_owner.py',
    'fuse': 'lifecycle.py', 'guard': 'guard.py', 'policy': 'capacity_policy.py',
    'monitor': 'monitor.py', 'protocol': 'route_contract.py',
    'range_transport': 'transport.py', 'header_protocol': 'header_protocol.py',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def ordinary_path(value):
    need(type(value) is str and 0 < len(value) <= 4096 and '\x00' not in value,
         'bounded literal path')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p) == value,
         'normalized absolute path')
    need(not any(q.is_symlink() for q in (p, *p.parents)), 'no symlink paths')
    return p


def descriptor(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact descriptor fields')
    ordinary_path(value['path'])
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 262144
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'bounded exact descriptor')
    return dict(value)


def read(path, cap=262144):
    p = ordinary_path(str(path))
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
             'bounded ordinary source or configuration')
        body = f.read(before.st_size + 1)
        after = os.fstat(f.fileno())
    keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(body) == before.st_size and all(
        getattr(before, k) == getattr(after, k) == getattr(p.lstat(), k) for k in keys),
        'stable complete source or configuration')
    return body


def pin(path, body):
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def verify_package(root=HERE):
    root = ordinary_path(str(root))
    manifest = strict(read(root / 'SOURCE_MANIFEST.json'))
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'consensus35_portable_source_manifest_v1', 'source manifest schema')
    rows = manifest['files']
    need(type(rows) is list and 0 < len(rows) <= 64, 'bounded manifest member population')
    expected, allowed_dirs, declared = set(), set(), 0
    for item in rows:
        need(type(item) is dict and set(item) == {'path', 'bytes', 'sha256'}, 'manifest member')
        rel = item['path']
        need(type(rel) is str and 0 < len(rel) <= 160
             and re.fullmatch(r'[A-Za-z0-9_./-]+', rel)
             and not Path(rel).is_absolute() and '..' not in Path(rel).parts
             and str(Path(rel)) == rel and len(Path(rel).parts) <= 3
             and rel != 'SOURCE_MANIFEST.json' and rel not in expected, 'unique relative source member')
        need(type(item['bytes']) is int and 0 < item['bytes'] <= 262144
             and type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}', item['sha256']),
             'exact declared member extent/hash')
        declared += item['bytes']
        need(declared <= 2 * MIB, 'declared source aggregate before member reads')
        expected.add(rel)
        allowed_dirs.update(str(p) for p in Path(rel).parents if str(p) != '.')
    need(len(allowed_dirs) <= 128 and not expected.intersection(allowed_dirs), 'bounded distinct directory roles')
    # scandir is consumed one entry at a time: undeclared/duplicate entries fail
    # before descending, without os.walk's eager list of arbitrary directories.
    actual, seen_dirs, pending = set(), set(), [root]
    visits = 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                visits += 1
                need(visits <= len(expected) + len(allowed_dirs) + 1, 'bounded namespace entries')
                rel = str(Path(entry.path).relative_to(root))
                need(not entry.is_symlink(), 'ordinary package entries')
                if entry.is_dir(follow_symlinks=False):
                    need(rel in allowed_dirs and rel not in seen_dirs, 'declared package directory')
                    seen_dirs.add(rel)
                    pending.append(Path(entry.path))
                else:
                    need(entry.is_file(follow_symlinks=False) and rel not in actual
                         and rel in expected | {'SOURCE_MANIFEST.json'}, 'declared ordinary package member')
                    actual.add(rel)
    need(actual == expected | {'SOURCE_MANIFEST.json'} and seen_dirs == allowed_dirs,
         'complete exact package namespace')
    contents = {}
    for item in rows:
        rel = item['path']
        body = read(root / rel, item['bytes'])
        need(len(body) == item['bytes'] and hashlib.sha256(body).hexdigest() == item['sha256'],
             'manifest source identity')
        contents[rel] = body
    return contents


def replace_assignments(body, replacements):
    source = body.decode()
    lines = source.splitlines(keepends=True)
    edits = []
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in replacements):
            name = node.targets[0].id
            edits.append((node.lineno - 1, node.end_lineno, name + ' = ' + replacements[name] + '\n'))
    need(len(edits) == len(replacements), 'exact selected relocation assignments')
    for first, last, text in reversed(edits):
        lines[first:last] = [text]
    result = ''.join(lines).encode()
    ast.parse(result)
    return result


def configure(config, output, package_root=HERE):
    content = verify_package(package_root)
    need(type(config) is dict and set(config) == {
        'schema', 'python', 'operands', 'targets', 'output_path', 'capture_path', 'audit_output_path'},
        'exact configuration fields; no execution authority')
    need(config['schema'] == 'consensus35_portable_configuration_v1', 'configuration schema')
    external = {key: descriptor(config[key]) for key in ('python', 'operands', 'targets')}
    for key, identity in EXTERNAL.items():
        need((external[key]['bytes'], external[key]['sha256']) == identity,
             'complete accepted external ' + key + ' identity')
    bundle = ordinary_path(str(output))
    roots = [bundle] + [ordinary_path(config[k]) for k in ('output_path', 'capture_path', 'audit_output_path')]
    need(len(set(roots)) == 4, 'four distinct source/capture/producer/audit roots')
    for p in roots:
        need(not p.exists() and p.parent.is_dir(), 'fresh root with existing ordinary parent')
        need(all(p not in q.parents and q not in p.parents for q in roots if q != p), 'non-overlapping roots')
        need(package_root != p and package_root not in p.parents and p not in package_root.parents,
             'configured and evidence roots outside package')
    for item in external.values():
        p = Path(item['path'])
        need(all(p != q and q not in p.parents for q in roots), 'external inputs outside all output roots')
    # No external metadata, Python executable, raw data or target file is opened.
    # The unchanged owner authenticates those pins only after separate selection.
    output_path, capture, audit_path = map(str, roots[1:])
    generated = {}
    def stage(name, body):
        need(name not in generated and len(body) <= 262144, 'bounded unique generated member')
        generated[name] = body
        return pin(bundle / name, body)
    sources = {role: stage(name, content['runtime/' + name]) for role, name in ROLES.items()}
    sources.update({key: external[key] for key in ('operands', 'targets')})
    owner = stage('header_owner.py', replace_assignments(content['templates/header_owner.py'],
                  {'OUTPUT': 'Path(' + repr(output_path) + ')'}))
    launcher = stage('launch_once.py', replace_assignments(content['templates/launch_once.py'], {
        'EXPECTED_OUTPUT': 'Path(' + repr(output_path) + ')',
        'EXPECTED_PYTHON': repr(external['python']['path'])}))
    tree = ast.parse(generated['header_owner.py'])
    limits_node = next(n for n in tree.body if isinstance(n, ast.Assign)
                       and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'LIMITS')
    # Evaluate only the authenticated constant dictionary, in an empty-builtins environment.
    limits = eval(compile(ast.Expression(limits_node.value), '<constant limits>', 'eval'),
                  {'__builtins__': {}, 'MIB': MIB})
    request = {'schema': 'consensus-original35-header-owner-binding-v1',
        'execution_authority': False, 'automatic_retry': False,
        'root_authority': 'INERT portable configuration; explicit operation selection required.',
        'observer_cpu_reserved_slots': None, 'owner': owner, 'python': external['python'],
        'sources': sources, 'limits': limits, 'output_path': output_path,
        'outside_host_bytes': 1342177280, 'outside_disk_bytes': 17368612864,
        'memory_floor_bytes': 2550136832, 'disk_floor_bytes': 18459131904}
    request_pin = stage('REQUEST_INERT.json', encoded(request))
    static = stage('STATIC_BINDINGS.json', encoded({'producer_request': request_pin, 'launcher': launcher}))
    auditor_body = replace_assignments(content['templates/audit.py'], {
        'ROOT': 'Path(' + repr(output_path) + ')', 'AUDIT_ROOT': 'Path(' + repr(audit_path) + ')'})
    marker = repr({'path': '/UNCONFIGURED/STATIC_BINDINGS.json', 'bytes': 1, 'sha256': '0' * 64}).encode()
    need(auditor_body.count(marker) == 1, 'one static audit descriptor placeholder')
    auditor = stage('audit.py', auditor_body.replace(marker, repr(static).encode()))
    stage('bind_audit.py', replace_assignments(content['templates/bind_audit.py'], {
        'E': 'Path(' + repr(str(roots[2].parent)) + ')', 'P': 'Path(' + repr(output_path) + ')',
        'C': 'Path(' + repr(capture) + ')', 'A': 'Path(' + repr(audit_path) + ')'}))
    bootstrap = (
        'import os,stat,hashlib,sys; p=' + repr(auditor['path']) + '; '
        'fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); s=os.fstat(fd); '
        'assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==' + str(auditor['bytes']) + '; '
        'f=os.fdopen(fd,"rb"); b=f.read(s.st_size+1); f.close(); '
        'assert len(b)==' + str(auditor['bytes']) + ' and hashlib.sha256(b).hexdigest()=='
        + repr(auditor['sha256']) + '; sys.argv=[p]+sys.argv[1:]; '
        'exec(compile(b,p,"exec"),{"__name__":"__main__","__file__":p})')
    recipe = {'schema': 'consensus35_portable_inert_recipe_v1', 'execution_authority': False,
        'configured_request': request_pin, 'launcher': launcher, 'auditor': auditor,
        'producer_argv_inert': [external['python']['path'], '-I', '-S', '-B', launcher['path'],
             '--request', request_pin['path'], '--bytes', str(request_pin['bytes']), '--sha256', request_pin['sha256']],
        'capture_path': capture, 'audit_output_path': audit_path,
        'audit_authenticated_argv_prefix': [external['python']['path'], '-I', '-S', '-B', '-c', bootstrap],
        'bootstrap_source_read_reservation_bytes': auditor['bytes'] + 1,
        'whole_audit_managed_read_allowance_bytes': 12 * MIB,
        'external_files_read_during_configuration': 0,
        'future_scope': {'objects': 35, 'animals': 7, 'ranges': 105, 'HTTP_transactions': 210,
                         'successful_namespace_files': 440, 'maximum_returned_entity_bytes': 143780},
        'next': 'Read README before separate selection. No launch, capture creation or audit was executed.'}
    stage('OPERATION.json', encoded(recipe))
    stage('CONFIGURATION.json', encoded(config))
    stage('GENERATED_MANIFEST.json', encoded({'schema': 'consensus35_configured_graph_v1',
          'files': [pin(bundle / name, body) for name, body in sorted(generated.items())]}))
    need(sum(map(len, generated.values())) <= 2 * MIB, 'whole generated graph bound')
    bundle.mkdir(mode=0o700)
    for name, body in generated.items():
        with (bundle / name).open('xb') as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        (bundle / name).chmod(0o400)
    return {'bundle': str(bundle), 'files': len(generated), 'bytes': sum(map(len, generated.values())),
            'request': request_pin, 'execution_authority': False, 'external_files_read': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(configure(strict(read(Path(args.config))), Path(args.output)), sort_keys=True))


if __name__ == '__main__':
    main()

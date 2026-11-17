"""Inactive CLI bootstrap for an independently admitted exact source closure.

The externally selected entry/manifest pins are the trusted loading boundary.
This file never discovers alternative source or installs dependencies.
"""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
import stat
import sys
from pathlib import PurePosixPath


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_exact(path, expected, maximum):
    require(type(maximum) is int and maximum > 0 and 0 <= expected['bytes'] <= maximum, 'explicit source/metadata extent')
    parsed = PurePosixPath(path)
    require(parsed.is_absolute() and str(parsed) == path and '..' not in parsed.parts, 'canonical absolute bootstrap object')
    parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW); fd = None; primary = None
    try:
        for part in parsed.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            old, parent = parent, child
            os.close(old)
        fd = os.open(parsed.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'ordinary exact source object')
        parts = []; count = 0
        while count <= expected['bytes']:
            raw = os.read(fd, min(65536, expected['bytes'] - count + 1))
            if not raw:
                break
            parts.append(raw); count += len(raw)
        raw = b''.join(parts); after = os.fstat(fd)
        require(count == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'] and
                (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns, before.st_size) ==
                (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size), 'complete unchanged source identity')
        return raw
    except BaseException as error:
        primary = error; raise
    finally:
        first = primary
        for owned in ([fd] if fd is not None else []) + [parent]:
            try:
                os.close(owned)
            except BaseException as error:
                if first is None:
                    first = error
                else:
                    first.add_note('Secondary bootstrap descriptor close: ' + type(error).__name__)
        if primary is None and first is not None:
            raise first


def parse_json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, 'duplicate bootstrap JSON key')
            out[key] = value
        return out
    def constant(value):
        raise ValueError('nonfinite bootstrap JSON constant')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


class SourceModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, manifest, total_limit):
        require(manifest['schema'] == 'n079_exact_runtime_modules_v1' and type(manifest['modules']) is dict, 'complete selected module manifest')
        require(sum(row['pin']['bytes'] for row in manifest['modules'].values()) <= total_limit, 'preventive full source closure capacity')
        self.modules = manifest['modules']; self.bodies = {}; self.loaded = []; self.read_bytes = 0
        for name, row in self.modules.items():
            require(name.startswith(('n079_', 'ach_resource_')) or name in
                    ('wire', 'store', 'linux_backend', 'investigator_wire', 'transport', 'native_adapter', 'native_compare'),
                    'closed package source names, no standard-library shadowing')
            require(name not in sys.modules and set(row) == {'path', 'pin'}, 'fresh exact source module')
            raw = read_exact(row['path'], row['pin'], total_limit); self.read_bytes += len(raw) + 1
            self.bodies[name] = raw

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.bodies:
            return importlib.util.spec_from_loader(fullname, self)
        require(not fullname.startswith(('n079_', 'ach_resource_')) and fullname not in
                ('wire', 'store', 'linux_backend', 'investigator_wire', 'transport', 'native_adapter', 'native_compare'),
                'no fallback to an unselected package implementation')
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__name__; require(name in self.bodies and name not in self.loaded, 'once-only exact module execution')
        self.loaded.append(name)
        module.__file__ = self.modules[name]['path']
        exec(compile(self.bodies[name], module.__file__, 'exec'), module.__dict__)


def execute_outer(config, profile, clock, cost, admission):
    """Concrete finalizer and additive report return on the same original audit."""
    from n079_outer import OuterFinalizer
    from n079_report_evidence import ReportResultComposer
    chosen = config['composition']['configuration']['report_result']
    require(profile['memory_mode'] == 'fresh_lifetime' and
            config['reader_admission']['memory_mode'] == 'fresh_lifetime' and
            config['composition']['configuration']['role_templates']['observer']['role_payload']['reader_admission']['memory_mode'] == 'fresh_lifetime',
            'this genuine entry admits fresh lifetime only; no held reset descriptor')
    for role, root in config['output_roots'].items():
        require(type(root) is dict and set(root) == {'path', 'identity', 'index_result_key', 'maximum_files', 'maximum_bytes'},
                'retain complete five-field producer root and inventory ceilings')
    require(chosen['report_root'] == config['report_root'] and
            chosen['controller_root'] == {k: config['output_roots']['controller'][k] for k in ('path', 'identity')} and
            chosen['grader_root'] == {k: config['output_roots']['grader'][k] for k in ('path', 'identity')},
            'same explicit two-field report references to complete producer roots')
    finalizer = OuterFinalizer(config, profile, clock, cost, None, admission)
    original = finalizer.run()
    try:
        result = ReportResultComposer(finalizer.io, chosen).compose(original, finalizer.observations['controller'])
        # The body contains the completed artifact and counters up to
        # that artifact. This final transport is separately charged;
        # it cannot recursively contain its own final byte accounting.
        from ach_resource_common import bounded_encode
        terminal = bounded_encode({'schema': 'n079_complete_source_terminal_v1', 'status': 'complete',
            'result': result, 'original_outer': original,
            'terminal_transport': 'same reserved finalizer row; counters in body precede this whole stdout frame'},
            finalizer.selected['encoding_limits']) + b'\n'
        require(len(terminal) <= finalizer.cfg['limits']['stream_bytes'], 'selected whole terminal frame ceiling')
        finalizer.audit.charge({'write_bytes': len(terminal), 'log_bytes': len(terminal)},
                              'complete finalizer stdout frame attempted', 'outer')
        offset = 0
        while offset < len(terminal):
            finalizer.clock.tick('outer'); count = os.write(1, terminal[offset:])
            require(count > 0, 'complete terminal stdout frame'); offset += count
        finalizer.clock.tick('outer')
        return result
    except BaseException as error:
        error.n079_terminal_failure = {'original_outer': original,
            'audit': finalizer.audit.snapshot(), 'complete': False,
            'additive_result': locals().get('result'), 'stdout_bytes_completed': locals().get('offset', 0),
            'terminal_boundary': 'common physical scope already closed; original finalizer allocation/clock only'}
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--independently-enabled', action='store_true')
    parser.add_argument('--entry-mode', choices=('role', 'outer'), default='role')
    for name in ('role-config', 'role-config-sha256', 'source-manifest', 'source-manifest-sha256'):
        parser.add_argument('--' + name, required=True)
    for name in ('role-config-bytes', 'source-manifest-bytes', 'max-source-bytes', 'max-bootstrap-metadata-bytes'):
        parser.add_argument('--' + name, type=int, required=True)
    parser.add_argument('--ready-fd', type=int)
    for name in ('outer-profile', 'outer-profile-sha256', 'configuration-admission', 'configuration-admission-sha256'):
        parser.add_argument('--' + name)
    for name in ('outer-profile-bytes', 'configuration-admission-bytes'):
        parser.add_argument('--' + name, type=int)
    args = parser.parse_args()
    require(args.independently_enabled, 'inactive source route before any configuration/source/host effect')
    config_raw = read_exact(args.role_config, {'bytes': args.role_config_bytes, 'sha256': args.role_config_sha256}, args.max_bootstrap_metadata_bytes)
    config = parse_json(config_raw)
    require(config.get('execution_enabled') is True, 'separately admitted role configuration required')
    manifest_raw = read_exact(args.source_manifest, {'bytes': args.source_manifest_bytes, 'sha256': args.source_manifest_sha256}, args.max_bootstrap_metadata_bytes)
    manifest = parse_json(manifest_raw)
    if args.entry_mode == 'role':
        require(config['module_manifest_pin'] == {'bytes': len(manifest_raw), 'sha256': hashlib.sha256(manifest_raw).hexdigest()},
                'same externally selected complete module closure')
        source_admission = config['context']['source_admission']
    else:
        require(args.ready_fd is None and all(getattr(args, n) is not None for n in
            ('outer_profile', 'outer_profile_sha256', 'outer_profile_bytes', 'configuration_admission',
             'configuration_admission_sha256', 'configuration_admission_bytes')), 'complete independently selected outer entry operands')
        source_admission = config['admission']
    require(all(row in source_admission['sources'] for row in manifest['modules'].values()),
            'every actual module body belongs to the complete independently admitted runtime source closure')
    loader = SourceModules(manifest, args.max_source_bytes)
    sys.meta_path.insert(0, loader)
    try:
        cost = {'configuration_bytes': len(config_raw) + 1, 'manifest_bytes': len(manifest_raw) + 1, 'source_bytes': loader.read_bytes}
        if args.entry_mode == 'outer':
            profile_raw = read_exact(args.outer_profile, {'bytes': args.outer_profile_bytes,
                'sha256': args.outer_profile_sha256}, args.max_bootstrap_metadata_bytes)
            admission = {'path': args.configuration_admission, 'pin': {'bytes': args.configuration_admission_bytes,
                'sha256': args.configuration_admission_sha256}}
            admission_raw = read_exact(admission['path'], admission['pin'], args.max_bootstrap_metadata_bytes)
            b = parse_json(admission_raw)
            cost.update(profile_bytes=len(profile_raw) + 1, detached_admission_bytes=len(admission_raw) + 1)
            from ach_resource_common import Clock
            return execute_outer(config, parse_json(profile_raw), Clock(**b['clock']), cost, admission)
        import n079_entry
        return n079_entry.run(config, loader, args.ready_fd, cost)
    finally:
        sys.meta_path.remove(loader)


if __name__ == '__main__':
    main()

"""Inactive, pinned source inspection and explicit trusted recovered-operator API.

No candidate interface, authority issuer or default scientific execution. The
externally selected caller binds this file and its interpreter/OS custody.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

MANIFEST = (3484, 'ec2793d65232546cf74f548b97b1a029a942656e7f55d0e09c298c0630534309')
BOOTSTRAP = (7267, '74f42d41f784d0ca12a83320eee611d7b7d0cf69645bc8f7f49fe827fe43c132')
SOURCE_COUNT = 19
SOURCE_BYTES = 238488
MAX_MEMBER = 1048576
MAX_CAPTURE = 16777216


def require(ok, message):
    if not ok:
        raise ValueError(message)


def decode(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, 'duplicate metadata key')
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def relative(value):
    require(type(value) is str and value and '\\' not in value, 'relative path text')
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and not set(p.parts) & {'.', '..'}, 'canonical relative path')
    return value


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def ordinary_path(path):
    p = Path(path).absolute()
    for item in (p, *p.parents):
        require(not item.is_symlink(), 'no symlink source/request path')
    return p


class Capture:
    def __init__(self, limit):
        require(type(limit) is int and 0 < limit <= MAX_CAPTURE, 'finite startup read ceiling')
        self.limit = limit
        self.reserved = 0
        self.attempts = []

    def read(self, path, *, expected=None, cap=MAX_MEMBER):
        require(type(cap) is int and 0 <= cap <= MAX_MEMBER, 'ordinary member cap')
        require(len(self.attempts) < 22, 'complete source/request attempt roster ceiling')
        record = {'path': str(path), 'status': 'attempted', 'reserved': 0, 'observed': 0}
        self.attempts.append(record)
        fd = None
        primary = None
        raw = None
        try:
            p = ordinary_path(path)
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    stat.S_IMODE(before.st_mode) in (0o444, 0o644) and before.st_size <= cap,
                    'bounded single-link ordinary source/request')
            require(self.reserved + before.st_size <= self.limit, 'startup read ceiling before read')
            self.reserved += before.st_size
            record['reserved'] = before.st_size
            pieces = []
            while record['observed'] <= before.st_size:
                piece = os.read(fd, min(65536, before.st_size + 1 - record['observed']))
                if not piece:
                    break
                pieces.append(piece)
                record['observed'] += len(piece)
            raw = b''.join(pieces)
            after = os.fstat(fd)
            linked = p.lstat()
            require(identity(before) == identity(after) == identity(linked) and
                    len(raw) == before.st_size, 'complete EOF and stable linked source/request')
            digest = hashlib.sha256(raw).hexdigest()
            if expected is not None:
                require((len(raw), digest) == tuple(expected), 'selected exact bytes and SHA256')
            record.update(status='captured', bytes=len(raw), sha256=digest, identity=list(identity(after)))
        except BaseException as error:
            primary = error
            record.update(status='failed', error_type=type(error).__name__)
        finally:
            if fd is not None:
                owned, fd = fd, None
                try:
                    os.close(owned)
                except BaseException as error:
                    record.setdefault('cleanup_errors', []).append(type(error).__name__)
                    if primary is None:
                        primary = error
                    else:
                        primary.add_note('owned source descriptor close: ' + type(error).__name__)
        if primary is not None:
            primary.nomad_installed_source_prefix = self.report()
            raise primary
        return raw

    def report(self):
        return {'logical_read_reserved': self.reserved, 'source_read_limit': self.limit,
                'attempts': [dict(row) for row in self.attempts],
                'external_interpreter_adapter_loads_measured': False}


def capture_source(root, meter):
    root = ordinary_path(root)
    raw = meter.read(root / 'SOURCE_MANIFEST.json', expected=MANIFEST, cap=MANIFEST[0])
    manifest = decode(raw)
    require(type(manifest) is dict and set(manifest) == {'schema', 'files', 'source_data', 'scope'},
            'closed accepted manifest')
    require(manifest['schema'] == 'nomad_recovered_operator_runtime_v1', 'accepted manifest schema')
    files = manifest['files']
    require(type(files) is dict and len(files) == SOURCE_COUNT, 'complete accepted19 source roster')
    require(sum(pin['bytes'] for pin in files.values()) == SOURCE_BYTES, 'complete source extent')
    captured = {}
    for name, pin in files.items():
        relative(name)
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
                type(pin['bytes']) is int and 0 <= pin['bytes'] <= MAX_MEMBER,
                'closed source pin')
        captured[name] = meter.read(root / name, expected=(pin['bytes'], pin['sha256']), cap=pin['bytes'])
    require((len(captured['bootstrap.py']), hashlib.sha256(captured['bootstrap.py']).hexdigest()) == BOOTSTRAP,
            'actual captured accepted bootstrap')
    data = {name: captured[path] for name, path in manifest['source_data'].items()}
    require(len(data) == 4 and all(path.startswith('source_data/') for path in manifest['source_data'].values()),
            'all four captured scientific fact documents')
    return root, manifest, captured, data


def inspect_source(root=None, *, source_read_limit=MAX_CAPTURE):
    meter = Capture(source_read_limit)
    root, manifest, captured, data = capture_source(Path(__file__).parent if root is None else root, meter)
    return {'schema': 'nomad_recovered_installed_inspection_v1',
            'source_manifest_pin': {'bytes': MANIFEST[0], 'sha256': MANIFEST[1]},
            'source_members': len(captured), 'source_bytes': sum(map(len, captured.values())),
            'source_scope': manifest['scope'], 'actions': ['plan', 'consume', 'grade'],
            'trusted_API': 'run_operator(root, request_path, request_sha256, *, source_read_limit)',
            'candidate_target_API': False, 'default_scientific_execution': False,
            'qualification': False, 'source_capture': meter.report()}


def run_operator(root, request_path, request_sha256, *, source_read_limit):
    """Explicit trusted entry. Request pins/rights/profiles/OS custody are external facts.

    Scientific request/actions and target-last grading are unchanged accepted
    code. Standalone chronology consumes physical data and is evaluator-only.
    This call does not issue authority or turn declared facts into evidence.
    """
    require(type(request_sha256) is str and len(request_sha256) == 64 and
            all(c in '0123456789abcdef' for c in request_sha256), 'independently selected request digest')
    meter = Capture(source_read_limit)
    loader = None
    primary = None
    result = None
    try:
        root, manifest, captured, data = capture_source(root, meter)
        request_raw = meter.read(request_path)
        require(hashlib.sha256(request_raw).hexdigest() == request_sha256, 'selected request SHA256')
        request = decode(request_raw)
        namespace = '_nomad_recovered_' + MANIFEST[1]
        require(not any(n == namespace or n.startswith(namespace + '.') for n in sys.modules),
                'fresh owned captured-module lifetime')
        bootstrap = {'__name__': '_nomad_installed_captured_bootstrap',
                     '__file__': str(root / 'bootstrap.py')}
        exec(compile(captured['bootstrap.py'], bootstrap['__file__'], 'exec', dont_inherit=True), bootstrap)
        loader = bootstrap['CapturedModules'](namespace, captured, root)
        sys.meta_path.insert(0, loader)
        module = importlib.import_module(namespace + '.nomad_entry')
        # The accepted Store consumes this entire prefix, with no duplicate source read.
        result = module.run(request, {'source_data': data, 'bootstrap_read_bytes': meter.reserved,
                    'source_manifest_pin': {'bytes': MANIFEST[0], 'sha256': MANIFEST[1]}})
    except BaseException as error:
        primary = error
    finally:
        if loader is not None:
            try:
                loader.close()
            except BaseException as error:
                if primary is None:
                    primary = error
                else:
                    primary.add_note('captured module cleanup: ' + type(error).__name__)
    if primary is not None:
        primary.nomad_installed_source_prefix = meter.report()
        raise primary
    return result


def main():
    parser = argparse.ArgumentParser(description='Inactive recovered NoMAD source inspection only')
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--root', default=str(Path(__file__).parent))
    args = parser.parse_args()
    try:
        result = inspect_source(args.root)
        text = json.dumps(result, allow_nan=False, sort_keys=True)
        require(len(text.encode()) <= MAX_MEMBER, 'bounded inspection JSON')
        print(text)
        return 0
    except BaseException as error:
        print(json.dumps({'schema': 'nomad_recovered_inspection_failure_v1', 'type': type(error).__name__,
              'source_prefix': getattr(error, 'nomad_installed_source_prefix', None)}, allow_nan=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

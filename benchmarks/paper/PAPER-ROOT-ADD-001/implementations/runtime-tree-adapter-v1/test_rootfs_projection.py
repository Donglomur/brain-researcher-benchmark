"""Nine portable, generated-only controls for prepare_provider_rootfs.py.

The real scanner's Python/tarfile admission is exercised without a mock. A new
output leaf is required; no retained image, package, or scientific data is read.
An external authenticated aggregate may call configure() and load this class.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tarfile
import time
import types
import unittest

FIXTURE_CAP = 196608
REPORT_CAP = 65536
READ_CAP = 6291456
R = ROOT = METER = None
DEADLINE = 0
TIMED_OUT = False
SLOTS = {'input', 'candidate', 'artifacts', 'executor', 'tmp', 'proc', 'dev'}
EMPTY = {'executor/entry.py', 'input/features.npy', 'input/request.json', 'input/responses.bin'}
NORMAL = {'etc/hostname', 'etc/hosts', 'etc/resolv.conf', 'etc/mtab'}
ZERO = hashlib.sha256(b'').hexdigest()


def require(ok, message):
    if not ok: raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


class FixtureMeter:
    def __init__(self):
        self.charged = self.fixture_written = self.target_written = 0
        self.read_bytes = self.generated_tar_bytes = self.cases = 0
        self.partial_apply_failures = 0
    def reserve(self, size):
        require(type(size) is int and size >= 0 and self.charged + size <= FIXTURE_CAP,
                'cumulative generated fixture/publication allowance')
        self.charged += size
    def write(self, path, body):
        self.reserve(len(body))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            view = memoryview(body)
            while view:
                count = os.write(fd, view); require(count > 0, 'complete fixture write')
                self.fixture_written += count; view = view[count:]
            os.fsync(fd)
        finally: os.close(fd)
    def read(self, path, cap):
        path = Path(path); before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
                'ordinary bounded generated/source input')
        self.charge_read(before.st_size + 1)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            opened = os.fstat(fd)
            require((opened.st_dev, opened.st_ino, opened.st_size) ==
                    (before.st_dev, before.st_ino, before.st_size), 'opened input identity')
            raw = os.read(fd, before.st_size + 1)
        finally: os.close(fd)
        require(len(raw) == before.st_size, 'complete input')
        return raw
    def charge_read(self, count):
        require(self.read_bytes + count <= READ_CAP, 'aggregate named generated/source read allowance')
        self.read_bytes += count


def configure(rootfs_module, output_root, meter=None, deadline=None):
    global R, ROOT, METER, DEADLINE, TIMED_OUT
    R, ROOT = rootfs_module, Path(output_root)
    METER = meter if meter is not None else FixtureMeter()
    DEADLINE = deadline if deadline is not None else time.monotonic() + 45
    TIMED_OUT = False


def new_case(label):
    METER.cases += 1
    path = ROOT / ('rootfs-%02d-' % METER.cases + label)
    path.mkdir(mode=0o700)
    return path


def budget(**limits):
    class CountedBudget(R.Budget):
        def read(self, size, metadata=False):
            METER.charge_read(size)
            return super().read(size, metadata)
    base = {'archive_bytes': 65536, 'member_bytes': 4096, 'nodes': 128,
            'output_bytes': 1024, 'manifest_bytes': 8192, 'audit_bytes': 16384,
            'plan_bytes': 16384, 'read_bytes': READ_CAP, 'metadata_bytes': 1048576}
    base.update(limits)
    return CountedBudget(base, seconds=max(0, min(30, DEADLINE - time.monotonic())))


def archive(entries):
    """Generate tiny USTAR bodies; never decode a retained archive."""
    sink = io.BytesIO()
    with tarfile.open(fileobj=sink, mode='w', format=tarfile.USTAR_FORMAT) as handle:
        for name, kind, value, mode in entries:
            row = tarfile.TarInfo(name)
            row.mode = mode; row.mtime = row.uid = row.gid = 0
            if kind == 'file':
                row.size = len(value); row.type = tarfile.REGTYPE
                handle.addfile(row, io.BytesIO(value))
            else:
                row.type = {'dir': tarfile.DIRTYPE, 'symlink': tarfile.SYMTYPE,
                            'hardlink': tarfile.LNKTYPE, 'fifo': tarfile.FIFOTYPE}[kind]
                row.linkname = value if kind in ('symlink', 'hardlink') else ''
                handle.addfile(row)
    raw = sink.getvalue()
    require(len(raw) <= 65536 and METER.generated_tar_bytes + len(raw) <= 1048576,
            'finite generated tar byte construction')
    METER.generated_tar_bytes += len(raw)
    return raw


def scan(raw, **limits):
    return R.scan_export(io.BytesIO(raw), len(raw), budget(**limits))


def simple_entries():
    return [('usr', 'dir', '', 0o755), ('usr/lib', 'dir', '', 0o755),
            ('usr/lib/numeric.dat', 'file', b'alpha\n', 0o644)]


def required(path='usr/lib/numeric.dat', value=b'alpha\n'):
    return [{'path': path, 'bytes': len(value), 'sha256': sha(value)}]


def projection(raw, required_files=None, **limits):
    return R.project_roster(scan(raw), required_files if required_files is not None else required(), budget(**limits))


def plan(raw, projected, required_files=None):
    return {'schema': 'language-provider-rootfs-plan/v1',
            'image': 'sha256:ab2bea4ced8dac37524a995444e928b80c4db04e9f5e7fddd26ea5dd3962781e',
            'archive': {'bytes': len(raw), 'sha256': sha(raw)},
            'required': required_files if required_files is not None else required(), 'projection': projected}


def apply(value, raw, label, *, stored=None, output=None, manifest=None):
    case = new_case(label)
    path = case / 'generated.tar'
    METER.write(path, raw if stored is None else stored)
    # Real low-level limits prove <=1024 payload bytes + <=8192 manifest bytes.
    # Failed partial output stays charged at this full reserved extent.
    METER.reserve(9216)
    owned = budget()
    destination = output if output is not None else case / 'runtime'
    metadata = manifest if manifest is not None else case / 'MANIFEST.json'
    try:
        result = R.apply_plan(value, path, destination, metadata, owned)
        return case, destination, metadata, result
    except BaseException:
        if Path(destination).exists(): METER.partial_apply_failures += 1
        raise
    finally:
        METER.target_written += owned.counters['written_bytes']
        require(owned.counters['written_bytes'] <= 9216, 'target writes within precharged extent')


class RootfsProjectionControls(unittest.TestCase):
    def setUp(self):
        require(R is not None and not TIMED_OUT and time.monotonic() < DEADLINE, 'selected finite fixture setup')

    def test01_real_tar_scanner_has_literal_range_and_hash_oracle(self):
        raw = archive(simple_entries())
        rows = scan(raw)
        self.assertEqual([r['path'] for r in rows], ['usr', 'usr/lib', 'usr/lib/numeric.dat'])
        row = rows[2]
        self.assertEqual(row['type'], 'file')
        self.assertEqual(row['offset'], 1536)
        self.assertEqual(row['bytes'], 6)
        self.assertEqual(row['sha256'], hashlib.sha256(b'alpha\n').hexdigest())
        self.assertEqual(raw[1536:1542], b'alpha\n')

    def test02_real_tar_refuses_traversal_duplicates_case_and_special_nodes(self):
        cases = [[('../escape', 'file', b'x', 0o644)],
                 [('same', 'file', b'a', 0o644), ('same', 'file', b'b', 0o644)],
                 [('Name', 'file', b'a', 0o644), ('name', 'file', b'b', 0o644)],
                 [('pipe', 'fifo', '', 0o600)], [('.wh.deleted', 'file', b'', 0o644)]]
        for entries in cases:
            with self.subTest(names=[e[0] for e in entries]):
                with self.assertRaises((R.Refusal, tarfile.TarError)):
                    scan(archive(entries))
        raw = archive(simple_entries())
        damaged = bytearray(raw); damaged[-1] = 1
        with self.assertRaises(R.Refusal): scan(bytes(damaged))

    def test03_virtual_aliases_use_componentwise_identity_and_forward_hardlinks(self):
        entries = simple_entries() + [('f', 'file', b'wrong\n', 0o644),
            ('hard', 'hardlink', 'd/f', 0o644), ('d', 'dir', '', 0o755),
            ('d/e', 'dir', '', 0o755), ('d/f', 'file', b'correct\n', 0o755),
            ('a', 'symlink', 'd/e', 0o777), ('b', 'symlink', 'a/../f', 0o777),
            ('absolute', 'symlink', '/d/f', 0o777), ('lib', 'symlink', 'usr/lib', 0o777)]
        value = projection(archive(entries))
        files = {r['path']: r for r in value['files']}
        for name in ['b', 'hard', 'absolute', 'd/f']:
            self.assertEqual(files[name]['sha256'], sha(b'correct\n'))
            self.assertEqual(files[name]['bytes'], 8)
            self.assertEqual(files[name]['mode'], 0o555)
        self.assertNotEqual(files['b']['sha256'], files['f']['sha256'])
        self.assertEqual(files['lib/numeric.dat']['sha256'], sha(b'alpha\n'))
        self.assertEqual(files['lib/numeric.dat']['mode'], 0o444)
        self.assertEqual(files['lib/numeric.dat']['hops'], 1)
        self.assertEqual(files['lib/numeric.dat']['chain_sha256'], sha(b'["lib"]\n'))
        self.assertTrue(any(row['action'] == 'alias-copy' and row['path'] == 'b' for row in value['audit']))

    def test04_reserved_and_host_normalizations_have_exact_empty_support(self):
        entries = simple_entries() + [('proc', 'dir', '', 0o755),
            ('proc/private', 'file', b'never copied', 0o644), ('input', 'dir', '', 0o755),
            ('input/old.npy', 'file', b'never copied', 0o644), ('etc', 'dir', '', 0o755),
            ('etc/hosts', 'file', b'generated host content', 0o644),
            ('etc/mtab', 'symlink', '/proc/self/mounts', 0o777)]
        value = projection(archive(entries)); files = {r['path']: r for r in value['files']}
        self.assertEqual({d for d in value['directories'] if d.split('/')[0] in SLOTS}, SLOTS)
        self.assertEqual({p for p in files if p.split('/')[0] in SLOTS}, EMPTY)
        for path in EMPTY | NORMAL:
            self.assertEqual((files[path]['bytes'], files[path]['sha256'], files[path]['mode']), (0, ZERO, 0o444))
        self.assertNotIn('proc/private', files); self.assertNotIn('input/old.npy', files)
        self.assertEqual(files['usr/lib/numeric.dat']['sha256'], sha(b'alpha\n'))
        self.assertTrue(any(x['action'] == 'reserved-omit' for x in value['audit']))
        self.assertTrue(any(x['action'] == 'host-normalize' for x in value['audit']))

    def test05_cycles_escapes_dynamic_and_dangling_links_refuse(self):
        links = [[('a', 'symlink', 'b', 0o777), ('b', 'symlink', 'a', 0o777)],
                 [('a', 'symlink', '../../outside', 0o777)],
                 [('a', 'symlink', '/proc/self/fd/0', 0o777)],
                 [('a', 'symlink', 'absent', 0o777)],
                 [('usr/lib/back', 'symlink', '../..', 0o777)],
                 [('harddir', 'hardlink', 'usr/lib', 0o644)]]
        for added in links:
            with self.subTest(links=added):
                with self.assertRaises(R.Refusal): projection(archive(simple_entries() + added))

    def test06_preallocation_limits_have_boundary_oracles(self):
        raw = archive(simple_entries()); rows = scan(raw)
        self.assertEqual(len(R.project_roster(rows, required(), budget(nodes=19))['files']), 9)
        with self.assertRaises(R.Refusal): R.project_roster(rows, required(), budget(nodes=18))
        self.assertEqual(sum(x['bytes'] for x in R.project_roster(rows, required(), budget(output_bytes=6))['files']), 6)
        with self.assertRaises(R.Refusal): R.project_roster(rows, required(), budget(output_bytes=5))
        with self.assertRaises(R.Refusal): scan(raw, member_bytes=5)
        with self.assertRaises(R.Refusal): scan(raw, path_chars=5)
        with self.assertRaises(R.Refusal): R.project_roster(rows, required(), budget(manifest_bytes=1))
        aliased = scan(archive(simple_entries() + [('copy', 'symlink', 'usr/lib/numeric.dat', 0o777)]))
        with self.assertRaises(R.Refusal): R.project_roster(aliased, required(), budget(alias_hops=0))

    def test07_apply_streams_exact_readonly_tree_and_external_manifest(self):
        raw = archive(simple_entries() + [('copy', 'hardlink', 'usr/lib/numeric.dat', 0o644)])
        value = plan(raw, projection(raw))
        case, root, mp, result = apply(value, raw, 'positive')
        self.assertEqual(result['status'], 'ordinary_runtime_projection_created')
        self.assertFalse(result['provider_qualified']); self.assertFalse(result['scientific_qualified'])
        manifest_raw = METER.read(mp, 8192); document = json.loads(manifest_raw)
        self.assertEqual(document['schema'], 'language-frozen-public-tree/v1')
        self.assertEqual((document['kind'], document['condition']), ('runtime', 'generic'))
        self.assertEqual(result['manifest']['sha256'], sha(manifest_raw))
        self.assertEqual(result['manifest']['bytes'], len(manifest_raw))
        self.assertEqual(stat.S_IMODE(mp.stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o555)
        expected = {'usr/lib/numeric.dat': b'alpha\n', 'copy': b'alpha\n', **{p: b'' for p in EMPTY | NORMAL}}
        self.assertEqual({r['path'] for r in document['files']}, set(expected))
        for row in document['files']:
            self.assertEqual(set(row), {'path', 'bytes', 'sha256', 'mode'})
            path = root / row['path']; st = path.lstat()
            self.assertTrue(stat.S_ISREG(st.st_mode)); self.assertEqual(st.st_nlink, 1)
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o444)
            self.assertEqual(METER.read(path, 1024), expected[row['path']])
            self.assertEqual(row['sha256'], sha(expected[row['path']]))
        for path in document['directories']:
            self.assertEqual(stat.S_IMODE((root / path).lstat().st_mode), 0o555)
        self.assertNotEqual((root / 'copy').stat().st_ino, (root / 'usr/lib/numeric.dat').stat().st_ino)

    def test08_apply_custody_range_and_partial_failure_remain_refusals(self):
        raw = archive(simple_entries() + [('aaa', 'hardlink', 'usr/lib/numeric.dat', 0o644)])
        good = plan(raw, projection(raw))
        bad_archive = bytearray(raw); bad_archive[1536] ^= 1
        with self.assertRaises(R.Refusal): apply(good, raw, 'wrong-whole-hash', stored=bytes(bad_archive))
        bad_range = copy.deepcopy(good)
        next(x for x in bad_range['projection']['files'] if x['path'] == 'aaa')['offset'] = len(raw)
        with self.assertRaises(R.Refusal): apply(bad_range, raw, 'outside-range')
        partial = copy.deepcopy(good)
        next(x for x in partial['projection']['files'] if x['path'] == 'aaa')['sha256'] = sha(b'other\n')
        before = METER.partial_apply_failures
        with self.assertRaisesRegex(R.Refusal, 'copied range digest'): apply(partial, raw, 'partial-copy')
        case = ROOT / ('rootfs-%02d-partial-copy' % METER.cases)
        self.assertEqual(METER.read(case / 'runtime/aaa', 1024), b'alpha\n')
        self.assertFalse((case / 'MANIFEST.json').exists())
        self.assertEqual(METER.partial_apply_failures, before + 1)
        symlink_case = new_case('ancestor-symlink')
        target = symlink_case / 'real'; target.mkdir(mode=0o700)
        alias = symlink_case / 'alias'; body = os.fsencode(str(target)); METER.reserve(len(body))
        os.symlink(target, alias); METER.fixture_written += len(body)
        with self.assertRaises(R.Refusal): apply(good, raw, 'unsafe-output', output=alias / 'runtime')

    def test09_required_scientific_identity_cannot_be_dropped_or_rebound(self):
        raw = archive(simple_entries()); rows = scan(raw)
        for req in [[{'path': 'missing', 'bytes': 6, 'sha256': sha(b'alpha\n')}],
                    [{'path': 'usr/lib/numeric.dat', 'bytes': 7, 'sha256': sha(b'alpha\n')}],
                    [{'path': 'usr/lib/numeric.dat', 'bytes': 6, 'sha256': sha(b'other\n')}],
                    required() + required()]:
            with self.subTest(required=req):
                with self.assertRaises(R.Refusal): R.project_roster(rows, req, budget())
        value = plan(raw, projection(raw)); value['required'] = required() + required()
        with self.assertRaises(R.Refusal): R.verify_projection(value, budget())
        value = plan(raw, projection(raw)); value['image'] = 'sha256:' + '0' * 64
        with self.assertRaises(R.Refusal): R.verify_projection(value, budget())


class BoundedText:
    def __init__(self): self.body = bytearray(); self.overflow = False; self.stop = None
    def write(self, value):
        raw = value.encode('utf-8', 'replace'); remaining = 32768 - len(self.body)
        self.body.extend(raw[:remaining])
        if len(raw) > remaining:
            self.overflow = True
            if self.stop is not None: self.stop()
        return len(value)
    def flush(self): pass


class TrackedResult(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args); self.started = []; self.stopped = []; self.successes = []
    def startTest(self, test): self.started.append(test.id()); super().startTest(test)
    def stopTest(self, test): self.stopped.append(test.id()); super().stopTest(test)
    def addSuccess(self, test): self.successes.append(test.id()); super().addSuccess(test)


def source_module(path, meter, expected=None):
    raw = meter.read(path, 131072)
    if expected is not None:
        require(len(raw) == expected['bytes'] and sha(raw) == expected['sha256'], 'exact selected source body')
    value = types.ModuleType('_rootfs_projection_target'); value.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value, {'bytes': len(raw), 'sha256': sha(raw)}


def fresh_root(path):
    path = Path(path).absolute()
    require(not os.path.lexists(path) and path.parent.is_dir(), 'absent owned artifact leaf; parent exists')
    for parent in path.parents:
        require(stat.S_ISDIR(parent.lstat().st_mode), 'ordinary artifact ancestors')
    path.mkdir(mode=0o700)
    return path


def write_report(path, body):
    require(len(body) <= 32768, 'one bounded generated report')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            count = os.write(fd, view); require(count > 0, 'complete report write'); view = view[count:]
        os.fsync(fd)
    finally: os.close(fd)


def main(argv=None):
    global TIMED_OUT
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--execute-generated-controls', action='store_true')
    args = parser.parse_args(argv)
    require(args.execute_generated_controls, 'generated execution not selected')
    sys.dont_write_bytecode = True; os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    meter = FixtureMeter(); source = Path(__file__).resolve().with_name('prepare_provider_rootfs.py')
    target, source_pin = source_module(source, meter)
    root = fresh_root(args.output_root); origin = time.monotonic(); configure(target, root, meter, origin + 45)
    log = BoundedText(); result = None; failure = None
    def timeout(signum, frame):
        global TIMED_OUT
        TIMED_OUT = True; raise TimeoutError('generated rootfs control deadline')
    previous = signal.signal(signal.SIGALRM, timeout); signal.setitimer(signal.ITIMER_REAL, 45)
    try:
        def factory(*args):
            value = TrackedResult(*args); log.stop = value.stop; return value
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(RootfsProjectionControls)
        require(suite.countTestCases() == 9, 'exact public method count')
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=factory).run(suite)
    except BaseException as error: failure = {'type': type(error).__name__, 'message': str(error)[:512]}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous)
    passed = bool(result and result.wasSuccessful() and result.testsRun == 9 and len(result.successes) == 9
                  and len(result.stopped) == 9 and not result.skipped and not TIMED_OUT
                  and not log.overflow and failure is None and time.monotonic() < DEADLINE)
    log_body = bytes(log.body); write_report(root / 'TEST_LOG.txt', log_body)
    report = {'schema': 'language-rootfs-generated-controls/v1', 'status': 'passed' if passed else 'failed_or_incomplete',
              'tests': result.testsRun if result else None, 'started': result.started if result else [],
              'stopped': result.stopped if result else [], 'successes': result.successes if result else [],
              'failures': len(result.failures) if result else None, 'errors': len(result.errors) if result else None,
              'skips': len(result.skipped) if result else None, 'timeout': TIMED_OUT, 'log_truncated': log.overflow,
              'exception': failure, 'elapsed_seconds': time.monotonic() - origin,
              'source': source_pin, 'runtime': {'python': list(sys.version_info[:3]), 'tarfile': dict(target.TARFILE)},
              'fixture_accounting': dict(meter.__dict__), 'report_write_cap': REPORT_CAP,
              'test_log': {'bytes': len(log_body), 'sha256': sha(log_body)},
              'generated_only': True, 'docker': 0, 'network': 0, 'native_runs': 0, 'fits': 0,
              'original_input_reads': 0, 'full_3042_inventory_qualified': False, 'provider_qualified': False,
              'scientific_qualified': False}
    body = encoded(report); write_report(root / 'RESULT.json', body)
    print(json.dumps({'status': report['status'], 'tests': report['tests'], 'result_sha256': sha(body)}), flush=True)
    # Forward the already bounded transcript once; ordinary unittest completion
    # stays last for the maintained CI reporter. Saved artifacts remain exact.
    sys.stdout.buffer.write(log_body)
    sys.stdout.buffer.flush()
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

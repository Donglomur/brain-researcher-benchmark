"""Only relocated ABR package entry/loading checks; no authentic inputs.

Run in a fresh output directory. Production sources are copied byte-for-byte;
the synthetic render exists only in a child interpreter's memory. This does
not repeat native preparation, persistence controls, or participant scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest


PINS = {
    'prepare_delivery.py': (24833, '38a5185491c0e0edfa0707bb9abb6f9949a19c97554121fc9c0c08bbc37541c9'),
    'manual_session.py': (35856, 'a656f6086a4dcc17e899fccad9bba2683b144335e2e4dce02cf3996bcba0cc50'),
    'abr_release.py': (31207, '827faa77da9c81a34c1d5b60875ad5446881db564f3671e0a5db2466abb5852e'),
    'raster.py': (8179, 'b8cc040978a38104a9adc7747748411e4abe61aa9df9c5a6cdd3c00902dd2a18'),
    'COMMON_DOCUMENTATION.txt': (3489, '455d5777bd6e49162055cbccfff079689517d8934bebc1a6adf4e49ee0c7b754'),
}
WRITE_LIMIT = 1024 * 1024
READ_LIMIT = 8 * 1024 * 1024
REPORT_RESERVE = 16384
CHILD_SOURCE_RESERVE = 262144
STREAM_LIMIT = 16384
PACKAGE = OUTPUT = RELOCATED = None
requested = REPORT_RESERVE
reads_reserved = 0
findings = {}
commands = []


def need(ok, message):
    if not ok:
        raise ValueError(message)


def reserve_read(n):
    global reads_reserved
    need(type(n) is int and n >= 0 and reads_reserved + n <= READ_LIMIT,
         'named source/read reservation exceeded')
    reads_reserved += n


def put(path, body):
    global requested
    need(type(body) is bytes and requested + len(body) <= WRITE_LIMIT,
         'generated artifact bound exceeded')
    requested += len(body)
    with open(path, 'xb') as stream:
        stream.write(body)


def command(arguments, label):
    # Trusted pinned standard-library-only entries, no descendant spawning in
    # their selected paths. All children retain the enclosing source-pool group.
    reserve_read(CHILD_SOURCE_RESERVE)
    result = subprocess.run(
        [sys.executable, '-I', '-S', '-B', *map(str, arguments)],
        cwd=RELOCATED, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=10, check=False,
    )
    need(len(result.stdout) <= STREAM_LIMIT and len(result.stderr) <= STREAM_LIMIT,
         'selected child output exceeds source-derived bound')
    put(OUTPUT / (label + '.stdout'), result.stdout)
    put(OUTPUT / (label + '.stderr'), result.stderr)
    commands.append({'label': label, 'returncode': result.returncode,
                     'stdout_bytes': len(result.stdout), 'stderr_bytes': len(result.stderr)})
    return result


def view_arguments(implementation=None, output_name='never-prepared'):
    return [RELOCATED / 'prepare_delivery.py',
            '--implementation', implementation or RELOCATED / 'abr_release.py',
            '--raster', RELOCATED / 'raster.py',
            '--documents', RELOCATED / 'COMMON_DOCUMENTATION.txt',
            '--deadline-seconds', '5', 'view', '--store', OUTPUT / 'missing-store',
            '--store-complete-bytes', '0', '--store-complete-sha256', '0' * 64,
            '--case-id', '0' * 32, '--output', OUTPUT / output_name]


class PortableEntry(unittest.TestCase):
    def test_01_real_help_entrypoints(self):
        for name in ('prepare_delivery.py', 'manual_session.py'):
            with self.subTest(entry=name):
                result = command([RELOCATED / name, '--help'], 'help-' + name)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, b'')
                self.assertIn(b'usage:', result.stdout)
        findings['real_help_entrypoints'] = 2

    def test_02_real_preparer_missing_store(self):
        result = command(view_arguments(), 'prepare-missing-store')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'missing-store', result.stderr)
        self.assertNotIn(b'source pin differs', result.stderr)
        self.assertFalse((OUTPUT / 'never-prepared').exists())
        findings['preparer_missing_store_refused_without_output'] = True

    def test_03_real_manual_missing_store(self):
        programme = OUTPUT / 'generated_programme.py'
        put(programme, b"print('generated entry control; not a participant')\n")
        session = OUTPUT / 'never-initialized-session'
        result = command([
            RELOCATED / 'manual_session.py', 'init', '--session', session,
            '--store', OUTPUT / 'missing-store', '--store-pin', '0:' + '0' * 64,
            '--representation', RELOCATED / 'prepare_delivery.py',
            '--release', RELOCATED / 'abr_release.py', '--raster', RELOCATED / 'raster.py',
            '--programme', programme, '--operator-id', 'generated-entry-control',
            '--programme-command', 'generated-command', '--attest-pre-exposure',
        ], 'manual-missing-store')
        self.assertEqual(result.returncode, 2)
        value = json.loads(result.stderr)
        self.assertEqual(value['status'], 'operator_operation_failed_closed')
        self.assertIn('missing-store', value['reason'])
        self.assertFalse(session.exists())
        findings['manual_missing_store_refused_before_session_creation'] = True

    def test_04_mutated_dependency_refused(self):
        source = RELOCATED / 'abr_release.py'
        reserve_read(source.stat().st_size)
        changed = source.read_bytes() + b'\n# generated dependency mutation\n'
        bad = OUTPUT / 'changed_release.py'
        put(bad, changed)
        result = command(view_arguments(bad, 'mutated-dependency-output'), 'mutated-dependency')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'missing-store', result.stderr)
        self.assertIn(b'ordinary pinned file required', result.stderr)
        self.assertFalse((OUTPUT / 'mutated-dependency-output').exists())
        findings['modified_dependency_refused_before_store_access'] = True

    def test_05_real_packaged_loader_and_generated_render(self):
        # A real relocated import and load_sources call, not a substitute module
        # or monkeypatched renderer. The packet is explicitly generated.
        helper = OUTPUT / 'generated_render_check.py'
        body = b'''from pathlib import Path
import importlib.util, json, struct, sys
p = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('portable_preparer', p / 'prepare_delivery.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r, raster, docs = m.load_sources(p / 'abr_release.py', p / 'raster.py', p / 'COMMON_DOCUMENTATION.txt')
packet = {'case_id': '0'*32, 'stimulus': {'kind': 'click'}, 'axis': 'sample_index',
          'amplitude_unit': 'native_raw_value', 'labelled_support_count': 0,
          'traces': [{'trace_id': f'{j+1:032x}', 'release_level_code': [0,5,5][j],
                      'sample_indices': [0,1952], 'samples': [float((i%7)-3) for i in range(1953)]}
                     for j in range(3)]}
v = r.Viewer(packet, raster)
numeric = v.action({'type':'numeric'})
assert numeric == r.canonical(packet)
pages = v.action({'type':'pages'})
png, meta = v.action({'type':'page','page':0})
assert png[:8] == b'\\x89PNG\\r\\n\\x1a\\n'
width, height = struct.unpack('>II', png[16:24])
assert (width,height) == (1400,820)
assert pages['pages'] == 1 and pages['trace_count'] == 3
assert meta['trace_indices'] == [0,1,2] and meta['samples_drawn'] == 5859
assert meta['native_amplitude_scale'] == 3.0
print(json.dumps({'numeric_roundtrip':True,'width':width,'height':height,'png_bytes':len(png),
                  'meta':meta,'documents_bytes':len(docs),'generated_only':True}, sort_keys=True))
'''
        put(helper, body)
        result = command([helper, RELOCATED], 'generated-render')
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stderr, b'')
        value = json.loads(result.stdout)
        self.assertTrue(value['generated_only'])
        self.assertTrue(value['numeric_roundtrip'])
        self.assertEqual(value['meta']['samples_drawn'], 5859)
        self.assertEqual(value['documents_bytes'], 3489)
        findings['real_packaged_loader_generated_render'] = value


def main():
    global PACKAGE, OUTPUT, RELOCATED
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    PACKAGE = args.package.resolve()
    OUTPUT = args.output.absolute()
    need(not OUTPUT.exists() and OUTPUT.parent.is_dir(), 'fresh output with existing parent required')
    OUTPUT.mkdir(mode=0o700)
    RELOCATED = OUTPUT / 'relocated package'
    RELOCATED.mkdir(mode=0o700)
    origin = time.monotonic()
    result = None
    preparation_error = None
    try:
        for name, (size, sha) in PINS.items():
            path = PACKAGE / name
            reserve_read(size)
            body = path.read_bytes()
            need(len(body) == size and hashlib.sha256(body).hexdigest() == sha,
                 'packaged source identity differs: ' + name)
            need(b'/Users/' not in body and b'/private/var/' not in body,
                 'machine-private source path')
            put(RELOCATED / name, body)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PortableEntry)
        need(suite.countTestCases() == 5, 'exact five changed-entry methods required')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    except Exception as exc:
        preparation_error = type(exc).__name__ + ': ' + str(exc)
    finally:
        passed = bool(result is not None and result.wasSuccessful() and result.testsRun == 5
                      and not result.skipped and preparation_error is None)
        report = {'schema':'abr-portable-entry-generated-check-v1','passed':passed,
                  'methods_run':result.testsRun if result else 0,
                  'failures':len(result.failures) if result else 0,
                  'errors':len(result.errors) if result else 0,
                  'skips':len(result.skipped) if result else 0,
                  'preparation_error':preparation_error,'findings':findings,'commands':commands,
                  'elapsed_seconds':time.monotonic()-origin,
                  'artifacts_requested_with_report_reserve':requested,
                  'read_reserved_bytes':reads_reserved,'write_cap':WRITE_LIMIT,'read_cap':READ_LIMIT,
                  'accounting':'Full logical publications plus16384 report reservation; child source reads conservatively262144 each. Not OS or physical-I/O measurement.',
                  'authentic_data_or_private_annotations_opened':False,
                  'original_or_persistence_suite_replayed':False,'new_benchmark_count':0}
        encoded=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
        need(len(encoded)<=REPORT_RESERVE, 'result envelope exceeds existing reservation')
        with open(OUTPUT/'RESULT.json','xb') as stream: stream.write(encoded)
        print(json.dumps({'passed':passed,'methods_run':report['methods_run'],
                          'read_reserved_bytes':reads_reserved,'artifacts_requested_bytes':requested}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

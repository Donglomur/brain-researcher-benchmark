"""Generated source relocation and path controls; no native/data/model execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import tempfile
import time
import types
import unittest

HERE = Path(__file__).absolute().parent
raw = (HERE / 'verify_source.py').read_bytes()
v = types.ModuleType('_078_portable_verifier')
v.__file__ = str(HERE / 'verify_source.py')
exec(compile(raw, v.__file__, 'exec'), v.__dict__)
source_raw = (HERE / 'SOURCE_MANIFEST.json').read_bytes()
SOURCE = v.pin(source_raw)
BODIES, _ = v.verify(HERE, SOURCE)
WRITTEN = 0


def put(path, body):
    global WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    WRITTEN += len(body)


def relocated(parent):
    destination = parent / 'relocated release with spaces'
    destination.mkdir()
    for name, body in {**BODIES, 'SOURCE_MANIFEST.json': source_raw}.items():
        put(destination / name, body)
    return destination


class Portable(unittest.TestCase):
    def check_refusal(self, mutate, message=None, repin=False):
        with tempfile.TemporaryDirectory(prefix='n078-portable-') as temporary:
            parent = Path(temporary).resolve()
            source = relocated(parent)
            mutate(source)
            selected = v.pin((source / 'SOURCE_MANIFEST.json').read_bytes()) if repin else SOURCE
            target = parent / 'operator'
            with self.assertRaises((ValueError, OSError, KeyError)):
                bodies, _ = v.verify(source, selected)
                v.install_producer(target, source, bodies, selected)
            self.assertFalse(os.path.lexists(target))

    def test_relocated_complete_producer_install_and_real_bootstrap(self):
        with tempfile.TemporaryDirectory(prefix='n078-portable-') as temporary:
            parent = Path(temporary).resolve()
            source = relocated(parent)
            bodies, _ = v.verify(source, SOURCE)
            target = parent / 'new operator with spaces'
            receipt = v.install_producer(target, source, bodies, SOURCE)
            self.assertEqual(len(receipt['files']), 18)
            self.assertFalse(receipt['candidate_or_grader_executed'])
            for row in receipt['files']:
                self.assertEqual(v.pin((target / row['path']).read_bytes()),
                                 {k: row[k] for k in ('bytes', 'sha256')})
            api = types.ModuleType('_078_relocated_api')
            api.__file__ = str(source / 'score_artifact.py')
            exec(compile(bodies['score_artifact.py'], api.__file__, 'exec'), api.__dict__)
            captured, mods, _ = api.bootstrap(SOURCE)
            self.assertEqual(captured, bodies)
            self.assertEqual(mods['policy'].SCOPE['participants'], 8)
            self.assertEqual(mods['policy'].SCOPE['required_fields'], 195)
            adapter = types.ModuleType('_078_relocated_adapter')
            adapter.__file__ = str(target / v.PRODUCER_RELATIVE / 'adapter.py')
            exec(compile(bodies['producer/adapter.py'], adapter.__file__, 'exec'), adapter.__dict__)
            self.assertEqual(adapter.ROOT, target)
            self.assertEqual(len(list((target / v.PRODUCER_RELATIVE).rglob('*'))), 19)
            self.assertFalse((target / 'authoring/delivery-20261105/common/exports').exists())

    def test_changed_body_refuses_before_install(self):
        self.check_refusal(lambda p: (p / 'grading.py').write_bytes(b'altered\n'))

    def test_missing_authored_dependency_refuses(self):
        self.check_refusal(lambda p: (p / 'producer/program/holder.py').unlink())

    def test_extra_file_refuses(self):
        self.check_refusal(lambda p: (p / 'unexpected.py').write_bytes(b'extra\n'))

    def test_extra_empty_directory_refuses(self):
        self.check_refusal(lambda p: (p / 'unexpected').mkdir())

    def test_symlink_member_refuses(self):
        def mutate(p):
            original = p / 'grading.py'
            original.unlink()
            original.symlink_to(p / 'admission.py')
        self.check_refusal(mutate)

    def test_hardlink_member_refuses(self):
        def mutate(p):
            os.link(p / 'grading.py', p.parent / 'outside-hardlink')
        self.check_refusal(mutate)

    def test_selected_manifest_digest_refuses(self):
        self.check_refusal(lambda p: (p / 'SOURCE_MANIFEST.json').write_bytes(source_raw + b' '))

    def test_duplicate_json_key_refuses_even_with_new_pin(self):
        self.check_refusal(lambda p: (p / 'SOURCE_MANIFEST.json').write_bytes(
            b'{"schema":"neural078_deferred_grade_source_v1","schema":"again","files":[]}'), repin=True)

    def test_traversing_member_refuses_even_with_new_pin(self):
        def mutate(p):
            obj = json.loads(source_raw)
            obj['files'][0]['path'] = '../outside.py'
            (p / 'SOURCE_MANIFEST.json').write_text(json.dumps(obj))
        self.check_refusal(mutate, repin=True)

    def test_boolean_extent_refuses_even_with_new_pin(self):
        def mutate(p):
            obj = json.loads(source_raw)
            obj['files'][0]['bytes'] = True
            (p / 'SOURCE_MANIFEST.json').write_text(json.dumps(obj))
        self.check_refusal(mutate, repin=True)

    def test_operator_root_existing_or_linked_is_not_modified(self):
        with tempfile.TemporaryDirectory(prefix='n078-portable-') as temporary:
            parent = Path(temporary).resolve()
            existing = parent / 'existing'
            existing.mkdir()
            sentinel = existing / 'sentinel'
            sentinel.write_bytes(b'preserve')
            linked = parent / 'linked'
            linked.symlink_to(existing, target_is_directory=True)
            for target in (existing, linked):
                with self.assertRaises(ValueError):
                    v.install_producer(target, HERE, BODIES, SOURCE)
            self.assertEqual(sentinel.read_bytes(), b'preserve')
            self.assertEqual(sorted(p.name for p in existing.iterdir()), ['sentinel'])

    def test_release_or_destination_linked_ancestor_refuses(self):
        with tempfile.TemporaryDirectory(prefix='n078-portable-') as temporary:
            parent = Path(temporary).resolve()
            actual = parent / 'actual'
            actual.mkdir()
            source = relocated(actual)
            linked = parent / 'linked'
            linked.symlink_to(actual, target_is_directory=True)
            with self.assertRaises(ValueError):
                v.verify(linked / source.name, SOURCE)
            with self.assertRaises(ValueError):
                v.install_producer(linked / 'new-root', HERE, BODIES, SOURCE)
            self.assertFalse((actual / 'new-root').exists())

    def test_nested_destination_refuses(self):
        with tempfile.TemporaryDirectory(prefix='n078-portable-') as temporary:
            source = relocated(Path(temporary).resolve())
            with self.assertRaises(ValueError):
                v.install_producer(source / 'operator', source, BODIES, SOURCE)
            self.assertFalse((source / 'operator').exists())

    def test_wrong_program_manifest_refuses_even_with_repin(self):
        def mutate(p):
            target = p / 'producer/program/SOURCE_MANIFEST.json'
            target.write_bytes(target.read_bytes() + b' ')
            manifest = json.loads(source_raw)
            for row in manifest['files']:
                if row['path'] == 'producer/program/SOURCE_MANIFEST.json':
                    row.update(v.pin(target.read_bytes()))
            (p / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest))
        self.check_refusal(mutate, repin=True)


if __name__ == '__main__':
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Portable))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print(json.dumps({'generated_source_only': True, 'tests': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors),
                      'source_capture_read_bytes': v.READ_BYTES,
                      'test_direct_reads_additional_conservative': 2000000,
                      'generated_source_written_bytes': WRITTEN,
                      'elapsed_seconds': time.monotonic() - started,
                      'cpu_seconds': usage.ru_utime + usage.ru_stime,
                      'peak_rss_darwin_bytes': usage.ru_maxrss,
                      'native_processes_started': 0, 'children': 0, 'pid': os.getpid()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

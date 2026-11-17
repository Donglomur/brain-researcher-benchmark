"""Generated controls for the source-only public-mode publisher successor.

No native runtime, candidate, scientific input, fitting, or grading is invoked.
Fixtures, including incomplete publications, are retained in --artifacts.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import stat
import time
import unittest
from unittest.mock import patch


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


class PublicModeControls(unittest.TestCase):
    def setUp(self):
        self.root = ARTIFACTS / self.id().rsplit('.', 1)[-1]
        self.root.mkdir(mode=0o700)
        self.previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, self.previous_umask)
        self.io = publisher.IO(time.monotonic() + 30)

    def fixture(self):
        source = self.root / 'generated-input'
        source.mkdir(mode=0o700)
        names = ('worker.py', 'controller.py', 'engine/native.py',
                 'engine/holder.py', 'candidate_entry.py', 'baseline_entry.py',
                 'BINDINGS.json', 'protocol.py', 'entry_common.py',
                 'spatial/generated.py')
        bodies = {name: ('# invented fixture: ' + name + '\n').encode()
                  for name in names}
        bodies['BINDINGS.json'] = b'{"generated":true}\n'
        for name, raw in bodies.items():
            target = source / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(raw)
        manifest = {
            'schema': 'visual_alpha_complete_program_source_v1',
            'task_id': 'PAPER-ROOT-ADD-014',
            'source_only': True,
            'files': {name: publisher.pin(raw) for name, raw in bodies.items()},
        }
        raw = publisher.encode(manifest)
        (source / 'SOURCE_MANIFEST.json').write_bytes(raw)
        return source, manifest, bodies, raw

    def test_frozen_sources_publish_all_bodies_without_widening_private_paths(self):
        source, manifest, bodies, manifest_raw = self.fixture()
        private = self.root / 'private-receipt'
        private.write_bytes(b'private generated control\n')
        destination = self.root / 'snapshot'
        original_end = self.io.end
        returned, captured = publisher.frozen_sources(
            source, destination, publisher.pin(manifest_raw), self.io)
        self.assertEqual(returned, manifest)
        self.assertEqual(captured, bodies)
        for name, raw in {**bodies, 'SOURCE_MANIFEST.json': manifest_raw}.items():
            with self.subTest(name=name):
                self.assertEqual((destination / name).read_bytes(), raw)
                self.assertEqual(mode(destination / name), 0o444)
                self.assertEqual(mode(source / name), 0o600)
        for directory in (destination, destination / 'engine', destination / 'spatial'):
            self.assertEqual(mode(directory), 0o555)
        self.assertEqual(mode(self.root), 0o700)
        self.assertEqual(mode(source), 0o700)
        self.assertEqual(mode(private), 0o600)
        self.assertEqual(self.io.write, sum(map(len, bodies.values())) + len(manifest_raw))
        self.assertEqual(self.io.read, len(manifest_raw) + 1 +
                         2 * sum(len(raw) + 1 for raw in bodies.values()))
        self.assertEqual(self.io.end, original_end)

    def test_save_full_short_writes_then_owned_fd_mode_then_fsync(self):
        target = self.root / 'nested' / 'public'
        raw = b'generated public body with several short writes\n'
        events = []
        real_write, real_fchmod, real_fsync = os.write, os.fchmod, os.fsync

        def short_write(fd, view):
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o400)
            n = real_write(fd, view[:7])
            events.append(('write', n))
            return n

        def owned_mode(fd, requested):
            st = os.fstat(fd)
            self.assertTrue(stat.S_ISREG(st.st_mode))
            self.assertEqual(st.st_ino, target.stat().st_ino)
            self.assertEqual(st.st_size, len(raw))
            self.assertEqual(target.read_bytes(), raw)
            self.assertEqual(requested, 0o444)
            events.append(('mode', requested))
            real_fchmod(fd, requested)

        def sync(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o444)
                events.append(('file-sync', 0))
            return real_fsync(fd)

        with patch.object(publisher.os, 'write', side_effect=short_write), \
             patch.object(publisher.os, 'fchmod', side_effect=owned_mode), \
             patch.object(publisher.os, 'fsync', side_effect=sync):
            result = self.io.save(target, raw)
        self.assertEqual(result, publisher.pin(raw))
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(mode(target), 0o444)
        self.assertEqual(mode(target.parent), 0o700)
        self.assertGreater(len(events), 3)
        self.assertEqual(events[-2:], [('mode', 0o444), ('file-sync', 0)])

    def test_empty_public_body_has_exact_mode(self):
        target = self.root / 'empty'
        self.assertEqual(self.io.save(target, b''), publisher.pin(b''))
        self.assertEqual(target.read_bytes(), b'')
        self.assertEqual(mode(target), 0o444)
        self.assertEqual(self.io.write, 0)

    def test_failed_partial_write_retains_unpublished_owned_file(self):
        target = self.root / 'partial'
        real_write = os.write
        calls = 0

        def fail_after_prefix(fd, view):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, view[:3])
            raise OSError('generated write failure')

        with patch.object(publisher.os, 'write', side_effect=fail_after_prefix), \
             patch.object(publisher.os, 'fchmod') as change_mode:
            with self.assertRaisesRegex(OSError, 'generated write failure'):
                self.io.save(target, b'partial generated body')
            change_mode.assert_not_called()
        self.assertEqual(target.read_bytes(), b'par')
        self.assertEqual(mode(target), 0o400)
        self.assertEqual(mode(self.root), 0o700)

    def test_zero_write_is_refused_before_public_mode(self):
        target = self.root / 'zero-write'
        with patch.object(publisher.os, 'write', return_value=0), \
             patch.object(publisher.os, 'fchmod') as change_mode:
            with self.assertRaisesRegex(ValueError, 'full observer write'):
                self.io.save(target, b'generated')
            change_mode.assert_not_called()
        self.assertEqual(target.read_bytes(), b'')
        self.assertEqual(mode(target), 0o400)

    def test_mode_failure_is_not_a_successful_publication(self):
        target = self.root / 'mode-failure'
        with patch.object(publisher.os, 'fchmod', side_effect=OSError('generated mode failure')):
            with self.assertRaisesRegex(OSError, 'generated mode failure'):
                self.io.save(target, b'complete generated body')
        self.assertEqual(target.read_bytes(), b'complete generated body')
        self.assertEqual(mode(target), 0o400)

    def test_exclusive_and_symlink_guards_preserve_existing_objects(self):
        existing = self.root / 'existing'
        existing.write_bytes(b'private original')
        with self.assertRaises(FileExistsError):
            self.io.save(existing, b'replacement')
        link = self.root / 'link'
        link.symlink_to(existing)
        with self.assertRaisesRegex(ValueError, 'ordinary exclusive path'):
            self.io.save(link, b'replacement')
        parent_link = self.root / 'linked-parent'
        parent_link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary exclusive path'):
            self.io.save(parent_link / 'new', b'replacement')
        self.assertEqual(existing.read_bytes(), b'private original')
        self.assertEqual(mode(existing), 0o600)
        self.assertFalse((self.root / 'new').exists())

    def test_deadline_and_write_budget_refuse_before_creation(self):
        self.io.write = publisher.WRITE_CAP
        with self.assertRaisesRegex(ValueError, 'observer cumulative write cap'):
            self.io.save(self.root / 'over-budget', b'x')
        self.assertFalse((self.root / 'over-budget').exists())
        expired = publisher.IO(time.monotonic() - 1)
        with self.assertRaisesRegex(ValueError, 'original whole observer deadline'):
            expired.save(self.root / 'expired', b'x')
        self.assertFalse((self.root / 'expired').exists())

    def test_frozen_sources_reject_corruption_before_publication(self):
        source, manifest, bodies, raw = self.fixture()
        (source / 'engine/holder.py').write_bytes(b'tampered generated fixture')
        destination = self.root / 'snapshot'
        with self.assertRaises(ValueError):
            publisher.frozen_sources(source, destination, publisher.pin(raw), self.io)
        self.assertFalse(destination.exists())

    def test_frozen_sources_preserve_existing_destination(self):
        source, manifest, bodies, raw = self.fixture()
        destination = self.root / 'snapshot'
        destination.mkdir(mode=0o700)
        marker = destination / 'private-marker'
        marker.write_bytes(b'original')
        with self.assertRaisesRegex(ValueError, 'fresh exclusive source snapshot'):
            publisher.frozen_sources(source, destination, publisher.pin(raw), self.io)
        self.assertEqual(marker.read_bytes(), b'original')
        self.assertEqual(mode(marker), 0o600)
        self.assertEqual(mode(destination), 0o700)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publisher', type=Path,
                        default=Path(__file__).with_name('run_public_modes_v2.py'))
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    ARTIFACTS = args.artifacts.absolute()
    ARTIFACTS.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('_alpha_public_mode_publisher', args.publisher)
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PublicModeControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

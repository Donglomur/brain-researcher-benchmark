"""Independent generated input boundaries; combined entry supplies the fixture.

No authentic input is opened. The entry pins and preloads test_input_adapter as
input_test_bundle. These two groups do not repeat its complete-load/read-fault
checks. Only fictional low-level file operations replace the frozen Reader's OS.
"""
import sys
import types
import unittest
from unittest.mock import patch


bundle = sys.modules['input_test_bundle']
api = bundle.module


class IndependentInputBoundaries(unittest.TestCase):
    def assert_terminal(self, fixture, loader):
        before = list(fixture.fs.opens)
        report = loader.report()
        self.assertTrue(report['closed'] and report['failed'])
        self.assertFalse(report['completed'] or report['reader_cleanup_confirmed'])
        self.assertFalse(report['array_payloads_opened'] or report['participant_or_provider_invoked'])
        with self.assertRaises(api.InputRefusal):
            loader.load()
        with self.assertRaises(api.InputRefusal):
            loader._read('cohort')
        self.assertEqual(fixture.fs.opens, before)

    def test_coherent_member_substitution_and_open_descriptor_link_refusal(self):
        # Even the final member's coherently authenticated wrong path must be
        # refused before the first member open, not after a partial population.
        for changed in ('all_paths', 'index_extent'):
            with self.subTest(changed=changed):
                f = bundle.Fixture()
                references = (f.cohort['native_member_bindings'][-1]['receipt'],
                              f.numeric['complete_member_receipts'][-1]['receipt'],
                              f.index['recordings'][-1]['native_receipt'])
                if changed == 'all_paths':
                    for reference in references:
                        reference['path'] = str(f.signal_root/'recording-170.success.json')
                else:
                    references[-1]['bytes'] += 1
                f.rebuild()  # All enclosing body hashes now match the mutation.
                loader = f.loader()
                with f.fs.active():
                    with self.assertRaises(api.InputRefusal):
                        loader.load()
                    self.assert_terminal(f, loader)
                self.assertEqual(set(f.fs.opens), {str(p) for p in f.paths.values()})
                self.assertEqual(len(f.fs.opens), 9)
                self.assertFalse(f.fs.fds)
                self.assertEqual(loader.report()['metadata_reads']['unknown_grant_upper_bound'], 0)

        # The pre-open path stat is admissible, but the opened descriptor has
        # more than one link. Body hashing alone must not admit this descriptor.
        f = bundle.Fixture()
        loader = f.loader()
        real_fstat = f.fs.fstat
        def linked_descriptor(fd):
            observed = real_fstat(fd)
            return types.SimpleNamespace(**{**vars(observed), 'st_nlink': 2})
        with patch.object(f.fs, 'fstat', linked_descriptor), f.fs.active():
            with self.assertRaises(api.InputRefusal):
                loader.load()
            self.assert_terminal(f, loader)
        self.assertEqual(f.fs.opens, [str(f.paths['cohort'])])
        self.assertEqual(f.fs.closes, [str(f.paths['cohort'])])
        self.assertFalse(f.fs.fds)
        self.assertEqual(loader.report()['metadata_reads']['known'], 0)

    def test_finish_and_close_failures_are_terminal_and_preserve_interruption(self):
        for kind in ('finish', 'close', 'interrupted_finish_and_close'):
            with self.subTest(kind=kind):
                f = bundle.Fixture()
                loader = f.loader()
                reader = loader.io.Reader
                original_finish, original_close = reader.finish, reader.close
                primary = KeyboardInterrupt('generated finish interruption') if kind.startswith('interrupted') else \
                    ValueError('generated finish refusal')
                cleanup = OSError('generated close uncertainty after effect')
                finish_calls, close_calls = [], []
                def finishing(stream):
                    finish_calls.append(stream.fd)
                    result = original_finish(stream)
                    if kind != 'close':
                        raise primary
                    return result
                def closing(stream):
                    close_calls.append(stream.fd)
                    original_close(stream)
                    if kind != 'finish':
                        raise cleanup
                expected = cleanup if kind == 'close' else primary
                with f.fs.active(), patch.object(reader, 'finish', finishing), patch.object(reader, 'close', closing):
                    with self.assertRaises(type(expected)) as caught:
                        loader.load()
                    self.assertIs(caught.exception, expected)
                    self.assert_terminal(f, loader)
                self.assertEqual(len(finish_calls), 1)
                self.assertEqual(len(close_calls), 1)
                self.assertEqual(f.fs.opens, [str(f.paths['cohort'])])
                self.assertEqual(f.fs.closes, [str(f.paths['cohort'])])
                self.assertFalse(f.fs.fds)
                report = loader.report()
                self.assertEqual(report['completed_files'], 0)
                self.assertEqual(report['reader_close_failures'], int(kind != 'finish'))
                self.assertFalse(report['reader_construction_uncertain'])
                self.assertEqual(report['metadata_reads']['known'], len(f.fs.files[str(f.paths['cohort'])][0]))
                self.assertEqual(report['metadata_reads']['charged'], report['metadata_reads']['known'])
                self.assertEqual(report['metadata_reads']['unknown_grant_upper_bound'], 0)


if __name__ == '__main__':
    unittest.main()

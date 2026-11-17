"""Generated path checks keep reconstruction outputs away from source/provenance."""
import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'construction_paths', ROOT / 'scripts/maintenance/_construction.py')
construction = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(construction)


class ConstructionPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.source = self.base / 'original-inputs'
        self.source.mkdir()
        self.output = self.base / 'staging'
        self.parser = argparse.ArgumentParser()
        construction.arguments(self.parser)

    def paths(self, source=None, output=None):
        args = argparse.Namespace(
            construction_root=str(self.source if source is None else source),
            output_directory=str(self.output if output is None else output))
        return construction.paths(args, self.parser)

    def refused(self, source=None, output=None):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            self.paths(source, output)
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_separate_staging_path_accepted_without_creating_it(self):
        self.assertEqual(self.paths(), (self.source, self.output))
        self.assertFalse(self.output.exists())

    def test_missing_explicit_arguments_refused(self):
        for source, output in ((None, str(self.output)), (str(self.source), None)):
            args = argparse.Namespace(construction_root=source, output_directory=output)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                construction.paths(args, self.parser)
            self.assertEqual(caught.exception.code, 2)

    def test_public_source_and_public_ancestor_refused(self):
        for source in (ROOT, ROOT.parent, ROOT / 'docs'):
            self.refused(source=source)

    def test_output_cannot_replace_public_source_or_provenance(self):
        for output in (ROOT, ROOT.parent, ROOT / 'docs/provenance/new'):
            self.refused(output=output)

    def test_output_cannot_overlap_construction_inputs(self):
        for output in (self.source, self.source / 'derived', self.source.parent):
            self.refused(output=output)

    def test_missing_source_and_file_output_refused(self):
        self.refused(source=self.base / 'missing')
        file = self.base / 'existing-file'
        file.write_text('preserved')
        self.refused(output=file)
        self.assertEqual(file.read_text(), 'preserved')

    def test_symlink_and_traversal_refused(self):
        linked = self.base / 'linked'
        linked.symlink_to(self.source, target_is_directory=True)
        self.refused(source=linked)
        self.refused(output=linked / 'derived')
        self.refused(output=self.base / 'missing' / '..' / 'staging')

    def test_generator_pin_names_current_public_repository(self):
        pin = construction.generator(ROOT / 'scripts/maintenance/_construction.py')
        self.assertEqual(pin['path'], 'scripts/maintenance/_construction.py')
        self.assertEqual(pin['scope'], 'current_public_repository')
        self.assertEqual(len(pin['sha256']), 64)
        self.assertGreater(pin['bytes'], 0)


if __name__ == '__main__':
    unittest.main()

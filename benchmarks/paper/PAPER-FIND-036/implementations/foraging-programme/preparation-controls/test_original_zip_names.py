"""Focused original-name controls; generated metadata, never MAT contents.

Run this file in its own Python process. The partial private projection exercises
actual prepare/common imports and manifest descriptors, not a complete runtime
admission. Both inventories retain all40 nominal members under one root.
"""
from pathlib import Path
import hashlib
import importlib
import io
import json
import stat
import sys
import traceback
import unittest
import zipfile

PROGRAM = Path(__file__).resolve().parents[1] / 'program'
sys.path.insert(0, str(PROGRAM))
common = importlib.import_module('common')
prepare = importlib.import_module('prepare')


def generated_members(nul_suffix=False):
    members = []
    for index in range(40):
        name = f'classification/#generated-{index:02d}_PL_eventClassificationData.mat'
        if nul_suffix and index == 0:
            name += '\x00hidden-suffix'
        info = zipfile.ZipInfo(name)
        info.file_size = 1
        info.compress_size = 1
        info.compress_type = zipfile.ZIP_STORED
        info.CRC = 0
        info.external_attr = (stat.S_IFREG | 0o600) << 16
        members.append(info)
    return members


class OriginalZIPNameControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Necessary consumer closure: the selected manifest actually binds the
        # changed preparer and its unchanged imported dependency. Every other
        # descriptor is preserved by the guarded construction map, not loaded
        # or qualified as a full scientific runtime by these focused controls.
        manifest = json.loads((PROGRAM / 'SOURCE_MANIFEST.json').read_text())
        if manifest['schema'] != 'foraging_program_source_v1' or manifest['task_id'] != 'PAPER-FIND-036':
            raise AssertionError('Expected task-local source manifest')
        for name, module in [('prepare.py', prepare), ('common.py', common)]:
            path = PROGRAM / name
            if Path(module.__file__).resolve() != path.resolve():
                raise AssertionError('Run focused controls in their own interpreter')
            raw = path.read_bytes()
            actual = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            if manifest['files'][name] != actual:
                raise AssertionError(f'Actual source manifest descriptor mismatch: {name}')
        cls.caps = {'archive_entries': 40, 'expanded_bytes': 40, 'member_bytes': 1}

    def test_malformed_original_nul_name_is_rejected_before_classification(self):
        infos = generated_members(nul_suffix=True)
        raw_name = infos[0].orig_filename
        self.assertIn('\x00', raw_name)
        self.assertEqual(infos[0].filename, raw_name.split('\x00', 1)[0])
        self.assertNotEqual(infos[0].filename, raw_name)
        # Without orig_filename the hidden suffix disappears and the prefix
        # looks like a valid member of the otherwise complete40 inventory.
        self.assertIsNotNone(prepare.SESSION.fullmatch(Path(infos[0].filename).name))
        self.assertEqual(len(infos), 40)
        with self.assertRaisesRegex(ValueError, '^safe unique exact member path$'):
            prepare.inspect_inventory(infos, self.caps)

    def test_ordinary_full40_members_keep_exact_names_tokens_and_root(self):
        infos = generated_members()
        expected_names = [info.orig_filename for info in infos]
        selected, inventory, root = prepare.inspect_inventory(infos, self.caps)
        self.assertEqual(root, 'classification')
        self.assertEqual(len(selected), 40)
        self.assertEqual([info for info, _ in selected], infos)
        self.assertEqual([token for _, token in selected],
                         [f'#generated-{index:02d}_PL' for index in range(40)])
        self.assertEqual([row['name'] for row in inventory], expected_names)
        self.assertEqual(len(set(expected_names)), 40)
        self.assertTrue(all(info.orig_filename == info.filename for info in infos))
        self.assertTrue(all(row['disposition'] == 'full_original_classification_MAT'
                            and row['bytes'] == row['compressed_bytes'] == 1
                            for row in inventory))


if __name__ == '__main__':
    output = io.StringIO()
    success = False
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(OriginalZIPNameControls)
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        success = result.wasSuccessful()
    except BaseException:
        traceback.print_exc(file=output)
    # One shared-pool attempt, with a hard16KiB emitted result/log ceiling.
    sys.stdout.write(output.getvalue()[:16384])
    raise SystemExit(0 if success else 1)

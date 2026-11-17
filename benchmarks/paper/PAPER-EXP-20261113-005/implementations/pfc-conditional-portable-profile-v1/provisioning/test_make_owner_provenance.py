"""Metadata-only compatibility controls; no scientific asset is opened."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_packet_release as audit
import make_owner_provenance as materializer


class OwnerMetadataTests(unittest.TestCase):
    def test_complete_identities_no_original_paths_or_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            pin = materializer.materialize(root / 'owner.json', root / 'identity-labels')
            value = json.loads((root / 'owner.json').read_text())
            self.assertEqual(set(value['inputs']), materializer.ROLES)
            self.assertEqual(sum(p['bytes'] for p in value['inputs'].values()), 22183624)
            self.assertTrue(all(not Path(p['path']).exists() for p in value['inputs'].values()))
            self.assertEqual({k: {x: v[x] for x in ('bytes', 'sha256')} for k, v in value['inputs'].items()},
                             materializer.load_lineage()['prepared_inputs'])
            self.assertEqual(pin['sha256'], hashlib.sha256((root / 'owner.json').read_bytes()).hexdigest())
            self.assertFalse(value['execution_authority'])
            self.assertFalse(value['input_file_presence_claimed'])

    def test_existing_output_remains_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); p = root / 'owner.json'; p.write_bytes(b'existing')
            with self.assertRaises(audit.Refusal):
                materializer.materialize(p, root / 'labels')
            self.assertEqual(p.read_bytes(), b'existing')

    def test_symlink_or_relative_locator_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); link = root / 'link'; link.symlink_to(root)
            for loc in (link / 'labels', Path('relative/labels')):
                with self.subTest(loc=loc), self.assertRaises(audit.Refusal):
                    materializer.materialize(root / 'owner.json', loc)
            self.assertFalse((root / 'owner.json').exists())

    def test_changed_public_manifest_refused_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(materializer, 'LINEAGE_SHA256', '0' * 64), self.assertRaises(audit.Refusal):
                materializer.materialize(root / 'owner.json', root / 'labels')
            self.assertFalse((root / 'owner.json').exists())

    def test_public_metadata_has_no_original_absolute_paths(self):
        body = json.dumps(materializer.load_lineage(), sort_keys=True)
        self.assertNotIn('/Users/', body)
        self.assertNotIn('/private/', body)
        self.assertNotIn('selected_for_execution', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)

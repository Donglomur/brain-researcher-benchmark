"""Invented metadata controls only; no candidate, Docker, model or authentic operand."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import setup

PACKAGE = Path(__file__).absolute().parent


class SetupControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bodies = setup.verify_engine(PACKAGE)
        cls.assets = setup.decode(cls.bodies['engine/ASSET_MANIFEST.template.json'])
        cls.owner = setup.decode(cls.bodies['engine/FULL120_OWNER.template.json'])
        cls.template = setup.decode(setup.read_metadata(PACKAGE / 'LOCATIONS.template.json'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['NIDER_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = copy.deepcopy(self.template)
        self.config['assets'] = {k: str(self.root / 'unopened-assets' / k)
                                 for k in self.config['assets']}
        self.config['full120_reference'] = str(self.root / 'unopened-reference')
        for key in ('delivery_basis', 'python', 'runtime_policy'):
            self.config[key] = {'path': str(self.root / ('unopened-' + key)),
                                'bytes': 1, 'sha256': '1' * 64}

    def build(self, config=None, output=None):
        return setup.plans(config or self.config, PACKAGE, output or self.root / 'setup',
                           self.assets, self.owner)[0]

    def test_24_slots_without_opening_any_external_operand(self):
        result = self.build()
        manifest = setup.decode(result['ASSET_MANIFEST.json'])
        self.assertEqual(len(manifest['assets']), 24)
        self.assertTrue(all(not Path(p).exists() for p in self.config['assets'].values()))
        for name, supplied in manifest['assets'].items():
            if name != 'delivery_basis':
                self.assertEqual(supplied['sha256'], self.assets['assets'][name]['sha256'])
                self.assertEqual(supplied['bytes'], self.assets['assets'][name]['bytes'])
        self.assertEqual(sum(k.startswith('doc_') for k in manifest['assets']), 6)

    def test_matched_arms_preserve_policy_and_fixed_reference(self):
        result = self.build()
        a, b = [setup.decode(result['PREPARE_' + arm + '.json']) for arm in ('A', 'B')]
        self.assertEqual(a['arm'], 'A'); self.assertEqual(b['arm'], 'B')
        self.assertNotEqual(a['output_root'], b['output_root'])
        for field in set(a) - {'arm', 'output_root'}:
            self.assertEqual(a[field], b[field])
        owner = setup.decode(result['FULL120_OWNER.json'])
        self.assertEqual(owner['maximum_attempts'], 1)
        self.assertEqual(owner['reference']['sha256'], self.owner['reference']['sha256'])
        self.assertEqual(owner['reference']['bytes'], self.owner['reference']['bytes'])

    def test_deterministic_metadata(self):
        self.assertEqual(self.build(), self.build())

    def test_missing_and_extra_asset_slots_refused(self):
        for mode in ('missing', 'extra'):
            c = copy.deepcopy(self.config)
            if mode == 'missing': del c['assets']['workbook_0']
            else: c['assets']['extra'] = str(self.root / 'extra')
            with self.assertRaisesRegex(ValueError, 'exactly_17'): self.build(c)

    def test_aliases_and_duplicate_paths_refused(self):
        c = copy.deepcopy(self.config); c['assets']['workbook_1'] = c['assets']['workbook_0']
        with self.assertRaisesRegex(ValueError, 'duplicate_operand'): self.build(c)
        for value in ('relative/file', '/operator/../secret', '//operator/secret', '/operator//secret'):
            with self.assertRaises(ValueError): setup.plain(value)

    def test_symlink_operand_refused_without_target_read(self):
        link = self.root / 'alias'; link.symlink_to(self.root / 'absent-target')
        self.config['assets']['workbook_0'] = str(link)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.build()

    def test_invalid_pins_refused(self):
        for key in ('delivery_basis', 'python', 'runtime_policy'):
            for field, value in [('bytes', True), ('bytes', 0), ('bytes', 8388609),
                                 ('sha256', 'not-a-digest')]:
                c = copy.deepcopy(self.config); c[key][field] = value
                with self.assertRaises(ValueError): self.build(c)

    def test_no_network_model_or_budget_expansion(self):
        for field, value in [('network', 'public'), ('model_execution', True),
                             ('wall_seconds', 3601), ('command_seconds', 31),
                             ('command_limit', True), ('tools', ['exec', 'submit', 'score'])]:
            c = copy.deepcopy(self.config); c['policy'][field] = value
            with self.assertRaises(ValueError): self.build(c)

    def test_source_and_operand_output_overlap_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside_source'): self.build(output=PACKAGE / 'generated')
        self.config['assets']['workbook_0'] = str(self.root / 'setup' / 'asset')
        with self.assertRaisesRegex(ValueError, 'operand_inside'): self.build()

    def test_duplicate_keys_and_nonfinite_json_refused(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError): setup.decode(raw)

    def test_changed_engine_manifest_refused(self):
        (self.root / 'ENGINE_MANIFEST.json').write_bytes(b'{}\n')
        with self.assertRaisesRegex(ValueError, 'engine_manifest_identity'):
            setup.verify_engine(self.root)

    def test_followup_requires_exact_operand_identity_and_schema(self):
        operand = self.root / 'OWNER_SESSION.json'
        raw = setup.encoded({'schema': 'nider_owner_package_session_v1', 'invented': True})
        operand.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'operand_identity'):
            setup.followup('prepare_assessment', operand, '0' * 64, self.root / 'bad.json')
        with self.assertRaisesRegex(ValueError, 'operand_schema'):
            setup.followup('summarize', operand, hashlib.sha256(raw).hexdigest(), self.root / 'bad.json')
        result = setup.followup('prepare_assessment', operand, hashlib.sha256(raw).hexdigest(), self.root / 'request.json')
        request = json.loads((self.root / 'request.json').read_bytes())
        self.assertEqual(request['session']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertFalse(result['execution_selected'])

    def test_bind_is_private_append_only_and_not_admission(self):
        output = self.root / 'setup'
        result = setup.bind(self.config, PACKAGE, output)
        self.assertFalse(result['execution_selected'])
        self.assertFalse(result['runtime_admitted'])
        self.assertFalse(result['authentic_operands_read'])
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        self.assertEqual(len(list(output.iterdir())), 5)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in output.iterdir()))
        original = (output / 'SETUP_RESULT.json').read_bytes()
        with self.assertRaises(FileExistsError): setup.bind(self.config, PACKAGE, output)
        self.assertEqual((output / 'SETUP_RESULT.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Three source/metadata composition controls; no scientific or Docker imports."""
import ast
import hashlib
from pathlib import Path
import tempfile
import unittest
import setup

PACKAGE = Path(__file__).absolute().parent
V3 = {
    'engine/configuration/LOCK.json': '9dd42262933e9436b1a2cb64ff9cb4702720757de166487a6a34fe9aa68624eb',
    'engine/configuration/configuration.py': '9f782ef7c4ee4053d7830ab9e8c8c490813605aed7b1f08993f18832ad98788c',
    'engine/owner/PACKAGE_LOCK.json': '452ad0877ba5fc64af08a7193d7af7464d4211b7ceed528a5d175cbb58852e94',
    'engine/owner/admit_runtime.py': 'a885d7feeef4be135e7562b9f542afa2e48ff95464e09139451661418bfd37d4',
    'engine/owner/owner_package.py': '31b9f9b0a75a01f42786170fbb21f047e82ec2eec78962f0b8fd6c766068e1d1',
    'engine/runtime/runtime_policy.py': '1c37d4dbda744fbaa9e7a9f5acd8e52df097469ec5187d5d564f65583c4cd00a',
}


class ProjectionControls(unittest.TestCase):
    def test_all_32_members_and_frozen_v3_successor(self):
        bodies = setup.verify_engine(PACKAGE)
        self.assertEqual(len(bodies), 32)
        for name, digest in V3.items():
            self.assertEqual(hashlib.sha256(bodies[name]).hexdigest(), digest)

    def test_private_home_guard_is_stricter_without_username(self):
        text = (PACKAGE / 'engine/runtime/runtime_policy.py').read_text()
        tuples = [tuple(item.value for item in node.elts)
                  for node in ast.walk(ast.parse(text))
                  if isinstance(node, ast.Tuple) and
                  all(isinstance(item, ast.Constant) for item in node.elts)]
        self.assertIn(('/Users/', 'neuroscience-benchmark-data', 'REFERENCE_VALUES.json',
                       'ISSUER_KEY.bin', 'official_source.R', 'article.pdf'), tuples)
        self.assertIn('runtime_no_private_config_history', text)

    def test_v3_request_routes_preserve_24_slots_and_private_reference(self):
        bodies = setup.verify_engine(PACKAGE)
        assets = setup.decode(bodies['engine/ASSET_MANIFEST.template.json'])
        owner = setup.decode(bodies['engine/FULL120_OWNER.template.json'])
        config = setup.decode((PACKAGE / 'LOCATIONS.template.json').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config['assets'] = {k: str(root / ('unopened-' + k)) for k in config['assets']}
            config['full120_reference'] = str(root / 'unopened-full-reference')
            for key in ('delivery_basis', 'python', 'runtime_policy'):
                config[key] = {'path': str(root / ('unopened-' + key)), 'bytes': 1, 'sha256': '1' * 64}
            products, _ = setup.plans(config, PACKAGE, root / 'new-output', assets, owner)
            generated = setup.decode(products['ASSET_MANIFEST.json'])
            self.assertEqual(len(generated['assets']), 24)
            self.assertEqual(sum(k.startswith('doc_') for k in generated['assets']), 6)
            for name, pin in generated['assets'].items():
                if name != 'delivery_basis':
                    self.assertEqual((pin['bytes'], pin['sha256']), (assets['assets'][name]['bytes'], assets['assets'][name]['sha256']))
            for arm in ('A', 'B'):
                request = setup.decode(products['PREPARE_' + arm + '.json'])
                self.assertEqual(request['source_anchor'], str(PACKAGE / 'engine/runtime'))
                self.assertEqual(request['configuration_anchor'], str(PACKAGE / 'engine/configuration'))
            output_owner = setup.decode(products['FULL120_OWNER.json'])
            self.assertEqual(output_owner['reference']['sha256'], owner['reference']['sha256'])
            self.assertEqual(output_owner['maximum_attempts'], 1)
            self.assertEqual(list(root.iterdir()), [])

if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Portable new transport controls; protocol-only is never OS qualification."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import generated_fixtures as F
M, C, T = F.M, F.C, F.T


class PortableModalityTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        F.CAP = 320 * 1024
        cls.root = Path(tempfile.mkdtemp(prefix='neural034-modality-protocol-', dir=os.environ.get('NEURAL034_CONTROL_TMP'))).resolve()
        cls.guard = F.guarded_writes(cls.root); cls.guard.__enter__()
        cls.addClassCleanup(cls.guard.__exit__, None, None, None)
        cls.deps = F.generated(); cls.deps.__enter__()
        cls.addClassCleanup(cls.deps.__exit__, None, None, None)
        cls.client = cls.root / 'client.py'; cls.client.write_text(F.CLIENT)
        cls.packet = F.Packet(0, 'behavior_only_v1')
        cls.output = cls.root / 'diagnostic'
        cls.result = M.run_fold(cls.packet, cls.output, cls.client, condition='behavior_only_v1',
                               python=sys.executable, sandbox='protocol_only', limits=F.limits())
        if cls.result['status'] != 'complete_unscored':
            raise AssertionError(cls.result)

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'fixture_root': str(cls.root), 'known_fixture_bytes_written': F.WRITTEN,
                          'cap_bytes': F.CAP, 'generated_render_calls_including_audits': F.RENDER_CALLS,
                          'actual_sandbox_tests': 0, 'sandbox_simulated': False,
                          'authentic_reads': 0, 'scientific_scores': 0}))

    def test_complete_protocol_diagnostic_is_explicit(self):
        receipt = M.audit_transport(self.output, self.packet, 'behavior_only_v1')
        self.assertEqual(receipt['boundary']['sandbox'], 'protocol_only')
        self.assertFalse(receipt['boundary']['provider_context_qualified'])
        self.assertEqual(set(receipt['answers']), set(C.IDS[0]))
        self.assertEqual(self.result['images'], 140)

    def test_condition_unknown_and_cross_condition_binding_refused(self):
        for condition in ('unknown', 'calcium_only_v1', 'combined_calcium_behavior_v1'):
            with self.assertRaises(ValueError):
                M.audit_transport(self.output, self.packet, condition)

    def test_protocol_only_boundary_cannot_enter_restricted_collection(self):
        paths = []
        for fold in range(7):
            path = self.root / f'metadata-{fold}'; path.mkdir()
            boundary = F.decode(self.output / 'BOUNDARY.json')
            boundary['fold'] = fold
            boundary['episode_id'] = f'{fold + 1:032x}'
            (path / 'BOUNDARY.json').write_bytes(T.encode(boundary)); paths.append(path)
        with self.assertRaisesRegex(ValueError, '(?i)(restricted|protocol|sandbox)'):
            M.collect('behavior_only_v1', [F.Packet(fold, 'behavior_only_v1') for fold in range(7)], paths, self.root / 'refused')
        self.assertFalse((self.root / 'refused' / 'TRANSPORT_COMPLETE.json').exists())

    def test_original_framing_carries_condition_and_exact_png_bytes(self):
        session = C.Session(self.packet, C.Selection('behavior_only_v1', F.limits()), 'f' * 32)
        response = session.handle({'action': 'query', 'index': 19})
        header, image = C.projection(response, 'behavior_only_v1')
        self.assertEqual(T.unpack(T.wire(header, image)), (header, F.PNG))
        self.assertEqual(header['condition'], 'behavior_only_v1')
        self.assertEqual(header['cells'], 0)
        self.assertEqual(header['clipped_cells'], [])
        with self.assertRaises(ValueError):
            C.projection(dict(response, context_label=1), 'behavior_only_v1')


if __name__ == '__main__':
    unittest.main()

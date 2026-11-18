"""Focused generated boundary controls; custody transports are explicit stubs.

The actual original NPZ validator, score arithmetic, and adapter are exercised.
Separate owner controls cover the new owner. No authentic packet is opened.
"""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_tested_cross_mode', HERE / 'cross_mode.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['NEURAL095_IMPLEMENTATIONS'])
        cls.actual = c.module(cls.root / 'participant-transport-v1/transport.py', '_fixture_actual_transport')
        cls.sources = cls.actual.v.Sources()
        cls.temp = tempfile.TemporaryDirectory(prefix='cross-mode-generated-', dir=HERE)
        cls.folder = Path(cls.temp.name)
        cls.ids = ['dmfc-%06d' % (1000 + i) for i in range(258)]
        cls.condition = np.arange(258, dtype=np.int64) % 40
        cls.context = cls.condition // 5
        cls.paths, cls.bodies = {}, {}
        for view, values in (('cue_only', [-1.] * 258), ('neural', [800. + i for i in range(258)])):
            # Intentionally permute programme NPZ rows: the original ABI allows
            # this and aligns by IDs; declared roster order must still match.
            body = cls.actual.v.submission(list(reversed(cls.ids)), list(reversed(values)))
            cls.paths[view] = cls.folder / (view + '.npz'); cls.paths[view].write_bytes(body)
            cls.bodies[view] = body
        body = cls.actual.v.submission(cls.ids[:-1], [800.] * 257)
        cls.short_path = cls.folder / 'missing.npz'; cls.short_path.write_bytes(body); cls.short_body = body
        cls.fixture_bytes_written = sum(map(len, cls.bodies.values())) + len(body)

    @classmethod
    def tearDownClass(cls):
        print('GENERATED_FIXTURE_BYTES_WRITTEN=' + str(cls.fixture_bytes_written))
        cls.temp.cleanup()

    def setUp(self):
        self.events = []
        self.inputs = {view: {name: c.pin((view + ':' + name).encode()) for name in self.actual.v.FILES}
                       for view in c.VIEWS}
        for view in c.VIEWS:
            for name in ('units.json', 'contract.json'):
                self.inputs[view][name] = c.pin(name.encode())
        self.packets = {view: SimpleNamespace(view=view, ids=self.ids.copy(), pins=self.inputs[view],
            common={'train': {'all_common': 'a' * 64}, 'query': {'all_common': 'b' * 64}},
            units=tuple(range(40)), sources=self.sources,
            arrays={'query': {'condition': self.condition.copy(), 'context': self.context.copy()}})
            for view in c.VIEWS}
        boundary = {'client': c.pin(b'generated client'), 'limits': {'max_actions': 2000},
            'sandbox': 'protocol_only', 'source': {'transport.py': c.pin(b'generated boundary')},
            'fresh_process_per_view': True, 'stateful_within_view': True}
        self.viewer_receipts = {view: {'boundary': copy.deepcopy(boundary), 'result': {'status': 'complete_unscored'}}
                                for view in c.VIEWS}
        self.viewer_vectors = {view: np.full(258, 810. if view == 'cue_only' else 805.) for view in c.VIEWS}
        self.viewer_receipt = {'submissions': {view: c.pin(self.actual.v.submission(self.ids, self.viewer_vectors[view]))
                                              for view in c.VIEWS}}
        self.programme = {'mode': c.PROGRAMME_MODE, 'status': 'closed_ungraded', 'case_ids': self.ids.copy(),
            'public_inputs': {view: [{'path': 'data/' + view + '/' + name, **self.inputs[view][name],
                'mount_destination': '/input/' + name, 'read_only': True} for name in self.actual.v.FILES]
                for view in c.VIEWS},
            'submissions': {view: {'body': body, 'pin': c.pin(body)} for view, body in self.bodies.items()},
            'submission_paths': self.paths.copy(),
            'program': c.pin(b'generated numerical program'), 'method_document': c.pin(b'generated method'),
            'actor': c.pin(b'original frozen actor'), 'policy': 'single_frozen_fit_batch/v1',
            'resource_policy': {'limits': {'wall_us': 900000000}, 'whole_seconds': 4800},
            'closure': {'generated_not_runtime_evidence': True}}
        self.fail_viewer = False; self.fail_programme = False
        def audit_pair(packets, sessions):
            self.events.append('closed_viewer')
            if self.fail_viewer:
                raise ValueError('Generated open/failed viewer producer')
            return self.viewer_receipts, {'cue_only': 'unused', 'neural': 'unused'}
        def validate_collection(packets, histories, collection):
            self.events.append('public_viewer')
            return self.viewer_vectors, self.viewer_receipt
        def validate_closed(root, selection):
            self.events.append('closed_programme')
            if self.fail_programme:
                raise ValueError('Generated open/failed programme producer')
            return self.programme
        original_validate = self.sources.modules['validator'].validate
        # Do not modify the shared source module across tests.
        validator = SimpleNamespace(MAX_FILE_BYTES=self.sources.modules['validator'].MAX_FILE_BYTES)
        def validate(path, ids):
            self.events.append('public_programme_' + Path(path).stem)
            return original_validate(path, ids)
        validator.validate = validate
        self.local_sources = SimpleNamespace(modules={**self.sources.modules, 'validator': validator})
        for packet in self.packets.values(): packet.sources = self.local_sources
        self.transport = SimpleNamespace(audit_pair=audit_pair, pin=c.pin, encode=self.actual.encode,
            decode=self.actual.decode, source_identity=lambda: {'fixture': True}, read=self.read)
        self.transport.v = SimpleNamespace(validate_collection=validate_collection, MODE=self.actual.v.MODE,
            MAX_HISTORY=self.actual.v.MAX_HISTORY, encoded=self.actual.v.encoded, pair_packets=self.actual.v.pair_packets)
        self.owner = SimpleNamespace(validate_closed=validate_closed)
        self.policy = c.actual_policy(self.transport, self.viewer_receipts, self.programme)
        self.private = {'case_id': np.array(self.ids), 'tp_ms': np.full(258, 800.),
                        'condition': self.condition.copy(), 'context': self.context.copy()}
        self.references = self.reference_fixture()

    def read(self, path, cap):
        if Path(path).name == 'TRANSPORT_COMPLETE.json':
            return self.actual.encode({'schema': 'neural095-participant-collection/v1',
                'status': 'both_closed_views_collected', 'mode': self.actual.v.MODE,
                'queries_per_view': 258, 'sessions': self.viewer_receipts,
                'original_collection': c.pin(self.actual.v.encoded(self.viewer_receipt)),
                'source': {'fixture': True}, 'provider_context_qualified': False, 'scientific_qualification': False})
        return self.actual.read(path, cap)

    def reference_fixture(self):
        row = {'n': 258, 'mae_ms': 10., 'rmse_ms': 10., 'eight_context_macro_mae_ms': 10.}
        for key, groups, size in (('by_condition', self.condition, 40), ('by_context', self.context, 8)):
            row[key] = {str(i): {'n': int(np.count_nonzero(groups == i)), 'mae_ms': 10.} for i in range(size)}
        return {'scores': {name: copy.deepcopy(row) for name in self.sources.modules['metrics'].METHODS}}

    def arguments(self):
        body = c.encoded(self.policy)
        return dict(transport=self.transport, owner=self.owner, packets=self.packets,
            sessions={}, collection=self.folder, programme_root=self.folder, programme_selection={},
            policy_body=body, policy_pin=c.pin(body))

    def grade(self):
        def reference(): self.events.append('references'); return self.references
        def private(): self.events.append('targets'); return self.private
        return c.evaluate(**self.arguments(), reference_loader=reference, private_loader=private)

    def refused_before_private(self):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.grade()
        self.assertNotIn('references', self.events); self.assertNotIn('targets', self.events)

    def test_all_four_admitted_before_grade_and_original_arithmetic(self):
        result = self.grade()
        self.assertEqual(self.events, ['closed_viewer', 'public_viewer', 'closed_programme',
            'public_programme_cue_only', 'public_programme_neural', 'references', 'targets'])
        self.assertEqual(result['arms']['frozen_program']['cue_only']['candidate']['mae_ms'], 801.)
        self.assertEqual(result['arms']['frozen_program']['neural']['candidate']['mae_ms'], 128.5)
        self.assertEqual(result['within_access_neural_increment']['frozen_program']['cue_minus_neural']['cue_minus_neural_mae_ms'], 672.5)
        self.assertEqual(result['descriptive_between_access_difference']['neural']['viewer_minus_frozen_program']['viewer_minus_frozen_program_mae_ms'], -123.5)
        self.assertNotIn('cue_minus_neural_mae_ms', result['descriptive_between_access_difference']['neural']['viewer_minus_frozen_program'])
        # Condition-specific checks detect reversed-ID alignment even though
        # the pooled mean of a permutation is unchanged.
        for condition in range(40):
            expected = sum(range(condition, 258, 40)) / len(range(condition, 258, 40))
            # Existing scalar MAE uses scaled summation; allow its final binary64
            # rounding only. This is not a scientific improvement threshold.
            self.assertAlmostEqual(result['arms']['frozen_program']['neural']['candidate']['by_condition'][str(condition)]['mae_ms'],
                                   expected, delta=2 * math.ulp(expected))
        self.assertEqual(result['cases_per_product'], 258)
        self.assertFalse(result['tools_only_causal_effect_claimed'])

    def test_changed_input_commitment_blocks_grade(self):
        self.programme['public_inputs']['neural'][0]['sha256'] = 'f' * 64
        self.refused_before_private()

    def test_reordered_declared_roster_blocks_grade(self):
        self.programme['case_ids'].reverse(); self.refused_before_private()

    def test_missing_last_programme_case_blocks_both_loaders(self):
        self.programme['submission_paths']['neural'] = self.short_path
        self.programme['submissions']['neural'] = {'body': self.short_body, 'pin': c.pin(self.short_body)}
        self.refused_before_private()

    def test_open_failed_producers_block_grade(self):
        for which in ('fail_viewer', 'fail_programme'):
            with self.subTest(which=which):
                self.events.clear(); setattr(self, which, True); self.refused_before_private(); setattr(self, which, False)

    def test_historical_scored_receipt_not_admitted(self):
        self.programme['status'] = 'complete_four_cell_operation'; self.refused_before_private()

    def test_viewer_is_not_adaptive_programme(self):
        self.policy['restricted_count_viewer']['condition'] = 'case_adaptive'; self.refused_before_private()

    def test_changed_method_or_client_policy_blocks_grade(self):
        for branch, field in (('frozen_program', 'method_document'), ('restricted_count_viewer', 'client'),
                              ('frozen_program', 'resource_policy')):
            with self.subTest(branch=branch):
                prior = self.policy[branch][field]; self.policy[branch][field] = c.pin(b'changed')
                self.refused_before_private(); self.policy[branch][field] = prior

    def test_nonfinite_viewer_product_blocks_grade(self):
        self.viewer_vectors['neural'][-1] = np.nan; self.refused_before_private()

    def test_private_order_or_cues_mismatch_refused(self):
        self.private['case_id'] = self.private['case_id'][::-1]
        with self.assertRaisesRegex(ValueError, 'identity order'): self.grade()
        self.private['case_id'] = np.array(self.ids)
        for name in ('condition', 'context'):
            with self.subTest(name=name):
                old = self.private[name][0]; self.private[name][0] += 1
                with self.assertRaisesRegex(ValueError, 'cue join'): self.grade()
                self.private[name][0] = old

    def test_input_roles_not_reordered_or_incomplete(self):
        self.programme['public_inputs']['neural'].reverse(); self.refused_before_private()

    def test_programme_captured_bytes_immutable(self):
        self.programme['submissions']['neural']['body'] += b'x'; self.refused_before_private()

    def test_viewer_common_cues_or_units_differ_refused(self):
        self.packets['neural'].units = tuple(range(1, 41)); self.refused_before_private()

    def test_captured_source_execution_does_not_reopen_changed_code(self):
        path = self.folder / 'generated-source.py'
        original, changed = b'answer = 23\n', b'answer = 99\n'
        path.write_bytes(original); type(self).fixture_bytes_written += len(original)
        captured = c.source_capture(path, c.pin(original))
        path.write_bytes(changed); type(self).fixture_bytes_written += len(changed)
        loaded = c.captured_module(path, '_generated_captured_code', captured)
        self.assertEqual(loaded.answer, 23)
        with self.assertRaisesRegex(ValueError, 'exact source dependency'):
            c.source_capture(path, c.pin(original))

    def test_source_descriptor_must_bind_complete_bytes(self):
        path = self.folder / 'generated-bounded-source.py'
        raw = b'answer = 41\n'; path.write_bytes(raw); type(self).fixture_bytes_written += len(raw)
        with self.assertRaisesRegex(ValueError, 'source size'):
            c.source_capture(path, {'bytes': len(raw) - 1, 'sha256': c.pin(raw)['sha256']})


class SourceControls(unittest.TestCase):
    def test_actual_captured_dependency_bootstrap(self):
        root = Path(os.environ['NEURAL095_IMPLEMENTATIONS'])
        selected = {name: c.pin((HERE / name).read_bytes())
                    for name in ('frozen_owner.py', 'frozen_collection.py')}
        transport, owner = c.dependencies(root, selected)
        self.assertEqual(transport.source_identity(), {
            name: {'bytes': c.DEPENDENCIES['participant-transport-v1/' + name][0],
                   'sha256': c.DEPENDENCIES['participant-transport-v1/' + name][1]}
            for name in ('transport.py', 'SOURCE_BINDINGS.json')})
        self.assertEqual(c.pin(owner.COLLECTION_SOURCE), selected['frozen_collection.py'])
        binding = json.loads((root / 'participant-transport-v1/SOURCE_BINDINGS.json').read_bytes())
        self.assertEqual(c.pin(transport.v.capture(root / 'count-viewer-v1/SOURCE.json', 65536)),
                         binding['members']['SOURCE.json'])

    def test_changed_selected_owner_pin_is_refused(self):
        root = Path(os.environ['NEURAL095_IMPLEMENTATIONS'])
        selected = {name: c.pin((HERE / name).read_bytes())
                    for name in ('frozen_owner.py', 'frozen_collection.py')}
        selected['frozen_owner.py']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'exact source dependency'):
            c.dependencies(root, selected)


class JoinedControls(unittest.TestCase):
    def test_real_generated_owner_closure_joins_original_public_validator_before_grade(self):
        """Actual new closure validator plus adapter, with native custody scripted.

The generated owner's metadata graph is in memory. Only its two complete NPZ
outputs are materialized for the unchanged public path validator. The viewer
custody boundary remains the explicit stub used by the separate adapter tests.
        """
        fixture = c.module(HERE / 'test_frozen_owner.py', '_joined_frozen_owner_fixture')
        fixture.Controls.setUpClass(); Controls.setUpClass()
        try:
            builder = fixture.Controls('test_11_complete_real_closed_validator_traversal_and_resource_policy')
            f = builder.closed_fixture()
            product = builder._validate_fixture(f)
            for view in c.VIEWS:
                fixture.write(Path(product['submission_paths'][view]), product['submissions'][view]['body'])
            case = Controls('test_all_four_admitted_before_grade_and_original_arithmetic'); case.setUp()
            case.programme = product
            for view in c.VIEWS:
                case.packets[view].ids = product['case_ids'].copy()
                case.packets[view].pins = c.public_inputs(product['public_inputs'][view])
            case.private['case_id'] = np.array(product['case_ids'])
            case.viewer_receipt['submissions'] = {
                view: c.pin(case.actual.v.submission(product['case_ids'], case.viewer_vectors[view])) for view in c.VIEWS}
            case.policy = c.actual_policy(case.transport, case.viewer_receipts, product)
            def validate(root, selected):
                self.assertEqual(root, f.root); self.assertEqual(selected, f.selected)
                case.events.append('closed_programme')
                return builder._validate_fixture(f)
            case.owner = SimpleNamespace(validate_closed=validate)
            arguments = case.arguments()
            arguments.update(programme_root=f.root, programme_selection=f.selected)
            def references(): case.events.append('references'); return case.references
            def private(): case.events.append('targets'); return case.private
            result = c.evaluate(**arguments, reference_loader=references, private_loader=private)
            self.assertEqual(result['cases_per_product'], 258)
            self.assertEqual(case.events[-2:], ['references', 'targets'])
            self.assertEqual(case.events.count('closed_programme'), 1)
            self.assertEqual(sum(x.startswith('public_programme_') for x in case.events), 2)
            self.assertFalse(result['same_resource_budget'])
            # A changed final opaque product still prevents BOTH protected
            # callbacks after the independent generated closure read succeeds.
            with Path(product['submission_paths']['neural']).open('ab') as out:
                fixture.WRITTEN += out.write(b'x')
            case.events.clear()
            with self.assertRaises(ValueError):
                c.evaluate(**arguments, reference_loader=references, private_loader=private)
            self.assertNotIn('references', case.events); self.assertNotIn('targets', case.events)
        finally:
            Controls.tearDownClass(); fixture.Controls.tearDownClass()


if __name__ == '__main__':
    unittest.main()

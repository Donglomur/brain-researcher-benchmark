"""Full original-census metadata controls; zero generated fixture file writes."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v = load('generated_reve_closed_views', HERE / 'views.py')
old_path = HERE.parent / 'opaque-submission-v1/tests/test_adapter.py'
assert hashlib.sha256(old_path.read_bytes()).hexdigest() == 'de716dd790fa9e6e9456e5e66dfd0ccf1a068813a17dde26fd7734095a1dbbcf'
old = load('generated_reve_view_predecessor_fixture', old_path)


def compile_document(document=None, panel_identity=None):
    document = old.DOCS[0] if document is None else document
    return v.compile_views(document, document['materials_identity'],
                           old.PANEL['panel_identity'] if panel_identity is None else panel_identity)


VIEWS = compile_document()


def seal(view):
    view.pop('view_identity', None)
    view['view_identity'] = v.identity(view)
    return view


def sizes(view):
    return {row['signal']: row['shape'][0] * 64 * 800 * 8 + 128 for row in view['records']}


def mounted(phase='development'):
    view = VIEWS[phase]
    return v.data_mount(view, '/generated-only/' + phase, sizes(view))


class ClosedViews(unittest.TestCase):
    def test_exact_complete_phase_counts_and_membership(self):
        dev, held = VIEWS['development'], VIEWS['test']
        self.assertEqual(dev['counts'], {'train': 6300, 'val': 1734})
        self.assertEqual(held['counts'], {'test': 1803})
        self.assertEqual((len(dev['records']), len(held['records'])), (534, 1803))
        self.assertEqual(sum(len(row['labels']) for row in dev['records']), 8034)
        self.assertEqual({row['participant'] for row in dev['records']}, set(range(1, 90)))
        self.assertEqual(len({row['event_ids'][0] for row in held['records']}), 1803)
        self.assertTrue(all(set(row) == v.TEST_FIELDS and row['shape'] == [1, 64, 800]
                            for row in held['records']))

    def test_data_views_identical_across_both_literal_access_conditions(self):
        paired = compile_document(old.DOCS[1])
        self.assertNotEqual(VIEWS['info']['materials_identity'], paired['info']['materials_identity'])
        for phase in ('development', 'test'):
            self.assertEqual(VIEWS[phase], paired[phase])
            self.assertEqual(v.pin_json(VIEWS[phase]), v.pin_json(paired[phase]))
            self.assertEqual(mounted(phase), v.data_mount(paired[phase], '/generated-only/' + phase, sizes(paired[phase])))

    def test_development_has_no_test_metadata_or_private_joins(self):
        body = v.a.canonical(VIEWS['development'])
        self.assertNotIn(b'trial-', body); self.assertNotIn(b'query-', body)
        for forbidden in ('condition', 'paper', 'official_code', 'data_identity', 'materials_identity',
                          'source_panel_identity', 'test_mapping_identity', 'test_ids', 'targets'):
            self.assertNotIn(forbidden, VIEWS['development'])
            self.assertNotIn(forbidden, VIEWS['test'])
        for row in VIEWS['test']['records']:
            self.assertTrue(set(row).isdisjoint({'participant', 'run', 'labels', 'source_event_id'}))

    def test_complete_document_is_detached_before_authentication(self):
        document = deepcopy(old.DOCS[0]); observed = []
        original = v.a.packet_info
        def check(snapshot, *args):
            self.assertIsNot(snapshot, document)
            self.assertIsNot(snapshot['data']['records'], document['data']['records'])
            observed.append(True)
            return original(snapshot, *args)
        with patch.object(v.a, 'packet_info', side_effect=check):
            compiled = compile_document(document)
        self.assertEqual(observed, [True])
        document['data']['records'][0]['labels'][0] ^= 1
        self.assertEqual(compiled['development'], VIEWS['development'])
        compiled['info']['records'][0]['labels'][0] ^= 1
        self.assertEqual(compiled['development'], VIEWS['development'])
        compiled['development']['geometry']['electrodes_in_signal_channel_order'][0] = 'foreign'
        self.assertEqual(compiled['test'], VIEWS['test'])

    def test_wrong_selected_material_or_panel_rejected_before_projection(self):
        with patch.object(v.r, 'phase_data', side_effect=AssertionError('projection before authentication')):
            with self.assertRaises(v.Refusal):
                v.compile_views(old.DOCS[0], '0' * 64, old.PANEL['panel_identity'])
            with self.assertRaises(v.Refusal):
                compile_document(panel_identity='0' * 64)

    def test_noncomplete_or_private_full_manifest_rejected(self):
        for change in ('missing_test', 'private_test_label', 'original_test_identity'):
            doc = deepcopy(old.DOCS[0])
            if change == 'missing_test': doc['data']['records'].pop()
            elif change == 'private_test_label': doc['data']['records'][-1]['labels'] = [0]
            else: doc['data']['records'][-1]['participant'] = 109
            old.repin(doc)
            with self.subTest(change=change), self.assertRaises(v.Refusal): compile_document(doc)

    def test_data_view_open_schema_rejected_even_when_repinned(self):
        for phase in ('development', 'test'):
            for field, value in (('condition', 'paper_data_code'), ('official_code', old.DOCS[1]['official_code']),
                                 ('test_mapping_identity', 'a' * 64), ('info', VIEWS['info'])):
                view = deepcopy(VIEWS[phase]); view[field] = value; seal(view)
                with self.subTest(phase=phase, field=field), self.assertRaises(v.Refusal): v.validate_view(view)

    def test_test_row_labels_ids_grouping_and_private_metadata_rejected(self):
        for field, value in (('labels', [0]), ('participant', 90), ('run', 4), ('source_event_id', 'S090R04-event000'),
                             ('signal', 'signals/S090R04.npy'), ('event_ids', ['S090R04-event000']),
                             ('shape', [2, 64, 800])):
            view = deepcopy(VIEWS['test']); view['records'][0][field] = value; seal(view)
            with self.subTest(field=field), self.assertRaises(v.Refusal): v.validate_view(view)

    def test_missing_duplicate_or_reordered_development_rejected(self):
        for change in ('missing', 'duplicate', 'reordered', 'test_subject', 'label_omitted', 'boolean_label'):
            view = deepcopy(VIEWS['development'])
            if change == 'missing': view['records'].pop()
            elif change == 'duplicate': view['records'][-1] = deepcopy(view['records'][0])
            elif change == 'reordered': view['records'][0], view['records'][1] = view['records'][1], view['records'][0]
            elif change == 'test_subject': view['records'][-1]['participant'] = 90
            elif change == 'label_omitted': view['records'][0]['labels'].pop()
            else: view['records'][0]['labels'][0] = True
            seal(view)
            with self.subTest(change=change), self.assertRaises(v.Refusal): v.validate_view(view)

    def test_mutated_view_digest_and_private_geometry_rejected(self):
        view = deepcopy(VIEWS['development']); view['records'][0]['labels'][0] ^= 1
        with self.assertRaises(v.Refusal): v.validate_view(view)
        view = deepcopy(VIEWS['test']); view['geometry']['private_join'] = 'forbidden'; seal(view)
        with self.assertRaises(v.Refusal): v.validate_view(view)

    def test_duplicate_test_files_or_ids_rejected(self):
        for field in ('signal', 'event_ids'):
            view = deepcopy(VIEWS['test']); view['records'][1][field] = deepcopy(view['records'][0][field]); seal(view)
            with self.subTest(field=field), self.assertRaises(v.Refusal): v.validate_view(view)

    def test_closed_directory_descriptor_exact_file_counts(self):
        for phase, count in (('development', 536), ('test', 1805)):
            desc = mounted(phase)
            self.assertEqual(len(desc['files']), count)
            self.assertEqual((desc['kind'], desc['purpose']), ('directory', 'input'))
            self.assertEqual(desc['files']['view.json'], v.pin_json(VIEWS[phase]))
            self.assertEqual(v.validate_mount(VIEWS[phase], desc), desc)
            self.assertEqual(set(desc['files']), {'view.json', 'positions.json'} |
                             {row['signal'] for row in VIEWS[phase]['records']})

    def test_full_packet_mount_and_extra_private_files_rejected(self):
        info = VIEWS['info']; all_sizes = {row['signal']: row['shape'][0]*64*800*8+128 for row in info['records']}
        full = old.a.packet_mount(info, Path('/generated-only/full'), info['manifest_pin'], all_sizes)
        with self.assertRaises(v.Refusal): v.validate_mount(VIEWS['development'], full)
        for name in ('materials.json', 'targets.json', 'private/map.json', 'paper.pdf', 'official-code.tar.gz',
                     VIEWS['test']['records'][0]['signal']):
            desc = mounted(); desc['files'][name] = v.a.pin(b'generated metadata only')
            with self.subTest(name=name), self.assertRaises(v.Refusal): v.validate_mount(VIEWS['development'], desc)

    def test_missing_geometry_manifest_or_signal_rejected(self):
        for name in ('view.json', 'positions.json', VIEWS['development']['records'][0]['signal']):
            desc = mounted(); desc['files'].pop(name)
            with self.subTest(name=name), self.assertRaises(v.Refusal): v.validate_mount(VIEWS['development'], desc)

    def test_wrong_pin_type_purpose_or_directory_kind_rejected(self):
        for change in ('geometry_pin', 'view_pin', 'signal_pin', 'pin_extra', 'purpose', 'kind', 'descriptor_extra'):
            desc = mounted()
            if change == 'geometry_pin': desc['files']['positions.json']['sha256'] = '0'*64
            elif change == 'view_pin': desc['files']['view.json']['bytes'] += 1
            elif change == 'signal_pin': desc['files'][VIEWS['development']['records'][0]['signal']]['sha256'] = '0'*64
            elif change == 'pin_extra': desc['files']['view.json']['private_labels'] = [0]
            elif change == 'purpose': desc['purpose'] = 'historical_author_source'
            elif change == 'kind': desc['kind'] = 'file'
            else: desc['private_join'] = 'forbidden'
            with self.subTest(change=change), self.assertRaises(v.Refusal): v.validate_mount(VIEWS['development'], desc)

    def test_extents_are_exact_phase_only_and_bounded(self):
        view = VIEWS['development']; first = view['records'][0]; payload = first['shape'][0]*64*800*8
        for size in (True, 0, payload+9, payload+65549):
            extents = sizes(view); extents[first['signal']] = size
            with self.subTest(size=size), self.assertRaises(v.Refusal): v.data_mount(view, '/generated/dev', extents)
        extents = sizes(view); extents.update(sizes(VIEWS['test']))
        with self.assertRaises(v.Refusal): v.data_mount(view, '/generated/dev', extents)
        for size in (payload+10, payload+65548):
            extents = sizes(view); extents[first['signal']] = size
            self.assertEqual(v.data_mount(view, '/generated/dev', extents)['files'][first['signal']]['bytes'], size)

    def test_root_is_absolute_nonroot_and_no_parent_traversal(self):
        for root in ('relative', '/', '/generated/../private'):
            with self.subTest(root=root), self.assertRaises(v.Refusal):
                v.data_mount(VIEWS['development'], root, sizes(VIEWS['development']))
        desc = mounted(); desc['path'] = '/generated-only//development'
        with self.assertRaises(v.Refusal): v.validate_mount(VIEWS['development'], desc)

    def test_no_array_reads_materialization_or_provider_execution(self):
        original_open = Path.open
        def only_pinned_source(path, *args, **kwargs):
            self.assertEqual(path, v.a.MATERIALS)
            self.assertEqual(args[0] if args else kwargs.get('mode'), 'rb')
            return original_open(path, *args, **kwargs)
        with (patch.object(Path, 'open', only_pinned_source),
              patch.object(v.a, 'transport_package', side_effect=AssertionError('provider unnecessary'))):
            result = compile_document()
            for phase in ('development', 'test'):
                v.validate_mount(result[phase], v.data_mount(result[phase], '/generated/' + phase, sizes(result[phase])))
        self.assertEqual(old.CREATED, 0)


if __name__ == '__main__':
    unittest.main()

"""Generated in-memory HDF-like objects only; no files, native imports or data."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import metadata_source as source_reader

from metadata_source import MetadataSourceError, read_metadata


class HardLink:
    pass


class SoftLink:
    pass


class ExternalLink:
    pass


class Reference:
    def __init__(self, target, valid=True):
        self.target, self.valid = target, valid

    def __bool__(self):
        return self.valid


class RegionReference(Reference):
    pass


class ObjectID:
    def __init__(self, owner):
        self.owner = owner

    def get_create_plist(self):
        return self.owner


class Array:
    def __init__(self, values):
        self.values = list(values)

    def tolist(self):
        return list(self.values)


class Dataset:
    def __init__(self, values, kind, *, protected=False, encoding=None, length=None):
        self.values = list(values)
        self.shape = (len(self.values),)
        self.dtype = SimpleNamespace(kind=kind, itemsize=length if length is not None else 8,
                                     fields=None, subdtype=None, encoding=encoding, length=length)
        self.chunks, self.filters, self.external = None, [], []
        self.is_virtual, self.protected = False, protected
        self.attrs, self.reads, self.id = {}, [], ObjectID(self)

    def get_nfilters(self):
        return len(self.filters)

    def get_filter(self, index):
        return (self.filters[index], 0, (), b'generated')

    def __getitem__(self, key):
        if self.protected:
            raise AssertionError('A protected event/index/trial value was read')
        self.reads.append(key)
        if key == ():
            return Array(self.values)
        if not isinstance(key, slice) or key.step is not None or key.stop != key.start + 1:
            raise AssertionError('String metadata must be read in single-row slices')
        return Array(self.values[key])


class Group:
    def __init__(self, children=None):
        self.children = {} if children is None else children
        self.links = {name: HardLink() for name in self.children}
        self.id = ObjectID(self)

    def get(self, name, *, getlink=False):
        if getlink is not True:
            raise AssertionError('Link metadata must be checked before dereference')
        return self.links.get(name)

    def __getitem__(self, key):
        if type(key) is Reference:
            return key.target
        if not isinstance(self.links.get(key), HardLink):
            raise AssertionError('An indirect source link was followed')
        return self.children[key]


def check_string_dtype(dtype):
    if dtype.encoding is None:
        return None
    return SimpleNamespace(encoding=dtype.encoding, length=dtype.length)


H5_API = SimpleNamespace(HardLink=HardLink, Dataset=Dataset, Group=Group,
                         Reference=Reference, check_string_dtype=check_string_dtype)


def fixture():
    # Actual source IDs are intentionally non-row-valued and unsorted.
    columns = {
        'units/id': Dataset([30, 7, 12], 'i'),
        'units/electrodes': Dataset([1, 0, 2], 'i'),
        'units/quality': Dataset([b'mua', b'good', b'mua'], 'O', encoding='utf-8'),
        'units/spike_times': Dataset([0.] * 5, 'f', protected=True),
        'units/spike_times_index': Dataset([2, 4, 5], 'u', protected=True),
        'intervals/trials/id': Dataset([5, 13], 'i', protected=True),
        'intervals/trials/start_time': Dataset([0., .5], 'f', protected=True),
        'intervals/trials/stop_time': Dataset([.0001, .5001], 'f', protected=True),
        'general/extracellular_ephys/electrodes/location': Dataset(
            [b' ', b'MGv', b'SG'], 'O', encoding='utf-8'),
    }
    # Exact authenticated storage widths for the fixed 26-source cohort.
    columns['units/id'].dtype.itemsize = 4
    root = Group()
    groups = {'': root}
    for path, value in columns.items():
        parts = path.split('/')
        current, prefix = root, ''
        for component in parts[:-1]:
            prefix = prefix + '/' + component if prefix else component
            if component not in current.children:
                current.children[component] = Group()
                current.links[component] = HardLink()
            current = current.children[component]
            groups[prefix] = current
        current.children[parts[-1]] = value
        current.links[parts[-1]] = HardLink()
    table = groups['general/extracellular_ephys/electrodes']
    columns['units/electrodes'].attrs['table'] = Reference(table)
    source = {'asset_id': 'generated-asset', 'subject_id': 'source-mouse',
              'path': 'sub-source-mouse/recording.nwb', 'bytes': 1000, 'sha256': 'a' * 64}
    declared = {
        'asset_id': source['asset_id'], 'source_subject_id': source['subject_id'],
        'source_asset': {key: source[key] for key in ('path', 'bytes', 'sha256')},
        'source_trial_rows': 2,
        'regions': [
            {'region': 'MGv', 'cluster_ids': [30], 'cluster_count': 1, 'quality_counts': {'mua': 1}},
            {'region': 'SG', 'cluster_ids': [12], 'cluster_count': 1, 'quality_counts': {'mua': 1}},
        ],
        'unassigned_cluster_ids': [7], 'unassigned_cluster_count': 1,
        'unassigned_quality_counts': {'good': 1},
    }
    return root, groups, columns, source, declared


def invoke(parts):
    root, _, _, source, declared = parts
    return read_metadata(root, h5api=H5_API, source=source, declared=declared)


class MetadataSourceTests(unittest.TestCase):
    def test_minimal_schema_preserves_source_rows_membership_and_unassigned_audit(self):
        parts = fixture()
        _, _, columns, source, _ = parts
        asset = invoke(parts)
        self.assertEqual(asset['source_unit_row_values'], [[30, 'MGv', 'mua'],
                                                          [7, ' ', 'good'], [12, 'SG', 'mua']])
        self.assertEqual(asset['eligible_unit_row_ordinals'], [0, 2])
        self.assertEqual(asset['unassigned_unit_row_ordinals'], [1])
        self.assertEqual((asset['eligible_cluster_count'], asset['unassigned_cluster_count']), (2, 1))
        self.assertEqual((asset['named_region_cell_count'], asset['trial_region_case_count']), (2, 4))
        self.assertEqual(asset['source_sha256'], source['sha256'])
        self.assertEqual(asset['spike_times']['shape'], [5])
        self.assertEqual(asset['spike_times_index']['shape'], [3])
        self.assertFalse(asset['spike_times']['values_decoded'])
        self.assertIsNone(asset['selected_spike_event_count'])
        for name, column in columns.items():
            if column.protected:
                self.assertEqual(column.reads, [])
            elif name.endswith(('quality', 'location')):
                self.assertEqual(column.reads, [slice(i, i + 1) for i in range(3)])
            else:
                self.assertEqual(column.reads, [()])

    def test_identifier_width_and_signedness_refuse_at_the_intended_guard(self):
        for path, kind, width in (
                ('units/id', 'i', 8), ('units/id', 'u', 4),
                ('units/id', 'f', 4), ('units/id', 'i', 2),
                ('units/electrodes', 'i', 4), ('units/electrodes', 'u', 8)):
            with self.subTest(path=path, kind=kind, width=width):
                parts = fixture()
                target = parts[2][path]
                target.dtype.kind, target.dtype.itemsize = kind, width
                with patch.object(source_reader, '_numeric', wraps=source_reader._numeric) as guard:
                    with self.assertRaisesRegex(MetadataSourceError, '^Unreviewed numeric source dtype$'):
                        invoke(parts)
                self.assertIs(guard.call_args.args[0], target)
                self.assertTrue(all(not column.reads for column in parts[2].values()))

    def test_event_index_and_timing_columns_still_require_64_bit_storage(self):
        for path in ('units/spike_times', 'units/spike_times_index',
                     'intervals/trials/id', 'intervals/trials/start_time',
                     'intervals/trials/stop_time'):
            with self.subTest(path=path):
                parts = fixture()
                target = parts[2][path]
                target.dtype.itemsize = 4
                with patch.object(source_reader, '_numeric', wraps=source_reader._numeric) as guard:
                    with self.assertRaisesRegex(MetadataSourceError, '^Unreviewed numeric source dtype$'):
                        invoke(parts)
                self.assertIs(guard.call_args.args[0], target)
                self.assertTrue(all(not column.reads for column in parts[2].values()))

    def test_fixed_ascii_and_unused_electrode_labels_do_not_change_unit_membership(self):
        parts = fixture()
        columns = parts[2]
        quality = columns['units/quality']
        quality.dtype = SimpleNamespace(kind='S', itemsize=4, fields=None, subdtype=None,
                                         encoding='ascii', length=4)
        locations = columns['general/extracellular_ephys/electrodes/location']
        locations.values.append(b'other-unused-location')
        locations.shape = (4,)
        self.assertEqual(invoke(parts)['source_unit_row_values'],
                         [[30, 'MGv', 'mua'], [7, ' ', 'good'], [12, 'SG', 'mua']])

    def test_no_single_contact_fallback_or_wrong_table_reference(self):
        for reference in (None, 'electrodes', Reference(None, False), Reference(Group()),
                          RegionReference(Group())):
            with self.subTest(reference=type(reference).__name__):
                parts = fixture()
                parts[2]['units/electrodes'].attrs['table'] = reference
                with self.assertRaises(MetadataSourceError):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values()))
        parts = fixture()
        parts[1]['units'].links['electrodes_index'] = HardLink()
        with self.assertRaises(MetadataSourceError):
            invoke(parts)
        self.assertTrue(all(not c.reads for c in parts[2].values()))

    def test_protected_hardlink_alias_refuses_before_any_value_read(self):
        # Same underlying object ID is forbidden even through another wrapper.
        for protected in ('units/spike_times_index', 'intervals/trials/id',
                          'intervals/trials/start_time', 'units/spike_times'):
            with self.subTest(protected=protected):
                parts = fixture()
                parts[2]['units/id'].id = parts[2][protected].id
                with self.assertRaisesRegex(MetadataSourceError, 'aliases'):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values()))
        parts = fixture()
        wave = Dataset([b'mua'] * 3, 'O', protected=True, encoding='utf-8')
        parts[1]['units'].children['waveforms'] = wave
        parts[1]['units'].links['waveforms'] = HardLink()
        parts[2]['units/quality'].id = wave.id
        with self.assertRaisesRegex(MetadataSourceError, 'aliases'):
            invoke(parts)
        self.assertTrue(all(not c.reads for c in parts[2].values()))

    def test_soft_external_and_missing_path_components_fail_before_values(self):
        for group, leaf in (('', 'units'), ('general', 'extracellular_ephys'),
                            ('general/extracellular_ephys', 'electrodes'),
                            ('units', 'quality'), ('intervals/trials', 'stop_time')):
            for link in (SoftLink(), ExternalLink(), None):
                with self.subTest(group=group, leaf=leaf, link=type(link).__name__):
                    parts = fixture()
                    parts[1][group].links[leaf] = link
                    with self.assertRaises(MetadataSourceError):
                        invoke(parts)
                    self.assertTrue(all(not c.reads for c in parts[2].values()))

    def test_storage_headers_and_shapes_refuse_before_any_metadata_values(self):
        mutations = [
            ('units/id', lambda d: setattr(d, 'shape', (2,))),
            ('units/spike_times', lambda d: setattr(d, 'shape', (86704,))),
            ('units/spike_times_index', lambda d: setattr(d.dtype, 'kind', 'i')),
            ('intervals/trials/id', lambda d: setattr(d, 'shape', (3,))),
            ('units/electrodes', lambda d: setattr(d, 'is_virtual', True)),
            ('units/quality', lambda d: setattr(d, 'external', [('elsewhere', 0, 24)])),
            ('units/id', lambda d: setattr(d, 'chunks', (262145,))),
            ('units/id', lambda d: setattr(d, 'filters', [32000])),
            ('units/id', lambda d: setattr(d, 'filters', [1])),
            ('units/quality', lambda d: setattr(d, 'chunks', (4097,))),
        ]
        for name, mutation in mutations:
            with self.subTest(name=name, mutation=mutation):
                parts = fixture()
                mutation(parts[2][name])
                with self.assertRaises(MetadataSourceError):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values()))
        parts = fixture()
        for column in parts[2].values():
            column.chunks, column.filters = (column.shape[0],), [2, 1, 3]
        self.assertEqual(invoke(parts)['eligible_cluster_count'], 2)

    def test_only_reviewed_string_dtypes_and_exact_literal_labels_are_accepted(self):
        header_mutations = [
            lambda d: setattr(d.dtype, 'encoding', None),
            lambda d: setattr(d.dtype, 'encoding', 'latin-1'),
            lambda d: setattr(d.dtype, 'kind', 'f'),
            lambda d: setattr(d.dtype, 'length', 65),
        ]
        for mutation in header_mutations:
            with self.subTest(mutation=mutation):
                parts = fixture()
                mutation(parts[2]['units/quality'])
                with self.assertRaises(MetadataSourceError):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values()))
        for value in (b'x' * 65, b'\xff', b'mua ', b'good\0', 3):
            with self.subTest(value=value):
                parts = fixture()
                parts[2]['units/quality'].values[0] = value
                with self.assertRaises(MetadataSourceError):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values() if c.protected))

    def test_source_membership_contact_bounds_and_quality_counts_must_match(self):
        changes = [
            lambda p: p[2]['units/id'].values.__setitem__(0, 7),
            lambda p: p[2]['units/id'].values.__setitem__(0, 99),
            lambda p: p[2]['units/electrodes'].values.__setitem__(0, -1),
            lambda p: p[2]['units/electrodes'].values.__setitem__(0, 3),
            lambda p: p[2]['units/electrodes'].values.__setitem__(0, 0),
            lambda p: p[2]['units/quality'].values.__setitem__(0, b'good'),
            lambda p: p[2]['general/extracellular_ephys/electrodes/location'].values.__setitem__(0, b''),
        ]
        for mutate in changes:
            with self.subTest(mutation=mutate):
                parts = fixture()
                mutate(parts)
                with self.assertRaises(MetadataSourceError):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values() if c.protected))

    def test_bad_declarations_fail_without_metadata_value_access(self):
        for mutate in (
            lambda p: p[3].__setitem__('sha256', 'b' * 64),
            lambda p: p[4].__setitem__('source_subject_id', 'different'),
            lambda p: p[4]['regions'][0].__setitem__('quality_counts', {'mua': True}),
            lambda p: p[4]['regions'][0].__setitem__('cluster_ids', [7]),
            lambda p: p[4]['regions'].append(deepcopy(p[4]['regions'][0])),
        ):
            with self.subTest(mutation=mutate):
                parts = fixture()
                mutate(parts)
                with self.assertRaises(MetadataSourceError):
                    invoke(parts)
                self.assertTrue(all(not c.reads for c in parts[2].values()))


if __name__ == '__main__':
    unittest.main()

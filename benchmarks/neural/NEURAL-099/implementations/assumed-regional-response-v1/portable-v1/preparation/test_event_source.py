"""Generated fake-object tests of documented HDF5 boundaries; no native import."""

from copy import deepcopy
import math
from types import SimpleNamespace
import unittest

from event_source import EventSourceError, iter_selected_clusters


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


class DatasetID:
    def __init__(self, owner):
        self.owner = owner

    def get_create_plist(self):
        return self.owner


class Array:
    def __init__(self, values, kind):
        self.values = list(values)
        self.shape = (len(self.values),)
        self.dtype = SimpleNamespace(kind=kind, itemsize=8, fields=None, subdtype=None)

    def tolist(self):
        return list(self.values)


class Dataset:
    def __init__(self, values, kind):
        self.values = list(values)
        self.shape = (len(self.values),)
        self.dtype = SimpleNamespace(kind=kind, itemsize=8, fields=None, subdtype=None)
        self.is_virtual, self.external, self.chunks = False, [], None
        self.filters, self.attrs, self.reads = [], {}, []
        self.id = DatasetID(self)
        self.slice_transform = None

    def get_nfilters(self):
        return len(self.filters)

    def get_filter(self, position):
        return (self.filters[position], 0, (), b'generated')

    def __getitem__(self, selection):
        self.reads.append(selection)
        if selection == ():
            result = Array(self.values, self.dtype.kind)
        else:
            if not isinstance(selection, slice) or selection.step is not None:
                raise AssertionError('Expected an ordinary contiguous source slice')
            if not 0 <= selection.start <= selection.stop <= len(self.values):
                raise AssertionError('Source slice escaped its declared extent')
            result = Array(self.values[selection], self.dtype.kind)
            if self.slice_transform is not None:
                self.slice_transform(result)
        return result


class Group:
    def __init__(self, children):
        self.children = children
        self.links = {name: HardLink() for name in children}

    def get(self, name, *, getlink=False):
        if getlink is not True:
            raise AssertionError('Inspect link metadata before resolving components')
        return self.links.get(name)

    def __getitem__(self, key):
        if type(key) is Reference:
            return key.target
        if not isinstance(self.links.get(key), HardLink):
            raise AssertionError('Attempted to follow an indirect link')
        return self.children[key]


H5_API = SimpleNamespace(HardLink=HardLink, Group=Group, Dataset=Dataset, Reference=Reference)


def fixture(rows=None, endpoints=None, events=None):
    if rows is None:
        rows = [[30, 'MGv', 'good'], [5, ' ', 'mua'], [18, 'SG', 'mua']]
    if endpoints is None:
        endpoints = [2, 3, 3]
    if events is None:
        events = [.1, .2, 99.]
    spikes = Dataset(events, 'f')
    index = Dataset(endpoints, 'u')
    index.attrs['target'] = Reference(spikes)
    units = Group({'spike_times': spikes, 'spike_times_index': index})
    handle = Group({'units': units})
    selected = [i for i, row in enumerate(rows) if row[1] != ' ']
    excluded = [i for i, row in enumerate(rows) if row[1] == ' ']
    bounds = {
        'asset_id': 'generated-asset',
        'spike_times': {'path': 'units/spike_times', 'shape': [len(events)],
                        'dtype': 'float64', 'logical_bytes': len(events) * 8},
        'spike_times_index': {'path': 'units/spike_times_index', 'shape': [len(rows)],
                              'dtype': 'uint64', 'logical_bytes': len(rows) * 8},
        'source_unit_row_values': deepcopy(rows),
        'eligible_unit_row_ordinals': selected, 'unassigned_unit_row_ordinals': excluded,
        'eligible_cluster_count': len(selected), 'unassigned_cluster_count': len(excluded),
    }
    return handle, units, spikes, index, bounds


def descriptors(handle, bounds):
    return list(iter_selected_clusters(handle, h5api=H5_API, asset_bounds=bounds))


class EventSourceTests(unittest.TestCase):
    def test_descriptors_are_lazy_and_empty_eligible_clusters_remain(self):
        handle, _, spikes, index, bounds = fixture()
        records = descriptors(handle, bounds)
        self.assertEqual(index.reads, [()])
        self.assertEqual(spikes.reads, [])
        self.assertEqual([(r['source_unit_row'], r['cluster_id'], r['region'], r['declared_spike_count'])
                          for r in records], [(0, 30, 'MGv', 2), (2, 18, 'SG', 0)])
        self.assertEqual([(r['source_global_start'], r['source_global_stop']) for r in records],
                         [(0, 2), (3, 3)])
        self.assertEqual(list(records[0]['chunks']), [{'source_start': 0, 'spikes': [.1, .2]}])
        self.assertEqual(list(records[1]['chunks']), [])
        self.assertEqual(spikes.reads, [slice(0, 2)])

    def test_selected_global_ranges_are_split_into_contiguous_unit_relative_chunks(self):
        events = [float(i) for i in range(65539)]
        handle, _, spikes, _, bounds = fixture(
            [[77, ' ', 'mua'], [910, 'MGd', 'mua']], [2, 65539], events)
        record, = descriptors(handle, bounds)
        self.assertEqual((record['source_global_start'], record['source_global_stop']), (2, 65539))
        self.assertEqual(record['declared_spike_count'], 65537)
        chunks = list(record['chunks'])
        self.assertEqual([set(c) for c in chunks], [{'source_start', 'spikes'}] * 2)
        self.assertEqual([c['source_start'] for c in chunks], [0, 65536])
        self.assertEqual([len(c['spikes']) for c in chunks], [65536, 1])
        self.assertEqual((chunks[0]['spikes'][0], chunks[0]['spikes'][-1], chunks[1]['spikes'][0]),
                         (2., 65537., 65538.))
        self.assertEqual(spikes.reads, [slice(2, 65538), slice(65538, 65539)])

    def test_mapping_is_copied_before_later_caller_mutation(self):
        handle, _, _, _, bounds = fixture()
        iterator = iter_selected_clusters(handle, h5api=H5_API, asset_bounds=bounds)
        first = next(iterator)
        bounds['source_unit_row_values'][2][0] = 999
        bounds['eligible_unit_row_ordinals'].clear()
        second = next(iterator)
        self.assertEqual((first['cluster_id'], second['cluster_id']), (30, 18))

    def test_target_reference_must_resolve_to_exact_spike_object_before_index_read(self):
        for target in (None, 'units/spike_times', Reference(None, valid=False),
                       Reference(Dataset([.1, .2, 99.], 'f')),
                       RegionReference(Dataset([.1], 'f'))):
            with self.subTest(target=type(target).__name__):
                handle, _, spikes, index, bounds = fixture()
                if target is None:
                    del index.attrs['target']
                else:
                    index.attrs['target'] = target
                with self.assertRaises(EventSourceError):
                    descriptors(handle, bounds)
                self.assertEqual((spikes.reads, index.reads), ([], []))
        # A second Python wrapper for the same underlying object is valid.
        handle, _, spikes, index, bounds = fixture()
        alias = Dataset([], 'f')
        alias.id = spikes.id
        index.attrs['target'] = Reference(alias)
        self.assertEqual(len(descriptors(handle, bounds)), 2)

    def test_index_endpoints_must_cover_full_source_without_decreasing(self):
        for endpoints in ([2, 1, 3], [2, 3, 2], [2, 4, 3], [2, 3, 4],
                          [2, 3, True], [2, 3, 3.0], [-1, 3, 3]):
            with self.subTest(endpoints=endpoints):
                handle, _, spikes, _, bounds = fixture(endpoints=endpoints)
                with self.assertRaises(EventSourceError):
                    descriptors(handle, bounds)
                self.assertEqual(spikes.reads, [])

    def test_every_path_component_must_be_a_hard_link(self):
        for level in ('units', 'spike_times', 'spike_times_index'):
            for link in (SoftLink(), ExternalLink(), None):
                with self.subTest(level=level, link=type(link).__name__):
                    handle, units, spikes, index, bounds = fixture()
                    (handle if level == 'units' else units).links[level] = link
                    with self.assertRaises(EventSourceError):
                        descriptors(handle, bounds)
                    self.assertEqual((spikes.reads, index.reads), ([], []))

    def test_all_storage_headers_checked_before_any_values(self):
        mutations = [
            lambda d: setattr(d, 'is_virtual', True),
            lambda d: setattr(d, 'external', [('external.bin', 0, 24)]),
            lambda d: setattr(d, 'shape', (3, 1)),
            lambda d: setattr(d, 'shape', (4,)),
            lambda d: setattr(d.dtype, 'itemsize', 4),
            lambda d: setattr(d.dtype, 'kind', 'i'),
            lambda d: setattr(d.dtype, 'fields', {'value': object()}),
            lambda d: setattr(d, 'chunks', (131073,)),
            lambda d: setattr(d, 'filters', [32000]),
            lambda d: setattr(d, 'filters', [1]),
            lambda d: setattr(d, 'filters', [1, 1]),
        ]
        for which in ('spikes', 'index'):
            for mutation in mutations:
                with self.subTest(which=which, mutation=mutation):
                    handle, _, spikes, index, bounds = fixture()
                    mutation(spikes if which == 'spikes' else index)
                    with self.assertRaises(EventSourceError):
                        descriptors(handle, bounds)
                    self.assertEqual((spikes.reads, index.reads), ([], []))
        handle, _, spikes, index, bounds = fixture()
        for dataset in (spikes, index):
            dataset.chunks, dataset.filters = (3,), [2, 1, 3]
        self.assertEqual(len(descriptors(handle, bounds)), 2)

    def test_frozen_selection_cannot_drop_zero_event_units_or_expand_to_unassigned(self):
        for mutation in (
            lambda b: b.__setitem__('eligible_unit_row_ordinals', [0]),
            lambda b: b.__setitem__('eligible_unit_row_ordinals', [0, 1, 2]),
            lambda b: b['source_unit_row_values'][0].__setitem__(2, 'noise'),
            lambda b: b['source_unit_row_values'][2].__setitem__(0, 30),
            lambda b: b['source_unit_row_values'][0].__setitem__(1, 'MGN'),
        ):
            with self.subTest(mutation=mutation):
                handle, _, spikes, index, bounds = fixture()
                mutation(bounds)
                with self.assertRaises(EventSourceError):
                    descriptors(handle, bounds)
                self.assertEqual((spikes.reads, index.reads), ([], []))

    def test_source_order_and_nonfinite_values_are_not_silently_cleaned(self):
        handle, _, _, _, bounds = fixture([[1, 'MGv', 'good']], [3], [2., 1., float('nan')])
        record, = descriptors(handle, bounds)
        chunk, = list(record['chunks'])
        self.assertEqual(chunk['spikes'][:2], [2., 1.])
        self.assertTrue(math.isnan(chunk['spikes'][2]))
        # The caller's two counting kernels reject invalid values/order; this
        # source boundary must not hide them by sorting or filtering.

    def test_slice_decode_cannot_shorten_or_change_dtype(self):
        for mutate in (lambda a: setattr(a, 'shape', (1,)),
                       lambda a: setattr(a.dtype, 'kind', 'i'),
                       lambda a: a.values.pop()):
            with self.subTest(mutation=mutate):
                handle, _, spikes, _, bounds = fixture()
                spikes.slice_transform = mutate
                records = descriptors(handle, bounds)
                with self.assertRaises(EventSourceError):
                    list(records[0]['chunks'])


if __name__ == '__main__':
    unittest.main()

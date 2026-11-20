"""Tiny generated HDF5 controls for the real target-free gain transform.

The parent owns the single campaign. This module never runs itself and imports
NumPy/h5py only inside exercise_transform. No production globals are replaced.
"""
from pathlib import Path
import hashlib
import inspect

TRANSFORM_SOURCE = {
    'bytes': 19658,
    'sha256': 'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda',
}
FILE_LIMIT = 32 * 1024
WRITE_LIMIT = 640 * 1024
NUMERIC_WORK_LIMIT = 512 * 1024
SERIALIZED_READ_LIMIT = 2816 * 1024


def exercise_transform(testcase, transform_module, root):
    """Run one generated transform exercise and return honest bounded counters.

    Seventeen HDF5 files persist: one source, two successful outputs, and seven
    invalid-source/partial-output pairs. File sizes are measured after each
    operation; a nonidentity output is charged three times its final size for
    initial copy plus modified rewrite. Counters are logical serialized charges,
    not a claim to measure physical filesystem block traffic or HDF5 buffering.
    """
    import h5py
    import numpy as np

    root = Path(root)
    testcase.assertTrue(root.is_absolute())
    testcase.assertEqual(root, root.resolve())
    testcase.assertFalse(any(p.is_symlink() for p in (root, *root.parents)))
    if root.exists():
        testcase.assertTrue(root.is_dir())
        testcase.assertEqual(list(root.iterdir()), [])
    else:
        root.mkdir()
    testcase.assertEqual(transform_module.source_identity(), TRANSFORM_SOURCE)
    testcase.assertEqual(set(inspect.signature(transform_module.transform_h5).parameters),
                         {'source', 'destination', 'expected_baseline_pin', 'gain', 'expected_shapes'})
    rate_keys = tuple(f'{split}_rates_{units}{suffix}'
                     for split in ('train', 'eval')
                     for suffix in ('', '_forward')
                     for units in ('heldin', 'heldout'))
    testcase.assertEqual(transform_module.RATE_KEYS, rate_keys)
    saved_shapes = {key: list(value) for key, value in transform_module.SHAPES.items()}
    saved_grid = transform_module.GAIN_GRID
    shapes = {name: [2 if name.startswith('train_') else 3,
                     1 if name.endswith('_forward') else 3,
                     2 if 'heldin' in name else 1] for name in rate_keys}
    creation_order = tuple(reversed(rate_keys))
    external_target = root / 'synthetic-external-target-must-not-exist.h5'
    external_storage = root / 'synthetic-external-storage-must-not-exist.bin'
    virtual_source = root / 'synthetic-virtual-source-must-not-exist.h5'
    absent_backings = (external_target, external_storage, virtual_source)
    for backing in absent_backings:
        testcase.assertFalse(backing.exists())
    files = []
    charge = 0
    explicit_reads = 0
    explicit_read_calls = 0
    byte_copy_hash_passes = 0
    hdf5_read_contexts = 0
    transform_read_allowance = 0
    inspection_read_allowance = 0
    numeric_charge = 0
    direct_refusals = []
    h5_refusals = []
    calls = 0

    def record(path, multiplier, role):
        nonlocal charge
        if path.exists():
            size = path.stat().st_size
            files.append({'name': path.name, 'bytes': size, 'write_multiplier': multiplier, 'role': role})
            charge += multiplier * size
            testcase.assertLessEqual(size, FILE_LIMIT, 'tiny fixture exceeded its prospective per-file cap')
            testcase.assertLessEqual(charge, WRITE_LIMIT, 'serialized write charge exceeded selected bound')

    def raw(path):
        nonlocal explicit_reads, explicit_read_calls
        value = path.read_bytes()
        explicit_reads += len(value)
        explicit_read_calls += 1
        return value

    def pin_bytes(value):
        return {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}

    def array_for(name):
        nonlocal numeric_charge
        index = rate_keys.index(name)
        dtype = np.dtype('float32' if index % 2 == 0 else 'float64')
        shape = tuple(shapes[name])
        value = np.arange(np.prod(shape), dtype=dtype).reshape(shape)
        value = value / np.asarray(8, dtype=dtype) + np.asarray(index + 1, dtype=dtype)
        value.flat[0] = 0
        numeric_charge += 8 * value.nbytes
        return value

    def fixture(path, invalid=None):
        try:
            with h5py.File(path, 'w', libver='earliest', track_order=True) as handle:
                handle.attrs['fixture'] = np.bytes_('generated-gain-control')
                group = handle.create_group('mc_maze_20', track_order=True)
                group.attrs['phase'] = np.bytes_('val')
                for name in creation_order:
                    if name == rate_keys[0] and invalid == 'softlink':
                        group[name] = h5py.SoftLink('/mc_maze_20/' + rate_keys[1])
                        continue
                    if name == rate_keys[0] and invalid == 'external':
                        group[name] = h5py.ExternalLink(str(external_target), '/never-read')
                        continue
                    array = array_for(name)
                    options = {'track_times': False, 'fillvalue': 0.0}
                    if name == rate_keys[0]:
                        options.update(chunks=(1, *array.shape[1:]), compression='gzip',
                                       compression_opts=1, shuffle=True, fletcher32=True,
                                       maxshape=(None, *array.shape[1:]))
                    if name == rate_keys[0] and invalid == 'scaleoffset':
                        options.update(scaleoffset=2, compression=None, compression_opts=None,
                                       shuffle=False, fletcher32=False)
                    if name == rate_keys[0] and invalid == 'external_storage':
                        # Metadata declaration only: no data argument, resize,
                        # or array assignment may materialize the backing file.
                        dataset = group.create_dataset(
                            name, shape=array.shape, dtype=array.dtype, track_times=False,
                            external=[(str(external_storage), 0, h5py.h5f.UNLIMITED)])
                        testcase.assertTrue(bool(dataset.external))
                    elif name == rate_keys[0] and invalid == 'virtual':
                        layout = h5py.VirtualLayout(shape=array.shape, dtype=array.dtype)
                        layout[:] = h5py.VirtualSource(str(virtual_source), '/never-read', shape=array.shape)
                        dataset = group.create_virtual_dataset(name, layout, fillvalue=0.0)
                        testcase.assertTrue(dataset.is_virtual)
                    else:
                        dataset = group.create_dataset(name, data=array, **options)
                    dataset.attrs['units'] = np.bytes_('spikes/bin')
                    dataset.attrs['ordinal'] = np.int16(rate_keys.index(name))
                if invalid == 'extra':
                    group.create_dataset('forbidden_target', data=np.asarray([7.0]), track_times=False)
                if invalid == 'reference':
                    handle.attrs['indirect'] = group[rate_keys[1]].ref
        finally:
            record(path, 1, 'generated-source')
        for backing in absent_backings:
            testcase.assertFalse(backing.exists(), 'fixture must remain metadata-only')

    def attrs(value):
        result = []
        for key in value.attrs:
            item = np.asarray(value.attrs[key])
            result.append((key, item.dtype.str, item.shape, item.tobytes(order='C')))
        return tuple(result)

    def metadata(path):
        nonlocal inspection_read_allowance, hdf5_read_contexts
        inspection_read_allowance += 2 * path.stat().st_size
        hdf5_read_contexts += 1
        with h5py.File(path, 'r') as handle:
            group = handle['mc_maze_20']
            result = {'root': attrs(handle), 'group': attrs(group), 'order': tuple(group), 'datasets': {}}
            for name in rate_keys:
                item = group[name]
                result['datasets'][name] = {
                    'shape': item.shape, 'dtype': item.dtype.str, 'attrs': attrs(item),
                    'chunks': item.chunks, 'compression': item.compression,
                    'compression_opts': item.compression_opts, 'shuffle': item.shuffle,
                    'fletcher32': item.fletcher32, 'scaleoffset': item.scaleoffset,
                    'maxshape': item.maxshape,
                    'fillvalue': np.asarray(item.fillvalue, dtype=item.dtype).tobytes(),
                }
            return result

    def transform(source, output, source_pin, gain):
        nonlocal calls, transform_read_allowance, numeric_charge
        nonlocal byte_copy_hash_passes, hdf5_read_contexts
        calls += 1
        completed = False
        try:
            result = transform_module.transform_h5(source, output, source_pin, gain, expected_shapes=shapes)
            completed = True
            return result
        finally:
            # Failed structural admission leaves a complete copied file. Only
            # successful nonidentity modification needs the extra rewrite charge.
            multiplier = 3 if gain != [1, 1] else 1
            record(output, multiplier, 'production-output-or-partial')
            output_size = output.stat().st_size if output.exists() else 0
            # Exact explicit production passes: one source copy, one copied-
            # output hash and, on success, one final output hash. Each HDF5
            # reading context receives two whole-container logical allowances.
            contexts = 2 if gain != [1, 1] else 1
            byte_copy_hash_passes += 2 + int(completed)
            hdf5_read_contexts += contexts
            transform_read_allowance += (source_pin['bytes'] + output_size
                                         + int(completed) * output_size
                                         + 2 * contexts * output_size)
            numeric_charge += 16 * sum(np.prod(shapes[key]) * 8 for key in rate_keys)

    source = root / 'baseline.h5'
    fixture(source)
    original = raw(source)
    original_pin = pin_bytes(original)
    before = metadata(source)
    testcase.assertEqual(before['order'], creation_order)
    identity_path = root / 'identity.h5'
    identity = transform(source, identity_path, original_pin, [1, 1])
    testcase.assertEqual(raw(identity_path), original)
    testcase.assertEqual(identity['output']['bytes'], original_pin['bytes'])
    testcase.assertEqual(identity['output']['sha256'], original_pin['sha256'])
    testcase.assertTrue(identity['identity_byte_copy'])
    testcase.assertFalse(identity['target_accessed'])
    testcase.assertFalse(identity['scientific_improvement'])
    testcase.assertEqual(metadata(identity_path), before)

    gained_path = root / 'gain-nine-eighths.h5'
    gained = transform(source, gained_path, original_pin, [9, 8])
    testcase.assertFalse(gained['identity_byte_copy'])
    testcase.assertFalse(gained['target_accessed'])
    testcase.assertFalse(gained['inference_execution_qualified'])
    testcase.assertFalse(gained['scientific_improvement'])
    testcase.assertEqual(set(gained['rate_fields']), set(rate_keys))
    testcase.assertEqual(metadata(gained_path), before)
    hdf5_read_contexts += 2
    inspection_read_allowance += 2 * (source.stat().st_size + gained_path.stat().st_size)
    with h5py.File(source, 'r') as original_h5, h5py.File(gained_path, 'r') as gained_h5:
        for name in rate_keys:
            old = original_h5['mc_maze_20'][name][()]
            new = gained_h5['mc_maze_20'][name][()]
            # All fixture rates and9/8 are dyadic, so this independent float64
            # arithmetic has no extra product rounding before the dtype cast.
            expected = (old.astype(np.float64) * 9.0 / 8.0).astype(old.dtype)
            testcase.assertEqual(new.dtype, old.dtype)
            testcase.assertEqual(new.shape, old.shape)
            testcase.assertEqual(new.tobytes(order='C'), expected.tobytes(order='C'))
            testcase.assertTrue(bool(np.any(new != old)), name + ' must actually be scaled')
            scalar = np.asarray(9, dtype=old.dtype) / np.asarray(8, dtype=old.dtype)
            testcase.assertEqual(gained['executed_gains'][name]['value_hex'], float(scalar).hex())
            numeric_charge += 16 * (old.nbytes + new.nbytes + expected.nbytes)
    testcase.assertEqual(raw(source), original)
    testcase.assertEqual(pin_bytes(raw(source)), original_pin)

    invalid_arrays = (
        ('float16', np.asarray([1.0], dtype=np.float16), [9, 8], 'float32/float64'),
        ('nan', np.asarray([np.nan], dtype=np.float32), [9, 8], 'finite nonnegative'),
        ('infinity', np.asarray([np.inf], dtype=np.float64), [9, 8], 'finite nonnegative'),
        ('negative', np.asarray([-0.125], dtype=np.float32), [9, 8], 'finite nonnegative'),
        ('overflow', np.asarray([np.finfo(np.float32).max], dtype=np.float32), [2, 1], 'overflow'),
        ('underflow', np.asarray([np.finfo(np.float32).smallest_subnormal], dtype=np.float32), [1, 2], 'underflow'),
    )
    for name, array, gain, message in invalid_arrays:
        with testcase.subTest(array_refusal=name):
            before_bytes = array.tobytes()
            with testcase.assertRaisesRegex(ValueError, message):
                transform_module.scale_block(array, gain)
            testcase.assertEqual(array.tobytes(), before_bytes)
            numeric_charge += 64 * array.nbytes
            direct_refusals.append(name)

    expected_errors = {
        'extra': 'canonical prediction group', 'softlink': 'direct rate dataset',
        'external': 'direct rate dataset', 'reference': 'no indirect or compound attribute',
        'scaleoffset': 'supported lossless rate storage',
        'external_storage': 'ordinary internal rate dataset',
        'virtual': 'ordinary internal rate dataset',
    }
    for invalid, message in expected_errors.items():
        with testcase.subTest(hdf5_refusal=invalid):
            invalid_source = root / (invalid + '-input.h5')
            invalid_output = root / (invalid + '-partial.h5')
            fixture(invalid_source, invalid)
            original_bad = raw(invalid_source)
            with testcase.assertRaisesRegex(ValueError, message):
                transform(invalid_source, invalid_output, pin_bytes(original_bad), [1, 1])
            testcase.assertTrue(invalid_output.exists(), 'failed copied output is retained')
            testcase.assertEqual(raw(invalid_output), original_bad)
            testcase.assertEqual(raw(invalid_source), original_bad)
            h5_refusals.append(invalid)
            for backing in absent_backings:
                testcase.assertFalse(backing.exists(), 'rejection must not materialize a backing file')
    for backing in absent_backings:
        testcase.assertFalse(backing.exists())
    testcase.assertEqual(transform_module.SHAPES, saved_shapes)
    testcase.assertEqual(transform_module.GAIN_GRID, saved_grid)
    testcase.assertEqual(transform_module.RATE_KEYS, rate_keys)
    testcase.assertEqual(len(files), 17)
    testcase.assertEqual(len({row['name'] for row in files}), 17)
    testcase.assertEqual(len(list(root.iterdir())), 17)
    testcase.assertEqual(calls, 9)
    testcase.assertEqual(explicit_read_calls, 25)
    testcase.assertEqual(byte_copy_hash_passes, 20)
    testcase.assertEqual(hdf5_read_contexts, 15)
    testcase.assertLessEqual(numeric_charge, NUMERIC_WORK_LIMIT)
    # This conservatively charges whole serialized containers repeatedly for
    # both direct HDF5 metadata inspection and production source/output reads.
    # It is an upper accounting allowance, not observed OS read syscall bytes.
    serialized_read_upper = (TRANSFORM_SOURCE['bytes'] + explicit_reads + transform_read_allowance
                             + inspection_read_allowance)
    testcase.assertLessEqual(serialized_read_upper, SERIALIZED_READ_LIMIT)
    return {
        'schema': 'smc_gain_generated_transform_controls_v2',
        'production_source': dict(TRANSFORM_SOURCE),
        'production_transform_h5_calls': calls,
        'identity_whole_file_byte_equality': True,
        'nonidentity_gain': [9, 8], 'all_eight_rate_fields_scaled': list(rate_keys),
        'mixed_float32_float64': True,
        'dtype_shape_order_attributes_creation_properties_preserved': True,
        'original_source_unchanged': True, 'target_operand_present': False,
        'direct_scale_block_refusals': direct_refusals,
        'hdf5_structural_refusals': h5_refusals,
        'synthetic_external_target_created': False,
        'synthetic_external_storage_created': False,
        'synthetic_virtual_source_created': False,
        'indirect_dataset_refusal_precedes_numeric_read': {
            'source_sha256': TRANSFORM_SOURCE['sha256'],
            'metadata_guard_line': 258, 'first_numeric_read_line': 271,
            'qualification': 'authenticated production source ordering plus real refusal calls; no backing file exists',
        },
        'production_globals_modified': False,
        'files': files, 'generated_files': 17, 'deleted_files': 0,
        'generated_serialized_file_bytes': sum(row['bytes'] for row in files),
        'generated_write_charge_bytes': charge,
        'explicit_file_read_bytes': explicit_reads,
        'generated_serialized_read_upper_bytes': serialized_read_upper,
        'read_pass_accounting': {
            'explicit_file_read_calls': explicit_read_calls,
            'production_copy_or_hash_passes': byte_copy_hash_passes,
            'hdf5_read_contexts': hdf5_read_contexts,
            'whole_container_allowances_per_hdf5_context': 2,
            'maximum_container_extents': 75,
            'fixed_source_authentication_bytes': TRANSFORM_SOURCE['bytes'],
            'prospective_serialized_read_upper_bytes': 2477258,
            'physical_os_read_bytes_measured': False,
        },
        'logical_numeric_read_write_charge_bytes': int(numeric_charge),
        'limits': {'write_bytes': WRITE_LIMIT, 'numeric_work_bytes': NUMERIC_WORK_LIMIT,
                   'serialized_read_bytes': SERIALIZED_READ_LIMIT, 'per_file_bytes': FILE_LIMIT},
        'original_data_used': False, 'native_qualification': False,
    }

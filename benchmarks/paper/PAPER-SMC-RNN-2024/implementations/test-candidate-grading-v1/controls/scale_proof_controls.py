"""Generated controls for the new independent TEST gain scale verifier.

One helper call belongs to the parent campaign. This does not rerun the old
transform suite or implement a numerical scorer. All fixtures are constructed
fresh; the real verifier is read-only and production globals remain untouched.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import inspect

VERIFIER_SOURCE = {
    'bytes': 30351,
    'sha256': '8e39f087935d26ab8869a697dc20d76f409db4fa5bf27bbbddb1c49ec4983e2c',
}
TRANSFORM_SOURCE = {
    'bytes': 19658,
    'sha256': 'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda',
}
FILE_LIMIT = 32 * 1024
FILE_WRITE_LIMIT = 320 * 1024
NUMERIC_WORK_LIMIT = 512 * 1024
SERIALIZED_READ_LIMIT = 3 * 1024 * 1024


def exercise_scaled_pair(testcase, verifier_module, transform_module, root):
    """Exercise actual verify_scaled_pair once per declared generated case.

    The caller authenticates the selected modules. Tiny geometry is supplied
    through the production function's explicit expected_shapes seam; original
    production dimensions/constants and function bodies are never replaced.
    This standalone verifier has no target operand. The parent grading control
    separately verifies its position before protected target access.
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
    testcase.assertEqual(set(inspect.signature(verifier_module.verify_scaled_pair).parameters),
                         {'reference_path', 'candidate_path', 'gain', 'expected_shapes'})
    rate_keys = tuple(f'{split}_rates_{units}{suffix}'
                     for split in ('train', 'eval')
                     for suffix in ('', '_forward')
                     for units in ('heldin', 'heldout'))
    testcase.assertEqual(transform_module.RATE_KEYS, rate_keys)
    testcase.assertEqual(verifier_module.PINS['gain_transform.py'], TRANSFORM_SOURCE)
    saved = {'SHAPES': deepcopy(transform_module.SHAPES),
             'RATE_KEYS': transform_module.RATE_KEYS,
             'GAIN_GRID': transform_module.GAIN_GRID,
             'verifier_PINS': deepcopy(verifier_module.PINS)}
    shapes = {name: [2 if name.startswith('train_') else 3,
                     1 if name.endswith('_forward') else 3,
                     2 if 'heldin' in name else 1] for name in rate_keys}
    files = []
    write_charge = 0
    explicit_read_bytes = 0
    explicit_read_calls = 0
    production_hash_passes = 0
    hdf5_read_contexts = 0
    verifier_read_allowance = 0
    numeric_charge = 0
    calls = 0
    refusals = []
    permutation_preserved_multiset = False

    def read(path):
        nonlocal explicit_read_bytes, explicit_read_calls
        value = path.read_bytes()
        explicit_read_bytes += len(value)
        explicit_read_calls += 1
        return value

    def pin(value):
        return {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}

    def record(path, role):
        nonlocal write_charge
        if path.exists():
            size = path.stat().st_size
            files.append({'name': path.name, 'bytes': size, 'role': role, 'write_multiplier': 1})
            write_charge += size
            testcase.assertLessEqual(size, FILE_LIMIT)
            testcase.assertLessEqual(write_charge, FILE_WRITE_LIMIT)

    def original_array(name):
        nonlocal numeric_charge
        index = rate_keys.index(name)
        dtype = np.dtype('float32' if index % 2 == 0 else 'float64')
        value = np.arange(np.prod(shapes[name]), dtype=dtype).reshape(shapes[name])
        value = value / np.asarray(8, dtype=dtype) + np.asarray(index + 1, dtype=dtype)
        numeric_charge += 16 * value.nbytes
        return value

    def construct(path, mode):
        nonlocal numeric_charge, permutation_preserved_multiset
        testcase.assertFalse(path.exists())
        order = tuple(reversed(rate_keys)) if mode == 'group_order' else rate_keys
        try:
            with h5py.File(path, 'w', libver='earliest', track_order=True) as handle:
                handle.attrs['fixture'] = np.bytes_('attribute-drift' if mode == 'attrs' else 'generated-test-scale-proof')
                group = handle.create_group('mc_maze_20', track_order=True)
                group.attrs['phase'] = np.bytes_('test')
                for name in order:
                    if mode == 'missing_train_forward' and name.startswith('train_') and name.endswith('_forward'):
                        continue
                    array = original_array(name)
                    if mode != 'reference' and not (mode == 'unscaled_train' and name.startswith('train_')):
                        # Round the gain in each source dtype before multiplying.
                        # This fixture arithmetic is independent of scale_block;
                        # the real verifier itself calls unchanged scale_block.
                        scalar = np.divide(np.asarray(8, dtype=array.dtype),
                                           np.asarray(9, dtype=array.dtype), dtype=array.dtype)
                        array = np.multiply(array, scalar, dtype=array.dtype)
                    if mode == 'row_permutation' and name == 'eval_rates_heldin':
                        before = array.copy()
                        array = array[[1, 0, 2], :, :]
                        testcase.assertEqual(array.shape, before.shape)
                        testcase.assertEqual(array.dtype, before.dtype)
                        testcase.assertEqual(np.sort(array, axis=None).tobytes(),
                                             np.sort(before, axis=None).tobytes())
                        testcase.assertNotEqual(array.tobytes(), before.tobytes())
                        permutation_preserved_multiset = True
                        numeric_charge += 16 * array.nbytes
                    if mode == 'dtype' and name == 'eval_rates_heldin':
                        testcase.assertEqual(array.dtype, np.dtype('float32'))
                        array = array.astype(np.float64)
                    options = {'track_times': False, 'fillvalue': 0.0}
                    if name == rate_keys[0]:
                        options.update(chunks=(1, *array.shape[1:]), compression='gzip',
                                       compression_opts=1, shuffle=True, fletcher32=True,
                                       maxshape=(None, *array.shape[1:]))
                    item = group.create_dataset(name, data=array, **options)
                    item.attrs['units'] = np.bytes_('spikes/20ms')
                    item.attrs['ordinal'] = np.int16(rate_keys.index(name))
                    numeric_charge += 16 * array.nbytes
        finally:
            record(path, mode)
        data = read(path)
        return pin(data), data

    def byte_fixture(path, data, role):
        testcase.assertFalse(path.exists())
        try:
            with path.open('xb') as output:
                output.write(data)
        finally:
            record(path, role)
        saved_data = read(path)
        testcase.assertEqual(saved_data, data)
        return pin(saved_data), saved_data

    reference_path = root / 'reference.h5'
    reference_pin, reference_bytes = construct(reference_path, 'reference')

    def verify(candidate_path, candidate_pin, candidate_bytes, gain, contexts):
        nonlocal calls, production_hash_passes, hdf5_read_contexts
        nonlocal verifier_read_allowance, numeric_charge
        calls += 1
        completed = False
        try:
            result = verifier_module.verify_scaled_pair(reference_path, candidate_path, gain, expected_shapes=shapes)
            completed = True
            return result
        finally:
            # Actual verifier hashes both whole files before checking and repeats
            # both hashes only on success. Identity drift refuses before HDF5.
            production_hash_passes += 2 + 2 * int(completed)
            hdf5_read_contexts += contexts
            verifier_read_allowance += ((1 + int(completed)) * (reference_pin['bytes'] + candidate_pin['bytes'])
                                        + (reference_pin['bytes'] + candidate_pin['bytes']) * contexts)
            testcase.assertEqual(read(candidate_path), candidate_bytes, 'independent verifier must not modify candidate')
            numeric_charge += 32 * sum(np.prod(shapes[key]) * 8 for key in rate_keys)

    candidate_path = root / 'scaled-eight-ninths.h5'
    candidate_pin, candidate_bytes = construct(candidate_path, 'scaled')
    result = verify(candidate_path, candidate_pin, candidate_bytes, [8, 9], 2)
    testcase.assertEqual(result['schema'], 'smc_test_gain_scale_proof_v1')
    testcase.assertEqual(result['gain'], [8, 9])
    testcase.assertEqual(result['reference'], reference_pin)
    testcase.assertEqual(result['candidate'], candidate_pin)
    testcase.assertEqual(result['rate_fields'], list(rate_keys))
    testcase.assertEqual(result['shapes'], shapes)
    testcase.assertTrue(result['all_eight_fields_exact'])
    testcase.assertFalse(result['identity_whole_file_equal'])
    testcase.assertFalse(result['target_accessed'])
    testcase.assertFalse(result['inference_execution_qualified'])
    rounded_float32 = np.divide(np.asarray(8, dtype=np.float32), np.asarray(9, dtype=np.float32), dtype=np.float32)
    testcase.assertNotEqual(float(rounded_float32), 8.0 / 9.0, 'source precision must be consequential')
    for name in rate_keys:
        dtype = np.dtype('float32' if rate_keys.index(name) % 2 == 0 else 'float64')
        rounded = np.divide(np.asarray(8, dtype=dtype), np.asarray(9, dtype=dtype), dtype=dtype)
        testcase.assertEqual(result['executed_gains'][name]['value_hex'], float(rounded).hex())
        testcase.assertEqual(result['executed_gains'][name]['dtype'], dtype.str)

    identity_path = root / 'identity.h5'
    identity_pin, identity_bytes = byte_fixture(identity_path, reference_bytes, 'identity')
    identity = verify(identity_path, identity_pin, identity_bytes, [1, 1], 2)
    testcase.assertEqual(identity_pin, reference_pin)
    testcase.assertEqual(identity['reference'], reference_pin)
    testcase.assertEqual(identity['candidate'], reference_pin)
    testcase.assertTrue(identity['all_eight_fields_exact'])
    testcase.assertTrue(identity['identity_whole_file_equal'])
    testcase.assertFalse(identity['target_accessed'])

    errors = {
        'row_permutation': 'Every TEST and TRAIN field equals',
        'unscaled_train': 'Every TEST and TRAIN field equals',
        'dtype': 'Exact unchanged dtype, field order, attributes',
        'group_order': 'Exact unchanged dtype, field order, attributes',
        'attrs': 'Exact unchanged dtype, field order, attributes',
        'missing_train_forward': 'canonical prediction group',
    }
    for mode, message in errors.items():
        with testcase.subTest(scale_refusal=mode):
            bad_path = root / (mode + '.h5')
            bad_pin, bad_bytes = construct(bad_path, mode)
            with testcase.assertRaisesRegex(ValueError, message):
                verify(bad_path, bad_pin, bad_bytes, [8, 9], 2)
            refusals.append(mode)
    testcase.assertTrue(permutation_preserved_multiset)

    drift_path = root / 'identity-byte-drift.h5'
    # One fresh write, not copy-then-append: every original HDF5 byte is preserved
    # as a prefix, while whole-file identity changes independently of arrays.
    trailer = b'generated identity whole-file mismatch\n'
    drift_pin, drift_bytes = byte_fixture(drift_path, reference_bytes + trailer, 'identity_byte_drift')
    testcase.assertEqual(drift_bytes[:-len(trailer)], reference_bytes)
    testcase.assertNotEqual(drift_pin, reference_pin)
    with testcase.assertRaisesRegex(ValueError, 'Identity gain requires complete serialized byte equality'):
        verify(drift_path, drift_pin, drift_bytes, [1, 1], 0)
    refusals.append('identity_byte_drift')
    testcase.assertEqual(read(reference_path), reference_bytes, 'reference bytes must remain unchanged')

    testcase.assertEqual(transform_module.SHAPES, saved['SHAPES'])
    testcase.assertEqual(transform_module.RATE_KEYS, saved['RATE_KEYS'])
    testcase.assertEqual(transform_module.GAIN_GRID, saved['GAIN_GRID'])
    testcase.assertEqual(verifier_module.PINS, saved['verifier_PINS'])
    testcase.assertEqual(len(files), 10)
    testcase.assertEqual(len({row['name'] for row in files}), 10)
    testcase.assertEqual(len(list(root.iterdir())), 10)
    testcase.assertEqual(calls, 9)
    testcase.assertEqual(explicit_read_calls, 20)
    testcase.assertEqual(production_hash_passes, 22)
    testcase.assertEqual(hdf5_read_contexts, 16)
    serialized_read_upper = explicit_read_bytes + verifier_read_allowance + calls * TRANSFORM_SOURCE['bytes']
    testcase.assertLessEqual(serialized_read_upper, SERIALIZED_READ_LIMIT)
    testcase.assertLessEqual(numeric_charge, NUMERIC_WORK_LIMIT)
    return {
        'schema': 'smc_test_generated_scale_proof_controls_v1',
        'verifier_source': dict(VERIFIER_SOURCE), 'arithmetic_source': dict(TRANSFORM_SOURCE),
        'real_verifier_calls': calls, 'successful_calls': 2, 'refusals': refusals,
        'all_eight_fields_checked': list(rate_keys), 'gain': [8, 9],
        'source_float32_rounding_consequential': True,
        'permuted_field_multiset_preserved': permutation_preserved_multiset,
        'all_train_fields_unscaled_refused': True, 'missing_both_train_forward_refused': True,
        'identity_requires_whole_file_equality': True,
        'dtype_group_order_attributes_refused': True,
        'target_operand_present': False,
        'target_order_scope': 'standalone target-free verifier; parent control separately binds pretarget grading order',
        'production_globals_modified': False,
        'files': files, 'generated_files': 10, 'deleted_files': 0,
        'generated_write_charge_bytes': write_charge,
        'explicit_file_read_bytes': explicit_read_bytes,
        'serialized_read_upper_bytes': serialized_read_upper,
        'numeric_read_write_charge_bytes': int(numeric_charge),
        'read_pass_accounting': {'explicit_file_reads': explicit_read_calls,
                                 'production_file_hashes': production_hash_passes,
                                 'hdf5_read_contexts': hdf5_read_contexts,
                                 'container_allowances_per_hdf5_context': 2,
                                 'maximum_container_extents': 74,
                                 'arithmetic_source_loads': calls,
                                 'prospective_serialized_upper_bytes': 2601754,
                                 'physical_os_read_bytes_measured': False},
        'limits': {'per_file_bytes': FILE_LIMIT, 'write_bytes': FILE_WRITE_LIMIT,
                   'serialized_reads': SERIALIZED_READ_LIMIT, 'numeric_work_bytes': NUMERIC_WORK_LIMIT},
        'original_data_used': False, 'numerical_scoring_performed': False,
        'native_runtime_qualification': False,
    }

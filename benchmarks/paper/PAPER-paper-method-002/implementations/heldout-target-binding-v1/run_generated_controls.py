"""Fixed portable entry for eight generated held-out target-binding controls.

Reuses the existing bounded reporting transport. No original data, model fit,
predictions, installation or scientific qualification occurs in this entry.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
import platform
from pathlib import Path
import stat
import sys
import types
import unittest

HELPER_PIN = (14104, 'd44de0d61c9b8c5f1f33226fcedfec40dc66873f669ad44e8c28eb07e930b59e')
BRIDGE_PIN = (9036, '532fca222720efb6c2d597083e3e79e6ee26a404da6822cfd6f2feef445f5573')
CONTROLS_PIN = (12756, '7256d9f49811c28af1c38aaa38b6a8c740820e0e329e83ef2001b632c43d278e')
DEPENDENCY_PINS = {
    'input_binding': ('original-input-programme-v1', 'input_binding.py', 10007, 'f4bd10b4c40cef74835001937ce3dc5cb4bd16fcc061b4138696b39827a707d9'),
    'scorer': ('retinal-heldout', 'score.py', 10745, 'b2ac5156fe01d600d32b35e0bbf716bd6dea69f59b6bd3a062a6a6c2b0bb126c'),
}
PUBLIC_NAMES = ['README.md', 'generated_target_binding_controls.py', 'run_generated_controls.py', 'target_binding.py']
EXPECTED_IDS = ['test_bounded_npy_decoder_rejects_wrong_headers_and_trailing_bytes', 'test_coherent_relabelled_split_and_site_orders_refuse_frozen_identity', 'test_derived_mask_requires_exact_float64_descriptor', 'test_file_identity_links_and_strict_json_fail_closed', 'test_real_file_bridge_existing_producer_and_existing_score', 'test_target_bytes_shape_dtype_and_finiteness_are_bound', 'test_test_target_in_participant_or_wrong_private_layout_refuses', 'test_undefined_site_is_preserved_by_existing_producer_and_scorer']

def _reporter():
    # Authenticate the one adjacent stdlib helper before executing its bytes.
    import hashlib
    import os
    import stat
    import types
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'original-input-programme-v1')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open('/', flags)
    fd = None
    try:
        for part in root.split('/')[1:]:
            if part in ('', '.', '..'):
                raise ValueError('noncanonical source root')
            child = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open('reporting_transport.py', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != HELPER_PIN[0]:
            raise ValueError('helper mode/link/extent')
        chunks, total = [], 0
        while total <= HELPER_PIN[0]:
            part = os.read(fd, min(8192, HELPER_PIN[0] + 1 - total))
            if not part:
                break
            chunks.append(part)
            total += len(part)
        body = b''.join(chunks)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(os.fstat(fd)) or len(body) != HELPER_PIN[0] or hashlib.sha256(body).hexdigest() != HELPER_PIN[1]:
            raise ValueError('helper byte identity')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)
    module = types.ModuleType('_jaxley_input_reporting_transport')
    module.__file__ = os.path.join(root, 'reporting_transport.py')
    exec(compile(body, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    return module, root



def _held_sources(reporting, package, implementations):
    directory = reporting._directory(package)
    try:
        reporting.require(sorted(os.listdir(directory)) == PUBLIC_NAMES, 'exact target-binding source namespace')
    finally:
        os.close(directory)
    held = {
        'bridge': reporting.read_source(package, 'target_binding.py', *BRIDGE_PIN),
        'controls': reporting.read_source(package, 'generated_target_binding_controls.py', *CONTROLS_PIN),
    }
    pins = {
        'bridge': {'path': os.path.join(package, 'target_binding.py'), 'bytes': BRIDGE_PIN[0], 'sha256': BRIDGE_PIN[1]},
        'controls': {'path': os.path.join(package, 'generated_target_binding_controls.py'), 'bytes': CONTROLS_PIN[0], 'sha256': CONTROLS_PIN[1]},
    }
    for role, (folder, name, size, digest) in DEPENDENCY_PINS.items():
        source_root = os.path.join(implementations, folder)
        held[role] = reporting.read_source(source_root, name, size, digest)
        pins[role] = {'path': os.path.join(source_root, name), 'bytes': size, 'sha256': digest}
    pins['reporting_transport'] = {'path': os.path.join(implementations, 'original-input-programme-v1', 'reporting_transport.py'),
                                 'bytes': HELPER_PIN[0], 'sha256': HELPER_PIN[1]}
    return held, pins


def _module(name, path, body, supplied=None):
    module = types.ModuleType(name)
    module.__file__ = path
    if supplied:
        module.__dict__.update(supplied)
    sys.modules[name] = module
    exec(compile(body, path, 'exec', dont_inherit=True), module.__dict__)
    return module


def _worker(reporting, package, artifacts, report_fd):
    entry = {'schema': 'jaxley-target-binding-control-entry-v1', 'source_pins': {},
             'runtime': None, 'control_call_started': False, 'resource_authority': False,
             'original_inputs': False, 'model_fits': False, 'actual_score': False,
             'scientific_qualification': False, 'current_source_and_runtime_bound': False}
    raw = None
    try:
        implementations = os.path.dirname(package)
        held, entry['source_pins'] = _held_sources(reporting, package, implementations)
        # The outer transport created this fresh leaf and these two files only.
        directory = reporting._directory(artifacts)
        try:
            reporting.require(sorted(os.listdir(directory)) == ['DIAGNOSTICS.log', 'RESULT.json'],
                              'fresh transport artifact workspace')
        finally:
            os.close(directory)
        import numpy as np
        reporting.require(sys.version_info[:3] == (3, 11, 18) and sys.flags.isolated == 1,
                          'selected hosted Python profile')
        reporting.require(platform.system() == 'Linux' and platform.machine() == 'x86_64',
                          'selected hosted operating-system profile')
        reporting.require(np.__version__ == '1.24.3' and metadata.version('numpy') == '1.24.3',
                          'selected hosted NumPy profile')
        for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                         'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
            reporting.require(os.environ.get(variable) == '1', 'one-thread environment:' + variable)
        bridge = _module('_jaxley_public_target_binding', entry['source_pins']['bridge']['path'], held['bridge'])
        controls = _module('_jaxley_public_target_binding_controls', entry['source_pins']['controls']['path'],
                           held['controls'], {'_CONTROL_ARTIFACT_ROOT': artifacts,
                           '_CONTROL_IMPLEMENTATIONS_ROOT': implementations, '_CONTROL_BRIDGE': bridge})
        entry['runtime'] = {'python': platform.python_version(), 'system': platform.system(),
            'machine': platform.machine(), 'numpy_version': np.__version__, 'numpy_origin': np.__file__,
            'numpy_init_bytes': len(controls.NUMPY_INIT_BODY),
            'numpy_init_sha256': hashlib.sha256(controls.NUMPY_INIT_BODY).hexdigest(),
            'profile': 'jaxley-input-cpu', 'scope': 'actual generated-control child; no whole binary/environment audit'}
        roster = unittest.defaultTestLoader.getTestCaseNames(controls.TargetBindingControls)
        reporting.require(roster == EXPECTED_IDS, 'exact eight-control method roster')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(controls.TargetBindingControls)
        entry['control_call_started'] = True
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
        raw = {'schema': 'jaxley-target-binding-generated-controls-v1',
            'status': 'PASS' if result.wasSuccessful() and not result.skipped and result.testsRun == 8 else 'FAIL',
            'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
            'skipped': len(result.skipped), 'controls': roster, 'controls_are_declared_roster': True,
            'generated_fixture_write_bytes': controls.WRITTEN_FIXTURE_BYTES,
            'generated_fixture_file_read_bytes': controls.FIXTURE_FILE_READ_BYTES,
            'original_inputs_read': False, 'actual_fit': False, 'actual_score': False,
            'model_packages_imported': [name for name in ('jax', 'jaxley', 'tensorflow', 'torch') if name in sys.modules]}
        reporting.require(raw['status'] == 'PASS' and not raw['model_packages_imported'],
                          'all eight unchanged controls must complete without model packages')
        report = {'status': 'PASS', 'controls': EXPECTED_IDS, 'scientific_result': raw, 'entry': entry}
        code = 0
    except Exception as error:
        report = {'status': 'FAIL', 'controls': [], 'error': reporting.bounded_error(error),
                  'scientific_result': raw, 'entry': entry, 'trace_observed_check_labels': [],
                  'trace_labels_are_completed_controls': False}
        code = 1
    reporting.write_worker_report(report_fd, report)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--artifacts', help='one absent artifact leaf outside the checkout')
    mode.add_argument('--worker-report-fd', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--worker-artifacts', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    reporting, unused_helper_root = _reporter()
    package = os.path.dirname(os.path.abspath(__file__))
    if args.worker_report_fd is not None:
        reporting.require(args.worker_artifacts is not None, 'internal artifact workspace required')
        return _worker(reporting, package, args.worker_artifacts, args.worker_report_fd)
    reporting.require(args.worker_artifacts is None, 'internal workspace is not a public option')
    repo = str(Path(package).parents[4])
    leaf = os.path.abspath(args.artifacts)
    reporting.require(os.path.commonpath([repo, leaf]) != repo, 'artifacts must be outside the checkout')
    command = [sys.executable, '-I', '-B', os.path.join(package, os.path.basename(__file__)),
               '--worker-artifacts', leaf]
    return reporting.transport(command, leaf, EXPECTED_IDS, timeout_seconds=55.0)


if __name__ == '__main__':
    raise SystemExit(main())

"""Official APCx Parquet -> exact accepted prepared inputs, owner-side only.

Requires separately admitted installed runtime files. Performs no download,
installation, fit, candidate execution, subprocess launch, or source-cohort cut.
"""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parent))

import task
import participant_core
import json_interface
from apcx_original import native_io
from apcx_original import native_scan
from apcx_original import runtime_guard

MIB = 1024**2


def specification():
    path = Path(__file__).absolute().with_name('official-input.json')
    cfg = json_interface.decode(path.read_bytes(), 65536)
    task.need(cfg['schema'] == 'apcx-official-input-conversion-v1', 'official source specification')
    task.need(cfg['native_limits']['layout_scope'] == {
        'rows': 95072, 'trials': 10831, 'sessions': 43,
        'session_unit_pairs': 383, 'command_samples': 7500}, 'complete immutable scope')
    task.need(cfg['official_input']['sha256'] ==
        '83193081d7486e95590f1599cc20943f702d05d2d1ccf4f124038a5f86598598', 'canonical original entity')
    return cfg


def admitted_runtime(path, expected_sha, budget):
    task.need(type(expected_sha) is str and task.boundary.HEX.fullmatch(expected_sha),
              'explicit independently admitted runtime manifest hash')
    body = task.read_bytes(path, budget, 4*MIB)
    task.need(hashlib.sha256(body).hexdigest() == expected_sha, 'runtime manifest whole hash')
    manifest = json_interface.decode(body, 4*MIB)
    expected_host = {'sys_platform': sys.platform, 'machine': platform.machine(),
                     'python': platform.python_version()}
    task.need(manifest['portable_host'] == expected_host, 'exact admitted native host')
    task.need(len(manifest['packages']) == 2, 'complete declared Arrow/NumPy runtime')
    expected_records = {'pyarrow-24.0.0.dist-info', 'numpy-2.4.6.dist-info'}
    task.need({Path(p['record']['path']).parent.name for p in manifest['packages']} == expected_records,
              'fixed native transformation package versions')
    task.need(Path(manifest['site_packages']).is_absolute(), 'admitted runtime root')
    return manifest


def verify_result(result):
    task.need(result['status'] == 'COMPLETE_NATIVE_RELEASE_CENSUS_WITH_SCIENTIFIC_HOLDS'
              and result['rows'] == 95072 and result['released_trials'] == 10831
              and result['released_sessions'] == 43
              and result['rows_without_groupable_released_identity'] == 0
              and result['all_columns_and_rows_scanned'] is True
              and result['holds'] == list(participant_core.HOLDS), 'whole released census with all seven holds')
    shared = result['shared_command_layout']
    task.need(shared['diagnostic_records'] == 10822 and shared['distinct_released_trial_keys'] == 10831
              and shared['rows'] == 95072 and shared['trial_records'] == 10831
              and shared['trial_keys_with_diagnostic_variants'] == 0,
              'whole lossless diagnostic/trial scope')
    commands = result['command_reconciliation']
    task.need(commands['status_counts'] == {
        'COMPATIBLE_CONDITIONAL_COMMAND_MODEL_NOT_PHYSICAL_DELIVERY': 87266, 'UNRESOLVED': 7806}
        and commands['original_legacy_row_flags'] == {
        'COMMAND_AMPLITUDE_NOT_EXACT_SOURCE_ZERO_OR_100': 44754,
        'COMMAND_RUN_NOT_ONE_50_SAMPLE_PULSE': 3150}, 'all unresolved and original flags preserved')
    task.need(result['models'] == 0 and result['fits'] == 0 and result['scientific_admission'] is False,
              'construction only')


def convert(args):
    cfg = specification()
    task.need(sys.platform in ('darwin', 'linux') and tuple(sys.version_info[:3]) == (3,11,6),
              'exact CPython3.11.6 POSIX transformation runtime')
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'ARROW_NUM_THREADS'):
        task.need(os.environ.get(key) == '1', 'set native thread limits before process start')
    source_path = task.absolute(args.parquet)
    native_io.ordinary(source_path, cfg['official_input']['bytes'])
    budget = native_io.Budget(cfg['managed_limits'], time.monotonic()+cfg['worker_seconds'])
    manifest = admitted_runtime(args.runtime_manifest, args.runtime_manifest_sha256, budget)
    output = task.fresh_directory(args.output)
    store = native_io.OutputStore(output, budget, cfg['per_file_bytes'])
    source = {'path': str(source_path), **{k: cfg['official_input'][k] for k in ('bytes','md5','sha256')}}
    runtime_before = runtime_after = result = None
    errors = []
    try:
        allowed, runtime_before = runtime_guard.verify_runtime(manifest, budget)
        pa, pq = runtime_guard.activate(manifest, allowed, output)
        # The accepted scanner hashes the full original before constructing a
        # ParquetFile and again after reading every column and row.
        result = native_scan.scan_file(pa, pq, source, cfg['native_limits'], budget, store)
        verify_result(result)
    except BaseException as exc:
        errors.append({'stage': 'complete_original_conversion', 'type': type(exc).__name__,
                       'message': str(exc)[:2048]})
    finally:
        if runtime_before is not None:
            try:
                _, runtime_after = runtime_guard.verify_runtime(manifest, budget)
                task.need(runtime_after == runtime_before, 'runtime changed during native conversion')
            except BaseException as exc:
                errors.append({'stage': 'runtime_postflight', 'type': type(exc).__name__,
                               'message': str(exc)[:2048]})
    if errors:
        # If the deadline/cap prevents even this receipt, the output still lacks
        # the completion manifest and must remain failed/partial.
        store.json('FAILED.json', {'status': 'FAILED_NO_COMPLETE_BRIDGE', 'errors': errors,
                                  'remaining_holds': list(participant_core.HOLDS)})
        raise ValueError('Complete native conversion failed; preserved output cannot be used as accepted inputs')
    task.check(budget)  # Include late native/runtime allocations before output admission.
    inventory = native_io.inventory_outputs(store)
    pins = {x['name']: {k:x[k] for k in ('bytes','sha256')} for x in inventory['files']}
    for name, expected in cfg['expected_bridge'].items():
        task.need(pins.get(name) == expected, 'complete prepared bridge differs: '+name)
    receipt = {'schema': 'apcx-official-input-complete-bridge-v1',
        'status': 'COMPLETE_EXACT_PREPARED_BRIDGE_WITH_SCIENTIFIC_HOLDS',
        'official_input': {k:cfg['official_input'][k] for k in ('name','bytes','md5','sha256','unsigned_url','versioned_record','license')},
        'runtime_manifest_sha256': args.runtime_manifest_sha256,
        'runtime_before': runtime_before, 'runtime_after': runtime_after,
        'complete_output_inventory': inventory, 'exact_prepared_bridge': cfg['expected_bridge'],
        'remaining_holds': list(participant_core.HOLDS), 'rows': 95072,
        'trials': 10831, 'sessions': 43, 'session_unit_pairs': 383,
        'managed_counters_before_final_receipt': budget.used,
        'models': 0, 'fits': 0, 'candidate_execution': False,
        'scientific_qualification': False, 'new_benchmark_count': 0,
        'note': 'Final receipt excludes its own write counter; independent terminal/output review remains required.'}
    return write_bridge(store, receipt, budget)


def write_bridge(store, receipt, budget):
    """A retained file is not success if either late resource checkpoint fails."""
    encoded = participant_core.canonical(receipt)
    task.check(budget)
    store.json('NATIVE_BRIDGE.json', receipt)
    task.check(budget)
    return {'manifest': 'NATIVE_BRIDGE.json', 'bytes': len(encoded),
            'sha256': hashlib.sha256(encoded).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parquet', required=True)
    p.add_argument('--runtime-manifest', required=True)
    p.add_argument('--runtime-manifest-sha256', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    print(json_interface.json.dumps(convert(args), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

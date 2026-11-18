"""Separate current CPU qualification suite; no installation or native work on import.

An independently pinned, trusted installation receipt is mandatory. This file
never fabricates VCS metadata or treats source-only controls as runtime success.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import importlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import re
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest

CONDITION = 'nuclr-current-cpu-source-wheels-v1'
PROFILE_SHA256 = '8dd946c9dd6c555b8e8d4851ad0393989874cb7ef4926df410cdb3ff8a63e382'
LOCAL_PINS = {
    'legacy': ('official-serialization-v1/hosted_original_runtime.py', '57a786aaa9ae19c1696023f481d8810364abb4bbdeb6a6a9ee89e57884675fbc'),
    'bridge': ('temporaldata-bridge-v1/bridge.py', 'e6548b3ef63c007056899407ac81159731d2265e19af4b6f490a6f5d96ecd4f7'),
    'serializer': ('official-serialization-v1/serializer.py', 'e0ab2ade4480b7f510edf6b13895ed2ae6c214e3f4f51f2ede2b6e041cd32b3e'),
    'plan': ('window-plan-v1/plan.py', '04917dd7e5d19c18abf55e2727941f3fa513f38863001c1f247b1e0b835e93c0'),
}
INHERITED = (
    'test_real_hdf5_roundtrip_and_description_defaults',
    'test_gap_union_lazy_half_open_end_and_origin_reset',
    'test_original_dataset_layout_ids_and_sequential_tail',
    'test_real_raw_column_assignment_leaves_normalized_input_unchanged',
)
FIFTH = 'test_generated_window_plan_matches_original_sampler'
METHODS = INHERITED + (FIFTH,)
SOURCE_PROJECTS = {'temporaldata', 'brainsets', 'pytorch-brain', 'antlr4-python3-runtime'}
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def name(value):
    return re.sub(r'[-_.]+', '-', value).lower()


def _hex(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'SHA256 required')
    return value


def read_json(path, expected_sha256, maximum):
    p = Path(path)
    need(p.is_file() and not p.is_symlink() and p.stat().st_size <= maximum, 'bounded regular receipt required')
    body = p.read_bytes()
    need(hashlib.sha256(body).hexdigest() == _hex(expected_sha256), 'independently pinned receipt/source mismatch')
    return json.loads(body)


def load_frozen(path, expected_sha256, module_name):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024, 'bounded frozen source required')
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == expected_sha256, 'frozen source differs: ' + str(path))
    module = ModuleType(module_name)
    module.__file__ = str(path)
    need(module_name not in sys.modules, 'frozen module namespace already occupied')
    sys.modules[module_name] = module
    try:
        exec(compile(body, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[module_name]
        raise
    return module


def expected_versions(profile, receipt):
    need(profile.get('schema') == 'nuclr-current-cpu-profile/v1' and profile.get('condition') == CONDITION,
         'wrong frozen current profile')
    expected = dict(profile['external_versions'])
    need(len(expected) == 71 and expected['setuptools'] == '68.2.2', 'all71 runtime pins required')
    for project, row in profile['source_distributions'].items():
        current = receipt['distributions'][project]
        version = row['version']
        if version is None:
            version = current.get('version')
            need(type(version) is str and bool(version), 'actual backend-derived brainsets version required')
        expected[project] = version
    need(len(expected) == 74 and profile['distribution_count'] == 74, 'exact74 distribution roster required')
    return expected


def validate_receipt(profile, receipt):
    """Pure schema/provenance admission, before installed paths or package imports.

    The outer caller must authenticate this operator-owned receipt by its frozen
    hash. It is not a participant-supplied self-attestation or a build-only log.
    """
    need(receipt.get('schema') == 'nuclr-installed-current-runtime/v1' and
         receipt.get('condition') == CONDITION and receipt.get('status') == 'qualified_installation',
         'genuine current installation qualification receipt required')
    need(receipt.get('profile_sha256') == PROFILE_SHA256, 'current profile differs')
    need(receipt.get('historical_environment_qualified') is False and
         receipt.get('scientific_result') is False, 'unsupported scientific/historical claim')
    for key in ('complete_artifact_roster_verified', 'wheel_record_and_abi_verified',
                'complete_installed_source_identity_verified', 'genuine_source_builds_verified',
                'frontend_cli_verified', 'runtime_dependencies_verified',
                'brainsets_complete98_git_context_verified', 'no_module_stubs',
                'network_egress_disabled', 'owned_resource_guards_verified'):
        need(receipt.get(key) is True, 'missing external qualification: ' + key)
    for key in ('installation_receipt_sha256', 'source_materialization_receipt_sha256',
                'frontend_receipt_sha256', 'resource_admission_sha256', 'runtime_artifact_manifest_sha256'):
        _hex(receipt.get(key))
    need(type(receipt.get('distributions')) is dict and len(receipt['distributions']) == 74,
         'complete trusted installed distribution roster required')
    expected = expected_versions(profile, receipt)
    need(set(receipt['distributions']) == set(expected), 'installed roster differs')
    builds = receipt.get('builds')
    need(type(builds) is dict and set(builds) == SOURCE_PROJECTS, 'four genuine source builds required')
    for project, build in builds.items():
        need(build.get('status') == 'success' and build.get('backend') == 'setuptools.build_meta',
             'source build not qualified: ' + project)
        _hex(build.get('receipt_sha256'))
        _hex(build.get('wheel_sha256'))
        need(build.get('version') == expected[project], 'build/installed version differs')
        if project == 'antlr4-python3-runtime':
            need(build.get('source_sdist_sha256') == 'f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b',
                 'ANTLR original source differs')
        else:
            need(build.get('source_commit') == profile['source_distributions'][project]['commit'],
                 'original source commit differs: ' + project)
    known = dict(profile['known_wheel_sha256'])
    known.update(profile['preserved_inherited_wheel_sha256'])
    for project, row in receipt['distributions'].items():
        need(row.get('version') == expected[project], 'installed version differs: ' + project)
        _hex(row.get('wheel_sha256'))
        if project in builds:
            need(row['wheel_sha256'] == builds[project]['wheel_sha256'], 'source build/install wheel differs')
        elif project in known:
            need(row['wheel_sha256'] == known[project], 'retained original wheel pin differs: ' + project)
        else:
            raise RuntimeError('unbound external artifact: ' + project)
        files = row.get('files')
        need(type(files) is dict and files and len(files) <= 100000, 'complete installed file identities required')
        for relative, identity in files.items():
            need(type(relative) is str and relative and not Path(relative).is_absolute(), 'relative installed file required')
            need(type(identity) is dict and type(identity.get('bytes')) is int and identity['bytes'] >= 0,
                 'file extent required')
            _hex(identity.get('sha256'))
    env = receipt.get('environment', {})
    need(env.get('python_version') == '3.11.18' and env.get('implementation') == 'CPython' and
         env.get('system') == 'Linux' and env.get('machine') == 'x86_64', 'exact current CPU platform required')
    for key in ('python_executable_sha256', 'runner_identity_sha256'):
        _hex(env.get(key))
    need(type(env.get('glibc')) is list and len(env['glibc']) == 2 and all(type(v) is str and v for v in env['glibc']),
         'actual glibc identity required')
    need(type(env.get('linked_hdf5_version')) is str and env['linked_hdf5_version'], 'actual linked HDF5 required')
    return expected


def authenticate_installed(profile, receipt, legacy):
    expected = validate_receipt(profile, receipt)
    env = receipt['environment']
    need((platform.python_version(), platform.python_implementation(), platform.system(), platform.machine()) ==
         (env['python_version'], env['implementation'], env['system'], env['machine']), 'observed platform differs')
    need(sha(sys.executable) == env['python_executable_sha256'] and list(platform.libc_ver()) == env['glibc'],
         'actual Python/libc differs')
    distributions = {}
    for dist in importlib.metadata.distributions():
        key = name(dist.metadata['Name'])
        need(key not in distributions, 'duplicate distribution: ' + key)
        distributions[key] = dist
    need(set(distributions) == set(expected), 'actual installed distribution roster differs')
    prefix = Path(sys.prefix).resolve(strict=True)
    for key, dist in distributions.items():
        row = receipt['distributions'][key]
        need(dist.version == expected[key], 'observed distribution version differs: ' + key)
        installed = {str(p) for p in (dist.files or ())}
        need(installed == set(row['files']), 'complete installed file roster differs: ' + key)
        direct = json.loads(dist.read_text('direct_url.json') or 'null')
        need(not isinstance(direct, dict) or ('vcs_info' not in direct and
             direct.get('dir_info', {}).get('editable') is not True), 'do not fabricate VCS/editable provenance')
        for relative, identity in row['files'].items():
            path = Path(dist.locate_file(relative))
            need(path.is_file() and not path.is_symlink(), 'installed file missing or symlinked')
            path = path.resolve(strict=True)
            need(path.is_relative_to(prefix), 'installed file escapes qualified environment')
            need(path.stat().st_size == identity['bytes'] and sha(path) == identity['sha256'], 'installed file changed')
    paths = {}
    for module, (old_dist, relative, digest) in legacy.SOURCE_FILES.items():
        key = 'pytorch-brain' if old_dist == 'torch-brain' else old_dist
        path = Path(distributions[key].locate_file(relative)).resolve(strict=True)
        need(sha(path) == digest, 'fixed original source differs: ' + module)
        paths[module] = path
    modules = {key: importlib.import_module(key) for key in (
        'numpy', 'h5py', 'omegaconf', 'temporaldata', 'brainsets.taxonomy',
        'brainsets.descriptions', 'brainsets.core', 'torch_brain.data.dataset', 'torch_brain.data.sampler')}
    for module, expected_path in paths.items():
        loaded = importlib.import_module(module)
        need(Path(loaded.__file__).resolve(strict=True) == expected_path, 'source module shadowed: ' + module)
        need(sha(loaded.__file__) == legacy.SOURCE_FILES[module][2], 'loaded original source changed')
    for module_name, module in modules.items():
        path = Path(module.__file__).resolve(strict=True)
        root_name = module_name.split('.')[0]
        dist_name = {'torch_brain':'pytorch-brain', 'omegaconf':'omegaconf'}.get(root_name, root_name)
        need(any(Path(distributions[dist_name].locate_file(rel)).resolve(strict=True) == path
                 for rel in receipt['distributions'][dist_name]['files']), 'package root shadows installed manifest')
    need(modules['temporaldata'].__version__ == '0.1.1', 'preserve temporaldata module/distribution distinction')
    need(modules['h5py'].version.hdf5_version == env['linked_hdf5_version'], 'actual linked HDF5 differs')
    td, desc, core = modules['temporaldata'], modules['brainsets.descriptions'], modules['brainsets.core']
    return SimpleNamespace(
        np=modules['numpy'], h5py=modules['h5py'], omegaconf=modules['omegaconf'],
        Data=td.Data, ArrayDict=td.ArrayDict, IrregularTimeSeries=td.IrregularTimeSeries,
        Interval=td.Interval, Species=modules['brainsets.taxonomy'].Species,
        BrainsetDescription=desc.BrainsetDescription, SubjectDescription=desc.SubjectDescription,
        SessionDescription=desc.SessionDescription, serialize_fn_map=core.serialize_fn_map,
        Dataset=modules['torch_brain.data.dataset'].Dataset,
        SequentialFixedWindowSampler=modules['torch_brain.data.sampler'].SequentialFixedWindowSampler,
        provenance={'condition': CONDITION, 'installation_receipt_sha256': receipt['installation_receipt_sha256'],
                    'historical_environment_qualified': False}, installation_authenticated=True, runtime_qualified=False)


def manifest_from_clocks(clock_cases, neurons=4):
    """Generated already-shifted clock metadata, never observed sampler/cache output."""
    sessions = []
    for sid, clocks in clock_cases:
        experiments, cursor, previous = [], 0, None
        for index, clock in enumerate(clocks):
            need(clock and len(clock) <= 120 and all(math.isfinite(float(v)) for v in clock), 'finite generated clocks required')
            start, end = float(clock[0]), float(clock[-1])
            need(all(float(a) <= float(b) for a, b in zip(clock, clock[1:])), 'generated clocks must be ordered')
            experiments.append({'experiment_id': 'Generated/' + str(index + 1), 'frames': len(clock),
                'row_start': cursor, 'row_stop': cursor + len(clock), 'source_offset_seconds': index * 3600,
                'shifted_first_second': start, 'shifted_last_second': end,
                'gap_from_previous_seconds': None if previous is None else start - previous})
            cursor += len(clock); previous = end
        sessions.append({'session_id': sid, 'neurons': neurons, 'frames': cursor, 'experiments': experiments})
    return {'sessions': sessions}


def configuration():
    return {'world_size':1, 'rank':0, 'context_seconds':30.0, 'limit_observation_time':None,
            'dataset_config':[{'selection':[{'brainset':'bugeon_transcriptomic_2022'}], 'config':{}}],
            'split':None, 'batch_size':2, 'num_workers':0, 'checkpoint_epochs':list(range(30))}


def window_rows(sampler):
    rows = [(i.recording_id, float(i.start).hex(), float(i.end).hex()) for i in sampler]
    need(len(rows) <= 256, 'generated window bound exceeded')
    return rows


def check_fifth(case):
    runtime, plan = case.runtime, case.window_plan
    # Independent fixed arithmetic metadata; no HDF5/source fixture is used to
    # determine its endpoints or ordering, and no observed sampler is read here.
    clocks = [('sb002_20200102', [list(range(41))]),
              ('sb001_20200101', [list(range(66)), list(range(3600, 3613))])]
    metadata = manifest_from_clocks(clocks)
    _, units, domains, windows, _ = plan._construct(metadata, configuration(), runtime, max_windows=256)
    wanted = [(r['recording_id'], float(r['start']).hex(), float(r['end']).hex()) for r in windows]
    config = runtime.omegaconf.OmegaConf.create(configuration()['dataset_config'])
    dataset = runtime.Dataset(str(case.root), config=config, split=None, unit_id_prefix_fn=lambda _: '')
    try:
        intervals = dataset.get_sampling_intervals()
        observed = runtime.SequentialFixedWindowSampler(sampling_intervals=intervals, window_length=30.0,
                                                         step=None, drop_short=True)
        case.assertEqual(window_rows(observed), wanted)
        case.assertEqual(len(observed), len(wanted))
        case.assertEqual(list(dataset.recording_dict), [row['recording_id'] for row in domains])
        case.assertEqual(dataset.get_unit_ids(), [u for values in units.values() for u in values])
        actual_domains = [{'recording_id':rid, 'intervals':[[float(a),float(b)] for a,b in zip(iv.start,iv.end)]}
                          for rid, iv in intervals.items()]
        case.assertEqual(actual_domains, domains)
        case.assertEqual(Counter(r[0] for r in wanted), Counter(r[0] for r in window_rows(observed)))
    finally:
        dataset._close_open_files()
    # <=32 direct sparse clock rows, including duplicates/nonintegers, touching
    # domains, a gap, short span and overlapping tail. No dense 3600-second array.
    sparse = [('sb003_20200103', [[0.125,0.125,40.125], [40.125,60.125,80.125], [3600.5,3610.5]]),
              ('sb004_20200104', [[0.25,30.25,65.25], [3600.75,3635.75]])]
    case.assertLessEqual(sum(len(c) for _, blocks in sparse for c in blocks), 32)
    _, expected_units, expected_domains, expected_windows, _ = plan._construct(
        manifest_from_clocks(sparse), configuration(), runtime, max_windows=256)
    # Separate explicitly specified real Interval objects; never copy domains
    # returned by the metadata constructor into the observed source sampler.
    intervals = {
        'bugeon_transcriptomic_2022/sb003_20200103':
            (runtime.Interval(0.125,40.125) | runtime.Interval(40.125,80.125) | runtime.Interval(3600.5,3610.5)),
        'bugeon_transcriptomic_2022/sb004_20200104':
            (runtime.Interval(0.25,65.25) | runtime.Interval(3600.75,3635.75)),
    }
    observed = runtime.SequentialFixedWindowSampler(sampling_intervals=intervals, window_length=30.0,
                                                     step=None, drop_short=True)
    expected = [(r['recording_id'], float(r['start']).hex(), float(r['end']).hex()) for r in expected_windows]
    case.assertEqual(window_rows(observed), expected)
    case.assertEqual(len(observed), len(expected))
    actual_domains = [{'recording_id':rid, 'intervals':[[float(a),float(b)] for a,b in zip(iv.start,iv.end)]}
                      for rid, iv in intervals.items()]
    case.assertEqual(actual_domains, expected_domains)
    case.assertEqual(expected_units, {rid:[rid.split('/')[1] + '_u' + str(i) for i in range(4)] for rid in intervals})
    case.assertEqual(Counter(r[0] for r in window_rows(observed)), Counter(r[0] for r in expected))


def _current_class(legacy, setup):
    class CurrentCpuControls(legacy.OriginalRuntimeControls):
        @classmethod
        def setUpClass(cls):
            setup(cls)

        def test_generated_window_plan_matches_original_sampler(self):
            check_fifth(self)

    for method in INHERITED:
        need(getattr(CurrentCpuControls, method) is getattr(legacy.OriginalRuntimeControls, method),
             'inherited genuine assertion changed: ' + method)
    need(set(unittest.TestLoader().getTestCaseNames(CurrentCpuControls)) == set(METHODS),
         'exactly four inherited plus one new genuine method required')
    return CurrentCpuControls


def _fixture_setup(cls, legacy, local, profile, receipt):
    cls.bridge = local['bridge']
    cls.runtime = authenticate_installed(profile, receipt, legacy)
    cls.serializer = local['serializer']
    cls.window_plan = local['plan']
    # Only setup is overridden. Same helper, specifications, construction order,
    # two drivers, bounds and accounting as the unchanged inherited setup.
    cls.tmp = tempfile.TemporaryDirectory(prefix='nuclr-current-generated-real-runtime-')
    cls.addClassCleanup(cls.tmp.cleanup)
    cls.root = Path(cls.tmp.name)
    cls.directory = cls.root / legacy.BRAINSET
    cls.directory.mkdir()
    cls.specifications = [('sb002_20200102', [(0,40)]), ('sb001_20200101', [(0,65),(3600,3612)])]
    cls.fixture = {}
    cls.budget = cls.serializer.WriteBudget(legacy.MIB)
    cls.bounded_extent = cls.direct_extent = None
    for index, (sid, spans) in enumerate(cls.specifications):
        data, raw, normalized, timestamps = legacy._fixture(cls.bridge, cls.runtime, sid, spans)
        cls.fixture[sid] = data, raw, normalized, timestamps
        path = cls.directory / (sid + '.h5')
        if index == 0:
            with path.open('x+b', buffering=0) as raw_file:
                bounded = cls.serializer.BoundedFile(raw_file, cls.budget)
                try:
                    with cls.runtime.h5py.File(bounded, 'w', driver='fileobj') as file:
                        data.to_hdf5(file, serialize_fn_map=cls.runtime.serialize_fn_map)
                    bounded.flush()
                finally:
                    bounded.close()
            cls.bounded_extent = path.stat().st_size
        else:
            with cls.runtime.h5py.File(path, 'x') as file:
                data.to_hdf5(file, serialize_fn_map=cls.runtime.serialize_fn_map)
            cls.direct_extent = path.stat().st_size
        need(0 < path.stat().st_size <= legacy.MIB, 'generated HDF5 fixture exceeds reviewed extent')


def build_suite(implementations, receipt_path, receipt_sha256):
    profile = read_json(Path(__file__).with_name('current_profile.json'), PROFILE_SHA256, 65536)
    receipt = read_json(receipt_path, receipt_sha256, MAX_RECEIPT_BYTES)
    validate_receipt(profile, receipt)
    root = Path(implementations)
    local = {key:load_frozen(root/relative, digest, '_nuclr_current_' + key)
             for key,(relative,digest) in LOCAL_PINS.items()}
    legacy = local['legacy']
    cls = _current_class(legacy, lambda cls:_fixture_setup(cls, legacy, local, profile, receipt))
    return unittest.TestSuite(cls(method) for method in METHODS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementations', type=Path, required=True)
    parser.add_argument('--installation-receipt', type=Path, required=True)
    parser.add_argument('--installation-receipt-sha256', required=True)
    args = parser.parse_args()
    suite = build_suite(args.implementations, args.installation_receipt, args.installation_receipt_sha256)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    need(result.testsRun == 5 and not result.skipped, 'exact five genuine outcomes and zero skips required')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()

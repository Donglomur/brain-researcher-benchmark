"""Proposed one-record authentic projection control. Never run on import.

This source alone grants no native/data authorization. A separately approved
native lease and artifact reservation must precede the supervise command.
"""
import argparse
import builtins
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time
import types

EDF = {'bytes': 42399744, 'sha256': '4c4a95a9b4331aeaadadd538763eb2e735950d9aa615b85ee6246c784be8ae90'}
HISTORICAL = {'bytes': 42568544, 'sha256': '6ebeeea5ee48d1d0e691be394bde4a96a49105b7ea999b999492f6f8b0c5d10f'}
ORIGINAL_MANIFEST = {'bytes': 1630, 'sha256': 'ad64dcbe1f9543725f2e4720ad974a608c512e8a2c833adad37dfd23119baef9'}
PYTHON = {'path': '/opt/homebrew/Cellar/python@3.11/3.11.6/Frameworks/Python.framework/Versions/3.11/bin/python3.11',
          'bytes': 52640, 'sha256': '4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1'}
DIST_INFO = [
    {'path': '/opt/homebrew/lib/python3.11/site-packages/numpy-2.4.6.dist-info/METADATA', 'bytes': 6608,
     'sha256': 'b082c52ccbe3b880bae177c35171b52ed6c947f3ad71e3762f2723f60a411de0'},
    {'path': '/opt/homebrew/lib/python3.11/site-packages/numpy-2.4.6.dist-info/RECORD', 'bytes': 127073,
     'sha256': 'a47e3969e70ac5f47798ae53b3ae42e922e280354f94090bfe8fe759e5078c6f'},
    {'path': '/opt/homebrew/lib/python3.11/site-packages/h5py-3.16.0.dist-info/METADATA', 'bytes': 3007,
     'sha256': 'e461fcf7eb9fee6242205f9225cc178455a0212d1c0cb8f997f7eebf8cd9695e'},
    {'path': '/opt/homebrew/lib/python3.11/site-packages/h5py-3.16.0.dist-info/RECORD', 'bytes': 12439,
     'sha256': 'afdcf1abd9b0f46118068e51417b8b61c7dd8c8f921907985f8c484fe3d8b44c'}]
ORIGINAL_NAMES = {'entry.py', 'prepare.py', 'storage.py', 'views.py', 'VENDOR_BINDINGS.json',
                  'vendor/edf_adapter.py', 'vendor/reconcile_annotations.py', 'vendor/io_contract.py',
                  'vendor/event_protocol.py', 'vendor/scorer.py'}
READ_LIMIT = 512 * 1048576
PROJECT_LIMIT = 2 * EDF['bytes'] + 8 * 1048576
OUTPUT_LIMIT = 96 * 1048576
LOG_LIMIT = 512 * 1024
META_LIMIT = 128 * 1024
NATIVE_IDENTITY_LIMIT = 32 * 1048576
DECLARED_RAM = 1024 * 1048576
WORKER_SECONDS = 120
CLEANUP_SECONDS = 10
WHOLE_SUPERVISOR_SECONDS = 140
THREAD_ENV = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode() + b'\n'


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def parse(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def bad(_):
        raise ValueError('nonfinite JSON')
    return json.loads(raw.decode(), object_pairs_hook=pairs, parse_constant=bad)


def canonical(value):
    need(type(value) is str and value.startswith('/') and not value.startswith('//')
         and '\x00' not in value and str(Path(value)) == value
         and all(x not in ('', '.', '..') for x in value.split('/')[1:]), 'canonical absolute path')
    p = Path(value)
    for part in [p, *p.parents]:
        need(not part.is_symlink(), 'no symlink component')
    return p


def stamp(p):
    s = canonical(str(p)).lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary single-link file')
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def sync_directory(p):
    fd = os.open(canonical(str(p)), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_once(p, body, cap=META_LIMIT):
    need(len(body) <= cap, 'bounded metadata output')
    fd = os.open(canonical(str(p)), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        remaining = memoryview(body)
        while remaining:
            n = os.write(fd, remaining)
            need(n > 0, 'complete create-only write')
            remaining = remaining[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_directory(p.parent)


class Reads:
    """Logical selected-body reservations; not measured C-library physical I/O."""
    def __init__(self):
        self.total = 0
        self.entries = []
    def reserve(self, name, count):
        need(type(count) is int and count >= 0 and self.total + count <= READ_LIMIT, 'logical read budget')
        self.total += count
        self.entries.append({'operation': name, 'reserved_bytes': count})


def captured(p, expected, reads, cap=1048576):
    need(type(expected['bytes']) is int and 0 < expected['bytes'] <= cap, 'bounded source metadata')
    reads.reserve('captured:' + p.name, expected['bytes'] + 1)
    before = stamp(p)
    need(before[2] == expected['bytes'], 'source metadata extent')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        data = bytearray()
        while len(data) <= expected['bytes']:
            chunk = os.read(fd, min(65536, expected['bytes'] + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        need(stamp(p) == before, 'source metadata immutable')
        raw = bytes(data)
        need(pin(raw) == expected, 'source metadata identity')
        return raw
    finally:
        os.close(fd)


def digest_file(p, cap, reads, expected=None):
    reads.reserve('hash:' + p.name, cap + 1)
    before = stamp(p)
    need(0 < before[2] <= cap, 'bounded payload extent')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    h, count = hashlib.sha256(), 0
    try:
        while count <= cap:
            chunk = os.read(fd, min(1048576, cap + 1 - count))
            if not chunk:
                break
            h.update(chunk)
            count += len(chunk)
        need(count == before[2] and count <= cap and stamp(p) == before, 'immutable complete payload')
    finally:
        os.close(fd)
    result = {'bytes': count, 'sha256': h.hexdigest()}
    need(expected is None or result == expected, 'fresh authentic payload hash')
    return result


def capture_worker_result(p, reads):
    """Capture under the fixed supervisor reservation persisted before launch."""
    need(any(r['operation'] == 'supervisor worker-result capture'
             and r['reserved_bytes'] == META_LIMIT + 1 for r in reads.entries),
         'result capture must be reserved before opening')
    before = stamp(p)
    need(0 < before[2] <= META_LIMIT, 'bounded worker-result extent')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        data = bytearray()
        while len(data) <= META_LIMIT:
            part = os.read(fd, min(65536, META_LIMIT + 1 - len(data)))
            if not part:
                break
            data.extend(part)
        need(len(data) == before[2] and len(data) <= META_LIMIT and stamp(p) == before,
             'worker-result immutable through bounded capture')
        return bytes(data)
    finally:
        os.close(fd)


def runtime_metadata(reads):
    need(platform.system() == 'Darwin' and platform.machine() == 'arm64'
         and sys.version_info[:3] == (3, 11, 6), 'selected local control runtime')
    actual = str(Path(sys.executable).resolve())
    need(actual == PYTHON['path'], 'selected canonical interpreter')
    captured(Path(actual), {k: PYTHON[k] for k in ('bytes', 'sha256')}, reads)
    for row in DIST_INFO:
        captured(Path(row['path']), {k: row[k] for k in ('bytes', 'sha256')}, reads)
    # These exact metadata bodies bind the selected installed distributions;
    # actual loaded versions are checked separately after the admitted imports.
    return {'interpreter': PYTHON, 'numpy_distribution': '2.4.6', 'h5py_distribution': '3.16.0',
            'native_imports_at_metadata_check': False,
            'complete_native_dependency_closure_qualified': False}


def original_projector(root, reads):
    raw = captured(root / 'SOURCE_MANIFEST.json', ORIGINAL_MANIFEST, reads)
    manifest = parse(raw)
    need(manifest['schema'] == 'neural010-preparation-runtime-sources-v1'
         and len(manifest['files']) == len(ORIGINAL_NAMES)
         and {r['name'] for r in manifest['files']} == ORIGINAL_NAMES, 'complete exact original source closure')
    bodies = {r['name']: captured(root / r['name'], {k: r[k] for k in ('bytes', 'sha256')}, reads)
              for r in manifest['files']}
    modules = {}
    normal = builtins.__import__
    def importer(name, globals=None, locals=None, fromlist=(), level=0):
        return modules[name] if name in modules else normal(name, globals, locals, fromlist, level)
    for name in ('event_protocol', 'edf_adapter'):
        mod = types.ModuleType('neural010_captured_' + name)
        mod.__file__ = str(root / 'vendor' / (name + '.py'))
        scope = dict(vars(builtins))
        scope['__import__'] = importer
        mod.__dict__['__builtins__'] = scope
        exec(compile(bodies['vendor/' + name + '.py'], mod.__file__, 'exec'), mod.__dict__)
        modules[name] = mod
    return modules['edf_adapter']


def loaded_runtime(np, h5py, reads):
    need(np.__version__ == '2.4.6' and h5py.__version__ == '3.16.0', 'actual loaded library versions')
    site = Path('/opt/homebrew/lib/python3.11/site-packages')
    for module, name in ((np, 'numpy'), (h5py, 'h5py')):
        need(Path(module.__file__).resolve().is_relative_to(site / name), 'selected loaded module origin')
    core = sys.modules.get('numpy._core._multiarray_umath')
    need(core is not None, 'actual NumPy core loaded')
    files = [Path(core.__file__).resolve(), Path(h5py.h5.__file__).resolve()]
    need(sum(stamp(p)[2] for p in files) <= NATIVE_IDENTITY_LIMIT, 'bounded selected native identity reads')
    identities = [{'path': str(p), **digest_file(p, stamp(p)[2], reads)} for p in files]
    return {'python_executable': str(Path(sys.executable).resolve()), 'python_version': sys.version,
            'numpy': {'version': np.__version__, 'module_path': np.__file__},
            'h5py': {'version': h5py.__version__, 'module_path': h5py.__file__,
                     'loaded_hdf5_version': h5py.version.hdf5_version},
            'selected_core_extension_identities': identities,
            'complete_transitive_native_dependency_closure_qualified': False,
            'legacy_reference_runtime_qualified': False}


def compare_projection(projected, historical, header, np, h5py, reads):
    """Every sample, plus exact semantic metadata; no score or annotations."""
    reads.reserve('two complete logical H5 comparison passes', 2 * PROJECT_LIMIT)
    old_stamp, new_stamp = stamp(historical), stamp(projected)
    names = {'eeg_digital', 'scale_to_microvolts', 'offset_microvolts', 'channel_labels', 'source_channel_index'}
    attributes = {'sample_rate_hz': 256, 'duration_seconds': 3600, 'schema_version': 1}
    selected = header['selected_channels']
    need(header['duration_seconds'] == 3600 and header['sample_rate_hz'] == 256
         and len(selected) == 23 and header['observed_intervals'] == [[0, 3600]],
         'complete known original recording geometry')
    need(header['source_channels'] == 23 and header['records'] == 3600
         and header['record_seconds'] == 1.0 and header['header_bytes'] == 6144
         and header['samples_per_source_record'] == [256] * 23
         and header['excluded_channels'] == [] and header['unsupported_intervals'] == []
         and header['interfile_gaps_included'] is False, 'complete source exposure and channel selection')
    expected = {'scale_to_microvolts': np.asarray([c['scale_to_microvolts'] for c in selected], dtype='<f8'),
                'offset_microvolts': np.asarray([c['offset_microvolts'] for c in selected], dtype='<f8'),
                'channel_labels': np.asarray([c['label'].encode() for c in selected], dtype='S32'),
                'source_channel_index': np.asarray([c['source_index'] for c in selected], dtype='<i2')}
    representations = {}
    with h5py.File(projected, 'r') as new, h5py.File(historical, 'r') as old:
        for kind, opened in (('new', new), ('historical', old)):
            need(set(opened.keys()) == names and set(opened.attrs) == set(attributes), 'exact projection members/attributes')
            attribute_types = {}
            for key, value in attributes.items():
                attribute = opened.attrs[key]
                attribute_id = opened.attrs.get_id(key)
                need(attribute_id.shape == () and attribute_id.dtype.kind in ('i', 'u')
                     and isinstance(attribute, (int, np.integer))
                     and not isinstance(attribute, (bool, np.bool_)) and int(attribute) == value,
                     'exact scalar integer projection attribute')
                attribute_types[key] = attribute_id.dtype.str
            for name in names:
                need(isinstance(opened.get(name, getlink=True), h5py.HardLink), 'no external/soft dataset links')
                dataset = opened[name]
                need(isinstance(dataset, h5py.Dataset) and not dataset.is_virtual
                     and dataset.external is None and dataset.compression is None
                     and not dataset.shuffle and not dataset.fletcher32 and dataset.scaleoffset is None,
                     'original plain dataset storage')
            need(opened['eeg_digital'].shape == (3600 * 256, 23)
                 and opened['eeg_digital'].dtype.str == '<i2'
                 and opened['eeg_digital'].chunks == (256, 23), 'full int16 signal geometry')
            for name, values in expected.items():
                dataset = opened[name]
                need(dataset.shape == values.shape and dataset.dtype == values.dtype,
                     'exact ordered metadata representation')
                need(np.array_equal(dataset[...], values), 'source-derived calibration/channel metadata')
            representations[kind] = {'dataset_dtypes': {n: opened[n].dtype.str for n in sorted(names)},
                                     'attribute_dtypes': attribute_types,
                                     'signal_chunks': list(opened['eeg_digital'].chunks)}
        samples = 0
        for start in range(0, 3600 * 256, 256):
            a = new['eeg_digital'][start:start + 256, :]
            b = old['eeg_digital'][start:start + 256, :]
            need(np.array_equal(a, b), 'exact complete int16 sample equality')
            samples += a.size
    need(stamp(historical) == old_stamp and stamp(projected) == new_stamp, 'comparison operands remained immutable')
    need(samples == 3600 * 256 * 23, 'every selected sample compared')
    return {'equal_int16_samples': samples, 'observed_seconds': 3600, 'sample_rate_hz': 256,
            'channels_including_order_and_duplicates': 23, 'sample_chunks': 3600,
            'calibration_and_source_indices_equal': True, 'required_attributes_equal': True,
            'actual_representations': representations,
            'hdf5_container_byte_identity_required': False}


def output_inventory(root):
    allowed = {'SUPERVISOR_INTENT.json', 'worker.log', 'projection.h5', 'CONTROL_RESULT.json',
               'WORKER_FAILURE.json', 'SUPERVISOR_RESULT.json'}
    files = []
    for p in root.iterdir():
        need(p.name in allowed, 'unexpected output member')
        s = stamp(p)
        cap = PROJECT_LIMIT if p.name == 'projection.h5' else LOG_LIMIT if p.name == 'worker.log' else META_LIMIT
        need(s[2] <= cap, 'individual output bound')
        files.append({'name': p.name, 'bytes': s[2]})
    need(sum(r['bytes'] for r in files) <= OUTPUT_LIMIT, 'combined output bound')
    return files


def worker(args):
    reads = Reads()
    root, source, historical = (canonical(getattr(args, n)) for n in ('output', 'edf', 'historical'))
    intent = parse(captured(root / 'SUPERVISOR_INTENT.json',
        {'bytes': args.intent_bytes, 'sha256': args.intent_sha256}, reads, META_LIMIT))
    need(os.getppid() == intent['supervisor_pid'] == args.supervisor_pid,
         'worker must be launched by its supervising parent')
    need(intent['operands'] == {'edf': str(source), 'historical': str(historical),
                              'original_source_root': args.original_source_root, 'output': str(root)},
         'exact supervised operands')
    reads.reserve('supervisor metadata and control-source reads', intent['supervisor_read_reserved_bytes'])
    captured(Path(__file__).resolve(), intent['control_source'], reads, 1048576)
    # CPU and file-size limits are hard kernel guards. RAM remains declared;
    # the independent native lease must inspect available resources/actual RSS.
    resource.setrlimit(resource.RLIMIT_CPU, (90, 95))
    resource.setrlimit(resource.RLIMIT_FSIZE, (PROJECT_LIMIT, PROJECT_LIMIT))
    try:
        runtime = runtime_metadata(reads)
        before_edf, before_old = stamp(source), stamp(historical)
        need(before_edf[2] == EDF['bytes'] and before_old[2] == HISTORICAL['bytes'], 'selected original extents')
        digest_file(historical, HISTORICAL['bytes'], reads, HISTORICAL)
        producer = original_projector(canonical(args.original_source_root), reads)
        import numpy as np
        import h5py
        loaded = loaded_runtime(np, h5py, reads)
        destination = canonical(str(root / 'projection.h5'))
        need(not os.path.lexists(destination), 'fresh native projection')
        reads.reserve('unchanged original EDF verify/header/project', 3 * EDF['bytes'] + 1)
        header = producer.project(source, destination, EDF)
        need(stamp(source) == before_edf and stamp(historical) == before_old, 'originals immutable through projection')
        fd = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        sync_directory(root)
        projected_pin = digest_file(destination, PROJECT_LIMIT, reads)
        comparison = compare_projection(destination, historical, header, np, h5py, reads)
        need(stamp(source) == before_edf and stamp(historical) == before_old, 'sources immutable through complete control')
        result = {'schema': 'neural010-one-record-projection-control-v1',
            'status': 'one_record_semantic_projection_control_passed_incomplete_cohort',
            'source_record': 'chb01/chb01_03.edf', 'source': EDF, 'historical_projection': HISTORICAL,
            'new_projection': projected_pin, 'original_source_manifest': ORIGINAL_MANIFEST,
            'source_header': header, 'comparison': comparison,
            'runtime_metadata_check': runtime, 'loaded_runtime': loaded,
            'logical_read_reservations': reads.entries, 'logical_read_reserved_bytes': reads.total,
            'logical_read_limit_bytes': READ_LIMIT, 'physical_native_io_measured': False,
            'worker_peak_rss_bytes_on_selected_darwin': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'declared_ram_bytes': DECLARED_RAM, 'os_rss_hard_limit': False,
            'prepared_original_records': 1, 'required_original_records': 686,
            'full_cohort_prepared': False, 'private_key_reads': 0, 'annotation_reads': 0,
            'models_or_scores': 0, 'detector_execution': False, 'scientific_or_runtime_readiness': False}
        need(result['worker_peak_rss_bytes_on_selected_darwin'] <= DECLARED_RAM, 'observed worker RAM exceeded declaration')
        write_once(root / 'CONTROL_RESULT.json', encode(result))
        output_inventory(root)
        return 0
    except BaseException as exc:
        failure = {'schema': 'neural010-one-record-control-failure-v1', 'error_type': type(exc).__name__,
                   'error': str(exc)[:2000], 'logical_read_reserved_bytes': reads.total,
                   'logical_read_reservations': reads.entries, 'partial_outputs_preserved': True,
                   'full_cohort_prepared': False, 'no_automatic_retry': True}
        if not (root / 'WORKER_FAILURE.json').exists():
            write_once(root / 'WORKER_FAILURE.json', encode(failure))
        return 1


def run_supervised(command, cwd, log_path, *, wall_seconds=WORKER_SECONDS,
                   cleanup_seconds=CLEANUP_SECONDS, log_limit=LOG_LIMIT, environment=None):
    """Bounded owned process group. Generic parameters exist for small controls."""
    need(wall_seconds > 0 and cleanup_seconds > 0 and 0 < log_limit <= LOG_LIMIT, 'bounded supervisor parameters')
    start = time.monotonic()
    fd = os.open(canonical(str(log_path)), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    proc = None
    selector = selectors.DefaultSelector()
    retained = emitted = 0
    reason = None
    prior_handlers = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt('supervisor signal ' + str(signum))
    def signal_group(sig):
        if proc is not None:
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass
    try:
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            prior_handlers[sig] = signal.signal(sig, interrupted)
        proc = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=True, close_fds=True)
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            if time.monotonic() - start >= wall_seconds:
                reason = 'worker_wall_deadline'
                break
            ready = selector.select(min(0.1, max(0, wall_seconds - (time.monotonic() - start))))
            for key, _ in ready:
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                emitted += len(chunk)
                keep = chunk[:max(0, log_limit - retained)]
                remaining = memoryview(keep)
                while remaining:
                    n = os.write(fd, remaining)
                    need(n > 0, 'complete bounded log write')
                    remaining = remaining[n:]
                    retained += n
                if emitted > log_limit:
                    reason = 'worker_output_limit'
                    break
            if reason is not None or (proc.poll() is not None and not selector.get_map()):
                break
    except BaseException as exc:
        reason = 'supervisor_' + type(exc).__name__
    finally:
        # Always stop only this owned process group, including natural-parent-exit
        # descendants. The selected original producer does not spawn processes.
        cleanup_start = time.monotonic()
        cleanup_signals = []
        cleanup_handlers = {}
        alarm_before = signal.getitimer(signal.ITIMER_REAL)
        # A whole-attempt alarm must not abort the finally block before SIGKILL.
        # Pause it only across independently bounded cleanup, then restore the
        # original absolute deadline (never a new full allowance).
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGALRM):
            cleanup_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, lambda signum, frame: cleanup_signals.append(signum))
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            signal_group(signal.SIGTERM)
            if proc is not None:
                try:
                    proc.wait(timeout=min(2, cleanup_seconds))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            # Nested finally also covers an exception while entering/waiting in
            # the graceful phase. No new attempt is launched on cleanup failure.
            signal_group(signal.SIGKILL)
            try:
                if proc is not None and proc.poll() is None:
                    try:
                        proc.wait(timeout=max(0.01, cleanup_seconds - (time.monotonic() - cleanup_start)))
                    except subprocess.TimeoutExpired:
                        reason = 'owned_process_unreaped'
            finally:
                for sig, handler in cleanup_handlers.items():
                    signal.signal(sig, handler)
        if cleanup_signals and reason is None:
            reason = 'supervisor_signal_during_cleanup'
        try:
            if proc is not None and proc.stdout is not None:
                proc.stdout.close()
            selector.close()
            os.fsync(fd)
        finally:
            os.close(fd)
            try:
                sync_directory(log_path.parent)
            finally:
                for sig, handler in prior_handlers.items():
                    signal.signal(sig, handler)
                # Restore/raise only after handles and handlers are settled.
                # A whole deadline already caught in the main wait must not
                # silently grant unbounded post-worker publication time.
                remaining = alarm_before[0] - (time.monotonic() - cleanup_start)
                if reason == 'supervisor_TimeoutError' or signal.SIGALRM in cleanup_signals \
                        or (alarm_before[0] > 0 and remaining <= 0):
                    raise TimeoutError('whole supervisor deadline')
                if alarm_before[0] > 0:
                    signal.setitimer(signal.ITIMER_REAL, remaining, alarm_before[1])
    return {'status': 'completed' if reason is None and proc is not None and proc.returncode == 0 else 'failed',
            'reason': reason, 'child_pid': None if proc is None else proc.pid,
            'exit_code': None if proc is None else proc.returncode,
            'wall_seconds': time.monotonic() - start, 'worker_wall_limit_seconds': wall_seconds,
            'cleanup_limit_seconds': cleanup_seconds, 'log_emitted_bytes': emitted,
            'log_retained_bytes': retained, 'log_limit_bytes': log_limit,
            'owned_group_cleanup_attempted': proc is not None, 'unrelated_processes_signaled': False}


def _supervise(args):
    reads = Reads()
    runtime_metadata(reads)  # Metadata/code only; no native scientific import.
    original_root, source, historical, root = (canonical(getattr(args, n))
        for n in ('original_source_root', 'edf', 'historical', 'output'))
    for operand in (original_root, source, historical):
        need(operand != root and not operand.is_relative_to(root) and not root.is_relative_to(operand),
             'source/output namespaces disjoint')
    need(not os.path.lexists(root), 'fresh output root; never retry/overwrite')
    os.mkdir(root, 0o700)
    sync_directory(root)
    sync_directory(root.parent)
    control_path = Path(__file__).resolve()
    control_stamp = stamp(control_path)
    need(control_stamp[2] <= 1048576, 'bounded selected control source')
    reads.reserve('supervisor control source', control_stamp[2] + 1)
    source_body = control_path.read_bytes()
    need(stamp(control_path) == control_stamp and len(source_body) == control_stamp[2], 'stable selected control source')
    # These bounded supervisor reads occur later, but their reservations are
    # durable before worker launch and included once in the worker's prefix.
    reads.reserve('supervisor bounded worker stdout', LOG_LIMIT + 65536)
    reads.reserve('supervisor worker-result capture', META_LIMIT + 1)
    intent = {'schema': 'neural010-one-record-control-supervision-v1', 'supervisor_pid': os.getpid(),
        'control_source': pin(source_body), 'runtime': PYTHON,
        'operands': {'edf': str(source), 'historical': str(historical),
                     'original_source_root': str(original_root), 'output': str(root)},
        'edf_expected': EDF, 'historical_expected': HISTORICAL,
        'worker_wall_seconds': WORKER_SECONDS, 'cleanup_seconds': CLEANUP_SECONDS,
        'whole_supervisor_alarm_seconds': WHOLE_SUPERVISOR_SECONDS,
        'cpu_seconds_soft_hard': [90, 95], 'threads': 1, 'declared_ram_bytes': DECLARED_RAM,
        'output_limit_bytes': OUTPUT_LIMIT, 'projection_limit_bytes': PROJECT_LIMIT,
        'read_limit_bytes': READ_LIMIT, 'no_automatic_retry': True,
        'supervisor_read_reserved_bytes': reads.total,
        'supervisor_read_reservations': reads.entries,
        'root_native_approval_required': True, 'full_cohort_preparation_authorized': False}
    body = encode(intent)
    write_once(root / 'SUPERVISOR_INTENT.json', body)
    command = [PYTHON['path'], '-I', '-B', str(Path(__file__).resolve()), '--_worker',
        '--original-source-root', str(original_root), '--edf', str(source), '--historical', str(historical),
        '--output', str(root), '--supervisor-pid', str(os.getpid()),
        '--intent-bytes', str(len(body)), '--intent-sha256', pin(body)['sha256']]
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
           'HDF5_PLUGIN_PATH': '/nonexistent', **{k: '1' for k in THREAD_ENV}}
    result = run_supervised(command, root, root / 'worker.log', environment=env)
    result.update({'schema': 'neural010-one-record-supervisor-result-v1',
                   'supervisor_metadata_read_reserved_bytes': reads.total,
                   'whole_supervisor_alarm_seconds': WHOLE_SUPERVISOR_SECONDS,
                   'full_cohort_prepared': False, 'scientific_or_runtime_readiness': False})
    if result['status'] == 'completed':
        rp = root / 'CONTROL_RESULT.json'
        need(rp.exists() and stamp(rp)[2] <= META_LIMIT, 'complete worker result required')
        raw = capture_worker_result(rp, reads)
        report = parse(raw)
        need(report['status'] == 'one_record_semantic_projection_control_passed_incomplete_cohort'
             and report['prepared_original_records'] == 1 and report['full_cohort_prepared'] is False,
             'one-record result only')
        result['control_result'] = pin(raw)
        need(type(report['logical_read_reserved_bytes']) is int
             and reads.total <= report['logical_read_reserved_bytes'] <= READ_LIMIT,
             'combined logical read limit includes supervisor prefix once')
        result['aggregate_logical_read_reserved_bytes'] = report['logical_read_reserved_bytes']
        result['worker_total_already_includes_supervisor_reservations'] = True
    result['retained_outputs_before_supervisor_receipt'] = output_inventory(root)
    write_once(root / 'SUPERVISOR_RESULT.json', encode(result))
    output_inventory(root)
    print(json.dumps({'status': result['status'], 'output': str(root), 'full_cohort_prepared': False}, sort_keys=True))
    return 0 if result['status'] == 'completed' else 1


@contextlib.contextmanager
def whole_attempt_guard(seconds=WHOLE_SUPERVISOR_SECONDS):
    """Process-local whole-supervisor alarm; does not prove kernel-stall bounds."""
    need(seconds > 0 and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'fresh whole-attempt timer')
    prior = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise TimeoutError('whole supervisor deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior)


def supervise(args):
    with whole_attempt_guard():
        return _supervise(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original-source-root', 'edf', 'historical', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--_worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--supervisor-pid', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--intent-bytes', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--intent-sha256', help=argparse.SUPPRESS)
    args = parser.parse_args()
    return worker(args) if args._worker else supervise(args)


if __name__ == '__main__':
    sys.exit(main())

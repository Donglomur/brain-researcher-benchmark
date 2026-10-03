"""Run one approved DEVCONN source route and persist primitives, never endpoint analysis.

Each route performs its own full source authentication. This wrapper adds exact
code/document binding, exclusive evidence publication and bounded safe primitive
serialization. No source/code import or source access occurs at module import.
Production pins remain fail-closed until the parent freezes them.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import sys
import time
import types

SUBJECTS = tuple(f'sub-pixar{i:03d}' for i in range(1, 156))
DOCUMENT_PINS = dict(source_manifest_sha256='0fb419ee0dbea59376f5b0dc1e91d26502e8203d6e7b02334b979e6a1d9f66e3',
    method_sha256='e8ba3df50c7cc4bf8b83e2db559c0f1e515f10bf4c45498da84076306e883f6e',
    output_schema_sha256='3463740e8c55a9f549590fee013aa29d30480eb63e9984acafd2a41c1a1531b4',
    reporting_kernel_sha256='2b3abe5fe37d3ad68db57301afa68cf6b0f5409abaf81bc5b06494ae4bf88638')
ROUTE_PINS = {
    'private': {
        'source_reference.py': '2ee516449dd0071018b5dec9cacf2ef00b80627cae487bb994f31a2abc86ed0f',
        'inspect_structure.py': 'b0474f9de46a4a76e9307928f0a7f1999f7e51c23c1b3dd3657860a9374f9a15',
        'source_numerics.py': 'cc39d43bfa3308433a71a0cdd5457d896625d33882c68bb6dfba0d44d4a19673',
        'reporting_kernel.py': DOCUMENT_PINS['reporting_kernel_sha256'],
        'coordinate_contract.py': '40991bfa9e2d78e14163b58a1f5f6ed30b9d14be6143c2671b5b87e5be8fc00e',
    },
    'oracle': {
        'oracle_source.py': '37c4a0b7c5caf9cddc67e6eb7f8271f53e9a19da49fe5dec31615ee5dda5b912',
        'stage_data.py': 'b653f7c9522055cbfed634e8a08352d556059110f027b5a58d69cd229e4b6210',
        'inspect_structure.py': 'b0474f9de46a4a76e9307928f0a7f1999f7e51c23c1b3dd3657860a9374f9a15',
        'oracle_numerics.py': 'ba579f1502f6752fe6314dad9a044596ddac85ae7288a325329163e41627d5f2',
        'reporting_kernel.py': DOCUMENT_PINS['reporting_kernel_sha256'],
        'coordinate_contract.py': '40991bfa9e2d78e14163b58a1f5f6ed30b9d14be6143c2671b5b87e5be8fc00e',
    },
}
N_ROIS = 264
MAX_ARRAY_BYTES = 256 * 1024**2
MAX_METADATA_BYTES = 32 * 1024**2


def require(ok, reason):
    if not ok: raise ValueError(reason)


def safe_path(value):
    text = os.fspath(value)
    require(type(text) is str and text.startswith('/') and '\0' not in text
            and not any(part in ('.', '..') for part in text.split('/')), 'safe_absolute_path')
    path = Path(text)
    for node in (*reversed(path.parents), path):
        if os.path.lexists(node):
            mode = node.lstat().st_mode
            require(not stat.S_ISLNK(mode), 'symlink_path')
            if node != path: require(stat.S_ISDIR(mode), 'path_ancestor')
    return path


def fresh_output(value, protected):
    output = safe_path(value)
    for item in (*protected, Path(__file__).absolute().parent):
        path = safe_path(item)
        require(output != path and output not in path.parents and path not in output.parents, 'protected_overlap')
    require(output.parent.is_dir(), 'output_parent_required')
    if os.path.lexists(output):
        require(output.is_dir() and not any(output.iterdir()), 'fresh_or_empty_output')
    else:
        output.mkdir()
    return output


def signature(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def pinned_bytes(path, pin, cap):
    require(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin), 'unfrozen_pin')
    path = safe_path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'pinned_input_cap_or_type')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        require(signature(os.fstat(stream.fileno())) == signature(before), 'input_changed')
        raw = stream.read(cap + 1)
        require(signature(os.fstat(stream.fileno())) == signature(before), 'input_changed')
    require(signature(path.lstat()) == signature(before), 'input_path_changed')
    require(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == pin, 'input_sha256')
    return raw


def load_adapter(route):
    require(route in ROUTE_PINS, 'route')
    directory = Path(__file__).absolute().parent
    pins = ROUTE_PINS[route]
    # Complete closure is authenticated before even the adapter is compiled.
    payloads = {name: pinned_bytes(directory / name, pin, 1024**2) for name, pin in pins.items()}
    filename = 'source_reference.py' if route == 'private' else 'oracle_source.py'
    key = '_devconn_route_' + route
    module = types.ModuleType(key); module.__file__ = str(directory / filename)
    sys.modules[key] = module
    try:
        exec(compile(payloads[filename], module.__file__, 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(key, None); raise
    policy = module.production_policy()
    dependency_pins = policy.module_pins if route == 'private' else policy.code_pins
    require(dependency_pins == {name: pin for name, pin in pins.items() if name != filename}, 'adapter_closure_pins')
    require(dict(source_manifest_sha256=policy.source_sha, method_sha256=policy.method_sha,
                 output_schema_sha256=policy.schema_sha, reporting_kernel_sha256=policy.reporting_sha) == DOCUMENT_PINS,
            'adapter_document_pins')
    return module.reconstruct


def json_bytes(value, cap):
    def depth(item, level=0):
        require(level <= 64, 'metadata_depth')
        if isinstance(item, dict):
            require(all(type(key) is str for key in item), 'metadata_key')
            for child in item.values(): depth(child, level + 1)
        elif isinstance(item, (list, tuple)):
            for child in item: depth(child, level + 1)
        else:
            require(item is None or type(item) in (str, int, float, bool), 'metadata_scalar_type')
            if type(item) is float: require(math.isfinite(item), 'metadata_nonfinite')
    depth(value)
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    require(len(raw) <= cap, 'metadata_byte_cap')
    return raw


def write_json(path, obj, cap=MAX_METADATA_BYTES):
    raw = json_bytes(obj, cap)
    with path.open('xb') as stream: stream.write(raw)
    return dict(path=path.name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def primitive_arrays(reference, expected_subjects, pilot, geometry_only=False):
    import numpy as np
    ids = list(() if geometry_only else expected_subjects[:1] if pilot else expected_subjects)
    status = 'geometry_only' if geometry_only else 'resource_pilot' if pilot else 'complete'
    require(reference.get('status') == status, 'route_status')
    require(reference.get('subject_ids') == ids and set(reference['persons']) == set(ids), 'route_subjects')
    require(reference.get('structural_subject_ids') == list(expected_subjects), 'structural_subjects')
    roi_ids = reference['roi_ids']
    require(type(roi_ids) is list and len(roi_ids) == N_ROIS and len(set(roi_ids)) == N_ROIS
            and all(type(v) is str and v for v in roi_ids), 'roi_axis')
    coordinates = np.asarray(reference['coordinates'])
    require(coordinates.shape == (N_ROIS, 3) and coordinates.dtype.kind in 'iuf'
            and np.isfinite(coordinates).all(), 'coordinate_shape_or_type')
    require(set(reference['covariates']) == set(expected_subjects)
            and [r['subject_id'] for r in reference['cohort']] == list(expected_subjects), 'complete_cohort_metadata')
    blocks, slices, start, total_bytes = [], [], 0, coordinates.nbytes
    for sid in ids:
        person = reference['persons'][sid]
        require(set(person) == {'raw_roi', 'cleaned_roi', 'canonical_active', 'frame_indices'}, 'person_primitive_fields')
        data = {name: np.asarray(value) for name, value in person.items()}
        frames = data['frame_indices']
        require(frames.ndim == 1 and frames.dtype.kind in 'iu' and len(frames) >= 2
                and np.array_equal(frames, np.arange(len(frames))), 'source_frame_axis')
        size = len(frames)
        for name in ('raw_roi', 'cleaned_roi'):
            require(data[name].shape == (size, N_ROIS) and data[name].dtype.kind in 'iuf'
                    and np.isfinite(data[name]).all(), 'primitive_real_shape_or_finite')
        require(data['canonical_active'].shape == (N_ROIS,) and data['canonical_active'].dtype == bool,
                'primitive_boolean_shape')
        total_bytes += sum(array.nbytes for array in data.values())
        require(total_bytes <= MAX_ARRAY_BYTES, 'primitive_byte_cap')
        blocks.append(data); slices.append(dict(subject_id=sid, start=start, stop=start + size)); start += size
    arrays = dict(subject_ids=np.asarray(ids, dtype='U'), structural_subject_ids=np.asarray(expected_subjects, dtype='U'),
        roi_ids=np.asarray(roi_ids, dtype='U'), coordinates=coordinates,
        frame_subject_ids=(np.concatenate([np.repeat(sid, len(data['frame_indices'])) for sid, data in zip(ids, blocks)])
                           if blocks else np.empty(0, dtype='U')),
        frame_indices=np.concatenate([data['frame_indices'] for data in blocks]) if blocks else np.empty(0, dtype=np.int64),
        raw_roi=np.concatenate([data['raw_roi'] for data in blocks]) if blocks else np.empty((0, N_ROIS), dtype=np.float64),
        cleaned_roi=np.concatenate([data['cleaned_roi'] for data in blocks]) if blocks else np.empty((0, N_ROIS), dtype=np.float64),
        canonical_active=np.stack([data['canonical_active'] for data in blocks]) if blocks else np.empty((0, N_ROIS), dtype=bool))
    require(sum(a.nbytes for a in arrays.values()) <= MAX_ARRAY_BYTES, 'primitive_byte_cap')
    metadata = {key: value for key, value in reference.items() if key not in ('persons', 'coordinates')}
    metadata['coordinates'] = coordinates.tolist()
    metadata['person_slices'] = slices
    return arrays, metadata


def run_route(adapter, data_dir, manifest, method, schema, output, *, route, pilot=False, geometry_only=False,
              expected_subjects=SUBJECTS, _document_pins=None, _code_pins=None):
    """Callable injection is manufactured-test-only; CLI always loads fixed pins."""
    require(route in ROUTE_PINS and type(pilot) is bool and type(geometry_only) is bool
            and not (pilot and geometry_only), 'route_or_mode')
    paths = [safe_path(value) for value in (data_dir, manifest, method, schema)]
    directory = fresh_output(output, paths)
    started = time.monotonic(); phase = 'binding'
    pins = dict(DOCUMENT_PINS if _document_pins is None else _document_pins)
    code_pins = dict(ROUTE_PINS[route] if _code_pins is None else _code_pins)
    try:
        write_json(directory / 'attempt.json', dict(status='running', route=route, pilot=pilot, geometry_only=geometry_only,
            document_pins=pins, code_pins=code_pins, endpoints_computed=False, production_artifacts_written=False))
        require(set(pins) == set(DOCUMENT_PINS) and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in pins.values()),
                'unfrozen_document_pins')
        for path, key in zip(paths[1:], ('source_manifest_sha256', 'method_sha256', 'output_schema_sha256')):
            pinned_bytes(path, pins[key], 4 * 1024**2)
        if adapter is None: adapter = load_adapter(route)
        require(callable(adapter), 'adapter_callable')
        phase = 'reconstruction'
        reference = adapter(*paths, pilot=pilot, geometry_only=geometry_only)
        require(reference.get('pins') == pins, 'returned_document_pins')
        require(not os.path.lexists(directory / 'failure_report.json'), 'authoritative_failure_marker')
        phase = 'primitive_serialization'
        arrays, metadata = primitive_arrays(reference, expected_subjects, pilot, geometry_only)
        import numpy as np
        with (directory / 'primitives.npz').open('xb') as stream:
            np.savez_compressed(stream, **arrays)
        array_file = directory / 'primitives.npz'
        require(array_file.stat().st_size <= MAX_ARRAY_BYTES, 'primitive_archive_cap')
        array_receipt = dict(path=array_file.name, size_bytes=array_file.stat().st_size,
                             sha256=hashlib.sha256(array_file.read_bytes()).hexdigest())
        meta_receipt = write_json(directory / 'canonical.json', metadata)
        require(not os.path.lexists(directory / 'failure_report.json'), 'authoritative_failure_marker')
        result = dict(status=reference['status'], route=route, pilot=pilot, geometry_only=geometry_only, document_pins=pins, code_pins=code_pins,
            n_subjects=len(reference['subject_ids']), n_frames=len(arrays['frame_indices']), n_rois=N_ROIS,
            n_structural_subjects=len(reference['structural_subject_ids']),
            files=[array_receipt, meta_receipt], primitives_sha256=array_receipt['sha256'],
            canonical_metadata_sha256=meta_receipt['sha256'], endpoints_computed=False, production_artifacts_written=False,
            elapsed_seconds=time.monotonic() - started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(directory / 'report.json', result)
        return result
    except BaseException as exc:
        # Never log arbitrary exception text: it may contain original values.
        failure = dict(status='failed', route=route, pilot=pilot, geometry_only=geometry_only, phase=phase, error_type=type(exc).__name__,
            reason='source_route_or_evidence_failure', endpoints_computed=False, production_artifacts_written=False,
            elapsed_seconds=time.monotonic() - started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if not os.path.lexists(directory / 'failure_report.json'):
            write_json(directory / 'failure_report.json', failure)
        if not os.path.lexists(directory / 'report.json'):
            write_json(directory / 'report.json', failure)
        return failure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', choices=tuple(ROUTE_PINS), required=True)
    parser.add_argument('--data-dir', required=True); parser.add_argument('--manifest', required=True)
    parser.add_argument('--method', required=True); parser.add_argument('--schema', required=True)
    parser.add_argument('--output', required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--pilot', action='store_true'); mode.add_argument('--geometry-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = run_route(None, args.data_dir, args.manifest, args.method, args.schema, args.output,
                           route=args.route, pilot=args.pilot, geometry_only=args.geometry_only)
        print(json.dumps({key: result.get(key) for key in ('status', 'route', 'pilot', 'geometry_only', 'n_subjects', 'elapsed_seconds', 'peak_rss_kib')}))
        return 0 if result['status'] in ('geometry_only', 'resource_pilot', 'complete') else 1
    except Exception as exc:
        print(json.dumps(dict(status='refused', error_type=type(exc).__name__)))
        return 1


if __name__ == '__main__': raise SystemExit(main())

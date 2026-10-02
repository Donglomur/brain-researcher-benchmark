"""Import-safe FCSTAB original-source oracle; no bank or private grader imports.

Source bytes are loaded by the separate oracle reader. The digest-bound public
kernel supplies the declared SD/Fisher/replay recipe. Success emits exactly the
five public artifacts. No endpoint sign, size, significance or equivalence gate.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import stat
import zipfile

import numpy as np
import scipy

import source_reader

METHOD_SHA = '004a396e4f4f37db956083939c84465819b7d3cd1a69569721c39e7884734ee4'
SCHEMA_SHA = 'bedafa3a91bcb6d6b83dd3ae6d4f2d4d9f7a58cc1f65631be3e5e7e86a47fadf'
KERNEL_SHA = 'a58264a5bb3ffd82b291434b2ca22843c276a42dab66d5e5abe220eb77ed7a49'
FILES = ('connectivity.npz', 'stability.csv', 'selection_evidence.json', 'summary.json', 'findings.md')
CSV_COLUMNS = ('subject_id', 'n_edges', 'forward_first_half', 'forward_second_half',
               'forward_delta', 'reverse_delta', 'independent_delta', 'random_delta')
SEGMENTS = ('first', 'second', 'full')
CAPS = dict(entire_output_tree_bytes=96*1024**2, output_entries=1000,
            npz_stored_bytes=64*1024**2, npz_expanded_bytes=128*1024**2, npz_members=16,
            selection_evidence_json_bytes=16*1024**2, summary_json_bytes=8*1024**2,
            csv_bytes=1024**2, findings_bytes=65536, json_depth=64)


class OracleError(ValueError):
    pass


def require(ok, reason):
    if not ok: raise OracleError(reason)


def disjoint(a, b):
    require(a != b and a not in b.parents and b not in a.parents, 'output overlaps protected source/code/document')


def policy_now():
    return source_reader.Policy(method_sha=METHOD_SHA, schema_sha=SCHEMA_SHA, kernel_sha=KERNEL_SHA)


def prepare_output(output_dir, protected):
    output = source_reader.safe_path(output_dir)
    for path in protected: disjoint(output, source_reader.safe_path(path))
    if os.path.lexists(output):
        require(stat.S_ISDIR(output.lstat().st_mode) and not any(output.iterdir()), 'output must be absent or an empty real directory')
    else:
        output.mkdir(parents=True, mode=0o755)
    info = output.lstat()
    return output, (info.st_dev, info.st_ino)


def guard_output(root, identity):
    source_reader.safe_path(root)
    info = root.lstat()
    require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == identity, 'output directory changed')
    require(not os.path.lexists(root/'failure_report.json'), 'authoritative failure marker')


def publish(root, identity, name, raw, cap):
    guard_output(root, identity)
    require(name in FILES and type(raw) is bytes and 0 < len(raw) <= cap, 'artifact byte cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)
    guard_output(root, identity)


def failure(root, identity, phase, exc):
    # Preserve all prior bytes and any preexisting/dangling failure marker.
    source_reader.safe_path(root); info = root.lstat()
    require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == identity, 'cannot safely mark changed output')
    if os.path.lexists(root/'failure_report.json'): return
    data = dict(status='failed', task_id='FCSTAB-001', phase=phase, error_type=type(exc).__name__,
                reason=str(exc) if isinstance(exc, OracleError) else 'source_kernel_or_io_failure',
                outputs_complete=False)
    with (root/'failure_report.json').open('xb') as stream:
        stream.write((json.dumps(data, allow_nan=False, sort_keys=True, indent=2)+'\n').encode())


def schema_caps(schema):
    require(type(schema) is dict and schema.get('task_id') == 'FCSTAB-001', 'schema task identity')
    declared = schema.get('limits')
    require(type(declared) is dict and schema.get('files') == list(FILES), 'schema files and limits')
    result = {}
    for key, maximum in CAPS.items():
        value = declared.get(key)
        require(type(value) is int and 0 < value <= maximum, 'invalid or excessive schema cap: '+key)
        result[key] = value
    return result


def source_primitives(basis, kernel):
    """Oracle-owned common mask and kernel Pearson, never private helpers."""
    raw = np.asarray(basis['raw'])
    ids, files = basis['subject_ids'], basis['participant_file_ids']
    require(raw.dtype == np.dtype('float64') and raw.ndim == 3 and bool(np.isfinite(raw).all()), 'finite original float64 matrix')
    people, frames, columns = raw.shape
    require(people == len(ids) == len(files) and people >= 2 and frames//2 >= 2 and columns >= 2,
            'source matrix shape')
    require(all(type(s) is str for s in ids+files) and len(set(ids)) == len(ids) and len(set(files)) == len(files), 'source identity axes')
    half = frames//2
    ranges = ((0, half), (frames-half, frames), (0, frames))
    sd = np.empty((people, 3, columns), dtype=np.float64)
    constants = np.empty_like(sd, dtype=bool)
    for person in range(people):
        for segment, (start, stop) in enumerate(ranges):
            for roi in range(columns):
                values = raw[person, start:stop, roi]
                constants[person, segment, roi] = bool(np.all(values == values[0]))
                sd[person, segment, roi] = kernel.population_sd(values)
    require(bool(np.isfinite(sd).all()) and bool((sd >= 0).all()), 'source population SD domain')
    support = sd > 1e-8
    common = np.all(support, axis=(0, 1))
    kept = np.flatnonzero(common)
    require(len(kept) >= 2, 'failed_precondition: fewer than two common ROIs')
    lower, upper = np.triu_indices(len(kept), 1)
    pairs = np.column_stack((kept[lower]+1, kept[upper]+1)).astype(np.int64)
    fisher = np.empty((people, 3, len(pairs)), dtype=np.float64)
    for person in range(people):
        for segment, (start, stop) in enumerate(ranges):
            fisher[person, segment] = kernel.fisher_z(np.ascontiguousarray(raw[person, start:stop][:, kept]))
    require(bool(np.isfinite(fisher).all()), 'source Fisher nonfinite')
    observed = copy.deepcopy(basis['source_observed'])
    for i, fid in enumerate(files):
        observed['persons'][fid]['segment_support'] = {name: support[i, j].tolist() for j, name in enumerate(SEGMENTS)}
        observed['persons'][fid]['exact_constant_mask'] = {name: constants[i, j].tolist() for j, name in enumerate(SEGMENTS)}
    observed.update(segment_ids=list(SEGMENTS), roi_ids=list(range(1, columns+1)), common_roi_mask=common.tolist())
    arrays = dict(subject_ids=np.asarray(ids, dtype='U'), segment_ids=np.asarray(SEGMENTS, dtype='U'),
                  roi_ids=np.arange(1, columns+1, dtype=np.int64), common_roi_mask=common,
                  edge_roi_i=pairs[:, 0], edge_roi_j=pairs[:, 1], fisher_z=fisher)
    return arrays, pairs, observed


def documents(basis, arrays, pairs, observed, kernel):
    result = kernel.analyze(arrays['fisher_z'], arrays['fisher_z'], basis['subject_ids'], pairs)
    pins = dict(basis['pins'])
    require(set(pins) == {'source_manifest_sha256','method_contract_sha256','output_schema_sha256','subject_ids_sha256'}
            and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in pins.values()), 'source document pins')
    evidence = dict(schema_version='fcstab-selection-v3', task_id='FCSTAB-001', status='complete', pins=pins,
                    n_edges=result['n_edges'], k=result['k'], seed=0,
                    subjects=[dict(subject_id=sid, **result['evidence'][sid]) for sid in basis['subject_ids']])
    summary = dict(schema_version='fcstab-summary-v3', task_id='FCSTAB-001', status='complete', pins=pins,
                   n_subjects=len(basis['subject_ids']),
                   cohort=[dict(file_id=fid, subject_id=sid) for fid, sid in zip(basis['participant_file_ids'], basis['subject_ids'])],
                   source_files=basis['source_files'], source_observed=observed,
                   software=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                   source_inference_support={key:dict(status=value['status']) for key, value in result['support_diagnostics'].items()},
                   **result['summaries'])
    return result['rows'], evidence, summary


def json_bytes(value, depth_cap):
    def walk(item, depth=0):
        require(depth <= depth_cap, 'JSON depth cap')
        if isinstance(item, float): require(math.isfinite(item), 'JSON nonfinite')
        elif isinstance(item, (list, dict)):
            for child in item.values() if isinstance(item, dict) else item: walk(child, depth+1)
    walk(value)
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def npz_bytes(arrays, caps):
    require(len(arrays) == 7 and len(arrays) <= caps['npz_members'], 'NPZ member count')
    for value in arrays.values():
        require(isinstance(value, np.ndarray) and value.dtype.kind in 'fiuUb', 'NPZ primitive dtype')
        if value.dtype.kind in 'fiu': require(bool(np.isfinite(value).all()), 'NPZ nonfinite')
    require(sum(v.nbytes for v in arrays.values()) <= caps['npz_expanded_bytes'], 'NPZ expanded cap')
    stream = io.BytesIO(); np.savez(stream, **arrays); raw = stream.getvalue()
    require(len(raw) <= caps['npz_stored_bytes'], 'NPZ stored cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(sum(x.file_size for x in archive.infolist()) <= caps['npz_expanded_bytes'], 'NPZ expanded cap')
    return raw


def csv_bytes(rows):
    output = io.StringIO(newline=''); writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        require(set(row) == set(CSV_COLUMNS), 'generated CSV columns')
        writer.writerow(row)  # Python repr preserves binary64 round-trip precision.
    return output.getvalue().encode('utf-8')


def findings(summary):
    lines = ['# Fixed-cohort selection sensitivity', '',
             'These signed later-minus-earlier Fisher-z summaries compare four edge-selection rules within the same runs.',
             'They do not establish a neural temporal effect, selection-free stability, or guaranteed forward/reverse bias cancellation.',
             'The common ROI mask uses the full cohort. LOSO excludes the held-out participant from ranking only; selectors overlap.',
             'Participant t/TOST results are nominal model-based diagnostics, not validated coverage for these shared selectors.',
             'The inherited ±0.05 Fisher-z equivalence margin is pedagogical, not a validated neural or clinical threshold.',
             'Edge Pearson/Spearman describe edge patterns and are not ICC. The frame-indexed sources do not verify TR or duration.', '']
    for name, record in summary['selection_schemes'].items():
        lines.append(f"- {name}: signed mean change {record['delta_mean']:.12g}; inference status {record['inference_status']}.")
    lines += ['', 'Undefined inference is retained with its public status; no participant or scheme is dropped.']
    return ('\n'.join(lines)+'\n').encode('utf-8')


def _run(data_dir, manifest_path, method_path, schema_path, subject_ids_path, kernel_path, output_dir, *, policy):
    code = Path(__file__).absolute().parent
    code_root = code.parent if (code.parent/'task.toml').is_file() else code
    root, identity = prepare_output(output_dir, [data_dir, manifest_path, method_path, schema_path,
                                                subject_ids_path, kernel_path, code_root])
    phase = 'authority_pins'
    try:
        require(type(policy) is source_reader.Policy and all(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin)
                for pin in (policy.source_sha, policy.method_sha, policy.schema_sha, policy.kernel_sha, policy.subject_ids_sha)),
                'unfrozen authority')
        phase = 'source_loading'
        basis = source_reader.load(data_dir, manifest_path, method_path, schema_path, subject_ids_path, policy=policy)
        require(basis['status'] == 'complete' and basis['raw'].shape[0] == policy.subjects, 'incomplete source scope')
        require(basis['method'].get('task_id') == 'FCSTAB-001', 'method task identity')
        caps = schema_caps(basis['schema'])
        kernel = source_reader.load_kernel(kernel_path, policy.kernel_sha)
        phase = 'source_support_and_Fisher'
        arrays, pairs, observed = source_primitives(basis, kernel)
        phase = 'own_full_precision_replay'
        rows, evidence, summary = documents(basis, arrays, pairs, observed, kernel)
        phase = 'artifact_publication'
        contents = dict(zip(FILES, [npz_bytes(arrays, caps), csv_bytes(rows),
                        json_bytes(evidence, caps['json_depth']), json_bytes(summary, caps['json_depth']), findings(summary)]))
        per_file = [caps[k] for k in ('npz_stored_bytes','csv_bytes','selection_evidence_json_bytes','summary_json_bytes','findings_bytes')]
        require(len(FILES) <= caps['output_entries'] and sum(map(len, contents.values())) <= caps['entire_output_tree_bytes'],
                'total output cap')
        for name, cap in zip(FILES, per_file): publish(root, identity, name, contents[name], cap)
        phase = 'final_inventory'
        guard_output(root, identity)
        entries = list(root.iterdir())
        require({p.name for p in entries} == set(FILES) and all(stat.S_ISREG(p.lstat().st_mode) for p in entries), 'late output inventory')
        require(all((root/name).stat().st_size == len(raw) for name, raw in contents.items()), 'artifact size changed')
        for name, raw in contents.items():
            source_reader.hashed_bytes(root/name, hashlib.sha256(raw).hexdigest(), len(raw))
        guard_output(root, identity)
        return dict(status='complete', task_id='FCSTAB-001', n_subjects=len(rows), n_edges=len(pairs),
                    files=list(FILES), total_output_bytes=sum(map(len, contents.values())))
    except BaseException as exc:
        failure(root, identity, phase, exc)
        raise


def run(data_dir='/app/data/fcstab', manifest_path='/app/source_manifest.json', method_path='/app/method_contract.json',
        schema_path='/app/output_schema.json', subject_ids_path='/app/subject_ids.txt', kernel_path='/app/selection_kernel.py',
        output_dir='/app/output'):
    return _run(data_dir, manifest_path, method_path, schema_path, subject_ids_path, kernel_path, output_dir, policy=policy_now())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in [('data-dir', os.environ.get('DATA_DIR', '/app/data/fcstab')),
                          ('manifest-path','/app/source_manifest.json'), ('method-path','/app/method_contract.json'),
                          ('schema-path','/app/output_schema.json'), ('subject-ids-path','/app/subject_ids.txt'),
                          ('kernel-path','/app/selection_kernel.py'), ('output-dir',os.environ.get('OUTPUT_DIR','/app/output'))]:
        parser.add_argument('--'+name, default=default)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(**vars(args)), allow_nan=False, sort_keys=True)); return 0
    except Exception as exc:
        print(json.dumps(dict(status='failed', error_type=type(exc).__name__))); return 1


if __name__ == '__main__':
    raise SystemExit(main())

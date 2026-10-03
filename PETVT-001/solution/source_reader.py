"""Offline oracle source decoding; no fits, network or historical references."""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

import numpy as np

SOURCE_SHA = '2e45467d3ef720a686b13a16ac33288369e3685044d243a5fe55128910adcfc8'
METHOD_SHA = '260a010f65be9a850b3ff46eaed0f5c7ec9b76c2d48cddbbd15e6636eecb8178'
SCHEMA_SHA = '23f68ffbbaefb40081fe9d33e1f020af85c69f0cec88d5216394766f267a97d0'
SUBJECTS = ('sub-sf02', 'sub-sf05', 'sub-sf06', 'sub-sf07', 'sub-sf08', 'sub-sf09', 'sub-sf10')
MISSING = ('', 'n/a')


def require(ok, message):
    if not ok: raise ValueError(message)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def signature(value):
    return value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def read(path, cap):
    path = Path(path); require(not any(p.is_symlink() for p in (path, *path.parents)), 'source/doc symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'source/doc file bound')
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(cap+1)
        require(len(raw) == before.st_size and signature(before) == signature(os.fstat(fd)) == signature(path.lstat()), 'source/doc changed')
        return raw
    finally: os.close(fd)


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key'); result[k] = v
        return result
    def invalid(x): raise ValueError('nonfinite JSON')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop(); require(depth <= 64, 'JSON nesting')
        if type(item) is float: require(math.isfinite(item), 'nonfinite JSON')
        elif type(item) is dict: stack.extend((v, depth+1) for v in item.values())
        elif type(item) is list: stack.extend((v, depth+1) for v in item)
    require(type(value) is dict, 'JSON object'); return value


def table(raw):
    require(b'\0' not in raw, 'table NUL'); csv.field_size_limit(16384)
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), delimiter='\t', strict=True))
    require(2 <= len(rows) <= 4097, 'table row bound')
    columns = rows.pop(0)
    require(1 <= len(columns) <= 1024 and len(set(columns)) == len(columns) and
            all(c and c == c.strip() and all(ord(x) >= 32 and ord(x) != 127 for x in c) for c in columns), 'table header')
    require(all(len(row) == len(columns) for row in rows), 'ragged table')
    return columns, rows


def number(token):
    require(token not in MISSING and token.strip() == token, 'missing/padded number')
    value = float(token); require(math.isfinite(value), 'nonfinite number'); return value


def expected_paths():
    result = {}
    for sid in SUBJECTS:
        prefix = sid+'/ses-baseline/pet/'+sid+'_ses-baseline_trc-sf51'
        result['derivatives/petprep_extract_tacs/'+sid+'/ses-baseline/'+sid+'_ses-baseline_trc-sf51_desc-gtmseg_tacs.tsv'] = ('tac', sid)
        for suffix, role in (('_recording-manual_blood.tsv', 'blood'), ('_pet.json', 'pet_metadata'),
                             ('_recording-manual_blood.json', 'blood_metadata')):
            result[prefix+suffix] = (role, sid)
    for path in ('README', 'dataset_description.json', 'derivatives/petprep_extract_tacs/dataset_description.json'):
        result[path] = ('provenance', None)
    return result


def authenticate(source, manifest_path, method_path, schema_path):
    expected_pins = (SOURCE_SHA, METHOD_SHA, SCHEMA_SHA)
    require(all(type(p) is str and len(p) == 64 for p in expected_pins), 'unfrozen source authority')
    documents = [read(p, 1048576) for p in (manifest_path, method_path, schema_path)]
    require(tuple(map(digest, documents)) == expected_pins, 'public document hash')
    manifest, method, schema = map(strict_json, documents)
    require(manifest['task_id'] == 'PETVT-001' and manifest['schema_version'] == 'petvt-source-v2' and
            manifest['status'] == 'complete_source_identity' and manifest['participant_ids'] == list(SUBJECTS), 'source lineage/cohort')
    root = Path(source); require(read(root/'source_manifest.json', 1048576) == documents[0], 'internal manifest')
    expected = expected_paths(); rows = manifest['files']; found = set()
    for row in rows:
        path = row['path']; require(path in expected and path not in found, 'source member identity')
        require((row['role'], row['participant_id']) == expected[path], 'source member role')
        require(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= 1048576, 'source size'); found.add(path)
    require(found == set(expected) and manifest['n_files'] == len(expected) and
            manifest['total_bytes'] == sum(r['size_bytes'] for r in rows) <= 4194304, 'source inventory totals')
    files, dirs = set(), set()
    expected_dirs = {str(p) for name in found for p in PurePosixPath(name).parents if str(p) != '.'}
    for base, children, names in os.walk(root, followlinks=False):
        for name in children:
            path = Path(base)/name; require(not path.is_symlink(), 'source directory symlink'); dirs.add(str(path.relative_to(root)))
        files.update(str((Path(base)/name).relative_to(root)) for name in names)
    require(files == found | {'source_manifest.json'} and dirs == expected_dirs, 'closed source bundle')
    buffers = {}
    for row in rows:
        raw = read(root/row['path'], row['size_bytes'])
        require(len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], 'source byte identity')
        git_sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        require(git_sha == row['git_blob_sha1'], 'source Git identity'); buffers[row['path']] = raw
    return manifest, method, schema, buffers


def decode_person(sid, manifest, method, buffers):
    rows = {r['role']: r for r in manifest['files'] if r['participant_id'] == sid}
    pet = strict_json(buffers[rows['pet_metadata']['path']]); blood_meta = strict_json(buffers[rows['blood_metadata']['path']])
    require(pet['Units'] == 'Bq/mL' and pet['ImageDecayCorrected'] is True and
        all(type(pet[k]) in (int, float) and pet[k] == v for k, v in
            (('ImageDecayCorrectionTime', 0), ('InjectionStart', 0), ('ScanStart', 0), ('RadionuclideHalfLife', 6586.2))), 'PET clock/unit')
    require(blood_meta['time']['Units'] == 's' and blood_meta['plasma_radioactivity']['Units'] == 'Bq/mL', 'blood units')
    th, tr = table(buffers[rows['tac']['path']]); bh, br = table(buffers[rows['blood']['path']])
    cortical = [c for c in th if c.startswith(('ctx-lh-', 'ctx-rh-'))]
    require(set(cortical) == set(method['source']['cortical_columns']) and len(tr) == method['source']['frame_counts'][sid]
            and len(br) == method['source']['blood_row_counts'][sid], 'source table dimensions/columns')
    starts = [number(r[th.index('frame_start')]) for r in tr]; ends = [number(r[th.index('frame_end')]) for r in tr]
    require(len(pet['FrameTimesStart']) == len(pet['FrameDuration']) == len(tr), 'sidecar frame count')
    require(abs(starts[0]) <= 1e-6 and all(a < b for a, b in zip(starts, ends)) and
            all(abs(x-y) <= 1e-6 for x, y in zip(ends[:-1], starts[1:])), 'frame continuity')
    require(all(abs(a-s) <= 1e-6 and abs((b-a)-d) <= 1e-6 for a,b,s,d in
                zip(starts,ends,pet['FrameTimesStart'],pet['FrameDuration'])), 'frame sidecar agreement')
    cortical_values = np.array([[number(row[th.index(c)]) for c in method['source']['cortical_columns']] for row in tr], dtype=np.float64)
    ledger, missing, groups = [], [], {}
    for i, row in enumerate(br):
        timestamp = number(row[bh.index('time')]); require(timestamp >= 0, 'blood clock')
        values, reasons = [], []
        for name in ('plasma_radioactivity', 'metabolite_parent_fraction'):
            token = row[bh.index(name)]
            if token in MISSING:
                missing.append(dict(source_row=i, column=name, token=token)); reasons.append('missing_'+name); values.append(None)
            else:
                value = number(token); require(value >= 0 and (name != 'metabolite_parent_fraction' or value <= 1), 'blood domain'); values.append(value)
        ledger.append(dict(source_row=i, time_s=timestamp, paired_eligible=not reasons, reasons=reasons))
        if not reasons: groups.setdefault(timestamp, []).append((i, tuple(values)))
    knots, activities, fractions = [], [], []
    for t, entries in sorted(groups.items()):
        require(all(pair == entries[0][1] for _, pair in entries), 'conflicting same-time paired values')
        indices = [i for i, _ in entries]
        knots.append(dict(time_s=t, representative_source_row=min(indices), contributing_row_indices=indices,
                          multiplicity=len(indices), exact_pair_equal=True))
        activities.append(entries[0][1][0]); fractions.append(entries[0][1][1])
    require(len(knots) == method['source']['distinct_knot_counts'][sid], 'distinct knot count')
    supported = len(knots) >= 2 and knots[-1]['time_s'] >= (starts[-1]+ends[-1])/2
    observed = dict(subject_id=sid, tac_path=rows['tac']['path'], blood_path=rows['blood']['path'],
        tac_columns=th, blood_columns=bh, cortical_columns=cortical, frame_count=len(tr), frame_starts_s=starts,
        frame_ends_s=ends, n_blood_rows=len(br), missing_selected_entries=missing, invalid_domain_entries=[],
        blood_row_ledger=ledger, coalesced_knot_ledger=knots, retained_knot_rows=[k['representative_source_row'] for k in knots],
        retained_knot_times_s=[k['time_s'] for k in knots], input_time_support=bool(supported),
        inserts_zero_anchor=bool(knots and knots[0]['time_s'] > 0), source_clock=dict(time_zero=pet['TimeZero'],
        scan_start_s=pet['ScanStart'], injection_start_s=pet['InjectionStart'], image_reference_s=pet['ImageDecayCorrectionTime'],
        half_life_s=pet['RadionuclideHalfLife'], concentration_units=pet['Units']))
    return dict(observed=observed, cortical_values=cortical_values, frame_starts_s=np.asarray(starts),
        frame_ends_s=np.asarray(ends), time_s=np.array([k['time_s'] for k in knots]),
        plasma=np.asarray(activities), parent_fraction=np.asarray(fractions), knot_rows=observed['retained_knot_rows'])


def load(source, manifest_path, method_path, schema_path, *, pilot=False):
    require(type(pilot) is bool, 'pilot exact Boolean')
    manifest, method, schema, buffers = authenticate(source, manifest_path, method_path, schema_path)
    people = {sid: decode_person(sid, manifest, method, buffers) for sid in SUBJECTS}
    authenticate(source, manifest_path, method_path, schema_path)
    selected = SUBJECTS[:1] if pilot else SUBJECTS
    return dict(status='resource_pilot' if pilot else 'complete', subject_ids=list(selected),
        persons={s: people[s] for s in selected}, source_observed={'persons': [people[s]['observed'] for s in SUBJECTS]},
        source_files=[{k: r[k] for k in ('path','role','participant_id','size_bytes','sha256','git_blob_sha1')} for r in manifest['files']],
        pins=dict(source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA, output_schema_sha256=SCHEMA_SHA),
        method=method, schema=schema)

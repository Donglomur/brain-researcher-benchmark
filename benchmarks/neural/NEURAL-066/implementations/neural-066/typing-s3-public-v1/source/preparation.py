"""Complete source-selected membership, paired opaque views and native projection.

All numerical/native imports are inside future explicitly selected worker calls.
No source metadata is mistaken for an authenticated waveform or sensor geometry.
"""
import failures
import operator_policy
import ast
import hashlib
import hmac
import math
import os
from collections import Counter
from pathlib import Path
from core import CHARS, CONDITIONS, COUNTS, MODES, encoded, exact, identity, need
from safe_io import array, capture, child, new_json, pin, strict, write_array
DATA_REVISION = '88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684'
AUTHOR_REVISION = '5f9889621d0df391c5aab37c996683d308e6e926'
PROJECTION_FAMILIES = ('NEURAL_PRE', 'NEURAL', 'NEURAL_POST', 'EOG', 'TIMING')
WINDOWS = {'NEURAL_PRE': (-0.7, -0.2), 'NEURAL': (-0.2, 0.3), 'NEURAL_POST': (0.3, 0.8), 'EOG': (-0.2, 0.3)}
EOG = ('RVEOG', 'LHEOG', 'RHEOG')

def key(row):
    return '|'.join((str(row[k]) for k in ('modality', 'alias', 'session', 'task', 'trial')))

def eligible(row, policy):
    return operator_policy.eligible(row, policy)

def token(seed, *parts):
    need(type(seed) is bytes and len(seed) == 32, 'Fresh operator-only opaque namespace seed')
    return hmac.new(seed, encoded(['NEURAL066-v1', *parts]), hashlib.sha256).hexdigest()

def role(row, person, fold):
    if row['person'] == person:
        return 'query' if row['fold'] == fold else 'unused'
    return 'train' if row['fold'] != fold else 'unused'

def load_original_metadata(root, policy):
    """Future operator-only reads. Never called by import or source controls."""
    policy = operator_policy.validate(policy)
    cohort_pin, log_pin = (policy['asset_pins'][k] for k in ('cohort', 'logs'))
    return (strict(capture(child(root, 'COHORT.json'), cohort_pin['bytes'], cohort_pin)), strict(capture(child(root, 'LOG_METADATA.json'), log_pin['bytes'], log_pin)))

def validate_membership(cohort, logs, metadata_pins, policy):
    need(cohort['source_revision'] == DATA_REVISION and cohort['loader_revision'] == AUTHOR_REVISION, 'Exact selected source revisions')
    included = [r for r in cohort['rows'] if r['included']]
    need(len(included) == 143 and len({(r['modality'], r['recording_alias'], r['session'], r['task']) for r in included}) == 143, 'Complete143 distinct selected timelines')
    for m, c in COUNTS.items():
        rows = [r for r in included if r['modality'] == m]
        need(len(rows) == c['timelines'] and len({r['person'] for r in rows}) == c['people'], 'Full modality people/timelines')
        for r in rows:
            alias = policy['meg_aliases'].get(r['recording_alias'], r['recording_alias']) if m == 'MEG' else r['recording_alias']
            need(r['person'] == m + '/' + alias, 'Original alias-resolved whole-person membership')
    selected = sorted({a for r in included for a in r['raw_assets']})
    need(len(selected) == 329 and sum((cohort['asset_files'][a]['size'] for a in selected)) == 187980093465, 'All329 exact selected native assets/declared bytes, not whole provider tree')
    assets = {}
    for name in selected:
        entry = cohort['asset_files'][name]
        d = {'bytes': entry['size'], 'sha256': entry['lfs']['oid']} if 'lfs' in entry else metadata_pins.get(name)
        need(d is not None and d['bytes'] == entry['size'], 'Publisher/held metadata member digest')
        assets[name] = {k: d[k] for k in ('bytes', 'sha256')}
    records = logs['records']
    need(len(records) == 9152 and sum((len(r['keys']) for r in records)) == 340813 and (len({key(r) for r in records}) == 9152), 'Exact complete raw-log normalization census')
    need(sum((not bool(r['keys']) for r in records)) == 25, 'Explicit25 empty sequences')
    chosen = [r for r in records if eligible(r, policy)]
    need(len(chosen) == 9126 and sum((len(r['keys']) for r in chosen)) == 340794, 'Exact endpoint exclusions')
    need({m: sum((r['modality'] == m for r in chosen)) for m in COUNTS} == {'MEG': 5163, 'EEG': 3963}, 'Complete eligible modality support')
    templates = logs['templates']
    need(len(templates) == 128 and len({v['group'] for v in templates.values()}) == 105 and ([len({v['group'] for v in templates.values() if v['fold'] == f}) for f in (0, 1)] == [49, 56]), 'Original template graph/folds')
    timeline_keys = {(r['modality'], r['recording_alias'], r['session'], r['task']) for r in included}
    for r in records:
        need((r['modality'], r['alias'], r['session'], r['task']) in timeline_keys and len(r['keys']) <= 256 and (r['fold'] == int(r['group'], 16) % 2), 'Bound original source row')
        for k in r['keys']:
            need(len(k) == 4 and all((type(v) in (float, int) and math.isfinite(v) for v in k)) and (k[1] > 0) and (type(k[3]) is int) and (0 <= k[3] < 29), 'Actual observed positive-duration mapped key')
    for t in timeline_keys:
        need(sum(((r['modality'], r['alias'], r['session'], r['task']) == t for r in records)) == 64, 'Every timeline all64 postpractice source sentences')
    cases = []
    for m in COUNTS:
        people = sorted({r['person'] for r in chosen if r['modality'] == m})
        for i, p in enumerate(people):
            for f in (0, 1):
                query = [r for r in chosen if r['modality'] == m and role(r, p, f) == 'query']
                train = [r for r in chosen if r['modality'] == m and role(r, p, f) == 'train']
                need(query and train and {r['person'] for r in train}.isdisjoint({p}) and {r['group'] for r in train}.isdisjoint({r['group'] for r in query}), 'Whole-person/template cases')
                cases.append({'slot': f'{m}-{i:02d}-{f}', 'person': p, 'fold': f, 'modality': m, 'train_keys': [key(r) for r in train], 'query_keys': [key(r) for r in query]})
    need(len(cases) == 78, 'All78 cases')
    return {'schema': 'neural066_private_membership_v1', 'timelines': included, 'assets': assets, 'cases': cases, 'eligible_keys': [key(r) for r in chosen], 'declared_raw_bytes': 187980093465, 'crossmodal_unique_recruits': None, 'source_payloads_admitted': False}

def stream_authenticate(path, expected, block=1048576):
    """Exact inert native-file hash, bounded live scratch; separate native I/O later."""
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == expected['bytes'], 'Exact regular original extent')
        total = 0
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, min(block, expected['bytes'] - total + 1))
            if not chunk:
                break
            total += len(chunk)
            need(total <= expected['bytes'], 'No trailing original bytes')
            digest.update(chunk)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all((getattr(before, k) == getattr(after, k) for k in fields)) and total == expected['bytes'] and (digest.hexdigest() == expected['sha256']), 'Stable complete original source bytes')
        return {'bytes': total, 'sha256': digest.hexdigest()}
    except BaseException as exc:
        failures.hold(exc, 'caught')
        primary = exc
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            if primary is None:
                raise
            failures.note(primary, 'Original descriptor close failed: ' + failures.kind(secondary))

def trigger_method(loader_body, modality, policy):
    import mne
    import numpy as np
    import pandas as pd
    need(pin(loader_body) == policy['asset_pins']['loader'], 'Pinned author trigger method source')
    tree = ast.parse(loader_body)
    name = 'Pinet2024Meg' if modality == 'MEG' else 'Pinet2024Eeg'
    cls = next((x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == name))
    node = next((x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '_preproc_events'))
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {'mne': mne, 'np': np, 'pd': pd}
    exec(compile(module, 'authenticated_author_trigger', 'exec'), namespace)
    return namespace['_preproc_events']

def align(raw_events, records, matcher, policy):
    import numpy as np
    events = sorted([e for r in records for e in r['alignment_events']], key=lambda x: x[0])
    rt = np.asarray(raw_events['start'], float)
    rv = np.asarray(raw_events['trigger'], int)
    lt = np.asarray([x[0] for x in events], float)
    lv = np.asarray([x[1] for x in events], int)
    i, j = matcher(rv, lv)
    i = np.asarray(i, int)
    j = np.asarray(j, int)
    need(len(i) == len(j) > 1 and len(set(i)) == len(i) and (len(set(j)) == len(j)) and np.all(rv[i] == lv[j]), 'Unique exact trigger values')
    offset = float(np.median(rt[i] - lt[j]))
    residual = np.abs(rt[i] - lt[j] - offset)
    need(np.isfinite(residual).all() and float(residual.max()) <= 0.05, 'Constant-offset50ms gate; no DTW repair')
    mapped = {(float(lt[b]), int(lv[b])): float(rt[a]) for a, b in zip(i, j)}
    need(len(mapped) == len(j), 'Unique aligned time/value pairs')
    for r in records:
        if eligible(r, policy):
            need(all(((float(k[0]), int(k[2])) in mapped for k in r['keys'])), 'Every eligible key aligns')
    return (mapped, {'raw_events': len(rt), 'log_events': len(lt), 'matched': len(i), 'offset_seconds': offset, 'max_clock_residual_seconds': float(residual.max()), 'dtw_used': False})

def geometry(raw, picks, modality):
    """Literal author minimal-Info/layout path; full coverage is mandatory."""
    import mne
    import numpy as np
    need(mne.__version__ == '1.11.0', 'Exact source-bound MNE geometry environment')
    selected = raw.copy().pick(picks)
    if modality == 'EEG':
        selected.set_montage(mne.channels.make_standard_montage('standard_1005'))
    names = list(selected.ch_names)
    types = selected.get_channel_types()
    minimal = mne.create_info(names, selected.info['sfreq'], types)
    for ch, source in zip(minimal['chs'], selected.info['chs']):
        ch['loc'] = np.asarray(source['loc']).copy()
    with minimal._unlock():
        minimal['highpass'] = selected.info['highpass']
        minimal['lowpass'] = selected.info['lowpass']
    layout = mne.find_layout(minimal)
    mapping = {name: pos[:2] for name, pos in zip(layout.names, layout.pos)}
    positions = []
    for name in names:
        lookup = name if name in mapping else name.split('-')[0]
        need(lookup in mapping, 'Every original sensor has source layout coordinates')
        positions.append(mapping[lookup])
    pos = np.asarray(positions, dtype=float)
    need(pos.shape == (COUNTS[modality]['channels'], 2) and np.isfinite(pos).all(), 'Full finite sensor geometry')
    low = pos.min(axis=0)
    width = pos.max(axis=0) - low
    need(np.all(width > 0), 'Nondegenerate source layout axes')
    pos = (pos - low) / width
    return {'schema': 'neural066_geometry_v1', 'modality': modality, 'channel_names': names, 'channel_types': types, 'positions': pos.astype(np.float32).tolist(), 'source_method': 'MNE1.11.0 minimalInfo/find_layout per-axis minmax; fullcoverage', 'layout_kind': str(layout.kind)}
PROJECTION_SCAN_ELEMENTS = 16384

def projection_live_floor(shapes, neural_channels, eog_channels):
    """Known array/storage scratch floor; native internals and RSS stay unqualified."""
    need(set(shapes) == set(PROJECTION_FAMILIES) and type(neural_channels) is int and (type(eog_channels) is int) and (neural_channels > 0) and (eog_channels > 0), 'Complete projection memory schema')
    for shape in shapes.values():
        need(all((type(n) is int and n > 0 for n in shape)), 'Positive full projection shape')
    sizes = {a: 4 * math.prod(s) for a, s in shapes.items()}
    channels = max(neural_channels, eog_channels)
    raw = 8 * channels * 500
    reduction = 8 * channels * 25
    extraction = 2 * raw + reduction + channels * 500
    scan = min(PROJECTION_SCAN_ELEMENTS, max((n // 4 for n in sizes.values())))
    publication = 2 * (max(sizes.values()) + 1024)
    return {'output_arrays_bytes': sum(sizes.values()), 'extraction_known_scratch_bytes': extraction, 'finite_scan_boolean_bytes': scan, 'publication_known_scratch_bytes': publication, 'live_array_bytes': sum(sizes.values()) + max(extraction, scan, publication), 'actual_peak_measured': False, 'native_internal_overhead_qualified': False}

def require_finite_projections(values):
    """Refuse any completed float32 overflow/nonfinite before publishing any file."""
    import numpy as np
    need(set(values) == set(PROJECTION_FAMILIES), 'All five completed families')
    for name in PROJECTION_FAMILIES:
        value = values[name]
        need(isinstance(value, np.ndarray) and value.dtype.str == '<f4' and value.flags.c_contiguous, 'Complete primitive float32 projection ' + name)
        flat = value.reshape(-1)
        for start in range(0, flat.size, PROJECTION_SCAN_ELEMENTS):
            need(np.isfinite(flat[start:start + PROJECTION_SCAN_ELEMENTS]).all(), 'Nonfinite completed projection ' + name + '; no clipping or omission')

def native_project(raw_root, record, records, asset_pins, loader_body, output, limits, policy):
    """Future actual full timeline implementation; never called by source inspection."""
    import mne
    import numpy as np
    from neuralset import utils as nutils
    need(len(records) == 64 and record['included'], 'Original complete included timeline')
    for rel in record['raw_assets']:
        stream_authenticate(child(raw_root, rel), asset_pins[rel])
    path = child(raw_root, record['raw_entry'])
    mod = record['modality']
    raw = mne.io.read_raw_fif(path, preload=False, allow_maxshield=True, verbose=False) if mod == 'MEG' else mne.io.read_raw_brainvision(path, preload=False, verbose=False)
    primary = None
    try:
        need(raw.info['sfreq'] == 1000, 'Exact native1000Hz')
        actual = {str(Path(p).resolve()) for p in raw.filenames}
        expected = {str(child(raw_root, p).resolve()) for p in record['raw_assets'] if p.endswith('.fif' if mod == 'MEG' else '.eeg')}
        need(actual == expected, 'No unbound native split/body opens')
        if mod == 'EEG':
            need(len(raw.ch_names) == 64 and all((n in raw.ch_names for n in EOG)), 'Original EEG64/threeEOG')
            picks = [i for i, n in enumerate(raw.ch_names) if n not in EOG]
            aux = [raw.ch_names.index(n) for n in EOG]
        else:
            picks = mne.pick_types(raw.info, meg=True, eeg=False, eog=False, stim=False, exclude=[]).tolist()
            aux = mne.pick_types(raw.info, meg=False, eeg=False, eog=True, emg=False, stim=False, exclude=[]).tolist()
        need(len(picks) == COUNTS[mod]['channels'] and 1 <= len(aux) <= 8, 'Full neural/actualEOG schema')
        geo = geometry(raw, picks, mod)
        mapped, audit = align(trigger_method(loader_body, mod, policy)(None, raw), records, nutils.match_list, policy)
        chosen = [r for r in records if eligible(r, policy)]
        n = sum((len(r['keys']) for r in chosen))
        shapes = {a: [n, len(aux) if a == 'EOG' else len(picks), 25] for a in WINDOWS}
        shapes['TIMING'] = [n, 3]
        memory_floor = projection_live_floor(shapes, len(picks), len(aux))
        need(memory_floor['live_array_bytes'] <= limits['live_array_bytes'] and all((math.prod(s) * 4 + 128 <= limits['array_bytes'] for s in shapes.values())), 'Complete projection live/array reservation before allocation')
        values = {a: np.empty(s, dtype='<f4') for a, s in shapes.items()}
        rows = []
        at = 0
        for r in chosen:
            begin = at
            for index, k in enumerate(r['keys']):
                onset = mapped[float(k[0]), int(k[2])]
                for a, (start, end) in WINDOWS.items():
                    lo = round(onset * 1000) - raw.first_samp + round(start * 1000)
                    hi = round(onset * 1000) - raw.first_samp + round(end * 1000)
                    use = aux if a == 'EOG' else picks
                    need(0 <= lo < hi <= raw.n_times and hi - lo == 500, 'Full half-open native window')
                    x = raw.get_data(picks=use, start=lo, stop=hi, reject_by_annotation=None)
                    need(x.shape == (len(use), 500) and np.isfinite(x).all(), 'No missing/nonfinite channel/key')
                    values[a][at] = x.reshape(len(use), 25, 20).mean(axis=2)
                    del x
                values['TIMING'][at] = [k[1], 0 if index == 0 else k[0] - r['keys'][index - 1][0], int(index == 0)]
                at += 1
            rows.append({'source_key': key(r), 'begin': begin, 'n_keys': at - begin})
        require_finite_projections(values)
        out = Path(output)
        if out.exists():
            need(out.is_dir() and (not any(out.iterdir())), 'Fresh empty owned output')
        else:
            out.mkdir()
        arrays = {a: write_array(out / (a + '.npy'), v, limits['array_bytes']) for a, v in values.items()}
        for rel in record['raw_assets']:
            stream_authenticate(child(raw_root, rel), asset_pins[rel])
        result = {'schema': 'neural066_native_projection_v1', 'record': record, 'record_identity': identity(record), 'rows': rows, 'arrays': arrays, 'geometry': geo, 'eog_names': [raw.ch_names[i] for i in aux], 'eog_types': raw.get_channel_types(picks=aux), 'alignment': audit, 'known_array_memory_floor': memory_floor, 'source_assets': {r: asset_pins[r] for r in record['raw_assets']}}
        new_json(out / 'RESULT.json', result)
        return result
    except BaseException as exc:
        failures.hold(exc, 'caught')
        primary = exc
        raise
    finally:
        try:
            raw.close()
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            if primary is None:
                raise
            failures.note(primary, 'Native reader close failed: ' + failures.kind(secondary))

def join_projections(membership, logs, projected, policy):
    need(len(projected) == 143, 'All143 authentic projection results')
    chosen = {key(r): r for r in logs['records'] if eligible(r, policy)}
    locations = {}
    geometries = {}
    schemas = {}
    types = {}
    for i, (record, q) in enumerate(zip(membership['timelines'], projected)):
        need(q['record'] == record and q['record_identity'] == identity(record) and (set(q['arrays']) == set(PROJECTION_FAMILIES)), 'Exact projection source/family join')
        expected = [r for r in logs['records'] if eligible(r, policy) and (r['modality'], r['alias'], r['session'], r['task']) == (record['modality'], record['recording_alias'], record['session'], record['task'])]
        at = 0
        for r, row in zip(expected, q['rows']):
            need(row == {'source_key': key(r), 'begin': at, 'n_keys': len(r['keys'])} and key(r) not in locations, 'Complete original sentence offsets')
            locations[key(r)] = {'projection': i, **row}
            at += len(r['keys'])
        need(len(expected) == len(q['rows']), 'No omitted or extra projection sentences')
        mod = record['modality']
        geo = q['geometry']
        need(geo['modality'] == mod, 'Geometry modality')
        need(mod not in geometries or geo == geometries[mod], 'Full modality fixed geometry, no manufactured average map')
        need(mod not in schemas or q['eog_names'] == schemas[mod], 'Full actual EOG schema consistency')
        need(type(q['eog_types']) is list and len(q['eog_types']) == len(q['eog_names']) and all((type(t) is str and t for t in q['eog_types'])), 'Complete source-authenticated ocular types')
        need(mod not in types or types[mod] == q['eog_types'], 'Exact ocular type/order across every timeline')
        geometries[mod] = geo
        schemas[mod] = q['eog_names']
        types[mod] = q['eog_types']
        for name in PROJECTION_FAMILIES:
            shape = [at, 3] if name == 'TIMING' else [at, len(q['eog_names']) if name == 'EOG' else COUNTS[mod]['channels'], 25]
            need(q['arrays'][name]['shape'] == shape and q['arrays'][name]['dtype'] == '<f4', 'Exact full projection shape/dtype')
    need(set(locations) == set(chosen), 'Complete selected sentence union')
    return {'schema': 'neural066_projection_join_v1', 'locations': locations, 'geometry': geometries, 'eog_names': schemas, 'eog_types': types}

def make_view(case, logs, joined, projections, projection_roots, seed, mode, condition, output, limits, contracts, policy):
    """Complete six-arm ABI, original outer shuffle and separate inner operands."""
    import numpy as np
    from features import feature_spec
    need(mode in (*MODES, 'reference') and condition in CONDITIONS, 'Declared independent six-arm realm')
    need(set(contracts) == {'source_contract_pin', 'language_policy_pin', 'projection_pin'}, 'Exact source/projection/language ancestry')
    domain = [case['slot']]
    all_rows = {key(r): r for r in logs['records'] if eligible(r, policy)}
    tr = [all_rows[k] for k in case['train_keys']]
    qu = sorted((all_rows[k] for k in case['query_keys']), key=lambda r: token(seed, *domain, 'query-order', key(r)))
    nt = sum((len(r['keys']) for r in tr))
    nq = sum((len(r['keys']) for r in qu))
    mod = case['modality']
    neural = joined['geometry'][mod]
    names = [] if condition == 'TIMING' else joined['eog_names'][mod] if condition == 'EOG' else neural['channel_names']
    types = [] if condition == 'TIMING' else joined['eog_types'][mod] if condition == 'EOG' else neural['channel_types']
    spec = feature_spec(condition, mod, names, types)
    dim = spec['dimensions']
    extra = nt * (dim + 2) * 4 if condition == 'SHUFFLE' and mode == 'reference' else 0
    need(nt > 0 and nq > 0 and (4 * (nt * (dim + 2) + nq * dim) + extra <= limits['live_array_bytes']), 'All complete view and original shuffle copies reserved')
    need(max(nt * (dim + 2), nq * dim) * 4 + 128 <= limits['array_bytes'], 'Complete primitive extent before allocation')
    train = np.empty((nt, dim + 2), dtype='<f4')
    query = np.empty((nq, dim), dtype='<f4')
    groups = Counter((r['person'] for r in tr))
    layout = []
    queries = []
    private = []
    offsets = {}
    at = 0
    private_groups = {}
    for r in tr:
        n = len(r['keys'])
        sid = token(seed, *domain, 'sentence', key(r))
        offsets[key(r)] = ('train', at, n)
        layout.append({'id': sid, 'person': token(seed, *domain, 'person', r['person']), 'session': token(seed, *domain, 'session', r['person'], r['alias'], r['session']), 'template': token(seed, *domain, 'template', r['group']), 'begin': at, 'n_keys': n})
        private_groups[sid] = {'person': r['person'], 'alias': r['alias'], 'session': r['session']}
        train[at:at + n, dim] = [k[3] for k in r['keys']]
        train[at:at + n, dim + 1] = nt / (len(groups) * groups[r['person']] * n)
        at += n
    at = 0
    for r in qu:
        n = len(r['keys'])
        sid = token(seed, *domain, 'sentence', key(r))
        offsets[key(r)] = ('query', at, n)
        queries.append({'id': sid, 'begin': at, 'n_keys': n})
        private.append({'id': sid, 'source_key': key(r)})
        at += n
    source_arm = 'NEURAL' if condition == 'SHUFFLE' else condition
    by_projection = {}
    for k in offsets:
        by_projection.setdefault(joined['locations'][k]['projection'], []).append(k)
    for i, keys in by_projection.items():
        desc = projections[i]['arrays'][source_arm]
        matrix = array(projection_roots[i], desc, limits['array_bytes'])
        need(np.isfinite(matrix).all(), 'Complete finite source projection')
        for k in keys:
            loc = joined['locations'][k]
            role, start, n = offsets[k]
            values = matrix[loc['begin']:loc['begin'] + n].reshape(n, dim)
            (train[:, :dim] if role == 'train' else query)[start:start + n] = values
        del matrix
    need(np.isfinite(train).all() and np.isfinite(query).all(), 'Complete finite six-arm values')
    out = Path(output)
    if out.exists():
        need(out.is_dir() and (not any(out.iterdir())), 'Fresh empty owned output')
    else:
        out.mkdir()
    private_shuffle = None
    unshuffled = None
    outer_mapping = []
    if condition == 'SHUFFLE':
        if mode == 'reference':
            unshuffled = write_array(out / 'UNSHUFFLED_TRAIN.npy', train, limits['array_bytes'])
            private_shuffle = new_json(out / 'SHUFFLE_GROUPS.json', {'schema': 'neural066_private_shuffle_groups_v1', 'groups': private_groups})
        blocks = {}
        for r in tr:
            begin = offsets[key(r)][1]
            blocks.setdefault((r['person'], r['alias'], r['session']), []).extend(range(begin, begin + len(r['keys'])))
        for group, indices in blocks.items():
            perm = sorted(indices, key=lambda j: hashlib.sha256(('typing-shuffle-v1:' + str(group) + ':' + str(j)).encode()).hexdigest())
            need(len(indices) > 1 and perm != indices, 'Original outer per-group nontrivial shuffle; no reroll')
            original = np.asarray(train[perm, :dim]).copy()
            train[indices, :dim] = original
            outer_mapping.append({'group': list(group), 'target_ordinals': indices, 'source_ordinals': perm})
    arrays = {'train.npy': write_array(out / 'train.npy', train, limits['array_bytes']), 'query.npy': write_array(out / 'query.npy', query, limits['array_bytes'])}
    geo = neural if condition not in ('TIMING', 'EOG') else {'schema': 'neural066_nonspatial_features_v1', 'modality': mod, 'channel_names': names, 'channel_types': types, 'positions': None, 'kind': spec['kind'], 'R2_supported': False}
    gp = new_json(out / 'GEOMETRY.json', geo)
    lp = new_json(out / 'TRAIN_LAYOUT.json', {'schema': 'neural066_train_layout_v1', 'sentences': layout})
    support = token(seed, *domain, 'support', case['train_keys'], case['query_keys'])
    view = {'format': 'typing_view_v3', 'schema': 'neural066_typed_view_v3', 'task': 'NEURAL-066', 'case': token(seed, *domain, 'case'), 'generation': token(seed, 'generation'), 'mode': mode, 'condition': condition, 'arm': condition, 'modality': mod, 'feature_dimensions': dim, 'feature_spec': spec, 'channels': names, 'samples_per_key': spec['samples_per_key'], 'queries': queries, 'arrays': arrays, 'layout': lp, 'geometry': gp, 'support_commitment': support, 'train_descriptor': arrays['train.npy'], 'query_descriptor': arrays['query.npy'], 'training_layout_descriptor': lp, **contracts}
    if unshuffled is not None:
        view['unshuffled_train'] = unshuffled
        view['private_shuffle_groups'] = private_shuffle
    vp = new_json(out / 'VIEW.json', view)
    provenance = {'schema': 'neural066_view_private_provenance_v1', 'arm': condition, 'support_commitment': support, 'outer_shuffle': outer_mapping, 'original_training_order': list(case['train_keys']), 'source_projection': contracts['projection_pin'], 'unshuffled_train': unshuffled}
    pp = new_json(out / 'PROVENANCE_PRIVATE.json', provenance)
    return {'view': vp, 'layout': lp, 'geometry': gp, 'arrays': arrays, 'private_queries': private, 'training_private_join': {row['id']: key(r) for row, r in zip(layout, tr)}, 'support_commitment': support, 'provenance': pp, 'context': {'case': view['case'], 'modality': mod, 'condition': condition, 'generation': view['generation']}}

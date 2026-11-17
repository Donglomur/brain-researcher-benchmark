"""Prospective exact-native metadata capture; all data access is explicit.

Construction tests inject a small fake library. Production supplies the pinned
MNE1.13.2 runtime after source/qualification checks and NativeIO activation.
"""
import math
import sys
from pathlib import Path

from custody import need
from source_plan import encode, digest


FIELDS = ('Stim_trigger', 'Category', 'Orientation', 'Duration', 'Task_relevance', 'Response')


def primitive_events(np, values, cap, *, allow_empty=False):
    need(isinstance(values, np.ndarray) and values.ndim == 2 and values.shape[1] == 3
         and (0 if allow_empty else 1) <= values.shape[0] <= cap
         and values.dtype.kind in 'iu', 'bounded observed native event matrix')
    need(bool(np.all(values >= 0)) and bool(np.all(values <= 10**12)), 'native integral event domain')
    return values.tolist()


def epoch_snapshot(np, epochs, caps):
    selection = epochs.selection
    need(isinstance(selection, np.ndarray) and selection.ndim == 1 and selection.dtype.kind in 'iu'
         and 0 < len(selection) <= caps['max_retained'], 'complete bounded native retained selection')
    events = primitive_events(np, epochs.events, caps['max_retained'])
    need(len(events) == len(selection), 'native retained alignment')
    need(bool(np.all(selection >= 0)) and bool(np.all(selection < caps['max_events'])), 'retained original event indices')
    metadata = epochs.metadata
    need(metadata is not None and set(FIELDS).issubset(metadata.columns) and len(metadata) == len(selection),
         'native saved metadata for all retained epochs')
    rows = []
    for _, row in metadata.iterrows():
        value = row['Stim_trigger']
        need(np.isscalar(value) and not isinstance(value, (bool, np.bool_))
             and bool(np.isfinite(value)) and float(value) == int(value), 'native integral stimulus identity')
        response = row['Response']
        if isinstance(response, np.bool_):
            response = bool(response)
        need(type(response) is bool or (type(response) is str and response in ('True', 'False')),
             'native explicit Response boolean')
        projected = {key: row[key] for key in FIELDS if key not in ('Stim_trigger', 'Response')}
        need(all(type(v) is str and 0 < len(v) <= 128 for v in projected.values()), 'source condition strings')
        rows.append(dict(projected, Stim_trigger=int(value), Response=response))
    drop = epochs.drop_log
    need(type(drop) in (tuple, list) and 0 < len(drop) <= caps['max_events'], 'complete native drop domain')
    reasons = []
    for item in drop:
        need(type(item) in (tuple, list) and len(item) <= 512
             and all(type(v) is str and v.isascii() and 0 < len(v) <= 128 for v in item), 'native drop reasons')
        reasons.append(list(item))
    sfreq = float(epochs.info['sfreq'])
    need(math.isfinite(sfreq) and 1 <= sfreq <= 10000, 'saved epoch clock')
    names = list(epochs.ch_names)
    need(0 < len(names) <= 512 and len(set(names)) == len(names)
         and all(type(s) is str and 0 < len(s) <= 128 for s in names), 'saved channel identity')
    times = epochs.times
    need(isinstance(times, np.ndarray) and times.ndim == 1 and 2 <= len(times) <= 10001
         and times.dtype.kind == 'f' and bool(np.isfinite(times).all()), 'saved epoch time grid')
    header = {'channels': names, 'channel_types': list(epochs.get_channel_types()),
              'bads': list(epochs.info['bads']), 'times': times.tolist(), 'sfreq': sfreq}
    observation = {'sfreq': sfreq, 'selection': selection.tolist(), 'events': events,
                   'metadata': rows, 'drop_log': reasons}
    # Canonical encoding also rejects nonprimitive/nonfinite header fields.
    return observation, digest(encode({'observations': observation, 'header': header}))


def verify_split_group(library, stage, group, budget):
    """Resolve the same native next-file helper, without auto-follow/data reads."""
    paths = [Path(stage) / row['path'] for row in group['parts']]
    for index, path in enumerate(paths):
        budget.check()
        fid = None
        try:
            fid, tree, _ = library.fiff_open(path, preload=False, verbose='ERROR')
            library.split_metadata(fid, tree)
            nxt = library.next_fname(fid, path, tree)
            expected = paths[index + 1] if index + 1 < len(paths) else None
            need(nxt == expected, 'exact complete ordered split chain before automatic native follow')
        finally:
            original = sys.exception()
            if fid is not None:
                try: fid.close()
                except BaseException as cleanup:
                    if original is not None and not isinstance(original, Exception): raise original
                    raise cleanup from original
        budget.check()
    return paths


def raw_geometry(np, raw, group_paths, caps):
    need(tuple(raw.filenames) == tuple(group_paths), 'native raw opened only the verified split closure')
    first = int(raw.first_samp); last = int(raw.last_samp); sfreq = float(raw.info['sfreq'])
    need(0 <= first <= last <= 10**12 and last - first + 1 == int(raw.n_times)
         and int(raw.n_times) <= caps['max_raw_samples'] and math.isfinite(sfreq)
         and 1 <= sfreq <= 10000 and 0 < len(raw.ch_names) <= 512, 'bounded complete raw geometry')
    firsts = [int(x) for x in raw._first_samps]; lasts = [int(x) for x in raw._last_samps]
    need(len(firsts) == len(group_paths) and len(lasts) == len(firsts)
         and firsts[0] == first and lasts[-1] == last
         and all(a <= b for a, b in zip(firsts, lasts))
         and all(a == b + 1 for a, b in zip(firsts[1:], lasts[:-1])), 'physical continuity within source split run')
    gaps = []
    need(len(raw._raw_extras) == len(group_paths), 'native split metadata extent')
    for extra in raw._raw_extras:
        entries = extra['ent']; bounds = extra['bounds']
        need(len(bounds) == len(entries) + 1 and len(entries) <= caps['max_events'], 'bounded native buffer geometry')
        starts = bounds[:-1]; ends = bounds[1:]
        for ent, lo, hi in zip(entries, starts, ends):
            lo = int(lo); hi = int(hi)
            need(first <= lo < hi <= last + 1, 'native buffer within physical raw domain')
            if ent is None:
                gaps.append([lo, hi])
            else:
                need(int(ent.type) not in (20, 21), 'real-valued raw recording profile')
    return {'first_sample': first, 'last_sample': last, 'sfreq': sfreq, 'gaps': gaps}


def capture_person(library, *, person, item, stage, source_roster_pin, history_sha256,
                   bridge, caps, budget):
    np = library.np
    runs = []; native_events = []; firsts = []; lasts = []; gap_map = {}
    for selected in item['runs']:
        budget.check()
        paths = {role: verify_split_group(library, stage, selected[role], budget)
                 for role in ('annot_raw', 'filtered_raw', 'events')}
        annot = filtered = None
        try:
            annot = library.mne.io.read_raw_fif(paths['annot_raw'][0], preload=False,
                                               allow_maxshield=False, on_split_missing='raise', verbose='ERROR')
            filtered = library.mne.io.read_raw_fif(paths['filtered_raw'][0], preload=False,
                                                  allow_maxshield=False, on_split_missing='raise', verbose='ERROR')
            a = raw_geometry(np, annot, paths['annot_raw'], caps)
            f = raw_geometry(np, filtered, paths['filtered_raw'], caps)
            need(all(a[k] == f[k] for k in ('first_sample', 'last_sample', 'sfreq')),
                 'observed P04 and P07 raw clocks/bounds agree; no inferred event rescaling')
            need('STI101' in annot.ch_names, 'author trigger channel present')
            response = library.mne.find_events(annot, stim_channel='STI101', consecutive=False,
                                               mask=65280, mask_type='not_and', verbose='ERROR')
            other = library.mne.find_events(annot, stim_channel='STI101', consecutive=True,
                                            min_duration=0.001001, mask=65280, mask_type='not_and', verbose='ERROR')
            primitive_events(np, response, caps['max_events'], allow_empty=True)
            primitive_events(np, other, caps['max_events'], allow_empty=True)
            observed = np.concatenate((response[response[:, 2] == 255], other[other[:, 2] != 255]), axis=0)
            need(len(observed) <= caps['max_events'], 'complete native event count')
            observed = observed[observed[:, 0].argsort(), :]
            saved = library.mne.read_events(paths['events'][0], verbose='ERROR')
            primitive_events(np, saved, caps['max_events'])
            need(np.array_equal(observed, saved), 'full trigger-derived event stream equals selected original event FIF')
            rows = primitive_events(np, observed, caps['max_events'])
            primary_raw = selected['annot_raw']['parts'][0]
            primary_events = selected['events']['parts'][0]
            runs.append({'run': selected['run'], 'first_sample': a['first_sample'], 'last_sample': a['last_sample'],
                         'sfreq': a['sfreq'], 'raw_source': {k: primary_raw[k] for k in ('bytes', 'sha256')},
                         'event_source': {k: primary_events[k] for k in ('bytes', 'sha256')}, 'events': rows})
            native_events.append(saved); firsts.append(f['first_sample']); lasts.append(f['last_sample'])
            gap_map[selected['run']] = {
                'annot': a['gaps'] + library.acquisition_gaps(annot, caps['max_events']),
                'filtered': f['gaps'] + library.acquisition_gaps(filtered, caps['max_events'])}
        finally:
            original = sys.exception()
            errors = []
            for raw in (filtered, annot):
                if raw is not None:
                    try:
                        raw.close()
                    except BaseException as exc:
                        errors.append(exc)
            if errors:
                if original is not None and not isinstance(original, Exception):
                    raise original
                raise errors[0]
        budget.check()
    need(sum(len(v) for v in native_events) <= caps['max_events'], 'whole person native event cap')
    combined = library.mne.concatenate_events(native_events, firsts, lasts)
    combined_rows = primitive_events(np, combined, caps['max_events'])
    epoch_paths = verify_split_group(library, stage, item['epochs'], budget)
    epochs = None
    try:
        epochs = library.mne.read_epochs(epoch_paths[0], preload=False, verbose='ERROR')
        observed_epochs, identity = epoch_snapshot(np, epochs, caps)
        primary = item['epochs']['parts'][0]
        observed_epochs['source'] = {k: primary[k] for k in ('bytes', 'sha256')}
    finally:
        original = sys.exception()
        if epochs is not None:
            try: library.close_epochs(epochs)
            except BaseException as cleanup:
                if original is not None and not isinstance(original, Exception): raise original
                raise cleanup from original
    budget.check()
    observation = {'schema': 'neural098-event-observation-v1', 'participant': person,
                   'source_roster': source_roster_pin, 'extraction_profile': dict(bridge.EXTRACTION),
                   'runs': runs, 'concatenated_events': combined_rows, 'epochs': observed_epochs,
                   'preprocessing_provenance': {'history_sha256': history_sha256,
                      'epoch_event_coordinates': item['epoch_coordinates']}}
    return observation, {'epoch_identity_sha256': identity, 'raw_gap_intervals': gap_map}


def verify_gap_horizons(observation, bindings, gaps, scientific, budget):
    """Gaps cannot establish button-free support or measured window values."""
    need(len(bindings['rows']) == len(observation['epochs']['metadata']), 'all retained gap joins')
    sfreq = bindings['sfreq']
    for binding, meta in zip(bindings['rows'], observation['epochs']['metadata']):
        budget.check()
        onset = binding['event_sample']; duration = int(meta['Duration'][:-2])
        available = scientific['AVAILABLE'][duration]
        spans = [scientific['BASELINE']] + [scientific['WINDOWS'][v] for v in available]
        for role, intervals in gaps[binding['run']].items():
            required = [(-.5, duration / 1000 + .3)] if role == 'annot' else spans
            for start, stop in intervals:
                for low, high in required:
                    intersects = ((stop - 1 - onset) / sfreq >= low and (start - onset) / sfreq < high)
                    need(not intersects, 'retained required raw interval intersects acquisition gap; no synthetic zero support')

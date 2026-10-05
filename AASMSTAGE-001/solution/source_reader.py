"""Original EDF headers/annotations and native MNE two-channel sample reader."""
from collections import Counter
from decimal import Decimal
import hashlib
from pathlib import Path

import mne
import numpy as np

CHANNELS = ['EEG Fpz-Cz', 'EEG Pz-Oz']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_edf_header(path):
    with Path(path).open('rb') as stream:
        fixed = stream.read(256)
        require(len(fixed) == 256, 'Truncated EDF header')
        fields, offset = {}, 0
        for name, size in [('version', 8), ('patient', 80), ('recording', 80),
                           ('start_date', 8), ('start_time', 8), ('header_bytes', 8),
                           ('reserved', 44), ('n_records', 8), ('record_duration_text', 8),
                           ('n_signals', 4)]:
            fields[name] = fixed[offset:offset+size].decode('ascii').strip()
            offset += size
        ns = int(fields['n_signals'])
        nh = int(fields['header_bytes'])
        require(ns > 0 and nh == 256*(ns+1), 'Invalid EDF channel/header dimensions')
        variable = stream.read(nh-256)
        require(len(variable) == nh-256, 'Truncated EDF channel headers')
    channels, offset = [{} for _ in range(ns)], 0
    for name, size in [('label', 16), ('transducer', 80), ('physical_dimension', 8),
                       ('physical_min_text', 8), ('physical_max_text', 8),
                       ('digital_min_text', 8), ('digital_max_text', 8),
                       ('prefilter', 80), ('samples_per_record_text', 8), ('reserved', 32)]:
        for channel in channels:
            channel[name] = variable[offset:offset+size].decode('ascii').strip()
            offset += size
    nrecords = int(fields['n_records'])
    duration = Decimal(fields['record_duration_text'])
    annotation_only = all(c['label'] == 'EDF Annotations' for c in channels)
    require(nrecords > 0 and duration.is_finite() and
            (duration > 0 or (annotation_only and duration == 0)), 'Invalid EDF record duration/count')
    for row, channel in enumerate(channels):
        samples = int(channel['samples_per_record_text'])
        numbers = [Decimal(channel[k]) for k in ('physical_min_text', 'physical_max_text',
                                                  'digital_min_text', 'digital_max_text')]
        require(samples > 0 and all(x.is_finite() for x in numbers) and numbers[3] > numbers[2],
                'Invalid EDF channel calibration/sample count')
        channel.update(row=row, sfreq_hz=float(Decimal(samples)/duration) if duration > 0 else None,
                       n_samples=samples*nrecords)
    require(Path(path).stat().st_size == nh+2*nrecords*sum(int(c['samples_per_record_text']) for c in channels),
            'EDF byte extent differs from fixed-header record dimensions')
    public = {k: fields[k] for k in ('version', 'start_date', 'start_time', 'reserved', 'record_duration_text')}
    public.update(header_bytes=nh, n_records=nrecords, n_signals=ns,
                  header_sha256=hashlib.sha256(fixed+variable).hexdigest())
    return public, channels


def parse_tals(payload):
    rows, keepers = [], []
    for tal_index, tal in enumerate(t for t in payload.split(b'\0') if t):
        pieces = tal.split(b'\x14')
        require(len(pieces) >= 2 and pieces[-1] == b'', 'Malformed annotation TAL delimiter')
        clock = pieces[0].split(b'\x15')
        require(len(clock) in (1, 2), 'Malformed annotation onset/duration')
        onset = Decimal(clock[0].decode('ascii'))
        duration = Decimal(clock[1].decode('ascii')) if len(clock) == 2 else Decimal(0)
        require(onset.is_finite() and duration.is_finite() and duration >= 0
                and (onset+duration).is_finite()
                and np.isfinite([float(onset), float(duration), float(onset+duration)]).all(), 'Invalid annotation time')
        descriptions = [p.decode('utf-8') for p in pieces[1:] if p]
        if not descriptions:
            keepers.append(dict(tal_index=tal_index, onset_s=float(onset)))
        for description in descriptions:
            rows.append(dict(annotation_index=len(rows), tal_index=tal_index,
                             onset_s=float(onset), duration_s=float(duration), description=description))
    return rows, keepers


def read_hypnogram(path, header, channels):
    require(len(channels) == 1 and channels[0]['label'] == 'EDF Annotations', 'Hypnogram must contain annotations only')
    with Path(path).open('rb') as stream:
        stream.seek(header['header_bytes'])
        rows, keepers = parse_tals(stream.read())
    native = mne.read_annotations(path)
    require(native.orig_time is None, 'Annotation origin must be recording-relative')
    require(keepers == [dict(tal_index=0, onset_s=0.0)], 'Unexpected original annotation timekeeping TAL')
    require(len(rows) == len(native), 'Native and original annotation count differ')
    for row, onset, duration, description in zip(rows, native.onset, native.duration, native.description):
        require(row['onset_s'] == onset and row['duration_s'] == duration and row['description'] == description,
                'Original TAL order differs from native annotation order')
    return rows, keepers


def annotation_ledgers(subject, rows, n_samples, method):
    require(len(rows) >= 3, 'At least three original annotations required')
    mapping = method['classes']['annotation_mapping']
    left, right = rows[1]['onset_s']-1800.0, rows[-2]['onset_s']+1800.0
    require(np.isfinite([left, right]).all() and right > left, 'Invalid original-index crop')
    effective_left, effective_right = max(0., left), min(n_samples/100., right)
    require(effective_right > effective_left, 'Empty crop support')
    annotations, epochs = [], []
    for source in rows:
        onset, duration = source['onset_s'], source['duration_s']
        require(np.isfinite([onset, duration, onset+duration]).all() and duration >= 0, 'Invalid source annotation')
        a, b = max(onset, left, 0.), min(onset+duration, right, n_samples/100.)
        label = mapping.get(source['description'])
        row = dict(subject=subject, recording=1, **source, stage_id=label,
                   effective_onset_s=None, effective_stop_s=None, n_complete_chunks=0,
                   discarded_tail_s=None, status='outside_crop_or_recording')
        if b >= a:
            require(all(abs(t-np.rint(t*100)/100) <= 1e-9 for t in (a, b)), 'Annotation bounds not sample-aligned')
            starts = [float(t) for t in np.arange(a, b, 30.) if b-t >= 30.-1e-8]
            row.update(effective_onset_s=a, effective_stop_s=b, n_complete_chunks=len(starts),
                       discarded_tail_s=max(0., b-a-30*len(starts)),
                       status='unsupported_stage' if label is None else 'used' if starts else 'no_complete_chunk')
            for chunk, start in enumerate(starts):
                sample = int(np.rint(start*100))
                require(abs(start-sample/100) <= 1e-9, 'Chunk onset not sample-aligned')
                stop = sample+3000
                bad = any(r['description'].lower().startswith('bad') and r['duration_s'] > 0
                          and start < r['onset_s']+r['duration_s'] and start+30 > r['onset_s'] for r in rows)
                reason = ('unsupported_stage' if label is None else
                          'outside_recording' if sample < 0 or stop > n_samples else
                          'overlap_bad_annotation' if bad else 'retained')
                epochs.append(dict(subject=subject, recording=1, annotation_index=source['annotation_index'],
                                   chunk_index=chunk, onset_s=start, onset_sample=sample,
                                   end_sample_exclusive=stop, n_samples=3000, stage_id=label,
                                   retained=reason == 'retained', drop_reason=reason))
        annotations.append(row)
    epochs.sort(key=lambda r: r['onset_sample'])
    require(len({r['onset_sample'] for r in epochs}) == len(epochs), 'Duplicate original candidate sample keys')
    mapped = [r for r in epochs if r['stage_id'] is not None]
    require(all(a['end_sample_exclusive'] <= b['onset_sample'] for a, b in zip(mapped, mapped[1:])),
            'Overlapping mapped candidate epochs')
    retained = sum(r['retained'] for r in epochs)
    require(retained > 0, 'No retained source epochs')
    diagnostics = dict(requested_crop_start_s=left, requested_crop_stop_s=right,
                       effective_crop_start_s=effective_left, effective_crop_stop_s=effective_right,
                       n_candidate_epochs=len(epochs), n_retained_epochs=retained,
                       n_dropped_epochs=len(epochs)-retained,
                       annotation_status_counts=dict(Counter(r['status'] for r in annotations)),
                       epoch_status_counts=dict(Counter(r['drop_reason'] for r in epochs)),
                       n_duplicate_candidate_start_samples=0)
    return annotations, epochs, diagnostics


def inspect_subject(subject, psg_path, hyp_path, method):
    psg, channels = read_edf_header(psg_path)
    hyp, hyp_channels = read_edf_header(hyp_path)
    require(all(psg[k] == hyp[k] for k in ('start_date', 'start_time')), 'PSG/hypnogram start differs')
    require([c['label'] for c in channels[:2]] == CHANNELS, 'Prescribed original EEG rows absent')
    require(all(c['sfreq_hz'] == 100 and c['physical_dimension'] == 'uV' for c in channels[:2]),
            'EEG sample rate or physical unit differs')
    require(channels[0]['n_samples'] == channels[1]['n_samples'], 'EEG channels have unequal support')
    rows, keepers = read_hypnogram(hyp_path, hyp, hyp_channels)
    n_samples = channels[0]['n_samples']
    annotations, epochs, diagnostics = annotation_ledgers(subject, rows, n_samples, method)
    deltas = [b['onset_s']-(a['onset_s']+a['duration_s']) for a, b in zip(rows, rows[1:])]
    observed = dict(subject=subject, recording=1, psg_path=Path(psg_path).name,
                    hypnogram_path=Path(hyp_path).name, psg_header=psg, hypnogram_header=hyp,
                    header_start_date_time_match=True, annotation_orig_time=None,
                    annotation_timekeepers=keepers, annotation_source_order_equal_mne=True,
                    first_samp=0, sfreq_hz=100, n_samples=n_samples,
                    recording_duration_s=n_samples/100., eeg_channels=channels[:2],
                    n_source_annotations=len(rows),
                    annotation_description_counts=dict(Counter(r['description'] for r in rows)),
                    n_bad_prefix_annotations=sum(r['description'].lower().startswith('bad') for r in rows),
                    n_annotation_gaps=sum(x > 1e-9 for x in deltas),
                    n_annotation_overlaps=sum(x < -1e-9 for x in deltas), **diagnostics)
    return annotations, epochs, observed


def read_retained_epochs(psg_path, epochs, observed):
    """Native EDF decoding only after full source/method verification by caller."""
    kept = [r for r in epochs if r['retained']]
    require(bool(kept), 'Empty retained source support')
    raw = mne.io.read_raw_edf(psg_path, include=CHANNELS, infer_types=False,
                              stim_channel=None, preload=False, verbose=False)
    try:
        require(raw.ch_names == CHANNELS and raw.info['sfreq'] == 100 and raw.first_samp == 0
                and raw.n_times == observed['n_samples'], 'Native reader differs from source header')
        start, stop = kept[0]['onset_sample'], kept[-1]['end_sample_exclusive']
        values = raw.get_data(picks=CHANNELS, start=start, stop=stop)
        array = np.stack([values[:, r['onset_sample']-start:r['end_sample_exclusive']-start] for r in kept])
        require(array.shape == (len(kept), 2, 3000) and array.dtype == np.float64
                and np.isfinite(array).all(), 'Invalid retained original EEG samples')
        return array
    finally:
        raw.close()

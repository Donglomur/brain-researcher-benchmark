"""Future deterministic local-only NWB preparation. Does not compute PAC.

Requires the full pinned source AND independently reviewed preprocessing/masks.
The supplied example masks are deliberately not accepted as a cohort mask.
"""
import argparse
import hashlib
import hmac
import io
import json
import math
from pathlib import Path
import numpy as np
from io_utils import read_json, ordinary_bytes, strict_json


def need(ok, message):
    if not ok: raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def opaque(key, value):
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:24]


def text(x):
    return x.decode('utf-8') if isinstance(x, bytes) else str(x)


def window_index(maintenance, probe, start, samples):
    need(all(math.isfinite(v) for v in (maintenance, probe, start)), 'Finite source clocks')
    first = math.ceil((maintenance - start) * 400)
    last = first + 1000
    # Sample support and conceptual full epoch must precede the probe.
    need(first >= 0 and last <= samples and maintenance + 2.5 <= probe
         and start + (last - 1) / 400 < maintenance + 2.5,
         'Complete 2.5s maintenance window before probe required')
    return first, last


def validate_review(review, assets):
    need(set(review) == {'schema', 'sessions'} and review['schema'] == 'neural042_clinical_review_v1', 'Clinical review schema')
    rows = review['sessions']; need(type(rows) is list and len(rows) == 44, '44 explicit session review records')
    by_id = {r['asset_id']: r for r in rows}
    need(len(by_id) == 44 and set(by_id) == {a['asset_id'] for a in assets}, 'Full source review join')
    for a in assets:
        r = by_id[a['asset_id']]
        need(set(r) == {'asset_id', 'source_sha256', 'preprocessing', 'evidence', 'channels'}, 'Exact session review fields')
        need(r['source_sha256'] == a['sha256'], 'Review bound to original bytes')
        need(r['preprocessing'] == {'local_reference_verified': True,
                                    'spike_interpolation_before_downsampling_verified': True,
                                    'lowpass_175hz_and_400hz_verified': True,
                                    'notch_60_120hz_verified': True}, 'Published preprocessing provenance unresolved')
        need(type(r['evidence']) is str and 20 <= len(r['evidence']) <= 4000, 'Reviewed documentary evidence required')
        need(type(r['channels']) is list and len(r['channels']) > 0, 'Every source channel reviewed')
    return by_id


def validate_channel_review(r):
    need(set(r) == {'row0', 'exclude_channel', 'reason', 'bad_trial_rows0'} and type(r['row0']) is int
         and 0 <= r['row0'] < 512 and type(r['exclude_channel']) is bool and type(r['reason']) is str
         and type(r['bad_trial_rows0']) is list
         and all(type(i) is int and 0 <= i < 140 for i in r['bad_trial_rows0'])
         and len(set(r['bad_trial_rows0'])) == len(r['bad_trial_rows0']), 'Exact channel review/mask')
    need(not r['exclude_channel'] or len(r['reason'].strip()) > 0, 'Clinical exclusion requires reason')


def mean_rate(trains, maintenance):
    need(len(trains) > 0 and math.isfinite(maintenance), 'Nonempty co-located unit set')
    count = sum(int(np.searchsorted(s, maintenance+2.5, 'left') - np.searchsorted(s, maintenance, 'left')) for s in trains)
    return count / (2.5 * len(trains))


def publish_metadata(output, used, cap, manifest, exclusions, review_body, lock_body):
    """Reserve every final metadata byte before writing; packet is completion marker."""
    encode=lambda x:(json.dumps(x,indent=2,allow_nan=False)+'\n').encode('utf-8')
    metadata={'packet.json':encode(manifest), 'OPERATOR_EXCLUSIONS.json':encode(exclusions),
              'OPERATOR_CLINICAL_REVIEW.json':review_body, 'OPERATOR_SOURCE_LOCK.json':lock_body}
    bindings={name:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for name,b in metadata.items()}
    metadata['OPERATOR_SOURCE_BINDING.json']=encode(bindings)
    need(used+sum(len(b) for b in metadata.values())<=cap,
         'Output cap includes metadata; incomplete directory is not a packet')
    for name,b in metadata.items():
        if name!='packet.json':(output/name).write_bytes(b)
    (output/'packet.json').write_bytes(metadata['packet.json'])


def build(source_root, lock, review_path, key_path, output, cap):
    import h5py
    source_root, output = Path(source_root).resolve(), Path(output)
    need(not output.exists() and type(cap) is int and 0 < cap <= 100_000_000_000, 'Fresh output and explicit byte cap')
    lock_body = ordinary_bytes(lock, 1_000_000)
    assets = strict_json(lock_body)['assets']
    need(len(assets) == 44 and len({a['asset_id'] for a in assets}) == 44
         and len({a['subject_id'] for a in assets}) == 36
         and sum(a['bytes'] for a in assets) == 23447043476, 'Complete pinned 2024 cohort')
    # Do not let a caller replace source pins with an arbitrary 44-record list.
    held = read_json(Path(__file__).with_name('SOURCE_ASSETS.json'))
    need(assets == held['assets'], 'Exact immutable source lock required')
    review_body = ordinary_bytes(review_path, 16_000_000)
    review = validate_review(strict_json(review_body), assets)
    key = ordinary_bytes(key_path, 32); need(len(key) == 32, 'Private32-byte ID key')
    for a in assets:
        p = source_root / a['path']
        need(p.is_file() and not p.is_symlink() and p.resolve() == p and p.stat().st_size == a['bytes'] and digest(p) == a['sha256'], 'Full source asset pin mismatch')
    output.mkdir(mode=0o700); (output/'channels').mkdir()
    records, exclusions, used = [], [], 0
    for a in assets:
        with h5py.File(source_root / a['path'], 'r') as f:
            need(text(f['general/subject/subject_id'][()]) == a['subject_id'], 'Source subject join')
            group = f['acquisition/LFPs']; data = group['data']
            rate = float(group['starting_time'].attrs['rate']); start = float(group['starting_time'][()])
            need(rate == 400 and data.ndim == 2 and data.dtype.kind in 'fiu' and data.shape[1] <= 512, 'Exact400Hz time x channel LFP')
            need(text(data.attrs.get('unit', '')) in ('volts', 'volt', 'V'), 'Explicit volts required')
            conv = float(data.attrs.get('conversion', 1)); offset = float(data.attrs.get('offset', 0))
            cc = np.asarray(group['channel_conversion']) if 'channel_conversion' in group else np.ones(data.shape[1])
            need(cc.shape == (data.shape[1],) and np.isfinite(cc).all() and (cc > 0).all()
                 and math.isfinite(conv) and conv > 0 and math.isfinite(offset), 'LFP conversion')
            electrode = np.asarray(group['electrodes']); locations = f['general/extracellular_ephys/electrodes/location']
            need(electrode.shape == (data.shape[1],) and electrode.dtype.kind in 'iu'
                 and len(set(electrode.tolist())) == len(electrode) and np.all((electrode >= 0) & (electrode < len(locations))), 'LFP electrode row mapping')
            fields = {k: np.asarray(f['intervals/trials/'+k]) for k in ('loads', 'response_accuracy', 'probe_in_out', 'timestamps_Maintenance', 'timestamps_Probe')}
            need(all(v.shape == (140,) and v.dtype.kind in 'biuf' and np.isfinite(v).all() for v in fields.values()), 'All140 aligned trial fields required')
            need(set(fields['loads']) <= {1, 3} and set(fields['response_accuracy']) <= {0, 1} and set(fields['probe_in_out']) <= {0, 1}, 'Unexpected source condition encoding; resolve without guessing')
            units = f['units']; ends = np.asarray(units['spike_times_index']); ue = np.asarray(units['electrodes'])
            need(ends.ndim == 1 and ends.dtype.kind in 'iu' and np.all(np.diff(np.r_[0, ends]) >= 0)
                 and (len(ends) == 0 or ends[-1] == len(units['spike_times'])), 'Ragged unit spike bounds')
            if 'electrodes_index' in units:
                ei = np.asarray(units['electrodes_index']); need(ei.shape == ends.shape and np.array_equal(ei, np.arange(1, len(ei)+1)), 'Only verified one-electrode units supported')
            need(ue.shape == ends.shape and ue.dtype.kind in 'iu' and np.all((ue >= 0) & (ue < len(locations))), 'Unit electrode association')
            reviewed = review[a['asset_id']]['channels']
            need(len(reviewed) == data.shape[1] and {r['row0'] for r in reviewed} == set(range(data.shape[1])), 'No omitted or extra channel review rows')
            for r in sorted(reviewed, key=lambda x: x['row0']):
                validate_channel_review(r)
                ch = r['row0']; el = electrode[ch]; loc = text(locations[el])
                selected_units = np.flatnonzero(ue == el)
                reason = ('outside_hippocampus' if loc not in ('hippocampus_left', 'hippocampus_right') else
                          'reviewed_channel_exclusion' if r['exclude_channel'] else
                          'no_colocated_sorted_unit' if len(selected_units) == 0 else None)
                if reason:
                    exclusions.append({'asset_id': a['asset_id'], 'channel_row0': ch, 'reason': reason}); continue
                trial_rows = [i for i in range(140) if i not in r['bad_trial_rows0']]
                if not trial_rows:
                    exclusions.append({'asset_id': a['asset_id'], 'channel_row0': ch, 'reason': 'all_trials_review_excluded'}); continue
                trains = []
                for u in selected_units:
                    spikes = np.asarray(units['spike_times'][0 if u == 0 else ends[u-1]:ends[u]], float)
                    need(np.isfinite(spikes).all() and np.all(np.diff(spikes) >= 0), 'Finite sorted per-unit spikes')
                    trains.append(spikes)
                x, rates = [], []
                for i in trial_rows:
                    first, last = window_index(float(fields['timestamps_Maintenance'][i]), float(fields['timestamps_Probe'][i]), start, len(data))
                    y = np.asarray(data[first:last, ch], float) * conv * cc[ch] + offset
                    need(y.shape == (1000,) and np.isfinite(y).all(), 'Finite complete trial; no silent dropping')
                    x.append(y); rates.append(mean_rate(trains, float(fields['timestamps_Maintenance'][i])))
                identity = opaque(key, a['asset_id']+':'+str(ch)); ids = [opaque(key, a['asset_id']+':trial:'+str(i)) for i in trial_rows]
                # Original trial ordering is retained only as a declared drift covariate.
                buf = io.BytesIO(); np.savez(buf, lfp=np.asarray(x), rates=np.asarray(rates),
                    loads=fields['loads'][trial_rows].astype('int8'), correct=fields['response_accuracy'][trial_rows].astype('int8'),
                    probe=fields['probe_in_out'][trial_rows].astype('int8'), order=np.asarray(trial_rows, 'int16'), ids=np.asarray(ids,'U24'))
                body = buf.getvalue(); used += len(body); need(used <= cap, 'Prepared-data byte cap exceeded; partial directory is not a packet')
                name = 'channels/'+identity+'.npz'; (output/name).write_bytes(body)
                records.append({'id': identity, 'patient': opaque(key, 'patient:'+a['subject_id']),
                                'session': opaque(key, a['asset_id']), 'path': name, 'bytes': len(body),
                                'sha256': hashlib.sha256(body).hexdigest(), 'n_trials': len(trial_rows)})
    manifest = {'schema': 'neural042_packet_v1', 'patients': sorted({opaque(key,'patient:'+a['subject_id']) for a in assets}),
                'source_sessions': 44, 'channels': sorted(records, key=lambda r:r['id'])}
    # These exact source inputs are private. Packet pinning alone cannot recover
    # which externally reviewed mask/preprocessing evidence produced the packet.
    publish_metadata(output, used, cap, manifest, exclusions, review_body, lock_body)


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source-root',required=True); p.add_argument('--lock',required=True)
    p.add_argument('--review',required=True); p.add_argument('--key',required=True); p.add_argument('--out',required=True)
    p.add_argument('--max-output-bytes',type=int,required=True); a=p.parse_args()
    build(a.source_root,a.lock,a.review,a.key,a.out,a.max_output_bytes)

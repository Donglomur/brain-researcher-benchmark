"""Third original-source route: direct Boolean multiset counts and paired-U/erfc.

No oracle code, generated counts, prior bank or model receipts are inputs.
Only public schema/parsing and the verifier's independently implemented direct rank
arithmetic are shared. An oracle directory is consulted AFTER source construction.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import time

import h5py
import numpy as np
import population_contract as q
import proof_of_work as proof


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1 << 20), b''): h.update(part)
    return h.hexdigest()


def no_links(path):
    p = Path(os.path.abspath(path))
    for item in (p, *p.parents):
        q.require(not item.is_symlink(), 'Symlinked evidence/source path')
    return p


def destinations(output, report, source):
    paths = [no_links(output), no_links(report)]; root = no_links(source)
    q.require(paths[0] != paths[1], 'Evidence destinations collide')
    for p in paths:
        q.require(not p.exists(), 'Refuse existing evidence destination')
        q.require(p != root and root not in p.parents, 'Evidence must be outside original source tree')
        q.require(not any(other in p.parents for other in paths if other != p), 'Nested evidence file destinations')
    return paths


def load_inputs(source, method):
    root = no_links(source); mp = no_links(method); manifest_path = root/'source_manifest.json'
    q.require(sha(manifest_path) == q.SOURCE_SHA256, 'Wrong frozen source manifest')
    q.require(sha(mp) == q.METHOD_SHA256, 'Wrong frozen public method')
    manifest_text, method_text = manifest_path.read_text(), mp.read_text()
    manifest, contract = json.loads(manifest_text), json.loads(method_text)
    records = manifest['files']; expected = {r['path'] for r in records}
    q.require(len(records) == len(expected) == 87, 'Incomplete frozen inventory')
    files = set()
    for p in root.rglob('*'):
        q.require(not p.is_symlink(), 'Source symlink forbidden')
        q.require(p.is_file() or p.is_dir(), 'Unexpected special source file')
        if p.is_file(): files.add(p.relative_to(root).as_posix())
    q.require(files == expected | {'source_manifest.json'}, 'Unexpected/missing original source files')
    for row in records:
        p = root/row['path']
        q.require(row['role'] == 'session_nwb' and p.is_file(), 'Wrong original source role')
        q.require(p.stat().st_size == row['size_bytes'] and sha(p) == row['sha256'], 'Original file identity failed')
    return root, sorted(records, key=lambda r: r['path']), manifest_text, method_text, contract


def text(value):
    if isinstance(value, (bytes, np.bytes_)): return bytes(value).decode('utf8')
    q.require(isinstance(value, (str, np.str_)), 'Literal source string required')
    return str(value)


def ints(value, unique=False):
    a = np.asarray(value)
    q.require(a.ndim == 1 and a.dtype.kind in 'iu', 'Original integer array required')
    values = [int(x) for x in a]
    q.require(all(-(2**63) <= x < 2**63 for x in values), 'Source integer overflow')
    if unique: q.require(len(set(values)) == len(values), 'Duplicate original IDs')
    return values


def ends(value, n, total):
    result = ints(value)
    q.require(len(result) == n and all(a <= b for a,b in zip([0]+result, result)), 'Invalid ragged source offsets')
    q.require((result[-1] if result else 0) == total, 'Wrong ragged final offset')
    return result


def count_intervals(spikes, onsets):
    """No sorting/search: count each original occurrence with the interval predicate."""
    s, t = np.asarray(spikes, dtype=np.float64), np.asarray(onsets, dtype=np.float64)
    q.require(s.ndim == t.ndim == 1 and np.isfinite(s).all() and np.isfinite(t).all(), 'Nonfinite source time')
    answer = []
    for onset in t:
        lo, hi = onset+np.float64(.2), onset+np.float64(1.7)
        q.require(np.isfinite(lo) and np.isfinite(hi) and lo < hi, 'Invalid count endpoints')
        answer.append(int(np.count_nonzero((s >= lo) & (s < hi))))
    return np.asarray(answer, dtype=np.int64)


def read_asset(path, rec):
    asset = rec['path']; ts, us, responses = [], [], []
    with h5py.File(path, 'r') as f:
        subject = text(f['general/subject/subject_id'][()])
        q.require(subject == rec['participant'], 'Original participant mismatch')
        description = text(f['acquisition/experiment_ids'].attrs['description'])
        declaration = re.fullmatch(r'learning: (\d+), recognition: (\d+)', text(f['general/data_collection'][()]))
        q.require(declaration is not None, 'Unknown source phase declaration')
        phases = dict(zip(('learn','recog'), map(int, declaration.groups())))
        q.require(phases['learn'] != phases['recog'], 'Ambiguous source phases')
        for phase, word in [('learn','learning'), ('recog','recognition')]:
            found = re.findall(rf'The {word} trials are demarcated by: (\d+)\.', description)
            q.require(len(found) == 1 and int(found[0]) == phases[phase], 'Inconsistent phase metadata')
        et = np.asarray(f['acquisition/events/timestamps'][:], dtype=np.float64)
        xt = np.asarray(f['acquisition/experiment_ids/timestamps'][:], dtype=np.float64)
        codes = [q.integer(text(x)) for x in f['acquisition/events/data'][:]]
        exp = [q.integer(x) for x in f['acquisition/experiment_ids/data'][:]]
        q.require(et.ndim == xt.ndim == 1 and len(et) == len(codes) == len(exp), 'Acquisition axes disagree')
        q.require(np.isfinite(et).all() and np.all(np.diff(et) >= 0) and np.array_equal(et, xt), 'Invalid original clocks')
        clock = Counter(zip(exp, codes, et.tolist()))
        table = f['intervals/trials']; ids = ints(table['id'][:], True); n = len(ids)
        phase = [text(x) for x in table['stim_phase'][:]]
        labels = [text(x) for x in table['new_old_labels_recog'][:]]
        images = [text(x) for x in table['external_image_file'][:]]
        times = {name: np.asarray(table[name][:], dtype=np.float64) for name in ('start_time','stim_on_time','stim_off_time','stop_time')}
        q.require(all(len(x) == n for x in (phase, labels, images, *times.values())), 'Original trial axes disagree')
        q.require(set(phase) <= set(phases), 'Unknown original phase')
        q.require(all(a.ndim == 1 and np.isfinite(a).all() for a in times.values()), 'Invalid trial clock')
        learned = {im for ph,im in zip(phase, images) if ph == 'learn'}
        memberships = {f'code{lab}_{state}_learning':0 for lab in (0,1) for state in ('absent_from','present_in')}
        for i, tid in enumerate(ids):
            a,b,c,d = [float(times[k][i]) for k in times]
            q.require(a == b and b <= c, 'Invalid original trial start/onset/offset order')
            q.require(phase[i] != 'recog' or c <= d, 'Invalid recognition trial end order')
            for token, stamp in ((1,b),(2,c),(6,d)):
                q.require(clock[(phases[phase[i]],token,stamp)] == 1, 'Missing unique source TTL mapping')
            included = phase[i] == 'recog'; lab = member = None
            if included:
                q.require(labels[i] in ('0','1'), 'Unknown released recognition label')
                lab = int(labels[i]); member = images[i] in learned
                memberships[f'code{lab}_{"present_in" if member else "absent_from"}_learning'] += 1
            ts.append(dict(asset_path=asset,source_trial_row=i,trial_id=tid,stim_phase=phase[i],source_label_token=labels[i],
                source_label=lab,external_image_file=images[i],image_in_learning=member,start_time_s=a,stim_on_time_s=b,
                stim_off_time_s=c,stop_time_s=d,included=included,status='included_recognition' if included else 'non_recognition_phase'))
        recognition = [r for r in ts if r['included']]
        electrode = f['general/extracellular_ephys/electrodes']; eids = ints(electrode['id'][:], True)
        channels = ints(electrode['origChannel'][:]); locations = [text(x) for x in electrode['location'][:]]
        q.require(len(eids) == len(channels) == len(locations), 'Original electrode axes disagree')
        units = f['units']; uids = ints(units['id'][:], True)
        q.require(f[units['electrodes'].attrs['table']].name == electrode.name, 'Wrong DynamicTableRegion target')
        links = ints(units['electrodes'][:]); le = ends(units['electrodes_index'][:],len(uids),len(links))
        se = ends(units['spike_times_index'][:],len(uids),len(units['spike_times']))
        q.require(all(b-a == 1 for a,b in zip([0]+le,le)), 'Ambiguous electrode links')
        q.require('obs_intervals' not in units and 'intervals/invalid_times' not in f, 'Unexpected observation tables')
        inversion = unordered = adjacent = duplicate = 0
        for i,uid in enumerate(uids):
            erow = links[i]; q.require(0 <= erow < len(eids), 'Electrode row outside table')
            location = locations[erow]; hits = [x for x in ('Hippocampus','Amygdala') if x in location]
            q.require(len(hits) <= 1, 'Ambiguous source anatomy')
            key = asset+'::unit='+str(uid)
            us.append(dict(asset_path=asset,unit_key=key,source_unit_row=i,unit_id=uid,n_electrode_links=1,
                electrode_row=erow,electrode_id=eids[erow],original_channel=channels[erow],location=location,
                included=bool(hits),region=hits[0] if hits else None,exclusion_reason='included_mtl' if hits else 'non_mtl_location'))
            s = np.asarray(units['spike_times'][se[i-1] if i else 0:se[i]],dtype=np.float64)
            q.require(s.ndim == 1 and np.isfinite(s).all(), 'Nonfinite original spike event')
            diff = np.diff(s); inv = int(np.count_nonzero(diff < 0)); inversion += inv; unordered += int(inv > 0)
            adjacent += int(np.count_nonzero(diff == 0)); duplicate += len(s)-len(set(s.tolist()))
            if hits:
                counts = count_intervals(s, [r['stim_on_time_s'] for r in recognition])
                responses.append((key,recognition,counts))
        label_description = text(table['new_old_labels_recog'].attrs['description'])
        def attr(node): return text(node.attrs['unit']) if 'unit' in node.attrs else None
        observed = dict(asset_path=asset,nwb_version=text(f.attrs['nwb_version']),session_start_time=text(f['session_start_time'][()]),
            timestamps_reference_time=text(f['timestamps_reference_time'][()]),event_timestamp_unit=attr(f['acquisition/events/timestamps']),
            experiment_timestamp_unit=attr(f['acquisition/experiment_ids/timestamps']),spike_times_literal_unit=attr(units['spike_times']),
            n_events=len(et),event_timestamps_finite=True,event_timestamps_nondecreasing=True,experiment_timestamps_exactly_match_events=True,
            phase_experiment_ids=phases,clock_mapping_counts=dict(n_trials=n,onset_exact_unique_ttl1=n,offset_exact_unique_ttl2=n,trial_end_exact_unique_ttl6=n,start_equals_stim_on=n),
            source_label_description=label_description,label_description_conflicts_with_released_code_semantics=bool(re.search(r'0\s*=+\s*Old',label_description) and re.search(r'1\s*=+\s*New',label_description)),
            label_membership_counts=memberships,unit_electrode_link_counts=dict(zero=0,one=len(uids),multiple=0),
            units_obs_intervals_present=False,invalid_times_present=False,observation_coverage='unknown',all_spikes_finite=True,
            all_unit_spikes_nondecreasing=unordered == 0,raw_adjacent_inversions=inversion,n_unordered_units=unordered,
            raw_adjacent_duplicate_spikes=adjacent,duplicate_timestamp_occurrences=duplicate,
            n_learning_temporal_order_violations=sum(r['stim_phase']=='learn' and not
                (r['start_time_s'] <= r['stim_on_time_s'] <= r['stim_off_time_s'] <= r['stop_time_s']) for r in ts),
            n_recognition_temporal_order_violations=sum(r['stim_phase']=='recog' and not
                (r['start_time_s'] <= r['stim_on_time_s'] <= r['stim_off_time_s'] <= r['stop_time_s']) for r in ts))
        session = dict(asset_path=asset,asset_id=rec['asset_id'],source_sha256=rec['sha256'],subject_id=subject,
            nwb_identifier=text(f['identifier'][()]),literal_session_id=text(f['general/session_id'][()]) if 'general/session_id' in f else None,
            n_source_trials=n,n_learning_trials=n-len(recognition),n_recognition_trials=len(recognition),
            n_new=sum(r['source_label'] == 0 for r in recognition),n_old=sum(r['source_label'] == 1 for r in recognition),
            n_source_units=len(us),n_mtl_units=len(responses),n_electrodes=len(eids),status='ok')
    return session,ts,us,responses,observed


def construct(inputs, pilot=False):
    root, records, manifest_text, method_text, contract = inputs
    ref = dict(sessions=[],trials=[],units=[],method_json=method_text,source_manifest_json=manifest_text)
    fields = {k:[] for k in ('unit_key','response_unit_index','source_trial_row','trial_id','source_label','spike_count')}
    observed = []
    for rec in records[:1] if pilot else records:
        session,trials,units,responses,obs = read_asset(root/rec['path'],rec)
        ref['sessions'].append(session); ref['trials'].extend(trials); ref['units'].extend(units); observed.append(obs)
        for key, rows, counts in responses:
            idx = len(fields['unit_key']); fields['unit_key'].append(key)
            fields['response_unit_index'].extend([idx]*len(rows))
            for name in ('source_trial_row','trial_id','source_label'): fields[name].extend(r[name] for r in rows)
            fields['spike_count'].extend(counts.tolist())
        print(json.dumps(dict(asset=rec['path'],n_mtl_units=session['n_mtl_units'])),flush=True)
    ref.update({k:np.asarray(v,dtype=str if k == 'unit_key' else np.int64) for k,v in fields.items()})
    ref['rate_hz'] = ref['spike_count']/1.5; ref['repeat_id'] = np.arange(60,dtype=np.int64)
    ref['train_membership'] = q.generate_masks(ref)
    status = 'resource_pilot' if pilot else 'complete'
    ref['metadata'] = dict(status=status,task_id='MTLMEMORY-001',dandiset_id='000004',published_version='0.220126.1852',
        source_manifest_sha256=q.SOURCE_SHA256,method_contract_sha256=q.METHOD_SHA256,
        source_sha256={r['path']:r['sha256'] for r in records},method_contract=contract,headline_population=q.POPULATIONS[1],
        source_observed=dict(n_sessions=len(observed),n_patients=len({r['subject_id'] for r in ref['sessions']}),
            n_source_trials=len(ref['trials']),n_recognition_trials=sum(r['included'] for r in ref['trials']),
            n_source_units=len(ref['units']),n_mtl_units=len(ref['unit_key']),sessions=observed),
        software_versions=dict(python=platform.python_version(),numpy=np.__version__,h5py=h5py.__version__,counting='direct Boolean interval multiset',statistics='direct paired wins erfc'))
    ref['provenance'] = dict(builder_id=proof.BUILDER_ID,status=status,source_manifest_sha256=q.SOURCE_SHA256,
        method_contract_sha256=q.METHOD_SHA256,source_route='Direct original HDF5, Boolean interval cardinality including multiplicity; paired wins/ties and erfc',
        scripts_sha256={p.name:sha(p) for p in [Path(__file__),Path(q.__file__),Path(proof.__file__),Path(__file__).with_name('memory_statistics.py')]})
    proof.validate_reference(ref,full=not pilot)
    return ref


def validate_pilot(output, ref):
    contract = ref['metadata']['method_contract']; root = Path(output)
    for filename, name in [('sessions.csv','sessions'),('trials.csv','trials'),('units.csv','units')]:
        q.validate_table(q.csv_load(root/filename,contract['outputs'][filename]),ref[name],q.TABLE_KEYS[filename])
    q.validate_arrays(root/'trial_counts.npz',ref)
    derived = q.analyze(ref)
    for filename,name in [('neurons.csv','neurons'),('split_events.csv','split_events')]:
        q.validate_table(q.csv_load(root/filename,contract['outputs'][filename]),derived[name],q.TABLE_KEYS[filename])
    q.validate_metadata(q.json_load(root/'run_metadata.json'),ref,q.POPULATIONS[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir',default='/app/data/mtlmemory')
    parser.add_argument('--method-contract',default='/app/method_contract.json')
    parser.add_argument('--output',required=True); parser.add_argument('--report',required=True)
    parser.add_argument('--pilot',action='store_true'); parser.add_argument('--oracle-output')
    args = parser.parse_args(); started = time.monotonic()
    output,report = destinations(args.output,args.report,args.source_dir)
    inputs = load_inputs(args.source_dir,args.method_contract); ref = construct(inputs,args.pilot)
    for p in (output,report): p.parent.mkdir(parents=True,exist_ok=True); no_links(p)
    with output.open('xb') as stream:
        np.savez_compressed(stream,**{'ref_'+k:ref[k] for k in q.ARRAY_FIELDS},
            reference_json=np.asarray(json.dumps({k:ref[k] for k in proof.PAYLOAD_FIELDS},allow_nan=False)))
    validation = 'not_requested'
    if args.oracle_output:
        (validate_pilot if args.pilot else q.validate_output_directory)(args.oracle_output,ref); validation = 'passed'
    derived = q.analyze(ref)
    result = dict(status=ref['metadata']['status'],source_only_construction=True,oracle_consulted_only_after_construction=True,
        oracle_validation=validation,bank_sha256=sha(output),bank_size_bytes=output.stat().st_size,
        elapsed_seconds=time.monotonic()-started,n_sessions=len(ref['sessions']),n_units=len(ref['unit_key']),
        n_responses=len(ref['spike_count']),n_split_events=len(derived['split_events']),provenance=ref['provenance'])
    if not args.pilot: result['results'] = q.summarize(ref,derived['neurons'],q.POPULATIONS[1])
    with report.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result,allow_nan=False))


if __name__ == '__main__': main()

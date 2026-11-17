"""Future deterministic FIF-to-window preparation. No model fitting/scoring.

Operator supplies authenticated read-only source paths and explicit raw-event
bindings. Official epoch metadata alone does not establish offset/button/run
alignment. No scientific payloads are accessed at import.

Modified 2026-11-17: reject incomplete native sample coverage, preserve grid
phase, and take an explicit hash-bound operator cohort. Original preparation
source and its scientific eligibility rules remain preserved in the shared
Four-programme distribution; see README.md for source pins and scoped terms.
"""
import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
import sys
# Reuse the frozen scientific contract and I/O, without probing held cohort or
# source/phase3 bodies. This entry is intended for a fresh isolated process.
SOURCE = (Path(__file__).resolve().parents[5] / 'benchmarks/shared/four-programmes'
          / '_four_programmes_source_v1/originals/authoring/delivery-20261105/neural098')
PINS = {
    'public/protocol.py': 'f08e50cf68f421ef43aa83391e30e5c51101673cb7f248289af30062ca1961fe',
    'public/io_utils.py': '7bbb7a95ded626b4145860b2acf6252448f86dac95d9d417e1ea436d7bdf2df9',
    'private/reference_program.py': '29e7c3d8530e9705cc35e96846b301a0cb660311aa4b339ad85e62e2a1ca386d',
}
for relative, digest in PINS.items():
    if hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest() != digest:
        raise RuntimeError('fixed preparation dependency changed')
sys.path.insert(0, str(SOURCE / 'public'))
sys.path.insert(0, str(SOURCE / 'private'))
from protocol import CHANNELS,WINDOWS,BASELINE,AVAILABLE,DURATIONS,RELEVANCE,ORIENTATIONS,validate_rows
from io_utils import read_json,write_json


def source_pin(path,pin):
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size!=pin['bytes'] or not 0<before.st_size<=2_000_000_000:raise ValueError('bounded pinned FIF')
        h=hashlib.sha256()
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        after=os.fstat(f.fileno())
    if signature(before)!=signature(after) or h.hexdigest()!=pin['sha256']:raise ValueError('source pin mismatch')
    return signature(before)


def signature(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def bool_response(value):
    # CSV roundtrips may supply canonical text, but truthy strings are forbidden.
    if type(value) is bool:return value
    if type(value) is str and value in ('True','False'):return value=='True'
    # numpy.bool_ is accepted by the explicit scalar type name only.
    if type(value).__module__=='numpy' and type(value).__name__=='bool':return bool(value)
    if type(value).__module__=='numpy' and type(value).__name__=='bool_':return bool(value)
    raise ValueError('explicit Response boolean')


def validate_binding(row,binding,sfreq,epoch_event_sample):
    fields={'selection_index','run','event_sample','epoch_event_sample','offset_sample','next_onset_sample','button_samples','stim_trigger'}
    if type(binding) is not dict or set(binding)!=fields:raise ValueError('exact independently mapped raw-event binding')
    for key in ('selection_index','run','event_sample','epoch_event_sample','offset_sample','next_onset_sample','stim_trigger'):
        if type(binding[key]) is not int or not 0<=binding[key]<=10**12:raise ValueError('integral event binding')
    if binding['run']<1 or binding['next_onset_sample']<=binding['offset_sample'] or binding['offset_sample']<=binding['event_sample']:raise ValueError('ordered actual events')
    if type(sfreq) not in (int,float) or not 1<=sfreq<=10000 or not math.isfinite(sfreq):raise ValueError('native sampling rate')
    if binding['stim_trigger']!=row['stim_trigger']:raise ValueError('actual stimulus mapping')
    if type(epoch_event_sample) is not int or binding['epoch_event_sample']!=epoch_event_sample:raise ValueError('raw-to-concatenated epoch onset join')
    expected=row['duration_ms']/1000
    observed=(binding['offset_sample']-binding['event_sample'])/sfreq
    if abs(observed-expected)>1.01/sfreq:raise ValueError('nominal duration differs from verified offset')
    # All five windows plus baseline belong to this stimulus's available epoch.
    end=row['duration_ms']/1000+.3
    complete=(binding['next_onset_sample']-binding['event_sample'])/sfreq>=end
    buttons=binding['button_samples']
    if type(buttons) is not list or len(buttons)>100 or any(type(x) is not int or not 0<=x<=10**12 for x in buttons) or buttons!=sorted(set(buttons)):
        raise ValueError('complete sorted raw button samples')
    return complete and not any(-.5<=(x-binding['event_sample'])/sfreq<end for x in buttons)


def windows_from_epochs(epochs,indices,rows):
    import numpy as np
    if len(indices) != len(rows):raise ValueError('one metadata row per selected epoch')
    if any(c not in epochs.ch_names for c in CHANNELS) or any(c in epochs.info['bads'] for c in CHANNELS):raise ValueError('all six prespecified good magnetometers required')
    types=dict(zip(epochs.ch_names,epochs.get_channel_types()))
    if any(types[c]!='mag' for c in CHANNELS):raise ValueError('magnetometer type required')
    times=np.asarray(epochs.times,dtype=np.float64)
    if times.ndim!=1 or not 2<=len(times)<=10001 or len(epochs.ch_names)>512 or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('bounded native time/channel grid')
    sf=float(epochs.info['sfreq'])
    if not math.isfinite(sf) or sf<=0:raise ValueError('finite positive native sampling rate')
    # Check the whole clock, not just adjacent differences: small per-step
    # errors must not accumulate into a shifted endpoint. Native t0 determines
    # the phase; do not require zero to be on the grid or resample the signal.
    sample_tolerance=1e-7
    if np.max(np.abs((times-times[0])*sf-np.arange(len(times))))>sample_tolerance:
        raise ValueError('uniform native clock')
    def positions(bounds):
        a,b=bounds
        # Native samples k satisfying a <= t0+k/sf < b. A negative start or
        # stop beyond the recording exposes a missing sample; clipping those
        # indices would silently change the baseline/window average.
        start=math.ceil((a-times[0])*sf-sample_tolerance)
        stop=math.ceil((b-times[0])*sf-sample_tolerance)
        if start<0 or stop>len(times) or stop-start<2:
            raise ValueError('complete physical window')
        return np.arange(start,stop)
    spans=[positions(v) for v in WINDOWS.values()];bs=positions(BASELINE)
    out=np.full((len(indices),5,6),np.nan,dtype='<f8')
    # Integer selection avoids version-dependent tmax endpoint conventions.
    # At most eight complete epochs are requested per call; no model is run.
    for start in range(0,len(indices),8):
        selection=indices[start:start+8]
        x=epochs[selection].get_data(picks=list(CHANNELS))
        if x.shape!=(len(selection),6,len(times)):raise ValueError('complete sensor observations')
        def average(values):
            if not np.isfinite(values).all():raise ValueError('finite required observations')
            with np.errstate(over='raise',invalid='raise'):return np.mean(values.astype(np.float64),axis=2)
        baseline=average(x[:,:,bs])
        for j,name in enumerate(WINDOWS):
            local=[i for i in range(len(selection)) if name in AVAILABLE[rows[start+i]['duration_ms']]]
            if local:
                with np.errstate(over='raise',invalid='raise'):out[[start+i for i in local],j]=average(x[local][:,:,spans[j]])-baseline[local]
    from reference_program import validate_features
    validate_features(out,rows)
    return out


def prepare(plan,output,participants):
    import numpy as np
    import mne
    if output.exists() or output.is_symlink():raise ValueError('fresh output directory')
    if set(plan)!={'schema','participants'} or plan['schema']!='neural098-source-plan-v1' or set(plan['participants'])!=set(participants):raise ValueError('full fixed source plan')
    all_rows=[];blocks=[];provenance=[]
    for person in participants:
        item=plan['participants'][person]
        if set(item)!={'epochs_path','epochs_bytes','epochs_sha256','events_path','events_sha256','preprocessing_provenance'}:raise ValueError('exact source operands')
        if type(item['preprocessing_provenance']) is not dict or not item['preprocessing_provenance']:raise ValueError('actual filtering/ICA/artifact history required')
        path=Path(item['epochs_path']);pin={'bytes':item['epochs_bytes'],'sha256':item['epochs_sha256']}
        before=source_pin(path,pin)
        bindings,_=read_json(item['events_path'],expected=item['events_sha256'])
        if set(bindings)!={'schema','participant','sfreq','rows'} or bindings['schema']!='neural098-event-bindings-v1' or bindings['participant']!=person:raise ValueError('event source schema')
        lookup={r['selection_index']:r for r in bindings['rows']}
        if len(lookup)!=len(bindings['rows']):raise ValueError('duplicate retained event binding')
        epochs=mne.read_epochs(path,preload=False,verbose='ERROR')
        if epochs.metadata is None:raise ValueError('author metadata required')
        required={'Category','Stim_trigger','Duration','Task_relevance','Orientation','Response'}
        if not required.issubset(epochs.metadata.columns):raise ValueError('exact author metadata fields')
        if set(lookup)!=set(map(int,epochs.selection)):raise ValueError('full retained selection join')
        selected=[];rows=[];seen=set()
        for pos,(_,meta) in enumerate(epochs.metadata.iterrows()):
            if meta['Category'] not in ('face','object') or meta['Task_relevance'] not in RELEVANCE:continue
            if meta['Duration'] not in ('500ms','1000ms','1500ms') or meta['Orientation'] not in ORIENTATIONS:raise ValueError('source condition vocabulary')
            trigger=meta['Stim_trigger']
            if not np.isscalar(trigger) or not np.isfinite(trigger) or float(trigger)!=int(trigger):raise ValueError('integral source identity')
            index=int(epochs.selection[pos]);event=lookup[index]
            if int(epochs.events[pos,2])!=int(trigger):raise ValueError('epoch event/category metadata disagreement')
            row={'participant':person,'trial_id':f'r{event["run"]}-e{event["event_sample"]}',
                 'stim_trigger':int(trigger),'category':0 if meta['Category']=='face' else 1,
                 'duration_ms':int(meta['Duration'][:-2]),'relevance':meta['Task_relevance'],'orientation':meta['Orientation']}
            if row['trial_id'] in seen:raise ValueError('duplicate actual event')
            seen.add(row['trial_id'])
            no_button=validate_binding(row,event,bindings['sfreq'],int(epochs.events[pos,0]))
            if bool_response(meta['Response']) or not no_button:continue
            selected.append(pos);rows.append(row)
        if len(all_rows)+len(rows)>100000:raise ValueError('full packet row cap')
        block=windows_from_epochs(epochs,selected,rows)
        if source_pin(path,pin)!=before:raise ValueError('FIF changed during controlled read')
        all_rows.extend(rows);blocks.append(block)
        provenance.append({'participant':person,'epochs_sha256':pin['sha256'],'events_sha256':item['events_sha256'],
                           'preprocessing_provenance':item['preprocessing_provenance'],'retained_rows':len(rows)})
    validate_rows(all_rows,participants)
    output.mkdir()
    with (output/'features.npy').open('xb') as f:np.save(f,np.concatenate(blocks).astype('<f8'),allow_pickle=False)
    digest=hashlib.sha256((output/'features.npy').read_bytes()).hexdigest()
    write_json(output/'packet.json',{'schema':'neural098-packet-v1','features_sha256':digest,'rows':all_rows})
    write_json(output/'PREPARATION.json',{'schema':'neural098-preparation-v1','sources':provenance,'scientific_analysis_executed':False,
               'window_projection':{'revision':'native-coverage-v2','clock_tolerance_samples':1e-7},
               'temporal_availability':'Retrospective author-preprocessed signals; no causal online claim.'})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source-plan',type=Path,required=True);ap.add_argument('--source-plan-sha256',required=True);ap.add_argument('--cohort',type=Path,required=True);ap.add_argument('--cohort-sha256',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.exists() or a.output.is_symlink():raise ValueError('fresh output directory')
    plan,_=read_json(a.source_plan,expected=a.source_plan_sha256)
    people=read_json(a.cohort,expected=a.cohort_sha256)[0]['participants']
    if type(people) is not list or len(people)!=33 or any(type(p) is not str or not p for p in people) or len(set(people))!=33:
        raise ValueError('complete fixed 33-participant operator roster')
    prepare(plan,a.output,people)

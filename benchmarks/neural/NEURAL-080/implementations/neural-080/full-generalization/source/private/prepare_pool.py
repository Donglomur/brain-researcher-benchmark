"""Full96-recording data-only EEG/eye projection. No model or scientific score.

Complete input verification is deliberately mandatory. This file has never
been invoked on empirical recordings; they are not held by this delivery.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import h5py
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_contract import capture,decode
from protocol import SUBJECTS,SESSIONS,FIT,VALIDATION,QUERY,ARMS
import arrays
from signals_core import eeg_bins,eye_bins,training_stats,timing_features

JOIN_SHA='fa3b05a001c897327990d60f13ba0969cced17a4f1aa1e6a5b64cb284148cd24'
REQUIRED_SHA='629f374eb781cb37ae207b295d7ab4aa758013e601bb5350274b9df2054add78'


def need(ok,msg):
    if not ok:raise ValueError(msg)


@contextmanager
def recording(path,row,owner):
    rec=owner.begin('original_recording:'+str(row['modality']))
    fd=None;f=None;h=None;before=None;sha=hashlib.sha256()
    state=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    try:
        owner.reserve('read_bytes',row['bytes']+1)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        f=os.fdopen(fd,'rb',closefd=False)
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_size==row['bytes'],'Exact source recording size/type')
        md5=hashlib.md5()
        remaining=row['bytes'];observed=0
        while remaining:
            block=f.read(min(remaining,8*1024**2));need(block,'Truncated source recording')
            remaining-=len(block);observed+=len(block);md5.update(block);sha.update(block)
        need(not f.read(1) and observed==row['bytes'],'No growing or trailing source recording')
        need(md5.hexdigest()==row['md5'],'Selected publisher recording identity mismatch')
        need(state(before)==state(os.fstat(fd))==state(os.stat(path,follow_symlinks=False)),'Recording changed during authentication')
        f.seek(0);h=h5py.File(f,'r')
        yield h,sha.hexdigest()
    except BaseException as exc:owner.failure(rec,exc)
    finally:
        # Preserve a body failure before every independent validation/close tail.
        if before is not None:
            try:need(state(before)==state(os.fstat(fd))==state(os.stat(path,follow_symlinks=False)),'Recording changed during projection')
            except BaseException as exc:owner.failure(rec,exc)
        if h is not None:owner.close(rec,h.close)
        if f is not None:owner.close(rec,f.close)
        if fd is not None:owner.close(rec,lambda:os.close(fd))
    owner.complete(rec)


def native(h,key,n,channels):
    need(key in h and isinstance(h.get(key,getlink=True),h5py.HardLink),'Declared internal source dataset')
    ds=h[key]
    need(isinstance(ds,h5py.Dataset) and not ds.is_virtual and not ds.external
         and ds.shape==(n,channels,1800) and ds.dtype.kind=='f','Source dataset geometry/type compatibility')
    return ds


def take(ds,indices):
    need(len(set(indices))==len(indices),'Distinct native row indices')
    order=np.argsort(indices);back=np.argsort(order)
    return ds[np.asarray(indices)[order]][back]


class Writer:
    def __init__(self,root,cap):
        need(cap>0 and not root.exists() and not root.is_symlink(),'Fresh pool with explicit cap')
        root.mkdir();self.root=root;self.cap=cap;self.used=0;self.files=[]
    def put(self,name,body):
        need(self.used+len(body)<=self.cap,'Aggregate output including receipts exceeds cap')
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(body)
        self.used+=len(body);r={'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()};self.files.append(r);return r
    def array(self,name,a):
        a=np.asarray(a)
        need(a.dtype.kind in 'fiub' and not a.dtype.hasobject and np.isfinite(a).all(),
             'Only finite primitive computed arrays may be committed; no imputation or partial-success receipt')
        b=io.BytesIO();np.save(b,a,allow_pickle=False);return self.put(name,b.getvalue())
    def json(self,name,obj):return self.put(name,(json.dumps(obj,allow_nan=False,separators=(',',':'))+'\n').encode())


def prepare(raw_root,feature_root,out,cap,*,metadata_root,owner):
    need(np.__version__=='2.2.6' and h5py.__version__=='3.13.0','Selected numerical/HDF source profile; not native qualification')
    here=Path(metadata_root)
    body=capture(here/'JOINED_METADATA.json',12_000_000,owner=owner);need(hashlib.sha256(body).hexdigest()==JOIN_SHA,'Authentic six-person metadata join')
    joined=decode(body);body=capture(here/'source/REQUIRED_RECORDINGS.json',100000,owner=owner)
    need(hashlib.sha256(body).hexdigest()==REQUIRED_SHA,'Exact96-recording manifest')
    required=decode(body);records=required['files'];lookup={(r['subject'],r['session'],r['modality']):r for r in records}
    need(len(records)==96 and set(lookup)=={(p,s,m) for p in SUBJECTS for s in SESSIONS for m in ('eeg','eye')},'Whole6×8×2 source panel')
    missing=[r['relative_path'] for r in records if not (raw_root/r['relative_path']).is_file()]
    need(not missing,'Complete96 source recordings required before source-body read:'+','.join(missing))
    features=decode(capture(feature_root/'FEATURES.json',4_000_000,owner=owner))
    need(features['schema']=='neural080_stimulus_features_v2' and features['recipe']=='duration_rgb8x8_audio8band_v1'
         and features['video_ids']==list(range(1,1103)) and len(features['media'])==1102,'Exact full audiovisual feature provenance')
    need([r['video_id'] for r in features['media']]==list(range(1,1103)),'Explicit video-ID/media mapping')
    need(features['decoder_profile']=='pyav_14.4.0_native_pts_rgb24_no_resample_v1'
         and features['hardware_alignment_verified'] is False
         and features['presentation_trial_warp_or_average'] is False,
         'Source clip-time profile; no hardware or trial-warp claim')
    for row in features['media']:
        need(row['source_bytes_sha256_verified'] is True and 'rational_clock' in row
             and set(row['decoded_arrays'])=={'cells','frame_starts','frame_ends','audio'},
             'Complete actual decoded-source provenance')
    static=arrays.load(feature_root/'static.npy',features['arrays']['static'],(1102,384),max_bytes=4_000_000,owner=owner)
    motion=arrays.load(feature_root/'motion.npy',features['arrays']['motion'],(1102,30,64),max_bytes=20_000_000,owner=owner)
    acoustic=arrays.load(feature_root/'acoustic.npy',features['arrays']['acoustic'],(1102,30,10),max_bytes=4_000_000,owner=owner)
    dynamic=arrays.load(feature_root/'dynamic.npy',features['arrays']['dynamic'],(1102,30,192),max_bytes=60_000_000,owner=owner)
    # No feature fitting or model selection here; only raw fixed features.
    video_nuisance=np.concatenate((static,motion.reshape(1102,-1),acoustic.reshape(1102,-1)),axis=1)
    writer=Writer(out,cap);shared=writer.array('features/dynamic.npy',dynamic.astype(np.float64));subjects=[];targets=[];source_provenance=[]
    for person in joined['subjects']:
        pid=person['subject'];sums=np.zeros((1102,127,150),float);ocular=np.zeros((1102,150,8),float)
        first_y=np.zeros_like(sums);first_eye=np.zeros_like(ocular)
        counts=np.zeros(1102,dtype=np.int64);timing={v:[] for v in range(1,1103)};norms=[]
        for sn,session in enumerate(SESSIONS,1):
            meta=person['sessions'][session];rows=meta['joined'];er=lookup[pid,session,'eeg'];orr=lookup[pid,session,'eye']
            with recording(raw_root/er['relative_path'],er,owner) as (eh,esha),recording(raw_root/orr['relative_path'],orr,owner) as (oh,osha):
                ed=native(eh,'eeg',meta['eeg_trials'],127);od=native(oh,'eyetracking',meta['eye_trials'],3)
                selected=[r for r in rows if r['video_id'] in FIT]
                def chunks():
                    for start in range(0,len(selected),16):yield eeg_bins(take(ed,[r['eeg_row'] for r in selected[start:start+16]]))
                anchor,mean,sd,n=training_stats(chunks());norms.append({'session':session,'joined_fit_trials':n})
                for start in range(0,len(rows),16):
                    batch=rows[start:start+16];y=((eeg_bins(take(ed,[r['eeg_row'] for r in batch]))-anchor)-mean)/sd
                    x=eye_bins(take(od,[r['eye_row'] for r in batch]));need(np.isfinite(y).all(),'Finite normalized joined EEG')
                    for r,yy,xx in zip(batch,y,x):
                        v=r['video_id']
                        if not counts[v-1]:first_y[v-1]=yy;first_eye[v-1]=xx
                        sums[v-1]+=yy-first_y[v-1];ocular[v-1]+=xx-first_eye[v-1];counts[v-1]+=1
                        timing[v].append({'session':sn,'run':r['run'],'trial':r['trial']})
                source_provenance.extend([{'subject':pid,'session':session,'modality':'eeg','sha256':esha},{'subject':pid,'session':session,'modality':'eye','sha256':osha}])
        need(np.array_equal(counts,person['counts_per_video']) and (counts>0).all(),'Exactly the authenticated complete intersection; no extra rejection')
        y=first_y+sums/counts[:,None,None];e=first_eye+ocular/counts[:,None,None]
        t=np.asarray([timing_features(timing[v]) for v in range(1,1103)])
        n=np.concatenate((video_nuisance,t),axis=1)
        subject={'subject':pid,'nuisance':writer.array(pid+'/nuisance.npy',n),
                 'ocular':writer.array(pid+'/ocular.npy',e.reshape(1102,-1)),
                 'fit_targets':writer.array(pid+'/fit_targets.npy',y[np.asarray(FIT)-1]),
                 'validation_targets':writer.array(pid+'/validation_targets.npy',y[np.asarray(VALIDATION)-1]),
                 'counts_per_video':counts.tolist(),'normalization':norms}
        subjects.append(subject)
        target=writer.array('gold/'+pid+'.npy',y[np.asarray(QUERY)-1]);targets.append({'subject':pid,'file':pid+'.npy','bytes':target['bytes'],'sha256':target['sha256']})
    query={'schema':'neural080_query_v1','subjects':list(SUBJECTS),'video_ids':list(QUERY),'shape_per_subject':[102,127,150],
           'arms':list(ARMS),'channel_names':joined['subjects'][0]['channel_names'],'fit_video_ids':list(FIT),'validation_video_ids':list(VALIDATION),
           'target':'FIT-only session-normalized EEG averaged over exactEEG/eye trialintersection','source_test_exposed':True}
    qr=writer.json('query.json',query)
    writer.json('gold/binding.json',{'schema':'neural080_private_v1','query_sha256':qr['sha256'],'targets':targets})
    writer.json('POOL.json',{'schema':'neural080_pool_v1','subjects':subjects,'dynamic':shared,'query':qr,'feature_provenance':features,
                           'joined_metadata_sha256':JOIN_SHA,'all_source_recordings':source_provenance})
    writer.json('PREPARATION.json',{'complete':True,'files':list(writer.files),'bytes_before_receipt':writer.used,
                                  'models_run':0,'scientific_scores':0,'hardware_alignment_verified':False})
    return {'complete':True,'retained_bytes':writer.used,'models_run':0,'scientific_scores':0}


if __name__=='__main__':
    raise RuntimeError('Use the trusted source_pipeline.prepare_sources caller with the original logical Owner; authentic input/native admission remains independently required')

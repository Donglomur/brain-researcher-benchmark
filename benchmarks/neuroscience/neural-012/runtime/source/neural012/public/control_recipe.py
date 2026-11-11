"""Prospective offline preprocessing/control recipes; no execution on import."""
import numpy as np
EDGES=('FP1-F7','F7-T7','T7-P7','P7-O1','FP1-F3','F3-C3','C3-P3','P3-O1','FP2-F4','F4-C4','C4-P4','P4-O2','FP2-F8','F8-T8','T8-P8','P8-O2','FZ-CZ','CZ-PZ')
ARMS=('native','harmonized','normalized','timing')
ALIASES={'T3':'T7','T4':'T8','T5':'P7','T6':'P8'}
def need(ok,message):
 if not ok:raise ValueError(message)
def normalized_label(label):return '-'.join(ALIASES.get(s,s) for s in label.upper().removeprefix('EEG ').split('-'))
def mapping(labels,cohort,common_reference_selected=False):
 labels=[normalized_label(s) for s in labels];need(cohort in ('CHB','Siena'),'known cohort');out=[]
 for edge in EDGES:
  a,b=edge.split('-')
  if cohort=='Siena':
   need(common_reference_selected,'declared common-reference computation; genuine evidence is enforced by the trusted host')
   need(labels.count(a)==1 and labels.count(b)==1,'complete unambiguous referential electrode pair');out.append([labels.index(a),labels.index(b),1])
  else:
   forward=[i for i,x in enumerate(labels) if x==edge];reverse=[i for i,x in enumerate(labels) if x==b+'-'+a]
   need(len(forward)+len(reverse)==1,'exact unique measured bipolar derivation; no silent duplicate/missing replacement');out.append([forward[0] if forward else reverse[0],None,1 if forward else -1])
 return out

def transform(physical_microvolts,rate_hz,labels,cohort,arm,common_reference_selected=False):
 """Whole recording, time×channels. Physical calibration must precede this call."""
 x=np.asarray(physical_microvolts,dtype=np.float64)
 need(x.ndim==2 and x.shape[1]==len(labels) and x.shape[0]>0 and rate_hz in (256,512) and x.shape[0]%rate_hz==0 and np.isfinite(x).all(),'complete finite physical recording')
 need((cohort=='CHB' and rate_hz==256) or (cohort=='Siena' and rate_hz==512),'native cohort rate')
 need(arm in ARMS[:3],'signal arm')
 if arm=='native':return x,rate_hz
 rows=mapping(labels,cohort,common_reference_selected)
 x=np.column_stack([sign*x[:,a] if b is None else x[:,a]-x[:,b] for a,b,sign in rows]);need(np.isfinite(x).all(),'representable rereferenced signal')
 from scipy.signal import butter,sosfiltfilt,resample_poly
 # Same physical1–30Hz band on each native clock; does not undo acquisition filters.
 sos=butter(4,[1.,30.],btype='bandpass',fs=rate_hz,output='sos');x=sosfiltfilt(sos,x,axis=0,padtype='odd')
 if rate_hz==512:x=resample_poly(x,1,2,axis=0,window=('kaiser',5.0),padtype='constant')
 need(x.shape[0]%256==0 and np.isfinite(x).all(),'whole harmonized support')
 if arm=='normalized':
  q=np.quantile(x,[.25,.5,.75],axis=0,method='linear');scale=q[2]-q[0]
  need(np.isfinite(scale).all() and (scale>0).all(),'all channels need positive IQR; never drop a person/recording')
  x=(x-q[1])/scale;need(np.isfinite(x).all(),'representable normalized values')
 return x,256

def feature(x,rate):
 x=np.asarray(x,dtype=np.float64);need(x.ndim==2 and x.shape[0]%rate==0 and np.isfinite(x).all(),'full per-second EEG')
 block=x.reshape(-1,rate,x.shape[1]);v=np.median(np.log1p(np.mean(np.abs(np.diff(block,axis=1)),axis=1)),axis=1);need(np.isfinite(v).all(),'finite feature');return v

def fit_threshold(train,expected_people,loader):
 need(expected_people in (22,23),'CHB-only fit count');groups={}
 for r in train:
  need(r['cohort']=='CHB' and 'events' in r,'CHB labeled training only');v=np.asarray(loader(r),dtype=np.float64);d=r['duration_seconds'];need(v.shape==(d,) and np.isfinite(v).all(),'complete training features');keep=np.ones(d,dtype=bool)
  for a,b in r['events']:need(type(a)in(int,float) and type(b)in(int,float) and a==int(a) and b==int(b) and 0<=a<b<=d,'training annotation');keep[int(a):int(b)]=False
  groups.setdefault(r['patient_id'],[]).append(v[keep])
 need(len(groups)==expected_people,'all training biological people')
 quantiles=[]
 for arrays in groups.values():
  v=np.concatenate(arrays);need(len(v)>0,'every training person has observed nonictal support');quantiles.append(float(np.quantile(v,.995,method='linear')))
 return float(np.median(quantiles))

def timing_table(train,expected_people):
 need(expected_people in (22,23),'source-only count');groups={}
 for r in train:need(r['cohort']=='CHB' and 'events' in r,'CHB training labels only');groups.setdefault(r['patient_id'],[]).append(r)
 need(len(groups)==expected_people,'whole training people');tables=[]
 for records in groups.values():
  count=np.zeros(60);hits=np.zeros(60)
  for r in records:
   for t in range(r['duration_seconds']):
    b=min(t//60,59);count[b]+=1;hits[b]+=any(a<=t<end for a,end in r['events'])
  tables.append((hits+1)/(count+2))
 return np.mean(tables,axis=0)

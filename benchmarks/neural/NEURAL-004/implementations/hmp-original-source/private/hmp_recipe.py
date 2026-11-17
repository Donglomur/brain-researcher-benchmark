"""Source-derived HMP calls. Importing this file does not import HMP or fit data."""
import protocol as p

def read_epochs(paths):
 import hmp
 return hmp.io.read_mne_data(paths,sfreq=512,data_format='epochs',lower_limit_rt=.1,offset_after_resp=.01,reject_threshold=1e-4,verbose=False,subj_name=list(p.PEOPLE))

def author_replay(epoch_data):
 """Exact central joint26 author call sequence; not held-person validation/Bambi."""
 import hmp
 prepared=hmp.preprocessing.Standard(epoch_data,n_comp=15,apply_zscore='participant',copy=True)
 pattern=hmp.patterns.HalfSine.create_expected(sfreq=epoch_data.sfreq,width=25)
 trials=hmp.trialdata.TrialData.from_preprocessed(preprocessed=prepared,pattern=pattern.template)
 model=hmp.models.CumulativeMethod(pattern);model.fit(trials,verbose=False,cpus=1)
 likes,events=model.final_model.transform(trials)
 durations=hmp.utils.event_times(events,duration=True,add_rt=True,as_time=True)
 return model,likes,events,durations

def project_held(query,weights,standard):
 """Compatibility repair for 1.0.0b2 Standard(weights=) unbound local.

 Uses the same release helpers/order; no PCA, covariance or model fit on query.
 """
 data=query.copy(deep=True).data.transpose('participant','epoch','channel','sample')
 data=standard._center(data) @ weights.copy(deep=True)
 ori_coords=data.coords
 data=(data.stack(participant_comp=['participant','component'])
       .groupby('participant_comp',squeeze=False)
       .map(standard.zscore_xarray).unstack())
 data=data.transpose('participant','epoch','sample','component').assign_coords(ori_coords)
 data.attrs['sfreq']=query.sfreq;data.attrs['offset']=query.offset
 return standard.stack_data(data)

def fit_fold(epoch_data,held):
 """NEW held-person extension. Only transform, never fit or RT-rescale, on heldperson."""
 import hmp,numpy as np
 training=epoch_data.sel(participant=[x for x in p.PEOPLE if x!=held]);query=epoch_data.sel(participant=[held])
 train_pre=hmp.preprocessing.Standard(training,n_comp=15,apply_zscore='participant',copy=True)
 # New train-only spatial weights. Held-person full-record zscore remains explicitly transductive.
 query_pre=project_held(query,train_pre.weights,hmp.preprocessing.Standard)
 pattern=hmp.patterns.HalfSine.create_expected(sfreq=512,width=25)
 train=hmp.trialdata.TrialData.from_preprocessed(preprocessed=train_pre,pattern=pattern.template)
 test=hmp.trialdata.TrialData.from_preprocessed(preprocessed=query_pre,pattern=pattern.template)
 likes={};five=None;train_events=None
 for k in (4,5,6):
  model=hmp.models.EventModel(pattern,n_events=k,tolerance=1e-4,max_iteration=1000,min_iteration=1,starting_points=1)
  model.fit(train,verbose=False,cpus=1)
  p.need(len(model.traces)<=1000 and np.all(np.isfinite(model.traces)) and np.all(np.isfinite(model.channel_pars)) and np.all(np.isfinite(model.time_pars)),'Finite HMP stop before iteration cap required')
  before=(model.channel_pars.copy(),model.time_pars.copy())
  ll,events=model.transform(test)
  p.need(all(np.array_equal(a,b) for a,b in zip(before,(model.channel_pars,model.time_pars))),'Held transform mutated fitted parameters')
  total=float(np.asarray(ll).sum());p.need(np.isfinite(total),'All fixed-count likelihoods finite')
  likes['hmp_'+str(k)+'_nats_per_trial']=p.cell(total/int(test.n_trials),int(test.n_trials))
  if k==5:
   five=events;_,train_events=model.transform(train)
 return likes,five,train_events

def event_rows(epoch_data,events,person):
 """Use author max-marginal modes and posterior-derived retained endpoint (offset kept)."""
 import hmp,numpy as np
 selected=events.isel(trial=np.flatnonzero(events.participant.values.astype(str)==person))
 d=hmp.utils.event_times(selected,duration=True,add_rt=True,as_time=True).transpose('trial','event').values
 times=hmp.utils.event_times(selected,add_rt=True,as_time=True).transpose('trial','event').values
 p.need(d.shape[1]==6 and times.shape[1]==6,'Exactly5event chronological identity, no event relabeling')
 lags=times[:,:5]-times[:,5,None]
 rows=[]
 for ep in selected.epoch.values:
  r={k:epoch_data[k].sel(participant=person,epoch=ep).item() for k in ('stimulus','condition','response')}
  rows.append(r)
 return rows,d,lags

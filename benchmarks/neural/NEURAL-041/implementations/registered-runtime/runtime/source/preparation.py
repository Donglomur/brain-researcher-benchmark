"""Future full-source NWB to private epochs. No original file opens on import.

Only run within the independently selected preparation capsule. Clinical review,
source roster, original identity-key provenance and finite native allowances
are mandatory inputs, whose real producers remain qualification gates.
"""
import hashlib,hmac,io,math,zipfile
from pathlib import Path
from core import need,finite,integer,encoded,pin,parse,publish,fresh,capture,descriptor
from nwb import Native
from schema import DATASET,AUTHOR_REVISION,exact,cohort

# Exact vocabulary in original condenseAreas.m; this is an anatomical source
# join, not a clinical eligibility decision or silent normalization.
AREA={a+'_'+side:r for a,r in (('amygdala','Amy'),('dorsal_anterior_cingulate_cortex','dACC'),
    ('hippocampus','Hippo'),('pre_supplementary_motor_area','preSMA'),('ventral_medial_prefrontal_cortex','vmPFC')) for side in ('left','right')}

def token(key,kind,value):return hmac.new(key,(kind+':'+value).encode(),hashlib.sha256).hexdigest()[:32]

def window(maintenance,probe,start,rate,samples):
    maintenance,probe,start,rate=map(finite,(maintenance,probe,start,rate))
    need(rate==400,'selected source 400 Hz; never guessed/resampled')
    first=math.ceil((maintenance-start)*400);last=first+1000
    # A half-open 2.5 s interval; its last sampled instant is strictly before
    # probe. The independent chronology review must resolve exclusive-end
    # equality, rather than silently discard a source trial at that boundary.
    need(first>=0 and last<=samples and maintenance+2.5<=probe,'complete equal maintenance interval before probe')
    need(start+first/400>=maintenance and start+(last-1)/400<probe,'no cue/probe samples')
    need((first==0 or start+(first-1)/400<maintenance) and start+(last-1)/400<maintenance+2.5,'first aligned sample and half-open stop')
    return first,last

def validate_review(review,roster):
    exact(review,('schema','dataset','author_revision','regions','sessions','provenance'),'full independently produced clinical/protocol review')
    need(review['schema']=='n041_clinical_review_v1' and review['dataset']==DATASET and review['author_revision']==AUTHOR_REVISION,'fixed archive/code')
    regions=review['regions'];need(regions==sorted(set(AREA.values())),'all five source areas, even when unavailable in a patient')
    need(review['provenance'],'actual clinical/exclusion/source preprocessing evidence required')
    sessions={x['asset_id']:x for x in review['sessions']}
    need(len(sessions)==len(roster['assets']) and set(sessions)=={x['asset_id'] for x in roster['assets']},'all source sessions reviewed')
    for asset in roster['assets']:
        r=sessions[asset['asset_id']]
        exact(r,('asset_id','source_session_id','source_pin','preprocessing','lfp','units','trials','evidence','eligibility_basis','clock_evidence'),'complete source-specific review')
        need(r['source_pin']==asset['pin'] and r['evidence'],'review to exact original source')
        need(type(r['source_session_id'])is str and r['source_session_id']==asset['session_id'],'reviewed original session ID')
        need(r['clock_evidence']==dict.fromkeys(('trial_seconds','spike_seconds','lfp_start_seconds','upstream_temporal_support_reviewed'),True),'independent actual source clock/preprocessing support evidence')
        need(r['preprocessing']=={'bundle_spike_interpolation':True,'local_reference':True,'lowpass_175Hz':True,'downsample_400Hz':True,'notch_60_120Hz':True},'published preprocessing must be verified, not repeated blindly')
        need(r['eligibility_basis']=='clinical_and_signal_artifact_only_blind_to_load_correctness_order','no condition/correctness or response-conditioned trial selection')
        for kind in ('lfp','units'):
            ids=[]
            for ch in r[kind]:
                exact(ch,('row0','electrode_row0','bundle','eligible','region','reason','bad_trial_rows0'),'complete modality element disposition')
                integer(ch['row0'],0);ids.append(ch['row0']);need(type(ch['eligible'])is bool,'typed modality exclusion')
                integer(ch['electrode_row0'],0);need(type(ch['bundle'])is str and ch['bundle'],'actual private microwire bundle join')
                bad=ch['bad_trial_rows0'];need(type(bad)is list and len(set(bad))==len(bad),'unique source artifact trial mask')
                for i in bad:integer(i,0,139)
                need(ch['region'] in regions or not ch['eligible'],'no unknown eligible region')
                need(type(ch['reason'])is str and (ch['eligible'] or bool(ch['reason'])),'retained exclusion reason')
            need(len(set(ids))==len(ids),'unique modality row review')
        ids=[]
        for trial in r['trials']:
            exact(trial,('row0','eligible','reason'),'outcome-independent global trial disposition')
            integer(trial['row0'],0);ids.append(trial['row0']);need(type(trial['eligible'])is bool,'typed trial exclusion')
            need(type(trial['reason'])is str and (trial['eligible'] or bool(trial['reason'])),'explicit artifact/availability disposition')
        need(len(ids)==len(set(ids)),'one disposition per original trial')
    return sessions

def save_epoch(path,arrays,budget,cap):
    import numpy as np
    planned=sum(a.nbytes for a in arrays.values())+8192
    need(planned<=cap,'prospective primitive epoch serialization allocation')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
        for name,array in sorted(arrays.items()):
            part=io.BytesIO();np.save(part,array,allow_pickle=False)
            info=zipfile.ZipInfo(name+'.npy',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED
            z.writestr(info,part.getvalue())
    raw=out.getvalue();need(len(raw)<=cap,'complete primitive NPZ bound')
    return publish(path,raw,budget,readonly=True)

def run(roster,review,raw_root,output,identity_key,budget,limits):
    import numpy as np
    exact(roster,('schema','dataset','assets','provenance'),'complete authentic roster')
    need(roster['schema']=='n041_roster_v1' and roster['dataset']==DATASET and roster['provenance'],'fixed archive roster provenance')
    assets=roster['assets'];need(len(assets)==44 and len({a['patient_id'] for a in assets})==36,'future actual 44-session/36-patient closure; not declaration as evidence')
    need(type(identity_key)is bytes and len(identity_key)==32,'operator private opaque-identity key')
    sessions=validate_review(review,roster);out=fresh(output,budget);epochs=fresh(out/'epochs',budget)
    rows=[];native=[];seen_assets=set();session_ids=set();chronology=[]
    for a in assets:
        exact(a,('asset_id','patient_id','session_id','path','pin'),'authentic source asset identity')
        need(a['asset_id'] not in seen_assets,'no duplicated source asset');seen_assets.add(a['asset_id']);descriptor(a['pin'])
        patient=token(identity_key,'patient',a['patient_id']);session=token(identity_key,'session',a['asset_id'])
        need(session not in session_ids,'one opaque session per source asset');session_ids.add(session)
        from core import relative
        r=sessions[a['asset_id']]
        with Native(Path(raw_root)/relative(a['path']),a['pin'],budget,limits['native']) as f:
            need(f.read('general/subject/subject_id',(),text=True)==a['patient_id'],'actual NWB subject to roster join')
            need(f.read('general/session_id',(),text=True)==a['session_id'],'actual NWB session to independently reviewed original session')
            has_lfp='LFPs' in f.object('acquisition','group')
            data=f.object('acquisition/LFPs/data') if has_lfp else None
            if has_lfp:
                need(data.ndim==2,'LFP time by channel')
                start=finite(f.read('acquisition/LFPs/starting_time',()).item());rate=f.attribute('acquisition/LFPs/starting_time','rate')
                need(f.attribute('acquisition/LFPs/data','unit',text=True) in('volts','volt','V'),'explicit source voltage units')
                conv=f.attribute('acquisition/LFPs/data','conversion') if 'conversion' in data.attrs else 1.
                off=f.attribute('acquisition/LFPs/data','offset') if 'offset' in data.attrs else 0.
                need(conv>0,'positive volts conversion');group=f.object('acquisition/LFPs','group')
                cc=f.read('acquisition/LFPs/channel_conversion',shape=(data.shape[1],)) if 'channel_conversion' in group else np.ones(data.shape[1])
                need((cc>0).all(),'positive per-channel conversion')
            loads=f.read('intervals/trials/loads',kinds='fiu');n=len(loads)
            need(n==140 and set(loads.tolist())=={1,3} and int((loads==1).sum())==70 and int((loads==3).sum())==70,'source-declared full 140/70/70 before eligibility; no sampling to manufacture balance')
            maintenance=f.read('intervals/trials/timestamps_Maintenance',shape=(n,))
            probe=f.read('intervals/trials/timestamps_Probe',shape=(n,))
            has_units='units' in f.file
            ends=f.read('units/spike_times_index',kinds='iu') if has_units else np.empty(0,dtype='<i8')
            if has_units:
                spikes=f.object('units/spike_times')
                need(ends.ndim==1 and spikes.ndim==1 and (int(ends[-1]) if len(ends) else 0)==spikes.shape[0] and (np.diff(np.r_[0,ends])>=0).all(),'complete ragged unit boundaries')
            need({x['row0'] for x in r['lfp']}==set(range(data.shape[1] if has_lfp else 0)),'complete LFP dispositions')
            need({x['row0'] for x in r['units']}==set(range(len(ends))),'complete unit dispositions')
            locations=f.object('general/extracellular_ephys/electrodes/location')
            for kind,path in (('lfp','acquisition/LFPs/electrodes'),('units','units/electrodes')):
                if not r[kind]:continue
                mapping=f.read(path,shape=(len(r[kind]),),kinds='iu')
                need(((mapping>=0)&(mapping<locations.shape[0])).all(),'source electrode row bounds')
                if kind=='units' and 'electrodes_index' in f.object('units','group'):
                    ei=f.read('units/electrodes_index',shape=ends.shape,kinds='iu')
                    need(np.array_equal(ei,np.arange(1,len(ends)+1)),'one source electrode per unit; incompatible schema is a hold')
                for decision in r[kind]:
                    need(int(mapping[decision['row0']])==decision['electrode_row0'],'actual source electrode row to clinical bundle map')
                    loc=f.read('general/extracellular_ephys/electrodes/location',int(mapping[decision['row0']]),text=True)
                    need(loc in AREA and AREA[loc]==decision['region'],'actual anatomical identity to review; no unknown-token dropping')
            need({x['row0'] for x in r['trials']}==set(range(n)),'all source trial dispositions')
            channels=sorted((x for x in r['lfp'] if x['eligible']),key=lambda x:x['row0'])
            units=sorted((x for x in r['units'] if x['eligible']),key=lambda x:x['row0'])
            trains=[]
            total_spikes=0
            for u in units:
                k=u['row0'];lo=0 if k==0 else int(ends[k-1]);hi=int(ends[k]);total_spikes+=hi-lo
                need(total_spikes<=limits['session_spikes'],'prospective full retained session spike allowance')
                train=f.read('units/spike_times',slice(lo,hi),shape=(hi-lo,));need((np.diff(train)>=0).all(),'sorted unit spike times')
                trains.append(train)
            for t in sorted(r['trials'],key=lambda x:x['row0']):
                i=t['row0'];tid=token(identity_key,'trial',a['asset_id']+':'+str(i));reason=t['reason'] if not t['eligible'] else ''
                trial_channels=[c for c in channels if i not in c['bad_trial_rows0']]
                trial_units=[(u,train) for u,train in zip(units,trains) if i not in u['bad_trial_rows0']]
                if not trial_channels and not trial_units:reason='no prospectively eligible neural modality'
                entry={'identity':{'patient':patient,'session':session,'trial':tid},'source':a['pin'],'trial_row0':i,'eligibility':not bool(reason),'reason':reason,'epoch':None,'load':int(loads[i])}
                if not reason:
                    need(float(maintenance[i])+2.5<=float(probe[i]),'full equal spike interval before probe')
                    first,last=window(float(maintenance[i]),float(probe[i]),start,rate,data.shape[0]) if has_lfp else (None,None)
                    need(len(trial_channels)*1000*8<=limits['epoch_bytes'],'prospective full LFP epoch allocation')
                    x=np.empty((len(trial_channels),1000),dtype='<f8')
                    for j,ch in enumerate(trial_channels):x[j]=f.read('acquisition/LFPs/data',(slice(first,last),ch['row0']),shape=(1000,))*conv*cc[ch['row0']]+off
                    need(np.isfinite(x).all(),'finite complete epoch; no element deletion')
                    event=[];offsets=[0]
                    for u,train in trial_units:
                        lo,hi=np.searchsorted(train,[maintenance[i],maintenance[i]+2.5],side='left')
                        event.append(np.asarray(train[lo:hi]-maintenance[i],dtype='<f8'));offsets.append(offsets[-1]+int(hi-lo))
                    need(offsets[-1]*8+x.nbytes<=limits['epoch_bytes']-8192,'complete joint epoch working bound')
                    arrays={'lfp':x,'lfp_region':np.asarray([review['regions'].index(c['region']) for c in trial_channels],dtype='<i4'),
                        'spike_times':np.concatenate(event) if event else np.empty(0,dtype='<f8'),
                        'spike_offsets':np.asarray(offsets,dtype='<i8'),'unit_region':np.asarray([review['regions'].index(u['region']) for u,train in trial_units],dtype='<i4')}
                    ep=save_epoch(epochs/(tid+'.npz'),arrays,budget,limits['epoch_bytes'])
                    entry['epoch']={'path':tid+'.npz','pin':ep}
                    chronology.append({'id':tid,'maintenance':float(maintenance[i]),'probe':float(probe[i]),'exclusive_end':float(maintenance[i])+2.5,'first':first,'last_exclusive':last,'source':a['pin'],
                        'fractional_alignment_seconds':None if first is None else start+first/400-float(maintenance[i]),'source_rate':None if not has_lfp else rate,
                        'lfp_original_rows0':[c['row0'] for c in trial_channels],'unit_original_rows0':[u['row0'] for u,train in trial_units]})
                rows.append(entry)
            native.append(f.record())
    lineage=cohort(rows);need(len(lineage['patients'])==36 and len(lineage['sessions'])==44,'complete actual source identity closure')
    # Private originals/targets/clock/region review are never mounted to actors.
    manifest={'schema':'n041_private_preparation_v1','rows':rows,'regions':review['regions'],'roster':pin(encoded(roster)),'review':pin(encoded(review)),
        'chronology':chronology,'native_records':native,'all44sessions_retained':True,'physical_native_costs_qualification_required':True}
    result=publish(out/'PRIVATE.json',encoded(manifest),budget,readonly=True)
    return {'path':str(out/'PRIVATE.json'),'pin':result}

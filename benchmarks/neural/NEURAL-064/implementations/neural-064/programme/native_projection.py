"""Unexecuted native source adapters. No h5py/numpy import occurs at module load.
The entrypoint refuses current-phase execution. Helpers consume already-owned
native handles; dictionaries and helper arguments are not admission issuers.
"""
from .lifecycle import require_native_producers
from .design import OUTCOME_FIELDS
from .event_metadata import event_domain_disposition,exclusion_record,projection_census

def _premean(values,times,onset):
    import numpy as np
    a,b=onset-.5,onset;i,j=map(int,np.searchsorted(times,[a,b],side='left'))
    if j-i<2 or times[0]>a or times[-1]<b or np.max(np.diff(np.r_[a,times[i:j],b]))>.1:return None
    part=values[i:j];good=np.isfinite(part)
    return float(np.mean(part[good])) if good.mean()>=.8 else None

def _project_admitted(f,record,reader,response_core,history_producer=None,*,secondary=True):
    """Source-derived event evidence plus held responses, preserving all dispositions.
    reader is the exact original nwb_source API, response_core the original
    spans/response API. The authenticated open-file owner must exist beforehand.
    Optional exact history is not inferred from image-set/session exposure counts.
    """
    import numpy as np
    import math
    cols=[]
    if secondary:
        data,times,published_cols=reader.neural(f,record)
        common=set(record['common_cell_specimen_ids']);rois=sorted(record['rois'],key=lambda x:x['cell_roi_id'])
        cols=np.asarray([col for col,roi in zip(published_cols,rois) if roi['cell_specimen_id'] in common],dtype=int)
        if len(cols)!=len(common):raise ValueError('complete registered-cell join')
    # Catalogue support needs behavior/event metadata, not registered-cell survival.
    for path,unit in [('processing/running/speed/data','cm/s'),('processing/running/speed/timestamps','seconds'),('acquisition/EyeTracking/eye_tracking/timestamps','seconds')]:
        accepted=(unit,unit.encode(),'cm/second',b'cm/second') if unit=='cm/s' else (unit,unit.encode())
        if reader.internal(f,path).attrs.get('unit') not in accepted:raise ValueError('declared behavior unit')
    run=reader.vector(f,'processing/running/speed/data',kind='f');rt=reader.vector(f,'processing/running/speed/timestamps',len(run),'f')
    pupil=reader.vector(f,'acquisition/EyeTracking/pupil_tracking/area',kind='f').astype(float)
    et=reader.vector(f,'acquisition/EyeTracking/eye_tracking/timestamps',len(pupil),'f')
    blink=reader.vector(f,'acquisition/EyeTracking/likely_blink/data',len(pupil),'b')
    pupil[blink|~np.isfinite(pupil)|(pupil<0)]=np.nan
    for clock in (rt,et):
        if not np.isfinite(clock).all() or np.any(np.diff(clock)<=0):raise ValueError('behavior clock')
    # Missing trial/outcome fields affect only the outcome sensitivity. Genuine
    # malformed tables fail; absent tables get an explicit unavailable disposition.
    trial_table={};intervals=reader.internal(f,'intervals')
    outcome_available='trials' in intervals and all(k in reader.internal(f,'intervals/trials') for k in ('id','start_time','stop_time')+OUTCOME_FIELDS)
    trial_ids=reader.vector(f,'intervals/trials/id',kind='iu',cap=100000) if outcome_available else []
    if outcome_available:
        start=reader.vector(f,'intervals/trials/start_time',len(trial_ids),'f',100000)
        stop=reader.vector(f,'intervals/trials/stop_time',len(trial_ids),'f',100000)
        flags={key:reader.vector(f,'intervals/trials/'+key,len(trial_ids),'b',100000) for key in OUTCOME_FIELDS}
        if len(set(trial_ids))!=len(trial_ids) or not np.isfinite(start).all() or not np.isfinite(stop).all() or np.any(stop<=start):raise ValueError('trial join')
        trial_table={int(tid):{'start':start[i],'stop':stop[i],'flags':[int(flags[k][i]) for k in OUTCOME_FIELDS]} for i,tid in enumerate(trial_ids)}
    presentations=[]
    for table in reader.presentations(f):
        p='intervals/'+table['group']+'/';n=len(table['ids']);blocks=reader.internal(f,p+'stimulus_block_name').asstr()[:]
        group=reader.internal(f,p)
        fields={key:reader.vector(f,p+key,n,kind,200000) for key,kind in [('is_change','bif'),('stop_time','f'),('active','b')]}
        fields['is_image_novel']=reader.vector(f,p+'is_image_novel',n,'bif',200000) if 'is_image_novel' in group else np.full(n,np.nan)
        trial=reader.vector(f,p+'trials_id',n,'iuf',200000) if 'trials_id' in group else np.full(n,np.nan)
        for i in range(n):
            presentations.append({'source_event':str(record['ophys_experiment_id'])+':'+table['group']+':'+str(table['ids'][i]),
                'image':table['image_names'][i],'omitted':table['omitted'][i],'onset':table['starts'][i],
                'block':blocks[i],'trial':trial[i],**{k:values[i] for k,values in fields.items()}})
    presentations.sort(key=lambda r:(r['onset'],r['source_event']))
    if len({r['source_event'] for r in presentations})!=len(presentations) or len({r['onset'] for r in presentations})!=len(presentations):raise ValueError('duplicate presentation identity/onset')
    history={};events=[];held={};dispositions=[]
    for sequence,row in enumerate(presentations):
        onset=float(row['onset']);eid=row['source_event'];image=row['image'];prior=history.get(image,0)
        if not math.isfinite(onset):raise ValueError('onset')
        reason=event_domain_disposition(row)
        if reason:
            dispositions.append(exclusion_record(record,row,reason));continue
        history[image]=prior+1
        if not row['active']:
            if secondary:raise ValueError('active secondary source mismatch')
            reason='not_active'
        elif not .15<=row['stop_time']-onset<=.35:reason='duration'
        elif sequence+1>=len(presentations) or presentations[sequence+1]['onset']<onset+.55:reason='next_stimulus_or_clock'
        if reason:dispositions.append(exclusion_record(record,row,reason));continue
        rv=_premean(run,rt,onset);pv=_premean(pupil,et,onset)
        native=bool(row['is_image_novel']) if row['is_image_novel'] in (0,1) else None
        change=int(row['is_change']) if row['is_change'] in (0,1) else None
        outcome=None;trial=row['trial']
        if math.isfinite(trial) and float(trial).is_integer() and int(trial) in trial_table:
            tr=trial_table[int(trial)]
            if not tr['start']<=onset<tr['stop']:raise ValueError('trial onset containment disagreement')
            outcome=tr['flags']
        lifetime=None
        if history_producer is not None:lifetime=history_producer.exact_prior_image_presentations(record['mouse_id'],record['ophys_session_id'],image,str(record['ophys_session_id'])+':'+eid.split(':',1)[1])
        if lifetime is not None and (type(lifetime)is not int or lifetime<0):raise ValueError('exact-history producer value')
        spans=response_core.spans(times,onset) if secondary else None;supported=secondary and spans is not None and bool(len(cols))
        event={'event':eid,'behavior_event':str(record['ophys_session_id'])+':'+eid.split(':',1)[1],'experiment':str(record['ophys_experiment_id']),'mouse':str(record['mouse_id']),'container':str(record['ophys_container_id']),
           'session':str(record['ophys_session_id']),'condition':record['experience_level'],'session_order':record.get('source_session_order'),
           'date':record['date_of_acquisition'],'onset_order':sequence,'image':image,'native_image_novel':native,
           'lifetime_image_count':lifetime,'lifetime_count_status':'known' if lifetime is not None else 'unavailable',
           'prior_image_set_sessions':record['prior_exposures_to_image_set'],'within_session_prior_count':prior,
           'within_session_history':sum(prior>=x for x in (10,50,200)),'pre_running_bin':sum(rv>=x for x in (1,5,10)) if rv is not None else None,
           'pre_pupil_bin':None,'pre_pupil_area':pv,'running':rv,'change':change,
           'outcome_status':'known' if outcome is not None else 'unavailable','outcome_flags':outcome,
           'neural_support':('supported' if supported else 'unavailable_clock_or_registered_cells') if secondary else 'not_requested_catalogue_support',
           'phase':'FIRST' if record['experience_level']=='Novel 1' else 'REPEAT' if record['experience_level']=='Novel >1' else None,
           'registered_cells':len(cols) if secondary else None,'split':record.get('split'),'cre_line':record['cre_line'],'image_set':record['image_set'],
           'area':record['targeted_structure'],'depth':float(record['targeted_imaging_depth'])}
        if supported:held[eid]=response_core.response(lambda a,b:data[a:b,:],cols,spans)
        events.append(event)
    valid=[r for r in events if r['pre_pupil_area'] is not None and r['running'] is not None]
    if valid:
        # Preserve and disclose original target-free full-session rank transduction.
        bins=response_core.percentile_bins([r['pre_pupil_area'] for r in valid])
        for row,bin_id in zip(valid,bins):row['pre_pupil_bin']=bin_id
    census=projection_census([r['source_event'] for r in presentations],events,dispositions)
    return {'events':events,'held_responses':held,'dispositions':dispositions,'event_census':census,
            'lifetime_counter_from_session_exposure':False,'original_source_QC_registration_transductive':True}

def run_projection(*args,**kwargs):require_native_producers()

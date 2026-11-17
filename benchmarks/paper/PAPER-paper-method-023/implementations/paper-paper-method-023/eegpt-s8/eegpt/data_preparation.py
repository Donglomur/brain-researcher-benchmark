"""Trusted raw-to-signal asset construction, never a participant capability.

Separately selected input preparation precedes a benchmark lifetime. It extracts
known annotations to private files; no candidate, prediction, score or fit runs.
Native converter parity and original event/split semantics remain actual gates.
"""
import math,os,hashlib
from pathlib import Path
from .protocol import HandleCustody,boundary,Directory,fields,need,digest,descriptor,identity,encode,decode,persist,stream_capture,read_metadata,observation,Refusal
from .scope import DATASETS,CLASSES,validate_census


class OriginalArrayWriter:
    """File-like sink with original short-write/prefix custody, no array logic."""
    def __init__(self,root,name,capacity,budget):
        self.name=name;self.capacity=capacity;self.budget=budget;self.accepted=0;self.hash=hashlib.sha256();self.fd=None;self.extent=None;self.close_failure=None;self.original_finalize_exception=None;self.original_close_exception=None;self.finalize_secondary_exceptions=[]
        budget.reserve('output_bytes',capacity);budget.reserve_file();self.fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=root.fd)
    def write(self,value):
        value=memoryview(value).cast('B');need(self.accepted+len(value)<=self.capacity,'original complete array write reserve');start=self.accepted
        while value:
            self.budget.guard('before_original_array_write');count=os.write(self.fd,value);need(type(count) is int and 0<count<=len(value),'original positive bounded write');self.hash.update(value[:count]);self.accepted+=count;self.budget.observe('output_bytes',count);value=value[count:];self.budget.guard('after_original_array_write')
        return self.accepted-start
    def flush(self):self.budget.guard('before_original_array_flush');os.fsync(self.fd);self.budget.guard('after_original_array_flush')
    def tell(self):return self.accepted
    def close(self):
        if self.fd is None:return
        fd=self.fd;self.fd=None;primary=None;secondary=[]
        try:self.extent=os.fstat(fd).st_size
        except BaseException as exc:primary=exc;self.original_finalize_exception=exc
        try:os.close(fd)
        except BaseException as exc:
            self.original_close_exception=exc
            if primary is None:primary=exc;self.original_finalize_exception=exc
            else:self.finalize_secondary_exceptions.append(exc);secondary.append(observation(exc))
            self.close_failure=observation(exc)
        if primary is not None:
            raise Refusal('original array writer finalization failed',observation={'primary':observation(primary),'secondary':secondary,'original_writer':self.evidence()}) from primary
    def evidence(self):
        return {'path':self.name,'known_accepted_prefix_bytes':self.accepted,'known_accepted_prefix_sha256':self.hash.hexdigest(),'observed_file_extent':self.extent,'additional_physical_bytes_unknown':self.extent is None or self.extent!=self.accepted,'original_file_retained':True,'close_failure':self.close_failure}


def raw_recording(root,record,budget):
    """Concrete raw readers; never an injected scientific decoder callback."""
    import numpy as np
    fields(record,('id','dataset','root','member','reader','array_key','source_axes','sampling_hz','channels','units','qualification'),'complete raw recording binding');digest(record['qualification']);member=descriptor(record['member']);stream_capture(root,member['path'],expected=member,ledger=budget,cap=budget.limits['per_file_bytes']);path=root.path/member['path']
    if record['reader'] in ('mne_edf','mne_gdf'):
        import mne
        reader=mne.io.read_raw_edf if record['reader']=='mne_edf' else mne.io.read_raw_gdf
        with HandleCustody('original_mne_recording') as owned:
            raw=owned.own(reader(str(path),preload=False,verbose='ERROR'),'raw_recording')
            need(list(raw.ch_names)==record['channels'] and float(raw.info['sfreq'])==record['sampling_hz'],'complete actual original source channel/rate metadata');need(len(raw.ch_names)*raw.n_times*8*4<=budget.limits['resident_bytes'],'full raw allocation fits preparation budget; no truncated recording');value=raw.get_data()
        need(record['source_axes']=='channel,time' and record['units']=='V','MNE physical reader yields volts; no silent unit relabeling')
    elif record['reader']=='scipy_mat':
        import scipy.io
        need(record['array_key'] and member['bytes']*4<=budget.limits['resident_bytes'],'explicit MAT member and bounded full read');document=scipy.io.loadmat(str(path),variable_names=[record['array_key']]);need(record['array_key'] in document,'original named MAT scientific array');value=document[record['array_key']]
    elif record['reader']=='numpy_npy':value=np.load(path,allow_pickle=False)
    elif record['reader']=='numpy_npz':
        with np.load(path,allow_pickle=False) as archive:need(record['array_key'] in archive.files,'original named NPZ scientific array');value=archive[record['array_key']]
    else:raise Refusal('G03/G05: selected original raw reader absent or unqualified; no format guess: '+record['reader'])
    need(value.dtype.kind in 'fiu' and value.ndim in (2,3) and np.isfinite(value).all(),'complete finite original source; no object array or invented missingness');need(value.nbytes*4<=budget.limits['resident_bytes'],'whole original signal transform budget')
    if record['source_axes']=='time,channel':value=value.T
    elif record['source_axes']=='epoch,time,channel':value=value.transpose(0,2,1)
    else:need(record['source_axes'] in ('channel,time','epoch,channel,time'),'declared original axis convention')
    need(value.shape[-2]==len(record['channels']),'actual complete original channel axis');return np.asarray(value,dtype=np.float64)


def derive_epoch(recording,record,row,recipe):
    """Explicit source clock, units, channel/reference/filter/resample order."""
    import numpy as np
    from scipy.signal import butter,sosfiltfilt,resample_poly
    fields(recipe,('id','channel_ids','scale_to_output_units','output_units','reference','bandpass','resample','window_samples','qualification','historical_parity'),'complete preselected signal recipe');digest(recipe['qualification']);need(recipe['historical_parity'] in ('unqualified','independently_qualified'),'native parity never inferred from a plausible transform')
    window=row['raw_window'];fields(window,('epoch_index','start_sample','end_sample'),'exact raw interval');start=window['start_sample'];end=window['end_sample'];need(type(start)is int and type(end)is int and 0<=start<end<=recording.shape[-1],'complete original raw sample interval')
    if recording.ndim==3:
        index=window['epoch_index'];need(type(index)is int and 0<=index<len(recording),'actual original epoch index');raw=recording[index,:,start:end]
    else:need(window['epoch_index'] is None,'continuous clock has no invented epoch index');raw=recording[:,start:end]
    need(len(set(recipe['channel_ids']))==len(recipe['channel_ids']) and set(recipe['channel_ids'])<=set(record['channels']),'selected available channels; never invent absent electrodes');indices=[record['channels'].index(c) for c in recipe['channel_ids']];value=raw[indices].copy()*recipe['scale_to_output_units'];need(math.isfinite(recipe['scale_to_output_units']) and recipe['scale_to_output_units']!=0,'explicit physical unit conversion')
    ref=recipe['reference'];fields(ref,('kind','channels'),'fixed reference recipe')
    if ref['kind']=='average':need(ref['channels'] and set(ref['channels'])<=set(recipe['channel_ids']),'actual selected reference electrodes');value-=value[[recipe['channel_ids'].index(c) for c in ref['channels']]].mean(axis=0,keepdims=True)
    else:need(ref['kind']=='unchanged' and ref['channels']==[],'no implicit reference')
    filt=recipe['bandpass']
    if filt is not None:
        fields(filt,('kind','low_hz','high_hz','order','padlen'),'fixed complete-epoch bandpass');need(filt['kind']=='scipy_butterworth_sos_zero_phase' and 0<filt['low_hz']<filt['high_hz']<record['sampling_hz']/2,'explicit filter; not claimed native FIR parity');sos=butter(filt['order'],[filt['low_hz'],filt['high_hz']],btype='bandpass',fs=record['sampling_hz'],output='sos');value=sosfiltfilt(sos,value,axis=-1,padlen=filt['padlen'])
    resample=recipe['resample'];fields(resample,('up','down','window','padtype','output_hz'),'exact rational resampling');need(type(resample['up'])is int and type(resample['down'])is int and resample['up']>0 and resample['down']>0 and record['sampling_hz']*resample['up']/resample['down']==resample['output_hz'],'source and rational derived clocks agree')
    if resample['up']!=resample['down']:value=resample_poly(value,resample['up'],resample['down'],axis=-1,window=tuple(resample['window']),padtype=resample['padtype'])
    need(value.shape==(len(recipe['channel_ids']),recipe['window_samples']) and np.isfinite(value).all(),'complete prespecified epoch; no silent trim, pad or drop');return np.asarray(value,dtype='<f8',order='C')


def build_assets(configuration,scope,budget):
    """Full selected source population, durable labels isolated from signals."""
    import numpy as np
    fields(configuration,('schema','raw_roots','metadata_root','plan','annotation_root','annotations','output_root','qualification','limits','operative_source_identity'),'whole separately selected asset preparation');need(configuration['schema']=='eegpt_raw_asset_preparation_v1','explicit trusted preparation');digest(configuration['qualification']);roots={};held=None;raw_meta=None;produced=[];handles=[];failure=None;result=None;close_failures=[]
    try:
        held=Directory(configuration['output_root']);need(not os.listdir(held.fd),'fresh complete asset destination')
        for name in ('signals','targets','development','metadata'):os.mkdir(name,0o700,dir_fd=held.fd)
        raw_meta=Directory(configuration['metadata_root']);plan=decode(read_metadata(raw_meta,configuration['plan'],cap=budget.limits['metadata_bytes'],ledger=budget));fields(plan,('schema','raw_recordings','rows','recipes','census','qualified_population','corpus_supports','source_annotation_key_policy')+(('temple_events',) if plan.get('schema')=='eegpt_full_raw_to_row_plan_v2' else ()),'complete unfiltered source-to-row plan');need(plan['schema'] in ('eegpt_full_raw_to_row_plan_v1','eegpt_full_raw_to_row_plan_v2') and set(plan['census']['datasets'])==set(DATASETS),'all seven downstream datasets');need(len({r['id'] for r in plan['raw_recordings']})==len(plan['raw_recordings']) and len({r['id'] for r in plan['rows']})==len(plan['rows']),'unique complete recording/row identities')
        validate_census(plan['census'],scope,plan['qualified_population'],require_target_roster=False)
        for k,v in configuration['raw_roots'].items():roots[k]=Directory(v)
        with HandleCustody('source_annotations') as owned:
            annotation_root=owned.own(Directory(configuration['annotation_root']),'annotations')
            annotations=decode(read_metadata(annotation_root,configuration['annotations'],cap=budget.limits['metadata_bytes'],ledger=budget))
        fields(annotations,('schema','labels','source_provenance'),'original private annotation map');need(annotations['schema']=='eegpt_source_annotations_v1','known answers from source annotations, never model outputs');annotation_identity=identity(configuration['annotations']);records={r['id']:r for r in plan['raw_recordings']};rows={r['id']:r for r in plan['rows']};byrecord={k:[] for k in records}
        for row in rows.values():
            fields(row,('id','recording_id','dataset','person','session','event','raw_window','recipe','annotation_key'),'complete original event');need(row['recording_id'] in records and row['dataset']==records[row['recording_id']]['dataset'] and type(row['recipe']) is dict and set(row['recipe'])==({'H','P_I'} if row['dataset'] in DATASETS else {'CORPUS'}) and set(row['recipe'].values())<=set(plan['recipes']),'concrete original dataset/source/recipe binding');byrecord[row['recording_id']].append(row)
        if plan['schema']=='eegpt_full_raw_to_row_plan_v2':
            need(type(plan['temple_events']) is dict and set(plan['temple_events'])=={rid for rid,r in records.items() if r['dataset']=='TUEV'},'exact complete TUEV event timing rosters; no other annotations in method preprocessing')
        need(all(byrecord.values()),'every admitted raw recording has its complete selected scientific rows');targets={d:{} for d in DATASETS};derived={};signals=Directory(str(held.path/'signals'));handles.append(signals)
        for rid,record in records.items():
            raw=boundary(budget,'complete_raw_recording',raw_recording,roots[record['root']],record,budget)
            for row in byrecord[rid]:
                views={};row_captures={}
                for mode,recipe_id in row['recipe'].items():
                    recipe=plan['recipes'][recipe_id];name=identity({'source_row':row['id'],'source':record['member'],'recipe':recipe})+'.npy'
                    if name in row_captures:capture=row_captures[name]
                    else:
                        value=boundary(budget,'complete_epoch_derivation',derive_epoch,raw,record,row,recipe);path=signals.path/name;capacity=value.nbytes+4096;writer=None;write_failure=None;write_secondary=[]
                        try:
                            writer=OriginalArrayWriter(signals,name,capacity,budget);np.lib.format.write_array(writer,value,version=(1,0),allow_pickle=False);writer.flush()
                        except BaseException as exc:write_failure=observation(exc)
                        finally:
                            if writer is not None:
                                try:writer.close()
                                except BaseException as exc:
                                    if write_failure is None:write_failure=observation(exc)
                                    else:write_secondary.append(observation(exc))
                        if write_failure is not None:raise Refusal('original complete epoch write failed',observation={'row':row['id'],'mode':mode,'path':name,'failure':write_failure,'secondary_failures':write_secondary,'original_writer':None if writer is None else writer.evidence(),'earlier_original_captures':produced})
                        size=writer.extent;need(size==writer.accepted and size<=capacity,'original reserved output extent and prefix');capture=stream_capture(signals,name,size=size,cap=budget.limits['per_file_bytes'],ledger=budget);row_captures[name]=capture
                    lineage={'raw_source_identity':identity(record),'raw_sample_interval':row['raw_window'],'source_hz':record['sampling_hz'],'derived_hz':recipe['resample']['output_hz'],'source_units':record['units'],'recipe':recipe}
                    views[mode]={'signal':{'root':'prepared_signals','member':capture['source'],'format':'npy_little_endian_c_float','shape':[len(recipe['channel_ids']),recipe['window_samples']],'label_free_evidence':configuration['qualification']},'channels':recipe['channel_ids'],'sampling_hz':recipe['resample']['output_hz'],'units':recipe['output_units'],'interval':[row['raw_window']['start_sample']/record['sampling_hz'],row['raw_window']['end_sample']/record['sampling_hz']],'transform_ancestry':identity(lineage)};produced.append({'row_id':row['id'],'mode':mode,'original_capture':capture,'lineage':lineage,'identical_nonadaptive_view_reused':list(row['recipe'].values()).index(recipe_id)!=list(row['recipe']).index(mode)})
                derived[row['id']]={'row':row,'views':views,'raw_source_identity':identity(record)}
                if row['dataset'] in DATASETS:
                    key=row['annotation_key'];need(key in annotations['labels'],'complete original annotation');label=annotations['labels'][key];need(type(label)is int and 0<=label<CLASSES[row['dataset']],'mapped semantic class');targets[row['dataset']][row['id']]=label
                else:need(row['annotation_key'] is None,'pretraining corpus export label-free')
            if record['dataset'] in ('TUAB','TUEV') and plan['schema']=='eegpt_full_raw_to_row_plan_v2':
                from .temple_assets import build_recording_views
                method_views=build_recording_views(raw,record,byrecord[rid],plan['temple_events'].get(rid),signals,configuration['qualification'],budget,produced)
                for row_id,views in method_views.items():derived[row_id]['method_views']=views
            raw=None
        census=decode(encode(plan['census']));census['target_rosters']={};census['development_label_rosters']={};troot=Directory(str(held.path/'targets'));handles.append(troot);droot=Directory(str(held.path/'development'));handles.append(droot);mroot=Directory(str(held.path/'metadata'));handles.append(mroot)
        for dataset,document in census['datasets'].items():
            included={r['id'] for r in document['records'] if r['included']};need(set(targets[dataset])==included,'every original included downstream event, no available subset')
            for r in document['records']:
                if not r['included']:continue
                d=derived[r['id']];need(d['row']['dataset']==dataset and d['row']['person']==r['person'] and d['row']['session']==r['session'],'full person/session/event joins');r['signal']={'by_mode':d['views'],**({'by_method':d['method_views']} if 'method_views' in d else {})};r['label_provenance']=annotation_identity;r['channels']=d['views']['P_I']['channels'];r['sampling_hz']=d['views']['P_I']['sampling_hz'];r['units']=d['views']['P_I']['units'];r['transform_ancestry']=identity(d);r['source_identity']=d['raw_source_identity'];r['interval']=d['views']['P_I']['interval']
            census['target_rosters'][dataset]=persist(troot,dataset+'.json',encode({'schema':'eegpt_protected_targets_v1','dataset':dataset,'rows':targets[dataset],'source_identity':annotation_identity,'exposure':document['source_policy']}),ledger=budget)
            for fold,split in enumerate(document['folds']):
                for mode in ('H','P_I'):
                    for role in ('train','validation'):
                        labels={rid:targets[dataset][rid] for rid in split[mode][role]};key=dataset+':f'+str(fold)+':'+mode+':'+role;census['development_label_rosters'][key]=persist(droot,identity(key)+'.json',encode({'schema':'eegpt_development_labels_v1','dataset':dataset,'fold':fold,'mode':mode,'role':role,'labels':labels,'source_identity':annotation_identity}),ledger=budget)
        for support in plan['corpus_supports'].values():
            for row in support['rows']:
                d=derived[row['id']];need(d['row']['annotation_key'] is None,'no corpus annotation export');view=d['views']['CORPUS'];row['signal']=view['signal']
                for key in ('channels','sampling_hz','units','interval','transform_ancestry'):row[key]=view[key]
        validate_census(census,scope,plan['qualified_population']);population_pin=persist(mroot,'QUALIFIED_POPULATION.json',encode(plan['qualified_population']),ledger=budget);cp=persist(mroot,'CENSUS.json',encode(census),ledger=budget);sp=persist(mroot,'CORPUS_SUPPORTS.json',encode(plan['corpus_supports']),ledger=budget);lineage=persist(mroot,'RAW_TO_ROW_LINEAGE.json',encode(derived),ledger=budget)
        result={'status':'complete_input_assets_constructed','census':cp,'qualified_population':population_pin,'corpus_supports':sp,'raw_to_row_lineage':lineage,'original_recordings':len(records),'original_rows':len(rows),'source_annotation_identity':annotation_identity,'scientific_benchmark_execution':False,'historical_converter_parity_claim':False,'qualification_established_by_construction':False}
    except BaseException as exc:failure=observation(exc)
    finally:
        for handle in [*handles,raw_meta,*roots.values(),held]:
            if handle is not None:
                try:handle.close()
                except BaseException as exc:close_failures.append(observation(exc))
    try:budget.guard('after_all_original_asset_closes_before_return')
    except BaseException as exc:
        if failure is None:failure=observation(exc)
        else:close_failures.append(observation(exc))
    if failure is not None or close_failures:raise Refusal('whole original raw preparation failed',observation={'failure':failure,'original_captures':produced,'original_close_failures':close_failures,'known_budget':budget.report(),'unpublished_result':result})
    return result

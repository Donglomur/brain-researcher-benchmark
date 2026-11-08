"""Private complete-cohort local-window construction. Authentic invocation remains gated."""
import math
from pathlib import Path
from core import DAYS,FAMILIES,VARIANTS,WINDOWS,encoded,identity,need,split,shuffled_targets
from safe_io import array,capture,child,new_json,strict,write_array


def read_array(root,d,cap):
    # The native envelope additionally retains original class, F order and NaN mask.
    return array(root,{k:d[k] for k in ('path','bytes','sha256','shape','dtype')},cap)


def channels(family,neural,nuisance):
    import numpy as np
    need(family in FAMILIES,'Declared matched family')
    if family=='neural':return neural
    if family=='nuisance_clock':return nuisance
    if family in ('combined','shuffled_combined'):return np.concatenate([neural,nuisance],axis=0)
    return np.empty((0,15),dtype='<f8')


def load_session(root,manifest,case,limits):
    import numpy as np
    need(manifest.get('status')=='structural_export_with_bound_identity_document','All original census, identity, cross-variant and source-order gates must close')
    rows=[r for r in manifest['imaging_sessions'] if all(r.get(k)==case[k] for k in ('variant','animal_ordinal','day'))]
    need(len(rows)==1,'Exact full original session member')
    row=rows[0];a=row['arrays'];cap=limits['max_array_bytes']
    # Bounds are derived from the full structural census, never a cropped panel.
    need(sum(d.get('bytes',0) for d in a.values() if type(d) is dict)<=limits['session_input_bytes'],'Whole session allocation')
    signal=read_array(root,a['spks'],cap);eligible=read_array(root,a['eligible_mask'],cap).reshape(-1)
    quality=read_array(root,a['iscell'],cap).reshape(-1)
    need(signal.ndim==3 and signal.shape[1:]==(140,402) and eligible.shape==(signal.shape[0],),'Complete original neural geometry')
    need(np.all(np.isfinite(quality)) and np.array_equal(eligible.astype(bool),quality>.3),'Literal common iscell predicate')
    need(np.any(eligible),'No eligible cells: explicit incomplete support, no replacement cohort')
    need(not np.isinf(signal).any(),'Infinite neural input is not missingness')
    locomotion=read_array(root,a['locomotion'],cap);need(locomotion.shape==(140,402) and not np.isinf(locomotion).any(),'Complete selected locomotion field')
    labels=read_array(root,a['first_odor_B'],cap).reshape(-1)
    behavior=read_array(root,a['beh'],cap);need(behavior.shape==(140,5),'Complete source condition metadata')
    conditions=behavior[:,0];need(np.all(np.isin(conditions,[11,12,21,22,511,512,521,522])),'Declared original condition strata')
    need(labels.shape==(140,) and np.all(np.isfinite(labels)) and np.all((labels==0)|(labels==1)),'All authenticated odor labels')
    offsets=read_array(root,a['lick_offsets'],cap).reshape(-1);events=read_array(root,a['lick_events_seconds'],cap).reshape(-1)
    need(offsets.shape==(141,) and offsets[0]==0 and offsets[-1]==len(events) and np.all(np.diff(offsets)>=0) and np.all(offsets==np.floor(offsets)),'Full ragged lick membership')
    need(np.all(np.isfinite(events)),'Missing lick timing cannot become zero licks')
    clock=row['clock'];times=read_array(root,clock['frametimes'],cap).reshape(-1)
    need(times.shape==(402,) and np.all(np.isfinite(times)) and np.all(np.diff(times)>0),'Full increasing authenticated frame clock')
    need(clock.get('common_delay_verified') is True and clock.get('first_odor_offset_verified') is True and clock.get('second_odor_onset_verified') is True,'Physical common-delay support must be authenticated, not inferred from array positions')
    edges=np.concatenate([[times[0]-(times[1]-times[0])/2],(times[:-1]+times[1:])/2,[times[-1]+(times[-1]-times[-2])/2]])
    licks=np.zeros((140,402),dtype='<f8')
    for i in range(140):licks[i]=np.histogram(events[int(offsets[i]):int(offsets[i+1])],edges)[0]
    return row,signal[eligible.astype(bool)],locomotion,licks,labels.astype(int).tolist(),conditions.astype(int).tolist()



def public_null(evidence):
    return {'schema':'h_public_conditional_null_summary_v2','public_seed_commitment':evidence['public_seed_commitment'],
            'atom_sizes':[len(a['trials']) for a in evidence['atoms']],
            'atom_class_counts':[a['class_counts'] for a in evidence['atoms']],
            'interpretation':evidence['meaning'],'permutation_and_seed_exposed':False}


def construct(root,manifest,case,limits,output,private_seed):
    """Private operator writes family views; role producers receive one family only."""
    import numpy as np
    row,signal,locomotion,licks,labels,conditions=load_session(root,manifest,case,limits)
    s=split(case['fold']);null,null_evidence=shuffled_targets(labels,s,case,private_seed)
    out=Path(output);need(not out.exists(),'Fresh complete fold preparation root');out.mkdir(parents=True)
    files={};families={};query=[]
    def save(directory,name,x):
        x=np.ascontiguousarray(x)
        d=write_array(directory/name,x,limits['max_array_bytes']);d['path']=str((directory/name).relative_to(out));files[d['path']]={k:d[k] for k in ('bytes','sha256')};return d
    for family in FAMILIES:
        folder=out/family;folder.mkdir()
        # All outer-fit training rows, ordered by independent case/group/window hash.
        training=[(t,w) for t in s['train'] for w in range(5)]
        training.sort(key=lambda pair:identity({'training_order':case,'trial':pair[0],'window':pair[1]}))
        groupmap={t:i for i,t in enumerate(s['train'])}
        values=[];missing=[];clocks=[];targets=[];groups=[]
        for trial,w in training:
            begin,end=WINDOWS[w];x=channels(family,signal[:,trial,begin:end],np.stack([locomotion[trial,begin:end],licks[trial,begin:end]]))
            mask=np.isnan(x);values.append(np.where(mask,0,x));missing.append(mask.astype('|u1'))
            clocks.append(np.eye(5,dtype='<f8')[w]);targets.append(null[trial] if family=='shuffled_combined' else labels[trial]);groups.append(groupmap[trial])
        data={}
        if family!='clock_prior':
            data['values']=save(folder,'values.npy',np.asarray(values,dtype='<f8'))
            data['missing']=save(folder,'missing.npy',np.asarray(missing,dtype='|u1'))
        if family!='neural':data['clock']=save(folder,'clock.npy',np.asarray(clocks,dtype='<f8'))
        data['labels']=save(folder,'labels.npy',np.asarray(targets,dtype='<i8').reshape(-1,1))
        data['trial_group']=save(folder,'trial_group.npy',np.asarray(groups,dtype='<i8').reshape(-1,1))
        inner=[{'fold':r['fold'],'train_groups':[groupmap[x] for x in r['train']],'validation_groups':[groupmap[x] for x in r['validation']]} for r in s['inner']]
        training_manifest={'schema':'h_training_view_v2','family':family,'rows':len(training),'groups':len(s['train']),'arrays':{k:{**v,'path':Path(v['path']).name} for k,v in data.items()},'inner_folds':inner,'channels':0 if family=='clock_prior' else int(values[0].shape[0]),'clock':family!='neural','null':public_null(null_evidence) if family=='shuffled_combined' else None,'feature_support':{'channels':0 if family=='clock_prior' else int(values[0].shape[0]),'samples':15,'clock':family!='neural'},'both_classes':set(targets)=={0,1},'query_labels_exposed':False}
        md=new_json(folder/'TRAINING.json',training_manifest);files[str((folder/'TRAINING.json').relative_to(out))]=md
        families[family]={'directory':family,'manifest':md,'files':{Path(v['path']).name:{k:v[k] for k in ('bytes','sha256')} for v in data.values()}|{'TRAINING.json':md}}
    # Queries are private and never co-mounted into a training producer.
    qdir=out/'private_query';qdir.mkdir()
    for trial in s['query']:
        for w,(begin,end) in enumerate(WINDOWS):
            opaque=identity({'private_query':case,'trial':trial,'window':w})
            query.append({'opaque_id':opaque,'trial':trial,'window':w,'label':labels[trial],'condition':conditions[trial]})
    query.sort(key=lambda r:r['opaque_id'])
    qa={'neural':save(qdir,'neural.npy',np.asarray([signal[:,r['trial'],slice(*WINDOWS[r['window']])] for r in query],dtype='<f8')),'nuisance':save(qdir,'nuisance.npy',np.asarray([np.stack([locomotion[r['trial'],slice(*WINDOWS[r['window']])],licks[r['trial'],slice(*WINDOWS[r['window']])]]) for r in query],dtype='<f8'))}
    q={'schema':'h_private_queries_v1','case':case,'records':query,'arrays':{k:{**v,'path':Path(v['path']).name} for k,v in qa.items()}}
    qpin=new_json(qdir/'QUERIES.json',q);files['private_query/QUERIES.json']=qpin
    private_null_pin=new_json(out/'PRIVATE_NULL_PROVENANCE.json',null_evidence);files['PRIVATE_NULL_PROVENANCE.json']=private_null_pin
    result={'schema':'h_fold_preparation_v1','case':case,'families':families,'private_query':{'manifest':qpin,'directory':'private_query','files':{Path(v['path']).name:{k:v[k] for k in ('bytes','sha256')} for v in qa.values()}|{'QUERIES.json':qpin}},'full_support':True,'trial_split':s,'source_technical_identity':row.get('technical_identity'),'files':files}
    new_json(out/'RESULT.json',result)
    return result

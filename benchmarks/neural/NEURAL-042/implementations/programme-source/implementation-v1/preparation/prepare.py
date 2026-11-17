"""Concrete full44-session preparation, no PAC/scoring; inactive until root gates.

Every original channel has a private disposition. Complete O/D/A views contain
only one person's permitted observations and no clinical/source/key material.
"""
import hashlib
import hmac
import math
import os
import struct
from pathlib import Path
from core import need,integer,finite,encoded,pin,parse,capture,publish,fresh,canonical,relative,parent_chain,sync_dir,close_preserving,cleanup_preserving,descriptor
from authority import selection_pin
from contracts import exact,opaque,identities,projection
from preparation.nwb import Native
from journal import Journal
LOCK={'bytes':16501,'sha256':'988b0b979d9d940963ee8c0223b2e0941ef8754279f59f60afb459da91dbe548'}


def token(key,text):return hmac.new(key,text.encode(),hashlib.sha256).hexdigest()[:24]


def secret(path,budget):
    path=parent_chain(path);budget.reserve_read(33);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        st=os.fstat(fd);need(st.st_size==32 and st.st_nlink==1 and st.st_mode&0o077==0,'private ordinary32-byte secret')
        import stat
        need(stat.S_ISREG(st.st_mode),'ordinary secret')
        data=os.read(fd,33);need(len(data)==32,'exact secret extent')
        from core import stamp
        need(stamp(st)==stamp(os.fstat(fd))==stamp(os.lstat(path)),'secret same-open/name custody')
        budget.tick();return data
    finally:close_preserving(fd)


def window(maintenance,probe,start,samples):
    maintenance,probe,start=map(finite,(maintenance,probe,start));first=math.ceil((maintenance-start)*400);last=first+1000
    need(type(samples)is int and first>=0 and last<=samples and maintenance+2.5<=probe and start+first/400>=maintenance
         and (first==0 or start+(first-1)/400<maintenance)and start+(last-1)/400<maintenance+2.5 and start+(last-1)/400<probe,
         'complete half-open maintenance support before probe; no guessed/resampled window')
    return first,last


def array_file(path,array,budget,max_bytes):
    """Primitive NPY1 writer with no pickle or full encoded-body copy."""
    import numpy as np
    need(type(array)is np.ndarray and array.dtype==np.dtype('<f8')and array.flags.c_contiguous,'primitive contiguous little-endian f8')
    shape=array.shape;need(len(shape)in(1,2)and all(type(v)is int and v>=0 for v in shape),'bounded array shape')
    description=repr({'descr':'<f8','fortran_order':False,'shape':shape}).encode('ascii')
    padding=(-10-len(description)-1)%64;header=description+b' '*padding+b'\n'
    need(len(header)<65536,'NPY1 header bound');prefix=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header
    length=len(prefix)+array.nbytes;need(length<=max_bytes,'selected prepared array extent')
    budget.reserve_write(length);path=parent_chain(path);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    digest=hashlib.sha256()
    try:
        for part in (memoryview(prefix),memoryview(array).cast('B')):
            while part:
                budget.tick();block=part[:1<<20];n=os.write(fd,block);need(n>0,'prepared array short write');digest.update(block[:n]);part=part[n:]
        os.fchmod(fd,0o444);os.fsync(fd)
    finally:close_preserving(fd)
    sync_dir(path.parent);result={'bytes':length,'sha256':digest.hexdigest()};budget.tick();return result


def review_valid(value,assets):
    exact(value,('schema','sessions','nonhippocampal_tokens','vocabulary_evidence'),'full clinical/schema review')
    need(value['schema']=='neural042_complete_clinical_review_v2','complete qualified region vocabulary schema')
    vocab=value['nonhippocampal_tokens'];need(type(vocab)is list and vocab==sorted(set(vocab))and len(vocab)<=4096,'complete bounded explicit nonhippocampal vocabulary')
    need(all(type(v)is str and 0<len(v.encode())<=256 and v not in('hippocampus_left','hippocampus_right')for v in vocab),'no implicit anatomical spelling normalization')
    evidence=value['vocabulary_evidence'];need(type(evidence)is list and evidence,'independent actual source-schema vocabulary evidence')
    for row in evidence:exact(row,('path','pin'),'source vocabulary evidence');relative(row['path']);descriptor(row['pin'])
    rows=value['sessions'];need(type(rows)is list and len(rows)==44,'all44 clinical session reviews')
    mapped={row['asset_id']:row for row in rows};need(len(mapped)==44 and set(mapped)=={x['asset_id']for x in assets},'complete source review join')
    for asset in assets:
        row=mapped[asset['asset_id']];exact(row,('asset_id','source_sha256','preprocessing','evidence','channels'),'exact session review')
        need(row['source_sha256']==asset['sha256'],'review to authentic source pin')
        need(row['preprocessing']==dict.fromkeys(('local_reference_verified','spike_interpolation_before_downsampling_verified','lowpass_175hz_and_400hz_verified','notch_60_120hz_verified'),True),'published preprocessing evidence unresolved')
        need(all(type(v)is bool for v in row['preprocessing'].values()),'typed preprocessing declarations')
        need(type(row['evidence'])is str and 20<=len(row['evidence'])<=4000,'documentary clinical evidence')
        need(type(row['channels'])is list and row['channels'],'complete channel decisions')
        for channel in row['channels']:
            exact(channel,('row0','exclude_channel','reason','bad_trial_rows0'),'exact channel review')
            integer(channel['row0'],0,511);need(type(channel['exclude_channel'])is bool,'typed clinical exclusion')
            need(type(channel['reason'])is str and len(channel['reason'])<=4000 and(not channel['exclude_channel']or channel['reason'].strip()),'clinical exclusion reason')
            bad=channel['bad_trial_rows0'];need(type(bad)is list and len(bad)==len(set(bad)),'unique reviewed trial mask')
            for i in bad:integer(i,0,139)
    return {'sessions':mapped,'nonhippocampal_tokens':vocab,'vocabulary_evidence':evidence}


def run(a,budget,captured):
    import numpy as np
    cfg=a['preparation'];roots=a['roots'];output=canonical(roots['packet']);private=canonical(roots['private'])
    made=False;intent=None;phase='admission';completed=[];native_records=[];audit_journal=None;audit_count=0
    try:
        need(np.__version__=='2.2.6','exact prospective preparation NumPy environment')
        lock=captured['files']['preparation/SOURCE_ASSETS.json'];need(pin(lock)==LOCK,'exact compiled source roster')
        source=parse(lock);assets=source['assets'];need(len(assets)==44 and len({x['subject_id']for x in assets})==36 and sum(x['bytes']for x in assets)==23447043476,'complete native source census')
        for asset in assets:relative(asset['path']);descriptor({'bytes':asset['bytes'],'sha256':asset['sha256']})
        review_raw,_=capture(Path(roots['operator'])/relative(cfg['clinical_review']['path']),cfg['clinical_review']['pin'],cfg['clinical_review_bytes'],budget,readonly=True)
        review=review_valid(parse(review_raw),assets)
        for evidence in review['vocabulary_evidence']:
            capture(Path(roots['operator'])/relative(evidence['path']),evidence['pin'],cfg['clinical_review_bytes'],budget,retain=False,readonly=True)
        for name in ('identity_key','control_seed'):
            path=canonical(cfg[name]);need(canonical(roots['secrets'])in path.parents,'secret in independently admitted private namespace')
        need(cfg['identity_key']!=cfg['control_seed'],'distinct identity and pre-study control secrets')
        key=secret(cfg['identity_key'],budget);seed=secret(cfg['control_seed'],budget)
        need(hashlib.sha256(seed).hexdigest()==cfg['prestudy_control_seed_commitment'],'independently precommitted controlseed before originals')
        # Secret values and identity-key hashes are never published or returned.
        people=sorted({token(key,'patient:'+x['subject_id'])for x in assets});identities(people,36)
        sessions=[{'id':token(key,x['asset_id']),'person':token(key,'patient:'+x['subject_id']),'eligible_channels':[]}for x in assets]
        need(len({s['id']for s in sessions})==44,'opaque source session bijection')
        fresh(output,budget);fresh(private,budget);made=True
        for name in ('O','D','A'):fresh(output/name,budget)
        intent=publish(private/'INTENT.json',encoded({'schema':'neural042_preparation_intent_v1','selection':selection_pin(a),'source':LOCK,'clinical_review':cfg['clinical_review']['pin'],'source_manifest':captured['pin'],'original_origin':a['clock']['origin'],'full_sessions':44,'full_people':36,'control_seed_commitment':hashlib.sha256(seed).hexdigest()}),budget,readonly=True)
        audit_journal=Journal(private/'CHANNEL_AUDIT.jsonl',budget,a['resources']['journal_bytes'],a['resources']['journal_event_bytes'])
        views={};channel_ids=set();dispositions={'considered':0,'eligible':0,'excluded':0}
        for world in ('O','D','A'):
            for person in people:
                root=fresh(output/world/person,budget)
                views[(world,person)]={'schema':'neural042_view_v1','world':world,'person':person,
                    'sessions':sorted(s['id']for s in sessions if s['person']==person),'channels':[],
                    'files':{},'source':LOCK,'protocol':cfg['protocol'],'preparation':selection_pin(a)}
        for asset,session in zip(assets,sessions):
            phase='session/'+session['id'];path=Path(roots['raw'])/relative(asset['path'])
            with Native(path,{'bytes':asset['bytes'],'sha256':asset['sha256']},budget,cfg['native_limits'])as f:
                need(f.read('general/subject/subject_id',(),text=True)==asset['subject_id'],'source subject identity')
                data=f.object('acquisition/LFPs/data');need(data.ndim==2 and data.dtype.kind in 'fiu'and 0<data.shape[1]<=512,'time by channel primitive LFP')
                start=finite(f.read('acquisition/LFPs/starting_time',(),shape=()).item());rate=f.attribute('acquisition/LFPs/starting_time','rate');need(rate==400,'source400Hz')
                need(f.attribute('acquisition/LFPs/data','unit',text=True)in('volts','volt','V'),'explicit volts source units')
                conv=f.attribute('acquisition/LFPs/data','conversion')if 'conversion'in data.attrs else 1.;offset=f.attribute('acquisition/LFPs/data','offset')if 'offset'in data.attrs else 0.
                need(conv>0,'positive conversion')
                group=f.object('acquisition/LFPs','group')
                cc=f.read('acquisition/LFPs/channel_conversion',shape=(data.shape[1],))if 'channel_conversion'in group else np.ones(data.shape[1])
                need((cc>0).all(),'positive channel conversion')
                electrodes=f.read('acquisition/LFPs/electrodes',shape=(data.shape[1],),kinds='iu');locations=f.object('general/extracellular_ephys/electrodes/location')
                need(locations.ndim==1 and len(set(electrodes.tolist()))==len(electrodes)and ((electrodes>=0)&(electrodes<locations.shape[0])).all(),'LFP electrode row mapping')
                fields={k:f.read('intervals/trials/'+k,shape=(140,),kinds='biuf')for k in ('loads','response_accuracy','probe_in_out','timestamps_Maintenance','timestamps_Probe')}
                need(set(fields['loads'].tolist())<={1,3}and set(fields['response_accuracy'].tolist())<={0,1}and set(fields['probe_in_out'].tolist())<={0,1},'no guessed source label recoding')
                units=f.object('units','group');ends=f.read('units/spike_times_index',kinds='iu');ue=f.read('units/electrodes',shape=ends.shape,kinds='iu');spikeset=f.object('units/spike_times')
                need(ends.ndim==1 and spikeset.ndim==1 and (len(ends)==0 or ends[-1]==spikeset.shape[0])and (np.diff(np.r_[0,ends])>=0).all(),'complete monotone unit spike boundaries')
                if 'electrodes_index'in units:
                    ei=f.read('units/electrodes_index',shape=ends.shape,kinds='iu');need(np.array_equal(ei,np.arange(1,len(ei)+1)),'only exactly one-electrode sorted units admitted')
                need(((ue>=0)&(ue<locations.shape[0])).all(),'unit electrode row mapping')
                decisions=review['sessions'][asset['asset_id']]['channels'];need(len(decisions)==data.shape[1]and {x['row0']for x in decisions}==set(range(data.shape[1])),'all source channels reviewed')
                for decision in sorted(decisions,key=lambda x:x['row0']):
                    ch=decision['row0'];dispositions['considered']+=1;loc=f.read('general/extracellular_ephys/electrodes/location',int(electrodes[ch]),text=True)
                    need(loc in('hippocampus_left','hippocampus_right')or loc in review['nonhippocampal_tokens'],'unsupported anatomical token is a source-schema refusal, never biological exclusion')
                    selected=np.flatnonzero(ue==electrodes[ch]);trials=[i for i in range(140)if i not in decision['bad_trial_rows0']]
                    reason='outside_hippocampus'if loc not in('hippocampus_left','hippocampus_right')else'reviewed_channel_exclusion'if decision['exclude_channel']else'no_colocated_sorted_unit'if not len(selected)else'all_trials_review_excluded'if not trials else None
                    audit={'asset':asset['asset_id'],'channel_row':ch,'reason':reason,'bad_trial_rows':decision['bad_trial_rows0']}
                    if reason:
                        dispositions['excluded']+=1;audit_journal.append({'kind':'channel_disposition',**audit});audit_count+=1;continue
                    n=len(trials);need(4*n*1000*8<=cfg['planned_working_array_bytes'],'prospective complete O/D/window temporary plan')
                    x=np.empty((n,1000),dtype='<f8');counts=np.zeros(n,dtype='<f8');maint=fields['timestamps_Maintenance'][trials];timing=[]
                    for j,i in enumerate(trials):
                        first,last=window(float(fields['timestamps_Maintenance'][i]),float(fields['timestamps_Probe'][i]),start,data.shape[0])
                        timing.append({'original_trial_row0':i,'recording_start_seconds':start,'maintenance_seconds':float(fields['timestamps_Maintenance'][i]),
                            'probe_seconds':float(fields['timestamps_Probe'][i]),'epoch_stop_seconds':float(fields['timestamps_Maintenance'][i])+2.5,
                            'first_sample_index0':first,'exclusive_last_sample_index0':last,'first_sample_time':start+first/400,
                            'last_sample_time':start+(last-1)/400,'fractional_alignment_seconds':start+first/400-float(fields['timestamps_Maintenance'][i]),'fs':400})
                        row=f.read('acquisition/LFPs/data',(slice(first,last),ch),shape=(1000,));x[j]=np.asarray(row,dtype='<f8')*conv*cc[ch]+offset
                    need(np.isfinite(x).all(),'finite converted full trial, never silent dropping')
                    for u in selected:
                        lo=0 if u==0 else int(ends[u-1]);hi=int(ends[u]);train=f.read('units/spike_times',slice(lo,hi),shape=(hi-lo,))
                        need((np.diff(train)>=0).all(),'sorted finite spike train')
                        counts+=np.searchsorted(train,maint+2.5,side='left')-np.searchsorted(train,maint,side='left')
                    rates=np.ascontiguousarray(counts/(2.5*len(selected)),dtype='<f8')
                    identity=token(key,asset['asset_id']+':'+str(ch));need(identity not in channel_ids,'opaque channel uniqueness');channel_ids.add(identity);session['eligible_channels'].append(identity)
                    ids=[token(key,asset['asset_id']+':trial:'+str(i))for i in trials]
                    labels={'id':identity,'session':session['id'],'loads':[int(fields['loads'][i])for i in trials],'correct':[int(fields['response_accuracy'][i])for i in trials],
                        'probe':[int(fields['probe_in_out'][i])for i in trials],'order':trials,'ids':ids,'n_trials':n,'samples':1000,'fs':400,'units':'volts'}
                    donor=list(range(n));strata={}
                    for i in range(n):strata.setdefault((trials[i]//35,labels['probe'][i]),[]).append(i)
                    draws=[]
                    for st,ix in sorted(strata.items()):
                        ix=sorted(ix,key=lambda i:ids[i]);g=np.random.default_rng(int.from_bytes(hmac.new(seed,(identity+':'+str(st)).encode(),hashlib.sha256).digest()[:8],'big'))
                        shift=int(g.integers(1,len(ix)))if len(ix)>1 else 0
                        for j,to in enumerate(ix):donor[to]=ix[(j-shift)%len(ix)]
                        draws.append({'stratum':list(st),'recipient_indices':ix,'shift':shift})
                    need(sorted(donor)==list(range(n)),'complete disrupted withinstratum bijection')
                    audit.update(opaque_channel=identity,person=session['person'],session=session['id'],trial_rows=trials,trial_ids=ids,colocated_units=selected.tolist(),control_draws=draws,donor_indices=donor)
                    audit['sample_timing']=timing;audit_journal.append({'kind':'channel_disposition',**audit});audit_count+=1;dispositions['eligible']+=1
                    for world in ('O','D','A'):
                        view=views[(world,session['person'])];root=output/world/session['person'];channel=fresh(root/identity,budget)
                        metadata=publish(channel/'CHANNEL.json',encoded(labels),budget,readonly=True);entry={'id':identity,'session':session['id'],'metadata':{'path':identity+'/CHANNEL.json','pin':metadata}}
                        view['files'][identity+'/CHANNEL.json']=metadata
                        if world!='A':
                            arr=x if world=='O'else np.ascontiguousarray(x[donor],dtype='<f8');rr=rates if world=='O'else np.ascontiguousarray(rates[donor],dtype='<f8')
                            for name,array in (('lfp.npy',arr),('rates.npy',rr)):
                                desc=array_file(channel/name,array,budget,cfg['prepared_array_bytes']);entry[name[:-4]]={'path':identity+'/'+name,'pin':desc};view['files'][identity+'/'+name]=desc
                        view['channels'].append(entry)
                native_records.append(f.record())
            completed.append(session['id'])
        rows=[]
        for (world,person),view in sorted(views.items()):
            view['channels'].sort(key=lambda x:x['id']);raw=encoded(view);desc=publish(output/world/person/'VIEW.json',raw,budget,readonly=True)
            rows.append({'world':world,'person':person,'path':world+'/'+person+'/VIEW.json','pin':desc})
        for session in sessions:session['eligible_channels'].sort()
        result={'schema':'neural042_projection_v1','source':LOCK,'protocol':cfg['protocol'],'preparation':selection_pin(a),'people':people,'sessions':sorted(sessions,key=lambda x:x['id']),'views':rows,'dispositions':dispositions};projection(result)
        audit_journal.close();audit_journal=None
        from core import describe_sealed
        audit_desc={'path':'CHANNEL_AUDIT.jsonl','pin':describe_sealed(private/'CHANNEL_AUDIT.jsonl',a['resources']['journal_bytes'],budget)}
        private_record={'schema':'neural042_private_preparation_evidence_v2','intent':intent,'clinical_review':cfg['clinical_review'],'full_source_lock':LOCK,'channel_audit':audit_desc,'channel_disposition_count':audit_count,'native_reads':native_records,'completed_sessions':completed,'all44sessions':len(completed)==44,'costs_before_publication':budget.record()}
        private_pin=publish(private/'PREPARATION.json',encoded(private_record),budget,readonly=True)
        rp=publish(output/'PROJECTION.json',encoded(result),budget,readonly=True)
        receipt={'schema':'neural042_preparation_complete_v1','projection':rp,'private_evidence':private_pin,'source':captured['pin'],'selection':selection_pin(a),'all_people':36,'all_sessions':44,'actual_physical_immutability_not_inferred_from_chmod':True,'costs_before_final_publication':budget.record()}
        cp=publish(private/'COMPLETE.json',encoded(receipt),budget,readonly=True);budget.tick();return {'status':'complete','projection':rp,'private_receipt':cp}
    except BaseException as error:
        failure={'schema':'neural042_preparation_failure_v1','phase':phase,'completed_sessions':completed,'intent':intent,'setup_returned':made,'early_setup_custody_unknown':not made,'original_error':type(error).__name__,'read_reserved':budget.read_bytes,'write_reserved':budget.write_bytes,'later_errors':[],'no_retry':True}
        try:
            if made:publish(private/'FAILED.json',encoded(failure),budget,readonly=True)
        except BaseException as later:failure['later_errors'].append(type(later).__name__)
        failure['final_read_reserved']=budget.read_bytes;failure['final_write_reserved']=budget.write_bytes
        try:error.failure_record=failure
        except BaseException:pass
        raise
    finally:
        if audit_journal is not None:cleanup_preserving(audit_journal.close)

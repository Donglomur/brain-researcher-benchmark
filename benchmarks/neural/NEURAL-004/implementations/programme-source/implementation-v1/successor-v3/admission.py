"""Actual original reader and private target-alias audit; dormant on import."""
import hashlib
import os
import stat
from pathlib import Path
from .common import PEOPLE,CHANNELS,fields,need,integer,finite,pin,check_pin,Cleanup,read_body,decode

class ReaderAudit:
    """Passthrough audit of the exact source crop function; never selects rows."""
    def __init__(self,original,np,ledger):self.original=original;self.np=np;self.ledger=ledger;self.people=[]
    def __call__(self,*args,**kwargs):
        need(not kwargs and len(args)==12,'exact pinned crop-call interface')
        data,rts,triggers,offset,hz,lower,upper,epochs,threshold,indices,ignore,verbose=args
        need(ignore is False and hz==512 and offset==5 and lower==.1 and threshold==1e-4,'unchanged original reader crop semantics')
        if self.np.isinf(upper):upper=epochs.tmax-(offset+1)/hz
        time0=epochs.time_as_index(0)[0];dispositions=[];eligible=[]
        need(len(indices)==len(rts)==len(data),'all original clean epochs in crop call')
        self.ledger.reserve({'read_bytes':int(data.nbytes)+int(self.np.asarray(rts).nbytes)},'audit exact original crop predicates')
        for pos,(epoch,rt) in enumerate(zip(indices,rts)):
            reason=None;n=None
            if self.np.isnan(rt):reason='missing_RT'
            elif rt>upper:reason='above_original_RT_limit'
            elif rt<lower:reason='below_original_RT_limit'
            else:
                samples=int(self.np.rint(rt*hz));n=samples+offset
                if samples<=0:reason='nonpositive_rounded_RT'
                elif not bool((self.np.abs(data[pos,:,time0:time0+n])<threshold).all()):reason='strict_original_amplitude_rejection'
            retained=reason is None
            if retained:eligible.append(int(epoch))
            dispositions.append({'epoch':int(epoch),'retained':retained,'reason':reason,'sample_count':n if retained else None})
        # Scientific result comes only from the original unchanged function.
        attempt={'status':'attempted','rows':dispositions};self.people.append(attempt)
        try:
            result=self.original(*args)
            need(list(map(int,result[1]))==eligible,'audited predicates equal original returned trial roster')
            attempt['status']='complete';self.ledger.tick();return result
        except BaseException as error:
            attempt.update(status='failed',failure=type(error).__name__);error.neural004_reader_audit=list(self.people);raise

def verify_file(path,descriptor,ledger):
    check_pin({k:descriptor[k] for k in ('bytes','sha256')})
    ledger.reserve({'read_bytes':descriptor['bytes']+1},'original file complete authentication')
    with Cleanup(ledger) as cleanup:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);cleanup.defer('close original authentication handle',lambda:os.close(fd))
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==descriptor['bytes'],'ordinary exact original file')
        digest=hashlib.sha256();count=0
        with ledger.live(65536,'original digest chunk'):
            while True:
                ledger.tick();raw=os.read(fd,65536)
                if not raw:break
                count+=len(raw);need(count<=descriptor['bytes'],'original file grew');digest.update(raw)
        after=os.fstat(fd);signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(signature(before)==signature(after) and count==descriptor['bytes'] and digest.hexdigest()==descriptor['sha256'],'complete unchanged original identity')
        return list(signature(after))

def alias_audit(metadata,event_id,event_code):
    # Mapping comes directly from original preprocessing.py stimulus/<trigger>.
    required={'event_name','rt','condition','side','stimulus','response'}
    need(required<=set(metadata),'original metadata fields')
    literal=str(metadata['stimulus']);y=float(literal)/100
    need(.025<finite(y)<1,'logged contrast/100 domain')
    name=str(metadata['event_name']);need(name.startswith('stimulus/'),'source stimulus event name')
    trigger=float(name.split('/',1)[1])
    need(trigger==float(literal) and name in event_id and event_id[name]==event_code and float(event_code)==trigger,'all target-bearing event aliases agree')
    need(metadata['condition'] in ('speed','accuracy') and metadata['side'] in ('left','right') and metadata['response'] in ('left','right'),'original instruction/expected/actual response vocabularies')
    return {'contrast':y,'logged_literal':literal,'rt':finite(float(metadata['rt'])),
        'instruction':int(metadata['condition']=='accuracy'),'response':str(metadata['response']),
        'side':str(metadata['side']),'event_name':name,'event_code':int(event_code)}

def read_original(root,source_roster,source_qualification,authorities,ledger,limits):
    """Only a separately qualified authentic invocation can call the real reader.

    Complete hashes bracket MNE/HMP reads. Qualified immutable mount custody is
    independently attested; hashing alone is not a physical isolation guarantee.
    """
    need(type(source_roster) is list and len(source_roster)==26,'original26 file roster')
    for pid,d in zip(PEOPLE,source_roster):
        fields(d,('person','name','bytes','sha256'));need(d['person']==pid and d['name']==pid+'_epo.fif','unchanged exact original roster')
    extent=sum(d['bytes'] for d in source_roster);need(extent<=integer(limits['source_bytes'],1),'complete source extent fits selected profile')
    qualified=authorities.verify(source_qualification,'operator','input_admission',pin(source_roster))
    fields(qualified['facts'],('immutable_mount','source_mapping','support_admission','runtime_admission','source_tree_pin','reader_memory_bound_bytes'))
    facts=qualified['facts']
    for key in ('immutable_mount','source_mapping','support_admission','runtime_admission','source_tree_pin'):check_pin(facts[key])
    need(facts['reader_memory_bound_bytes']<=integer(limits['reader_live_bytes'],1),'independently admitted whole reader memory bound')
    # Bounds reserve the complete known invocation, not an unsupported RSS claim.
    ledger.reserve({'processes':1,'read_bytes':extent},'MNE/HMP full reader invocation')
    root=Path(root);need(root.is_absolute() and not root.is_symlink(),'fixed admitted original root')
    before={d['person']:verify_file(root/d['name'],d,ledger) for d in source_roster}
    import importlib.metadata
    import mne
    import hmp
    import numpy as np
    need(importlib.metadata.version('hmp')=='1.0.0b2','exact admitted HMP release')
    from .hmp_core.binding import EXPECTED_BINDING
    source_doc=decode(read_body(Path(__file__).parent/'hmp_core/SOURCES.json',EXPECTED_BINDING,ledger,EXPECTED_BINDING['bytes']),EXPECTED_BINDING['bytes'])
    io_record=next(x for x in source_doc['files'] if x.get('installed_relative')=='hmp/io.py')
    read_body(Path(hmp.io.__file__),{k:io_record[k] for k in ('bytes','sha256')},ledger,io_record['bytes'])
    original={};header_roster=[]
    with ledger.live(facts['reader_memory_bound_bytes'],'whole original reader reservation'):
        for d in source_roster:
            epochs=mne.read_epochs(root/d['name'],preload=False,verbose=False)
            need(epochs.info['sfreq']==512 and [n for n,t in zip(epochs.ch_names,epochs.get_channel_types()) if t=='eeg']==list(CHANNELS),'source512Hz32channel order')
            need(epochs.metadata is not None,'original metadata present')
            local={}
            need(list(map(int,epochs.selection))==[i for i,reasons in enumerate(epochs.drop_log) if not reasons],'exact source drop-log/epoch selection mapping')
            # The HMP reader uses epochs.selection as original epoch identity.
            for pos,epoch in enumerate(epochs.selection):
                md=epochs.metadata.iloc[pos].to_dict()
                local[int(epoch)]={'raw_metadata':md,'event_id':dict(epochs.event_id),'event_code':int(epochs.events[pos,2]),'metadata':{k:str(md[k]) for k in ('event_name','stimulus','condition','side','response')},'epoch_tmax':float(epochs.tmax)}
            original[d['person']]=local
            header_roster.append({'person':d['person'],'source_pin':{k:d[k] for k in ('bytes','sha256')},'original_epoch_ids':list(local),
                'upstream_drop_log':[{'epoch':i,'reasons':list(reasons),'present_in_cleaned_reader_input':not bool(reasons)} for i,reasons in enumerate(epochs.drop_log)]})
        ledger.tick()
        original_crop=hmp.io._cut_at_rt;audit=ReaderAudit(original_crop,np,ledger)
        with Cleanup(ledger) as cleanup:
            def restore_reader():
                need(hmp.io._cut_at_rt is audit,'only restore owned exact reader wrapper');hmp.io._cut_at_rt=original_crop
            cleanup.defer('restore exact original crop function',restore_reader);hmp.io._cut_at_rt=audit
            epoch_data=hmp.io.read_mne_data([str(root/d['name']) for d in source_roster],sfreq=512,data_format='epochs',
                lower_limit_rt=.1,offset_after_resp=.01,reject_threshold=1e-4,verbose=False,subj_name=list(PEOPLE))
        need(len(audit.people)==26,'complete original-epoch eligibility audit for all26 reader calls')
        need(float(epoch_data.sfreq)==512 and list(epoch_data.participant.values.astype(str))==list(PEOPLE),'complete returned person geometry')
        need(list(epoch_data.channel.values.astype(str))==list(CHANNELS),'returned complete channel order')
        rows=[];audit_rows=[];hmp_rows={p:[] for p in PEOPLE}
        for pid in PEOPLE:
            person=epoch_data.sel(participant=pid)
            for epoch in person.epoch.values:
                values=person.data.sel(epoch=epoch).transpose('channel','sample').values
                mask=np.isfinite(values);valid=np.all(mask,axis=0)
                if not mask.any():continue  # xarray union padding, never a source trial.
                n=int(valid.sum());need(n>=8 and valid[:n].all() and not mask[:,n:].any(),'complete contiguous source samples and padding')
                need(int(epoch) in original[pid],'retained epoch original identity join');source=original[pid][int(epoch)];a=alias_audit(source['raw_metadata'],source['event_id'],source['event_code'])
                need(.1<=a['rt']<=source['epoch_tmax']-(round(.01*512)+1)/512 and n==int(np.rint(a['rt']*512))+int(np.rint(.01*512)),'exact source RT window/rounding/offset')
                need(np.all(np.abs(values[:,:n])<1e-4),'strict original amplitude eligibility')
                for column in ('stimulus','condition','response'):
                    need(str(person[column].sel(epoch=epoch).item())==source['metadata'][column],'reader metadata exact source join')
                source_row=pin({'person':pid,'epoch':int(epoch),'audit':a,'source_pin':{k:source_roster[int(pid)][k] for k in ('bytes','sha256')}})
                rows.append({'person':pid,'epoch':int(epoch),'rt':a['rt'],'instruction':a['instruction'],'samples':n,
                    'waveform':values[:,:n].tolist(),'contrast':a['contrast'],'source_row':source_row})
                audit_rows.append({'person':pid,'epoch':int(epoch),'alias_audit':a,'source_row':source_row})
                hmp_rows[pid].append({'epoch':int(epoch),'sample_count':n})
        need(all(hmp_rows[p] for p in PEOPLE),'complete nonempty26 person support')
    after={d['person']:verify_file(root/d['name'],d,ledger) for d in source_roster};need(after==before,'original file closure identity')
    return {'epoch_data':epoch_data,'private_rows':rows,'private_alias_audit':audit_rows,
        'source_admission':{'source_roster':source_roster,'header_roster':header_roster,'retained_rows':hmp_rows,
            'eligibility_dispositions':dict(zip(PEOPLE,audit.people)),
            'qualification_pin':qualified['envelope_pin'],'data_pin':pin({'source_roster':source_roster,'retained_rows':hmp_rows,'eligibility':dict(zip(PEOPLE,audit.people))})}}

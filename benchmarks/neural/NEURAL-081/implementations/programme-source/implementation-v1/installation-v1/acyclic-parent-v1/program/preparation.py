"""Trusted complete original-format preparation. No reads/imports at module load.

Only admitted G0 entry calls these functions. The full annotation/key reads are
legitimate trusted preparation reads, never ordinary pre-grade controller reads.
"""
import hashlib,io,os,stat
from pathlib import Path
import common as c
import protocol as p
import arrays
from custody import disjoint_roots

def verify_release(root,inventory,budget):
    c.exact(inventory,('schema','name','torrent_sha256','info_sha1','files','total_bytes','piece_length','piece_sha1'))
    c.need(inventory['schema']=='neural081_release_inventory_v1'and inventory['name']=='OpenMIIR-RawEEG_v1','exact original release')
    c.need(type(inventory['total_bytes'])is int and inventory['total_bytes']==6995284395 and type(inventory['piece_length'])is int and inventory['piece_length']==2097152,'complete original release extent/pieces')
    expected=[x+'-raw.fif'for x in c.PEOPLE]+['README.md'];files=inventory['files'];c.need(type(files)is list and [x['name']for x in files]==expected,'all ten FIFs and README in original torrent order')
    c.need(type(inventory['piece_sha1'])is list and len(inventory['piece_sha1'])==3336,'complete torrent piece roster')
    root=c.absolute(str(root));c.need(not any(x.is_symlink()for x in(root,*root.parents)),'ordinary original release root')
    remainder=bytearray();piece=0;total=0;pins=[]
    for row in files:
        c.exact(row,('name','bytes'));size=c.integer(row['bytes'],1);path=root/row['name'];budget.charge('read_bytes',size+1)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd);c.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==size,'complete ordinary original file')
            h=hashlib.sha256();n=0
            while True:
                budget.check_clock();block=os.read(fd,min(1048576,size+1-n))
                if not block:break
                n+=len(block);c.need(n<=size,'original file grew');h.update(block);remainder.extend(block)
                while len(remainder)>=2097152:
                    c.need(piece<3336 and hashlib.sha1(remainder[:2097152]).hexdigest()==inventory['piece_sha1'][piece],'original cross-file torrent piece')
                    del remainder[:2097152];piece+=1
            after=os.fstat(fd);named=path.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
            c.need(n==size and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields),'complete stable original release file')
            pins.append({'path':str(path),'bytes':n,'sha256':h.hexdigest()});total+=n
        finally:os.close(fd)
    if remainder:
        c.need(piece<3336 and hashlib.sha1(remainder).hexdigest()==inventory['piece_sha1'][piece],'final torrent piece');piece+=1
    c.need(total==6995284395 and piece==3336,'entire release verified before scientific open');budget.check_clock();return pins

class MeteredFIF(io.BufferedReader):
    """Count actual library reads including EOF probes, preserving seek semantics."""
    def __init__(self,path,budget):
        self.budget=budget;self.path=path
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        s=os.fstat(fd);c.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'ordinary original FIF')
        self.stamp=tuple(getattr(s,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
        super().__init__(io.FileIO(fd,'rb',closefd=True))
    def read(self,size=-1):
        if size<0:size=self.stamp[2]-self.tell()+1
        self.budget.charge('read_bytes',size);return super().read(size)
    def readinto(self,buffer):self.budget.charge('read_bytes',len(buffer));return super().readinto(buffer)
    def read1(self,size=-1):
        if size<0:size=io.DEFAULT_BUFFER_SIZE
        self.budget.charge('read_bytes',size);return super().read1(size)
    def stable(self):
        s=os.fstat(self.fileno());named=Path(self.path).stat();keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        c.need(tuple(getattr(s,k)for k in keys)==self.stamp==tuple(getattr(named,k)for k in keys),'original FIF stable through MNE preparation')

def prepare_person(person,file_desc,key,generation,output,budget,environment):
    """One complete person worker; all selected rows survive or worker refuses."""
    c.need(person in c.PEOPLE,'original person');c.digest(generation);c.descriptor(file_desc)
    # No import precedes this exact external environment selection.
    c.exact(environment,('numpy','mne','source_qualified','annotation_qualified'))
    c.need(environment['source_qualified']is True and environment['annotation_qualified']is True,'independently admitted original source/annotation and numerical environment')
    import numpy as np
    import mne
    c.need(np.__version__==environment['numpy']and mne.__version__==environment['mne'],'selected installed package versions; source/image identity also admitted upstream')
    out=c.new_directory(output,budget);rows=[]
    c.authenticate_stream(file_desc,budget,[Path(file_desc['path']).parent])
    with MeteredFIF(file_desc['path'],budget)as source:
        raw=mne.io.read_raw_fif(source,preload=True,verbose='ERROR')
        try:
            c.need(float(raw.info['sfreq'])==512.0 and not any(bool(x.get('active'))for x in raw.info['projs']),'original 512Hz/no active projection')
            c.need(all(raw.ch_names.count(x)==1 for x in p.CHANNELS)and raw.ch_names.count('STI 014')==1,'all canonical channels/processed marker channel')
            bad_channels=raw.info['bads']
            c.need(type(bad_channels)is list and all(type(x)is str and x in raw.ch_names for x in bad_channels)and len(set(bad_channels))==len(bad_channels),'complete original bad-channel metadata, never inferred empty')
            bad_channels=list(bad_channels)  # Private provenance only; all64 EEG picks remain.
            picks=[raw.ch_names.index(x)for x in p.CHANNELS]
            c.need(all(raw.get_channel_types(picks=[i])[0]=='eeg'for i in picks),'complete EEG channel types')
            events=mne.find_events(raw,stim_channel='STI 014',shortest_event=1,verbose='ERROR')
            c.need(type(events)is np.ndarray and events.dtype.kind in 'iu'and events.ndim==2 and events.shape[1]==3,'integer processed event table')
            selected=p.event_roster(events.tolist(),int(raw.first_samp),int(raw.n_times))
            for selected_row in selected:
                budget.check_clock();start=selected_row['source_onset_sample']-int(raw.first_samp)+256
                x=raw.get_data(picks=picks,start=start,stop=start+2048)
                c.need(type(x)is np.ndarray and x.shape==(64,2048)and bool(np.isfinite(x).all()),'every complete original window finite')
                x=np.asarray(x,dtype=np.float64);x=x-x.mean(axis=0,keepdims=True,dtype=np.float64)
                y=x.reshape(64,512,4).mean(axis=2,dtype=np.float64).astype(np.float32)
                ident=p.canonical_id(key,person,selected_row['source_event_index']);d=arrays.write(out/(ident+'.npy'),y,budget)
                rows.append({'person':person,'canonical_id':ident,**selected_row,'processed_condition':4,'source_file_descriptor':file_desc,'window_descriptor':d,'physical_boundary_disposition':'full_fixed_window_admitted'})
            source.stable()
        finally:raw.close()
    rows.sort(key=lambda x:x['canonical_id']);c.need(len({x['canonical_id']for x in rows})==len(rows),'person identity collision')
    receipt={'schema':'neural081_trusted_person_preparation_v1','person':person,'generation':generation,'source':file_desc,'environment':environment,'rows':rows,'original_bad_channels':bad_channels,'real_annotation_reads':True,'complete_condition4_support':True,'feedback_used_for_geometry_or_selection':False,'budget':budget.snapshot()}
    return c.publish_json(out/'PERSON_PROTECTED.json',receipt,budget)

def assemble(person_receipts,key,generation,output,protocol_source,inventory_sources,annotation_authority,budget):
    """Trusted G0 only: exact labels and all keyless future context permutations."""
    c.need(type(person_receipts)is list and len(person_receipts)==10,'ten complete original workers')
    out=c.new_directory(output,budget);private=c.new_directory(out/'protected',budget);roles=c.new_directory(out/'roles',budget);contexts=c.new_directory(out/'contexts',budget)
    allrows=[];bad_flags=[]
    for person,desc in zip(c.PEOPLE,person_receipts):
        body=c.capture_json(desc,budget,[Path(desc['path']).parent]);c.need(body['schema']=='neural081_trusted_person_preparation_v1'and body['person']==person and body['generation']==generation and body['complete_condition4_support']is True,'all ten naturally closed source-bound person results')
        c.need({r['private_label']for r in body['rows']}==set(c.CLASSES),'all original class support privately validated')
        flags=body['original_bad_channels'];c.need(type(flags)is list and all(type(x)is str and x for x in flags)and len(set(flags))==len(flags),'complete privately recorded original flags')
        bad_flags.append({'person':person,'bad_channels':flags})
        allrows.extend(body['rows'])
    allrows.sort(key=lambda r:(c.PEOPLE.index(r['person']),r['canonical_id']));c.need(len({r['canonical_id']for r in allrows})==len(allrows),'global unique canonical support')
    private_rows=[{('source_file'if k=='source_file_descriptor'else k):v for k,v in r.items()}for r in allrows]
    support={'schema':'neural081_support_v1','task_id':c.TASK,'preparation_generation':generation,'protocol_source':protocol_source,'source_inventory':inventory_sources,'people':list(c.PEOPLE),'class_ids':list(c.CLASSES),'canonical_channels':list(p.CHANNELS),'rows':private_rows,'private_boundary_evidence':annotation_authority,'original_bad_channel_flags':bad_flags}
    sd=c.publish_json(private/'SUPPORT.json',support,budget)
    target={'schema':'neural081_assessment_target_v1','task_id':c.TASK,'preparation_generation':generation,'rows':[{'canonical_id':r['canonical_id'],'person':r['person'],'label':r['private_label']}for r in allrows]}
    td=c.publish_json(private/'ASSESSMENT.json',target,budget)
    byid={r['canonical_id']:r for r in allrows};role_map=[];context_map=[];model_tokens=[]
    for view in c.VIEWS:
        for outer in c.PEOPLE:
            training=[r for r in allrows if r['person']!=outer]
            for inner in ('FINAL',*[i for i in c.PEOPLE if i!=outer]):
                people=[x for x in c.PEOPLE if x!=outer and x!=inner];kind='FINAL'if inner=='FINAL'else'INNER'
                ids=p.role_order(key,generation,kind,view,outer,inner,[r['canonical_id']for r in training if r['person']in people])
                permitted=[byid[i]for i in ids]
                # Only this training role gets these labels; global operands are never a dependency.
                labels=c.publish_json(roles/(view+'-'+outer+'-'+inner+'-labels.json'),{'schema':'neural081_role_labels_v1','generation':generation,'ids':ids,'labels':[r['private_label']for r in permitted]},budget)
                role={'schema':'neural081_role_v1','generation':generation,'view':view,'outer_person':outer,'inner_person_or_FINAL':inner,'kind':kind,'people':people,'ids':ids,'windows':[r['window_descriptor']for r in permitted]if view=='EEG'else[],'labels':labels,'rows':[{'canonical_id':r['canonical_id'],'person':r['person']}for r in permitted]}
                rd=c.publish_json(roles/(view+'-'+outer+'-'+inner+'.json'),role,budget);role_map.append({'view':view,'outer':outer,'inner':inner,'role':rd,'allowed':[rd,labels,*role['windows']]})
                if inner=='FINAL':
                    tokens=[p.opaque(key,'|'.join(('NEURAL081-model-row-v2',generation,kind,view,outer,inner,i)))for i in ids]
                    c.need(tokens==sorted(tokens)and len(set(tokens))==len(ids),'fixed role order tokens')
                    td0=c.publish_json(roles/(view+'-'+outer+'-MODEL-TOKENS.json'),{'schema':'neural081_model_row_tokens_v1','generation':generation,'view':view,'outer':outer,'training_role':rd,'tokens':tokens},budget)
                    model_tokens.append({'view':view,'outer':outer,'training_role':rd,'tokens_descriptor':td0})
            # Every episode gets a preissued keyless permutation. No secret in the later issuer.
            for mode in c.MODES:
                for replication in c.REPS:
                    for query in (r for r in allrows if r['person']==outer):
                        alias=p.query_alias(key,mode,replication,view,query['canonical_id']);ordered=p.candidate_aliases(key,generation,alias,training)
                        cm={'schema':'neural081_issued_context_map_v1','generation':generation,'mode':mode,'replication':replication,'view':view,'context_alias':alias,'outer_person':outer,'canonical_id':query['canonical_id'],'training_permutation':ordered,'query_window':query['window_descriptor']if view=='EEG'else None,'training_role':next(x['role']for x in role_map if x['view']==view and x['outer']==outer and x['inner']=='FINAL'),'global_labels_required':False}
                        cd=c.publish_json(contexts/(alias+'.json'),cm,budget);context_map.append({'mode':mode,'replication':replication,'view':view,'canonical_id':query['canonical_id'],'context_alias':alias,'map':cd})
    closed={'schema':'neural081_preparation_closure_v1','generation':generation,'person_results':person_receipts,'protected_support':sd,'protected_assessment':td,'roles':role_map,'contexts':context_map,'model_row_tokens':model_tokens,'annotation_authority':annotation_authority,'complete':True,'trusted_G0_actual_label_reads':True,'all_role_contexts_preissued':True,'budget':budget.snapshot()}
    cd=c.publish_json(out/'PREPARATION_CLOSURE.json',closed,budget)
    index={'schema':'neural081_label_free_support_index_v3','task_id':c.TASK,'preparation_generation':generation,'protocol_source':protocol_source,'source_inventory_descriptors':inventory_sources,'people':list(c.PEOPLE),'class_ids':list(c.CLASSES),'canonical_channels':list(p.CHANNELS),'rows':[{k:v for k,v in r.items()if k!='private_label'}for r in allrows],'protected_support_descriptor':sd,'protected_assessment_descriptor':td,'preparation_closure':cd,'support_disposition':{'complete':True,'all_class_support_privately_validated':True,'physical_annotation_authority':annotation_authority}}
    p.validate_index(index);ix=c.publish_json(out/'SUPPORT_INDEX.json',index,budget);budget.check_clock();return {'index':ix,'closure':cd,'protected_support':sd,'protected_assessment':td}

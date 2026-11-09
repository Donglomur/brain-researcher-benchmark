"""Complete public protocol and exact operator metadata checks. No numeric I/O."""
import hashlib,hmac
import common as c

CHANNELS=('Fp1','AF7','AF3','F1','F3','F5','F7','FT7','FC5','FC3','FC1','C1','C3','C5','T7','TP7','CP5','CP3','CP1','P1','P3','P5','P7','P9','PO7','PO3','O1','Iz','Oz','POz','Pz','CPz','Fpz','Fp2','AF8','AF4','AFz','Fz','F2','F4','F6','F8','FT8','FC6','FC4','FC2','FCz','Cz','C2','C4','C6','T8','TP8','CP6','CP4','CP2','P2','P4','P6','P8','P10','PO8','PO4','O2')
FAMILIES=('BP_LDA','TM_LDA','RBF_KRR')
HANDLES=(*FAMILIES,'HISTORICAL_BP_LDA')
POLICY='single_query_transductive_v4'
REPRESENTATION={'dtype':'float32','shape':[64,512],'sample_rate_hz':128,'units':'V','channels':list(CHANNELS)}
INDEX_KEYS=('schema','task_id','preparation_generation','protocol_source','source_inventory_descriptors','people','class_ids','canonical_channels','rows','protected_support_descriptor','protected_assessment_descriptor','preparation_closure','support_disposition')
ROW_KEYS=('person','canonical_id','source_event_index','source_onset_sample','processed_condition','source_file_descriptor','window_descriptor','physical_boundary_disposition')

def opaque(key,domain):
    c.need(type(key)is bytes and len(key)==32 and type(domain)is str,'exact private identity material/domain')
    return hmac.new(key,domain.encode('utf-8'),hashlib.sha256).hexdigest()[:32]

def canonical_id(key,person,event_index):
    c.need(person in c.PEOPLE,'complete original person');c.integer(event_index)
    return opaque(key,'NEURAL-081:'+person+':'+str(event_index))

def query_alias(key,mode,replication,view,ident):
    c.need(mode in c.MODES and replication in c.REPS and view in c.VIEWS,'selected full mode/replication/view');c.ident(ident)
    return opaque(key,':'.join(('NEURAL-081','query-v2',mode,replication,view,ident)))

def role_order(key,generation,kind,view,outer,inner,ids):
    c.need(kind in ('INNER','FINAL')and view in c.VIEWS and outer in c.PEOPLE and (inner=='FINAL'or inner in c.PEOPLE),'private role identity')
    c.digest(generation);c.need(type(ids)is list and len(set(ids))==len(ids),'complete unique role identities')
    rows=[(opaque(key,'|'.join(('NEURAL081-model-row-v2',generation,kind,view,outer,inner,c.ident(i)))),i)for i in ids]
    c.need(len({x[0]for x in rows})==len(rows),'role identity collision');return [i for _,i in sorted(rows)]

def candidate_aliases(key,generation,alias,rows):
    c.digest(generation);c.ident(alias)
    result=[]
    for row in rows:
        i=c.ident(row['canonical_id']);person=row['person'];c.need(person in c.PEOPLE,'training person')
        result.append({'canonical_id':i,'row_alias':opaque(key,'|'.join(('NEURAL081-training-row-v2',generation,alias,i))),'group_alias':opaque(key,'|'.join(('NEURAL081-training-group-v2',generation,alias,person)))})
    c.need(len({x['row_alias']for x in result})==len(result)and len({x['group_alias']for x in result})==9,'complete collision-free nine-person aliases')
    return sorted(result,key=lambda x:x['row_alias'])

def event_roster(events,first_sample,samples):
    """All condition4 rows or refusal; pseudo-time feedback never sets geometry."""
    c.integer(first_sample);c.integer(samples,2304)
    c.need(type(events)is list and events,'complete processed marker table')
    physical=[];selected=[];previous=-1
    for index,event in enumerate(events):
        c.need(type(event)is list and len(event)==3,'integer event triple')
        for v in event:c.integer(v,0)
        sample,_,code=event;c.need(sample>=previous and first_sample<=sample<first_sample+samples,'ordered in-record marker');previous=sample
        if code in (2000,2001):continue
        if code in (1000,1111):physical.append((sample,code,index));continue
        label,condition=divmod(code,10)
        c.need(label in c.CLASSES and condition in (1,2,3,4),'unknown or unmatched physical/processed event blocks complete support')
        physical.append((sample,code,index))
        if condition==4:selected.append({'source_event_index':index,'source_onset_sample':sample,'private_label':label})
    c.need(12<=len(selected)<=10000 and {r['private_label']for r in selected}==set(c.CLASSES),'complete nonempty twelve-class person support')
    for row in selected:
        s=row['source_onset_sample'];begin=s+256;end=s+2304
        c.need(first_sample<=begin<end<=first_sample+samples,'full fixed crop within recording')
        for t,code,index in physical:
            if index==row['source_event_index']:continue
            c.need(t!=s,'ambiguous coincident physical events')
            c.need(not(s<t<end),'genuine physical onset interrupts full selected window')
    return selected

def validate_index(index):
    c.exact(index,INDEX_KEYS);c.need(index['schema']=='neural081_label_free_support_index_v3'and index['task_id']==c.TASK,'label-free complete support only')
    c.digest(index['preparation_generation']);c.descriptor(index['protocol_source'])
    c.need(c.typed_equal(index['people'],list(c.PEOPLE))and c.typed_equal(index['class_ids'],list(c.CLASSES))and c.typed_equal(index['canonical_channels'],list(CHANNELS)),'original full cohort/classes/channels')
    for d in index['source_inventory_descriptors']:c.descriptor(d)
    for k in ('protected_support_descriptor','protected_assessment_descriptor','preparation_closure'):c.descriptor(index[k])
    c.exact(index['support_disposition'],('complete','all_class_support_privately_validated','physical_annotation_authority'))
    c.need(index['support_disposition']['complete']is True and index['support_disposition']['all_class_support_privately_validated']is True,'trusted full preparation disposition')
    c.descriptor(index['support_disposition']['physical_annotation_authority'])
    rows=index['rows'];c.need(type(rows)is list,'complete typed index rows');keys=[];counts={p:0 for p in c.PEOPLE}
    for row in rows:
        c.exact(row,ROW_KEYS);p=row['person'];c.need(p in c.PEOPLE,'original person');i=c.ident(row['canonical_id'])
        c.integer(row['source_event_index']);c.integer(row['source_onset_sample']);c.need(type(row['processed_condition'])is int and row['processed_condition']==4,'condition alone, no encoded class')
        c.descriptor(row['source_file_descriptor']);c.descriptor(row['window_descriptor'])
        c.need(row['physical_boundary_disposition']=='full_fixed_window_admitted','typed non-narrative physical disposition')
        keys.append((c.PEOPLE.index(p),i));counts[p]+=1
    c.need(keys==sorted(keys)and len({i for _,i in keys})==len(keys),'unique complete canonical order')
    c.need(all(12<=n<=10000 for n in counts.values()),'all ten complete person supports')
    protected=[c.absolute(index[k]['path'])for k in ('protected_support_descriptor','protected_assessment_descriptor')]
    c.need(protected[0]!=protected[1],'distinct complete protected bodies');return index

def permitted_rows(index,people):
    validate_index(index);c.need(type(people)is list and people==[p for p in c.PEOPLE if p in people]and len(set(people))==len(people),'canonical distinct permitted people')
    return [r for r in index['rows']if r['person']in people]

def counts(index):
    validate_index(index);n=len(index['rows'])
    return {'N':n,'people':10,'classes':12,'inner_fits':3600,'inner_inferences':3600,'selectors':20,'final_fits':60,'historical_fits':20,'final_inferences':80,'fixed_fits':3680,'fixed_inferences':3680,'F_cases':6*n,'I_contexts':6*n,'case_closures':12*n,'candidate_panels':120,'reference_panels':80,'analytic_panels':40,'assessment_panels':240,'author_episodes':3,'maximum_scientific_workers':7391+54*n,'maximum_author_native_workers':24,'maximum_provider_requests':54*n+27}

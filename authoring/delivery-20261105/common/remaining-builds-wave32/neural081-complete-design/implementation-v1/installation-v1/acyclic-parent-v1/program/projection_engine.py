"""Trusted keyless current-context projection over exact passed descriptors.

The persistent worker invokes this after its concrete OS access restriction.
It receives no global support/assessment/key descriptor and returns no labels.
"""
import io,os
import common as c
import protocol as p
import arrays
import fd_protocol as f

OUTPUTS=('train.npy','train_labels.npy','train_rows.json','query.npy')

def read_input(sock,expected,sequence,budget,maximum):
    message,fd=f.receive(sock,deadline=budget.end,budget=budget)
    try:
        c.exact(message,('kind','sequence','descriptor'));c.need(message['kind']=='input'and type(message['sequence'])is int and message['sequence']==sequence and c.typed_equal(message['descriptor'],expected)and fd is not None,'exact next selected input descriptor')
        return f.fd_capture(fd,{k:expected[k]for k in ('bytes','sha256')},budget,maximum)
    finally:
        if fd is not None:os.close(fd)

def array_body(raw,dtype,shape,np):
    offset,declared=arrays.npy_header(raw,dtype,shape)
    size=arrays.expected_extent(dtype,shape)
    a=np.frombuffer(raw,dtype=declared,count=size//arrays.DTYPES[dtype][1],offset=offset).reshape(tuple(shape)).astype(dtype,copy=True)
    c.need(type(a)is np.ndarray and bool(np.isfinite(a).all()),'complete finite primitive projection input');return a

class CurrentBudget:
    def __init__(self,parent,endpoint):
        self.parent=parent;self.origin=parent.origin;self.end=c.finite(endpoint);self.clock=parent.clock
        c.need(self.clock()<self.end<=parent.end,'current context inherits whole endpoint');self.before=dict(parent.used)
    def check_clock(self):self.parent.check_clock();c.need(self.clock()<self.end,'original current projection endpoint')
    def charge(self,key,amount):self.check_clock();self.parent.charge(key,amount)
    def snapshot(self):return {'original_origin':self.origin,'original_deadline':self.end,'current_requested_io':{k:self.parent.used[k]-self.before[k]for k in('read_bytes','write_bytes')},'enclosing':self.parent.snapshot()}

def project(sock,request,budget,np):
    c.exact(request,('kind','ordinal','context','role','source','generation','limits','original_endpoint','case_endpoint'))
    c.need(request['kind']=='project'and type(request['ordinal'])is int and request['ordinal']>=0 and type(request['original_endpoint'])is float and request['original_endpoint']==budget.end,'typed current projection and original endpoint')
    budget=CurrentBudget(budget,request['case_endpoint'])
    limits=request['limits'];c.exact(limits,('metadata_bytes','output_bytes','array_bytes'))
    for v in limits.values():c.integer(v,1)
    context=c.parse(read_input(sock,request['context'],0,budget,limits['metadata_bytes']));role=c.parse(read_input(sock,request['role'],1,budget,limits['metadata_bytes']))
    c.exact(context,('schema','generation','mode','replication','view','context_alias','outer_person','canonical_id','training_permutation','query_window','training_role','global_labels_required'))
    c.need(context['schema']=='neural081_issued_context_map_v1'and context['generation']==request['generation']and c.typed_equal(context['training_role'],request['role'])and context['global_labels_required']is False,'exact keyless context/role generation')
    c.need(context['mode']in c.MODES and context['replication']in c.REPS and context['view']in c.VIEWS and context['outer_person']in c.PEOPLE,'all complete current-query identities')
    c.ident(context['context_alias']);c.ident(context['canonical_id'])
    c.exact(role,('schema','generation','view','outer_person','inner_person_or_FINAL','kind','people','ids','windows','labels','rows'))
    people=[x for x in c.PEOPLE if x!=context['outer_person']]
    c.need(role['schema']=='neural081_role_v1'and role['generation']==request['generation']and role['view']==context['view']and role['outer_person']==context['outer_person']and role['inner_person_or_FINAL']=='FINAL'and role['kind']=='FINAL'and role['people']==people,'exact nine-person current training role')
    n=len(role['ids']);c.need(108<=n<=90000 and len(set(role['ids']))==n and len(role['rows'])==n and context['canonical_id']not in role['ids'],'complete current training, query excluded')
    private={}
    for ident,row in zip(role['ids'],role['rows']):
        c.ident(ident);c.exact(row,('canonical_id','person'));c.need(row['canonical_id']==ident and row['person']in people,'permitted training row');private[ident]=row
    c.need({r['person']for r in role['rows']}==set(people),'exact all nine permitted training people')
    permutation=context['training_permutation'];c.need(type(permutation)is list and len(permutation)==n,'full keyless permutation')
    for row in permutation:c.exact(row,('canonical_id','row_alias','group_alias'));c.ident(row['canonical_id']);c.ident(row['row_alias']);c.ident(row['group_alias'])
    c.need({r['canonical_id']for r in permutation}==set(role['ids'])and len({r['row_alias']for r in permutation})==n and [r['row_alias']for r in permutation]==sorted(r['row_alias']for r in permutation),'complete sorted alias bijection')
    groupmap={}
    for row in permutation:
        person=private[row['canonical_id']]['person'];c.need(person not in groupmap or groupmap[person]==row['group_alias'],'same person has one group');groupmap[person]=row['group_alias']
    c.need(len(set(groupmap.values()))==9,'nine distinct opaque groups')
    labels=c.parse(read_input(sock,role['labels'],2,budget,limits['metadata_bytes']))
    c.exact(labels,('schema','generation','ids','labels'));c.need(labels['schema']=='neural081_role_labels_v1'and labels['generation']==request['generation']and labels['ids']==role['ids']and len(labels['labels'])==n and all(type(v)is int and v in c.CLASSES for v in labels['labels'])and set(labels['labels'])==set(c.CLASSES),'exact legitimate isolated training labels')
    lookup=dict(zip(role['ids'],labels['labels']));windows=dict(zip(role['ids'],role['windows']))if context['view']=='EEG'else{}
    c.need(len(role['windows'])==(n if context['view']=='EEG'else 0)and (context['query_window']is not None)==(context['view']=='EEG'),'ZERO has no EEG operands')
    outputs={};fds=[]
    try:
        for name in OUTPUTS:
            message,fd=f.receive(sock,deadline=budget.end,budget=budget)
            if fd is not None:fds.append(fd)
            c.exact(message,('kind','ordinal','name','maximum'))
            c.need(message['kind']=='output'and type(message['ordinal'])is int and message['ordinal']==request['ordinal']and message['name']==name and fd is not None and type(message['maximum'])is int and message['maximum']<=limits['output_bytes'],'exact source-owned output slots')
            outputs[name]=f.Output(fd,budget,message['maximum'])
        # This header then one contiguous row at a time avoids retaining n waveforms.
        np.lib.format.write_array_header_2_0(outputs['train.npy'],{'descr':np.dtype('<f4').str,'fortran_order':False,'shape':(n,64,512)})
        for j,row in enumerate(permutation):
            if context['view']=='EEG':
                raw=read_input(sock,windows[row['canonical_id']],3+j,budget,limits['array_bytes']);a=array_body(raw,'float32',[64,512],np)
            else:a=np.zeros((64,512),dtype=np.float32)
            outputs['train.npy'].write(np.asarray(a,dtype='<f4',order='C').tobytes(order='C'))
        y=np.array([lookup[r['canonical_id']]for r in permutation],dtype='<i8');np.lib.format.write_array(outputs['train_labels.npy'],y,allow_pickle=False)
        outputs['train_rows.json'].write(c.encoded([{'row_alias':r['row_alias'],'group_alias':r['group_alias']}for r in permutation]))
        if context['view']=='EEG':query=array_body(read_input(sock,context['query_window'],3+n,budget,limits['array_bytes']),'float32',[64,512],np)
        else:query=np.zeros((64,512),dtype=np.float32)
        np.lib.format.write_array(outputs['query.npy'],query,allow_pickle=False)
        pins={name:out.pin()for name,out in outputs.items()};budget.check_clock()
        return {'schema':'neural081_projection_reply_v1','ordinal':request['ordinal'],'context':request['context'],'role':request['role'],'generation':request['generation'],'context_alias':context['context_alias'],'mode':context['mode'],'replication':context['replication'],'view':context['view'],'n_train':n,'outputs':pins,'global_label_opens':0,'budget':budget.snapshot()}
    finally:
        for fd in fds:os.close(fd)

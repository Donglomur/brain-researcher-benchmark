"""Operator-only packet admission and exact individual-file fold views; no data copies."""
from pathlib import Path
import secrets
from . import contracts as c
from .budget import Budget
from .storage import IO,root,disjoint,OperationFailure,failure_record,raise_failed
from .prepare import _json


def _load_packet(descriptor,budget,store):
    c.need(type(descriptor) is dict and set(descriptor)=={'root','complete'},'packet input descriptor')
    base=root(descriptor['root']);c.artifact(descriptor['complete'])
    budget.reserve(descriptor['complete']['pin']['bytes']*12+65536,'retained preparation completion')
    complete=store.json(base,descriptor['complete'])
    c.need(complete.get('schema')=='neural049_prepare_complete_v1' and complete.get('status')=='complete_core_bank'
           and complete.get('source_count')==55 and complete.get('person_count')==12,'full preparation completion metadata')
    c.artifact(complete['manifest'])
    budget.reserve(complete['manifest']['pin']['bytes']*12+1048576,'retained complete private packet metadata')
    m=store.json(base,complete['manifest'])
    c.need(m.get('schema')=='neural049_private_packet_v1' and m.get('status')=='complete_core_bank'
           and m.get('source_selection')==complete['source_selection'] and m.get('authority')==complete['authority'],'packet producer joins')
    days=m.get('days');c.need(type(days) is list and len(days)==55,'complete day bank')
    rows=0;keys=[];all_ids=[];all_paths=[];handles=[];axes={}
    for day in days:
        p,d=day['person'],day['day'];c.need(type(p) is str and c.integer(d,1),'private original person/day')
        keys.append((p,d));c.opaque(day['handle']);handles.append(day['handle'])
        ids=day['ids'];axis=day['axis'];n=day['rows'];c.need(c.integer(n) and type(ids) is list and len(ids)==n,'complete ordered row IDs')
        c.need(type(axis) is list and len(axis)>0 and len(axis)==len(set(axis)),'complete unique channel axis')
        for item in ids+axis:c.opaque(item)
        c.need(p not in axes or axes[p]==axis,'one qualified person channel axis');axes[p]=axis
        all_ids.extend(ids);rows+=n
        c.need(day['status']==('empty' if n==0 else 'complete'),'perday disposition')
        expected={'x':([n,len(axis),5000],'<f8'),'mask':([n,len(axis),5000],'|b1'),
                  'context':([n,6],'<f8'),'offsets':([n],'<f8')}
        c.need(type(day['arrays']) is dict and set(day['arrays'])==set(expected),'complete bank field set')
        for name,(shape,dtype) in expected.items():
            x=c.array_descriptor(day['arrays'][name]);c.need(x['shape']==shape and x['dtype']==dtype,'exact array geometry')
            c.need(x['path']=='bank/'+day['handle']+'/'+name+'.npy','positive public bank namespace')
            all_paths.append(x['path'])
        c.need(set(day['labels'])==set(c.ENDPOINTS),'all three private target arrays')
        for endpoint,x in day['labels'].items():
            c.array_descriptor(x);c.need(x['shape']==[n] and x['dtype']=='<f8','exact private label shape')
            c.need(x['path']=='private/'+day['handle']+'/'+endpoint+'.npy','exact private label namespace');all_paths.append(x['path'])
        da=day['disrupted_arrays']
        if da is not None:
            c.need(set(da)=={'x','mask','offsets'},'complete moved bundle')
            for name,x in da.items():
                c.array_descriptor(x);shape,dtype=expected[name]
                c.need(x['shape']==shape and x['dtype']==dtype,'disrupted bundle shape')
                c.need(x['path']=='disrupted/'+day['handle']+'/'+name+'.npy','exact disrupted bank namespace');all_paths.append(x['path'])
    c.need(len(keys)==len(set(keys))==55 and len(axes)==12 and len(handles)==len(set(handles)),'complete distinct person/day handles')
    c.need(len(all_ids)==len(set(all_ids)) and rows==complete['rows']==m['rows'],'complete exact row union')
    c.need(len(all_paths)==len(set(all_paths)),'distinct original and private/disrupted paths')
    c.need(sorted(axes)==[f'{i:02}' for i in range(1,13)] and all(sum(p==f'{i:02}' for p,d in keys)==n
           for i,n in enumerate([4,4,4,5,3,5,5,5,5,5,5,5],1)),'full original source support')
    budget.tick();return base,complete,m


def admit_packet(packet_descriptor,inherited_context):
    budget=inherited_context if type(inherited_context) is Budget else Budget(inherited_context);store=IO(budget)
    try:
        base,complete,m=_load_packet(packet_descriptor,budget,store)
        return {'root':str(base),'complete':complete,'manifest':m,'costs':budget.record(),
                'body_authentication':'metadata only; immutable body sealing/readback remains external'}
    except BaseException as exc:
        raise OperationFailure(failure_record(exc,budget,'packet_admission')) from exc


def select_days(manifest,selection):
    required={'schema','person','train_days','query_days','view','role','case_id','source_policy','packet_pin','selection_authority'}
    c.need(type(selection) is dict and set(selection)==required and selection['schema']=='neural049_fold_selection_v1','exact fold selection')
    c.need(selection['view'] in ('C','N','NC','NC_D') and selection['role'] in ('outer','inner','fit_only','query_only'),'selected role/view')
    c.opaque(selection['case_id']);c.pin(selection['source_policy']);c.pin(selection['packet_pin'])
    person=selection['person'];days={d['day']:d for d in manifest['days'] if d['person']==person}
    train=selection['train_days'];query=selection['query_days']
    c.need(type(train) is list and type(query) is list and all(c.integer(d,1) for d in train+query)
           and train==sorted(set(train)) and query==sorted(set(query)) and not(set(train)&set(query)),'disjoint ordered day sets')
    c.need(set(train+query)<=set(days),'full source membership before paths')
    role=selection['role']
    if role=='outer':c.need(len(query)==1 and set(train)==set(days)-set(query),'full outer other-day training')
    elif role=='inner':c.need(len(query)==1 and len(train)==len(days)-2,'full inner training; one other held outer day')
    elif role=='fit_only':c.need(not query and len(train) in (len(days)-1,len(days)-2),'complete unique selected training scope')
    else:c.need(not train and query and len(query)<=len(days),'full selected query days')
    if selection['view']=='NC_D':
        c.need(manifest['assignment_status']=='complete' and all(d['disrupted_arrays'] is not None for d in manifest['days']),'whole55day D feasibility required')
    return [days[d] for d in train],[days[d] for d in query]



def view_authority(selection,packet,budget,store):
    c.need(type(selection) is dict,'selection metadata')
    descriptor=selection.get('selection_authority')
    c.need(type(descriptor) is dict and set(descriptor)=={'root','body'},'external view authority descriptor')
    base=root(descriptor['root']);c.artifact(descriptor['body'])
    value=store.json(base,descriptor['body'])
    projection={k:v for k,v in selection.items() if k!='selection_authority'}
    c.need(value.get('schema')=='neural049_view_authority_v1' and value.get('status')=='selected_qualified_view', 'view operation inactive/unqualified')
    c.need(c.typed_equal(value.get('selection'),c.pin_bytes(c.canonical(projection)))
           and c.typed_equal(value.get('packet'),packet),'exact selected view and packet')
    c.need(c.typed_equal({k:value.get(k) for k in ('origin','deadline','limits')},
                        {'origin':budget.origin,'deadline':budget.deadline,'limits':budget.limits}), 'view cannot reset clocks/caps')
    c.artifact(value['source_closure']);c.artifact(value['independent_completion'])
    c.need(value.get('physical_roots_status')=='independently_qualified','physical source/private/output custody')
    budget.tick();return value

def materialize_view(packet_descriptor,selection,output_root,inherited_context):
    budget=None;store=None;output=None
    try:
        budget=inherited_context if type(inherited_context) is Budget else Budget(inherited_context);store=IO(budget)
        view_authority(selection,packet_descriptor,budget,store)
        base,complete,m=_load_packet(packet_descriptor,budget,store)
        c.need(c.typed_equal(selection.get('packet_pin'),packet_descriptor['complete']['pin']),'exact preparation pin')
        train,query=select_days(m,selection)
        out=root(output_root,False);disjoint(base,out)
        # The owner authenticates the separately selected operation/role authority before this API.
        # This source enforces the exact role membership and does not trust arbitrary mount callbacks.
        count=sum(d['rows'] for d in train+query)
        with budget.hold(count*2048+1048576,'all selected view IDs/descriptors and serializations'):
            store.mkdir(out);output=out
            _json(store,out,'ATTEMPT.json',{'schema':'neural049_view_attempt_v1','selection':selection,'costs':budget.record()})
            public={'schema':'neural049_case_view_v1','case':selection['case_id'],
                    'view':'NC' if selection['view']=='NC_D' else selection['view'],'sample_rate':500,
                    'train_parts':[],'query_parts':[]}
            mounts=[];private_parts=[];alias_sources={};paths=set()
            for kind,chosen in (('train',train),('query',query)):
                for day in chosen:
                    handle=budget.call('mint opaque view part identity',secrets.token_hex,16)
                    part={'ids':day['ids'],'axis':day['axis'],'arrays':{}}
                    arrays=dict(day['arrays'])
                    if selection['view']=='NC_D':arrays.update(day['disrupted_arrays'])
                    names=['mask','offsets']+([] if selection['view']=='C' else ['x'])+([] if selection['view']=='N' else ['context'])
                    for name in names:
                        desc=arrays[name];alias='inputs/'+handle+'/'+name+'.npy'
                        c.need(alias not in paths,'unique opaque actor path');paths.add(alias)
                        part['arrays'][name]={**desc,'path':alias}
                        mounts.append({'source_root':str(base),'source':{'path':desc['path'],'pin':{'bytes':desc['bytes'],'sha256':desc['sha256']}},
                                       'target':'/case/'+alias,'readonly':True,'role':kind,'kind':name})
                        alias_sources[alias]=desc['path']
                    if kind=='train':
                        part['labels']={}
                        for endpoint,desc in day['labels'].items():
                            alias='inputs/'+handle+'/'+endpoint+'.npy'
                            part['labels'][endpoint]={**desc,'path':alias}
                            mounts.append({'source_root':str(base),'source':{'path':desc['path'],'pin':{'bytes':desc['bytes'],'sha256':desc['sha256']}},
                                           'target':'/case/'+alias,'readonly':True,'role':'train','kind':'label_'+endpoint})
                    public[kind+'_parts'].append(part)
                    private_parts.append({'handle':handle,'person':day['person'],'day':day['day'],'role':kind,
                                          'ids':day['ids'],'axis':day['axis'],'source':day['source'],'empty':day['rows']==0})
            # No source path/ordinal/arm flag enters VIEW; context arrays alone expose legal C day values.
            pub_body=c.canonical(public);c.need(len(pub_body)<=budget.limits['metadata_bytes'],'complete public VIEW size')
            view=store.put(out,'VIEW.json',pub_body)
            private={'schema':'neural049_mount_plan_v1','status':'requires_independent_immutable_mount_admission',
                     'view':view,'packet':packet_descriptor,'selection':selection,'parts':private_parts,'mounts':mounts,
                     'rules':{'individual_files_only':True,'no_source_NWB_or_directory_mount':True,'query_labels':False,
                              'actual_immutability_qualified':False,'case_writable_state_shared':False},'costs':budget.record()}
            mp=_json(store,out,'MOUNTS.json',private)
            final=_json(store,out,'COMPLETE.json',{'schema':'neural049_view_complete_v1','view':view,'mounts':mp,
                    'selection_pin':c.pin_bytes(c.canonical(selection)),'costs_before_publication':budget.record()})
        budget.tick();return {'root':str(out),'complete':final,'view':view,'mounts':mp,'costs':budget.record()}
    except BaseException as exc:
        if store is None:raise OperationFailure(failure_record(exc,budget,'view_initial_admission')) from exc
        raise_failed(store,output,exc,'fold_view_materialization')

"""Full source-owned55-day constructor. Authentic invocation requires external qualification."""
from contextlib import ExitStack
from pathlib import Path
import secrets
from . import contracts as c
from . import npy
from .authority import admit
from .budget import Budget
from .epoch import window,context,donor_order
from .schema import open_day,validate_geometry
from .storage import IO,OperationFailure,failure_record,raise_failed


def _json(store,root,name,value):
    with store.meter.hold(store.meter.limits['metadata_bytes']*12+4096,'metadata serialization '+name):
        body=c.canonical(value)
        c.need(len(body)<=store.meter.limits['metadata_bytes'],'bounded metadata publication')
        return store.put(root,name,body,private=True)


def _permuted(store,root,arrays,donors,base):
    out={};budget=store.meter
    for name in ('x','mask','offsets'):
        desc=arrays[name];shape=desc['shape'];rel=base+'/'+name+'.npy'
        _,rowbytes=c.shape_bytes(shape[1:],desc['dtype']);budget.array(rowbytes)
        with budget.hold(rowbytes+131072,'one whole donor bundle component'):
            with store.verified(root,npy.descriptor(desc)) as src:
                start=npy.inspect(src,desc['bytes'],shape,desc['dtype'],budget)
                with store.writer(root,rel,private=True) as dst:
                    dst.write(npy.header(shape,desc['dtype']))
                    for donor in donors:
                        c.need(c.integer(donor) and donor<shape[0],'donor index full row membership')
                        src.seek(start+donor*rowbytes)
                        b=src.read(rowbytes);c.need(len(b)==rowbytes,'complete donor payload')
                        dst.write(b)
        out[name]=npy.describe(store,root,rel,shape,desc['dtype'])
    return out


def build_day(store,source_root,output,source,axis,environment,module_D,budget):
    g=source['geometry'];n=g['rows'];channels=len(axis)
    # Every ID is minted once under this preparation. It is not a reversible source hash.
    day_id=budget.call('mint opaque day identity',secrets.token_hex,16)
    ids=[budget.call('mint opaque row identity',secrets.token_hex,16) for _ in range(n)]
    c.need(len(ids)==len(set(ids)),'minted public identity collision')
    base='bank/'+day_id
    shapes={'x':([n,channels,5000],'<f8'),'mask':([n,channels,5000],'|b1'),
            'context':([n,6],'<f8'),'offsets':([n],'<f8')}
    array_paths={k:base+'/'+k+'.npy' for k in shapes}
    label_paths={k:'private/'+day_id+'/'+k+'.npy' for k in c.ENDPOINTS}
    audit_path='private/'+day_id+'/rows.jsonl'
    seen=set();cues=set();all_masked=0;row_count=0
    with open_day(store,source_root,source,axis,environment) as (native,np):
        with ExitStack() as stack:
            streams={k:stack.enter_context(npy.writer(store,output,array_paths[k],shape,dtype,private=True))
                     for k,(shape,dtype) in shapes.items()}
            labels={k:stack.enter_context(npy.writer(store,output,label_paths[k],[n],'<f8',private=True)) for k in c.ENDPOINTS}
            audit=stack.enter_context(store.writer(output,audit_path,private=True))
            for i in range(n):
                budget.progress_current={'person':source['person'],'day':source['day'],'entered_row':i,'total_rows':n}
                with budget.hold(channels*5000*72+262144,'complete epoch and all transient masks/conversion/copies'):
                    row=native.row(i)
                    c.need(row['id'] not in seen,'duplicate original reach ID; no row exclusion')
                    seen.add(row['id'])
                    c.need(row['start_time'] not in cues,'duplicate/ambiguous selected event cue; no row exclusion')
                    cues.add(row['start_time'])
                    w=window(row['start_time'],g['starting_time'],g['samples'])
                    x,mask,reasons=native.epoch(w,np)
                    empty=not bool(np.any(mask));all_masked+=int(empty)
                    streams['x'].write(x);streams['mask'].write(mask)
                    streams['context'].write(np.asarray([context(source['day'],row['start_time'])],dtype='<f8'))
                    streams['offsets'].write(np.asarray([w['offset']],dtype='<f8'))
                    for endpoint,column in c.ENDPOINTS.items():
                        labels[endpoint].write(np.asarray([row[column]],dtype='<f8'))
                    private={'row':i,'source_interval_id':row['id'],'public_id':ids[i],
                             'source_path':source['path'],'selected_table':'intervals/reaches','clock':w,
                             'availability':reasons,'all_masked':empty,'status':'complete','target_row':i}
                    body=c.canonical(private)+b'\n';c.need(len(body)<=budget.limits['metadata_bytes'],'single row audit cap')
                    audit.write(body);row_count+=1
                    budget.tick()
                    del x,mask,row,w,private,body
    c.need(row_count==n,'complete released row census')
    arrays={k:npy.describe(store,output,array_paths[k],shape,dtype) for k,(shape,dtype) in shapes.items()}
    labels={k:npy.describe(store,output,label_paths[k],[n],'<f8') for k in c.ENDPOINTS}
    d=donor_order(source['person'],source['day'],source['path'],n)
    # Context, labels and recipient IDs are unchanged. No donor map is actor-visible.
    disrupted=None
    if module_D and d['status'] in ('complete','empty'):
        disrupted=_permuted(store,output,arrays,d['donors'],'disrupted/'+day_id)
    result={'person':source['person'],'day':source['day'],'handle':day_id,'source':{'path':source['path'],'pin':source['pin']},
            'geometry':g,'axis':axis,'ids':ids,'rows':n,'status':'empty' if n==0 else 'complete',
            'arrays':arrays,'labels':labels,'row_audit':store.describe(output,audit_path),'all_masked_rows':all_masked,
            'assignment':d,'disrupted_arrays':disrupted}
    budget.tick();return result


def prepare_run(authority_path,authority_pin,inherited_context):
    budget=None;store=None;output=None;days=[]
    try:
        budget=inherited_context if type(inherited_context) is Budget else Budget(inherited_context);store=IO(budget)
        budget.reserve(authority_pin['bytes']*12+1048576,'authority and qualification retention before capture')
        a,source_root,selected_output,selection_pin=admit(authority_path,authority_pin,budget,store)
        budget.progress=[{'person':s['person'],'day':s['day'],'status':'unentered'} for s in a['sources']]
        for s in a['sources']:
            validate_geometry(s['geometry'],a['axes'][s['person']],budget)
        total_rows=sum(s['geometry']['rows'] for s in a['sources'])
        budget.add_rows(total_rows)
        c.need(budget.limits['source_files']>=55,'full55 sources prospective')
        # Includes nested header/profile metadata, ID sets, donor maps and final manifest.
        metadata_hold=budget.reserve(total_rows*2048+55*32768+authority_pin['bytes']*12,'complete persistent census/authority/day metadata')
        profile=store.json(Path(a['metadata_root']),a['environment']['memory_profile'])
        c.need(profile.get('schema')=='neural049_hdf5_memory_profile_v1' and c.integer(profile.get('native_workspace_bytes'),1)
               and profile.get('host_memory_enforcement')=='independently_qualified','actual qualified native metadata/codec workspace')
        native_hold=budget.reserve(profile['native_workspace_bytes'],'selected native HDF5/codec workspace')
        store.mkdir(selected_output);output=selected_output
        _json(store,output,'ATTEMPT.json',{'schema':'neural049_prepare_attempt_v1','authority':authority_pin,
              'selection':selection_pin,'origin':budget.origin,'deadline':budget.deadline,'status':'entered','costs':budget.record()})
        for index,s in enumerate(a['sources']):
            budget.source();budget.progress[index]['status']='entered_incomplete'
            day=build_day(store,source_root,output,s,a['axes'][s['person']],a['environment'],a['module_D'],budget)
            days.append(day);budget.progress[index]['status']=day['status']
        all_ids=[i for d in days for i in d['ids']]
        c.need(len(all_ids)==len(set(all_ids)) and len(days)==55,'all original rows unique and full55day completion')
        d_status=('not_selected' if not a['module_D'] else
                  'unsupported_singleton' if any(d['assignment']['status']=='unsupported_singleton' for d in days) else 'complete')
        manifest={'schema':'neural049_private_packet_v1','status':'complete_core_bank','source_selection':selection_pin,
                  'authority':authority_pin,'authority_descriptor':{'root':a['metadata_root'],'body':{'path':Path(authority_path).name,'pin':authority_pin}},
                  'source_closure':a['source_closure'],'roster':a['roster'],'environment':a['environment'],
                  'qualifications':a['qualifications'],'days':days,'people':sorted(a['axes']),
                  'source_count':55,'person_count':12,'rows':total_rows,'assignment_status':d_status,
                  'physical_immutability':'not established by construction; owner independent sealing/lifecycle required',
                  'costs':budget.record()}
        desc=_json(store,output,'PACKET.json',manifest)
        complete={'schema':'neural049_prepare_complete_v1','status':'complete_core_bank','manifest':desc,
                  'source_selection':selection_pin,'authority':authority_pin,'source_count':55,'person_count':12,
                  'rows':total_rows,'assignment_status':d_status,'costs_before_this_publication':budget.record(),
                  'actual_scientific_qualification':None}
        final=_json(store,output,'COMPLETE.json',complete)
        budget.release(native_hold);budget.release(metadata_hold);budget.tick()
        return {'root':str(output),'complete':final,'costs_after_publication_and_readback':budget.record(),
                'physical_immutability_qualified':False}
    except BaseException as exc:
        if store is None:
            raise OperationFailure(failure_record(exc,budget,'prepare_initial_admission')) from exc
        raise_failed(store,output,exc,'prepare_full55')

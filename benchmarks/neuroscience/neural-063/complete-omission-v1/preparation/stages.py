"""Concrete full-panel S00--S06 stage handlers, unexecuted during construction."""
from bisect import bisect_left
from collections import Counter, defaultdict
import hashlib
import hmac
import secrets
from owner.io import Artifact, ContractError, canonical
from owner.model import StageResult
from owner.scoring import hierarchy, training_scale
from . import algorithm as alg
from . import native, source, transport

CAP=1_500_000_000
SCHEMAS={'source_selection':'neural063_source_selection_v2','source_sizes':'neural063_source_sizes_v2',
         'source_inventory':'neural063_source_inventory_v2','native_metadata':'neural063_native_metadata_v2',
         'schedule_bank':'neural063_schedule_bank_v2','projected_rows':'neural063_projected_rows_v2',
         'projection_census':'neural063_projection_census_v2'}


def read(ctx,key):
    value=ctx.read_input(key,roles={key},cap=CAP)
    if value.get('schema')!=SCHEMAS[key]: raise ContractError('ancestor artifact schema mismatch: '+key)
    return value


def nested(ctx,value,role,schema):
    ref=Artifact.parse(value)
    if ref.visibility!='operator': raise ContractError('operator intermediate must remain private')
    result=ctx.store.read_json(ref,roles={role},cap=CAP)
    if result.get('schema')!=schema: raise ContractError('embedded authenticated artifact schema mismatch')
    return result


def put(ctx,key,value,role=None,visibility='operator'):
    return ctx.write_json(key+'.json',value,role=role or key,visibility=visibility)


def full_rows(selection):
    rows=selection['experiments']
    if (len(rows)!=1936 or len({r['ophys_experiment_id'] for r in rows})!=1936
            or len({r['mouse_id'] for r in rows})!=107 or len({r['ophys_session_id'] for r in rows})!=703
            or sum(len(r['rois']) for r in rows)!=133066):
        raise ContractError('full original source panel mandatory')
    return rows


def s00(ctx):
    value=source.selection(ctx)
    return {'source_selection':put(ctx,'source_selection',value)}


def s01(ctx):
    selection=read(ctx,'source_selection');full_rows(selection)
    return {'source_sizes':put(ctx,'source_sizes',transport.size_census(ctx,selection))}


def s02(ctx):
    selection=read(ctx,'source_selection');full_rows(selection)
    return {'source_inventory':put(ctx,'source_inventory',transport.acquire(ctx,selection,read(ctx,'source_sizes')))}


def inventory_map(ctx,selection):
    inventory=read(ctx,'source_inventory')
    if inventory['source_selection_sha256']!=ctx.inputs['source_selection'].sha256:
        raise ContractError('source inventory selection changed')
    files={r['experiment']:r for r in inventory['files']}
    if len(files)!=1936 or set(files)!={r['ophys_experiment_id'] for r in full_rows(selection)}:
        raise ContractError('all authenticated native objects required')
    if len({r['source']['sha256'] for r in files.values()})!=1936:
        raise ContractError('duplicate native source identities')
    return files


def s03(ctx):
    selection=read(ctx,'source_selection');files=inventory_map(ctx,selection);entries=[]
    for row in full_rows(selection):
        eid=row['ophys_experiment_id'];binding=files[eid]
        if binding['blake2b_512']!=row['blake2b_512'] or binding['version_id']!=row['version_id']:
            raise ContractError('native source provider identity mismatch')
        with native.opened(ctx,binding['source'],row['blake2b_512']) as file:
            _,metadata=native.neural_metadata(file,row)  # no data slice here
            records=native.presentations(file)
        value={'schema':'neural063_native_experiment_v2','experiment':eid,
               'session':row['ophys_session_id'],'mouse':row['mouse_id'],'split':row['split'],
               'source_sha256':binding['source']['sha256'],'neural_metadata':metadata,
               'presentations':records,'presentation_sha256':hashlib.sha256(canonical(records)).hexdigest(),
               'response_projection_performed':False}
        ref=put(ctx,'native_'+eid,value,role='native_experiment_metadata')
        entries.append({'experiment':eid,'metadata':ref.object()})
    result={'schema':SCHEMAS['native_metadata'],'entries':entries,'experiments':1936,
            'published_valid_rois':133066,'source_inventory_sha256':ctx.inputs['source_inventory'].sha256,
            'source_selection_sha256':ctx.inputs['source_selection'].sha256,'response_projection_performed':False}
    return {'native_metadata':put(ctx,'native_metadata',result)}


def native_bank(ctx,selection):
    bank=read(ctx,'native_metadata')
    if bank['source_selection_sha256']!=ctx.inputs['source_selection'].sha256:
        raise ContractError('native metadata selection binding mismatch')
    entries={e['experiment']:e['metadata'] for e in bank['entries']}
    if len(entries)!=1936 or set(entries)!={r['ophys_experiment_id'] for r in full_rows(selection)}:
        raise ContractError('full native metadata bank required')
    return entries


def s04(ctx):
    selection=read(ctx,'source_selection');entries=native_bank(ctx,selection)
    by_session=defaultdict(list)
    for row in full_rows(selection): by_session[row['ophys_session_id']].append(row)
    sessions=[];experiment_entries=[]
    for sid,rows in sorted(by_session.items()):
        planes={r['ophys_experiment_id']:nested(ctx,entries[r['ophys_experiment_id']],
                'native_experiment_metadata','neural063_native_experiment_v2') for r in rows}
        values=list(planes.values());records=values[0]['presentations']
        digest=hashlib.sha256(canonical(records)).hexdigest()
        for plane in values:
            if plane['session']!=sid or plane['presentation_sha256']!=digest or plane['presentations']!=records:
                raise ContractError('all-plane session presentation consensus failed before response projection')
        schedule=alg.schedule(records)
        session={'schema':'neural063_session_schedule_v2','session':sid,'presentation_sha256':digest,
                 'presentations':records,**schedule,'experiment_ids':sorted(planes)}
        session_ref=put(ctx,'session_'+sid,session,role='session_schedule')
        sessions.append({'session':sid,'schedule':session_ref.object()})
        for row in rows:
            eid=row['ophys_experiment_id'];metadata=planes[eid]['neural_metadata'];clock=metadata['clock']
            alg.validate_clock(clock)
            supported=[];unsupported=[]
            for k in schedule['selected']:
                event=records[k]
                try: spans=alg.native_bins(clock,event['start'])
                except alg.ClockUnsupported as exc:
                    unsupported.append({'key':event['key'],'reason':str(exc),'category':'clock_unsupported'})
                    continue
                supported.append({'key':event['key'],'presentation_index':k,'onset':event['start'],'spans':spans})
            privacy={'scope':'not_query','history_intervals':0,'held_target_intervals':0,'intersections':0}
            if row['split']=='query':
                histories=[[e['spans'][0][0],e['spans'][11][1]] for e in supported]
                # Project every shared scheduled target window onto THIS native
                # plane clock, including an event supported in another plane.
                # This covers cross-plane schedule availability without equating
                # unrelated frame indices between different clocks.
                targets=[[bisect_left(clock,records[k]['start']),bisect_left(clock,records[k]['start']+.6)]
                         for k in schedule['selected']]
                alg.intersections(histories,targets)
                privacy={'scope':'all_session_scheduled_targets_mapped_to_this_plane_clock',
                         'history_intervals':len(histories),'held_target_intervals':len(targets),'intersections':0}
            value={'schema':'neural063_experiment_support_v2','experiment':eid,'session':sid,'mouse':row['mouse_id'],
                   'split':row['split'],'native_metadata':entries[eid],'session_schedule':session_ref.object(),
                   'supported_events':supported,'clock_unsupported_events':unsupported,'privacy':privacy,
                   **{k:schedule[k] for k in ('original_omissions','timing_excluded','thinning_excluded','scheduled')},
                   'supported':len(supported),'clock_unsupported':len(unsupported)}
            if value['original_omissions']!=value['timing_excluded']+value['thinning_excluded']+value['scheduled'] or value['scheduled']!=value['supported']+value['clock_unsupported']:
                raise ContractError('disjoint complete omission census failed')
            ref=put(ctx,'support_'+eid,value,role='experiment_support')
            experiment_entries.append({'experiment':eid,'support':ref.object()})
    bank={'schema':SCHEMAS['schedule_bank'],'sessions':sessions,'experiments':experiment_entries,
          'native_metadata_sha256':ctx.inputs['native_metadata'].sha256,
          'source_selection_sha256':ctx.inputs['source_selection'].sha256,
          'schedule_before_response_projection':True}
    return {'schedule_bank':put(ctx,'schedule_bank',bank)}


def s05(ctx):
    selection=read(ctx,'source_selection');files=inventory_map(ctx,selection)
    bank=read(ctx,'schedule_bank')
    if bank['source_selection_sha256']!=ctx.inputs['source_selection'].sha256:
        raise ContractError('schedule source selection mismatch')
    supports={x['experiment']:x['support'] for x in bank['experiments']}
    if len(supports)!=1936 or set(supports)!=set(files) or len(bank['sessions'])!=703:
        raise ContractError('complete all-session all-experiment schedule required')
    projections=[];dispositions=[];supported_mice=set();case_count=0
    for row in full_rows(selection):
        eid=row['ophys_experiment_id'];s=nested(ctx,supports[eid],'experiment_support','neural063_experiment_support_v2')
        metadata=nested(ctx,s['native_metadata'],'native_experiment_metadata','neural063_native_experiment_v2')
        session=nested(ctx,s['session_schedule'],'session_schedule','neural063_session_schedule_v2')
        projected=[]
        with native.opened(ctx,files[eid]['source'],row['blake2b_512']) as file:
            dataset,current=native.neural_metadata(file,row)
            if current!=metadata['neural_metadata'] or native.presentations(file)!=session['presentations']:
                raise ContractError('same-source metadata changed since pre-response schedule')
            for event in s['supported_events']:
                history,target=alg.population(lambda a,b:dataset[a:b,:].tolist(),current['columns'],event['spans'])
                k=event['presentation_index'];onset=event['onset']
                previous=[{'image':p['image'],'omitted':p['omitted'],'start_relative_seconds':p['start']-onset}
                          for p in session['presentations'][k-3:k]]
                projected.append({'source_event':event['key'],'source_experiment':eid,'source_mouse':row['mouse_id'],
                                  'source_session':row['ophys_session_id'],'split':row['split'],'history':history,
                                  'target':target,'previous':previous,'context':row['context'],'spans':event['spans']})
        case_count+=len(projected)
        if case_count>1_000_000: raise ContractError('complete case bound exceeded; full-panel amendment required, no truncation')
        if len(projected)!=s['supported']: raise ContractError('projected event/support count mismatch')
        if projected: supported_mice.add(row['mouse_id'])
        p=put(ctx,'projection_'+eid,{'schema':'neural063_projection_experiment_v2','experiment':eid,'rows':projected},role='projection_experiment')
        projections.append({'experiment':eid,'rows':p.object()})
        dispositions.append({'experiment':eid,'mouse':row['mouse_id'],'session':row['ophys_session_id'],
                             'split':row['split'],'context':row['context'],'published_valid_rois':len(row['rois']),
                             **{k:s[k] for k in ('original_omissions','timing_excluded','thinning_excluded','scheduled','supported','clock_unsupported')},
                             'source_sha256':files[eid]['source']['sha256'],'native_metadata':s['native_metadata'],
                             'schedule':s['session_schedule'],'support':supports[eid],'projection':p.object(),
                             'disposition':'supported' if projected else 'no_supported_scheduled_omission',
                             'clock_unsupported_events':s['clock_unsupported_events'],'privacy':s['privacy']})
    census={'schema':SCHEMAS['projection_census'],'source_counts':alg.COUNTS,'experiments':dispositions,
            'supported_mice_by_split':dict(Counter(selection['mouse_assignments'][m] for m in supported_mice)),
            'missing_mouse_support':sorted(set(selection['mouse_assignments'])-supported_mice),
            'rows':case_count,'source_inventory_sha256':ctx.inputs['source_inventory'].sha256,
            'schedule_bank_sha256':ctx.inputs['schedule_bank'].sha256,'reference_gain':None}
    census_ref=put(ctx,'projection_census',census)
    if supported_mice!=set(selection['mouse_assignments']):
        raise ContractError('full107-mouse supported omission gate not established; full census retained')
    projected={'schema':SCHEMAS['projected_rows'],'experiments':projections,'rows':case_count,
               'source_selection_sha256':ctx.inputs['source_selection'].sha256,
               'projection_census_sha256':census_ref.sha256}
    return {'projected_rows':put(ctx,'projected_rows',projected),'projection_census':census_ref}


def alias(secret,kind,value):
    return kind+'_'+hmac.new(secret,(kind+':'+value).encode(),hashlib.sha256).hexdigest()


def s06(ctx):
    selection=read(ctx,'source_selection');full_rows(selection)
    projected=read(ctx,'projected_rows');census=read(ctx,'projection_census')
    if (projected['projection_census_sha256']!=ctx.inputs['projection_census'].sha256
            or projected['source_selection_sha256']!=ctx.inputs['source_selection'].sha256
            or census['source_counts']!=alg.COUNTS or census['supported_mice_by_split']!=alg.SPLITS
            or census['missing_mouse_support'] or len(census['experiments'])!=1936):
        raise ContractError('complete source/projected support binding required')
    secret=secrets.token_bytes(32);rows=[];joins=[];seen=set();source_map={r['ophys_experiment_id']:r for r in selection['experiments']}
    if len(projected['experiments'])!=1936 or {e['experiment'] for e in projected['experiments']}!=set(source_map):
        raise ContractError('complete projection shards required')
    for entry in projected['experiments']:
        data=nested(ctx,entry['rows'],'projection_experiment','neural063_projection_experiment_v2')
        eid=entry['experiment'];original=source_map[eid]
        if data['experiment']!=eid: raise ContractError('projection identity mismatch')
        for raw in data['rows']:
            if (raw['source_experiment']!=eid or raw['source_mouse']!=original['mouse_id']
                    or raw['source_session']!=original['ophys_session_id'] or raw['split']!=original['split']):
                raise ContractError('projection hierarchy mismatch')
            source_key=eid+':'+raw['source_event']
            if source_key in seen: raise ContractError('duplicate native event identity')
            seen.add(source_key)
            row={'id':alias(secret,'event',source_key),'mouse':alias(secret,'mouse',raw['source_mouse']),
                 'session':alias(secret,'session',raw['source_session']),'experiment':alias(secret,'experiment',eid),
                 'split':raw['split'],'history':raw['history'],'previous':raw['previous'],
                 'context':raw['context'],'target':raw['target']}
            if len(row['history'])!=12 or row['history'][11]!=0 or len(row['target'])!=3:
                raise ContractError('exact original endpoint required')
            for v in row['history']+row['target']: alg.number(v)
            rows.append(row);joins.append({'id':row['id'],'source_event':raw['source_event'],
                                          'source_experiment':eid,'source_session':raw['source_session'],
                                          'source_mouse':raw['source_mouse'],'native_spans':raw['spans']})
    rows.sort(key=lambda x:x['id']);joins.sort(key=lambda x:x['id'])
    if len(rows)!=projected['rows'] or len({r['id'] for r in rows})!=len(rows) or len(rows)>1_000_000:
        raise ContractError('complete unique opaque row index required')
    groups={split:[r for r in rows if r['split']==split] for split in alg.SPLITS}
    for split,expected in alg.SPLITS.items(): hierarchy(groups[split],expected)
    sd=training_scale(groups['fit'])
    outputs={}
    for split in ('fit','validation'):
        value={'schema':'neural063_rows_v2','split':split,'rows':[alg.view(r,'N',True) for r in groups[split]]}
        key='fit_rows' if split=='fit' else 'validation_rows'
        outputs[key]=put(ctx,key,value,visibility='operator')
        # Candidate development mounts use explicit independently serialized
        # T/N files; references use operator FIT/VAL N envelopes above.
        for information in ('T','N'):
            key=split+'_'+information
            outputs[key]=put(ctx,key,{'schema':'neural063_rows_v2','split':split,
                            'rows':[alg.view(r,information,True) for r in groups[split]]},visibility='development')
    outputs['fit_scale']=put(ctx,'fit_scale',{'schema':'neural063_fit_scale_v2','training_target_sd':sd,
                         'fit_mice':73,'fit_rows_sha256':outputs['fit_rows'].sha256})
    query=groups['query'];ids=[r['id'] for r in query]
    outputs['query_index']=put(ctx,'query_index',{'schema':'neural063_query_index_v2','ids':ids,
                              'target_shape':[3],'heldout_mouse_count':19},visibility='candidate')
    for information in ('T','N'):
        key='query_'+information
        outputs[key]=put(ctx,key,{'schema':'neural063_rows_v2','split':'query',
                                 'rows':[alg.view(r,information,False) for r in query]},visibility='operator')
    # Whole-panel query files are operator-only. Runtime must mount only the
    # individual event view; no candidate ever mounts a complete query bank.
    targets=[{k:r[k] for k in ('id','mouse','session','experiment','split','target','context','previous')} for r in query]
    outputs['query_targets']=put(ctx,'query_targets',{'schema':'neural063_query_targets_v2','rows':targets,
                                 'query_index_sha256':outputs['query_index'].sha256,
                                 'fit_scale_sha256':outputs['fit_scale'].sha256})
    public_census={**census,'schema':'neural063_support_census_v2',
                   'fit_scale_sha256':outputs['fit_scale'].sha256,'query_index_sha256':outputs['query_index'].sha256}
    outputs['support_census']=put(ctx,'support_census',public_census)
    outputs['private_lineage']=put(ctx,'private_lineage',{'schema':'neural063_private_lineage_v2','joins':joins,
                                  'source_selection_sha256':ctx.inputs['source_selection'].sha256,
                                  'projection_census_sha256':ctx.inputs['projection_census'].sha256,
                                  'query_index_sha256':outputs['query_index'].sha256})
    outputs['packet_binding']=put(ctx,'packet_binding',{'schema':'neural063_packet_binding_v2',
                                 'artifacts':{k:v.object() for k,v in outputs.items()},
                                 'endpoint':{'history_bins':12,'target_bins':3,'bin_seconds':.2,
                                             'baseline':'own_final_pre_bin','history_final_bin':0},
                                 'source_counts':alg.COUNTS,'supported_mice_by_split':alg.SPLITS})
    packet_bytes=sum(a.bytes for a in outputs.values())
    if packet_bytes>CAP: raise ContractError('complete packet byte bound exceeded; no view/event truncation')
    return outputs


HANDLERS={'S00':s00,'S01':s01,'S02':s02,'S03':s03,'S04':s04,'S05':s05,'S06':s06}


def run(stage,ctx):
    ctx.require_scientific()  # before any actual source, metadata or response access
    if stage not in HANDLERS or ctx.stage!=stage: raise ContractError('wrong preparation stage')
    try:
        outputs=HANDLERS[stage](ctx)
        # All dynamic metadata, transport attempts and acquired objects remain
        # listed in addition to principal keys; failures are never overwritten.
        extra={k:v for k,v in ctx.written.items() if v not in outputs.values()}
        return StageResult('complete',{**outputs,**extra},measurements=ctx.store.meter.snapshot())
    except Exception as exc:
        record={'schema':'neural063_preparation_failure_v2','stage':stage,'failure_class':type(exc).__name__,
                'reason':str(exc)[:4096],'scope_unchanged':alg.COUNTS,'costs':ctx.store.meter.snapshot(),
                'partial_artifacts':{k:v.object() for k,v in ctx.written.items()},
                'dependent_stages':'not_executed_due_to_failed_prerequisite','reference_gain':None}
        failure=put(ctx,'preparation_failure',record,role='preparation_failure')
        return StageResult('failed',{**ctx.written,'preparation_failure':failure},
                           measurements=ctx.store.meter.snapshot(),reasons=[record['reason']])

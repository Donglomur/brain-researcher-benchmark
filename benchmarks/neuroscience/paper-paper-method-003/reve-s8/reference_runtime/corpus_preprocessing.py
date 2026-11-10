"""Registered full-session corpus preparation; no operator-normalized shard shortcut."""
from .catalog import need,identity,canonical

def corpus_recipe(io,c):
    r=io.r['payload']['corpus_preprocessing']
    keys={'schema','expected_source_ids','source_inventory','pretraining_exclusion_qualification','geometry_qualification','recordings','excluded_sources','max_windows','chunk_rows','max_recording_bytes'}
    need(set(r)==keys and r['schema']=='reve-full-session-corpus-preparation-v1','closed corpus preparation recipe')
    need(len(r['expected_source_ids'])==len(set(r['expected_source_ids']))==92,'all 92 original corpus source slots')
    need(r['source_inventory'] and r['pretraining_exclusion_qualification'] and r['geometry_qualification']==c['geometry_qualification'],'qualified corpus source/exclusion/geometry identities')
    need(all(type(r[k])is int and r[k]>0 for k in ('max_windows','chunk_rows','max_recording_bytes')),'finite selected corpus construction bounds')
    need(r['chunk_rows']<=r['max_windows'],'bounded output shards')
    ids=set();sources=set();planned=0
    for rec in r['recordings']:
        need(set(rec)=={'id','source_id','recording','sampling_hz','unit','session_bounds','positions','channel_ids','support','people'},'closed complete session recording')
        need(rec['id'] not in ids and rec['source_id'] in r['expected_source_ids'] and rec['support'],'unique qualified recording');ids.add(rec['id']);sources.add(rec['source_id'])
        need(type(rec['sampling_hz'])in (int,float) and rec['sampling_hz']>199 and rec['unit'] in ('V','mV','uV'),'physical recording scale supported by the retained preparation method')
        need(rec['session_bounds'] and len(rec['people'])==len(rec['session_bounds']) and all(rec['people']),'session/biological support alignment')
        need(rec['channel_ids'] and len(rec['channel_ids'])==len(set(map(str,rec['channel_ids']))),'ordered unique source channels')
        need(len(rec['channel_ids'])>(6 if c['purpose']=='R-native' else 0),'original native channel eligibility')
        cursor=0
        for start,stop in rec['session_bounds']:
            need(type(start)is type(stop)is int and start==cursor<stop,'complete nonoverlapping full-session partition');cursor=stop
            planned+=int((stop-start)*200/rec['sampling_hz'])//2000
        need(rec['recording'] in io.manifest and io.manifest[rec['recording']]['bytes']<=r['max_recording_bytes'],'recording read bounded before array access')
    excluded=set()
    for row in r['excluded_sources']:
        need(set(row)=={'source_id','reason','evidence','eligible_windows'} and row['source_id'] in r['expected_source_ids'] and row['source_id'] not in excluded and row['reason'] and row['evidence'] and row['eligible_windows']==0,'qualified zero-window exclusion')
        excluded.add(row['source_id'])
    need(sources.isdisjoint(excluded) and sources|excluded==set(r['expected_source_ids']),'all source slots have actual recording or qualified exclusion')
    need(planned<=r['max_windows'],'whole selected corpus window cap before reads')
    need(len(io.r['expected_outputs'])==1 and next(iter(io.r['expected_outputs'].values()))['kind']=='preprocessing','one owned corpus preprocessing product')
    return r

def prepare_corpus(io,c):
    r=corpus_recipe(io,c)
    import numpy as np
    from .preprocessing import corpus_windows
    name=next(iter(io.r['expected_outputs']));chunks=[];normalization=[];geometries=[];objects=[];raw_support=[];all_events=[];counts={k:0 for k in r['expected_source_ids']}
    for index,rec in enumerate(r['recordings']):
        # This reserves the selected worst case before loading/filtering a full
        # session; native process memory accounting remains independently required.
        channels=len(rec['channel_ids']);rows=sum(int((b-a)*200/rec['sampling_hz'])//2000 for a,b in rec['session_bounds'])
        need(3*rows*channels*2000*4+8*r['max_recording_bytes']<=io.r['resource_limits']['memory_bytes'],'full-session producer working-set reservation')
        x=io.array(rec['recording']);pos=io.array(rec['positions'])
        need(x.ndim==2 and x.shape[0]==channels and x.shape[-1]==rec['session_bounds'][-1][1] and pos.shape==(channels,3),'actual full recording/channel/geometry support')
        windows,records=corpus_windows(x,rec['sampling_hz'],rec['unit'],rec['session_bounds'])
        events=[];people=[]
        for row in records:
            starts=row.get('starts_200Hz',[])
            events.extend(identity({'recording':rec['id'],'source':rec['source_id'],'session':row['session'],'start_200Hz':a}) for a in starts)
            people.extend([rec['people'][row['session']]]*len(starts))
        need(len(windows)==len(events)==rows,'actual window count matches complete session partition')
        counts[rec['source_id']]+=len(windows);raw_support.append(rec['support'])
        normalization.append({'recording':rec['id'],'source_id':rec['source_id'],'raw_support':rec['support'],'session_bounds':rec['session_bounds'],'sampling_hz':rec['sampling_hz'],'input_unit':rec['unit'],'records':records})
        if windows:
            geo=io.write_array(f'{name}.recording{index}.positions.npy',pos);objects.append(geo);geometries.append(pos)
            for start in range(0,len(windows),r['chunk_rows']):
                batch=windows[start:start+r['chunk_rows']];prefix=f'{name}.recording{index}.chunk{start}'
                signal=io.write_array(prefix+'.npy',np.stack(batch));objects.append(signal)
                support={'raw':rec['support'],'recording':rec['id'],'source_id':rec['source_id'],'events':events[start:start+len(batch)]}
                chunks.append({'prefix':prefix,'source_id':rec['source_id'],'rows':len(batch),'channels':channels,'signal':signal,'positions':geo,'events':support['events'],'people':people[start:start+len(batch)],'support':identity(support),'channel_ids':rec['channel_ids']})
            all_events.extend(events)
        del x,pos,windows
    need(chunks and len(all_events)==len(set(all_events)),'nonempty nonduplicated normalized corpus windows')
    stats=io.write(name+'.normalization.json',canonical({'schema':'reve-full-session-normalization-v1','records':normalization}));objects.append(stats)
    exclusions=list(r['excluded_sources'])
    represented={x['source_id'] for x in chunks}
    for source in {x['source_id'] for x in r['recordings']}-represented:
        exclusions.append({'source_id':source,'reason':'all_authorized_sessions_shorter_than_10_seconds','evidence':identity({'source':source,'actual_normalization':stats}),'eligible_windows':0})
    normalization_id=identity({'producer':identity(io.r),'statistics':stats,'recipe':'S7-corpus_windows-session-zscore-clipped15'})
    corpus_id=identity({'source_inventory':r['source_inventory'],'sources':r['expected_source_ids'],'exclusions':exclusions,'normalization':normalization_id,'chunks':chunks})
    geometry=io.write_array(name+'.geometry.npy',np.concatenate(geometries,axis=0));objects.append(geometry)
    census=[]
    for chunk in chunks:
        view={'schema':'reve-fixed-array-view-v1','role':'pretrain','dataset':'REVE-92-source-corpus','sampling_hz':200,'unit':'session_zscore_clipped15','signals':chunk['signal']['path'],'labels':None,'events':chunk['events'],'people':chunk['people'],'positions':chunk['positions']['path'],'channel_ids':chunk['channel_ids'],'support':chunk['support'],'geometry_qualification':r['geometry_qualification'],'corpus_identity':corpus_id,'normalization_qualification':normalization_id,'pretraining_exclusion_qualification':r['pretraining_exclusion_qualification']}
        v=io.write(chunk['prefix']+'.view.json',canonical(view));objects.append(v)
        census.append({'view':v['path'],'rows':chunk['rows'],'channels':chunk['channels'],'source_ids':[chunk['source_id']],'events_identity':identity(chunk['events'])})
    manifest={'schema':'reve-corpus-buckets-v1','dataset':'REVE-92-source-corpus','unit':'session_zscore_clipped15','sampling_hz':200,'source_inventory':r['source_inventory'],'expected_source_ids':r['expected_source_ids'],'pretraining_exclusion_qualification':r['pretraining_exclusion_qualification'],'geometry_qualification':r['geometry_qualification'],'normalization_qualification':normalization_id,'chunks':census,'geometry_dictionary':geometry['path'],'corpus_identity':corpus_id,'excluded_sources':exclusions}
    bucket=io.write(name+'.corpus.json',canonical(manifest));objects.append(bucket)
    io.emit(name,{'raw_support':raw_support,'epoch_support':all_events,'unit_projection':{'physical':'session_zscore_clipped15','sampling_hz':200,'corpus':bucket},'clock_mapping':[{'recording':x['recording'],'session_bounds':x['session_bounds']} for x in normalization],'fitted_dependencies':raw_support,'recipe':{'id':'S8-registered-full-session-corpus-v1','kind':'full_session_corpus','historical_qualified':False,'method':'existing_S7_corpus_windows','normalization_identity':normalization_id},'state':{'normalization':stats},'exclusions':exclusions},objects)


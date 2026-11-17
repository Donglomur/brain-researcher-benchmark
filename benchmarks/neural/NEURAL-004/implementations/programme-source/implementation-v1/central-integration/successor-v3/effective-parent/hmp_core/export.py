"""Explicit private-to-tool schema, not a generic object/attribute exporter.

Owner remaps and sorts every person/trial roster before candidate delivery.
No raw EEG, cross-correlation, targets, original paths or xarray metadata enter
the nested state payloads. The returned top-level private joins stay operator-only.
"""
import json
import math
from pathlib import Path
from .binding import EXPECTED_BINDING
from .schedule import PEOPLE, COUNTS, need
from .storage import Session, load_array


def _pin(d):
    return None if d is None else {k:d[k]for k in('bytes','sha256')}


def _json(session,root,d):
    need(type(d)is dict and Path(d['name']).name==d['name']and d['name']not in('.','..'),'single selected artifact name')
    need(d['bytes']<=session.limits['metadata_bytes'],'bounded JSON artifact')
    return json.loads(session.read(root/d['name'],d))


def _open(index,limits,context):
    session=Session(limits,context);root=Path(index['output_root'])
    need(root.is_absolute(),'absolute private retained root')
    doc=_json(session,root,index['index']);need(doc['schema']=='neural004_complete_hmp_index_v1'and doc['source']==EXPECTED_BINDING and doc['people']==list(PEOPLE),'complete source index identity')
    admission=_json(session,root,doc['admission'])
    need(admission['dataset_pin']==doc['dataset_pin']and admission['source_binding']==EXPECTED_BINDING,'retained admission lineage')
    return session,root,doc,admission


def _number(x):
    value=float(x)
    return value if math.isfinite(value)else None


def _array(session,root,descriptor):
    arr=load_array(session,root,descriptor)
    session.response(int(arr.size)*40+1024,int(arr.nbytes))
    # Fixed numerical axes and units only. Filenames and producer paths are absent.
    return {'dtype':descriptor['dtype'],'shape':descriptor['shape'],'axes':descriptor['axes'],'unit':descriptor['unit'],
            'values':[_number(x)for x in arr.reshape(-1)],'nonfinite':not bool(__import__('numpy').isfinite(arr).all())}


def export_private_tool(index,held,limits,inherited_context):
    import numpy as np
    need(held in PEOPLE,'one exact outer person')
    session,root,doc,admission=_open(index,limits,inherited_context)
    pca=None;norms={};out={'schema':'neural004_private_hmp_tool_v1','models':[],'evaluations':[]}
    if held in doc['pca']:
        pca=_json(session,root,doc['pca'][held]);nr=_json(session,root,pca['normalization'])
        for support in('train','held'):
            norms[support]={(x['person'],x['epoch']):{'centering':x['centering'],'components':x['components']}for x in nr[support]}
    for k in COUNTS:
        sd=doc['models'][f'{held}/{k}'];state=_json(session,root,sd)
        need(state['held']==held and state['events']==k and state['dataset_pin']==admission['dataset_pin']and state['source_binding']==EXPECTED_BINDING,'exact per-count state lineage')
        row={'events':k,'state_pin':_pin(sd),'pca':None,'normalization':{'centering':'per-trial/channel nanmean of retained samples','component_zscore':'per-person/component non-NaN population mean and SD; held person is retrospective/transductive','normalization_arrays':'attached to each keyed evaluation row'},
             'channel_parameters':None,'duration_parameters':None,'grouping':None,'template':None,'em_trace':[],
             'stop':state.get('stop'),'source_pin':EXPECTED_BINDING,'training_people':[p for p in PEOPLE if p!=held],
             'status':state['status'],'failure':state['failure']}
        if pca is not None:
            row['pca']={'weights':_array(session,root,pca['weights']),'state':{n:_array(session,root,d)for n,d in pca['state'].items()},'components':15,'channel_order':pca['channel_order']}
            row['template']=_array(session,root,pca['pattern'])
        if state['arrays']:
            row['channel_parameters']=_array(session,root,state['arrays']['channel_pars'])
            row['duration_parameters']=_array(session,root,state['arrays']['time_pars'])
            row['grouping']={'dictionary':state['grouping']['dictionary'],'channel_map':_array(session,root,state['arrays']['channel_map']),
                             'time_map':_array(session,root,state['arrays']['time_map']),'location_samples':state['grouping']['location_samples']}
        for step in state['history']:
            row['em_trace'].append({'iteration':step['iteration'],**{n:_array(session,root,step[n])for n in('likelihood','channel','time')}})
        out['models'].append(row)
        session.response(4096)
        for support in('train','held'):
            pair=_json(session,root,doc['pairs'][f'{held}/{k}/{support}']);deltas={}
            if pair['status']=='complete':
                for group in pair['groups']:
                    values=load_array(session,root,group['delta'])
                    need(len(values)==len(group['members']),'one delta per original group member')
                    for identity,value in zip(group['members'],values):deltas[tuple(identity)]=_number(value)
            for gain in('ordinary','zero'):
                ed=doc['evaluations'][f'{held}/{k}/{support}/{gain}'];evaluation=_json(session,root,ed)
                need(evaluation['state']==sd and evaluation['held']==held and evaluation['events']==k and evaluation['support']==support and evaluation['gain']==gain,'complete exact evaluation-state identity')
                trial_payload={};groups=[]
                for group in evaluation['groups']:
                    arrays={n:load_array(session,root,d)for n,d in group['arrays'].items()}
                    session.response(1024+len(group['members'])*128,sum(int(a.nbytes)for a in arrays.values()))
                    groups.append({'id':group['id'],'M':group['M'],'location':False,'members':group['members'],'scalar_total':group['scalar_total'],
                                   'pmf_normalizers':[_number(v)for v in arrays['pmf_normalizers']],'status':group['status']})
                    for i,identity in enumerate(group['members']):
                        trial_payload[tuple(identity)]={'marginals':arrays['marginals'][i],'log_mass':_number(arrays['log_masses'][i]),
                            'event_normalizers':[_number(v)for v in arrays['event_normalizers'][i]],'group':group['id'],
                            'normalizer_status':{'finite_positive':group['positive_finite_normalizers'],'source_clipping':'unchanged source np.clip(0,None)'},'status':group['status']}
                timing={}
                if 'times_ms'in evaluation:
                    times=load_array(session,root,evaluation['times_ms']);intervals=load_array(session,root,evaluation['intervals_ms'])
                    sums=load_array(session,root,evaluation['sums_ms'])if k==5 else None
                    for i,identity in enumerate(evaluation['timing_rows']):timing[tuple(identity)]=(times[i],intervals[i],None if sums is None else sums[i])
                wanted=[held]if support=='held'else[p for p in PEOPLE if p!=held];rows=[]
                expected=[[p,r['epoch']]for p in wanted for r in admission['rows'][p]]
                need(evaluation['rows']==expected,'complete failed-or-valid evaluation roster')
                if not groups:
                    groups=[{'id':0,'M':max(r['sample_count']for p in wanted for r in admission['rows'][p]),'location':False,
                             'members':expected,'scalar_total':None,'pmf_normalizers':None,'status':evaluation['status']}]
                for person in wanted:
                    for original in admission['rows'][person]:
                        ident=(person,original['epoch']);payload=trial_payload.get(ident);tim=timing.get(ident);n=original['sample_count']
                        record={'person':person,'epoch':original['epoch'],'samples':n,'marginals':None,'times_ms':None,'intervals_ms':None,'sums_ms':None,
                                'endpoint_ms':None,'log_mass':None,'log_mass_delta_ordinary_minus_zero':deltas.get(ident),'event_normalizers':None,
                                'normalization':norms.get(support,{}).get(ident),'group':0,'normalizer_status':None,'status':evaluation['status'],'failure':evaluation['failure']}
                        if payload is not None:
                            arr=payload.pop('marginals');need(arr.shape[0]>=n and arr.shape[1]==k,'complete original sample/event support')
                            session.response(n*k*40+4096,int(arr.nbytes))
                            record.update(payload);record['marginals']={'shape':[n,k],'axes':['sample','event'],'dtype':'float64','values':[_number(v)for v in arr[:n].reshape(-1)]}
                        if tim is not None:
                            record['times_ms']=[_number(v)for v in tim[0][:-1]];record['endpoint_ms']=_number(tim[0][-1]);record['intervals_ms']=[_number(v)for v in tim[1]]
                            record['sums_ms']=None if tim[2]is None else[_number(v)for v in tim[2]]
                            if any(v is None for v in record['times_ms']+record['intervals_ms']):record.update(status='undefined_timing',failure='source_group_zero_mode_or_nonfinite_timing')
                        if payload is None:session.response(4096)
                        rows.append(record)
                out['evaluations'].append({'events':k,'support':'training'if support=='train'else'held','gain':gain,'state_pin':_pin(sd),'groups':groups,'rows':rows,
                    'normalization_state':{'rule':'per-keyed-row source centering and per-person/component moments','held_transductive':support=='held','sfreq':512,'offset':admission['offset']},
                    'source_pin':EXPECTED_BINDING,'status':evaluation['status'],'failure':evaluation['failure']})
    session.tick();return out


def export_spatial_indices(index,limits,inherited_context):
    import numpy as np
    session,root,doc,admission=_open(index,limits,inherited_context);people={}
    for held in PEOPLE:
        d=doc['evaluations'][f'{held}/5/held/ordinary'];evaluation=_json(session,root,d);observed={}
        for group in evaluation['groups']:
            if group['status']!='complete':continue
            arr=load_array(session,root,group['arrays']['marginals'])
            # Exact max marginal source: NaN filled0, first argmax; source marks
            # an event undefined when its group's mean mode is sample0.
            modes=np.nan_to_num(arr,nan=0).argmax(axis=1);undefined=(modes.astype('float32').mean(axis=0)==0)
            for identity,values in zip(group['members'],modes):
                observed[tuple(identity)]=[None if undefined[j]else int(values[j])for j in range(5)]
        rows=[]
        for row in admission['rows'][held]:
            values=observed.get((held,row['epoch']));valid=values is not None and all(v is not None and 0<=v<row['sample_count']for v in values)
            rows.append({'epoch':row['epoch'],'samples':row['sample_count'],'indices':values,'status':'complete'if valid else'undefined_or_failed',
                         'failure':None if valid else evaluation['failure']or'source_group_zero_mode','evaluation_pin':_pin(d),'state_pin':_pin(evaluation['state'])})
            session.response(1024)
        people[held]=rows
    session.tick();return {'schema':'neural004_private_spatial_indices_v1','people':people,'source_pin':EXPECTED_BINDING,
        'interpretation':'Same-observation ordinary5-event max-marginal alignment, not independent biological validation; no extra HMP evaluation.'}

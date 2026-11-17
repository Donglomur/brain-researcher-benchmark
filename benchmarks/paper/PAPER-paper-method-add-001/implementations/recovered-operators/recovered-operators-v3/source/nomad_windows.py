"""Evaluator-owned T11 windows derived only after the full local archive barrier.

The physical NWB reader is concrete; no event/score callback is accepted. Unknown
original event, calibration, boundary, early-acquisition or tail facts refuse.
"""
from .nomad_math import need,closed,finite,identity,array_identity,seal_array,numpy_for
from .nomad_nwb import read_physical_fields,physical_trial_rows
from .nomad_t11 import complete_sequences,derive_recenter_intervals,intended_reach,METHODS


class T11Windows:
    def __init__(self,archive,captured,catalog,selection_name,budget):
        # No protected catalog method may run until all checks in this section
        # succeed. These are actual arrays and source-owned completed seals.
        need(archive.get('schema')=='nomad_complete_local_archive_v2', 'actual completed local archive')
        closure=archive.get('t11_logical_closure')
        need(type(closure) is dict and closure.get('logical_prediction_barrier')=='complete',
             'complete two-session prediction barrier before protected evaluation reads')
        self.sessions={r['session_id'] for r in closure['calibration_bindings']}
        need(len(self.sessions)==2 and len(closure['calibration_bindings'])==8,'both sessions/all calibration uses')
        rows={sp['product_id']:(r,sp,a,l) for r,sp,a,l in captured}
        need(len(rows)==len(captured) and set(rows)==set(archive['expected_product_ids']), 'complete expected captured membership')
        self.bindings={};self.by_slot={};self.full_ids={};self.budget=budget;self.catalog=catalog
        for r in closure['calibration_bindings']+closure['prediction_bindings']:
            key=(r['session_id'],r['block_id'],r['method']);need(key not in self.bindings,'unique full chronological slot')
            self.bindings[key]=r
        expected=8+closure['roster']['postcalibration_slot_count']
        need(len(self.bindings)==expected,'every full calibration/first/post slot')
        for row,sp,a,lineage in captured:
            if sp['task'] not in self.sessions:continue
            key=(sp['task'],sp['query_id'],sp['method']);need(key in self.bindings and key not in self.by_slot,'every graded T11 slot has one seal')
            binding=self.bindings[key];self.by_slot[key]=(row,sp,a,lineage)
            if row['status']=='complete':
                need(binding['status']=='complete' and array_identity(a)==binding['pin'], 'unchanged full-block values before protected reads')
            else:need(binding['status']=='failed' and row['failure_descriptor']['sha256']==binding['pin']['failure_evidence']['prefix_pin'], 'same retained failed attempt')
            block=key[:2]
            if block not in self.full_ids:self.full_ids[block]=list(sp['sample_ids'])
            need(self.full_ids[block]==sp['sample_ids'],'all four methods share complete full-block row identities')
        need(set(self.by_slot)==set(self.bindings),'no omitted full-block or calibration slot before protected reads')
        self.block_support={}
        for r in closure['block_support_bindings']:
            key=(r['session_id'],r['block_id']);need(key not in self.block_support,'unique complete block clock binding')
            self.block_support[key]=r
        need(set(self.block_support)==set(self.full_ids),'all public full-block supports sealed')
        self.closure=closure;self.windows={};self.sources={}
        # First protected read is strictly after the complete local barrier.
        selection=catalog.document(selection_name)
        closed(selection,['schema','physical_sessions','window_policy','source_pin'],'closed protected evaluator selection')
        need(selection['schema']=='nomad_t11_evaluator_selection_v3' and selection['source_pin'], 'explicit selected evaluator semantics')
        policy=selection['window_policy']
        closed(policy,['maximum_seconds','boundary'],'complete source-selected window convention')
        need(policy['maximum_seconds']==0.6 and policy['boundary'] in ('closed','right_open'),'original600ms cap and explicitly selected sample boundary')
        selected=selection['physical_sessions'];need(type(selected) is list and len(selected)==2,'both complete physical sessions')
        seen=set()
        for row in selected:
            closed(row,['nwb','physical_schema','trial_identity_selection','event_profile','sequence_profile',
                        'target_profiles','calibration_eligibility','event_trial_map'],'complete protected physical/evaluation source')
            schema=catalog.document(row['physical_schema']);mapping=catalog.document(row['trial_identity_selection'])
            physical=read_physical_fields(catalog,row['nwb'],schema,budget)
            trial_data=physical_trial_rows(physical,mapping);sid=physical['session_id']
            need(sid in self.sessions and sid not in seen,'exact independently expected physical session');seen.add(sid)
            events=catalog.document(row['event_profile']);seq_profile=catalog.document(row['sequence_profile'])
            targets=catalog.document(row['target_profiles']);cal_policy=catalog.document(row['calibration_eligibility'])
            event_map=catalog.document(row['event_trial_map'])
            closed(targets,['calibration','evaluation'],'separate explicit calibration/evaluation target profiles')
            for tp in targets.values():
                closed(tp,['component','axis_ids','axis_units','coordinate_fields','reach_profile'],'complete target coordinate/quantity profile')
                need(tp['component'] in ('position','velocity') and tp['coordinate_fields']==['tgt_x','tgt_y'],
                     'explicit physical target coordinates and prediction quantity')
                need(tp['axis_ids']==closure['axes'] and tp['axis_units']==closure['units'], 'selected target axes/units match sealed predictions')
            closed(cal_policy,['rule','success_value','source_pin'],'unresolved calibration eligibility cannot be inferred from Simon sequences')
            need(cal_policy['rule']=='successful_physical_calibration_movements' and cal_policy['source_pin'], 'explicit original calibration eligibility profile required')
            cal=trial_data['offline_calibration_mapping'];cal_block=cal['calibration_blocks'][0]
            evaluation=cal['evaluation_blocks']
            actual_order=[]
            for r in closure['roster']['slots']:
                if r['session_id']==sid and r['block_id'] not in actual_order:actual_order.append(r['block_id'])
            expected_cal={r['block_id'] for r in closure['calibration_bindings'] if r['session_id']==sid}
            need(expected_cal=={cal_block} and actual_order==evaluation,'actual applied flags match all sealed calibration/evaluation blocks')
            trials=trial_data['trial_rows'];post={k:v for k,v in trials.items() if v['block_id'] in evaluation}
            need(set(seq_profile['trial_ids'])==set(post),'all actual evaluation movements in sequence eligibility')
            members={}
            for name,ids in trial_data['sequence_members'].items():
                need(ids and all(t in trials for t in ids),'source sequence members exist')
                in_post=[t in post for t in ids];need(all(in_post) or not any(in_post),'no sequence crosses calibration/evaluation roles')
                if all(in_post):members[name]=ids
            eligibility=complete_sequences(post,members,seq_profile)
            allowed={t for r in eligibility['sequences'].values() if r['eligible'] for t in r['trial_ids']}
            allowed.update(t for t,r in trials.items() if r['block_id']==cal_block and r['result']==cal_policy['success_value'])
            need(type(event_map) is dict and set(event_map)=={cal_block,*evaluation}, 'all blocks have complete detected-event source mapping')
            f=physical['fields'];codes=f['acquisition/block_num'];need(codes.ndim==1,'one actual physical block per sample')
            ids=mapping['trial_ids'];physical_trial_index={tid:i for i,tid in enumerate(ids)}
            for block in [cal_block]+evaluation:
                global_rows=[]
                for i,v in enumerate(codes):
                    code=str(v.item());need(code in mapping['block_labels'],'all physical neural block codes resolved')
                    if mapping['block_labels'][code]==block:global_rows.append(i)
                key=(sid,block);sealed=self.block_support[key]
                times=[float(f['timestamps'][i]) for i in global_rows]
                need(times==sealed['timestamps'] and len(times)==len(self.full_ids[key]),'complete physical clock equals sealed full-block rows')
                np=numpy_for(events);self.np=np
                budget.reserve('T11.evaluator.physical_block',{'neural_index_and_cast':2*len(global_rows)*f['acquisition/binned_spikes'].shape[1],
                    'cursor_index_and_cast':2*len(global_rows)*f['acquisition/cursor_pos'].shape[1]})
                neural=np.asarray(f['acquisition/binned_spikes'][global_rows],dtype='<f8',order='C')
                for j,i in enumerate(global_rows):
                    for left,right in zip(neural[j:j+1].flat,f['acquisition/binned_spikes'][i:i+1].flat):
                        a=right.item();b=left.item()
                        need((int(b)==a and b==int(b)) if type(a) in (int,bool) else b==a,
                             'no lossy physical neural conversion')
                need(array_identity(neural)==sealed['neural_pin'],'actual full physical neural values match sealed query source')
                cursor=np.asarray(f['acquisition/cursor_pos'][global_rows],dtype='<f8',order='C')
                derived=derive_recenter_intervals(cursor,times,events,budget)['intervals']
                movement_ids=event_map[block]
                need(type(movement_ids) is list and len(movement_ids)==len(derived) and len(set(movement_ids))==len(movement_ids),
                     'every detected physical event mapped exactly once')
                need(all(t in trials and trials[t]['block_id']==block for t in movement_ids),'actual movement/block identities')
                required={t for t in allowed if trials[t]['block_id']==block}
                need(required<=set(movement_ids),'no eligible movement omitted from event matching')
                tp=targets['calibration' if block==cal_block else 'evaluation'];reach=tp['reach_profile']
                unit=reach['position_units']
                need(f['acquisition/cursor_pos'].shape[1]==2 and len(events['center'])==2,
                     'full two-coordinate physical cursor support')
                need(physical['field_units']['acquisition/cursor_pos']==unit and all(
                    physical['field_units']['trials/'+field]==unit for field in tp['coordinate_fields']), 'physical coordinate units match intended target algebra')
                expected_units=unit if tp['component']=='position' else reach['velocity_units']
                need(tp['axis_units']==[expected_units]*2,'explicit intended quantity unit per coordinate')
                indices=[];target_rows=[];dispositions=[]
                for tid,event in zip(movement_ids,derived):
                    tr=trials[tid]
                    need(tr['start_time']<=event['start_time']<event['stop_time']<=tr['stop_time'], 'derived event lies in matched physical trial interval')
                    if tid not in required:
                        dispositions.append({'trial_id':tid,'status':'excluded_failed_sequence_or_calibration','rows':[]});continue
                    stop=min(event['stop_time'],event['start_time']+policy['maximum_seconds'])
                    local=[i for i,t in enumerate(times) if t>=event['start_time'] and
                           (t<=stop if policy['boundary']=='closed' else t<stop)]
                    need(local and not set(local)&set(indices),'complete nonempty disjoint movement windows')
                    rel=[times[i]-event['start_time'] for i in local]
                    ti=physical_trial_index[tid];target=[float(f['trials/'+field][ti]) for field in tp['coordinate_fields']]
                    intended=intended_reach(rel,events['center'],target,event['stop_time']-event['start_time'],reach,budget)
                    values=intended[tp['component']]
                    indices.extend(local);target_rows.append(values)
                    dispositions.append({'trial_id':tid,'status':'eligible','rows':local,'relative_times':rel,
                        'start_time':event['start_time'],'acquisition_time':event['stop_time']})
                need(indices,'no original eligible support; cannot score full block or empty substitute')
                need(indices==sorted(indices),'complete chronological evaluator support')
                budget.reserve('T11.evaluator.target_join',{'concatenated_target':2*len(indices)})
                target=seal_array(np,np.concatenate(target_rows,axis=0),budget,'T11.evaluator.target')
                self.windows[key]={'selected_rows':indices,'sample_ids':[self.full_ids[key][i] for i in indices],
                    'target':target,'dispositions':dispositions,'source':{'physical':physical['physical_source_descriptor'],
                    'schema_identity':physical['schema_identity'],'event_profile':identity(events),'sequence_profile':identity(seq_profile),
                    'target_profile':identity(tp),'calibration_policy':identity(cal_policy),'window_policy':dict(policy),
                    'event_trial_mapping':identity(event_map),'full_clock_pin':identity(times)}}
            self.sources[sid]={'physical':physical['physical_source_descriptor'],'schema_identity':physical['schema_identity']}
        need(seen==self.sessions and set(self.windows)==set(self.block_support),'all complete two-session blocks evaluated')

    def project(self,support,full_prediction,lineage):
        key=(support['task'],support['query_id'],support['method']);need(key in self.bindings,'actual sealed method/block')
        seal=self.bindings[key];need(seal['status']=='complete' and array_identity(full_prediction)==seal['pin'],
             'no independently supplied subset or post-seal mutation')
        block=key[:2];window=self.windows[block]
        need(support['sample_ids']==self.full_ids[block] and support['axis_ids']==self.closure['axes']
             and lineage['axis_units']==self.closure['units'],'full support joins before evaluator projection')
        n=len(window['selected_rows']);d=len(support['axis_ids'])
        self.budget.reserve('T11.evaluator.prediction_selection',{'selected_prediction':n*d})
        prediction=seal_array(self.np,full_prediction[window['selected_rows'],:],self.budget,'T11.evaluator.selected_prediction')
        return {'prediction':prediction,'target':window['target'],'selected_rows':list(window['selected_rows']),
            'sample_ids':list(window['sample_ids']),'full_seal':seal['pin'],'evaluation_source':window['source'],
            'movement_dispositions':window['dispositions']}

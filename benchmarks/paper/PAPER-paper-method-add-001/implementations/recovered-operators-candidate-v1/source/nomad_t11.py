"""Protected T11 operators. No unknown original tail/event recipe is defaulted."""
from dataclasses import dataclass
from types import MappingProxyType
import json
from .nomad_math import (need, closed, integer, finite, numpy_for, matrix,
                         seal_array, identity, array_identity)


METHODS=('Static','RTI','NoMAD','NoMAD+RTI')
REPRESENTATIONS={'Static':'smoothed_spikes','RTI':'smoothed_spikes',
                 'NoMAD':'recurrent_Generator','NoMAD+RTI':'recurrent_Generator'}


def complete_sequences(trial_rows, sequence_members, profile):
    """Evaluate every source-bound four-movement sequence; no outlier dropping.

    These rows must come from the actual field adapter, not candidate reports.
    Sequence membership is a required original fact, never consecutive-ID guessing.
    """
    closed(profile,['success_value','trial_ids','sequence_ids','sequence_source_pin'],
           'complete original sequence policy')
    ids=profile['trial_ids'];sids=profile['sequence_ids']
    need(len(ids)==len(set(ids)) and len(sids)==len(set(sids)), 'unique full roster')
    need(type(trial_rows) is dict and set(trial_rows)==set(ids), 'all actual trial rows')
    need(type(sequence_members) is dict and set(sequence_members)==set(sids), 'all sequences')
    covered=[];out={}
    for sid in sids:
        members=sequence_members[sid]
        need(type(members) is list and len(members)==4 and len(set(members))==4,
             'exact four distinct movements per sequence')
        need(set(members)<=set(ids), 'actual source trial identities')
        covered.extend(members)
        rows=[trial_rows[t] for t in members]
        for row in rows:
            closed(row,['trial_id','block_id','result','start_time','stop_time'],
                   'adapter-supplied trial fields')
            need(finite(row['start_time'])<finite(row['stop_time']), 'actual movement time interval')
        need([r['trial_id'] for r in rows]==members and len({r['block_id'] for r in rows})==1,
             'same-block sequence and exact identities')
        success=all(r['result']==profile['success_value'] for r in rows)
        out[sid]={'trial_ids':tuple(members),'eligible':success,
                  'trial_eligible':{t:success for t in members},
                  'results':tuple(r['result'] for r in rows)}
    need(len(covered)==len(ids) and len(set(covered))==len(ids),
         'complete partition, no lost or reused trial')
    return {'sequences':out,'source_profile_pin':profile['sequence_source_pin'],
            'eligible_count':sum(4 for r in out.values() if r['eligible']),
            'total_trial_count':len(ids)}


def intended_reach(times, center, target, acquired_at, profile, budget):
    """Compute the source-defined 500ms segment, refusing an unresolved tail.

    Times are seconds relative to the admitted movement onset, not inferred from
    arbitrary row numbers. Full requested support must fit the resolved domain.
    """
    closed(profile,['numpy_version','time_units','position_units','velocity_units',
                    'early_acquisition','tail','profile_id','source_profile_pin'],
           'complete explicit intended-reach profile')
    need(profile['time_units']=='seconds', 'explicit original second clock conversion')
    need(profile['tail']=='unresolved_refuse', 'no500–600ms recipe was selected')
    need(profile['early_acquisition'] in ('unresolved_refuse','truncate_at_acquisition'),
         'explicit early acquisition disposition')
    np=numpy_for(profile)
    need(type(times) is list and times and all(0<=finite(t) for t in times)
         and all(a<b for a,b in zip(times,times[1:])), 'complete relative movement clock')
    c=[finite(x) for x in center];g=[finite(x) for x in target]
    need(len(c)==len(g) and len(c)>0, 'actual center/target coordinate vector')
    acquisition=finite(acquired_at,0)
    if acquisition<0.5:
        need(profile['early_acquisition']=='truncate_at_acquisition',
             'unresolved original early-acquisition behavior')
    stop=min(0.6,acquisition)
    need(all(t<=stop for t in times), 'supplied scoring support exceeds actual end')
    need(all(t<=0.5 for t in times), 'original500–600ms intended-velocity tail unresolved')
    budget.reserve('T11.intended_reach', {'position_and_velocity':2*len(times)*len(c),
                                        'vectors_and_time':4*len(c)+len(times)})
    c=np.array(c,dtype=np.float64);g=np.array(g,dtype=np.float64)
    velocity=(g-c)/0.5
    position=c[None,:]+np.array(times,dtype=np.float64)[:,None]*velocity[None,:]
    velocities=np.broadcast_to(velocity,position.shape).copy()
    need(bool(np.isfinite(position).all()) and bool(np.isfinite(velocities).all()),
         'finite target algebra')
    return {'position':seal_array(np,position,budget,'intended.position'),
            'velocity':seal_array(np,velocities,budget,'intended.velocity'),
            'times':tuple(times),'profile':dict(profile),
            'original_tail_resolved':False,'source_semantics':'constant500msstraightreach'}


def derive_recenter_intervals(cursor, times, profile, budget):
    """An explicit gradient-discontinuity/last-center-sample operator.

    The source reports that family but not these numerical choices. An unresolved
    historical profile refuses; this function never manufactures original values.
    """
    closed(profile,['numpy_version','gradient_metric','jump_threshold','center',
                    'center_tolerance','center_match','minimum_start_index',
                    'source_profile_pin','profile_id'], 'complete explicit event profile')
    need(profile['gradient_metric'] in ('sample_difference_l2','per_second_l2'),
         'unresolved gradient metric')
    need(profile['center_match']=='last_sample_within_declared_distance',
         'only explicitly selected center-sample rule supported; no inferred crossing rule')
    threshold=finite(profile['jump_threshold'],0);tolerance=finite(profile['center_tolerance'],0)
    need(threshold>0, 'selected discontinuity threshold')
    first=integer(profile['minimum_start_index'])
    np=numpy_for(profile);n=len(times);d=len(profile['center'])
    need(n>=2 and all(a<b for a,b in zip(times,times[1:])), 'full ordered event clock')
    ts=[finite(x) for x in times];center=[finite(x) for x in profile['center']]
    matrix(np,cursor,(n,d),budget,'T11.cursor')
    budget.reserve('T11.event_operator',{'diff_and_norms':3*n*d+4*n,'center':d})
    delta=cursor[1:]-cursor[:-1]
    if profile['gradient_metric']=='per_second_l2':delta/=np.diff(np.array(ts))[:,None]
    magnitude=np.linalg.norm(delta,axis=1)
    center_distance=np.linalg.norm(cursor-np.array(center)[None,:],axis=1)
    need(bool(np.isfinite(magnitude).all()) and bool(np.isfinite(center_distance).all()),
         'finite event comparisons')
    stops=[i+1 for i,v in enumerate(magnitude) if v>threshold];intervals=[];previous=first
    for stop in stops:
        candidates=[i for i in range(previous,stop) if center_distance[i]<=tolerance]
        need(candidates, 'discontinuity has no admitted previous center event')
        start=candidates[-1]
        need(start<stop, 'positive movement interval')
        intervals.append({'start_index':start,'stop_index':stop,
                          'start_time':ts[start],'stop_time':ts[stop]})
        previous=stop
    return {'intervals':intervals,'full_stop_indices':stops,'profile':dict(profile),
            'original_event_profile_authenticated':False}


def compile_block_roster(sessions):
    need(type(sessions) is list and len(sessions)==2,'complete two-session study')
    need(len({r['session_id'] for r in sessions})==2,'two unique session identities')
    rows=[];calibration=[]
    for session in sessions:
        closed(session,['session_id','calibration_block','postcalibration_blocks',
                        'block_source_pin'],'exact chronological session descriptor')
        blocks=session['postcalibration_blocks']
        need(type(blocks) is list and blocks and len(set(blocks))==len(blocks)
             and session['calibration_block'] not in blocks, 'full ordered disjoint block roster')
        for method in METHODS:
            calibration.append((session['session_id'],session['calibration_block'],method))
        for i,block in enumerate(blocks):
            for method in METHODS:
                rows.append({'session_id':session['session_id'],'block_id':block,
                    'index':i+1,'method':method,'representation':REPRESENTATIONS[method],
                    'first_evaluation':i==0})
    return {'slots':tuple(rows),'calibration_slots':tuple(calibration),
        'first_evaluation_slots':8,'unique_initial_representation_decoder_endpoints':4,
        'postcalibration_slot_count':4*sum(len(s['postcalibration_blocks']) for s in sessions),
        'empirical_source_pins':tuple(s['block_source_pin'] for s in sessions)}


class ChronologicalRelease:
    """Owns logical prediction-before-history barriers, not OS process proof.

    Construct only in the trusted controller. Full private blocks stay in this
    object; query_view returns a newly built allowlisted view without target-
    derived masks. This is not a sandbox and cannot grant deployment qualification.
    """
    def __init__(self,sessions,private_blocks,query_schema,profile,budget):
        self.roster=compile_block_roster(sessions);self.sessions=json.loads(json.dumps(sessions))
        closed(query_schema,['neural_fields','nonbehavioral_metadata_fields','axes','units'],
               'closed nonbehavioral query view')
        need(query_schema['neural_fields']==['binned_spikes'], 'complete declared neural query only')
        need(query_schema['nonbehavioral_metadata_fields']==['session_id','block_id','timestamps'],
             'no current target/event/success or arbitrary metadata fields')
        self.schema=json.loads(json.dumps(query_schema));self.profile=dict(profile);self.budget=budget
        self.np=numpy_for(profile);self.private=private_blocks;self.predictions={};self.sealed={};self.calibrations={}
        self.open_block=None;self.closed=False
        expected={(s['session_id'],b) for s in sessions for b in
                  [s['calibration_block']]+s['postcalibration_blocks']}
        need(type(private_blocks) is dict and set(private_blocks)==expected,'all private source blocks')
        self.expected=expected;self.events=[]

    def _session(self,sid):
        found=[s for s in self.sessions if s['session_id']==sid]
        need(len(found)==1,'actual session');return found[0]

    def register_calibration(self,sid,method,prediction,source_state_pin):
        session=self._session(sid);key=(sid,method)
        need(not self.closed and self.open_block is None and key not in self.calibrations
             and method in METHODS and not any(k[0]==sid for k in self.predictions),
             'once-only initial calibration before any session query')
        raw=self.private[(sid,session['calibration_block'])]
        n=len(raw['timestamps']);d=len(self.schema['axes'])
        matrix(self.np,prediction,(n,d),self.budget,'calibration.prediction')
        need(type(source_state_pin) is str and source_state_pin,'actual initial fitted state identity')
        a=seal_array(self.np,prediction,self.budget,'calibration.copy')
        self.calibrations[key]={'values':a,'pin':array_identity(a),'state_pin':source_state_pin}

    def query_view(self,sid,block):
        need(not self.closed and self.open_block is None,'one open full block')
        session=self._session(sid);blocks=session['postcalibration_blocks']
        need(all((sid,m) in self.calibrations for m in METHODS),'all calibration method slots')
        for first,second in (('Static','RTI'),('NoMAD','NoMAD+RTI')):
            a=self.calibrations[(sid,first)];b=self.calibrations[(sid,second)]
            need(a['pin']==b['pin'] and a['state_pin']==b['state_pin'],
                 'shared original initial decoder/product inside each method pair')
        need(block in blocks,'post-calibration query')
        i=blocks.index(block)
        need(all((sid,b) in self.sealed for b in blocks[:i]) and (sid,block) not in self.sealed,
             'chronological unqueried block only')
        raw=self.private[(sid,block)]
        for key in ('session_id','block_id','timestamps','binned_spikes'):
            need(key in raw,'source query field')
        need(raw['session_id']==sid and raw['block_id']==block,'exact source block identity')
        times=raw['timestamps'];a=raw['binned_spikes']
        need(type(times) is list and len(times)==a.shape[0] and
             all(x<y for x,y in zip(times,times[1:])), 'complete block neural clock')
        matrix(self.np,a,a.shape,self.budget,'query.neural')
        self.open_block=(sid,block)
        self.events.append({'action':'open_query','session':sid,'block':block})
        return {'session_id':sid,'block_id':block,'timestamps':tuple(times),
                'binned_spikes':seal_array(self.np,a,self.budget,'query.neural_copy')}

    def record_prediction(self,sid,block,method,prediction,source_state_pin):
        need(self.open_block==(sid,block) and method in METHODS,'actual current method slot')
        key=(sid,block,method);need(key not in self.predictions,'immutable once-only method prediction')
        need(type(source_state_pin) is str and source_state_pin,'fitted scientific state identity')
        raw=self.private[(sid,block)];n=len(raw['timestamps']);d=len(self.schema['axes'])
        matrix(self.np,prediction,(n,d),self.budget,'whole_block_prediction')
        a=seal_array(self.np,prediction,self.budget,'sealed.prediction')
        self.predictions[key]={'status':'complete','values':a,'pin':array_identity(a),'state_pin':source_state_pin,
                               'axes':tuple(self.schema['axes']),'units':tuple(self.schema['units'])}
        return dict(self.predictions[key]['pin'])

    def record_failure(self,sid,block,method,error,captured_prefix_pin):
        """Trusted controller preserves an actual exception; no fabricated score.

        Prefix identity is independently captured by the artifact consumer. This
        logical class does not turn the prefix or exception into OS qualification.
        """
        need(self.open_block==(sid,block) and method in METHODS,'actual current failed slot')
        key=(sid,block,method);need(key not in self.predictions,'failed slot cannot replace output')
        need(isinstance(error,BaseException),'actual retained exception object')
        need(type(captured_prefix_pin) is str and captured_prefix_pin,'captured attempt-prefix identity')
        evidence={'exception_type':type(error).__name__,'prefix_pin':captured_prefix_pin}
        self.predictions[key]={'status':'failed','values':None,'pin':{'failure_evidence':evidence},
                               'state_pin':None,'failure_evidence':evidence}

    def seal_block(self,sid,block):
        need(self.open_block==(sid,block),'original open block')
        need(all((sid,block,m) in self.predictions for m in METHODS),'all four actual full products')
        bindings={m:self.predictions[(sid,block,m)]['pin'] for m in METHODS}
        for m in METHODS:
            row=self.predictions[(sid,block,m)]
            if row['status']=='complete':need(array_identity(row['values'])==row['pin'],'unchanged actual prediction bytes')
            else:need(row['values'] is None and row['pin']=={'failure_evidence':row['failure_evidence']},'retained failed slot')
        if self._session(sid)['postcalibration_blocks'][0]==block:
            for a,b in (('Static','RTI'),('NoMAD','NoMAD+RTI')):
                x=self.predictions[(sid,block,a)];y=self.predictions[(sid,block,b)]
                if x['status']=='complete' and y['status']=='complete':
                    need(x['pin']==y['pin'] and x['state_pin']==y['state_pin'],
                         'shared unchanged first-evaluation products')
        self.sealed[(sid,block)]=identity(bindings);self.open_block=None
        self.events.append({'action':'seal_four_methods','session':sid,'block':block,
                            'prediction_set_pin':self.sealed[(sid,block)]})
        return self.sealed[(sid,block)]

    def historical_context(self,sid,next_block,fields):
        session=self._session(sid);blocks=session['postcalibration_blocks']
        need(next_block in blocks,'future fit target exists');i=blocks.index(next_block)
        need(all((sid,b) in self.sealed for b in blocks[:i]),'past four-method barriers before release')
        allowed={'binned_spikes','timestamps','cursor_pos','target_pos','cursor_vel',
                 'cond_id','trial_start','trial_stop','result','sequence_members'}
        need(type(fields) is list and fields and len(set(fields))==len(fields)
             and set(fields)<=allowed,'explicit permitted past task context; no score/residual/target artifact')
        out=[]
        for b in [session['calibration_block']]+blocks[:i]:
            raw=self.private[(sid,b)];row={'session_id':sid,'block_id':b}
            for name in fields:
                need(name in raw,'required historical field actually captured')
                v=raw[name]
                if type(v) is self.np.ndarray:
                    row[name]=seal_array(self.np,v,self.budget,'history.'+name)
                else:
                    row[name]=json.loads(json.dumps(v,allow_nan=False))
            out.append(row)
        self.events.append({'action':'release_past_context','session':sid,'for_block':next_block,
                            'blocks':[r['block_id'] for r in out],'fields':tuple(fields)})
        return out

    def finish(self):
        need(not self.closed and self.open_block is None,'complete single-use closure')
        expected={(r['session_id'],r['block_id']) for r in self.roster['slots']}
        need(set(self.sealed)==expected and len(self.predictions)==self.roster['postcalibration_slot_count'],
             'full two-session method/block barrier')
        need(len(self.calibrations)==8,'all eight calibration method uses retained')
        for row in self.calibrations.values():need(array_identity(row['values'])==row['pin'],'unchanged calibration arrays')
        for row in self.predictions.values():
            if row['status']=='complete':need(array_identity(row['values'])==row['pin'], 'unchanged sealed full arrays')
        self.closed=True
        return {'logical_prediction_barrier':'complete','roster':self.roster,
                'prediction_pins':{'/'.join(k):v['pin'] for k,v in self.predictions.items()},
                'calibration_pins':{'/'.join(k):v['pin'] for k,v in self.calibrations.items()},
                'events':list(self.events),'original_process_closure_verified':False,
                'axes':list(self.schema['axes']),'units':list(self.schema['units']),
                'block_support_bindings':[{'session_id':sid,'block_id':block,
                    'timestamps':list(self.private[(sid,block)]['timestamps']),
                    'neural_pin':array_identity(self.private[(sid,block)]['binned_spikes'])}
                    for sid,block in sorted(self.expected)],
                'prediction_bindings':[{'session_id':k[0],'block_id':k[1],'method':k[2],
                    'status':v['status'],'pin':v['pin'],'state_pin':v['state_pin']} for k,v in self.predictions.items()],
                'calibration_bindings':[{'session_id':k[0],'block_id':self._session(k[0])['calibration_block'],
                    'method':k[1],'status':'complete','pin':v['pin'],'state_pin':v['state_pin']} for k,v in self.calibrations.items()],
                'scientific_or_deployment_qualification':False,
                'target_reader_not_part_of_this_object':True}

"""Independent typed-event preparation; native author output is a separate lane."""
import copy
import math
import statistics
from reward_common import need, finite_number, integer, unique_records, native_integral

CONDITIONS = ('30s','60s','300s','600s','3600s','60s-few','60s-few-ctxt',
              '60s-CSminus','600s-bgdmilk','60s-50percent','60s-10percent','FC-45s','FC-135s')
D_CONDITIONS = ('60s','600s','3600s','60s-few','60s-50percent','60s-10percent','FC-45s','FC-135s')


def count_window(events, left, right):
    need(right > left, 'Positive count window')
    return sum(left <= x < right for x in events)


def fit_optical(times, control, signal):
    """Full-session retrospective OLS only; no prospective claim."""
    need(len(times) == len(control) == len(signal) >= 2, 'Optical shape')
    x = [finite_number(v) for v in control]
    y = [finite_number(v) for v in signal]
    mx, my = statistics.mean(x), statistics.mean(y)
    denom = math.fsum((v-mx)**2 for v in x)
    need(denom > 0, 'Constant control channel')
    a = math.fsum((u-mx)*(v-my) for u,v in zip(x,y))/denom
    b = my-a*mx
    fitted = [a*v+b for v in x]
    need(all(v != 0 for v in fitted), 'Zero optical denominator')
    return {'times':times, 'values':[100*(v-f)/f for v,f in zip(y,fitted)],
            'a':a,'b':b,'fit_scope':'retrospective_full_session'}


def signal_response(trace, baseline, response):
    if trace is None:
        return {'status':'unavailable','reason':'modality_absent'}
    kwargs = {'max_gap':trace['max_gap'],'valid':trace.get('valid')}
    base = native_integral(trace['times'],trace['values'],*baseline,**kwargs)
    resp = native_integral(trace['times'],trace['values'],*response,**kwargs)
    if not (math.isclose(base['covered_seconds'],base['requested_seconds'],rel_tol=1e-10,abs_tol=1e-10)
            and math.isclose(resp['covered_seconds'],resp['requested_seconds'],rel_tol=1e-10,abs_tol=1e-10)):
        return {'status':'unscorable','reason':'incomplete_interval','baseline':base,'response':resp}
    selected = [v for t,v in zip(trace['times'],trace['values']) if response[0] <= t < response[1]]
    if not selected:
        return {'status':'unscorable','reason':'no_observed_response_sample'}
    indices=[i for i,w in enumerate(resp['weights']) if w>0]
    target={'times':[trace['times'][i] for i in indices], 'values':[trace['values'][i] for i in indices],
            'window':list(response),'max_gap':trace['max_gap'],'fit_scope':trace['fit_scope']}
    base={k:v for k,v in base.items() if k not in ('weights','segments')}
    resp={k:v for k,v in resp.items() if k not in ('weights','segments')}
    return {'status':'computed','auc':resp['integral']-base['mean']*resp['requested_seconds'],
            'peak':max(selected)-base['mean'],'baseline':base,'response':resp,
            'target_trace':target}


def _trace(session, branch):
    raw = session.get('raw_optical')
    if raw is not None:
        trace = fit_optical(raw['times'],raw['control'],raw['signal'])
        trace['max_gap'] = finite_number(raw['max_gap'])
        trace['valid'] = raw.get('valid')
        return trace
    trace = session.get('photometry')
    if trace is None:
        return None
    need(branch in ('retrospective_processed','engineering'), 'Processed signal cannot silently become prospective')
    need(trace.get('fit_scope') in ('retrospective_full_session','training_prefix','invented'), 'Signal fit provenance')
    return trace


def _video_response(video, cue, duration):
    if video is None:
        return {'status':'unavailable','reason':'video_absent'}
    times = [finite_number(t) for t in video['times']]
    motion = [finite_number(v) for v in video['motion']]
    max_gap=finite_number(video['max_gap']);need(max_gap>0,'Video gap limit')
    need(len(times)==len(motion), 'Video shape')
    need(all(b>a for a,b in zip(times,times[1:])), 'Video clock')
    freeze = video.get('freezing')
    if freeze is None:
        # Native ezTrack minimum run-length criterion; no scattered low-motion frames.
        freeze = [0]*len(motion); start=0
        while start<len(motion):
            if motion[start]>=500:
                start+=1;continue
            stop=start
            while stop<len(motion) and motion[stop]<500 and (stop==start or times[stop]-times[stop-1]<=max_gap):stop+=1
            if stop-start>=10:freeze[start:stop]=[1]*(stop-start)
            start=stop
    need(len(freeze)==len(times) and all(x in (0,1) and type(x) is int for x in freeze),'Binary freeze frames')
    out={}
    for name,left,right in [('baseline',cue-duration,cue),('cue',cue,cue+duration)]:
        inds=[i for i,t in enumerate(times) if left<=t<right]
        support=native_integral(times,[1]*len(times),left,right,max_gap)
        if not inds or not math.isclose(support['covered_seconds'],right-left,abs_tol=1e-9):
            return {'status':'unscorable','reason':'missing_video_window_or_clock_gap'}
        out[name+'_freezing']=statistics.mean(freeze[i] for i in inds)
        out[name+'_motion']=statistics.mean(finite_number(motion[i]) for i in inds)
        out[name+'_frames']=len(inds)
    out.update(status='computed',freezing_change=out['cue_freezing']-out['baseline_freezing'],
               motion_change=out['cue_motion']-out['baseline_motion'])
    return out


def prepare(corpus, branch='retrospective_processed'):
    """Prepare all supplied animals, never merge identity from filename hints.

    Neutral input is an explicit versioned export, not a discovery heuristic.
    The full13-condition gate is separate from whether an individual is usable.
    """
    need(corpus.get('schema')=='reward_neutral_corpus_v1','Neutral export schema')
    need(branch in ('retrospective_processed','engineering'),'Explicit implemented preparation branch')
    animals=unique_records(corpus['animals'],['animal_id'])
    output=[];exclusions=[];session_keys=set()
    for (aid,),animal in animals.items():
        condition=animal['condition'];need(condition in CONDITIONS,'Unknown condition')
        need(animal.get('identity_status') in ('verified','invented'), 'Unresolved biological identity')
        trials=[];conditioning_offset=0
        for session in sorted(animal['sessions'],key=lambda s:s['session_number']):
            integer(session['session_number'],'session number',1)
            key=(aid,session['session_number']);need(key not in session_keys,'Duplicate session');session_keys.add(key)
            session_start=finite_number(session['start_time']);session_end=finite_number(session['end_time'])
            need(session_end>session_start,'Positive observed session duration')
            on=[finite_number(x) for x in session.get('lick_on',[])]
            off=[finite_number(x) for x in session.get('lick_off',[])]
            need(on==sorted(on) and off==sorted(off),'Ordered lick events')
            need(len(on)==len(off) and all(b>=a for a,b in zip(on,off)),'Paired lick contacts')
            need(all(b<=a for b,a in zip(off,on[1:])),'Nonoverlapping lick contacts')
            need(all(session_start<=a<=b<=session_end for a,b in zip(on,off)),'Contact session bounds')
            trace=_trace(session,branch)
            source_trials=unique_records(session['trials'],['trial_id'])
            ordered=sorted(source_trials.values(),key=lambda t:t['cue_on'] if t['kind']!='milk' else t['outcome_time'])
            previous_bout_end=None
            for row in ordered:
                kind=row['kind'];need(kind in ('CS_plus','CS_minus','milk','shock'),'Typed event')
                cue=finite_number(row['outcome_time'] if kind=='milk' else row['cue_on'])
                outcome=finite_number(row['outcome_time'])
                need(type(row['delivered']) is bool,'Outcome delivery flag')
                need(session_start<=cue<=outcome<=session_end,'Trial session chronology')
                if kind=='CS_minus':need(not row['delivered'],'CS minus is unrewarded cue')
                r={'animal_id':aid,'condition':condition,'session_number':session['session_number'],
                   'trial_id':row['trial_id'],'kind':kind,'cue_on':None if kind=='milk' else cue,
                   'outcome_time':outcome,'delivered':row['delivered'],'source':session['source'],
                   'clock_origin':session.get('clock_origin',0),'missing':copy.deepcopy(row.get('missing',[]))}
                r['elapsed_conditioning_cue']=conditioning_offset+cue-session_start
                r['lick_times_relative']=[x-cue for x in on if cue-2.5<=x<cue+7.5]
                r['contacts_relative']=[[a-cue,b-cue] for a,b in zip(on,off) if b>=cue-2.5 and a<cue+7.5]
                iti_start=previous_bout_end
                r['preceding_ITI_lick_rate']=(count_window(on,iti_start,cue)/(cue-iti_start)
                    if iti_start is not None and cue>iti_start and 'licks' not in r['missing'] else None)
                r['preceding_ITI_bounds']=None if iti_start is None else [iti_start,cue]
                r['consumption_bout_seconds']=None
                r['long_contact_present']=any(b-a>10 for a,b in zip(on,off))
                r['lick_epoch_complete']=session_start<=cue-2.5 and cue+7.5<=session_end and 'licks' not in r['missing']
                if trace is not None:
                    r['da_epoch']={'times':[t-cue for t in trace['times'] if cue-2.5<=t<cue+20],
                                   'values':[v for t,v in zip(trace['times'],trace['values']) if cue-2.5<=t<cue+20]}
                if kind in ('CS_plus','CS_minus'):
                    need(outcome>=cue,'Outcome after cue')
                    available='licks' not in r['missing'] and session_start<=cue-1.25 and cue+1.25<=session_end
                    B=count_window(on,cue-1.25,cue) if available else None
                    A=count_window(on,cue,cue+1.25) if available else None
                    r.update(B=B,A=A,D=None if A is None else A-B,
                             delta_hz=None if A is None else (A-B)/1.25)
                    r['cue_da']=signal_response(trace,(cue-.5,cue),(cue,cue+.5))
                if kind=='shock':
                    duration=finite_number(row.get('cue_duration',15))
                    r['behavior']=_video_response(session.get('video'),cue,duration)
                    r['cue_da']=signal_response(trace,(cue-14,cue),(cue+1,cue+15))
                if kind in ('CS_plus','milk') and row['delivered']:
                    spans=any(a<=outcome<b for a,b in zip(on,off))
                    after=[x for x in on if outcome<=x<outcome+5]
                    consumed=outcome if spans else (after[0] if after else None)
                    if consumed is not None:
                        contact=next((i for i,(a,b) in enumerate(zip(on,off)) if a<=consumed<=b),None)
                        if contact is not None:
                            end=contact
                            while end+1<len(on) and on[end+1]-off[end]<=.5:end+=1
                            r['consumption_bout_seconds']=off[end]-consumed
                            previous_bout_end=off[end]
                    r['consumption_onset']=consumed
                    r['consumed_within5']=consumed is not None
                    # Background milk is never a fabricated cue event.
                    base=cue if kind=='CS_plus' else outcome
                    r['reward_da']=(signal_response(trace,(base-.5,base),(consumed,consumed+.5))
                                    if consumed is not None else {'status':'unscorable','reason':'not_consumed'})
                    r['reward_da_2s']=(signal_response(trace,(base-2,base),(consumed,consumed+2))
                                      if consumed is not None else {'status':'unscorable','reason':'not_consumed'})
                elif kind=='CS_plus':
                    r['omission_da']=signal_response(trace,(cue-2,cue),(outcome,outcome+2))
                trials.append(r)
            conditioning_offset+=session_end-session_start
        output.append({'animal_id':aid,'condition':condition,'identity_status':animal['identity_status'],
                       'histology':copy.deepcopy(animal.get('histology')),'trials':trials,
                       'source_exclusions':copy.deepcopy(animal.get('source_exclusions',[]))})
    present=sorted({a['condition'] for a in output})
    return {'schema':'reward_prepared_v1','branch':branch,'animals':output,
            'present_conditions':present,'missing_conditions':sorted(set(CONDITIONS)-set(present)),
            'source_corpus_sha256':corpus['corpus_identity'],'exclusions':exclusions,
            'scientific_qualification':False}

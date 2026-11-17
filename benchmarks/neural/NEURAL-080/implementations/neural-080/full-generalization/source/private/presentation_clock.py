"""Extract original saved per-trial PTB timing, never fabricate trigger timing.

Original EMD run_experiment.m saves data after every run. GetSecs/Flip timing
is reported software timing, not independently measured neural/audio latency.
"""
import io
import math
from pathlib import Path
from input_owner import need,integer,descriptor,capture,Writer

def number(x):
    need(type(x) in (int,float) and math.isfinite(x),'Finite real software timestamp')
    return float(x)

def integer_scalar(x,lo,hi):
    # MATLAB stores these integer-valued quantities as doubles. Do not accept
    # arbitrary rounding or boolean coordinates when converting the saved schema.
    need(type(x) in (int,float) and math.isfinite(x) and int(x)==x and lo<=x<=hi,'Exact MATLAB integer-valued coordinate')
    return int(x)

def project_trial(trial,subject,session,run,media):
    need(type(trial) is dict,'Original saved trial structure')
    t=integer_scalar(trial['trial'],1,66)
    need(integer_scalar(trial['run'],1,16)==run,'Saved run joins enclosing file coordinate')
    vid=integer_scalar(trial['video_number'],1,1102)
    need(trial['name']==Path(media[vid]['source_media']['path']).name,'Original saved video name joins selected byte mapping')
    expected='train' if vid<=1000 else 'test'
    need(trial['partition']==expected,'Original training/query partition')
    count=integer_scalar(trial['count'],1,1000);played=integer_scalar(trial['played_frames'],1,1000)
    times=trial['frames_timing']
    if hasattr(times,'tolist'):times=times.tolist()
    need(type(times) is list and len(times)==max(count,played),'Original preallocated frame vector, including any real extension')
    observed=[number(x) for x in times[:played]]
    need(all(x==0 for x in times[played:]),'Unused preallocated frame entries must remain zero, not observed frames')
    onset=number(trial['onset_visuals']);offset=number(trial['offset_visuals'])
    a=number(trial['onset_audio']);b=number(trial['offset_audio'])
    need(observed[0]==onset and all(y>x for x,y in zip(observed,observed[1:])) and offset>observed[-1] and b>a,'Actual monotonic displayed-frame and playback-command times')
    need(number(trial['visuals_duration'])==offset-onset and number(trial['audio_duration'])==b-a,'Saved duration joins actual saved endpoints')
    starts=[x-onset for x in observed];ends=[x-onset for x in observed[1:]]+[offset-onset]
    return {'subject':subject,'session':session,'run':run,'trial':t,'video_id':vid,'media':media[vid]['source_media'],'partition':expected,'frame_starts_relative_first_flip':starts,'frame_ends_relative_first_flip':ends,'played_frames':played,'declared_frames':count,'frame_count_matches':played==count,'audio_command_start_relative_first_flip':a-onset,'audio_command_stop_relative_first_flip':b-onset,'eeg_trigger_time':None,'eye_message_time':None,'physical_audio_onset':None,'hardware_alignment_verified':False}

def project_run(data,subject,session,run,media):
    need(type(data) is dict and type(data.get('subject')) is dict,'Original data.subject structure')
    need(integer_scalar(data['subject']['id'],1,6)==subject and integer_scalar(data['subject']['session'],1,8)==session and integer_scalar(data['run'],1,16)==run,'Saved person/session/run joins selected file')
    # Do not retain age, sex, responses, labels, correctness, captions or tasks.
    trials=data['trials']
    need(type(trials) is list and len(trials)==66,'Complete original 66 non-catch trials')
    result=[project_trial(x,subject,session,run,media) for x in trials]
    need([r['trial'] for r in result]==list(range(1,67)),'Exact run trial order; no catch trial admission')
    return result

def saved_scalar_projection(data,np):
    """Normalize real SciPy/NumPy scalar representations, not their values.

    Only source fields consumed by the timing projection are retained here.
    Boolean/nonfinite/nonintegral checks remain in project_run/project_trial.
    """
    need(type(data) is dict and type(data.get('subject')) is dict,'Original saved struct')
    scalar=lambda x:x.item() if isinstance(x,np.generic) else x
    trials=data['trials'];need(type(trials) is list and len(trials)==66,'Full original saved trial struct array')
    numeric=('trial','run','video_number','count','played_frames','onset_visuals','offset_visuals','onset_audio','offset_audio','visuals_duration','audio_duration')
    projected=[]
    for row in trials:
        need(type(row) is dict,'Saved trial struct')
        r={k:scalar(row[k]) for k in numeric}
        r.update(name=scalar(row['name']),partition=scalar(row['partition']),frames_timing=row['frames_timing'])
        projected.append(r)
    return {'subject':{'id':scalar(data['subject']['id']),'session':scalar(data['subject']['session'])},'run':scalar(data['run']),'trials':projected}

def read_run(root,row,media,owner):
    rec=owner.begin('presentation_run');buffer=None;answer=None
    try:
        import scipy
        import numpy as np
        from scipy.io import loadmat
        need(scipy.__version__=='1.15.3','Exact prospective MAT reader version')
        body=capture(root,row['file'],owner)
        owner.reserve('retained_bytes',len(body));buffer=io.BytesIO(body)
        # This real source reader supports v4/v6/v7 through7.2 only. MATLAB7.3,
        # malformed compressed data or absent fields fail; no schema fabrication.
        data=loadmat(buffer,appendmat=False,variable_names=['data'],simplify_cells=True,verify_compressed_data_integrity=True)['data']
        answer=project_run(saved_scalar_projection(data,np),row['subject'],row['session'],row['run'],media)
    except BaseException as exc:owner.failure(rec,exc)
    finally:
        if buffer is not None:owner.close(rec,buffer.close)
    owner.complete(rec);return answer

def produce(root,selection,media_selection,joined,owner,out):
    rec=owner.begin('complete_presentation_source');answer=None
    try:
        need(type(selection) is dict and set(selection)=={'schema','files'} and selection['schema']=='neural080_behavior_logs_v1','Closed actual-log selection')
        files=selection['files'];expected={(p,s,r) for p in range(1,7) for s in range(1,9) for r in range(1,17)}
        need(type(files) is list and len(files)==768,'Full 6×8×16 behavioral-log descriptors; no observed subset')
        seen=set();paths=set()
        for row in files:
            need(type(row) is dict and set(row)=={'subject','session','run','file'},'Closed log role')
            need(all(type(row[k]) is int for k in ('subject','session','run')),'Strict enclosing coordinates')
            key=tuple(row[k] for k in ('subject','session','run'))
            need(key in expected and key not in seen,'Unique complete log role');seen.add(key)
            descriptor(row['file']);need(row['file']['path'] not in paths,'Unique log file');paths.add(row['file']['path'])
        need(seen==expected,'Complete original log support')
        media={r['video_id']:r for r in media_selection['videos']}
        need(set(media)==set(range(1,1103)),'Complete selected original media map')
        expected_join={}
        need(joined['schema']=='neural080_joined_metadata_v1' and len(joined['subjects'])==6,'Original complete EEG-eye joined metadata')
        for person in joined['subjects']:
            p=int(person['subject'].removeprefix('sub-'))
            for name,session in person['sessions'].items():
                s=int(name.removeprefix('ses-'))
                for row in session['joined']:
                    key=(p,s,row['run'],row['trial']);need(key not in expected_join,'Unique rejection-aware joined trial');expected_join[key]=row['video_id']
        need(len(expected_join)==45144,'Full frozen 45,144 intersection, not a new outcome-selected cohort')
        writer=Writer(out,owner);all_seen=set();joined_seen=set();records=[]
        for row in sorted(files,key=lambda x:(x['subject'],x['session'],x['run'])):
            trials=read_run(root,row,media,owner)
            for trial in trials:
                key=tuple(trial[k] for k in ('subject','session','run','trial'))
                need(key not in all_seen,'Unique actual presentation');all_seen.add(key)
                trial['in_released_eeg_eye_intersection']=key in expected_join
                if key in expected_join:
                    need(trial['video_id']==expected_join[key],'Presentation joins exact EEG-eye source identity')
                    joined_seen.add(key)
            name='sub-%02d-ses-%02d-run-%02d.json'%(row['subject'],row['session'],row['run'])
            records.append(writer.document(name,{'source':row['file'],'trials':trials}))
        need(joined_seen==set(expected_join),'No joined trial missing a real presentation record')
        answer={'schema':'neural080_presentation_observations_v1','files':records,'all_presented_noncatch_trials':len(all_seen),'joined_trials':len(joined_seen),'source_method':'saved Flip/GetSecs fields only','hardware_alignment_verified':False,'neural_trigger_bridge':'unavailable: configured 0.01367 wait is not an observed trigger timestamp','stimulus_features_recomputed':False,'trial_timing_warp_or_average':False}
        writer.document('PRESENTATION_CLOCK.json',answer)
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer

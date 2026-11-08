"""One protected whole-study grade, with unchanged historical primary."""
import common as c
import schedule

def matched_packet(h,m,hpin,sealpin,core):
    c.exact(m,('schema_version','task_id','phase','historical_packet','four_stream_seal','matched_prediction','records'))
    c.need(type(m['schema_version'])is int and m['schema_version']==1 and m['task_id']==c.TASK and m['phase']=='post_prediction_matched_diagnostic','matched packet identity')
    c.need(c.typed_equal(m['historical_packet'],hpin)and c.typed_equal(m['four_stream_seal'],sealpin),'matched packet joins same historical source and master seal')
    rows=core.validate_packet(h);expected=sorted(r['recording_id']for r in rows)
    c.need(type(m['records'])is list and [r.get('recording_id')for r in m['records']]==expected,'complete ordered matched support')
    byid={r['recording_id']:r for r in rows}
    for r in m['records']:
        c.exact(r,('recording_id','events'));d=byid[r['recording_id']]['duration_seconds'];core.intervals(r['events'],d)
        c.need(core.event.canonical(r['events'],d)==r['events'],'canonical matched events')
    return rows,{r['recording_id']:r['events']for r in m['records']}

def reconstruct_matched(h,m,hpin,sealpin,core):
    rows,hyp=matched_packet(h,m,hpin,sealpin,core);people={};montages={};localization=[]
    for row in sorted(rows,key=lambda r:r['recording_id']):
        pid,mid,rid,d=row['patient_id'],row['montage_id'],row['recording_id'],row['duration_seconds']
        cell={arm:core.event.count_events(row['annotations'],events,d)for arm,events in [('candidate',row['arms']['candidate']),('matched_no_eeg',hyp[rid])]}
        for arm,counts in cell.items():
            people.setdefault(pid,{}).setdefault(arm,[]).append(counts)
            montages.setdefault(mid,{}).setdefault(pid,{}).setdefault(arm,[]).append(counts)
        fp=core.false_alarms(row['annotations'],hyp[rid],d)
        c.need(len(fp)==cell['matched_no_eeg']['false_alarm_events'],'matched localization reconciles exactly')
        localization.append({'recording_id':rid,'arm':'matched_no_eeg','intervals':fp})
    def scores(table):return {p:{a:core.event.summarize(v)for a,v in arms.items()}for p,arms in sorted(table.items())}
    def difference(table):
        return {metric:core.paired([v['candidate'][metric]-v['matched_no_eeg'][metric]for v in table.values()if v['candidate'][metric]is not None and v['matched_no_eeg'][metric]is not None])for metric in core.METRICS}
    ps=scores(people);strata={}
    for mid,table in sorted(montages.items()):
        v=scores(table);strata[mid]={'patients':{p:{'matched_no_eeg':a['matched_no_eeg']}for p,a in v.items()},'candidate_minus_matched_no_eeg':difference(v),'biological_patients':len(v),'single_patient_support':len(v)==1}
    return {'patients':{p:{'matched_no_eeg':a['matched_no_eeg']}for p,a in ps.items()},'candidate_minus_matched_no_eeg':difference(ps),'montages':strata,'false_alarm_localization':localization,'recordings':686,'biological_patients':23,'observed_seconds':sum(r['duration_seconds']for r in rows),'interfile_gaps_included':False,'artifact_class_or_causal_attribution_supported':False}

def report_shape(report,h,matched):
    """Public support/schema admission only, without expected counts or errors."""
    comparison='candidate_minus_matched_no_eeg'if matched else'candidate_minus_comparator'
    c.exact(report,('patients',comparison,'montages','false_alarm_localization','recordings','biological_patients','observed_seconds','interfile_gaps_included','artifact_class_or_causal_attribution_supported'))
    c.need(type(report['recordings'])is int and report['recordings']==686 and type(report['biological_patients'])is int and report['biological_patients']==23,'complete report support')
    c.need(type(report['observed_seconds'])is int and report['observed_seconds']==sum(r['duration_seconds']for r in h['records']),'complete observed time')
    c.need(report['interfile_gaps_included']is False and report['artifact_class_or_causal_attribution_supported']is False,'exact unsupported-claim flags')
    arms=('matched_no_eeg',)if matched else('candidate','signal_reference','montage_only')
    people=sorted({r['patient_id']for r in h['records']});strata={}
    for row in h['records']:strata.setdefault(row['montage_id'],set()).add(row['patient_id'])
    metrics=('event_f1','event_sensitivity','event_precision','false_alarms_per_24_observed_hours','observed_seconds','reference_events','true_positive_events','false_alarm_events','false_negative_events','nonictal_seconds')
    counts=set(metrics[4:])
    def table(value,ids):
        c.exact(value,ids)
        for row in value.values():
            c.exact(row,arms)
            for v in row.values():
                c.exact(v,metrics)
                for k,x in v.items():
                    if x is None:c.need(k in metrics[:3],'only undefined ratio fields may be null')
                    else:
                        y=c.finite(x)
                        if k in counts:c.need(y>=0 and y==int(y),'nonnegative integral count, not bool')
    def paired(value):
        c.exact(value,('n','mean','standard_error','positive','negative','zero'))
        for k in('n','positive','negative','zero'):x=c.finite(value[k]);c.need(x>=0 and x==int(x),'nonnegative integral paired count')
        for k in('mean','standard_error'):
            if value[k]is not None:c.finite(value[k])
    def contrasts(value):
        tables=[value]if matched else list(c.exact(value,('signal_reference','montage_only')).values())
        for v in tables:
            c.exact(v,('event_f1','event_sensitivity','false_alarms_per_24_observed_hours'))
            for x in v.values():paired(x)
    table(report['patients'],people);contrasts(report[comparison]);c.exact(report['montages'],strata)
    for mid,ids in strata.items():
        v=report['montages'][mid];c.exact(v,('patients',comparison,'biological_patients','single_patient_support'))
        c.need(type(v['biological_patients'])is int and v['biological_patients']==len(ids)and type(v['single_patient_support'])is bool and v['single_patient_support']==(len(ids)==1),'complete montage support')
        table(v['patients'],ids);contrasts(v[comparison])
    expected=[(r['recording_id'],arm,r['duration_seconds'])for r in sorted(h['records'],key=lambda r:r['recording_id'])for arm in arms]
    loc=report['false_alarm_localization'];c.need(type(loc)is list and len(loc)==len(expected),'all false-alarm localization rows')
    for row,(rid,arm,duration)in zip(loc,expected):
        c.exact(row,('recording_id','arm','intervals'));c.need(row['recording_id']==rid and row['arm']==arm,'exact ordered localization support')
        c.need(type(row['intervals'])is list,'localization interval list');last=0
        for pair in row['intervals']:
            c.need(type(pair)is list and len(pair)==2,'interval pair');a,b=map(c.finite,pair);c.need(last<=a<b<=duration,'sorted in-file interval');last=b

def admit_submissions(submissions,contexts,envelope,view_bindings,hpin,mpin,h):
    """All twelve complete identities/schemas before any expected report."""
    expected=list(schedule.analyst_contexts());c.need(type(submissions)is list and len(submissions)==12 and type(contexts)is list and len(contexts)==12,'all twelve analyst outputs and closures')
    admitted=[]
    for wanted,context,submission in zip(expected,contexts,submissions):
        c.exact(submission,('schema','task_id','context','source','envelope','view_manifest','historical_submission','matched_submission'))
        c.need(submission['schema']=='neural010-complete-context-submission-v1'and submission['task_id']==c.TASK and c.typed_equal(submission['context'],wanted),'exact full ordered mode/view/replication roster')
        c.need(c.typed_equal(context['context'],wanted)and context['status']=='completed'and type(context['returncode'])is int and context['returncode']==0 and context['natural_completion']is True and context['unknown_survivors']is False,'complete separately observed current-context closure')
        c.need(c.typed_equal(submission['source'],context['sealed_source'])and c.typed_equal(submission['envelope'],envelope)and c.typed_equal(submission['view_manifest'],view_bindings[wanted['id']]),'source/envelope/view lineage')
        historical=submission['historical_submission'];c.exact(historical,('schema_version','task_id','input_sha256','report'))
        c.need(type(historical['schema_version'])is int and historical['schema_version']==1 and historical['task_id']==c.TASK and historical['input_sha256']==hpin['sha256']and type(historical['report'])is dict,'whole original historical submission schema')
        matched=submission['matched_submission'];c.exact(matched,('schema_version','task_id','historical_packet_sha256','input_sha256','report'))
        c.need(type(matched['schema_version'])is int and matched['schema_version']==1 and matched['task_id']==c.TASK and matched['historical_packet_sha256']==hpin['sha256']and matched['input_sha256']==mpin['sha256']and type(matched['report'])is dict,'whole sibling diagnostic submission schema')
        report_shape(historical['report'],h,False);report_shape(matched['report'],h,True)
        admitted.append((wanted,historical,matched))
    return admitted

def grade_all(h,m,hpin,mpin,sealpin,submissions,contexts,envelope,view_bindings,core,budget):
    admitted=admit_submissions(submissions,contexts,envelope,view_bindings,hpin,mpin,h)
    # Neither reconstruction function is called until all12 output identities
    # and complete outer/nested closure records are admitted by the caller.
    budget.check_clock();expected_matched=reconstruct_matched(h,m,hpin,sealpin,core);out=[]
    for wanted,historical,matched in admitted:
        budget.check_clock();primary=core.grade(h,hpin['sha256'],historical)
        error=core.numeric_error(matched['report'],expected_matched)
        out.append({'context':wanted,'historical_primary':primary,'matched_diagnostic':{'metric':'maximum_scaled_reconstruction_error','error':error,'within_numerical_tolerance':error<=1e-8,'lower_is_better':True},'native_waveform_understanding_established':False})
    budget.check_clock()
    return {'schema':'neural010-whole-study-grade-v1','task_id':c.TASK,'contexts':out,'complete_analyst_executions':12,'historical_evaluations':12,'matched_evaluations':12,'grading_phases':1,'scientific_detector_outcomes_separate':True,'canonical_tasks_added':0,'runtime_or_scientific_qualification_established':False}

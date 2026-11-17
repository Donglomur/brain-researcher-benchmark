"""Categorical event-domain and census helpers used by the native source caller.
Tests may exercise invented category tokens; no signal/clock/model computation.
"""
def event_domain_disposition(row):
    # Preserve inherited extract.project's domain ordering. Omission is undefined
    # on non-change-detection rows and must not be consulted for their exclusion.
    if 'change_detection' not in row['block']:return 'not_change_detection'
    if row['omitted'] not in (0,1):raise ValueError('ambiguous omission label')
    return 'not_shown_change_detection_image' if row['omitted'] else None

def exclusion_record(record,row,reason):
    eid=row['source_event']
    return {'event':eid,'behavior_event':str(record['ophys_session_id'])+':'+eid.split(':',1)[1],
       'experiment':str(record['ophys_experiment_id']),'mouse':str(record['mouse_id']),
       'session':str(record['ophys_session_id']),'container':str(record['ophys_container_id']),
       'condition':record['experience_level'],'reason':reason}

def projection_census(source_ids,events,excluded):
    source=list(source_ids);retained=[r['event'] for r in events];dropped=[r['event'] for r in excluded]
    if len(source)!=len(set(source)) or len(retained)!=len(set(retained)) or len(dropped)!=len(set(dropped)):raise ValueError('duplicate event census identity')
    if set(retained)&set(dropped) or set(source)!=set(retained)|set(dropped):raise ValueError('source event partition incomplete')
    return {'source_event_observations':len(source),'retained_event_observations':len(retained),
       'excluded_event_observations':len(dropped),'status':'complete_source_event_partition',
       'unit':'experiment-event observations; behavioral duplicates separately identified'}

"""Categorical support-table producer; actual biological execution is inactive.
Engineering controls use invented category tokens only. Unknown facts never
become zero, and absent selected-panel conditions do not describe the catalogue.
"""
from collections import Counter,defaultdict
from .design import CONDITIONS

AVAILABLE=('complete','partial','unavailable','failed','not_selected')

def _identifier(value):
    if not isinstance(value,str) or not value or len(value)>512:raise ValueError('bounded identity')
    return value

CENSUS_FIELDS=('source_event_observations','retained_event_observations','excluded_event_observations')
SUPPORT_EVIDENCE_FIELDS=('condition_support','joint_support','overlap','coverage','biological_units','overlap_scope',
    'unique_behavior_events','event_count_unit','event_dispositions','disposition_counts','event_denominators','event_denominator_summary')

def validate_membership(membership):
    # These are consumer checks, never an issuer of source-owned membership.
    if membership['population'] not in ('catalogue','secondary'):raise ValueError('population')
    records=membership['experiments'];ids=[_identifier(r['experiment']) for r in records]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate experiment membership')
    for r in records:
        for key in ('mouse','session','container','condition'):_identifier(r[key])
        if r['status'] not in AVAILABLE:raise ValueError('source availability')
        for key in CENSUS_FIELDS:
            value=r.get(key)
            if r['status']=='complete':
                if type(value)is not int or value<0:raise ValueError('complete source event census required')
            elif value is not None:raise ValueError('incomplete source denominator must remain unknown')
        if r['status']=='complete' and r[CENSUS_FIELDS[0]]!=r[CENSUS_FIELDS[1]]+r[CENSUS_FIELDS[2]]:raise ValueError('source census partition')
    return {r['experiment']:r for r in records}

def support_tables(membership,events,dispositions):
    records=validate_membership(membership);population=membership['population'];events=list(events);dispositions=list(dispositions)
    if membership.get('membership_status')!='admitted':
        if records or events or dispositions:raise ValueError('unadmitted membership may not masquerade as observed facts')
        result={key:None for key in SUPPORT_EVIDENCE_FIELDS}
        result.update({'population':population,'membership_status':'unavailable','condition_support':[
            {'condition':c,'experiments':None,'events':None,'status':'unknown_catalogue_membership' if population=='catalogue' else 'unknown_secondary_membership'} for c in CONDITIONS],
            'complete_quantitative_support':False})
        return result
    experiment_counts=Counter(r['condition'] for r in records.values())
    event_counts=Counter();joint=Counter();seen=set();per_experiment=Counter();overlap_rows=[];behavior_seen={};unique_condition=Counter()
    excluded_counts=Counter();per_excluded=Counter();reason_counts=Counter();reason_behavior=defaultdict(set);exclusion_rows=[]
    def event_join(row):
        key=_identifier(row['event']);eid=row['experiment'];_identifier(row['behavior_event'])
        if key in seen:raise ValueError('duplicate or retained/excluded event identity')
        seen.add(key)
        if eid not in records:raise ValueError('event outside source-owned population')
        rec=records[eid]
        if rec['status'] not in ('complete','partial'):raise ValueError('events from unavailable/failed experiment')
        for field in ('mouse','session','container','condition'):
            if row[field]!=rec[field]:raise ValueError('event/membership join')
        return eid,(row['mouse'],row['session'],row['behavior_event'])
    def behavior_join(key,signature):
        if key in behavior_seen and behavior_seen[key]!=signature:raise ValueError('session-plane disposition/support disagreement')
        fresh=key not in behavior_seen;behavior_seen[key]=signature;return fresh
    for row in events:
        eid,behavior_key=event_join(row)
        if row['native_image_novel'] is not None and type(row['native_image_novel']) is not bool:raise ValueError('native novelty domain')
        if row['lifetime_count_status'] not in ('known','unavailable'):raise ValueError('lifetime status')
        if row['lifetime_count_status']=='known':
            if type(row['lifetime_image_count']) is not int or row['lifetime_image_count']<0:raise ValueError('known lifetime count')
        elif row['lifetime_image_count'] is not None:raise ValueError('unavailable lifetime count must be null')
        lifetime=row['lifetime_image_count'] if row['lifetime_count_status']=='known' else 'UNAVAILABLE'
        native='unseen' if row['native_image_novel'] is True else 'seen' if row['native_image_novel'] is False else 'UNAVAILABLE'
        strata=(row['mouse'],row['session'],row['container'],row['condition'],row['image'],native,lifetime,
                row['within_session_history'],row['pre_running_bin'],row['pre_pupil_bin'],row['outcome_status'],row['neural_support'])
        joint[strata]+=1;event_counts[row['condition']]+=1;per_experiment[eid]+=1
        signature=('retained',)+tuple(repr(row.get(k)) for k in ('condition','image','native_image_novel','lifetime_image_count','within_session_history','pre_running_bin','pre_pupil_bin','outcome_flags'))
        if behavior_join(behavior_key,signature):overlap_rows.append(row);unique_condition[row['condition']]+=1
    for row in dispositions:
        eid,behavior_key=event_join(row);reason=_identifier(row['reason'])
        behavior_join(behavior_key,('excluded',row['condition'],reason))
        per_excluded[eid]+=1;excluded_counts[row['condition']]+=1;reason_counts[(row['condition'],reason)]+=1;reason_behavior[(row['condition'],reason)].add(behavior_key)
        fields=('event','behavior_event','experiment','mouse','session','container','condition','reason')
        if set(row)!=set(fields):raise ValueError('exclusion metadata fields; no neural values')
        exclusion_rows.append({k:row[k] for k in fields})
    denominators=[]
    for eid,rec in sorted(records.items()):
        complete=rec['status']=='complete';retained=per_experiment[eid];excluded=per_excluded[eid]
        if complete and (retained,excluded)!=(rec['retained_event_observations'],rec['excluded_event_observations']):raise ValueError('source-owned exclusion/retention census differs from evidence')
        denominators.append({'experiment':eid,'mouse':rec['mouse'],'session':rec['session'],'container':rec['container'],'condition':rec['condition'],
           'source_status':rec['status'],'denominator_status':'complete_source_event_partition' if complete else 'failed_source_projection_unknown_denominator' if rec['status']=='failed' else 'unavailable_source_projection_unknown_denominator',
           'source_event_observations':rec.get('source_event_observations') if complete else None,
           'retained_event_observations':retained if complete else None,'excluded_event_observations':excluded if complete else None,
           'observed_retained_prefix':retained,'observed_excluded_prefix':excluded})
    complete_membership=all(r['status']=='complete' for r in records.values())
    conditions=[]
    for condition in sorted(set(CONDITIONS)|set(experiment_counts)):
        n=experiment_counts[condition];selected=[r for r in records.values() if r['condition']==condition];complete=all(r['status']=='complete' for r in selected)
        status=('absent_in_admitted_secondary_panel' if population=='secondary' else 'absent_in_admitted_catalogue') if n==0 else ('complete_observed' if complete else 'partial_or_unavailable_events')
        conditions.append({'condition':condition,'experiments':n,'events':event_counts[condition] if complete else None,
           'observed_event_prefix':event_counts[condition],'unique_behavior_events':unique_condition[condition] if complete else None,
           'source_event_observations':sum(r['source_event_observations'] for r in selected) if complete else None,
           'excluded_event_observations':excluded_counts[condition] if complete else None,'observed_excluded_prefix':excluded_counts[condition],'status':status})
    columns=['mouse','session','container','condition','image','native_image_novel','lifetime_image_count','within_session_history','pre_running_bin','pre_pupil_bin','outcome_status','neural_support']
    joints=[{'key':dict(zip(columns,key)),'events':value} for key,value in sorted(joint.items(),key=lambda kv:repr(kv[0]))]
    coverage=[{'experiment':eid,'status':rec['status'],'observed_events':per_experiment[eid],'observed_excluded_events':per_excluded[eid],
               'mouse':rec['mouse'],'session':rec['session'],'container':rec['container'],'condition':rec['condition']} for eid,rec in sorted(records.items())]
    return {'population':population,'membership_status':'admitted_consumer_input_not_new_authority','condition_support':conditions,'joint_support':joints,
       'overlap':overlap_profiles(overlap_rows),'coverage':coverage,
       'biological_units':{'mice':len({r['mouse'] for r in records.values()}),'sessions':len({r['session'] for r in records.values()}),'containers':len({r['container'] for r in records.values()}),'experiments':len(records)},
       'event_count_unit':'experiment-event observations; unique_behavior_events deduplicates retained imaging-plane events',
       'unique_behavior_events':len(overlap_rows),'event_dispositions':sorted(exclusion_rows,key=lambda r:r['event']),
       'disposition_counts':[{'condition':key[0],'reason':key[1],'experiment_event_observations':value,'unique_behavior_events':len(reason_behavior[key])} for key,value in sorted(reason_counts.items())],
       'event_denominators':denominators,'event_denominator_summary':{
           'source_event_observations':sum(r['source_event_observations'] for r in records.values()) if complete_membership else None,
           'observed_source_event_prefix':len(events)+len(dispositions),'observed_retained_prefix':len(events),'observed_excluded_prefix':len(dispositions),
           'unique_source_behavior_events':len(behavior_seen) if complete_membership else None,'observed_unique_source_behavior_prefix':len(behavior_seen),
           'unit':'source experiment-event observations; distinct behavior IDs deduplicate planes','complete':complete_membership},
       'complete_quantitative_support':complete_membership,'source_membership_binding':membership['source_membership_binding'],
       'overlap_scope':'complete_population' if complete_membership else 'observed_prefix_only_not_population_absence'}

def overlap_profiles(rows):
    """Report separate constraint profiles; UNKNOWN never enters a matching stratum."""
    profiles=[]
    dimensions=(('image_animal',('mouse','image')),
      ('image_animal_exact_lifetime',('mouse','image','lifetime_image_count')),
      ('image_animal_session_order',('mouse','image','session','session_order')),
      ('image_animal_exact_lifetime_prestate',('mouse','image','lifetime_image_count','change','pre_running_bin','pre_pupil_bin')),
      ('image_animal_exact_lifetime_prestate_outcome',('mouse','image','lifetime_image_count','change','pre_running_bin','pre_pupil_bin','outcome_flags')),
      ('image_animal_prestate_history',('mouse','image','change','pre_running_bin','pre_pupil_bin','within_session_history')),
      ('image_animal_prestate_history_outcome',('mouse','image','change','pre_running_bin','pre_pupil_bin','within_session_history','outcome_flags')))
    for contrast in ('Familiar_vs_Novel1','Familiar_vs_NovelRepeated','native_seen_vs_unseen'):
      for name,fields in dimensions:
        groups=defaultdict(lambda:{'left':[],'right':[]});unknown=Counter();eligible=Counter()
        for row in rows:
            if contrast=='Familiar_vs_Novel1':side={'Familiar':'left','Novel 1':'right'}.get(row['condition'])
            elif contrast=='Familiar_vs_NovelRepeated':side={'Familiar':'left','Novel >1':'right'}.get(row['condition'])
            else:side='right' if row['native_image_novel'] is True else 'left' if row['native_image_novel'] is False else None
            if side is None:continue
            unavailable=[k for k in fields if row.get(k) is None or (k=='lifetime_image_count' and row['lifetime_count_status']!='known') or (k=='outcome_flags' and row['outcome_status']!='known')]
            if unavailable:
                for k in unavailable:unknown[k]+=1
                continue
            key=tuple(tuple(row[k]) if isinstance(row[k],list) else row[k] for k in fields)
            groups[key][side].append(row['event']);eligible[side]+=1
        matched=sum(min(len(g['left']),len(g['right'])) for g in groups.values())
        profiles.append({'contrast':contrast,'constraints':name,'fields':list(fields),'eligible_left':eligible['left'],'eligible_right':eligible['right'],
                         'one_to_one_pair_capacity':matched,'overlap_strata':sum(bool(g['left'] and g['right']) for g in groups.values()),
                         'unavailable_by_field':dict(sorted(unknown.items())),
                         'status':'unavailable_required_fields' if not groups and unknown else 'observed_overlap' if matched else 'observed_no_overlap',
                         'causal_identification':False})
    return profiles

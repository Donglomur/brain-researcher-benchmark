"""Complete protected source/run/event census before any neural projection.

Custodian qualification is a separately selected input, not fabricated by code.
Native samples join a qualified explicit event map or exact offset transform;
raw and concatenated clocks are never silently assumed equal.
"""
from .io import need,exact,identity,canonical,pin_shape
from .contract import ROSTER

def integer(v):return type(v)is int and v>=0

def validate_census(cohort,native_manifest,census,qualification,binding):
    need(census['schema']=='n097-complete-run-event-census-v2'and census['contract']==binding,'Selected complete census contract')
    need(census['cohort_identity']==identity(canonical(cohort))and census['native_manifest_identity']==identity(canonical(native_manifest)),'Exact cohort and whole native source union')
    need(qualification['status']=='independently_qualified'and qualification['census_identity']==identity(canonical(census))and qualification['cohort_identity']==census['cohort_identity']and qualification['native_manifest_identity']==census['native_manifest_identity'],'Independent exact custodian census/clock qualification')
    need(qualification['original_producer_and_rejection_history_verified']is True and qualification['clock_transform_verified']is True,'Original source/clock evidence required, not a placeholder reconciliation')
    names={x['path']for x in native_manifest}
    need(len(names)==len(native_manifest)and names,'Unique complete native source identities')
    need(set(census['part_roles'])==names and all(v in ('epochs','events','metadata','clock_provenance','preprocessing_provenance')for v in census['part_roles'].values()),'Every source member has a declared scientific role')
    need([x['source_person']for x in census['members']]==list(ROSTER),'Exact33 census members')
    expected={};dispositions=[];used=set()
    for member,entry in zip(cohort['members'],census['members']):
        person=member['source_person'];parts=set(member['source_parts'])
        need(parts==set(entry['parts'])and parts<=names and len(entry['parts'])==len(parts),'Exact selected person source-part union')
        need([x['run']for x in entry['runs']]==member['runs'],'Every original ten-run disposition in declared order')
        member_used=set();selections=set()
        for run in entry['runs']:
            runparts=set(run['source_parts']);need(runparts and runparts<=parts and len(runparts)==len(run['source_parts']),'Exact unique run source-part union')
            member_used.update(runparts);used.update(runparts)
            pin_shape(run['original_census_evidence']);pin_shape(run['clock_transform']['source_evidence'])
            need(run['disposition']in ('included','empty','excluded'),'Explicit original run disposition')
            events=run['events'];need(type(events)is list and run['original_event_count']==len(events),'Every original onset event and rejection retained')
            need(len({e['event_id']for e in events})==len(events)and all(type(e['event_id'])is str and e['event_id']for e in events),'Unique original run event identities')
            clock=run['clock_transform'];need(clock['kind']in ('integer_sample_offset','explicit_event_pairs'),'Qualified declared clock transform')
            if clock['kind']=='integer_sample_offset':
                need(type(clock['offset'])is int and clock['raw_sample_units']==clock['native_sample_units']=='samples_at_identical_rate','Explicit same-rate offset, never guessed equality')
                need(type(clock['sample_rate_hz'])in (int,float)and __import__('math').isfinite(clock['sample_rate_hz'])and clock['sample_rate_hz']>0,'Qualified physical clock rate')
            else:
                pairs=clock['pairs'];need(len(pairs)==len(events)and {x['event_id']for x in pairs}=={e['event_id']for e in events},'Complete qualified explicit original event mapping')
                need(len({x['event_id']for x in pairs})==len(pairs),'No duplicate clock mappings')
                pairs={x['event_id']:x for x in pairs}
            retained=0;rejected=0
            for event in events:
                need(integer(event['raw_sample'])and integer(event['native_sample'])and type(event['onset_trigger'])is int,'Typed observed source clocks/onset')
                if clock['kind']=='integer_sample_offset':need(event['native_sample']==event['raw_sample']+clock['offset'],'Exact qualified original sample-offset transform')
                else:need(pairs[event['event_id']]['raw_sample']==event['raw_sample']and pairs[event['event_id']]['native_sample']==event['native_sample'],'Exact qualified raw/native event pair')
                need(event['disposition']in ('retained','rejected')and type(event['reason'])is str,'Every original retained/rejected event disposition')
                if event['disposition']=='retained':
                    need(integer(event['epoch_selection'])and event['epoch_selection']not in selections and not event['reason'],'Unique retained native selection and no fabricated rejection')
                    selections.add(event['epoch_selection']);retained+=1
                    key=(person,'V1',run['run'],event['raw_sample'],event['epoch_selection'])
                    need(key not in expected,'Unique full retained original event join')
                    expected[key]={'native_sample':event['native_sample'],'onset_trigger':event['onset_trigger'],'source_parts':run['source_parts'],'event_id':event['event_id']}
                else:
                    need(event['epoch_selection']is None and event['reason'],'Original rejection reason and absent retained selection');rejected+=1
            need(run['retained_count']==retained and run['rejected_count']==rejected,'Original run counts exactly reconcile')
            if run['disposition']=='empty':need(not events and run['reason'],'Empty original run requires original evidence/reason')
            elif run['disposition']=='excluded':need(retained==0 and run['reason'],'Excluded original run cannot contain projected retained epochs')
            else:need(events and not run['reason'],'Included original run has complete event census')
            dispositions.append({'source_person':person,'run':run['run'],'disposition':run['disposition'],'original_event_count':len(events),'retained_count':retained,'rejected_count':rejected,'reason':run['reason'],'original_census_evidence':run['original_census_evidence']})
        need(member_used==parts,'No declared person source part disappears from run census')
    need(used==names and len(dispositions)==330,'All330 person/runs and complete selected native union')
    return {'expected_retained':expected,'run_dispositions':dispositions,'identity':identity(canonical(census)),'qualification_identity':identity(canonical(qualification))}

def validate_observed(row,census_index):
    key=(row['source_person'],row['visit'],row['run'],row['raw_sample'],row['epoch_selection'])
    need(key in census_index['expected_retained'],'Observed row belongs to full qualified original retained census')
    expected=census_index['expected_retained'][key]
    need(row['native_sample']==expected['native_sample']and row['onset_trigger']==expected['onset_trigger'],'Actual native sample/onset agrees with qualified original clock mapping')
    need(row['source_parts']==expected['source_parts'],'Exact original run-part lineage, not a subset')
    return key

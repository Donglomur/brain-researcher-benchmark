"""Evaluator-only queries with full source universe and documented-session masks."""
import copy
from reward_common import need,object_sha256,unique_records
from information import ENDPOINT_CLOCK,public_case
from support import source_inventory,finish_support,KEYS,coverage


def assemble(prepared,registry,baseline_provider,feature_provider,density_spec):
    """Register complete source metadata first; availability never deletes a row.

    Registry documented_sessions contains all source trial identities, including
    records whose modality is unavailable. Session ordinal comes from that fixed
    source chronology. Full reproduction observations remain unchanged.
    """
    inventory=source_inventory(registry)
    animals=unique_records(prepared['animals'],['animal_id']);source_animals={a['animal_id']:a for a in registry}
    need({k[0] for k in animals}<=set(source_animals),'No added unregistered biological animal')
    observed={}
    for (aid,),animal in animals.items():
        need(animal['condition']==source_animals[aid]['condition'],'Biological condition binding')
        for row in animal['trials']:
            key=(aid,row['session_number'],row['trial_id'])
            need(key not in observed,'Unique source trial observations');observed[key]=row
    inventory_trials={(r['animal_id'],r['session'],r['trial_id']) for r in inventory['records']}
    need(set(observed)<=inventory_trials,'Every observed trial belongs to complete source registry')
    cases=[];public=[];records=[]
    for original in inventory['records']:
        record=copy.deepcopy(original)
        if record['status']!='eligible_pending':records.append(record);continue
        aid=record['animal_id'];ep=record['endpoint'];key=(aid,record['session'],record['trial_id'])
        row=observed.get(key);reason=None
        if row is None:reason='source_trial_record_absent'
        else:
            need(row['kind']==record['kind'] and row['delivered']==record['delivered'] and
                 row['source']==record['source_pin'],'Source trial/event/modality provenance')
        if reason:
            record.update(status='source_unavailable',reason=reason);records.append(record);continue
        clock=ENDPOINT_CLOCK[ep]
        when=row['cue_on'] if clock=='cue' else row.get('consumption_onset') if clock=='consumption' else row['outcome_time']
        c={k:record[k] for k in KEYS}
        c.update(case_id=record['case_id'],prediction_clock=clock,allowed_prediction_clock=clock,
                 prediction_time=when,behavior_only_designated=record['behavior_only_designated'])
        if ep in ('L','Qminus'):
            if row.get('A') is None or row.get('B') is None:reason='missing_count_window'
            elif type(row['A']) is not int or type(row['B']) is not int or min(row['A'],row['B'])<0:reason='invalid_count_support'
            else:c.update(target=row['A'],B=row['B'])
        elif ep in ('F','M'):
            behavior=row.get('behavior',{})
            if behavior.get('status')!='computed':reason='missing_video_or_calibration'
            else:c['target']=behavior['cue_freezing' if ep=='F' else 'cue_motion']
        else:
            response=row.get({'C':'cue_da','R':'reward_da','O':'omission_da','V':'cue_da'}[ep],{})
            trace=response.get('target_trace')
            if trace is None or when is None:
                reason=response.get('reason','missing_native_target_support')
                if reason=='video_absent':reason='missing_video_or_calibration'
            elif trace['fit_scope'] not in ('training_prefix','invented'):
                reason='retrospective_preprocessing_cannot_satisfy_prospective_information_boundary'
            else:
                need(trace['fit_scope']!='invented' or prepared['branch']=='engineering','Invented signal only in engineering')
                c.update(target=trace['values'],times=[t-when for t in trace['times']],
                         window=[t-when for t in trace['window']],max_gap=trace['max_gap'],
                         density_family=density_spec['family'],density_df=density_spec.get('df'))
        if reason:
            record.update(status='source_unavailable',reason=reason);records.append(record);continue
        record.update(status='available',reason=None);c['support_row_sha256']=object_sha256(record)
        records.append(record)
        features=feature_provider.features(c,row,animals[(aid,)])
        pub=public_case(c,features);c['baseline_prediction']=baseline_provider.predict(pub)
        cases.append(c);public.append(pub)
    support=finish_support(inventory,records)
    unavailable=[copy.deepcopy(r) for r in records if r['status']=='source_unavailable']
    population_coverage={}
    for key,expected in inventory['populations']['expected_animals_by_endpoint_condition'].items():
        ep,cond=key.split(':',1);population_coverage[key]=coverage(records,ep,[cond],expected)
    return {'private_cases':cases,'public_queries':public,'required_unscorable':unavailable,
            'support_manifest':support,'source_populations':inventory['populations'],
            'expected_source_queries':len(records),
            'eligible_queries':sum(r['status'] in ('available','source_unavailable') for r in records),
            'available_queries':len(cases),'out_of_horizon_queries':sum(r['status']=='out_of_horizon' for r in records),
            'inapplicable_queries':sum(r['status']=='inapplicable' for r in records),
            'complete':not unavailable and all(v['full_source_support'] for v in population_coverage.values()),
            'population_coverage':population_coverage,'available_queries_ready':True,'scientific_qualification':False,
            'support_registration_required':'Commit exact support manifest before candidate predictions; bind it in scoring.'}

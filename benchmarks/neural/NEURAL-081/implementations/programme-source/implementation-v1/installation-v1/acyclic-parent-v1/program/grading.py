"""Protected target-last full-study assessment using unchanged canonical arithmetic."""
import math
from pathlib import Path
import common as c
import protocol as p
import schedule,metrics

def panel_key(identity):
    role=identity['role']
    if role=='candidate':return (role,identity['mode'],identity['replication'],identity['view'])
    return (role,identity['handle'],identity['view'])

def admit_panels(index,panel_descriptors,access,source):
    p.validate_index(index);wanted=list(schedule.panels());c.need(type(panel_descriptors)is list and len(panel_descriptors)==240,'every complete candidate/reference/analytic panel')
    groups={};admitted=[]
    for descriptor,identity in zip(panel_descriptors,wanted):
        body=access.json(descriptor);c.exact(body,('schema','identity','submission','producer_closures','source','generation','role_support'))
        c.need(body['schema']=='neural081_closed_panel_v1'and c.typed_equal(body['identity'],identity)and c.typed_equal(body['source'],source)and body['generation']==index['preparation_generation'],'exact typed complete source-bound panel identity')
        c.need(type(body['producer_closures'])is list and body['producer_closures'],'all actual producer closures bound before target')
        ids=[r['canonical_id']for r in index['rows']if r['person']==identity['person']]
        c.need(body['role_support']==ids,'complete person support in canonical order')
        rows=metrics.submission_rows(access.json(body['submission']),ids)
        key=panel_key(identity);c.need(identity['person']not in groups.setdefault(key,{}),'one exact person panel per condition');groups[key][identity['person']]=rows
        admitted.append({'panel':descriptor,'submission':body['submission'],'identity':identity,'producer_closures':body['producer_closures']})
    c.need(len(groups)==24 and all(set(v)==set(c.PEOPLE)for v in groups.values()),'24 complete ten-person condition groups')
    return groups,admitted

def protected_labels(index,access):
    """Only called after independent full graph and all240 bodies are admitted."""
    c.need(access.role=='G5','separately admitted protected grader role')
    support=access.json(index['protected_support_descriptor']);assessment=access.json(index['protected_assessment_descriptor'])
    c.exact(support,('schema','task_id','preparation_generation','protocol_source','source_inventory','people','class_ids','canonical_channels','rows','private_boundary_evidence','original_bad_channel_flags'))
    c.need(support['schema']=='neural081_support_v1'and support['task_id']==c.TASK and support['preparation_generation']==index['preparation_generation'],'actual complete protected support')
    for a,b in [('protocol_source','protocol_source'),('source_inventory','source_inventory_descriptors'),('people','people'),('class_ids','class_ids'),('canonical_channels','canonical_channels')]:c.need(c.typed_equal(support[a],index[b]),'protected/label-free '+a+' correspondence')
    c.need(c.typed_equal(support['private_boundary_evidence'],index['support_disposition']['physical_annotation_authority']),'same admitted original physical/annotation evidence')
    c.exact(assessment,('schema','task_id','preparation_generation','rows'));c.need(assessment['schema']=='neural081_assessment_target_v1'and assessment['task_id']==c.TASK and assessment['preparation_generation']==index['preparation_generation'],'same complete protected assessment generation')
    c.need(len(support['rows'])==len(assessment['rows'])==len(index['rows']),'full three-way support counts')
    labels=[];people=[];ids=[]
    for public,private,target in zip(index['rows'],support['rows'],assessment['rows']):
        c.exact(private,('person','canonical_id','source_event_index','source_onset_sample','processed_condition','private_label','source_file','window_descriptor','physical_boundary_disposition'))
        comparison={('source_file_descriptor'if k=='source_file'else k):v for k,v in private.items()if k!='private_label'}
        c.need(c.typed_equal(comparison,public),'actual exact private/label-free row, including physical source/window')
        c.exact(target,('canonical_id','person','label'));label=private['private_label'];c.need(type(label)is int and label in c.CLASSES and type(target['label'])is int and target['label']==label and target['canonical_id']==public['canonical_id']and target['person']==public['person'],'both full protected label bodies agree exactly')
        labels.append(label);people.append(public['person']);ids.append(public['canonical_id'])
    c.need(all({label for label,person in zip(labels,people)if person==p0}==set(c.CLASSES)for p0 in c.PEOPLE),'all twelve original classes in every full person')
    flags=support['original_bad_channel_flags'];c.need(type(flags)is list and len(flags)==10,'complete private bad-channel roster')
    for person,row in zip(c.PEOPLE,flags):
        c.exact(row,('person','bad_channels'));values=row['bad_channels']
        c.need(row['person']==person and type(values)is list and all(type(x)is str and x for x in values)and len(set(values))==len(values),'exact private original bad flags, never fabricated empties')
    return ids,people,labels,flags

def bad_channel_prevalence(flags):
    c.need([r['person']for r in flags]==list(c.PEOPLE),'same complete private ten-person source roster')
    any_flag=sum(bool(r['bad_channels'])for r in flags);eeg_flag=sum(any(x in p.CHANNELS for x in r['bad_channels'])for r in flags)
    return {'people':10,'people_with_any_original_bad_flag':any_flag,'proportion_with_any_original_bad_flag':any_flag/10,'people_with_any_canonical_eeg_bad_flag':eeg_flag,'proportion_with_any_canonical_eeg_bad_flag':eeg_flag/10,'per_person':flags,'canonical_eeg_channel_person_counts':[{'channel':name,'people_flagged':sum(name in r['bad_channels']for r in flags)}for name in p.CHANNELS],'channels_dropped_or_interpolated':False,'released_after_complete_target_last_barrier':True}

def complete_rows(group):return [row for person in c.PEOPLE for row in group[person]]

def subtract(left,right):
    c.need([x['participant']for x in left['per_participant']]==list(c.PEOPLE)==[x['participant']for x in right['per_participant']],'paired biological person order')
    rows=[]
    for a,b in zip(left['per_participant'],right['per_participant']):rows.append({'person':a['participant'],'balanced_accuracy_difference':a['balanced_accuracy']-b['balanced_accuracy'],'log_loss_difference':a['log_loss']-b['log_loss']})
    return {'per_person':rows,'participant_macro_balanced_accuracy_difference':math.fsum(x['balanced_accuracy_difference']for x in rows)/10,'participant_macro_log_loss_difference':math.fsum(x['log_loss_difference']for x in rows)/10}

def score(index,groups,labels,people,strongest):
    results={};diagnostics={}
    for key,group in groups.items():
        rows=complete_rows(group);results[key]=metrics.numerical_score(rows,labels,people);diagnostics[key]=metrics.descriptive_diagnostics(rows,labels,people,results[key])
    for view in c.VIEWS:
        rows=[]
        for person in c.PEOPLE:
            handle=strongest[(view,person)];c.need(handle in p.FAMILIES,'training-selected strongest source handle');rows.extend(groups[('reference',handle,view)][person])
        results[('reference','STRONGEST_TRAINING_SELECTED',view)]=metrics.numerical_score(rows,labels,people)
        diagnostics[('reference','STRONGEST_TRAINING_SELECTED',view)]=metrics.descriptive_diagnostics(rows,labels,people,results[('reference','STRONGEST_TRAINING_SELECTED',view)])
    contrasts=[]
    for rep in c.REPS:
        for view in c.VIEWS:
            contrasts.append({'contrast':'I-minus-F','replication':rep,'view':view,**subtract(results[('candidate','I',rep,view)],results[('candidate','F',rep,view)])})
        for mode in c.MODES:
            contrasts.append({'contrast':'EEG-minus-ZERO','replication':rep,'mode':mode,**subtract(results[('candidate',mode,rep,'EEG')],results[('candidate',mode,rep,'ZERO')])})
    comparisons=[]
    for mode in c.MODES:
        for rep in c.REPS:
            for view in c.VIEWS:
                for handle in (*p.HANDLES,'STRONGEST_TRAINING_SELECTED'):
                    comparisons.append({'mode':mode,'replication':rep,'view':view,'comparator':handle,**subtract(results[('candidate',mode,rep,view)],results[('reference',handle,view)])})
                for handle in ('UNIFORM','LAPLACE'):comparisons.append({'mode':mode,'replication':rep,'view':view,'comparator':handle,**subtract(results[('candidate',mode,rep,view)],results[('analytic',handle,view)])})
    means=[]
    for mode in c.MODES:
        for view in c.VIEWS:
            values=[results[('candidate',mode,rep,view)]for rep in c.REPS]
            person_means=[{'participant':person,'balanced_accuracy':math.fsum(v['per_participant'][j]['balanced_accuracy']for v in values)/3,'log_loss':math.fsum(v['per_participant'][j]['log_loss']for v in values)/3}for j,person in enumerate(c.PEOPLE)]
            means.append({'mode':mode,'view':view,'replications':list(c.REPS),'participant_macro_balanced_accuracy':math.fsum(x['participant_macro_balanced_accuracy']for x in values)/3,'participant_macro_log_loss':math.fsum(x['participant_macro_log_loss']for x in values)/3,'balanced_accuracy_replications':metrics.replication_summary([x['participant_macro_balanced_accuracy']for x in values]),'log_loss_replications':metrics.replication_summary([x['participant_macro_log_loss']for x in values]),'per_person_replication_mean':person_means,'leave_one_person_out_aggregation_sensitivity':metrics.aggregation_sensitivity(person_means)})
    paired_means=[]
    for kind,field,conditions in(('I-minus-F','view',c.VIEWS),('EEG-minus-ZERO','mode',c.MODES)):
        for condition in conditions:
            values=[next(row for row in contrasts if row['contrast']==kind and row['replication']==rep and row[field]==condition)for rep in c.REPS]
            person_means=[{'participant':person,'balanced_accuracy_difference':math.fsum(v['per_person'][j]['balanced_accuracy_difference']for v in values)/3,'log_loss_difference':math.fsum(v['per_person'][j]['log_loss_difference']for v in values)/3}for j,person in enumerate(c.PEOPLE)]
            ba=metrics.replication_summary([v['participant_macro_balanced_accuracy_difference']for v in values]);ll=metrics.replication_summary([v['participant_macro_log_loss_difference']for v in values])
            paired_means.append({'contrast':kind,field:condition,'replications':list(c.REPS),'participant_macro_balanced_accuracy_difference':ba['mean'],'participant_macro_log_loss_difference':ll['mean'],'balanced_accuracy_replications':ba,'log_loss_replications':ll,'per_person_replication_mean':person_means,'leave_one_person_out_aggregation_sensitivity':metrics.aggregation_sensitivity(person_means,'balanced_accuracy_difference','log_loss_difference')})
    return {'conditions':[{'key':list(key),'metrics':value,'descriptive':diagnostics[key]}for key,value in results.items()],'replication_means':means,'paired_contrasts':contrasts,'mean_paired_contrasts':paired_means,'candidate_comparisons':comparisons,'uncertainty_scope':'Ten fixed biological people with overlapping LOPO training; descriptive aggregation sensitivity and author-replication variation, not independent confidence intervals or significance tests.'}

def execute(request,access,source,output):
    # Source-owned independent graph admission is concrete, not supplied by a
    # caller callback or a candidate success flag. It reopens exact safe metadata.
    import closure
    c.exact(request,('schema','source','index','study','output_root'))
    c.need(request['schema']=='neural081_protected_grade_request_v1'and c.typed_equal(request['source'],source)and request['output_root']==str(output)and access.role=='G5','exact selected protected operation')
    access._protected(request['index']['path'])
    index=p.validate_index(access.json(request['index']))
    c.need([str(x)for x in access.protected]==[index[k]['path']for k in ('protected_support_descriptor','protected_assessment_descriptor')],'both exact global protected operands guarded through pre-grade admission')
    from custody import Access
    protected=[index[k]for k in ('protected_support_descriptor','protected_assessment_descriptor')]
    for d in protected:access.admit(d)
    denied={d['path']for d in protected}
    pregrade=Access('G4',[d for path,d in access.allowed.items()if path not in denied],protected,access.budget,opaque=access.opaque)
    graph=closure.admit(request['study'],index,pregrade,source)
    groups,panels=admit_panels(index,graph['panels'],pregrade,source)
    # This boundary is after ALL source/producer/case/action/native/panel checks.
    ids,people,labels,source_flags=protected_labels(index,access)
    result=score(index,groups,labels,people,graph['strongest'])
    report={'schema':'neural081_complete_assessment_v4','task_id':c.TASK,'source':source,'generation':index['preparation_generation'],'index':request['index'],'study':request['study'],'admitted_panels':panels,'complete_counts':p.counts(index),'primary_metric':'participant_macro_balanced_accuracy','assessment':result,'status':'provisional_until_independent_whole_controller_natural_exit','scope':'Descriptive instructed-excerpt decoding in these ten people and source conditions; single-query-transductive candidates versus fixed inductive references. Numerical improvements are not reasoning-only attribution, mental-state verification, pure imagery, causal or neural-mechanism proof. LOPO training sets overlap and query trials are not independent biological samples.','protected_reads_after_full_barrier':True,'provider_or_candidate_resume_allowed':False}
    report['original_bad_channel_prevalence']=bad_channel_prevalence(source_flags)
    access.budget.check_clock();return c.publish_json(output/'RESULT.json',report,access.budget)

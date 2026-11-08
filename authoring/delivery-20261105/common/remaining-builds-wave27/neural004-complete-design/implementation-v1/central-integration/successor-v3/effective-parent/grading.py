"""Independent protected scoring; reconstruction, prediction and reasoning stay distinct."""
import math
from .common import (PEOPLE,PREDICTION_POLICIES,fields,need,probability,finite,
    integer,same_roster,pin,check_pin)
from .investigator import forecast_rows

class ReleaseBarrier:
    """Operator-side complete roster, never an actor-provided ready Boolean."""
    def __init__(self,contexts,reference_contexts,authorities,ledger):
        need(len(contexts)==208 and len(reference_contexts)==52,'full208 actors plus52 reference slots')
        need(len(set(contexts))==208 and len(set(reference_contexts))==52 and not(set(contexts)&set(reference_contexts)),'unique actor/reference contexts')
        self.expected=set(contexts)|set(reference_contexts);self.closed={};self.authorities=authorities;self.ledger=ledger;self.release=None
        self.registered={}
    def register(self,context,disposition,limits,operation_qualifications):
        need(context in self.expected and context not in self.registered,'one source-owned expected context')
        need(set(operation_qualifications)==set(disposition['operation_bindings']),'every actual operation independently qualified before target barrier')
        for result in operation_qualifications.values():need(result['qualified_custody'] is True,'source-verified operation custody')
        self.registered[context]={'disposition_pin':pin(disposition),'limits':dict(limits),'operation_qualifications':operation_qualifications}
    def close(self,context,disposition,closure_envelope):
        need(context in self.expected and context not in self.closed,'one complete context disposition')
        fields(disposition,('context','status','seal_pin','history_pin','operation_bindings'))
        need(disposition['context']==context and disposition['status'] in ('sealed','failed','blocked'),'honest closed disposition')
        check_pin(disposition['history_pin'])
        if disposition['status']=='sealed':check_pin(disposition['seal_pin'])
        else:need(disposition['seal_pin'] is None,'failed/blocked context has no fabricated forecast')
        need(context in self.registered and self.registered[context]['disposition_pin']==pin(disposition),'automatic actual-job qualification and exact expected disposition')
        verified=self.authorities.verify(closure_envelope,'observer','operation_closure',pin(disposition))
        f=verified['facts'];fields(f,('all_context_processes_closed','all_provider_requests_closed','no_feedback_released',
            'isolation_receipt','source_view_receipt','operation_bindings','operation_qualifications_pin','physical_resources','origin_ns','finished_ns','unknown'))
        need(all(f[k] is True for k in ('all_context_processes_closed','all_provider_requests_closed','no_feedback_released')) and not f['unknown'],'independent full context closure before target release')
        need(f['operation_bindings']==disposition['operation_bindings'],'all actual context operation bindings')
        expected=self.registered[context]
        need(f['operation_qualifications_pin']==pin(expected['operation_qualifications'],8*1048576),'complete joined per-job qualifications, no opaque work-cost promise')
        from .context_budget import bounded_resources,PHYSICAL_CAPS
        fields(f['physical_resources'],PHYSICAL_CAPS)
        for value in f['physical_resources'].values():integer(value)
        need(type(f['origin_ns']) is int and type(f['finished_ns']) is int and self.ledger.origin<=f['origin_ns']<=f['finished_ns']<self.ledger.closeout,'original bounded context clocks')
        over=[k for k,cap in PHYSICAL_CAPS.items() if f['physical_resources'][k]>expected['limits'][cap]]
        if disposition['status']=='sealed':
            need(f['finished_ns']<self.ledger.scientific,'successful context within original science deadline')
            bounded_resources(f['physical_resources'],expected['limits'])
        for k in ('isolation_receipt','source_view_receipt'):check_pin(f[k])
        self.closed[context]={'disposition':disposition,'qualification':verified['envelope_pin'],
            'operation_qualifications':expected['operation_qualifications'],'physical_resources':f['physical_resources'],'resource_failures':over}
    def open(self,target_bundle,release_envelope):
        need(self.release is None and set(self.closed)==self.expected,'all contexts closed before any scorer answer release')
        fields(target_bundle,('answers','context_answer_maps','source_admission_pin'));check_pin(target_bundle['source_admission_pin'])
        self.target_bundle_pin=pin(target_bundle,32*1048576)
        subject={'contexts_pin':pin(self.closed,8*1048576),'target_bundle_pin':self.target_bundle_pin}
        verified=self.authorities.verify(release_envelope,'operator','target_release',subject)
        fields(verified['facts'],('prediction_contexts_closed','no_live_actor_feedback_route','protected_scorer_identity','release_ns'))
        need(verified['facts']['prediction_contexts_closed'] is True and verified['facts']['no_live_actor_feedback_route'] is True,'target release exclusion')
        check_pin(verified['facts']['protected_scorer_identity']);need(self.ledger.origin<=verified['facts']['release_ns']<=self.ledger.tick(),'original target-release chronology')
        self.release=verified;return verified

def person_loss(forecasts,answers):
    need(type(answers) is list and answers,'nonempty complete person answers')
    target={}
    for row in answers:
        fields(row,('id','value'));need(row['id'] not in target,'unique target support');y=finite(row['value']);need(.025<y<1,'exact logged contrast domain');target[row['id']]=y
    predictions=forecast_rows(forecasts,list(target));errors=[]
    for row in predictions:
        value=(row['prediction']-target[row['id']])**2;need(math.isfinite(value),'finite squared error')
        errors.append({'id':row['id'],'squared_error':value})
    return {'trial_errors':errors,'n':len(errors),'mse':math.fsum(x['squared_error'] for x in errors)/len(errors)}

def grade_prediction_panels(barrier,actor_panels,reference_panels,target_bundle):
    need(type(barrier) is ReleaseBarrier and barrier.release is not None,'independently opened protected target barrier')
    need(pin(target_bundle,32*1048576)==barrier.target_bundle_pin,'exact independently released answers and private identity maps')
    answers=target_bundle['answers'];maps=target_bundle['context_answer_maps']
    fields(actor_panels,PREDICTION_POLICIES);fields(reference_panels,('B','N'));fields(answers,PEOPLE)
    results={};references={}
    def one_panel(panel):
        fields(panel,PEOPLE);rows=[];failures=[]
        for person in PEOPLE:
            record=panel[person];fields(record,('context','status','forecasts','seal','answer_map'))
            need(record['context'] in barrier.closed,'context physically closed')
            disposition=barrier.closed[record['context']]['disposition'];need(record['status']==disposition['status'],'same closed context status')
            if record['status']!='sealed':failures.append({'person':person,'status':record['status']});continue
            need(pin(record['seal'],8*1048576)==disposition['seal_pin'],'same actual forecast seal')
            mapping=record['answer_map'];need(type(mapping) is list and mapping==maps[record['context']],'released exact physical-to-opaque map')
            canonical={a['id']:a['value'] for a in answers[person]}
            need(len(canonical)==len(answers[person]),'unique canonical answers')
            same_roster([x['source_id'] for x in mapping],list(canonical));need(len({x['id'] for x in mapping})==len(mapping),'bijective opaque answer map')
            local=[{'id':x['id'],'value':canonical[x['source_id']]} for x in mapping]
            forecast_pin=record['seal'].get('forecast_pin',record['seal'].get('seal',{}).get('forecast_pin'))
            check_pin(forecast_pin);need(pin(record['forecasts'],8*1048576)==forecast_pin,'forecast bytes exactly sealed')
            rows.append({'person':person,**person_loss(record['forecasts'],local)})
        if failures:return {'status':'incomplete','person_results':rows,'failures':failures,'macro_mse':None}
        need([r['person'] for r in rows]==list(PEOPLE),'all26 person scoring units')
        loss=math.fsum(r['mse'] for r in rows)/26;need(math.isfinite(loss),'finite person-macro score')
        leave=[math.fsum(r['mse'] for r in rows if r['person']!=p)/25 for p in PEOPLE]
        return {'status':'complete','person_results':rows,'failures':[],'macro_mse':loss,'display_percentage_point_rmse':100*math.sqrt(loss),
            'descriptive_delete_one_person_macro':leave,'population_confidence_interval':None,'unit':'fractional contrast squared'}
    for family,panel in reference_panels.items():references[family]=one_panel(panel)
    for policy,panel in actor_panels.items():
        result=one_panel(panel);result['versus_behavior_reference']=None
        if result['status']==references['B']['status']=='complete':
            diff=[{'person':p,'behavior_minus_actor_mse':b['mse']-a['mse']} for p,b,a in zip(PEOPLE,references['B']['person_results'],result['person_results'])]
            result['versus_behavior_reference']={'people':diff,'person_macro_difference':math.fsum(x['behavior_minus_actor_mse'] for x in diff)/26,
                'positive_neural_gain_required':False,'mutual_information':False}
        results[policy]=result
    return {'schema':'neural004_prediction_grade_v1','release_pin':barrier.release['envelope_pin'],'actors':results,'references':references,
        'whole_prediction_complete':all(r['status']=='complete' for r in list(results.values())+list(references.values())),
        'whole_study_qualified':False,'reference_empirical_competence':'requires independent full reference diagnostics review'}

def validate_reconstruction_reference(reference,tolerance_policy):
    """Admit the independent report/policy before candidate-specific grading."""
    fields(tolerance_policy,('source_pin','rules'));check_pin(tolerance_policy['source_pin'])
    need(reference['schema']=='neural004_report_v1' and len(reference['people'])==26,'full independent reconstruction report')
    need([r['person'] for r in reference['people']]==list(PEOPLE),'ordered complete independent reconstruction support')
    # Presence of these trusted report fields is an admission requirement.
    reference['dataset_sha256'];reference['mode']
    for row in reference['people']:
        for key in ('n_trials','design_rank','negative_interval_trials'):row[key]
        need(len(row['metrics'])==114 and set(row['metrics'])==set(tolerance_policy['rules']),'all114 independent rules/cells')
        for name,expected in row['metrics'].items():
            fields(expected,('value','support','reason'))
            rule=tolerance_policy['rules'][name];fields(rule,('unit','absolute_tolerance','relative_tolerance'))
            need(rule['unit'] in ('ms','nats_per_trial'),'independently frozen source units')
            atol=finite(rule['absolute_tolerance']);rtol=finite(rule['relative_tolerance'])
            need(atol>=0 and rtol>=0,'nonnegative independently selected tolerances')
            if expected['value'] is not None:finite(expected['value'])
    return reference

def compare_reconstruction(candidate,reference,tolerance_policy):
    """All26×114 declared cells, independently selected per-quantity units/tolerances."""
    validate_reconstruction_reference(reference,tolerance_policy)
    for report in (candidate,reference):
        need(report['schema']=='neural004_report_v1' and len(report['people'])==26,'full reconstruction report')
        need([r['person'] for r in report['people']]==list(PEOPLE),'ordered complete original reconstruction support')
    need(candidate['dataset_sha256']==reference['dataset_sha256'] and candidate['mode']==reference['mode'],'same source and report mode')
    outcomes=[]
    for a,b in zip(candidate['people'],reference['people']):
        for k in ('n_trials','design_rank','negative_interval_trials'):need(a[k]==b[k],'same structural reconstruction field '+k)
        need(len(b['metrics'])==114 and set(a['metrics'])==set(b['metrics'])==set(tolerance_policy['rules']),'all114 per-person rules/cells')
        for name,expected in b['metrics'].items():
            actual=a['metrics'][name];fields(actual,('value','support','reason'));fields(expected,('value','support','reason'))
            rule=tolerance_policy['rules'][name];fields(rule,('unit','absolute_tolerance','relative_tolerance'))
            need(rule['unit'] in ('ms','nats_per_trial'),'independently frozen source units')
            atol=finite(rule['absolute_tolerance']);rtol=finite(rule['relative_tolerance']);need(atol>=0 and rtol>=0,'nonnegative independently selected tolerances')
            support=actual['support']==expected['support'] and actual['reason']==expected['reason']
            if actual['value'] is None or expected['value'] is None:
                matched=support and actual['value'] is expected['value'];error=None
            else:
                x=finite(actual['value']);y=finite(expected['value']);error=abs(x-y);matched=support and error<=atol+rtol*abs(y)
            outcomes.append({'person':a['person'],'metric':name,'unit':rule['unit'],'match':matched,'absolute_error':error,'support_match':support})
    need(len(outcomes)==2964,'complete reconstruction cells')
    return {'cells':outcomes,'all_declared_cells_match':all(x['match'] for x in outcomes),'whole_paper_reproduction':False}

RUBRIC=('evidence_correctness','information_source_reasoning','identifiability_and_alternatives','exposure_and_uncertainty','method_source_fidelity','discriminating_next_analysis')
def score_reasoning(reports,reviews,evidence_pin,reviewer_admission):
    fields(reports,PREDICTION_POLICIES);fields(reviews,PREDICTION_POLICIES);check_pin(evidence_pin);check_pin(reviewer_admission)
    values={};pairs=[]
    for policy in PREDICTION_POLICIES:
        entries=reviews[policy];need(type(entries) is list and len(entries)==2,'two independent blinded initial reviewers')
        need(entries[0]['reviewer']!=entries[1]['reviewer'],'distinct reviewers')
        for row in entries:
            fields(row,('reviewer','report_pin','evidence_pin','scores','rationales','blinding_receipt'))
            need(row['report_pin']==pin(reports[policy],8*1048576) and row['evidence_pin']==evidence_pin,'same immutable report/evidence')
            check_pin(row['blinding_receipt']);fields(row['scores'],RUBRIC);fields(row['rationales'],RUBRIC)
            for dim in RUBRIC:
                need(type(row['scores'][dim]) is int and row['scores'][dim] in (0,1,2) and type(row['rationales'][dim]) is str and row['rationales'][dim],'all dimensions with evidence-linked rationale')
        for dim in RUBRIC:pairs.append((entries[0]['scores'][dim],entries[1]['scores'][dim]))
        values[policy]={'original_reviews':entries,'totals':[sum(e['scores'].values()) for e in entries],'consensus':None}
    n=len(pairs);observed=sum(a==b for a,b in pairs)/n
    wobs=sum(1-abs(a-b)/2 for a,b in pairs)/n
    pa=[sum(a==k for a,b in pairs)/n for k in range(3)];pb=[sum(b==k for a,b in pairs)/n for k in range(3)]
    expected=sum(pa[a]*pb[b]*(1-abs(a-b)/2) for a in range(3) for b in range(3))
    kappa=None if expected==1 else (wobs-expected)/(1-expected)
    return {'reports':values,'raw_dimension_agreement':observed,'linear_weighted_kappa':kappa,'reviewer_admission':reviewer_admission,
        'small_dependent_report_sample':True,'rubric_validation_established':False,'numerical_score_composite':None}

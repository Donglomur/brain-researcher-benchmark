"""Fresh report-only source execution and independently reviewable claim rubric.

No prediction data, private target, model state, old agent context or mutable
learning capability is released. Rubric completion requires actual independent
blind reviews of these new reports; prequalified reviewers are not a score.
"""
import os
from .protocol import HandleCustody,Directory,fields,need,identity,encode,persist,observation,digest,finite
from .information import public_request
from .products import validate_scientific_body

CLAIMS=tuple('CL%02d'%i for i in range(1,25))


def approved_aggregate(report,budget):
    facts=[]
    def fact(kind,body):
        value={'kind':kind,'body':body};value['evidence_id']=identity(value);facts.append(value)
    # These are source-owned whitelists, never a recursive copy of an arbitrary
    # candidate report, receipt, failure traceback or host filename.
    for pid,row in sorted(report['all_case_grades'].items()):
        metrics=row.get('metrics');allowed=None if metrics is None else {k:metrics[k] for k in ('balanced_accuracy','cohen_kappa','weighted_f1','auroc','log_loss','brier')}
        fact('complete_case_metrics',{'case':pid,'status':row['status'],'metrics':allowed})
    for pid,row in sorted(report['all_diagnostic_grades'].items()):
        comparison=row.get('full_comparison');fact('complete_scientific_diagnostic',{'product':pid,'status':row['status'],'scientific_agreement':row.get('scientific_agreement'),'compared_values':None if comparison is None else comparison['numeric_values'],'maximum_absolute_difference':None if comparison is None else comparison['max_absolute_error'],'outside_tolerance':None if comparison is None else comparison['outside_tolerance'],'causal_interpretation':False})
        # Actual protected reductions are released, not candidate supplied scores.
        if row.get('scientific_summary') is not None:fact('complete_scientific_summary',{'product':pid,'summary':row['scientific_summary']})
    for key,row in sorted(report['historical_reconstruction'].items()):fact('historical_reconstruction',{'case_pair':key,'scope':row['scope'],'monitor_difference':row['monitor_difference'],'historical_parity_qualified':row['historical_parity_qualified'],'published_mean_used_as_target':False})
    # effects_report is source-owned mathematics; project only its fixed public
    # schema through the recursive scalar whitelist below, never original
    # issuer/private source receipts or per-person target maps.
    def clean(value):
        if value is None or type(value) in (bool,int,float,str):
            if type(value) is float:finite(value,'released finite scientific result')
            return value
        if type(value) is list:return [clean(x) for x in value]
        need(type(value) is dict,'typed closed aggregate result');out={}
        for k,v in value.items():
            if k in ('original_receipt','original_failure','all_twelve_validation_summaries','evidence','token','journal','state','states','source','scope','rows','person_ids'):continue
            out[k]=clean(v)
        return out
    fact('complete_reproduction_dataset_reductions',clean(report['complete_reproduction_dataset_reductions']));fact('complete_improvement_families',clean(report['improvement']));fact('matched_B_minus_A_access_effects',clean(report['matched_B_minus_A_access_effects']))
    # All source-owned signed contrasts reach both fresh interpretation arms.
    for key,row in sorted(report['complete_within_family_contrasts'].items()):
        fact('complete_within_family_contrast',{'contrast':key,'scope':row['scope'],'coefficients':row['coefficients'],'metrics':clean(row['metrics']),'component_statuses':row['component_statuses'],'all_original_components':row['components'],'all_required_pairing_components':row['all_required_pairing_components'],'all_required_pairing_statuses':row['all_required_pairing_statuses'],'paired_support_status':row['paired_support_status'],'descriptive_only':True,'confirmatory_p_value':None,'conditional_on_realized_states':True,'interval_limitation':row['interval_limitation']})
    fact('qualified_information_limits',{'gates':{k:v['status'] for k,v in report['scientific_qualification']['gates'].items()},'favorable_paper_conclusion_required':False,'direct_native_neural_understanding_established':False,'causal_or_clinical_claim_established':False,'same_fitted_states_conditioned_on':True,'new_pretraining_population_inferred':False})
    fact('resource_observations',{'known':dict(budget.known),'reserved':dict(budget.reserved),'unknown_observations':len(budget.unknown),'peak_resident_bytes':budget.peak_resident,'peak_gpu_resident_bytes':budget.peak_gpu_resident,'physical_costs_not_multiplied_by_logical_aliases':True})
    return {'schema':'eegpt_aggregate_release_v1','facts':facts,'claim_ids':list(CLAIMS),'complete_numeric_report_identity':identity(report),'claim_outcome_key':None,'targets_or_model_states_included':False}


def release_and_interpret(programme,report,score):
    p=programme;policy=p.config['release_policy'];fields(policy,('schema','claim_ids','reservation','review_qualification','maximum_report_bytes'),'full original report-only release policy');need(policy['schema']=='eegpt_report_only_v1' and policy['claim_ids']==list(CLAIMS),'all24 original claims');digest(policy['review_qualification']);need(policy==p.config['genesis']['release_policy'],'report resources and policy predeclared at original G0')
    aggregate=approved_aggregate(report,p.budget);root=p.paths['reports']/'aggregate';os.mkdir(root,0o700)
    with HandleCustody('approved_aggregate_publication') as owned:
        held=owned.own(Directory(str(root)),'aggregate')
        pin=persist(held,'AGGREGATE.json',encode(aggregate),ledger=p.operator)
    release=p.issuer.authorize_report(score,identity(aggregate));p._global();outputs={}
    for access in ('A','B'):
        p.budget.guard('before_next_original_report_only_arm')
        source=p.sources[access];parents=[release,source['receipt']];scope={'mode':'REPORT','access':access,'policy_id':p.config['genesis']['scientific_policy'],'dataset':'AGGREGATES','outer_fold':'closed','method':'fresh_interpretation','repetition':None};support={'released_evidence':[r['evidence_id'] for r in aggregate['facts']]}
        expected={'product_id':'reasoning-'+access,'type':'T14','scope':scope,'support':support,'support_identity':identity(support),'parents':[r['record_sha256'] for r in parents],'arrays':{}}
        context=os.urandom(32).hex();request=public_request(call='INTERPRET',scope=scope,request_id=os.urandom(16).hex(),source=source['identity'],parents=expected['parents'],inputs=[{'name':'aggregates','guest_root':'/inputs/aggregates','public_identity':pin['sha256']}],output_contract={'products':[expected],'maximum_report_bytes':policy['maximum_report_bytes'],'all_numerical_results_final':True},resources=policy['reservation'],seed=p.config['genesis']['seed_policy']['inference_seed'],feedback=None,context=context,action='interpret_complete_frozen_scientific_evidence')
        try:
            call=p.session.call(None,source,request,parents,repetition=None,reservation=policy['reservation'],inputs=[{'host':str(root),'guest':'/inputs/aggregates','identity':pin['sha256']}],query=True);response=call['response'];need(response['status']=='ok' and len(response['products'])==1,'one full original claim report');product=response['products'][0]
            for k in ('product_id','type','scope','parents','support_identity'):need(product[k]==expected[k],'actual full report-only product '+k)
            need(product['status']=='complete' and product['body']['release']==identity(aggregate) and product['body']['phase']=='post_score_interpretation','report bound to identical approved released facts');validate_scientific_body(product,expected)
            need(len(encode(product))<=policy['maximum_report_bytes'],'complete report under original finite ceiling; no truncation')
            outputs[access]={'status':'awaiting_independent_blinded_review','product':product,'original_process':call['process_receipt'],'original_capture':call['capture_receipt'],'new_context_identity':context,'numerical_scores_alterable':False}
        except BaseException as exc:outputs[access]={'status':'failed','reason':observation(exc),'numerical_scores_alterable':False}
    p.budget.guard('after_complete_original_report_only_arms')
    return {'schema':'eegpt_complete_interpretation_v1','aggregate_member':pin,'aggregate_identity':identity(aggregate),'original_release':release,'released_evidence_ids':[f['evidence_id'] for f in aggregate['facts']],'arms':outputs,'adjudicated_claims':[{'claim_id':claim,'status':'pending_independent_review','evidence':[],'criteria':{k:None for k in ('RR1','RR2','RR3','RR4')}} for claim in CLAIMS],'review_qualification':policy['review_qualification'],'automatic_semantic_correctness_claim':False}


def adjudicate_blinded_reviews(interpretations,review_packet,qualification):
    """Source-owned later review reduction; data records, not a judge callback.

    The enclosing authorized report-review operation must authenticate the exact
    immutable report and original reviewer packet bytes before calling this.
    A pre-run qualification identifies reviewers/calibration, not their votes.
    """
    fields(qualification,('identity','reviewers','blind_aliases','calibration','tie_policy'),'actual independent reviewer qualification');digest(qualification['identity']);digest(qualification['calibration']);need(len(qualification['reviewers'])>=2 and len(set(qualification['reviewers']))==len(qualification['reviewers']),'at least two distinct qualified independent scientific reviewers')
    need(qualification['identity']==interpretations['review_qualification'],'original G24 review qualification');need(set(qualification['blind_aliases'].values())=={'A','B'} and len(qualification['blind_aliases'])==2,'private randomized arm aliases')
    fields(review_packet,('schema','interpretation_identity','qualification','reports','reviewers','adjudications'),'actual full reviewer packet');need(review_packet['schema']=='eegpt_blinded_claim_review_v1' and review_packet['interpretation_identity']==identity(interpretations) and review_packet['qualification']==qualification['identity'],'reviews bind these new immutable reports, never a historical score')
    need(set(review_packet['reports'])==set(qualification['blind_aliases']) and set(review_packet['reviewers'])==set(qualification['reviewers']),'complete original arm and reviewer set');matrix={};disagreement=[];allowed_evidence=set(interpretations['released_evidence_ids'])
    for reviewer,rows in review_packet['reviewers'].items():need(set(rows)==set(qualification['blind_aliases']),'each actual reviewer covers exactly both blinded arms')
    for alias,arm in qualification['blind_aliases'].items():
        need(interpretations['arms'][arm]['status']=='awaiting_independent_blinded_review' and review_packet['reports'][alias]==identity(interpretations['arms'][arm]['product']),'exact actually produced blinded report')
        matrix[arm]={}
        for claim in CLAIMS:
            matrix[arm][claim]={}
            for criterion in ('RR1','RR2','RR3','RR4'):
                votes=[]
                for reviewer in qualification['reviewers']:
                    rows=review_packet['reviewers'][reviewer][alias];need(set(rows)==set(CLAIMS),'all24 actual reviewed claims');fields(rows[claim],('RR1','RR2','RR3','RR4'),'complete four-criterion row');vote=rows[claim][criterion];fields(vote,('score','rationale','evidence'),'actual independent criterion judgment');need(type(vote['score']) is int and vote['score'] in (0,1) and vote['rationale'] and type(vote['evidence']) is list,'binary observed score with scientific justification');need(set(vote['evidence'])<=allowed_evidence,'review citations refer to original immutable released evidence');votes.append(vote['score'])
                key=alias+':'+claim+':'+criterion
                if len(set(votes))==1:value=votes[0]
                else:
                    disagreement.append(key);need(qualification['tie_policy']=='explicit_independent_adjudication' and key in review_packet['adjudications'],'all reviewer disagreements receive an explicit original adjudication');decision=review_packet['adjudications'][key];fields(decision,('reviewer','score','rationale'),'full original disagreement resolution');need(decision['reviewer'] not in qualification['reviewers'] and type(decision['score']) is int and decision['score'] in (0,1) and decision['rationale'],'separate actual adjudicator, no automated majority assumption');value=decision['score']
                matrix[arm][claim][criterion]=value
    need(set(review_packet['adjudications'])==set(disagreement),'no absent or unexplained post hoc adjudications')
    return {'status':'adjudicated','criterion_matrix':matrix,'descriptive_sums':{a:sum(sum(r.values()) for r in rows.values()) for a,rows in matrix.items()},'original_disagreement_cells':disagreement,'original_review_packet_identity':identity(review_packet),'scientific_metric_vector_replaced':False,'adjudicated_claims':[{'claim_id':c,'status':'adjudicated','evidence':[identity(review_packet)],'criteria_by_arm':{a:matrix[a][c] for a in ('A','B')}} for c in CLAIMS]}

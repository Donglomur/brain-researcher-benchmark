"""Aggregate-only report and separate blinded ordinal rubric."""
from .contracts import need,closed,descriptor,canonical,digest,parse,integer
from .programme import expected_groups,group_id,group_key

def aggregate(grade,intervals,costs,exposure,disposition):
 need(set(grade['contrasts'])==set(intervals['whole_trial']),'full contrast accounting')
 means={}
 for condition in sorted({g['condition']for g in expected_groups()}):
  for mode in('F','I'):
   for view in('A','B'):
    keys=[group_key(condition,mode,view,s)for s in range(1,6)];values=[grade['scores'][k]['co_bps']for k in keys]
    if any(x is None for x in values):row={'status':'unavailable','seed_values':values}
    else:
     mean=sum(values)/5;row={'status':'complete','seed_values':values,'mean_bps':mean,'sample_sd_bps':(sum((x-mean)**2 for x in values)/4)**.5}
    means[condition+'/'+mode+'-'+view]=row
 return {'schema':'NLB017_aggregate_only_report_inputs_v1','all_seed_groups':means,'all_scores':grade['scores'],'all_65_contrasts':grade['contrasts'],'uncertainty':intervals,'original_R1_delta':grade['original_R1_delta'],'resources':costs,'exposure':exposure,'disposition':disposition,'limitations':['One historically exposed public animal/session; no unseen-session generalization.','Metadata-neutral prompts do not anonymize biology or identify native understanding.','Within-condition shuffle preserves/in some strata permits recovery of information; not causal deletion.','Deterministic reference construction is separate from five agent replicates.','Prediction evidence and blinded scientific prose rubric are separate endpoints.']}

ITEMS=('factual_accuracy','uncertainty','diagnostic_interpretation','limitations','scientific_reasoning')

def rubric_contract(rubric):
 closed(rubric,{'schema','items','reviewers','adjudicator','disagreement_policy','max_report_bytes'})
 need(rubric['schema']=='NLB017_precommitted_report_rubric_v2','precommitted report rubric');closed(rubric['items'],ITEMS)
 for anchors in rubric['items'].values():
  closed(anchors,{'0','1','2'});need(all(type(v)is str and v.strip()and len(v.encode())<=8192 for v in anchors.values()),'explicit complete ordinal anchors')
 ids=[*rubric['reviewers'],rubric['adjudicator']]
 need(type(rubric['reviewers'])is list and len(rubric['reviewers'])==2 and len(set(ids))==3 and all(type(v)is str and v.strip()and len(v)<=256 for v in ids),'two independent selected reviewers and distinct adjudicator')
 need(rubric['disagreement_policy']=='third_review_all_disagreements','fixed disagreement policy');integer(rubric['max_report_bytes'],1,128*2**10)
 return rubric

def produce_report(model,store,aggregate_pin,rubric_pin,programme,job,seed,budget,max_tokens):
 """One actual post-barrier model exchange; no tool/prediction feedback path."""
 aggregate=store.json(aggregate_pin,32*2**20);rubric=rubric_contract(store.json(rubric_pin,2**20))
 need(aggregate['schema']=='NLB017_aggregate_only_report_inputs_v1','only committed aggregate report inputs')
 messages=[{'role':'system','content':'Write an evidence-grounded neuroscience report using only the supplied complete aggregate results. Discuss negative findings, uncertainty, diagnostic limitations, costs and exposure. Do not identify the model/provider or alter predictions. No tools, refits or additional experiments are available.'},
           {'role':'user','content':canonical({'aggregate':aggregate,'rubric_anchors':rubric['items']}).decode()}]
 reply,original=model.exchange(job,'S15',messages,seed,budget,max_tokens)
 need(reply['tool_calls']==[]and type(reply['content'])is str and reply['content'].strip(),'postfreeze prose only');need(len(reply['content'].encode())<=rubric['max_report_bytes'],'complete report without truncation')
 report={'schema':'NLB017_postfreeze_report_v2','programme':programme,'aggregate':aggregate_pin,'rubric':rubric_pin,'content':reply['content'],'generator':model.identity,'actual_model_exchange':original}
 pin=store.write('reports/REPORT.json',canonical(report),2**20)
 # The blinded packet deliberately omits generator identity/provider metadata.
 packet=store.write('reports/BLINDED_INPUT.json',canonical({'schema':'NLB017_blinded_report_inputs_v2','report_source':pin,'content':reply['content'],'aggregate':aggregate,'aggregate_source':aggregate_pin,'rubric_source':rubric_pin,'rubric_anchors':rubric['items']}),40*2**20)
 return {'report':pin,'blinded_packet':packet,'original_exchange':original,'messages':messages}

def grade_report(report_raw,report_pin,reviews,adjudication,aggregate_pin,rubric_pin,rubric):
 """Bind independent original judgments to the exact actual report bytes.

The trusted operator selects authenticated reviewer records. This consumer
does not invent human/model judgments or claim blinding from text alone.
"""
 descriptor(report_pin);descriptor(aggregate_pin);descriptor(rubric_pin);rubric_contract(rubric)
 need(type(report_raw)is bytes and len(report_raw)==report_pin['bytes']and digest(report_raw)==report_pin['sha256'],'exact actual report bytes')
 report=parse(report_raw);closed(report,{'schema','programme','aggregate','rubric','content','generator','actual_model_exchange'})
 need(report['schema']=='NLB017_postfreeze_report_v2'and report['aggregate']==aggregate_pin and report['rubric']==rubric_pin,'report aggregate/rubric ancestry')
 need(type(report['content'])is str and report['content'].strip()and len(report['content'].encode())<=rubric['max_report_bytes'],'complete bounded report')
 need(type(reviews)is list and len(reviews)==2,'two original independent judgments');by_id={}
 for review in reviews:
  closed(review,{'schema','aggregate','rubric','report_source','blinded_reviewer','blinding_attestation','items','justifications'})
  need(review['schema']=='NLB017_blinded_report_review_v2'and review['aggregate']==aggregate_pin and review['rubric']==rubric_pin and review['report_source']==report_pin,'review exact report/rubric/aggregate')
  rid=review['blinded_reviewer'];need(rid in rubric['reviewers']and rid not in by_id,'selected nonduplicate reviewer identity');need(review['blinding_attestation']=='received_only_bound_blinded_packet','required original blinding attestation')
  closed(review['items'],ITEMS);closed(review['justifications'],ITEMS)
  for key in ITEMS:integer(review['items'][key],0,2);need(type(review['justifications'][key])is str and review['justifications'][key].strip()and len(review['justifications'][key].encode())<=8192,'reasoned independent item judgments')
  by_id[rid]=review
 need(set(by_id)==set(rubric['reviewers']),'complete selected reviewer roster')
 first,second=[by_id[r]for r in rubric['reviewers']];disagreements=[k for k in ITEMS if first['items'][k]!=second['items'][k]]
 final={k:first['items'][k]for k in ITEMS if k not in disagreements}
 if disagreements:
  closed(adjudication,{'schema','aggregate','rubric','report_source','adjudicator','items','justifications'})
  need(adjudication['schema']=='NLB017_report_adjudication_v2'and adjudication['aggregate']==aggregate_pin and adjudication['rubric']==rubric_pin and adjudication['report_source']==report_pin and adjudication['adjudicator']==rubric['adjudicator'],'independent exact adjudication ancestry')
  closed(adjudication['items'],disagreements);closed(adjudication['justifications'],disagreements)
  for key in disagreements:integer(adjudication['items'][key],0,2);need(type(adjudication['justifications'][key])is str and adjudication['justifications'][key].strip()and len(adjudication['justifications'][key].encode())<=8192,'complete disagreement reasons');final[key]=adjudication['items'][key]
 else:need(adjudication is None,'no unselected adjudication when reviewers agree')
 return {'schema':'NLB017_bound_report_judgment_v2','report_source':report_pin,'aggregate':aggregate_pin,'rubric':rubric_pin,'original_reviews':reviews,'disagreement_items':disagreements,'agreement_items':len(ITEMS)-len(disagreements),'adjudication':adjudication,'final_items':final,'separate_from_predictive_metric':True,'does_not_modify_bps':True,'complete':True,'blinding_limit':'Operator-authenticated attestation; text alone does not prove procedural blinding.'}

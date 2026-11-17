"""Additive reduction of actual independent reviews of a closed programme.

This never resumes a participant, opens a target, refits, or rewrites the
original numerical report. Blinding/independence require the actual selected
G24 review evidence; JSON shape and two reviewer names do not prove them.
"""
from .protocol import boundary,Directory,fields,need,digest,identity,encode,decode,read_metadata,persist,observation,Refusal
from .budget import Budget
from .reporting import adjudicate_blinded_reviews
from .products import scientific_completion


def reduce_closed_review(selection):
    fields(selection,('schema','input_root','report','review_packet','qualification','review_evidence','output_root','limits','root_selection_identity','completion'),'complete independent closed review selection')
    need(selection['schema']=='eegpt_closed_review_selection_v1','separate additive closed-report review');digest(selection['root_selection_identity'])
    budget=Budget(selection['limits'],label='original closed-report review');root=None;output=None;failure=None;closures=[];publication=None;result=None;captures=[]
    try:
        root=Directory(selection['input_root']);values={}
        for name in ('report','review_packet','qualification','review_evidence'):
            member=selection[name];values[name]=decode(read_metadata(root,member,cap=budget.limits['metadata_bytes'],ledger=budget));captures.append({'role':name,'original_member':member})
        report=values['report']
        from .completion import admit_original_completion
        need(selection['input_root']==selection['completion']['work_root'],'review reads original producer report root')
        completion=admit_original_completion(selection['completion'],selection['report'],report,budget)
        q=values['qualification'];e=values['review_evidence']
        need(report['schema']=='eegpt_complete_scientific_report_v1' and report['numerical_scoring_closed'] and 'score_closure' in report,'exact original whole closed numerical report')
        fields(e,('schema','root_selection_identity','report_identity','review_packet_identity','qualification_identity','blind_material_publication','independent_review_receipts','calibration_evidence','status'),'actual independent review provenance')
        need(e['schema']=='eegpt_independent_claim_review_evidence_v1' and e['root_selection_identity']==selection['root_selection_identity'] and e['report_identity']==identity(report) and e['review_packet_identity']==identity(values['review_packet']) and e['qualification_identity']==identity(q) and e['status']=='qualified','root-selected exact new review, not historical or participant supplied judgments')
        need(e['blind_material_publication'] and e['independent_review_receipts'] and e['calibration_evidence'],'actual separate blinded material, original reviewer and calibration receipts required')
        reviewed=boundary(budget,'closed_blinded_review',adjudicate_blinded_reviews,report['interpretations'],values['review_packet'],q)
        selectors=report['all_same_fold_selection_records'];complete=boundary(budget,'closed_review_completion',scientific_completion,report['original_closed_collection'],{**report['all_case_grades'],**report['all_diagnostic_grades']},report['scientific_qualification']['gates'],{a:[v for k,v in selectors.items() if k.startswith(a+':')] for a in ('A','B')},reviewed['adjudicated_claims'],report['complete_within_family_contrasts'])
        result={'schema':'eegpt_additive_closed_review_v1','original_report_member':selection['report'],'original_report_identity':identity(report),'original_numeric_report_not_modified':True,'original_review_inputs':captures,'root_selection_identity':selection['root_selection_identity'],'adjudication':reviewed,'original_producer_completion':completion,'scientifically_complete':complete,'science_or_participant_execution':False,'known_review_budget':budget.report()}
        output=Directory(selection['output_root']);publication=persist(output,'CLOSED_REVIEW.json',encode(result),ledger=budget)
    except BaseException as exc:failure=observation(exc)
    finally:
        for h in (output,root):
            if h is not None:
                try:h.close()
                except BaseException as exc:closures.append(observation(exc))
    try:budget.guard('after_original_review_publication_close_before_return')
    except BaseException as exc:
        if failure is None:failure=observation(exc)
        else:closures.append(observation(exc))
    if failure is not None or closures:raise Refusal('original closed-review reduction failed',observation={'failure':failure,'close_failures':closures,'captures':captures,'publication':publication,'known_budget':budget.report()})
    return {'original_publication':publication,'scientifically_complete':result['scientifically_complete'],'numerical_report_unchanged':True,'final_budget':budget.report()}

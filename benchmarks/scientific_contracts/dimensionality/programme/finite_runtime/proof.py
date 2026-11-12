"""Protected qualified structured scientific/source adjudication.

The rubric is a separately reviewed target, never supplied by the participant.
Unknown supplement/source coverage is required-unscorable. This is not a prose
similarity model or a claim that numeric equality establishes scientific reasoning.
"""
from __future__ import annotations
from .common import require,identity

R01_CLAIMS={'task_estimand','neuron_estimand','uncentered_estimand','finite_estimand',
            'sampling_units','integrability','tuple_independence','moment_vs_ratio',
            'noise_assumptions','local_metric_and_target'}

def adjudicate(obligation,submission,rubric,*,source_registry,admission):
    admission.check('before_source_proof_adjudication')
    require(obligation in {'R01','R33','R35'},'UNKNOWN_SOURCE_PROOF_OBLIGATION')
    if not rubric.get('independent_qualification_id'):
        return {'status':'qualification_required','obligation':obligation,
                'reason':'Independent semantic/source-proof rubric is not qualified.'}
    require(rubric['obligation']==obligation and rubric['source_registry_sha256']==identity(source_registry),
            'RUBRIC_SOURCE_OR_OBLIGATION_SUBSTITUTION')
    if obligation=='R35' and rubric['supplement_disposition'] not in {'verified_present','verified_absent'}:
        return {'status':'qualification_required','obligation':'R35',
                'reason':'Original external supplement completeness is unresolved.'}
    claims={x['id']:x for x in submission['claims']}
    require(len(claims)==len(submission['claims']),'DUPLICATE_SOURCE_PROOF_CLAIM')
    expected=rubric['claims']
    if obligation=='R01':require(set(expected)>=R01_CLAIMS,'INCOMPLETE_ESTIMAND_RUBRIC')
    if obligation=='R33':require(set(rubric['required_source_members'])==set(source_registry),
                               'INCOMPLETE_SOURCE_ACCOUNT_RUBRIC')
    results=[]
    for key,rule in expected.items():
        admission.check('next_protected_proof_claim')
        actual=claims.get(key)
        valid=actual is not None
        reasons=[]
        if actual is not None:
            # Scientific propositions are versioned typed trees, including domains,
            # assumptions, target measure and limitations. Free text stays in report.
            if actual.get('proposition')!=rule['proposition']:valid=False;reasons.append('proposition_mismatch')
            if actual.get('disposition')!=rule['disposition']:valid=False;reasons.append('claim_support_mismatch')
            citations=actual.get('citations',[])
            for citation in rule['required_citations']:
                if citation not in citations:valid=False;reasons.append('missing_exact_source_anchor')
            for source_id in actual.get('source_members',[]):
                if source_id not in source_registry:valid=False;reasons.append('unknown_source_member')
            if rule.get('derivation') is not None and actual.get('derivation')!=rule['derivation']:
                valid=False;reasons.append('derivation_not_the_qualified_typed_proof')
        else:reasons.append('missing_required_claim')
        results.append({'claim':key,'satisfied':valid,'reasons':reasons})
    extras=sorted(set(claims)-set(expected))
    # Unreviewed additional claims remain visible and do not acquire support by omission.
    return {'status':'ok','obligation':obligation,'claims':results,'unreviewed_additional_claims':extras,
            'all_required_claims_supported':all(x['satisfied'] for x in results),
            'rubric_qualification':rubric['independent_qualification_id'],
            'free_text_semantically_graded':False}

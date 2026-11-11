"""Submission-to-protected-evidence composition source; public native leaf held.
MetadataInvestigation is an ordinary engineering owner, not a production private
filesystem/process issuer. This composition is never run on scientific bodies in
BUILD. A qualified production owner must replace that boundary before operation.
"""
import json
from .lifecycle import require_native_producers
from .evidence import PRODUCT_IDS,admit_support_claim,_support_evidence_consumer,_evaluate_policy
from .metadata_io import encoded
from .design import POLICIES

def _consume_captured(owner,products,protected_descriptor,core):
    with owner.investigation():
        if owner.expected!=PRODUCT_IDS:raise ValueError('complete investigation product roster')
        # Actual ordinary capture reauthentication is implemented in lifecycle.
        # Production isolation/role admission is a missing producer, not this call.
        capture=owner.capture_submission(products)
        target=json.loads(owner.open_target_metadata(capture,protected_descriptor))
        if target['investigation_binding']!=owner.query:raise ValueError('protected investigation lineage')
        bodies={key:json.loads(owner.store.read(pin)) for key,pin in zip(PRODUCT_IDS,capture.members)}
        support=_support_evidence_consumer(admit_support_claim(bodies['original_support']),target['support'])
        analyses={}
        for policy,product in zip(POLICIES,('prestate_predictions','outcome_sensitivity_predictions')):
            protected=target['analyses'][policy]
            analyses[policy]=_evaluate_policy(policy,bodies[product],protected,protected['references'],target['query_bindings'][policy],core)
        report={'original_question_support':support,'observational_analyses':analyses,
           'candidate_report_retained':bodies['analysis_report'],'causal_novelty_effect':None,
           'complete_investigation':support['original_support_success'] and all(v['complete_primary_support'] for v in analyses.values()),
           'scientific_qualification':'requires_independent_native_evidence_and_review','physical_resource_totals':'unknown_unless_supplied_by_real_owner'}
        result=owner.store.publish('EVIDENCE.json',encoded(report))
        receipt=owner.publish_report(capture,result)
        return {'evidence':result,'receipt':receipt}

def main():require_native_producers()
if __name__=='__main__':main()

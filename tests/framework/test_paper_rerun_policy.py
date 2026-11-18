"""Invented paired rerun fixtures only; no neuroscience data or model execution."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("legacy_fixture", Path(__file__).with_name("test_paper_improvement.py"))
legacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(legacy)
paper = legacy.paper


def seal(c, r):
    digest = paper.contract_digest(c)
    for record in (r, r["freeze"], r["evaluation"], r["uncertainty"], r["reproduced_author_baseline"]["freeze"]):
        record["contract_digest"] = digest
    measured = paper.rerun_measurement_digest(r)
    for holder in (r, r["reproduced_author_baseline"]):
        holder["output_verification"]["measurement_digest"] = measured
        for usage in holder['budget_usage'].values():usage['contract_digest']=digest
    if 'exposure' in r:r['exposure']['contract_digest']=digest
    records = [r["freeze"], r["evaluation"], r["reproduced_author_baseline"]["freeze"], r["analysis_execution"], r["output_verification"],
        r["reproduced_author_baseline"]["analysis_execution"], r["reproduced_author_baseline"]["output_verification"]]
    if 'exposure' in r:records.append(r['exposure'])
    records.extend(r['budget_usage'].values());records.extend(r['reproduced_author_baseline']['budget_usage'].values())
    evidence = {row["id"]: row for row in r["evidence"]}
    for record in records:
        for ref in record["evidence_ids"]:
            if ref in evidence:
                evidence[ref]["sha256"] = paper.rerun_record_digest(record)


def fixture(published=None):
    original, r = legacy.fixture()
    original.update(disposition="source_unresolved", blocking_issues=["Historical assignments unavailable"])
    original["same_task"]["split"].update(status="unresolved", description="Original stochastic trial protocol; historical assignments unavailable")
    original["comparison"]["published_baseline"].update(status="unresolved" if published is None else "verified", value=published)
    original.pop("admission_policy")
    c = deepcopy(original)
    c.update(schema_version=paper.RERUN_VERSION, objective="improve_qualified_author_method_same_task",
        disposition="metadata_ready", blocking_issues=[], source_contract_digest=paper.contract_digest(original))
    c["comparison"]["improvement_requires"] = ["Paired source-method gain with independent biological uncertainty"]
    c["comparison"].pop("paper_win_requires")
    _, initial = legacy.fixture()
    old_contract, _ = legacy.fixture()
    policy = deepcopy(old_contract["admission_policy"])
    c["admission_policy"] = policy
    policy["comparator"] = "qualified_author_rerun_on_identical_cases"
    policy["author_baseline"].update(route="qualified_source_method", implementation_origin="author_released_code", method_sha256="b"*64,
        source_version="Invented fixed author code", qualification_sha256="9"*64,
        corrections={"status":"not_applicable","description":"No corrections in this generated fixture","evidence_ids":[]},
        evidence_ids=["code","registration"])
    policy["uncertainty_rule"].update(comparison_target="paired_qualified_author_rerun", independent_unit="animal", minimum_independent_units=7)
    c["comparison"]["uncertainty"]["independent_unit"] = "animal"
    policy["requirement_checks"] = [{"requirement": c["comparison"]["improvement_requires"][0],
        "checks": ["same_task", "reproduced_author_effect", "uncertainty", "candidate_freeze", "final_evaluation", "budgets", "provenance"]}]
    c["evidence"].append({"id":"registration", "kind":"registration", "url":"https://example.org/generated-registration",
        "locator":"Invented preregistration", "supports":"Generated assignment and inference policy"})
    identity = {key: str(i+1)*64 for i,key in enumerate(paper._IDENTITIES)}
    protocol = {"assignment_origin":"preregistered_regeneration", "historical_assignment_status":"unavailable",
        "historical_assignment_sha256":None, "source_split_protocol":{"status":"verified","description":"Same trial split unit and five-fold recipe","evidence_ids":["paper"]},
        "generation_record_sha256":"1"*64, "frozen_at":"2026-11-16T07:00:00Z", "evaluation_identity":identity,
        "exposure_policy_sha256":"2"*64, "prior_public_test_exposure":"Public original observations disclosed; no contamination-free claim",
        "analysis_interface_sha256":"3"*64, "authentic_data_manifest_sha256":"4"*64,
        "verification_program_sha256":"5"*64,
        "required_outputs":[{"id":"predictions", "kind":"observation_level", "identity_sha256":"6"*64,"control_rule":None,"evidence_ids":["paper"]},
            {"id":"shuffle", "kind":"companion_control", "identity_sha256":"7"*64,
             "control_rule":{"minimum":0,"maximum":.55,"evidence_ids":["paper"]},"evidence_ids":["paper"]}],
        "independent_units":{"unit":"animal", "count":7, "manifest_sha256":"8"*64,
            "aggregation_sha256":identity["aggregation"], "preserves_source_estimand":True,
            "dependence_method":"Paired animal clusters; retain original session weights", "evidence_ids":["registration"]},
        "evidence_ids":["paper","registration"]}
    policy["evaluation_protocol"] = protocol
    policy["source_blocker_dispositions"]=[{"blocker":"Historical assignments unavailable","resolution":"historical_assignment_unavailable","evidence_ids":["registration"]}]
    policy["author_baseline"]["qualification_sha256"]=paper.rerun_qualification_digest(c)
    r = deepcopy(initial)
    r.update(schema_version=paper.RERUN_RESULT_VERSION, claim=paper.RERUN_CLAIM,
        same_task=deepcopy(c["same_task"]), source_evidence_ids=["paper","code","registration"],
        selection_started_at="2026-11-16T08:00:00Z")
    r["measurement"].update(comparator_kind="qualified_author_rerun", published_value=published)
    r["evaluation"].update(finished_at="2026-11-16T11:00:00Z", evaluation_identity=deepcopy(identity))
    r["freeze"]["selection_started_at"]=r["selection_started_at"]
    r["exposure"]={"exposure_policy_sha256":protocol["exposure_policy_sha256"],"exposure_manifest_sha256":"a"*64,
        "prior_public_test_exposure":protocol["prior_public_test_exposure"],"protected_labels_accessed_before_freeze":False,"evidence_ids":["exposure"],
        "contract_digest":"f"*64,"candidate_sha256":r['candidate_sha256'],"baseline_method_sha256":"b"*64,
        "candidate_execution_id":"candidate-execution","baseline_execution_id":"baseline-execution",
        "selection_started_at":r['selection_started_at'],"candidate_frozen_at":r['freeze']['frozen_at'],
        "evaluation_started_at":r['evaluation']['started_at'],"evaluation_finished_at":r['evaluation']['finished_at']}
    baseline=r["reproduced_author_baseline"]
    baseline.update(same_task=deepcopy(c["same_task"]),method_sha256="b"*64,qualification_sha256=policy["author_baseline"]["qualification_sha256"],
        freeze={"contract_digest":"f"*64,"candidate_sha256":"b"*64,"frozen_at":"2026-11-16T07:30:00Z","evidence_ids":["baseline-freeze"]},
        budget_usage=deepcopy(r["budget_usage"]))
    for label,holder,method in [("candidate",r,r["candidate_sha256"]),("baseline",baseline,baseline["method_sha256"])]:
        holder["analysis_execution"]={"execution_id":label+"-execution","executor_role":"independent_operator",
            "candidate_sha256":method,"analysis_interface_sha256":protocol["analysis_interface_sha256"],
            "authentic_data_manifest_sha256":protocol["authentic_data_manifest_sha256"],"runtime_manifest_sha256":"d"*64,
            "invocation_sha256":"e"*64,"evaluation_identity":deepcopy(identity),"started_at":"2026-11-16T10:01:00Z",
            "finished_at":"2026-11-16T10:10:00Z","output_manifest_sha256":("c" if label=="candidate" else "b")*64,
            "evidence_ids":[label+"-execution"]}
        holder["output_verification"]={"verifier_role":"independent_operator","verification_program_sha256":protocol["verification_program_sha256"],
            "execution_id":label+"-execution","output_manifest_sha256":holder["analysis_execution"]["output_manifest_sha256"],
            "measurement_digest":"f"*64,"started_at":"2026-11-16T10:11:00Z","finished_at":"2026-11-16T10:20:00Z",
            "evidence_ids":[label+"-verification"],"outputs":[{"id":row["id"],"identity_sha256":row["identity_sha256"],"status":"verified",
                "value":.5 if row['kind']=='companion_control' else None} for row in protocol["required_outputs"]]}
        for key,usage in holder['budget_usage'].items():
            usage.update(contract_digest='f'*64,candidate_sha256=method,execution_id=label+'-execution',evidence_ids=[label+'-'+key+'-budget'])
            r['evidence'].append({'id':label+'-'+key+'-budget','kind':'budget','sha256':'a'*64,'locator':'generated-only/'+label+'-'+key})
    r["uncertainty"].update(comparison_target="paired_qualified_author_rerun",published_value=published,
        comparator_value=baseline["value"],independent_unit="animal",n_independent_units=7,
        evaluation_identity=deepcopy(identity),candidate_output_manifest_sha256="c"*64,
        baseline_output_manifest_sha256="b"*64,independent_units_manifest_sha256="8"*64)
    for row in r["evidence"]:
        if row["id"]=="baseline":row["sha256"]=policy["author_baseline"]["qualification_sha256"]
    r["evidence"].extend({"id":name,"kind":kind,"sha256":"a"*64,"locator":"generated-only/"+name}
        for name,kind in [("exposure","exposure"),("baseline-freeze","freeze"),("candidate-execution","analysis_execution"),("baseline-execution","analysis_execution"),
            ("candidate-verification","output_verification"),("baseline-verification","output_verification")])
    seal(c,r)
    return original,c,r


def qualify(c,r):
    """Invent a replacement review commitment only for generated valid-policy cases."""
    digest=paper.rerun_qualification_digest(c)
    c['admission_policy']['author_baseline']['qualification_sha256']=digest
    r['reproduced_author_baseline']['qualification_sha256']=digest
    for row in r['evidence']:
        if row['id']=='baseline':row['sha256']=digest
    seal(c,r)


class RerunPolicyTests(unittest.TestCase):
    def compare(self,c,r,s):return paper.compare(c,r,source_contract=s)
    def reject(self,mutation,*,contract=False):
        s,c,r=fixture();mutation(c if contract else r);seal(c,r)
        self.assertFalse(self.compare(c,r,s)["comparison_admitted"])

    def test_new_schema_matches_runtime_and_old_schema_unchanged(self):
        self.assertEqual(json.loads((ROOT/'docs/science/paper-improvement/contract.v2.schema.json').read_text()),paper.RERUN_CONTRACT_SCHEMA)
        self.assertEqual(json.loads((ROOT/'docs/science/paper-improvement/contract.schema.json').read_text()),paper.CONTRACT_SCHEMA)

    def test_nullable_published_and_scoped_success(self):
        s,c,r=fixture();self.assertEqual(paper.contract_validate(c,source_contract=s),[])
        out=self.compare(c,r,s);self.assertTrue(out['comparison_admitted'],out['errors']);self.assertTrue(out['criterion_satisfied'])
        self.assertIsNone(out['paper_win']);self.assertEqual(out['scientific_outcome'],'unknown');self.assertEqual(out['current_sota'],'not_assessed')

    def test_contextual_stronger_published_does_not_change_paired_gain(self):
        s,c,r=fixture();a=self.compare(c,r,s)
        s,c,r=fixture(99);b=self.compare(c,r,s)
        self.assertEqual((a['criterion_satisfied'],a['reproduced_improvement']),(b['criterion_satisfied'],b['reproduced_improvement']))

    def test_legacy_published_and_stronger_comparator_gates_remain(self):
        c,r=legacy.fixture();self.assertTrue(paper.compare(c,r)['comparison_admitted'])
        c['comparison']['published_baseline'].update(value=None);self.assertFalse(paper.compare(c,r)['comparison_admitted'])
        c,r=legacy.fixture();r['reproduced_author_baseline']['value']=80.4;r['measurement']['candidate_value']=82.1
        self.assertFalse(paper.compare(c,r)['comparison_admitted'])

    def test_explicit_source_and_version_separation(self):
        s,c,r=fixture();self.assertFalse(paper.compare(c,r)['comparison_admitted'])
        v1,old=legacy.fixture();self.assertFalse(paper.compare(v1,r)['comparison_admitted'])
        self.assertFalse(self.compare(c,old,s)['comparison_admitted'])

    def test_original_source_identity_and_historical_unknown_preserved(self):
        for key in ('source_contract_digest','same_task'):
            self.reject(lambda c:c.update({key:'f'*64 if key=='source_contract_digest' else deepcopy(legacy.fixture()[0]['same_task'])}),contract=True)
        self.reject(lambda c:c['admission_policy']['evaluation_protocol'].update(historical_assignment_status='verified'),contract=True)

    def test_same_cases_required_even_when_scores_match(self):
        for holder in ('candidate','baseline'):
            self.reject(lambda r:(r if holder=='candidate' else r['reproduced_author_baseline'])['analysis_execution']['evaluation_identity'].update(split='f'*64))

    def test_observations_metric_aggregation_and_cohort_cannot_change(self):
        for key in ('observations','metric','aggregation','cohort','panel'):
            self.reject(lambda r:r['analysis_execution']['evaluation_identity'].update({key:'f'*64}))

    def test_complete_granular_outputs_and_controls_required(self):
        self.reject(lambda r:r['output_verification']['outputs'].pop())
        self.reject(lambda r:r['reproduced_author_baseline']['output_verification']['outputs'].append(deepcopy(r['output_verification']['outputs'][0])))

    def test_qualified_source_method_and_independent_verification_required(self):
        self.reject(lambda r:r['reproduced_author_baseline'].update(method_sha256='f'*64))
        self.reject(lambda r:r['output_verification'].update(verifier_role='ai_solver'))
        self.reject(lambda r:r['reproduced_author_baseline']['output_verification'].update(verification_program_sha256='f'*64))

    def test_selection_protocol_and_candidate_freezes(self):
        self.reject(lambda r:r.update(selection_started_at='2026-11-16T06:00:00Z'))
        self.reject(lambda r:r['freeze'].update(frozen_at='2026-11-16T10:00:00Z'))
        self.reject(lambda r:r['reproduced_author_baseline']['freeze'].update(frozen_at='2026-11-16T08:01:00Z'))

    def test_exposure_disclosure_is_required_and_not_erased(self):
        self.reject(lambda r:r.pop('exposure'))
        self.reject(lambda r:r['exposure'].update(protected_labels_accessed_before_freeze=True))
        self.reject(lambda r:r['exposure'].update(prior_public_test_exposure='None'))
        self.reject(lambda r:r['exposure'].update(protected_labels_accessed_before_freeze=0))

    def test_uncertainty_binds_both_outputs_and_same_cases(self):
        for key in ('candidate_output_manifest_sha256','baseline_output_manifest_sha256','independent_units_manifest_sha256'):
            self.reject(lambda r:r['uncertainty'].update({key:'f'*64}))
        self.reject(lambda r:r['uncertainty']['evaluation_identity'].update(split='f'*64))

    def test_seven_animals_not_fifty_five_fold_units_and_no_animalmean(self):
        self.reject(lambda r:r['uncertainty'].update(n_independent_units=55))
        self.reject(lambda c:c['admission_policy']['evaluation_protocol']['independent_units'].update(aggregation_sha256='f'*64),contract=True)

    def test_failed_criteria_are_scoped_not_historical_failure(self):
        s,c,r=fixture();r['measurement']['candidate_value']=80.9;r['uncertainty'].update(value=.1,interval=[.1,2]);seal(c,r)
        out=self.compare(c,r,s);self.assertTrue(out['comparison_admitted'],out['errors']);self.assertFalse(out['criterion_satisfied']);self.assertIsNone(out['paper_win'])
        s,c,r=fixture();r['uncertainty'].update(value=-.1,interval=[-.1,4.5]);seal(c,r)
        self.assertFalse(self.compare(c,r,s)['criterion_satisfied'])

    def test_interval_must_contain_paired_effect(self):
        self.reject(lambda r:r['uncertainty'].update(value=4,interval=[4,5]))

    def test_both_cumulative_resource_budgets_enforced(self):
        self.reject(lambda r:r['budget_usage']['resource'].update(used=21))
        self.reject(lambda r:r['reproduced_author_baseline']['budget_usage']['resource'].update(used=21))

    def test_cross_execution_splicing_and_unbound_evidence_rejected(self):
        self.reject(lambda r:r['output_verification'].update(execution_id='other'))
        self.reject(lambda r:r['analysis_execution'].update(evidence_ids=['missing']))
        s,c,r=fixture();r['evidence'][1]['sha256']='0'*64
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_equal_output_hashes_do_not_prohibit_equal_valid_analyses(self):
        s,c,r=fixture();b=r['reproduced_author_baseline'];b['analysis_execution']['output_manifest_sha256']='c'*64
        b['output_verification']['output_manifest_sha256']='c'*64;r['uncertainty']['baseline_output_manifest_sha256']='c'*64;seal(c,r)
        self.assertTrue(self.compare(c,r,s)['comparison_admitted'])

    def test_paper_win_sota_and_promotions_cannot_be_submitted(self):
        for key,value in [('paper_win',True),('current_sota','source_verified'),('improvement_ready',True)]:
            self.reject(lambda r:r.update({key:value}))
        self.reject(lambda c:c.update(disposition='improvement_ready'),contract=True)

    def test_finite_numbers_and_required_registration(self):
        for value in (True,float('nan'),float('inf'),10**1000):
            s,c,r=fixture();r['measurement']['candidate_value']=value
            self.assertFalse(self.compare(c,r,s)['comparison_admitted'])
        self.reject(lambda c:c['admission_policy']['evaluation_protocol'].update(evidence_ids=['paper']),contract=True)

    def test_unknown_split_recipe_cannot_become_missing_seeds_only(self):
        s,c,r=fixture();c['admission_policy']['evaluation_protocol']['source_split_protocol']['status']='unresolved';qualify(c,r)
        out=self.compare(c,r,s);self.assertFalse(out['comparison_admitted'])
        self.assertTrue(any('split unit and evaluation recipe' in e for e in out['errors']))

    def test_source_split_recipe_requires_primary_evidence(self):
        s,c,r=fixture();c['admission_policy']['evaluation_protocol']['source_split_protocol']['evidence_ids']=['registration'];qualify(c,r)
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_chronology_fields_cannot_change_without_receipt_commitments(self):
        s,c,r=fixture();r['selection_started_at']='2026-11-16T08:01:00Z'
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])
        s,c,r=fixture();r['reproduced_author_baseline']['freeze']['frozen_at']='2026-11-16T07:31:00Z'
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_authenticated_failing_control_blocks_otherwise_positive_gain(self):
        for arm in ('candidate','baseline'):
            s,c,r=fixture();holder=r if arm=='candidate' else r['reproduced_author_baseline']
            holder['output_verification']['outputs'][1]['value']=.7;seal(c,r)
            out=self.compare(c,r,s);self.assertTrue(out['comparison_admitted'],out['errors'])
            self.assertFalse(out['required_controls_pass']);self.assertFalse(out['criterion_satisfied']);self.assertIsNone(out['paper_win'])

    def test_output_map_cannot_change_under_existing_qualification(self):
        s,c,r=fixture();c['admission_policy']['evaluation_protocol']['required_outputs'].pop()
        r['output_verification']['outputs'].pop();r['reproduced_author_baseline']['output_verification']['outputs'].pop();seal(c,r)
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_ineligible_source_is_not_promoted(self):
        s,c,r=fixture();s['disposition']='ineligible';c['source_contract_digest']=paper.contract_digest(s);qualify(c,r)
        out=self.compare(c,r,s);self.assertFalse(out['comparison_admitted'])
        self.assertTrue(any('ineligible source' in e for e in out['errors']))

    def test_unrelated_source_blockers_cannot_disappear(self):
        s,c,r=fixture();s['blocking_issues'].append('Unknown source quality-control exclusions')
        c['source_contract_digest']=paper.contract_digest(s);qualify(c,r)
        out=self.compare(c,r,s);self.assertFalse(out['comparison_admitted'])
        self.assertTrue(any('every original source blocker' in e for e in out['errors']))

    def test_independently_qualified_paper_method_without_official_code(self):
        s,c,r=fixture();b=c['admission_policy']['author_baseline']
        b.update(implementation_origin='independent_paper_method',evidence_ids=['paper','registration']);qualify(c,r)
        self.assertTrue(self.compare(c,r,s)['comparison_admitted'])

    def test_corrections_need_adjudication(self):
        s,c,r=fixture();c['admission_policy']['author_baseline']['corrections']={
            'status':'verified','description':'Generated correction','evidence_ids':['code']};qualify(c,r)
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_summary_and_aliases_cannot_promote_historical_readiness(self):
        s,c,r=fixture();out=paper.contract_summary(c,source_contract=s)
        self.assertTrue(out['branch_metadata_ready']);self.assertFalse(out['improvement_ready']);self.assertIsNone(out['paper_win'])
        self.assertEqual(paper.validate_contract(c,expected_task_id=c['task_id'],source_contract=s),[])

    def test_exposure_attestation_cannot_be_spliced_from_another_candidate(self):
        s,c,r=fixture();r['exposure']['candidate_sha256']='f'*64;seal(c,r)
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])
        s,c,r=fixture();r['exposure']['baseline_execution_id']='other-baseline';seal(c,r)
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_budget_record_cannot_be_spliced_from_another_episode(self):
        self.reject(lambda r:r['budget_usage']['resource'].update(execution_id='other-episode'))

    def test_original_source_evidence_ids_cannot_be_redefined(self):
        s,c,r=fixture();c['evidence'][0]['url']='https://example.org/unrelated';qualify(c,r)
        self.assertFalse(self.compare(c,r,s)['comparison_admitted'])

    def test_unmeasured_baseline_cannot_be_marked_verified(self):
        self.reject(lambda c:c['comparison']['reproduced_author_baseline'].update(value=None),contract=True)

    def test_public_schemas_have_unique_required_property_names(self):
        def visit(node):
            if isinstance(node,dict):
                if 'required' in node:self.assertEqual(len(node['required']),len(set(node['required'])))
                for value in node.values():visit(value)
            elif isinstance(node,list):
                for value in node:visit(value)
        for schema in (paper.CONTRACT_SCHEMA,paper.RESULT_SCHEMA,paper.RERUN_CONTRACT_SCHEMA,paper.RERUN_RESULT_SCHEMA):visit(schema)


if __name__=='__main__':unittest.main()

"""No missing scientific product becomes a passed benchmark through reporting."""
from .errors import require
from .objects import canonical,digest


def report(controller,case_results,contrasts,claim_product=None):
    controller.guard()
    require(controller.closed is not None,'report before complete terminal collection')
    obligations=controller.scope.obligations['obligations'];coverage=[]
    for obligation in obligations:
        controller.guard()
        required=[name for name,spec in controller.plan['required_products'].items() if obligation['id'] in spec.get('obligations',[])]
        present=[name for name in required if name in controller.collector.products]
        coverage.append({'id':obligation['id'],'family':obligation['family'],'required_products':required,'present_products':present,'complete':bool(required) and len(required)==len(present),'gates':obligation['required_gates']})
    identifiers=[r['case_id'] for r in case_results]
    require(len(identifiers)==len(set(identifiers)) and set(identifiers)==set(controller.scope.ids),'all2144 case disposition rows')
    missing=[r['case_id'] for r in case_results if r['status']!='scored']
    output={'schema':'reve-full-scientific-report-v1','plan':controller.plan_receipt,'closed_bank':controller.closed,
            'scope':{'families':13,'obligations':54,'stages':22,'datasets':10,'legacy_cases':2144,'fewshot_cases':1800,'principal_products':113},
            'obligation_coverage':coverage,'case_results':case_results,'confirmatory_contrasts':contrasts,
            'direct_A_B_comparisons':controller.grading_results['reductions']['direct_A_B'],'trusted_scientific_reductions':controller.grading_results['reductions'],'scientific_audits':controller.grading_results['scientific_audits'],'reference_banks':controller.grading_results['reference_banks'],'support_admissions':controller.support_admissions,
            'missing_case_count':len(missing),'missing_case_ids':missing,'all_discrepancies':controller.scope.discrepancies,
            'gates':controller.scope.gates,'claims':claim_product,'all_original_attempts':controller.launcher.attempts,
            'gross_resources':controller.launcher.spent,'empirical_qualification':False,'submission_ready':False,
            'original_job_dispositions':controller.collector.terminal,'complete_required_scientific_outputs':controller.grading_results['reductions']['complete_required_outputs'],'original_historical_run_predictions_invented':False,'canonical_task_delta':0,
            'complete_products':all(x['complete'] for x in coverage) and not missing and controller.closed['complete']}
    controller.ledger.append('whole_report_closed',{'identity':digest(canonical(output)),'complete_products':output['complete_products'],'scientifically_qualified':False})
    controller.guard()
    return output


def source_aggregate(dataset_results,table):
    """Only named paper aggregations; no universal ten-dataset score."""
    memberships={2:('TUAB','TUEV','PhysioNet-MI','BCIC-IV-2a','FACED','ISRUC','Mumtaz2016','MentalArithmetic','BCIC2020-3'),
                 4:('Mumtaz2016','MentalArithmetic','TUAB','PhysioNet-MI','BCIC-IV-2a','ISRUC','HMC','BCIC2020-3','TUEV','FACED'),
                 18:('Mumtaz2016','TUAB','ISRUC','HMC','BCIC2020-3','TUEV','PhysioNet-MI','FACED'),
                 19:('PhysioNet-MI','MentalArithmetic'),20:('BCIC-IV-2a','TUEV','PhysioNet-MI')}
    require(table in memberships,'table needs its separately selected condition roster')
    expected=memberships[table];require(set(dataset_results)==set(expected),'exact named source aggregate')
    values=[dataset_results[k] for k in expected]
    return {'table':table,'datasets':list(expected),'mean':sum(values)/len(values) if all(x is not None for x in values) else None,'complete':all(x is not None for x in values)}

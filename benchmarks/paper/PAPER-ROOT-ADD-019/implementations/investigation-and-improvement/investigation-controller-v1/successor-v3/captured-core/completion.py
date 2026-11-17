"""Whole scientific-core completion joins, without runtime qualification claims."""
from common import STRATA, ACCESS, need, pin, require_pin
import numeric_backend as numeric
from study import cohort_queries

def expected_reference_fits(plan):
    result = {}
    for panel_key,spec in plan['panels'].items():
        if spec['actor'] != 'operator':
            continue
        base=spec['bundle_fit_id']; training=spec['training_animals']
        for setting in numeric.settings():
            for held in training:
                for stratum in STRATA:
                    key=base+'|inner|'+held+'|'+stratum+'|'+setting['id']
                    result[key]={'panel_key':panel_key,'training_animals':[a for a in training if a!=held],
                                 'stratum':stratum,'validation_animal':held,'setting':setting}
        for stratum in STRATA:
            key=base+'|refit|'+stratum
            result[key]={'panel_key':panel_key,'training_animals':training,'stratum':stratum,
                         'validation_animal':None,'setting':'selected_from_complete_inner_grid'}
    need(len(result)==plan['counts']['reference_regularized_head_fits'], 'complete symbolic reference work')
    return result

def validate_final_reference_bundle(study, panel_key, spec, selection, state, model, records):
    """Exact final-model joins; selection must come from the complete-grid check.

    This smaller structural function is independently testable without creating
    a fabricated eighty-thousand-fit result graph. It does not qualify a study.
    """
    need(type(state) is dict and set(state)==set(STRATA),'complete final four-head state')
    need(model['panel_key']==panel_key and model['model_id']==spec['bundle_fit_id'] and
         model['training_animals']==spec['training_animals'] and
         model['selection_pin']==pin(selection) and model['state_pin']==pin(state),
         'operator fitted model joins complete selection and four-head state')
    for stratum,head in state.items():
        phase=spec['bundle_fit_id']+'|refit|'+stratum;record=records[phase]
        need(type(head) is dict and set(head)=={'model','transform','training_animals','training_row_ids',
             'training_sessions','phase','resource_plan'},'exact final reference head state')
        need(head['phase']==phase and head['training_animals']==spec['training_animals'] and
             head['model']['setting']==selection['setting'] and
             head['transform']['variant']==spec['variant'] and head['transform']['stratum']==stratum,
             'final reference head exact selected setting fold variant and stratum')
        expected_rows=sorted(q['id'] for q in cohort_queries(study,spec['cohort']) if
            q['animal'] in spec['training_animals'] and q['stratum']==stratum)
        need(head['training_row_ids']==expected_rows and
             record['model_pin']==pin(head['model']) and record['transform_pin']==pin(head['transform']) and
             record['training_rows_pin']==pin(expected_rows) and record['resource_plan']==head['resource_plan'] and
             head['model']['row_ids']==expected_rows, 'final reference model transform row and resource joins')
        need(head['model']['feature_count']==head['transform']['feature_count'] and
             head['model']['fit_resource_plan']==head['resource_plan'], 'final model feature and resource geometry')
    return {'heads_joined':len(STRATA),'complete_selection_or_actual_execution_qualified':False}

def validate_reference_fit_records(plan, study, records, selections, final_states, fitted):
    expected=expected_reference_fits(plan)
    need(type(records) is dict and set(records)==set(expected), 'every required reference head fit; no survivor-only portfolio')
    panels={k:s for k,s in plan['panels'].items() if s['actor']=='operator'}
    need(type(selections) is dict and set(selections)==set(panels), 'every complete nested selection')
    need(type(final_states) is dict and set(final_states)==set(panels),'every final operator four-head state')
    for key,spec in panels.items():
        selection=selections[key]
        need(type(selection) is dict and set(selection)=={'loss_cells','selection'}, 'nested selection artifact')
        recomputed=numeric.select_setting(selection['loss_cells'],spec['training_animals'])
        need(selection['selection']==recomputed,'source-computed selection from complete frozen grid')
        validate_final_reference_bundle(study,key,spec,recomputed,final_states[key],
                                        fitted[spec['bundle_fit_id']],records)
    for key,cell in expected.items():
        row=records[key]
        required={'phase','training_animals','training_rows_pin','model_pin','transform_pin','resource_plan'}
        if cell['validation_animal'] is not None:
            required |= {'validation_predictions_pin','normalized_loss'}
        need(type(row) is dict and set(row)==required and row['phase']==key and
             row['training_animals']==cell['training_animals'],'full reference fit identity')
        panel=panels[cell['panel_key']]
        expected_rows=sorted(q['id'] for q in cohort_queries(study,panel['cohort']) if
            q['animal'] in cell['training_animals'] and q['stratum']==cell['stratum'])
        need(row['training_rows_pin']==pin(expected_rows),'every original row in exact reference fitting partition')
        for name in ('training_rows_pin','model_pin','transform_pin'):
            require_pin(row[name])
        if cell['validation_animal'] is not None:
            require_pin(row['validation_predictions_pin'])
            matching=[c for c in selections[cell['panel_key']]['loss_cells'] if
                      c['setting_id']==cell['setting']['id'] and c['animal']==cell['validation_animal'] and
                      c['stratum']==cell['stratum']]
            need(len(matching)==1 and matching[0]['loss']==row['normalized_loss'],'same observed validation loss')
    return {'required_fits':len(expected),'all_declared_records_joined':True,
            'actual_execution_or_source_custody_proven':False}

def validate_diagnostics(plan, diagnostics):
    expected={k:s for k,s in plan['panels'].items() if s['actor']=='operator'}
    need(type(diagnostics) is dict and set(diagnostics)==set(expected),'every reference diagnostic panel')
    from common import finite
    unavailable=0
    for key,spec in expected.items():
        panel=diagnostics[key]
        need(type(panel) is dict and set(panel)==set(spec['query_ids']),'complete diagnostic query support')
        for value in panel.values():
            need(type(value) is dict and set(value)=={'training_mean_log_seconds','persistence_status',
                                                    'persistence_log_seconds'},'diagnostic schema')
            finite(value['training_mean_log_seconds'])
            need(value['persistence_status'] in ('available','unavailable_history'),'explicit persistence status')
            if value['persistence_status']=='available':
                finite(value['persistence_log_seconds'])
            else:
                need(value['persistence_log_seconds'] is None,'no invented fallback for unavailable history')
                unavailable+=1
    return {'diagnostic_panels':len(expected),'persistence_unavailable_queries':unavailable,
            'persistence_is_protected_comparator':False}

def validate_programme_prerequisites(plan, native_report, ed_dispositions, null_reports,
                                    fit_admission, diagnostic_admission, candidate_method_admission):
    need(type(native_report) is dict and native_report.get('records')==111 and
         type(native_report.get('all_declared_quantities_match')) is bool,
         'complete native quantity comparison required; disagreement is an outcome')
    require_pin(native_report['policy_pin'])
    need(type(ed_dispositions) is dict and set(ed_dispositions)=={str(i) for i in range(1,11)},'all ED1-10 dispositions')
    unresolved=[]
    for key,value in ed_dispositions.items():
        need(type(value) is dict and set(value)=={'status','evidence_pin'},'ED disposition schema')
        need(value['status'] in ('quantitative_producer_verified','unresolved_producer','illustrative_noncomputational'),
             'explicit ED coverage status')
        require_pin(value['evidence_pin'])
        if value['status']!='quantitative_producer_verified':
            unresolved.append(key)
    selected_nulls={s['realization'] for s in plan['panels'].values()}-{'observed'}
    need(selected_nulls and set(null_reports)==selected_nulls,'mandatory null policy/results cannot be absent')
    for key,value in null_reports.items():
        need(type(value) is dict and set(value)=={'policy_pin','generation_pin','complete_fit_query_graph_pin'},
             'null complete generation/refit/query lineage')
        for operand in value.values():require_pin(operand)
    need(fit_admission['required_fits']==plan['counts']['reference_regularized_head_fits'] and
         fit_admission['all_declared_records_joined'] is True,'full reference work admission')
    need(diagnostic_admission['diagnostic_panels']==plan['counts']['reference_final_bundles'],'full diagnostics')
    expected={k for k,s in plan['panels'].items() if s['actor'] in ACCESS}
    need(type(candidate_method_admission) is dict and set(candidate_method_admission)==expected,
         'every candidate fit/search/method record independently admitted')
    for record in candidate_method_admission.values():
        need(type(record) is dict and set(record)=={'method_conformance_evidence','fit_search_ledger_pin',
              'source_state_lineage_pin'},'candidate method/inner-selection/resource evidence')
        for value in record.values():require_pin(value)
    return {'source_level_complete_core_dependencies_joined':True,'unresolved_ED_dispositions':unresolved,
            'native_reproduction_success_under_declared_policy':native_report['all_declared_quantities_match'],
            'native_quantity_comparison':native_report,
            'whole_paper_reproduced':False,'runtime_qualified':False,'reference_competence_qualified':False,
            'scientific_qualified':False,'independent_evidence_authenticity_not_proven_by_pins':True}

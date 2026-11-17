"""Complete source-owned campaign. Never selected merely by importing source."""
from pathlib import Path
from core import need, fresh, publish, encoded, pin
from authority import validate
from engine import Engine
from journal import Journal
from views import Views
from runtime import Runtime
from references import References
from authors import Authors
from panel_budget import PanelBudget
from schedule import panels,required_counts


def run(selection,budget,frozen):
    qualification=validate(selection,frozen['pin'],budget)
    root=fresh(selection['roots']['output'],budget)
    journal=None;runtime=None;references=None;authors=None;panel_budget=None;completed_panels=[]
    primary=None;later=[];failed_panel=None
    try:
        journal=Journal(root/'JOURNAL.jsonl',budget,selection['limits']['journal_bytes'],selection['limits']['journal_event_bytes'])
        emit=journal.append
        emit({'kind':'campaign_started','task':'NEURAL-058','selection':pin(encoded(selection)),
              'source':frozen['pin'],'origin':budget.origin,'deadline':budget.deadline,
              'qualification':qualification.observed})
        views=Views(selection['roots']['prepared'],selection['prepared'],root/'views',budget,selection['data_limits'])
        need(views.top['authority']==selection['prepared_authority'],'exact independently qualified prepared input selection')
        fixed=required_counts(views.roster)
        emit({'kind':'full_scope_admitted','task':'NEURAL-058','counts':fixed,'roster':views.roster,
              'prepared':selection['prepared'],'cohort':views.top['cohort']})
        engine=Engine(selection['engine'],budget,emit)
        runtime=Runtime(selection,frozen,budget,engine,emit,qualification)
        references=References(runtime,views,selection,budget,emit);selected=references.build()
        counts=required_counts(views.roster,selected['choices'])
        need(len(references.cv)==160 and len(references.models)==counts['reference_final_fits']
             and len(references.predictions)==counts['reference_session_predictions'],'complete actual reference producers')
        authors=Authors(runtime,views,references,selection,budget,emit)
        for panel in panels():
            profile=selection['panel_limits'][panel['id']]
            panel_budget=PanelBudget(budget,profile,panel['id'],engine,selection['provider'],emit,journal)
            emit({'kind':'panel_started','task':'NEURAL-058','panel':panel,'profile':profile,'scope':panel_budget.snapshot()})
            if panel['mode']=='F':
                # One global method is sealed/fitted before any held animal is
                # mounted. All later13 animals share its remaining ceiling.
                authors.construct(panel,'global',panel_budget,panel_budget.deadline)
                for animal in views.roster['eval_animals']:
                    for sid in views.animal_sessions(animal):
                        authors.infer_session(panel,animal,sid,panel_budget,panel_budget.deadline)
            else:
                for i,animal in enumerate(views.roster['eval_animals']):
                    cutoff=panel_budget.episode_cutoff(i,13)
                    authors.construct(panel,animal,panel_budget,cutoff)
                    for sid in views.animal_sessions(animal):
                        authors.infer_session(panel,animal,sid,panel_budget,cutoff)
            ending=panel_budget.finish(panel);panel_budget=None
            completed_panels.append(panel['id'])
        need(len(authors.methods)==168 and len(authors.fits)==168 and len(authors.outputs)==696,'complete24 panels/168 contexts/696 session outputs')
        payload={'schema':'neural058_production_complete_v1','task':'NEURAL-058',
                 'selection':pin(encoded(selection)),'source':frozen['pin'],'prepared':selection['prepared'],
                 'roster':views.roster,'counts':counts,'completed_panels':completed_panels,
                 'reference_selection':selected,
                 'reference_cv':{r+'/'+c+'/'+str(f):p['operation'] for (r,c,f),p in references.cv.items()},
                 'reference_models':{r+'/'+c:p['operation'] for (r,c),p in references.models.items()},
                 'reference_predictions':{r+'/'+c+'/'+s:p['operation'] for (r,c,s),p in references.predictions.items()},
                 'methods':authors.methods,'author_transcripts':authors.transcripts,'numeric_slots':authors.numeric_slots,
                 'candidate_fits':{k:p['operation'] for k,p in authors.fits.items()},
                 'candidate_outputs':{p+'/'+s:v['operation'] for (p,s),v in authors.outputs.items()},
                 'products':runtime.results,'semantic_qualification_pending':True,
                 'protected_targets_read':False,'scientifically_qualified':False,
                 'budget_before_publication':budget.record()}
        budget.reserve_write(selection['limits']['complete_metadata_bytes'])
        body=encoded(payload);need(len(body)<=selection['limits']['complete_metadata_bytes'],'complete graph must fit without pruning')
        complete=publish(root/'COMPLETE.json',body,budget,readonly=True)
        emit({'kind':'campaign_product_written','task':'NEURAL-058','complete':complete,'protected_targets_read':False})
        journal.close();journal=None;budget.tick()
        return {'complete':complete,'output':str(root),'source':frozen['pin'],'selection':payload['selection'],
                'natural_external_closure_still_required':True,'semantic_qualification_pending':True}
    except BaseException as error:
        primary=error
        if panel_budget is not None:
            failed_panel=panel_budget.snapshot()
            try:failed_panel=panel_budget.fail()
            except BaseException as cleanup:
                failed_panel=panel_budget.snapshot();failed_panel['failure_publication_or_scope_closure_unknown']=True
                later.append(cleanup)
        failure={'task':'NEURAL-058','complete':False,'first_failure_type':type(error).__name__,
                 'completed_panels':completed_panels,'failed_panel_accounting':failed_panel,'attempted_native_operations':0 if runtime is None else len(runtime.results),
                 'completed_candidate_predictions':0 if authors is None else len(authors.outputs),
                 'completed_reference_selection_fits':0 if references is None else len(references.cv),
                 'read_reserved_bytes':budget.read_bytes,'write_reserved_bytes':budget.write_bytes,
                 'full_details':'retained journal and attempted products; incomplete publication may require inspection',
                 'unattempted_remainder_retained_as_scope':True,'scientifically_qualified':False}
        if journal is not None:
            try:journal.append({'kind':'campaign_failed',**failure})
            except BaseException as publication:later.append(publication)
        error.failure_record=failure
        raise
    finally:
        if journal is not None and journal.fd is not None:
            try:journal.close()
            except BaseException as cleanup:later.append(cleanup)
        if later:
            combined=BaseExceptionGroup('campaign primary and ordered cleanup/publication failures',([primary] if primary else [])+later)
            combined.failure_record=getattr(primary,'failure_record',{'complete':False,'closure_unknown':True})
            raise combined

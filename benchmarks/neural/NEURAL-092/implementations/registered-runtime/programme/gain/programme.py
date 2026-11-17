"""Scientific composition; only an acquired host092 coordinator is admitted."""
from .authority import require_live
from .constants import MODELS
from .cost import Attempt,session_plan
from .features import inspect_metadata
from .host import NativeHost,TrainingCapture,QueryCapture,FrozenPredictions
from .reference import grid_session,validation_session,refit_session,predict_session,make_reference_record,ReferenceSession
from .scoring import admit_prediction,score_session,aggregate_panel
from prospective.phase_projection import project_prediction_index
from prospective.phase_order import validate_phase_claim

def run_programme(host,attempt):
    # Caller retains this exact engineering owner through success or raw-first
    # rethrow, including cleanup/publication tails occurring after a host write.
    if type(attempt)is not Attempt or attempt.first is not None or attempt.events:raise TypeError('fresh caller-owned Attempt required')
    frozen=None;result=None;admitted=False
    try:
        # Attempt exists before the hard gate. No array, input/header capture or
        # numerical work precedes genuine admission; dictionaries never pass.
        require_live(host,'full32 gain programme')
        if not isinstance(host,NativeHost):raise TypeError('genuine reviewed native host required')
        admitted=True
        panel=host.describe_complete_panel()
        if type(panel)is not dict or len(panel)!=32:raise ValueError('complete source-selected32 session descriptors')
        metadata={};infos={};plans={};mice={}
        for sid,meta in panel.items():
            if type(sid)is not str or meta['session_id']!=sid or type(meta['mouse_id'])is not str or not meta['mouse_id']:raise ValueError('session/animal identity')
            info=inspect_metadata(meta);metadata[sid]=meta;infos[sid]=info;mice[sid]=meta['mouse_id']
            plans[sid]=session_plan(*(len(info['rows'][p])for p in ('FIT','VALIDATION','QUERY')),len(info['unit_ids']),len(info['vocabulary']))
        if len(set(mice.values()))!=32:raise ValueError('selected32 distinct mice; no transfer')
        # The host must reserve complete simultaneous panel output/custody and
        # per-session kernel/capture peaks, not only one favorable fit's arrays.
        host.admit_full_resources(plans)
        original_index=host.capture_original_index()
        prediction_view=project_prediction_index(original_index,list(panel))
        for row in prediction_view['sessions']:
            if row['mouse_id']!=mice[row['session_id']]:raise ValueError('original index/captured metadata animal join')
        host.freeze_design_and_issue_prediction_view(prediction_view)
        references={sid:make_reference_record(metadata[sid],infos[sid])for sid in panel}
        attempt.references=references
        attempt.full_plans=plans
        # Whole-panel barriers: every grid fit precedes validation, and all
        # method selections precede any refit. No per-unit phase interleaving.
        for producer,barrier in ((grid_session,host.freeze_fit_grid),
                                 (validation_session,host.record_validation_and_freeze_selection),
                                 (refit_session,host.freeze_refit_models)):
            for sid in panel:
                capture=None;local=Attempt()
                try:
                    capture=host.open_training(sid)
                    if not isinstance(capture,TrainingCapture):raise TypeError('typed real training capture required')
                    if capture.metadata!=metadata[sid]:raise ValueError('described/captured original metadata mismatch')
                    producer(capture.metadata,capture.fit_counts,capture.validation_counts,references[sid],host,attempt.calls)
                    host.retain_reference_dispositions(sid,references[sid],attempt.calls)
                except BaseException as error:local.fail('training_body',error)
                finally:
                    if capture is not None:local.cleanup('training_close',lambda:capture.close())
                for occurrence in local.events:attempt.fail(occurrence['where'],occurrence['error'])
                if local.first is not None:raise local.first
            barrier(references)
        for sid in panel:
            predict_session(metadata[sid],references[sid],host,attempt.calls)
            host.retain_reference_dispositions(sid,references[sid],attempt.calls)
        if any(not r.complete for r in references.values()):raise ValueError('required reference fit/prediction failure; no complete gain endpoint')
        candidates=host.capture_complete_candidate_predictions(metadata)
        if type(candidates)is not dict or set(candidates)!=set(panel):raise ValueError('complete candidate panel before targets')
        for sid in panel:admit_prediction(candidates[sid],metadata[sid],infos[sid])
        frozen=host.freeze_and_readback_all_predictions(references,candidates)
        if not isinstance(frozen,FrozenPredictions):raise TypeError('real immutable prediction capture required')
        # Revalidate the entire immutable readback BEFORE opening any QUERY.
        frozen_references={};frozen_candidates={}
        for sid in panel:
            r=frozen.read_reference(sid);c=frozen.read_candidate(sid)
            if type(r)is not ReferenceSession or r.session_id!=sid or not r.complete or r.info!=infos[sid]or set(r.predictions)!=set(MODELS):raise ValueError('complete bound fixed-reference readback')
            for model in MODELS:
                admit_prediction({'session_id':sid,'unit_ids':list(infos[sid]['unit_ids']),'query_ids':[x['id']for x in infos[sid]['rows']['QUERY']],'means':r.predictions[model]},metadata[sid],infos[sid])
            admit_prediction(c,metadata[sid],infos[sid]);frozen_references[sid]=r;frozen_candidates[sid]=c
        sessions={}
        for sid in panel:
            capture=None;local=Attempt()
            try:
                capture=host.open_private_query(frozen,sid)
                if not isinstance(capture,QueryCapture):raise TypeError('real private target capture required')
                sessions[sid]=score_session(metadata[sid],frozen_references[sid],frozen_candidates[sid],capture.counts,host,attempt.calls)
            except BaseException as error:local.fail('private_query_body',error)
            finally:
                if capture is not None:local.cleanup('private_query_close',lambda:capture.close())
            for occurrence in local.events:attempt.fail(occurrence['where'],occurrence['error'])
            if local.first is not None:raise local.first
        result=aggregate_panel(sessions,mice)
        host.publish_private_scores(frozen,result,attempt)
        # Original source/run.py score/reference remains the actual observed
        # route. A genuine host must execute that original isolated programme;
        # a claimed investigation dictionary is not a substitute for its call.
        observation=host.release_observed_query_and_execute_original_investigation(frozen)
        phase_claim=validate_phase_claim(host.export_phase_claim())
        result={'prediction':result,'original_observed_investigation':observation,'phase_claim_grammar_only':phase_claim,'qualified':False}
    except BaseException as error:
        # A delegated first already retained is not a second failed operation.
        if attempt.first is not error:attempt.fail('programme_body',error)
    finally:
        if frozen is not None:attempt.cleanup('frozen_capture_close',lambda:frozen.close())
        # No host interaction is allowed following hard admission refusal.
        # Only original acquired coordinator authority reaches this branch.
        if admitted:
            attempt.cleanup('terminal_attempt_publication',lambda:host.retain_terminal_attempt(attempt))
    attempt.finish()
    return result

def main():
    # An ordinary CLI invocation cannot construct a native host from options.
    attempt=Attempt()
    return run_programme(None,attempt)

if __name__=='__main__':main()

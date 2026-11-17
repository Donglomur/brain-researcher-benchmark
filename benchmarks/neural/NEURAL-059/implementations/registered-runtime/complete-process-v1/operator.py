"""Actual owner of the complete N059 attempt and original failure transport."""
from pathlib import Path
from .core import encode, pin, need, literal
from .selection import validate
from .donor.budget import Budget
from .donor.journal import Journal
from .donor.common import FailureCarrier
from .transport import OCIStudy
from .runner import Programme
from .publication import document
from .managed_io import bind


def run(selection,origin,cpu_origin,bootstrap_read_bytes):
    validate(selection)
    budget=Budget(origin,selection['budget'],cpu_origin=cpu_origin)
    budget.read(bootstrap_read_bytes); budget.check('after complete source/bootstrap capture')
    root=literal(selection['output_root']); code=literal(selection['deployment']['code_root'])
    need(not root.is_relative_to(code) and not code.is_relative_to(root), 'private output separate from immutable source')
    carrier=FailureCarrier(); journal=Journal(root,budget,carrier)
    managed_state=None
    host=None; programme=None; original=None; error=None; budget_original=None; failure_original=None
    try:
        managed_state=bind(budget)
        journal.json('SELECTION.json',selection)
        host=OCIStudy(selection,budget,journal,carrier)
        programme=Programme(selection,host,budget,journal)
        original=programme.run()
        need(all(r['closed'] for r in host.rows),'every actual constructed role closed')
        need(carrier.first is None and not budget.unknown,'no unresolved original process/cost/custody failure')
        host.poll(); journal.json('RESULT.json',original)
    except BaseException as caught:
        error=caught; carrier.fail(caught,'complete N059 operator')
        failure={'status':'failed','error_type':type(caught).__name__,
            'completed_scope_is_not_inferred_from_prefix':True,
            'full_expected_sessions':29,'full_expected_animals':13,'full_expected_labs':7,
            'declared_reference_slots':61132,'actual_declared_slot_prefix':
                None if programme is None else programme.declared_slots,
            'lifecycle':None if programme is None or programme.lifecycle is None else programme.lifecycle.report(),
            'actor_attempts':None if programme is None else programme.actor_attempts,
            'model_reservations':None if programme is None else [
                {'cell':list(k),'account':v} for k,v in programme.model_account.items()],
            'managed_scientific_io':None if managed_state is None else managed_state.snapshot(),
            'failed_work_interpretation':'Incomplete cells retain attempted prefixes/unknown totals; original successful-only ledger is not a complete failed-cost report'}
        if host is not None:
            try: failure['containment']=host.contain()
            except BaseException as secondary:
                carrier.fail(secondary,'independent owned containment'); failure['containment_error_type']=type(secondary).__name__
        try: failure_original=document(journal,'FAILURE',failure,selection['budget']['write_bytes'])
        except BaseException as secondary: carrier.fail(secondary,'full failure publication')
    finally:
        # This compact final record points to complete original role/RPC/process
        # files. It never creates a native/scientific qualification receipt.
        try:
            budget_original=document(journal,'OWNER_BUDGET_BEFORE_TERMINAL',
                {'owner_budget':budget.snapshot(),'managed_scientific_io':None if managed_state is None else managed_state.snapshot()},
                selection['budget']['write_bytes'])
        except BaseException as publication_error:
            carrier.fail(publication_error,'complete owner budget publication')
            if error is None: error=publication_error
        outcome={'schema':'n059_complete_operator_outcome_v1','status':'failed' if error else 'closed',
            'source':selection['source_sha256'],'selection':pin(selection),'qualification':False,
            'scientific_ready':False,'old93_query_pilot':'separate unchanged',
            'worker_count':0 if host is None else len(host.rows),
            'all_worker_closures':False if host is None else all(r['closed'] for r in host.rows),
            'original_budget_manifest':budget_original,'original_failure_manifest':failure_original,
            'managed_counters_before_terminal':{k:getattr(budget,k) for k in
                ('read_bytes','write_bytes','live_bytes','files','model_calls','stream_bytes')},
            'whole_cgroup_cpu_last_observed':None if host is None else host.last_cpu,
            'native_IO':'not inferred from tmpfs or managed counters; package reads and native file churn unmeasured',
            'failure_transport':{'count':len(carrier.failures),'first_type':None if error is None else type(error).__name__},
            'external_supervisor_must_observe_operator_exit_and_final_whole_group':True}
        durable=journal.terminal(outcome)
    if error is not None: raise error
    need(durable,'complete original outcome publication')
    budget.check('after final outcome publication')
    return 0

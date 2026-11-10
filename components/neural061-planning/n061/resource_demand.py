"""Complete source-operation demand skeleton; no invented native extents/caps."""
from dataclasses import dataclass
from .contracts import need
from .access import author_contexts
from .admission import MISSING_PRODUCERS,MissingNativeProducers

@dataclass(frozen=True)
class Operation:
    ordinal:int
    kind:str
    owner:tuple
    operands:tuple
    input_bytes:object=None
    output_bytes:object=None
    state_bytes:object=None
    native_limits:object=None
    provider_limits:object=None

@dataclass(frozen=True)
class OperationPlan:
    catalogue:object
    operations:tuple
    fairness:str
    missing:tuple=MISSING_PRODUCERS
    def require_native_allocation(self):
        # Even finite source counts do not allocate actual owners or capacity.
        raise MissingNativeProducers('complete measured operation/capacity allocation')

def compile_plan(cat):
    cat.validate();rows=[]
    def add(kind,owner,*operands):rows.append(Operation(len(rows),kind,owner,tuple(operands)))
    for sid in cat.source+cat.evaluation:
        for kind in ('original_capture','unit_rate_QC_projection','window_target_projection','public_private_publication','input_readback','capture_cleanup'):
            add(kind,('preparation',),sid)
        for cell in cat.cells:add('fixed_matching',('preparation',),sid,cell[1:])
    for cell in cat.cells:
        for arm in cat.policy.reference_arms:
            own=('reference',cell,arm)
            add('source_views',own,cat.source)
            for config in range(6):
                for fold in range(5):
                    for kind in ('reference_cv_fit','reference_cv_predict','reference_cv_state_retire'):
                        add(kind,own,config,fold)
            for kind in ('reference_select','reference_final_fit','reference_state_capture'):
                add(kind,own)
            for sid in cat.evaluation:add('reference_query_predict',own,sid)
            add('reference_state_retire',own)
    for panel in cat.policy.panels:
        for context in author_contexts(cat,panel):
            request=context.request();own=('panel',panel)
            add('author_context',own,context.animal,context.cell,context.arm)
            add('method_capture_observe',own,context.animal,context.cell,context.arm)
            cells=cat.cells if panel[0]=='F' else (context.cell,)
            for cell in cells:
                arms=cat.policy.candidate_arms if panel[0]=='F' else (context.arm,)
                for arm in arms:
                    add('candidate_source_views',own,cell,arm)
                    if panel[1]=='T1':add('same_cell_arm_tool_lease',own,cell,arm)
                    for kind in ('candidate_fit','state_capture_observe'):
                        add(kind,own,context.animal,cell,arm)
                    for sid in cat.evaluation if panel[0]=='F' else context.evaluation_sessions:
                        for kind in ('query_projection','candidate_predict','prediction_capture_observe'):
                            add(kind,own,context.animal,cell,arm,sid)
                    add('candidate_state_retire',own,context.animal,cell,arm)
                    if panel[1]=='T1':add('tool_lease_retire',own,cell,arm)
            add('method_retire',own,context.animal,context.cell,context.arm)
    for kind,owner in [('complete_collection_publish','production'),('independent_outside_observation','observer'),('target_barrier','grading'),('protected_target_capture','grading'),('same_support_scoring','grading'),('family_report','grading'),('independent_cleanup_and_outside_tail','observer')]:
        add(kind,(owner,))
    need(tuple(x.ordinal for x in rows)==tuple(range(len(rows))),'closed original operation order')
    return OperationPlan(cat,tuple(rows),'Equal total selected F/I panel ceilings; all I contexts partition same panel, no copied full budget or arbitrary tiny slice; actual amounts UNKNOWN.')

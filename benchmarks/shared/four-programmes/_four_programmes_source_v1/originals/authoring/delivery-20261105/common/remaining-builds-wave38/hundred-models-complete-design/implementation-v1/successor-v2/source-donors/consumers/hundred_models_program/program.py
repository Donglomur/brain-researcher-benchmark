"""Compose the complete catalog compiler with explicit-convention inference.

No empirical file readers, models, checkpoints, or fitting are present here.
"""
from dataclasses import dataclass
from . import catalog
from . import inference


@dataclass(frozen=True)
class BoundProgram:
    compiled_catalog_bytes: bytes
    compiled_catalog_sha256: str
    scope: inference.Scope
    limits: inference.WorkLimits


def bind_program(protocol_raw, inventory_raw, graph_bindings_raw, admitted_graph_pin, *,
                 schedule, layer_null_rule, comparisons, limits):
    """Bind every99 model's source layers before any inference stream is read."""
    result = catalog.compile_catalog(protocol_raw, inventory_raw, graph_bindings_raw,
        admitted_graph_pin, require_complete=True)
    model_layers = tuple((key, tuple(result['models'][key]['layers'])) for key in result['model_order'])
    scope = inference.Scope(model_layers=model_layers,
        layer_catalog_sha256=inference.canonical_digest(model_layers), schedule=schedule,
        layer_null_rule=layer_null_rule, comparisons=tuple(comparisons),
        subjects=inference.SUBJECTS, rois=inference.ROIS, stimuli=inference.STIMULI,
        protocol_sha256=catalog.PROTOCOL_PIN['sha256'])
    inference.validate_scope(scope, limits)
    body = catalog.encoded(result)
    return BoundProgram(body, catalog.pin(body)['sha256'], scope, limits)


def validate_program(program):
    catalog.need(type(program) is BoundProgram, 'compiled complete program binding')
    catalog.need(catalog.pin(program.compiled_catalog_bytes)['sha256'] == program.compiled_catalog_sha256,
                 'compiled catalog bytes unchanged')
    value = catalog.strict(program.compiled_catalog_bytes)
    catalog.need(value['complete'] is True and value['protocol'] == catalog.PROTOCOL_PIN
                 and value['task_id'] == catalog.TASK and value['profile'] == catalog.PROFILE
                 and tuple(value['model_order']) == inference.MODELS,
                 'full99 source catalog still bound')
    layer_rows = tuple((key, tuple(value['models'][key]['layers'])) for key in value['model_order'])
    catalog.need(layer_rows == program.scope.model_layers
                 and all(value['models'][key]['metadata_closure_complete'] is True for key in value['model_order']),
                 'no catalog-to-inference scope substitution')
    inference.validate_scope(program.scope, program.limits)


def run_program(program, observed_rois, null_batches):
    """Consumes all17 observed and1000-perROI null frames; no smaller fallback."""
    validate_program(program)
    result = inference.run_inference(program.scope, observed_rois, null_batches, limits=program.limits)
    return {'schema':'hundred_models_bound_inference_result_v1', 'task_id':catalog.TASK,
            'compiled_catalog':catalog.pin(program.compiled_catalog_bytes),
            'ordered_layer_catalog_sha256':program.scope.layer_catalog_sha256,
            'schedule_sha256':program.scope.schedule.schedule_sha256,
            'inference':result, 'actual_inputs_authenticated_by_this_program':False,
            'historical_reproduction_claimed':False, 'scientific_execution_qualified':False}

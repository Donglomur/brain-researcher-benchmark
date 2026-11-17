"""Owner-level source constraints around concrete graph/native components."""
from .codec import need
from banc_graph_core.banc_graph import prepare_native_request as _prepare, NativeParameters


def prepare_native_request(*args, graph_variant, parameters, **kwargs):
    """Retain the original PSOCK calculator's fixed count threshold as well
    as its full-global-graph rebuild. The immutable helper remains unchanged.
    """
    need(type(parameters) is NativeParameters, 'exact native parameter object')
    if graph_variant.endswith('/parallel_rebuild_default_global'):
        need(parameters.count_thresh==5,
             'original banc_influence_loop.R189-190 parallel constructor hardcodes count_thresh=5')
    return _prepare(*args,graph_variant=graph_variant,parameters=parameters,**kwargs)


def native_r_job(request, seed_requests, *, metadata_types, edge_types, program_identity):
    """Build exact typed descriptors consumed by source-owned banc_read_r_job.

    Explicit column types avoid implicit ID/numeric/factor coercion. The
    concrete R reader constructs job$metadata and job$edges data.frames.
    Native dtype and historical parity remain qualification gates.
    """
    from .r_bridge import make_native_r_job
    return make_native_r_job(request,seed_requests,metadata_types=metadata_types,
                             edge_types=edge_types,program_identity=program_identity)

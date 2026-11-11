"""Fixed concrete scientific dispatch. No dynamic import, callback or user shell."""
import inspect
from . import numerics,preparation,simulation,memory,spatial,aggregation,source_semantics,external
from .custody import need
from .guard import integer

KERNELS={
 'external_psth':external.task_psth,'external_rtt_onsets':external.rtt_onsets,'external_maze_onsets':external.maze_onsets,
 'source_dense_from_variates':source_semantics.dense_from_variates,
 'source_structured_from_variates':source_semantics.structured_from_variates,
 'source_local_probability':source_semantics.local_probability,
 'source_strong_pairs':source_semantics.strong_pairs_literal,
 'source_centroid_decode':source_semantics.centroid_decode,
 'source_ridge_retrieval':source_semantics.ridge_retrieval,
 'source_mutate_time_prefix':source_semantics.mutate_time_prefix,
 'calcium_prepare':preparation.calcium,'ephys_prepare':preparation.ephys,
 'time_chunks':preparation.time_chunks,'shuffle_schedule':preparation.shuffle_schedule,
 'subsample':preparation.subsample,'behavioural_states':preparation.behavioural_states,
 'fluorescence_bin':preparation.fluorescence_bin,
 'zscore':numerics.zscore,'spatial_split':numerics.spatial_split,
 'spectra':numerics.spectra,'exponent':numerics.exponent,'dmd':numerics.dmd,
 'pc_crosscorrelation':numerics.pc_crosscorrelation,'rotation_summary':numerics.rotation_summary,
 'connectivity':simulation.connectivity,'ou_theory':simulation.ou_theory,
 'observed_predictor':simulation.observed_predictor,'integrate':simulation.integrate,
 'imaging_noise':simulation.imaging_noise,
 'memory_embed':memory.embed,'memory_drive':memory.drive_patterns,
 'memory_readouts':memory.readouts,'binary_decode':memory.binary,'zero_shot_decode':memory.zero_shot,
 'subspace_map':memory.subspace_map,'spatial_pairs':spatial.pair_statistics,'pc_maps':spatial.pc_maps,
 'population':aggregation.population,'paired_test':aggregation.paired_test,
 'normalized_acg':aggregation.normalized_acg,'cluster_improvement':aggregation.cluster_improvement
}

def dispatch(name,arguments,*,reservation,budget):
    need(name in KERNELS and type(arguments)is dict,'fixed named kernel and exact keyword arguments')
    integer(reservation,1);signature=inspect.signature(KERNELS[name])
    signature.bind(**arguments) # no unknown parameters or omitted required scientific choices
    budget.reserve_array(reservation)
    try:
        result=KERNELS[name](**arguments);budget.check()
        return result
    finally:budget.release_array(reservation)

def flatten(value):
    """JSON skeleton + numeric arrays; no implicit stringification of predictions."""
    import numpy as np
    arrays={}
    def visit(v):
        if isinstance(v,np.ndarray):
            need(v.dtype.kind in 'biufc'and np.isfinite(v).all(),'finite supported complete output array')
            key='a'+str(len(arrays));arrays[key]=v
            return {'array':key,'shape':list(v.shape),'dtype':v.dtype.str}
        if isinstance(v,np.generic):return visit(v.item())
        if type(v)is dict:
            need(all(type(k)is str and k for k in v),'string output keys')
            return {k:visit(x)for k,x in v.items()}
        if type(v)in (tuple,list):return [visit(x)for x in v]
        need(v is None or type(v)in(bool,int,float,str),'portable explicit output value')
        return v
    return visit(value),arrays


"""Exact deterministic choices for the prospective native reference workers."""
import hashlib
from core import encoded, need


def seeds(role, fold, epoch=None):
    need(role in ('C','J') and (fold == 'full' or type(fold) is int and 0 <= fold < 5), 'reference role/fold seed key')
    if epoch is None:
        key = ['NEURAL058-reference-v1','initialization',role,fold,580058]
        digest = hashlib.sha256(encoded(key)).digest()
        return {'key':key,'sha256':digest.hex(),'torch_cpu_and_python':int.from_bytes(digest[:8],'big') & ((1<<63)-1)}
    need(type(epoch) is int and epoch >= 0, 'zero-based epoch')
    key = ['NEURAL058-reference-v1','epoch-permutation',role,fold,epoch,580058]
    digest = hashlib.sha256(encoded(key)).digest()
    return {'key':key,'sha256':digest.hex(),'numpy_PCG64':int.from_bytes(digest[:16],'big')}


RECIPE = {
    'version':'neural058-reference-numerics-v1',
    'ridge_objective':'sum(normalized_weight * squared_error) + alpha * squared_nonintercept_coefficient_norm',
    'feature_statistics':'float64 complete training-animal weighted means/variances; fixed roster/window/timestamp order',
    'target_scaling':'training-fold mean/SD only; zero SD is explicit failure',
    'logical_batch_windows':32,
    'microbatch_windows':1,
    'units_per_microbatch':'all original units, never sampled',
    'batch_loss':'M * sum(w * ((velocity_error**2 + speed_error**2)/2)) over every batch window and timestamp',
    'w':'1/(training_animals * sessions_of_animal * windows_of_session * timestamps_of_window)',
    'M':'ceil(total_training_windows/32), including incomplete final batch',
    'gradient_order':['zero gradient once','one-window backward accumulation in fixed epoch permutation order',
                      'clip accumulated global L2 norm once to1','one AdamW step'],
    'adamw':{'betas':[0.9,0.999],'eps':1e-8,'amsgrad':False},
    'initialization':'reset Python and torch CPU RNG from seeds(role,fold); initialize parameters on CPU before device transfer',
    'configuration_pairing':'identical role/fold architecture initialization and epoch permutation prefixes across all grid configurations; no traversal-order RNG state',
    'deterministic_algorithms':True,
    'model_and_optimizer_dtype':'float32',
    'scaler_and_score_dtype':'float64',
    'forest':{'random_state':580058,'n_jobs':1,'n_estimators':512,'criterion':'squared_error','bootstrap':False,'max_features':1.0},
    'no_evaluation_target_selection':True,
}

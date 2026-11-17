"""Exact released state-model calls; unknown empirical BMM producer is explicit."""
import types
from .domain import Refusal, MissingDefinition, Pin, closed

SOURCES = {'bmm': '5f35c0cd7c1ac51a8dd2de8d44cf5c6311952627cbf589458f8c9f2462125143',
           'lg': 'c8c0574f52b66da1cd16c1a3ab4a29f47ae62483b892d0cd7dc54e87a570718c'}

def load_state_module(store, pin, family):
    if pin.sha256 != SOURCES[family]: raise Refusal('state source')
    module = types.ModuleType('trial_session_original_'+family)
    exec(compile(store.read(pin), pin.path, 'exec'), module.__dict__)
    return module

def require_contiguous(indices, segments):
    if len(indices) != len(segments) or not indices: raise Refusal('state sequence support')
    for a,b,sa,sb in zip(indices, indices[1:], segments, segments[1:]):
        if sa == sb and b != a+1: raise MissingDefinition('masked trial gap needs selected state transition law')
    if len(set(segments)) != 1: raise Refusal('state call must be one actual contiguous segment')

def released_bmm(module, decoder_probabilities, initialization, sequence, segments, method, priors=None):
    import numpy as np
    require_contiguous(sequence, segments)
    d = np.asarray(decoder_probabilities).reshape(-1)
    if len(d) != len(sequence) or not np.isfinite(d).all() or np.any(d <= 0) or np.any(d >= 1):
        raise Refusal('Beta-domain decoder probabilities; no silently selected clipping')
    closed(initialization, ('pi', 'a', 'phi', 'beta_a', 'beta_b', 'tol', 'cutoff'), 'BMM initialization')
    args = (d, initialization['pi'], initialization['a'], initialization['phi'],
            initialization['beta_a'], initialization['beta_b'])
    if method == 'bmm_hmm': model = module.BMM_HMM(*args, tol=initialization['tol'])
    elif method in ('empirical_bmm_hmm', 'rrr_bmm_hmm'):
        # A concentration/rate dictionary cannot establish the missing empirical fit producer.
        raise MissingDefinition('original empirical HMM/BMM prior-fit caller and sign convention not recovered')
    else: raise Refusal('BMM route')
    model.update(d, cutoff=initialization['cutoff'])
    labels, p = module.posterior_inference(model, d)
    return {'probability': np.asarray(p), 'labels': np.asarray(labels), 'model': model,
            'readout': 'released_forward_backward_offline', 'causal': False}

def released_lg(module, decoder, train_decoders, train_behaviors, sequence, segments, method, config):
    require_contiguous(sequence, segments)
    closed(config, ('constructor', 'n_samples', 'is_low_snr'), 'LG configuration')
    if method == 'lg_ar1':
        model = module.LG_AR1(**config['constructor'])
        p, rho, theta, mu = model.forward(decoder, is_oracle=False, n_samples=config['n_samples'], is_low_snr=config['is_low_snr'])
        return {'prediction': p, 'parameters': {'rho':rho,'theta':theta,'mu':mu}, 'readout': 'released_posterior_predictive', 'causal': False}
    if method in ('empirical_lg_ar1', 'rrr_lg_ar1'):
        if not train_decoders or len(train_decoders) != len(train_behaviors): raise Refusal('non-target training prior support')
        model = module.MultiSession_LG_AR1(**config['constructor'])
        p, rho, theta, mu = model.forward(decoder, train_decoders, train_behaviors,
                          n_samples=config['n_samples'], is_low_snr=config['is_low_snr'])
        return {'prediction': p, 'parameters': {'rho':rho,'theta':theta,'mu':mu}, 'readout': 'released_latent_state_mean_not_paper_observation',
                'causal': False, 'paper_equivalence': False}
    raise Refusal('LG route')

def oracle_diagnostic(barrier, module, decoder, initialization):
    from .publication import require_result_barrier
    require_result_barrier(barrier)
    # Query truth is only visible after both arms' immutable prediction barrier.
    args = (decoder, initialization['pi'], initialization['a'], initialization['phi'],
            initialization['beta_a'], initialization['beta_b'])
    model = module.Oracle_BMM_HMM(*args, tol=initialization['tol'])
    return module.posterior_inference(model, decoder)

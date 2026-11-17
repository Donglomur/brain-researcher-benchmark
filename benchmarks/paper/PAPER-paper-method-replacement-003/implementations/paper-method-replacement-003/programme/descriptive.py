"""Source-grounded descriptive products; no published target-table substitution."""
from .cohort import CLASSES,SupportError

def true_spike_fraction(violation_count,spike_count,mean_rate,refractory_seconds):
    """Article MathML M3; undefined support stays undefined, never clipped."""
    import numpy as np
    nv=np.asarray(violation_count);n=np.asarray(spike_count);rate=np.asarray(mean_rate)
    if refractory_seconds not in (0.001,0.0005):raise SupportError('original one-ms or complex-spike half-ms support required')
    if not (nv.shape==n.shape==rate.shape) or np.any(n<=0) or np.any(rate<=0) or np.any(nv<0):
        raise SupportError('invalid aligned contamination operands')
    squared=1-nv/(n*rate*refractory_seconds)
    if np.any(squared<0) or not np.isfinite(squared).all():raise SupportError('true-spike estimate outside defined support')
    return np.sqrt(squared)

def curation_counts(members):
    """Every retained/excluded/unresolved row counted with biological identity."""
    counts={};seen=set()
    for member in members:
        member.validate();key=(member.population,member.key)
        if key in seen:raise SupportError('duplicate curation disposition')
        seen.add(key);group=(member.population.value,member.disposition,member.reason)
        counts[group]=counts.get(group,0)+1
    return tuple({'population':p,'disposition':d,'reason':r,'units':n} for (p,d,r),n in counts.items())

def latent_decoder_grid(encoder,decoder,input_array,unit_keys,*,component_standard_deviations,standardized_axis_positions):
    """Complete 8×8 S5 grid; representative scale is required, never guessed."""
    import numpy as np
    import torch
    from sklearn.decomposition import PCA
    if component_standard_deviations is None or len(component_standard_deviations)!=2:
        raise SupportError('original representative latent-grid scale producer missing')
    if standardized_axis_positions is None or len(standardized_axis_positions)!=8:
        raise SupportError('exact eight original latent-axis positions are required')
    if len(input_array)!=len(unit_keys) or len(set(unit_keys))!=len(unit_keys):raise SupportError('latent input identity mismatch')
    with torch.no_grad():
        latent=encoder(input_array).mean.detach().cpu().numpy()
    if latent.shape!=(len(unit_keys),10):raise SupportError('complete ten-dimensional latent required')
    pca=PCA(n_components=2);coordinates=pca.fit_transform(latent)
    octiles=np.asarray(standardized_axis_positions,dtype=float)
    if not np.isfinite(octiles).all() or not np.all(np.diff(octiles)>0):
        raise SupportError('latent grid positions must be finite and increasing')
    axis0=octiles*component_standard_deviations[0];axis1=octiles*component_standard_deviations[1]
    grid=np.asarray([(a,b) for a in axis0 for b in axis1]);restored=pca.inverse_transform(grid)
    parameter=next(decoder.parameters())
    with torch.no_grad():reconstructed=decoder(torch.as_tensor(restored,dtype=parameter.dtype,device=parameter.device)).detach().cpu().numpy()
    return {'units':tuple(unit_keys),'latent':latent,'pca_coordinates':coordinates,'grid':grid,
            'reconstruction':reconstructed,'explained_variance':pca.explained_variance_,
            'profile':'parameter_bound_grid; historical octile positions and scale require source qualification'}

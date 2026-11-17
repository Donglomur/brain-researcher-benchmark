"""Explicit source clock and waveform transforms; no inferred empirical facts."""
from .common import require


def biophysical_twice_speed(signal, truth_sample_times, *, phase, truth_policy,
                            original_frequency, budget):
    """Return every-second sample and a separately declared protected truth mapping.

    The Methods leaves the original truth rounding/phase unavailable. Therefore
    phase and policy are required inputs; none is silently selected. The sorter
    frequency is the Methods' 32000 in both normal and accelerated views.
    """
    import numpy as np
    require(phase in (0,1) and type(phase) is int, 'unselected-decimation-phase')
    require(truth_policy in {'rational-exact','integer-only'}, 'unselected-truth-clock-policy')
    require(original_frequency == 32000, 'biophysical-original-clock')
    require(signal.ndim == 2 and truth_sample_times.dtype.kind in 'iu', 'biophysical-input-axes')
    shifted = truth_sample_times.astype('int64')-phase
    require(np.all(shifted>=0) and np.all(truth_sample_times<len(signal)), 'truth-clock-support')
    if truth_policy == 'integer-only':
        require(np.all(shifted%2==0), 'truth-off-retained-sample-lattice')
    view = signal[phase::2]
    budget.charge('array', view.nbytes)
    # Integer numerator/denominator retain half-samples, never round them away.
    return {'signal':view.copy(),'truth_numerators':shifted,'truth_denominator':2,
            'sorter_frequency':32000,'quality_bin_seconds':[1,2000],
            'decimation_phase':phase,'truth_policy':truth_policy,
            'historical_equivalence':False}


def unwhiten_and_encode(voltage, whitening, *, budget):
    """Methods Sec40 arithmetic only, after separately generated full signal/noise."""
    import numpy as np
    require(voltage.ndim==2 and whitening.shape==(voltage.shape[1],voltage.shape[1]),
            'whitening-channel-support')
    require(np.all(np.isfinite(voltage)) and np.all(np.isfinite(whitening)), 'nonfinite-unwhitening-input')
    budget.charge('array', voltage.size*18+whitening.size*8)
    restored = np.linalg.solve(whitening, voltage.T).T
    require(np.all(np.isfinite(restored)), 'nonfinite-unwhitening-result')
    return np.clip(200*restored,-32767,32767).astype('<i2')


def depth_interpolation(drift, positions, channel_positions, *, extrapolation, budget):
    import numpy as np
    from scipy.interpolate import interp1d
    require(drift.ndim==2 and drift.shape[1]==9 and len(positions)==9,
            'nine-position-drift-required')
    require(len(channel_positions)==384 and np.all(np.diff(positions)>0), 'original-probe-position-support')
    require(extrapolation in {'refuse','linear'}, 'unselected-drift-extrapolation')
    budget.charge('array',drift.shape[0]*384*8)
    if extrapolation=='refuse':
        require(min(channel_positions)>=positions[0] and max(channel_positions)<=positions[-1],
                'drift-channel-outside-observed-support')
    f=interp1d(positions,drift,axis=1,kind='linear',bounds_error=extrapolation=='refuse',
               fill_value='extrapolate' if extrapolation=='linear' else float('nan'))
    result=f(channel_positions)
    require(np.all(np.isfinite(result)), 'nonfinite-interpolated-drift')
    return result

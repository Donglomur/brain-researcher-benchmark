"""Bank B streaming statistics and independently assembled masked spectra."""
import math
from .budget import require
from .contracts import numpy, batch_check

WINDOWS = tuple((float(k), float(k + 1)) for k in range(-5, 5)) + ((-1.5, -1.), (0., .5))
BANDS = ((1, 4), (4, 8), (8, 32), (32, 55), (65, 76),
         (76, 100), (100, 115), (125, 175), (185, 200))


def scalar_moments(values):
    """Welford population moments, literal supplied encounter order."""
    n, mean, m2 = 0, 0., 0.
    for value in values:
        n += 1
        delta = float(value) - mean
        mean += delta / n
        m2 += delta * (float(value) - mean)
    require(n > 0 and math.isfinite(mean) and math.isfinite(m2) and m2 >= 0,
            'unsupported/nonfinite streaming moments')
    return n, mean, math.sqrt(m2 / n)


def column_moments(values, budget):
    np = numpy()
    require(values.ndim == 2 and values.shape[0] > 0, 'column training support')
    n, p = values.shape
    budget.arrays(p * 17, 'column moments', live=values.nbytes + p * 64)
    budget.ops(n*p*8, 'streaming column moments')
    mean, scale, active = np.empty(p), np.empty(p), np.empty(p, dtype=bool)
    for j in range(p):
        budget.tick('column moments')
        _, mean[j], sd = scalar_moments(values[i, j] for i in range(n))
        active[j] = sd > 0
        scale[j] = sd if sd > 0 else 1.
    return mean, scale, active


def channel_moments(batch, view, budget):
    np = numpy()
    n, c = batch_check(batch, view, budget)
    require(n > 0, 'zero training support')
    budget.arrays(c * 17, 'channel statistics state', live=n*c*5000*32+c*64)
    mean, scale, active = np.zeros(c), np.ones(c), np.zeros(c, dtype=bool)
    if view == 'C':
        return mean, scale, active
    budget.ops(n*c*5000*10, 'full streaming channel statistics')
    for ch in range(c):
        count, mu, m2 = 0, 0., 0.
        for e in range(n):
            budget.tick('channel event streaming')
            for j in range(5000):
                if batch['mask'][e, ch, j]:
                    count += 1
                    z = float(batch['x'][e, ch, j])
                    delta = z - mu
                    mu += delta / count
                    m2 += delta * (z - mu)
        require(math.isfinite(mu) and math.isfinite(m2) and m2 >= 0, 'channel moment failure')
        mean[ch] = mu if count else 0.
        if count and m2 > 0:
            scale[ch], active[ch] = math.sqrt(m2 / count), True
    return mean, scale, active


def window_indices(offset, budget):
    np = numpy()
    budget.arrays(5000*16+7000*8, 'exact relative grid and window indices')
    budget.ops(5000*12*3, 'source-grid membership')
    r = -5. + float(offset) + np.arange(5000, dtype=np.float64) / 500.
    out = []
    for a, b in WINDOWS:
        idx = np.flatnonzero((r >= a) & (r < b))
        require(len(idx) == (500 if b-a == 1 else 250), '500/250 source-grid membership mismatch')
        out.append(idx)
    return out


def mask_summary(mask, budget):
    """Count-based availability, including finite zeros as observed."""
    np = numpy()
    length = len(mask)
    budget.arrays(length*24, 'Hann/mask weighted support')
    budget.ops(length*12, 'mask/Hann construction')
    hann = .5 - .5 * np.cos(2. * math.pi * np.arange(length, dtype=np.float64) / (length - 1))
    weights = hann * mask
    count = 0
    longest = run = 0
    for present in mask:
        if present:
            count += 1
            run = 0
        else:
            run += 1
            longest = max(longest, run)
    energy = math.fsum(float(w)*float(w) for w in weights)
    return (count/length, longest/length, float(count > 0), float(energy > 0)), weights, energy


def band_log_power(values, weights, energy, budget):
    np = numpy()
    length = len(values)
    budget.arrays(length*96, 'window FFT primitive/workspace source reservation')
    budget.ops(length*(64+32*int(math.ceil(math.log2(length)))), 'complete window FFT work bound')
    if energy == 0:
        return [0.] * 9
    denom = math.fsum(float(w) for w in weights)
    mean = math.fsum(float(x)*float(w) for x, w in zip(values, weights))/denom
    z = weights * (values - mean)
    spectrum = np.fft.rfft(z)
    psd = (spectrum.real*spectrum.real + spectrum.imag*spectrum.imag)/(500.*energy)
    if length % 2 == 0:
        psd[1:-1] *= 2.
    else:
        psd[1:] *= 2.
    output = []
    for band, (lo, hi) in enumerate(BANDS):
        power = math.fsum(float(psd[k]) for k in range(len(psd))
                          if lo <= k*500./length and
                          (k*500./length <= hi if band == 8 else k*500./length < hi)) * 500./length
        output.append(math.log(power + 1e-12))
    require(all(math.isfinite(v) for v in output), 'nonfinite periodogram features')
    return output


def standardized_waveform(batch, e, channel_state, view, budget):
    np = numpy()
    c = len(batch['axis'])
    budget.arrays(c*5000*24, 'event standardization', live=c*5000*80 + batch['mask'].nbytes +
                  (0 if batch.get('x') is None else batch['x'].nbytes))
    out = np.zeros((c, 5000), dtype=np.float64)
    if view != 'C':
        mu, sd, active = channel_state
        for ch in range(c):
            budget.tick('event channel normalization')
            if active[ch]:
                np.subtract(batch['x'][e, ch], mu[ch], out=out[ch])
                out[ch] /= sd[ch]
                out[ch, ~batch['mask'][e, ch]] = 0.
    return out


def feature_matrix(batch, view, channel_state, budget, *, scalar_only=False):
    np = numpy()
    n, c = batch_check(batch, view, budget)
    require(type(channel_state) in (tuple, list) and len(channel_state) == 3, 'channel state')
    mu, sd, active = channel_state
    require(mu.shape == sd.shape == active.shape == (c,) and mu.dtype == sd.dtype == np.float64
            and active.dtype == np.bool_ and bool(np.isfinite(mu).all())
            and bool(np.isfinite(sd).all()) and bool((sd > 0).all()), 'channel transform state')
    p = 6 + (48 if scalar_only else 165)*c
    budget.arrays(n*p*8, 'full feature matrix', live=n*c*5000*32+n*p*64+c*5000*96+200000)
    out = np.zeros((n, p), dtype=np.float64)
    if view != 'N':
        out[:, :6] = batch['context']
    structural_offset = 6 if scalar_only else 6 + 117*c
    for e in range(n):
        budget.tick('full feature event')
        indices = window_indices(batch['offsets'][e], budget)
        signal = None if scalar_only or view == 'C' else standardized_waveform(batch, e, channel_state, view, budget)
        for ch in range(c):
            powers, support = [], []
            for w, ix in enumerate(indices):
                budget.arrays(len(ix)*10, 'window mask/value indexing')
                summary, weights, energy = mask_summary(batch['mask'][e, ch, ix], budget)
                start = structural_offset + ch*48 + w*4
                out[e, start:start+4] = summary
                if not scalar_only and view != 'C':
                    power = band_log_power(signal[ch, ix], weights, energy, budget)
                    powers.append(power)
                    support.append(energy > 0)
                    out[e, 6+ch*117+w*9:6+ch*117+(w+1)*9] = power
            if not scalar_only and view != 'C' and support[10] and support[11]:
                for band in range(9):
                    out[e, 6+ch*117+108+band] = powers[11][band] - powers[10][band]
    require(bool(np.isfinite(out).all()), 'finite complete features')
    budget.tick('feature matrix completed')
    return out


def apply_columns(values, means, scales, active, budget):
    np = numpy()
    budget.arrays(values.nbytes*3, 'train-frozen feature scaling', live=values.nbytes*5+means.nbytes*4)
    result = (values-means)/scales
    result[:, ~active] = 0.
    require(bool(np.isfinite(result).all()), 'nonfinite transformed features')
    return result


def feature_transform(batch, view, budget, environment, statistics=None, temporal=False):
    """Convenience API. Caller must admit training scope before statistics=None."""
    from .contracts import environment_check
    environment_check(environment, numerical=True)
    n, c = batch_check(batch, view, budget)
    require(type(temporal) is bool, 'temporal flag')
    if statistics is None:
        channel = channel_moments(batch, view, budget)
    else:
        require(type(statistics) is dict and statistics.get('view') == view and
                statistics.get('axis') == batch['axis'] and statistics.get('temporal') is temporal,
                'sealed feature scope')
        channel = tuple(statistics[k] for k in ('channel_mean', 'channel_scale', 'channel_active'))
    values = feature_matrix(batch, view, channel, budget, scalar_only=temporal)
    if statistics is None:
        mean, scale, active = column_moments(values, budget)
        statistics = {'view': view, 'axis': list(batch['axis']), 'temporal': temporal,
                      'channel_mean': channel[0], 'channel_scale': channel[1], 'channel_active': channel[2],
                      'feature_mean': mean, 'feature_scale': scale, 'feature_active': active}
    else:
        mean, scale, active = (statistics[k] for k in ('feature_mean', 'feature_scale', 'feature_active'))
        require(mean.shape == scale.shape == active.shape == (values.shape[1],), 'feature statistics shape')
    transformed = apply_columns(values, mean, scale, active, budget)
    output = {'features': transformed, 'statistics': statistics}
    if temporal:
        np = numpy()
        budget.arrays(n*2*c*5000*4, 'complete feature waveform output', live=n*c*5000*64+values.nbytes*5)
        waveform = np.empty((n, 2*c, 5000), dtype=np.float32)
        for row in range(n):
            waveform[row, :c] = standardized_waveform(batch, row, channel, view, budget)
            waveform[row, c:] = batch['mask'][row]
        output['waveform'] = waveform
    budget.tick('complete feature convenience output')
    return output

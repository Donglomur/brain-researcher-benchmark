"""Independent private FCSTAB source moments/Pearson/Fisher reconstruction.

No public kernel, oracle, loader, selections, inference or reference-bank
imports. Shared public fsum moment algebra; independently composed normalized
column vectors and explicit einsum pair dots. Input remains original float64.
"""
import math

import numpy as np

SD_THRESHOLD = 1e-8
FISHER_CLIP = 0.999999
SEGMENTS = ('first', 'second', 'full')


def need(ok, reason):
    if not ok: raise ValueError(reason)


def no_bool(value):
    if isinstance(value, (list, tuple)):
        for item in value: no_bool(item)
    else:
        need(not isinstance(value, (bool, np.bool_)), 'Boolean source value')


def floats(value, ndim):
    no_bool(value)
    raw = np.asarray(value)
    need(raw.ndim == ndim and raw.dtype.kind in 'iuf', 'source numeric shape/type')
    out = np.asarray(raw, dtype=np.float64, order='C')
    need(bool(np.isfinite(out).all()), 'nonfinite source')
    return out


def centered_sd(column):
    """Exact-constant bypass, fsum mean, scaled population variance."""
    x = floats(column, 1)
    need(len(x) >= 2, 'segment requires two frames')
    if bool(np.all(x == x[0])):
        return np.zeros_like(x), 0.
    try: mean = math.fsum(float(v) for v in x)/len(x)
    except OverflowError: raise ValueError('source mean overflow') from None
    with np.errstate(over='ignore', invalid='ignore'): centered = x-mean
    need(math.isfinite(mean) and bool(np.isfinite(centered).all()), 'source centered moments nonfinite')
    scale = float(np.max(np.abs(centered)))
    if scale == 0.: return centered, 0.
    scaled = centered/scale
    sd = scale*math.sqrt(math.fsum(float(v)*float(v) for v in scaled)/len(x))
    need(math.isfinite(sd), 'source SD nonfinite')
    return centered, sd


def unit_column(column):
    centered, sd = centered_sd(column)
    magnitude = float(np.max(np.abs(centered)))
    need(sd > 0 and magnitude > 0, 'inactive source column')
    scaled = centered/magnitude
    norm = math.sqrt(math.fsum(float(v)*float(v) for v in scaled))
    need(math.isfinite(norm) and norm > 0, 'source L2 unavailable')
    return scaled/norm


def reconstruct(raw):
    """Return all source primitives, not selections or subject endpoints.

    raw axes are person, original frame, original positional ROI. All persons
    contribute to the common mask. Original odd middle frame is full-only.
    """
    values = floats(raw, 3)
    people, frames, columns = values.shape
    need(people >= 1 and columns >= 1 and frames//2 >= 2, 'source cohort/half shape')
    half = frames//2
    slices = (slice(0, half), slice(frames-half, frames), slice(0, frames))
    sd = np.empty((people, 3, columns), dtype=np.float64)
    constants = np.empty((people, 3, columns), dtype=bool)
    for person in range(people):
        for segment, window in enumerate(slices):
            chunk = values[person, window]
            for roi in range(columns):
                column = chunk[:, roi]
                constants[person, segment, roi] = bool(np.all(column == column[0]))
                _, sd[person, segment, roi] = centered_sd(column)
    supported = sd > SD_THRESHOLD
    common = supported.all(axis=(0, 1))
    kept = np.flatnonzero(common)
    need(len(kept) >= 2, 'insufficient_common_rois')
    i, j = np.triu_indices(len(kept), 1)
    fisher = np.empty((people, 3, len(i)), dtype=np.float64)
    for person in range(people):
        for segment, window in enumerate(slices):
            chunk = values[person, window]
            normalized = np.ascontiguousarray(np.stack([unit_column(chunk[:, k]) for k in kept], axis=1))
            correlation = np.einsum('ti,tj->ij', normalized, normalized, optimize=False)[i, j]
            need(bool(np.isfinite(correlation).all()) and bool((np.abs(correlation) <= 1+1e-12).all()),
                 'source correlation excursion')
            fisher[person, segment] = np.arctanh(np.clip(correlation, -FISHER_CLIP, FISHER_CLIP))
    need(bool(np.isfinite(fisher).all()), 'source Fisher nonfinite')
    return dict(segment_ids=list(SEGMENTS), roi_ids=np.arange(1, columns+1, dtype=np.int64),
                population_sd=sd, exact_constant_mask=constants, segment_support=supported,
                common_roi_mask=common, edge_roi_i=kept[i]+1, edge_roi_j=kept[j]+1,
                fisher_z=fisher, n_common_rois=len(kept), n_edges=len(i), L=half,
                segment_frame_ranges=[[0, half], [frames-half, frames], [0, frames]],
                unused_middle_frame_indices=list(range(half, frames-half)))

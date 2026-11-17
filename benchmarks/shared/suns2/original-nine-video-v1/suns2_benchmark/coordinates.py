"""Explicit movie-to-original-MAT axes for the SUNS2 TUnCaT endpoint.

Retained author generate_masks_tuncat.py uses FinalMasks.transpose(2, 1, 0)
before combining masks with network_input[T, row, col]. Therefore:
    movie[t, row, col] <-> original_masks[col, row, instance]

The original scorer consumes the original MAT orientation. These helpers are
representation conversions, not image registration or evidence that acquired
movie payloads have already been spatially validated. Square 50x50 dimensions
alone cannot verify this correspondence.
"""

import numpy as np

from .constants import MASK_HEIGHT, MASK_WIDTH, MAX_INSTANCES


def _binary_array(value):
    if not isinstance(value, np.ndarray) or value.ndim != 3:
        raise ValueError("A three-dimensional NumPy mask array is required")
    if value.dtype not in (np.dtype("bool"), np.dtype("uint8")):
        raise ValueError("Masks must use bool or uint8 storage")
    if value.size > MASK_HEIGHT * MASK_WIDTH * MAX_INSTANCES:
        raise ValueError("Mask array exceeds the declared instance bound")
    if not np.all((value == 0) | (value == 1)):
        raise ValueError("Masks must be binary")


def original_masks_to_movie_instances(masks):
    """Return a view in [instance, movie-row, movie-col] order."""
    _binary_array(masks)
    if masks.shape[:2] != (MASK_WIDTH, MASK_HEIGHT):
        raise ValueError("Original MAT axes must be [col=50, row=50, instance]")
    if masks.shape[2] > MAX_INSTANCES:
        raise ValueError("Too many instances")
    return masks.transpose(2, 1, 0)


def movie_instances_to_original_masks(instances):
    """Return a view in original MAT [movie-col, movie-row, instance] order."""
    _binary_array(instances)
    if instances.shape[1:] != (MASK_HEIGHT, MASK_WIDTH):
        raise ValueError("Movie-aligned axes must be [instance, row=50, col=50]")
    if instances.shape[0] > MAX_INSTANCES:
        raise ValueError("Too many instances")
    return instances.transpose(2, 1, 0)

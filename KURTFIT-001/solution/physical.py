"""Convert a physical FWHM to Gaussian voxel standard deviations."""
import numpy as np

def gaussian_sigma(fwhm_mm, voxel_sizes_mm):
    zooms = np.asarray(voxel_sizes_mm, float)
    if zooms.shape != (3,) or not np.isfinite(zooms).all() or np.any(zooms <= 0):
        raise ValueError("three finite positive voxel sizes required")
    return tuple(float(x) for x in fwhm_mm / np.sqrt(8 * np.log(2)) / zooms) + (0.0,)

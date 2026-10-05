import numpy as np

def gaussian_sigma(fwhm,zooms):
    z=np.asarray(zooms,float)
    if z.shape!=(3,) or not np.isfinite(z).all() or np.any(z<=0):raise ValueError("invalid physical voxel sizes")
    return tuple(fwhm/np.sqrt(8*np.log(2))/z)+(0.,)

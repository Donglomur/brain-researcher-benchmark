"""Worker: register ONE subject's mean BOLD to MNI (dipy affine), warp Harvard-Oxford atlas to native,
extract ROI FC vector, save to outfile.npy. Run in a subprocess with a hard timeout so a pathological
registration cannot hang the whole job. Usage: python3 cnp_worker.py <bold.nii.gz> <out.npy>"""
import warnings; warnings.filterwarnings("ignore")
import sys, numpy as np, nibabel as nib
from nilearn.datasets import load_mni152_template, fetch_atlas_harvard_oxford
from nilearn.image import resample_to_img
from nilearn.maskers import NiftiLabelsMasker
from dipy.align.imaffine import (AffineMap, MutualInformationMetric, AffineRegistration,
                                 transform_centers_of_mass)
from dipy.align.transforms import TranslationTransform3D, RigidTransform3D, AffineTransform3D

bold, out = sys.argv[1], sys.argv[2]
mni = load_mni152_template(resolution=3)
ho = fetch_atlas_harvard_oxford("cort-maxprob-thr25-2mm")
atlas = np.asarray(resample_to_img(ho.maps, mni, interpolation="nearest").dataobj)
static = np.asarray(mni.dataobj).astype(float); static_aff = mni.affine

img = nib.load(bold)
mean = img.get_fdata().mean(-1).astype(float)
c = transform_centers_of_mass(static, static_aff, mean, img.affine)
areg = AffineRegistration(metric=MutualInformationMetric(32, None),
                          level_iters=[40, 20, 5], sigmas=[3, 1, 0], factors=[4, 2, 1], verbosity=0)
a = c.affine
for T in (TranslationTransform3D(), RigidTransform3D(), AffineTransform3D()):
    a = areg.optimize(static, mean, T, None, static_aff, img.affine, starting_affine=a).affine
amap = AffineMap(a, static.shape, static_aff, mean.shape, img.affine)
an = np.round(amap.transform_inverse(atlas.astype(float), interpolation="nearest",
                                     sampling_grid_shape=img.shape[:3])).astype(np.int16)
from nilearn.image import high_variance_confounds
conf = high_variance_confounds(img, n_confounds=5)   # CompCor-like denoising (motion/physio proxy)
m = NiftiLabelsMasker(nib.Nifti1Image(an, img.affine), standardize=True, detrend=True,
                      high_pass=0.01, low_pass=0.1, t_r=2.0)
ts = m.fit_transform(img, confounds=conf)
fc = np.corrcoef(ts.T); iu = np.triu_indices(fc.shape[0], 1)
np.save(out, np.nan_to_num(fc[iu]))
print("OK", bold.split("/")[-1], "ts", ts.shape)

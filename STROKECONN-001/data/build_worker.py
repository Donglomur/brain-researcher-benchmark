"""Worker: one stroke subject -> ROI TIMESERIES (T x 48, Harvard-Oxford cortical), CompCor-denoised,
registered to MNI. Saves the timeseries (needed to compute hemodynamic lag, not just FC).
Usage: python3 hemolag_worker.py <bold.nii.gz> <out.npy> [<tr>]"""
import warnings; warnings.filterwarnings("ignore")
import sys, numpy as np, nibabel as nib
from nilearn.datasets import load_mni152_template, fetch_atlas_harvard_oxford
from nilearn.image import resample_to_img, high_variance_confounds
from nilearn.maskers import NiftiLabelsMasker
from dipy.align.imaffine import (AffineMap, MutualInformationMetric, AffineRegistration,
                                 transform_centers_of_mass)
from dipy.align.transforms import TranslationTransform3D, RigidTransform3D, AffineTransform3D

bold, out = sys.argv[1], sys.argv[2]
tr = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
mni = load_mni152_template(resolution=3); static = np.asarray(mni.dataobj).astype(float)
atlas = np.asarray(resample_to_img(fetch_atlas_harvard_oxford("cort-maxprob-thr25-2mm").maps, mni,
                                   interpolation="nearest").dataobj)
img = nib.load(bold); mean = img.get_fdata().mean(-1).astype(float)
c = transform_centers_of_mass(static, mni.affine, mean, img.affine)
areg = AffineRegistration(metric=MutualInformationMetric(32, None),
                          level_iters=[40, 20, 5], sigmas=[3, 1, 0], factors=[4, 2, 1], verbosity=0)
a = c.affine
for T in (TranslationTransform3D(), RigidTransform3D(), AffineTransform3D()):
    a = areg.optimize(static, mean, T, None, mni.affine, img.affine, starting_affine=a).affine
an = np.round(AffineMap(a, static.shape, mni.affine, mean.shape, img.affine).transform_inverse(
    atlas.astype(float), interpolation="nearest", sampling_grid_shape=img.shape[:3])).astype(np.int16)
conf = high_variance_confounds(img, n_confounds=5)
# NOTE: NO band-pass low_pass here — hemodynamic-lag needs the full spectrum; only high-pass + detrend
ts = NiftiLabelsMasker(nib.Nifti1Image(an, img.affine), standardize=True, detrend=True,
                       high_pass=0.008, t_r=tr).fit_transform(img, confounds=conf)
np.save(out, ts.astype(np.float32))
print("OK", bold.split("/")[-1], "ts", ts.shape)

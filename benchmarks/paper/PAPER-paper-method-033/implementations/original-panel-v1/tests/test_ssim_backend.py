"""Mandatory declared-backend controls, separate from mocked local SSIM guards.

Requires the reviewed hosted scikit-image0.25.2 environment. Missing or different
versions fail; these tests never skip and do not qualify historical author SSIM.
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import skimage

if skimage.__version__ != '0.25.2':
    raise RuntimeError('mandatory SSIM controls require exact scikit-image0.25.2')

spec = importlib.util.spec_from_file_location('mindbridge_panel_ssim_backend',
    Path(__file__).resolve().parents[1] / 'panel.py')
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


def textured_pair():
    y, x = np.meshgrid(np.arange(425), np.arange(425), indexing='ij')
    r = np.stack((.5 + .23 * np.sin(x / 7.) * np.cos(y / 11.),
                  .5 + .21 * np.cos(x / 13. + y / 9.),
                  .5 + .19 * np.sin(x / 5. - y / 17.)))
    p = .88 * np.roll(r, (2, 3), axis=(1, 2)) + .06
    return r.astype(np.float64), p.astype(np.float64)


def gaussian_mean(array):
    # Independent explicit separable convolution, not skimage/scipy filtering.
    # sigma1.5/truncate3.5 gives radius5; symmetric extension matches reflect.
    offsets = np.arange(-5, 6, dtype=np.float64)
    kernel = np.exp(-.5 * (offsets / 1.5)**2)
    kernel /= kernel.sum()
    horizontal = np.apply_along_axis(lambda a: np.convolve(a, kernel, mode='valid'),
        1, np.pad(array, ((0, 0), (5, 5)), mode='symmetric'))
    return np.apply_along_axis(lambda a: np.convolve(a, kernel, mode='valid'),
        0, np.pad(horizontal, ((5, 5), (0, 0)), mode='symmetric'))


def independent_ssim(reference, prediction):
    coefficients = np.array([.2125, .7154, .0721])[:, None, None]
    r, p = (np.sum(image * coefficients, axis=0) for image in (reference, prediction))
    mr, mp = gaussian_mean(r), gaussian_mean(p)
    vr = gaussian_mean(r * r) - mr * mr
    vp = gaussian_mean(p * p) - mp * mp
    covariance = gaussian_mean(r * p) - mr * mp
    numerator = (2 * mr * mp + .01**2) * (2 * covariance + .03**2)
    denominator = (mr * mr + mp * mp + .01**2) * (vr + vp + .03**2)
    return float((numerator / denominator)[5:-5, 5:-5].mean())


class DeclaredSSIMBackendTests(unittest.TestCase):
    def test_identical_nonconstant_rgb_has_identity_metrics(self):
        r, _ = textured_pair()
        result = panel.image_pair_metrics(r, r, skimage_version='0.25.2')
        self.assertAlmostEqual(result['pixcorr'], 1., places=13)
        self.assertAlmostEqual(result['ssim'], 1., places=13)

    def test_textured_pair_matches_independent_gaussian_population_oracle(self):
        r, p = textured_pair()
        expected_ssim = independent_ssim(r, p)
        rc, pc = r.reshape(-1) - r.mean(), p.reshape(-1) - p.mean()
        expected_pixel = float(np.dot(rc, pc) / np.sqrt(np.dot(rc, rc) * np.dot(pc, pc)))
        result = panel.image_pair_metrics(r, p, skimage_version='0.25.2')
        self.assertGreater(expected_ssim, 0.)
        self.assertLess(expected_ssim, .99)
        self.assertAlmostEqual(result['ssim'], expected_ssim, delta=1e-12)
        self.assertAlmostEqual(result['pixcorr'], expected_pixel, delta=1e-12)

    def test_exact_runtime_declaration_mismatch_is_refused(self):
        r, p = textured_pair()
        with self.assertRaises(panel.PanelError):
            panel.image_pair_metrics(r, p, skimage_version='0.19.3')


if __name__ == '__main__':
    unittest.main()

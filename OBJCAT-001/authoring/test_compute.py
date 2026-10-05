"""Numerical mechanics on tiny fixtures; never source-derived fit evidence."""
import importlib.util
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("objcat_compute_mechanics", Path(__file__).parents[1] / "solution/compute.py")
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


def valid_labels():
    one = ["rest"] * 49 + [str(label) for label in c.CATEGORIES for _ in range(9)]
    return ["labels chunks"] + [f"{label} {run}" for run in range(12) for label in one]


def test_original_label_support(tmp_path):
    path = tmp_path / "labels.txt"; path.write_text("\n".join(valid_labels()) + "\n")
    labels, runs = c.read_labels(path)
    assert len(labels) == 1452 and np.count_nonzero(labels != "rest") == 864
    np.testing.assert_array_equal(np.unique(runs), np.arange(12))


@pytest.mark.parametrize("defect", ["header", "missing", "extra", "unknown_label", "fractional_run", "run_order", "class_count"])
def test_malformed_labels_fail_closed(tmp_path, defect):
    lines = valid_labels()
    if defect == "header": lines[0] = "chunks labels"
    elif defect == "missing": lines.pop()
    elif defect == "extra": lines.append("rest 11")
    elif defect == "unknown_label": lines[1] = "unknown 0"
    elif defect == "fractional_run": lines[1] = "rest 0.5"
    elif defect == "run_order": lines[1], lines[122] = lines[122], lines[1]
    else: lines[50] = "cat 0"
    path = tmp_path / "labels.txt"; path.write_text("\n".join(lines))
    with pytest.raises(ValueError): c.read_labels(path)


def test_exact_feature_ties_choose_larger_source_indices():
    rng = np.random.RandomState(3)
    y = np.repeat(["a", "b", "c"], 6)
    column = rng.normal(size=18) + np.repeat([0, 1, 2], 6)
    scores, indices, _ = c.select_features(np.repeat(column[:, None], 5, axis=1), y, k=2)
    np.testing.assert_array_equal(indices, [3, 4])
    assert len(np.unique(scores)) == 1


def test_constant_nan_features_rank_last_without_silent_deletion():
    rng = np.random.RandomState(4)
    y = np.repeat(["a", "b", "c"], 6)
    X = np.column_stack([np.zeros(18), rng.normal(size=(18, 4))]).astype(float)
    scores, indices, warnings = c.select_features(X, y, k=3)
    assert np.isnan(scores[0])
    assert 0 not in indices and len(scores) == 5
    assert warnings


def test_infinite_selected_f_is_precondition_not_clipped_truth():
    y = np.repeat(["a", "b", "c"], 6)
    X = np.repeat(np.repeat([0.0, 1.0, 2.0], 6)[:, None], 3, axis=1)
    with pytest.raises(ValueError, match="finite"):
        c.select_features(X, y, k=2)


def test_insufficient_finite_features_fail():
    with pytest.raises(ValueError, match="finite"):
        c.select_features(np.zeros((18, 4)), np.repeat(["a", "b", "c"], 6), k=3)


def test_c_order_extraction_and_clean_matches_pinned_masker():
    from nilearn.maskers import NiftiMasker
    rng = np.random.RandomState(9)
    data = rng.normal(size=(8, 8, 8, 24)).astype(np.float64)
    data += np.arange(24)[None, None, None, :] * 3
    mask = np.ones((8, 8, 8), dtype=np.uint8); mask[0, 0, 0] = 0
    runs = np.repeat(np.arange(3), 8)
    actual, ijk = c.extract_and_clean(data, mask, runs)
    masker = NiftiMasker(mask_img=nib.Nifti1Image(mask, np.eye(4)), dtype="float64", runs=runs,
                         detrend=True, standardize="zscore_sample", t_r=2.5, reports=False)
    expected = masker.fit_transform(nib.Nifti1Image(data, np.eye(4)))
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12)
    np.testing.assert_array_equal(ijk, np.argwhere(mask))
    assert actual.dtype == np.float64
    for run in range(3):
        np.testing.assert_allclose(actual[runs == run].mean(axis=0), 0, atol=1e-13)
        np.testing.assert_allclose(actual[runs == run].std(axis=0, ddof=1), 1, atol=1e-13)


def test_cleaning_full_runs_before_rest_removal_is_not_selected_only_cleaning():
    rng = np.random.RandomState(18)
    data = rng.normal(size=(8, 8, 8, 20)); mask = np.ones((8, 8, 8))
    runs = np.repeat([0, 1], 10); keep = np.tile(np.arange(10) >= 4, 2)
    full, _ = c.extract_and_clean(data, mask, runs)
    selected, _ = c.extract_and_clean(data[..., keep], mask, runs[keep])
    assert not np.allclose(full[keep], selected)


@pytest.mark.parametrize("defect", ["nan_bold", "inf_mask", "fractional_mask", "too_small", "wrong_shape"])
def test_no_imputation_or_silent_mask_changes(defect):
    data = np.ones((8, 8, 8, 10)); mask = np.ones((8, 8, 8))
    if defect == "nan_bold": data[0, 0, 0, 0] = np.nan
    elif defect == "inf_mask": mask[0, 0, 0] = np.inf
    elif defect == "fractional_mask": mask[0, 0, 0] = 0.5
    elif defect == "too_small": mask[:2] = 0
    else: mask = mask[:-1]
    with pytest.raises(ValueError): c.extract_and_clean(data, mask, np.zeros(10))


def test_affine_mismatch_fails_instead_of_resampling():
    bold = nib.Nifti1Image(np.zeros((2, 2, 2, 1452), dtype=np.int16), np.eye(4))
    affine = np.eye(4); affine[0, 3] = 1
    mask = nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.uint8), affine)
    with pytest.raises(ValueError, match="affines"):
        c.geometry(bold, mask)

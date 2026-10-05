"""Output/pilot mechanics on tiny fixtures, not real ROI or reference data."""
import csv
import json
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"solution"))
import compute as c
import estimators as e
from test_estimators import geometry, signal_fixture


@pytest.fixture
def prepared(geometry):
    bvals, bvecs, design = geometry
    _, signal = signal_fixture(design)
    ijk = np.array([[0, 0, index] for index in range(5)])
    return dict(roi_ijk=ijk, signal=np.vstack([signal*(1+.1*index) for index in range(5)]),
                raw_signal=np.tile(signal, (5, 1)), volume_indices=np.arange(len(bvals)), bvals=bvals, bvecs=bvecs,
                original_bvals=bvals, original_bvecs=bvecs, brain_ijk=ijk, brain_low_beta=np.zeros((5, 7)),
                seed_ijk=np.array([[1, 1, 1]]), roi_fa_low=np.ones(5)*.5, roi_md_low=np.ones(5)*.001,
                n_brain_voxels=5, n_seed_voxels=1)


def test_metadata_template_has_no_fitted_answers(geometry):
    bvals, bvecs, _ = geometry
    image = nib.Nifti1Image(np.zeros((2, 2, 2, len(bvals))), np.eye(4))
    contract = c.metadata_contract(dict(image=image, bvals=bvals, bvecs=bvecs, hashes={"input": "a"*64}))
    assert contract["preprocessing"]["smoothing"]["fwhm_voxels"] == .625
    assert contract["header_spatial_units"] == "unknown"
    assert "n_roi_voxels" not in contract and "fa_proxy_roi" not in contract
    assert contract["models"]["minimum_selected"] == 2
    assert contract["models"]["fwdti"]["optimizer_settings"]["maxfev"] == 1800
    json.dumps(contract, allow_nan=False)


def test_pilot_selects_original_evenly_spaced_rows(prepared):
    arrays = c.fit_models(prepared, ("dti_b1000", "dti_b2000"), pilot_max_voxels=3)
    assert arrays["selected_roi_indices"].tolist() == [0, 2, 4]
    assert np.array_equal(arrays["full_roi_ijk"], prepared["roi_ijk"])
    assert len(arrays["roi_ijk"]) == 3


@pytest.mark.parametrize("number", [0, 65, -1])
def test_pilot_size_invalid_before_any_fit(prepared, number):
    with pytest.raises(ValueError): c.fit_models(prepared, ("dti_b1000", "dti_b2000"), number)


def test_DTI_pair_without_freewater_is_complete(prepared, tmp_path):
    arrays = c.fit_models(prepared, ("dti_b1000", "dti_b2000"))
    result, metadata = c.write_outputs(tmp_path, arrays, {"pipeline_id": c.PIPELINE_ID}, "dti_b1000")
    assert set(result["by_model"]) == {"dti_b1000", "dti_b2000"}
    assert result["main_model"] == "dti_b1000" and result["n_roi_voxels"] == 5
    for filename, expected in (("fa_voxelwise.csv", 5), ("fa_sweep.csv", 10), ("fit_parameters.csv", 10)):
        with (tmp_path/filename).open() as stream: rows = list(csv.DictReader(stream))
        assert len(rows) == expected
    assert json.loads((tmp_path/"run_metadata.json").read_text()) == metadata
    with np.load(tmp_path/"analysis_arrays.npz", allow_pickle=False) as bank:
        assert json.loads(str(bank["metadata_json"].item())) == metadata
        assert np.array_equal(bank["roi_ijk"], prepared["roi_ijk"])


def test_common_support_selected_models_only(prepared):
    arrays = c.fit_models(prepared, ("dti_b1000", "dti_b2000"))
    arrays["models"]["dti_b1000"]["eligible"][0] = False
    result, common = c.summarize_results(arrays, "dti_b2000")
    assert common.sum() == 4 and result["by_model"]["dti_b2000"]["n_valid"] == 5
    assert result["common_valid"]["n_voxels"] == 4
    expected = np.mean(arrays["models"]["dti_b2000"]["fa"][common]-arrays["models"]["dti_b1000"]["fa"][common])
    assert result["common_valid"]["paired_fa_differences"]["dti_b2000_minus_dti_b1000"] == expected


def test_empty_common_support_null_not_dropped_rows(prepared, tmp_path):
    arrays = c.fit_models(prepared, ("dti_b1000", "dti_b2000"))
    arrays["models"]["dti_b1000"]["eligible"][:] = False
    result, _ = c.write_outputs(tmp_path, arrays, {}, "dti_b1000")
    assert result["fa_proxy_roi"] is None and result["n_roi_voxels"] == 5
    assert result["common_valid"]["paired_fa_differences"]["dti_b2000_minus_dti_b1000"] is None
    assert "NaN" not in (tmp_path/"results.json").read_text()


def test_pilot_is_not_ok_output(prepared, tmp_path):
    arrays = c.fit_models(prepared, ("dti_b1000", "dti_b2000"), 2)
    result, metadata = c.write_outputs(tmp_path, arrays, {}, "dti_b1000", "resource_pilot")
    assert result["status"] == metadata["status"] == "resource_pilot"
    assert metadata["n_source_roi_voxels"] == 5 and metadata["selected_roi_indices"] == [0, 4]


@pytest.mark.parametrize("models,main", [(('fwdti',), 'fwdti'), (('dti_b1000','dti_b1000'), 'dti_b1000'),
                                        (('dti_b1000','dti_b2000'), 'fwdti')])
def test_invalid_model_selection_before_source_access(models, main, tmp_path):
    with pytest.raises(ValueError): c.run(tmp_path/"missing", tmp_path, models, main)


def test_csv_nonfinite_undefined_not_json_literals():
    assert c.csv_value(np.nan) == c.csv_value(np.inf) == c.csv_value(None) == ""
    assert c.csv_value(np.bool_(True)) == 1


def test_public_failed_fields_blank(prepared, tmp_path):
    arrays = c.fit_models(prepared, ("dti_b1000", "dti_b2000"))
    blank = e.base_record(len(prepared["bvals"]))
    blank.update(status="insufficient_signal", observed_b0=0., normalization_scale=1e-6)
    extra = c.assemble_model([blank]*5, np.arange(len(prepared["bvals"])), np.zeros((len(prepared["bvals"]), 7)))
    arrays["models"]["fwdti"] = extra
    result, _ = c.write_outputs(tmp_path, arrays, {}, "fwdti")
    assert result["fa_proxy_roi"] is None
    with (tmp_path/"fit_parameters.csv").open() as stream:
        fw = [row for row in csv.DictReader(stream) if row["model"] == "fwdti"]
    assert len(fw) == 5 and all(row["Dxx"] == row["f"] == row["fa"] == "" for row in fw)

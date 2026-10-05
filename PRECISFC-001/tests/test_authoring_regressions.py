"""Source-free arithmetic/parser regressions; no original measurements."""
import copy
import json
import math
import numpy as np
import pytest
import qc_contract as q
import proof_of_work as p
from fixture_support import emit, fixture_reference


@pytest.mark.parametrize("values,status", [([], "insufficient_frames"), ([1], "insufficient_frames"),
    ([0,0], "constant"), ([.1]*10, "constant"), ([1,1+1e-15,1], "numerically_constant"),
    ([1,2], "ok"), ([1e300,2e300], "ok"), ([1e-300,2e-300], "ok"), ([1e-320,2e-320], "ok")])
def test_stable_vector_support(values, status):
    out = q.vector_state(values)
    assert out["status"] == status
    if len(values) < 2:
        assert out["raw_l2"] is out["centered_l2"] is out["zero_bound"] is None
    else:
        assert all(math.isfinite(out[k]) and out[k] >= 0 for k in ("raw_l2", "centered_l2", "zero_bound"))


@pytest.mark.parametrize("values", [[float("nan"),1], [float("inf"),1], [-float("inf"),1]])
def test_nonfinite_vectors(values):
    with pytest.raises(AssertionError):
        q.vector_state(values)


@pytest.mark.parametrize("scale", [1e-300, 1., 1e300])
def test_scaled_pearson(scale):
    a = q.vector_state(np.array([1.,2.,4.,3.])*scale)
    assert q.pearson(a, a) == pytest.approx(1)
    assert q.pearson(a, q.vector_state(-np.array([1.,2.,4.,3.])*scale)) == pytest.approx(-1)


def test_constant_preservation_and_level_tolerance():
    ref = np.ones((1, 12, 1)); masks = np.ones((1,12), bool); peaks = np.ones((1,1))
    q.validate_fidelity(ref + 5e-10, ref, peaks, masks)
    fake = ref.copy(); fake[:, ::2] += 5e-10
    with pytest.raises(AssertionError, match="constant"):
        q.validate_fidelity(fake, ref, peaks, masks)


def test_source_zero_requires_exact_zero():
    ref = np.zeros((1, 4, 1)); mask = np.ones((1,4), bool)
    q.validate_fidelity(ref, ref, np.zeros((1,1)), mask)
    with pytest.raises(AssertionError, match="original source"):
        q.validate_fidelity(ref+1e-300, ref, np.zeros((1,1)), mask)


def test_nonexact_both_inactive():
    ref = np.ones((1,12,1)); ref[0,0,0] += 1e-15
    q.validate_fidelity(np.ones_like(ref), ref, np.ones((1,1)), np.ones((1,12),bool))


@pytest.mark.parametrize("factor,passes", [(0.5e-6, True), (2e-6, False)])
def test_active_centered_fidelity(factor, passes):
    ref = np.array([-1.,1.,-1.,1.])[None,:,None]*1e-5
    submitted = ref*(1+factor)
    if passes:
        q.validate_fidelity(submitted, ref, np.ones((1,1)), np.ones((1,4),bool))
    else:
        with pytest.raises(AssertionError, match="centered-signal"):
            q.validate_fidelity(submitted, ref, np.ones((1,1)), np.ones((1,4),bool))


def test_censored_arm_fidelity_is_not_full_arm_only():
    ref = np.array([1.,1.,2.,3.])[None,:,None]
    submitted = ref.copy(); submitted[0,0,0] += 1e-10
    q.validate_fidelity(submitted, ref, np.ones((1,1))*3, np.ones((1,4),bool))
    with pytest.raises(AssertionError, match="constant"):
        q.validate_fidelity(submitted, ref, np.ones((1,1))*3, np.array([[1,1,0,0]],bool))


@pytest.mark.parametrize("mask", [[0,0,0],[1,0,0]])
def test_empty_and_one_frame_fidelity(mask):
    ref=np.arange(3.)[None,:,None]
    q.validate_fidelity(ref, ref, np.array([[2.]]), np.array([mask], bool))


@pytest.mark.parametrize("a,b,status", [([], [], "insufficient_common_edges"),
    ([1,1], [1,2], "constant_edge_vector"), ([1,1+1e-15],[1,2],"numerically_constant_edge_vector"),
    ([1,2],[1,2],"ok")])
def test_pair_status_precedence(a,b,status):
    assert q.pair_state(q.vector_state(a),q.vector_state(b))["status"] == status


@pytest.mark.parametrize("values,status", [([],"empty_qc_subset"),([None,.5],"incomplete_subjects"),([-.5,.5],"ok")])
def test_group_null_and_negative_values(values,status):
    assert q.group(values)["status"] == status


@pytest.mark.parametrize("value", [True, "1.5", "NaN", "Infinity", "false"])
def test_invalid_integer(value):
    with pytest.raises(AssertionError):
        p.integer(value)


@pytest.mark.parametrize("value", ["2", "2.0", "2e0"])
def test_integer_format(value):
    assert p.integer(value) == 2


def test_large_json_integer_exactness():
    p.match(2**60+1, 2**60+1)
    with pytest.raises(AssertionError):
        p.match(float(2**60+1), 2**60+1)


@pytest.mark.parametrize("value", ["1.0", "1e0", "yes", "False", "nan"])
def test_boolean_literal_contract(value):
    with pytest.raises(AssertionError):
        p.flag(value)


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}',
    '{"extra":{"note":[1e999]}}', '{"extra":[{"note":-1e999}]}'])
def test_malformed_json(text):
    with pytest.raises(AssertionError):
        p.json_text(text)


@pytest.mark.parametrize("actual,expected", [(True,1),(1,True),("1",1),(1.1,1)])
def test_json_typed_fields(actual,expected):
    with pytest.raises(AssertionError):
        p.match(actual, expected)


@pytest.mark.parametrize("constant", [False, True])
def test_complete_tiny_output(tmp_path, constant):
    ref=fixture_reference(constant=constant)
    emit(tmp_path, ref)
    own=p.validate_output_directory(tmp_path,ref)
    if constant:
        assert own["stats"]["n_common_edges"] == 0
        assert own["stats"]["group_mean_reliability"]["all_six_censored"]["value"] is None


def test_axis_and_csv_reordering(tmp_path):
    ref=fixture_reference(); arrays,_=emit(tmp_path,ref)
    # Jointly permute each independent public axis, including per-run frame keys.
    R,T,P=arrays["roi_means"].shape
    runs=np.arange(R)[::-1]; frames=np.arange(T)[::-1]; rois=np.arange(P)[::-1]
    for k in ("run_subject","run_session"):
        arrays[k]=arrays[k][runs]
    for k in ("frame_indices","tmask"):
        arrays[k]=arrays[k][runs][:,frames]
    arrays["roi_means"]=arrays["roi_means"][runs][:,frames][:,:,rois]
    arrays["roi_source_peak_abs"]=arrays["roi_source_peak_abs"][runs][:,rois]
    arrays["roi_ids"]=arrays["roi_ids"][rois]; arrays["common_roi"]=arrays["common_roi"][rois]
    arrays["voxel_ijk"]=arrays["voxel_ijk"][rois]
    arrays["arm_names"]=arrays["arm_names"][::-1]
    arrays["edge_roi_ids"]=arrays["edge_roi_ids"][::-1]; arrays["edge_valid"]=arrays["edge_valid"][::-1]
    for k in ("raw_r","fisher_z"):
        arrays[k]=arrays[k][runs][:,::-1,::-1]
    np.savez_compressed(tmp_path/"connectivity_arrays.npz",**arrays)
    for path in tmp_path.glob("*.csv"):
        lines=path.read_text().splitlines(); path.write_text("\n".join([lines[0],*lines[:0:-1]])+"\n")
    p.validate_output_directory(tmp_path,ref)


@pytest.mark.parametrize("mutation", ["means","mask","peak","common","raw","z","foreign_roi","duplicate_frame"])
def test_primitive_or_derived_mutation(tmp_path,mutation):
    ref=fixture_reference(); a,_=emit(tmp_path,ref)
    if mutation=="means": a["roi_means"][0,0,0] += .1
    elif mutation=="mask": a["tmask"][0,0] = ~a["tmask"][0,0]
    elif mutation=="peak": a["roi_source_peak_abs"][0,0] *= 2
    elif mutation=="common": a["common_roi"][0] = False
    elif mutation=="raw": a["raw_r"][0,0,0] = .99
    elif mutation=="z": a["fisher_z"][0,0,0] = .99
    elif mutation=="foreign_roi": a["roi_ids"][0] = 500
    elif mutation=="duplicate_frame": a["frame_indices"][0,0]=a["frame_indices"][0,1]
    np.savez_compressed(tmp_path/"connectivity_arrays.npz",**a)
    with pytest.raises(AssertionError): p.validate_output_directory(tmp_path,ref)


def test_optional_zero_counts_versions_and_extra_prose(tmp_path):
    ref=fixture_reference(); emit(tmp_path,ref)
    path=tmp_path/"reliability_stats.json"; stats=json.loads(path.read_text())
    for k, statuses in (("roi_status_counts",q.ROI_STATUSES),("pair_status_counts",q.PAIR_STATUSES)):
        stats[k].update({s:0 for s in statuses if s not in stats[k]})
    path.write_text(json.dumps(stats))
    path=tmp_path/"run_metadata.json"; meta=json.loads(path.read_text())
    meta["software_versions"]={"python":"alternate", "numpy":"alternate", "nibabel":"not_used"}
    meta["notes"]="Harmless additional information."
    path.write_text(json.dumps(meta)); (tmp_path/"findings.md").write_text("X")
    p.validate_output_directory(tmp_path,ref)


def test_old_bank_rejected_without_reading_real_bank(tmp_path):
    path=tmp_path/"obsolete.npz"; np.savez(path, ref_stats=np.array("{}"))
    with pytest.raises(AssertionError, match="obsolete"):
        p.load_reference(path)


@pytest.mark.parametrize("coherent", [True, False])
def test_public_near_boundary_support_change(tmp_path,coherent):
    # A source-free4096-point precision fixture permits a one-ULP crossing;
    # it is not an assertion about the818-frame original-source margins.
    n=4096; ref=fixture_reference(frames=n)
    wave=1+np.resize(np.array([-1.,1.]),n)*10*n*q.EPS
    ref["roi_means"][:,:,0]=wave
    alternate=ref["roi_means"].copy()
    alternate[:,1,0]=np.nextafter(alternate[:,1,0],-np.inf)
    assert q.vector_state(wave)["status"]=="ok"
    assert q.vector_state(alternate[0,:,0])["status"]=="numerically_constant"
    q.validate_fidelity(alternate,ref["roi_means"],ref["roi_source_peak_abs"],ref["tmask"])
    if coherent:
        emit(tmp_path,ref,alternate)
        own=p.validate_output_directory(tmp_path,ref)
        assert not own["common_roi"][0]
    else:
        arrays,_=emit(tmp_path,ref); arrays["roi_means"]=alternate
        np.savez_compressed(tmp_path/"connectivity_arrays.npz",**arrays)
        with pytest.raises(AssertionError,match="own-primitive support"):
            p.validate_output_directory(tmp_path,ref)


@pytest.mark.parametrize("mutated",[False,True])
def test_nondiscrimination_requires_independent_source_fidelity(mutated):
    from test_real_outputs import independent_fidelity_check
    ref=fixture_reference(constant=True);means=ref["roi_means"].copy()
    if mutated:means[:,::2,0]+=5e-10
    assert independent_fidelity_check(means,ref) is (not mutated)

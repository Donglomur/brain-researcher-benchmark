"""Source-free parser, numerical and categorical mechanics, not source evidence."""
from fractions import Fraction
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.ndimage import affine_transform
import build_reference as builder
import graph_contract as g
import proof_of_work as proof


@pytest.mark.parametrize("value",[1,1.,"1","001","1.0","1e0"," 1 "])
def test_integral_notation(value):
    assert g.integer(value) == 1


@pytest.mark.parametrize("value",[True,False,"true","NaN","inf","1.1","subject1",None,[],{}])
def test_invalid_integer(value):
    with pytest.raises(AssertionError):
        g.integer(value)


@pytest.mark.parametrize("value",[True,False,"NaN","inf",float("inf"),float("nan"),None,[],{},""])
def test_invalid_measurement(value):
    with pytest.raises(AssertionError):
        g.number(value)


@pytest.mark.parametrize("text",['{"x":NaN}','{"x":Infinity}','{"x":1,"x":2}'])
def test_json_no_nonfinite_or_duplicate_keys(tmp_path,text):
    path = tmp_path/"invalid.json"
    path.write_text(text)
    with pytest.raises(AssertionError):
        g.read_json(path)


@pytest.mark.parametrize("text",["participant,participant\n1,1\n","participant,value\n1\n","participant,value\n1,2,3\n"])
def test_csv_malformed_rows_fail(tmp_path,text):
    path = tmp_path/"invalid.csv"
    path.write_text(text)
    with pytest.raises(AssertionError):
        g.read_csv(path,("participant","value"))


def test_empty_complete_disconnected_graphs():
    for values,expected in [(np.zeros(6),Fraction(0)),(np.ones(6),Fraction(1))]:
        row,score,_,_ = g.graph_measurements(values,"absolute",.5,None,4)
        assert score == expected
        assert row["n_connected_pairs"]+row["n_disconnected_pairs"] == 6
    row,score,_,_ = g.graph_measurements(np.array([1,0,0,0,0,0]),"absolute",.5,None,4)
    assert score == Fraction(1,6) and row["n_components"] == 3


def test_path_hops_not_euclidean_or_weighted_lengths():
    values = np.array([1,0,0,1,0,1])
    _,score,hist,_ = g.graph_measurements(values,"absolute",.5,None,4)
    assert score == Fraction(13,18)
    np.testing.assert_array_equal(hist,[0,3,2,1])


def test_cutoff_ties_negative_and_zero_edges():
    values = np.array([.5,0,-.1,-.1,-.2,-.3])
    row,_,_,selected = g.graph_measurements(values,"proportional",.5,3,4)
    assert selected.tolist() == [True,True,True,True,False,False]
    assert row["n_edges"] == 4 and row["n_negative_edges"] == 2 and row["n_zero_edges"] == 1
    assert row["n_at_cutoff"] == 2 and row["realized_density"] == 4/6


def test_empty_absolute_minimum_is_undefined():
    row,_,_,_ = g.graph_measurements(np.zeros(6),"absolute",.5,None,4)
    assert row["minimum_selected_correlation"] is None and row["n_components"] == 4


def test_equal_five_density_weights_and_requested_k():
    assert [round(4950*d) for d in g.DENSITIES] == list(g.KS)
    values = [Fraction(1,3),Fraction(1,2),Fraction(2,3),Fraction(3,4),Fraction(4,5)]
    assert sum(values)/5 == Fraction(61,100)
    assert abs(np.trapezoid(list(map(float,values)),g.DENSITIES)/.15-.61) > .01


def test_average_ranks_exact_fraction_ties():
    np.testing.assert_array_equal(g.ranks([Fraction(1,3),Fraction(2,6),Fraction(2,3)]),[1.5,1.5,3])


def test_fraction_centering_does_not_create_false_constant():
    values = [Fraction(1,2)+Fraction(i,2**100) for i in range(4)]
    assert len(set(map(float,values))) == 1
    result = g.correlation(values,[0.,1.,2.,3.])
    assert result["status"] == "ok" and abs(result["value"]-1)<1e-14


@pytest.mark.parametrize("values",[[0.]*4,[.1]*4,[Fraction(2,3)]*4])
def test_constant_diagnostics_are_null(values):
    assert g.correlation(values,[1,2,3,4]) == dict(value=None,status="undefined_constant",n_participants=4)


def test_top_eighth_boundary_all_ties_and_arbitrary_tie_order():
    participants = list(range(10))
    scores = [Fraction(1)]*7+[Fraction(1,2)]*3
    order,top = g.ranking(participants,scores)
    assert set(top) == set(participants)
    g.validate_order(dict(ranking_by_efficiency=order[:7]+order[7:][::-1],top_by_efficiency=top[::-1]),participants,scores,8)


def test_top_set_cannot_drop_equal_boundary_people():
    with pytest.raises(AssertionError,match="boundary"):
        g.validate_order(dict(ranking_by_efficiency=list(range(10)),top_by_efficiency=list(range(8))),list(range(10)),[Fraction(0)]*10,8)


def test_rounded_equal_printed_scores_do_not_authorize_wrong_rank():
    scores = [Fraction(1,2)+Fraction(i,10**12) for i in range(10)]
    with pytest.raises(AssertionError,match="order"):
        g.validate_order(dict(ranking_by_efficiency=list(range(10)),top_by_efficiency=list(range(2,10))),list(range(10)),scores,8)


def test_missing_undefined_value_not_same_as_null():
    with pytest.raises(AssertionError,match="Missing"):
        g.required_object({"status":"undefined_constant"},{"status":"undefined_constant","value":None})


def test_observed_scaling_not_generic_geometry_absolute_tolerance():
    g.validate_observed_fields({"intensity_slope":1.95e-7,"intensity_intercept":0.,"storage_dtype":"<f4"},
        {"intensity_slope":1.9499999999999999e-7,"intensity_intercept":0.,"storage_dtype":"float32"})
    with pytest.raises(AssertionError):
        g.validate_observed_fields({"intensity_slope":2.95e-7},{"intensity_slope":1.95e-7})


@pytest.mark.parametrize("offset",[-.5,-1e-10,0,.5,1.5,2,2+1e-10])
def test_explicit_nearest_matches_declared_closed_domain(offset):
    labels = np.arange(27).reshape(3,3,3)
    target_affine = np.eye(4)
    target_affine[0,3] = offset
    actual = builder.explicit_nearest(labels,np.eye(4),(1,3,3),target_affine)
    expected = affine_transform(labels,np.eye(3),offset=[offset,0,0],output_shape=(1,3,3),order=0,mode="constant",cval=0,prefilter=False)
    np.testing.assert_array_equal(actual,expected)


def test_half_voxel_not_bankers_round():
    labels = np.arange(5)[:,None,None]
    target_affine = np.eye(4)
    target_affine[0,0] = 1.5
    assert builder.explicit_nearest(labels,np.eye(4),(3,1,1),target_affine)[:,0,0].tolist() == [0,2,3]


def test_independent_clean_rank_deficient_confounds():
    rng = np.random.RandomState(0)
    n = 31
    x = np.linspace(-1,1,n)
    confounds = np.zeros((n,17))
    confounds[:,0] = x
    confounds[:,1] = 1
    confounds[:,2] = 2*x
    raw = rng.normal(size=(n,4))+x[:,None]
    weights,info,evidence = builder.independent_clean(raw,confounds)
    assert info["confound_rank"] == 1 and len(info["constant_confound_columns"]) == 15
    np.testing.assert_allclose(evidence["cleaned"].mean(axis=0),0,atol=1e-14)
    np.testing.assert_allclose(evidence["cleaned"].std(axis=0,ddof=1),1,atol=1e-14)
    np.testing.assert_allclose(weights,np.corrcoef(evidence["cleaned"],rowvar=False)[np.triu_indices(4,1)],atol=1e-14)


@pytest.mark.parametrize("kind",["constant","nuisance_only","nonfinite"])
def test_independent_clean_fails_unresolved_parcels(kind):
    x = np.linspace(-1,1,31)
    raw = np.column_stack([x,x**2])
    confounds = np.zeros((31,17))
    confounds[:,0] = x
    if kind == "constant":
        raw[:,0] = .1
    elif kind == "nonfinite":
        raw[3,0] = np.nan
    with pytest.raises(AssertionError):
        builder.independent_clean(raw,confounds)


def test_tiny_genuine_residual_not_arbitrary_amplitude_qc():
    x = np.linspace(-1,1,31)
    confounds = np.zeros((31,17))
    confounds[:,0] = x
    raw = np.column_stack([x+1e-8*np.sin(np.arange(31)),x+1e-8*np.cos(np.arange(31))])
    assert np.isfinite(builder.independent_clean(raw,confounds)[0]).all()


def test_legacy_bank_always_rejected(tmp_path):
    path = tmp_path/"obsolete.npz"
    np.savez(path,ref_stats=np.array('{"n":40}'),ref_eff=np.arange(40))
    with pytest.raises(AssertionError,match="Legacy"):
        proof.load_reference(path)


def test_wrong_method_pin_stops_before_source_images(tmp_path):
    method = tmp_path/"method.json"
    method.write_text("{}")
    with pytest.raises(AssertionError,match="method checksum"):
        builder.load_sources(tmp_path,method)


def test_frozen_schema_matches_code():
    task = Path(__file__).resolve().parents[1]
    method = json.loads((task/"environment/method_contract.json").read_text())
    assert builder.sha256(task/"environment/method_contract.json") == proof.METHOD_SHA256
    assert builder.sha256(task/"environment/source_manifest.json") == proof.SOURCE_MANIFEST_SHA256
    assert method["outputs"]["connectomes.csv"] == list(g.FC_FIELDS)
    assert method["outputs"]["graph_metrics.csv"] == list(g.GRAPH_FIELDS)
    assert method["outputs"]["efficiency.csv"] == list(g.EFFICIENCY_FIELDS)


def test_entrypoint_offline_python3_and_builder_independence():
    directory = Path(__file__).parent
    script = (directory/"test.sh").read_text()
    assert "python3 -m pytest" in script
    assert not any(word in script for word in ("apt-get","curl","uvx","pip install"))
    builder_text = (directory/"build_reference.py").read_text()
    assert "import solution" not in builder_text and "from solution" not in builder_text
@pytest.mark.parametrize("value",[-1.,0.,1.])
def test_diagnostic_endpoint_is_valid(value):
    record = {"value":value,"status":"ok","n_participants":40}
    g.validate_diagnostics({"x":record},{"x":record})


@pytest.mark.parametrize("value",[-1.0000005,1.0000005])
def test_diagnostic_tolerance_does_not_authorize_out_of_domain(value):
    expected = {"value":float(np.sign(value)),"status":"ok","n_participants":40}
    with pytest.raises(AssertionError,match="mathematical domain"):
        g.validate_diagnostics({"x":dict(expected,value=value)},{"x":expected})


@pytest.mark.parametrize("value,lower,upper",[(-1e-10,0,1),(1+1e-10,0,1),(1+1e-8,-1-1e-12,1+1e-12)])
def test_numeric_tolerance_does_not_widen_measurement_domain(value,lower,upper):
    with pytest.raises(AssertionError,match="mathematical domain"):
        g.bounded(value,lower,upper,"test measurement")


def test_required_diagnostics_have_closed_identity_set():
    record = {"value":None,"status":"undefined_constant","n_participants":40}
    with pytest.raises(AssertionError,match="identity set"):
        g.validate_diagnostics({"x":record,"invented":record},{"x":record})


def test_strength_inherits_allowed_pearson_roundoff(tmp_path):
    import csv
    row = dict(participant=1,n_densities=5,global_efficiency=.5,
        mean_signed_correlation=1+5e-13,mean_positive_part_correlation=1+5e-13)
    path = tmp_path/"efficiency.csv"
    with path.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=g.EFFICIENCY_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    # This is a numerical-domain fixture, not an original-source reference.
    g.validate_efficiencies(path,{"efficiency_rows":[row]})


def test_strength_rejects_excursion_beyond_pearson_contract(tmp_path):
    import csv
    expected = dict(participant=1,n_densities=5,global_efficiency=.5,
        mean_signed_correlation=1+5e-13,mean_positive_part_correlation=1+5e-13)
    path = tmp_path/"efficiency.csv"
    for field in ("mean_signed_correlation","mean_positive_part_correlation"):
        row = dict(expected)
        row[field] = 1+1e-9
        with path.open("w",newline="") as stream:
            writer = csv.DictWriter(stream,fieldnames=g.EFFICIENCY_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        with pytest.raises(AssertionError,match="mathematical domain"):
            g.validate_efficiencies(path,{"efficiency_rows":[expected]})

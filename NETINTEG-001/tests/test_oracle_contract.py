"""Source-free numerical tests; no participant values or reference bank loaded."""
from fractions import Fraction
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1]/"solution"/"compute.py"
SPEC = importlib.util.spec_from_file_location("netinteg_oracle_under_test",PATH)
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


@pytest.mark.parametrize("value",[-.9,0,.2,.9])
def test_complete_graph_with_all_exact_cutoff_ties(value):
    row,score,adj,hist = oracle.graph_measurements(np.full(4950,value),"proportional",.05,248)
    assert score == 1 and row["n_edges"] == 4950 and row["n_at_cutoff"] == 4950
    assert row["n_negative_edges"] == (4950 if value<0 else 0)
    assert row["n_zero_edges"] == (4950 if value==0 else 0)
    assert hist[1] == 4950 and row["n_components"] == 1
    assert not np.diag(adj).any()


def test_empty_graph_keeps_all_nodes_and_pairs():
    row,score,_,_ = oracle.graph_measurements(np.zeros(4950),"absolute",.2,None)
    assert score == 0
    assert row["n_components"] == 100 and row["n_disconnected_pairs"] == 4950
    assert row["minimum_selected_correlation"] is None


def test_connected_pairs_not_used_as_denominator():
    weights = np.zeros(4950)
    mask = ((oracle.UPPER[0]==0)&(oracle.UPPER[1]==1))|((oracle.UPPER[0]==1)&(oracle.UPPER[1]==2))
    weights[mask] = .5
    row,score,_,hist = oracle.graph_measurements(weights,"absolute",.2,None)
    assert score == Fraction(5,9900)
    assert row["n_connected_pairs"] == 3 and row["n_components"] == 98
    assert hist[1] == 2 and hist[2] == 1


def test_signed_order_is_not_absolute_weight_order():
    weights = np.linspace(-1,.5,4950)
    row,_,adj,_ = oracle.graph_measurements(weights,"proportional",.05,248)
    assert row["n_negative_edges"] == 0
    assert np.array_equal(adj[oracle.UPPER],weights>=np.sort(weights)[-248])


def test_resampling_positive_halves_and_outside_center_domain():
    atlas = np.arange(101).reshape(101,1,1)
    labels,counts = oracle.resample_atlas(atlas,np.eye(4),(203,1,1),np.diag([.5,1,1,1]))
    expected = np.floor(np.arange(203)*.5+.5).astype(int)
    expected[np.arange(203)*.5>100] = 0
    assert np.array_equal(labels[:,0,0],expected)
    assert labels[1,0,0] == 1 and labels[201,0,0] == 0
    assert np.all(counts>0)


@pytest.mark.parametrize("case",["missing_source","fractional","missing_target"])
def test_missing_or_fractional_atlas_labels_fail(case):
    atlas = np.arange(101,dtype=float).reshape(101,1,1)
    shape = (101,1,1)
    if case == "missing_source":
        atlas[100,0,0] = 99
    elif case == "fractional":
        atlas[1,0,0] = 1.1
    else:
        shape = (100,1,1)
    with pytest.raises(ValueError):
        oracle.resample_atlas(atlas,np.eye(4),shape,np.eye(4))


def test_rank_complete_boundary_ties():
    ids = list(range(1,11))
    scores = [Fraction(20-i) if i<7 else Fraction(10) for i in range(10)]
    order,top = oracle.rank_summary(ids,scores)
    assert order==ids and top==ids


def test_average_rank_ties_and_constant_status():
    assert np.array_equal(oracle.average_ranks([3,1,1,2]),[4,1.5,1.5,3])
    record = oracle.correlation_record([Fraction(1)]*4,[1,2,3,4],True)
    assert record == dict(value=None,status="undefined_constant",n_participants=4)


def test_distinct_fractions_that_round_to_same_float_are_not_constant():
    values = [Fraction(1)+Fraction(i,10**20) for i in range(4)]
    assert len(set(map(float,values))) == 1
    record = oracle.correlation_record(values,[1.,2.,3.,4.])
    assert record["status"] == "ok"
    assert record["value"] == pytest.approx(1,abs=1e-15)


def test_pearson_regression_and_constant_confound_drop():
    rng = np.random.default_rng(501)
    n = 60
    conf = rng.normal(size=(n,17))
    conf[:,1] = .1
    conf[:,3] = conf[:,0]
    raw = rng.normal(size=(n,100))+conf[:,0,None]*3
    weights,meta,private = oracle.clean_and_correlate(raw,conf)
    assert meta["constant_confound_columns"] == ["constant"]
    assert meta["confound_rank"] == 15
    centered = raw-raw.mean(0)
    design = conf-np.mean(conf,axis=0)
    design[:,1] = 0
    reference = centered-design@np.linalg.lstsq(design,centered,rcond=1e-12)[0]
    assert np.allclose(weights,np.corrcoef(reference,rowvar=False)[oracle.UPPER],atol=1e-12)
    assert np.allclose(private["cleaned"].mean(0),0,atol=1e-12)
    assert np.allclose(private["cleaned"].std(0,ddof=1),1,atol=1e-12)


@pytest.mark.parametrize("case",["constant","nuisance_only","nonfinite"])
def test_invalid_residuals_are_not_normalized_into_noise(case):
    rng = np.random.default_rng(88)
    conf = rng.normal(size=(40,17))
    raw = rng.normal(size=(40,100))
    if case == "constant":
        raw[:,0] = .1
    elif case == "nuisance_only":
        raw[:,0] = conf[:,0]
    else:
        raw[0,0] = np.nan
    with pytest.raises(ValueError):
        oracle.clean_and_correlate(raw,conf)


def test_small_independent_residual_is_not_a_physiological_rejection():
    rng = np.random.default_rng(7)
    conf = rng.normal(size=(60,17))
    raw = rng.normal(size=(60,100))
    raw[:,0] = conf[:,0]+1e-8*raw[:,0]
    weights,_,private = oracle.clean_and_correlate(raw,conf)
    assert np.all(np.isfinite(weights))
    assert private["residual_norm"][0]>private["residual_zero_bound"][0]


def test_empty_confound_span_is_demeaned_empirical_pearson():
    rng = np.random.default_rng(21)
    raw = rng.normal(size=(30,100))
    weights,meta,_ = oracle.clean_and_correlate(raw,np.ones((30,17)))
    assert meta["confound_rank"] == 0 and meta["confound_rank_threshold"] == 0
    assert np.allclose(weights,np.corrcoef(raw,rowvar=False)[oracle.UPPER],atol=1e-14)


def test_build_stager_fallback_and_missing(tmp_path):
    build = tmp_path/"stage_data.py"
    build.write_text("# fixture\n")
    assert oracle.resolve_stager_path(tmp_path/"solution"/"compute.py",build) == build
    with pytest.raises(ValueError):
        oracle.resolve_stager_path(tmp_path/"solution"/"compute.py",tmp_path/"absent.py")


def test_csv_and_json_undefined_are_portable(tmp_path):
    oracle.write_csv(tmp_path/"fixture.csv",["value"],[{"value":None}])
    oracle.write_json(tmp_path/"fixture.json",{"value":None})
    assert (tmp_path/"fixture.csv").read_text()== 'value\n""\n'
    assert json.loads((tmp_path/"fixture.json").read_text())["value"] is None
    with pytest.raises(ValueError):
        oracle.write_json(tmp_path/"invalid.json",{"value":float("nan")})


@pytest.mark.parametrize("target",["output","private"])
def test_existing_evidence_is_preserved_before_source_reads(tmp_path,target):
    output,private = tmp_path/"output",tmp_path/"private"
    path = output if target=="output" else private
    path.mkdir()
    sentinel = path/"run_metadata.json"
    sentinel.write_text("preserve me")
    with pytest.raises(oracle.PreserveExistingEvidence):
        oracle.run(tmp_path/"absent_source",tmp_path/"absent_method",output,private)
    assert sentinel.read_text()=="preserve me"


@pytest.mark.parametrize("relationship",["same","nested","symlink"])
def test_output_directory_relationships_are_safe(tmp_path,relationship):
    output = tmp_path/"output"
    private = output if relationship=="same" else output/"private"
    if relationship=="symlink":
        target = tmp_path/"existing"
        target.mkdir()
        output.symlink_to(target,target_is_directory=True)
        private = tmp_path/"private"
    with pytest.raises(oracle.PreserveExistingEvidence):
        oracle.prepare_output_directories(output,private)

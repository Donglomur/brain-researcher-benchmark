"""Bounded denominator/QC mechanics, with no historical or fabricated bank."""
import copy
import json

import numpy as np
import pytest

from test_contract import mechanical_reference, emit
import proof_of_work as q


def test_primary_all_units_and_qc_subset_are_distinct():
    reference=mechanical_reference()
    result=q.summarize(reference["primary"],reference["qc"])
    assert result["n_visp_units_total"]==result["n_visp_units_analyzed"]==3
    assert result["n_orientation_selective"]==1
    assert result["orientation_selective_fraction"]==pytest.approx(1/3)
    assert result["n_qc_responsive_units"]==1
    assert result["qc_responsive_selective_fraction"]==1


def test_undefined_osi_never_drops_primary_denominator():
    reference=mechanical_reference()
    primary=copy.deepcopy(reference["primary"])
    primary["osi"][:]=0;primary["osi_defined"][:]=False;primary["selective"][:]=False
    result=q.summarize(primary)
    assert result["n_visp_units_analyzed"]==3
    assert result["n_osi_undefined"]==3
    assert result["orientation_selective_fraction"]==0


def test_zero_qc_responsive_support_is_null_not_zero():
    reference=mechanical_reference()
    qc=copy.deepcopy(reference["qc"]);qc["in_qc_responsive"][:]=False
    result=q.summarize(reference["primary"],qc)
    assert result["n_qc_responsive_units"]==result["n_qc_responsive_orientation_selective"]==0
    assert result["qc_responsive_selective_fraction"] is None


@pytest.mark.parametrize("metric,value",[("isi_violations",.5),("amplitude_cutoff",.1),("presence_ratio",.9)])
def test_exact_qc_threshold_excluded_without_altering_primary(metric,value):
    reference=mechanical_reference()
    metrics={key:reference[key].copy() for key in q.QC_METRICS}
    metrics[metric][0]=value
    qc=q.derive_qc(metrics,reference["baseline_counts"],reference["primary"])
    assert not qc["qc_pass"][0]
    result=q.summarize(reference["primary"],qc)
    assert result["n_visp_units_analyzed"]==3 and result["n_orientation_selective"]==1


@pytest.mark.parametrize("peak,baseline,expected",[(2.,0.,False),(3.,2.,False),(3.00001,2.,True)])
def test_strict_responsiveness_boundaries(peak,baseline,expected):
    primary={"peak_rate_hz":np.array([peak])}
    metrics={"isi_violations":np.array([.1]),"amplitude_cutoff":np.array([.01]),"presence_ratio":np.array([.95])}
    # A baseline of 2Hz is one event per half-second window.
    qc=q.derive_qc(metrics,np.full((1,2),int(baseline*.5),dtype=int),primary)
    assert bool(qc["responsive"][0])==expected


@pytest.mark.parametrize("key",["n_visp_units_total","n_visp_units_analyzed","n_orientation_selective","orientation_selective_fraction"])
def test_wrong_primary_count_or_denominator_rejected(tmp_path,key):
    reference=mechanical_reference();emit(tmp_path,reference)
    result=q.load_json(tmp_path/"results.json")
    result[key]=result["qc_responsive_selective_fraction"] if key=="orientation_selective_fraction" else result[key]+1
    (tmp_path/"results.json").write_text(json.dumps(result))
    with pytest.raises(AssertionError):q.validate_output_directory(tmp_path,reference)


def test_qc_source_missingness_is_not_filled():
    reference=mechanical_reference()
    assert np.isnan(reference["isi_violations"][1])
    assert not reference["qc"]["qc_metrics_complete"][1]
    assert not reference["qc"]["qc_pass"][1]
    assert q.summarize(reference["primary"])["n_visp_units_analyzed"]==3

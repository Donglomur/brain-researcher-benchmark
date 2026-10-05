"""Tiny parser/arithmetic fixtures; no original source, fits or reference bank."""
import copy
import csv
import json
from pathlib import Path
import sys

import numpy as np
import pytest

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/"tests"))
import proof_of_work as q


def mechanical_reference():
    direction=np.repeat(q.DIRECTIONS,4)
    frequency=np.tile([1.,1.,2.,2.],8)
    durations=np.tile([1.,2.,1.,2.],8)
    starts=100.+np.arange(len(direction))*4
    responses=np.array([[12,5,2,4,8,6,2,3],[0]*8,[6,2,2,1,6,2,2,1]])
    rates=np.column_stack([responses[:,int(d//45)] if tf==1 else np.ones(3) for d,tf in zip(direction,frequency)])
    rates[1,:]=0
    counts=(rates*durations[None,:]).astype(np.int64)
    baseline=np.zeros_like(counts); baseline[2,:]=4
    reference={"unit_ids":np.array([101,102,103]),"peak_channel_ids":np.array([5001,5002,5003]),
               "presentation_ids":np.arange(2000,2000+len(direction)),"start_time":starts,"stop_time":starts+durations,
               "direction":direction,"temporal_frequency":frequency,"spike_counts":counts,"baseline_counts":baseline,
               "isi_violations":np.array([.1,np.nan,.5]),"amplitude_cutoff":np.array([.01,.02,.02]),
               "presence_ratio":np.array([.95,.96,.96]),
               "stats":{"pipeline_id":q.PIPELINE_ID,"source_sha256":{"mechanics-only":"0"*64},
                        "metadata_contract":{"pipeline_id":q.PIPELINE_ID,"source_sha256":{"mechanics-only":"0"*64},
                                             "windows":{"endpoint":"half_open","baseline_seconds":.5}},
                        "n_units_total":5,"n_original_presentations":len(direction)+5,"n_blank_presentations":5}}
    primary=q.derive(counts,starts,starts+durations,direction,frequency)
    qc=q.derive_qc({key:reference[key] for key in q.QC_METRICS},baseline,primary)
    reference["stats"]["results"]=q.summarize(primary,qc)
    return q.validate_reference(reference)


def write_csv(path,fields,rows):
    with Path(path).open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def public_value(value):
    if isinstance(value,(bool,np.bool_)): return bool(value)
    if isinstance(value,(int,np.integer)): return int(value)
    if isinstance(value,(float,np.floating)): return float(value) if np.isfinite(value) else ""
    return str(value)


def emit(output,reference,include_qc=True,counts=None):
    """Format mechanical fixtures or genuine retained values, never a bank."""
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    counts=reference["spike_counts"] if counts is None else counts
    primary=q.derive(counts,reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    qc=q.derive_qc({key:reference[key] for key in q.QC_METRICS},reference["baseline_counts"],primary) if include_qc else None
    write_csv(output/"presentations.csv",q.PRESENTATION_FIELDS,[
        dict(presentation_id=int(identifier),start_time=float(reference["start_time"][j]),stop_time=float(reference["stop_time"][j]),
             duration_seconds=float(reference["stop_time"][j]-reference["start_time"][j]),direction=float(reference["direction"][j]),
             temporal_frequency=float(reference["temporal_frequency"][j]))
        for j,identifier in enumerate(reference["presentation_ids"])])
    write_csv(output/"trial_responses.csv",q.TRIAL_FIELDS,[
        dict(unit_id=int(unit),presentation_id=int(presentation),spike_count=int(counts[i,j]),rate_hz=float(primary["rates"][i,j]))
        for i,unit in enumerate(reference["unit_ids"]) for j,presentation in enumerate(reference["presentation_ids"])])
    write_csv(output/"condition_means.csv",q.CONDITION_FIELDS,[
        dict(unit_id=int(unit),direction=float(direction),temporal_frequency=float(frequency),
             n_presentations=int(primary["condition_repeats"][di,ti]),mean_rate_hz=float(primary["condition_means"][i,di,ti]))
        for i,unit in enumerate(reference["unit_ids"]) for di,direction in enumerate(q.DIRECTIONS)
        for ti,frequency in enumerate(primary["temporal_frequencies"])])
    write_csv(output/"units.csv",q.UNIT_FIELDS,[
        dict(unit_id=int(unit),peak_channel_id=int(reference["peak_channel_ids"][i]),
             **{key:public_value(primary[key][i]) for key in q.UNIT_FIELDS[2:]})
        for i,unit in enumerate(reference["unit_ids"])])
    if include_qc:
        write_csv(output/"baseline_counts.csv",("unit_id","presentation_id","spike_count"),[
            dict(unit_id=int(unit),presentation_id=int(presentation),spike_count=int(reference["baseline_counts"][i,j]))
            for i,unit in enumerate(reference["unit_ids"]) for j,presentation in enumerate(reference["presentation_ids"])])
        write_csv(output/"qc_sensitivity.csv",q.QC_FIELDS,[
            dict(unit_id=int(unit),**{key:public_value(qc[key][i]) for key in q.QC_FIELDS[1:]})
            for i,unit in enumerate(reference["unit_ids"])])
    else:
        for filename in q.QC_FILES:
            if (output/filename).exists(): (output/filename).unlink()
    result=q.summarize(primary,qc)
    metadata=copy.deepcopy(reference["stats"]["metadata_contract"])
    metadata.update(status="ok",n_units_total=reference["stats"]["n_units_total"],n_visp_units_total=len(reference["unit_ids"]),
                    n_original_presentations=reference["stats"]["n_original_presentations"],n_blank_presentations=reference["stats"]["n_blank_presentations"],
                    n_gratings_presentations=len(reference["presentation_ids"]),directions=q.DIRECTIONS.tolist(),
                    temporal_frequencies=primary["temporal_frequencies"].tolist(),include_qc=include_qc)
    (output/"results.json").write_text(json.dumps(result,allow_nan=False))
    (output/"run_metadata.json").write_text(json.dumps(metadata,allow_nan=False))
    (output/"findings.md").write_text("These are same-trial, one-session descriptive measurements, not independent population prevalence.\n")
    return primary,qc


@pytest.fixture
def reference(): return mechanical_reference()


@pytest.mark.parametrize("include_qc",[False,True])
def test_complete_required_contract_with_and_without_qc(tmp_path,reference,include_qc):
    emit(tmp_path,reference,include_qc)
    primary,qc=q.validate_output_directory(tmp_path,reference)
    assert len(primary["osi"])==3 and (qc is not None)==include_qc


@pytest.mark.parametrize("value",["unit101","-101suffix","1.5","101.00000000000000001",True,"nan","inf",""])
def test_no_digit_stripping_or_rounding_of_identifiers(value):
    with pytest.raises(AssertionError): q.integer(value,"unit_id")


@pytest.mark.parametrize("value",[101,"101","101.0","1.01e2"])
def test_equivalent_exact_integer_formats(value): assert q.integer(value,"unit_id")==101


def test_half_open_endpoints_and_repeated_spikes():
    counts=q.half_open_counts([0,1,1,2,3],[0,1,2],[1,2,3])
    assert counts.tolist()==[1,2,1]


def test_unequal_durations_equal_weight_rates_not_pooled_counts(reference):
    counts=reference["spike_counts"].copy()
    # Two presentations of one condition: 10/1 and 0/2 => mean5, not10/3.
    counts[0,0],counts[0,1]=10,0
    derived=q.derive(counts,reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    assert derived["condition_means"][0,0,0]==5
    assert derived["condition_means"][0,0,0]!=pytest.approx(10/3)


def test_preferred_frequency_uses_max_direction_not_mean(reference):
    counts=reference["spike_counts"].copy()
    duration=reference["stop_time"]-reference["start_time"]
    counts[0,:]=np.where(reference["temporal_frequency"]==1,10,0)*duration
    target=(reference["temporal_frequency"]==2)&(reference["direction"]==45)
    counts[0,target]=20*duration[target]
    derived=q.derive(counts,reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    assert derived["preferred_temporal_frequency"][0]==2


def test_lowest_tf_and_orientation_exact_ties(reference):
    counts=np.ones_like(reference["spike_counts"])*(reference["stop_time"]-reference["start_time"]).astype(int)[None,:]
    derived=q.derive(counts,reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    assert np.all(derived["preferred_temporal_frequency"]==1)
    assert np.all(derived["preferred_orientation"]==0)
    assert np.all(derived["osi"]==0) and derived["osi_defined"].all()


def test_equal_opposite_direction_folding(reference):
    derived=reference["primary"]
    assert derived["r_pref_hz"][0]==10
    assert derived["r_orth_hz"][0]==2
    assert derived["osi"][0]==pytest.approx(2/3)


def test_opposite_conditions_have_equal_weight_despite_unequal_repetitions(reference):
    selected=np.arange(len(reference["presentation_ids"]))!=0
    derived=q.derive(reference["spike_counts"][:,selected],reference["start_time"][selected],
        reference["stop_time"][selected],reference["direction"][selected],reference["temporal_frequency"][selected])
    assert derived["condition_repeats"][0,0]==1 and derived["condition_repeats"][4,0]==2
    assert derived["r_pref_hz"][0]==10
    assert derived["r_pref_hz"][0]!=pytest.approx((12+8+8)/3)


def test_missing_source_condition_is_not_zero_imputed(reference):
    selected=~((reference["direction"]==0)&(reference["temporal_frequency"]==1))
    with pytest.raises(AssertionError,match="condition grid"):
        q.derive(reference["spike_counts"][:,selected],reference["start_time"][selected],reference["stop_time"][selected],
                 reference["direction"][selected],reference["temporal_frequency"][selected])


def test_zero_responses_retained_and_exact_threshold_strict(reference):
    primary=reference["primary"]
    assert primary["osi"][1]==0 and not primary["osi_defined"][1] and not primary["selective"][1]
    assert primary["osi"][2]==.5 and not primary["selective"][2]
    assert q.summarize(primary)["n_visp_units_analyzed"]==3


def test_rounded_osi_does_not_flip_categorical_threshold(tmp_path,reference):
    # Strictly >.5 source value can be reported as .5 within numeric tolerance.
    reference=copy.deepcopy(reference)
    source=reference["spike_counts"]
    source[2,:]*=100000
    source[2,(reference["direction"]==0)&(reference["temporal_frequency"]==1)]+=1
    primary=q.derive(source,reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    qc=q.derive_qc({key:reference[key] for key in q.QC_METRICS},reference["baseline_counts"],primary)
    reference["stats"]["results"]=q.summarize(primary,qc)
    q.validate_reference(reference)
    emit(tmp_path,reference,False)
    rows=q.read_csv(tmp_path/"units.csv",q.UNIT_FIELDS)
    assert primary["osi"][2]>.5 and primary["osi"][2]<.500001
    rows[2]["osi"]="0.5"
    write_csv(tmp_path/"units.csv",q.UNIT_FIELDS,rows)
    q.validate_output_directory(tmp_path,reference)
    rows[2]["selective"]="false"
    write_csv(tmp_path/"units.csv",q.UNIT_FIELDS,rows)
    with pytest.raises(AssertionError,match="selective"):q.validate_output_directory(tmp_path,reference)


@pytest.mark.parametrize("mutation",["drop","duplicate","fractional_id","prefix_id","foreign_id","fractional_count","negative_count","changed_count","changed_rate"])
def test_strict_count_receipt(tmp_path,reference,mutation):
    emit(tmp_path,reference)
    rows=q.read_csv(tmp_path/"trial_responses.csv",q.TRIAL_FIELDS)
    if mutation=="drop":rows.pop()
    elif mutation=="duplicate":rows.append(dict(rows[0]))
    elif mutation=="fractional_id":rows[0]["unit_id"]="101.01"
    elif mutation=="prefix_id":rows[0]["unit_id"]="unit101"
    elif mutation=="foreign_id":rows[0]["unit_id"]="999"
    elif mutation=="fractional_count":rows[0]["spike_count"]="1.5"
    elif mutation=="negative_count":rows[0]["spike_count"]="-1"
    elif mutation=="changed_count":rows[0]["spike_count"]=str(int(rows[0]["spike_count"])+1)
    elif mutation=="changed_rate":rows[0]["rate_hz"]=str(float(rows[0]["rate_hz"])+1)
    write_csv(tmp_path/"trial_responses.csv",q.TRIAL_FIELDS,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(tmp_path,reference)


@pytest.mark.parametrize("trigger",["baseline","qc","result","metadata"])
def test_partial_optional_qc_never_accepted(tmp_path,reference,trigger):
    emit(tmp_path,reference,False)
    if trigger in ("baseline","qc"):(tmp_path/("baseline_counts.csv" if trigger=="baseline" else "qc_sensitivity.csv")).write_text("header\n")
    elif trigger=="result":
        result=q.load_json(tmp_path/"results.json"); result["n_qc_responsive_units"]=1
        (tmp_path/"results.json").write_text(json.dumps(result))
    else:
        metadata=q.load_json(tmp_path/"run_metadata.json");metadata["include_qc"]=True
        (tmp_path/"run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError,match="QC sensitivity"):q.validate_output_directory(tmp_path,reference)


def test_legacy_bank_fails_closed(tmp_path):
    # A malformed historical-format fixture, never a scientific reference bank.
    # Keep this regression active after the genuine task bank is regenerated.
    path=tmp_path/"obsolete_reference.npz"
    np.savez(path,ref_stats=np.array(json.dumps({"pipeline_id":"allen-osi-legacy"})))
    with pytest.raises(AssertionError,match="obsolete"):q.load_reference(path)


def test_no_nonconstant_or_outcome_gate(tmp_path,reference):
    reference=copy.deepcopy(reference)
    reference["spike_counts"][:]=0
    primary=q.derive(reference["spike_counts"],reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    qc=q.derive_qc({key:reference[key] for key in q.QC_METRICS},reference["baseline_counts"],primary)
    reference["stats"]["results"]=q.summarize(primary,qc)
    q.validate_reference(reference);emit(tmp_path,reference)
    q.validate_output_directory(tmp_path,reference)
    result=q.load_json(tmp_path/"results.json")
    assert result["orientation_selective_fraction"]==0 and result["n_visp_units_analyzed"]==3
    assert result["qc_responsive_selective_fraction"] is None

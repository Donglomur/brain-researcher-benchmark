"""Complete original-unit/presentation receipts for a descriptive custom OSI.

Counts and immutable source timing determine categorical choices. Numeric
reporting tolerance never changes preferences, selective flags or denominators.
No quality filter is mandatory and no outcome/correlation/prose gate is used.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

import numpy as np

PIPELINE_ID = "allen-visp-two-point-osi-v2"
DIRECTIONS = np.arange(0,360,45,dtype=float)
ORIENTATIONS = np.arange(0,180,45,dtype=float)
ATOL = RTOL = 1e-6
TIME_ATOL = 1e-9
FILES = ("presentations.csv","trial_responses.csv","condition_means.csv","units.csv",
         "results.json","run_metadata.json","findings.md")
QC_FILES = ("qc_sensitivity.csv","baseline_counts.csv")
QC_RESULT_KEYS = ("n_qc_responsive_units","n_qc_responsive_orientation_selective","qc_responsive_selective_fraction")
PRESENTATION_FIELDS = ("presentation_id","start_time","stop_time","duration_seconds","direction","temporal_frequency")
TRIAL_FIELDS = ("unit_id","presentation_id","spike_count","rate_hz")
CONDITION_FIELDS = ("unit_id","direction","temporal_frequency","n_presentations","mean_rate_hz")
UNIT_FIELDS = ("unit_id","peak_channel_id","preferred_temporal_frequency","preferred_orientation",
               "r_pref_hz","r_orth_hz","peak_rate_hz","osi","osi_defined","selective")
QC_FIELDS = ("unit_id","isi_violations","amplitude_cutoff","presence_ratio","qc_metrics_complete",
             "qc_pass","baseline_rate_hz","responsive","in_qc_responsive")
QC_METRICS = ("isi_violations","amplitude_cutoff","presence_ratio")


def finite(value, name):
    assert not isinstance(value,(bool,np.bool_)), f"{name}: boolean is not a number"
    try: parsed=float(value)
    except (TypeError,ValueError,OverflowError) as exc: raise AssertionError(f"{name}: expected finite number") from exc
    assert np.isfinite(parsed), f"{name}: expected finite number"
    return parsed


def integer(value, name):
    assert not isinstance(value,(bool,np.bool_)), f"{name}: boolean is not an integer"
    try: parsed=Decimal(str(value).strip())
    except (InvalidOperation,ValueError) as exc: raise AssertionError(f"{name}: expected exact integer") from exc
    assert parsed.is_finite() and parsed==parsed.to_integral_value(), f"{name}: expected exact integer"
    assert abs(parsed)<=2**63-1, f"{name}: integer outside int64"
    return int(parsed)


def boolean(value,name):
    if isinstance(value,(bool,np.bool_)): return bool(value)
    if isinstance(value,str):
        if value.strip().lower() in ("true","1"): return True
        if value.strip().lower() in ("false","0"): return False
    raise AssertionError(f"{name}: expected boolean")


def optional_number(value,name):
    if value is None or isinstance(value,str) and not value.strip(): return np.nan
    return finite(value,name)


def load_json(path):
    try: value=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError,ValueError) as exc: raise AssertionError(f"cannot read {path}") from exc
    assert isinstance(value,dict), f"{path}: expected object"
    return value


def read_csv(path,columns):
    try:
        with Path(path).open(newline="",encoding="utf-8-sig") as stream:
            reader=csv.DictReader(stream)
            assert reader.fieldnames is not None, "missing CSV header"
            reader.fieldnames=[str(key).strip() for key in reader.fieldnames]
            assert len(reader.fieldnames)==len(set(reader.fieldnames)), "duplicate CSV column"
            assert set(columns)<=set(reader.fieldnames), f"missing required columns in {Path(path).name}"
            rows=[]
            for row in reader:
                assert None not in row, "unlabelled extra CSV cells"
                if not any(str(value or "").strip() for value in row.values()): continue
                assert all(row.get(key) is not None for key in columns), "truncated CSV row"
                rows.append({key:value.strip() if isinstance(value,str) else value for key,value in row.items()})
    except OSError as exc: raise AssertionError(f"cannot read {path}") from exc
    return rows


def numeric_match(actual,expected,name,atol=ATOL,rtol=RTOL):
    actual,expected=np.asarray(actual),np.asarray(expected)
    assert actual.shape==expected.shape, f"{name}: shape mismatch"
    assert np.array_equal(np.isfinite(actual),np.isfinite(expected)), f"{name}: availability mismatch"
    good=np.isfinite(expected)
    assert np.allclose(actual[good],expected[good],atol=atol,rtol=rtol), f"{name}: numeric mismatch"


def match_metadata(actual,expected,name="metadata"):
    if isinstance(expected,dict):
        assert isinstance(actual,dict), f"{name}: expected object"
        if name.endswith("source_sha256") or name.endswith("input_hashes"):
            assert actual==expected, f"{name}: source hash mismatch"
            return
        for key,value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_metadata(actual[key],value,name+"."+key)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected), f"{name}: list mismatch"
        for index,value in enumerate(expected): match_metadata(actual[index],value,f"{name}[{index}]")
    elif expected is None or isinstance(expected,(bool,str)):
        assert type(actual) is type(expected) and actual==expected, f"{name}: public contract mismatch"
    else:
        assert abs(finite(actual,name)-expected)<=1e-12*abs(expected), f"{name}: public contract mismatch"


def match_result(actual,expected,name="results"):
    for key,value in expected.items():
        assert key in actual, f"{name}: missing {key}"
        if value is None or isinstance(value,(bool,str)):
            assert type(actual[key]) is type(value) and actual[key]==value, f"{name}.{key}: mismatch"
        elif isinstance(value,int):
            assert integer(actual[key],key)==value, f"{name}.{key}: count mismatch"
        else:
            assert np.isclose(finite(actual[key],key),value,atol=ATOL,rtol=RTOL), f"{name}.{key}: arithmetic mismatch"


def half_open_counts(spikes,starts,stops):
    """Independent endpoint convention used by the authoring builder and fixtures."""
    spikes,starts,stops=(np.asarray(value,float) for value in (spikes,starts,stops))
    assert spikes.ndim==starts.ndim==stops.ndim==1
    assert len(starts)==len(stops) and np.isfinite(spikes).all() and np.isfinite(starts).all() and np.isfinite(stops).all()
    assert np.all(np.diff(spikes)>=0) and np.all(stops>starts)
    return np.searchsorted(spikes,stops,side="left")-np.searchsorted(spikes,starts,side="left")


def derive(counts,starts,stops,directions,frequencies):
    """Rates, equal-presentation condition means and custom two-point OSI."""
    counts=np.asarray(counts); starts,stops,directions,frequencies=(np.asarray(value,float) for value in (starts,stops,directions,frequencies))
    assert counts.ndim==2 and counts.dtype.kind in "iu" and np.all(counts>=0)
    assert counts.shape[1]==len(starts)==len(stops)==len(directions)==len(frequencies)
    assert len(starts)>0 and np.isfinite(starts).all() and np.isfinite(stops).all() and np.all(stops>starts)
    assert set(directions)==set(DIRECTIONS), "required eight source directions"
    assert np.isfinite(frequencies).all() and np.all(frequencies>0)
    tfs=np.unique(frequencies)
    rates=counts/(stops-starts)[None,:]
    condition=np.empty((len(counts),len(DIRECTIONS),len(tfs)))
    repeats=np.empty((len(DIRECTIONS),len(tfs)),int)
    for di,direction in enumerate(DIRECTIONS):
        for ti,frequency in enumerate(tfs):
            selected=(directions==direction)&(frequencies==frequency)
            assert selected.any(), "source condition grid is incomplete"
            repeats[di,ti]=int(selected.sum())
            condition[:,di,ti]=rates[:,selected].mean(axis=1)
    # Ascending source categories give the public lowest-value exact tie break.
    preferred_tf_index=np.argmax(np.max(condition,axis=1),axis=1)
    rows=np.arange(len(counts))
    tuning=(condition[:,:4,:]+condition[:,4:,:])*.5
    selected_tuning=tuning[rows,:,preferred_tf_index]
    preferred_orientation_index=np.argmax(selected_tuning,axis=1)
    r_pref=selected_tuning[rows,preferred_orientation_index]
    r_orth=selected_tuning[rows,(preferred_orientation_index+2)%4]
    denominator=r_pref+r_orth
    defined=denominator>0
    osi=np.zeros(len(counts))
    osi[defined]=(r_pref[defined]-r_orth[defined])/denominator[defined]
    return {"rates":rates,"condition_means":condition,"condition_repeats":repeats,"temporal_frequencies":tfs,
            "preferred_temporal_frequency":tfs[preferred_tf_index],
            "preferred_orientation":ORIENTATIONS[preferred_orientation_index],
            "r_pref_hz":r_pref,"r_orth_hz":r_orth,"peak_rate_hz":condition.max(axis=(1,2)),
            "osi":osi,"osi_defined":defined,"selective":osi>.5,"orientation_tuning":selected_tuning}


def derive_qc(source_metrics,baseline_counts,primary):
    baseline_counts=np.asarray(baseline_counts)
    assert baseline_counts.ndim==2 and baseline_counts.dtype.kind in "iu" and np.all(baseline_counts>=0)
    isi,amplitude,presence=(np.asarray(source_metrics[key],float) for key in QC_METRICS)
    assert isi.shape==amplitude.shape==presence.shape==(len(baseline_counts),)
    complete=np.isfinite(isi)&np.isfinite(amplitude)&np.isfinite(presence)
    qc_pass=complete&(isi<.5)&(amplitude<.1)&(presence>.9)
    baseline=(baseline_counts/.5).mean(axis=1)
    responsive=(primary["peak_rate_hz"]>2)&(primary["peak_rate_hz"]>baseline+1)
    return {**source_metrics,"qc_metrics_complete":complete,"qc_pass":qc_pass,
            "baseline_rate_hz":baseline,"responsive":responsive,"in_qc_responsive":qc_pass&responsive}


def summarize(primary,qc=None):
    n=len(primary["osi"])
    assert n>0, "no source VISp units"
    result={"status":"ok","pipeline_id":PIPELINE_ID,"orientation_selective_fraction":float(np.count_nonzero(primary["selective"])/n),
            "n_visp_units_total":n,"n_visp_units_analyzed":n,"n_orientation_selective":int(np.count_nonzero(primary["selective"])),
            "n_osi_undefined":int(np.count_nonzero(~primary["osi_defined"])),"osi_threshold":.5}
    if qc is not None:
        selected=qc["in_qc_responsive"]; denominator=int(selected.sum())
        numerator=int(np.count_nonzero(selected&primary["selective"]))
        result.update(n_qc_responsive_units=denominator,n_qc_responsive_orientation_selective=numerator,
                      qc_responsive_selective_fraction=numerator/denominator if denominator else None)
    return result


def require_files(output):
    for filename in FILES: assert (Path(output)/filename).is_file(), f"missing required output {filename}"
    assert (Path(output)/"findings.md").read_text(encoding="utf-8-sig").strip(), "empty findings.md"


def wants_qc(output,result,metadata):
    requested=any((Path(output)/filename).exists() for filename in QC_FILES) or any(key in result for key in QC_RESULT_KEYS) or metadata.get("include_qc") is True
    if requested:
        assert all((Path(output)/filename).is_file() for filename in QC_FILES), "QC sensitivity requires both supporting CSV files"
        assert all(key in result for key in QC_RESULT_KEYS), "QC sensitivity requires complete optional result fields"
        assert metadata.get("include_qc") is True, "QC sensitivity requires include_qc=true"
    else:
        assert metadata.get("include_qc") is False, "primary-only metadata requires include_qc=false"
    return requested


def read_presentations(output,reference):
    found={}
    for row in read_csv(Path(output)/"presentations.csv",PRESENTATION_FIELDS):
        identifier=integer(row["presentation_id"],"presentation_id")
        assert identifier in reference["presentation_index"], "unknown presentation ID"
        assert identifier not in found, "duplicate presentation ID"
        found[identifier]={key:finite(row[key],key) for key in PRESENTATION_FIELDS[1:]}
    assert set(found)==set(reference["presentation_index"]), "presentations must contain every source nonblank presentation"
    actual={key:np.asarray([found[int(identifier)][key] for identifier in reference["presentation_ids"]]) for key in PRESENTATION_FIELDS[1:]}
    for field,expected in (("start_time",reference["start_time"]),("stop_time",reference["stop_time"]),
                           ("duration_seconds",reference["stop_time"]-reference["start_time"])):
        numeric_match(actual[field],expected,"source "+field,TIME_ATOL,0)
    for field in ("direction","temporal_frequency"):
        assert np.array_equal(actual[field],reference[field]), f"source {field} mismatch"
    assert np.all(actual["duration_seconds"]>0), "nonpositive presentation duration"
    return actual


def read_count_table(path,reference,with_rates):
    columns=TRIAL_FIELDS if with_rates else ("unit_id","presentation_id","spike_count")
    shape=(len(reference["unit_ids"]),len(reference["presentation_ids"]))
    counts=np.full(shape,-1,dtype=np.int64); rates=np.full(shape,np.nan)
    for row in read_csv(path,columns):
        unit=integer(row["unit_id"],"unit_id"); presentation=integer(row["presentation_id"],"presentation_id")
        assert unit in reference["unit_index"], "unknown source VISp unit ID"
        assert presentation in reference["presentation_index"], "unknown source presentation ID"
        index=(reference["unit_index"][unit],reference["presentation_index"][presentation])
        assert counts[index]<0, "duplicate unit/presentation response"
        count=integer(row["spike_count"],"spike_count")
        assert count>=0, "spike count must be nonnegative"
        counts[index]=count
        if with_rates: rates[index]=finite(row["rate_hz"],"rate_hz")
    assert np.all(counts>=0), "response table must contain complete source unit by presentation product"
    expected=reference["spike_counts" if with_rates else "baseline_counts"]
    assert np.array_equal(counts,expected), "spike counts differ from original source windows"
    if with_rates:
        numeric_match(rates,counts/(reference["stop_time"]-reference["start_time"])[None,:],"source count-derived firing rate")
    return counts,rates


def read_conditions(output,reference,primary):
    tfs=primary["temporal_frequencies"]
    tf_index={float(value):index for index,value in enumerate(tfs)}
    direction_index={float(value):index for index,value in enumerate(DIRECTIONS)}
    shape=primary["condition_means"].shape
    means=np.full(shape,np.nan); repeats=np.full(shape,-1,dtype=np.int64)
    for row in read_csv(Path(output)/"condition_means.csv",CONDITION_FIELDS):
        unit=integer(row["unit_id"],"unit_id")
        direction=finite(row["direction"],"direction"); frequency=finite(row["temporal_frequency"],"temporal_frequency")
        assert unit in reference["unit_index"], "condition has unknown unit ID"
        assert direction in direction_index and frequency in tf_index, "condition has unknown source category"
        index=(reference["unit_index"][unit],direction_index[direction],tf_index[frequency])
        assert repeats[index]<0, "duplicate unit/condition row"
        repeats[index]=integer(row["n_presentations"],"n_presentations")
        assert repeats[index]>0, "condition must have positive source presentation count"
        means[index]=finite(row["mean_rate_hz"],"mean_rate_hz")
    assert np.all(repeats>0), "incomplete source unit/condition grid"
    assert np.array_equal(repeats,np.broadcast_to(primary["condition_repeats"],shape)), "condition presentation count mismatch"
    numeric_match(means,primary["condition_means"],"equal-presentation condition mean")
    return means


def read_units(output,reference,primary):
    found={}
    for row in read_csv(Path(output)/"units.csv",UNIT_FIELDS):
        unit=integer(row["unit_id"],"unit_id")
        assert unit in reference["unit_index"], "unknown original VISp unit ID"
        assert unit not in found, "duplicate unit ID"
        found[unit]={"peak_channel_id":integer(row["peak_channel_id"],"peak_channel_id"),
                     **{key:finite(row[key],key) for key in UNIT_FIELDS[2:-2]},
                     "osi_defined":boolean(row["osi_defined"],"osi_defined"),"selective":boolean(row["selective"],"selective")}
    assert set(found)==set(reference["unit_index"]), "units must include every original VISp unit"
    values={key:np.asarray([found[int(unit)][key] for unit in reference["unit_ids"]]) for key in UNIT_FIELDS[1:]}
    assert np.array_equal(values["peak_channel_id"],reference["peak_channel_ids"]), "source peak-channel mapping mismatch"
    for key in ("preferred_temporal_frequency","preferred_orientation","osi_defined","selective"):
        assert np.array_equal(values[key],primary[key]), f"{key} must follow unrounded source arithmetic"
    for key in ("r_pref_hz","r_orth_hz","peak_rate_hz","osi"):
        numeric_match(values[key],primary[key],"source-derived "+key)
    return values


def read_qc(output,reference,primary):
    counts,_=read_count_table(Path(output)/"baseline_counts.csv",reference,False)
    expected=derive_qc({key:reference[key] for key in QC_METRICS},counts,primary)
    found={}
    for row in read_csv(Path(output)/"qc_sensitivity.csv",QC_FIELDS):
        unit=integer(row["unit_id"],"unit_id")
        assert unit in reference["unit_index"], "QC has unknown unit ID"
        assert unit not in found, "duplicate QC unit"
        found[unit]={**{key:optional_number(row[key],key) for key in QC_METRICS},
                     "baseline_rate_hz":finite(row["baseline_rate_hz"],"baseline_rate_hz"),
                     **{key:boolean(row[key],key) for key in ("qc_metrics_complete","qc_pass","responsive","in_qc_responsive")}}
    assert set(found)==set(reference["unit_index"]), "QC table must retain every original VISp unit"
    values={key:np.asarray([found[int(unit)][key] for unit in reference["unit_ids"]]) for key in QC_FIELDS[1:]}
    for key in (*QC_METRICS,"baseline_rate_hz"):
        numeric_match(values[key],expected[key],"source QC "+key)
    for key in ("qc_metrics_complete","qc_pass","responsive","in_qc_responsive"):
        assert np.array_equal(values[key],expected[key]), f"QC {key} must follow unrounded source metrics/counts"
    return expected


def validate_output_directory(output,reference):
    output=Path(output); require_files(output)
    result,metadata=load_json(output/"results.json"),load_json(output/"run_metadata.json")
    include_qc=wants_qc(output,result,metadata)
    read_presentations(output,reference)
    counts,_=read_count_table(output/"trial_responses.csv",reference,True)
    primary=derive(counts,reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    read_conditions(output,reference,primary)
    read_units(output,reference,primary)
    qc=read_qc(output,reference,primary) if include_qc else None
    match_result(result,summarize(primary,qc))
    match_metadata(metadata,reference["stats"]["metadata_contract"])
    assert metadata.get("status")=="ok", "metadata status must be ok"
    expected_counts={"n_units_total":reference["stats"]["n_units_total"],"n_visp_units_total":len(reference["unit_ids"]),
                     "n_original_presentations":reference["stats"]["n_original_presentations"],
                     "n_blank_presentations":reference["stats"]["n_blank_presentations"],
                     "n_gratings_presentations":len(reference["presentation_ids"])}
    for key,value in expected_counts.items(): assert integer(metadata.get(key),key)==value, f"metadata {key} mismatch"
    assert isinstance(metadata.get("directions"),list) and np.array_equal(metadata["directions"],DIRECTIONS), "metadata directions mismatch"
    assert isinstance(metadata.get("temporal_frequencies"),list) and np.array_equal(metadata["temporal_frequencies"],primary["temporal_frequencies"]), "metadata temporal frequencies mismatch"
    return primary,qc


def validate_reference(reference):
    stats=reference["stats"]
    assert stats.get("pipeline_id")==PIPELINE_ID, "obsolete reference; genuine immutable-source bank required"
    assert stats["metadata_contract"]["pipeline_id"]==PIPELINE_ID
    assert stats["source_sha256"]==stats["metadata_contract"]["source_sha256"], "bank source hash mismatch"
    for key in ("unit_ids","peak_channel_ids","presentation_ids"):
        assert reference[key].ndim==1 and reference[key].dtype.kind in "iu" and np.all(reference[key]>=0), f"bank {key} malformed"
    assert len(reference["unit_ids"])>0 and len(set(reference["unit_ids"]))==len(reference["unit_ids"])
    assert len(reference["presentation_ids"])>0 and len(set(reference["presentation_ids"]))==len(reference["presentation_ids"])
    assert len(reference["peak_channel_ids"])==len(reference["unit_ids"])
    reference["unit_index"]={int(value):index for index,value in enumerate(reference["unit_ids"])}
    reference["presentation_index"]={int(value):index for index,value in enumerate(reference["presentation_ids"])}
    n,p=len(reference["unit_ids"]),len(reference["presentation_ids"])
    assert integer(stats["n_units_total"],"bank total units")>=n
    assert integer(stats["n_original_presentations"],"bank original presentations")==p+integer(stats["n_blank_presentations"],"bank blank presentations")
    assert stats["n_blank_presentations"]>=0
    for key in ("start_time","stop_time","direction","temporal_frequency"):
        assert reference[key].shape==(p,) and np.isfinite(reference[key]).all(), f"bank {key} malformed"
    for key in ("spike_counts","baseline_counts"):
        assert reference[key].shape==(n,p) and reference[key].dtype.kind in "iu" and np.all(reference[key]>=0), f"bank {key} malformed"
    for key in QC_METRICS:
        assert reference[key].shape==(n,) and not np.isinf(reference[key]).any(), f"bank QC {key} malformed"
    primary=derive(reference["spike_counts"],reference["start_time"],reference["stop_time"],reference["direction"],reference["temporal_frequency"])
    qc=derive_qc({key:reference[key] for key in QC_METRICS},reference["baseline_counts"],primary)
    match_result(stats["results"],summarize(primary,qc))
    reference["primary"],reference["qc"]=primary,qc
    return reference


def load_reference(path=None):
    path=Path(path) if path is not None else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path,allow_pickle=False) as bank:
            stats=json.loads(str(bank["ref_stats"].item()))
            assert stats.get("pipeline_id")==PIPELINE_ID, "obsolete reference; genuine immutable-source bank required"
            keys=("unit_ids","peak_channel_ids","presentation_ids","start_time","stop_time","direction",
                  "temporal_frequency","spike_counts","baseline_counts",*QC_METRICS)
            reference={key:bank["ref_"+key] for key in keys}
            reference["stats"]=stats
    except (OSError,ValueError,KeyError) as exc:
        raise AssertionError("missing, corrupt or obsolete genuine reference bank") from exc
    return validate_reference(reference)

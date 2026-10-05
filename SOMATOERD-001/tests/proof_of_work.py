"""Source-indexed total-trial-power receipts, without outcome or prose gates."""
from __future__ import annotations
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import numpy as np

PIPELINE_ID = "somato-total-power-v2"  # Private bank format; not a participant field.
TASK_ID = "SOMATOERD-001"
POWER_ATOL, POWER_RTOL, PERCENT_ATOL, TIME_ATOL = 1e-8, 1e-6, 1e-6, 1e-9
EVENT_FIELDS = ("event_index","event_sample","event_code","retained","drop_reason","epoch_start_sample","epoch_end_sample")
MEAN_FIELDS = ("channel","frequency_hz","time_index","time_s","mean_power_T2_per_m2")
TRIAL_FIELDS = ("event_index","channel","frequency_hz","baseline_power_T2_per_m2","target_power_T2_per_m2")
CURVE_FIELDS = ("time_index","time_s","beta_power_pct")
FILES = ("source_events.csv","mean_power.csv","trial_windows.csv","beta_power_timecourse.csv","erd.json","run_metadata.json","findings.md")
METADATA_FIELDS = ("status","task_id","source_manifest_sha256","source_fif_sha256","method_contract_sha256",
                   "sfreq_hz","first_samp","n_source_samples","n_discovered_events","n_trials","n_epoch_times",
                   "source_bads","n_source_projectors","software_versions","method_contract")


def integer(value, name="integer"):
    assert not isinstance(value,(bool,np.bool_)), f"{name}: boolean is not integer"
    try: number=Decimal(str(value).strip())
    except (InvalidOperation,ValueError) as error: raise AssertionError(f"{name}: exact integer required") from error
    assert number.is_finite() and number==number.to_integral_value() and abs(number)<=2**63-1, f"{name}: exact int64 required"
    return int(number)


def finite(value, name="number"):
    assert not isinstance(value,(bool,np.bool_)), f"{name}: boolean is not numeric"
    try: number=float(value)
    except (TypeError,ValueError,OverflowError) as error: raise AssertionError(f"{name}: finite number required") from error
    assert np.isfinite(number), f"{name}: finite number required"
    return number


def load_json(path):
    try: obj=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError,ValueError) as error: raise AssertionError(f"cannot read {path}") from error
    assert isinstance(obj,dict), f"{path}: JSON object required"
    return obj


def read_csv(path, fields):
    try:
        with Path(path).open(newline="",encoding="utf-8-sig") as stream:
            reader=csv.DictReader(stream)
            assert reader.fieldnames, "CSV header required"
            reader.fieldnames=[name.strip() for name in reader.fieldnames]
            assert len(set(reader.fieldnames))==len(reader.fieldnames), "duplicate CSV header"
            assert set(fields)<=set(reader.fieldnames), f"missing required columns: {Path(path).name}"
            rows=[]
            for row in reader:
                assert None not in row, "unlabelled CSV cells"
                if not any(str(value or "").strip() for value in row.values()): continue
                assert all(row.get(key) is not None for key in fields), "truncated CSV row"
                rows.append({key:value.strip() if isinstance(value,str) else value for key,value in row.items()})
    except OSError as error: raise AssertionError(f"cannot read {path}") from error
    return rows


def close(actual, expected, name, atol=PERCENT_ATOL):
    actual,expected=np.asarray(actual,dtype=float),np.asarray(expected,dtype=float)
    assert actual.shape==expected.shape, f"{name}: shape mismatch"
    assert np.isfinite(actual).all() and np.isfinite(expected).all(), f"{name}: nonfinite values"
    assert np.all(np.abs(actual-expected)<=atol), f"{name}: numeric mismatch"


def power_close(actual, expected, baseline, name):
    actual,expected=np.asarray(actual,dtype=float),np.asarray(expected,dtype=float)
    baseline=np.asarray(baseline,dtype=float)
    assert actual.shape==expected.shape, f"{name}: shape mismatch"
    assert np.isfinite(actual).all() and np.isfinite(expected).all(), f"{name}: nonfinite power"
    assert np.isfinite(baseline).all() and np.all(baseline>0), "invalid source normalization baseline"
    # Do not use a raw absolute tolerance: these SI powers are very small.
    assert np.all(np.abs(actual-expected)<=POWER_ATOL*baseline+POWER_RTOL*np.abs(expected)), f"{name}: source-scaled power mismatch"


def match_metadata(actual, expected, name="metadata"):
    if isinstance(expected,dict):
        assert isinstance(actual,dict), f"{name}: object required"
        for key,value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_metadata(actual[key],value,name+"."+key)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected), f"{name}: list mismatch"
        for index,value in enumerate(expected): match_metadata(actual[index],value,f"{name}[{index}]")
    elif isinstance(expected,(str,bool)) or expected is None:
        assert type(actual) is type(expected) and actual==expected, f"{name}: contract mismatch"
    elif isinstance(expected,int):
        assert integer(actual,name)==expected, f"{name}: count mismatch"
    else:
        assert abs(finite(actual,name)-expected)<=abs(expected)*1e-12, f"{name}: contract mismatch"


def validate_versions(metadata):
    versions=metadata.get("software_versions")
    assert isinstance(versions,dict) and versions, "software_versions must report the implementation stack"
    assert all(isinstance(key,str) and key.strip() and isinstance(value,str) and value.strip()
               for key,value in versions.items()), "software_versions entries must be nonempty strings"


def window_masks(times, contract):
    baseline=(times>=contract["baseline_seconds"][0])&(times<=contract["baseline_seconds"][1])
    target=(times>=contract["target_seconds"][0])&(times<=contract["target_seconds"][1])
    assert baseline.any() and target.any(), "empty source time window"
    return baseline,target


def derive(mean_power, times, contract):
    mean_power=np.asarray(mean_power,dtype=float)
    assert mean_power.ndim==3 and mean_power.shape[-1]==len(times)
    assert np.isfinite(mean_power).all() and (mean_power>=0).all(), "raw mean power must be finite and nonnegative"
    baseline_mask,target_mask=window_masks(times,contract)
    baseline=mean_power[...,baseline_mask].mean(axis=-1)
    assert np.all(np.isfinite(baseline)&(baseline>0)), "aggregate baseline power must be strictly positive"
    percent=100*(mean_power/baseline[...,None]-1)
    curve=percent.mean(axis=(0,1))
    return dict(baseline_power=baseline,target_power=mean_power[...,target_mask].mean(axis=-1),
                percent_power=percent,beta_power_pct=curve,beta_erd_percent=float(curve[target_mask].mean()))


def result_from(reference, derived=None):
    derived=reference["derived"] if derived is None else derived
    contract=reference["stats"]["metadata"]["method_contract"]
    return dict(beta_erd_percent=derived["beta_erd_percent"], band_hz=[15,30],
                channels=[str(value) for value in reference["channels"]], window_ms=[100,350],baseline_ms=[-1000,-250],
                n_trials=len(reference["retained_event_indices"]))


def match_result(actual, expected):
    for key,value in expected.items():
        assert key in actual, f"erd.json missing {key}"
        if key=="beta_erd_percent": close(finite(actual[key],key),value,key)
        elif key=="n_trials": assert integer(actual[key],key)==value, "wrong retained trial count"
        else: match_metadata(actual[key],value,"erd."+key)


def read_events(output, reference):
    found=set()
    expected={integer(row["event_index"]):row for row in reference["source_events"]}
    for row in read_csv(Path(output)/"source_events.csv",EVENT_FIELDS):
        key=integer(row["event_index"],"event_index")
        assert key in expected and key not in found, "unknown or duplicate source event"
        found.add(key)
        for field in EVENT_FIELDS:
            if field=="drop_reason": assert row[field]==expected[key][field], "source event drop reason mismatch"
            else: assert integer(row[field],field)==expected[key][field], f"source event {field} mismatch"
    assert found==set(expected), "every discovered source event required"


def read_mean_power(output, reference):
    channels={str(channel):index for index,channel in enumerate(reference["channels"])}
    frequencies={float(frequency):index for index,frequency in enumerate(reference["frequencies"])}
    found=set(); power=np.empty_like(reference["mean_power"],dtype=float)
    for row in read_csv(Path(output)/"mean_power.csv",MEAN_FIELDS):
        channel=row["channel"]; frequency=finite(row["frequency_hz"],"frequency_hz")
        time=integer(row["time_index"],"time_index")
        assert channel in channels and frequency in frequencies and 0<=time<len(reference["times"]), "unknown channel/frequency/time key"
        key=(channels[channel],frequencies[frequency],time)
        assert key not in found, "duplicate mean-power key"
        found.add(key)
        close(finite(row["time_s"],"time_s"),reference["times"][time],"source time",TIME_ATOL)
        power[key]=finite(row["mean_power_T2_per_m2"],"mean power")
    assert len(found)==power.size, "complete channel-frequency-time grid required"
    power_close(power,reference["mean_power"],reference["derived"]["baseline_power"][...,None],"mean power")
    return power


def read_trial_windows(output, reference):
    event_lookup={int(event):index for index,event in enumerate(reference["retained_event_indices"])}
    channel_lookup={str(channel):index for index,channel in enumerate(reference["channels"])}
    freq_lookup={float(frequency):index for index,frequency in enumerate(reference["frequencies"])}
    baseline=np.empty_like(reference["trial_baseline_power"],dtype=float); target=np.empty_like(baseline)
    found=set()
    for row in read_csv(Path(output)/"trial_windows.csv",TRIAL_FIELDS):
        event=integer(row["event_index"],"event_index")
        channel=row["channel"]; frequency=finite(row["frequency_hz"],"frequency_hz")
        assert event in event_lookup and channel in channel_lookup and frequency in freq_lookup, "unknown trial-window key"
        key=(event_lookup[event],channel_lookup[channel],freq_lookup[frequency])
        assert key not in found, "duplicate trial-window key"
        found.add(key)
        baseline[key]=finite(row["baseline_power_T2_per_m2"],"trial baseline")
        target[key]=finite(row["target_power_T2_per_m2"],"trial target")
    assert len(found)==baseline.size, "complete retained-event/channel/frequency receipt required"
    assert (baseline>=0).all() and (target>=0).all(), "trial powers must be nonnegative"
    scale=reference["derived"]["baseline_power"][None,...]
    power_close(baseline,reference["trial_baseline_power"],scale,"trial baseline")
    power_close(target,reference["trial_target_power"],scale,"trial target")
    return baseline,target


def validate_power_receipts(output, reference):
    mean=read_mean_power(output,reference)
    trial_baseline,trial_target=read_trial_windows(output,reference)
    derived=derive(mean,reference["times"],reference["stats"]["metadata"]["method_contract"])
    source_baseline=reference["derived"]["baseline_power"]
    power_close(trial_baseline.mean(axis=0),derived["baseline_power"],source_baseline,"pooled baseline arithmetic")
    power_close(trial_target.mean(axis=0),derived["target_power"],source_baseline,"pooled target arithmetic")
    return derived


def read_curve(output, reference, derived):
    curve=np.empty(len(reference["times"]));found=set()
    for row in read_csv(Path(output)/"beta_power_timecourse.csv",CURVE_FIELDS):
        time=integer(row["time_index"],"time_index")
        assert 0<=time<len(curve) and time not in found, "unknown or duplicate curve time"
        found.add(time)
        close(finite(row["time_s"],"time_s"),reference["times"][time],"curve source time",TIME_ATOL)
        curve[time]=finite(row["beta_power_pct"],"beta_power_pct")
    assert len(found)==len(curve), "complete epoch curve required"
    close(curve,derived["beta_power_pct"],"curve recomputation")
    close(curve,reference["derived"]["beta_power_pct"],"source curve")
    return curve


def validate_output_directory(output, reference):
    output=Path(output)
    for filename in FILES: assert (output/filename).is_file(), f"missing {filename}"
    read_events(output,reference)
    derived=validate_power_receipts(output,reference)
    read_curve(output,reference,derived)
    result=load_json(output/"erd.json")
    match_result(result,result_from(reference,derived))
    close(finite(result["beta_erd_percent"]),reference["derived"]["beta_erd_percent"],"source endpoint")
    metadata=load_json(output/"run_metadata.json")
    match_metadata(metadata,{key:reference["stats"]["metadata"][key] for key in METADATA_FIELDS if key!="software_versions"})
    validate_versions(metadata)
    assert metadata["status"]=="ok" and metadata["task_id"]==TASK_ID
    assert (output/"findings.md").read_text(encoding="utf-8-sig").strip(), "findings.md is empty"
    return derived


def validate_reference(reference):
    stats=reference["stats"]; metadata=stats["metadata"];contract=metadata["method_contract"]
    assert stats.get("pipeline_id")==PIPELINE_ID, "obsolete reference; genuine original-source bank required"
    assert metadata["status"]=="ok" and metadata["task_id"]==TASK_ID
    for field in METADATA_FIELDS: assert field in metadata, f"bank metadata missing {field}"
    validate_versions(metadata)
    assert np.array_equal(reference["channels"],contract["channels"])
    assert np.array_equal(reference["frequencies"],contract["frequencies_hz"])
    assert len(set(reference["channels"]))==len(reference["channels"])
    times,offsets=reference["times"],reference["sample_offsets"]
    sfreq=finite(metadata["sfreq_hz"],"sfreq")
    assert sfreq>0 and offsets.ndim==1 and offsets.dtype.kind in "iu"
    expected=np.arange(round(contract["epoch_seconds"][0]*sfreq),round(contract["epoch_seconds"][1]*sfreq)+1)
    np.testing.assert_array_equal(offsets,expected)
    close(times,offsets/sfreq,"bank source clock",1e-14)
    assert len(times)==integer(metadata["n_epoch_times"])
    events=reference["source_events"]
    assert len(events)==integer(metadata["n_discovered_events"])
    assert [row["event_index"] for row in events]==list(range(len(events)))
    assert all(events[index]["event_sample"]<events[index+1]["event_sample"] for index in range(len(events)-1))
    retained=[]
    for row in events:
        for field in EVENT_FIELDS:
            if field!="drop_reason": assert isinstance(row[field],int) and not isinstance(row[field],bool)
        assert row["retained"] in (0,1)
        assert row["epoch_start_sample"]==row["event_sample"]+offsets[0]
        assert row["epoch_end_sample"]==row["event_sample"]+offsets[-1]
        if row["retained"]:
            assert row["event_code"]==contract["event_id"] and row["drop_reason"]==""
            assert row["epoch_start_sample"]>=metadata["first_samp"]
            assert row["epoch_end_sample"]<metadata["first_samp"]+metadata["n_source_samples"]
            retained.append(row["event_index"])
        else:
            assert isinstance(row["drop_reason"],str) and row["drop_reason"]
            if row["event_code"]!=contract["event_id"]: assert row["drop_reason"]=="non_target_event"
    np.testing.assert_array_equal(reference["retained_event_indices"],retained)
    assert len(retained)==integer(metadata["n_trials"]) and retained
    shape=(len(reference["channels"]),len(reference["frequencies"]),len(times))
    assert reference["mean_power"].shape==shape
    derived=derive(reference["mean_power"],times,contract)
    for key in ("trial_baseline_power","trial_target_power"):
        assert reference[key].shape==(len(retained),*shape[:2])
        assert np.isfinite(reference[key]).all() and (reference[key]>=0).all()
    power_close(reference["trial_baseline_power"].mean(axis=0),derived["baseline_power"],derived["baseline_power"],"bank baseline arithmetic")
    power_close(reference["trial_target_power"].mean(axis=0),derived["target_power"],derived["baseline_power"],"bank target arithmetic")
    reference["derived"]=derived
    match_result(stats["results"],result_from(reference))
    return reference


def load_reference(path=None):
    path=Path(path) if path else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path,allow_pickle=False) as archive:
            stats=json.loads(str(archive["ref_stats"].item()))
            assert stats.get("pipeline_id")==PIPELINE_ID, "obsolete reference; genuine original-source bank required"
            reference={key:archive["ref_"+key] for key in ("channels","frequencies","times","sample_offsets",
                "retained_event_indices","mean_power","trial_baseline_power","trial_target_power")}
            reference["source_events"]=json.loads(str(archive["ref_source_event_json"].item()))
            reference["stats"]=stats
    except (OSError,ValueError,KeyError) as error: raise AssertionError("missing/corrupt/obsolete genuine bank") from error
    validate_reference(reference)
    template=next((candidate for candidate in (Path("/app/method_contract.json"),
        Path(__file__).resolve().parents[1]/"environment/method_contract.json") if candidate.is_file()),None)
    assert template is not None, "public method contract missing"
    metadata=stats["metadata"]
    assert hashlib.sha256(template.read_bytes()).hexdigest()==metadata["method_contract_sha256"], "bank/public template fingerprint mismatch"
    assert load_json(template)==metadata["method_contract"], "bank/public method mismatch"
    assert np.array_equal(reference["frequencies"],np.arange(15,31)) and len(reference["channels"])==4
    for key in ("source_manifest_sha256","source_fif_sha256"):
        value=metadata[key]
        assert isinstance(value,str) and len(value)==64 and all(char in "0123456789abcdef" for char in value), "bank lacks source fingerprint"
    return reference

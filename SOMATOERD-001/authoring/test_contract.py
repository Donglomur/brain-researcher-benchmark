"""Small, explicitly synthetic mechanics fixtures; never scientific reference banks."""
from __future__ import annotations
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/"tests"))
import proof_of_work as q


def dump_json(path, obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")


def write_csv(path, fields, rows):
    with Path(path).open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def csv_rows(path):
    with Path(path).open(newline="") as stream:
        reader=csv.DictReader(stream)
        return reader.fieldnames,list(reader)


def synthetic_reference(sign=-1):
    """A 3-trial mechanics example with distinct baselines and heterogeneous CF scales."""
    contract=json.loads((TASK/"environment/method_contract.json").read_text())
    sfreq=100.
    offsets=np.arange(-150,151)
    times=offsets/sfreq
    channels=np.array(contract["channels"])
    frequencies=np.array(contract["frequencies_hz"],float)
    factor=(1+np.arange(64).reshape(4,16)/13.)*1e-24
    pulse=np.exp(-((times-.22)/.13)**2)
    background=np.sin(times*3.1)
    trial=np.stack([factor[...,None]*((index+1.5)+sign*(.10+.15*index)*pulse+.04*background)
                    for index in range(3)])
    if sign==0:
        trial=np.stack([np.broadcast_to(factor[...,None]*(index+1.5),factor.shape+(len(times),))
                        for index in range(3)])
    mean=trial.mean(axis=0)
    b,t=q.window_masks(times,contract)
    events=[dict(event_index=index,event_sample=3000+1000*index,event_code=1 if index<3 else 2,
                 retained=int(index<3),drop_reason="" if index<3 else "non_target_event",
                 epoch_start_sample=2850+1000*index,epoch_end_sample=3150+1000*index)
            for index in range(4)]
    metadata=dict(status="ok",task_id=q.TASK_ID,source_manifest_sha256="1"*64,source_fif_sha256="2"*64,
        method_contract_sha256=hashlib.sha256((TASK/"environment/method_contract.json").read_bytes()).hexdigest(),
        sfreq_hz=sfreq,first_samp=1000,n_source_samples=10000,n_discovered_events=4,n_trials=3,n_epoch_times=len(times),
        source_bads=[],n_source_projectors=0,software_versions={"fixture":"synthetic-mechanics-only"},
        method_contract=contract)
    reference=dict(channels=channels,frequencies=frequencies,times=times,sample_offsets=offsets,
        retained_event_indices=np.arange(3),mean_power=mean,
        trial_baseline_power=trial[...,b].mean(axis=-1),trial_target_power=trial[...,t].mean(axis=-1),
        source_events=events,stats=dict(pipeline_id=q.PIPELINE_ID,metadata=metadata))
    reference["derived"]=q.derive(mean,times,contract)
    reference["stats"]["results"]=q.result_from(reference)
    return q.validate_reference(reference)


def emit(output, reference):
    """Write numeric receipts from the explicitly supplied fixture or measured bank."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    write_csv(output/"source_events.csv",q.EVENT_FIELDS,reference["source_events"])
    write_csv(output/"mean_power.csv",q.MEAN_FIELDS,
        (dict(channel=str(channel),frequency_hz=float(frequency),time_index=t,time_s=float(time),
              mean_power_T2_per_m2=float(reference["mean_power"][c,f,t]))
         for c,channel in enumerate(reference["channels"])
         for f,frequency in enumerate(reference["frequencies"]) for t,time in enumerate(reference["times"])))
    write_csv(output/"trial_windows.csv",q.TRIAL_FIELDS,
        (dict(event_index=int(event),channel=str(channel),frequency_hz=float(frequency),
              baseline_power_T2_per_m2=float(reference["trial_baseline_power"][e,c,f]),
              target_power_T2_per_m2=float(reference["trial_target_power"][e,c,f]))
         for e,event in enumerate(reference["retained_event_indices"])
         for c,channel in enumerate(reference["channels"]) for f,frequency in enumerate(reference["frequencies"])))
    derived=q.derive(reference["mean_power"],reference["times"],reference["stats"]["metadata"]["method_contract"])
    write_csv(output/"beta_power_timecourse.csv",q.CURVE_FIELDS,
        (dict(time_index=t,time_s=float(time),beta_power_pct=float(derived["beta_power_pct"][t]))
         for t,time in enumerate(reference["times"])))
    dump_json(output/"erd.json",q.result_from(reference,derived))
    dump_json(output/"run_metadata.json",reference["stats"]["metadata"])
    (output/"findings.md").write_text("A descriptive calculation; no inferential claim.\n")


@pytest.fixture
def toy():
    return synthetic_reference()


@pytest.mark.parametrize("sign",[-1,0,1])
def test_both_signs_and_constant_zero_are_legitimate(tmp_path, sign):
    ref=synthetic_reference(sign)
    emit(tmp_path,ref)
    q.validate_output_directory(tmp_path,ref)


@pytest.mark.parametrize("value",["1","1.0","1e0",np.int64(1),1])
def test_exact_integer_notations(value):
    assert q.integer(value)==1


@pytest.mark.parametrize("value",[True,False,np.bool_(True),"true","False","1.01","NaN","Inf","",2**64])
def test_invalid_integer(value):
    with pytest.raises(AssertionError): q.integer(value)


@pytest.mark.parametrize("value",[True,"NaN","Infinity","",None])
def test_nonfinite_numeric_rejected(value):
    with pytest.raises(AssertionError): q.finite(value)


def test_si_tolerance_is_normalized_not_raw_atol():
    source=np.array([1e-24,1e-25])
    baseline=np.array([2e-24,2e-24])
    q.power_close(source*(1+1e-7),source,baseline,"tiny equivalent")
    for wrong in (np.zeros(2),source*2,np.full(2,1e-9)):
        with pytest.raises(AssertionError): q.power_close(wrong,source,baseline,"wrong source")


def test_baseline_and_trial_aggregation_are_distinct(toy):
    b=toy["trial_baseline_power"];t=toy["trial_target_power"]
    correct=100*(t.mean(axis=0)/b.mean(axis=0)-1).mean()
    wrong=(100*(t/b-1)).mean()
    assert abs(correct-wrong)>1e-3
    assert abs(correct-toy["derived"]["beta_erd_percent"])<1e-12


def test_sensor_pooling_before_normalization_changes_endpoint(toy):
    mean=toy["mean_power"].copy()
    # Unequal CF changes make a pooled ratio inequivalent to equally weighted ratios.
    _,target=q.window_masks(toy["times"],toy["stats"]["metadata"]["method_contract"])
    mean[0,0,target]*=2
    d=q.derive(mean,toy["times"],toy["stats"]["metadata"]["method_contract"])
    pooled=100*(d["target_power"].mean()/d["baseline_power"].mean()-1)
    assert abs(d["beta_erd_percent"]-pooled)>1e-3


def test_versions_truthful_not_oracle_identity(tmp_path,toy):
    emit(tmp_path,toy)
    metadata=q.load_json(tmp_path/"run_metadata.json")
    metadata["software_versions"]={"numpy":"other-valid-version","independent-convolution":"local-v1"}
    dump_json(tmp_path/"run_metadata.json",metadata)
    q.validate_output_directory(tmp_path,toy)


@pytest.mark.parametrize("versions",[{},[],{"numpy":""},{"numpy":1},{"":"1"},None])
def test_version_schema(versions):
    with pytest.raises(AssertionError): q.validate_versions({"software_versions":versions})


@pytest.mark.parametrize("field",["source_manifest_sha256","source_fif_sha256","method_contract_sha256",
                                 "first_samp","n_source_samples","n_discovered_events","n_trials","n_epoch_times"])
def test_source_metadata_cannot_be_forged(tmp_path,toy,field):
    emit(tmp_path,toy)
    metadata=q.load_json(tmp_path/"run_metadata.json")
    metadata[field]=("f"*64 if "sha256" in field else metadata[field]+1)
    dump_json(tmp_path/"run_metadata.json",metadata)
    with pytest.raises(AssertionError): q.validate_output_directory(tmp_path,toy)


def test_legacy_bank_always_rejected(tmp_path):
    legacy=tmp_path/"old.npz"
    np.savez_compressed(legacy,ref_stats=np.array(json.dumps({"pipeline_id":"old-correlation-bank"})))
    with pytest.raises(AssertionError,match="obsolete"): q.load_reference(legacy)


def test_physical_sample_clock_uses_first_samp(toy):
    bad=copy.deepcopy(toy)
    for row in bad["source_events"]:
        for key in ("event_sample","epoch_start_sample","epoch_end_sample"): row[key]-=1000
    # Self-consistent relative clock is still a different original source ledger.
    assert bad["source_events"]!=toy["source_events"]
    assert toy["source_events"][0]["event_sample"]-toy["stats"]["metadata"]["first_samp"]==2000


@pytest.mark.parametrize("exit_code",[0,3])
def test_actual_entrypoint_offline_python3(tmp_path,exit_code):
    """Run shell control flow with a fake Python3, no scientific processing or network."""
    script=(TASK/"tests/test.sh").read_text()
    assert "python3 -m pytest" in script
    for forbidden in ("uvx","pip install","curl","wget","apt-get","source $HOME"):
        assert forbidden not in script
    bindir=tmp_path/"bin";bindir.mkdir()
    stub=bindir/"python3"
    stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGS_FILE\"\nexit \"$FAKE_EXIT\"\n")
    stub.chmod(0o755)
    altered=tmp_path/"test.sh"
    altered.write_text(script.replace("/logs/verifier",str(tmp_path/"logs")))
    env=dict(os.environ,PATH=str(bindir)+os.pathsep+os.environ["PATH"],
             ARGS_FILE=str(tmp_path/"args"),FAKE_EXIT=str(exit_code))
    proc=subprocess.run(["/bin/bash",str(altered)],env=env,capture_output=True,text=True,timeout=10)
    assert proc.returncode==exit_code
    assert (tmp_path/"logs/reward.txt").read_text().strip()==("1" if exit_code==0 else "0")
    args=(tmp_path/"args").read_text().splitlines()
    assert args[:2]==["-m","pytest"] and "/tests/test_outputs.py" in args


def builder_module():
    spec=importlib.util.spec_from_file_location("somato_builder_mechanics",TASK/"authoring/build_reference.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("frequency",[15.,20.,30.])
def test_explicit_morlet_matches_pinned_formula(frequency):
    import mne
    builder=builder_module()
    actual=builder.explicit_morlet(300.3074951171875,frequency)
    expected=mne.time_frequency.morlet(300.3074951171875,[frequency],n_cycles=frequency/2,zero_mean=True)[0]
    np.testing.assert_allclose(actual,expected,atol=1e-15,rtol=1e-14)
    assert abs(np.linalg.norm(actual)-np.sqrt(2))<1e-14


def test_independent_frequency_at_a_time_convolution_on_tiny_signals(toy):
    import mne
    builder=builder_module()
    rng=np.random.RandomState(72)
    epochs=rng.normal(size=(2,4,len(toy["times"])))*1e-13
    contract=toy["stats"]["metadata"]["method_contract"]
    expected=mne.time_frequency.tfr_array_morlet(epochs,sfreq=100.,freqs=toy["frequencies"],
        n_cycles=toy["frequencies"]/2,zero_mean=True,use_fft=True,output="power",n_jobs=1,verbose="error")
    actual=builder.independent_powers(epochs,toy["times"],100.,contract)
    b,t=q.window_masks(toy["times"],contract)
    derived=q.derive(expected.mean(axis=0),toy["times"],contract)
    q.power_close(actual["mean_power"],expected.mean(axis=0),derived["baseline_power"][...,None],"toy independent powers")
    q.power_close(actual["trial_baseline_power"],expected[...,b].mean(axis=-1),derived["baseline_power"][None,...],"toy baseline")
    q.power_close(actual["trial_target_power"],expected[...,t].mean(axis=-1),derived["baseline_power"][None,...],"toy target")
    q.close(actual["beta_power_pct"],derived["beta_power_pct"],"toy equivalent percentages")


def test_builder_import_has_no_source_execution_or_bank_writes():
    before=(TASK/"tests/reference.npz").read_bytes()
    module=builder_module()
    assert callable(module.build) and callable(module.independent_powers)
    assert (TASK/"tests/reference.npz").read_bytes()==before

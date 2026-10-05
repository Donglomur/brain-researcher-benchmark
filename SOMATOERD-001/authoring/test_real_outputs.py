"""Mutation tests require real original-source outputs; never fabricate a bank."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from test_contract import TASK, q, csv_rows, write_csv, dump_json, emit


@pytest.fixture(scope="module")
def genuine():
    value=os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not value:
        pytest.skip("requires parent-executed original-source oracle")
    path=Path(value)
    assert path.is_dir(), "explicit genuine-output path is missing"
    return path,q.load_reference()


@pytest.fixture
def copied(tmp_path,genuine):
    original,reference=genuine
    output=tmp_path/"submission"
    shutil.copytree(original,output)
    return output,reference


def rewrite(path, callback):
    fields,rows=csv_rows(path)
    callback(rows)
    write_csv(path,fields,rows)


def fails(output,reference):
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


def test_genuine_oracle_complete(genuine):
    output,reference=genuine
    q.validate_output_directory(output,reference)


def test_genuine_independent_implementation(genuine):
    _output,reference=genuine
    value=os.environ.get("REPAIR_INDEPENDENT_OUTPUT")
    if not value: pytest.skip("requires parent-executed independent output")
    assert Path(value).is_dir()
    q.validate_output_directory(value,reference)


def test_public_template_identity_and_minimal_metadata(copied):
    output,reference=copied
    metadata=q.load_json(output/"run_metadata.json")
    public=q.load_json(TASK/"environment/method_contract.json")
    assert public==reference["stats"]["metadata"]["method_contract"]==metadata["method_contract"]
    metadata={key:metadata[key] for key in q.METADATA_FIELDS}
    metadata["method_contract"]=public
    dump_json(output/"run_metadata.json",metadata)
    q.validate_output_directory(output,reference)


def test_genuine_alternate_version_report(copied):
    output,reference=copied
    metadata=q.load_json(output/"run_metadata.json")
    metadata["software_versions"]={"independent-implementation":"own-reported-version"}
    dump_json(output/"run_metadata.json",metadata)
    q.validate_output_directory(output,reference)


def test_order_extra_columns_equivalent_numbers(copied):
    output,reference=copied
    integer_fields=set(q.EVENT_FIELDS)-{"drop_reason"}
    integer_fields|={"time_index","frequency_hz"}
    for filename in ("source_events.csv","mean_power.csv","trial_windows.csv","beta_power_timecourse.csv"):
        fields,rows=csv_rows(output/filename)
        for row in rows:
            row["optional_note"]="not graded"
            for field in integer_fields.intersection(row):
                previous=q.integer(row[field])
                row[field]=format(float(previous),".17e")
                assert q.integer(row[field])==previous
        write_csv(output/filename,list(reversed(fields))+["optional_note"],list(reversed(rows)))
    q.validate_output_directory(output,reference)


def test_free_prose_and_optional_private_files_ignored(copied):
    output,reference=copied
    (output/"findings.md").write_text("A numerical observation, not an inferential conclusion.\n")
    (output/"analysis_arrays.npz").write_text("Optional participant extras are not scored.")
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",q.FILES)
def test_every_required_file_missing(copied,filename):
    output,reference=copied
    (output/filename).unlink()
    fails(output,reference)


def test_empty_findings(copied):
    output,reference=copied
    (output/"findings.md").write_text(" \n")
    fails(output,reference)


@pytest.mark.parametrize("filename",["source_events.csv","mean_power.csv","trial_windows.csv","beta_power_timecourse.csv"])
@pytest.mark.parametrize("operation",["drop","duplicate"])
def test_complete_unique_keys(copied,filename,operation):
    output,reference=copied
    rewrite(output/filename,lambda rows: rows.pop() if operation=="drop" else rows.append(dict(rows[0])))
    fails(output,reference)


@pytest.mark.parametrize("filename,field,value",[
    ("source_events.csv","event_sample","1.5"),
    ("source_events.csv","retained","true"),
    ("source_events.csv","drop_reason","invented exclusion"),
    ("mean_power.csv","frequency_hz","14"),
    ("mean_power.csv","time_index","true"),
    ("mean_power.csv","channel","MEG 1342 alias"),
    ("mean_power.csv","mean_power_T2_per_m2","NaN"),
    ("trial_windows.csv","event_index","0.01"),
    ("trial_windows.csv","target_power_T2_per_m2","Infinity"),
    ("beta_power_timecourse.csv","time_s","NaN"),
    ("beta_power_timecourse.csv","beta_power_pct","NaN"),
])
def test_bad_keys_and_nonfinite(copied,filename,field,value):
    output,reference=copied
    rewrite(output/filename,lambda rows:rows[0].__setitem__(field,value))
    fails(output,reference)


def test_relative_event_clock_cannot_impersonate_source(copied):
    output,reference=copied
    first=reference["stats"]["metadata"]["first_samp"]
    assert first!=0
    def edit(rows):
        for row in rows:
            for field in ("event_sample","epoch_start_sample","epoch_end_sample"):
                row[field]=q.integer(row[field])-first
    rewrite(output/"source_events.csv",edit)
    metadata=q.load_json(output/"run_metadata.json");metadata["first_samp"]=0
    dump_json(output/"run_metadata.json",metadata)
    fails(output,reference)


@pytest.mark.parametrize("scale",[0.,.5,2.])
def test_coherent_raw_power_rescaling_not_hidden_by_unchanged_percent(tmp_path,genuine,scale):
    _original,reference=genuine
    forged=copy.deepcopy(reference)
    for key in ("mean_power","trial_baseline_power","trial_target_power"):
        forged[key]=forged[key]*scale
    output=tmp_path/"forgery"
    if scale>0:
        emit(output,forged)  # All percentage/JSON arithmetic is reconstructed coherently.
        assert np.allclose(q.load_json(output/"erd.json")["beta_erd_percent"],
                           reference["derived"]["beta_erd_percent"],atol=1e-10,rtol=0)
        fails(output,reference)
    else:
        # Preserve plausible percentages but replace all raw evidence by zeros.
        # A zero baseline has no legitimate percent definition and must not be
        # swallowed by a raw SI-space absolute tolerance.
        shutil.copytree(_original,output)
        for filename,fields in (("mean_power.csv",["mean_power_T2_per_m2"]),
                                ("trial_windows.csv",["baseline_power_T2_per_m2","target_power_T2_per_m2"])):
            def edit(rows):
                for row in rows:
                    for field in fields: row[field]=0
            rewrite(output/filename,edit)
        fails(output,reference)


@pytest.mark.parametrize("axis",[0,1])
def test_swap_sensor_or_frequency_identity_preserves_band_curve_but_fails(tmp_path,genuine,axis):
    _original,reference=genuine
    forged=copy.deepcopy(reference)
    permutation=np.arange(reference["mean_power"].shape[axis])[::-1]
    forged["mean_power"]=np.take(reference["mean_power"],permutation,axis=axis)
    for key in ("trial_baseline_power","trial_target_power"):
        forged[key]=np.take(reference[key],permutation,axis=axis+1)
    assert np.any(forged["mean_power"]!=reference["mean_power"])
    output=tmp_path/"forgery";emit(output,forged)
    q.close(q.load_json(output/"erd.json")["beta_erd_percent"],reference["derived"]["beta_erd_percent"],"same band mean")
    fails(output,reference)


def test_trial_identity_permutation_preserves_aggregates_but_fails(tmp_path,genuine):
    _original,reference=genuine
    forged=copy.deepcopy(reference)
    for key in ("trial_baseline_power","trial_target_power"): forged[key]=reference[key][::-1].copy()
    assert np.any(forged["trial_baseline_power"]!=reference["trial_baseline_power"])
    output=tmp_path/"forgery";emit(output,forged)
    q.read_mean_power(output,reference)  # Unchanged aggregate truly remains valid.
    with pytest.raises(AssertionError,match="trial baseline"): q.read_trial_windows(output,reference)


def test_normalize_each_trial_first_is_not_the_declared_estimator(copied):
    output,reference=copied
    wrong=float((100*(reference["trial_target_power"]/reference["trial_baseline_power"]-1)).mean())
    assert abs(wrong-reference["derived"]["beta_erd_percent"])>q.PERCENT_ATOL, "actual control is not distinguishable"
    value=q.load_json(output/"erd.json");value["beta_erd_percent"]=wrong
    dump_json(output/"erd.json",value)
    fails(output,reference)


def test_pool_sensor_frequency_before_normalization_wrong(copied):
    output,reference=copied
    mean=reference["mean_power"].mean(axis=(0,1))
    b,t=q.window_masks(reference["times"],reference["stats"]["metadata"]["method_contract"])
    wrong=100*(mean/mean[b].mean()-1)
    assert np.max(abs(wrong-reference["derived"]["beta_power_pct"]))>q.PERCENT_ATOL
    fields,rows=csv_rows(output/"beta_power_timecourse.csv")
    for row in rows: row["beta_power_pct"]=float(wrong[q.integer(row["time_index"])])
    write_csv(output/"beta_power_timecourse.csv",fields,rows)
    result=q.load_json(output/"erd.json");result["beta_erd_percent"]=float(wrong[t].mean())
    dump_json(output/"erd.json",result)
    fails(output,reference)


def test_endpoint_preserving_correlation_shortcut_fails(copied):
    output,reference=copied
    endpoint=reference["derived"]["beta_erd_percent"]
    wrong=2*reference["derived"]["beta_power_pct"]-endpoint
    fields,rows=csv_rows(output/"beta_power_timecourse.csv")
    for row in rows: row["beta_power_pct"]=float(wrong[q.integer(row["time_index"])])
    write_csv(output/"beta_power_timecourse.csv",fields,rows)
    _,t=q.window_masks(reference["times"],reference["stats"]["metadata"]["method_contract"])
    q.close(float(wrong[t].mean()),endpoint,"unchanged endpoint")
    assert np.max(abs(wrong-reference["derived"]["beta_power_pct"]))>q.PERCENT_ATOL
    fails(output,reference)


@pytest.mark.parametrize("field",["source_manifest_sha256","source_fif_sha256","method_contract_sha256","status",
                                  "n_trials","n_epoch_times","n_source_samples","n_source_projectors","source_bads"])
def test_metadata_forgery(copied,field):
    output,reference=copied
    metadata=q.load_json(output/"run_metadata.json")
    if "sha256" in field: metadata[field]="f"*64
    elif field=="status": metadata[field]="resource_pilot"
    elif field=="source_bads": metadata[field]=["MEG 1342"]
    else: metadata[field]+=1
    dump_json(output/"run_metadata.json",metadata)
    fails(output,reference)


def test_wrong_public_method_claim(copied):
    output,reference=copied
    metadata=q.load_json(output/"run_metadata.json")
    metadata["method_contract"]["morlet"]["zero_mean"]=False
    dump_json(output/"run_metadata.json",metadata)
    fails(output,reference)


@pytest.mark.parametrize("field,value",[("band_hz",[16,30]),("window_ms",[0,350]),("baseline_ms",[-1000,0]),("n_trials",0)])
def test_wrong_result_scope(copied,field,value):
    output,reference=copied
    result=q.load_json(output/"erd.json");result[field]=value
    dump_json(output/"erd.json",result)
    fails(output,reference)

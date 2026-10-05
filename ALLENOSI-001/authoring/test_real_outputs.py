"""Genuine original-source positives and coherent negative receipts.

REPAIR_ORACLE_OUTPUT must point to the full immutable-source execution. Tests
only copy/mutate task-owned temporary outputs, never raw NWB data or the bank.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from test_contract import TASK, emit, write_csv, public_value
import proof_of_work as q


@pytest.fixture(scope="module")
def genuine_output():
    configured=os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not configured:pytest.skip("requires genuine immutable-source oracle output")
    path=Path(configured);assert path.is_dir()
    return path


@pytest.fixture(scope="module")
def reference(genuine_output):
    reference=q.load_reference(TASK/"tests/reference.npz")
    q.validate_output_directory(genuine_output,reference)
    return reference


@pytest.fixture
def output(tmp_path,genuine_output):
    for filename in (*q.FILES,*q.QC_FILES):
        if (genuine_output/filename).is_file():shutil.copyfile(genuine_output/filename,tmp_path/filename)
    return tmp_path


def test_genuine_original_output_without_private_arrays(output,reference):
    assert not (output/"analysis_arrays.npz").exists()
    q.validate_output_directory(output,reference)


def test_primary_only_no_qc_artifact_is_required(output,reference):
    for filename in q.QC_FILES:
        if (output/filename).exists():(output/filename).unlink()
    result=q.load_json(output/"results.json")
    for key in q.QC_RESULT_KEYS:result.pop(key,None)
    (output/"results.json").write_text(json.dumps(result))
    metadata=q.load_json(output/"run_metadata.json");metadata["include_qc"]=False
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    primary,qc=q.validate_output_directory(output,reference)
    assert qc is None and len(primary["osi"])==len(reference["unit_ids"])


def test_separate_genuine_primary_only_execution(reference):
    configured=os.environ.get("REPAIR_PRIMARY_OUTPUT")
    if not configured:pytest.skip("requires separately retained genuine --no-qc execution")
    source=Path(configured)
    assert all(not (source/filename).exists() for filename in q.QC_FILES)
    primary,qc=q.validate_output_directory(source,reference)
    assert qc is None and len(primary["osi"])==len(reference["unit_ids"])


def test_public_template_identity_and_minimal_measured_metadata(output,reference):
    template=q.load_json(TASK/"environment/method_contract.json")
    assert template==reference["stats"]["metadata_contract"]
    measured=q.load_json(output/"run_metadata.json")
    for key in ("status","n_units_total","n_visp_units_total","n_original_presentations",
                "n_blank_presentations","n_gratings_presentations","directions","temporal_frequencies","include_qc"):
        template[key]=measured[key]
    (output/"run_metadata.json").write_text(json.dumps(template))
    (output/"findings.md").write_text("These tables report one-session descriptive measurements under the stated method.")
    q.validate_output_directory(output,reference)


def test_rows_columns_extras_and_exact_numeric_id_formats(output,reference):
    fields_by_file={"presentations.csv":q.PRESENTATION_FIELDS,"trial_responses.csv":q.TRIAL_FIELDS,
                    "condition_means.csv":q.CONDITION_FIELDS,"units.csv":q.UNIT_FIELDS,
                    "baseline_counts.csv":("unit_id","presentation_id","spike_count"),"qc_sensitivity.csv":q.QC_FIELDS}
    for filename,fields in fields_by_file.items():
        if not (output/filename).exists():continue
        rows=q.read_csv(output/filename,fields)
        for row in rows:
            for key in ("unit_id","presentation_id","peak_channel_id","spike_count","n_presentations"):
                if key in row:
                    original=q.integer(row[key],key)
                    row[key]=format(float(original),".17e")
                    assert q.integer(row[key],key)==original
            row["optional_description"]="not graded"
        write_csv(output/filename,list(rows[0])[::-1],rows[::-1])
    metadata=q.load_json(output/"run_metadata.json");metadata["extra_diagnostic"]={"note":"permitted"}
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(output,reference)


def test_optional_private_artifact_is_ignored(output,reference):
    (output/"analysis_arrays.npz").write_bytes(b"not a required participant artifact")
    q.validate_output_directory(output,reference)


def test_genuine_full_independent_histogram_and_summary_outputs(output,reference):
    configured=os.environ.get("REPAIR_INDEPENDENT_COUNTS")
    if not configured:pytest.skip("requires retained independently counted original source and report")
    artifact_path=Path(configured)
    report_path=Path(os.environ["REPAIR_INDEPENDENT_REPORT"]) if os.environ.get("REPAIR_INDEPENDENT_REPORT") else artifact_path.with_name(artifact_path.name.removesuffix(".counts.npz")+".json")
    report=q.load_json(report_path)
    assert report["status"]=="passed" and report["pipeline_id"]==q.PIPELINE_ID
    assert report["source_sha256"]==reference["stats"]["source_sha256"]
    assert report["source_manifest_sha256"]==reference["stats"]["metadata_contract"]["source_manifest_sha256"]
    assert hashlib.sha256(artifact_path.read_bytes()).hexdigest()==report["independent_counts_sha256"]
    with np.load(artifact_path,allow_pickle=False) as artifact:
        arrays={key:artifact[key] for key in artifact.files}
    assert str(arrays["pipeline_id"].item())==q.PIPELINE_ID
    assert json.loads(str(arrays["source_sha256_json"].item()))==reference["stats"]["source_sha256"]
    assert np.array_equal(arrays["unit_id"],reference["unit_ids"])
    assert np.array_equal(arrays["presentation_id"],reference["presentation_ids"])
    uid,pid=arrays["unit_id"],arrays["presentation_id"]
    assert arrays["spike_count"].shape==arrays["baseline_spike_count"].shape==(len(uid),len(pid))
    # All public numeric tables below come directly from the independently
    # retained histogram/fsum computation, not recomputation from bank answers.
    write_csv(output/"presentations.csv",q.PRESENTATION_FIELDS,[
        {key:public_value(arrays[key][j]) for key in q.PRESENTATION_FIELDS} for j in range(len(pid))])
    write_csv(output/"trial_responses.csv",q.TRIAL_FIELDS,[
        dict(unit_id=int(unit),presentation_id=int(presentation),spike_count=int(arrays["spike_count"][i,j]),rate_hz=float(arrays["rate_hz"][i,j]))
        for i,unit in enumerate(uid) for j,presentation in enumerate(pid)])
    write_csv(output/"condition_means.csv",q.CONDITION_FIELDS,[
        dict(unit_id=int(unit),direction=float(direction),temporal_frequency=float(frequency),
             n_presentations=int(arrays["condition_n_presentations"][di,ti]),mean_rate_hz=float(arrays["mean_rate_hz"][i,di,ti]))
        for i,unit in enumerate(uid) for di,direction in enumerate(q.DIRECTIONS) for ti,frequency in enumerate(arrays["temporal_frequencies"])])
    write_csv(output/"units.csv",q.UNIT_FIELDS,[
        {key:public_value(arrays[key][i]) for key in q.UNIT_FIELDS} for i in range(len(uid))])
    write_csv(output/"baseline_counts.csv",("unit_id","presentation_id","spike_count"),[
        dict(unit_id=int(unit),presentation_id=int(presentation),spike_count=int(arrays["baseline_spike_count"][i,j]))
        for i,unit in enumerate(uid) for j,presentation in enumerate(pid)])
    write_csv(output/"qc_sensitivity.csv",q.QC_FIELDS,[
        {key:public_value(arrays[key][i]) for key in q.QC_FIELDS} for i in range(len(uid))])
    (output/"results.json").write_text(str(arrays["results_json"].item()))
    metadata=q.load_json(output/"run_metadata.json")
    metadata["independent_implementation"]="Histogram endpoint-bin counts; explicit condition means using math.fsum"
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["scale_counts","single_spike","unit_permutation","trial_permutation"])
def test_coherently_recomputed_false_counts_fail_source_binding(output,reference,mutation):
    counts=reference["spike_counts"].copy()
    if mutation=="scale_counts":counts*=2
    elif mutation=="single_spike":counts[0,0]+=1
    elif mutation=="unit_permutation":counts=counts[::-1].copy()
    elif mutation=="trial_permutation":counts=counts[:,::-1].copy()
    assert not np.array_equal(counts,reference["spike_counts"])
    emit(output,reference,True,counts=counts)
    with pytest.raises(AssertionError,match="spike counts differ"):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",["trial_responses.csv","baseline_counts.csv"])
@pytest.mark.parametrize("mutation",["drop","duplicate","prefix_id","fractional_id","unknown_unit","unknown_presentation","fractional_count","negative_count","wrong_count"])
def test_complete_original_unit_presentation_product(output,reference,filename,mutation):
    if filename=="baseline_counts.csv":assert (output/filename).is_file(),"oracle should retain genuine optional QC for authoring tests"
    fields=q.TRIAL_FIELDS if filename=="trial_responses.csv" else ("unit_id","presentation_id","spike_count")
    rows=q.read_csv(output/filename,fields)
    if mutation=="drop":rows.pop()
    elif mutation=="duplicate":rows.append(dict(rows[0]))
    elif mutation=="prefix_id":rows[0]["unit_id"]="unit"+rows[0]["unit_id"]
    elif mutation=="fractional_id":rows[0]["unit_id"]=rows[0]["unit_id"]+".5"
    elif mutation=="unknown_unit":rows[0]["unit_id"]="999999999999"
    elif mutation=="unknown_presentation":rows[0]["presentation_id"]="999999999999"
    elif mutation=="fractional_count":rows[0]["spike_count"]="1.5"
    elif mutation=="negative_count":rows[0]["spike_count"]="-1"
    elif mutation=="wrong_count":rows[0]["spike_count"]=str(int(rows[0]["spike_count"])+1)
    write_csv(output/filename,fields,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["drop","duplicate","start","stop","duration","direction","frequency","invent_id"])
def test_original_presentation_identity_and_timing(output,reference,mutation):
    rows=q.read_csv(output/"presentations.csv",q.PRESENTATION_FIELDS)
    if mutation=="drop":rows.pop()
    elif mutation=="duplicate":rows.append(dict(rows[0]))
    elif mutation=="start":rows[0]["start_time"]=str(float(rows[0]["start_time"])+.001)
    elif mutation=="stop":rows[0]["stop_time"]=str(float(rows[0]["stop_time"])+.001)
    elif mutation=="duration":rows[0]["duration_seconds"]=str(float(rows[0]["duration_seconds"])+.001)
    elif mutation=="direction":rows[0]["direction"]=str((float(rows[0]["direction"])+45)%360)
    elif mutation=="frequency":rows[0]["temporal_frequency"]=str(float(rows[0]["temporal_frequency"])+1)
    elif mutation=="invent_id":rows[0]["presentation_id"]="999999999999"
    write_csv(output/"presentations.csv",q.PRESENTATION_FIELDS,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["drop","duplicate","wrong_repeat","mean_shift","scale_means","wrong_direction","wrong_tf"])
def test_condition_means_and_membership(output,reference,mutation):
    rows=q.read_csv(output/"condition_means.csv",q.CONDITION_FIELDS)
    if mutation=="drop":rows.pop()
    elif mutation=="duplicate":rows.append(dict(rows[0]))
    elif mutation=="wrong_repeat":rows[0]["n_presentations"]=str(int(rows[0]["n_presentations"])+1)
    elif mutation=="mean_shift":rows[0]["mean_rate_hz"]=str(float(rows[0]["mean_rate_hz"])+1)
    elif mutation=="scale_means":
        for row in rows:row["mean_rate_hz"]=str(2*float(row["mean_rate_hz"])+.1)
    elif mutation=="wrong_direction":rows[0]["direction"]="20"
    elif mutation=="wrong_tf":rows[0]["temporal_frequency"]="999"
    write_csv(output/"condition_means.csv",q.CONDITION_FIELDS,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["drop","duplicate","prefix_id","channel","tf","orientation","r_pref","r_orth","peak","osi","osi_defined","selective"])
def test_every_unit_tuning_chain(output,reference,mutation):
    rows=q.read_csv(output/"units.csv",q.UNIT_FIELDS)
    if mutation=="drop":rows.pop()
    elif mutation=="duplicate":rows.append(dict(rows[0]))
    elif mutation=="prefix_id":rows[0]["unit_id"]="unit"+rows[0]["unit_id"]
    elif mutation=="channel":rows[0]["peak_channel_id"]=str(int(rows[0]["peak_channel_id"])+1)
    elif mutation=="tf":rows[0]["preferred_temporal_frequency"]="999"
    elif mutation=="orientation":rows[0]["preferred_orientation"]=str((float(rows[0]["preferred_orientation"])+45)%180)
    elif mutation in ("r_pref","r_orth","peak"):
        field={"r_pref":"r_pref_hz","r_orth":"r_orth_hz","peak":"peak_rate_hz"}[mutation]
        rows[0][field]=str(float(rows[0][field])+1)
    elif mutation=="osi":rows[0]["osi"]=str(float(rows[0]["osi"])+.1)
    elif mutation in ("osi_defined","selective"):rows[0][mutation]=str(not q.boolean(rows[0][mutation],mutation))
    write_csv(output/"units.csv",q.UNIT_FIELDS,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",["isi_violations","amplitude_cutoff","presence_ratio","baseline_rate_hz",
                                 "qc_metrics_complete","qc_pass","responsive","in_qc_responsive"])
def test_optional_qc_is_source_and_count_bound(output,reference,field):
    rows=q.read_csv(output/"qc_sensitivity.csv",q.QC_FIELDS)
    if field in ("qc_metrics_complete","qc_pass","responsive","in_qc_responsive"):
        rows[0][field]=str(not q.boolean(rows[0][field],field))
    else:
        row=next(row for row in rows if row[field])
        row[field]=str(float(row[field])+1)
    write_csv(output/"qc_sensitivity.csv",q.QC_FIELDS,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",["n_visp_units_total","n_visp_units_analyzed","n_orientation_selective",
 "n_osi_undefined","orientation_selective_fraction","osi_threshold","n_qc_responsive_units",
 "n_qc_responsive_orientation_selective","qc_responsive_selective_fraction"])
def test_declared_counts_denominators_and_fractions(output,reference,field):
    result=q.load_json(output/"results.json")
    value=result[field]
    result[field]=1 if value is None else value+(.1 if "fraction" in field or field=="osi_threshold" else 1)
    (output/"results.json").write_text(json.dumps(result))
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["hash","extra_hash","pipeline","total_units","original_presentations",
 "blank_presentations","selected_presentations","visp_units","directions","frequencies","include_qc"])
def test_public_source_metadata(output,reference,mutation):
    metadata=q.load_json(output/"run_metadata.json")
    if mutation=="hash":metadata["source_sha256"][next(iter(metadata["source_sha256"]))]="0"*64
    elif mutation=="extra_hash":metadata["source_sha256"]["other"]="0"*64
    elif mutation=="pipeline":metadata["pipeline_id"]="old"
    elif mutation in ("total_units","original_presentations","blank_presentations","selected_presentations","visp_units"):
        key={"total_units":"n_units_total","original_presentations":"n_original_presentations","blank_presentations":"n_blank_presentations",
             "selected_presentations":"n_gratings_presentations","visp_units":"n_visp_units_total"}[mutation]
        metadata[key]+=1
    elif mutation=="directions":metadata["directions"].pop()
    elif mutation=="frequencies":metadata["temporal_frequencies"].append(999)
    elif mutation=="include_qc":metadata["include_qc"]=False
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",q.FILES)
def test_missing_required_files(output,reference,filename):
    (output/filename).unlink()
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",q.QC_FILES)
def test_optional_claim_requires_both_qc_artifacts(output,reference,filename):
    (output/filename).unlink()
    with pytest.raises(AssertionError,match="QC sensitivity"):q.validate_output_directory(output,reference)


def test_empty_findings(output,reference):
    (output/"findings.md").write_text(" \n ")
    with pytest.raises(AssertionError,match="empty findings"):q.validate_output_directory(output,reference)

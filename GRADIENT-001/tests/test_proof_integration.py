"""Manufactured private-basis integration; never original data or old targets."""
import copy
import csv
import json

import numpy as np
import pytest

import artifact_reader as a
import fixture_support as f
import gradient_reporting as r
import proof_of_work as p


@pytest.fixture(scope="module")
def reference():
    return f.manufactured_reference()


@pytest.fixture
def output(tmp_path,reference):
    return f.emit(tmp_path/"output",reference)


def rewrite_npz(output, callback):
    path=output/"gradient_arrays.npz"
    with np.load(path,allow_pickle=False) as saved:arrays={key:saved[key] for key in saved.files}
    callback(arrays)
    with path.open("wb") as handle:np.savez_compressed(handle,**arrays)


def rewrite_csv(output,name,callback):
    path=output/name
    with path.open(newline="") as handle:reader=csv.DictReader(handle);fields=reader.fieldnames;rows=list(reader)
    callback(rows)
    with path.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def rewrite_json(output,name,callback):
    path=output/name;value=json.loads(path.read_text());callback(value);path.write_text(json.dumps(value,allow_nan=False))


def test_complete_identical_people_are_allowed(output,reference):
    result=p.validate(output,reference)
    assert result["status"]=="accepted" and result["gpa_defined"]


def test_complete_undefined_support_is_valid_not_zero_imputed(tmp_path):
    ref=f.manufactured_reference(undefined=True);out=f.emit(tmp_path/"undefined",ref)
    assert p.validate(out,ref)["n_operator_valid"]==0
    results=json.loads((out/"results.json").read_text())
    assert results["unaligned_signed"]["value"] is None
    assert results["principal_gradient_identity_robust"] is None


def test_harmless_json_extras_software_and_free_prose(output,reference):
    def metadata(value):
        value["source_observed"]["headers"][reference["arrays"]["participant_ids"][0]]["description"]="harmless"
        value["software_versions"]={key:"alternative implementation" for key in value["software_versions"]}
        value["source_observed"]["frame_alignment"]="The same released-frame ordering; no measured onset claim."
    rewrite_json(output,"run_metadata.json",metadata)
    rewrite_json(output,"results.json",lambda value:value.update(claim_scope="Opposite findings are equally valid.",extra={"value":.25}))
    (output/"findings.md").write_text("No Default-apex, alignment-gain, or instability claim is required.")
    assert p.validate(output,reference)["status"]=="accepted"


def test_source_receipt_rounding_and_integral_float_axes(output,reference):
    def change(arrays):
        arrays["raw_means"]=arrays["raw_means"].astype(np.float32)
        arrays["cleaned_series"]=arrays["cleaned_series"].astype(np.float32)
        for key in ("source_positions","frame_indices","parcel_ids"):arrays[key]=arrays[key].astype(float)
        arrays["raw_diffusion"]+=2e-7
        arrays["gpa_reference_history"]+=2e-7
    rewrite_npz(output,change)
    assert p.validate(output,reference)["status"]=="accepted"


def test_csv_rows_columns_and_keyed_json_order_are_not_signals(output,reference):
    for name in ("cohort.csv","parcels.csv","configurations.csv","per_subject.csv"):
        rewrite_csv(output,name,lambda rows:rows.reverse())
    def reorder(value):
        value["source_files"].reverse();observed=value["source_observed"]
        observed["participant_ids"].reverse();observed["atlas_labels"].reverse()
        for rows in observed["voxel_support_by_subject"].values():rows.reverse()
    rewrite_json(output,"run_metadata.json",reorder)
    rewrite_json(output,"results.json",lambda value:value["configuration_summaries"].reverse())
    assert p.validate(output,reference)["status"]=="accepted"


def test_all_coherent_npz_axes_and_pair_direction_reorder(output,reference):
    def reorder(arrays):
        permutations={name:np.arange(len(arrays[key]))[::-1] for name,key in (
            ("s","participant_ids"),("t","frame_indices"),("p","parcel_ids"),("a","arm_ids"),
            ("c","configuration_ids"),("e","embedding_ids"),("q","quantity_ids"))}
        layouts={
            "participant_ids":"s","source_positions":"s","frame_indices":"t","parcel_ids":"p","arm_ids":"a",
            "configuration_ids":"c","configuration_membership":"cs","raw_means":"stp","geometry_valid":"sp",
            "raw_sample_sd":"sp","activity_threshold":"sp","cleaned_series":"satp","clean_centered_l2":"sap",
            "person_parcel_active":"sap","fc":"sapp","configuration_fc":"cpp","configuration_parcel_active":"cp",
            "embedding_ids":"e","operator_valid":"e","embedding_valid":"e","principal_valid":"e","retained_span_valid":"e",
            "eigenvalues":"e-","eigenvectors":"ep-","raw_diffusion":"ep-","gpa_rotations":"-s--",
            "gpa_reference_history":"-p-","aligned_gradients":"sp-","quantity_ids":"q","display_signs":"q-",
            "display_coordinates":"qp-","display_valid":"q-"}
        for key,layout in layouts.items():
            value=arrays[key]
            for dimension,label in enumerate(layout):
                if label!="-":value=np.take(value,permutations[label],axis=dimension)
            arrays[key]=value
        arrays["pair_participant_ids"]=arrays["pair_participant_ids"][::-1,::-1]
        arrays["signed_pair_consistency"]=arrays["signed_pair_consistency"][::-1]
        arrays["pair_consistency_valid"]=arrays["pair_consistency_valid"][::-1]
    rewrite_npz(output,reorder)
    assert p.validate(output,reference)["status"]=="accepted"


def test_keyed_metadata_dtype_alias_is_equivalent(output,reference):
    def change(value):
        observed=value["source_observed"]
        observed["atlas_header"]["source_dtype"]="float32"
        for row in observed["headers"].values():row["source_dtype"]="float32"
    rewrite_json(output,"run_metadata.json",change)
    assert p.validate(output,reference)["status"]=="accepted"


@pytest.mark.parametrize("mode",["raw","clean","fc","support","source_position","basis_scale","eigenvalue","raw_sign",
                               "gradient","rotation","history","display","pair","null","nonfinite_extra"])
def test_numerical_and_source_mutations_fail(output,reference,mode):
    def mutate(arrays):
        if mode=="raw":arrays["raw_means"][0,0,0]+=1
        elif mode=="clean":arrays["cleaned_series"][0,0,0,0]+=1
        elif mode=="fc":arrays["fc"][0,0,0,1]+=.1
        elif mode=="support":arrays["person_parcel_active"][0,0,0]=False
        elif mode=="source_position":arrays["source_positions"][0]=19
        elif mode=="basis_scale":arrays["eigenvectors"][0,:,0]*=2
        elif mode=="eigenvalue":arrays["eigenvalues"][0,0]+=.01
        elif mode=="raw_sign":
            arrays["eigenvectors"][0,:,0]*=-1;arrays["raw_diffusion"][0,:,0]*=-1
        elif mode=="gradient":arrays["raw_diffusion"][0,0,0]+=1
        elif mode=="rotation":arrays["gpa_rotations"][0,0,0,0]+=1
        elif mode=="history":arrays["gpa_reference_history"][1,0,0]+=1
        elif mode=="display":arrays["display_coordinates"][0,0,0]+=1
        elif mode=="pair":arrays["signed_pair_consistency"][0,0]=-.5
        elif mode=="null":arrays["raw_means"][0,0,0]=np.nan
        else:arrays["extra"]=np.array([np.nan])
    rewrite_npz(output,mutate)
    with pytest.raises(ValueError):p.validate(output,reference)


@pytest.mark.parametrize("mode",["digit_id","duplicate_pair","self_pair","wrong_config_member","claim_null","false_status",
                               "source_pin","source_clock","negative_domain","dropped_row","wrong_apex","zero_instead_null"])
def test_identity_schema_and_report_mutations_fail(output,reference,mode):
    if mode in ("digit_id","duplicate_pair","self_pair","wrong_config_member"):
        def change(arrays):
            if mode=="digit_id":arrays["participant_ids"][0]="126"
            elif mode=="duplicate_pair":arrays["pair_participant_ids"][0]=arrays["pair_participant_ids"][1]
            elif mode=="self_pair":arrays["pair_participant_ids"][0,1]=arrays["pair_participant_ids"][0,0]
            else:arrays["configuration_membership"][2,0]=False
        rewrite_npz(output,change)
    elif mode=="claim_null":rewrite_json(output,"results.json",lambda value:value.update(claim_scope=None))
    elif mode=="false_status":rewrite_json(output,"results.json",lambda value:value.update(status="failed"))
    elif mode=="source_pin":rewrite_json(output,"run_metadata.json",lambda value:value.update(source_manifest_sha256="0"*64))
    elif mode=="source_clock":rewrite_json(output,"run_metadata.json",lambda value:value["source_observed"].update(effective_TR_s=1.))
    elif mode=="negative_domain":rewrite_csv(output,"configurations.csv",lambda rows:rows[0].update(between_within="-1"))
    elif mode=="dropped_row":rewrite_csv(output,"parcels.csv",lambda rows:rows.pop())
    elif mode=="wrong_apex":rewrite_csv(output,"configurations.csv",lambda rows:rows[0].update(apex_network="not_a_network"))
    else:rewrite_json(output,"results.json",lambda value:value.update(principal_gradient_identity_robust=0))
    with pytest.raises(ValueError):p.validate(output,reference)


@pytest.mark.parametrize("kind",["empty","dangling","directory"])
def test_late_authoritative_failure_overrides_complete_output(output,reference,kind):
    path=output/"failure_report.json"
    if kind=="empty":path.write_text("")
    elif kind=="directory":path.mkdir()
    else:path.symlink_to(output/"missing")
    with pytest.raises(ValueError,match="failure_report"):p.validate(output,reference)


def test_pilot_reference_cannot_grade_full_outputs(output,reference):
    partial=dict(reference,pilot=True)
    with pytest.raises(ValueError,match="full source"):p.validate(output,partial)


def test_signed_zero_and_negative_pearson_are_legitimate():
    assert r.pearson(np.array([-1.,0,1]),np.array([1.,0,-1]))==pytest.approx(-1., abs=1e-14, rel=0.)
    assert r.pearson(np.array([1.,0,-1]),np.array([1.,-2,1]))==0
    assert r.pearson(np.full(8,.1),np.arange(8.)) is None


def test_exactconstant_variance_zero_without_new_epsilon():
    values=np.column_stack([np.full(100,.1),np.linspace(0,1e-16,100)])
    variances=r.variance_columns(values)
    assert variances[0]==0 and variances[1]>0

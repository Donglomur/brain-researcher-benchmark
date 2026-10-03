"""PR200 authoring-only genuine-output controls, ported from fixed PR190.

Baseline: 4cf8f988b4f5109055455d5781fbfb1bb1157f82. This module is NOT a
production scoring dependency. Actual cases require the explicit environment
opt-in REPAIR_RUN_ACTUAL_CONTROLS=1. Collection without it does not import
private modules, inspect an output, or reconstruct a source.

One freshly authenticated private reconstruction serves all cases. Genuine
/app/output is read-only; each candidate is detached. Scientific tests retain
the original equivalence/certificate/own-replay controls, including explicit
unavailable and nondiscriminating results. The redundant historical-bank
replacement case is removed; no historical numerical artifact is used.
Unexpected failures preserve their owned candidate directory for inspection.
"""
from __future__ import annotations

import copy
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import types

import numpy as np
import pytest

# Root binds these only after reviewing the final installed private closure.
GUARD_SHA = 'dc2f38c307cac2507690de534bed1c7d8e83721e0cf4f9522cbf620e56826523'
BOOTSTRAP_SHA = 'f921d255d10c482d72e89b2d1a0c85726867e9d1386790c5ed4d181e0f4819a2'
FIXTURE_SUPPORT_SHA = '75b72f0cd5d719ac7ca896c931b39bb7767c254f74ecfcbd048800681e964b31'
PRIVATE_ROOT = Path("/tests")
pytestmark = pytest.mark.skipif(
    os.environ.get("REPAIR_RUN_ACTUAL_CONTROLS") != "1",
    reason="authoring-only original gate requires REPAIR_RUN_ACTUAL_CONTROLS=1",
)
a = f = m = r = p = s = None


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _pinned_code(path, digest):
    """Small stdlib bootstrap only; execute exactly the authenticated bytes."""
    assert isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest), "unfrozen authoring pin"
    path = Path(path)
    assert path.is_absolute() and path.parent == PRIVATE_ROOT, "fixed private code location"
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        assert not stat.S_ISLNK(info.st_mode), "private code symlink"
        if part != path:
            assert stat.S_ISDIR(info.st_mode), "private code ancestor"
    before = path.lstat()
    assert stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 1024**2, "bounded private code"
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        assert _identity(os.fstat(stream.fileno())) == _identity(before), "private code open identity"
        raw = stream.read(1024**2 + 1)
        assert _identity(os.fstat(stream.fileno())) == _identity(before), "private code read identity"
    assert _identity(path.lstat()) == _identity(before), "private code path identity"
    assert len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == digest, "private code SHA256"
    return raw


def _module(name, path, raw):
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ""
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def json_write(path, value):
    def encode(item):
        if isinstance(item, Decimal): return float(item)
        raise TypeError(type(item).__name__)
    path.write_text(json.dumps(value, default=encode, allow_nan=False), encoding="utf-8")


def csv_write(path, rows):
    assert rows
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def npz_write(path, arrays):
    with path.open("wb") as stream: np.savez_compressed(stream, **arrays)


def hashes(root):
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in a.REQUIRED}


@pytest.fixture(scope="session")
def native():
    global a, f, m, r, p, s
    assert os.environ.get("REPAIR_RUN_ACTUAL_CONTROLS") == "1", "actual control opt-in"
    # Authenticate all authoring loader bytes before executing any of them.
    paths = {name: PRIVATE_ROOT / filename for name, filename in (
        ("code_guard", "code_guard.py"), ("_pr200_authoring_bootstrap", "grader_bootstrap.py"),
        ("_pr200_authoring_fixture_support", "fixture_support.py"))}
    pins = dict(zip(paths, (GUARD_SHA, BOOTSTRAP_SHA, FIXTURE_SUPPORT_SHA)))
    payloads = {name: _pinned_code(paths[name], digest) for name, digest in pins.items()}
    names = [*paths, "artifact_reader", "gradient_math", "source_numerics",
             "source_reference", "gradient_reporting", "proof_of_work"]
    absent = object()
    previous = {name: sys.modules.get(name, absent) for name in names}
    try:
        guard = _module("code_guard", paths["code_guard"], payloads["code_guard"])
        boot = _module("_pr200_authoring_bootstrap", paths["_pr200_authoring_bootstrap"],
                       payloads["_pr200_authoring_bootstrap"])
        context = boot.load_private()
        modules = context["modules"]
        a, m, r, p, s = (modules[name] for name in (
            "artifact_reader", "gradient_math", "gradient_reporting", "proof_of_work", "source_reference"))
        # This source-only positive shares the declared grader spectral/report
        # machinery. It is not an independent third scientific implementation.
        f = _module("_pr200_authoring_fixture_support", paths["_pr200_authoring_fixture_support"],
                    payloads["_pr200_authoring_fixture_support"])
        documents = context["private_documents"]
        root = guard.disjoint_output(boot.OUTPUT_DIR, boot.DATA_DIR, context["private_dir"],
                                     [*documents.values(), *boot.PUBLIC_DOCUMENTS.values()])
        guard.output_inventory(root, require_files=boot.REQUIRED)
        before = hashes(root)
        artifacts = a.read_artifacts(root)
        originals = {name: (root/name).read_bytes() for name in a.REQUIRED}
        assert {name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()} == before
        reference = s.reconstruct(data_dir=boot.DATA_DIR, method_path=documents["method_path"],
                                  schema_path=documents["schema_path"])
        assert p.validate(root, reference)["status"] == "accepted"
        arrays = p.canonical_arrays(artifacts["gradient_arrays.npz"], reference)
        gradients, gpa = p.certified_coordinates(arrays, reference)
        derived = r.derive(reference, gradients, gpa)
        try:
            yield dict(root=root, artifacts=artifacts, originals=originals, reference=reference,
                       arrays=arrays, gradients=gradients, gpa=gpa, derived=derived)
        finally:
            assert hashes(root) == before, "a native control modified original evidence"
            guard.output_inventory(root, require_files=boot.REQUIRED)
            s.authenticate_source(boot.DATA_DIR)
            guard.recheck(context)
            for name, digest in pins.items():
                assert _pinned_code(paths[name], digest) == payloads[name], "authoring code changed"
    finally:
        for name, old in previous.items():
            if old is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        a = f = m = r = p = s = None


@pytest.fixture
def control_workspace(tmp_path, request):
    # Cleanup is limited to this fixture's fresh child. Pytest records a failed
    # call before fixture teardown, so unexpected failures keep their candidate.
    root = tmp_path / "native-control-owned"
    root.mkdir()
    identity = (root.stat().st_dev, root.stat().st_ino)
    failed_before = request.session.testsfailed
    yield root
    assert root.parent == tmp_path and not root.is_symlink()
    assert (root.stat().st_dev, root.stat().st_ino) == identity
    if request.session.testsfailed > failed_before:
        request.node.user_properties.append(("candidate_preserved", str(root)))
    else:
        shutil.rmtree(root)


def output_copy(native,tmp_path):
    root=tmp_path/"output";root.mkdir()
    for name,payload in native["originals"].items():
        with (root/name).open("xb") as stream:stream.write(payload)
    return root


def unchanged_provenance(root,native):
    for name in ("cohort.csv","parcels.csv","run_metadata.json","findings.md"):
        assert (root/name).read_bytes()==native["originals"][name]


def gap(actual,expected,atol,rtol):
    actual,expected=np.asarray(actual),np.asarray(expected)
    assert actual.shape==expected.shape
    support=np.isnan(actual)!=np.isnan(expected)
    finite=np.isfinite(actual)&np.isfinite(expected)
    delta=np.abs(actual[finite]-expected[finite])
    count=int(support.sum())+int(np.sum(delta>atol+rtol*np.abs(expected[finite])))
    return count,float(delta.max()) if delta.size else 0.


def not_constructed(root,native,record_property,reason):
    record_property("control_status","control_not_constructed_"+reason)
    assert p.validate(root,native["reference"])["status"]=="accepted"


def test_native_baseline(native,record_property):
    assert p.validate(native["root"],native["reference"])["status"]=="accepted"
    record_property("control_status","genuine_native_positive")


def test_native_reconstructed_source_positive(native,control_workspace,record_property):
    # Source-only inputs, no oracle arrays. This shares grader spectral/report
    # replay and fixture emitter, so it is not claimed to be an independent
    # third mathematical implementation.
    root=f.emit(control_workspace/"source-reconstructed",native["reference"])
    result=json.loads((root/"results.json").read_text())
    result["claim_scope"]="Source-only descriptive method control; verifier replay is shared."
    json_write(root/"results.json",result)
    (root/"findings.md").write_text("Source-only reconstruction, not an outcome-direction check.\n")
    assert p.validate(root,native["reference"])["status"]=="accepted"
    record_property("control_status","source_only_positive_shared_verifier_replay")


def test_native_coherent_axes_keys_and_pair_directions(native,control_workspace,record_property):
    root=output_copy(native,control_workspace);arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"])
    permutations={name:np.arange(len(arrays[key]))[::-1] for name,key in (
        ("s","participant_ids"),("t","frame_indices"),("p","parcel_ids"),("a","arm_ids"),
        ("c","configuration_ids"),("e","embedding_ids"),("q","quantity_ids"))}
    layouts={"participant_ids":"s","source_positions":"s","frame_indices":"t","parcel_ids":"p","arm_ids":"a",
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
    for key in ("signed_pair_consistency","pair_consistency_valid"):arrays[key]=arrays[key][::-1]
    for key in ("source_positions","frame_indices","parcel_ids"):arrays[key]=arrays[key].astype(float)
    arrays["participant_ids"]=arrays["participant_ids"].astype("S")
    npz_write(root/"gradient_arrays.npz",arrays)
    for name in ("cohort.csv","parcels.csv","configurations.csv","per_subject.csv"):
        csv_write(root/name,[dict(reversed(list(row.items()))) for row in native["artifacts"][name][::-1]])
    metadata=copy.deepcopy(native["artifacts"]["run_metadata.json"])
    metadata["source_files"].reverse();observed=metadata["source_observed"]
    observed["participant_ids"].reverse();observed["atlas_labels"].reverse()
    for rows in observed["voxel_support_by_subject"].values():rows.reverse()
    json_write(root/"run_metadata.json",metadata)
    results=copy.deepcopy(native["artifacts"]["results.json"]);results["configuration_summaries"].reverse()
    json_write(root/"results.json",results)
    assert p.validate(root,native["reference"])["status"]=="accepted"
    record_property("control_status","equivalent_representation_positive")


def write_derived(root,native,derived):
    arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"])
    # Derived arrays are in canonical order. Canonicalize only those key axes
    # when replacing; the current genuine producer uses canonical axes, while
    # this helper explicitly joins quantity/pair families for reorder safety.
    quantities=arrays["quantity_ids"].astype(str).tolist()
    expected_quantities=derived["arrays"]["quantity_ids"].tolist()
    parcel_order=p.axis(arrays["parcel_ids"],native["reference"]["arrays"]["parcel_ids"].tolist(),"parcel",True)
    inverse_parcel=np.argsort(parcel_order)
    for key in ("display_coordinates","display_signs","display_valid"):
        value=derived["arrays"][key][[expected_quantities.index(q) for q in quantities]]
        if key=="display_coordinates":value=value[:,inverse_parcel]
        arrays[key]=value
    expected_pairs={frozenset(row):i for i,row in enumerate(derived["arrays"]["pair_participant_ids"].tolist())}
    pair_order=[expected_pairs[frozenset(row)] for row in arrays["pair_participant_ids"].astype(str).tolist()]
    for key in ("signed_pair_consistency","pair_consistency_valid"):arrays[key]=derived["arrays"][key][pair_order]
    npz_write(root/"gradient_arrays.npz",arrays)
    csv_write(root/"configurations.csv",derived["configurations"])
    csv_write(root/"per_subject.csv",derived["per_subject"])
    result=copy.deepcopy(derived["results"]);result["claim_scope"]=native["artifacts"]["results.json"]["claim_scope"]
    json_write(root/"results.json",result)


def test_native_six_decimal_derived_serialization(native,control_workspace,record_property):
    root=output_copy(native,control_workspace);derived=copy.deepcopy(native["derived"])
    def rounded(value):
        if isinstance(value,float):return round(value,6)
        if isinstance(value,list):return [rounded(x) for x in value]
        if isinstance(value,dict):return {key:rounded(x) for key,x in value.items()}
        return value
    derived["configurations"]=rounded(derived["configurations"])
    derived["per_subject"]=rounded(derived["per_subject"])
    derived["results"]=rounded(derived["results"])
    write_derived(root,native,derived)
    assert p.validate(root,native["reference"])["status"]=="accepted"
    record_property("control_status","equivalent_six_decimal_positive")


def test_native_float32_source_receipts_when_representable(native,control_workspace,record_property):
    root=output_copy(native,control_workspace);arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"])
    with np.errstate(over="ignore",invalid="ignore"):
        for key in ("raw_means","cleaned_series"):arrays[key]=arrays[key].astype(np.float32)
    canonical=p.canonical_arrays(arrays,native["reference"])
    count=0
    for key,tol in (("raw_means",(1e-5,1e-7)),("cleaned_series",(1e-6,1e-6))):
        count+=gap(canonical[key],native["reference"]["arrays"][key],*tol)[0]
        if np.isinf(canonical[key]).any():count+=1
    if count:
        not_constructed(root,native,record_property,"float32_outside_public_source_precision");return
    npz_write(root/"gradient_arrays.npz",arrays)
    assert p.validate(root,native["reference"])["status"]=="accepted"
    record_property("control_status","equivalent_float32_receipts_positive")


def test_native_harmless_extras_and_nonprescribed_findings(native,control_workspace,record_property):
    root=output_copy(native,control_workspace)
    arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"]);arrays["finite_extra"]=np.zeros((1,1,1,1))
    npz_write(root/"gradient_arrays.npz",arrays)
    metadata=copy.deepcopy(native["artifacts"]["run_metadata.json"]);metadata["description"]="No inferred causal or population effect."
    json_write(root/"run_metadata.json",metadata)
    (root/"findings.md").write_text("Observed apex, signed consistency and undefined support may take any valid values.")
    npz_write(root/"optional_arrays.npz",dict(untrusted=np.array([123.])))
    assert p.validate(root,native["reference"])["status"]=="accepted"
    record_property("control_status","harmless_extras_positive")


@pytest.mark.parametrize("mode",["raw_changed","clean_arms_swapped","absolute_fc","group_half_substitution",
                               "undefined_fc_zero_fill"])
def test_native_source_component_binding(native,control_workspace,record_property,mode):
    root=output_copy(native,control_workspace);arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"])
    if mode == "raw_changed":
        key="raw_means";tol=(1e-5,1e-7)
        finite=np.argwhere(np.isfinite(arrays[key]))
        if not len(finite):not_constructed(root,native,record_property,"no_raw_geometry");return
        index=tuple(finite[0]);old=float(arrays[key][index])
        arrays[key]=arrays[key].astype(float);arrays[key][index]=old+1+abs(old)
    elif mode=="clean_arms_swapped":
        key="cleaned_series";tol=(1e-6,1e-6);arrays[key]=arrays[key][:,::-1].copy()
    elif mode=="absolute_fc":
        key="fc";tol=(1e-8,1e-7);arrays[key]=np.abs(arrays[key])
    elif mode=="undefined_fc_zero_fill":
        key="fc";tol=(1e-8,1e-7)
        if not np.isnan(arrays[key]).any():not_constructed(root,native,record_property,"all_FC_defined");return
        arrays[key][np.isnan(arrays[key])]=0.
    else:
        key="configuration_fc";tol=(1e-8,1e-7);ids=arrays["configuration_ids"].astype(str).tolist()
        arrays[key][ids.index("nobp_firstHalf")]=arrays[key][ids.index("nobp_secondHalf")]
    canonical=p.canonical_arrays(arrays,native["reference"])
    count,maximum=gap(canonical[key],native["reference"]["arrays"][key],*tol)
    support_count=int(np.count_nonzero(np.isnan(canonical[key]) != np.isnan(native["reference"]["arrays"][key])))
    numeric_count=count-support_count
    record_property("changed_source_cells",count);record_property("max_source_absolute_difference",maximum)
    record_property("numeric_effect_count",numeric_count);record_property("support_effect_count",support_count)
    npz_write(root/"gradient_arrays.npz",arrays);unchanged_provenance(root,native)
    if not count:
        assert p.validate(root,native["reference"])["status"]=="accepted"
        record_property("control_status","control_not_discriminating_within_source_precision");return
    with pytest.raises(ValueError,match="source/replay mismatch|undefined mask"):p.source_receipts(canonical,native["reference"])
    with pytest.raises(ValueError,match="source/replay mismatch|undefined mask"):p.validate(root,native["reference"])
    record_property("control_status", "effective_source_numerical_rejection" if numeric_count else
                    "effective_source_support_mask_rejection")


@pytest.mark.parametrize("mode",["wrong_lambda","scaled_U","wrong_markov_normalization","raw_sign",
                               "nonorthogonal_rotation","false_history","undefined_embedding_zero_fill",
                               "undefined_aligned_zero_fill"])
def test_native_spectral_alignment_certificates(native,control_workspace,record_property,mode):
    root=output_copy(native,control_workspace);arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"])
    canonical=native["arrays"];valid=np.flatnonzero(canonical["operator_valid"])
    reason="eigenvalue receipt|orthonormality|raw diffusion-coordinate sign|rotation orthogonality|recurrence receipt|undefined mask"
    if mode in ("undefined_embedding_zero_fill","undefined_aligned_zero_fill"):
        key="raw_diffusion" if mode=="undefined_embedding_zero_fill" else "aligned_gradients"
        missing=np.isnan(arrays[key])
        if not missing.any():not_constructed(root,native,record_property,"selected_coordinates_all_defined");return
        arrays[key][missing]=0.;violation=int(missing.sum())
        assert violation>0
        record_property("certificate_kind","undefined_support_mask")
    elif mode in ("nonorthogonal_rotation","false_history"):
        record_property("certificate_kind","GPA")
        if native["gpa"] is None:not_constructed(root,native,record_property,"GPA_undefined");return
        if mode=="nonorthogonal_rotation":
            arrays["gpa_rotations"][0,0]*=2
            violation=float(np.max(np.abs(arrays["gpa_rotations"][0,0].T@arrays["gpa_rotations"][0,0]-np.eye(10))))
            assert violation>m.GRAM_ATOL
        else:
            arrays["gpa_reference_history"][1,0,0]+=1+abs(arrays["gpa_reference_history"][1,0,0])
            violation=float(abs(arrays["gpa_reference_history"][1,0,0]-native["artifacts"]["gradient_arrays.npz"]["gpa_reference_history"][1,0,0]))
            assert violation>1e-6
    else:
        record_property("certificate_kind","spectrum")
        if not len(valid):not_constructed(root,native,record_property,"all_source_operators_undefined");return
        index=int(valid[0]);embedding=native["reference"]["arrays"]["embedding_ids"][index]
        supplied=arrays["embedding_ids"].astype(str).tolist().index(embedding)
        if mode=="wrong_lambda":
            old=arrays["eigenvalues"][supplied,0]
            arrays["eigenvalues"][supplied,0]+=.001 if old<.999 else -.001
            violation=float(abs(arrays["eigenvalues"][supplied,0]-old));assert violation>m.EIGEN_ATOL
        elif mode in ("scaled_U","wrong_markov_normalization"):
            if mode=="scaled_U":arrays["eigenvectors"][supplied]*=2
            else:
                # Actual Markov-space psi=U/u0, incorrectly supplied as the
                # Euclidean-orthonormal symmetric-conjugate eigenvectors.
                canonical_order=p.axis(arrays["parcel_ids"],native["reference"]["arrays"]["parcel_ids"].tolist(),"parcel",True)
                serialized_u0=native["reference"]["source_bases"][index]["u0"][np.argsort(canonical_order)]
                arrays["eigenvectors"][supplied]/=serialized_u0[:,None]
            gram=arrays["eigenvectors"][supplied].T@arrays["eigenvectors"][supplied]
            violation=float(np.max(np.abs(gram-np.eye(10))));assert violation>m.GRAM_ATOL
        else:
            choices=[(i,c) for i,g in enumerate(native["gradients"]) if g is not None
                     for c in range(g.shape[1]) if np.max(np.abs(g[:,c]))>0]
            if not choices:not_constructed(root,native,record_property,"all_diffusion_coordinates_zero_or_undefined");return
            index,column=choices[0];embedding=native["reference"]["arrays"]["embedding_ids"][index]
            supplied=arrays["embedding_ids"].astype(str).tolist().index(embedding)
            arrays["eigenvectors"][supplied,:,column]*=-1;arrays["raw_diffusion"][supplied,:,column]*=-1
            wrong=-native["gradients"][index][:,column]
            ids=native["reference"]["arrays"]["parcel_ids"]
            tied=np.flatnonzero(np.abs(wrong)==np.max(np.abs(wrong)));anchor=tied[np.argmin(ids[tied])]
            assert wrong[anchor]<0;violation=float(abs(wrong[anchor]))
    record_property("certificate_violation",violation)
    npz_write(root/"gradient_arrays.npz",arrays);unchanged_provenance(root,native)
    mutated=p.canonical_arrays(arrays,native["reference"])
    with pytest.raises(ValueError,match=reason):p.certified_coordinates(mutated,native["reference"])
    with pytest.raises(ValueError,match=reason):p.validate(root,native["reference"])
    record_property("control_status","effective_spectral_or_GPA_certificate_rejection")


def scalar_cells(derived):
    cells={}
    for pair,values in zip(derived["arrays"]["pair_participant_ids"],derived["arrays"]["signed_pair_consistency"]):
        for arm,value in enumerate(values):
            cells[("pair",*pair,arm)]=float(value) if np.isfinite(value) else None
    for row in derived["per_subject"]:
        for key in ("unaligned_signed","aligned_signed"):cells[("person",row["participant_id"],key)]=row[key]
    for row in derived["configurations"]:
        for key in [f"mean_g{i}" for i in range(1,11)]+["between_within"]:
            cells[("quantity",row["quantity"],row["network"],key)]=row[key]
    for key in ("unaligned_signed","aligned_signed"):cells[("aggregate",key)]=derived["results"][key]["value"]
    return cells


def component_candidate(native,mode):
    derived=copy.deepcopy(native["derived"]);people=native["reference"]["arrays"]["participant_ids"].tolist()
    pair_ids=derived["arrays"]["pair_participant_ids"];values=derived["arrays"]["signed_pair_consistency"]
    valid=derived["arrays"]["pair_consistency_valid"]
    if mode=="pooled_network_means":
        quantities=derived["arrays"]["quantity_ids"].tolist()
        for row in derived["configurations"]:
            coords=derived["arrays"]["display_coordinates"][quantities.index(row["quantity"])]
            for component in range(coords.shape[1]):
                if np.isfinite(coords[:,component]).all():row[f"mean_g{component+1}"]=float(np.mean(coords[:,component]))
        return derived
    if mode=="absolute_signed_consistency":values[valid]=np.abs(values[valid])
    for person,row in zip(people,derived["per_subject"]):
        selected=np.any(pair_ids==person,axis=1)
        for arm,name in enumerate(("unaligned_signed","aligned_signed")):
            if not valid[selected,arm].all():continue
            vals=values[selected,arm]
            if mode=="self_pair_inclusion":vals=np.r_[vals,1.]
            elif mode=="dropped_partner":vals=vals[1:]
            row[name]=float(np.mean(vals))
    for arm,name in enumerate(("unaligned_signed","aligned_signed")):
        if valid[:,arm].all():
            derived["results"][name]["value"]=(float(np.mean(values[:,arm])) if mode=="absolute_signed_consistency"
                else float(np.mean([row[name] for row in derived["per_subject"]])))
    return derived


@pytest.mark.parametrize("mode",["absolute_signed_consistency","self_pair_inclusion","dropped_partner","pooled_network_means"])
def test_native_complete_pair_arithmetic_controls(native,control_workspace,record_property,mode):
    root=output_copy(native,control_workspace);candidate=component_candidate(native,mode)
    old,new=scalar_cells(native["derived"]),scalar_cells(candidate)
    changed=[];maximum=0.
    for key,expected in old.items():
        actual=new[key]
        if expected is None or actual is None:
            if expected is not actual:changed.append(key)
        else:
            difference=abs(actual-expected);maximum=max(maximum,difference)
            if difference>1e-6+1e-6*abs(expected):changed.append(key)
    record_property("changed_report_observables",len(changed));record_property("max_report_absolute_difference",maximum)
    write_derived(root,native,candidate);unchanged_provenance(root,native)
    if changed:
        key=changed[0]
        with pytest.raises(ValueError,match="numeric mismatch|null required"):
            p.match(new[key],old[key],"native arithmetic component")
        with pytest.raises(ValueError,match="source/replay mismatch|numeric mismatch|null required"):
            p.validate(root,native["reference"])
        record_property("control_status","effective_derived_arithmetic_rejection")
    else:
        assert p.validate(root,native["reference"])["status"]=="accepted"
        record_property("control_status","control_not_discriminating_undefined_or_within_scalar_precision")


@pytest.mark.parametrize("mode",["digit_id","duplicate_pair","self_pair","drop_configuration","wrong_membership",
                               "source_hash","source_clock","failure_empty","failure_dangling","nonfinite_extra"])
def test_native_identity_provenance_and_failure_guards(native,control_workspace,record_property,mode):
    root=output_copy(native,control_workspace)
    if mode in ("digit_id","duplicate_pair","self_pair","wrong_membership","nonfinite_extra"):
        arrays=copy.deepcopy(native["artifacts"]["gradient_arrays.npz"])
        if mode=="digit_id":
            old=str(arrays["participant_ids"][0]);arrays["participant_ids"][0]=old.removeprefix("sub-pixar")
            assert arrays["participant_ids"][0]!=old
        elif mode=="duplicate_pair":arrays["pair_participant_ids"][0]=arrays["pair_participant_ids"][1]
        elif mode=="self_pair":arrays["pair_participant_ids"][0,1]=arrays["pair_participant_ids"][0,0]
        elif mode=="wrong_membership":arrays["configuration_membership"][0,0]=~arrays["configuration_membership"][0,0]
        else:arrays["extra"]=np.array([np.inf])
        npz_write(root/"gradient_arrays.npz",arrays)
    elif mode=="drop_configuration":
        rows=copy.deepcopy(native["artifacts"]["configurations.csv"]);deleted=rows.pop()
        assert len(rows)+1==len(native["artifacts"]["configurations.csv"]) and deleted
        csv_write(root/"configurations.csv",rows)
    elif mode in ("source_hash","source_clock"):
        metadata=copy.deepcopy(native["artifacts"]["run_metadata.json"])
        if mode=="source_hash":
            old=metadata["source_manifest_sha256"];metadata["source_manifest_sha256"]="0"*64
            assert metadata["source_manifest_sha256"]!=old
        else:
            observed=metadata["source_observed"];old=float(observed["effective_TR_s"])
            observed["effective_TR_s"]=old+1;assert observed["effective_TR_s"]!=old
        json_write(root/"run_metadata.json",metadata)
    elif mode=="failure_empty":(root/"failure_report.json").write_text("")
    else:(root/"failure_report.json").symlink_to(root/"nonexistent")
    with pytest.raises(ValueError):p.validate(root,native["reference"])
    record_property("control_status","effective_identity_or_failure_rejection")

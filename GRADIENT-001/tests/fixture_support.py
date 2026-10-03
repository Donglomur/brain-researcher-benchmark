"""Manufactured private bases for composition tests, NEVER a source bank.

The synthetic operator is a controlled analytic affinity, not a claim that the
placeholder receipt arrays reconstruct it. Source reconstruction has separate
manufactured tests and original execution is separately gated. Production has
no API accepting these private fixtures from a participant.
"""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import numpy as np
from scipy import fft, linalg

import gradient_math as m
import gradient_reporting as r


def manufactured_reference(undefined=False):
    root = Path(__file__).resolve().parents[1]
    method = json.loads((root / "environment/method_contract.json").read_text())
    schema = json.loads((root / "environment/output_schema.json").read_text())
    people = method["source"]["participant_ids"]; n, t, p, k = 20, 168, 400, 10
    networks = np.asarray([method["source"]["networks"][i % 7] for i in range(p)])
    membership = np.zeros((4, n), bool)
    for i, conf in enumerate(method["configurations"]): membership[i, conf["positions"]] = True
    configs = [c["id"] for c in method["configurations"]]
    arrays = dict(participant_ids=np.asarray(people), source_positions=np.arange(n), frame_indices=np.arange(t),
                  parcel_ids=np.arange(1, p + 1), arm_ids=np.asarray(["nobp", "bp"]), configuration_ids=np.asarray(configs),
                  configuration_membership=membership, raw_means=np.zeros((n, t, p)),
                  geometry_valid=np.ones((n, p), bool), cleaned_series=np.zeros((n, 2, t, p)),
                  raw_sample_sd=np.zeros((n, p)), clean_centered_l2=np.zeros((n, 2, p)), activity_threshold=np.full((n, p), 1e-12 * np.sqrt(t)),
                  person_parcel_active=np.full((n, 2, p), not undefined, bool),
                  fc=np.full((n, 2, p, p), np.nan if undefined else 0.),
                  configuration_fc=np.full((4, p, p), np.nan if undefined else 0.),
                  configuration_parcel_active=np.full((4, p), not undefined, bool),
                  embedding_ids=np.asarray(["subject:" + x for x in people] + ["configuration:" + x for x in configs]))
    # Explicit small nontrivial spectrum, simple stationary mode, all entries
    # positive. No empirical/source outcomes determine this fixture.
    q = fft.dct(np.eye(p), type=2, norm="ortho", axis=0).T
    lam = np.r_[1., np.linspace(.02, .001, 11), np.zeros(p - 12)]
    affinity = (q * lam) @ q.T
    basis = None if undefined else m.operator_basis(affinity, np.arange(1, p + 1), k)
    cohorts, parcels = [], []
    headers = {}; supports = {}
    labels = [dict(parcel_id=j + 1, label=f"synthetic_{j+1}", network=networks[j]) for j in range(p)]
    for i, person in enumerate(people):
        cohorts.append(dict(participant_id=person, source_position=i, phenotype_row_index=i,
                            age=5., child_adult="manufactured", bold_path=person+".nii", confounds_path=person+".tsv",
                            n_frames=t, first_half=i < 10, second_half=i >= 10))
        supports[person] = [dict(parcel_id=j+1, n_voxels=1, support_sha256="1"*64) for j in range(p)]
        for label in labels: parcels.append(dict(participant_id=person, **label, n_voxels=1, support_sha256="1"*64, geometry_status="ok"))
        headers[person] = dict(shape=[1, 1, p, t], affine=np.eye(4).tolist(), source_dtype="<f4", spatial_units="unknown",
                               temporal_units="unknown", raw_TR=1., raw_toffset=0., effective_scaling_slope=1., effective_scaling_intercept=0.)
    atlas_header = {key: value for key, value in headers[people[0]].items() if key not in ("temporal_units", "raw_TR", "raw_toffset")}
    atlas_header["shape"] = [1, 1, p]
    observed = dict(participant_ids=people, source_order=people, participant_column_names=["participant_id","Age","Child_Adult"],
                    confound_column_names={x:["manufactured"] for x in people}, headers=headers, atlas_header=atlas_header,
                    atlas_labels=labels, voxel_support_by_subject=supports,
                    frame_alignment="released_frame_index_only_no_measured_movie_onset",
                    raw_clock_metadata={x:dict(raw_TR=1.,raw_toffset=0.,temporal_units="unknown") for x in people},
                    effective_TR_s=2., effective_origin_s=0.)
    metadata = dict(schema_version="gradient-metadata-v2", status="ok", task_id="GRADIENT-001",
                    source_manifest_sha256="1"*64, method_sha256="2"*64, output_schema_sha256="3"*64,
                    source_files=[dict(path="manufactured", role="provenance", participant_id=None, size_bytes=1, sha256="1"*64)],
                    source_observed=observed, software_versions={x:"not_used" for x in ("python","numpy","scipy","nibabel","nilearn","brainspace")})
    return dict(method=method,schema=schema,metadata=metadata,cohort=cohorts,parcels=parcels,arrays=arrays,
                source_bases=[basis]*(n+4),nuisance_ranks={x:0 for x in people},networks=networks,pilot=False)


def certificate(reference):
    a = reference["arrays"]; n, p, k = len(a["participant_ids"]),len(a["parcel_ids"]),reference["method"]["diffusion"]["n_components"]
    bases = reference["source_bases"]; gradients=[]
    vectors=np.full((len(bases),p,k),np.nan); eigenvalues=np.full((len(bases),k+1),np.nan)
    for i,basis in enumerate(bases):
        if basis is None: gradients.append(None); continue
        vectors[i],g = m.orient(basis["proposal_vectors"],basis); gradients.append(g)
        eigenvalues[i] = basis["spectral_eigenvalues"]
    gpa = None
    if all(b is not None and b["gpa_eligible"] for b in bases[:n+1]):
        data=np.stack(gradients[:n]); prior=gradients[n]; history=[prior]; rotations=[]; distances=[]; previous=None
        for _ in range(10):
            step=np.stack([linalg.orthogonal_procrustes(person,prior)[0] for person in data])
            aligned=np.stack([person@rotation for person,rotation in zip(data,step)])
            current=np.mean(aligned,axis=0); distance=float(np.sum((prior-current)**2))
            rotations.append(step);history.append(current);distances.append(distance)
            if previous is not None and abs(distance-previous)<1e-5:break
            prior,previous=current,distance
        gpa=m.validate_gpa_history(data,gradients[n],np.stack(rotations),np.stack(history),np.asarray(distances),len(rotations),aligned)
        gpa["rotations"]=np.stack(rotations)
    statuses=[r.embedding_status(b,g) for b,g in zip(bases,gradients)]
    out=copy.deepcopy(a)
    out.update(operator_valid=np.asarray([b is not None for b in bases]),embedding_valid=np.asarray([g is not None for g in gradients]),
               principal_valid=np.asarray([x[1]=="ok" for x in statuses]),retained_span_valid=np.asarray([x[2]=="ok" for x in statuses]),
               eigenvalues=eigenvalues,eigenvectors=vectors,
               raw_diffusion=np.stack([np.full((p,k),np.nan) if g is None else g for g in gradients]),
               gpa_n_iterations=np.asarray(0 if gpa is None else gpa["n_iterations"]),
               gpa_rotations=np.empty((0,n,k,k)) if gpa is None else gpa["rotations"],
               gpa_reference_history=np.empty((0,p,k)) if gpa is None else gpa["reference_history"],
               gpa_distances=np.empty(0) if gpa is None else gpa["distances"])
    derived=r.derive(reference,gradients,gpa); out.update(derived["arrays"])
    return out,derived


def emit(output, reference):
    output=Path(output);output.mkdir()
    arrays,derived=certificate(reference)
    for name,rows in (("cohort.csv",reference["cohort"]),("parcels.csv",reference["parcels"]),
                      ("configurations.csv",derived["configurations"]),("per_subject.csv",derived["per_subject"])):
        with (output/name).open("x",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (output/"gradient_arrays.npz").open("xb") as handle:np.savez_compressed(handle,**arrays)
    results=derived["results"];results["claim_scope"]="Manufactured example; no scientific claim."
    metadata=copy.deepcopy(reference["metadata"]);metadata.update(warnings=[],numerical_method_amendments="Public corrected symmetric operator and explicit source recipe.")
    for name,value in (("results.json",results),("run_metadata.json",metadata)):
        (output/name).write_text(json.dumps(value,allow_nan=False))
    (output/"findings.md").write_text("Any observed direction or undefined support is legitimate.")
    return output

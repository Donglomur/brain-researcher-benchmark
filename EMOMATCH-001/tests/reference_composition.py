"""Pure source-basis composition. No source/output reader or execution entrypoint.

Supplied arrays must come from the separately authenticated source reader (or
explicit manufactured fixtures). This module imports no oracle code and never
loads a bank. It shares the public HRF and numerical contract through the grader
module. Original execution still requires a separate parent gate.
"""
import hashlib
import json
import math

import numpy as np

import numerical_contract as n
import artifact_reader as io

MODELS = ("modelA", "modelB")
SPHERES = ("amy_L", "amy_R", "ffa_L", "ffa_R", "dACC", "aIns_L", "aIns_R",
           "dlPFC_L", "dlPFC_R", "IPS_L", "IPS_R")
AGGREGATES = {"amygdala": SPHERES[:2], "fusiform": SPHERES[2:4], "control": SPHERES[4:]}
NETWORKS = ("Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default")
SCHEMA_ID = "EMOMATCH-001-duration-sensitivity-outputs-v2"


def grid_id(header):
    shape = np.asarray(header["shape"][:3], dtype="<i8")
    affine = n.array(header["chosen_affine"], 2).copy()
    n.require(shape.shape == (3,) and np.all(shape > 0) and affine.shape == (4, 4), "grid geometry")
    affine[affine == 0] = 0.0
    return "grid_" + hashlib.sha256(b"EMOMATCH_grid_v1\n" + shape.tobytes() +
                                  affine.astype("<f8").tobytes(order="C") + b"mm\n").hexdigest()


def fmean(values):
    return math.fsum(map(float, values)) / len(values) if len(values) else None


def documentary_duplicates(text, path):
    """Lossless duplicate accounting for unused documentary JSON only."""
    class Pairs(list):
        pass
    root=json.loads(text,object_pairs_hook=Pairs,
                    parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite documentary JSON")))
    def signature(value):
        if isinstance(value,Pairs):
            return ("object",tuple((k,signature(v)) for k,v in value))
        if isinstance(value,list): return ("array",tuple(signature(v) for v in value))
        if isinstance(value,float): n.require(math.isfinite(value),"nonfinite documentary JSON")
        return (type(value).__name__,value)
    rows=[]
    def walk(value):
        if isinstance(value,Pairs):
            groups={}
            for k,v in value:
                groups.setdefault(k,[]).append(v)
                walk(v)
            for k,group in groups.items():
                if len(group)>1:
                    rows.append(dict(path=path,key=k,occurrences=len(group),
                                     identical=all(signature(v)==signature(group[0]) for v in group[1:]),analysis_use=False))
        elif isinstance(value,list):
            for child in value: walk(child)
    signature(root)
    walk(root)
    return rows


def aggregate(values, members):
    chosen = [values[key] for key in members]
    return None if any(value is None for value in chosen) else fmean(chosen)


def endpoints(reference):
    mapping = {key: (key,) for key in SPHERES}
    mapping.update(AGGREGATES)
    for network in NETWORKS:
        mapping[network] = tuple(str(row["label_id"]) for row in reference["primitives"]["atlas"]["lut"]
                                 if row["network"] == network)
        n.require(mapping[network], "complete network family")
    return mapping


def own_groups(reference, contrasts=None, activations=None, rt_records=None):
    """One accepted authority per endpoint. No additional canonical t/p gate."""
    arrays = reference["arrays"]
    ids = arrays["participant_id"].tolist()
    rois = arrays["roi_id"].tolist()
    if contrasts is None:
        contrasts = arrays["contrast_estimate"]
    if activations is None:
        activations = reference["activation"]
    if rt_records is None:
        rt_records = reference["rt_records"]
    act = {row["participant_id"]: row for row in activations}
    rt = {row["participant_id"]: row for row in rt_records}
    n.require(set(act) == set(rt) == set(ids), "complete authority people")
    endpoint_map = endpoints(reference)
    records = []
    for model in MODELS:
        for name, members in endpoint_map.items():
            values = []
            for s, subject in enumerate(ids):
                m = 2*s + MODELS.index(model)
                if name in AGGREGATES:
                    value = act[subject][f"{name}_{model}"]
                else:
                    primitive = {roi: (float(contrasts[m, r]) if arrays["contrast_defined"][m, r] else None)
                                 for r, roi in enumerate(rois)}
                    value = aggregate(primitive, members)
                values.append(value)
            records.append(dict(model=model, endpoint=name, roi_ids=list(members),
                                weights=[1/len(members)]*len(members),
                                statistic=n.complete_summary(values, len(ids))))
    changes = {}
    paired = []
    for name in AGGREGATES:
        changes[name] = [None if act[s][name+"_modelA"] is None or act[s][name+"_modelB"] is None
                         else act[s][name+"_modelB"]-act[s][name+"_modelA"] for s in ids]
        paired.append(dict(endpoint=name+"_B_minus_A",
                           statistic=n.complete_summary(changes[name], len(ids))))
    difference = [None if a is None or c is None else a-c
                  for a, c in zip(changes["amygdala"], changes["control"])]
    paired.append(dict(endpoint="amygdala_change_minus_control_change",
                       statistic=n.complete_summary(difference, len(ids))))
    ordered_rt = [rt[s] for s in ids]
    return dict(schema_id=SCHEMA_ID, status="complete", n_expected=len(ids), models=records,
                paired_changes=paired, rt_summary=dict(per_subject=ordered_rt,
                    emotion=n.complete_summary([row["mean_emotion_s"] for row in ordered_rt], len(ids)),
                    control=n.complete_summary([row["mean_control_s"] for row in ordered_rt], len(ids)),
                    emotion_minus_control=n.complete_summary([row["difference_s"] for row in ordered_rt], len(ids))))


def compile_reference(primitives, method, method_sha256):
    """Compose targets without filesystem access; caller owns production scope."""
    ids, rois = primitives["participant_ids"], primitives["roi_ids"]
    n.require(len(ids) == len(set(ids)) > 0 and len(rois) == len(set(rois)) == 111, "basis identity")
    n.require(rois == [str(i) for i in range(1, 101)] + list(SPHERES), "canonical ROI basis")
    persons = {row["participant_id"]: row for row in primitives["subjects"]}
    n.require(set(persons) == set(ids), "basis people")
    source_rows = {(r["participant_id"], r["role"]): r for r in primitives["source_records"]}
    prepared, columns = [], []
    for subject in ids:
        person = persons[subject]
        raw = n.array(person["raw_roi_mean"], 2)
        n.require(raw.shape[1] == 111 and raw.shape[0] == person["header"]["shape"][3], "source response shape")
        norm = n.normalization(raw)
        cf = n.impute_confounds(person["confound_raw"], person["confound_missing"])
        n.require(person["confound_names"] == list(n.CONFOUNDS), "canonical nuisance axis")
        ev = person["events"]
        duration = n.duration_models(ev["response_time"], ev["response_time_missing"])
        fits = []
        for model in MODELS:
            design = n.design(ev["onsets"], duration[model], ev["conditions"], len(raw), cf["effective"])
            fit = n.fit_svd(design["matrix"], norm["normalized"], design["contrast"],
                            condition_present=design["condition_present"])
            for key in design["column_keys"]:
                if key not in columns:
                    columns.append(key)
            fits.append(dict(model=model, design=design, fit=fit))
        prepared.append(dict(source=person, raw=raw, norm=norm, cf=cf, duration=duration, fits=fits))
    frame_count = sum(len(p["raw"]) for p in prepared)
    size = len(ids)
    arrays = dict(participant_id=np.asarray(ids, dtype="U"), roi_id=np.asarray(rois, dtype="U"),
                  confound_name=np.asarray(n.CONFOUNDS, dtype="U"), column_key=np.asarray(columns, dtype="U"),
                  frame_subject_index=np.concatenate([np.full(len(p["raw"]), s, dtype=np.int64) for s,p in enumerate(prepared)]),
                  source_frame_index=np.concatenate([np.arange(len(p["raw"]), dtype=np.int64) for p in prepared]),
                  frame_time_s=np.concatenate([2.*np.arange(len(p["raw"])) for p in prepared]),
                  roi_mean=np.concatenate([p["raw"] for p in prepared]),
                  roi_raw_mean=np.stack([p["norm"]["mean"] for p in prepared]),
                  roi_raw_sd=np.stack([p["norm"]["sd"] for p in prepared]),
                  normalization_denominator=np.stack([p["norm"]["denominator"] for p in prepared]),
                  roi_normalized=np.concatenate([p["norm"]["normalized"] for p in prepared]),
                  confound_effective=np.concatenate([p["cf"]["effective"] for p in prepared]),
                  confound_was_missing=np.concatenate([p["cf"]["missing"] for p in prepared]),
                  fit_subject_index=np.repeat(np.arange(size, dtype=np.int64), 2),
                  fit_model=np.tile(np.asarray(MODELS, dtype="U"), size),
                  observation_fit_index=np.concatenate([np.full(len(p["raw"]), 2*s+j, dtype=np.int64)
                      for s,p in enumerate(prepared) for j in range(2)]),
                  observation_frame_index=np.concatenate([np.arange(sum(len(q["raw"]) for q in prepared[:s]),
                      sum(len(q["raw"]) for q in prepared[:s+1]), dtype=np.int64)
                      for s in range(size) for _ in range(2)]),
                  design_matrix=np.zeros((2*frame_count, len(columns))),
                  column_present=np.zeros((2*size, len(columns)), dtype=bool),
                  beta=np.zeros((2*size, len(columns), 111)), contrast_vector=np.zeros((2*size, len(columns))),
                  contrast_estimate=np.stack([f["fit"]["contrast_estimate"] for p in prepared for f in p["fits"]]),
                  contrast_defined=np.stack([f["fit"]["contrast_defined"] for p in prepared for f in p["fits"]]),
                  design_rank=np.asarray([f["fit"]["design_rank"] for p in prepared for f in p["fits"]]),
                  residual_df=np.asarray([f["fit"]["residual_df"] for p in prepared for f in p["fits"]]),
                  contrast_estimable=np.asarray([f["fit"]["contrast_estimable"] for p in prepared for f in p["fits"]]),
                  residual_sse=np.stack([f["fit"]["residual_sse"] for p in prepared for f in p["fits"]]))
    fit_records, activation, events, supports, rt_records, duration_records, headers = [], [], [], [], [], [], []
    offset = 0
    for s, (subject, person) in enumerate(zip(ids, prepared)):
        original = person["source"]
        header = original["header"]
        for j, fitted in enumerate(person["fits"]):
            m = 2*s+j
            design, fit = fitted["design"], fitted["fit"]
            ix = [columns.index(key) for key in design["column_keys"]]
            rows = np.arange(offset, offset+len(person["raw"]))
            arrays["design_matrix"][np.ix_(rows, ix)] = design["matrix"]
            arrays["column_present"][m, ix] = True
            arrays["beta"][m, ix] = fit["beta"]
            arrays["contrast_vector"][m, ix] = design["contrast"]
            offset += len(person["raw"])
            fit_records.append(dict(participant_id=subject, model=fitted["model"], status=fit["status"],
                n_observations=len(person["raw"]), n_columns=len(ix), rank=fit["design_rank"],
                residual_df=fit["residual_df"], singular_values=fit["singular_values"].tolist(),
                rank_cutoff=fit["rank_cutoff"], contrast_rowspace_residual=fit["contrast_rowspace_residual"],
                estimability_bound=fit["estimability_bound"],
                n_exact_constant_rois=int(person["norm"]["exact_constant"].sum())))
        row = dict(participant_id=subject)
        for j, model in enumerate(MODELS):
            values = {roi: float(arrays["contrast_estimate"][2*s+j,r]) if arrays["contrast_defined"][2*s+j,r] else None
                      for r,roi in enumerate(rois)}
            for name, members in AGGREGATES.items():
                value = aggregate(values, members)
                row[name+"_"+model] = value
                row[name+"_"+model+"_status"] = "ok" if value is not None else "incomplete_support"
        activation.append(row)
        ev = original["events"]
        good = ~ev["response_time_missing"]
        condition = ev["conditions"]
        means = {name: fmean(ev["response_time"][(condition==name)&good]) for name in ("emotion", "control")}
        rt_records.append(dict(participant_id=subject, n_valid_emotion=int(np.count_nonzero((condition=="emotion")&good)),
            n_valid_control=int(np.count_nonzero((condition=="control")&good)),
            mean_emotion_s=means["emotion"], mean_control_s=means["control"],
            difference_s=None if None in means.values() else means["emotion"]-means["control"]))
        positions = {int(k): j for j,k in enumerate(ev["selected_source_event_row"])}
        for event in ev["ledger"]:
            k = event["source_row_index"]
            tokens, numeric = event["original"], event["numeric"]
            included = event["included_condition"]
            position = positions[k] if included else None
            missing = numeric["response_time"]["status"] == "missing"
            b = float(person["duration"]["modelB"][position]) if included else None
            events.append(dict(participant_id=subject, source_event_row=k,
                trial_type_token=tokens["trial_type"], onset_token=tokens["onset"], duration_token=tokens["duration"],
                rt_token=tokens["response_time"], onset_s=numeric["onset"]["value"],
                source_duration_s=numeric["duration"]["value"], response_time_s=numeric["response_time"]["value"],
                included=included, inclusion_reason="included_target" if included else "unsupported_trial_type",
                rt_status="not_target" if not included else "missing" if missing else "valid",
                modelA_duration_s=person["duration"]["median"] if included else None,
                modelB_duration_s=b, modelB_imputed=bool(included and missing),
                source_duration_minus_rt_s=numeric["duration"]["value"]-numeric["response_time"]["value"]
                    if included and not missing else None,
                source_duration_minus_modelB_s=numeric["duration"]["value"]-b if included else None))
        current = [r for r in events if r["participant_id"] == subject and r["included"]]
        validdiff = [r["source_duration_minus_rt_s"] for r in current if r["source_duration_minus_rt_s"] is not None]
        imputeddiff = [r["source_duration_minus_modelB_s"] for r in current if r["modelB_imputed"]]
        duration_records.append(dict(participant_id=subject, n_target_with_source_duration=len(current),
            n_valid_rt_and_duration=len(validdiff), n_imputed_rt_and_duration=len(imputeddiff),
            n_exact_source_duration_rt_differences=sum(v != 0. for v in validdiff),
            max_abs_source_duration_minus_rt_s=max(map(abs,validdiff)) if validdiff else None,
            max_abs_source_duration_minus_imputed_modelB_s=max(map(abs,imputeddiff)) if imputeddiff else None))
        gid = grid_id(header)
        lut = {str(r["label_id"]):r for r in primitives["atlas"]["lut"]}
        for support in original["supports"]:
            key = support["roi_id"]
            parcel = key in lut
            xyz = [None]*3 if parcel else method["spatial"]["spheres"][key]
            supports.append(dict(participant_id=subject, roi_id=key, family="parcel" if parcel else "sphere",
                label_name=lut[key]["name"] if parcel else key, network=lut[key]["network"] if parcel else None,
                atlas_label=int(key) if parcel else None, center_x=xyz[0], center_y=xyz[1], center_z=xyz[2],
                radius=None if parcel else 6., grid_id=gid, n_voxels=support["n_voxels"],
                support_sha256=support["support_sha256"], support_status="ok"))
        headers.append(dict(participant_id=subject, bold_shape=header["shape"], affine=header["chosen_affine"],
            spatial_units=header["spatial_unit"], temporal_units=header["temporal_unit"],
            header_TR=header["header_tr_raw"], effective_TR_s=2., effective_origin_s=0.,
            scaling_slope=header["effective_slope"], scaling_intercept=header["effective_intercept"],
            qform_code=header["qform_code"], sform_code=header["sform_code"], source_dtype=header["dtype"],
            n_confound_rows=len(person["raw"]), grid_id=gid,
            **{key:header[key] for key in ("raw_scaling_slope", "raw_scaling_intercept", "raw_scaling_nonfinite",
                                          "header_toffset_raw", "header_toffset_nonfinite")}))
    byperson = {p["source"]["participant_id"]:p for p in prepared}
    cohort = []
    for original in primitives["cohort_rows"]:
        subject = original["participant_id"]
        selected = subject in ids
        row = dict(source_row=original["source_row"], participant_id=subject, selected=selected,
                   selection_reason="selected_fixed_cohort" if selected else "not_in_fixed_cohort",
                   source_status="ok" if selected else "not_selected")
        for role in ("bold", "confounds", "events"):
            row[role+"_path"] = source_rows[subject,role]["path"] if selected else None
        for name in ("n_frames", "n_emotion", "n_control", "n_valid_rt_emotion", "n_valid_rt_control",
                     "n_missing_rt_emotion", "n_missing_rt_control", "median_rt_s"):
            row[name] = None
        if selected:
            p = byperson[subject]
            row.update(n_frames=len(p["raw"]), median_rt_s=p["duration"]["median"])
            for condition in ("emotion", "control"):
                chosen = p["source"]["events"]["conditions"] == condition
                missing = p["source"]["events"]["response_time_missing"]
                row["n_"+condition] = int(chosen.sum())
                row["n_valid_rt_"+condition] = int(np.count_nonzero(chosen & ~missing))
                row["n_missing_rt_"+condition] = int(np.count_nonzero(chosen & missing))
        cohort.append(row)
    atlas = primitives["atlas"]
    metadata = dict(schema_id=SCHEMA_ID, task_id="EMOMATCH-001", status="complete",
        source_manifest_sha256=primitives["source_proof"]["manifest_sha256"],
        method_contract_sha256=method_sha256, method=method, selected_participant_ids=list(ids),
        source_files=[{k:r[k] for k in ("path","role","participant_id","size_bytes","sha256")}
                      for r in primitives["source_records"]], fits=fit_records,
        source_observed=dict(participants=headers,
            atlas=dict(image_path=source_rows[None,"atlas_image"]["path"], labels_path=source_rows[None,"atlas_labels"]["path"],
                template_name="MNI152NLin2009cAsym", shape=atlas["header"]["shape"], affine=atlas["header"]["chosen_affine"],
                label_ids=list(range(1,101)), network_names=list(NETWORKS), spatial_units=atlas["header"]["spatial_unit"]),
            event_column_names={s:persons[s]["event_column_names"] for s in ids},
            confound_column_names={s:persons[s]["confound_column_names"] for s in ids},
            duration_rt_comparison=duration_records,
            documented_timing=dict(task_bold_path=source_rows[None,"task_bold_json"]["path"],
                raw_bold_paths={s:source_rows[s,"raw_bold_json"]["path"] for s in ids},
                preproc_bold_paths={s:source_rows[s,"preproc_bold_json"]["path"] for s in ids},
                scanner_discarded_volumes={s:persons[s]["sidecars"]["raw_bold_json"]["NumberOfVolumesDiscardedByScanner"] for s in ids},
                inherited_slice_timing_s=primitives["task_timing"]["SliceTiming"],
                frame_origin_s=0., exporter_frame_reference="unknown", additional_discarded_frames=0,
                fmriprep_version_literal=io.parse_json(primitives["source_documents"]["derivative_description"].encode())["PipelineDescription"]["Version"]),
            documentary_duplicate_keys=documentary_duplicates(primitives["source_documents"]["participants_schema"],
                                                               source_rows[None,"participants_schema"]["path"])))
    reference = dict(primitives=primitives, arrays=arrays, prepared=prepared, cohort=cohort,
                     events=events, supports=supports, activation=activation, rt_records=rt_records, metadata=metadata)
    reference["groups"] = own_groups(reference)
    return reference

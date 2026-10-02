"""QA-only manufactured complete37 reference and writer; never production imports."""
import csv
import json
from pathlib import Path

import numpy as np
import measurement_kernel as mk
import wave_contract as wc

IDS = [str(i) for i in range(1,41) if i not in (1,5,16)]
CHANNELS = ["FP1","F3","F7","FC3","C3","C5","P3","P7","P9","PO7","PO3","O1","Oz","Pz","CPz",
            "FP2","Fz","F4","F8","FC4","FCz","Cz","C4","C6","P4","P8","P10","PO8","PO4","O2"]
PINS = dict(source_manifest_sha256="3970137c64990f680468baf1d51b89a73a61a748639795541e2c2734777b54cd",
            method_contract_sha256="549cf315f0175ab13c3007703cec298a6cc5080d695aecd9f93f49e98a08ce92",
            output_schema_sha256="fab0dbf2ff1fb60f0596b065ff5f148d9d46da8c89c6e81203dbc346a2070814")
KERNEL_SHA = "bc12162f1496b3f4b83419748ee33905a050331cc815ea7d7a9788e6a6fbba9e"


def manufactured_reference(kind="ordinary"):
    offsets = np.arange(-51,103)
    wave = np.zeros(154)
    wave[(offsets>=25)&(offsets<=35)] = [-1,-2,-3,-4,-6,-8,-6,-4,-3,-2,-1]
    evoked = np.zeros((37,2,154)); defined = np.ones((37,2),bool)
    annotations=[]; trials=[]; keys=[]; ptp=[]; baseline=[]; files=[]; source_persons=[]; analysis=[]
    for index,sid in enumerate(IDS):
        car = np.sin(np.arange(154)/15.)*.2
        car -= np.mean(car[:52])
        diff = wave*(1+index/50.)
        if kind == "zero": diff = np.zeros(154)
        elif kind == "positive": diff = -diff
        elif kind == "constant_amplitude": diff = wave.copy()
        evoked[index] = np.stack([car+diff,car])
        for role in ("set","fdt"):
            files.append(dict(subject_id=sid,role=role,path=f"{sid}_N170_shifted_ds.{role}",
                              size_bytes=100,sha256=f"{2*index+(role=='fdt'):064x}"))
        for event,code in enumerate((0,1,41,2)):
            annotations.append(dict(subject_id=sid,source_event_index=event,type_json=json.dumps(code),
                latency_json=json.dumps(1001+event*500),duration_json="null",urevent_json=json.dumps(event+1),
                normalized_event_code=code,event_role="other" if event==0 else "car" if event==2 else "face"))
            if not event: continue
            condition = "car" if event==2 else "face"
            keep = event in (1,2)
            if kind == "missing_one" and index==0 and condition=="face": keep=False
            if kind == "missing_all": keep=False
            trials.append(dict(subject_id=sid,source_event_index=event,condition=condition,event_sample=1000+event*500,
                epoch_first_sample=949+event*500,epoch_last_sample=1102+event*500,epoch_status="ok",
                accepted=keep,rejection_reason="accepted" if keep else "peak_to_peak"))
            keys.append((sid,event)); values=np.ones(30)*10
            if not keep: values[0]=200
            ptp.append(values); baseline.append(float(index)*.01)
        for j,name in enumerate(("face","car")):
            if not any(r["subject_id"]==sid and r["condition"]==name and r["accepted"] for r in trials):
                defined[index,j]=False;evoked[index,j]=0
        source_persons.append(dict(subject_id=sid,set_path=f"{sid}_N170_shifted_ds.set",fdt_path=f"{sid}_N170_shifted_ds.fdt",
            literal_data_pointer=f"{sid}_N170_shifted_ds.fdt",mat_layout="nested_EEG",
            header_fields=dict(srate=256.0,pnts=4096,nbchan=33,trials=1,xmin=0.0,ref="common"),
            channel_labels=CHANNELS+["HEOG_left","HEOG_right","VEOG_lower"],
            channel_records=[dict(labels=c) for c in CHANNELS+["HEOG_left","HEOG_right","VEOG_lower"]],
            event_fields=["duration","latency","type","urevent"],n_events=4,boundary_event_indices=[],
            boundary_cut_samples=[0,4096],filter_segments=[[0,4096]],fdt_size_bytes=33*4096*4,
            ica_field_shapes={"icaweights":[0,0]}))
        selected=[r for r in trials if r["subject_id"]==sid]
        record=dict(subject_id=sid,condition_defined=defined[index].tolist(),n_eligible_epochs=3,
            rejection_counts={reason:sum(r["rejection_reason"]==reason for r in selected)
                              for reason in ("out_of_bounds","duplicate_target_sample","crosses_boundary","peak_to_peak","accepted")})
        for name in ("face","car"):
            candidates=[r for r in selected if r["condition"]==name]; n=sum(r["accepted"] for r in candidates)
            record.update({f"n_{name}_candidates":len(candidates),f"n_{name}_accepted":n,f"n_{name}_rejected":len(candidates)-n})
        analysis.append(record)
    return dict(status="complete",pins=PINS.copy(),subjects=IDS.copy(),condition_labels=["face","car"],
                sample_offsets=offsets,condition_defined=defined,evoked_po8_uv=evoked,
                rejection_channel_labels=CHANNELS.copy(),epoch_keys=keys,
                epoch_peak_to_peak_uv=np.asarray(ptp),epoch_po8_baseline_uv=np.asarray(baseline),
                annotations=annotations,trials=trials,source_files=files,
                source_observed={"persons":source_persons},analysis_observed={"persons":analysis})


def arrays(reference):
    return dict(subject_ids=np.asarray(reference["subjects"]),condition_labels=np.asarray(["face","car"]),
        sample_offsets=reference["sample_offsets"].copy(),condition_defined=reference["condition_defined"].copy(),
        evoked_po8_uv=reference["evoked_po8_uv"].copy(),rejection_channel_labels=np.asarray(CHANNELS),
        epoch_subject_ids=np.asarray([k[0] for k in reference["epoch_keys"]]),
        epoch_source_event_index=np.asarray([k[1] for k in reference["epoch_keys"]]),
        epoch_peak_to_peak_uv=reference["epoch_peak_to_peak_uv"].copy(),
        epoch_po8_baseline_uv=reference["epoch_po8_baseline_uv"].copy())


def documents(reference, canonical_waves=None):
    """Manufactured writer order is canonical; permutation tests reorder later."""
    waves=reference["evoked_po8_uv"] if canonical_waves is None else canonical_waves
    offsets=reference["sample_offsets"];times=offsets*(1000./256.)
    people=[]
    for i,sid in enumerate(IDS):
        ref={c:reference["evoked_po8_uv"][i,j] if reference["condition_defined"][i,j] else None for j,c in enumerate(("face","car"))}
        got={c:waves[i,j] if reference["condition_defined"][i,j] else None for j,c in enumerate(("face","car"))}
        m=wc.replay_conditions(times,got,ref)["measurement"]
        row={"subject_id":sid}
        counts=reference["analysis_observed"]["persons"][i]
        row.update({k:counts[k] for k in ("n_face_candidates","n_car_candidates","n_face_accepted","n_car_accepted","n_face_rejected","n_car_rejected")})
        row.update(waveform_status="ok" if reference["condition_defined"][i].all() else "missing_condition",
            amp_po8_uv=m["amplitude_uv"],amplitude_status=m["amplitude_status"],
            onset_ms=m["onset_ms"],onset_status=m["onset_status"],measurement_baseline_uv=m["measurement_baseline_uv"],
            peak_selection=m["peak_selection"],peak_sample_offset=None if m["peak_index"] is None else int(offsets[m["peak_index"]]),
            peak_time_ms=m["peak_time_ms"],peak_uv=m["peak_uv"],half_height_uv=m["half_height_uv"],
            crossing_sample_offset=None if m["crossing_index"] is None else int(offsets[m["crossing_index"]]))
        people.append(row)
    summaries=[]
    for key in ("amp_po8_uv","onset_ms"):
        s=mk.aggregate_complete([r[key] for r in people])
        s["missing_subject_ids"]=[IDS[j] for j in s.pop("missing_indices")]
        summaries.append(s)
    a,o=summaries
    result=dict(schema_version="n170-output-v1",n_subjects=37,electrode="PO8",amp_po8_uv=a["mean"],amp_po8_ci95=a["ci95"],
        onset_latency_ms=o["mean"],onset_ci95=o["ci95"],amplitude_summary=a,onset_summary=o)
    meta=dict(schema_version="n170-output-v1",task_id="N170PROFILE-001",status="complete",**PINS,
        measurement_kernel_sha256=KERNEL_SHA,cohort=IDS.copy(),source_files=reference["source_files"],
        source_observed=reference["source_observed"],analysis_observed=reference["analysis_observed"],
        software_versions={"python":"manufactured","numpy":"manufactured","scipy":"manufactured"},warnings=[])
    return people,result,meta


def write_csv(path,rows,fields=None):
    fields=list(rows[0]) if fields is None else fields
    with Path(path).open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({k:("true" if v else "false") if type(v) is bool else "" if v is None else v for k,v in row.items()} for row in rows)


def write_json(path,value):
    Path(path).write_text(json.dumps(value,allow_nan=False,indent=2)+"\n")


def emit(path,reference,canonical_waves=None):
    path=Path(path);path.mkdir()
    a=arrays(reference)
    if canonical_waves is not None:a["evoked_po8_uv"]=canonical_waves.copy()
    people,result,meta=documents(reference,canonical_waves)
    np.savez(path/"erp_evidence.npz",**a)
    write_csv(path/"annotations.csv",reference["annotations"])
    write_csv(path/"trials.csv",reference["trials"])
    write_csv(path/"per_subject.csv",people)
    write_json(path/"n170.json",result);write_json(path/"run_metadata.json",meta)
    (path/"findings.md").write_text("Manufactured descriptive example; no source outcomes.\n")
    return path

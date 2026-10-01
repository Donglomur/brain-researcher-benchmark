"""Explicit shifted_ds adaptation: no ICA and no additional onset low-pass.
This implements a reproducible candidate transform; matching the old bake is NOT assumed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

CHANNELS=["FP1","F3","F7","FC3","C3","C5","P3","P7","P9","PO7","PO3","O1","Oz","Pz","CPz",
          "FP2","Fz","F4","F8","FC4","FCz","Cz","C4","C6","P4","P8","P10","PO8","PO4","O2"]
IDS=[i for i in range(1,41) if i not in (1,5,16)]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-index",required=True,type=Path,help="JSON: subject->{set: path, fdt: path}; authentic shifted_ds files")
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--compare-bake",type=Path)
    args=p.parse_args()
    assert not args.output.exists(), "refuse to overwrite existing bake"
    provenance=json.loads((Path(__file__).resolve().parents[1]/"solution/data_provenance.json").read_text())
    source=json.loads(args.source_index.read_text())
    assert set(source)==set(map(str,IDS))
    import mne
    records=[];waves=[];times=None;sfreq=None
    for sid in IDS:
        paths={kind:Path(source[str(sid)][kind]).resolve() for kind in ("set","fdt")}
        assert paths["set"].parent==paths["fdt"].parent
        record={"subject":str(sid),"source_stage":"shifted_ds","ica":"not applied"}
        for kind,path in paths.items():
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest==provenance["per_subject"][str(sid)][kind+"_sha256"], "wrong original source bytes"
            record[kind+"_sha256"]=digest
        raw=mne.io.read_raw_eeglab(paths["set"],preload=True,verbose="ERROR")
        assert set(CHANNELS)<=set(raw.ch_names)
        raw.pick(CHANNELS);raw.reorder_channels(CHANNELS)
        raw.set_eeg_reference("average",projection=False,verbose="ERROR")
        raw.filter(.1,30.,method="fir",phase="zero",fir_design="firwin",verbose="ERROR")
        events,_=mne.events_from_annotations(raw,event_id=lambda description:
                                           int(description) if description.isdigit() and 1<=int(description)<=80 else None,
                                           verbose="ERROR")
        face=events[(events[:,2]>=1)&(events[:,2]<=40)].copy()
        car=events[(events[:,2]>=41)&(events[:,2]<=80)].copy()
        face[:,2]=1;car[:,2]=2
        combined=np.vstack([face,car]);combined=combined[np.argsort(combined[:,0],kind="stable")]
        epochs=mne.Epochs(raw,combined,event_id={"face":1,"car":2},tmin=-.2,tmax=.4,
                          baseline=(-.2,0),reject={"eeg":150e-6},preload=True,
                          reject_by_annotation=True,verbose="ERROR")
        assert len(epochs["face"]) and len(epochs["car"])
        wave=(epochs["face"].average().data-epochs["car"].average().data)*1e6
        record.update(n_face=len(epochs["face"]),n_car=len(epochs["car"]),
                      rejected_epoch_indices=np.flatnonzero([bool(d) for d in epochs.drop_log]).tolist())
        if times is None:
            times=epochs.times*1000;sfreq=float(raw.info["sfreq"])
        assert np.allclose(epochs.times*1000,times) and float(raw.info["sfreq"])==sfreq
        waves.append(wave);records.append(record)
    array=np.stack(waves)
    if args.compare_bake:
        previous=np.load(args.compare_bake,allow_pickle=False)
        assert list(previous["subjects"])==list(map(str,IDS))
        assert np.allclose(previous["times_ms"],times,atol=1e-9)
        assert np.allclose(previous["diff_uv"],array,atol=1e-5,rtol=1e-5), "old bake not reproduced: regenerate reference and inspect differences"
    np.savez_compressed(args.output,subjects=np.asarray(list(map(str,IDS))),diff_uv=array,
                        ch_names=np.asarray(CHANNELS),times_ms=times,sfreq=sfreq)
    receipt={"schema_version":"n170-shifted-ds-adaptation-v2","mne_version":mne.__version__,
             "filter":"MNE zero-phase FIR firwin .1–30Hz","reference":"30-scalp average",
             "events":"1–40 faces;41–80cars","baseline_ms":[-200,0],"epoch_ms":[-200,400],
             "rejection_uv_peak_to_peak":150,"units":"microvolts","onset_extra_filter":"none",
             "exclusions":[1,5,16],"subjects":records,
             "bake_sha256":hashlib.sha256(args.output.read_bytes()).hexdigest(),
             "interpretation":"paper-derived adaptation, not paper ICA/onset-filter reproduction"}
    args.output.with_suffix(".provenance.json").write_text(json.dumps(receipt,indent=2))

if __name__=="__main__":
    main()

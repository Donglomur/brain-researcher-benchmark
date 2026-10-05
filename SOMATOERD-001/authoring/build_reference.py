#!/usr/bin/env python3
"""Rebuild only from full original-source execution, with separate convolution.

This authoring program reuses the oracle's verified source reader/MNE epoch
construction, but independently implements discrete Morlet wavelets and uses
SciPy fftconvolve rather than MNE's TFR routine. A separate checker independently
audits trigger/epoch construction. Neither is a new biological ground truth.
Run only under the parent's approved source-processing resource contract.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
from scipy.signal import fftconvolve

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/"tests"))
import proof_of_work as q


def explicit_morlet(sfreq, frequency):
    """MNE1.12.1 convention, implemented without importing MNE TFR functions."""
    cycles=frequency/2
    sigma=cycles/(2*np.pi*frequency)
    positive=np.arange(0.,5*sigma,1./sfreq)
    time=np.concatenate((-positive[::-1],positive[1:]))
    wave=(np.exp(2j*np.pi*frequency*time)-np.exp(-2*(np.pi*frequency*sigma)**2))*np.exp(-time**2/(2*sigma**2))
    wave/=np.sqrt(.5)*np.linalg.norm(wave)
    return np.asarray(wave,dtype=np.complex128)


def independent_powers(epochs, times, sfreq, contract):
    """Bounded frequency-at-a-time convolution; no saved full trial-power tensor."""
    epochs=np.asarray(epochs,dtype=np.float64)
    assert epochs.ndim==3 and epochs.shape[0]>0 and np.isfinite(epochs).all()
    assert epochs.shape[1]==len(contract["channels"]) and epochs.shape[-1]==len(times)
    b,t=q.window_masks(times,contract)
    mean=np.empty((epochs.shape[1],len(contract["frequencies_hz"]),len(times)))
    trial_baseline=np.empty((epochs.shape[0],epochs.shape[1],mean.shape[1]))
    trial_target=np.empty_like(trial_baseline)
    for f,frequency in enumerate(contract["frequencies_hz"]):
        wave=explicit_morlet(sfreq,frequency)
        assert len(wave)<=len(times), "wavelet longer than declared source epoch"
        convolution=fftconvolve(epochs,wave[None,None,:],mode="same",axes=-1)
        power=np.abs(convolution)**2
        assert np.isfinite(power).all()
        mean[:,f,:]=power.mean(axis=0)
        trial_baseline[:,:,f]=power[...,b].mean(axis=-1)
        trial_target[:,:,f]=power[...,t].mean(axis=-1)
    return dict(mean_power=mean,trial_baseline_power=trial_baseline,trial_target_power=trial_target,
                **q.derive(mean,times,contract))


def load_oracle():
    spec=importlib.util.spec_from_file_location("somato_original_oracle",TASK/"solution/compute.py")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def numeric_receipt_matches(receipt, expected, baseline):
    """Validate measured private arrays, including aggregates not needed in public CSV."""
    for key in ("mean_power","trial_baseline_power","trial_target_power"):
        scale=baseline[...,None] if key=="mean_power" else baseline[None,...]
        q.power_close(receipt[key],expected[key],scale,"private "+key)
    for key in ("baseline_power",):
        q.power_close(receipt[key],expected[key],baseline,"private "+key)
    for key in ("percent_power","beta_power_pct","beta_erd_percent"):
        q.close(receipt[key],expected[key],"private "+key)


def build(args):
    oracle=load_oracle()
    inputs=oracle.load_inputs(args.data_dir,args.method_contract)
    prepared=oracle.prepare_epochs(inputs,pilot_trials=None)
    private=Path(args.private_dir or args.output_dir)/"analysis_arrays.npz"
    with np.load(private,allow_pickle=False) as archive:
        receipt={key:archive[key] for key in archive.files}
    assert str(receipt["pipeline_id"].item())==q.PIPELINE_ID, "obsolete private pipeline"
    metadata=json.loads(str(receipt["metadata_json"].item()))
    assert metadata.get("status")=="ok", "resource pilot/failure cannot produce a bank"
    source_events=json.loads(str(receipt["source_events_json"].item()))
    assert source_events==prepared["source_events"], "private event ledger is not the original source"
    for key in ("retained_event_indices","times","sample_offsets"):
        np.testing.assert_array_equal(receipt[key],prepared[key],err_msg="private source "+key)
    np.testing.assert_array_equal(receipt["source_retained_event_indices"],prepared["retained_event_indices"])
    np.testing.assert_array_equal(receipt["selected_epochs"],prepared["selected_epochs"])
    for key in ("source_grad_names","grad_projector"):
        np.testing.assert_array_equal(receipt[key],prepared[key],err_msg="private source "+key)
    expected_metadata=oracle.make_metadata(inputs,prepared)
    q.match_metadata(metadata,expected_metadata,"private source metadata")
    contract=json.loads(Path(args.method_contract).read_text())
    assert metadata["method_contract"]==contract
    np.testing.assert_array_equal(receipt["channels"],contract["channels"])
    np.testing.assert_array_equal(receipt["frequencies_hz"],contract["frequencies_hz"])
    assert hashlib.sha256(Path(args.method_contract).read_bytes()).hexdigest()==metadata["method_contract_sha256"]
    masks=q.window_masks(prepared["times"],contract)
    for key,mask in zip(("baseline_mask","target_mask"),masks):
        np.testing.assert_array_equal(receipt[key],mask,err_msg="private unrounded-time window")
    independent=independent_powers(prepared["selected_epochs"],prepared["times"],metadata["sfreq_hz"],contract)
    numeric_receipt_matches(receipt,independent,independent["baseline_power"])
    reference=dict(channels=np.asarray(contract["channels"]),frequencies=np.asarray(contract["frequencies_hz"],float),
        times=prepared["times"],sample_offsets=prepared["sample_offsets"],retained_event_indices=prepared["retained_event_indices"],
        mean_power=np.asarray(receipt["mean_power"],float),
        trial_baseline_power=np.asarray(receipt["trial_baseline_power"],float),
        trial_target_power=np.asarray(receipt["trial_target_power"],float),source_events=source_events,
        stats=dict(pipeline_id=q.PIPELINE_ID,metadata=metadata,
                   results=json.loads(str(receipt["results_json"].item())),
                   authoring_evidence={"source_epochs_reloaded":True,"power_check":"explicit Morlet + SciPy fftconvolve",
                     "shared_components":"verified original reader and MNE epoch/SSP construction",
                     "private_receipt_sha256":hashlib.sha256(private.read_bytes()).hexdigest()}))
    q.validate_reference(reference)
    q.validate_output_directory(args.output_dir,reference)
    # Numerical differences are allowed only within the predeclared public criteria.
    q.close(reference["derived"]["beta_power_pct"],independent["beta_power_pct"],"independent source curve")
    q.close(reference["derived"]["beta_erd_percent"],independent["beta_erd_percent"],"independent source endpoint")
    bank={"ref_"+key:reference[key] for key in ("channels","frequencies","times","sample_offsets","retained_event_indices",
                                               "mean_power","trial_baseline_power","trial_target_power")}
    bank["ref_source_event_json"]=np.array(json.dumps(source_events,allow_nan=False))
    bank["ref_stats"]=np.array(json.dumps(reference["stats"],allow_nan=False))
    destination=Path(args.reference);destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,prefix=".reference-",suffix=".npz",delete=False) as stream:
            temporary=Path(stream.name)
            np.savez_compressed(stream,**bank)
        q.load_reference(temporary)
        temporary.replace(destination)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()
    print(json.dumps(dict(status="ok",reference=str(destination),reference_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                          n_trials=len(reference["retained_event_indices"]),n_epoch_times=len(reference["times"]),
                          beta_erd_percent=reference["derived"]["beta_erd_percent"]),allow_nan=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=Path("/app/data/somato"))
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--private-dir",type=Path)
    parser.add_argument("--method-contract",type=Path,default=Path("/app/method_contract.json"))
    parser.add_argument("--reference",type=Path,default=TASK/"tests/reference.npz")
    build(parser.parse_args())


if __name__=="__main__":
    main()

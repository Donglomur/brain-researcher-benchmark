"""Build the immutable-source bank from a genuine full oracle execution.

This authoring-only command rereads authenticated NWB structure/spikes and
recounts all fixed windows. It shares the source reader with the oracle, while
the separately executed histogram checker supplies independent source counting.
It never downloads inputs or uses the obsolete bank as a measurement.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/"tests"))
import proof_of_work as q


def load_oracle():
    spec=importlib.util.spec_from_file_location("allenosi_source_authoring",TASK/"solution/compute.py")
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    return oracle


def same(actual,expected,name):
    actual,expected=np.asarray(actual),np.asarray(expected)
    assert actual.shape==expected.shape, f"{name}: shape mismatch"
    equal=np.array_equal(actual,expected,equal_nan=True) if expected.dtype.kind in "fc" else np.array_equal(actual,expected)
    assert equal, f"{name}: genuine receipt/source mismatch"


def build(data,output,bank,template):
    output=Path(output);oracle=load_oracle()
    inputs=oracle.load_inputs(data);contract=oracle.metadata_contract(inputs)
    assert q.load_json(template)==contract, "public template differs from authenticated source contract"
    assert {key:importlib.metadata.version(key) for key in contract["software"]}==contract["software"], "authoring software differs from pinned versions"
    result,metadata=q.load_json(output/"results.json"),q.load_json(output/"run_metadata.json")
    assert result["status"]==metadata["status"]=="ok", "cannot build bank from pilot/failure"
    assert metadata["include_qc"] is True, "authoring bank requires genuine primary and optional QC receipts"
    source=oracle.read_source(inputs)
    presentations=oracle.presentation_support(source["presentations_raw"])
    oracle.source_condition_checks(source,presentations,include_qc=True)
    starts,stops=presentations["start_time"],presentations["stop_time"]
    assert np.all(starts>=.5), "source baseline windows must lie within recording support"
    counts=np.asarray([q.half_open_counts(train,starts,stops) for train in source["spikes"]],dtype=np.int64)
    baseline=np.asarray([q.half_open_counts(train,starts-.5,starts) for train in source["spikes"]],dtype=np.int64)
    primary=q.derive(counts,starts,stops,presentations["direction"],presentations["temporal_frequency"])
    qc=q.derive_qc(source["qc"],baseline,primary)
    reference={"unit_ids":source["unit_id"],"peak_channel_ids":source["peak_channel_id"],
               "presentation_ids":presentations["presentation_id"],"start_time":starts,"stop_time":stops,
               "direction":presentations["direction"],"temporal_frequency":presentations["temporal_frequency"],
               "spike_counts":counts,"baseline_counts":baseline,**source["qc"],
               "stats":{"pipeline_id":q.PIPELINE_ID,"source_sha256":inputs["source_sha256"],
                        "metadata_contract":contract,"n_units_total":len(source["unit_ids_all"]),
                        "n_original_presentations":presentations["n_original_presentations"],
                        "n_blank_presentations":presentations["n_blank_presentations"],"results":result,
                        "source_spike_times_sha256_le_float64":source["spike_times_sha256_le_float64"],
                        "authoring_evidence":{"all_original_windows_recounted":True,
                            "shared_oracle_source_reader":True,"independent_histogram_checker_required_separately":True}}}
    with np.load(output/"analysis_arrays.npz",allow_pickle=False) as receipt:
        assert json.loads(str(receipt["metadata_json"].item()))==metadata
        assert json.loads(str(receipt["result_json"].item()))==result
        for key in ("unit_id","peak_channel_id","unit_ids_all","unit_regions_all","visp_source_rows"):
            same(receipt[key],source[key],key)
        assert str(receipt["spike_times_sha256_le_float64"].item())==source["spike_times_sha256_le_float64"]
        for key,value in presentations.items():same(receipt[key],value,key)
        same(receipt["spike_count"],counts,"all original grating counts")
        same(receipt["baseline_spike_count"],baseline,"all original baseline counts")
        same(receipt["rate_hz"],primary["rates"],"actual-duration rates")
        same(receipt["mean_rate_hz"],primary["condition_means"],"condition means")
        for key in q.UNIT_FIELDS[2:]:same(receipt[key],primary[key],key)
        for key in q.QC_METRICS:same(receipt["source_"+key],source["qc"][key],"source "+key)
        for key in q.QC_FIELDS[1:]:same(receipt[key],qc[key],"QC "+key)
    q.validate_reference(reference)
    q.validate_output_directory(output,reference)
    payload={"ref_"+key:reference[key] for key in ("unit_ids","peak_channel_ids","presentation_ids",
             "start_time","stop_time","direction","temporal_frequency","spike_counts","baseline_counts",*q.QC_METRICS)}
    payload.update(ref_unit_ids_all=source["unit_ids_all"],ref_unit_regions_all=source["unit_regions_all"],
                   ref_visp_source_rows=source["visp_source_rows"],
                   ref_stats=np.asarray(json.dumps(reference["stats"],allow_nan=False)))
    bank=Path(bank);bank.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".reference-v2-",suffix=".npz",dir=bank.parent,delete=False) as stream:
        temporary=Path(stream.name)
        np.savez_compressed(stream,**payload);stream.flush();os.fsync(stream.fileno())
    try:
        checked=q.load_reference(temporary)
        q.validate_output_directory(output,checked)
        os.replace(temporary,bank)
    finally:
        if temporary.exists():temporary.unlink()
    print(json.dumps({"reference":str(bank),"pipeline_id":q.PIPELINE_ID,"n_visp_units":len(source["unit_id"]),
                      "n_nonblank_presentations":len(starts),"n_source_response_counts":int(counts.size)},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=Path("/app/data/allenosi"))
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--reference","--bank",dest="reference",type=Path,default=TASK/"tests/reference.npz")
    parser.add_argument("--template",type=Path,default=TASK/"environment/method_contract.json")
    args=parser.parse_args()
    build(args.data,args.output,args.reference,args.template)


if __name__=="__main__":main()

"""Private original-source reference loader; legacy scalar banks fail closed."""
import json
from pathlib import Path
import numpy as np
from graph_contract import (PARTICIPANTS,PIPELINE_ID,derive,required_object,require,validate_output_directory)

METHOD_SHA256 = "8053a2afbe2a23d1dabd70e03e55bace10e70b221b84a97a959e7f7894f5273d"
SOURCE_MANIFEST_SHA256 = "6bc0e95fdd48ed3d3229acc9ce9e48a55860837a5e10d3acade4f0d645cbc5aa"
BUILDER_ID = "original-source-parcel-bincount-gelsd-bfs-v2"
BANK_KEYS = {"ref_participants","ref_weights","ref_path_histogram","ref_metadata_json",
    "ref_ranking_json","ref_graph_rows_json","ref_efficiency_rows_json","ref_provenance_json"}

def _json_scalar(archive,key):
    value = archive[key]
    require(value.shape == () and value.dtype.kind in "US", f"Invalid non-object reference scalar {key}")
    def reject(token):
        raise AssertionError(f"Nonfinite reference JSON {token}")
    return json.loads(str(value),parse_constant=reject)

def load_reference(path=Path(__file__).with_name("reference.npz")):
    with np.load(path,allow_pickle=False) as archive:
        require(set(archive.files) == BANK_KEYS, "Legacy/unrecognized reference schema; genuine source-only rebuild required")
        participants = archive["ref_participants"]
        require(participants.dtype.kind in "iu" and participants.shape == (40,)
            and tuple(map(int,participants)) == PARTICIPANTS, "Wrong source-reference cohort")
        weights = np.array(archive["ref_weights"],dtype=np.float64)
        require(weights.shape == (40,4950) and np.isfinite(weights).all(), "Incomplete source reference connectomes")
        require(np.max(np.abs(weights)) <= 1+1e-12, "Invalid empirical reference correlations")
        metadata = _json_scalar(archive,"ref_metadata_json")
        provenance = _json_scalar(archive,"ref_provenance_json")
        require(isinstance(metadata,dict) and isinstance(provenance,dict), "Reference metadata/provenance must be objects")
        require(metadata.get("pipeline_id") == PIPELINE_ID and metadata.get("status") == "ok", "Reference pipeline/full-run identity invalid")
        require(len(METHOD_SHA256) == 64 and len(SOURCE_MANIFEST_SHA256) == 64, "Source/method not yet frozen; legacy bank cannot be reused")
        required_object(provenance,dict(builder_id=BUILDER_ID,pipeline_id=PIPELINE_ID,
            method_contract_sha256=METHOD_SHA256,source_manifest_sha256=SOURCE_MANIFEST_SHA256),(0,0),"reference provenance")
        require(metadata.get("method_contract_sha256") == METHOD_SHA256 and metadata.get("source_manifest_sha256") == SOURCE_MANIFEST_SHA256,
            "Reference method/source fingerprints differ from frozen task")
        require(isinstance(metadata.get("source_sha256"),dict) and metadata["source_sha256"], "Missing reference source hashes")
        require(provenance.get("source_sha256") == metadata["source_sha256"], "Reference lineage disagreement")
        graph_rows = _json_scalar(archive,"ref_graph_rows_json")
        efficiency_rows = _json_scalar(archive,"ref_efficiency_rows_json")
        ranking = _json_scalar(archive,"ref_ranking_json")
        histogram = np.array(archive["ref_path_histogram"])
    reference = derive(PARTICIPANTS,weights)
    require(histogram.dtype.kind in "iu" and histogram.shape == (40,8,100) and np.array_equal(histogram,reference["histograms"]),
        "Reference hop histograms do not derive from complete source connectomes")
    required_object({"rows":graph_rows},{"rows":reference["graph_rows"]},(1e-13,1e-13),"bank graph arithmetic")
    required_object({"rows":efficiency_rows},{"rows":reference["efficiency_rows"]},(1e-13,1e-13),"bank efficiency arithmetic")
    required_object(ranking,reference["ranking"],(1e-12,1e-12),"bank ranking arithmetic")
    reference["metadata"],reference["provenance"] = metadata,provenance
    return reference

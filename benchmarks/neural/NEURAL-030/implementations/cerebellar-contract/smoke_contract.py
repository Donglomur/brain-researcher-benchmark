"""Portable import/dependency smoke; tiny invented arithmetic only."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import candidate_contract
import candidate_views
import score


def main():
    for module in (candidate_contract, candidate_views, score):
        if Path(module.__file__).resolve().parent != HERE:
            raise ValueError("component dependency resolved outside this directory")
    body = (HERE / "score.py").read_bytes()
    if len(body) != 8568 or hashlib.sha256(body).hexdigest() != "4b4186e14063235f99f0eab8a09bb4edbc6d3cb1f0c9bd9184e194e89cbb7e0a":
        raise ValueError("exact original scorer dependency changed")
    tid, sid = "1" * 32, "2" * 32
    case = {"session_id": sid, "required_predictions": [{"trial_id": tid, "bin_count": 10}]}
    response = {"schema": "neural030_prediction_v1", "task_id": "NEURAL-030", "session_id": sid,
                "arm": "joint", "predictions": [{"trial_id": tid, "counts": [3.] * 10}]}
    raw = json.dumps(response).encode("utf-8")
    parsed = candidate_contract.parse_response(raw, max_bytes=len(raw))
    predictions = candidate_contract.validate_response(parsed, case, "joint")
    result = candidate_contract.score_predictions(
        [{"trial_id": tid, "session_id": sid, "bin_count": 10, "counts": [2] * 10}], predictions)
    if result["trial_results"][0]["mse"] != 1. or result["scientific_qualification"] is not False:
        raise ValueError("invented arithmetic smoke failed")
    print(json.dumps({"status": "PASS", "scope": "portable imports and invented arithmetic only",
                      "scientific_qualification": False, "model_fits": 0, "authentic_payload_reads": 0}, sort_keys=True))


if __name__ == "__main__":
    main()

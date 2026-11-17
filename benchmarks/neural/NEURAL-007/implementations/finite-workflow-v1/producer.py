"""Trusted output envelope around the unchanged one-file programme ABI.

This wrapper runs inside the participant container. Its statements are not
closure evidence: only the external Provider's captured receipt supplies that.
"""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, "/trusted")
import common


def main():
    request_raw = common.snapshot("/request.json", 32768)
    request = json.loads(request_raw)
    definition = json.loads(common.snapshot("/trusted/PROGRAMME.json", 32768))
    common.need(common.pin(common.snapshot("/program/program.py", 200000)) == definition["programme"],
                "frozen complete programme")
    common.need(not list(Path("/output").iterdir()), "fresh participant output")
    result = subprocess.run([sys.executable, "-I", "-B", "/program/program.py", "--input", "/input", "--out", "/output"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    common.need(result.returncode == 0, "participant exit")
    common.need({p.name for p in Path("/output").iterdir()} == {"predictions.npz"}, "original single-file output ABI")
    prediction = common.pin(common.snapshot("/output/predictions.npz", 400000))
    case = json.loads(common.snapshot("/input/case.json", 32768))
    report = {"schema": "sleep007_finite_producer_v1", "case_id": case["case_id"], "epochs": case["epochs"],
              "programme": definition["programme"], "predictions": prediction, "participant_exit": result.returncode}
    report_pin = common.plain(common.write("/output/RESULT.json", common.json_bytes(report)))
    envelope = {"schema": "osl_transport_output_manifest_v1", "phase_id": request["phase_id"],
                "request_sha256": common.pin(request_raw)["sha256"],
                "files": {"predictions.npz": prediction, "RESULT.json": report_pin}}
    common.write("/output/OUTPUTS.json", common.json_bytes(envelope))


if __name__ == "__main__":
    main()

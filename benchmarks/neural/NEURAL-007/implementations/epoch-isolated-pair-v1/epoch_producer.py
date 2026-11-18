"""Trusted epoch output envelope, executed only inside the canonical confined producer."""
import hashlib
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, "/trusted")
import contract as C


def body(path, cap):
    p = C.ordinary_path(path)
    C.need(p.is_file() and 0 < p.stat().st_size <= cap, "Bounded ordinary producer operand")
    raw = p.read_bytes()
    return C.read_exact(p, C.pin(raw), cap)


def main():
    request_raw = body("/request.json", 32768)
    request = C.decode(request_raw)
    definition = C.decode(body("/trusted/PROGRAMME.json", 32768))
    C.need(definition["schema"] == "sleep007_epoch_programme_definition_v1"
           and definition["condition"] == C.PROGRAMME_CONDITION
           and definition["information_contract"] == C.PAIR_CONDITION
           and definition["additional_training_or_reference_assets"] == []
           and C.pin(body("/program/program.py", 200000)) == definition["programme"],
           "Frozen one-file same-epoch programme")
    case_raw = body("/input/case.json", 4096)
    signal_raw = body("/input/signals.npy", 76106)
    packet = C.EpochPacket(C.decode(case_raw), signal_raw)
    C.need({p.name for p in Path("/input").iterdir()} == {"case.json", "signals.npy"},
           "No richer epoch input or other target")
    C.need(not list(Path("/output").iterdir()), "Fresh target output")
    result = subprocess.run([sys.executable, "-I", "-B", "/program/program.py",
                             "--input", "/input", "--out", "/output"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False)
    C.need(result.returncode == 0, "Participant exit")
    C.need({p.name for p in Path("/output").iterdir()} == {"prediction.json"},
           "One target answer, no extra export")
    raw = body("/output/prediction.json", 8192)
    prediction = C.decode(raw)
    C.need(type(prediction) is dict and set(prediction) == {"condition", "epoch_id", "probabilities"}
           and prediction["condition"] == C.PROGRAMME_CONDITION
           and prediction["epoch_id"] == packet.epoch_id, "Exact target answer")
    C.probabilities(prediction["probabilities"])
    prediction_pin = C.pin(raw)
    report = {"schema": "sleep007_epoch_producer_v1", "condition": C.PROGRAMME_CONDITION,
              "epoch_id": packet.epoch_id, "programme": definition["programme"],
              "knowledge": definition["knowledge"], "prediction": prediction_pin, "participant_exit": 0}
    report_pin = C.write_new("/output/RESULT.json", C.encode(report))
    C.write_new("/output/OUTPUTS.json", C.encode({"schema": "osl_transport_output_manifest_v1",
                "phase_id": request["phase_id"], "request_sha256": C.pin(request_raw)["sha256"],
                "files": {"prediction.json": prediction_pin,
                          "RESULT.json": {key: report_pin[key] for key in ("bytes", "sha256")}}}))


if __name__ == "__main__":
    main()

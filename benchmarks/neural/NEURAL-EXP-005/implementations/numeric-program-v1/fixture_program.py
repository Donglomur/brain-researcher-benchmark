"""Generated packet reader for engineering tests only; not a neural reference."""

import json
from pathlib import Path
import sys

instructions = Path(sys.argv[1]).read_text()
assert "helsinki-causal-packet-v1" in instructions and "[29,30)" in instructions
packet = json.loads(sys.stdin.readline())
assert packet["schema"] == "helsinki-causal-packet-v1"
assert packet["prediction_interval_seconds"] == [29, 30]
assert len(packet["montage"]) == 18 and len(packet["quality_flags"]) == 30
assert packet["sample_clock"] == {"first_tick": 0, "step_ticks": 1, "ticks_per_second": 1}
assert set(packet).isdisjoint({"labels", "recording_id", "source_asset", "recordings"})
samples = packet["samples"]
assert len(samples) == 30 and all(len(row) == 18 for row in samples)
origin = samples[0][0]
assert all(abs(value - origin - index - channel / 100) < 1e-12
           for index, row in enumerate(samples) for channel, value in enumerate(row))
probability = 0.25 + (samples[-1][-1] - origin - 29.17)
mode = sys.argv[2] if len(sys.argv) > 2 else "good"
answer = {"action": "answer", "case_id": packet["case_id"],
          "input_sha256": packet["input_sha256"], "probability": probability}
if mode == "wrong_binding": answer["case_id"] = "0" * 64
if mode == "nonfinite": answer["probability"] = float("nan")
if mode == "numeric_view": answer = {"action": "describe"}
print(json.dumps(answer, separators=(",", ":")), flush=True)
receipt = json.loads(sys.stdin.readline())
assert receipt["accepted"] is True
if mode == "extra": print(" ", flush=True)
if mode == "nonzero": raise SystemExit(2)

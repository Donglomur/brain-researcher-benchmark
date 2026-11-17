"""Invented-data isolation/protocol controls; used only by the control harness."""
import json
import os
from pathlib import Path
import select
import socket
import sys
import time
sys.path.insert(0, str(Path(__file__).absolute().parent))
from consumer import decode_reply
from model_artifact import decode_artifact, predict_artifact
import control_constants

mode = Path(__file__).stem.removeprefix("attack_")
with open("/model/model.json", "rb") as f:
    model = decode_artifact(f.read(65537))
if mode == "early_exit":
    raise SystemExit(0)
if mode == "trial_reset":
    assert not Path("/tmp/previous-trial-marker").exists(), "state survived real trial boundary"
    Path("/tmp/previous-trial-marker").write_text("created only in this ephemeral trial")
if mode == "isolation":
    try:
        with open(control_constants.HOST_CANARY, "rb") as f: f.read(1)
    except OSError:
        pass
    else:
        raise AssertionError("hidden host filesystem was readable")
    try:
        with open("/model/model.json", "ab") as f: f.write(b"changed")
    except OSError:
        pass
    else:
        raise AssertionError("frozen artifact was writable")
    assert not Path("/var/run/docker.sock").exists()
    connection = socket.socket(); connection.settimeout(.25)
    try:
        connection.connect(("198.51.100.1", 80))
    except OSError:
        pass
    else:
        raise AssertionError("network isolation absent")
    finally:
        connection.close()
first = True
while True:
    if mode == "lookahead":
        # Avoid BufferedReader read-ahead hiding an erroneously prequeued query.
        parts = bytearray()
        while len(parts) < 4097:
            one = os.read(sys.stdin.fileno(), 1)
            if not one: break
            parts.extend(one)
            if one == b"\n": break
        line = bytes(parts)
    else:
        line = sys.stdin.buffer.readline(4097)
    if not line:
        raise AssertionError("missing explicit committed-trial termination")
    query = decode_reply(line)
    if query == {"schema": "hybrid-trial-end-v1"}:
        if mode == "orphan_child":
            child = os.fork()
            if child == 0:
                os.setsid(); time.sleep(300); os._exit(0)
        break
    if mode == "lookahead":
        assert not select.select([sys.stdin], [], [], .05)[0], "future input available before commitment"
    if mode == "timeout":
        time.sleep(300)
    reply = {"token": query["token"], "probabilities": predict_artifact(model, query["observation"])}
    if first and mode == "wrong_token":
        reply["token"] = "0" * 64 if query["token"] != "0" * 64 else "f" * 64
    if first and mode == "zero_probability":
        reply["probabilities"] = [0, .2, .3, .5]
    text = json.dumps(reply, separators=(",", ":")) + "\n"
    if first and mode == "duplicate_key":
        text = '{"token":"x","token":"y","probabilities":[0.25,0.25,0.25,0.25]}\n'
    if first and mode == "nan":
        text = '{"token":"' + query["token"] + '","probabilities":[NaN,0.2,0.3,0.5]}\n'
    if first and mode == "extra_reply":
        text += text
    if first and mode == "oversized":
        text = "x" * 5120 + "\n"
    if first and mode == "unterminated":
        text = "x" * 4097
    sys.stdout.write(text); sys.stdout.flush(); first = False

"""Selected stdlib reference participant: one fresh isolated process per trial."""
import json
import re
import sys
import platform
from pathlib import Path

# The readonly /program directory contains only this admitted public programme.
sys.path.insert(0, str(Path(__file__).absolute().parent))
from consumer import ContractError, decode_reply, validate_observation
from model_artifact import decode_artifact, predict_artifact


def main():
    if sys.version_info[:3] != (3, 12, 8) or platform.system() != "Linux" or platform.machine() != "aarch64":
        raise ContractError("exact existing participant interpreter profile")
    if sys.argv[1:] != ["/model/model.json"]:
        raise ContractError("exact anonymous model operand")
    with open(sys.argv[1], "rb") as f:
        artifact = decode_artifact(f.read(65537))
    first = True
    while True:
        line = sys.stdin.buffer.readline(4097)
        if not line:
            return 0
        if not line.endswith(b"\n") or len(line) > 4096:
            raise ContractError("bounded complete current query")
        q = decode_reply(line)
        if q == {"schema": "hybrid-trial-end-v1"} and not first:
            return 0
        if type(q) is not dict or set(q) != {"schema", "token", "new_trial", "observation"} or q["schema"] != "hybrid-current-query-v1":
            raise ContractError("current query fields")
        if type(q["token"]) is not str or re.fullmatch(r"[a-f0-9]{64}", q["token"]) is None or q["new_trial"] is not first:
            raise ContractError("fresh trial and opaque token")
        validate_observation(q["observation"])
        out = {"token": q["token"], "probabilities": predict_artifact(artifact, q["observation"])}
        body = json.dumps(out, separators=(",", ":"), allow_nan=False) + "\n"
        if len(body.encode()) > 4096:
            raise ContractError("reply bound")
        sys.stdout.write(body); sys.stdout.flush(); first = False


if __name__ == "__main__":
    raise SystemExit(main())

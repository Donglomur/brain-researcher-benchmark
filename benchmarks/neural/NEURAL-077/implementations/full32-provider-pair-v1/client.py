"""One trusted full32 provider client with private inherited descriptor custody.

The caller must freeze this component, its exact sibling bridge, model/configuration
and the donor source before query access. Configuration is a trusted operator
input through a private pipe, never a participant-supplied code selector. This
source supplies capture and admission primitives; it does not qualify live remote
context isolation, provider capacity, tool policy or scientific performance.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

HERE = Path(__file__).absolute().parent
DONOR_PIN = {"bytes": 19747, "sha256": "299d3effae6db940cf2dcd8498a2b43af0b36978e9f892cdd3b8af39391d9aef"}
CONFIG_CAP = 16384
CREDENTIAL_CAP = 4096
BRIDGE_CAP = 131072
BOOTSTRAP_SECONDS = 5.0
CUSTODY_SECONDS = 2.0
CONFIG_KEYS = {"schema", "model", "max_output_tokens", "deadline", "trial_id",
               "context_sha256", "bridge_path", "bridge_pin"}
FILES = {"REQUEST.bin", "RESPONSE.bin", "HTTP.json", "BRIDGE.json"}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, "duplicate_json_key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and 0 < value["bytes"] <= cap
         and type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
         "source_descriptor")


def source_bytes(path, expected):
    """Read only one selected ordinary bounded file without following aliases."""
    descriptor(expected, BRIDGE_CAP)
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts
         and all(not part.is_symlink() for part in (path, *path.parents)), "source_path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected["bytes"], "source_file")
        body = stream.read(expected["bytes"] + 1)
        after = os.fstat(stream.fileno())
    fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
                            value.st_ctime_ns, value.st_nlink)
    need(fields(before) == fields(after) == fields(path.lstat()) and pin(body) == expected,
         "source_changed")
    return body


def load_module(name, path, body):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


@lru_cache(maxsize=1)
def donor():
    path = HERE.parent / "waveform-provider-v1/client.py"
    return load_module("erp_full32_pinned_https_primitives", path, source_bytes(path, DONOR_PIN))


def configuration(raw):
    need(type(raw) is bytes and 0 < len(raw) <= CONFIG_CAP, "configuration")
    value = decode(raw)
    need(type(value) is dict and set(value) == CONFIG_KEYS
         and value["schema"] == "erp_full32_openai_client_v1", "configuration")
    need(type(value["model"]) is str
         and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value["model"]), "configuration")
    need(type(value["max_output_tokens"]) is int and 1 <= value["max_output_tokens"] <= 32768,
         "configuration")
    need(type(value["deadline"]) in (int, float) and math.isfinite(value["deadline"])
         and CUSTODY_SECONDS < value["deadline"] - time.monotonic() <= 3600, "configuration")
    need(type(value["trial_id"]) is str and re.fullmatch(r"q-[0-9a-f]{32}", value["trial_id"]),
         "configuration")
    need(type(value["context_sha256"]) is str
         and re.fullmatch(r"[0-9a-f]{64}", value["context_sha256"]), "configuration")
    need(type(value["bridge_path"]) is str and value["bridge_path"] == str(HERE / "bridge.py"),
         "exact_sibling_bridge_required")
    descriptor(value["bridge_pin"], BRIDGE_CAP)
    return value


def load_bridge(config):
    path = HERE / "bridge.py"
    need(config["bridge_path"] == str(path), "exact_sibling_bridge_required")
    return load_module("erp_full32_selected_responses_bridge", path,
                       source_bytes(path, config["bridge_pin"]))


def arguments(argv):
    """The inherited descriptor-number interface is unchanged."""
    return donor().arguments(argv)


def main(argv=None, *, http_factory=http.client.HTTPSConnection, input_stream=None, output_stream=None):
    """One actual sender only when explicitly invoked by an admitted operator.

    Injected factories are for generated controls. They are not a live provider
    connection or a provider qualification. Credentials never enter argv/env.
    """
    started = time.monotonic()
    alarm = None
    fds = {}
    custody = sender = config = None
    recorded = success = False
    primitives = None
    try:
        primitives = donor()
        need(primitives.FILES == FILES and primitives.CUSTODY_SECONDS == CUSTODY_SECONDS,
             "pinned_donor_interface")
        fds = arguments(sys.argv[1:] if argv is None else argv)
        alarm = primitives.Alarm(started + BOOTSTRAP_SECONDS)
        raw = primitives.pipe_body(fds["--config-fd"], CONFIG_CAP, started + BOOTSTRAP_SECONDS)
        os.close(fds.pop("--config-fd"))
        config = configuration(raw)
        config_pin = pin(raw)
        custody = primitives.Custody(fds["--custody-fd"], config_pin, config["deadline"])
        alarm.arm(config["deadline"] - CUSTODY_SECONDS)
        secret = primitives.pipe_body(fds["--credential-fd"], CREDENTIAL_CAP,
                                      config["deadline"] - CUSTODY_SECONDS)
        os.close(fds.pop("--credential-fd"))
        need(1 <= len(secret) <= CREDENTIAL_CAP and all(33 <= byte <= 126 for byte in secret),
             "credential")
        credential = secret.decode("ascii")
        del secret
        bridge = load_bridge(config)
        sender = primitives.Sender(config, config_pin, credential, custody, bridge, alarm, http_factory)
        del credential

        def record(receipt):
            nonlocal recorded
            need(not recorded, "second_bridge_receipt")
            need(sender.credential.encode("ascii") not in primitives.encode(receipt), "credential_echo")
            custody.json("BRIDGE.json", {
                "schema": "erp_full32_provider_binding_bridge_v1", "config_pin": config_pin,
                "status": "recorded", "receipt": receipt, "failure": None})
            need(custody.created == FILES and set(os.listdir(custody.fd)) == FILES,
                 "custody_membership")
            recorded = True

        bridge.serve(sys.stdin.buffer if input_stream is None else input_stream,
                     sys.stdout.buffer if output_stream is None else output_stream,
                     model=config["model"], max_output_tokens=config["max_output_tokens"],
                     send_json=sender, record=record)
        need(custody.created == FILES and set(os.listdir(custody.fd)) == FILES,
             "custody_membership")
        success = True
    except Exception:
        # Exceptions can carry HTTP/credential material; retain only fixed errors.
        success = False
    finally:
        if sender is not None:
            sender.credential = None
        if custody is not None and config is not None and primitives is not None:
            try:
                alarm.arm(config["deadline"])
                if "REQUEST.bin" not in custody.created:
                    custody.put("REQUEST.bin", b"")
                if "RESPONSE.bin" not in custody.created:
                    custody.put("RESPONSE.bin", b"")
                if "HTTP.json" not in custody.created:
                    custody.json("HTTP.json", {
                        "schema": "neural077_https_binding_v1", "config_pin": custody.config_pin,
                        "endpoint": primitives.ENDPOINT, "request": pin(b""), "response": pin(b""),
                        "status_code": None, "request_complete": False, "response_complete": False,
                        "body_overflow": False, "requests_attempted": 0, "redirects_followed": 0,
                        "retries": 0, "connection_closed": False, "credential_retained": False,
                        "failure": "preflight_or_incomplete_custody", "started_monotonic": started,
                        "finished_monotonic": time.monotonic(), "deadline": config["deadline"]})
                if not recorded and "BRIDGE.json" not in custody.created:
                    custody.json("BRIDGE.json", {
                        "schema": "erp_full32_provider_binding_bridge_v1", "config_pin": custody.config_pin,
                        "status": "not_called", "receipt": None, "failure": "preflight_or_invalid_prompt"})
            except Exception:
                success = False
        if alarm is not None:
            alarm.close()
        for fd in fds.values():
            try:
                os.close(fd)
            except OSError:
                success = False
    return 0 if success else 3


if __name__ == "__main__":
    raise SystemExit(main())

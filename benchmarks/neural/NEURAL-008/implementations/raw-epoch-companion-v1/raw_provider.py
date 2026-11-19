"""N008 schema/modality adapter; the maintained S7 broker and HTTPS custody do the work."""
import builtins
import http.client
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import raw_contract as C
import raw_viewer as V

PROVIDER_PATH = "benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1/epoch_provider.py"
PROVIDER_PIN = {"bytes": 16962, "sha256": "4205f7d9c8ee6bd7c3ac6968bab5576f4c13a0d4944a2acb45d57356393b5d47"}


def _adapter(runtime, modality):
    modality = C.checked_modality(modality)
    cache = runtime.setdefault("raw_provider_adapters", {})
    if modality in cache:
        return cache[modality]
    environment = runtime["raw_environment"]
    expected = environment["bindings"]["upstream"].get(PROVIDER_PATH)
    C.need(expected == PROVIDER_PIN, "Exact maintained S7 broker source")
    path = environment["root"] / PROVIDER_PATH
    body = C.read_exact(path, expected)
    def session(packet, selected_runtime, max_actions, session_id=None):
        C.need(packet.modality == modality, "Provider adapter cannot substitute a modality")
        return V.Session(packet, selected_runtime, max_actions, session_id)
    facade = SimpleNamespace(CONDITION=C.VIEWER_CONDITIONS[modality], MEMORY_POLICY=V.MEMORY_POLICY,
                             need=C.need, pin=C.pin, encode=V.encode, Session=session,
                             request_bytes=V.request_bytes)
    # Import adaptation is private to this freshly compiled namespace. Do not
    # patch epoch_visual, frozen S7 modules, or shared sys.path/module aliases.
    original_import = builtins.__import__
    def isolated_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "epoch_visual" and level == 0:
            return facade
        if name == "sys" and level == 0:
            return SimpleNamespace(path=list(sys.path))
        return original_import(name, globals, locals, fromlist, level)
    name = "_n008_provider_" + modality
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    module.__dict__["__builtins__"] = dict(vars(builtins), __import__=isolated_import)
    exec(compile(body, str(path), "exec"), module.__dict__)
    module.EVENT_SCHEMA = "neural008_raw_epoch_visual_event_v1"
    module.END_SCHEMA = "neural008_raw_epoch_visual_end_v1"
    original_config, original_end = module.config_value, module._end
    def config_value(selected_runtime, selected_session, knowledge, budget):
        value = original_config(selected_runtime, selected_session, knowledge, budget)
        value.update(schema="neural008_raw_epoch_visual_config_v1", family=C.FAMILY,
                     modality=modality, available_channels=list(C.CHANNELS_BY_MODALITY[modality]))
        return value
    def end_value(*args, **kwargs):
        value = original_end(*args, **kwargs)
        complete = value.pop("complete_three_channel_epoch")
        value.update(family=C.FAMILY, modality=modality,
                     complete_available_channel_epoch=complete,
                     available_channels=list(C.CHANNELS_BY_MODALITY[modality]))
        return value
    module.config_value, module._end = config_value, end_value
    cache[modality] = module
    return module


def checked_budget(runtime, value):
    return _adapter(runtime, C.EEG).checked_budget(runtime, value)


def run_epoch(runtime, packet, knowledge, budget, custody_root, credential, input_token_bound,
              *, session_id=None, http_factory=http.client.HTTPSConnection):
    """Only a separately selected operation may invoke transport; no qualification is granted."""
    result = _adapter(runtime, packet.modality).run_epoch(
        runtime, packet, knowledge, budget, custody_root, credential, input_token_bound,
        session_id=session_id, http_factory=http_factory)
    C.need(result["condition"] == C.VIEWER_CONDITIONS[packet.modality]
           and result["modality"] == packet.modality, "Exact modality-bound terminal custody")
    return result


def audit_session(session_root, packet, runtime, knowledge):
    """Replay the actual maintained custody verifier with the same N008 adapter."""
    value = _adapter(runtime, packet.modality).audit_session(session_root, packet, runtime, knowledge)
    C.need(value["condition"] == C.VIEWER_CONDITIONS[packet.modality], "Exact companion viewer condition")
    return dict(value, family=C.FAMILY, modality=packet.modality,
                available_channels=list(packet.channels))


def run_configuration(descriptor):
    """Run only an explicit trusted, pinned operator configuration.

    Credentials are fetched from the named environment entry, never written into
    configuration/custody. The separately pinned token-bound source is an
    operator input; its presence grants no provider or token qualification.
    """
    import os
    import re
    value = C.decode(C.capture(descriptor, 65536))
    C.need(type(value) is dict and set(value) == {
        "schema", "source_bindings", "dependency_root", "projection", "knowledge", "budget",
        "custody_root", "credential_env", "input_token_bound", "session_id"}
        and value["schema"] == "neural008_raw_epoch_viewer_operation_v1", "Exact trusted viewer operation")
    C.checked_knowledge(value["knowledge"])
    C.need(type(value["credential_env"]) is str
           and re.fullmatch("[A-Za-z_][A-Za-z0-9_]{0,127}", value["credential_env"]), "Credential environment name")
    runtime = V.load_runtime(value["source_bindings"], value["dependency_root"])
    budget = checked_budget(runtime, value["budget"])
    packet = C.read_projection(value["projection"])
    token_source = C.capture(value["input_token_bound"], 65536)
    namespace = {"__name__": "_n008_selected_input_token_bound", "__file__": value["input_token_bound"]["path"]}
    exec(compile(token_source, value["input_token_bound"]["path"], "exec"), namespace)
    callback = namespace.get("input_token_bound")
    C.need(callable(callback), "Pinned trusted source must export input_token_bound(raw, deadline)")
    credential = os.environ.get(value["credential_env"])
    C.need(type(credential) is str and bool(credential), "Selected credential environment entry is absent")
    return run_epoch(runtime, packet, value["knowledge"], budget, value["custody_root"], credential,
                     callback, session_id=value["session_id"])


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Explicit selected N008 raw-epoch viewer operation")
    parser.add_argument("--operation", required=True, choices=("run",))
    parser.add_argument("--config", required=True)
    parser.add_argument("--bytes", required=True, type=int)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_configuration({"path": str(Path(args.config).absolute()), "bytes": args.bytes, "sha256": args.sha256})
    except Exception as exc:
        # Do not echo credentials, source bodies or provider response content.
        print(C.encode({"status": "refused_or_failed_no_admission", "error_type": type(exc).__name__,
                        "scientific_qualification": False}).decode(), end="")
        return 2
    print(C.encode(result).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

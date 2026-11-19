"""N008 modality-limited viewer adapter around the maintained N007 epoch viewer."""
from pathlib import Path
import importlib.util
import json
import sys
from types import SimpleNamespace
import raw_contract as C

VISUAL_PATH = "benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1/epoch_visual.py"
VISUAL_PIN = {"bytes": 15668, "sha256": "46aa524ce965ecb69b4cbbd7b79d93f589f524bce314007da724d8bf8acbaec8"}
MEMORY_POLICY = "immutable_complete_epoch_overview_plus_current_detail_no_history_v1"
need, pin = C.need, C.pin


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _module(path, body, name):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def load_runtime(bindings_descriptor, dependency_root=None, local_root=None):
    environment = C.verify_source(bindings_descriptor, dependency_root, local_root)
    expected = environment["bindings"]["upstream"].get(VISUAL_PATH)
    C.need(expected == VISUAL_PIN, "Exact maintained S7 viewer adapter source")
    path = environment["root"] / VISUAL_PATH
    raw = C.read_exact(path, expected)
    base = _module(path, raw, "_n008_upstream_visual_runtime")
    # Its existing loader authenticates the current renderer/sender dependency
    # closure. Retain its packet reader, not a fixture or alternate signal loader.
    prior_contract = sys.modules.get("contract")
    try:
        runtime = base.load_runtime(environment["root"])
    finally:
        if prior_contract is None:
            sys.modules.pop("contract", None)
        else:
            sys.modules["contract"] = prior_contract
    originals = runtime["source"]
    runtime["original_viewer"] = runtime["viewer"]
    runtime["contract"] = C
    runtime["raw_environment"] = environment
    runtime["raw_visuals"] = {}
    for modality in C.MODALITIES:
        module = _module(path, raw, "_n008_visual_" + modality)
        module.CONDITION = C.VIEWER_CONDITIONS[modality]
        runtime["raw_visuals"][modality] = module
    runtime["source"] = {"family": C.FAMILY, "upstream_n007": originals,
                         "companion_source_binding": environment["source"],
                         "companion_local": environment["bindings"]["local"],
                         "adaptation": "isolated_modality_namespace_and_physical_projection_v1"}
    return runtime


class Session:
    """Only channels physically present in this immutable projection can be viewed."""
    def __init__(self, packet, runtime, max_actions, session_id=None):
        C.need(type(packet) is C.RawEpochPacket, "Authenticated N008 raw projection")
        C.need(runtime["contract"] is C, "Exact raw companion contract")
        modality = packet.modality
        base = runtime["raw_visuals"][modality]
        original = runtime["original_viewer"]
        # The old viewer uses CHANNELS for both action admission and initial state.
        # This session-private facade excludes EOG as well as omitting its bytes.
        viewer = SimpleNamespace(CHANNELS=packet.channels, GAINS=original.GAINS,
                                 probabilities=original.probabilities)
        contract = SimpleNamespace(**{name: getattr(C, name) for name in dir(C) if not name.startswith("__")})
        contract.CHANNELS = packet.channels
        adapted = dict(runtime, viewer=viewer, contract=contract)
        self._base, self._session = base, base.Session(packet, adapted, max_actions, session_id)
        self.modality = modality

    def __getattr__(self, name):
        return getattr(self._session, name)

    def observation(self):
        header, images = self._session.observation()
        header = dict(header, schema="neural008_raw_epoch_visual_observation_v1", family=C.FAMILY,
                      modality=self.modality, available_channels=list(self.packet.channels))
        return header, images

    def initial(self):
        self._session.initial()
        return self.observation()

    def validate_action(self, request):
        return self._session.validate_action(request)

    def handle(self, request):
        result = self._session.handle(request)
        if self._session.closed:
            result = dict(result)
            result.pop("full_three_channel_epoch_available", None)
            result.update(family=C.FAMILY, modality=self.modality,
                          complete_available_channel_epoch=True, channel_count=len(self.packet.channels))
            return result
        return self.observation()


def request_bytes(session, model, budget, knowledge):
    C.need(type(session) is Session, "N008 trusted viewer session")
    raw = session._base.request_bytes(session._session, model, budget, knowledge)
    value = C.decode(raw)
    first = C.decode(value["input"][0]["content"][0]["text"])
    first.update(schema="neural008_raw_epoch_visual_request_v1", family=C.FAMILY,
                 modality=session.modality)
    first["public_task"]["schema"] = "neural008_raw_epoch_public_task_v1"
    first["public_task"]["modality"] = session.modality
    first["observation"] = session.observation()[0]
    value["input"][0]["content"][0]["text"] = encode(first).decode()
    description = "two EEG channels" if session.modality == C.EEG else "two EEG channels plus EOG"
    value["instructions"] = value["instructions"].replace(
        "The immutable complete three-channel target overview is always supplied",
        "The immutable complete target overview of " + description + " is always supplied")
    value["instructions"] += (" This is the separately named NEURAL-008 raw epoch companion, modality "
                              + session.modality + ". Only the declared available channels are accessible.")
    encoded = encode(value)
    C.need(len(encode(value["input"])) <= budget.max_history_bytes
           and len(encoded) <= budget.max_request_bytes <= session.runtime["sender"].REQUEST_CAP,
           "Complete actual N008 request fits the unchanged provider bounds")
    return encoded

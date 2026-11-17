"""Generated-only neural rollout component; source-amended, inactive and unqualified.

The released generator and all original files remain unchanged. This component
implements the paper's current-token/past-buffer mechanism with explicit changes
to the defective release. It does not recover an ablation recipe or paper run.
Numerical leaves are supplied by a separately qualified runtime; importing this
module imports no numerical/model package and performs no scientific work.
"""
from __future__ import annotations
import ast
import copy
import hashlib
import math
import struct
from numbers import Integral

import native_dataset as native
import run_composition as composition

require = native.require
PROFILE = "protected_generated_only_native10ms_v1"
SCHEMA = "neuroformer_protected_rollout_request_v1"
LIMITS = {"max_windows", "max_events", "max_model_calls", "max_vocab",
          "max_current_tokens", "max_history_tokens", "max_feature_elements"}


def native_endpoint(tick):
    """Exact original x['interval'] float32 representation, never a tolerance join."""
    try:
        value = struct.unpack("<f", struct.pack("<f", tick / 100))[0]
    except (OverflowError, struct.error):
        require(False, "endpoint cannot be represented by the original float32 ABI")
    require(math.isfinite(value), "finite original float32 endpoint")
    return value


def descriptor(value):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "exact identity descriptor")
    native.relative(value["path"])
    native.integer(value["bytes"], "identity bytes")
    require(type(value["sha256"]) is str and len(value["sha256"]) == 64 and
            all(c in "0123456789abcdef" for c in value["sha256"]), "identity digest")


def source_receipt(bodies):
    """Authenticate the exact captured originals before compiling any leaf."""
    required = {
        "neuroformer/simulation.py": (20772, "cb7b0a2445c468e13ab197a69205b08cc4b15907ef36bb3fe593a8dced75033d"),
        "neuroformer/data_utils.py": (53196, "71ec03aa43aa911c53d680d9f7a8e0f9fd677f50f97ab983acccfcd63ffa15e4"),
        "neuroformer/model_neuroformer.py": (58004, "919dbeed014d1a600743d415cccfb594caf74f7edf47cfa5b3747ba0456bb3cd"),
    }
    for path, (size, digest) in required.items():
        require(type(bodies.get(path)) is bytes and len(bodies[path]) == size and
                hashlib.sha256(bodies[path]).hexdigest() == digest, "exact original rollout dependency: " + path)
    return {"revision": native.REVISION,
            "definitions": [composition.definition(bodies, path, name) for path, name in (
                ("neuroformer/simulation.py", "generate_spikes"),
                ("neuroformer/simulation.py", "top_k_top_p_filtering"),
                ("neuroformer/data_utils.py", "NFDataloader"),
                ("neuroformer/model_neuroformer.py", "Neuroformer"))]}


def admit_request(request, fitted):
    require(type(request) is dict and set(request) == {"schema", "profile", "run_id", "seed",
            "config_identity", "run_identity", "checkpoint_identity", "device", "sampling",
            "limits", "support", "episodes", "source_revision", "method_binding"}, "closed rollout request")
    require(request["schema"] == SCHEMA and request["profile"] == PROFILE and
            request["source_revision"] == native.REVISION, "explicit amended source profile")
    require(request["method_binding"] == "component_only_no_original_ablation_mapping", "no invented ablation binding")
    require(type(request["run_id"]) is str and request["run_id"], "explicit run identity")
    native.integer(request["seed"], "explicit rollout seed", 0)
    require(request["seed"] < 2**32, "seed range")
    for field in ("config_identity", "run_identity", "checkpoint_identity"):
        descriptor(request[field])
    require(type(request["device"]) is str and (request["device"] == "cpu" or
            (request["device"].startswith("cuda:") and request["device"][5:].isdigit())), "explicit device")
    require(set(request["limits"]) == LIMITS, "explicit limits")
    for n in request["limits"].values():
        native.integer(n, "positive resource admission")
    require(type(request["support"]) is dict and set(request["support"]) == {"train", "selection", "evaluation"} and
            all(type(rows) is list and 0 < len(rows) <= request["limits"]["max_windows"] for rows in request["support"].values()),
            "bounded support before capture")
    require(type(request["episodes"]) is list and 0 < len(request["episodes"]) <= request["limits"]["max_windows"],
            "bounded episode count before capture")
    require(all(type(e) is dict and type(e.get("row_ids")) is list and
                0 < len(e["row_ids"]) <= request["limits"]["max_windows"] for e in request["episodes"]),
            "bounded episode rows before capture")
    request = copy.deepcopy(request)
    s = request["sampling"]
    require(type(s) is dict and set(s) == {"sample", "top_k", "top_p", "top_p_dt", "temperature", "temperature_dt"}, "explicit sampling recipe, no defaults")
    require(type(s["sample"]) is bool, "sampling or argmax explicit")
    native.integer(s["top_k"], "top k", 0)
    for field in ("top_p", "top_p_dt", "temperature", "temperature_dt"):
        require(type(s[field]) in (float, int) and math.isfinite(s[field]), "finite sampling scalar")
    require(0 <= s["top_p"] <= 1 and 0 <= s["top_p_dt"] <= 1 and
            s["temperature"] > 0 and s["temperature_dt"] > 0, "sampling domain")
    require(fitted["condition"] == composition.PROTECTED and fitted["selected_checkpoint_loaded"] is True,
            "protected selected checkpoint required")
    # Identity capture and physical/runtime qualification remain operator gates.
    # These exact descriptors must be attached by that operator, not inferred.
    require(fitted.get("rollout_identities") == {k: request[k] for k in
            ("config_identity", "run_identity", "checkpoint_identity")}, "selected fitted identity binding")
    require(fitted["seed"] == request["seed"], "explicit fit/rollout seed identity")
    c = fitted["config"]
    require(c.resolution.dt == .01 and c.window.curr == .05 and c.window.prev == .05 and
            c.window.frame == .15, "native10ms 50/50/150ms source geometry")
    require(not c.mlp_only and not c.gru_only and not c.gru2_only, "Neuroformer component, no baseline substitution")
    for name, limit in (("id", "max_current_tokens"), ("prev_id", "max_history_tokens")):
        width = getattr(c.block_size, name)
        native.integer(width, "source block width", 3)
        require(width <= request["limits"][limit], "block capacity before allocation")
    receipt = composition.admit_support(request["support"], composition.PROTECTED)
    rows = request["support"]["evaluation"]
    require(len({row["recording"] for row in rows}) == 1, "one recording per native Trial0 output packet")
    require(len({native_endpoint(row["end_tick"]) for row in rows}) == len(rows),
            "distinct full evaluation windows in the original float32 ABI")
    require(len(rows) <= request["limits"]["max_windows"] and
            len(rows) * (c.block_size.id - 1) <= request["limits"]["max_model_calls"], "complete rollout capacity")
    require(type(request["episodes"]) is list and request["episodes"], "explicit episode partition")
    seen = []
    by_id = {r["id"]: r for r in rows}
    episode_names = set()
    for episode in request["episodes"]:
        require(type(episode) is dict and set(episode) == {"id", "initial_history", "row_ids"}, "episode keys")
        require(type(episode["id"]) is str and episode["id"] and episode["id"] not in episode_names, "unique episode identity")
        episode_names.add(episode["id"])
        require(episode["initial_history"] == "empty_generated_buffer" and
                type(episode["row_ids"]) is list and episode["row_ids"], "explicit amended empty-history start")
        previous = None
        for row_id in episode["row_ids"]:
            require(type(row_id) is str and row_id in by_id, "episode row belongs to full evaluation support")
            row = by_id[row_id]
            require(row["end_tick"] >= 5, "negative source window not silently wrapped or dropped")
            if previous:
                require(row["recording"] == previous["recording"] and row["end_tick"] == previous["end_tick"] + 5,
                        "contiguous same-recording generated-history episode")
            previous = row
            seen.append(row_id)
    require(seen == [r["id"] for r in rows], "episodes preserve complete ordered evaluation support")
    return request, receipt


def vocabulary(tokenizer, limits):
    vocab = {}
    for name in ("ID", "dt"):
        stoi, itos = tokenizer.stoi[name], tokenizer.itos[name]
        require(type(stoi) is dict and type(itos) is dict and 0 < len(stoi) == len(itos) <= limits["max_vocab"], "bounded complete vocabulary")
        require(set(itos) == set(range(len(itos))) and all(type(i) is int for i in itos), "dense integer token indices")
        require(all(type(index) is int and index in itos and itos[index] == value for value, index in stoi.items()), "exact inverse vocabulary")
        require(all(token in stoi for token in ("SOS", "EOS", "PAD")), "named special tokens")
        vocab[name] = {"stoi": dict(stoi), "itos": dict(itos)}
    ids = {i: value for i, value in vocab["ID"]["itos"].items() if value not in ("SOS", "EOS", "PAD")}
    # Native preparation uses list(np.arange(N)); these are Integral scalars,
    # not necessarily exact Python int objects. No numerical import is needed.
    require(ids and all(isinstance(n, Integral) and not isinstance(n, bool) and n >= 0 for n in ids.values()), "physical neuron IDs")
    ids = {i: int(n) for i, n in ids.items()}
    dt_values = {}
    for i, value in vocab["dt"]["itos"].items():
        if value in ("SOS", "EOS", "PAD"):
            continue
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0 and
                abs(value * 100 - round(value * 100)) < 1e-7, "native10ms time vocabulary")
        dt_values[i] = round(value * 100)
    require(0 in vocab["dt"]["stoi"] and all(t / 100 in vocab["dt"]["stoi"] for t in range(5)), "complete native50ms offsets")
    return vocab, ids, dt_values


def history_tokens(events, end_tick, width, vocab):
    """Stable time/ID order, shared paired truncation, source SOS/EOS/PAD layout."""
    start, stop = end_tick - 10, end_tick - 5
    selected = sorted((e for e in events if start <= e[1] < stop), key=lambda e: (e[1], e[0]))[-(width - 2):]
    si, st = vocab["ID"]["stoi"], vocab["dt"]["stoi"]
    ids = [si["SOS"]] + [si[neuron] for neuron, tick in selected] + [si["EOS"]]
    times = [0] + [st[(tick - start) / 100] for neuron, tick in selected] + [st["EOS"]]
    padding = width - len(selected) - 1
    # Original get_interval returns width+1 and __getitem__ drops its last item.
    return ((ids + [si["PAD"]] * padding)[:-1],
            (times + [st["PAD"]] * padding)[:-1], padding, tuple(selected))


def admit_features(features, config, max_elements):
    expected_modalities = {}
    if config.modalities is not None:
        for group, declaration in vars(config.modalities).items():
            variables = {name for name, v in vars(declaration.variables).items() if v.predict is False}
            if variables:
                expected_modalities[group] = variables
    expected = {"modalities"} if config.modalities is not None else set()
    if getattr(config.layers, "stimulus", 0) > 0:
        expected.add("frames")
    require(type(features) is dict and set(features) == expected, "only declared exogenous features, no current/history truth")
    tensors = []
    if "frames" in features:
        tensors.append(features["frames"])
    if "modalities" in features:
        groups = features["modalities"]
        require(type(groups) is dict and set(groups) == set(expected_modalities), "exact source-declared input modalities")
        for group, names in expected_modalities.items():
            require(type(groups[group]) is dict and set(groups[group]) == names, "exact source input variables")
            for variable in groups[group].values():
                require(type(variable) is dict and set(variable) == {"value", "dt"}, "closed input variable")
                tensors.extend((variable["value"], variable["dt"]))
    total = 0
    for tensor in tensors:
        shape = tuple(tensor.shape)
        require(shape and shape[0] == 1 and all(type(n) is int and n > 0 for n in shape), "one-window positive feature shape")
        size = 1
        for n in shape:
            require(n <= max_elements // size, "feature extent before transfer")
            size *= n
        total += size
        require(total <= max_elements, "complete feature capacity")
    return features


class NativeStep:
    """Actual Torch/model/sampling call path; controls bind explicitly inert leaves."""
    def __init__(self, bodies, runtime, model, device, sampling, vocab_sizes):
        self.runtime, self.model, self.device = runtime, model, device
        self.sampling, self.vocab_sizes = sampling, vocab_sizes
        path = "neuroformer/simulation.py"
        nodes = [n for n in ast.parse(bodies[path]).body if isinstance(n, ast.FunctionDef) and n.name == "top_k_top_p_filtering"]
        require(len(nodes) == 1, "exact original filtering definition")
        ns = {"torch": runtime.torch, "F": runtime.F}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), ns)
        self.filtering = ns["top_k_top_p_filtering"]

    def __call__(self, state, features, position):
        r, s = self.runtime, self.sampling
        x = {name: r.torch.tensor([value], dtype=r.torch.long, device=self.device)
             for name, value in state.items() if name not in ("dt", "dt_prev", "interval")}
        for name in ("dt", "dt_prev", "interval"):
            x[name] = r.torch.tensor([state[name]], dtype=r.torch.float32, device=self.device)
        x.update(r.all_device(features, self.device))
        logits, _, _ = self.model(x, None)
        choices = []
        for name, top_p, temperature in (("id", s["top_p"], s["temperature"]),
                                          ("dt", s["top_p_dt"], s["temperature_dt"])):
            value = logits[name]
            require(tuple(value.shape) == (1, len(state["id"]), self.vocab_sizes[name]), "actual full native logits shape")
            value = value[:, position].clone()
            # Released ordering: filter, then divide temperature, then softmax.
            # The dt filter is independently selected here (explicit amendment).
            if s["top_k"] or top_p:
                value = self.filtering(value, top_k=s["top_k"], top_p=top_p)
            probabilities = r.F.softmax(value / temperature, dim=-1)
            draw = r.torch.multinomial(probabilities, num_samples=1) if s["sample"] else r.torch.topk(probabilities, k=1, dim=-1)[1]
            require(tuple(draw.shape) == (1, 1), "single selected token")
            choice = draw.detach().cpu().item()
            require(type(choice) is int and 0 <= choice < self.vocab_sizes[name], "selected integer token")
            choices.append(choice)
        return tuple(choices)


def produce(bodies, runtime, fitted, request, queries):
    """Consume all queries with no evaluator/ground-truth capability in this API.

    queries is an iterable of {row_id, features}; it must not be a dataset yielding
    (x,y). Native/runtime identity, observation provenance and process isolation
    are still required external gates. This is a component, not an ablation run.
    """
    source = source_receipt(bodies)
    request, support = admit_request(request, fitted)
    c, limits = fitted["config"], request["limits"]
    require(fitted["model"].config is c and fitted["model"].tokenizer is fitted["tokenizer"],
            "actual selected model/config/tokenizer object join")
    vocab, physical_ids, dt_ticks = vocabulary(fitted["tokenizer"], limits)
    require(request["sampling"]["top_k"] <= min(len(vocab[n]["itos"]) for n in ("ID", "dt")), "top-k vocabulary bound")
    si, st = vocab["ID"]["stoi"], vocab["dt"]["stoi"]
    rows = {r["id"]: r for r in request["support"]["evaluation"]}
    runtime.set_seed(request["seed"])
    model = fitted["model"].to(request["device"]).eval()
    step = NativeStep(bodies, runtime, model, request["device"], request["sampling"],
                      {"id": len(vocab["ID"]["itos"]), "dt": len(vocab["dt"]["itos"])})
    iterator = iter(queries)
    prediction = {k: [] for k in ("ID", "dt", "Trial", "Interval")}
    windows, calls = [], 0
    with runtime.torch.no_grad():
        for episode in request["episodes"]:
            events = []
            for row_id in episode["row_ids"]:
                row = rows[row_id]
                try:
                    query = next(iterator)
                except StopIteration:
                    require(False, "incomplete query support")
                require(type(query) is dict and set(query) == {"row_id", "features"} and query["row_id"] == row_id,
                        "exact ordered query with no labels")
                features = admit_features(query["features"], c, limits["max_feature_elements"])
                previous_ids, previous_dt, padding, selected = history_tokens(events, row["end_tick"], c.block_size.prev_id, vocab)
                prefix_ids, prefix_dt = [si["SOS"]], [0]
                termination, produced = "block_capacity_without_eos", 0
                for position in range(c.block_size.id - 1):
                    require(calls < limits["max_model_calls"], "model call bound at effect")
                    state = {"id": prefix_ids + [si["PAD"]] * (c.block_size.id - len(prefix_ids)),
                             "dt": prefix_dt + [st["PAD"]] * (c.block_size.id - len(prefix_dt)),
                             "pad": c.block_size.id - len(prefix_ids),
                             "id_prev": previous_ids, "dt_prev": previous_dt, "pad_prev": padding,
                             "interval": row["end_tick"] / 100, "trial": 0}
                    ix, tx = step(state, features, position)
                    calls += 1
                    if ix == si["EOS"]:
                        termination = "eos"
                        break
                    require(ix in physical_ids, "non-EOS special ID token is not silently accepted as termination")
                    require(tx in dt_ticks and 0 <= dt_ticks[tx] < 5, "generated offset must be a native current-window tick")
                    require(len(prediction["ID"]) < limits["max_events"], "complete event capacity before append")
                    neuron, offset = physical_ids[ix], dt_ticks[tx]
                    events.append((neuron, row["end_tick"] - 5 + offset))
                    for name, value in (("ID", neuron), ("dt", offset / 100), ("Trial", 0), ("Interval", native_endpoint(row["end_tick"]))):
                        prediction[name].append(value)
                    prefix_ids.append(ix)
                    prefix_dt.append(tx)
                    produced += 1
                windows.append({"row_id": row_id, "recording": row["recording"], "end_tick": row["end_tick"],
                                "episode": episode["id"], "history_events": len(selected),
                                "generated_events": produced, "termination": termination})
                # Only the immediately relevant generated window remains resident.
                events = [event for event in events if event[1] >= row["end_tick"] - 5]
    try:
        next(iterator)
    except StopIteration:
        pass
    else:
        require(False, "extra query support")
    return {"schema": "neuroformer_protected_rollout_result_v1", "profile": PROFILE,
            "predictions": prediction, "windows": windows, "model_calls": calls,
            "request": request, "source": source, "support": support,
            "all_windows_reached_eos": all(w["termination"] == "eos" for w in windows),
            "candidate_current_truth_accessed": False, "generated_only_history": True,
            "initial_history": "explicit empty generated buffer at every declared episode",
            "physical_isolation_qualified": False, "native_runtime_qualified": False,
            "original_run_or_ablation_mapping": None, "selected_figure6_metric": None,
            "paper_parity": False, "source_complete": False, "scientifically_qualified": False}

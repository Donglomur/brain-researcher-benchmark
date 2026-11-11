"""Inactive source-backed run composition. Import uses only standard-library code.

Historical/source-native and protected/source-amended conditions are distinct.
The runtime leaves must be bound to a separately qualified original environment;
inert controls of this caller do not confer scientific or execution authority.
"""
from __future__ import annotations
import ast
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
from types import SimpleNamespace

import native_dataset as native

HISTORICAL = "released_computational_path_10ms"
PROTECTED = "protected_support_source_amended_10ms"
PROSPECTIVE = "prospective_existing_bridge_5ms"
WIDER = ("simulation", "passive control", "variability", "geometry",
         "representation probing", "CEBRA", "training curves")
PROSPECTIVE_FAMILIES = ("blocked_speed", "blocked_neural", "held_session_speed", "blocked_joint")
PANEL_DESCRIPTOR = {"path": "PANEL.json", "bytes": 9886,
    "sha256": "6dae6f239a4c4d562457510f53edb0e9814553c312c4ce6aaaf9ad147f0c665f"}
require = native.require


def definition(bodies, path, name):
    nodes = [n for n in ast.parse(bodies[path], filename=path).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name]
    require(bool(nodes), "original definition missing: " + name)
    node = nodes[-1]
    lines = bodies[path].decode().splitlines(keepends=True)
    body = "".join(lines[node.lineno - 1:node.end_lineno]).encode()
    return {"path": path, "name": name, "line": node.lineno, "end_line": node.end_lineno,
            "definition_sha256": hashlib.sha256(body).hexdigest(),
            "file_sha256": hashlib.sha256(bodies[path]).hexdigest()}


def source_dependencies(bodies):
    refs = {name: definition(bodies, path, name) for path, names in {
        "neuroformer/datasets.py": ("load_visnav", "split_data_by_interval"),
        "neuroformer/data_utils.py": ("NFDataloader", "Tokenizer"),
        "neuroformer/model_neuroformer.py": ("Neuroformer", "ImprovedGRU", "NF_GRU", "load_model_and_tokenizer"),
        "neuroformer/trainer.py": ("Trainer", "TrainerConfig"),
        "neuroformer/simulation.py": ("generate_spikes", "decode_modality"),
        "neuroformer/analysis.py": ("compute_scores", "compute_scores_scikit"),
        "neuroformer/utils.py": ("set_seed", "get_attr"),
    }.items() for name in names}
    return {"revision": native.REVISION, "definitions": refs,
        "captured_configurations": list(native.CONFIGS),
        "unresolved_methods": {
            "lasso": "No original fitting recipe found in the 26 captured text bodies.",
            "glm": "No original fitting recipe found in the 26 captured text bodies.",
            "mlp": "mlp_only builds self.mlp but forward bypasses it; original run/config mapping absent.",
            "bidirectional_gru": "gru2_only selects ImprovedGRU (bidirectional); gru_only selects unidirectional NF_GRU. Original run/config mapping absent.",
            "fewshot": "Source loader takes floor(1% of randomly ordered train); training script still trains train_dataset. Neither actual pretrained/scratch fine-tuning nor 10% recipe is supplied.",
            "ablations": "Current/past/video/behavior/contrastive names do not establish exact original config/run identities."},
        "historical_behaviors": [
            "80% random training draw, ordered test complement, first floor1% training prefix for finetune.",
            "Training entrypoint uses test_dataset in a shuffled two-item demonstration forward before Trainer.train.",
            "Trainer uses the supplied test dataset for checkpoint selection.",
            "Nominal config min_eval_epoch50/eval_every5 are read on Trainer self with defaults0/1.",
            "One best_loss variable is reused across total and component checkpoint losses.",
            "Behavior decode supplies y to model; behavior projection heads only run inside targets!=None.",
            "Generation entrypoint uses finetune_dataset; get_interval overwrites the generated-history data argument.",
            "Plot Pearson uses the first200 decoded rows. Its scope is distinct from full-support evaluation.",
            "Teacher-forced token metrics, true-present interval helper, and predicted-present weighted helper are distinct."],
        "scientifically_qualified": False}


def build_matrix(source_root):
    root = Path(source_root)
    panel = json.loads(native.capture(root / "public", PANEL_DESCRIPTOR, 9886))
    bodies = native.source_snapshot(root)
    require(len(panel["cases"]) == 46 and len({c["id"] for c in panel["cases"]}) == 46, "exact46 slot roster")
    rows = []
    for case in panel["cases"]:
        prospective = case["family"] in PROSPECTIVE_FAMILIES
        conditions = [PROSPECTIVE] if prospective else [HISTORICAL, PROTECTED]
        cells = []
        for condition in conditions:
            if condition == PROSPECTIVE:
                metric_profile = "existing_5ms_finite_artifact"
            elif case["kind"] == "classification":
                metric_profile = "native_classification_mapping_unresolved"
            elif case["kind"] == "counts":
                metric_profile = "source_token_window_diagnostics" if condition == HISTORICAL else "protected_autoregressive_metric_unresolved"
            else:
                metric_profile = "released_plot_first200_pearson" if condition == HISTORICAL else "protected_full_support_pearson"
            holds = ["authentic complete inputs and provenance", "qualified runtime and containment",
                     "explicit run/config/seed/split identity", "full-support metric provenance"]
            if condition == PROSPECTIVE:
                holds += ["existing5ms bridge remains scientifically unqualified; no10ms conversion invented"]
            else:
                if case["cohort"] == "medial":
                    holds += ["no released medial configuration or authenticated medial run mapping"]
                if case["method"] in ("lasso", "glm", "mlp", "bidirectional_gru"):
                    holds += ["original method-specific recipe/config/run mapping"]
                if case["family"] == "fewshot_speed":
                    holds += ["actual paired pretrained/scratch finetuning and original budget recipe"]
                if case["family"] == "neural_ablation":
                    holds += ["original ablation config and neural metric branch mapping"]
                if case["kind"] == "classification":
                    holds += ["original class quantizer and classification configuration"]
                if condition == PROTECTED:
                    holds += ["physically isolated training/selection/query/target resources",
                              "nonoverlapping full neural/video context support"]
                    if case["kind"] == "counts":
                        holds += ["actual autoregressive current-token and generated-only-history producer absent"]
            cells.append({"id": case["id"] + "::" + condition, "condition": condition,
                "native_tick_us": 5000 if prospective else 10000,
                "historical_selection_uses_test": condition == HISTORICAL,
                "target_free_behavior_head_available": condition == PROTECTED and case["method"] == "neuroformer" and case["kind"] in ("regression", "joint"),
                "generated_history_repair_included": False, "holds": holds, "ready": False})
            cells[-1]["metric_profile"] = metric_profile
            cells[-1]["metric_selection_scientifically_qualified"] = False
        rows.append({"case": copy.deepcopy(case), "source_conditioned": not prospective, "cells": cells})
    require(sum(r["source_conditioned"] for r in rows) == 39, "exact39 source-conditioned slots")
    require(sum(len(r["cells"]) for r in rows) == 85, "39historical+39protected+7existing prospective")
    return {"schema": "neuroformer_run_matrix_v1", "rows": rows,
        "unique_case_slots": 46, "source_conditioned_slots": 39, "existing_prospective_slots": 7,
        "condition_cells": 85, "assignment_count_change": 0, "wider_families": list(WIDER),
        "source_dependencies": source_dependencies(bodies),
        "metric_provenance": {
            "released_plot_first200_pearson": {"source":"neuroformer_inference.py", "lines":[257,261],
                "source_sha256":hashlib.sha256(bodies["neuroformer_inference.py"]).hexdigest(),
                "call":"scipy.stats.pearsonr(predicted_first200,true_first200)",
                "adapter":"operator/run_metrics.py:grade_behavior", "paper_run_identity_qualified":False},
            "protected_full_support_pearson": {"source_formula":"same SciPy Pearson call",
                "support":"all admitted protected observations", "source_amended":True,
                "adapter":"operator/run_metrics.py:assess_behavior_runs", "historical_metric_parity":False},
            "source_token_window_diagnostics": {"definitions":[definition(bodies,"neuroformer/analysis.py",name)
                for name in ("compute_scores","compute_scores_scikit")],
                "truth_converter":"operator/run_metrics.py:window_truth", "adapter":"operator/run_metrics.py:grade_generation",
                "selected_figure6_branch":None,"teacher_forced_token_metrics_are_separate":True},
            "native_classification_mapping_unresolved": {"holds":["original quantizer","native class decoding","paper metric/support mapping"],
                "no_prospective25class_substitution":True},
            "protected_autoregressive_metric_unresolved": {"holds":["current-token autoregressive producer","generated-only history","metric/window mapping"],
                "teacher_forced_current_inputs_not_admitted_as_protected":True},
            "existing_5ms_finite_artifact": {"retained_roles":["public/metrics.py","operator/score.py"],
                "adapter":"operator/score.py:metric; biological_macro", "native_source_metric_parity_qualified":False}},
        "source_complete": False,
        "scientifically_qualified": False, "submission_ready": False}


def lookup(matrix, cell_id):
    found = [(row["case"], cell) for row in matrix["rows"] for cell in row["cells"] if cell["id"] == cell_id]
    require(len(found) == 1, "unknown or duplicate cell")
    return found[0]


def native_context_span(end_tick, recording_ticks):
    """Conservative union of exact released neural and 3-frame video inputs.

    Source neural windows use [t-10,t) in10ms ticks. Video normally ends t+5;
    initial windows clamp to the first three50ms frames. No early row is dropped.
    """
    native.integer(end_tick, "native endpoint", 0)
    native.integer(recording_ticks, "recording length")
    require(recording_ticks % 5 == 0 and end_tick % 5 == 0 and end_tick < recording_ticks,
            "exact native interval clock")
    frame_stop = min(max(end_tick // 5 + 1, 3), recording_ticks // 5)
    frame_start = max(0, frame_stop - 3)
    return min(max(0, end_tick - 10), frame_start * 5), max(end_tick, frame_stop * 5)


def admit_support(support, condition):
    require(set(support) == {"train", "selection", "evaluation"}, "all three support roles required")
    spans = {}
    all_ids = set()
    recording_lengths = {}
    for role, rows in support.items():
        require(type(rows) is list and rows, "nonempty full support role")
        spans[role] = {}
        physical_windows = set()
        for row in rows:
            require(set(row) == {"id", "recording", "end_tick", "recording_ticks"}, "support row keys")
            require(type(row["id"]) is str and row["id"] and type(row["recording"]) is str and row["recording"], "support identities")
            key = (role, row["id"])
            require(key not in all_ids, "duplicate support identity")
            all_ids.add(key)
            window_key = (row["recording"], row["end_tick"])
            require(window_key not in physical_windows, "duplicate physical window within role")
            physical_windows.add(window_key)
            require(recording_lengths.setdefault(row["recording"], row["recording_ticks"]) == row["recording_ticks"],
                    "inconsistent recording extent across roles")
            start, stop = native_context_span(row["end_tick"], row["recording_ticks"])
            spans[role].setdefault(row["recording"], []).append((start, stop, row["id"]))
    if condition == HISTORICAL:
        require(support["selection"] == support["evaluation"], "historical checkpoint selection uses original test support")
        return {"test_exposed_during_selection": True, "context_purge_applied": False}
    require(condition == PROTECTED, "native support cannot stand in for prospective5ms bridge")
    for left, right in (("train", "selection"), ("train", "evaluation"), ("selection", "evaluation")):
        require(not ({r["id"] for r in support[left]} & {r["id"] for r in support[right]}), "protected role identities overlap")
        for recording in spans[left].keys() & spans[right].keys():
            a, b = sorted(spans[left][recording]), sorted(spans[right][recording])
            i = j = 0
            while i < len(a) and j < len(b):
                require(a[i][1] <= b[j][0] or b[j][1] <= a[i][0], "protected neural/video contexts overlap")
                if a[i][1] <= b[j][1]: i += 1
                else: j += 1
    return {"test_exposed_during_selection": False, "full_contexts_nonoverlapping": True,
            "physical_isolation_qualified": False}


def trainer_call(bodies):
    tree = ast.parse(bodies["neuroformer_train.py"])
    found = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and
             any(isinstance(t, ast.Name) and t.id == "tconf" for t in n.targets)]
    require(len(found) == 1 and isinstance(found[0], ast.Call), "unique original TrainerConfig call")
    return compile(ast.Expression(found[0]), "neuroformer_train.py", "eval")


def admit_native_geometry(dataset, cohort, ticks):
    require(dataset.dataset == cohort and dataset.dt == .01 and dataset.window == .05 and
            dataset.window_prev == .05 and dataset.frame_window == .15 and dataset.dt_frames is None,
            "actual source dataset context geometry")
    require(tuple(dataset.data["ID"].shape) == ({"medial":1905,"lateral":2022}[cohort], ticks),
            "full native original neuron/time shape")


def admit_native_dataset(dataset, rows, cohort):
    """Bind actual native dataset metadata to its full declared ordered support."""
    require(len(dataset) == len(rows) > 0 and len(dataset.t) == len(rows), "complete actual native dataset length")
    require(len({r["recording"] for r in rows}) == 1, "one original VisNav recording per native dataset")
    ticks = rows[0]["recording_ticks"]
    admit_native_geometry(dataset, cohort, ticks)
    encode = lambda x: struct.unpack("<f", struct.pack("<f", float(x)))[0]
    require([encode(x) for x in dataset.t] == [encode(r["end_tick"] * .01) for r in rows],
            "actual dataset interval order matches declared support")


def training_constants(bodies):
    names = {"MAX_EPOCHS", "BATCH_SIZE", "SHUFFLE"}
    values = {}
    for node in ast.parse(bodies["neuroformer_train.py"]).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in names:
                values[name] = eval(compile(ast.Expression(node.value), "neuroformer_train.py", "eval"), {"__builtins__": {}}, {})
    require(set(values) == names, "exact original training constants")
    return values


class ReleasedCalls:
    """Actual model/trainer/inference calls with explicit native runtime bindings.

    Runtime must supply original Neuroformer, TrainerConfig, Trainer,
    load_model_and_tokenizer, decode_modality, generate_spikes, set_seed, NumPy,
    DataLoader, all_device and Torch. Source/native identity and sandbox qualification remain
    external holds. Engineering tests supply inert leaves explicitly.
    """
    def __init__(self, bodies, runtime):
        self.bodies = bodies
        self.runtime = runtime
        self._trainer_call = trainer_call(bodies)
        self.constants = training_constants(bodies)

    def replay_source_split(self, train, selection, original_interval_count):
        chosen = self.runtime.np.random.choice(original_interval_count, int(original_interval_count * .8), replace=False)
        chosen = [int(i) for i in chosen]
        chosen_set = set(chosen)
        require(len(chosen) == len(chosen_set) == int(original_interval_count * .8) and
                all(0 <= i < original_interval_count for i in chosen), "exact native draw domain")
        complement = [i for i in range(original_interval_count) if i not in chosen_set]
        require([round(float(t) * 100) for t in train.t] == [i * 5 for i in chosen] and
                [round(float(t) * 100) for t in selection.t] == [i * 5 for i in complement],
                "actual source RNG draw must match complete ordered train/test support")

    def fit(self, *, config, tokenizer, train, selection, seed, cohort, output_directory,
            condition, original_interval_count, title):
        require(condition in (HISTORICAL, PROTECTED), "native fit condition")
        native.integer(seed, "explicit seed", 0)
        require(seed < 2**32 and cohort in ("medial", "lateral"), "seed/cohort")
        require(Path(output_directory).is_absolute(), "explicit operator-owned absolute output directory")
        require(type(title) is str and title, "explicit run title")
        native.integer(original_interval_count, "original interval count")
        r = self.runtime
        r.set_seed(seed)
        if condition == HISTORICAL:
            # Native preparation isolates its draw; replay original global NumPy
            # consumption before model construction. No seed/default is invented.
            self.replay_source_split(train, selection, original_interval_count)
            next(iter(train))  # Original pre-model dataset demonstration, including failures.
        config.id_vocab_size = tokenizer.ID_vocab_size
        model = r.Neuroformer(config, tokenizer)
        if condition == HISTORICAL:
            x, y = next(iter(r.DataLoader(selection, batch_size=2, shuffle=True, num_workers=0)))
            model(x, y)  # Original test demonstration consumes RNG and accesses y.

        def no_telemetry_config(**kwargs):
            # Explicit apparatus amendment, not an unreported recipe default.
            kwargs["use_wandb"] = False
            return r.TrainerConfig(**kwargs)

        ns = {"TrainerConfig": no_telemetry_config, **self.constants,
            "train_dataset": train, "config": config,
            "CKPT_PATH": output_directory,
            "args": SimpleNamespace(dist=False, dataset=cohort, title=title)}
        tconf = eval(self._trainer_call, {"__builtins__": {"len": len}}, ns)
        trainer = r.Trainer(model, train, selection, tconf, config)
        trainer.train()
        if condition == PROTECTED:
            loaded_config, loaded_tokenizer, selected_model = r.load_model_and_tokenizer(output_directory)
        else:
            loaded_config, loaded_tokenizer, selected_model = config, tokenizer, model
        return {"model": selected_model, "config": loaded_config, "tokenizer": loaded_tokenizer,
            "condition": condition, "seed": seed, "cohort": cohort,
            "output_directory": output_directory, "original_interval_count": original_interval_count,
            "selected_checkpoint_loaded": condition == PROTECTED,
            "historical_test_demo": condition == HISTORICAL,
            "amendments": ["network telemetry disabled", "single-process original Trainer branch"],
            "native_qualified": False, "paper_run_identity_qualified": False}

    def historical_behavior(self, fitted, dataset):
        require(fitted["condition"] == HISTORICAL and fitted["selected_checkpoint_loaded"], "historical decoder needs selected checkpoint and condition")
        out = {}
        # Actual inference entrypoint overwrites CLI modes with these three.
        for mode in ("speed", "phi", "th"):
            variable = getattr(fitted["config"].modalities.behavior.variables, mode)
            out[mode] = self.runtime.decode_modality(fitted["model"], dataset, modality=mode,
                block_type="behavior", objective=variable.objective)
        return out

    def historical_generation(self, fitted, finetune_dataset, *, true_past):
        require(fitted["condition"] == HISTORICAL and fitted["selected_checkpoint_loaded"] and type(true_past) is bool, "explicit historical history flag")
        c = fitted["config"]
        return self.runtime.generate_spikes(fitted["model"], finetune_dataset, c.window.curr,
            c.window.prev, fitted["tokenizer"], sample=True, top_p=.95, top_p_t=.95,
            temp=1., temp_t=1., frame_end=0, true_past=true_past, get_dt=True,
            gpu=True, pred_dt=True, plot_probs=False)

    def historical_inference(self, fitted, train, test, finetune, *, true_past):
        """Actual released computational ordering; retain its history defect.

        Plot/CSV/pickle serialization is omitted from this in-memory producer.
        It does not claim an authenticated original author's seed/run identity.
        """
        require(fitted["condition"] == HISTORICAL and type(true_past) is bool, "explicit historical inference condition")
        r = self.runtime
        r.set_seed(fitted["seed"])
        config, tokenizer, model = r.load_model_and_tokenizer(fitted["output_directory"])
        self.replay_source_split(train, test, fitted["original_interval_count"])
        admit_native_geometry(finetune, fitted["cohort"], train.data["ID"].shape[1])
        require(len(finetune) == len(finetune.t) == int(len(train) * .01) and
                list(finetune.t) == list(train.t[:int(len(train) * .01)]), "exact original floor1percent prefix for generation")
        next(iter(train))
        config.id_vocab_size = tokenizer.ID_vocab_size
        x, y = next(iter(r.DataLoader(test, batch_size=2, shuffle=True, num_workers=0)))
        model(x, y)
        active = dict(fitted, model=model, config=config, tokenizer=tokenizer, selected_checkpoint_loaded=True)
        generated = self.historical_generation(active, finetune, true_past=true_past)
        model.load_state_dict(r.torch.load(str(Path(fitted["output_directory"]) / "model.pt"), map_location=r.torch.device("cpu")))
        return {"generation": generated, "behavior": self.historical_behavior(active, test),
                "true_past": true_past, "generated_history_override_defect_preserved": True,
                "figure6_metric_selected": None, "source_complete": False, "scientifically_qualified": False}

    def protected_behavior(self, fitted, query_batches, modes, *, expected_ids, max_rows):
        require(fitted["condition"] == PROTECTED, "separate protected fitted model required")
        require(type(modes) is tuple and modes and set(modes) <= {"speed", "phi", "th"}, "behavior targets")
        require(type(expected_ids) is list and 0 < len(expected_ids) == len(set(expected_ids)) and
                type(max_rows) is int and len(expected_ids) <= max_rows, "bounded full protected support")
        expected_ids = tuple(expected_ids)
        model = fitted["model"]
        model.eval()
        device = self.runtime.torch.cuda.current_device() if self.runtime.torch.cuda.is_available() else "cpu"
        model.to(device)
        outputs = []
        consumed = 0
        with self.runtime.torch.no_grad():
            for batch in query_batches:
                require(set(batch) == {"row_ids", "x"}, "protected query contains labels or unspecified payload")
                require(type(batch["row_ids"]) is list and 0 < len(batch["row_ids"]) <= max_rows - consumed,
                        "protected batch capacity before model invocation")
                n = len(batch["row_ids"])
                require(tuple(batch["row_ids"]) == expected_ids[consumed:consumed+n], "ordered complete protected query identities")
                x = batch["x"]
                require(set(x) <= {"id", "dt", "pad", "id_prev", "dt_prev", "pad_prev", "interval", "trial",
                    "modalities", "frames", "cid", "pid"}, "unexpected protected feature field")
                for variables in x.get("modalities", {}).values():
                    require(not (set(variables) & set(modes)), "prediction target appears as a modality input")
                x = self.runtime.all_device(x, device)
                _, features, _ = model(x, None)
                mean = features["last_layer"].mean(dim=1)
                values = {}
                for mode in modes:
                    value = model.modality_projection_heads["behavior"][mode](mean)
                    require(tuple(value.shape) == (n, 1), "protected head shape before CPU capture")
                    values[mode] = value.detach().cpu()
                outputs.append({"row_ids": list(batch["row_ids"]), "values": values})
                consumed += n
        require(consumed == len(expected_ids), "full protected query support consumed")
        return outputs


def dispatch_native(matrix, cell_id, calls, job, providers):
    """Run one explicitly selected cell; preserve all other matrix obligations.

    Providers are operator-owned capabilities. In protected mode, evaluation
    queries are not requested until training/checkpoint selection has completed;
    targets are never passed to this producer. Physical isolation is not proved
    by Python callback separation and remains a mandatory external gate.
    """
    case, cell = copy.deepcopy(lookup(matrix, cell_id))
    job = copy.deepcopy(job)
    condition = cell["condition"]
    require(condition != PROSPECTIVE, "existing5ms branch must use its distinct bridge caller")
    require(set(job) == {"run_id", "seed", "config_identity", "run_provenance", "support", "output_directory", "original_interval_count", "limits", "historical_true_past"}, "explicit job identity")
    require(type(job["run_id"]) is str and job["run_id"], "explicit run identity")
    native.integer(job["seed"], "seed", 0)
    require(job["seed"] < 2**32 and Path(job["output_directory"]).is_absolute(), "seed/output path admission")
    native.integer(job["original_interval_count"], "original interval count")
    require(type(job["historical_true_past"]) is bool if condition == HISTORICAL else job["historical_true_past"] is None,
            "explicit source history flag; no protected rollout substitute")
    require(set(job["limits"]) == {"max_support_rows", "max_prediction_rows", "max_native_intervals"}, "explicit caller resource bounds")
    for value in job["limits"].values(): native.integer(value, "caller resource bound")
    require(set(job["support"]) == {"train", "selection", "evaluation"}, "full support roles")
    require(sum(len(v) for v in job["support"].values()) <= job["limits"]["max_support_rows"], "support capacity")
    require(len(job["support"]["evaluation"]) <= job["limits"]["max_prediction_rows"] and
            job["original_interval_count"] <= job["limits"]["max_native_intervals"], "prediction/native interval capacity")
    for key in ("config_identity", "run_provenance"):
        require(type(job[key]) is dict and set(job[key]) == {"path", "bytes", "sha256"}, "exact provenance descriptor")
        native.relative(job[key]["path"])
        native.integer(job[key]["bytes"], "provenance bytes")
        require(type(job[key]["sha256"]) is str and len(job[key]["sha256"]) == 64 and
                all(c in "0123456789abcdef" for c in job[key]["sha256"]), "provenance hash")
    # Unsupported methods are retained in the matrix, not silently substituted.
    require(case["method"] == "neuroformer" and case["kind"] in ("regression", "joint"),
            "original method/quantizer/ablation/fewshot recipe remains unresolved")
    if condition == HISTORICAL:
        require(case["cohort"] == "lateral", "no authenticated released medial run/configuration")
    support_receipt = admit_support(job["support"], condition)
    configuration = providers.configuration(copy.deepcopy(job["config_identity"]), copy.deepcopy(job["run_provenance"]))
    require(configuration["cohort"] == case["cohort"], "configuration cohort identity")
    require(configuration["config_status"] == ("released_lateral_config" if case["cohort"] == "lateral"
            else "lateral_config_on_medial_unqualified"), "explicit source configuration status")
    c = configuration["config"]
    require(c.resolution.dt == .01 and c.window.curr == .05 and c.window.prev == .05 and c.window.frame == .15,
            "native source clocks required")
    require(not c.mlp_only and not c.gru_only and not c.gru2_only, "no baseline flag relabelling")
    modes = ("speed", "phi", "th") if case["kind"] == "joint" else ("speed",)
    for mode in modes:
        variable = getattr(c.modalities.behavior.variables, mode)
        require(variable.predict is True and variable.objective == "regression", "original behavior head configuration")
    train = providers.training(copy.deepcopy(job["support"]["train"]))
    selection = providers.selection(copy.deepcopy(job["support"]["selection"]))
    admit_native_dataset(train, job["support"]["train"], case["cohort"])
    admit_native_dataset(selection, job["support"]["selection"], case["cohort"])
    require(job["original_interval_count"] == train.data["ID"].shape[1] // 5,
            "full original native interval population")
    fitted = calls.fit(config=c, tokenizer=configuration["tokenizer"], train=train, selection=selection,
        seed=job["seed"], cohort=case["cohort"], output_directory=job["output_directory"],
        condition=condition, original_interval_count=job["original_interval_count"], title=job["run_id"])
    if condition == HISTORICAL:
        prefix = copy.deepcopy(job["support"]["train"][:int(len(train) * .01)])
        finetune = providers.historical_finetune(prefix)
        source_inference = calls.historical_inference(fitted, train, selection, finetune,
            true_past=job["historical_true_past"])
        predictions = source_inference["behavior"]
    else:
        source_inference = None
        predictions = calls.protected_behavior(fitted, providers.protected_queries(copy.deepcopy(job["support"]["evaluation"])), modes,
            expected_ids=[r["id"] for r in job["support"]["evaluation"]], max_rows=job["limits"]["max_prediction_rows"])
        require([i for batch in predictions for i in batch["row_ids"]] ==
                [r["id"] for r in job["support"]["evaluation"]], "complete ordered protected output support")
    return {"cell_id": cell_id, "condition": condition, "predictions": predictions, "support": support_receipt,
            "historical_inference": source_inference,
            "source_complete": False, "scientifically_qualified": False, "paper_parity": False}


def dispatch_prospective(matrix, bridge_query, program, runner, bridge_api):
    """Call the existing distinct5ms programme through its operator-owned runner.

    This is explicit routing, not a native-to5ms converter. The existing bridge
    admission, candidate execution and scorer remain required real runtime leaves.
    """
    # The existing ABI requires ALL46 cases. Do not invent a per-case5ms query
    # or weaken its complete-submission check to just the seven prospective rows.
    bridge_query = copy.deepcopy(bridge_query)
    bridge_api.query(copy.deepcopy(bridge_query), production=True)
    require([c["definition"] for c in bridge_query["cases"]] == [r["case"] for r in matrix["rows"]],
            "exact inherited46 case definitions")
    submitted = runner(program=program, query=copy.deepcopy(bridge_query))
    submitted = copy.deepcopy(submitted)
    bridge_api.submission(copy.deepcopy(submitted), copy.deepcopy(bridge_query))
    selected = [r["case"]["id"] for r in matrix["rows"] if not r["source_conditioned"]]
    return {"condition": PROSPECTIVE, "full_submission": submitted,
            "selected_prospective_case_ids": selected, "native_to5ms_conversion_performed": False,
            "source_complete": False, "scientifically_qualified": False}

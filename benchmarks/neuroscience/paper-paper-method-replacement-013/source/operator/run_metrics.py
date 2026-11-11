"""Native metric assembly/provenance, distinct from the existing5ms scorer.

Only standard-library imports. Native numerical/model execution remains a future
operator action; engineering tests explicitly replace numerical leaves.
"""
import ast
import collections
import copy
import hashlib
import math
import numbers
import struct

from run_composition import HISTORICAL, PROTECTED, require, definition


def finite_scalar(value):
    require(type(value) in (int, float) and math.isfinite(value), "finite scalar metric input")
    return float(value)


def assemble_behavior_packet(result, expected, *, max_values):
    """Bind actual decoder frames or protected tensors to ordered native support.

    Historical intervals are compared to the exact float32 endpoint encoding
    used by NFDataloader. Only single-recording, trial-zero VisNav support is
    admitted on that path. Protected batches use explicit returned row IDs.
    All tensor/frame lengths are checked before tolist()/detachment allocations.
    """
    require(type(max_values) is int and max_values > 0, "explicit scalar capture bound")
    require(result["cell_id"] == expected["cell_id"] and result["condition"] == expected["condition"], "run/metric condition identity")
    rows = expected["support"]
    modes = expected["modes"]
    require(type(rows) is list and rows and type(modes) is list and modes and
            len(set(modes)) == len(modes) and set(modes) <= {"speed", "phi", "th"}, "full native behavior schema")
    require(len(rows) * len(modes) <= max_values, "full scalar output capture capacity")
    ids = [r["id"] for r in rows]
    require(len(set(ids)) == len(ids), "unique complete row identities")
    values = {mode: [] for mode in modes}
    if expected["condition"] == HISTORICAL:
        require(len({r["recording"] for r in rows}) == 1, "original VisNav decoder has no recording-ID column")
        canonical = [struct.unpack("<f", struct.pack("<f", r["end_tick"] * .01))[0] for r in rows]
        require(len(set(canonical)) == len(canonical), "float32 source endpoints do not uniquely identify windows")
        for mode in modes:
            frame = result["predictions"][mode]
            require(len(frame) == len(rows), "full original decoder output rows")
            for column in ("interval", "trial", f"behavior_{mode}_value"):
                require(len(frame[column]) == len(rows), "full original decoder column")
            intervals = frame["interval"].tolist()
            trials = frame["trial"].tolist()
            require(intervals == canonical and all(type(t) in (int, float) and t == 0 for t in trials),
                    "exact original float32 interval/trial alignment")
            values[mode] = [finite_scalar(v) for v in frame[f"behavior_{mode}_value"].tolist()]
            # frame['true'] is deliberately not consumed by candidate admission.
    else:
        require(expected["condition"] == PROTECTED, "no native/5ms metric substitution")
        packets = result["predictions"]
        require(type(packets) is list and 0 < len(packets) <= len(rows), "bounded complete batch roster")
        output_ids = []
        for batch in packets:
            require(set(batch) == {"row_ids", "values"} and type(batch["row_ids"]) is list,
                    "protected tensor packet fields")
            n = len(batch["row_ids"])
            require(n > 0 and len(output_ids) + n <= len(rows), "complete predicted batch capacity")
            require(set(batch["values"]) == set(modes), "complete protected head outputs")
            output_ids.extend(batch["row_ids"])
            for mode in modes:
                tensor = batch["values"][mode]
                require(tuple(tensor.shape) in ((n,), (n, 1)), "exact protected head output shape")
                detached = tensor.detach().cpu().reshape(-1).tolist()
                require(len(detached) == n, "protected scalar conversion width")
                values[mode].extend(finite_scalar(v) for v in detached)
        require(output_ids == ids, "complete ordered protected tensor support")
    return {"cell_id": result["cell_id"], "row_ids": ids, "values": values}


def assess_behavior_runs(results, expected, target_loader, pearsonr, *, max_values):
    """Actual native outputs → immutable scalar admission → delayed private metric."""
    expected = copy.deepcopy(expected)
    require(type(results) is list and len(results) == len(expected) > 0, "complete selected run roster")
    require(type(max_values) is int and max_values > 0 and
            sum(len(s["support"]) * len(s["modes"]) for s in expected) <= max_values,
            "aggregate complete output scalar bound")
    packets = [assemble_behavior_packet(r, s, max_values=max_values) for r, s in zip(results, expected)]
    specs = [{"cell_id":s["cell_id"], "row_ids":[r["id"] for r in s["support"]],
              "modes":s["modes"], "condition":s["condition"]} for s in expected]
    return grade_behavior(packets, specs, target_loader, pearsonr)


def freeze_behavior_packets(packets, expected):
    """Admit ALL selected candidate packets before any target-loader callback.

    Values here are already detached scalar lists. No native tensor or mutable
    candidate object survives the admission boundary. This does not establish
    filesystem/process isolation or authenticate an independently chosen cohort.
    """
    require(type(packets) is list and len(packets) == len(expected) > 0, "complete selected packet roster")
    frozen = []
    for packet, spec in zip(packets, expected):
        require(set(packet) == {"cell_id", "row_ids", "values"}, "candidate packet fields")
        require(packet["cell_id"] == spec["cell_id"] and packet["row_ids"] == spec["row_ids"], "full ordered candidate identities")
        require(len(packet["row_ids"]) == len(set(packet["row_ids"])) > 0, "unique nonempty support")
        require(set(packet["values"]) == set(spec["modes"]), "complete behavioral target roster")
        values = {}
        for mode in spec["modes"]:
            seq = packet["values"][mode]
            require(type(seq) is list and len(seq) == len(packet["row_ids"]), "complete behavioral scalar support")
            values[mode] = tuple(finite_scalar(x) for x in seq)
        frozen.append({"cell_id": packet["cell_id"], "row_ids": tuple(packet["row_ids"]), "values": values})
    return frozen


def grade_behavior(packets, expected, target_loader, pearsonr):
    """Evaluate the literal historical first200 Pearson and protected full support.

    ``pearsonr`` is the SciPy callable used by the original entrypoint, or a named
    inert leaf in engineering controls. Undefined native r/p are represented as
    null, never fabricated zeros. Both conditions report their actual n.
    """
    expected = copy.deepcopy(expected)
    frozen = freeze_behavior_packets(packets, expected)
    targets = target_loader()  # First target access is after whole candidate admission.
    require(type(targets) is list and len(targets) == len(expected), "full private target roster")
    results = []
    for candidate, spec, target in zip(frozen, expected, targets):
        require(set(target) == {"cell_id", "row_ids", "values"}, "target fields")
        require(target["cell_id"] == spec["cell_id"] and target["row_ids"] == spec["row_ids"], "exact target support")
        require(spec["condition"] in (HISTORICAL, PROTECTED), "native condition")
        require(set(target["values"]) == set(spec["modes"]), "complete private target variables")
        n = min(200, len(spec["row_ids"])) if spec["condition"] == HISTORICAL else len(spec["row_ids"])
        require(n >= 2, "Pearson requires at least two selected observations")
        values = {}
        for mode in spec["modes"]:
            raw_truth = target["values"][mode]
            require(type(raw_truth) is list and len(raw_truth) == len(spec["row_ids"]), "complete private scalar support")
            truth = [finite_scalar(x) for x in raw_truth]
            pred = candidate["values"][mode]
            r, p = pearsonr(list(pred[:n]), truth[:n])  # Literal original argument order.
            values[mode] = {"pearson_r": float(r) if math.isfinite(float(r)) else None,
                            "pearson_p": float(p) if math.isfinite(float(p)) else None,
                            "n": n, "total_admitted_support": len(truth)}
        results.append({"cell_id": spec["cell_id"], "condition": spec["condition"], "values": values,
            "metric_profile": "released_plot_first200_pearson" if spec["condition"] == HISTORICAL else "protected_full_support_pearson",
            "paper_result_reproduced": False, "scientifically_qualified": False})
    return {"schema": "neuroformer_native_behavior_metrics_v1", "rows": results,
            "all_candidates_admitted_before_targets": True, "source_complete": False,
            "scientifically_qualified": False}


def scalar_tensor(value):
    """Actual scalar-tensor conversion; inert tensor leaves implement item()."""
    scalar = value.item()
    return finite_scalar(scalar)


def integer_id(value):
    require(type(value) is int and value >= 0, "nonnegative integral neural ID")
    return value


def window_truth(dataset, tokenizer, *, max_windows, max_tokens):
    """Capture per-window truth from actual original dataset items.

    This mirrors generate_spikes' y['id'][:T_id-pad] slice, then removes named
    special vocabulary tokens. Each true event retains its OWN interval/trial.
    It never zips generator prediction metadata onto the unrelated raw true list.
    This defines an explicitly named source-token diagnostic; paper Figure6
    event/window/truncation equivalence remains unqualified.
    """
    require(type(max_windows) is int and type(max_tokens) is int and max_windows > 0 and max_tokens > 0, "explicit truth capture bounds")
    require(0 < len(dataset) <= max_windows, "full native truth window capacity")
    windows = []
    identities = set()
    total = 0
    itos = tokenizer.itos["ID"]
    for index in range(len(dataset)):
        x, y = dataset[index]
        interval = scalar_tensor(x["interval"])
        trial_float = scalar_tensor(x["trial"])
        require(trial_float.is_integer() and trial_float >= 0, "source trial identity")
        trial = int(trial_float)
        key = (interval, trial)
        require(key not in identities, "duplicate original window identity")
        identities.add(key)
        raw_codes = y["id"]
        width = len(raw_codes)
        require(raw_codes.ndim == 1 and width == dataset.config.block_size.id, "original generator T_id matches dataset token width")
        require(total + width <= max_tokens, "complete native token capture capacity")
        codes = raw_codes.detach().cpu().flatten().tolist()
        require(len(codes) == width, "native token conversion width")
        pad_float = scalar_tensor(x["pad"])
        require(pad_float.is_integer() and 0 <= pad_float <= len(codes), "source pad domain")
        end = len(codes) - int(pad_float)
        ids = []
        for code in codes[:end]:
            require(type(code) is int and code in itos, "known native vocabulary code")
            decoded = itos[code]
            if decoded in ("SOS", "EOS", "PAD"):
                continue
            require(isinstance(decoded, numbers.Integral) and not isinstance(decoded, bool), "integral original neuron vocabulary")
            ids.append(integer_id(int(decoded)))
        total += len(codes)
        require(total <= max_tokens, "complete native token capture capacity")
        windows.append({"interval": interval, "trial": trial, "ids": tuple(ids)})
    return tuple(windows)


def freeze_generation(prediction, *, max_events):
    """Freeze only the aligned PREDICTED columns before opening evaluator truth."""
    require(type(max_events) is int and max_events > 0, "explicit event capacity")
    required = ("ID", "dt", "Trial", "Interval")
    require(all(k in prediction for k in required), "all source predicted columns")
    require(all(type(prediction[k]) in (list, tuple) for k in required), "bounded source predicted sequences required")
    n = len(prediction["ID"])
    require(n <= max_events and all(len(prediction[k]) == n for k in required), "aligned complete predicted events")
    columns = {k: tuple(prediction[k]) for k in required}
    frozen = []
    for i in range(n):
        neural_id = integer_id(columns["ID"][i])
        trial = integer_id(columns["Trial"][i])
        interval = finite_scalar(columns["Interval"][i])
        dt = finite_scalar(columns["dt"][i])
        require(dt >= 0, "native time offset")
        frozen.append((neural_id, dt, trial, interval))
    # prediction['true'] and prediction['time'] are intentionally never consumed.
    return tuple(frozen)


def original_metric_functions(bodies, runtime):
    """Compile and call the two exact original helper definitions without imports."""
    path = "neuroformer/analysis.py"
    names = ("compute_scores", "compute_scores_scikit")
    effective = {n.name: n for n in ast.parse(bodies[path]).body if isinstance(n, ast.FunctionDef)}
    ns = {"collections": collections, "np": runtime.np,
          "precision_recall_fscore_support": runtime.precision_recall_fscore_support}
    for name in names:
        exec(compile(ast.Module(body=[effective[name]], type_ignores=[]), path, "exec"), ns)
    return {name: ns[name] for name in names}


def grade_generation(prediction, truth_loader, bodies, runtime, *, max_events, max_windows):
    """Admit predictions, obtain independently bound window truth, call both ABIs."""
    require(type(max_windows) is int and max_windows > 0, "explicit complete-window capacity")
    frozen = freeze_generation(prediction, max_events=max_events)
    windows = truth_loader()
    require(type(windows) is tuple and 0 < len(windows) <= max_windows, "nonempty complete native window truth")
    identities = set()
    total = 0
    for window in windows:
        require(type(window) is dict and set(window) == {"interval", "trial", "ids"}, "exact evaluator window keys")
        interval = finite_scalar(window["interval"])
        trial = integer_id(window["trial"])
        require(type(window["ids"]) is tuple, "bounded immutable evaluator ID sequence")
        total += len(window["ids"])
        require(total <= max_events, "complete evaluator event capacity before materialization")
        for neural_id in window["ids"]: integer_id(neural_id)
        identities.add((interval, trial))
    require(len(identities) == len(windows), "unique evaluator windows")
    true_rows = []
    for window in windows:
        for neural_id in window["ids"]:
            true_rows.append({"ID": integer_id(neural_id), "Interval": window["interval"], "Trial": window["trial"]})
    pred_rows = []
    for neural_id, dt, trial, interval in frozen:
        require((interval, trial) in identities, "predicted event outside independently bound windows")
        pred_rows.append({"ID": neural_id, "Interval": interval, "Trial": trial})
    true = runtime.pd.DataFrame(true_rows, columns=["ID", "Interval", "Trial"])
    pred = runtime.pd.DataFrame(pred_rows, columns=["ID", "Interval", "Trial"])
    helpers = original_metric_functions(bodies, runtime)
    branches = {name: dict(function(true, pred)) for name, function in helpers.items()}
    return {"schema": "neuroformer_source_token_window_diagnostics_v1", "branches": branches,
        "complete_windows": len(windows), "true_present_windows": sum(bool(w["ids"]) for w in windows),
        "predicted_present_windows": len({(i, t) for _, _, t, i in frozen}),
        "truth_source": "per-window original dataset y[:T_id-pad], vocabulary decoded and named special tokens removed",
        "raw_generator_true_alignment_used": False,
        "metric_provenance": {name: definition(bodies, "neuroformer/analysis.py", name) for name in helpers},
        "empty_branch_dictionary_preserved": True, "selected_paper_figure6_metric": None,
        "source_complete": False, "scientifically_qualified": False}

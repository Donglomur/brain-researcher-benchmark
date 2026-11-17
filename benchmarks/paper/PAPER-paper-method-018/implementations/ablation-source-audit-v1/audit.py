"""Inspect the published ablation route as text; never import or execute it.

This is a source-lineage extractor, not a model runner or benchmark scorer.
It accepts the pinned public notebook JSON and three Python source files.
The public sources were retrieved through commit-specific jsDelivr URLs.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path


SOURCE_COMMIT = "421b5eef321cac3d1c1279759e0f6b638068b021"
SOURCE_FILES = (
    "Reproduce_figures/SupTable_Ablation_experiments.ipynb",
    "DataLoader.py", "model_trainer.py", "GLMTransformer.py",
)


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def numeric(node):
    """Evaluate only bounded numeric literals and elementary arithmetic."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        result = node.value
    elif isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult):
        left, right = numeric(node.left), numeric(node.right)
        result = {ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                  ast.Mult: lambda: left * right}[type(node.op)]()
    else:
        raise AuditError("unsupported numeric source expression")
    require(abs(result) <= 10**9, "numeric source expression exceeds inspection bound")
    return result


def parse_cell(source):
    # IPython line magics are documentary text here, never executed.
    cleaned = "\n".join("" if line.lstrip().startswith(("%", "!")) else line
                        for line in source.splitlines())
    try:
        return ast.parse(cleaned)
    except SyntaxError as exc:
        raise AuditError("notebook cell cannot be inspected as Python") from exc


def documentary_notebook(text):
    """Read the existing code-only derivative without inventing notebook outputs."""
    require(f"# Original commit {SOURCE_COMMIT};" in text,
            "documentary derivative does not declare the expected upstream revision")
    parts = re.split(r"^# Original code cell ([0-9]+)\s*$", text, flags=re.MULTILINE)
    require(len(parts) > 1, "missing documentary cell labels")
    labels = parts[1::2]
    require(len(labels) == len(set(labels)), "duplicate documentary cell labels")
    return {"cells": [{"cell_type": "code", "source": source,
                        "source_cell_label": "cached-cell:" + label}
                       for label, source in zip(labels, parts[2::2])]}


def calls(tree, name):
    return sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and ast.unparse(n.func) == name), key=lambda n: (n.lineno, n.col_offset))


def assignments(tree, target):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
            and any(ast.unparse(t) == target for t in n.targets)]


def one(items, label):
    require(len(items) == 1, f"expected one {label}, found {len(items)}")
    return items[0]


def method(tree, class_name, name):
    cls = one([n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == class_name], class_name)
    return one([n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == name], f"{class_name}.{name}")


def literal_kwargs(call):
    result = {}
    for kw in call.keywords:
        require(kw.arg is not None, "expanded source keyword arguments require manual inspection")
        try:
            result[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, TypeError):
            result[kw.arg] = {"expression": ast.unparse(kw.value)}
    return result


def displayed_summary(cell):
    """Extract rounded historical table strings, never treat them as a rerun."""
    text = ""
    for output in cell.get("outputs", []):
        raw = output.get("text", "")
        if isinstance(raw, list) and all(isinstance(s, str) for s in raw):
            text += "".join(raw)
        elif isinstance(raw, str):
            text += raw
    columns = ["full_model", "without_encoder", "without_coupling",
               "without_post_spike", "rnn"]
    rows = []
    for line in text.splitlines():
        fields = line.split("\t")
        if not fields or not re.fullmatch(r"Data [0-9]+", fields[0]):
            continue
        require(len(fields) == 6, "unexpected displayed ablation table width")
        row = {"dataset_row_one_based": int(fields[0].split()[1]), "values": {}}
        for name, value in zip(columns, fields[1:]):
            match = re.fullmatch(r"([0-9]+\.[0-9]+) \(([0-9]+\.[0-9]+)\)", value)
            require(match is not None, "unexpected displayed ablation numeric format")
            row["values"][name] = {"printed_mean": match[1],
                                    "printed_parenthesized_value": match[2]}
        rows.append(row)
    require(len({r["dataset_row_one_based"] for r in rows}) == len(rows),
            "duplicate displayed dataset rows")
    return {"role": "historical_notebook_output_not_fresh_execution",
            "precision": "printed_strings_only; original_arrays_not_loaded", "rows": rows}


def inspect_sources(notebook, loader_source, trainer_source, model_source):
    require(isinstance(notebook, dict) and isinstance(notebook.get("cells"), list),
            "expected notebook cells")
    cells, cell_records = [], {}
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        raw = cell.get("source", "")
        require(isinstance(raw, str) or (isinstance(raw, list)
                and all(isinstance(s, str) for s in raw)), "invalid cell source")
        source = "".join(raw) if isinstance(raw, list) else raw
        label = cell.get("source_cell_label", f"notebook-index:{index}")
        cells.append((label, parse_cell(source)))
        cell_records[label] = cell
    packed = one([(i, t) for i, t in cells if assignments(t, "real_dataloader_fast")],
                 "packed Allen data cell")
    packed_i, packed_tree = packed
    shape_call = one(calls(packed_tree, "np.zeros"), "packed count tensor allocation")
    require(len(shape_call.args) == 1 and isinstance(shape_call.args[0], ast.Tuple),
            "packed source shape must be a literal tuple")
    shape = [numeric(n) for n in shape_call.args[0].elts]
    require(len(shape) == 3 and all(type(n) is int and n > 0 for n in shape),
            "packed source shape must contain three positive integers")
    data_call = one(calls(packed_tree, "Simple_dataloader_from_spikes"), "packed loader")
    kwargs = literal_kwargs(data_call)
    require(all(type(kwargs.get(k)) in (int, float) for k in
                ("train_ratio", "val_ratio", "npadding", "batch_size")),
            "packed loader requires literal split/padding/batch parameters")
    n = shape[2]
    split1 = int(kwargs["train_ratio"] * n)
    split2 = int((kwargs["train_ratio"] + kwargs["val_ratio"]) * n)
    loader_tree, trainer_tree, model_tree = map(ast.parse,
                                              (loader_source, trainer_source, model_source))
    init = method(loader_tree, "Simple_dataloader_from_spikes", "__init__")
    split_assign = one([a for a in ast.walk(init) if isinstance(a, ast.Assign)
                       and any(ast.unparse(t) == "(split1, split2)" for t in a.targets)],
                      "simple loader split assignment")
    expected_split = "(int(train_ratio * self.ntrial), int((train_ratio + val_ratio) * self.ntrial))"
    require(ast.unparse(split_assign.value) == expected_split,
            "simple-loader split arithmetic changed; derived counts would be unsupported")
    train = method(trainer_tree, "Trainer", "train")
    accepted = {a.arg for a in train.args.args + train.args.kwonlyargs}
    require(train.args.kwarg is None, "trainer has open keywords; inspect call compatibility manually")
    steps = []
    for cell_i, tree in cells:
        train_calls = calls(tree, "trainer.train")
        saves = calls(tree, "np.save")
        if not train_calls or not saves:
            continue
        save = one(saves, "ablation save")
        require(save.args and isinstance(save.args[0], ast.Constant)
                and isinstance(save.args[0].value, str), "nonliteral result destination")
        captured = one(assignments(tree, "test_loss"), "captured training result")
        require(isinstance(captured.value, ast.Call) and captured.value in train_calls,
                "captured score is not a direct trainer.train call")
        captured_index = train_calls.index(captured.value)
        steps.append({
            "cell_label": cell_i,
            "result_basename": Path(save.args[0].value).name,
            "train_calls": [{"line_in_cell": c.lineno, "keywords": literal_kwargs(c),
                             "unsupported_keywords": sorted(k.arg for k in c.keywords
                                                             if k.arg not in accepted)}
                            for c in train_calls],
            "saved_training_call_one_based": captured_index + 1,
            "later_training_calls_before_save": len(train_calls) - captured_index - 1,
        })
    settings = one([(i, t) for i, t in cells if assignments(t, "nrep")], "replicate setting cell")
    nrep = numeric(one(assignments(settings[1], "nrep"), "nrep").value)
    loss = one([x for x in ast.walk(model_tree) if isinstance(x, ast.FunctionDef)
                and x.name == "loss_function"], "model loss function")
    stats = one([(i, t) for i, t in cells if any(isinstance(x, ast.FunctionDef)
                 and x.name == "mean_sem" for x in t.body)], "summary cell")
    mean_sem = one([x for x in stats[1].body if isinstance(x, ast.FunctionDef)
                    and x.name == "mean_sem"], "mean_sem")
    return {
        "packed_allen_route": {
            "cell_label": packed_i,
            "allocated_time_neuron_trial_shape": shape,
            "input_iterables": [ast.unparse(x.iter) for x in ast.walk(packed_tree)
                                if isinstance(x, ast.For)],
            "neuron_layout_expression": ast.unparse(one(assignments(packed_tree, "acc_nneuron"),
                                                        "neuron layout").value),
            "simple_loader_keywords": kwargs,
            "derived_split_sizes_if_all_allocated_rows_are_valid": {
                "train": split1, "validation": split2 - split1, "test": n - split2},
            "post_padding_time_bins": shape[0] - kwargs["npadding"],
            "loader_split_expression": ast.unparse(split_assign.value),
            "loader_seed_calls": [ast.unparse(c) for c in calls(init, "utils.set_seed")],
            "loader_session_identity_assignments": [ast.unparse(a.value)
                for a in assignments(init, "self.session_ids")],
        },
        "replicate_setting": {"cell_label": settings[0], "nrep": nrep},
        "summary": {"cell_label": stats[0], "function": ast.unparse(mean_sem)},
        "historical_displayed_summary": displayed_summary(cell_records[stats[0]]),
        "ablation_stages": steps,
        "trainer": {
            "train_line": train.lineno,
            "accepted_train_keywords": sorted(accepted - {"self"}),
            "iterated_loader_expressions": [ast.unparse(x.iter) for x in ast.walk(train)
                                            if isinstance(x, ast.For)
                                            and "_loader" in ast.unparse(x.iter)],
            "returns": [ast.unparse(x.value) for x in ast.walk(train)
                        if isinstance(x, ast.Return)],
            "penalty_additions": [x.lineno for x in ast.walk(train)
                if isinstance(x, ast.AugAssign) and ast.unparse(x.target) == "loss"
                and ast.unparse(x.value) == "self.get_penalty()"],
        },
        "model_loss": {"line": loss.lineno, "function": ast.unparse(loss)},
    }


def audit_directory(source_root, pins_path):
    pins = json.loads(pins_path.read_text())
    require(pins.get("source_commit") == SOURCE_COMMIT, "wrong source revision")
    blobs, receipts = {}, []
    for name in SOURCE_FILES:
        path = source_root / name
        require(path.is_file() and path.stat().st_size <= 8 * 1024**2,
                f"missing or oversized source file: {name}")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(pins["files"].get(name) == digest, f"source digest mismatch: {name}")
        blobs[name] = raw.decode("utf-8")
        receipts.append({"path": name, "sha256": digest, "bytes": len(raw)})
    return {"task_id": "PAPER-paper-method-018", "source_commit": SOURCE_COMMIT,
            "evidence_type": "static_public_source_inspection_only",
            "source_retrieval": "commit_specific_jsdelivr_urls; pinned_bytes",
            "sources": receipts,
            "extraction": inspect_sources(json.loads(blobs[SOURCE_FILES[0]]),
                blobs["DataLoader.py"], blobs["model_trainer.py"], blobs["GLMTransformer.py"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_directory(args.source_root, Path(__file__).with_name("source-pins.json"))
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()

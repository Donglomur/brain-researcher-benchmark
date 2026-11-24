"""Public-only, streaming NEURAL-062 FIT/INFER input and prediction preflight.

No fitting, protected targets, scientific scoring or runtime qualification.
The two dependencies are the preserved public protocol and ordinary I/O module.
"""
import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct

PUBLIC = Path(__file__).resolve().parent.parent / "registered-runtime/source/public"
PINS = {
    "protocol.py": "e02a6c6b93e2c4f2c8bfd4792ee7d1318a41fc5cf83092f1011dc67ea9234ea4",
    "delivery_io.py": "1c6171e9abc8f732fe8ab190af040251a6ad0253e74bbecbb4c046ec967c375b",
}
HEX = re.compile(r"[a-f0-9]{64}")


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def dependencies(public_code):
    modules = []
    for name, pin in PINS.items():
        path = Path(public_code) / name
        need(path.is_file() and not path.is_symlink(), "Ordinary public source module")
        body = path.read_bytes()
        need(hashlib.sha256(body).hexdigest() == pin, "Preserved public source identity")
        spec = importlib.util.spec_from_file_location("n062_public_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        # Execute the bytes checked above, not a reopened path or bytecode cache.
        exec(compile(body, str(path), "exec"), module.__dict__)
        modules.append(module)
    return modules


def metadata(root, public_code=PUBLIC):
    protocol, io = dependencies(public_code)
    root = io.regular(root)
    need(root.is_dir(), "Phase input directory")
    view = io.json_file(root / "VIEW.json", 40_000_000)
    need(type(view) is dict and view.get("phase") in ("fit", "infer"), "FIT or INFER phase")
    phase = view["phase"]
    fields = ["format", "phase", "generation", "case", "arm", "feature_names",
              "classes", "array", "array_name"]
    io.exact(view, fields + (["groups_pin"] if phase == "fit" else ["query_ids"]))
    need(view["format"] == "neural062_phase_view_v1" and
         digest(view["generation"]) and digest(view["case"]), "Exact phase identity")
    need(view["feature_names"] == list(protocol.names(view["arm"])) and
         view["classes"] == list(range(8)) and
         all(type(x) is int for x in view["classes"]), "Unchanged features and eight classes")
    name = "train.npy" if phase == "fit" else "query.npy"
    need(view["array_name"] == name, "Disjoint phase array")
    wanted = {"VIEW.json", name} | ({"TRAIN_GROUPS.json"} if phase == "fit" else set())
    need({x.name for x in root.iterdir()} == wanted, "Exact public phase file set")
    record = view["array"]
    io.exact(record, ["bytes", "sha256", "shape"])
    io.check_pin({k: record[k] for k in ("bytes", "sha256")}, 4_000_000_000)
    shape = record["shape"]
    width = len(view["feature_names"]) + (2 if phase == "fit" else 0)
    need(type(shape) is list and len(shape) == 2 and
         all(type(x) is int for x in shape) and shape[1] == width and
         (1 if phase == "fit" else 0) <= shape[0] <= (3_000_000 if phase == "fit" else 500_000),
         "Complete bounded phase geometry")
    runs = []
    if phase == "fit":
        io.check_pin(view["groups_pin"], 16_000_000)
        groups = io.json_file(root / "TRAIN_GROUPS.json", 16_000_000, view["groups_pin"])
        io.exact(groups, ["schema", "rows", "runs"])
        need(groups["schema"] == "neural062.train-mouse-groups.v1" and
             type(groups["rows"]) is int and groups["rows"] == shape[0] and
             type(groups["runs"]) is list and 0 < len(groups["runs"]) <= shape[0],
             "Training mouse groups cover the training rows")
        total = 0
        for run in groups["runs"]:
            io.exact(run, ["group", "count"])
            need(digest(run["group"]) and type(run["count"]) is int and
                 0 < run["count"] <= shape[0], "Opaque training mouse and positive run count")
            total += run["count"]
        need(total == shape[0] and len({r["group"] for r in groups["runs"]}) <= 73,
             "Complete training-only mouse support")
        runs = groups["runs"]
    else:
        ids = view["query_ids"]
        need(type(ids) is list and len(ids) == shape[0] and all(digest(x) for x in ids) and
             len(ids) == len(set(ids)), "Every opaque query identity exactly once")
    return root, view, runs, io


def header(stream, record):
    need(stream.read(8) == b"\x93NUMPY\x01\x00", "NPY1 only")
    raw = stream.read(2)
    need(len(raw) == 2, "Complete NPY header extent")
    size = struct.unpack("<H", raw)[0]
    need(0 < size <= 4096, "Bounded NPY header")
    raw = stream.read(size)
    need(len(raw) == size and raw.endswith(b"\n"), "Complete NPY header")
    try:
        tree = ast.parse(raw.decode("latin1").strip(), mode="eval")
        need(isinstance(tree.body, ast.Dict) and len(tree.body.keys) == 3 and
             {ast.literal_eval(k) for k in tree.body.keys} == {"descr", "fortran_order", "shape"},
             "Exact unique NPY header fields")
        value = ast.literal_eval(tree)
    except (SyntaxError, TypeError, RecursionError, MemoryError) as exc:
        raise ValueError("Malformed NPY header") from exc
    need(value["descr"] == "<f4" and value["fortran_order"] is False and
         type(value["shape"]) is tuple and all(type(x) is int for x in value["shape"]) and
         value["shape"] == tuple(record["shape"]), "Exact little-endian float32 C-order matrix")
    need(stream.tell() + math.prod(record["shape"]) * 4 == record["bytes"], "Exact NPY payload extent")
    return stream.tell()


class PhaseRows:
    """One complete row traversal while the validated descriptor remains open."""
    def __init__(self, view, runs, stream):
        self.view, self.runs, self.stream = view, runs, stream
        self.used = False

    def rows(self):
        need(not self.used, "A phase row traversal may be consumed only once")
        self.used = True
        count, width = self.view["array"]["shape"]
        decoder = struct.Struct("<" + "f" * width)
        group_index = 0
        group_end = self.runs[0]["count"] if self.runs else 0
        for index in range(count):
            raw = self.stream.read(decoder.size)
            need(len(raw) == decoder.size, "Complete phase row")
            values = decoder.unpack(raw)
            if self.view["phase"] == "fit":
                while index >= group_end:
                    group_index += 1
                    group_end += self.runs[group_index]["count"]
                yield {"index": index, "features": values[:-2], "label": int(values[-2]),
                       "weight": values[-1], "group": self.runs[group_index]["group"]}
            else:
                yield {"id": self.view["query_ids"][index], "features": values}


@contextmanager
def open_phase(root, public_code=PUBLIC):
    """Validate every value before exposing any row; keep the verified FD open.

    Logical reads: complete hash, complete semantic scan, then requested rows.
    A row traversal keeps O(width) numeric memory; public JSON remains bounded.
    """
    root, view, runs, io = metadata(root, public_code)
    record = view["array"]
    pin = {k: record[k] for k in ("bytes", "sha256")}
    with io.verified_stream(root / view["array_name"], pin) as stream:
        offset = header(stream, record)
        count, width = record["shape"]
        decoder = struct.Struct("<" + "f" * width)
        labels = set()
        for _ in range(count):
            raw = stream.read(decoder.size)
            need(len(raw) == decoder.size, "Complete phase row")
            values = decoder.unpack(raw)
            features = values[:-2] if view["phase"] == "fit" else values
            need(all(not math.isinf(x) for x in features),
                 "Finite features; only NaN denotes missingness")
            if view["phase"] == "fit":
                label, weight = values[-2:]
                need(math.isfinite(label) and label.is_integer() and 0 <= label < 8 and
                     math.isfinite(weight) and weight > 0, "Eight-way label and positive sample weight")
                labels.add(int(label))
        need(view["phase"] != "fit" or labels == set(range(8)), "All eight training classes")
        need(not stream.read(1), "No trailing matrix bytes")
        stream.seek(offset)
        io.reserve("read_bytes", count * width * 4)
        yield PhaseRows(view, runs, stream)


def prediction_preflight(root, prediction, public_code=PUBLIC):
    """Check complete INFER artifact identity/support; never read a target."""
    with open_phase(root, public_code) as phase:
        view = phase.view
        need(view["phase"] == "infer", "Predictions require an INFER view")
        _, io = dependencies(public_code)
        result = io.json_file(prediction, 160_000_000)
        io.exact(result, ["format", "generation", "case", "arm", "probabilities"])
        need(result["format"] == "neural062_predictions_v1" and
             all(result[k] == view[k] for k in ("generation", "case", "arm")), "Current prediction identity")
        rows = result["probabilities"]
        need(type(rows) is list and len(rows) == len(view["query_ids"]), "Complete prediction row count")
        seen = set()
        for row in rows:
            io.exact(row, ["id", "p"])
            need(digest(row["id"]) and row["id"] not in seen, "Unique prediction identity")
            seen.add(row["id"])
            prob = row["p"]
            need(type(prob) is list and len(prob) == 8 and
                 all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in prob) and
                 abs(sum(prob) - 1) <= 1e-6, "Finite eight-probability simplex")
        need(seen == set(view["query_ids"]), "Exact query identity support")
        return {"status": "public_prediction_structure_valid", "rows": len(rows),
                "private_target_reads": 0, "scientifically_qualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--public-code", default=str(PUBLIC))
    parser.add_argument("--prediction")
    args = parser.parse_args()
    if args.prediction:
        result = prediction_preflight(args.input, args.prediction, args.public_code)
    else:
        with open_phase(args.input, args.public_code) as phase:
            view = phase.view
            result = {"status": "public_phase_structure_valid", "phase": view["phase"],
                      "rows": view["array"]["shape"][0], "features": len(view["feature_names"]),
                      "training_mice": len({x["group"] for x in phase.runs}),
                      "private_target_reads": 0, "scientifically_qualified": False}
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

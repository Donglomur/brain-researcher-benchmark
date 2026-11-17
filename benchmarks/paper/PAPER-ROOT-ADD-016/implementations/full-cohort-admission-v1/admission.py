"""Operator-only full-cohort preparation and independent saved-draw summaries.

No model fitting, candidate execution, downloads or runtime qualification.  This
is an additional operator reference-review route, not a candidate grading rule.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TASK = "PAPER-ROOT-ADD-016"
PREFIX = "benchmarks/paper/" + TASK + "/"
DEPENDENCIES = {
    PREFIX + "task.json": (19324, "bed3f79d97c1ded8380e92e1ef6f6387d8910a37c890c8d2d4ed9d7477e8ab04"),
    PREFIX + "implementations/matched-artifacts/MODEL_CONTRACT.json":
        (1894, "ce1b65e4434f6b3237671b0a3c141f75ea4817af264282a9a3f25efac0027701"),
    PREFIX + "implementations/matched-artifacts/MATH_SPEC.md":
        (1485, "b814c48c52ac61f895293112d00e927c30faa95c7c11a10a622734076f6cb7c1"),
    PREFIX + "implementations/six-model-summary/TASK.md":
        (3941, "0f5f2213b512c59dab9d2a4858d600b3fc5bf78c585aa00275e7058611a94ff0"),
    PREFIX + "implementations/six-model-summary/summary_score.py":
        (9874, "3d40ba1ff118059cf6df88e0a8bd29688486a1b6b57d3cfbcdf597cae04696b9"),
}
VARIABLES = ("alpha_c", "beta", "sigma", "nu", "alpha")
CHAINS, DRAWS = 4, 2000
DRAW_BYTES = CHAINS * DRAWS * 8
JSON_CAP = 200_000
EVIDENCE_CAP = 1_048_576
LIMITS = [
    "Input identity and complete numerical support do not authenticate acquisition or rights.",
    "Saved draws and producer/log identities do not prove fitting, custody, data use or independence.",
    "Tuning, convergence and native numerical fidelity are not inferred from retained draws.",
    "No runtime, resource feasibility, protected execution or scientific qualification is granted.",
    "All 655 participants are exposed development reconstruction inputs; no held-out split exists.",
    "No scientific pass threshold or automatic private-reference binding is supplied.",
]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= JSON_CAP, "bounded JSON bytes")
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def bad(value):
        raise ValueError("nonfinite JSON token: " + value)
    try:
        return json.loads(raw.decode("utf8"), object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError("unsupported JSON encoding or nesting") from exc


def unlinked(path):
    path = Path(path)
    need(path.is_absolute(), "absolute physical path required")
    need(".." not in path.parts, "canonical absolute path required")
    need(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path")
    return path


def read_regular(path, cap, seen_files=None):
    """Snapshot an ordinary single-link file without following aliases or FIFOs."""
    path = unlinked(path)
    before_name = path.lstat()
    need(stat.S_ISREG(before_name.st_mode) and before_name.st_nlink == 1,
         "ordinary single-link file required")
    file_id = (before_name.st_dev, before_name.st_ino)
    if seen_files is not None:
        need(file_id not in seen_files, "distinct physical artifact roles")
    need(type(cap) is int and 0 < before_name.st_size <= cap, "bounded nonempty file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and identity(before) == identity(before_name),
             "file changed before snapshot")
        chunks, left = [], before.st_size
        while left:
            part = os.read(fd, min(left, 65536))
            need(part, "truncated file")
            chunks.append(part)
            left -= len(part)
        need(not os.read(fd, 1), "growing file")
        need(identity(before) == identity(os.fstat(fd)) == identity(path.lstat()),
             "file changed during snapshot")
    finally:
        os.close(fd)
    if seen_files is not None:
        seen_files.add(file_id)
    return b"".join(chunks)


def source(relative):
    size, digest = DEPENDENCIES[relative]
    raw = read_regular(ROOT / relative, size)
    need(pin(raw) == {"bytes": size, "sha256": digest}, "changed current source: " + relative)
    return raw


def verify_sources():
    return {name: pin(source(name)) for name in DEPENDENCIES}


def load_contract():
    verify_sources()
    return decode(source(PREFIX + "implementations/matched-artifacts/MODEL_CONTRACT.json"))


def load_current_scorer():
    relative = PREFIX + "implementations/six-model-summary/summary_score.py"
    raw = source(relative)
    module = types.ModuleType("_cardiac_admission_verified_summary")
    module.__file__ = str(ROOT / relative)
    # Execute exactly the authenticated body, never a cached bytecode file.
    exec(compile(raw, module.__file__, "exec"), module.__dict__)
    return module


def moments(values):
    need(values and all(finite(v) for v in values), "finite numerical column")
    try:
        mean = math.fsum(values) / len(values)
        sd = math.hypot(*(v - mean for v in values)) / math.sqrt(len(values))
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("unsupported column arithmetic") from exc
    need(finite(mean) and finite(sd) and sd > 0, "finite nonconstant column")
    return mean, sd


def parse_complete_table(raw, contract):
    """Structural/numeric preparation only; not frozen empirical identity admission."""
    need(type(raw) is bytes and 0 < len(raw) <= EVIDENCE_CAP, "bounded CSV")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf8"), newline=""), strict=True)
        need(reader.fieldnames == contract["columns"], "exact CSV column order")
        rows = list(reader)
        need(len(rows) == contract["participants"] == 655, "complete 655-row cohort")
        need(all(set(r) == set(contract["columns"]) and all(type(v) is str for v in r.values())
                 for r in rows), "complete rectangular rows")
        ids = [r["subject_id"] for r in rows]
        need(all(ids) and len(set(ids)) == 655, "655 distinct nonempty participant IDs")
        columns = {name: [float(r[name]) for r in rows] for name in contract["columns"][2:]}
        for values in columns.values():
            moments(values)
    except (UnicodeError, csv.Error, OverflowError) as exc:
        raise ValueError("invalid CSV or unsupported numeric column") from exc
    return {"participant_ids": ids, "columns": columns}


def prepare_models(table, contract):
    raw = table["columns"]
    need(set(raw) == set(contract["columns"][2:]) and
         all(type(v) is list and len(v) == 655 for v in raw.values()), "full numeric population")
    standardized = {}
    for name, values in raw.items():
        mean, sd = moments(values)
        standardized[name] = [(v - mean) / sd for v in values]
        need(all(finite(v) for v in standardized[name]), "supported standardized column")
    result = {}
    for model in contract["models"]:
        current = raw if model["scale"] == "raw" else standardized
        x, y = list(current["age"]), list(current[model["condition"]])
        xm, sx = moments(x)
        ym, sy = moments(y)
        b = 2.5 * sy / sx
        a = math.hypot(2.5 * sy, xm * b)
        need(finite(a) and finite(b) and a > 0 and b > 0, "supported prior scales")
        result[model["name"]] = {"x": x, "y": y, "scales": {
            "x_mean": xm, "y_mean": ym, "x_sd": sx, "y_sd": sy,
            "beta_sd": b, "alpha_c_sd": a}}
    return result


def log_density(prepared, alpha_c, beta, sigma, nu):
    """Scalar source-model density in natural parameters, without a sampler."""
    need(all(finite(v) for v in (alpha_c, beta, sigma, nu)) and sigma > 0 and nu > 0,
         "finite density point with positive sigma/nu")
    s = prepared["scales"]
    def normal(z, mu, sd):
        return -math.log(sd) - 0.5 * math.log(2 * math.pi) - 0.5 * ((z - mu) / sd) ** 2
    def student(z, mean, scale, df):
        return (math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
                - math.log(scale) - 0.5 * math.log(df * math.pi)
                - ((df + 1) / 2) * math.log1p(((z - mean) / scale) ** 2 / df))
    try:
        likelihood = math.fsum(student(y, alpha_c + beta * (x - s["x_mean"]), sigma, nu)
                               for x, y in zip(prepared["x"], prepared["y"]))
        prior = (normal(alpha_c, s["y_mean"], s["alpha_c_sd"])
                 + normal(beta, 0, s["beta_sd"])
                 + math.log(2) + student(sigma, 0, s["y_sd"], 4)
                 + 2 * math.log(0.1) - math.lgamma(2) + math.log(nu) - 0.1 * nu)
        value = likelihood + prior
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("unsupported scalar density arithmetic") from exc
    need(finite(value), "finite scalar density")
    return value


def prepare_density_probes(models):
    """Prepare source-derived scalar expectations, never a native comparison."""
    probes = {}
    for name, prepared in models.items():
        s = prepared["scales"]
        points = [(s["y_mean"], -0.01, s["y_sd"], 6.0),
                  (s["y_mean"] + 0.12, 0.08, s["y_sd"] * 1.8, 2.3),
                  (s["y_mean"] - 0.05, -0.13, s["y_sd"] * 0.7, 18.0)]
        probes[name] = []
        for ac, beta, sigma, nu in points:
            value = log_density(prepared, ac, beta, sigma, nu)
            probes[name].append({"natural_point": {"alpha_c": ac, "beta": beta, "sigma": sigma, "nu": nu},
                "expected_log_density": value,
                "expected_log_density_with_log_sigma_nu_jacobian": value + math.log(sigma) + math.log(nu)})
    return probes


def inspect_input(csv_path):
    contract = load_contract()
    raw = read_regular(csv_path, contract["input"]["bytes"])
    need(pin(raw) == contract["input"], "exact original CSV identity required")
    table = parse_complete_table(raw, contract)
    ids_raw = json.dumps(table["participant_ids"], ensure_ascii=False, separators=(",", ":")).encode()
    need(hashlib.sha256(ids_raw).hexdigest() == contract["participant_id_hash"],
         "exact original ordered participant identity")
    models = prepare_models(table, contract)
    probes = prepare_density_probes(models)
    report = {"schema": "cardiac_full_cohort_preparation_v1", "benchmark_id": TASK,
        "input": pin(raw), "participants": 655, "participant_id_sha256": contract["participant_id_hash"],
        "participant_split": "none_exposed_development_reconstruction", "models": {
            name: {"rows": 655, "scales": m["scales"]} for name, m in models.items()},
        "sampling_prescription": contract["sampling"], "density_probes": probes,
        "native_density_comparison_performed": False, "scientific_qualified": False,
        "source_dependencies": verify_sources(), "limits": LIMITS}
    return {"report": report, "models": models, "contract": contract}


def summarize_chains(chains):
    need(type(chains) is list and len(chains) == CHAINS and
         all(type(c) is list and len(c) == DRAWS for c in chains), "exact four chains of 2000 draws")
    values = [v for c in chains for v in c]
    need(all(finite(v) for v in values), "finite draws, not booleans")
    try:
        mean = math.fsum(values) / len(values)
        sd = math.hypot(*(v - mean for v in values)) / math.sqrt(len(values))
        ordered = sorted(values)
        step = math.floor(0.94 * len(ordered))
        widths = [ordered[i + step] - ordered[i] for i in range(len(ordered) - step)]
        need(all(finite(v) for v in widths), "supported HDI width arithmetic")
        start = min(range(len(widths)), key=widths.__getitem__)
        batches = [math.fsum(c[i:i + 100]) / 100 for c in chains for i in range(0, DRAWS, 100)]
        batch_mean = math.fsum(batches) / len(batches)
        mcse = math.hypot(*(b - batch_mean for b in batches)) / math.sqrt(len(batches) * (len(batches) - 1))
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("unsupported saved-draw summary arithmetic") from exc
    need(all(finite(v) for v in (mean, sd, mcse)), "finite saved-draw summary")
    return {"mean": mean, "sd_population": sd, "hdi_94_low": ordered[start],
            "hdi_94_high": ordered[start + step], "mcse_mean_batch": mcse}


def descriptor_body(root, descriptor, cap, seen_files=None):
    need(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"}, "exact artifact descriptor")
    name, size, digest = descriptor["path"], descriptor["bytes"], descriptor["sha256"]
    need(type(name) is str and name and "\\" not in name and "\x00" not in name, "relative artifact path")
    rel = PurePosixPath(name)
    need(not rel.is_absolute() and str(rel) == name and all(p not in (".", "..") for p in rel.parts),
         "canonical relative artifact path")
    need(type(size) is int and 0 < size <= cap, "bounded declared bytes")
    need(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "exact SHA256")
    raw = read_regular(root / name, size, seen_files)
    need(pin(raw) == {"bytes": size, "sha256": digest}, "artifact identity mismatch")
    return raw


def review_draws(prepared, draw_root):
    """Recompute all summaries; this function never admits a reference as trusted."""
    root = unlinked(draw_root)
    need(root.is_dir(), "draw root directory")
    seen_files = set()
    manifest_raw = read_regular(root / "draws.json", JSON_CAP, seen_files)
    manifest = decode(manifest_raw)
    need(type(manifest) is dict and set(manifest) == {"schema", "benchmark_id", "input_sha256",
         "participant_id_sha256", "producer", "environment_record", "execution_record", "models"}, "exact draw manifest")
    need(manifest["schema"] == "cardiac_operator_draw_review_v1" and manifest["benchmark_id"] == TASK,
         "operator draw review schema")
    contract = prepared["contract"]
    need(manifest["input_sha256"] == contract["input"]["sha256"] and
         manifest["participant_id_sha256"] == contract["participant_id_hash"], "draw input/cohort join")
    names = [m["name"] for m in contract["models"]]
    need(type(manifest["models"]) is dict and set(manifest["models"]) == set(names), "all six models")
    used_paths = {"draws.json"}
    evidence = {}
    for role in ("producer", "environment_record", "execution_record"):
        descriptor = manifest[role]
        body = descriptor_body(root, descriptor, EVIDENCE_CAP, seen_files)
        need(descriptor["path"] not in used_paths, "distinct artifact roles")
        used_paths.add(descriptor["path"])
        evidence[role] = pin(body)
    summary = {"schema_version": 1, "input_sha256": contract["input"]["sha256"],
               "target": "salzburg_bambi091_six_student_t_targets", "models": {}}
    details, fit_ids = {}, set()
    for name in names:
        record = manifest["models"][name]
        need(type(record) is dict and set(record) == {"fit_id", "requested_tune_per_chain", "seed", "draws"},
             "exact per-model draw evidence")
        fit_id = record["fit_id"]
        need(type(fit_id) is str and 0 < len(fit_id) <= 200 and not any(ord(c) < 32 for c in fit_id)
             and fit_id not in fit_ids, "distinct declared model fit IDs")
        fit_ids.add(fit_id)
        need(type(record["requested_tune_per_chain"]) is int and record["requested_tune_per_chain"] == 2000,
             "declared source tuning prescription")
        need(record["seed"] is None or type(record["seed"]) is int, "reported seed or explicit unavailable")
        need(type(record["draws"]) is dict and set(record["draws"]) == set(VARIABLES), "all five draw parameters")
        arrays, pins = {}, {}
        for variable in VARIABLES:
            d = record["draws"][variable]
            need(type(d) is dict and set(d) == {"encoding", "shape", "artifact"}, "exact draw stream declaration")
            need(d["encoding"] == "float64-le-chain-major" and d["shape"] == [CHAINS, DRAWS]
                 and all(type(v) is int for v in d["shape"]), "fixed binary layout and full shape")
            raw = descriptor_body(root, d["artifact"], DRAW_BYTES, seen_files)
            need(len(raw) == DRAW_BYTES and d["artifact"]["path"] not in used_paths,
                 "exact complete distinct draw streams")
            used_paths.add(d["artifact"]["path"])
            values = [x[0] for x in struct.iter_unpack("<d", raw)]
            need(all(math.isfinite(v) for v in values), "finite complete draw stream")
            if variable in ("sigma", "nu"):
                need(all(v > 0 for v in values), "strictly positive sigma/nu draws")
            arrays[variable] = [values[i * DRAWS:(i + 1) * DRAWS] for i in range(CHAINS)]
            pins[variable] = pin(raw)
        parameters = {v: summarize_chains(arrays[v]) for v in VARIABLES}
        xm = prepared["models"][name]["scales"]["x_mean"]
        differences = [alpha - (ac - xm * beta) for acs, betas, alphas in
                       zip(arrays["alpha_c"], arrays["beta"], arrays["alpha"])
                       for ac, beta, alpha in zip(acs, betas, alphas)]
        need(all(finite(v) for v in differences), "supported alpha identity arithmetic")
        details[name] = {"fit_id_as_declared": fit_id, "seed_as_declared": record["seed"],
            "requested_tuning_as_declared": 2000, "observed_retained_shape": [CHAINS, DRAWS],
            "draw_pins": pins, "alpha_identity_max_absolute_error": max(abs(v) for v in differences),
            "alpha_identity_nonzero_binary64_differences": sum(v != 0 for v in differences),
            "alpha_identity_acceptance_tolerance": None}
        summary["models"][name] = {"summary": parameters, "diagnostics": {
            "chains": CHAINS, "draws_per_chain": DRAWS, "tune_per_chain": None,
            "divergences": None, "max_rhat": None, "min_ess_bulk": None, "min_ess_tail": None}}
    scorer = load_current_scorer()
    scorer.validate(summary)
    raw_summary = encoded(summary)
    need(len(raw_summary) <= scorer.MAX_BYTES, "current bounded summary interface")
    review = {"schema": "cardiac_saved_draw_review_v1", "benchmark_id": TASK,
        "status": "complete_saved_draw_summaries_prepared_for_independent_operator_review",
        "manifest": pin(manifest_raw), "evidence_bodies": evidence, "input": contract["input"],
        "summary": pin(raw_summary), "models": details, "retained_draw_values": 240000,
        "current_summary_schema_valid": True, "reference_accepted": False,
        "independently_fitted_reference_verified": False, "data_dependence_verified": False,
        "tuning_verified": False, "convergence_verified": False, "custody_verified": False,
        "runtime_qualified": False, "scientific_qualified": False, "limits": LIMITS}
    return raw_summary, review


def fresh_directory(out, forbidden_roots):
    out = unlinked(out)
    need(out.parent.is_dir() and not out.exists(), "fresh output with existing parent")
    for root in forbidden_roots:
        root = unlinked(root)
        identity = lambda p: (p.stat().st_dev, p.stat().st_ino)
        need(identity(root) not in {identity(p) for p in (out.parent, *out.parent.parents)},
             "separate output and source/input roots")
    out.mkdir(mode=0o700)
    return out


def write_private(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd is not None:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify-source")
    for name in ("inspect-input", "review-reference"):
        p = sub.add_parser(name)
        p.add_argument("--csv", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        if name == "review-reference":
            p.add_argument("--draw-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify-source":
        print(json.dumps({"status": "source_verified", "dependencies": verify_sources(),
                          "scientific_qualified": False}, sort_keys=True))
        return 0
    prepared = inspect_input(args.csv)
    forbidden = [ROOT]
    raw_summary, review = None, None
    if args.command == "review-reference":
        forbidden.append(args.draw_root)
        raw_summary, review = review_draws(prepared, args.draw_root)
    out = fresh_directory(args.out, forbidden)
    # A failed write may leave partial private output; only a final receipt means completion.
    write_private(out / "input-preparation.json", encoded(prepared["report"]))
    if raw_summary is not None:
        write_private(out / "reference-summary.json", raw_summary)
        write_private(out / "reference-review.json", encoded(review))
    receipt = {"schema": "cardiac_preparation_receipt_v1", "benchmark_id": TASK,
               "command": args.command, "files": {}, "reference_accepted": False,
               "scientific_qualified": False, "limits": LIMITS}
    for name in ("input-preparation.json", "reference-summary.json", "reference-review.json"):
        if (out / name).exists():
            receipt["files"][name] = pin(read_regular(out / name, JSON_CAP))
    write_private(out / "receipt.json", encoded(receipt))
    print(json.dumps({"status": "operator_preparation_complete", "receipt": str(out / "receipt.json"),
                      "reference_accepted": False, "scientific_qualified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "refused", "reason": str(error), "scientific_qualified": False}, sort_keys=True))
        raise SystemExit(2)

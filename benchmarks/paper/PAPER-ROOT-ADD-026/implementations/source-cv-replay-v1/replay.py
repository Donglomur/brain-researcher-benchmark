"""Original condition-sampling replay and trusted training-only projection.

No model import, fit, score, historical RNG claim, or qualification decision.
The two column interpretations are explicit and must never be pooled.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import random
import sys

CATEGORIES = ("BODIES", "BUILDINGS", "FACES", "OBJECTS", "SCENES", "SCRAMBLED")
TRIALS = ("onepulse", "twopulse_repeat")
HEADER = ["trial_type", "img_cat", "temp_cond"] + [str(i) for i in range(819)]
BRANCHES = ("source_positional_cv", "named_response_columns")
FIT_SOURCE_SHA256 = "d28ac1550806a4748a1f73d894906721bdb7b075075eed85137688077f881330"
COHORT_FILE_SHA256 = "58a7baba4a984c17930fef5e733a385bbc4be02f8814ad4e0c9cc0be2b9b1a0f"
SCHEMA = "temporal026-source-cv-replay/v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def is_hash(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def cohort():
    raw = Path(__file__).with_name("cohort.json").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == COHORT_FILE_SHA256, "Frozen public cohort metadata changed")
    return json.loads(raw)["selected"]


def validate_rows(rows):
    require(type(rows) is list and len(rows) == 72, "Exactly 72 ordered condition rows required")
    observed = []
    for row in rows:
        require(type(row) is dict and set(row) == {"trial_type", "img_cat", "temp_cond"},
                "Condition rows contain only the three source identity fields")
        require(type(row["temp_cond"]) is int, "Temporal index must be an integer, not boolean")
        require(type(row["trial_type"]) is str and type(row["img_cat"]) is str,
                "String trial and category identities required")
        observed.append((row["trial_type"], row["img_cat"], row["temp_cond"]))
    expected = {(trial, category, index) for trial in TRIALS for category in CATEGORIES for index in range(6)}
    require(len(set(observed)) == 72 and set(observed) == expected, "Exact original 2 x 6 x 6 condition grid required")


def validate_metadata(metadata):
    require(type(metadata) is dict and set(metadata) == {"schema", "electrodes"}, "Metadata envelope has unexpected fields")
    require(metadata["schema"] == "temporal026-ordered-source-metadata/v1", "Metadata schema mismatch")
    items = metadata["electrodes"]
    require(type(items) is list and len(items) == 79, "Full 79-electrode Figure 3 cohort required")
    expected = {row["id"] for row in cohort()}
    found = set()
    for item in items:
        require(type(item) is dict and set(item) == {"electrode_id", "source_data_sha256", "rows"}, "Electrode metadata fields mismatch")
        identity = item["electrode_id"]
        require(type(identity) is str and identity in expected and identity not in found, "Unknown or repeated electrode")
        found.add(identity)
        require(is_hash(item["source_data_sha256"]), "Exact source-table SHA-256 required")
        validate_rows(item["rows"])
    require(found == expected, "Complete fixed cohort required")


def seed_for(master_seed, electrode_id):
    require(type(master_seed) is int and 0 <= master_seed < 2**256, "Seed must be an integer in [0, 2**256)")
    return int(digest([SCHEMA, str(master_seed), electrode_id]), 16)


def source_folds(rows, seed):
    """Replay modelFit.py's category-ordered sample-one/remove loop exactly.

    The declared seed is prospective; Python's version is recorded by freeze.
    Original unseeded process scheduling and RNG state are not reconstructed.
    """
    validate_rows(rows)
    rng = random.Random(seed)
    initial = digest(rng.getstate())
    pools = [[i for i, row in enumerate(rows) if row["img_cat"] == category] for category in CATEGORIES]
    folds = []
    for fold in range(12):
        test_idx = []
        for j in range(len(CATEGORIES)):
            test_idx.append(rng.sample(pools[j], 1)[0])
            pools[j].remove(test_idx[j])
        folds.append({"fold": fold, "test_rows": test_idx,
                      "train_rows": [i for i in range(72) if i not in test_idx]})
    return folds, initial, digest(rng.getstate())


def freeze(metadata, master_seed):
    validate_metadata(metadata)
    by_id = {item["electrode_id"]: item for item in metadata["electrodes"]}
    records = []
    for electrode in cohort():
        identity = electrode["id"]
        item = by_id[identity]
        seed = seed_for(master_seed, identity)
        folds, initial, final = source_folds(item["rows"], seed)
        records.append({**item, "seed": str(seed), "rng_state_before_sha256": initial,
                        "rng_state_after_sha256": final, "folds": folds})
    result = {"schema": SCHEMA, "source_fit_sha256": FIT_SOURCE_SHA256,
              "cohort_sha256": digest(cohort()), "ordered_metadata_sha256": digest(metadata),
              "master_seed": str(master_seed), "python": platform.python_version(),
              "python_implementation": platform.python_implementation(),
              "replay_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "sampling": "random.Random.sample(pool, 1), then remove; category order; 12 folds",
              "scope": "prospective per-electrode source-loop replay; common author/candidate folds; not historical assignments",
              "qualification": "software_component_only", "electrodes": records}
    result["manifest_sha256"] = digest(result)
    return result


def validate_manifest(manifest, expected_sha256):
    """Require an independently frozen digest, then validate all fold allocations.

    This is integrity checking, not authority or a substitute for source parity.
    Exact stored allocations remain usable across Python RNG implementations.
    """
    require(type(manifest) is dict, "Manifest must be an object")
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    require(is_hash(expected_sha256) and digest(body) == expected_sha256 == manifest.get("manifest_sha256"), "Frozen manifest digest mismatch")
    require(manifest.get("schema") == SCHEMA and manifest.get("source_fit_sha256") == FIT_SOURCE_SHA256, "Source protocol mismatch")
    require(manifest.get("cohort_sha256") == digest(cohort()), "Cohort identity mismatch")
    items = manifest.get("electrodes")
    require(type(items) is list, "Manifest electrode records required")
    metadata = {"schema": "temporal026-ordered-source-metadata/v1", "electrodes": [
        {k: item[k] for k in ("electrode_id", "source_data_sha256", "rows")} for item in items]}
    validate_metadata(metadata)
    for item in items:
        rows = item["rows"]
        require(type(item["folds"]) is list and len(item["folds"]) == 12, "Exactly 12 folds required")
        used = []
        for fold, allocation in enumerate(item["folds"]):
            require(set(allocation) == {"fold", "test_rows", "train_rows"}, "Fold allocation fields mismatch")
            require(type(allocation["fold"]) is int and allocation["fold"] == fold, "Canonical zero-based fold order required")
            test = allocation["test_rows"]
            require(type(test) is list and len(test) == 6 and all(type(i) is int and 0 <= i < 72 for i in test), "Six integer query indices required")
            require([rows[i]["img_cat"] for i in test] == list(CATEGORIES), "One query per category in source order required")
            require(all(type(i) is int for i in allocation["train_rows"]) and allocation["train_rows"] == [i for i in range(72) if i not in test], "Training must be the ordered complement of six queries")
            used.extend(test)
        require(sorted(used) == list(range(72)), "Every condition must be held out exactly once across folds")
    return {item["electrode_id"]: item for item in items}


def parse_source_table(raw):
    """Strict released literal-space schema; no numerical preparation is implicit."""
    require(type(raw) is bytes, "Source must be captured as bytes")
    table = list(csv.reader(io.StringIO(raw.decode("utf-8")), delimiter=" "))
    require(len(table) == 73 and table[0] == HEADER, "Expected 72 rows with released 3+819 column header")
    rows, responses = [], []
    for fields in table[1:]:
        require(len(fields) == 822, "Literal-space row width mismatch")
        require(fields[2] in tuple(str(i) for i in range(6)), "Canonical temporal index token required")
        rows.append({"trial_type": fields[0], "img_cat": fields[1], "temp_cond": int(fields[2])})
        values = [float(x) for x in fields[3:]]
        # Do not silently impute, drop conditions or change the author NaN metric.
        # Nonfinite source requires an explicit future source parity policy.
        require(all(math.isfinite(x) for x in values), "Nonfinite source responses require separate reviewed handling")
        responses.append(values)
    validate_rows(rows)
    return rows, responses


def project(raw, manifest, expected_sha256, electrode_id, fold, branch):
    """Trusted operator only: returns 66 responses, six response-free identities.

    Caller must isolate outputs per fold and prevent cross-fold state reuse.
    This function is not a filesystem/process sandbox.
    """
    require(branch in BRANCHES, "Explicit source_positional_cv or named_response_columns required")
    require(type(fold) is int and 0 <= fold < 12, "Fold must be an integer from 0 through 11")
    by_id = validate_manifest(manifest, expected_sha256)
    require(type(electrode_id) is str and electrode_id in by_id, "Unknown electrode")
    item = by_id[electrode_id]
    require(hashlib.sha256(raw).hexdigest() == item["source_data_sha256"], "Source table bytes differ from frozen metadata")
    rows, responses = parse_source_table(raw)
    require(rows == item["rows"], "Ordered source identities differ from frozen metadata")
    allocation = item["folds"][fold]
    columns = HEADER[2:821] if branch == "source_positional_cv" else HEADER[3:]
    training = []
    for i in allocation["train_rows"]:
        values = ([float(rows[i]["temp_cond"])] + responses[i][:-1]) if branch == "source_positional_cv" else responses[i][:]
        training.append({"source_row": i, **rows[i], "response": values})
    return {"schema": "temporal026-fold-training-packet/v1", "manifest_sha256": expected_sha256,
            "electrode_id": electrode_id, "fold": fold, "column_branch": branch,
            "target_columns": columns, "source_data_sha256": item["source_data_sha256"],
            "training": training, "queries": [{"source_row": i, **rows[i]} for i in allocation["test_rows"]],
            "qualification": "software_component_only"}


def read_json(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "Duplicate JSON key")
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonstandard JSON number")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze", help="Freeze full-cohort ordered metadata using a declared seed")
    f.add_argument("--metadata", required=True)
    f.add_argument("--seed", type=int, required=True)
    f.add_argument("--output", required=True)
    p = sub.add_parser("project", help="Trusted operator exports one fold; never expose source table to candidate")
    p.add_argument("--manifest", required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--source-table", required=True)
    p.add_argument("--electrode", required=True)
    p.add_argument("--fold", type=int, required=True)
    p.add_argument("--branch", choices=BRANCHES, required=True)
    p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        result = freeze(read_json(args.metadata), args.seed)
    else:
        result = project(Path(args.source_table).read_bytes(), read_json(args.manifest),
                         args.manifest_sha256, args.electrode, args.fold, args.branch)
    payload = encoded(result) + b"\n"
    # Exclusive creation preserves frozen evidence; no overwrite or append mode.
    with open(args.output, "xb") as handle:
        handle.write(payload)
    print(json.dumps({"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                      "qualification": "software_component_only"}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        sys.exit("source-cv-replay: " + str(exc))

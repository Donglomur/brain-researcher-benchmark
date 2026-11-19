"""Additive complete original Figure 3b dual outcomes; no native admission bypass."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
SCHEMA = "language-original-figure3b-dual-outcome-protocol/v1"
SCOPE = "original_figure3b_population_dual_outcome"
TOKEN = "execute-admitted-original-figure3b-dual-outcome"
CONDITIONS = ("paper_data", "paper_data_author_code")
CONTRACT_SHA = "bdde5a49079f59267485bd790bc157564146863a1c2f85bf20282deb6f9d314a"
MAX_PROTOCOL_BYTES = 262144
PAIR_SCHEMA = "language-original-figure3b-dual-outcome-pair/v1"
PAIR_KEYS = {"schema", "scope", "arms", "execution_policy", "pair_output", "pair_output_bytes"}
MAX_SOURCE_BYTES = 262144
MAX_RECOVERY_BYTES = 4 * 1024**2
MAX_OUTCOME_BYTES = 1024**2
KEYS = {"schema", "scope", "outcomes", "output_policy", "condition",
        "execution_policy", "dependency_root", "entry_sources",
        "selected_protocol", "selected_protocol_sha256", "outcome_output_bytes"}
DEPENDENCIES = {
    "original-figure3b-execution-v1/run.py": (8592, "2677c6554137e23ad860174488685d61ebe931128682782dd2027993224ece6e"),
    "original-figure3b-execution-v1/execution.py": (28981, "5ee501891b963abbce4f6f4aa5085e60e78544cc65f261e00ec75a0c5852229d"),
    "original-figure3b-execution-v1/reference.py": (4327, "4341454b459eb817741556f99cbabe71ee1e2e4da022741b62c246286fdbc4f4"),
    "original-figure3b-store-v1/producer.py": (17280, "620a265897e0b110ffb25da1816f27938f70df4ae3122f7a5c8a71232e9232e9"),
    "original-figure3b-store-v1/reader.py": (15742, "84a1f6e94dd855aec991026f3804cfe660914d084dbe14ee8b73ba63db39e6c3"),
    "original-exec-provider-v1/provider.py": (41474, "c9426ce6c51f2ac830809a9aab6649ab5926e5de7d983d0085b448001afb1b98"),
}
LEGACY_SOURCE_PINS = {name.rsplit("/", 1)[1]: digest for name, (_, digest) in DEPENDENCIES.items()
                      if name != "original-figure3b-execution-v1/run.py"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    need(type(value) is str and len(value) == 64 and all(x in "0123456789abcdef" for x in value),
         "Exact lowercase SHA256 required")
    return value


def parse(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate JSON field")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "Nonfinite JSON is forbidden"))


def stamp(info):
    return tuple(getattr(info, k) for k in
                 ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


def ordinary_absolute(path):
    need(type(path) is str and 0 < len(path) <= 4096, "Bounded explicit path")
    p = Path(path)
    need(p.is_absolute() and ".." not in p.parts, "Canonical absolute path")
    for parent in p.parents:
        need(stat.S_ISDIR(parent.lstat().st_mode), "Ordinary metadata ancestors")
    return p


def read_pinned(path, *, maximum, expected_sha256, expected_bytes=None):
    """Check extent before allocation and use exactly the authenticated bytes."""
    digest(expected_sha256)
    path = ordinary_absolute(str(path))
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= maximum
         and (expected_bytes is None or before.st_size == expected_bytes),
         "Bounded ordinary exact file before read")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        need(stamp(before) == stamp(opened), "Metadata changed before open")
        body = stream.read(before.st_size + 1)
        need(len(body) == before.st_size and sha(body) == expected_sha256
             and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
             "Exact stable pinned bytes required")
    return body


def pin_shape(pin, maximum):
    need(type(pin) is dict and set(pin) == {"bytes", "sha256"}
         and type(pin["bytes"]) is int and 0 < pin["bytes"] <= maximum,
         "Exact bounded source/receipt descriptor")
    digest(pin["sha256"])
    return pin


def load_contract():
    return parse(read_pinned(HERE / "contract.json", maximum=65536, expected_sha256=CONTRACT_SHA))


def validate_envelope(value):
    need(type(value) is dict and set(value) == KEYS and value["schema"] == SCHEMA
         and value["scope"] == SCOPE, "Exact additive named Figure3b envelope")
    need(value["outcomes"] == ["reproduction", "improvement"]
         and value["output_policy"] == "shared_frozen_candidate_predictions"
         and value["execution_policy"] == "existing_native_admission_required",
         "Explicit shared-output dual outcome policy; no alternate executor")
    need(type(value["condition"]) is str and value["condition"] in CONDITIONS, "Declared access condition")
    need(type(value["selected_protocol"]) is dict, "Embedded unchanged selected execution protocol")
    p = value["selected_protocol"]
    digest(value["selected_protocol_sha256"])
    need(len(encoded(p)) <= 65536 and sha(encoded(p)) == value["selected_protocol_sha256"],
         "Exact embedded selected-protocol identity")
    need(p.get("schema") == "language-selected-figure3b-execution-protocol/v1"
         and p.get("scope") == "original_figure3b_improvement",
         "Maintain existing store/runner scope; full224 reproduction is separate")
    need(p.get("source_pins") == LEGACY_SOURCE_PINS, "Reviewed maintained source dependency pins")
    config = p.get("provider_config")
    need(type(config) is dict and config.get("condition") == value["condition"],
         "Condition agrees with unchanged provider configuration")
    need(type(config.get("caps")) is dict and type(config["caps"].get("max_jobs")) is int
         and config["caps"]["max_jobs"] == 42
         and type(config["caps"].get("max_requests")) is int
         and config["caps"]["max_requests"] == 5685,
         "Full original42-cell/5685-request schedule")
    need(type(value["outcome_output_bytes"]) is int
         and 1 <= value["outcome_output_bytes"] <= MAX_OUTCOME_BYTES, "Finite additive outcome output allowance")
    root = ordinary_absolute(value["dependency_root"])
    need(stat.S_ISDIR(root.lstat().st_mode), "Ordinary maintained dependency directory")
    ordinary_absolute(p["output_root"])
    ordinary_absolute(p["provider_evidence_root"])
    protected = [p["store_root"], p["reference_path"], value["dependency_root"], str(HERE)]
    for name in ("candidate", "runtime", "assistance"):
        need(type(config.get(name)) is dict and type(config[name].get("root")) is str,
             "Declared candidate/runtime/assistance tree")
        protected.append(config[name]["root"])
    for path in protected:
        ordinary_absolute(path)
    writers = [p["output_root"], p["provider_evidence_root"]]
    need(disjoint(writers) and all(disjoint([writer, protected_path])
         for writer in writers for protected_path in protected),
         "Writing roots outside every protected source and participant context")
    sources = value["entry_sources"]
    need(type(sources) is dict and set(sources) == {"run.py", "outcomes.py", "contract.json"},
         "Complete additive entry source pins")
    contract = load_contract()
    need(contract["mode_scope"] == SCOPE and contract["historical_contract_unchanged"] is True,
         "Exact named additive contract")
    for name, pin in sources.items():
        pin_shape(pin, MAX_SOURCE_BYTES)
        if name == "contract.json":
            need(pin["sha256"] == CONTRACT_SHA, "Reviewed contract identity")
        if name == "outcomes.py":
            need(pin == contract["outcomes_dependency"], "Reviewed outcome composition source")
        read_pinned(HERE / name, maximum=MAX_SOURCE_BYTES,
                    expected_sha256=pin["sha256"], expected_bytes=pin["bytes"])
    return parse(encoded(value))


def read_protocol(path, expected):
    raw = read_pinned(path, maximum=MAX_PROTOCOL_BYTES, expected_sha256=expected)
    value = parse(raw)
    need(encoded(value) == raw, "Canonical externally pinned additive protocol")
    return validate_pair(value) if value.get("schema") == PAIR_SCHEMA else validate_envelope(value)


def module_from_bytes(name, path, raw):
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ""
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module


def load_selected_runner(root):
    """Authenticate six maintained seams, then import their exact source bytes."""
    root = Path(root)
    bodies = {rel: read_pinned(root / rel, maximum=MAX_SOURCE_BYTES,
                              expected_bytes=size, expected_sha256=identity)
              for rel, (size, identity) in DEPENDENCIES.items()}
    aliases = {name: sys.modules.get(name) for name in ("execution", "reference")}
    old_path = list(sys.path)
    try:
        for name in ("execution", "reference"):
            rel = "original-figure3b-execution-v1/" + name + ".py"
            sys.modules[name] = module_from_bytes("_language_dual_outcome_" + name,
                                                  root / rel, bodies[rel])
        rel = "original-figure3b-execution-v1/run.py"
        return module_from_bytes("_language_dual_outcome_selected_runner", root / rel, bodies[rel])
    finally:
        sys.path[:] = old_path
        for name, old in aliases.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def load_outcomes(pin):
    raw = read_pinned(HERE / "outcomes.py", maximum=MAX_SOURCE_BYTES,
                      expected_bytes=pin["bytes"], expected_sha256=pin["sha256"])
    return module_from_bytes("_language_original_figure3b_outcomes", HERE / "outcomes.py", raw)


def write_outcome(path, value, limit):
    raw = encoded(value)
    need(len(raw) <= limit <= MAX_OUTCOME_BYTES, "Complete additive result before output allocation")
    path = ordinary_absolute(str(path))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        need(stream.write(raw) == len(raw), "Complete additive result write")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o400)
    return {"bytes": len(raw), "sha256": sha(raw)}


def _run_validated_arm(value, runner):
    p = value["selected_protocol"]
    # The complete maintained runner alone constructs NativeProvider. Its real
    # host/qualification/admission checks still precede original store access.
    result = runner.run_protocol(p)
    need(type(result) is dict and result.get("scope") == p["scope"]
         and result.get("scientific_qualification") is False, "Maintained selected runner outcome")
    collection = pin_shape(result.get("collection"), MAX_RECOVERY_BYTES)
    recovery = pin_shape(result.get("recovery"), MAX_RECOVERY_BYTES)
    path = Path(p["output_root"]) / "RECOVERY.json"
    raw = read_pinned(path, maximum=MAX_RECOVERY_BYTES,
                      expected_bytes=recovery["bytes"], expected_sha256=recovery["sha256"])
    recovered = parse(raw)
    need(encoded(recovered) == raw, "Canonical authenticated maintained recovery")
    outcomes = load_outcomes(value["entry_sources"]["outcomes.py"])
    report = outcomes.compose_recovered(recovered, condition=value["condition"],
                                        collection_sha256=collection["sha256"],
                                        recovery_sha256=recovery["sha256"],
                                        source_root=value["dependency_root"])
    final = {"schema": "language-original-figure3b-dual-outcome-entry-result/v1",
             "scope": SCOPE, "condition": value["condition"],
             "output_policy": value["output_policy"],
             "outcomes": report, "maintained_execution": result,
             "selected_protocol_sha256": value["selected_protocol_sha256"],
             "additive_protocol_sha256": sha(encoded(value)),
             "entry_sources": value["entry_sources"],
             "maintained_store_scope": p["scope"],
             "full_224_array_contract_changed": False,
             "protected_execution_qualification_promoted": False,
             "scientific_qualification": False,
             "additional_reporting_bounds": {"recovery_read_ceiling_bytes": MAX_RECOVERY_BYTES,
                                              "outcome_output_limit_bytes": value["outcome_output_bytes"],
                                              "candidate_executions_added_for_second_outcome": 0}}
    output = Path(p["output_root"]) / "FIGURE3B_OUTCOMES.json"
    pin = write_outcome(output, final, value["outcome_output_bytes"])
    return {"scope": SCOPE, "condition": value["condition"], "output": str(output),
            "outcomes_receipt": pin, "maintained_execution": result, "scientific_qualification": False}


def disjoint(paths):
    values = [Path(x) for x in paths]
    return all(a != b and a not in b.parents and b not in a.parents
               for i, a in enumerate(values) for b in values[i + 1:])


def validate_pair(value):
    need(type(value) is dict and set(value) == PAIR_KEYS and value["schema"] == PAIR_SCHEMA
         and value["scope"] == SCOPE
         and value["execution_policy"] == "sequential_two_existing_runs",
         "Exact paired task-local protocol")
    arms = value["arms"]
    need(type(arms) is dict and set(arms) == set(CONDITIONS), "Both complete access arms must be frozen")
    frozen = {condition: validate_envelope(arms[condition]) for condition in CONDITIONS}
    need(all(frozen[c]["condition"] == c for c in CONDITIONS), "Opposite exact arm conditions")
    a, b = (frozen[c] for c in CONDITIONS)
    need(a["dependency_root"] == b["dependency_root"] and a["entry_sources"] == b["entry_sources"]
         and a["outcome_output_bytes"] == b["outcome_output_bytes"],
         "Same reviewed implementations and report allowances for both arms")
    pa, pb = a["selected_protocol"], b["selected_protocol"]
    matched = ("source_pins", "store_root", "store_sha256", "store_read_limit", "store_working_limit",
               "schedule_sha256", "reference_path", "reference_sha256", "source_support_sha256",
               "numpy_version", "limits", "operator_joint_admission_bytes")
    need(all(key in pa and key in pb and pa[key] == pb[key] for key in matched),
         "Matched complete source/reference/runtime and resource allowances")
    ca, cb = pa["provider_config"], pb["provider_config"]
    provider_matched = ("schema", "mode", "provider_source_sha256", "store_sha256", "schedule_sha256",
                        "runtime", "bwrap", "cgroup_parent", "python_path", "caps")
    need(all(key in ca and key in cb and ca[key] == cb[key] for key in provider_matched),
         "Matched provider/runtime/resource policy")
    contexts = []
    for p, config in ((pa, ca), (pb, cb)):
        need(type(config.get("candidate")) is dict and type(config.get("assistance")) is dict,
             "Explicit candidate and assistance contexts")
        for root in (p["output_root"], p["provider_evidence_root"], config["candidate"]["root"]):
            ordinary_absolute(root)
            contexts.append(root)
    need(disjoint(contexts), "Disjoint per-arm output/provider/candidate contexts")
    output = ordinary_absolute(value["pair_output"])
    need(output.name.endswith(".json") and not output.exists() and not output.is_symlink(),
         "Fresh private paired result file")
    protected_paths = [str(HERE), a["dependency_root"]]
    for p in (pa, pb):
        protected_paths.extend([p["store_root"], p["reference_path"]])
        protected_paths.extend(p["provider_config"][key]["root"]
                               for key in ("candidate", "runtime", "assistance"))
    writing_paths = [str(output)]
    writing_paths.extend(p[key] for p in (pa, pb) for key in ("output_root", "provider_evidence_root"))
    need(all(disjoint([writer, protected_path]) for writer in writing_paths for protected_path in protected_paths),
         "All paired writing paths disjoint from both arms' protected sources/trees")
    need(all(disjoint([str(output), context]) for context in contexts),
         "Paired result cannot overlap either arm's output/provider/candidate context")
    need(type(value["pair_output_bytes"]) is int and 1 <= value["pair_output_bytes"] <= 131072,
         "Finite paired receipt allowance")
    result = parse(encoded(value))
    result["arms"] = frozen
    return result


def run_protocol(envelope):
    """One arm; it is not a completed two-condition study."""
    value = validate_envelope(envelope)
    runner = load_selected_runner(value["dependency_root"])
    return _run_validated_arm(value, runner)


def run_pair(protocol):
    """Freeze and preflight both protocols before either unchanged runner call."""
    value = validate_pair(protocol)
    runner = load_selected_runner(value["arms"][CONDITIONS[0]]["dependency_root"])
    for condition in CONDITIONS:
        p = value["arms"][condition]["selected_protocol"]
        validated = runner.validate_protocol(p)
        need(encoded(validated) == encoded(p), "Maintained preflight must preserve frozen protocol")
    completed = {}
    for condition in CONDITIONS:
        # A failure propagates. The completed first-arm file is retained; no pair
        # success is published and no automatic retry is attempted.
        completed[condition] = _run_validated_arm(value["arms"][condition], runner)
    result = {"schema": "language-original-figure3b-dual-outcome-pair-result/v1",
              "scope": SCOPE, "conditions": list(CONDITIONS), "arms": completed,
              "pair_protocol_sha256": sha(encoded(value)),
              "schedules": 2, "callbacks_per_candidate_condition": 5685,
              "total_software_callbacks_for_this_shared_output_pair": 11370,
              "shared_output_scoring_within_each_arm": True,
              "two_separately_frozen_programmes_per_arm_would_require_four_schedules": True,
              "full_224_array_contract_changed": False,
              "protected_execution_qualification_promoted": False,
              "scientific_qualification": False}
    pin = write_outcome(Path(value["pair_output"]), result, value["pair_output_bytes"])
    return {"scope": SCOPE, "conditions": list(CONDITIONS), "pair_output": value["pair_output"],
            "pair_receipt": pin, "arms": completed, "scientific_qualification": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--execute-admitted-native", required=True, choices=[TOKEN])
    args = parser.parse_args(argv)
    value = read_protocol(args.protocol, args.protocol_sha256)
    result = run_pair(value) if value["schema"] == PAIR_SCHEMA else run_protocol(value)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

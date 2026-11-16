"""Concrete additive evaluator for the fixed NEURAL-077 observed NPZ interface.

Authentic execution belongs in the already qualified isolated private grader.
The caller supplies its existing hash/ID-checking private_loader and references.
No candidate code is executed; no data or private loader is bundled here.
"""
import copy
import hashlib
import importlib.util
import math
import numbers
import os
from pathlib import Path
import stat
import types

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural077_supplemental_metrics", HERE / "supplemental_metrics.py")
supplemental = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supplemental)

CANONICAL_PINS = {
    "validator.py": {"bytes": 9277, "sha256": "5483d1b04e6f81d048351ca202c13a7c4183988469b88ca0274874b4714346a2"},
    "metrics.py": {"bytes": 8557, "sha256": "e053d4dbf7237b0e630a8b9f097ce4fb5bb3cd3f547e892b4aa425a736f6a99f"},
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pinned_bytes(path, pin, cap):
    need(type(pin) is dict and set(pin) == {"bytes", "sha256"}
         and type(pin["bytes"]) is int and 0 < pin["bytes"] <= cap
         and type(pin["sha256"]) is str and len(pin["sha256"]) == 64, "exact bounded file pin")
    path = Path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"], "ordinary exact file before open")
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        need(identity(opened) == identity(before) and stat.S_ISREG(opened.st_mode), "opened file identity")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(cap + 1)
        need(identity(before) == identity(os.fstat(fd)) == identity(path.lstat()), "file changed while reading")
    finally:
        os.close(fd)
    need(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"], "file pin mismatch")
    return body


def load_canonical(directory):
    # Authenticate both complete source bodies before executing either. Execute
    # those verified bytes, not a second pathname read or an ambient import.
    bodies = {name: pinned_bytes(Path(directory) / name, pin, 65536)
              for name, pin in CANONICAL_PINS.items()}
    modules = {}
    for name, body in bodies.items():
        module = types.ModuleType("neural077_pinned_" + Path(name).stem)
        module.__file__ = str(Path(directory) / name)
        exec(compile(body, module.__file__, "exec"), module.__dict__)
        modules[name] = module
    return modules["validator.py"], modules["metrics.py"]


def _merge_supplemental(ordered, private_loader, reference_scores, canonical_score):
    """Internal composition seam; the file entry point binds canonical_score.

    Keep original private dtypes for the canonical validator. Conversion to plain
    integer labels occurs only AFTER complete canonical scoring succeeds.
    """
    need(type(ordered) is dict and set(ordered) == set(supplemental.CASES), "both fixed probability cases")
    public_copy = {}
    for case in supplemental.CASES:
        values = list(ordered[case])
        need(len(values) == 200 and all(isinstance(v, numbers.Real) and not isinstance(v, bool)
             and math.isfinite(v) and 0 <= v <= 1 for v in values), "both complete public vectors before private loading")
        public_copy[case] = [float(v) for v in values]
    need(callable(private_loader) and callable(canonical_score), "trusted score and private-loader closures")
    cache = {}
    def recording_loader(case):
        need(case in supplemental.CASES and case not in cache, "one private load per declared person")
        original = private_loader(case)
        cache[case] = copy.deepcopy(original)
        return original  # Never launder float labels through int before validation.
    primary = canonical_score(ordered, recording_loader, reference_scores)
    need(type(primary) is dict and primary.get("status") == "scored"
         and primary.get("target_loader_invocations") == 2
         and set(cache) == set(supplemental.CASES), "complete canonical score before supplementation")
    need("supplemental_metrics" not in primary, "no replacement of an existing supplement")
    labels = {case: [int(v) for v in cache[case]] for case in supplemental.CASES}
    result = dict(primary)  # Every canonical key/value remains unchanged.
    result["supplemental_metrics"] = supplemental.summarize(public_copy, labels)
    result["supplemental_metrics"]["additional_private_loader_invocations"] = 0
    result["supplemental_metrics"]["input_condition_is_operator_declared"] = True
    return result


def evaluate_submission(submission_path, expected_ids, private_loader, reference_scores,
                        canonical_directory, *, submission_pin, condition):
    """Score the same committed observed-input 400-row NPZ, adding two metrics.

    The operator authenticates the observed-input producer receipt and proves
    producer absence before this call. A condition string alone does not establish
    that provenance. The input file must remain frozen/read-only throughout.
    """
    need(condition == "observed_signal", "only the selected observed-input endpoint")
    need(type(expected_ids) is dict and set(expected_ids) == set(supplemental.CASES)
         and all(len(expected_ids[c]) == 200 for c in supplemental.CASES), "fixed two-person public ID contract")
    pinned_bytes(submission_path, submission_pin, 1048576)
    validator, metrics = load_canonical(canonical_directory)
    ordered = validator.validate(submission_path, expected_ids)
    # Detect any file change during public validation before private access.
    pinned_bytes(submission_path, submission_pin, 1048576)
    return _merge_supplemental(ordered, private_loader, reference_scores, metrics.score_candidate)

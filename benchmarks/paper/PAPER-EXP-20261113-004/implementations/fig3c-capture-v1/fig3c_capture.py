"""Bind source-shaped owner JSON projections to the pinned Figure 3c scorer.

This is not a dill loader. Projection creation, original observation custody,
native return containers and publication-reference admission remain external.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types


COMMIT = "adf0f9ed3defa22275d92fa0ed996f47008e05b3"
CAPTURE_SCHEMA = "reward-relative-fig3c-owner-projection-v1"
SUPPORT_SCHEMA = "reward-relative-fig3c-owner-support-v1"
PROFILE_BYTES = 12881
PROFILE_SHA256 = "9fd76c464a0e33e3267b8229dca3a6ab256f61866a070d6189c8975885f22444"
FIELDS = ("pred", "actual", "pred_shuffle", "actual_shuffle")
REPEATS = tuple(str(i) for i in range(100))


class CaptureError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise CaptureError(message)


def exact(obj, fields, name):
    need(type(obj) is dict and set(obj) == set(fields), name + ": exact keys required")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def hash_value(value, name):
    need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value), name + ": invalid SHA256")


def bounded_bytes(path, maximum):
    """Read one ordinary file once, with an operator-declared finite byte cap."""
    need(type(maximum) is int and 0 < maximum < 2**63, "positive finite byte cap required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, "ordinary bounded input required")
        raw = handle.read(before.st_size)
        need(not handle.read(1), "input grew beyond observed extent")
        after = os.fstat(handle.fileno())
    need(len(raw) == before.st_size <= maximum and
         (before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "input changed or exceeded cap")
    return raw


def read_bound_json(path, expected_sha256, maximum):
    hash_value(expected_sha256, "external input digest")
    raw = bounded_bytes(path, maximum)
    need(sha(raw) == expected_sha256, "input byte digest mismatch")

    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def reject(value):
        raise CaptureError("nonfinite JSON constant; source NaN must be null")

    def floating(value):
        result = float(value)
        need(math.isfinite(result), "nonfinite JSON exponent")
        return result

    try:
        value = json.loads(raw.decode("utf8"), object_pairs_hook=pairs,
                           parse_constant=reject, parse_float=floating)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaptureError("invalid UTF-8 JSON") from exc
    return value


class CaptureAdapter:
    def __init__(self, profile_path=None):
        if profile_path is None:
            profile_path = Path(__file__).resolve().parent.parent / "fig3c-profiles-v1" / "fig3c_profiles.py"
        raw = bounded_bytes(profile_path, PROFILE_BYTES)
        need(len(raw) == PROFILE_BYTES and sha(raw) == PROFILE_SHA256,
             "accepted Figure 3c dependency pin mismatch")
        # Execute only the exact trusted benchmark module bytes, never the
        # captured author notebook or input contents. Avoid a second file read.
        module = types.ModuleType("_pinned_exp004_fig3c_profiles")
        module.__file__ = str(profile_path)
        exec(compile(raw, str(profile_path), "exec"), module.__dict__)
        self.profiles = module

    def _panel(self, capture, support):
        """Map declared JSON projection axes; complete semantic checks are in score."""
        p = self.profiles
        exact(capture, ("schema", "source_commit", *FIELDS), "capture")
        need(capture["schema"] == CAPTURE_SCHEMA and capture["source_commit"] == COMMIT,
             "wrong capture projection/source")
        exact(support, ("schema", "source_commit", "preparation_sha256",
                        "fold_receipt_sha256", "sample_ids"), "support")
        need(support["schema"] == SUPPORT_SCHEMA and support["source_commit"] == COMMIT,
             "wrong support projection/source")
        for field in ("preparation_sha256", "fold_receipt_sha256"):
            hash_value(support[field], field)
        days = tuple(str(day) for day in p.DAYS)
        exact(support["sample_ids"], days, "support days")
        for field in FIELDS:
            exact(capture[field], days, field + " days")
            for day in days:
                exact(capture[field][day], p.ANIMALS, field + " animals")
                for animal in p.ANIMALS:
                    exact(capture[field][day][animal], p.CELL_TYPES, field + " populations")
                    for cell in p.CELL_TYPES:
                        exact(capture[field][day][animal][cell], p.MODELS, field + " cross-switch models")
        for day in days:
            exact(support["sample_ids"][day], p.ANIMALS, "support animals")
            for animal in p.ANIMALS:
                exact(support["sample_ids"][day][animal], p.MODELS, "support models")

        def vectors(obj, name):
            need(type(obj) is list and len(obj) == 10 and all(type(x) is list for x in obj),
                 name + ": ten ordered fold vectors required")
            return obj

        rows = []
        for day in p.DAYS:
            key = str(day)
            for animal in p.ANIMALS:
                for cell in p.CELL_TYPES:
                    for model in p.MODELS:
                        pred, actual, shuffled_pred, shuffled_actual = (
                            capture[field][key][animal][cell][model] for field in FIELDS)
                        ids = vectors(support["sample_ids"][key][animal][model], "sample IDs")
                        vectors(pred, "real prediction")
                        vectors(actual, "real target")
                        exact(shuffled_pred, REPEATS, "shuffle prediction repeats")
                        exact(shuffled_actual, REPEATS, "shuffle target repeats")
                        folds = [{"sample_ids": ids[f], "actual": actual[f], "predicted": pred[f]}
                                 for f in range(10)]
                        shuffles = []
                        for repeat in REPEATS:
                            prediction = vectors(shuffled_pred[repeat], "shuffle prediction")
                            target = vectors(shuffled_actual[repeat], "shuffle target")
                            # Reuse original IDs only because source shuffles roll
                            # neural inputs with unchanged y/ds; the scorer requires
                            # every shuffled target/order to equal the real target.
                            shuffles.append([{"sample_ids": ids[f], "actual": target[f],
                                              "predicted": prediction[f]} for f in range(10)])
                        rows.append({"animal": animal, "day": day, "cell_type": cell,
                                     "model": model, "folds": folds, "shuffles": shuffles})
        return {"schema": p.SCHEMA, "source_commit": COMMIT,
                "preparation_sha256": support["preparation_sha256"],
                "fold_receipt_sha256": support["fold_receipt_sha256"], "rows": rows}

    def score(self, capture, support):
        """Validate complete support and compute all 462 companion conditions."""
        try:
            result = self.profiles.score_panel(self._panel(capture, support))
        except self.profiles.InputError as exc:
            raise CaptureError(str(exc)) from exc
        result["capture_binding"] = {
            "projection_schema": CAPTURE_SCHEMA, "support_schema": SUPPORT_SCHEMA,
            "accepted_profile_module_sha256": PROFILE_SHA256,
            "capture_semantic_sha256": self.profiles.digest(capture),
            "support_semantic_sha256": self.profiles.digest(support),
            "native_serialization_loaded": False, "observation_custody_authenticated": False,
            "publication_artifact_authenticated": False,
            "qualification": "source-shaped owner projection mapped; scientific admission remains external"}
        return result

    def score_files(self, capture_path, support_path, *, capture_sha256, support_sha256,
                    max_capture_bytes, max_support_bytes):
        capture = read_bound_json(capture_path, capture_sha256, max_capture_bytes)
        support = read_bound_json(support_path, support_sha256, max_support_bytes)
        result = self.score(capture, support)
        result["capture_binding"].update(capture_file_sha256=capture_sha256,
                                         support_file_sha256=support_sha256,
                                         identity_only_not_provider_authentication=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--support", required=True)
    parser.add_argument("--capture-sha256", required=True)
    parser.add_argument("--support-sha256", required=True)
    parser.add_argument("--max-capture-bytes", required=True, type=int)
    parser.add_argument("--max-support-bytes", required=True, type=int)
    parser.add_argument("--profile-module")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = CaptureAdapter(args.profile_module).score_files(
            args.capture, args.support, capture_sha256=args.capture_sha256,
            support_sha256=args.support_sha256, max_capture_bytes=args.max_capture_bytes,
            max_support_bytes=args.max_support_bytes)
        with Path(args.output).open("x") as handle:
            json.dump(result, handle, allow_nan=False, separators=(",", ":"))
            handle.write("\n")
    except (CaptureError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()

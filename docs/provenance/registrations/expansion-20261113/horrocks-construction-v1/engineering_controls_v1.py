"""One finite synthetic engineering invocation; no science/model/network/MATLAB.
Owner-selected after whole-source review. All generated fixtures/output stay outside
the source queue. Tiny ZIP tests temporarily substitute synthetic identity constants;
they never assert that an official data archive was acquired or admitted.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import time
import traceback
from unittest.mock import patch
import zipfile

MAX_BYTES = 8 * 1024 * 1024
MAX_SECONDS = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", required=True)
    args = ap.parse_args()
    work = Path(args.work_dir)
    work.mkdir(parents=False, exist_ok=False)
    source = Path(__file__).with_name("horrocks_contract_v2.py")
    spec = importlib.util.spec_from_file_location("horrocks_reviewed", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    h = module
    start = time.monotonic()
    results = []

    def control(name, function):
        if time.monotonic() - start > MAX_SECONDS:
            raise RuntimeError("engineering wall budget exhausted")
        try:
            detail = function()
            results.append({"name": name, "status": "PASS", "detail": detail})
        except Exception as error:
            results.append({"name": name, "status": "FAIL", "exception": type(error).__name__,
                            "message": str(error), "traceback": traceback.format_exc()})

    def refuses(function, *args, errors=(h.Refusal,)):
        try:
            function(*args)
        except errors:
            return "refused"
        raise AssertionError("unexpected acceptance")

    def intake():
        sessions = []
        for mouse, date in h.ROSTER:
            trials = [{"trial_id": hashlib.sha256(f"synthetic:{mouse}:{i}".encode()).hexdigest()[:32],
                       "source_ordinal": i, "onset_s": i*3.0,
                       "state": h.STATES[(i//6) % 2], "visual_class": i % 6 + 1}
                      for i in range(241)]
            sessions.append({"mouse": mouse, "session": date, "member_sha256": "a"*64, "trials": trials})
        return {"schema": "horrocks-owner-trial-index-v1", "archive_sha256": "b"*64,
                "sessions": sessions}

    original = intake()
    protocol = h.make_protocol(original)

    def prediction_rows(p, constant=None):
        return [{"trial_id": t["trial_id"], "window": w,
                 "prediction": t["visual_class"] if constant is None else constant}
                for s in p["body"]["sessions"] for t in s["trials"]
                if t["partition"] == "evaluation" and t["state"] is not None
                for w in h.WINDOWS]

    truth_rows = prediction_rows(protocol)
    chance_rows = prediction_rows(protocol, 1)

    def zip_fixture(name, extra=None):
        path = work / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as z:
            for mouse, date in h.ROSTER:
                z.writestr(f"synthetic/{mouse}_{date}_basic.mat", b"synthetic-not-MAT")
            if extra:
                extra(z)
        return path

    def inspect_synthetic(path, limit=100000):
        data = path.read_bytes()
        with patch.object(h, "ARCHIVE_BYTES", len(data)), patch.object(h, "ARCHIVE_MD5", hashlib.md5(data).hexdigest()):
            return h.authenticate_archive_inventory(path, limit)

    valid_zip = zip_fixture("synthetic.zip")

    def valid_archive():
        out = inspect_synthetic(valid_zip)
        assert len(out["selected_sessions"]) == 5 and not out["scientifically_admitted"]
        assert not out["member_content_hashes_verified"]
        return "synthetic identity/index only; no MATLAB content or official-data admission"

    control("actual_official_pin_rejects_synthetic_archive",
            lambda: refuses(h.authenticate_archive_inventory, valid_zip, 100000))
    control("synthetic_archive_identity_and_all_five_members", valid_archive)

    def wrong_digest():
        with patch.object(h, "ARCHIVE_BYTES", valid_zip.stat().st_size):
            return refuses(h.authenticate_archive_inventory, valid_zip, 100000)
    control("wrong_digest_after_matching_size", wrong_digest)
    control("archive_unpack_budget", lambda: refuses(inspect_synthetic, valid_zip, 1))
    unsafe = zip_fixture("unsafe.zip", lambda z: z.writestr("../escape", b"x"))
    control("archive_traversal", lambda: refuses(inspect_synthetic, unsafe))
    duplicate = zip_fixture("ambiguous.zip",
                            lambda z: z.writestr("another/M22027_20220517_basic.mat", b"x"))
    control("archive_ambiguous_canonical_session", lambda: refuses(inspect_synthetic, duplicate))

    def symlink_member(z):
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, "synthetic/M22027_20220517_basic.mat")
    link_zip = zip_fixture("member-symlink.zip", symlink_member)
    control("archive_member_symlink", lambda: refuses(inspect_synthetic, link_zip))
    link = work / "archive-link.zip"
    link.symlink_to(valid_zip.name)
    control("archive_path_symlink", lambda: refuses(inspect_synthetic, link, errors=(OSError, h.Refusal)))

    def canonical_order():
        shuffled = copy.deepcopy(original)
        shuffled["sessions"].reverse()
        p = h.make_protocol(shuffled)
        assert p == protocol
        assert h.validate_protocol(p) == p["body"]
        return "valid reversed input reconstructs identically"
    control("canonical_session_order_round_trip", canonical_order)

    def mutation_intake(transform):
        value = copy.deepcopy(original)
        transform(value)
        return refuses(h.make_protocol, value)
    control("missing_mouse", lambda: mutation_intake(lambda d: d["sessions"].pop()))
    control("duplicate_mouse", lambda: mutation_intake(
        lambda d: d["sessions"].__setitem__(1, copy.deepcopy(d["sessions"][0]))))
    control("incomplete_trial_census", lambda: mutation_intake(
        lambda d: d["sessions"][0]["trials"].pop(2)))
    control("duplicate_trial_id", lambda: mutation_intake(
        lambda d: d["sessions"][0]["trials"][1].__setitem__("trial_id", d["sessions"][0]["trials"][0]["trial_id"])))
    control("nonchronological_onset", lambda: mutation_intake(
        lambda d: d["sessions"][0]["trials"][1].__setitem__("onset_s", 0.0)))

    def overlapping_guard(d):
        for t in d["sessions"][0]["trials"]:
            t["onset_s"] = t["source_ordinal"] * 0.5
    control("fixed_guard_full_window_overlap", lambda: mutation_intake(overlapping_guard))

    def missing_class(d, partition):
        for t in d["sessions"][0]["trials"]:
            selected = t["source_ordinal"] < 120 if partition == "calibration" else t["source_ordinal"] > 120
            if selected and t["visual_class"] == 6:
                t["visual_class"] = 5
    control("missing_calibration_class", lambda: mutation_intake(lambda d: missing_class(d, "calibration")))
    control("missing_evaluation_class", lambda: mutation_intake(lambda d: missing_class(d, "evaluation")))

    def altered_protocol(change):
        p = copy.deepcopy(protocol)
        change(p["body"])
        p["sha256"] = h.canonical_sha(p["body"])
        return refuses(h.validate_protocol, p)
    control("rehashed_partition_mutation", lambda: altered_protocol(
        lambda b: b["sessions"][0]["trials"][0].__setitem__("partition", "evaluation")))
    control("rehashed_time_window_mutation", lambda: altered_protocol(lambda b: b["window_ms"].pop()))

    def query_projection():
        mouse = h.ROSTER[0][0]
        query = h.public_query_index(protocol, mouse)
        assert query == sorted(query, key=lambda x: (x["trial_id"], x["window"]))
        assert all(set(row) == {"trial_id", "window"} for row in query)
        chronological = [t["trial_id"] for t in protocol["body"]["sessions"][0]["trials"]
                         if t["partition"] == "evaluation"]
        ordered = [row["trial_id"] for row in query if row["window"] == 0]
        assert ordered != chronological and set(ordered) == set(chronological)
        return "no chronological output order or owner metadata; real ID opacity remains an admission gate"
    control("query_projection_and_order", query_projection)

    def changed_predictions(change):
        rows = copy.deepcopy(truth_rows)
        change(rows)
        return refuses(h.score_improvement, protocol, rows, truth_rows, truth_rows)
    control("missing_prediction", lambda: changed_predictions(lambda r: r.pop()))
    control("duplicate_prediction", lambda: changed_predictions(lambda r: r.__setitem__(1, copy.deepcopy(r[0]))))
    control("extra_prediction_field", lambda: changed_predictions(lambda r: r[0].__setitem__("visual_class", 1)))
    for name, bad in (("nan", float("nan")), ("infinity", float("inf")),
                      ("boolean", True), ("float_class", 1.0), ("invalid_class", 7)):
        control("prediction_" + name, lambda value=bad: changed_predictions(
            lambda r: r[0].__setitem__("prediction", value)))
    control("required_full_baseline", lambda: refuses(h.score_improvement, protocol, truth_rows, [], truth_rows))
    control("required_diagonal_baseline", lambda: refuses(h.score_improvement, protocol, truth_rows, truth_rows, []))

    def equality():
        result = h.score_improvement(protocol, truth_rows, truth_rows, truth_rows)
        assert result["n_independent_animals"] == 5 and not result["scientifically_qualified"]
        assert result["mean_paired_delta"] == 0 and result["paired_animal_sem"] == 0
        assert list(result["paired_delta_by_animal"].values()) == [0]*5
        return "exact zero paired differences for five animals"
    control("paired_equality_and_n5", equality)

    def perfect_vs_constant():
        out = h.score_improvement(protocol, truth_rows, chance_rows, chance_rows)
        assert math.isclose(out["candidate"]["mean"], 1)
        assert math.isclose(out["full_lda"]["mean"], 1/6)
        assert math.isclose(out["mean_paired_delta"], 5/6)
        return "perfect=1, constant=1/6, paired delta=5/6"
    control("analytic_perfect_and_chance", perfect_vs_constant)

    def imbalanced():
        d = copy.deepcopy(original)
        for s in d["sessions"]:
            for t in s["trials"]:
                if t["source_ordinal"] > 132:
                    t["visual_class"] = 1
        p = h.make_protocol(d)
        rows = prediction_rows(p, 1)
        out = h.score_improvement(p, rows, rows, rows)
        assert math.isclose(out["candidate"]["mean"], 1/6)
        labels = [t["visual_class"] for s in p["body"]["sessions"] for t in s["trials"]
                  if t["partition"] == "evaluation"]
        assert sum(x == 1 for x in labels) / len(labels) > 0.8
        return "raw majority accuracy>0.8; balanced accuracy=1/6"
    control("imbalance_does_not_reward_majority", imbalanced)

    def unequal_animals():
        d = copy.deepcopy(original)
        mouse = h.ROSTER[0][0]
        d["sessions"][0]["trials"] = [
            {"trial_id": hashlib.sha256(f"synthetic:{mouse}:{i}".encode()).hexdigest()[:32],
             "source_ordinal": i, "onset_s": i*3.0,
             "state": h.STATES[(i//6) % 2], "visual_class": i % 6 + 1}
            for i in range(481)]
        p = h.make_protocol(d)
        rows = prediction_rows(p)
        first_ids = {t["trial_id"] for t in p["body"]["sessions"][0]["trials"]}
        for row in rows:
            if row["trial_id"] in first_ids:
                row["prediction"] = row["prediction"] % 6 + 1
        reference = prediction_rows(p)
        out = h.score_improvement(p, rows, reference, reference)
        assert math.isclose(out["candidate"]["mean"], 0.8)
        assert math.isclose(out["mean_paired_delta"], -0.2)
        return "double-sized failed animal retains one-fifth weight"
    control("equal_animal_weight_despite_trial_count", unequal_animals)

    def reproduction(value):
        return {mouse: {state: {"within_time": [value]*191,
                               "cross_time": [[value]*20 for _ in range(20)]}
                        for state in h.STATES} for mouse, _ in h.ROSTER}
    ref = reproduction(0.5)
    def reproduction_offsets():
        out = h.compare_reproduction(reproduction(0.75), ref, 0.25)
        assert out["maximum_absolute_error"] == 0.25 and out["within_owner_tolerance"]
        assert all(x["root_mean_squared_error"] == 0.25 for x in out["components"].values())
        assert not out["scientifically_qualified"]
        return "exact known0.25 offset; diagnostic tolerance only"
    control("complete_reproduction_numeric_comparison", reproduction_offsets)
    control("missing_reproduction_mouse", lambda: refuses(h.compare_reproduction,
            {k: v for k, v in ref.items() if k != h.ROSTER[0][0]}, ref))
    def incomplete_curve():
        value = copy.deepcopy(ref)
        value[h.ROSTER[0][0]][h.STATES[0]]["within_time"].pop()
        return refuses(h.compare_reproduction, value, ref)
    control("missing_reproduction_time", incomplete_curve)

    def relative_ratio():
        matrix = [[0.2]*20 for _ in range(20)]
        for i in range(20):
            matrix[i][i] = 0.8 if i % 2 == 0 else 0.4
        for i in range(2, 12):
            matrix[3][i] = 0.4 if i == 3 else 0.3
        out = h.relative_generalization(matrix, "paper_eq21_unclipped")
        assert math.isclose(out["relative_performance"], 43/130)
        return "hand-derived ratio43/130"
    control("relative_ratio_of_means", relative_ratio)
    def clipped():
        matrix = [[0.6]*20 for _ in range(20)]
        for i in range(2, 12):
            matrix[3][i] = 0.6 if i == 3 else 0.1
        paper = h.relative_generalization(matrix, "paper_eq21_unclipped")
        code = h.relative_generalization(matrix, "publication_analysis_clipped")
        assert math.isclose(paper["relative_performance"], -1/26)
        assert math.isclose(code["relative_performance"], 0.1)
        return "unclipped=-1/26, clipped=0.1; never conflated"
    control("distinct_clipping_conventions", clipped)
    control("undefined_relative_denominator", lambda: refuses(
        h.relative_generalization, [[1/6]*20 for _ in range(20)], "paper_eq21_unclipped"))
    control("strict_json_duplicate_keys", lambda: refuses(h.strict_json, '{"x":1,"x":2}'))
    control("strict_json_nonfinite", lambda: refuses(h.strict_json, '{"x":NaN}'))

    report = {"schema": "horrocks-finite-engineering-result-v1", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "synthetic": True, "scientific_results": False, "new_ready_benchmarks": 0,
              "elapsed_seconds": time.monotonic()-start, "controls": results,
              "passed": sum(x["status"] == "PASS" for x in results),
              "failed": sum(x["status"] == "FAIL" for x in results)}
    output = work / "RESULT.json"
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    retained = sum(x.stat().st_size for x in work.rglob("*") if x.is_file() and not x.is_symlink())
    report["retained_fixture_and_output_bytes_before_summary"] = retained
    report["within_selected_limits"] = retained + 4096 <= MAX_BYTES and report["elapsed_seconds"] <= MAX_SECONDS
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"result_path": str(output), "result_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "passed": report["passed"], "failed": report["failed"],
                      "elapsed_seconds": report["elapsed_seconds"], "fixture_output_bytes": retained,
                      "within_selected_limits": report["within_selected_limits"]}))
    return 0 if report["failed"] == 0 and report["within_selected_limits"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

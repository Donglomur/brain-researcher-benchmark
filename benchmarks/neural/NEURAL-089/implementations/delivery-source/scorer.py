"""Official-2025-compatible 39-class metrics, strict complete-ID input boundary."""
import argparse
import hashlib
import math
from pathlib import Path
from io_contract import TASK, ID, MAX_JSON, fields, header, need, panel_ids, read, strict, write


def predictions(value, panel):
    ids = panel_ids(panel); header(value, "predictions")
    rows = value["predictions"]
    need(type(rows) is list and len(rows) == len(ids), "all query probabilities required")
    result = {}
    for row in rows:
        fields(row, ["query_id", "probabilities"])
        q, p = row["query_id"], row["probabilities"]
        need(type(q) is str and ID.fullmatch(q) and q not in result, "unique opaque query")
        need(type(p) is list and len(p) == 39, "exact39 probabilities in frozen class order")
        try: valid = all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in p)
        except OverflowError: valid = False
        need(valid and abs(math.fsum(p) - 1.) <= 1e-6, "finite probability simplex; booleans forbidden")
        # max returns the first index on ties, exactly as NumPy argmax.
        result[q] = max(range(39), key=p.__getitem__)
    need(set(result) == set(ids), "exact query coverage")
    return result


def labels(value, panel, panel_sha256):
    fields(value, ["schema_version", "task_id", "panel_sha256", "targets"])
    need(type(value["schema_version"]) is int and value["schema_version"] == 1 and value["task_id"] == TASK
         and value["panel_sha256"] == panel_sha256, "private target task/panel binding")
    rows = value["targets"]; ids = panel_ids(panel)
    need(type(rows) is list and len(rows) == len(ids), "complete private targets")
    result = {}
    for row in rows:
        fields(row, ["query_id", "label"]); q, y = row["query_id"], row["label"]
        need(type(q) is str and ID.fullmatch(q) and q not in result
             and type(y) is int and 0 <= y < 39, "exact private target row")
        result[q] = y
    need(set(result) == set(ids), "complete private target join")
    return result


def metrics(predicted, truth, ids):
    confusion = [[0] * 39 for _ in range(39)]
    for q in ids: confusion[truth[q]][predicted[q]] += 1
    per_class = []
    for i in range(39):
        tp = confusion[i][i]; support = sum(confusion[i]); called = sum(row[i] for row in confusion)
        precision = tp / called if called else 0.
        recall = tp / support if support else 0.
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
        per_class.append({"class_id": i, "support": support, "predicted": called,
                          "precision": precision, "recall": recall, "f1": f1})
    return {"macro_f1_39": math.fsum(r["f1"] for r in per_class) / 39,
            "accuracy": sum(confusion[i][i] for i in range(39)) / len(ids),
            "macro_precision_39": math.fsum(r["precision"] for r in per_class) / 39,
            "macro_recall_39": math.fsum(r["recall"] for r in per_class) / 39,
            "query_count": len(ids), "per_class": per_class, "confusion_matrix": confusion}


def score_files(submission_path, panel_path, targets_path, targets_sha256):
    private_read = False
    try:
        need(type(targets_sha256) is str and len(targets_sha256) == 64, "private target SHA256 required")
        panel_raw = read(panel_path); panel = strict(panel_raw); ids = panel_ids(panel)
        try: pred = predictions(strict(read(submission_path)), panel)
        except (ValueError, OSError, OverflowError) as error:
            return {"status": "invalid_submission", "metrics": None, "private_targets_read": False, "reason": str(error)[:300]}
        target_raw = read(targets_path); private_read = True
        need(hashlib.sha256(target_raw).hexdigest() == targets_sha256, "private target SHA256 mismatch")
        truth = labels(strict(target_raw), panel, hashlib.sha256(panel_raw).hexdigest())
        return {"status": "scored", "task_id": TASK, "metrics": metrics(pred, truth, ids),
                "primary": "macro_f1_39", "direction": "higher", "secondary": "accuracy",
                "private_targets_read": True, "candidate_executed": False,
                "scientific_success_threshold": None, "scientific_success": None,
                "scope": "All queries in one native held run, one person; no across-person inference."}
    except (ValueError, OSError) as error:
        return {"status": "operator_error", "metrics": None, "private_targets_read": private_read, "reason": str(error)[:300]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("submission", "panel", "targets", "output"): p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--targets-sha256", required=True); a = p.parse_args(argv)
    result = score_files(a.submission, a.panel, a.targets, a.targets_sha256); write(a.output, result)
    return {"scored": 0, "invalid_submission": 2, "operator_error": 1}[result["status"]]


if __name__ == "__main__": raise SystemExit(main())

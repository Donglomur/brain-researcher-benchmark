"""Unchanged original39-class metric kernels; full-panel grading remains protected."""
import math,re
TASK="NEURAL-089"
ID=re.compile(r"[0-9a-f]{24}\Z")
MAX_QUERIES=200000
need=c.need
def fields(value, keys): need(type(value) is dict and set(value) == set(keys), "exact fields required")

def header(value, tail):
    fields(value, ["schema_version", "task_id", tail])
    need(type(value["schema_version"]) is int and value["schema_version"] == 1 and value["task_id"] == TASK,
         "exact task/schema")

def panel_ids(value):
    header(value, "query_ids")
    ids = value["query_ids"]
    need(type(ids) is list and 1 <= len(ids) <= MAX_QUERIES and all(type(q) is str and ID.fullmatch(q) for q in ids)
         and len(set(ids)) == len(ids), "complete unique opaque panel")
    return ids

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

ORIGINAL_LOCK_PIN={'bytes': 91873, 'sha256': '23489ecda2cfb13fcb425593fa9370f64e4188c8aca7f5c9d79bb4343e0ddcba'}
if c.pin(source_bodies['source_identity/ORIGINAL_ASSETS.json'])!=ORIGINAL_LOCK_PIN:raise ValueError('exact original source lock')
ORIGINAL_ASSETS=c.parse(source_bodies['source_identity/ORIGINAL_ASSETS.json'])

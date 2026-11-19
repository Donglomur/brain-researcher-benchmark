"""One complete generated scalar fixture; no original values or model fitting."""
import hashlib
import generic_contract as contract
import generic_prepare as prepare
from storage import encoded


def fixture():
    people = contract.published_participants()
    folds, start = {}, 0
    for fold, count in enumerate([10] * 4 + [9] * 6):
        for participant in people[start:start + count]:
            folds[participant] = fold
        start += count
    records = [{"row_key": hashlib.sha256(("generated-" + person + "-" + label).encode()).hexdigest(),
                "participant": person, "label": label, "value": (index + 1) / 200}
               for index, (person, label) in enumerate((p, label) for p in people for label in contract.PAIR)]
    plan_folds = []
    for fold in range(10):
        held = [i for i, row in enumerate(records) if folds[row["participant"]] == fold]
        train = [i for i in range(188) if i not in held]
        plan_folds.append({"fold": fold, "train_indices": train, "test_indices": held,
            "train_row_keys": [records[i]["row_key"] for i in train],
            "test_row_keys": [records[i]["row_key"] for i in held],
            "train_participants": [p for p in people if folds[p] != fold],
            "test_participants": [p for p in people if folds[p] == fold]})
    plan = {"orientation": list(contract.ORIENTATION), "folds": plan_folds,
            "source_order_sha256": prepare.source_order_hash(records),
            "recipe": "generated fixed participant map", "sklearn_version": "not run",
            "historical_folds_replayed": False}
    ledger = {"schema": "meg-frozen-before-first-fit-v1", "plans": [plan],
              "input_sha256": prepare.INVENTORY_PIN["sha256"]}
    predictions, probabilities = [], {}
    correct_by_fold = [13, 16, 13, 11, 13, 13, 9, 13, 10, 10]
    for fold, state in enumerate(plan_folds):
        for local, index in enumerate(state["test_indices"]):
            row = records[index]
            predicted = row["label"] if local < correct_by_fold[fold] else contract.PAIR[1 - contract.PAIR.index(row["label"])]
            probability = 0.75 if predicted == "object" else 0.25
            predictions.append({"row_key": row["row_key"], "participant": row["participant"],
                "truth": row["label"], "prediction": predicted, "p_object": probability, "fold": fold})
            probabilities[contract.source_id(row["participant"], row["label"])] = probability
    reference = {"schema": "meg-fresh-reference-result-v1", "status": "success",
        "input_sha256": prepare.INVENTORY_PIN["sha256"], "roster": list(people),
        "primary_orientation": list(contract.ORIENTATION), "plans": [plan],
        "results": [{"arm": prepare.REFERENCE_ARM, "orientation": list(contract.ORIENTATION),
                     "predictions": predictions, "metrics": {"generated_only": True},
                     "fits": 0, "test_batch_access": "generated fixture; no fits"}]}
    panel = contract.build_panel(records, folds, b"g" * 32, prepare.INVENTORY_PIN)
    responses = {}
    for role in ("A", "B"):
        responses[role] = {}
        by_id = {r["id"]: r["source_id"] for r in panel["private_records"]}
        for fold in range(10):
            context = contract.public_context(panel, fold)
            responses[role][fold] = {"schema": contract.RESPONSE_SCHEMA, "input_mode": contract.MODE,
                "context_sha256": context["context_sha256"],
                "probabilities": {i: probabilities[by_id[i]] for i in context["queries"]}}
    arms = {role: contract.collect(panel, responses[role], "reproduction") for role in ("A", "B")}
    return {"records": records, "folds": folds, "panel": panel, "reference": reference,
            "ledger": ledger, "responses": responses, "arms": arms,
            "binding": contract.reference_binding(panel)}

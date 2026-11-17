"""Pure sealed reference tool: allowed event in, three values out, no file/API I/O.

The protected runtime authenticates and loads only the matched eligible model;
this module has no target, metric, training-row, network or mutable cache API.
"""
from owner.io import ContractError
from .schema import admit_rows
from .primary import predict


def predict_one(model, request):
    if not isinstance(request, dict) or set(request) != {"view", "event"}:
        raise ContractError("exact reference inference request required")
    view = request["view"]
    if view not in ("T", "N") or model.get("view") != view:
        raise ContractError("matched model/information view required")
    event = request["event"]
    if not isinstance(event, dict) or event.get("split") != "query":
        raise ContractError("one query event required")
    rows = admit_rows({"schema": "neural063_rows_v2", "split": "query", "rows": [event]},
                      "query", view=view, require_target=False, expected_mice=1)
    result = predict(rows, model)
    return {"id": result[0]["id"], "values": result[0]["values"]}

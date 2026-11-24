"""Lossless restricted numeric observations and complete response collection.

Consumes the existing public one-query ABI only. This is a source component,
not an isolation mechanism or an authentic-data qualification receipt.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ARMS = ("SIGNAL", "PRE", "NUISANCE", "SIGNAL_NUISANCE", "PRE_NUISANCE")
CHANNELS = ("MEG1931", "MEG2121", "MEG2331", "MEG1921", "MEG2111", "MEG2341")
DURATIONS = ("500ms", "1000ms", "1500ms")
RELEVANCES = ("Irrelevant", "Relevant non-target")
ORIENTATIONS = ("Center", "Left", "Right")
UNITS = "T means for SIGNAL/PRE columns; binary design indicators for NUISANCE"


class ObservationError(ValueError):
    """Invalid public input; never permission to omit a case."""


def need(ok, message):
    if not ok:
        raise ObservationError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), "Exact object fields required")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def identity(value):
    body = canonical(value)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def nonce(value):
    need(type(value) is str and len(value) == 48 and set(value) <= set("0123456789abcdef"),
         "Expected an opaque 24-byte hexadecimal nonce")


def columns(arm):
    need(arm in ARMS, "Exact existing feature arm required")
    source = "SIGNAL" if arm.startswith("SIGNAL") else "PRE"
    neural = [{"name": f"{source}:{channel}:bin{b:02d}", "units": "T", "channel": channel,
               "bin_index": b} for channel in CHANNELS for b in range(10)]
    nuisance = [{"name": name + ":" + value, "units": "indicator"}
                for name, values in (("Duration", DURATIONS), ("Task_relevance", RELEVANCES),
                                     ("Orientation", ORIENTATIONS)) for value in values]
    return nuisance if arm == "NUISANCE" else neural + (nuisance if arm.endswith("_NUISANCE") else [])


def byte_pin(value, path=None):
    exact(value, ("bytes", "sha256") if path is None else ("path", "bytes", "sha256"))
    need(type(value["bytes"]) is int and value["bytes"] >= 0, "Nonnegative integer byte count")
    h = value["sha256"]
    need(type(h) is str and len(h) == 64 and set(h) <= set("0123456789abcdef"), "Lowercase SHA256")
    if path is not None:
        need(value["path"] == path, "Exact public member path")


def validate_query(query, arm):
    exact(query, ("schema", "opaque_episode_nonce", "opaque_query_nonce", "x_numeric_vector"))
    need(query["schema"] == "neural097-query-v2", "Existing label-hidden one-query schema required")
    nonce(query["opaque_episode_nonce"])
    nonce(query["opaque_query_nonce"])
    values = query["x_numeric_vector"]
    need(type(values) is list and len(values) == len(columns(arm)), "Complete selected feature vector")
    for value in values:
        need(type(value) in (int, float), "Nonboolean numeric features required")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        need(finite, "Representable finite features required")
    if arm == "NUISANCE" or arm.endswith("_NUISANCE"):
        indicators = values[-8:]
        need(all(value in (0, 1) for value in indicators)
             and all(sum(group) == 1 for group in (indicators[:3], indicators[3:5], indicators[5:])),
             "Exactly one original indicator per duration, relevance and orientation")


def make_packet(training_view, query):
    """Project an admitted public query; never consume protected observations.

    The training view identity binds the calibration context and its three
    member identities. It does not demonstrate that a participant received it.
    """
    exact(training_view, ("schema", "opaque_episode_nonce", "contract_version", "access_arm",
                          "feature_arm", "feature_columns", "feature_units", "features_member",
                          "training_rows_member", "inner_validation_plan_member"))
    need(training_view["schema"] == "neural097-train-view-v2", "Existing public training view required")
    nonce(training_view["opaque_episode_nonce"])
    need(training_view["access_arm"] in ("A", "B"), "Existing access arm required")
    arm = training_view["feature_arm"]
    need(training_view["feature_columns"] == columns(arm) and training_view["feature_units"] == UNITS,
         "Unchanged feature order and physical units required")
    exact(training_view["contract_version"], ("scientific", "estimand_reporting"))
    for key, path in (("scientific", "contracts/SCIENTIFIC_CONTRACT.json"),
                      ("estimand_reporting", "contracts/ESTIMAND_REPORTING_CONTRACT.json")):
        byte_pin(training_view["contract_version"][key], path)
    for key, path in (("features_member", "features.npy"), ("training_rows_member", "rows.json"),
                      ("inner_validation_plan_member", "inner.json")):
        byte_pin(training_view[key], path)
    validate_query(query, arm)
    need(query["opaque_episode_nonce"] == training_view["opaque_episode_nonce"], "Same training/query episode")
    # Copy only this allowlist: input labels, group joins and metadata cannot ride along.
    packet = {"schema": "n097-restricted-numeric-observation-v1", "query": query,
              "training_view_identity": identity(training_view), "access_arm": training_view["access_arm"],
              "feature_arm": arm, "feature_columns": columns(arm), "feature_units": UNITS}
    return json.loads(canonical(packet))


def validate_packet(packet):
    exact(packet, ("schema", "query", "training_view_identity", "access_arm", "feature_arm",
                   "feature_columns", "feature_units"))
    need(packet["schema"] == "n097-restricted-numeric-observation-v1", "Restricted observation schema")
    need(packet["access_arm"] in ("A", "B"), "Existing access arm required")
    arm = packet["feature_arm"]
    need(packet["feature_columns"] == columns(arm) and packet["feature_units"] == UNITS,
         "Exact fixed coordinate metadata required")
    byte_pin(packet["training_view_identity"])
    validate_query(packet["query"], arm)
    return packet


def render_text(packet):
    """Show every value with Python's round-trip numeric representation."""
    validate_packet(packet)
    q = packet["query"]
    lines = ["NEURAL-097 restricted numeric observation", "Face is positive; report p_face in [0,1].",
             "This card requests a single response. Tool restriction requires an external transport.",
             "Calibration context must be delivered separately with the same training view identity.",
             "Episode: " + q["opaque_episode_nonce"], "Query: " + q["opaque_query_nonce"],
             "Access: " + packet["access_arm"], "Feature arm: " + packet["feature_arm"],
             "Training view SHA256: " + packet["training_view_identity"]["sha256"],
             "Coordinate\tUnits\tValue"]
    lines.extend(f"{column['name']}\t{column['units']}\t{value!r}"
                 for column, value in zip(packet["feature_columns"], q["x_numeric_vector"]))
    return "\n".join(lines) + "\n"


def collect_responses(packets, responses):
    """Return the existing outcomes ABI for one complete expected episode.

    Operator-owned packets define the expected roster, never the response set.
    Missing responses become explicit failed outcomes. Unknown, duplicate or
    malformed submissions refuse collection; no successful subset is scored.
    The registered collector makes any abstained/failed condition unavailable.
    """
    need(type(packets) is list and 0 < len(packets) <= 20000, "Complete bounded episode packet roster")
    need(type(responses) is list and len(responses) <= 20000, "Bounded response list required")
    expected = {}
    context = None
    for packet in packets:
        validate_packet(packet)
        query = packet["query"]
        current = (query["opaque_episode_nonce"], packet["training_view_identity"],
                   packet["access_arm"], packet["feature_arm"])
        if context is None:
            context = current
        need(current == context, "One same-context episode, never mixed arms or training payloads")
        key = query["opaque_query_nonce"]
        need(key not in expected, "Unique complete expected query roster")
        expected[key] = packet
    received = {}
    for response in responses:
        need(type(response) is dict, "Typed response required")
        status = response.get("status")
        need(status in ("complete", "abstain", "failed"), "Typed original outcome status")
        fields = ("schema", "opaque_episode_nonce", "opaque_query_nonce", "status")
        exact(response, (*fields, "p_face" if status == "complete" else "reason"))
        need(response["schema"] == "neural097-query-prediction-v2", "Existing response ABI required")
        need(response["opaque_episode_nonce"] == context[0], "Response episode matches observation")
        key = response["opaque_query_nonce"]
        need(type(key) is str and key in expected and key not in received, "Unique expected query response")
        row = {"opaque_query_nonce": key, "status": status}
        if status == "complete":
            value = response["p_face"]
            need(type(value) in (int, float) and 0 <= value <= 1, "Finite nonboolean probability in [0,1]")
            row["p_face"] = value
        else:
            reason = response["reason"]
            need(type(reason) is str and 0 < len(reason) <= 256, "Bounded original failure reason")
            row["reason"] = reason
        received[key] = row
    rows = [received.get(key, {"opaque_query_nonce": key, "status": "failed", "reason": "missing_response"})
            for key in expected]
    return {"schema": "n097-query-outcomes-v1", "opaque_episode_nonce": context[0], "outcomes": rows}


def read_json(path, cap):
    path = Path(path)
    with path.open("rb") as stream:
        body = stream.read(cap + 1)
    need(len(body) <= cap, "Input exceeds complete artifact cap; never truncate")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def constant(_):
        raise ObservationError("Nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render", help="Render one existing public query without reading training payloads")
    for name in ("training-view", "query", "packet", "text"):
        render.add_argument("--" + name, required=True)
    collect = sub.add_parser("collect", help="Collect one complete trusted episode; preserve missing outcomes")
    for name in ("packets", "responses", "output"):
        collect.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.command == "render":
        packet = make_packet(read_json(args.training_view, 1000000), read_json(args.query, 100000))
        outputs = [(args.packet, canonical(packet)), (args.text, render_text(packet).encode())]
    else:
        body = collect_responses(read_json(args.packets, 100000000), read_json(args.responses, 16000000))
        outputs = [(args.output, canonical(body))]
    need(len({str(Path(path).absolute()) for path, _ in outputs}) == len(outputs), "Distinct fresh outputs")
    need(all(not Path(path).exists() for path, _ in outputs), "Fresh output paths required")
    for path, body in outputs:
        with Path(path).open("xb") as stream:
            stream.write(body)


if __name__ == "__main__":
    main()

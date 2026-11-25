"""Original search-panel evaluator; never fits or executes submitted code.

The public loader authenticates the original OSF archive before opening its CSV.
Pure helpers are for generated controls, not alternate source admission routes.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile


ARCHIVE_SHA256 = "5b3f614b1f629629bed5e52ab9f7f1c33bf46ad558d7e030bb74c67eba5ffcdc"
ARCHIVE_BYTES = 7_794_928
MEMBER = "data/brain-lang-data_participant_20230728.csv"
MEMBER_BYTES = 28_502_131
PARTICIPANTS = (797, 841, 880)
ITEMS = tuple(range(1, 1501))
ROI = "lang_LH_netw"
CONDITION_COUNTS = {"B": 1000, "D": 250, "S": 250}
SOURCE_COLUMNS = (
    "response_target,roi,target_UID,item_id,sentence,cond,cond_approach,"
    "encoding_model_pred,mapping_result_identifier,session_id,run_id,trial_num,"
    "run_within_session,log-prob-5gram_mean,log-prob-gpt2-xl_mean,log-prob-pcfg_mean,"
    "rating_arousal_mean,rating_conversational_mean,rating_sense_mean,rating_gram_mean,"
    "rating_frequency_mean,rating_imageability_mean,rating_others_thoughts_mean,"
    "rating_physical_mean,rating_places_mean,rating_valence_mean,response_target_non_norm"
).split(",")


class InvalidPanel(ValueError):
    """The requested complete source endpoint cannot be computed."""


def require(test, reason):
    if not test:
        raise InvalidPanel(reason)


def finite(value):
    require(not isinstance(value, bool), "boolean is not a measurement")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise InvalidPanel("invalid measurement") from error
    require(math.isfinite(result), "nonfinite measurement; no complete-case deletion")
    return result


def integer(value):
    require(type(value) in (str, int), "integer identity required")
    try:
        result = int(value)
    except ValueError as error:
        raise InvalidPanel("integer identity required") from error
    require(str(result) == str(value), "canonical integer identity required")
    return result


def mean(values):
    require(bool(values), "empty average")
    return math.fsum(x / len(values) for x in values)


def pearson(prediction, response):
    """Pearson r after removing a finite anchor; undefined remains explicit."""
    require(len(prediction) == len(response) and len(response) >= 2, "paired vectors required")
    require(all(math.isfinite(v) for v in prediction + response), "finite vectors required")
    constant_p = all(v == prediction[0] for v in prediction)
    constant_y = all(v == response[0] for v in response)
    if constant_p or constant_y:
        reason = "constant_both" if constant_p and constant_y else (
            "constant_prediction" if constant_p else "constant_response")
        return {"n_items": len(response), "r": None, "undefined_reason": reason}
    def center(values):
        # Subtract before scaling so representable differences near a large
        # common offset survive. Only opposite finite extremes need halving.
        origin = values[0]
        shifted = [v - origin for v in values]
        if not all(math.isfinite(v) for v in shifted):
            shifted = [v * 0.5 - origin * 0.5 for v in values]
        scale = max(map(abs, shifted))
        require(scale > 0, "numerically unresolved correlation")
        scaled = [v / scale for v in shifted]
        average = mean(scaled)
        return [v - average for v in scaled]

    p, y = center(prediction), center(response)
    pn, yn = math.hypot(*p), math.hypot(*y)
    require(pn > 0 and yn > 0, "numerically unresolved correlation")
    r = math.fsum((a / pn) * (b / yn) for a, b in zip(p, y))
    require(abs(r) <= 1 + 1e-12, "numerically invalid correlation")
    return {"n_items": len(response), "r": max(-1., min(1., r)), "undefined_reason": None}


@dataclass(frozen=True)
class Panel:
    conditions: tuple[str, ...]
    normalized: tuple[tuple[float, ...], ...]
    non_normalized: tuple[tuple[float, ...], ...]
    source_predictions: tuple[float, ...]
    identity_sha256: str


def _panel_from_rows(rows):
    """Select before numeric conversion; never convert other people's outcomes."""
    cells, metadata, predictions = {}, {}, {}
    for row in rows:
        uid = integer(row["target_UID"])
        if uid not in PARTICIPANTS or row["roi"] != ROI:
            continue
        item = integer(row["item_id"])
        require(item in ITEMS, "unexpected original search item")
        key = (uid, item)
        require(key not in cells, "duplicate participant/item target")
        cond = row["cond"]
        require(cond in CONDITION_COUNTS, "unknown condition")
        require(row["cond_approach"] == ("B" if cond == "B" else cond + "_search"),
                "modify and search panels cannot be exchanged")
        require((cond == "B") == (item <= 1000), "original repeated baseline identity changed")
        current = (row["sentence"], cond, row["cond_approach"])
        require(type(current[0]) is str and bool(current[0]), "sentence identity required")
        require(item not in metadata or metadata[item] == current,
                "sentence/condition identity differs between participants")
        metadata[item] = current
        pred = finite(row["encoding_model_pred"])
        require(item not in predictions or predictions[item] == pred,
                "source encoding prediction differs between participants")
        predictions[item] = pred
        cells[key] = (finite(row["response_target"]), finite(row["response_target_non_norm"]))
    require(set(cells) == {(u, i) for u in PARTICIPANTS for i in ITEMS},
            "all 4500 original participant/item observations required")
    conditions = tuple(metadata[i][1] for i in ITEMS)
    require({c: conditions.count(c) for c in CONDITION_COUNTS} == CONDITION_COUNTS,
            "original 1000/250/250 condition allocation required")
    identity = [[i, *metadata[i]] for i in ITEMS]
    identity_hash = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return Panel(conditions,
                 tuple(tuple(cells[u, i][0] for i in ITEMS) for u in PARTICIPANTS),
                 tuple(tuple(cells[u, i][1] for i in ITEMS) for u in PARTICIPANTS),
                 tuple(predictions[i] for i in ITEMS), identity_hash)


@contextmanager
def original_rows(path):
    """Operator-only authenticated CSV stream; no extraction or code execution."""
    with Path(path).open("rb") as raw:
        body = raw.read(ARCHIVE_BYTES + 1)
    require(len(body) == ARCHIVE_BYTES, "wrong OSF archive length")
    require(hashlib.sha256(body).hexdigest() == ARCHIVE_SHA256, "wrong OSF archive SHA256")
    # Decode exactly the bytes whose identity was checked. A retained file
    # descriptor alone does not prevent in-place changes after authentication.
    with io.BytesIO(body) as authenticated:
        with tarfile.open(fileobj=authenticated, mode="r:*") as archive:
            members = [m for m in archive.getmembers() if m.name == MEMBER]
            require(len(members) == 1 and members[0].isfile() and members[0].size == MEMBER_BYTES,
                    "exact original regular CSV member required")
            with archive.extractfile(members[0]) as member:
                reader = csv.DictReader(io.TextIOWrapper(member, encoding="utf-8-sig", newline=""))
                require(reader.fieldnames == SOURCE_COLUMNS, "original CSV columns changed")
                yield reader


def load_original_archive(path):
    """Operator-only. No extraction, pickle, source code or private oracle reads."""
    with original_rows(path) as rows:
        return _panel_from_rows(rows)


def load_predictions(path):
    require(Path(path).stat().st_size <= 200_000, "prediction CSV exceeds 200 KB")
    predictions = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == ["item_id", "prediction"], "prediction columns must be item_id,prediction")
        for row in reader:
            require(set(row) == {"item_id", "prediction"}, "malformed prediction row")
            item = integer(row["item_id"])
            require(item in ITEMS and item not in predictions, "duplicate or unknown prediction item")
            predictions[item] = finite(row["prediction"])
    require(set(predictions) == set(ITEMS), "all 1500 predictions required")
    return [predictions[i] for i in ITEMS]


def _condition_effects(panel):
    out = {}
    for label, values in (("voxel_session_z_before_ROI_mean", panel.normalized),
                          ("source_non_normalized_BOLD", panel.non_normalized)):
        item_means = [mean(list(x)) for x in zip(*values)]
        means = {c: mean([y for y, condition in zip(item_means, panel.conditions) if condition == c])
                 for c in CONDITION_COUNTS}
        out[label] = {"means": means, "contrasts": {"D-B": means["D"] - means["B"],
                                                     "S-B": means["S"] - means["B"]}}
    raw = out["source_non_normalized_BOLD"]["means"]
    percent = {c: 100 * (raw[c] / raw["B"] - 1) if raw["B"] != 0 else None for c in ("D", "S")}
    require(all(v is None or math.isfinite(v) for v in percent.values()), "nonfinite relative BOLD change")
    out["percent_change_from_baseline"] = percent
    out["percent_denominator"] = raw["B"]
    out["zero_denominator"] = raw["B"] == 0
    out["scope"] = "Fig.2b event-related descriptive means only; no mixed-model inference or blocked/modify substitution"
    return out


def score(panel, prediction):
    require(len(prediction) == len(ITEMS), "full original panel prediction required")
    prediction = [finite(v) for v in prediction]
    response = [mean(list(x)) for x in zip(*panel.normalized)]
    source = list(panel.source_predictions)
    groups = {"all_1500": list(range(1500))}
    groups.update({c: [i for i, label in enumerate(panel.conditions) if label == c]
                   for c in CONDITION_COUNTS})
    scores = {}
    for name, indices in groups.items():
        candidate = pearson([prediction[i] for i in indices], [response[i] for i in indices])
        author = pearson([source[i] for i in indices], [response[i] for i in indices])
        delta = None if candidate["r"] is None or author["r"] is None else candidate["r"] - author["r"]
        scores[name] = {"candidate": candidate, "released_author_prediction": author,
                        "descriptive_candidate_minus_released_author_r": delta}
    return {
        "schema": "original_fig3_measurement_v1", "source_archive_sha256": ARCHIVE_SHA256,
        "identity_sha256": panel.identity_sha256, "participants": list(PARTICIPANTS),
        "n_observations": 4500, "n_items": 1500, "condition_item_counts": dict(CONDITION_COUNTS),
        "roi": ROI, "response_units": "source bySessVoxZ: voxel/session z before ROI averaging",
        "primary_endpoint": "all_1500", "aggregation": "mean three people within item, then Pearson across 1500 items",
        "metrics": scores, "participant_diagnostics": {
            str(u): pearson(prediction, list(y)) for u, y in zip(PARTICIPANTS, panel.normalized)},
        "response_effect_calibration": _condition_effects(panel),
        "published_author_final_rounded_r": {"all_1500": 0.43, "B": 0.30},
        "author_replay": "not performed; released predictions are not an independently refitted comparator",
        "scientific_limits": [
            "Descriptive fixed-panel measurement, no effect-size or uncertainty decision rule.",
            "Public historical responses and predictions; this function does not establish blind access.",
            "Blocked experiment, linguistic-control fits and complete 184-handle obligations remain separate.",
            "No whole-registration win, prospective stimulus-control improvement, or SOTA claim."
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    predictions = load_predictions(args.predictions)
    result = score(load_original_archive(args.archive), predictions)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

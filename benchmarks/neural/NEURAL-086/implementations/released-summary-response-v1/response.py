"""Static numerical observations for one qualified NEURAL-086 FFD job.

This is an operator-owned presentation/collection component, not a process
sandbox or an admitted ZuCo campaign. It never opens recordings or gold labels.
"""

import copy
import hashlib
import html
import json
import math
import re

TASK = "NEURAL-086"
ARMS = ("COVARIATES", "PLUS_EEG", "COVARIATES_SHUFFLED_E")
BANDS = ("t1", "t2", "a1", "a2", "b1", "b2", "g1", "g2")
BAND_HZ = ((4, 6), (6.5, 8), (8.5, 10), (10.5, 13),
           (13.5, 18), (18.5, 30), (30.5, 40), (40, 49.5))
NUMERIC = ("word_chars", "word_position_fraction", "previous_word_chars",
           "next_word_chars", "sentence_words", "sentence_mean_word_chars",
           "sentence_type_token_ratio", "train_word_logcount", "train_word_oov",
           "sentence_train_unigram_surprisal", "FFD_ms", "GD_ms", "GPT_ms",
           "TRT_ms", "nFixations", "meanPupilSize", "window_pupilSize",
           "omissionRate", "sentence_duration_seconds")
BASE_NAMES = NUMERIC + tuple("missing_" + x for x in NUMERIC) + tuple(
    "missing_EEG_" + b for b in BANDS)
IDENTITY_KEYS = ("task", "person_token", "item_fold", "context", "arm",
                 "representation", "mode", "seed", "programme_sha256",
                 "source_sha256", "split_sha256", "information_set",
                 "generation", "role", "method")
HEX = re.compile(r"[0-9a-f]{64}\Z")


def need(condition, code):
    if not condition:
        raise ValueError(code)


def exact(obj, fields, code):
    need(type(obj) is dict and set(obj) == set(fields), code)


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def encode(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(obj):
    return hashlib.sha256(obj if type(obj) is bytes else encode(obj)).hexdigest()


def _decode(raw):
    def pairs(rows):
        obj = {}
        for key, value in rows:
            need(key not in obj, "duplicate_json_key")
            obj[key] = value
        return obj
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("nonfinite_json")))


def _hex(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def _pin(raw, descriptor):
    exact(descriptor, ("bytes", "sha256"), "input_pin_fields")
    need(type(descriptor["bytes"]) is int and descriptor["bytes"] == len(raw)
         and _hex(descriptor["sha256"]) and digest(raw) == descriptor["sha256"],
         "input_pin_mismatch")


def _features(value, arm):
    exact(value, ("base",) if arm == "COVARIATES" else ("base", "eeg"),
          "closed_feature_blocks")
    base = value["base"]
    need(type(base) is list and len(base) == 46, "base46")
    need(all(x is None or finite(x) for x in base[:19]), "base_numeric")
    need(all(type(x) is int and x in (0, 1) for x in base[19:]), "binary_masks")
    need(base[19:38] == [int(x is None) for x in base[:19]], "base_missingness")
    if arm != "COVARIATES":
        eeg = value["eeg"]
        need(type(eeg) is list and len(eeg) == 8 and
             all(x is None or finite(x) for x in eeg), "eight_scalp_means")
        need(base[38:] == [int(x is None) for x in eeg], "eeg_missingness")


class Session:
    """Keep issuer bytes private; expose only fixed observations and responses.

    `binding` must be frozen independently by the trusted operator before
    participant exposure. Deriving it from a participant's chosen subset would
    defeat the census check. Its hashes establish identity, not source truth.
    The actual participant must never receive this object or its private state.
    """

    def __init__(self, training_bytes, query_bytes, binding, *, max_input_bytes):
        need(type(max_input_bytes) is int and max_input_bytes > 0, "input_budget")
        need(type(training_bytes) is bytes and type(query_bytes) is bytes and
             len(training_bytes) + len(query_bytes) <= max_input_bytes,
             "input_bytes_budget")
        exact(binding, ("training", "query", "identity_sha256",
                        "training_census_sha256", "query_ids"), "binding_fields")
        _pin(training_bytes, binding["training"])
        _pin(query_bytes, binding["query"])
        training, query = _decode(training_bytes), _decode(query_bytes)
        exact(training, ("train", "identity", "information_set"), "training_fields")
        exact(query, ("query", "identity", "information_set"), "query_fields")
        identity = training["identity"]
        exact(identity, IDENTITY_KEYS, "identity_fields")
        need(identity == query["identity"] and digest(identity) == binding["identity_sha256"],
             "bound_same_identity")
        need(identity["task"] == TASK and identity["context"] == "FFD" and
             identity["representation"] == "released_summary" and
             identity["role"] == "participant" and identity["method"] == "candidate"
             and identity["arm"] in ARMS, "supported_source_job")
        need(identity["mode"] in ("frozen_program", "case_adaptive") and
             type(identity["item_fold"]) is int and 0 <= identity["item_fold"] < 5
             and type(identity["seed"]) is int and identity["seed"] == 0,
             "source_schedule")
        need(all(_hex(identity[k]) for k in ("person_token", "programme_sha256",
                 "source_sha256", "split_sha256", "generation")), "opaque_source_identity")
        need(all(x == "offline_case_local" for x in
                 (identity["information_set"], training["information_set"],
                  query["information_set"])), "information_set")
        need(type(training["train"]) is list and training["train"] and
             type(query["query"]) is list, "row_lists")
        train_ids, query_ids, person_labels = [], [], {}
        for kind, rows in (("train", training["train"]), ("query", query["query"])):
            for row in rows:
                fields = ("id", "features", "label", "weight", "person_group", "item_group") if kind == "train" else ("id", "features")
                exact(row, fields, "closed_" + kind + "_row")
                need(_hex(row["id"]), "opaque_row_id")
                _features(row["features"], identity["arm"])
                (train_ids if kind == "train" else query_ids).append(row["id"])
                if kind == "train":
                    need(type(row["label"]) is int and row["label"] in (0, 1), "training_label")
                    need(finite(row["weight"]) and row["weight"] > 0, "positive_training_weight")
                    need(_hex(row["person_group"]) and _hex(row["item_group"]), "opaque_training_groups")
                    person_labels.setdefault(row["person_group"], set()).add(row["label"])
        need(len(person_labels) == 17 and all(labels == {0, 1} for labels in person_labels.values()),
             "seventeen_training_people_both_conditions")
        need(len(set(train_ids)) == len(train_ids) and len(set(query_ids)) == len(query_ids)
             and not set(train_ids) & set(query_ids), "unique_disjoint_rows")
        need(_hex(binding["training_census_sha256"]) and
             digest(train_ids) == binding["training_census_sha256"], "training_census")
        need(type(binding["query_ids"]) is list and query_ids == binding["query_ids"], "query_census")
        self._training = copy.deepcopy(training["train"])
        self._query = copy.deepcopy(query["query"])
        self._binding = copy.deepcopy(binding)
        self._identity = copy.deepcopy(identity)
        self._people = {value: "person-%03d" % i for i, value in enumerate(sorted(person_labels), 1)}
        groups = sorted({r["item_group"] for r in self._training})
        self._items = {value: "item-%05d" % i for i, value in enumerate(groups, 1)}
        self._session = digest(binding)
        self._phase = "calibration"
        self._presented = set()
        self._responses = {}
        self._actions = []

    def overview(self):
        need(self._phase != "closed", "closed_session")
        return {"session": self._session, "task": TASK, "context": "FFD",
                "representation": "released_summary_numeric_card",
                "arm": self._identity["arm"], "training_rows": len(self._training),
                "query_rows": len(self._query), "training_people": 17,
                "target": "probability of TSR (1); NR is 0",
                "base_columns": list(BASE_NAMES),
                "eeg_columns": [] if self._identity["arm"] == "COVARIATES" else list(BANDS),
                "limitations": "Source-derived summary values, not EEG traces; no runtime isolation or scientific qualification."}

    def _observation(self, index, training):
        need(self._phase != "closed", "closed_session")
        rows = self._training if training else self._query
        need(type(index) is int and 0 <= index < len(rows), "row_index")
        if not training:
            need(self._phase == "inference", "inference_not_started")
            self._presented.add(index)
        row = rows[index]
        result = {"session": self._session,
                  "token": ("training-" if training else "query-") + str(index),
                  "kind": "calibration" if training else "query",
                  "base": dict(zip(BASE_NAMES, row["features"]["base"]))}
        if "eeg" in row["features"]:
            result["eeg"] = {band: {"value": value, "source_band_hz": list(bounds)}
                             for band, value, bounds in zip(BANDS, row["features"]["eeg"], BAND_HZ)}
        if training:
            result.update(label=row["label"], weight=row["weight"],
                          person_group=self._people[row["person_group"]],
                          item_group=self._items[row["item_group"]])
        self._actions.append({"action": "training" if training else "query", "index": index})
        return copy.deepcopy(result)

    def training(self, index):
        """All calibration rows remain available before and during inference."""
        return self._observation(index, True)

    def begin_inference(self):
        need(self._phase == "calibration", "calibration_already_closed")
        self._phase = "inference"
        self._actions.append({"action": "begin_inference"})
        return {"session": self._session, "query_rows": len(self._query)}

    def query(self, index):
        return self._observation(index, False)

    def answer(self, session, token, probability):
        need(self._phase == "inference", "inference_not_open")
        need(session == self._session and type(token) is str and
             re.fullmatch(r"query-(0|[1-9][0-9]*)", token) is not None, "response_binding")
        index = int(token[6:])
        need(index in self._presented and index < len(self._query), "query_not_presented")
        need(index not in self._responses, "response_already_final")
        need(finite(probability) and 0 <= probability <= 1, "finite_probability")
        self._responses[index] = probability
        self._actions.append({"action": "answer", "index": index, "p": probability})

    def finish_operator(self):
        """Return source-ID mapping to the trusted operator, never the participant.

        This report is NOT a programme execution receipt and cannot bypass the
        campaign's source, global admission, target-last or rubric gates.
        """
        need(self._phase == "inference", "inference_not_open")
        need(set(self._responses) == set(range(len(self._query))), "incomplete_responses")
        self._phase = "closed"
        probabilities = [{"id": row["id"], "p": self._responses[i]}
                         for i, row in enumerate(self._query)]
        return {"schema": "neural086-summary-response-collection/v1",
                "session": self._session, "source_identity": copy.deepcopy(self._identity),
                "input_binding": copy.deepcopy(self._binding), "probabilities": probabilities,
                "probability_sha256": digest(probabilities), "actions": copy.deepcopy(self._actions),
                "prediction_count": len(probabilities),
                "query_disposition": "all_supplied_queries_answered" if probabilities else
                    "empty_supplied_query_census_requires_operator_disposition",
                "complete_supplied_job": True, "scientifically_qualified": False,
                "campaign_admitted": False, "runtime_isolation_established": False}


def render_svg(observation):
    """Render a complete static numerical card without autoscaling or truncation.

    Use only an observation emitted by Session. Returned SVG is source text;
    this function does not prove a model saw raster pixels or can read the card.
    """
    keys = {"session", "token", "kind", "base"}
    if observation.get("kind") == "calibration":
        keys |= {"label", "weight", "person_group", "item_group"}
    if "eeg" in observation:
        keys.add("eeg")
    exact(observation, keys, "observation_fields")
    need(observation["kind"] in ("calibration", "query"), "observation_kind")
    lines = ["NEURAL-086 | FFD released summaries | " + observation["token"],
             "Numerical feature card; not an EEG waveform. null = unavailable."]
    if observation["kind"] == "calibration":
        lines.append("label=%s weight=%s %s %s" % (observation["label"], observation["weight"],
                     observation["person_group"], observation["item_group"]))
    lines.extend(name + " = " + json.dumps(value, allow_nan=False)
                 for name, value in observation["base"].items())
    if "eeg" in observation:
        lines.extend("EEG " + band + " " + str(value["source_band_hz"]) + " Hz = " +
                     json.dumps(value["value"], allow_nan=False) for band, value in observation["eeg"].items())
    need(len(lines) <= 64 and all(len(line) <= 1024 for line in lines), "bounded_card_lines")
    height = 30 + 22 * len(lines)
    width = max(1100, 32 + 9 * max(map(len, lines)))
    # A fixed textLength makes the complete numeric line fit the declared SVG
    # extent even when the renderer's fallback monospace font differs.
    texts = "".join('<text x="16" y="%d" textLength="%d" lengthAdjust="spacingAndGlyphs">%s</text>' %
                    (26 + 22 * i, 9 * len(line), html.escape(line))
                    for i, line in enumerate(lines))
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="100%%" height="100%%" fill="white"/><g font-family="monospace" font-size="14" fill="black">%s</g></svg>' % (width, height, width, height, texts)
    need(len(svg.encode("utf-8")) <= 131072, "svg_byte_limit")
    return svg

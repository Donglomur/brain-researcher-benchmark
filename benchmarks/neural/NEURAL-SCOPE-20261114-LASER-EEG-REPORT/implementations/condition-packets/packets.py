"""Owner-side packet construction from reviewed normalized laser-EEG inputs.

This module neither reads native recordings nor runs a candidate. Its outputs
are an evidence-matching interface, not proof of source or execution admission.
"""
import hashlib
import hmac
import json
import math
import re
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

TASK_ID = "NEURAL-SCOPE-20261114-LASER-EEG-REPORT"
COUNTS = (26, 29, 39, 30, 65, 95, 142, 223, 29)
DEVICES = ("BioSemi", "ANT", "BrainProducts", "ANT", "ANT", "BrainProducts",
           "BioSemi", "BrainProducts", "BrainProducts")
MAX_EPOCH_BYTES = 32 * 1024 * 1024
MAX_LIVE_TOKENS = 1_048_576


class ContractError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ContractError(message)


def exact(value, fields, name):
    need(type(value) is dict and set(value) == set(fields), name + ": exact fields")


def identifier(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value),
         "normalized identifier required; never a filesystem path")
    return value


def pin(value):
    need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "SHA-256 required")
    return value


def number(value, *, lower=None, upper=None):
    need(type(value) in (int, float), "finite numeric operand; Boolean is not numeric")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise ContractError("numeric representation refused") from None
    need(math.isfinite(result), "finite numeric operand required")
    need(lower is None or result >= lower, "numeric operand below domain")
    need(upper is None or result <= upper, "numeric operand above domain")
    return result


def encode(value):
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("ascii")
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ContractError("ordinary finite JSON value required") from None


def sha256(value):
    return hashlib.sha256(encode(value)).hexdigest()


def decode_epoch(raw, expected):
    need(type(raw) is bytes and len(raw) <= MAX_EPOCH_BYTES,
         "complete normalized epoch exceeds source-interface byte bound")
    need(hashlib.sha256(raw).hexdigest() == expected, "normalized epoch body changed")
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate normalized epoch field")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: need(False, "nonfinite JSON literal"))
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("invalid normalized epoch JSON") from None


def _text(value, limit, label):
    need(type(value) is str and 0 < len(value) <= limit, label)
    return value


def validate_protocol(protocol):
    exact(protocol, ("schema", "task_id", "documentation", "documentation_sha256",
                     "context_review_sha256", "contexts", "stimulated_sides"), "protocol")
    need(protocol["schema"] == "lep-packet-protocol-v1" and protocol["task_id"] == TASK_ID,
         "packet protocol identity")
    text = _text(protocol["documentation"], 1_000_000, "complete reviewed documentation")
    need(hashlib.sha256(text.encode("utf-8")).hexdigest() == pin(protocol["documentation_sha256"]),
         "documentation body identity")
    pin(protocol["context_review_sha256"])
    need(type(protocol["contexts"]) is dict and protocol["contexts"], "reviewed context table")
    for key, value in protocol["contexts"].items():
        identifier(key)
        exact(value, ("device", "reference", "rating_protocol"), "reviewed context")
        need(value["device"] in DEVICES, "declared acquisition device")
        _text(value["reference"], 256, "reviewed reference description")
        _text(value["rating_protocol"], 2048, "reviewed intensity-report protocol")
    sides = protocol["stimulated_sides"]
    need(type(sides) is list and sides and all(type(side) is str for side in sides)
         and len(set(sides)) == len(sides), "reviewed side categories")
    for side in sides:
        identifier(side)


def validate_representation(representation):
    exact(representation, ("schema", "task_id", "normalization_review_sha256",
                           "endpoint_convention", "times_us", "sample_rate_hz",
                           "bandlimit_hz", "quantization_uv", "montages"), "representation")
    need(representation["schema"] == "lep-normalized-representation-v1"
         and representation["task_id"] == TASK_ID, "representation identity")
    pin(representation["normalization_review_sha256"])
    need(type(representation["sample_rate_hz"]) is int and representation["sample_rate_hz"] == 100,
         "declared 100-Hz common representation")
    need(type(representation["bandlimit_hz"]) is int and representation["bandlimit_hz"] == 30,
         "declared 30-Hz bandlimit; filtering itself is an external source gate")
    need(type(representation["quantization_uv"]) in (int, float)
         and representation["quantization_uv"] == 0.01, "declared 0.01-microvolt quantum")
    endpoint = representation["endpoint_convention"]
    need(endpoint in ("right_open", "inclusive"), "owner must freeze the endpoint convention")
    stop = 2_000_000 if endpoint == "right_open" else 2_000_001
    times = representation["times_us"]
    need(type(times) is list and all(type(t) is int for t in times)
         and times == list(range(-1_000_000, stop, 10_000)), "complete declared epoch grid")
    montages = representation["montages"]
    need(type(montages) is dict and montages, "complete reviewed montage table")
    for key, montage in montages.items():
        identifier(key)
        exact(montage, ("coordinate_system", "channels"), "montage")
        identifier(montage["coordinate_system"])
        need(type(montage["channels"]) is list and montage["channels"], "complete EEG channel roster")
        labels = set()
        for channel in montage["channels"]:
            exact(channel, ("label", "xyz_mm"), "EEG channel")
            label = identifier(channel["label"])
            need(label not in labels, "duplicate EEG channel")
            labels.add(label)
            xyz = channel["xyz_mm"]
            need(xyz is None or type(xyz) is list and len(xyz) == 3, "coordinate triplet or explicit missing")
            if xyz is not None:
                for coordinate in xyz:
                    number(coordinate)


class PreparedAssay:
    """Trusted owner object. Never expose this object or its loader to a candidate.

    Only authoring_packet()/query_packet() bytes cross the candidate boundary.
    Every epoch is loaded by an explicit trusted callback and matched to its pin.
    """

    def __init__(self, ledger, protocol, representation, epoch_loader, *,
                 protocol_sha256, representation_sha256, support_salt, opaque_key):
        pin(protocol_sha256)
        pin(representation_sha256)
        need(sha256(protocol) == protocol_sha256, "reviewed protocol changed")
        need(sha256(representation) == representation_sha256, "reviewed representation changed")
        need(type(support_salt) is bytes and len(support_salt) == 32, "fixed 32-byte support salt")
        need(type(opaque_key) is bytes and len(opaque_key) == 32, "independent 32-byte opaque-ID key")
        need(support_salt != opaque_key, "separate selection and opaque-ID secrets")
        need(callable(epoch_loader), "trusted normalized epoch loader")
        validate_protocol(protocol)
        validate_representation(representation)
        # Freeze metadata by value. Loader changes are detected by body pins.
        self.protocol = json.loads(encode(protocol))
        self.representation = json.loads(encode(representation))
        self.protocol_sha256, self.representation_sha256 = protocol_sha256, representation_sha256
        self._salt, self._key, self._loader = support_salt, opaque_key, epoch_loader
        self._ledger = json.loads(encode(ledger))
        self._people, self._trials, self._queries = {}, {}, {}
        self._validate_ledger()
        self._supports, self._purged = self._select_supports()

    def _opaque(self, purpose, values):
        return hmac.new(self._key, encode(["lep-opaque-v1", purpose, values]), hashlib.sha256).hexdigest()

    def _trial_id(self, fold, key):
        return self._opaque("trial", [fold, *key])

    def _validate_ledger(self):
        doc = self._ledger
        exact(doc, ("schema", "task_id", "protocol_sha256", "representation_sha256",
                    "inventory_receipt_sha256", "producer_receipt_sha256",
                    "identity_receipt_sha256", "identity_linkage", "people"), "normalized ledger")
        need(doc["schema"] == "lep-normalized-ledger-v1" and doc["task_id"] == TASK_ID,
             "normalized ledger identity")
        need(doc["protocol_sha256"] == self.protocol_sha256
             and doc["representation_sha256"] == self.representation_sha256, "ledger policy mismatch")
        for field in ("inventory_receipt_sha256", "producer_receipt_sha256", "identity_receipt_sha256"):
            pin(doc[field])
        need(doc["identity_linkage"] in ("complete", "unresolved"), "explicit person linkage scope")
        need(type(doc["people"]) is list and len(doc["people"]) == 678, "all 678 nominal people required")
        eligible_aliases = set()
        for person in doc["people"]:
            exact(person, ("experiment", "person_key", "biological_group", "trials"), "person")
            exp, pkey = person["experiment"], identifier(person["person_key"])
            need(type(exp) is int and 1 <= exp <= 9, "exact integer experiment 1..9")
            pk = (exp, pkey)
            need(pk not in self._people, "duplicate nominal person")
            group = person["biological_group"]
            need(group is not None or doc["identity_linkage"] == "unresolved", "complete linkage needs every person group")
            if group is not None:
                identifier(group)
            need(type(person["trials"]) is list and person["trials"], "complete source trial ledger")
            previous, eligible = -1, []
            for trial in person["trials"]:
                exact(trial, ("trial_key", "chronology", "eligible", "rating", "exclusion_reason",
                              "alias_group", "epoch_sha256", "montage_id", "context_id"), "trial")
                key = (exp, pkey, identifier(trial["trial_key"]))
                need(key not in self._trials, "duplicate canonical source trial")
                order = trial["chronology"]
                need(type(order) is int and order >= 0 and order > previous, "strict source chronology")
                previous = order
                identifier(trial["alias_group"])
                need(type(trial["eligible"]) is bool, "explicit predeclared eligibility")
                if trial["eligible"]:
                    need(trial["alias_group"] not in eligible_aliases,
                         "duplicate eligible source trial alias; canonicalize with documented exclusions")
                    eligible_aliases.add(trial["alias_group"])
                    number(trial["rating"], lower=0, upper=10)
                    need(trial["exclusion_reason"] is None, "eligible trial has no exclusion reason")
                    pin(trial["epoch_sha256"])
                    identifier(trial["montage_id"])
                    identifier(trial["context_id"])
                    need(trial["montage_id"] in self.representation["montages"], "reviewed complete montage binding")
                    context = self.protocol["contexts"].get(trial["context_id"])
                    need(context is not None and context["device"] == DEVICES[exp - 1], "experiment device/context binding")
                    eligible.append(key)
                else:
                    need(trial["rating"] is None and trial["epoch_sha256"] is None
                         and trial["montage_id"] is None and trial["context_id"] is None,
                         "excluded trial has no target or normalized payload")
                    _text(trial["exclusion_reason"], 512, "predeclared exclusion reason")
                self._trials[key] = trial
            need(len(eligible) >= 3, "fewer than three eligible trials holds the full assay")
            self._people[pk] = {"person": person, "eligible": eligible}
            for key in eligible[2:]:
                self._queries[self._trial_id(exp, key)] = key
        for exp, expected in enumerate(COUNTS, 1):
            need(sum(key[0] == exp for key in self._people) == expected, "all nine registered experiment counts")

    def _select_supports(self):
        # A shared trial alias establishes a person link even when the biological
        # identity table is incomplete. Close those links transitively, retaining
        # excluded trials as provenance, before selecting any support.
        parents = {pk: pk for pk in self._people}
        def root(pk):
            while parents[pk] != pk:
                parents[pk] = parents[parents[pk]]
                pk = parents[pk]
            return pk
        def join(left, right):
            left, right = root(left), root(right)
            if left != right:
                parents[max(left, right)] = min(left, right)
        links = {}
        for pk, person in self._people.items():
            group = person["person"]["biological_group"]
            identifiers = [("alias", trial["alias_group"])
                           for trial in person["person"]["trials"]]
            if group is not None:
                identifiers.append(("person", group))
            for identity in identifiers:
                if identity in links:
                    join(pk, links[identity])
                else:
                    links[identity] = pk
        supports, purged = {}, {}
        for fold in range(1, 10):
            heldout_components = {root(pk) for pk in self._people if pk[0] == fold}
            chosen, excluded = [], []
            for train in range(1, 10):
                if train == fold:
                    continue
                pool = []
                for pk, person in self._people.items():
                    if pk[0] != train:
                        continue
                    repeated_person = root(pk) in heldout_components
                    for key in person["eligible"]:
                        if repeated_person:
                            excluded.append(key)
                        else:
                            pool.append(key)
                need(pool, "purging held-out cohort leaves a training experiment without a support")
                def ordering(key):
                    digest = hashlib.sha256(self._salt + encode(["lep-support-v1", *key])).digest()
                    return digest, key
                chosen.append(min(pool, key=ordering))
            supports[fold], purged[fold] = tuple(chosen), tuple(sorted(excluded))
        return supports, purged

    @property
    def query_ids(self):
        return tuple(sorted(self._queries))

    def _case(self, fold, key, *, labeled):
        trial = self._trials[key]
        raw = self._loader(key)
        epoch = decode_epoch(raw, trial["epoch_sha256"])
        exact(epoch, ("schema", "representation_sha256", "samples_uv", "valid_mask",
                      "delivered_energy_j", "stimulated_side", "calibration_category"), "normalized epoch")
        need(epoch["schema"] == "lep-normalized-epoch-v1"
             and epoch["representation_sha256"] == self.representation_sha256, "epoch representation")
        montage = self.representation["montages"][trial["montage_id"]]
        values, mask = epoch["samples_uv"], epoch["valid_mask"]
        channels, times = len(montage["channels"]), len(self.representation["times_us"])
        need(type(values) is list and type(mask) is list and len(values) == len(mask) == channels,
             "complete channel roster; no common-channel intersection")
        quantized, missing, max_residual = [], 0, Decimal(0)
        for data, valid in zip(values, mask):
            need(type(data) is list and type(valid) is list and len(data) == len(valid) == times,
                 "every grid sample retained")
            row = []
            for value, observed in zip(data, valid):
                need(type(observed) is bool, "explicit sample mask")
                if not observed:
                    need(value is None, "missing samples stay missing, never imputed")
                    row.append(None)
                    missing += 1
                    continue
                number(value)
                physical = Decimal(str(value))
                with localcontext() as context:
                    context.prec = max(50, len(physical.as_tuple().digits)
                                       + abs(physical.as_tuple().exponent) + 4)
                    integer = int((physical * 100).to_integral_value(rounding=ROUND_HALF_EVEN))
                    residual = abs(physical - Decimal(integer) / 100)
                need(residual <= Decimal("0.005"), "quantization residual bound")
                max_residual = max(max_residual, residual)
                row.append(integer)
            quantized.append(row)
        energy = epoch["delivered_energy_j"]
        if energy is not None:
            number(energy, lower=0)
        category = epoch["calibration_category"]
        if category is not None:
            number(category, lower=0, upper=10)
        need(epoch["stimulated_side"] in self.protocol["stimulated_sides"], "reviewed stimulated side")
        case = {"id": self._trial_id(fold, key), "channels": montage["channels"],
                "coordinate_system": montage["coordinate_system"], "samples_001uv": quantized,
                "valid_mask": mask, "context": self.protocol["contexts"][trial["context_id"]],
                "delivered_energy_j": energy, "stimulated_side": epoch["stimulated_side"],
                "calibration_category": category,
                "quantization": {"max_abs_residual_uv": float(max_residual), "missing_samples": missing}}
        if labeled:
            case["rating"] = trial["rating"]
        return case

    def _common(self, fold, schema):
        need(type(fold) is int and 1 <= fold <= 9, "outer fold 1..9")
        return {"schema": schema, "task_id": TASK_ID, "fold_id": self._opaque("fold", fold),
                "protocol_sha256": self.protocol_sha256, "representation_sha256": self.representation_sha256,
                "documentation": self.protocol["documentation"],
                "signal_grid": {"times_us": self.representation["times_us"], "scale_uv": 0.01,
                                "endpoint_convention": self.representation["endpoint_convention"]},
                "training_support": [self._case(fold, key, labeled=True) for key in self._supports[fold]]}

    def authoring_packet(self, fold):
        """Eight fixed training examples plus common documentation, no held-out labels."""
        return encode(self._common(fold, "lep-authoring-packet-v1"))

    def query_packet(self, query_id):
        """Exactly eight training, two calibration and one unlabeled complete query."""
        need(type(query_id) is str and query_id in self._queries, "required scored query ID")
        key = self._queries[query_id]
        fold = key[0]
        packet = self._common(fold, "lep-query-packet-v1")
        packet["calibration"] = [self._case(fold, item, labeled=True)
                                 for item in self._people[key[:2]]["eligible"][:2]]
        packet["query"] = self._case(fold, key, labeled=False)
        return encode(packet)

    def packets_for_modes(self, query_id):
        """Construct once; modes receive the exact same immutable bytes."""
        raw = self.query_packet(query_id)
        return {mode: raw for mode in ("A", "B", "C")}

    def prepare_all(self, authoring_sink, query_sink, counter, *, tokenizer_sha256):
        """Stream the complete roster into owner-only staging and return its receipt.

        Sinks receive (opaque ID, immutable bytes). A failed call leaves partial
        staging, never a successful receipt. Publishing/atomic release is an owner
        duty. Each counter call must cover the real tokenizer and chat framing.
        """
        need(callable(authoring_sink) and callable(query_sink), "owner-only staging sinks")
        pin(tokenizer_sha256)
        entries = []
        def stage(kind, packet_id, raw, sink):
            digest = hashlib.sha256(raw).hexdigest()
            capacity = check_context_capacity(raw, counter, tokenizer_sha256=tokenizer_sha256,
                                              expected_packet_sha256=digest)
            sink(packet_id, raw)
            entries.append({"kind": kind, "packet_id": packet_id, "sha256": digest,
                            "bytes": len(raw), "live_context_tokens": capacity["live_context_tokens"]})
        for fold in range(1, 10):
            stage("authoring", self._opaque("fold", fold), self.authoring_packet(fold), authoring_sink)
        for query_id in self.query_ids:
            stage("query", query_id, self.query_packet(query_id), query_sink)
        return {"schema": "lep-complete-packet-receipt-v1", "task_id": TASK_ID,
                "protocol_sha256": self.protocol_sha256,
                "representation_sha256": self.representation_sha256,
                "selection_audit_sha256": sha256(self.private_selection_audit()),
                "targets_sha256": sha256(self.private_targets()),
                "tokenizer_sha256": tokenizer_sha256, "authoring_packets": 9,
                "query_packets": len(self._queries), "nominal_people": 678,
                "packets": entries, "scientific_qualification": False,
                "execution_qualification": False, "cumulative_runtime_budgets_enforced": False}

    def private_targets(self):
        """Compatible with the retained full-assay scorer; evaluator-private only."""
        people = []
        for (exp, pkey), person in sorted(self._people.items()):
            trials = []
            for trial in person["person"]["trials"]:
                key = (exp, pkey, trial["trial_key"])
                trials.append({"query_id": self._trial_id(exp, key), "chronology": trial["chronology"],
                               "eligible": trial["eligible"], "rating": trial["rating"],
                               "exclusion_reason": trial["exclusion_reason"]})
            people.append({"experiment": exp, "person_id": self._opaque("person", [exp, pkey]), "trials": trials})
        return {"schema": "lep-targets-v1", "task_id": TASK_ID,
                "protocol_sha256": self.protocol_sha256, "representation_sha256": self.representation_sha256,
                "inventory_receipt_sha256": self._ledger["inventory_receipt_sha256"],
                "producer_receipt_sha256": self._ledger["producer_receipt_sha256"], "people": people}

    def private_selection_audit(self):
        return {"schema": "lep-packet-selection-audit-v1", "task_id": TASK_ID,
                "support_salt_sha256": hashlib.sha256(self._salt).hexdigest(),
                "identity_linkage": self._ledger["identity_linkage"],
                "identity_receipt_sha256": self._ledger["identity_receipt_sha256"],
                "nominal_people": 678, "query_count": len(self._queries),
                "folds": [{"experiment": fold, "support_source_keys": list(self._supports[fold]),
                           "purged_source_keys": list(self._purged[fold])} for fold in range(1, 10)],
                "scientific_qualification": False, "execution_qualification": False}


def check_context_capacity(packet_bytes, counter, *, tokenizer_sha256, expected_packet_sha256):
    """Use an owner-reviewed real tokenizer/framing counter; never estimate from bytes.

    The callback must include actual chat framing and complete supplied scientific
    context. Its authenticity and runtime budgets remain external owner duties.
    """
    pin(tokenizer_sha256)
    pin(expected_packet_sha256)
    need(type(packet_bytes) is bytes and hashlib.sha256(packet_bytes).hexdigest() == expected_packet_sha256,
         "exact complete packet identity")
    need(callable(counter), "selected tokenizer and actual-framing counter required")
    count = counter(packet_bytes)
    need(type(count) is int and 0 < count <= MAX_LIVE_TOKENS,
         "complete context does not fit; truncation is forbidden")
    return {"packet_sha256": expected_packet_sha256, "tokenizer_sha256": tokenizer_sha256,
            "live_context_tokens": count, "live_context_limit": MAX_LIVE_TOKENS,
            "scientific_qualification": False, "cumulative_runtime_budgets_enforced": False}

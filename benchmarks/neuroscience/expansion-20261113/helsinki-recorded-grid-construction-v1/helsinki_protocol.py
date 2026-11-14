"""Trusted owner control plane; external isolation/resource host is still required.

These functions never run submitted Python or a model. Only canonical packet
bytes cross to a participant; this module and its Python objects must not cross.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import random
from dataclasses import asdict, dataclass

from helsinki_profile import COORDINATE_ID, profile_identity, validate_lineage
from helsinki_fixture import (FixtureCorpus, FIXTURE_PROTOCOL_ID, FIXTURE_COORDINATE_ID,
                              validate_fixture_lineage)

from helsinki_intake import (Corpus, FS, INFANTS, MONTAGE, Refusal, QualityFlags,
                             PROTOCOL_ID, FLAG_RULE, canonical, digest, finite, require)

SPLIT_SEED = "helsinki-v4-infant-fivefold-20261113-v1"
CONDITIONS = ("A_case_investigation", "B_program_in_advance")
SIGNAL_CONDITIONS = ("recorded_eeg", "training_noise", "amplitude_only")
CASE_NAMESPACE = PROTOCOL_ID + ":case"


def _checked_lineage(corpus):
    """Production identity admission; Python objects are not isolation proof."""
    if type(corpus) is Corpus:
        return validate_lineage(corpus.lineage())
    if type(corpus) is FixtureCorpus:
        return validate_fixture_lineage(corpus.lineage())
    raise Refusal("complete_production_or_explicit_fixture_corpus_required")


def session_protocol_id(session):
    """Select namespace from the exact reviewed controller class, never its fields."""
    if type(session) is Session:
        return PROTOCOL_ID
    if type(session) is EngineeringSession:
        return FIXTURE_PROTOCOL_ID
    raise Refusal("unknown_session_controller_class")


def case_identifier(key, fold, infant, second, lineage_sha256, *, protocol_id=PROTOCOL_ID):
    """One source/version-bound namespace for creation, issuance and scoring."""
    require(isinstance(key, bytes) and len(key) >= 32, "owner_secret_too_short")
    require(type(fold) is int and 0 <= fold < 5 and
            type(infant) is int and infant in INFANTS and
            type(second) is int and second >= 29 and _sha(lineage_sha256),
            "invalid_case_identity_input")
    require(protocol_id in (PROTOCOL_ID, FIXTURE_PROTOCOL_ID), "unknown_case_namespace")
    value = {"namespace": protocol_id + ":case", "lineage_sha256": lineage_sha256,
             "fold": fold, "infant": infant, "recorded_second": second}
    return hmac.new(key, canonical(value), hashlib.sha256).hexdigest()


def partitions():
    ordered = sorted(INFANTS, key=lambda i: hashlib.sha256(
        (SPLIT_SEED + ":" + str(i)).encode()).hexdigest())
    return tuple(tuple(sorted(ordered[j::5])) for j in range(5))


def roles(fold):
    require(type(fold) is int and 0 <= fold < 5, "invalid_fold")
    groups = partitions()
    test = groups[fold]
    development = groups[(fold + 1) % 5]
    training = tuple(i for i in INFANTS if i not in test + development)
    require(set(training) | set(development) | set(test) == set(INFANTS) and
            not (set(training) & set(development) or set(training) & set(test) or
                 set(development) & set(test)), "group_role_overlap")
    return {"training": training, "development": development, "test": test}


def group_ledger(corpus):
    """Private census. Contains no selected-out infant or available-case score."""
    lineage = _checked_lineage(corpus)
    groups = partitions()
    rows = []
    for infant in INFANTS:
        duration = corpus.durations[infant]
        rows.append({"infant": infant, "outer_test_fold": next(
            f for f in range(5) if infant in groups[f]), "declared_recorded_seconds": duration,
            "first_primary_second": 29, "last_primary_second": duration - 1,
            "primary_cases": duration - 29, "prespecified_leading_seconds": 29,
            "final_incomplete_seconds": 0,
            "support_audit": "COMPLETE_RECORDED_GRID_LINEAGE_REQUIRED",
            "source_reported_pause": infant == 42})
    return {"schema": "helsinki-recorded-grid-owner-census-v2", "infants": rows,
            "split_seed": SPLIT_SEED, "partitions": groups,
            "lineage": lineage, "scoreable_primary_infants": 79,
            "protocol_id": lineage["profile"]["protocol_id"],
            "engineering_only": type(corpus) is FixtureCorpus,
            "quality_interpretation": "Flags are not verified pause or missingness truth.",
            "time_coordinate_id": lineage["profile"]["coordinate_id"], "physical_clock_verified": False,
            "known_hold": "Preserved earlier protocols remain unchanged. This version "
            "retains every author-exported record and source-preserved artifact."}


def fold_support(corpus, fold):
    """Owner-only pre-model audit; never return these label counts to model arms.

    This successor requires both expert-label classes in train/development only.
    A seizure-free held group is valid for Brier and never causes repartitioning.
    No seizure label is used to select or change the fixed infant partition.
    """
    _checked_lineage(corpus)
    audit = {}
    for role, infants in roles(fold).items():
        votes = [a for i in infants for k in corpus.seconds(i) for a in corpus.votes(i, k)]
        audit[role] = {"infants": list(infants), "expert_seconds": len(votes),
                       "positive_expert_seconds": sum(votes)}
        if role != "test":
            require(0 < sum(votes) < len(votes), "degenerate_training_or_development_fold")
    return audit


class TrainingView:
    """Owner-side view used by a reviewed baseline, never an isolation mechanism."""
    def __init__(self, corpus, fold):
        _checked_lineage(corpus)
        self.__corpus = corpus
        self.fold = fold
        self.infants = roles(fold)["training"]

    def cases(self):
        for infant in self.infants:
            for second in self.__corpus.seconds(infant):
                yield infant, second

    def votes(self, infant, second):
        require(infant in self.infants, "baseline_target_role_violation")
        return self.__corpus.votes(infant, second)

    def waveform(self, infant, second):
        require(infant in self.infants, "baseline_signal_role_violation")
        return self.__corpus.waveform(infant, second)


@dataclass(frozen=True)
class ConstantPrior:
    probability: float
    training_infants: tuple[int, ...]
    development_infants: tuple[int, ...]
    fold: int
    lineage_sha256: str
    fit_manifest_sha256: str

    def predict(self, packet):
        return self.probability


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(
        c in "0123456789abcdef" for c in value)


def validate_prior(prior, corpus, fold):
    r = roles(fold)
    require(isinstance(prior, ConstantPrior) and prior.fold == fold and
            prior.training_infants == r["training"] and
            prior.development_infants in ((), r["development"]) and
            prior.lineage_sha256 == digest(_checked_lineage(corpus)), "baseline_lineage_mismatch")
    require(0 <= finite(prior.probability) <= 1 and _sha(prior.fit_manifest_sha256),
            "invalid_prior_probability_or_pin")


def fit_prior(corpus, fold, *, calibrate_on_development=False):
    """Equal-infant prevalence; optional constant-only development calibration.

    This is a null comparator, not the authors' SDA and not a strong baseline.
    Calibration and its source role are chosen before any held data are opened.
    """
    fold_support(corpus, fold)
    r = roles(fold)
    training = TrainingView(corpus, fold)
    per_infant = []
    for i in training.infants:
        targets = [sum(training.votes(i, k)) / 3 for k in corpus.seconds(i)]
        per_infant.append(math.fsum(targets) / len(targets))
    prior = math.fsum(per_infant) / len(per_infant)
    development = ()
    if calibrate_on_development:
        development = r["development"]
        # The optimal calibrated constant under the same infant-macro loss.
        means = [math.fsum(sum(corpus.votes(i, k)) / 3 for k in corpus.seconds(i)) /
                 len(corpus.seconds(i)) for i in development]
        prior = math.fsum(means) / len(means)
    lineage = digest(_checked_lineage(corpus))
    fit = {"algorithm": "infant_macro_constant_prevalence",
           "training_infants": training.infants, "development_infants": development,
           "calibrate_on_development": calibrate_on_development, "fold": fold,
           "lineage_sha256": lineage, "probability": prior}
    return ConstantPrior(prior, training.infants, development, fold, lineage, digest(fit))


@dataclass(frozen=True)
class NoiseFit:
    means: tuple[float, ...]
    standard_deviations: tuple[float, ...]
    training_infants: tuple[int, ...]
    fold: int
    lineage_sha256: str


def validate_noise(noise, corpus, fold):
    require(isinstance(noise, NoiseFit) and noise.fold == fold and
            noise.training_infants == roles(fold)["training"] and
            noise.lineage_sha256 == digest(_checked_lineage(corpus)), "noise_role_mismatch")
    require(type(noise.means) is tuple and type(noise.standard_deviations) is tuple and
            len(noise.means) == len(noise.standard_deviations) == 18,
            "noise_fit_must_have_18_channels")
    for value in noise.means:
        finite(value)
    for value in noise.standard_deviations:
        require(finite(value) >= 0, "negative_noise_deviation")


@dataclass(frozen=True)
class MaskPrior:
    probabilities: tuple[float, ...]
    training_infants: tuple[int, ...]
    fold: int
    lineage_sha256: str
    fit_manifest_sha256: str

    def predict(self, flags):
        features = flags.validate().features()
        return self.probabilities[sum(int(v) << i for i, v in enumerate(features))]


def validate_mask_prior(prior, corpus, fold):
    require(isinstance(prior, MaskPrior) and prior.fold == fold and
            prior.training_infants == roles(fold)["training"] and
            prior.lineage_sha256 == digest(_checked_lineage(corpus)) and
            _sha(prior.fit_manifest_sha256), "mask_baseline_lineage_mismatch")
    require(type(prior.probabilities) is tuple and len(prior.probabilities) == 16,
            "mask_baseline_bin_count")
    require(all(0 <= finite(v) <= 1 for v in prior.probabilities),
            "mask_baseline_probability")


def fit_mask_prior(corpus, fold):
    """Training-only 16-bin quality-flag comparator, fixed unit-prior shrinkage.

    Four bits: any context zero-bipolar, final zero-bipolar, any context flatline,
    final flatline. Each infant contributes total weight1 across its cases.
    Each bin has fixed pseudo-weight1 at the training macro prevalence.
    This is an acquisition-cue comparator, not a physiological seizure model.
    """
    prior = fit_prior(corpus, fold)
    weighted_targets, weights = [0.0] * 16, [0.0] * 16
    for infant in roles(fold)["training"]:
        weight = 1.0 / len(corpus.seconds(infant))
        for second in corpus.seconds(infant):
            _, flags = corpus.case_data(infant, second)
            index = sum(int(v) << i for i, v in enumerate(flags.features()))
            weighted_targets[index] += weight * sum(corpus.votes(infant, second)) / 3
            weights[index] += weight
    probabilities = tuple((value + prior.probability) / (weight + 1)
                          for value, weight in zip(weighted_targets, weights))
    manifest = {"algorithm": "quality_flags_16_bins_unit_prior_v1", "fold": fold,
                "training_infants": prior.training_infants, "flag_rule": FLAG_RULE,
                "lineage_sha256": prior.lineage_sha256,
                "probabilities": probabilities, "bin_weights": weights}
    return MaskPrior(probabilities, prior.training_infants, fold,
                     prior.lineage_sha256, digest(manifest))


def fit_noise(corpus, fold):
    """Full training-only waveform moments; each raw second contributes once.

    This expensive authentic-data operation is not selected in source construction.
    Source-preserved artifacts remain in the moments; no samples are dropped.
    """
    sums, squares, counts = [0.0] * 18, [0.0] * 18, [0] * 18
    view = TrainingView(corpus, fold)
    for i in view.infants:
        for k in corpus.seconds(i):
            signals = view.waveform(i, k)
            # Initial context is included once; each later call adds its final second.
            start = 0 if k == 29 else 29 * FS
            for ch, signal in enumerate(signals):
                values = signal[start:]
                sums[ch] += math.fsum(values)
                squares[ch] += math.fsum(v * v for v in values)
                counts[ch] += len(values)
    means = tuple(s / n for s, n in zip(sums, counts))
    deviations = tuple(math.sqrt(max(0.0, q / n - mean * mean))
                       for q, n, mean in zip(squares, counts, means))
    require(all(math.isfinite(v) for v in means + deviations), "invalid_noise_fit")
    return NoiseFit(means, deviations, view.infants, fold, digest(_checked_lineage(corpus)))


def validate_external_baseline_manifest(manifest, corpus, fold):
    """Structural lineage admission only; no claim that arbitrary code is honest.

    The actual isolated trainer, fit capture and frozen-artifact verification are
    required host gates. A signed manifest is not sufficient evidence by itself.
    """
    r = roles(fold)
    require(tuple(manifest["fit_infants"]) == r["training"], "external_fit_role_violation")
    require(tuple(manifest["selection_infants"]) in ((), r["development"]),
            "external_selection_role_violation")
    require(manifest["lineage_sha256"] == digest(_checked_lineage(corpus)), "baseline_source_mismatch")
    for field in ("source_sha256", "artifact_sha256", "environment_sha256",
                  "owner_fit_receipt_sha256"):
        require(isinstance(manifest.get(field), str) and len(manifest[field]) == 64 and
                all(c in "0123456789abcdef" for c in manifest[field]), "invalid_baseline_pin")
    require(manifest.get("pretrained_weights") is False, "unresolved_pretrained_membership")
    return digest(manifest)


def _signal_shape(signal):
    require(len(signal) == 18 and all(len(ch) == 30 * FS for ch in signal),
            "wrong_waveform_shape")
    require(all(type(v) in (int, float) and math.isfinite(v) for ch in signal for v in ch),
            "invalid_waveform_value")


def projected_signal(signal, signal_condition, noise_fit=None, seed=None):
    """Pure projection used by Session; does not authenticate a baseline or corpus."""
    _signal_shape(signal)
    require(signal_condition in SIGNAL_CONDITIONS, "unknown_signal_condition")
    if signal_condition != "training_noise":
        require(noise_fit is None and seed is None, "unexpected_noise_projection_input")
        if signal_condition == "amplitude_only":
            return tuple((math.sqrt(math.fsum(v * v for v in ch) / len(ch)),) * len(ch)
                         for ch in signal)
        return signal
    require(isinstance(noise_fit, NoiseFit) and isinstance(seed, bytes) and len(seed) == 32,
            "invalid_noise_projection_input")
    require(type(noise_fit.means) is tuple and type(noise_fit.standard_deviations) is tuple and
            len(noise_fit.means) == len(noise_fit.standard_deviations) == 18,
            "noise_fit_must_have_18_channels")
    require(all(math.isfinite(finite(v)) for v in noise_fit.means) and
            all(finite(v) >= 0 for v in noise_fit.standard_deviations), "invalid_noise_projection_fit")
    rng = random.Random(int.from_bytes(seed, "big"))
    return tuple(tuple(rng.gauss(mu, sd) for _ in range(30 * FS))
                 for mu, sd in zip(noise_fit.means, noise_fit.standard_deviations))


def public_packet(case_id, signal, flags):
    """Only these canonical bytes cross to the participant; no source-owner cues."""
    require(_sha(case_id), "invalid_public_case_id")
    _signal_shape(signal)
    require(isinstance(flags, QualityFlags), "invalid_public_quality_flags_type")
    flags.validate()
    packet = {"case_id": case_id, "sample_hz": FS, "units": "uV",
              "montage": [a + "-" + b for a, b in MONTAGE],
              "context_seconds": 30, "target_relative_interval": [29, 30],
              "quality_flags": flags.public(), "waveform": signal}
    return canonical(packet)


@dataclass(frozen=True)
class ProtocolIdentity:
    canonical_bytes: bytes
    sha256: str
    owner_hmac: str


class Session:
    """One fold/arm/control. Serialized calls from a trusted isolated host only."""
    def __init__(self, corpus, fold, arm, signal_condition, key, model_revision,
                 baseline, mask_baseline, *, noise_fit=None):
        require((type(self) is Session and type(corpus) is Corpus) or
                (type(self) is EngineeringSession and type(corpus) is FixtureCorpus),
                "session_domain_corpus_type_mismatch")
        admitted_profile = _checked_lineage(corpus)["profile"]
        self.protocol_id = PROTOCOL_ID if type(self) is Session else FIXTURE_PROTOCOL_ID
        self.coordinate_id = COORDINATE_ID if type(self) is Session else FIXTURE_COORDINATE_ID
        require(admitted_profile["protocol_id"] == self.protocol_id and
                admitted_profile["coordinate_id"] == self.coordinate_id, "session_domain_profile_mismatch")
        self.engineering_only = type(self) is EngineeringSession
        require(arm in CONDITIONS and signal_condition in SIGNAL_CONDITIONS, "unknown_condition")
        require(isinstance(key, bytes) and len(key) >= 32, "owner_secret_too_short")
        require(isinstance(model_revision, str) and model_revision.strip(), "model_revision_required")
        r = roles(fold)
        validate_prior(baseline, corpus, fold)
        validate_mask_prior(mask_baseline, corpus, fold)
        if signal_condition == "training_noise":
            validate_noise(noise_fit, corpus, fold)
        else:
            require(noise_fit is None, "unexpected_noise_fit")
        self.corpus, self.fold, self.arm = corpus, fold, arm
        self.signal_condition, self.key = signal_condition, key
        self.model_revision, self.baseline, self.noise_fit = model_revision, baseline, noise_fit
        self.mask_baseline = mask_baseline
        self.program_sha256 = None
        self._program_hmac = None
        self.failed = False
        self.started = False
        self.pending = None
        self.predictions = {}
        self.issued = {}
        self.case_map = {}
        self.lineage_sha256 = digest(_checked_lineage(corpus))
        self.profile_sha256 = digest(admitted_profile)
        # Identical IDs/order across paired arms and controls; bound to this source.
        for infant in r["test"]:
            for second in corpus.seconds(infant):
                case_id = case_identifier(key, fold, infant, second, self.lineage_sha256,
                                          protocol_id=session_protocol_id(self))
                require(case_id not in self.case_map, "case_id_collision")
                self.case_map[case_id] = (infant, second)
        self.order = tuple(sorted(self.case_map))
        self.position = 0
        value = canonical(self.protocol_payload())
        self.identity = ProtocolIdentity(value, hashlib.sha256(value).hexdigest(),
            hmac.new(key, value, hashlib.sha256).hexdigest())
        self.protocol_sha256 = self.identity.sha256

    def protocol_payload(self):
        return {"protocol_id": self.protocol_id, "time_coordinate_id": self.coordinate_id,
                "engineering_only": self.engineering_only,
                "profile_sha256": self.profile_sha256,
                "lineage_sha256": self.lineage_sha256, "flag_rule": FLAG_RULE,
                "arm": self.arm, "signal_condition": self.signal_condition,
                "model_revision": self.model_revision, "fold": self.fold,
                "split": roles(self.fold), "lineage": _checked_lineage(self.corpus),
                "cases": self.order, "baseline": asdict(self.baseline),
                "mask_baseline": asdict(self.mask_baseline),
                "noise_fit": asdict(self.noise_fit) if self.noise_fit else None,
                "required_state_policy": "fresh_case_process_and_model_context",
                "case_tool_budget": [10, 120, 1024 ** 3]}

    def validate_identity(self):
        require((type(self) is Session and type(self.corpus) is Corpus and
                 self.protocol_id == PROTOCOL_ID and self.coordinate_id == COORDINATE_ID and
                 self.engineering_only is False) or
                (type(self) is EngineeringSession and type(self.corpus) is FixtureCorpus and
                 self.protocol_id == FIXTURE_PROTOCOL_ID and self.coordinate_id == FIXTURE_COORDINATE_ID and
                 self.engineering_only is True), "session_domain_changed")
        current_lineage = _checked_lineage(self.corpus)
        require(self.lineage_sha256 == digest(current_lineage) and
                self.profile_sha256 == digest(current_lineage["profile"]), "source_profile_identity_changed")
        validate_prior(self.baseline, self.corpus, self.fold)
        validate_mask_prior(self.mask_baseline, self.corpus, self.fold)
        if self.signal_condition == "training_noise":
            validate_noise(self.noise_fit, self.corpus, self.fold)
        else:
            require(self.noise_fit is None, "unexpected_noise_fit")
        value = canonical(self.protocol_payload())
        require(value == self.identity.canonical_bytes and
                hashlib.sha256(value).hexdigest() == self.protocol_sha256 == self.identity.sha256 and
                hmac.compare_digest(hmac.new(self.key, value, hashlib.sha256).hexdigest(),
                                    self.identity.owner_hmac), "protocol_identity_changed")
        if self.program_sha256 is not None:
            require(_sha(self.program_sha256) and hmac.compare_digest(
                hmac.new(self.key, self.program_sha256.encode(), hashlib.sha256).hexdigest(),
                self._program_hmac or ""), "program_commitment_changed")

    def freeze_program(self, source_bytes):
        self.validate_identity()
        require(self.arm == CONDITIONS[1] and not self.started and
                self.program_sha256 is None, "program_must_be_frozen_before_test")
        require(isinstance(source_bytes, bytes) and 0 < len(source_bytes) <= 1048576,
                "invalid_program_source")
        self.program_sha256 = hashlib.sha256(source_bytes).hexdigest()
        self._program_hmac = hmac.new(self.key, self.program_sha256.encode(), hashlib.sha256).hexdigest()
        return self.program_sha256

    def next_packet(self):
        self.validate_identity()
        require(not self.failed, "session_previously_failed")
        require(self.pending is None, "previous_prediction_not_committed")
        if self.arm == CONDITIONS[1]:
            require(self.program_sha256 is not None, "program_not_frozen")
        require(self.position < len(self.order), "all_cases_already_issued")
        self.started = True
        case_id = self.order[self.position]
        infant, second = self.case_map[case_id]
        require(type(infant) is int and infant in roles(self.fold)["test"] and
                type(second) is int and second in self.corpus.seconds(infant),
                "issued_case_outside_frozen_test_support")
        expected_id = case_identifier(self.key, self.fold, infant, second,
                                      self.lineage_sha256, protocol_id=session_protocol_id(self))
        require(hmac.compare_digest(case_id, expected_id), "case_binding_changed_before_issuance")
        signal, flags = self.corpus.case_data(infant, second)
        flags.validate()
        original_signal_sha256 = digest(signal)
        seed = (hmac.new(self.key, ("noise:" + case_id).encode(), hashlib.sha256).digest()
                if self.signal_condition == "training_noise" else None)
        signal = projected_signal(signal, self.signal_condition, self.noise_fit, seed)
        body = public_packet(case_id, signal, flags)
        original = {"case_id": case_id, "protocol_sha256": self.protocol_sha256,
                    "lineage_sha256": self.lineage_sha256, "profile_sha256": self.profile_sha256,
                    "original_signal_sha256": original_signal_sha256,
                    "quality_flags": flags.public(), "quality_stratum": flags.stratum(),
                    "packet_sha256": hashlib.sha256(body).hexdigest()}
        original["owner_hmac"] = hmac.new(self.key, canonical(original), hashlib.sha256).hexdigest()
        self.issued[case_id] = original
        self.pending = {"case_id": case_id, "packet_sha256": hashlib.sha256(body).hexdigest(),
                        "lineage_sha256": self.lineage_sha256, "profile_sha256": self.profile_sha256,
                        "issued_original_sha256": digest(original),
                        "tool_calls": 0, "reported_cpu_seconds": 0.0,
                        "reported_peak_memory_bytes": 0}
        return body

    def baseline_probability(self, case_id):
        self.validate_identity()
        require(self.pending is not None and self.pending["case_id"] == case_id,
                "baseline_wrong_case")
        return self.baseline.probability

    def mask_only_probability(self, case_id):
        self.validate_identity()
        require(self.pending is not None and self.pending["case_id"] == case_id,
                "mask_baseline_wrong_case")
        flags = self.issued[case_id]["quality_flags"]
        q = QualityFlags(tuple(flags["zero_bipolar_seconds"]),
                         tuple(flags["any_flatline_seconds"]))
        return self.mask_baseline.predict(q)

    def record_tool_accounting(self, case_id, *, cpu_seconds, peak_memory_bytes):
        self.validate_identity()
        require(not self.failed, "session_previously_failed")
        require(self.pending is not None and self.pending["case_id"] == case_id,
                "tool_wrong_case")
        require(self.arm == CONDITIONS[0], "per_case_model_tool_not_allowed_in_program_arm")
        cpu = finite(cpu_seconds)
        require(cpu >= 0 and type(peak_memory_bytes) is int and peak_memory_bytes >= 0,
                "invalid_resource_receipt")
        self.pending["tool_calls"] += 1
        self.pending["reported_cpu_seconds"] += cpu
        self.pending["reported_peak_memory_bytes"] = max(
            self.pending["reported_peak_memory_bytes"], peak_memory_bytes)
        within_budget = (self.pending["tool_calls"] <= 10 and
                         self.pending["reported_cpu_seconds"] <= 120 and
                         self.pending["reported_peak_memory_bytes"] <= 1024 ** 3)
        if not within_budget:
            self.failed = True
        require(within_budget, "case_resource_budget_exceeded")

    def commit(self, *, case_id, packet_sha256, probability, program_sha256=None):
        self.validate_identity()
        require(not self.failed, "session_previously_failed")
        require(self.pending is not None and case_id == self.pending["case_id"] and
                packet_sha256 == self.pending["packet_sha256"], "prediction_case_binding")
        require(case_id not in self.predictions, "duplicate_prediction")
        if self.arm == CONDITIONS[1]:
            require(program_sha256 == self.program_sha256, "program_changed_after_test_open")
        else:
            require(program_sha256 is None, "unexpected_program_pin")
        p = finite(probability)
        require(0 <= p <= 1, "invalid_probability")
        self.predictions[case_id] = {**self.pending, "probability": p,
            "protocol_sha256": self.protocol_sha256, "program_sha256": self.program_sha256}
        self.predictions[case_id]["owner_receipt_hmac"] = hmac.new(
            self.key, canonical(self.predictions[case_id]), hashlib.sha256).hexdigest()
        self.pending = None
        self.position += 1

    def complete(self):
        return (not self.failed and self.pending is None and self.position == len(self.order) and
                set(self.predictions) == set(self.case_map))


class EngineeringSession(Session):
    """Explicit invented-fixture domain; never accepted by production scorers.

    All behavior is inherited from the same guarded Session implementation.
    Constructor and identity validation bind the exact fixture type/namespace.
    """
    pass

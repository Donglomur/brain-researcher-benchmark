"""Explicit-context ICNet probability bridge for the original input interface.

No model is loaded here. A trusted operator supplies an already authenticated
author model, an explicit context provider and its source-evidence identities.
This bridge does not authenticate those external qualifications or establish
paper-era context/alignment, native numerical parity, protection or a paper win.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from source import (ANIMALS, SOUNDS, TIME_BINS, AUDIO_SAMPLES, UNITS, FS_AUDIO,
                    FS_NEURAL, is_sha, require)
from predictions import MAX_BLOCK_BINS

AUTHOR_REVISION = "7a631f1779662ee70b1819ac0c9ce0191bcaf158"
AUTHOR_FUNCTIONS_SHA256 = "71f991df7fdc9d697cf6ab21c0da207d6e98d8e37520f81964f39b7e798eea19"
LEFT_CONTEXT_SAMPLES = 2048
AUTHOR_DECODERS = 9
COUNT_CLASSES = 5
AUDIO_SCALE = 0.04
TIME_SCALE = 1.0 / 36000.0


def _keras_branch(inputs, output):
    # Native dependency import occurs only when an explicitly supplied author
    # model is actually used. This module never downloads or loads a checkpoint.
    from tensorflow.keras import Model
    return Model(inputs=inputs, outputs=output)


def _validate_binding(binding):
    require(type(binding) is dict and set(binding) == {
        "schema", "author_revision", "author_functions_sha256",
        "checkpoint_sha256", "context_alignment_evidence_sha256",
        "measurement_time_mapping_evidence_sha256"}, "exact author bridge binding required")
    require(binding["schema"] == "icnet-author-probability-bridge-binding/v1"
            and binding["author_revision"] == AUTHOR_REVISION
            and binding["author_functions_sha256"] == AUTHOR_FUNCTIONS_SHA256,
            "author source identity differs from the inspected interface")
    for key in ("checkpoint_sha256", "context_alignment_evidence_sha256",
                "measurement_time_mapping_evidence_sha256"):
        require(is_sha(binding[key]), "explicit checkpoint/context/time evidence identity required")


def _validate_request(request):
    require(type(request) is dict and set(request) == {
        "animal", "sound", "trial", "audio_pa", "fs_audio", "fs_neural",
        "time_bins", "measurement_time_seconds", "characteristic_frequencies_hz",
        "unit_ids", "maximum_block_bins"}, "exact public prediction request required")
    require(type(request["animal"]) is int and request["animal"] in ANIMALS
            and request["sound"] in SOUNDS and type(request["trial"]) is int
            and request["trial"] in (1, 2), "original animal/sound/trial identity required")
    require(type(request["time_bins"]) is int and request["time_bins"] == TIME_BINS
            and request["fs_audio"] == FS_AUDIO and request["fs_neural"] == FS_NEURAL,
            "complete original support and clocks required")
    require(type(request["maximum_block_bins"]) is int
            and 1 <= request["maximum_block_bins"] <= MAX_BLOCK_BINS,
            "invalid probability streaming bound")
    time = request["measurement_time_seconds"]
    require(type(time) in (int, float) and math.isfinite(time) and time >= 0,
            "finite nonnegative measurement time in seconds required")
    audio, cfs = request["audio_pa"], request["characteristic_frequencies_hz"]
    require(type(audio) is np.ndarray and audio.dtype == np.dtype("float32")
            and audio.shape == (AUDIO_SAMPLES,) and np.isfinite(audio).all(),
            "complete finite float32 audio in calibrated Pa required")
    require(type(cfs) is np.ndarray and cfs.dtype == np.dtype("float64")
            and cfs.shape == (UNITS,)
            and np.all((np.isfinite(cfs) & (cfs > 0)) | np.isneginf(cfs)),
            "complete original characteristic-frequency metadata required")
    expected = tuple(f"animal_{request['animal']}:original_column_{i}" for i in range(UNITS))
    require(type(request["unit_ids"]) is tuple and request["unit_ids"] == expected,
            "original column identities required; sorted CFs do not define column identity")


class AuthorProbabilityBridge:
    """Callable accepted by ``predictions.run``; returns unsampled distributions.

    ``context_provider`` receives only the animal/sound/trial/time identity and
    must return the explicit preceding 2048 calibrated samples and their digest.
    There is no zero-padding default. Supplying evidence digests is a declaration,
    not verification that a context policy is the historical paper policy.

    The model can produce the full 22,784 x 512 x 5 probability tensor. Only its
    export is block streamed: this is not bounded-memory model inference. Native
    checkpoint/source/dependencies/peak memory remain operator qualifications.
    """

    def __init__(self, model, context_provider, binding, *, branch_factory=None):
        _validate_binding(binding)
        require(callable(context_provider), "an explicit context provider is mandatory")
        require(branch_factory is None or callable(branch_factory), "invalid branch factory")
        self._model = model
        self._context_provider = context_provider
        self._binding = dict(binding)
        self._factory = _keras_branch if branch_factory is None else branch_factory
        self._branches = {}

    def _branch(self, animal):
        if animal not in self._branches:
            layout = self._model.input
            require(isinstance(layout, (list, tuple)) and len(layout) == 2
                    and isinstance(layout[1], (list, tuple))
                    and len(layout[1]) == AUTHOR_DECODERS,
                    "author model must preserve the inspected audio/nine-time-input layout")
            layers = self._model.layers
            require(isinstance(layers, (list, tuple)) and len(layers) >= AUTHOR_DECODERS,
                    "author model lacks the original decoder layer positions")
            index = animal - 1
            # Positional branch selection follows the inspected pinned helper.
            # These positions are not a checkpoint-authentication substitute.
            decoder = layers[len(layers) - AUTHOR_DECODERS + index]
            branch = self._factory([layout[0], layout[1][index]], decoder.output)
            require(callable(getattr(branch, "predict", None)), "selected branch lacks predict")
            self._branches[animal] = branch
        return self._branches[animal]

    def __call__(self, request):
        _validate_request(request)
        identity = {name: request[name] for name in
                    ("animal", "sound", "trial", "measurement_time_seconds")}
        context = self._context_provider(dict(identity))
        require(type(context) is dict and set(context) == {
            "identity", "left_context_pa", "samples_sha256", "alignment_evidence_sha256"},
            "explicit identity-bound context record required")
        require(context["identity"] == identity
                and context["alignment_evidence_sha256"] ==
                self._binding["context_alignment_evidence_sha256"],
                "context identity or alignment-evidence binding differs")
        previous = context["left_context_pa"]
        require(type(previous) is np.ndarray and previous.dtype == np.dtype("float32")
                and previous.shape == (LEFT_CONTEXT_SAMPLES,) and np.isfinite(previous).all(),
                "exact finite float32 preceding context in Pa required")
        context_bytes = np.asarray(previous, dtype="<f4").tobytes(order="C")
        require(is_sha(context["samples_sha256"])
                and hashlib.sha256(context_bytes).hexdigest() == context["samples_sha256"],
                "preceding context byte identity differs")

        # A new allocation prevents the author's in-place audio normalization
        # from altering the shared public waveform or the supplied context.
        waveform = np.concatenate((previous, request["audio_pa"])).reshape(1, -1, 1)
        waveform *= np.float32(AUDIO_SCALE)
        # Preserve the pinned helper's dtype and operation ordering. Do not
        # reinterpret the misleading hours docstring as an hours-valued input.
        clock = np.arange(0.0, TIME_BINS / FS_NEURAL, 1.0 / FS_NEURAL,
                          dtype=waveform.dtype) * TIME_SCALE
        require(clock.shape == (TIME_BINS,), "source clock recipe does not produce exact support")
        clock += np.asarray(request["measurement_time_seconds"] * TIME_SCALE,
                            dtype=waveform.dtype)
        clock = clock.reshape(1, TIME_BINS, 1)
        raw = self._branch(request["animal"]).predict((waveform, clock), verbose=0)
        require(type(raw) is np.ndarray and raw.dtype in (np.dtype("float32"), np.dtype("float64"))
                and raw.shape == (1, TIME_BINS, UNITS, COUNT_CLASSES),
                "author branch must return complete unsampled categorical probabilities")
        # Existing predictions.convert_block authenticates categorical values,
        # computes expectations, and applies its independently declared PCG64
        # sampling. No TensorFlow sampling or CF sorting takes place here.
        columns = list(range(UNITS))
        step = request["maximum_block_bins"]
        for start in range(0, TIME_BINS, step):
            yield {"start_bin": start,
                   "probabilities": raw[0, start:min(start + step, TIME_BINS)],
                   "column_indices": list(columns)}

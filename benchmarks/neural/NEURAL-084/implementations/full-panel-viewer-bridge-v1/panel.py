"""Complete54 collection bridge around the frozen NEURAL-084 FoldViewer.

Operator-only, in-process construction. No native/runtime qualification,
participant isolation, private targets, comparator generation or scoring.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import ModuleType

VIEWER_BYTES = 13035
VIEWER_SHA256 = "c3f7b05f1afd007096cbc31d0b5165fd9a6cbad26cbb07ce15e47cd6e2dce345"
FOLDS = tuple(f"fold{person:03d}" for person in range(1, 55))
PREDICTION_CAP = 262144
CAPTURE_CAP = 54 * PREDICTION_CAP


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _viewer(source):
    source = Path(source) if source is not None else Path(__file__).resolve().parents[1] / "typed-waveform-v1/viewer.py"
    with source.open("rb") as stream:
        body = stream.read(VIEWER_BYTES + 1)
    need(len(body) == VIEWER_BYTES and hashlib.sha256(body).hexdigest() == VIEWER_SHA256,
         "exact accepted FoldViewer source required")
    module = ModuleType("neural084_pinned_fold_viewer")
    module.__file__ = str(source)
    exec(compile(body, str(source), "exec"), module.__dict__)
    return module


class Panel:
    """Serial collection of all54 independently constructed FoldViewer instances.

    The operator supplies authenticated public fold metadata and trusted epoch
    providers. No input or callback is participant-selected. A fresh instance
    resets only viewer API state, not an external model/process/context.
    """

    def __init__(self, folds, *, max_requests, max_capture_bytes,
                 viewer_source=None, source_root=None):
        need(type(max_requests) is int and 1 <= max_requests <= 2**53 - 1,
             "positive declared request allowance")
        need(type(max_capture_bytes) is int and 1 <= max_capture_bytes <= CAPTURE_CAP,
             "positive bounded prediction capture allowance")
        need(type(folds) is list and len(folds) == 54, "all54 public fold records required")
        self._viewer = _viewer(viewer_source)
        self._protocol, self._io, self._contracts = self._viewer._dependencies(source_root)
        self._source_root = source_root
        self._folds, self._fold_pins = [], []
        generation = None
        query_ids = set()
        for person, supplied in enumerate(folds, 1):
            raw = self._io.canonical(supplied)
            need(0 < len(raw) <= self._contracts.FOLD_CAP, "bounded complete fold metadata")
            fold = self._io.decode(raw)
            if person == 1:
                generation = fold.get("generation") if type(fold) is dict else None
            self._contracts._fold_contract(fold, person, generation)
            need(not query_ids.intersection(fold["ids"]), "disjoint21600 query identities across folds")
            query_ids.update(fold["ids"])
            self._folds.append(fold)
            self._fold_pins.append(self._io.pin(raw))
        need(len(query_ids) == 21600, "complete21600-query support")
        self._generation = generation
        self._max_requests, self._max_capture_bytes = max_requests, max_capture_bytes
        self._requests, self._captured_bytes, self._next = 0, 0, 0
        self._active = None
        self._outputs, self._receipts = {}, []
        self._failed = False
        self._complete = None

    def _charge(self):
        need(not self._failed, "failed collection cannot resume or export")
        need(self._complete is None, "complete collection is immutable")
        need(self._requests < self._max_requests, "collection request allowance exhausted")
        self._requests += 1

    def open_next(self, training_raw, training_epoch, query_epoch):
        """Operator opens exactly the next fold; no alternate index or skip API."""
        self._charge()
        need(self._active is None, "finish active fold before opening the next")
        need(self._next < 54, "all54 folds already closed")
        # Bind the EXACT captured public training.json bytes, not a re-encoded
        # object, to the metadata frozen for this fold before any delivery.
        # This is packet identity, not proof of original-data authenticity.
        try:
            fold = self._folds[self._next]
            need(type(training_raw) is bytes and 0 < len(training_raw) <= self._contracts.JSON_CAP,
                 "bounded complete training JSON bytes")
            expected = {key: fold["training_metadata"][key] for key in ("bytes", "sha256")}
            need(self._io.pin(training_raw) == expected, "exact frozen training metadata identity")
            training = self._io.decode(training_raw)
            # The original constructor validates all21200 donor rows and
            # excludes the designated held person before delivery.
            active = self._viewer.FoldViewer(fold, training, training_epoch, query_epoch,
                                             source_root=self._source_root)
        except BaseException:
            self._failed = True
            raise
        self._active = active
        return {"fold": FOLDS[self._next], "training_rows": 21200,
                "query_rows": 400, "stage": "training"}

    def handle(self, raw):
        """One bounded original typed request, applied only to the active fold."""
        self._charge()
        need(self._active is not None, "operator must open the next fold")
        need(type(raw) is bytes and 0 < len(raw) <= self._viewer.MAX_REQUEST_BYTES,
             "bounded request bytes")
        request = self._io.decode(raw)
        response = self._active.handle(raw)
        if type(request) is not dict or request.get("action") != "finish":
            return response
        # A successful FoldViewer finish already closed its source providers.
        # If capture/admission fails after that transition, fail the panel;
        # do not replace responses, repeat the fold or skip its output.
        try:
            fold = self._folds[self._next]
            self._contracts.prediction(response, fold)
            need(self._captured_bytes + len(response) <= self._max_capture_bytes,
                 "prediction capture allowance exceeded")
            name = FOLDS[self._next]
            need(name not in self._outputs, "first-final fold output is immutable")
            self._outputs[name] = response  # bytes are immutable
            self._captured_bytes += len(response)
            self._receipts.append({"fold": name, "fold_metadata": self._fold_pins[self._next],
                                   "prediction": self._io.pin(response), "query_count": 400})
            self._active = None
            self._next += 1
        except BaseException:
            self._failed = True
            self._active = None
            raise
        return self._io.canonical({"schema": "neural084-viewer-fold-closed-v1",
                                   "fold": name, "closed_folds": self._next,
                                   "required_folds": 54})

    def finish_collection(self):
        """Return an operator collection receipt, never native execution proof."""
        self._charge()
        need(self._active is None and self._next == 54
             and tuple(self._outputs) == FOLDS, "all54 complete first-final folds required")
        result = {"schema": "neural084-viewer-collection-v1", "task_id": "NEURAL-084",
                  "generation": self._generation, "status": "complete_unqualified",
                  "fold_count": 54, "query_count": 21600,
                  "folds": self._receipts, "captured_prediction_bytes": self._captured_bytes,
                  "requests_charged": self._requests,
                  "representation": "typed_SVG_text_operator_API",
                  "native_programme_execution_receipt": False,
                  "participant_transport_and_isolation_qualified": False,
                  "authentic_inputs_qualified": False,
                  "comparators_generated": False, "private_scoring_performed": False,
                  "scientific_qualified": False}
        self._complete = self._io.canonical(result)
        return self._complete

    def candidate_prediction(self, fold):
        """Read-only original raw-score bytes; unavailable for partial panels.

        The caller may use these as candidate inputs to the existing scorer.
        It must separately provide complete, qualified baseline-mode outputs,
        protected pool/gold and transport/provenance evidence. This API has
        no alternate-mode override or synthetic comparator fallback.
        """
        need(not self._failed and self._complete is not None,
             "complete54 collection required before prediction export")
        need(type(fold) is str and fold in FOLDS, "exact original fold name")
        return self._outputs[fold]

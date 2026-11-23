"""Trusted, one-case grading of a bound static behavior-to-ERP response.

No model, source-data, fit or provider execution occurs. Private targets and the
binding belong exclusively to the operator, after response commitment.
"""
import hashlib
from pathlib import Path
import types

CONDITION = "direct_numeric_behavior_to_erp_encoding"
_ROOT = Path(__file__).resolve().parents[1]
_SOURCES = {
    "adapter": ("static-direct-response-v1/static_direct_response.py",
                "e0d59b8c877c38c1316c8caef1e3ac3fb2b6e84b562b2853c89bfe06c337a129"),
    "arithmetic": ("paired-loss-v2/paired_loss.py",
                   "75c35093870fd3a5b021eddcf438992390f667d0e12a718fccd21616cc6e2d9a"),
}


def _load(name):
    relative, expected = _SOURCES[name]
    path = _ROOT / relative
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError("direct_loss_source_changed: " + relative)
    module = types.ModuleType("neural006_direct_loss_" + name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


_ADAPTER = _load("adapter")
_ARITHMETIC = _load("arithmetic")


def score_response(case, private_binding, response_bytes, private_held_rows, reference):
    """Grade one observed development case without relabeling its condition.

    Collection authenticates the unchanged presented case, complete response
    and packet binding before private target arithmetic. The caller must commit
    response_bytes before exposing targets to trusted scoring; this in-memory
    function cannot prove chronology, provider isolation or data provenance.
    """
    collection = _ADAPTER.collect(case, private_binding, response_bytes)
    score = _ARITHMETIC._score_modes(
        case, private_held_rows, reference,
        {CONDITION: collection["candidate"]}, (CONDITION,))
    return {
        "schema": "neural006-static-numeric-score-v1",
        "condition": CONDITION,
        "scope": "one_observed_development_lopo33_case",
        "participant": score["participant"],
        "paired_scored_rows": score["paired_scored_rows"],
        "components": score["components"],
        "case_sha256": collection["case_sha256"],
        "packet_sha256": collection["packet_sha256"],
        "response_sha256": collection["response_sha256"],
        "prediction_sha256": collection["prediction_sha256"],
        "source_sha256": {name: pin for name, (_, pin) in _SOURCES.items()},
        "scientific_qualification": "not_established",
    }

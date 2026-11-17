"""Majaj source-diagnostic integration with the complete S3 scientific worker."""
import math
from .common import ScientificGate, require, result
from . import majaj_core as core

COMMIT = "f18de35818502744329f7c92bb17a80af8f48549"
PREPARATION_SHA = "646fd59e206f6d3062887fb7a9da09baa0e37028e6ba1d8175bdc48a92093a4f"
ANALYSIS_SHA = "0a2930d761273baf3d9d540ac341384e13cb62e239a39253208a90b39b75e0cd"


def _admit(protocol):
    require(protocol.get("lane") == "RELEASED_MAJAJ_SOURCE_DIAGNOSTIC",
            "released 1000-draw Majaj source cannot silently satisfy the final paper")
    require(protocol.get("source_commit") == COMMIT and
            protocol.get("preparation_notebook_sha256") == PREPARATION_SHA and
            protocol.get("analysis_notebook_sha256") == ANALYSIS_SHA, "exact recovered source identities")
    require(protocol.get("source_qualification_id"), "external producer qualification remains required", "qualification_required")


def _call(fn, *args):
    try:
        return fn(*args)
    except core.MajajError as error:
        raise ScientificGate("invalid_protocol", str(error)) from error


def prepare(payload):
    p, r = payload["protocol"], payload["request"]
    _admit(p)
    require(p.get("transform_ancestry_admitted") is True, "trusted input ancestry required", "qualification_required")
    raw = _call(core.prepare_assembly, payload["arrays"]["responses"], r["coordinates"], r["provenance"], r["group"])
    support = raw.pop("support")
    return result(raw, support, ["No new normalization or upstream-window claim.",
        "This source diagnostic does not discharge final-paper 500-draw, cohort or native-environment holds."])


def literal_draw(payload):
    p, r = payload["protocol"], payload["request"]
    _admit(p)
    raw = _call(core.draw, payload["arrays"]["trials"], r["plan"], r["grid_ordinal"], r["draw_ordinal"])
    return result({"draw": raw}, {"recipe": core.RECIPE, "backend": "NumPy float64 algebra",
                  "native_JAX_parity": "unperformed", "historical_RNG_state": "unrecovered"},
                  ["Conditional draws are not independent animals or new benchmarks."], status="ok")


def aggregate(payload):
    from .scoring import curves
    _admit(payload["protocol"])
    r = payload["request"]
    source = _call(core.aggregate_axis, r["records"], r["plan"])
    protected = {}
    for name, cells in source["source_plot_curves"].items():
        protected[name] = []
        for cell in cells:
            raw = cell.pop("raw_records")
            summary = curves({"request": {"records": raw, "planned_draws": 1000,
                              "unit": "conditional draw within one fixed animal/ROI panel"}})
            # Raw records already have individual trusted draw receipts and are
            # preserved again in the aggregate request's parameter tables. Echoing
            # them twice here would exceed the unchanged 1 MiB response frame.
            summary["outputs"].pop("raw_records")
            nonfinite = {key: ("NaN" if math.isnan(value) else "+Inf" if value > 0 else "-Inf")
                         for key, value in summary["outputs"].items()
                         if isinstance(value, float) and not math.isfinite(value)}
            if nonfinite:
                # Preserve the actual reduction's failure and complete support;
                # never replace it with a different mean algorithm or valid value.
                summary["diagnostics"]["original_computed_status"] = summary["status"]
                summary["diagnostics"]["nonfinite_summary_fields"] = nonfinite
                summary["status"] = "nonfinite_aggregation"
                for key in nonfinite:
                    summary["outputs"][key] = None
            cell["failed_draw_ordinals_by_status"] = {
                status: [i for i, row in enumerate(raw) if row["status"] == status]
                for status in sorted({row["status"] for row in raw}) if status != "ok"}
            protected[name].append(summary)
    return result({"source_plot": source, "complete_denominator_summaries": protected},
                  {"draws": 10000, "estimator_records": 40000, "biological_panels": 1,
                   "raw_record_custody": "original trusted draw receipts and aggregate request parameter tables",
                   "raw_records_echoed_in_response": False},
                  ["Source nanmean/median/std0 are preserved separately from complete-denominator summaries.",
                   "Last-grid both-estimator mean(A)/mean(B) is a plotting reference, not population truth."])

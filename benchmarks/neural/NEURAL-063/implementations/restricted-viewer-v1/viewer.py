"""Complete paired restricted displays for prepared NEURAL-063 observations.

No target lookup, model execution, browser launch, or scientific scoring occurs.
The trusted host must deliver one page to one fresh participant context.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path

DIRECT = Path(__file__).resolve().parents[1] / "direct-numeric-v1" / "direct_delivery.py"
_spec = importlib.util.spec_from_file_location("neural063_viewer_direct", DIRECT)
d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d)

SCHEMA = "neural063_restricted_viewer_delivery_v1"
PRESENTATION = "neural063_restricted_viewer_presentation_v1"
STYLE = """body{font:16px system-ui,sans-serif;line-height:1.5;max-width:960px;margin:2rem auto;padding:0 1rem;color:#172331;background:#fff}h1,h2,h3{line-height:1.2}table{border-collapse:collapse;margin:1rem 0;width:100%}th,td{border:1px solid #c4ccd2;padding:.35rem .65rem;text-align:left;overflow-wrap:anywhere}th{background:#eef2f5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef2f5;padding:1rem}svg{width:100%;height:auto}code{overflow-wrap:anywhere}.note{border-left:4px solid #316c9c;padding:.5rem 1rem;background:#f1f7fc}"""


def _text(value):
    return escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False))


def _table(headers, rows):
    return "<table><thead><tr>" + "".join("<th>" + _text(x) + "</th>" for x in headers) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join("<td>" + _text(x) + "</td>" for x in row) + "</tr>" for row in rows
    ) + "</tbody></table>"


def _history(values):
    # Normalize before plotting: subtraction/range arithmetic can overflow even
    # for valid finite observations. Exact values remain in the adjacent table.
    scale = max(abs(x) for x in values) or 1
    points = " ".join(f"{70 + 50 * i},{130 - 95 * (x / scale):.8f}" for i, x in enumerate(values))
    plot = (
        '<svg viewBox="0 0 700 280" role="img" aria-label="Twelve preceding population-history bins; exact values in table below">'
        '<rect x="0" y="0" width="700" height="280" fill="white"/>'
        '<line x1="45" y1="130" x2="645" y2="130" stroke="#aaa"/>'
        '<line x1="45" y1="25" x2="45" y2="235" stroke="#172331"/>'
        f'<polyline points="{points}" fill="none" stroke="#176399" stroke-width="3"/>'
        '<text x="8" y="135">0</text><text x="45" y="255">−2.4 s</text>'
        '<text x="645" y="255" text-anchor="end">0 s</text>'
        '<text x="180" y="275">Bin centers, relative to scheduled omission</text></svg>'
    )
    return "<h3>Pre-omission population history</h3><p>Dimensionless dF/F minus the final history-bin mean. Plot scale: ±" + _text(scale) + ". The table preserves every supplied value.</p>" + plot + _table(
        ["Half-open bin (seconds)", "Baseline-subtracted population mean dF/F"],
        [(f"[{left},{right})", value) for (left, right), value in zip(d.HISTORY_BINS, values)],
    )


def _observation(row, *, demonstration=False):
    body = _table(["Grouping token", "Value"], [(key, row[key]) for key in ("id", "mouse", "session", "experiment", "split")])
    body += "<h3>Recording context</h3>" + _table(["Field", "Value"], list(row["context"].items()))
    body += "<h3>Three preceding presentations</h3>" + _table(
        ["Image", "Omitted", "Onset relative to scheduled omission (seconds)"],
        [(p["image"], p["omitted"], p["start_relative_seconds"]) for p in row["previous"]],
    )
    if "history" in row:
        body += _history(row["history"])
    if demonstration:
        body += "<h3>Permitted FIT demonstration response</h3>" + _table(
            ["Target bin (seconds)", "Baseline-subtracted dF/F"],
            [(f"[{left},{right})", value) for (left, right), value in zip(d.TARGET_BINS, row["target"])],
        )
    return body


def _render(request, presentation_sha256):
    template = {"presentation_sha256": presentation_sha256,
                "request_sha256": request["request_sha256"], "id": request["id"],
                "information": request["information"], "values": [None, None, None]}
    body = '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    body += '<meta name="viewport" content="width=device-width,initial-scale=1">'
    body += '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
    body += "<title>NEURAL-063 — restricted observation</title><style>" + STYLE + "</style></head><body>"
    body += "<h1>Predict the omission response</h1><p class=\"note\">Restricted viewer condition · " + _text(request["information"]) + " view · " + _text(request["exposure_condition"]) + "</p>"
    instruction = request["instruction"].replace(
        "with exactly request_sha256, id, information, and values",
        "with exactly presentation_sha256, request_sha256, id, information, and values")
    body += "<p>" + _text(instruction) + "</p>"
    body += "<p>For this viewer response, also copy <code>presentation_sha256</code> from the response template. Return exactly the five fields shown there.</p>"
    body += "<h2>Response definition</h2><p>Baseline: " + _text(request["baseline"]) + " Units: " + _text(request["units"]) + ".</p>"
    body += _table(["Output position", "Half-open target bin (seconds)"], [(i + 1, f"[{left},{right})") for i, (left, right) in enumerate(request["target_bins_seconds"])])
    body += "<h2>Query observation</h2>" + _observation(request["observation"])
    body += "<h2>Fixed FIT demonstrations</h2>"
    if not request["demonstrations"]:
        body += "<p>None. This is the zero-shot condition.</p>"
    for i, row in enumerate(request["demonstrations"]):
        body += "<h3>Demonstration " + str(i + 1) + "</h3>" + _observation(row, demonstration=True)
    body += "<h2>Response template</h2><p>Replace each null with one finite number, in target-bin order. Null is a placeholder and is not an admissible prediction.</p><pre>" + escape(json.dumps(template, indent=2, ensure_ascii=False)) + "</pre>"
    body += "<p>This page contains one permitted query only. Browser magnification and scrolling change presentation, not observations. No query targets, future traces, source lookup, or score feedback are supplied.</p></body></html>\n"
    return body.encode("utf-8")


def prepare(timing, neural, **demonstrations):
    """Build all T/N pages after unchanged complete paired row admission."""
    bundle = d.build(timing, neural, **demonstrations)
    pages, entries = {}, []
    for ordinal, request in enumerate(bundle["requests"]):
        presentation = d.digest({"schema": PRESENTATION, "request_sha256": request["request_sha256"]})
        body = _render(request, presentation)
        filename = presentation + ".html"
        pages[filename] = body
        entries.append({"ordinal": ordinal, "id": request["id"], "information": request["information"],
                        "request_sha256": request["request_sha256"], "presentation_sha256": presentation,
                        "file": filename, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    manifest = {"schema": SCHEMA, "task": "NEURAL-063", "mode": "restricted_viewer",
                "direct_request_bundle_sha256": d.digest(bundle),
                "exposure_condition": bundle["exposure_condition"], "events": bundle["events"],
                "query_mice": 19, "pages": entries}
    return bundle, manifest, pages


def collect(timing, neural, responses, *, expected_manifest_sha256, **demonstrations):
    """Reconstruct frozen displays before accepting a complete response set."""
    bundle, manifest, _ = prepare(timing, neural, **demonstrations)
    if d.digest(manifest) != expected_manifest_sha256:
        raise d.ContractError("precommitted restricted display manifest mismatch")
    if not isinstance(responses, list) or len(responses) != len(manifest["pages"]):
        raise d.ContractError("one response for every restricted display required")
    numeric = []
    for page, response in zip(manifest["pages"], responses):
        if not isinstance(response, dict) or set(response) != {"presentation_sha256", "request_sha256", "id", "information", "values"}:
            raise d.ContractError("exact five viewer response fields required")
        if response["presentation_sha256"] != page["presentation_sha256"]:
            raise d.ContractError("response belongs to another restricted display")
        numeric.append({k: v for k, v in response.items() if k != "presentation_sha256"})
    result = d.collect(bundle, numeric, expected_bundle_sha256=manifest["direct_request_bundle_sha256"])
    result.update({"schema": "neural063_restricted_viewer_predictions_v1", "mode": "restricted_viewer",
                   "display_manifest_sha256": expected_manifest_sha256, "response_sha256": d.digest(responses)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("render", "collect"))
    parser.add_argument("--timing", required=True)
    parser.add_argument("--neural", required=True)
    parser.add_argument("--fit-timing")
    parser.add_argument("--fit-neural")
    parser.add_argument("--demonstration-ids")
    parser.add_argument("--responses")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.operation == "render" and (args.responses or args.manifest_sha256):
        parser.error("response inputs are only valid for collect")
    if args.operation == "collect" and not (args.responses and args.manifest_sha256):
        parser.error("collect requires --responses and --manifest-sha256")
    flags = (args.fit_timing, args.fit_neural, args.demonstration_ids)
    if any(flags) and not all(flags):
        parser.error("demonstrations require both FIT views and an explicit ID-list file")
    ids = d.read_json(args.demonstration_ids) if args.demonstration_ids else ()
    if args.demonstration_ids and (not isinstance(ids, list) or not ids):
        parser.error("demonstration ID list must be nonempty before FIT views may be read")
    demos = dict(fit_timing=d.read_json(args.fit_timing) if args.fit_timing else None,
                 fit_neural=d.read_json(args.fit_neural) if args.fit_neural else None, demonstration_ids=ids)
    timing, neural = d.read_json(args.timing), d.read_json(args.neural)
    out = Path(args.output)
    if args.operation == "render":
        _, manifest, pages = prepare(timing, neural, **demos)
        out.mkdir()  # A new directory only; a failed partial delivery stays partial.
        for filename, body in pages.items():
            with (out / filename).open("xb") as stream:
                stream.write(body)
        # Manifest is written last; absence means the delivery did not complete.
        with (out / "MANIFEST.json").open("xb") as stream:
            stream.write(d.canonical(manifest))
        print(d.digest(manifest))
    else:
        result = collect(timing, neural, d.read_json(args.responses),
                         expected_manifest_sha256=args.manifest_sha256, **demos)
        with out.open("xb") as stream:
            stream.write(d.canonical(result))
        print(d.digest(result))


if __name__ == "__main__":
    main()

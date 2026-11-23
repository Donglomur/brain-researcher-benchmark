"""Observation-only package and typed SVG access for the fixed descriptive task.

The caller freezes the preparation or package hash outside participant control.
This is a file/package integrity boundary, not an OS sandbox or image-provider
transport. SVG color/display precision differs from numeric programme inputs.
No data are opened on import; private reference/answer values are never decoded.
The operator package contains both representations. Viewer participants must
receive only typed index/SVG responses, never the programme file or operator
filesystem. This module does not itself qualify that provider/access boundary.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
from xml.etree import ElementTree as ET

import view


METHOD = "neural096-split-stratified-quarter-rate-contrasts/v1"
OBSERVATION_KEYS = {"schema", "method", "unit_ids", "phase_bins", "quarter_bin_slices",
                    "rate_units", "display_rate_max_hz", "cells", "information_condition", "limits"}
CELL_KEYS = set(view.CELL_KEYS | view.OPTIONAL_CELL_KEYS)
LIMITS = [
    "One previously exposed animal/session; these are response-conditioned observations.",
    "Recording segments and original train/validation labels are not established randomization or independence blocks.",
    "Aggregate rates omit individual-trial detail in BOTH matched access arms.",
    "Typed SVG viewing has finite visual precision; numerical programme inputs retain numeric precision.",
    "No computed difference, reference summary or numerical answer is delivered.",
]
MAX_OBSERVATION_BYTES = 4 * 1024**2
MAX_INDEX_BYTES = 64 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_BUNDLE_BYTES = 32 * 1024**2
IDS = tuple(row[0] for row in view.ordered_cells())
SVG_NAMES = tuple("viewer/cells/" + cell + ".svg" for cell in IDS)
PAYLOAD_NAMES = ("programme/observations.json", "viewer/INDEX.json", *SVG_NAMES)
ORIGINAL_RECEIPT_SHA = "3011373f5286ee20e3b308644f22c27203cfcd69b971d2f1ff039584734982ac"
ORIGINAL_SOURCE_SHA = "6212aaee2c978d1cd53fbfb433d11f418ed27cd83017b8b2befa4a1d7add5198"
PRECISION = {
    "programme": "original JSON numeric prior-specific means",
    "viewer": "SVG 1360x1180; 256 white-to-blue shade levels; shared global scale",
    "matched_underlying_observations": True,
    "identical_numerical_precision": False,
    "scoring_tolerance_changed": False,
    "image_provider_transport_qualified": False,
    "participant_isolation_qualified": False,
}


class DeliveryError(ValueError):
    """Unbound, incomplete or altered observation delivery."""


def require(ok, message):
    if not ok:
        raise DeliveryError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf8")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def digest(value):
    require(type(value) is str and len(value) == 64
            and all(x in "0123456789abcdef" for x in value), "external frozen SHA256 required")
    return value


def pin_shape(item, limit):
    require(type(item) is dict and set(item) == {"bytes", "sha256"}
            and type(item["bytes"]) is int and 0 < item["bytes"] <= limit,
            "bounded exact file pin required")
    digest(item["sha256"])


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def real(value):
        number = float(value)
        require(math.isfinite(number), "nonfinite JSON value")
        return number
    def constant(value):
        raise DeliveryError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_float=real, parse_constant=constant)


def ordinary(path, *, directory=False):
    path = Path(path)
    require(path.is_absolute(), "absolute operator path required")
    for part in (path, *path.parents):
        require(not part.is_symlink(), "symlink component refused")
    require(path.is_dir() if directory else path.is_file(), "ordinary path required")
    return path


def bounded(path, limit):
    path = ordinary(path)
    require(0 < path.stat().st_size <= limit, "file size outside bound")
    with path.open("rb") as handle:
        body = handle.read(limit + 1)
    require(0 < len(body) <= limit, "file grew beyond bound")
    return body


def pinned(path, expected, limit):
    pin_shape(expected, limit)
    body = bounded(path, expected["bytes"])
    require(pin(body) == expected, "file does not match frozen pin")
    return body


def exact(actual, expected, label):
    require(type(actual) is type(expected), "metadata type mismatch: " + label)
    if type(expected) is dict:
        require(set(actual) == set(expected), "metadata keys mismatch: " + label)
        for key in expected:
            exact(actual[key], expected[key], label + "/" + key)
    elif type(expected) is list:
        require(len(actual) == len(expected), "metadata length mismatch: " + label)
        for i, (left, right) in enumerate(zip(actual, expected)):
            exact(left, right, label + "/" + str(i))
    else:
        require(actual == expected, "metadata value mismatch: " + label)


def observation(body):
    require(type(body) is bytes and 0 < len(body) <= MAX_OBSERVATION_BYTES,
            "bounded observation bytes required")
    data = strict_json(body)
    require(type(data) is dict and set(data) == OBSERVATION_KEYS,
            "exact observation top-level whitelist required")
    exact({key: data[key] for key in ("schema", "method", "phase_bins", "quarter_bin_slices",
                                    "rate_units", "information_condition", "limits")},
          {"schema": view.SCHEMA, "method": METHOD, "phase_bins": 20,
           "quarter_bin_slices": [[0, 5], [5, 10], [10, 15], [15, 20]],
           "rate_units": "spikes/s/source unit",
           "information_condition": "matched_prior_specific_aggregate_trajectories", "limits": LIMITS},
          "observation contract")
    require(type(data["cells"]) is list and all(type(row) is dict and set(row) == CELL_KEYS
                                               for row in data["cells"]),
            "exact observation cell whitelist required")
    view.validate_observation(data)
    return data


def source_binding(binding, observation_body):
    require(type(binding) is dict and set(binding) == {
        "preparation_completion_sha256", "preparation_receipt", "observation"}, "source binding fields")
    digest(binding["preparation_completion_sha256"])
    pin_shape(binding["preparation_receipt"], 128 * 1024)
    pin_shape(binding["observation"], MAX_OBSERVATION_BYTES)
    require(binding["observation"] == pin(observation_body), "observation source binding changed")


def _inventory(root, layout):
    ordinary(root, directory=True)
    for relative, expected in layout.items():
        folder = ordinary(root / relative, directory=True)
        found = set()
        for entry in folder.iterdir():
            require(len(found) < len(expected) and entry.name in expected,
                    "closed inventory mismatch")
            require(not entry.is_symlink(), "indirect inventory entry")
            relative_name = str(entry.relative_to(root))
            ordinary(entry, directory=relative_name in layout)
            found.add(entry.name)
        require(found == set(expected), "closed inventory mismatch")


def load_prepared_observation(prepared, frozen_completion_sha):
    """Authenticate only observation/receipt data; private numeric files stay closed."""
    prepared = Path(prepared)
    digest(frozen_completion_sha)
    _inventory(prepared, {
        "": {"participant", "private", "COMPLETE.json"},
        "participant": {"observations.json", "MANIFEST.json"},
        "private": {"reference.json", "expected-answer.json", "RECEIPT.json"},
    })
    complete_body = bounded(prepared / "COMPLETE.json", 4096)
    require(pin(complete_body)["sha256"] == frozen_completion_sha, "preparation completion changed")
    complete = strict_json(complete_body)
    require(type(complete) is dict and set(complete) == {"schema", "receipt", "total_payload_bytes"}
            and complete["schema"] == "neural096-preparation-completion/v1", "preparation completion schema")
    receipt_body = pinned(prepared / "private/RECEIPT.json", complete["receipt"], 128 * 1024)
    receipt = strict_json(receipt_body)
    require(receipt["schema"] == "neural096-descriptive-operator-preparation/v1"
            and receipt["method"] == METHOD, "preparation method/schema mismatch")
    original = receipt["original_preparation"]
    require(original["receipt_sha256"] == ORIGINAL_RECEIPT_SHA
            and original["source_sha256"] == ORIGINAL_SOURCE_SHA, "original saved-packet binding mismatch")
    files = receipt["files"]
    require(type(files) is dict and set(files) == {"participant/observations.json", "participant/MANIFEST.json",
                                                "private/reference.json", "private/expected-answer.json"},
            "preparation artifact roster mismatch")
    for value in files.values():
        pin_shape(value, 16 * 1024**2)
    require(type(complete["total_payload_bytes"]) is int
            and complete["total_payload_bytes"] == len(receipt_body) + sum(x["bytes"] for x in files.values())
            and complete["total_payload_bytes"] + len(complete_body) <= 16 * 1024**2,
            "preparation byte inventory mismatch")
    body = pinned(prepared / "participant/observations.json", files["participant/observations.json"], MAX_OBSERVATION_BYTES)
    manifest_body = pinned(prepared / "participant/MANIFEST.json", files["participant/MANIFEST.json"], MAX_MANIFEST_BYTES)
    exact(strict_json(manifest_body), {
        "schema": "neural096-matched-participant-delivery/v1", "method": METHOD,
        "files": {"observations.json": pin(body)},
        "access": "Same aggregate observation in typed viewer and numerical programme conditions.",
        "private_files_delivered": False, "runtime_or_model_delivery_qualified": False,
    }, "preparation participant manifest")
    observation(body)
    binding = {"preparation_completion_sha256": frozen_completion_sha,
               "preparation_receipt": pin(receipt_body), "observation": pin(body)}
    return body, binding


def _index(data):
    fields = ("cell_id", "source_split", "observation_segment", "is_eye", "theta",
              "n_long", "n_short", "supported", "missing_priors")
    return {"schema": "neural096-typed-svg-index/v1", "method": METHOD,
            "unit_ids": data["unit_ids"], "phase_bins": 20,
            "quarter_bin_slices": [[0, 5], [5, 10], [10, 15], [15, 20]],
            "rate_units": data["rate_units"], "display_rate_max_hz": data["display_rate_max_hz"],
            "cells": [{**{key: cell[key] for key in fields},
                       "svg": "viewer/cells/" + cell["cell_id"] + ".svg"} for cell in data["cells"]],
            "precision": PRECISION, "scope": "Deterministic descriptive analysis; no learned neural understanding or inference is established."}


def _cell_id(cell_id):
    require(type(cell_id) is str and cell_id in IDS, "exact typed cell ID required")
    return cell_id


def _verify_svg(data, cell_id, body):
    require(type(body) is bytes and 0 < len(body) <= view.MAX_SVG_BYTES, "bounded SVG required")
    try:
        xml = body.decode("utf8")
    except UnicodeDecodeError as exc:
        raise DeliveryError("UTF-8 SVG required") from exc
    # The approved renderer emits no declaration, comment, PI or CDATA. Default
    # ElementTree discards PIs/comments, so reject them before parsing.
    require("<!" not in xml and "<?" not in xml, "SVG declarations/comments/processing instructions refused")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise DeliveryError("invalid SVG") from exc
    ns = "{http://www.w3.org/2000/svg}"
    allowed = {
        "svg": {"width", "height", "viewBox", "role"}, "title": set(), "desc": set(),
        "rect": {"class", "data-unit", "data-bin", "x", "y", "width", "height", "fill", "stroke"},
        "defs": set(), "linearGradient": {"id"}, "stop": {"offset", "stop-color"},
        "g": {"font-family", "fill", "id", "data-scale-min", "data-scale-max"},
        "text": {"x", "y", "font-size", "text-anchor", "data-unit-id"},
        "line": {"x1", "x2", "y1", "y2", "stroke", "stroke-width"},
    }
    nodes = list(root.iter())
    require(len(nodes) <= 5000, "SVG node count bound")
    for node in nodes:
        require(node.tag.startswith(ns) and node.tag[len(ns):] in allowed, "SVG tag not allowed")
        tag = node.tag[len(ns):]
        require(set(node.attrib) <= allowed[tag], "SVG attributes not allowed")
        if tag in ("title", "desc", "rect", "stop", "text", "line"):
            require(len(node) == 0, "SVG leaf element cannot hide child content")
        for value in node.attrib.values():
            require("url(" not in value or value == "url(#rate-scale)", "external SVG reference refused")
        require(not (node.tail or "").strip(), "unexpected SVG tail text")
        if tag not in ("title", "desc", "text"):
            require(not (node.text or "").strip(), "unexpected SVG element text")
    exact(root.attrib, {"width": "1360", "height": "1180", "viewBox": "0 0 1360 1180", "role": "img"}, "SVG canvas")
    cell = data["cells"][IDS.index(cell_id)]
    units, scale = data["unit_ids"], float(data["display_rate_max_hz"])
    require([node.tag for node in root] == [ns + tag for tag in ("title", "desc", "rect", "defs", "g")],
            "SVG top-level structure")
    exact(root[2].attrib, {"width": "100%", "height": "100%", "fill": "white"}, "SVG background")
    require(len(root[3]) == 1 and root[3][0].tag == ns + "linearGradient", "SVG scale gradient")
    gradient = root[3][0]
    exact(gradient.attrib, {"id": "rate-scale"}, "SVG gradient identifier")
    require(len(gradient) == 2 and all(node.tag == ns + "stop" for node in gradient), "SVG gradient stops")
    for node, attributes in zip(gradient, ({"offset": "0%", "stop-color": "#ffffff"},
                                         {"offset": "100%", "stop-color": "#0000ff"})):
        exact(node.attrib, attributes, "SVG scale colors")
    main = root[4]
    exact(main.attrib, {"font-family": "sans-serif", "fill": "#111"}, "SVG foreground")
    require([node.tag for node in main] == [ns + tag for tag in
            ("text",)*5 + ("g", "g", "text", "rect") + ("line", "text")*5], "SVG main ordering")
    def text_geometry(node, x, y, size=12, anchor="start"):
        exact(node.attrib, {"x": str(x), "y": str(y), "font-size": str(size), "text-anchor": anchor},
              "SVG text geometry")
    for node, (y, size) in zip(main[:5], ((30, 21), (55, 15), (79, 12), (100, 12), (1165, 12))):
        text_geometry(node, 24, y, size)
    headings = ["NEURAL-096: prior-specific mean-rate observations",
                f'{cell["source_split"]}; recording segment {cell["observation_segment"]}; '
                f'{"eye" if cell["is_eye"] else "hand"}; direction {cell["theta"]} degrees',
                "Equal-trial mean of count / actual bin exposure; Hz (spikes/s/source unit).",
                "Recording segments are observation support, not verified randomized blocks.",
                "Finite display and color precision limit numerical estimates."]
    require([node.text for node in main[:5]] == headings, "SVG heading/context text")
    text_geometry(main[7], 24, 1101)
    require(main[7].text == f"Common display scale: 0 to {scale:.6g} Hz. White = 0; blue = maximum.",
            "SVG common-scale caption")
    exact(main[8].attrib, {"x": "24", "y": "1115", "width": "320", "height": "12",
                          "fill": "url(#rate-scale)", "stroke": "#555"}, "SVG scale geometry")
    for tick in range(5):
        x = 24 + 80*tick
        exact(main[9 + 2*tick].attrib, {"x1": str(x), "x2": str(x), "y1": "1127", "y2": "1131", "stroke": "#555"}, "SVG scale ticks")
        text_geometry(main[10 + 2*tick], x, 1144, 10, "middle")
        require(main[10 + 2*tick].text == f"{scale * (tick/4):.6g}", "SVG ordered scale labels")
    panels = {node.attrib["id"]: node for node in nodes if node.tag == ns + "g" and "id" in node.attrib}
    require(set(panels) == {"long-panel", "short-panel"}, "both prior panels required")
    require(len([node for node in nodes if "id" in node.attrib]) == 3,
            "exact SVG identifier inventory required")
    texts = [node.text or "" for node in nodes if node.tag == ns + "text"]
    expected_texts = ["NEURAL-096: prior-specific mean-rate observations",
                      f'{cell["source_split"]}; recording segment {cell["observation_segment"]}; '
                      f'{"eye" if cell["is_eye"] else "hand"}; direction {cell["theta"]} degrees',
                      "Equal-trial mean of count / actual bin exposure; Hz (spikes/s/source unit).",
                      "Recording segments are observation support, not verified randomized blocks.",
                      "Finite display and color precision limit numerical estimates.",
                      f"Common display scale: 0 to {scale:.6g} Hz. White = 0; blue = maximum.",
                      *(f"{scale * (tick/4):.6g}" for tick in range(5))]
    rate_count = missing_count = 0
    for prior, left in zip(("long", "short"), (170, 850)):
        panel = panels[prior + "-panel"]
        exact(panel.attrib, {"id": prior + "-panel", "data-scale-min": "0", "data-scale-max": f"{scale:.17g}"}, "common SVG scale")
        labels = [node for node in panel.iter(ns + "text") if "data-unit-id" in node.attrib]
        require(len(labels) == 54, "all unit labels required")
        for u, node in enumerate(labels):
            exact(node.attrib, {"x": str(left - 8), "y": str(152 + 16*u + 12), "font-size": "10",
                                "text-anchor": "end", "data-unit-id": str(units[u])}, "unit label geometry")
            require(node.text == str(units[u]), "unit label identity changed")
        matrix = cell[prior + "_rate_hz"]
        panel_order = ["text"]
        for _ in units:
            panel_order.extend(["text"] + (["rect"]*20 if matrix is not None else []))
        if matrix is None:
            panel_order.append("rect")
        panel_order.extend(["line"]*21)
        if matrix is None:
            panel_order.extend(("rect", "text"))
        panel_order.extend(["text"]*25)
        require([node.tag for node in panel] == [ns + tag for tag in panel_order],
                "SVG direct-child paint order")
        rates = [node for node in panel.iter(ns + "rect") if node.attrib.get("class") == "rate"]
        require(len(rates) == (0 if matrix is None else 1080), "full unit/bin SVG coverage required")
        for j, node in enumerate(rates):
            u, b = divmod(j, 20)
            shade = round(255 * (1.0 - float(matrix[u][b]) / scale))
            exact(node.attrib, {"class": "rate", "data-unit": str(u), "data-bin": str(b),
                                "x": str(left + 24*b), "y": str(152 + 16*u), "width": "24", "height": "16",
                                "fill": f"#{shade:02x}{shade:02x}ff"}, "quantized SVG rate")
        plain_rects = [node for node in panel.iter(ns + "rect") if node.attrib.get("class") != "rate"]
        require(len(plain_rects) == (2 if matrix is None else 0), "missing-prior rectangle inventory")
        if matrix is None:
            exact(plain_rects[0].attrib, {"x": str(left), "y": "152", "width": "480", "height": "864", "fill": "#eee"}, "missing-prior panel geometry")
            exact(plain_rects[1].attrib, {"x": str(left + 8), "y": "518", "width": "464", "height": "32", "fill": "#eee"}, "missing-prior annotation backing")
        lines = list(panel.iter(ns + "line"))
        require(len(lines) == 21, "all SVG phase boundaries required")
        for phase, node in enumerate(lines):
            quarter = phase % 5 == 0
            exact(node.attrib, {"x1": str(left + phase*24), "x2": str(left + phase*24), "y1": "152", "y2": "1016",
                                "stroke": "#555" if quarter else "#ddd", "stroke-width": "1.5" if quarter else "0.25"}, "SVG phase/quarter boundaries")
        other_texts = [node for node in panel.iter(ns + "text") if "data-unit-id" not in node.attrib]
        require(len(other_texts) == (27 if matrix is None else 26), "panel text inventory")
        text_geometry(other_texts[0], left + 240, 132, 17, "middle")
        require(other_texts[0].text == f"{prior.capitalize()} prior — n = {cell['n_' + prior]}",
                "SVG prior/count caption")
        start = 1
        if matrix is None:
            text_geometry(other_texts[1], left + 240, 540, 14, "middle")
            require(other_texts[1].text == "UNSUPPORTED: no trials for this prior", "SVG missing-prior caption")
            start += 1
        for phase in range(20):
            text_geometry(other_texts[start + phase], left + (phase + 0.5)*24, 1034, 10, "middle")
            require(other_texts[start + phase].text == str(phase + 1), "SVG phase labels")
        for quarter in range(4):
            text_geometry(other_texts[start + 20 + quarter], left + (quarter*5 + 2.5)*24, 1055, 12, "middle")
            require(other_texts[start + 20 + quarter].text == f"Q{quarter+1}", "SVG quarter labels")
        text_geometry(other_texts[-1], left + 240, 1076, 11, "middle")
        require(other_texts[-1].text == "20 phase bins spanning the complete observed Set–Go interval",
                "SVG interval caption")
        expected_texts.extend([f"{prior.capitalize()} prior — n = {cell['n_' + prior]}",
                               *(str(unit) for unit in units), *(str(b + 1) for b in range(20)),
                               *(f"Q{q+1}" for q in range(4)),
                               "20 phase bins spanning the complete observed Set–Go interval"])
        if matrix is None:
            expected_texts.append("UNSUPPORTED: no trials for this prior")
            missing_count += 1
        rate_count += len(rates)
    require(Counter(texts) == Counter(expected_texts), "exact visible text inventory required")
    counts = Counter(node.tag[len(ns):] for node in nodes)
    exact(dict(counts), {"svg": 1, "title": 1, "desc": 1, "rect": 2 + rate_count + 2*missing_count,
                        "defs": 1, "linearGradient": 1, "stop": 2, "g": 3,
                        "text": len(expected_texts), "line": 47}, "SVG structural inventory")
    require(root.find(ns + "title").text == "NEURAL-096 prior-specific mean-rate observations", "SVG title")
    require(root.find(ns + "desc").text == "All 54 source units and 20 phase bins. Same scale for both priors and all cells. No difference, reference summary, confidence interval or significance conclusion is displayed.", "SVG description")
    return {"rate_rectangles": rate_count, "missing_prior_panels": missing_count}


def verify_svg(data, cell_id, body):
    """Structural/semantic SVG validation without raster or model transport."""
    _cell_id(cell_id)
    validated = observation(encoded(data))
    return _verify_svg(validated, cell_id, body)


def iter_payloads(observation_body, binding):
    """Yield all 50 non-manifest payloads without writing files or retaining all SVGs."""
    data = observation(observation_body)
    source_binding(binding, observation_body)
    yield "programme/observations.json", observation_body
    index = encoded(_index(data))
    require(len(index) <= MAX_INDEX_BYTES, "index exceeds bound")
    yield "viewer/INDEX.json", index
    for cell_id in IDS:
        body = view.render_cell(data, cell_id)
        _verify_svg(data, cell_id, body)
        yield "viewer/cells/" + cell_id + ".svg", body


def _file_limit(name):
    return (MAX_OBSERVATION_BYTES if name == "programme/observations.json" else
            MAX_INDEX_BYTES if name == "viewer/INDEX.json" else view.MAX_SVG_BYTES)


def _manifest(files, binding):
    require(type(files) is dict and set(files) == set(PAYLOAD_NAMES), "complete payload inventory required")
    for name, item in files.items():
        pin_shape(item, _file_limit(name))
    return {"schema": "neural096-observation-delivery-manifest/v1", "method": METHOD,
            "source_binding": binding, "files": files, "cells": 48, "precision": PRECISION,
            "private_reference_or_answers_delivered": False,
            "scope": "Deterministic descriptive observations; successful programmed arithmetic alone does not establish learned neural understanding."}


def exclusive_write(path, body):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def write_bundle(observation_body, binding, output):
    """Write a fresh public package. Preserve partial writes; never retry in place."""
    data = observation(observation_body)
    source_binding(binding, observation_body)
    output = Path(output)
    require(output.is_absolute() and not output.exists() and not output.is_symlink(), "fresh absolute output required")
    ordinary(output.parent, directory=True)
    require(not any((p / ".git").exists() for p in (output.parent, *output.parents)), "generated package must stay outside Git")
    output.mkdir(mode=0o700)
    for name in ("programme", "viewer", "viewer/cells"):
        (output / name).mkdir(mode=0o700)
    files, total = {}, 0
    for name, body in iter_payloads(observation_body, binding):
        require(name in PAYLOAD_NAMES and name not in files, "payload path inventory")
        total += len(body)
        require(total <= MAX_BUNDLE_BYTES - MAX_MANIFEST_BYTES, "package exceeds byte cap")
        exclusive_write(output / name, body)
        files[name] = pin(body)
    manifest_body = encoded(_manifest(files, binding))
    require(len(manifest_body) <= MAX_MANIFEST_BYTES, "manifest exceeds bound")
    _bundle_inventory(output, complete=False)
    exclusive_write(output / "MANIFEST.json", manifest_body)
    supported = sum(cell["supported"] for cell in data["cells"])
    return {"schema": "neural096-observation-delivery-write/v1", "method": METHOD,
            "manifest": pin(manifest_body), "files_written": 51,
            "bytes_written": total + len(manifest_body), "cells": 48,
            "supported_cells": supported, "unsupported_cells": 48 - supported,
            "source_binding": binding, "provider_transport_qualified": False,
            "participant_isolation_qualified": False}


def prepare_bundle(prepared, frozen_completion_sha, output):
    body, binding = load_prepared_observation(prepared, frozen_completion_sha)
    return write_bundle(body, binding, output)


def _bundle_inventory(bundle, *, complete=True):
    _inventory(bundle, {
        "": {"programme", "viewer"} | ({"MANIFEST.json"} if complete else set()),
        "programme": {"observations.json"}, "viewer": {"INDEX.json", "cells"},
        "viewer/cells": {cell + ".svg" for cell in IDS},
    })


def _load(bundle, frozen_manifest_sha):
    bundle = Path(bundle)
    digest(frozen_manifest_sha)
    _bundle_inventory(bundle)
    manifest_body = bounded(bundle / "MANIFEST.json", MAX_MANIFEST_BYTES)
    require(pin(manifest_body)["sha256"] == frozen_manifest_sha, "package manifest changed")
    manifest = strict_json(manifest_body)
    require(type(manifest) is dict and set(manifest) == set(_manifest(
        {name: {"bytes": 1, "sha256": "0"*64} for name in PAYLOAD_NAMES}, {})), "manifest top-level keys")
    files, binding = manifest["files"], manifest["source_binding"]
    exact(manifest, _manifest(files, binding), "package manifest")
    require(sum(item["bytes"] for item in files.values()) + len(manifest_body) <= MAX_BUNDLE_BYTES,
            "package declared bytes exceed cap")
    body = pinned(bundle / "programme/observations.json", files["programme/observations.json"], MAX_OBSERVATION_BYTES)
    source_binding(binding, body)
    data = observation(body)
    index_body = pinned(bundle / "viewer/INDEX.json", files["viewer/INDEX.json"], MAX_INDEX_BYTES)
    index = strict_json(index_body)
    exact(index, _index(data), "typed index")
    return manifest, data, index, body, manifest_body


def verify_bundle(bundle, frozen_manifest_sha):
    """Read/hash/validate every public artifact once; never decode private values."""
    bundle = Path(bundle)
    manifest, data, index, body, manifest_body = _load(bundle, frozen_manifest_sha)
    totals = {"rate_rectangles": 0, "missing_prior_panels": 0}
    for cell_id, name in zip(IDS, SVG_NAMES):
        svg = pinned(bundle / name, manifest["files"][name], view.MAX_SVG_BYTES)
        counts = _verify_svg(data, cell_id, svg)
        for key in totals:
            totals[key] += counts[key]
    supported = sum(cell["supported"] for cell in data["cells"])
    return {"schema": "neural096-observation-delivery-verification/v1", "method": METHOD,
            "manifest": pin(manifest_body), "files_verified": 51,
            "bytes_verified": len(manifest_body) + sum(p["bytes"] for p in manifest["files"].values()),
            "cells": 48, "supported_cells": supported, "unsupported_cells": 48 - supported,
            **totals, "provider_transport_qualified": False, "participant_isolation_qualified": False}


def list_cells(bundle, frozen_manifest_sha):
    """Return the complete typed index after metadata/inventory authentication."""
    return _load(bundle, frozen_manifest_sha)[2]


def read_programme(bundle, frozen_manifest_sha):
    """Return byte-identical numeric observations, never private reference values."""
    return _load(bundle, frozen_manifest_sha)[3]


def get_view(bundle, frozen_manifest_sha, cell_id):
    """Verify metadata plus the selected SVG; other SVG bytes are not reread."""
    _cell_id(cell_id)  # Reject arbitrary paths before any filesystem access.
    bundle = Path(bundle)
    manifest, data, index, body, manifest_body = _load(bundle, frozen_manifest_sha)
    name = "viewer/cells/" + cell_id + ".svg"
    svg = pinned(bundle / name, manifest["files"][name], view.MAX_SVG_BYTES)
    _verify_svg(data, cell_id, svg)
    return svg

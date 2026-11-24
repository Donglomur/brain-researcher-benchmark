"""Export one complete, target-free N057 query view as an offline observation page.

This is observation delivery, not a direct-lane runner, access-control boundary,
scorer, or qualification credential. No training or protected files are read.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

DIMENSIONS = {"IMAGE": 176, "PRE": 170, "BASE": 346, "LATE": 686}
QUERY_FIELDS = {"schema", "cell", "category_schema_sha256", "categories",
                "features", "query_ids", "fit_state_sha256", "preparation_sha256"}
MAX_QUERY_BYTES = 524288
MAX_FEATURE_BYTES = 200 * 686 * 8 + 4108


class ObservationError(ValueError):
    """A view does not preserve the exact registered observation boundary."""


def require(condition, message):
    if not condition:
        raise ObservationError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    require(type(value) is str and len(value) == 64
            and set(value) <= set("0123456789abcdef"), "exact SHA-256 identity")


def strings(values, count, label):
    require(type(values) is list and len(values) == count
            and all(type(v) is str and 0 < len(v.encode("utf-8")) <= 1024 for v in values)
            and len(set(values)) == count, "complete ordered unique " + label)


def parse(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def invalid(_):
        raise ObservationError("nonfinite JSON token")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def validate_view(doc):
    require(type(doc) is dict and set(doc) == QUERY_FIELDS,
            "closed query view; no targets, training rows or extra fields")
    require(doc["schema"] == "neural057-query-view-v1", "registered query schema")
    cell = doc["cell"]
    require(type(cell) is dict and set(cell) == {"person", "mode", "panel"}, "closed cell")
    require(type(cell["person"]) is str and cell["person"] in tuple(
        "sub-%02d" % p for p in range(1, 11))
        and type(cell["mode"]) is str and cell["mode"] in ("F", "I")
        and type(cell["panel"]) is str and cell["panel"] in DIMENSIONS, "registered full-cell identity")
    for key in ("category_schema_sha256", "fit_state_sha256", "preparation_sha256"):
        digest(doc[key])
    strings(doc["categories"], 53, "category roster")
    strings(doc["query_ids"], 200, "query IDs")
    feature = doc["features"]
    require(type(feature) is dict and set(feature) == {"path", "bytes", "sha256"},
            "closed feature descriptor")
    require(feature["path"] == "features.npy", "only the same-directory campaign feature file")
    require(type(feature["bytes"]) is int and 0 < feature["bytes"] <= MAX_FEATURE_BYTES,
            "bounded exact feature byte count")
    digest(feature["sha256"])
    return cell["panel"]


def decode_features(raw, panel):
    """Read only the C-order little-endian f8 format written by panel_features.

    No NumPy installation, pickle loader, casts, cropping, rescaling or imputation.
    """
    require(type(raw) is bytes and len(raw) <= MAX_FEATURE_BYTES, "bounded primitive feature bytes")
    require(raw[:6] == b"\x93NUMPY" and raw[6:8] in (b"\x01\x00", b"\x02\x00"),
            "primitive NPY version 1 or 2")
    prefix = 10 if raw[6:8] == b"\x01\x00" else 12
    require(len(raw) >= prefix, "complete NPY header prefix")
    header_bytes = int.from_bytes(raw[8:prefix], "little")
    require(0 < header_bytes <= 4096 and len(raw) >= prefix + header_bytes,
            "bounded complete NPY header")
    try:
        header = ast.literal_eval(raw[prefix:prefix + header_bytes].decode("latin1"))
    except (SyntaxError, ValueError, UnicodeError) as exc:
        raise ObservationError("literal primitive NPY header") from exc
    require(type(header) is dict and set(header) == {"descr", "fortran_order", "shape"}
            and header["descr"] == "<f8" and header["fortran_order"] is False
            and type(header["shape"]) is tuple
            and all(type(n) is int for n in header["shape"])
            and header["shape"] == (200, DIMENSIONS[panel]),
            "complete original 200-row panel, C-order little-endian float64")
    data = raw[prefix + header_bytes:]
    width = DIMENSIONS[panel]
    require(len(data) == 200 * width * 8, "exact data extent; no missing rows or trailing payload")
    rows = list(struct.iter_unpack("<" + "d" * width, data))
    require(all(math.isfinite(v) for row in rows for v in row), "finite original features")
    return rows


def feature_labels(panel):
    image = ["IMAGE RGB cell r%d c%d %s mean" % (r, c, color)
             for r in range(1, 5) for c in range(1, 5) for color in ("R", "G", "B")]
    image += ["IMAGE Sobel cell r%d c%d orientation bin %d mean magnitude" % (r, c, b)
              for r in range(1, 5) for c in range(1, 5) for b in range(8)]
    pre = ["PRE whitened axis %02d ordered sample %02d" % (axis, sample)
           for axis in range(1, 18) for sample in range(1, 11)]
    late = ["LATE whitened axis %02d ordered sample %02d" % (axis, sample)
            for axis in range(1, 18) for sample in range(1, 21)]
    return {"IMAGE": image, "PRE": pre, "BASE": image + pre,
            "LATE": image + pre + late}[panel]


def read_regular(path, maximum):
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= maximum, "bounded regular input file")
        raw = handle.read(maximum + 1)
        require(len(raw) == info.st_size and len(raw) <= maximum, "complete bounded input read")
        return raw


def load_query(path):
    raw = read_regular(path, MAX_QUERY_BYTES)
    doc = parse(raw)
    panel = validate_view(doc)
    features = read_regular(path.parent / "features.npy", doc["features"]["bytes"])
    require(len(features) == doc["features"]["bytes"] and sha(features) == doc["features"]["sha256"],
            "exact recorded feature bytes and SHA-256")
    return doc, decode_features(features, panel), sha(raw)


def render(doc, rows, query_sha256):
    panel = validate_view(doc)
    digest(query_sha256)
    require(len(rows) == 200 and all(len(row) == DIMENSIONS[panel] for row in rows)
            and all(type(v) in (int, float) and math.isfinite(v) for row in rows for v in row),
            "complete finite render matrix")
    payload = dict(doc, feature_labels=feature_labels(panel), values=rows,
                   query_view_sha256=query_sha256)
    # Do not allow text from a category/ID to close the inert JSON script element.
    data = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return (PAGE.replace("__OBSERVATION_JSON__", data)).encode("utf-8")


PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>NEURAL-057 complete query observations</title>
<style>body{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;line-height:1.5}table{border-collapse:collapse;width:100%}td,th{padding:.3rem .6rem;border-bottom:1px solid #ddd;text-align:left}td:last-child{font-family:monospace}select,button{font:inherit;padding:.3rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}#position{margin:1rem 0}caption{text-align:left;font-weight:bold}</style>
<h1>Complete query observations</h1><p id="cell"></p>
<p>Every one of the 200 query rows and every feature in this panel is retained in its original order. Values are shown without scaling, clipping or rounding. Category names are the output roster, not query labels.</p>
<p>EEG values are released noise-normalized coordinates, averaged over all 80 test repetitions. PRE uses the registered [-0.1, 0) s window; LATE uses [0.2, 0.4) s. Axis and sample labels are positional: the query view does not contain anatomical channel names or exact source timestamps. Image features comprise 48 RGB means followed by 128 Sobel means; no original image is added.</p>
<label for="query">Query row</label> <button id="previous" type="button">Previous</button>
<select id="query"></select> <button id="next" type="button">Next</button><p id="position" aria-live="polite"></p>
<table><caption>All feature values for the selected query</caption><thead><tr><th scope="col">Column</th><th scope="col">Coordinate</th><th scope="col">Value</th></tr></thead><tbody id="features"></tbody></table>
<details><summary>All 53 categories, in prediction order</summary><ol id="categories"></ol></details>
<details><summary>Exact input identities</summary><pre id="identity"></pre></details>
<p>Observation delivery only. This page does not implement a restricted execution environment, training exposure, model-state custody, scoring or a complete direct-versus-tool comparison. Keep it within the authorized participant boundary; it contains the complete query observations and IDs. Authentic data and runtime qualification remain required.</p>
<noscript>This local viewer requires JavaScript to select rows. The complete observations remain embedded in this file; no network service is used.</noscript>
<script id="observations" type="application/json">__OBSERVATION_JSON__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('observations').textContent);
const choose=document.getElementById('query');
document.getElementById('cell').textContent='NEURAL-057 · '+data.cell.person+' · mode '+data.cell.mode+' · panel '+data.cell.panel+' · 200 rows × '+data.feature_labels.length+' features';
data.query_ids.forEach((id,i)=>{const o=document.createElement('option');o.value=String(i);o.textContent=String(i+1)+': '+id;choose.append(o);});
data.categories.forEach(name=>{const li=document.createElement('li');li.textContent=name;document.getElementById('categories').append(li);});
document.getElementById('identity').textContent=JSON.stringify({query_view_sha256:data.query_view_sha256,features:data.features,category_schema_sha256:data.category_schema_sha256,fit_state_sha256:data.fit_state_sha256,preparation_sha256:data.preparation_sha256},null,2);
function show(){const i=Number(choose.value),body=document.getElementById('features');body.replaceChildren();data.feature_labels.forEach((label,j)=>{const tr=document.createElement('tr');[String(j+1),label,Object.is(data.values[i][j],-0)?'-0':String(data.values[i][j])].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});body.append(tr);});document.getElementById('position').textContent='Row '+String(i+1)+' of 200 · '+data.query_ids[i];document.getElementById('previous').disabled=i===0;document.getElementById('next').disabled=i===199;}
choose.addEventListener('change',show);
document.getElementById('previous').addEventListener('click',()=>{choose.selectedIndex=Math.max(0,choose.selectedIndex-1);show();});
document.getElementById('next').addEventListener('click',()=>{choose.selectedIndex=Math.min(199,choose.selectedIndex+1);show();});
show();
</script></html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    doc, rows, query_sha256 = load_query(args.query)
    body = render(doc, rows, query_sha256)
    with args.output.open("xb") as handle:
        handle.write(body)


if __name__ == "__main__":
    main()

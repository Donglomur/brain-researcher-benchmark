"""Export complete, target-free NEURAL-065 EEG query observations for inspection.

Consumes only pinned public query/preparation manifests and float64 observations.
This is an offline presentation component, not a participant isolation runtime.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile

TASK_ID = "NEURAL-065"
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_ASSET_BYTES = 64 * 1024 * 1024
TIME_COORDINATE = "sample_index / sampling_frequency_hz, relative to each window"


class ViewError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ViewError(message)


def fields(value, names, context):
    require(isinstance(value, dict) and set(value) == set(names.split()), context + ": fields")


def positive_int(value, context):
    require(type(value) is int and value > 0, context + ": positive integer required")
    return value


def pin(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid SHA256")
    return value


def query_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value), "opaque query ID required")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    def bad(value):
        raise ViewError("nonfinite JSON constant")
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ViewError("invalid JSON") from exc


class Reader:
    def __init__(self, maximum):
        self.maximum = positive_int(maximum, "input byte limit")
        self.bytes = 0

    def read(self, path, expected_hash, limit):
        pin(expected_hash)
        allowance = min(limit, self.maximum - self.bytes)
        require(allowance >= 0, "input byte limit exceeded")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "input must be a regular file")
            raw = source.read(allowance + 1)
        self.bytes += len(raw)
        require(len(raw) <= allowance, "input byte limit exceeded")
        require(digest(raw) == expected_hash, "input digest mismatch")
        return raw


def validate_queries(value):
    fields(value, "schema_version task_id packet_sha256 queries", "queries")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1, "query version")
    require(value["task_id"] == TASK_ID, "query task mismatch")
    pin(value["packet_sha256"])
    require(isinstance(value["queries"], list) and value["queries"], "empty query roster")
    result = {}
    for row in value["queries"]:
        fields(row, "query_id neural_asset_sha256", "query")
        qid = query_id(row["query_id"])
        require(qid not in result, "duplicate query ID")
        result[qid] = pin(row["neural_asset_sha256"])
    return result


def validate_observations(value):
    fields(value, "schema_version task_id modality dtype byte_order axes unit sampling_frequency_hz "
           "time_origin_s time_coordinate channel_ids observations", "observations")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1, "observation version")
    require(value["task_id"] == TASK_ID and value["modality"] == "EEG", "observation task/modality")
    require(value["dtype"] == "float64" and value["byte_order"] == "little"
            and value["axes"] == ["time", "channel"] and value["unit"] == "V", "observation format/units")
    hz = value["sampling_frequency_hz"]
    require(type(hz) in (int, float), "invalid sampling frequency")
    try:
        require(math.isfinite(float(hz)) and hz > 0 and float(hz) == hz, "invalid sampling frequency")
    except OverflowError as exc:
        raise ViewError("invalid sampling frequency") from exc
    require(type(value["time_origin_s"]) is int and value["time_origin_s"] == 0
            and value["time_coordinate"] == TIME_COORDINATE, "relative time convention")
    channels = value["channel_ids"]
    require(isinstance(channels, list) and 0 < len(channels) <= 4096
            and channels == [f"EEG{i:03d}" for i in range(len(channels))], "channel roster")
    require(isinstance(value["observations"], list) and value["observations"], "empty observation roster")
    seen = set()
    for row in value["observations"]:
        fields(row, "query_id neural_asset_sha256 path bytes shape", "observation")
        qid = query_id(row["query_id"])
        require(qid not in seen, "duplicate observation ID"); seen.add(qid)
        pin(row["neural_asset_sha256"])
        require(row["path"] == "assets/" + qid + ".f64le", "noncanonical asset path")
        shape = row["shape"]
        require(isinstance(shape, list) and len(shape) == 2, "observation shape")
        positive_int(shape[0], "time samples"); positive_int(shape[1], "channels")
        require(shape[1] == len(channels), "channel dimension mismatch")
        require(type(row["bytes"]) is int and row["bytes"] == shape[0] * shape[1] * 8
                and row["bytes"] <= MAX_ASSET_BYTES, "observation size/profile bound")
        require(math.isfinite((shape[0] - 1) / hz), "nonfinite relative time")
    return value


PAGE = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<title>NEURAL-065 EEG observation</title>
<style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem}label{display:inline-block;margin:0 1rem 1rem 0}input{width:8rem}canvas{width:100%;border:1px solid #999}table{border-collapse:collapse}th,td{padding:.2rem 1rem;text-align:right}th{position:sticky;top:0;background:white}.scroll{max-height:28rem;overflow:auto}#error{color:#a00}</style>
<a href="index.html">Complete query collection</a><h1>EEG observation</h1>
<p id="identity"></p><p id="dimensions"></p>
<p>Raw voltage observations. Channel IDs preserve source order; anatomical locations are unavailable.
Time is relative to this sentence window. The viewport displays every selected sample without averaging,
filtering or downsampling. All samples remain available through navigation. Calibration support is separate.</p>
<label>Channel <select id="channel"></select></label>
<label>First sample <input id="first" type="number" min="0" value="0" step="1"></label>
<label>Samples to display (1–4096) <input id="count" type="number" min="1" max="4096" value="1000" step="1"></label>
<button id="previous">Previous window</button> <button id="next">Next window</button> <button id="show">Show</button>
<p id="error" role="alert"></p><p id="range"></p><canvas id="plot" width="1200" height="360"></canvas>
<div class="scroll"><table><thead><tr><th>Sample index</th><th>Relative time (s)</th><th>Voltage (V)</th></tr></thead><tbody id="values"></tbody></table></div>
<script id="observation" type="application/json">__DATA__</script>
<script>
"use strict";
const obs = JSON.parse(document.getElementById("observation").textContent);
const decoded = atob(obs.data_base64), buffer = new ArrayBuffer(decoded.length), bytes = new Uint8Array(buffer);
for (let i = 0; i < decoded.length; i++) bytes[i] = decoded.charCodeAt(i);
const data = new DataView(buffer), samples = obs.shape[0], channels = obs.shape[1];
const byId = id => document.getElementById(id), channel = byId("channel"), first = byId("first"), count = byId("count");
byId("identity").textContent = "Query " + obs.query_id + " · Packet SHA-256 " + obs.packet_sha256;
byId("dimensions").textContent = samples + " samples × " + channels + " channels · " + obs.sampling_frequency_hz + " Hz · volts";
obs.channel_ids.forEach((name, i) => {const option = document.createElement("option"); option.value = i; option.textContent = name; channel.appendChild(option);});
count.value = Math.min(1000, samples); first.max = samples - 1;
function selection() {
  const a = Number(first.value), n = Number(count.value), c = Number(channel.value);
  if (!Number.isInteger(a) || a < 0 || a >= samples || !Number.isInteger(n) || n < 1 || n > 4096 || !Number.isInteger(c) || c < 0 || c >= channels) throw Error("Choose an available channel, a valid first sample, and 1–4096 samples.");
  return {a, b: Math.min(samples, a + n), c};
}
function render() {
  byId("error").textContent = "";
  try {
    const {a,b,c} = selection(), values = [];
    for(let i=a;i<b;i++) values.push(data.getFloat64(8*(i*channels+c),true));
    const low = Math.min(...values), high = Math.max(...values), constant = high === low;
    // Normalize plot coordinates only, avoiding overflow for finite extremes.
    const magnitude = Math.max(Math.abs(low),Math.abs(high)) || 1;
    const scaledLow=low/magnitude, scaledHigh=high/magnitude;
    const canvas=byId("plot"), ctx=canvas.getContext("2d"), left=110, right=1170, top=25, bottom=300;
    ctx.clearRect(0,0,1200,360); ctx.fillStyle="#222"; ctx.font="14px system-ui";
    ctx.fillText(high.toExponential(5)+" V",5,top+5); ctx.fillText(low.toExponential(5)+" V",5,bottom);
    ctx.fillText((a/obs.sampling_frequency_hz).toPrecision(8)+" s",left,335);
    ctx.fillText(((b-1)/obs.sampling_frequency_hz).toPrecision(8)+" s",right-100,335);
    ctx.strokeStyle="#2563eb"; ctx.lineWidth=1; ctx.beginPath();
    values.forEach((v,j)=>{const x=values.length===1?(left+right)/2:left+j*(right-left)/(values.length-1), y=constant?(bottom+top)/2:bottom-(v/magnitude-scaledLow)*(bottom-top)/(scaledHigh-scaledLow); if(j===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}); ctx.stroke();
    if(values.length===1){ctx.beginPath();ctx.arc((left+right)/2,(bottom+top)/2,3,0,2*Math.PI);ctx.fill();}
    byId("range").textContent = obs.channel_ids[c]+": samples ["+a+", "+b+") of "+samples+". Vertical scale follows this viewport; compare numerical volts across views.";
    const rows=document.createDocumentFragment();
    values.forEach((v,j)=>{const row=document.createElement("tr");[a+j,(a+j)/obs.sampling_frequency_hz,v].forEach(value=>{const cell=document.createElement("td");cell.textContent=String(value);row.appendChild(cell);});rows.appendChild(row);});
    byId("values").replaceChildren(rows);
  } catch(error) {byId("error").textContent=error.message;}
}
byId("show").onclick=render; channel.onchange=render;
byId("next").onclick=()=>{try{const {a,b}=selection();first.value=b<samples?b:a;render();}catch(error){byId("error").textContent=error.message;}};
byId("previous").onclick=()=>{try{const {a}=selection();first.value=Math.max(0,a-Number(count.value));render();}catch(error){byId("error").textContent=error.message;}};
render();
</script></html>
'''


def export(queries_path, observations, output, *, queries_sha256, max_input_bytes, max_output_bytes):
    """Validate exact complete query support and publish a new collection atomically."""
    positive_int(max_output_bytes, "output byte limit")
    require(observations, "observation manifests required")
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), "output already exists")
    require(output.parent.is_dir(), "output parent missing")
    reader = Reader(max_input_bytes)
    queries = parse_json(reader.read(queries_path, queries_sha256, MAX_METADATA_BYTES))
    wanted = validate_queries(queries)
    selected, seen, manifest_pins = {}, set(), []
    for path, expected_hash in observations:
        path = Path(path)
        require(path.name == "observations.json", "expected preparation observations.json")
        value = validate_observations(parse_json(reader.read(path, expected_hash, MAX_METADATA_BYTES)))
        manifest_pins.append(expected_hash)
        require(not (path.parent / "assets").is_symlink(), "asset directory symlink forbidden")
        for row in value["observations"]:
            qid = row["query_id"]
            require(qid not in seen, "observation ID repeated across sources"); seen.add(qid)
            if qid in wanted:
                require(row["neural_asset_sha256"] == wanted[qid], "query observation digest mismatch")
                selected[qid] = (path.parent / row["path"], row, value)
    require(set(selected) == set(wanted), "incomplete query observation coverage")
    staging = Path(tempfile.mkdtemp(prefix=".neural065-view-", dir=output.parent))
    output_bytes, files = 0, []
    def write(name, raw):
        nonlocal output_bytes
        require(output_bytes + len(raw) <= max_output_bytes, "output byte limit exceeded")
        (staging / name).write_bytes(raw); output_bytes += len(raw)
        files.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    try:
        for qid in wanted:  # Preserve the complete evaluator roster order.
            path, row, metadata = selected[qid]
            raw = reader.read(path, wanted[qid], row["bytes"])
            require(len(raw) == row["bytes"], "observation byte/shape mismatch")
            require(all(math.isfinite(v[0]) for v in struct.iter_unpack("<d", raw)), "nonfinite observation")
            payload = {"query_id": qid, "packet_sha256": queries["packet_sha256"],
                       "shape": row["shape"], "channel_ids": metadata["channel_ids"],
                       "sampling_frequency_hz": metadata["sampling_frequency_hz"],
                       "data_base64": base64.b64encode(raw).decode("ascii")}
            page = PAGE.replace("__DATA__", json.dumps(payload, separators=(",", ":"), allow_nan=False))
            write(qid + ".html", page.encode())
        links = "\n".join('<li><a href="'+qid+'.html">'+qid+'</a></li>' for qid in wanted)
        index = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                 '<title>NEURAL-065 complete query collection</title><h1>EEG query observations</h1><p>'
                 + str(len(wanted)) + ' queries; all selected samples and channels are retained. '
                 'No target labels or calibration labels are included. This presentation component does not enforce no-tools participation.</p>'
                 '<p>Packet SHA-256: ' + queries["packet_sha256"] + '</p><ol>' + links + '</ol></html>')
        write("index.html", index.encode())
        receipt = {"schema_version": 1, "task_id": TASK_ID, "packet_sha256": queries["packet_sha256"],
                   "queries_sha256": queries_sha256, "observation_manifest_sha256": manifest_pins,
                   "query_count": len(wanted), "files": list(files), "input_bytes_read": reader.bytes,
                   "qualification": "observation_presentation_component_only", "model_executed": False}
        write("collection.json", json_bytes(receipt))
        require(not output.exists() and not output.is_symlink(), "output appeared during export")
        staging.rename(output)
        staging = None
        return {"queries": len(wanted), "input_bytes_read": reader.bytes, "output_bytes": output_bytes,
                "collection_sha256": digest(json_bytes(receipt)), "qualification": receipt["qualification"]}
    finally:
        if staging is not None:
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("queries", "queries-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--observations", nargs=2, action="append", required=True, metavar=("MANIFEST", "SHA256"))
    for name in ("max-input-bytes", "max-output-bytes"):
        parser.add_argument("--" + name, type=int, required=True)
    args = vars(parser.parse_args())
    try:
        result = export(args.pop("queries"), args.pop("observations"), args.pop("output"), **args)
        print(json.dumps(result, sort_keys=True))
    except (ViewError, OSError) as exc:
        parser.exit(2, "observation export refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()

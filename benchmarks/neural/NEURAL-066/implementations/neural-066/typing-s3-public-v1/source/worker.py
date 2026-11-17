"""Trusted generic entry; science imports occur only after actual job selection."""
import failures
import math
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import encoded, exact, need
from safe_io import capture, child, new_json, pin, strict

def files(output, cap, maximum):
    out = {}
    for path in sorted(Path(output).rglob('*')):
        need(not path.is_symlink(), 'No output symlink')
        if path.is_file():
            name = str(path.relative_to(output))
            need(name != 'OUTPUTS.json', 'No prewritten completion manifest')
            body = capture(path, cap)
            out[name] = pin(body)
            need(len(out) <= maximum and sum((x['bytes'] for x in out.values())) <= cap, 'Complete full output cap before completion')
    return out

def run(request, inputroot, outputroot, local_end):
    need(time.monotonic() < local_end, 'Guest-local elapsed allowance before action')
    action = request['action']
    role = request['role']
    if action in ('candidate_policy', 'candidate_fit', 'candidate_infer'):
        need(role in ('A', 'B'), 'Exact candidate source role')
        from candidate_worker import run as candidate
        result = candidate(request, inputroot, outputroot)
    elif action in ('r2_inner', 'r2_final', 'r2_infer', 'r0fit', 'r0infer', 'r1count', 'r1infer'):
        need(role == 'reference', 'Operator-independent reference role')
        from reference.worker import run as reference
        result = reference(request['reference_request'], inputroot, outputroot)
    else:
        need(role == 'operator', 'Original preparation operator realm')
        from preparation_dispatch import run as preparation
        result = preparation(request, inputroot, outputroot)
    need(time.monotonic() < local_end, 'Guest-local elapsed allowance after action')
    return result

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--request', required=True)
    p.add_argument('--wire', required=True)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args(argv)
    wire_raw = capture(a.wire, 2097152)
    wire = strict(wire_raw)
    request_raw = capture(a.request, 2097152)
    request = strict(request_raw)
    duration = request['guest_duration_seconds']
    need(type(duration) in (int, float) and math.isfinite(duration) and (duration > 0), 'Finite guest elapsed duration supplied by host')
    start = time.monotonic()
    end = start + duration
    output = Path(a.output)
    try:
        result = run(request, Path(a.input), output, end)
    except BaseException as error:
        failures.hold(error, 'caught')
        owner=failures.hold(error,'worker_action')
        try:
            target = output / 'WORKER_FAILURE.json'
            if not target.exists():
                new_json(target, {'schema': 'neural066_worker_failure_v1', 'status': 'failed', 'type': failures.kind(error), 'message': failures.describe(error)[:2000], 'failure': failures.projection(error), 'read_capture': failures.evidence(error, 'capture_observation', None), 'reference_read_custody': failures.evidence(error, 'reference_read_custody', None), 'action': request.get('action'), 'request_pin': pin(request_raw), 'elapsed_seconds': time.monotonic() - start, 'guest_duration_seconds': duration})
        except BaseException as publication:
            owner.hold(publication,'worker_failure_publication')
            owner.raise_first()
        return 2
    need(time.monotonic() < end, 'Original guest elapsed completion cutoff')
    inventory = files(output, request['limits']['output_bytes'], request['limits']['max_output_files'])
    if request['role'] == 'reference':
        # Incomplete science may complete transport: preserve its exact private
        # diagnostic result instead of replacing it with a transport exception.
        need(type(result) is dict and result.get('schema') == 'neural066_reference_result_v1' and result.get('status') in ('complete', 'incomplete'), 'Typed reference diagnostic/scientific disposition')
        custody = result.get('read_custody')
        need(type(custody) is dict and custody.get('schema') == 'neural066_reference_read_custody_v1' and custody.get('raw_input_exported') is False, 'Source-owned private reference read diagnostics required')
        need(inventory.get('RESULT.json') == pin(encoded(result)), 'Full normal reference result including diagnostics equals the published bytes')
    new_json(output / 'OUTPUTS.json', {'schema': 'osl_transport_output_manifest_v1', 'phase_id': wire['phase_id'], 'request_sha256': hashlib.sha256(wire_raw).hexdigest(), 'files': inventory})
    need(time.monotonic() < end, 'Guest completion publication inside elapsed allowance')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

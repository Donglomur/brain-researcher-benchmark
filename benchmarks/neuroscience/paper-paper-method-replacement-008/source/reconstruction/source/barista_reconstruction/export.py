"""Export one complete masked-channel prediction from supplied predicted tokens.

This joins the actual paper-derived head to the scorer's NPY interface. It does
not produce the missing original H tokens or implement query isolation/training.
"""
from pathlib import Path

from .arrays import write_array
from .io_contract import fresh
from .protocol import requests, validate_panel
from .reconstruction_head import MaskedTokenLayout, project_masked_tokens


def validate_request(panel, request_id, layout, max_output_bytes):
    validate_panel(panel)
    if type(layout) is not MaskedTokenLayout:
        raise ValueError('Exact complete masked-token layout required')
    layout.validate()
    if type(max_output_bytes) is not int or not 0 < max_output_bytes <= 256_000_000:
        raise ValueError('Explicit primitive output cap required')
    matches = [e for e in requests(panel) if e['id'] == request_id]
    if len(matches) != 1:
        raise ValueError('Exact full-panel request identity required')
    e = matches[0]
    session = next(s for s in panel['sessions'] if s['person'] == e['person'])
    if (layout.recording != session['recording'] or layout.channel_id != e['channel_id']
            or len(layout.segment_ids) != e['shape'][0]):
        raise ValueError('Token layout must retain exact recording/channel/full segment count')
    # Native segment identity/order authenticity remains an external missing
    # source obligation; cardinality and distinct string IDs do not establish it.
    if e['shape'][0] * e['shape'][1] * 8 + 4096 > max_output_bytes:
        raise ValueError('Reserve complete float64 output plus bounded NPY header')
    return e


def export_prediction(panel, request_id, tokens, weight, bias, layout, out_path,
                      *, use_bias, max_known_tensor_bytes, max_known_export_bytes,
                      max_output_bytes):
    e = validate_request(panel, request_id, layout, max_output_bytes)
    if (type(max_known_tensor_bytes) is not int or max_known_tensor_bytes <= 0
            or type(max_known_export_bytes) is not int or max_known_export_bytes <= 0):
        raise ValueError('Explicit combined known head/host-export capacity required')
    payload = e['shape'][0] * e['shape'][1] * 8
    if max_known_tensor_bytes + 3 * payload + 4096 > max_known_export_bytes:
        raise ValueError('Combined known head, host-copy and NPY-capture reserve exceeded')
    out = fresh(out_path)
    if Path(out).name != request_id + '.npy':
        raise ValueError('Source-owned per-request prediction filename required')
    waveform = project_masked_tokens(tokens, weight, bias, layout, use_bias=use_bias,
                                    max_known_tensor_bytes=max_known_tensor_bytes)
    # Known host-copy/capture arrays have a separate combined reserve above;
    # genuine native peak, process/device capacity and lifetime remain unqualified.
    value = waveform.detach().cpu().numpy()
    if tuple(value.shape) != tuple(e['shape']):
        raise ValueError('Full source waveform shape required at NPY producer')
    d = write_array(out, value, cap=max_output_bytes)
    return {'id': e['id'], 'values': d}

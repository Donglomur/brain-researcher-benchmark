"""Bridge actual source-amended predictions into the existing complete scorer."""
from pathlib import Path
from .training import predict_channel


def export_channel(panel, request_id, model, session, observed_waveforms,
                   observed_channel_ids, test_segment_ids, target_channel_id,
                   out_path, *, arm, max_output_bytes, max_known_export_bytes):
    from barista_reconstruction.arrays import write_array
    from barista_reconstruction.export import validate_request
    from barista_reconstruction.io_contract import fresh
    from barista_reconstruction.reconstruction_head import MaskedTokenLayout
    import numpy as np
    layout = MaskedTokenLayout(session['recording'], target_channel_id,
                               test_segment_ids, 'predicted_masked', tuple(range(12)))
    request = validate_request(panel, request_id, layout, max_output_bytes)
    if (request['arm'] != arm or request['model'] != model.model_name
            or request['person'] != session['person']):
        raise ValueError('Exact source model/person/arm request required')
    panel_session = next(s for s in panel['sessions'] if s['person'] == session['person'])
    if tuple(panel_session['channel_ids']) != session['channels']:
        raise ValueError('Panel channel order must match the fitted session')
    payload = request['shape'][0] * 6144 * 8
    if type(max_known_export_bytes) is not int or max_known_export_bytes < 3*payload+4096:
        raise ValueError('Reserve output, host batch and NPY capture; native peak separate')
    out = fresh(out_path)
    if Path(out).name != request_id + '.npy':
        raise ValueError('Exact request-owned filename required')
    value = np.empty(tuple(request['shape']), dtype='<f8')
    offset = 0
    for batch in predict_channel(model, session, observed_waveforms,
                                 observed_channel_ids, test_segment_ids,
                                 target_channel_id, arm=arm):
        array = batch.detach().cpu().numpy()
        n = array.shape[0]
        if array.shape != (n, 6144) or offset+n > value.shape[0]:
            raise ValueError('Complete ordered prediction support required')
        value[offset:offset+n] = array
        offset += n
    if offset != value.shape[0]:
        raise ValueError('No incomplete per-channel exports')
    descriptor = write_array(out, value, cap=max_output_bytes)
    return {'id': request_id, 'values': descriptor}

"""Fixed source-pinned packaged helper entry inside the candidate namespace."""
import argparse
import hashlib
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    for name in ('request-bytes', 'output-bytes', 'source-bytes', 'mapping-bytes', 'block-columns',
                 'max-rows', 'max-query-rows', 'max-columns', 'max-matrix-elements', 'max-live-float-slots',
                 'encoding-bytes', 'encoding-nodes', 'encoding-depth', 'encoding-string-chars'):
        parser.add_argument('--' + name, type=int, required=True)
    parser.add_argument('--numeric-sha256', required=True); parser.add_argument('--numeric-bytes', type=int, required=True)
    args = parser.parse_args()
    if any(v <= 0 for k, v in vars(args).items() if isinstance(v, int)):
        raise ValueError('every actual helper extent must be independently selected')
    # /source contains only the exact source closure authenticated/staged by
    # the actual supervisor. Candidate generated files cannot replace it.
    sys.path.insert(0, '/source')
    from n079_common import require, pin, canonical
    from n079_fit_helper import load_numeric, compute
    from n079_generated_worker import write_new
    from collections.abc import Mapping
    import dataclasses
    import numpy as np
    limits = {k: getattr(args, k) for k in ('max_rows', 'max_query_rows', 'max_columns', 'max_matrix_elements', 'max_live_float_slots')}
    encoding = {k: getattr(args, 'encoding_' + k) for k in ('bytes', 'nodes', 'depth', 'string_chars')}
    with open('/request/request.json', 'rb') as stream:
        raw = stream.read(args.request_bytes + 1)
    require(len(raw) <= args.request_bytes, 'bounded exact helper request')
    from ach_resource_common import bounded_decode
    request = bounded_decode(raw, encoding)
    from n079_candidate_helper import configuration
    shared = configuration(request['helper_configuration'])
    require(shared == {'schema':'n079_shared_sandbox_helper_configuration_v1',
        'numeric_pin':{'bytes':args.numeric_bytes,'sha256':args.numeric_sha256},'source_bytes':args.source_bytes,
        'mapping_bytes':args.mapping_bytes,'block_columns':args.block_columns,'limits':limits},
        'actual I tool uses exactly the same numerical source and ceilings exposed to F code')
    numeric = load_numeric('/source/n079_numeric_r1.py', {'bytes': args.numeric_bytes, 'sha256': args.numeric_sha256}, args.source_bytes)
    result = compute(request, numeric, limits, column_block=args.block_columns, mapping_limit=args.mapping_bytes)
    files = []; total = 0; visited = 0
    def pack(value, depth=0):
        nonlocal total, visited
        visited += 1
        require(visited <= encoding['nodes'] and depth <= encoding['depth'], 'complete bounded helper state graph')
        if isinstance(value, np.ndarray):
            require(value.dtype.kind in 'fbiu' and value.size and value.size <= limits['max_matrix_elements'] and
                    3 * value.size <= limits['max_live_float_slots'], 'helper state extent before finite-mask allocation')
            require(np.isfinite(value).all(), 'plain finite actual helper state')
            dtype = value.dtype.newbyteorder('<'); size = value.size * dtype.itemsize
            total += size; require(total <= args.output_bytes, 'full helper state bytes before publication')
            name = 'helper-array-%d.raw' % len(files)
            fd = os.open('/output/' + name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
            first = None; digest = hashlib.sha256(); written = 0
            try:
                iterator = np.nditer(value, flags=['external_loop', 'buffered'], op_flags=['readonly'],
                                     order='C', op_dtypes=[dtype], casting='equiv', buffersize=max(1, 65536 // dtype.itemsize))
                for block in iterator:
                    body = block.tobytes(); digest.update(body); done = 0
                    while done < len(body):
                        n = os.write(fd, body[done:]); require(n > 0, 'complete helper state artifact'); done += n
                    written += len(body)
                require(written == size, 'complete raw helper array'); os.fsync(fd)
            except BaseException as error:
                first = error; raise
            finally:
                try:
                    os.close(fd)
                except BaseException as error:
                    if first is None:
                        raise
                    first.add_note('Secondary helper artifact close: ' + type(error).__name__)
            files.append(name)
            return {'path': name, 'bytes': size, 'sha256': digest.hexdigest(), 'dtype': dtype.str, 'shape': list(value.shape)}
        if dataclasses.is_dataclass(value):
            value = {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
        if isinstance(value, Mapping):
            require(all(type(k) is str for k in value), 'plain helper state keys')
            return {k: pack(v, depth + 1) for k, v in value.items()}
        if type(value) in (list, tuple):
            return [pack(x, depth + 1) for x in value]
        if isinstance(value, np.generic):
            return pack(value.item(), depth + 1)
        require(type(value) in (str, int, float, bool) or value is None, 'plain helper state leaf')
        return value
    metadata = pack(result)
    body = canonical(metadata, encoding); total += len(body); require(total <= args.output_bytes, 'full helper learned state plus metadata')
    write_new('helper-state.json', body); files.append('helper-state.json')
    index = {'schema': 'n079_generated_result_v1', 'phase': request['phase'], 'request_pin': pin(raw),
             'payload': {'state_files': files, 'analysis': {'helper_state': 'helper-state.json',
                 'fit_video_ids': request['helper']['fit_video_ids'], 'predict_video_ids': request['helper']['predict_video_ids'],
                 'feature_outputs': 17, 'no_protected_score': True}}}
    index_body = canonical(index, encoding); total += len(index_body)
    require(total <= args.output_bytes, 'whole helper state and both metadata outputs before final publication')
    write_new('RESULT_INDEX.json', index_body)
    fd = os.open('/output', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    first = None
    try:
        os.fsync(fd)
    except BaseException as error:
        first = error; raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if first is None:
                raise
            first.add_note('Secondary helper directory close: ' + type(error).__name__)


if __name__ == '__main__':
    main()

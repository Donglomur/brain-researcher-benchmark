"""Trusted NEURAL-073 original NIfTI -> complete native-grid corpus bridge.

No download, fit, subprocess, catalogue discovery, or candidate execution.
Authentic conversion is future work; current controls use invented maps only.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import time

import catalogue


class ConversionError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise ConversionError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def keys(value, names, label):
    need(type(value) is dict and set(value) == set(names), 'closed fields: '+label)
    return value


def integer(value, label):
    need(type(value) is int and 0 < value <= 2**53-1, 'positive integer: '+label)
    return value


def relative(value):
    need(type(value) is str and value and not value.startswith('/') and
         all(p not in ('', '.', '..') for p in value.split('/')), 'relative path')
    return value.split('/')


def stamp(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


@contextmanager
def directory(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute directory required')
    fds = [os.open('/', os.O_RDONLY | os.O_DIRECTORY)]
    try:
        for component in path.parts[1:]:
            fds.append(os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                               dir_fd=fds[-1]))
        yield fds[-1]
    finally:
        for fd in reversed(fds):
            os.close(fd)


def read_pinned(root, path, pin, cap):
    """Read the explicit regular original once through non-following descriptors."""
    keys(pin, ('bytes', 'sha256'), 'pin')
    integer(pin['bytes'], 'pin bytes')
    catalogue.require_sha(pin['sha256'])
    need(pin['bytes'] <= cap, 'file cap')
    parts = relative(path)
    with directory(root) as rootfd:
        fds, chain = [], []
        parent = rootfd
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=parent)
                fds.append(child)
                chain.append((parent, part, child, stamp(os.fstat(child))))
                parent = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent)
            fds.append(fd)
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                 before.st_size == pin['bytes'], 'regular single-link exact original')
            chunks, left = [], pin['bytes']
            while left:
                block = os.read(fd, min(left, 65536))
                need(bool(block), 'short original')
                chunks.append(block)
                left -= len(block)
            need(stamp(before) == stamp(os.fstat(fd)) ==
                 stamp(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)),
                 'original changed during read')
            for p, n, child, before_stamp in chain:
                need(before_stamp == stamp(os.fstat(child)) ==
                     stamp(os.stat(n, dir_fd=p, follow_symlinks=False)),
                     'source ancestor changed')
            raw = b''.join(chunks)
            need(sha(raw) == pin['sha256'], 'original hash mismatch')
            return raw
        finally:
            for fd in reversed(fds):
                os.close(fd)


def load_contract():
    raw = Path(__file__).with_name('CONTRACT.json').read_bytes()
    contract = catalogue.strict_json(raw)
    parser = Path(__file__).with_name('catalogue.py').read_bytes()
    need({'bytes': len(parser), 'sha256': sha(parser)} == contract['catalogue_parser'],
         'inherited catalogue parser changed')
    return contract, sha(raw)


def load_catalogue(root, contract):
    bodies = {name: read_pinned(root, name, pin, 1 << 20)
              for name, pin in contract['catalogue_pins'].items()}
    pins = catalogue.strict_json(bodies['PAGE_PINS.json'])
    pages = {entry['path']: bodies['page_%02d.json' % i]
             for i, entry in enumerate(pins['pages'])}
    return catalogue.catalogue_from_pages(pages, bodies['PAGE_PINS.json'],
                                          bodies['SUPPORT.json'])


def unpack_original(raw, cap):
    """Bound gzip expansion before NIfTI parsing; never trust its size trailer."""
    if raw[:2] != b'\x1f\x8b':
        need(len(raw) <= cap, 'uncompressed extent cap')
        return raw, False
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(cap + 1)
    need(len(decoded) <= cap, 'gzip expansion cap')
    return decoded, True


def decode(raw, limits, contract):
    """Preserve voxel coordinates; scaled float64 values flattened in C order."""
    import nibabel as nib
    import numpy as np
    need({'nibabel': nib.__version__, 'numpy': np.__version__} ==
         contract['runtime_versions'], 'exact selected decoder versions required')
    reservation = (2 * len(raw) + 4 * limits['decompressed_file_bytes'] +
                   4 * limits['canonical_file_bytes'] + (32 << 20))
    need(reservation <= limits['max_workspace_bytes'], 'workspace reservation cap')
    expanded, compressed = unpack_original(raw, limits['decompressed_file_bytes'])
    need(len(expanded) >= 4, 'NIfTI header missing')
    size = struct.unpack('<i', expanded[:4])[0]
    if size not in (348, 540):
        size = struct.unpack('>i', expanded[:4])[0]
    need(size in (348, 540), 'only NIfTI-1/2 single-file images supported')
    image_type = nib.Nifti1Image if size == 348 else nib.Nifti2Image
    magic = expanded[344:348] if size == 348 else expanded[4:12]
    need(magic == (b'n+1\0' if size == 348 else b'n+2\0\r\n\x1a\n'),
         'paired/unknown image format refused')
    need(len(expanded) >= size+4, 'complete header and extension marker required')
    # Parse the literal header before Image.from_bytes can normalize it. Even
    # NiBabel's intentionally tolerated zero offset is unsafe for this bridge.
    header = image_type.header_class(binaryblock=expanded[:size], check=False)
    offset = float(header['vox_offset'])
    need(math.isfinite(offset) and offset.is_integer() and offset >= size+4,
         'finite integral single-file payload offset beyond header required')
    offset = int(offset)
    need(offset <= len(expanded), 'payload offset exceeds original extent')
    try:
        header.check_fix(error_level=1)
    except nib.spatialimages.HeaderDataError as error:
        raise ConversionError('invalid literal NIfTI header; repair refused') from error
    need(header.binaryblock == expanded[:size], 'header repair or normalization refused')
    hshape = tuple(int(v) for v in header.get_data_shape())
    need(len(hshape) == 3 and min(hshape) >= 4 and math.prod(hshape) >= 256,
         'full three-dimensional map required; no squeeze or crop')
    hdtype = header.get_data_dtype()
    need(hdtype.kind in ('i', 'u', 'f') and hdtype.itemsize <= 8,
         'only real scalar integer/float voxels supported')
    need(offset + math.prod(hshape)*hdtype.itemsize <= len(expanded),
         'complete literal voxel payload extent required')
    marker = expanded[size:size+4]
    need(marker[1:] == b'\0\0\0', 'reserved extension marker bytes must be zero')
    if marker[0]:
        need(offset > size+4, 'extension marker requires an extension record')
        position = size+4
        while position < offset:
            need(position+8 <= offset, 'incomplete NIfTI extension record')
            extension_size = struct.unpack_from(header.endianness+'i', expanded, position)[0]
            need(extension_size >= 16 and extension_size % 16 == 0 and
                 position+extension_size <= offset, 'invalid NIfTI extension extent')
            position += extension_size
        need(position == offset, 'extension records must end at voxel payload')
    image = image_type.from_bytes(expanded)
    shape = tuple(int(v) for v in image.shape)
    need(len(shape) == 3 and min(shape) >= 4 and math.prod(shape) >= 256,
         'full three-dimensional map required; no squeeze or crop')
    canonical_bytes = 8 * math.prod(shape)
    need(canonical_bytes <= limits['canonical_file_bytes'], 'canonical extent cap')
    # Conservative logical reservation; a qualified external host must enforce RSS.
    dtype = image.get_data_dtype()
    need(dtype.kind in ('i', 'u', 'f') and dtype.itemsize <= 8,
         'only real scalar integer/float voxels supported')
    units = image.header.get_xyzt_units()[0]
    need(units in ('unknown', 'meter', 'mm', 'micron'), 'recognized spatial unit code required')
    sform, scode = image.get_sform(coded=True)
    qform, qcode = image.get_qform(coded=True)
    need(int(scode) > 0 or int(qcode) > 0, 'coded spatial transform required')
    chosen = sform if int(scode) > 0 else qform
    need(np.isfinite(chosen).all() and np.array_equal(chosen, image.affine),
         'finite documented selected affine required')
    need(np.array_equal(chosen[3], [0, 0, 0, 1]) and
         math.isfinite(float(np.linalg.det(chosen[:3, :3]))) and
         float(np.linalg.det(chosen[:3, :3])) != 0, 'nonsingular affine required')
    orientation = list(nib.aff2axcodes(chosen))
    need(None not in orientation and len(set(orientation)) == 3, 'orientation must be resolvable')
    values = image.get_fdata(dtype=np.float64, caching='unchanged')
    need(values.shape == shape and np.isfinite(values).all(), 'finite complete scaled map required')
    canonical = values.astype('<f8', order='C', copy=False).tobytes(order='C')
    need(len(canonical) == canonical_bytes, 'canonical extent mismatch')
    geometry = {'shape': list(shape), 'affine': chosen.reshape(-1).tolist(),
                'orientation': orientation}
    evidence = {'format': 'NIfTI-%d' % (1 if size == 348 else 2),
                'gzip': compressed, 'expanded_bytes': len(expanded),
                'stored_dtype': dtype.str, 'sform_code': int(scode), 'qform_code': int(qcode),
                'sform': None if sform is None else sform.reshape(-1).tolist(),
                'qform': None if qform is None else qform.reshape(-1).tolist(),
                'spatial_units': units, 'unit_conversion_performed': False,
                'selected_affine': 'sform' if int(scode) > 0 else 'qform',
                'slope': float(image.dataobj.slope), 'intercept': float(image.dataobj.inter),
                'geometry': geometry, 'canonical_bytes': len(canonical),
                'canonical_sha256': sha(canonical), 'workspace_reserved_bytes': reservation,
                'independent_fidelity_qualification': False}
    return canonical, geometry, evidence


LIMIT_NAMES = ('original_file_bytes', 'decompressed_file_bytes', 'canonical_file_bytes',
               'total_original_bytes', 'total_canonical_bytes', 'metadata_output_bytes',
               'max_workspace_bytes', 'whole_seconds')
ROW_NAMES = ('record_id', 'path', 'original', 'source_version',
             'source_locator_digest', 'rights_evidence_digest')


def validate_plan(document, cat):
    keys(document, ('schema', 'domain', 'catalogue_digest', 'limits', 'records'), 'input plan')
    need(document['schema'] == 'n073_original_conversion_plan_v1' and
         document['domain'] == cat.domain and document['catalogue_digest'] == cat.fingerprint,
         'exact catalogue/domain binding')
    limits = keys(document['limits'], LIMIT_NAMES, 'limits')
    for k, v in limits.items():
        integer(v, k)
    rows = document['records']
    need(type(rows) is list and len(rows) == len(cat.records), 'complete original roster required')
    ids, total, expected = set(), 0, set(cat.by_id)
    for row in rows:
        keys(row, ROW_NAMES, 'original row')
        rid = row['record_id']
        need(type(rid) is str and rid in expected and rid not in ids, 'unique known original ID')
        ids.add(rid)
        relative(row['path'])
        pin = keys(row['original'], ('bytes', 'sha256'), 'original pin')
        need(integer(pin['bytes'], 'original bytes') <= limits['original_file_bytes'], 'original file cap')
        reservation = (2*pin['bytes'] + 4*limits['decompressed_file_bytes'] +
                       4*limits['canonical_file_bytes'] + (32 << 20))
        need(reservation <= limits['max_workspace_bytes'],
             'whole original roster workspace admission before any signal read')
        catalogue.require_sha(pin['sha256'])
        catalogue.require_sha(row['source_locator_digest'])
        catalogue.require_sha(row['rights_evidence_digest'])
        need(type(row['source_version']) is str and row['source_version'], 'source version required')
        total += pin['bytes']
    need(ids == expected and total <= limits['total_original_bytes'], 'full roster/read budget')
    need(len(rows) * limits['canonical_file_bytes'] <= limits['total_canonical_bytes'],
         'reserve the full canonical output before any original read')
    need(len(rows) * 8192 + (1 << 20) <= limits['metadata_output_bytes'],
         'reserve complete inventory and evidence metadata')
    return rows, limits


def _write(fd, name, raw):
    need('/' not in name and name not in ('.', '..'), 'single output component')
    out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(out, view)
            need(n > 0, 'short output write')
            view = view[n:]
        os.fsync(out)
    finally:
        os.close(out)


def convert_catalogue(cat, document, original_root, output, contract, contract_sha):
    """One fresh destination, every record, inventory published only on completion.

    The CLI only issues the full authentic catalogue. Tests may explicitly pass
    a factory-issued invented catalogue; domains are never promoted.
    """
    cat.require_valid()
    rows, limits = validate_plan(document, cat)
    output = Path(output)
    need(output.is_absolute(), 'absolute new output required')
    started, inventory, last, total_out = time.monotonic(), [], None, 0
    metadata_out = 0
    geometry, spatial_units = None, None
    with directory(output.parent) as parent:
        os.mkdir(output.name, mode=0o700, dir_fd=parent)
        outfd = os.open(output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            os.mkdir('canonical', mode=0o700, dir_fd=outfd)
            os.mkdir('conversion', mode=0o700, dir_fd=outfd)
            canonicalfd = os.open('canonical', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=outfd)
            try:
                evidencefd = os.open('conversion', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=outfd)
                try:
                    for row in rows:
                        need(time.monotonic() - started < limits['whole_seconds'], 'conversion deadline')
                        last = row['record_id']
                        raw = read_pinned(original_root, row['path'], row['original'], limits['original_file_bytes'])
                        canonical, observed, evidence = decode(raw, limits, contract)
                        need(geometry is None or geometry == observed, 'heterogeneous native grids; design revision required')
                        need(spatial_units is None or spatial_units == evidence['spatial_units'],
                             'heterogeneous native spatial units; design revision required')
                        geometry = observed
                        spatial_units = evidence['spatial_units']
                        evidence.update(record_id=last, domain=cat.domain,
                                        original_sha256=row['original']['sha256'],
                                        original_bytes=len(raw), decoder_contract_digest=contract_sha)
                        eraw = catalogue.canonical_json(evidence)
                        metadata_out += len(eraw)
                        need(metadata_out <= limits['metadata_output_bytes'], 'metadata output cap')
                        name = sha(last.encode('utf-8'))
                        _write(evidencefd, name+'.json', eraw)
                        _write(canonicalfd, name+'.f64', canonical)
                        total_out += len(canonical)
                        need(total_out <= limits['total_canonical_bytes'], 'total canonical output cap')
                        receipt = {'record_id': last, 'domain': cat.domain,
                                   'original_sha256': row['original']['sha256'], 'original_bytes': len(raw),
                                   'source_version': row['source_version'],
                                   'source_locator_digest': row['source_locator_digest'],
                                   'rights_evidence_digest': row['rights_evidence_digest'],
                                   'decoder_contract_digest': contract_sha, 'conversion_evidence_digest': sha(eraw)}
                        inventory.append({'record_id': last, 'original_receipt': receipt,
                                          'canonical': {'path': 'canonical/'+name+'.f64',
                                                        'bytes': len(canonical), 'sha256': sha(canonical)}})
                        del raw, canonical
                finally:
                    os.close(evidencefd)
            finally:
                os.close(canonicalfd)
            result = {'schema': 'n073_canonical_inventory_v1', 'records': inventory}
            iraw = catalogue.canonical_json(result)
            summary = {'schema': 'n073_conversion_result_v1', 'domain': cat.domain,
                       'catalogue_digest': cat.fingerprint, 'geometry': geometry,
                       'spatial_units': spatial_units, 'unit_conversion_performed': False,
                       'records': len(inventory), 'canonical_bytes': total_out,
                       'inventory': {'bytes': len(iraw), 'sha256': sha(iraw)},
                       'independent_fidelity_rights_identity_qualification': False,
                       'deployment_enabled': False}
            sraw = catalogue.canonical_json(summary)
            need(metadata_out + len(iraw) + len(sraw) <= limits['metadata_output_bytes'], 'final metadata cap')
            need(time.monotonic() - started < limits['whole_seconds'], 'conversion deadline')
            _write(outfd, 'RESULT.json', sraw)
            _write(outfd, 'INVENTORY.pending.json', iraw)
            # Pre-publication fsync/close failures preserve only the staged body.
            # Rename commits the inventory; later directory-close/report errors
            # cannot roll it back. Directory crash durability is not established.
            os.rename('INVENTORY.pending.json', 'INVENTORY.json', src_dir_fd=outfd, dst_dir_fd=outfd)
            return summary
        except BaseException as exc:
            # Failure preserves completed artifacts; it is never an inventory.
            _write(outfd, 'FAILURE.json', catalogue.canonical_json({
                'schema': 'n073_conversion_failure_v1', 'domain': cat.domain,
                'last_record_id': last, 'completed_records': len(inventory),
                'error_type': type(exc).__name__, 'complete_inventory': False}))
            raise
        finally:
            os.close(outfd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue-dir', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--plan-bytes', type=int, required=True)
    parser.add_argument('--original-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    contract, contract_sha = load_contract()
    cat = load_catalogue(args.catalogue_dir, contract)
    raw = read_pinned(args.plan.parent, args.plan.name,
                      {'bytes': args.plan_bytes, 'sha256': args.plan_sha256}, 32 << 20)
    result = convert_catalogue(cat, catalogue.strict_json(raw), args.original_root,
                               args.output, contract, contract_sha)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()

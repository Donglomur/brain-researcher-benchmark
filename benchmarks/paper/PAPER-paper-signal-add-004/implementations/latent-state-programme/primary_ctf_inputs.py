"""Original CTF input preparation for the current two-branch paper objective.

This does not fit a model or replace the separate complete six-branch build.
Only ``build`` authenticates the fixed released ZIP before projecting inputs.
"""
import io
import zipfile
from pathlib import Path

from core import TASK, encoded, identity, need, people
from safe_io import capture, durable_new, strict, write_array
from source_inputs import CTF_BYTES, CTF_SHA, ctf_demographics, numeric_original

DIRECTORY_BYTES = 29616
DIRECTORY_SHA = '1aa249aeca60fe36f9b9021d24f6c9e515339349ac3fdfc944224204f3f9e020'
PRIMARY_BRANCHES = ('ctf_tde', 'ctf_dynemo')


def _members():
    return ({f'{family}/{person}.npy' for family in ('bursts', 'networks')
             for person in people('ctf_tde')} | {'demographics.csv', 'bursts/', 'networks/'})


def _directory(rows):
    """Validate the complete released directory without first collapsing names."""
    need(type(rows) is list and len(rows) == 133, 'All133 original directory entries')
    need(all(type(row) is dict and type(row.get('member')) is str for row in rows),
         'Explicit original member names')
    names = [row['member'] for row in rows]
    need(len(set(names)) == len(names) and set(names) == _members(),
         'Exact unique65 network+65 burst+demographic+two-directory support')
    for row in rows:
        need(all(type(row.get(k)) is int and row[k] >= 0 for k in
                 ('bytes', 'compressed_bytes', 'local_header_offset', 'compression', 'flags')),
             'Original nonnegative integer ZIP metadata')
        need(type(row.get('crc32')) is str and len(row['crc32']) == 8 and
             all(c in '0123456789abcdef' for c in row['crc32']), 'Original CRC32')
        need(not row['flags'] & 1, 'No encrypted member')
    return {row['member']: row for row in rows}


def _project(archive_body, directory, save, save_array, array_cap, read_charge):
    """Internal projection, after build's immutable source-identity gate.

    Generated tests exercise this helper without claiming source authentication.
    All133 metadata entries are checked; only the66 primary member bodies are
    decompressed. Bursts remain in the authenticated ZIP and are not decoded.
    """
    import numpy as np
    entries = _directory(directory)
    roster = people('ctf_tde')
    native, regional = {}, []
    with zipfile.ZipFile(io.BytesIO(archive_body)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        need(names == [row['member'] for row in directory] and len(set(names)) == 133,
             'Exact original archive directory order, without duplicates')
        for info in infos:
            row = entries[info.filename]
            need((info.file_size, info.compress_size, info.header_offset, info.compress_type,
                  info.flag_bits, info.CRC) ==
                 (row['bytes'], row['compressed_bytes'], row['local_header_offset'],
                  row['compression'], row['flags'], int(row['crc32'], 16)),
                 'Complete source ZIP metadata parity')

        def member(name):
            read_charge(entries[name]['bytes'])
            body = archive.read(name)  # zipfile also verifies CRC.
            need(len(body) == entries[name]['bytes'], 'Full original member extent')
            return body

        raw_demographics = member('demographics.csv')
        ages = ctf_demographics(raw_demographics)
        native['ctf/demographics.csv'] = save('ctf/demographics.csv', raw_demographics)
        for person in roster:
            member_name = f'networks/{person}.npy'
            raw = member(member_name)
            # Bound materialized float64 output BEFORE numeric_original allocates.
            import ast
            need(len(raw) >= 12 and raw[:6] == b'\x93NUMPY' and
                 raw[6:8] in (b'\x01\x00', b'\x02\x00'), 'Original NPY1/2 network member')
            start = 10 if raw[6] == 1 else 12
            size = int.from_bytes(raw[8:start], 'little')
            need(0 < size <= 65536 and start + size <= len(raw), 'Bounded original header')
            header = ast.literal_eval(raw[start:start + size].decode('latin1'))
            shape = header.get('shape') if type(header) is dict else None
            need(type(shape) is tuple and len(shape) == 2 and
                 all(type(n) is int and n > 0 for n in shape) and shape[1] == 38,
                 'All38 source parcels and complete positive time extent')
            need(shape[0] * 38 * 8 <= array_cap and shape[0] * 8 <= array_cap,
                 'Explicit per-array allocation before materialization')
            values = numeric_original(raw)
            native_name = 'ctf/' + member_name
            native[native_name] = save(native_name, raw)
            regional.append({
                'person': person, 'run': 1,
                'observations': save_array(f'regional/ctf_networks/{person}.npy', values),
                'physical_rows': save_array(f'physical_rows/ctf_networks/{person}.npy',
                                            np.arange(len(values), dtype='<i8')),
                'original': {'path': native_name, **native[native_name]},
            })
    return native, regional, ages


def build(spec, output, limits):
    """Future operator preparation of the exact65-person primary inputs.

    No Elekta operand is accepted. Output uses a distinct primary-input schema;
    it is not an ``osl_complete_originals_v1`` six-branch completion receipt.
    The caller must separately admit storage/RAM, original source rights and
    execution. This function neither executes original models nor qualifies a
    reference, historical fit criterion or paper improvement.
    """
    need(type(spec) is dict and set(spec) == {'ctf_archive', 'ctf_directory'},
         'Only the two exact CTF source operands; no extra/different cohort')
    need(type(limits) is dict and set(limits) == {'read_bytes', 'write_bytes', 'array_bytes'}
         and all(type(v) is int and v > 0 for v in limits.values()), 'Explicit input/output/array limits')
    expected = {'ctf_archive': {'bytes': CTF_BYTES, 'sha256': CTF_SHA},
                'ctf_directory': {'bytes': DIRECTORY_BYTES, 'sha256': DIRECTORY_SHA}}
    for name, descriptor in expected.items():
        record = spec[name]
        need(type(record) is dict and set(record) == {'path', 'bytes', 'sha256'} and
             {k: record[k] for k in ('bytes', 'sha256')} == descriptor,
             'Exact fixed original CTF identity, not a candidate-provided replacement')
    used = {'read': 0, 'write': 0}

    def read_charge(size):
        need(type(size) is int and size >= 0, 'Nonnegative logical source read')
        used['read'] += size
        need(used['read'] <= limits['read_bytes'], 'Complete primary-input read allocation')

    def read(name):
        record = spec[name]
        read_charge(record['bytes'])
        return capture(record['path'], record['bytes'], expected[name])

    directory = strict(read('ctf_directory'))['members']
    _directory(directory)
    archive_body = read('ctf_archive')
    root = Path(output)
    need(not root.exists() and not root.is_symlink(), 'Fresh primary-CTF output root')
    root.mkdir(mode=0o700, parents=True)

    def save(name, raw):
        used['write'] += len(raw)
        need(used['write'] <= limits['write_bytes'], 'Primary input output allocation')
        path = root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return durable_new(path, raw)

    def save_array(name, values):
        path = root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        record = write_array(path, values, min(limits['array_bytes'], limits['write_bytes'] - used['write']))
        used['write'] += record['bytes']
        record['path'] = name
        return record

    native, regional, ages = _project(archive_body, directory, save, save_array,
                                     limits['array_bytes'], read_charge)
    del archive_body
    lineage = identity({'ctf_archive': expected['ctf_archive'],
                        'ctf_directory': expected['ctf_directory'], 'native': native})
    packet = {'schema': 'osl_original_regional_packet_v1', 'task_id': TASK, 'branch': 'ctf_tde',
              'sampling_frequency': 250, 'channels': 38,
              'original_preparation_binding': lineage, 'runs': regional}
    packets = {'ctf_tde': {'path': 'packets/ctf_tde.json',
                           **save('packets/ctf_tde.json', encoded(packet)), 'identity': identity(packet)}}
    age_record = {'path': 'AGES.json', **save('AGES.json', encoded(ages)), 'identity': identity(ages)}
    result = {'schema': 'osl_primary_ctf_originals_v1', 'task_id': TASK,
              'primary_branches': list(PRIMARY_BRANCHES), 'ctf_people': 65,
              'native_files': native, 'packets': packets, 'ages': age_record, 'lineage': lineage,
              'full_source_archive_identity': expected['ctf_archive'],
              'full_archive_entries_checked': 133, 'member_bodies_decoded': 66,
              'excluded_from_this_primary_projection': ['ctf_bursts', 'ctf_static', 'elekta_ae', 'elekta_tde'],
              'native_arrays_for_both_primary_branches': 'ctf/networks/subject00..subject64.npy',
              'literal_source_member_bytes_preserved': True,
              'model_preprocessing_or_fit_executed': False,
              'historical_fit_selection_or_scientific_qualification': False,
              'six_branch_completion': False,
              'logical_IO_before_completion_record': used.copy()}
    completion = save('PRIMARY_CTF_INPUTS.json', encoded(result))
    return {'inputs': result, 'completion': completion, 'logical_IO': used.copy()}

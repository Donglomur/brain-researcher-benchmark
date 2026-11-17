"""Concrete complete306-object preparation. No acquisition or implicit selection.

This command is gated by an independently supplied operator preparation grant.
It reads original scientific bodies only when explicitly invoked in a separately
qualified environment. Construction does not invoke it.
"""
import argparse
import hashlib
import os
from pathlib import Path
import time
import uuid
from .common import capture, decode, encoded, need, ordinary, pin, publish, stream_pin, Meter, descriptor, DecodingStream
from .packet import roster
from .edf import header, psg_geometry, annotations, channel_chunks
from .science import full_clock_labels


def file_pin(path, cap):
    path, st = ordinary(path); need(st.st_size <= cap, 'Prepared extent within selected reservation')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            block = handle.read(65536)
            if not block:
                break
            digest.update(block)
    return {'path': str(path), 'bytes': st.st_size, 'sha256': digest.hexdigest()}


def prepare(grant, roster_bytes, folds_bytes, source_root, output, source_pin):
    import numpy as np
    need(type(grant) is dict and set(grant) == {'schema', 'authorized', 'source', 'roster', 'folds', 'source_root', 'output', 'clock', 'limits', 'boundary_review', 'qualified_dependency_roots'}, 'Exact external preparation grant')
    need(grant['schema'] == 'neural007_preparation_grant_v1' and grant['authorized'] is True, 'Explicit separate authentic preparation authority')
    need(grant['source'] == source_pin and grant['roster'] == pin(roster_bytes) and grant['folds'] == pin(folds_bytes), 'Exact prepared source/scope binding')
    descriptor(grant['boundary_review'])
    source_root, output = Path(source_root), Path(output)
    need(str(source_root) == grant['source_root'] and str(output) == grant['output'] and source_root.is_absolute() and output.is_absolute(), 'Exact original/new output paths')
    need(source_root.is_dir() and not output.exists() and not output.is_relative_to(source_root) and not source_root.is_relative_to(output), 'Disjoint fresh preparation root')
    need(not any(p.is_symlink() for p in (source_root, output.parent, *source_root.parents, *output.parents)), 'Ordinary source/output ancestors')
    limits = grant['limits']
    need(set(limits) == {'read_bytes', 'write_bytes', 'retained_bytes', 'annotation_bytes_per_file', 'free_floor_bytes'}, 'Full preparation I/O/storage caps')
    need(all(type(v) is int and v > 0 for v in limits.values()), 'Positive prospective preparation bounds')
    meter = Meter(limits['read_bytes'], limits['write_bytes'], grant['clock']['origin'], grant['clock']['deadline'])
    rows, _ = roster(roster_bytes, folds_bytes)
    # Complete presence/header census precedes output creation. No candidate is
    # launched, and no scientifically favorable subset may replace a failure.
    originals, plans, total_epochs = [], [], 0
    for row in rows:
        meter.tick(); assets = {}
        for a in row['source_assets']:
            path = source_root / a['filename']; path, st = ordinary(path)
            expected = {'bytes': st.st_size, 'sha256': a['publisher_sha256']}
            stream_pin(path, expected, meter)
            meter.read(min(st.st_size, 256 * 65))
            with path.open('rb') as f:
                h = header(f, st.st_size)
            assets[a['kind']] = (path, h)
            originals.append({'filename': a['filename'], 'path': str(path), **expected})
        need(assets['PSG'][1]['start'] == assets['Hypnogram'][1]['start'], 'PSG/hypnogram original clocks match exactly')
        indexes, epochs, tail = psg_geometry(assets['PSG'][1]); total_epochs += epochs
        plans.append((row, assets, indexes, epochs, tail))
    # Exact numerical extents plus generous finite metadata/header allowance,
    # not a performance estimate. A too-small allocation refuses all153.
    numerical = total_epochs * (72000 + 32 + 2)
    # Dispositions scale with every epoch; file headers, full absolute index
    # paths and both final metadata bodies are reserved before any output.
    reserve = (numerical + total_epochs * 40 + 153 * (6 * 4096 + 8192)
               + len(encoded(originals)) + 153 * (4096 + 8 * len(str(output).encode())) + 4 * 1024 * 1024)
    need(reserve <= limits['retained_bytes'] and reserve <= limits['write_bytes'], 'Selected full-cohort retained/write reservation')
    disk = os.statvfs(output.parent)
    need(disk.f_bavail * disk.f_frsize >= reserve + limits['free_floor_bytes'], 'Full prospective source projection capacity')
    output.mkdir(mode=0o700)
    parent_fd = os.open(output.parent, os.O_RDONLY)
    try: os.fsync(parent_fd)
    finally: os.close(parent_fd)
    (output / 'public_channels').mkdir(); (output / 'private').mkdir(mode=0o700)
    prepared, written = [], 0
    retained_reserved = 0
    def retain(n):
        nonlocal retained_reserved
        need(type(n) is int and n >= 0 and retained_reserved + n <= limits['retained_bytes'], 'Prospective retained reservation before creation')
        retained_reserved += n
    started = time.monotonic()
    try:
        for row, assets, indexes, epochs, tail in plans:
            meter.tick(); opaque = uuid.uuid4().hex
            public = output / 'public_channels' / opaque; private = output / 'private' / opaque
            public.mkdir(mode=0o700); private.mkdir(mode=0o700)
            channel_paths = [public / ('channel-' + str(c) + '.npy') for c in range(3)]
            mappings = []
            try:
                for path in channel_paths:
                    retain(epochs * 3000 * 8 + 4096); meter.write(epochs * 3000 * 8 + 4096)
                    mappings.append(np.lib.format.open_memmap(path, mode='w+', dtype='<f8', shape=(epochs * 3000,)))
                path, h = assets['PSG']
                expected = next({k: a[k] for k in ('bytes','sha256')} for a in originals if a['path'] == str(path))
                with DecodingStream(path, expected, meter) as handle:
                    need(header(handle, expected['bytes']) == h, 'Decoded source header matches admitted census')
                    for offset, values in channel_chunks(handle, h, indexes, epochs * 3000):
                        meter.tick()
                        for target, data in zip(mappings, values):
                            target[offset:offset + len(data)] = data
                for mapped in mappings:
                    mapped.flush()
            finally:
                for mapped in mappings:
                    mapped._mmap.close()
            starts = np.arange(epochs, dtype=np.float64) * 30
            angles = 2 * np.pi * (starts + assets['PSG'][1]['clock_seconds']) / 86400
            clock = np.column_stack((starts, starts / 3600, np.sin(angles), np.cos(angles)))
            clock_path = public / 'clock.npy'; retain(clock.nbytes + 4096); meter.write(clock.nbytes + 4096)
            with clock_path.open('xb') as f:
                np.save(f, clock, allow_pickle=False)
            path, h = assets['Hypnogram']
            expected = next({k: a[k] for k in ('bytes','sha256')} for a in originals if a['path'] == str(path))
            with DecodingStream(path, expected, meter) as handle:
                need(header(handle, expected['bytes']) == h, 'Decoded hypnogram header matches admitted census')
                events = annotations(handle, h, limits['annotation_bytes_per_file'])
            stage, disposition = full_clock_labels(epochs, events)
            stage_array = np.asarray(stage, dtype=np.int8); mask = stage_array >= 0
            stage_path, mask_path = private / 'stages.npy', private / 'mask.npy'
            for path, array in ((stage_path, stage_array), (mask_path, mask)):
                retain(array.nbytes + 4096); meter.write(array.nbytes + 4096)
                with path.open('xb') as f:
                    np.save(f, array, allow_pickle=False)
            disposition_path = private / 'disposition.json'
            disposition_body = encoded({'schema': 'neural007_epoch_dispositions_v1', 'epochs': epochs,
                                        'terminal_signal_samples_preserved_in_original': tail, 'epoch_disposition': disposition,
                                        'source_start_clock_matched': True, 'no_sleep_label_crop': True})
            retain(len(disposition_body)); publish(disposition_path, disposition_body, meter)
            paths = channel_paths + [clock_path, stage_path, mask_path, disposition_path]
            locks = {}
            for path in paths:
                with path.open('rb') as durable_file: os.fsync(durable_file.fileno())
                meter.read(path.stat().st_size + 1)
                locks[path.name] = file_pin(path, limits['retained_bytes'])
                path.chmod(0o444); written += path.stat().st_size
            need(written <= limits['retained_bytes'], 'Complete measured retained-byte ceiling')
            prepared.append({'official_subject': row['official_subject'], 'official_night': row['official_night'],
                             'opaque_night': opaque, 'epochs': epochs,
                             'channels': {str(c): locks['channel-' + str(c) + '.npy'] for c in range(3)},
                             'clock': locks['clock.npy'], 'stages': locks['stages.npy'], 'mask': locks['mask.npy'],
                             'disposition': locks['disposition.json']})
            public.chmod(0o555); private.chmod(0o500)
            for directory in (public, private, output / 'public_channels', output / 'private'):
                dfd = os.open(directory, os.O_RDONLY)
                try: os.fsync(dfd)
                finally: os.close(dfd)
        receipt = {'schema': 'neural007_full153_preparation_receipt_v1', 'source': source_pin, 'roster': pin(roster_bytes),
                   'people': 78, 'nights': 153, 'objects': 306, 'epochs': total_epochs, 'numerical_bytes': numerical,
                   'retained_member_bytes': written, 'logical_accounting': meter.report(), 'wall_seconds': time.monotonic() - started,
                   'payload_prepared': True, 'independent_numeric_parity_admitted': False, 'runtime_or_science_qualified': False}
        receipt_body = encoded(receipt); retain(len(receipt_body))
        receipt_pin = publish(output / 'PREPARATION.json', receipt_body, meter)
        index = {'schema': 'neural007_full153_input_v1', 'roster': pin(roster_bytes), 'originals': originals,
                 'nights': prepared, 'preparation_source': source_pin, 'preparation_receipt': receipt_pin}
        index_body = encoded(index); retain(len(index_body))
        index_pin = publish(output / 'INPUT_INDEX.json', index_body, meter)
        meter.tick()
        return {'index': index_pin, 'receipt': receipt_pin, 'status': 'complete_preparation_independent_admission_pending',
                'accounting': meter.report(), 'retained_reserved_bytes': retained_reserved,
                'retained_complete_bytes': written + len(receipt_body) + len(index_body), 'scientific_qualification': False}
    except BaseException as exc:
        # Preserve existing partials. Failure metadata publication is bounded by
        # the original remaining grant; its failure never erases the first error.
        try:
            failure_body = encoded({'status': 'incomplete', 'error_type': type(exc).__name__,
                    'prepared_nights': len(prepared), 'retained_member_bytes': written, 'accounting': meter.report()})
            retain(len(failure_body)); publish(output / 'FAILED.json', failure_body, meter)
        except BaseException:
            pass
        raise

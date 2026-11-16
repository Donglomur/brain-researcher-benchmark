"""Verify archives and every RECORD entry without importing wheel code."""
import base64
import csv
import hashlib
import io
from pathlib import Path, PurePosixPath
import stat
import zipfile

UNPACKED_CAP = 850000000  # Leave space inside the 1 GiB overlay for pip/cache metadata.


def require(value, message):
    if not value:
        raise ValueError(message)


def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def verify_wheel(path, expected, model_specs=()):
    require(path.is_file() and not path.is_symlink(), 'regular wheel required')
    require(path.stat().st_size == expected['bytes'] and sha_file(path) == expected['sha256'], 'wheel SHA-256/length')
    models = []
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(len(entries) <= 30000 and len(names) == len(set(names)), 'archive entry count/duplicates')
        for entry in entries:
            parts = PurePosixPath(entry.filename)
            require(not parts.is_absolute() and '..' not in parts.parts and '\\' not in entry.filename and entry.filename != '', 'archive traversal')
            require(str(parts) == entry.filename.rstrip('/'), 'noncanonical archive path')
            require(not stat.S_ISLNK(entry.external_attr >> 16) and not entry.flag_bits & 1, 'archive link/encryption')
            require(0 <= entry.file_size <= 500000000, 'archive member bound')
        files = {entry.filename: entry for entry in entries if not entry.is_dir()}
        unpacked = sum(entry.file_size for entry in entries)
        require(unpacked <= UNPACKED_CAP, 'single archive uncompressed bound')
        records = [name for name in files if name.endswith('.dist-info/RECORD') and len(PurePosixPath(name).parts) == 2]
        require(len(records) == 1 and files[records[0]].file_size <= 16000000, 'exact one bounded wheel RECORD')
        record_name = records[0]
        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode('utf-8'))))
        require(len(rows) == len(files), 'every archive file must appear in RECORD')
        seen = set()
        for row in rows:
            require(len(row) == 3, 'RECORD field count')
            name, encoded_hash, encoded_size = row
            require(name in files and name not in seen, 'RECORD exact unique path')
            seen.add(name)
            if name == record_name:
                require(encoded_hash == encoded_size == '', 'RECORD self entry')
                continue
            require(encoded_size.isascii() and encoded_size.isdigit() and int(encoded_size) == files[name].file_size, 'RECORD member size')
            require(encoded_hash.startswith('sha256='), 'explicit SHA-256 RECORD algorithm')
            h = hashlib.sha256()
            count = 0
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1048576), b''):
                    count += len(block)
                    require(count <= files[name].file_size, 'expanded member overlength')
                    h.update(block)
            actual = base64.urlsafe_b64encode(h.digest()).decode().rstrip('=')
            require(count == files[name].file_size and encoded_hash == 'sha256=' + actual, 'RECORD hash mismatch')
        for spec in model_specs:
            name = spec['wheel_relative_path']
            require(name in files and files[name].file_size == spec['bytes'], 'explicit model length')
            body = archive.read(name)
            git_digest = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
            require(git_digest == spec['git_blob_sha1'], 'historic model Git blob mismatch')
            models.append({'variant': spec['variant'], 'path': name, 'bytes': len(body),
                           'git_blob_sha1': git_digest, 'sha256': hashlib.sha256(body).hexdigest()})
    return {'filename': path.name, 'bytes': path.stat().st_size, 'sha256': expected['sha256'],
            'record_entries_verified': len(files), 'uncompressed_bytes': unpacked, 'models': models}


def verify_all(manifest, provenance, cached_reader, wheels=Path('/wheels'), reader=Path('/reader/reader.whl')):
    require(len(manifest['downloads']) == 28, 'exact package count')
    require({p.name for p in wheels.iterdir()} == {row['filename'] for row in manifest['downloads']}, 'wheel directory exact inventory')
    reports = []
    total = 0
    for row in manifest['downloads']:
        specs = provenance['weights'] if row['name'] == 'yasa' else ()
        report = verify_wheel(wheels / row['filename'], row, specs)
        reports.append(report)
        total += report['uncompressed_bytes']
        require(total <= UNPACKED_CAP, 'aggregate archive expansion cap')
    report = verify_wheel(reader, cached_reader)
    total += report['uncompressed_bytes']
    require(total <= UNPACKED_CAP, 'aggregate expansion including cached reader')
    require(sum(len(row['models']) for row in reports) == 2, 'exact two selected models checked')
    return {'status': 'all_archives_and_RECORD_entries_verified_before_install_or_joblib',
            'new_wheel_count': 28, 'new_wheel_bytes': sum(r['bytes'] for r in reports),
            'uncompressed_bytes_including_cached_reader': total, 'uncompressed_cap_bytes': UNPACKED_CAP,
            'wheels': reports, 'cached_reader': report, 'joblib_loads_so_far': 0}

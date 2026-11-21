"""Operator-only CHB-MIT original-file admission; no EEG decoding or model calls."""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

ROOT = Path(__file__).resolve().parent
EVENTS = ROOT.parent / 'seizure-events-v1'
EVENTS_CLI_SHA256 = '3b5ca6fe922a5f674a0598cd6912bae62ca139524466c42f5603c5684ae77dca'
EVENTS_MANIFEST_SHA256 = '6e97b56bd2043184f53e9e9be13317ce312bae10ee213dfdd54edaeb5b32fb62'
CHECKSUMS_SHA256 = 'f1698efeb9fef887e55cedf6eda13386d9a888db663aec48b2aa194b7b753d2b'
RECORDS_SHA256 = '72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08'
POSITIVE_LIST_SHA256 = 'eadf7ef26246132b8708c2b4571e05cc0112d791e6b4eba2718bba0875ca5fad'
MISSING_SUMMARIES = tuple(f'chb24/chb24_{n:02d}.edf' for n in (2,5,8,10,12,16,18,19,20,22))
MAX_METADATA_BYTES = 262144

class Refused(ValueError):
    pass

def need(condition, message):
    if not condition:
        raise Refused(message)

def keys(value, fields, name):
    need(type(value) is dict and set(value) == set(fields), name + ': unexpected or missing fields')

def integer(value, name, minimum=1, maximum=2**53-1):
    need(type(value) is int and minimum <= value <= maximum, name + ': invalid integer')
    return value

def digest(value):
    return hashlib.sha256(value).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest_text(value, name):
    need(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), name + ': invalid digest')

def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result

def json_bytes(body):
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refused('Non-finite JSON')))

def ordinary_open(path, cap):
    integer(cap, 'File byte limit')
    path = Path(path)
    # The operator owns the directory tree. Reject stable symlinks before opening;
    # this is not a hostile concurrent-filesystem sandbox.
    need(not any(p.is_symlink() for p in [path, *path.parents]), 'Input traverses a symlink')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    stream = os.fdopen(fd, 'rb')
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_size > cap or info.st_nlink != 1:
        stream.close()
        raise Refused('Input must be an unaliased regular file within byte budget')
    return stream, info

def stable(before, after):
    fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
    need(all(getattr(before, key) == getattr(after, key) for key in fields), 'Input changed during read')

def read_bytes(path, cap, expected=None):
    with ordinary_open(path, cap)[0] as stream:
        before = os.fstat(stream.fileno())
        data = stream.read(min(cap, before.st_size) + 1)
        need(len(data) <= cap and len(data) == before.st_size, 'Input size changed or exceeds budget')
        stable(before, os.fstat(stream.fileno()))
    if expected is not None:
        need(digest(data) == expected, 'Publisher/source identity mismatch: ' + Path(path).name)
    return data

def safe_member(root, member):
    need(isinstance(member, str) and not member.startswith('/') and
         all(p not in ('', '.', '..') for p in member.split('/')), 'Invalid source member')
    root = Path(root).resolve(strict=True)
    return root / member

def load_core():
    body = read_bytes(EVENTS / 'cli.py', MAX_METADATA_BYTES, EVENTS_CLI_SHA256)
    cli = types.ModuleType('_neural009_existing_verified_cli')
    cli.__file__ = str(EVENTS / 'cli.py')
    exec(compile(body, cli.__file__, 'exec'), cli.__dict__)
    core, _ = cli.load_verified_core(EVENTS_MANIFEST_SHA256)
    return core

def parse_summary(body, folder):
    """Strict original-summary event blocks; absence is never implicitly zero."""
    need(re.fullmatch(r'chb\d{2}', folder), 'Invalid case folder')
    text = body.decode('ascii')
    blocks = re.split(r'(?m)^File Name: ', text)
    need(len(blocks) > 1, 'Summary contains no recording blocks')
    result = {}
    for block in blocks[1:]:
        lines = block.splitlines()
        filename = lines[0].strip()
        need(re.fullmatch(re.escape(folder) + r'[a-z]?_[A-Za-z0-9_+\-]+\.edf', filename), 'Malformed summary filename')
        identifier = folder + '/' + filename
        need(identifier not in result, 'Repeated summary recording')
        counts = [re.fullmatch(r'Number of Seizures in File:\s*(\d+)\s*', line) for line in lines[1:]]
        counts = [int(m.group(1)) for m in counts if m]
        need(len(counts) == 1, 'Summary must explicitly state one event count')
        events = []
        pending = None
        for raw in lines[1:]:
            line = raw.strip()
            if not line.startswith('Seizure'):
                continue
            m = re.fullmatch(r'Seizure(?: \d+)? (Start|End) Time:\s*(\d+) seconds', line)
            need(m is not None, 'Unrecognized seizure annotation line')
            seconds = int(m.group(2))
            if m.group(1) == 'Start':
                need(pending is None, 'Unpaired seizure start')
                pending = seconds * 10
            else:
                need(pending is not None and pending < seconds * 10, 'Invalid seizure end')
                need(not events or pending >= events[-1][1], 'Overlapping or unordered source annotations')
                events.append([pending, seconds * 10])
                pending = None
        need(pending is None and len(events) == counts[0], 'Summary event count/pair mismatch')
        result[identifier] = events
    return result

def checksums(body):
    result = {}
    for line in body.decode('ascii').splitlines():
        fields = line.split()
        need(len(fields) == 2 and re.fullmatch('[0-9a-f]{64}', fields[0]), 'Malformed publisher checksum')
        name = fields[1]
        need(name not in result and not name.startswith('/') and
             all(p not in ('','.','..') for p in name.split('/')), 'Repeated/unsafe publisher member')
        result[name] = fields[0]
    return result

def metadata(root, index):
    """Authenticate exact release metadata and reconcile the full annotation roster."""
    raw_checks = read_bytes(safe_member(root, 'SHA256SUMS.txt'), MAX_METADATA_BYTES, CHECKSUMS_SHA256)
    sums = checksums(raw_checks)
    raw_records = read_bytes(safe_member(root, 'RECORDS'), MAX_METADATA_BYTES, RECORDS_SHA256)
    roster = raw_records.decode('ascii').splitlines()
    need(roster == list(index), 'Exact publisher RECORDS ordering differs from evaluator')
    for name, row in index.items():
        need(sums.get(name) == row['publisher_sha256'], 'Publisher EDF/index mismatch')
    raw_positive = read_bytes(safe_member(root, 'RECORDS-WITH-SEIZURES'), MAX_METADATA_BYTES, POSITIVE_LIST_SHA256)
    listed = [line.strip() for line in raw_positive.decode('ascii').splitlines() if line.strip()]
    need(len(listed) == len(set(listed)) and set(listed) <= set(index), 'Malformed positive-file list')
    rows, summary_hashes = {}, {}
    for folder in sorted({r['case_folder'] for r in index.values()}):
        name = folder + '/' + folder + '-summary.txt'
        need(name in sums, 'Summary absent from publisher checksum inventory')
        raw = read_bytes(safe_member(root, name), MAX_METADATA_BYTES, sums[name])
        parsed = parse_summary(raw, folder)
        need(not set(rows) & set(parsed), 'Repeated summary identity')
        rows.update(parsed)
        summary_hashes[folder] = digest(raw)
    need(set(rows) <= set(index), 'Summary contains an unregistered recording')
    missing = set(index) - set(rows)
    need(missing == set(MISSING_SUMMARIES), 'Unreviewed summary-absent recording set')
    sidecar_paths = {name[:-len('.seizures')] for name in sums if name.endswith('.edf.seizures')}
    positive = {name for name, intervals in rows.items() if intervals}
    need(sidecar_paths <= set(index) and positive == sidecar_paths,
         'Summary positives disagree with complete publisher sidecar inventory')
    need(set(listed) - positive == {'chb07/chb07_18.edf'} and
         positive - set(listed) == {'chb07/chb07_19.edf'}, 'Unreviewed positive-list discrepancy')
    # The selected author loader uses summary second boundaries. The ten absent
    # chb24 blocks are admitted only under the explicitly reviewed exhaustive-
    # sidecar source assumption, never by general missing-label imputation.
    references, coverage = {}, {}
    for name in index:
        inferred = name in missing
        intervals = rows.get(name, [])
        proof = {'recording_id': name, 'summary_sha256': summary_hashes[index[name]['case_folder']],
                 'publisher_checksums_sha256': CHECKSUMS_SHA256,
                 'positive_list_sha256': POSITIVE_LIST_SHA256,
                 'source_category': ('inferred_zero_from_exhaustive_sidecar_inventory' if inferred else
                                     'explicit_summary_events' if intervals else 'explicit_summary_zero'),
                 'sidecar_sha256': sums.get(name + '.seizures'),
                 'reference_intervals_ticks': intervals}
        references[name] = {'intervals': intervals, 'annotation_sha256': digest(canonical(proof))}
        coverage[name] = proof
    report = {'schema': 'neural009_source_annotation_reconciliation_v1',
              'policy': 'pinned_author_summary_seconds_with_reviewed_chb24_sidecar_absence_v1',
              'recordings': len(index), 'explicit_summary_records': len(rows),
              'summary_positive_recordings': len(positive), 'summary_events': sum(map(len, rows.values())),
              'inferred_zero_recordings': sorted(missing),
              'positive_list_only': sorted(set(listed)-positive),
              'summary_sidecar_only': sorted(positive-set(listed)),
              'record_evidence': coverage, 'binary_annotation_timing_parity': False,
              'clinical_label_correction': False, 'scientific_qualification': False}
    return references, report

def ascii_int(raw, name, minimum=1):
    text = raw.decode('ascii').strip()
    need(re.fullmatch(r'[0-9]+', text) is not None, name + ': invalid EDF integer')
    return integer(int(text), name, minimum=minimum)

def parse_edf_header(header, file_size):
    """Read exact EDF geometry, without decoding sample payloads or wall clocks."""
    need(len(header) >= 256 and header[:8] == b'0       ', 'Unsupported EDF version')
    n = ascii_int(header[252:256], 'EDF signal count')
    need(n <= 256, 'EDF signal count exceeds supported bound')
    size = ascii_int(header[184:192], 'EDF header length')
    need(size == 256 + 256*n and len(header) == size, 'EDF header length mismatch')
    reserved = header[192:236].decode('ascii').strip()
    need(reserved == '' or reserved.startswith('EDF+C'), 'Discontinuous/unsupported EDF record clock')
    records = ascii_int(header[236:244], 'EDF data record count')
    try:
        duration = Fraction(header[244:252].decode('ascii').strip())
    except (ValueError, ZeroDivisionError) as exc:
        raise Refused('Invalid EDF record duration') from exc
    need(duration > 0, 'Nonpositive EDF record duration')
    labels = [header[256+16*i:256+16*(i+1)].decode('ascii').strip() for i in range(n)]
    need(all(labels) and all(len(s) <= 256 for s in labels), 'Missing EDF signal labels')
    samples_start = 256 + 216*n
    samples = [ascii_int(header[samples_start+8*i:samples_start+8*(i+1)], 'EDF samples per record') for i in range(n)]
    expected_bytes = size + 2*records*sum(samples)
    need(file_size == expected_bytes, 'EDF body size differs from declared complete sample geometry')
    ticks = duration * records * 10
    need(ticks.denominator == 1, 'EDF observed duration is off the exact 10 Hz grid')
    integer(ticks.numerator, 'Observed ticks')
    return {'labels': labels, 'samples_per_record': samples, 'data_records': records,
            'record_duration': duration, 'observed_ticks': ticks.numerator,
            'header_sha256': digest(header)}

def inspect_edf(path, expected, cap):
    """Stream-authenticate the whole original EDF and retain only its header."""
    digest_text(expected, 'Expected EDF hash')
    stream, before = ordinary_open(path, cap)
    with stream:
        fixed = stream.read(256)
        need(len(fixed) == 256, 'Truncated EDF fixed header')
        n = ascii_int(fixed[252:256], 'EDF signal count')
        need(n <= 256, 'EDF signal count exceeds supported bound')
        length = ascii_int(fixed[184:192], 'EDF header bytes')
        need(length == 256 + 256*n, 'EDF header length mismatch')
        header = fixed + stream.read(length-256)
        geometry = parse_edf_header(header, before.st_size)
        hashed = hashlib.sha256(header)
        consumed = len(header)
        while True:
            chunk = stream.read(min(65536, cap-consumed+1))
            if not chunk:
                break
            consumed += len(chunk)
            need(consumed <= cap, 'EDF grew beyond byte limit')
            hashed.update(chunk)
        stable(before, os.fstat(stream.fileno()))
    need(consumed == before.st_size and hashed.hexdigest() == expected, 'Complete EDF publisher hash mismatch')
    return geometry, consumed, (before.st_dev, before.st_ino)

def build(core, source_root, review, limits, *, max_edf_bytes, max_total_edf_bytes):
    """Build existing evaluator admission from all exact original local files."""
    integer(max_edf_bytes, 'Per-EDF byte cap'); integer(max_total_edf_bytes, 'Total EDF byte cap')
    keys(limits, ('max_record_ticks','max_total_ticks','max_prediction_segments'), 'Scorer limits')
    for field, value in limits.items():
        integer(value, field)
    index, people, index_sha = core.source_index()
    keys(review, ('schema','source_index_sha256','normalization_recipe_sha256','clock_review_sha256',
                  'rights_review_sha256','accept_annotation_source_assumptions','records'), 'Source review')
    need(review['schema'] == 'neural009_source_review_v1' and review['source_index_sha256'] == index_sha,
         'Wrong source review identity')
    need(review['accept_annotation_source_assumptions'] is True, 'Reviewed annotation source assumptions required')
    for field in ('normalization_recipe_sha256','clock_review_sha256','rights_review_sha256'):
        digest_text(review[field], field)
    need(type(review['records']) is list and len(review['records']) == len(index), 'Complete channel review required')
    reviews = {}
    for row in review['records']:
        keys(row, ('recording_id','edf_header_sha256','channels','predictor_channels'), 'Channel review')
        name = row['recording_id']
        need(isinstance(name,str) and name in index and name not in reviews, 'Repeated/unknown channel-review identity')
        digest_text(row['edf_header_sha256'], 'Reviewed header hash')
        need(type(row['channels']) is list and row['channels'] and type(row['predictor_channels']) is list,
             'Missing reviewed montage')
        for channel in row['channels']:
            keys(channel, ('label','role'), 'Reviewed channel')
            need(isinstance(channel['label'],str) and channel['role'] in ('eeg','annotation','other'), 'Invalid channel review')
            need(channel['label'].strip() != 'EDF Annotations' or channel['role'] == 'annotation',
                 'EDF Annotations has a defined non-EEG role')
        selected = row['predictor_channels']
        need(selected and all(type(i) is int and 0 <= i < len(row['channels']) for i in selected)
             and len(set(selected)) == len(selected), 'Invalid selected EEG channel indices')
        need(all(row['channels'][i]['role']=='eeg' for i in selected), 'Non-EEG selected as predictor')
        reviews[name] = row
    refs, reconciliation = metadata(source_root, index)
    result = {'schema': 'neural009_admission_v1','task_id':'NEURAL-009','source_index_sha256':index_sha,
              'public_development_only':True,'folds':core._folds(people),'records':[],
              **{field:review[field] for field in ('normalization_recipe_sha256','clock_review_sha256','rights_review_sha256')}}
    total = 0
    observed_total = 0
    identities = set()
    for name, original in index.items():
        remaining = min(max_edf_bytes, max_total_edf_bytes-total)
        need(remaining > 0, 'Total EDF byte budget exhausted')
        geometry, size, physical = inspect_edf(safe_member(source_root,name), original['publisher_sha256'], remaining)
        need(geometry['observed_ticks'] <= limits['max_record_ticks'], 'EDF exceeds per-record scorer support budget')
        observed_total += geometry['observed_ticks']
        need(observed_total <= limits['max_total_ticks'], 'EDF cohort exceeds total scorer support budget')
        need(physical not in identities, 'Two recording paths alias the same physical file')
        identities.add(physical); total += size
        reviewed = reviews[name]
        need(geometry['header_sha256'] == reviewed['edf_header_sha256'], 'EDF header differs from reviewed montage/clock')
        need([c['label'] for c in reviewed['channels']] == geometry['labels'], 'Reviewed channel order differs from EDF')
        selected = reviewed['predictor_channels']
        rates = [Fraction(geometry['samples_per_record'][i],1)/geometry['record_duration'] for i in selected]
        need(len(set(rates)) == 1 and rates[0].denominator == 1, 'Selected EEG channels require one exact integer sample rate')
        samples = geometry['samples_per_record'][selected[0]] * geometry['data_records']
        row = {'recording_id':name,'biological_person':original['biological_person'],
               'edf_sha256':original['publisher_sha256'],'edf_header_sha256':geometry['header_sha256'],
               'annotation_sha256':refs[name]['annotation_sha256'],
               'annotation_status':'explicit_events' if refs[name]['intervals'] else 'explicit_zero_events',
               'native_sample_rate_hz':rates[0].numerator,'native_sample_count':samples,
               'observed_ticks':geometry['observed_ticks'],'channels':reviewed['channels'],
               'predictor_channels':selected,'reference_intervals':refs[name]['intervals']}
        result['records'].append(row)
    core._admit(result,index,people,index_sha,limits)
    support = core.public_support(result)
    core.validate_public_support(support,limits)
    reconciliation.update({'complete_edf_bytes_authenticated':total,
                           'normalization_executed':False,'signal_samples_decoded':False,
                           'protected_execution_qualified':False,
                           'source_review_sha256':digest(canonical(review)),
                           'admission_sha256':digest(canonical(result)),
                           'public_support_sha256':digest(canonical(support))})
    return {'admission.json':result,'public-support.json':support,'private-source-evidence.json':reconciliation}

def write_outputs(directory, outputs, cap):
    integer(cap,'Output byte cap')
    serialized = {name:(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode() for name,value in outputs.items()}
    need(sum(map(len,serialized.values())) <= cap, 'Complete output exceeds byte budget')
    directory = Path(directory)
    need(not directory.exists() and not directory.is_symlink(), 'Output directory must be fresh')
    directory.mkdir(mode=0o700)
    for name,body in serialized.items():
        with os.fdopen(os.open(directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as handle:
            handle.write(body)
    return {name:{'bytes':len(body),'sha256':digest(body)} for name,body in serialized.items()}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('metadata','build'))
    parser.add_argument('--source-root',required=True)
    parser.add_argument('--review')
    parser.add_argument('--limits')
    parser.add_argument('--output',required=True)
    parser.add_argument('--max-json-bytes',type=int,required=True)
    parser.add_argument('--max-output-bytes',type=int,required=True)
    parser.add_argument('--max-edf-bytes',type=int)
    parser.add_argument('--max-total-edf-bytes',type=int)
    args=parser.parse_args(argv)
    try:
        core=load_core()
        integer(args.max_json_bytes,'JSON byte cap')
        if args.command=='metadata':
            index,_,_=core.source_index()
            _,report=metadata(args.source_root,index)
            outputs={'private-source-evidence.json':report}
        else:
            need(args.review and args.limits and args.max_edf_bytes and args.max_total_edf_bytes,
                 'Build requires review, scorer limits and explicit EDF byte budgets')
            review=json_bytes(read_bytes(Path(args.review),args.max_json_bytes))
            limits=json_bytes(read_bytes(Path(args.limits),args.max_json_bytes))
            outputs=build(core,args.source_root,review,limits,max_edf_bytes=args.max_edf_bytes,
                          max_total_edf_bytes=args.max_total_edf_bytes)
        pins=write_outputs(args.output,outputs,args.max_output_bytes)
        print(json.dumps({'status':'complete','outputs':pins,'scientific_qualification':False},sort_keys=True))
        return 0
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,OverflowError,MemoryError) as exc:
        print(json.dumps({'status':'refused','reason':str(exc),'scientific_qualification':False}),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())

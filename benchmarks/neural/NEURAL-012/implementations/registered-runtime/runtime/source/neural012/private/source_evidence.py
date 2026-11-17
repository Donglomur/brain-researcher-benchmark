"""Complete observed-source joins. Consistency never issues authentic authority."""
import hashlib, re
from pathlib import PurePosixPath
import io_contract as io
import scientific_contract as sc
from analysis import panel as validate_panel, interval_list
from source_header import inspect_header
import annotation_binding as annotation

SCHEMA = 'neural012_source_evidence_selection_v1'
CHB_RECORDS_IDENTITY = {'bytes':13056,'sha256':'72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08'}
ASSET_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
DOC_FIELDS = ('chb_records','siena_records','chb_positives','chb_summaries','chb_case_indices',
              'chb_correction_companion','siena_summaries','common_reference','grouping','record_time')
HOLDS = ('publisher_origin','biological_identity_truth','original_record_time_independence',
         'publisher_whitelist_interpretation','common_reference_physics','authentic_clock_adjudication',
         'protected_target_authority','native_isolation')

def sha(raw): return hashlib.sha256(raw).hexdigest()
def same(a, b): return io.encoded(a) == io.encoded(b)
def relative(value):
    io.need(type(value) is str and value and not value.startswith('/') and '\\' not in value
            and all(x not in ('','.','..') for x in value.split('/'))
            and not any(c in value for c in '\0\r\n'), 'confined relative source member')
    return value
def asset_id(value):
    io.need(type(value) is str and ASSET_ID.fullmatch(value), 'bounded asset identity'); return value
def group(path, cohort):
    first = path.split('/')[0]
    return ('CHB:' + ('chb01' if first == 'chb21' else first)) if cohort == 'CHB' else 'Siena:' + first

def validate_target_selection(selection, value):
    io.fields(value, ['path','bytes','sha256','panel_sha256','scientific_profile_sha256','source_targets_sha256'])
    path = value['path']
    io.need(type(path) is str and path.startswith('/') and '\\' not in path and
            all(x not in ('.','..') for x in PurePosixPath(path).parts) and not any(c in path for c in '\0\r\n'), 'selected absolute private target path')
    io.need(type(value['bytes']) is int and 0 < value['bytes'] <= io.MAX_JSON, 'complete bounded target extent')
    for key in ('sha256','panel_sha256','scientific_profile_sha256','source_targets_sha256'): sc.pin(value[key])
    io.need(value['panel_sha256'] == sha(io.encoded(selection['panel'])) and
            value['scientific_profile_sha256'] == sc.profile_sha256(selection['panel']['scientific_profile']) and
            value['source_targets_sha256'] == sha(io.encoded(selection['source_targets'])), 'target selection joins original panel/source/profile')
    io.need(same(value, selection['target_selection']), 'exact original selected target declaration')
    return value

def validate_selection(selection):
    io.fields(selection, ['schema','panel','reference','source_targets','target_selection','records','assets','documents','whitelists'])
    io.need(selection['schema'] == SCHEMA, 'source evidence selection version')
    panel = selection['panel']; rows = validate_panel(panel); reference = selection['reference']
    sc.validate_reference(reference, panel['records'])
    io.need(same(reference['scientific_profile'], panel['scientific_profile']), 'one original scientific profile')
    gold = selection['source_targets']; io.fields(gold, ['panel_sha256','scientific_profile_sha256','records'])
    profile_pin = sc.profile_sha256(panel['scientific_profile'])
    io.need(gold['panel_sha256'] == sha(io.encoded(panel)) and gold['scientific_profile_sha256'] == profile_pin, 'CHB targets bind exact panel/profile')
    io.need(type(gold['records']) is list and len(gold['records']) == 686, 'complete source targets')
    target_ids = set()
    for row in gold['records']:
        io.fields(row, ['recording_id','events']); rid = row['recording_id']
        io.need(rid in rows and rows[rid]['cohort'] == 'CHB' and rid not in target_ids, 'unique source-only target')
        interval_list(row['events'], rows[rid]['duration_seconds']); target_ids.add(rid)
    io.need(target_ids == {r for r in rows if rows[r]['cohort'] == 'CHB'}, 'all original source labels')
    validate_target_selection(selection, selection['target_selection'])
    assets = selection['assets']; io.need(type(assets) is list and 1454 < len(assets) <= 4096, 'full raw/prepared/document assets')
    by_asset = {}; locations = set()
    for a in assets:
        io.fields(a, ['asset_id','root','path','bytes','sha256','capture']); aid = asset_id(a['asset_id'])
        asset_id(a['root']); relative(a['path']); sc.pin(a['sha256'])
        io.need(aid not in by_asset and (a['root'],a['path']) not in locations and type(a['bytes']) is int
                and 0 < a['bytes'] < 10000000000 and a['capture'] in ('none','edf_header','whole_metadata'), 'unique selected source asset and bounded extent')
        by_asset[aid] = a; locations.add((a['root'],a['path']))
    docs = selection['documents']; io.fields(docs, DOC_FIELDS); used = set()
    def doc(aid):
        asset_id(aid); io.need(aid in by_asset and by_asset[aid]['capture'] == 'whole_metadata', 'captured original document selection'); used.add(aid)
    for key in ('chb_records','siena_records','chb_positives','chb_correction_companion'): doc(docs[key])
    roster_asset = by_asset[docs['chb_records']]
    io.need({k:roster_asset[k] for k in ('bytes','sha256')} == CHB_RECORDS_IDENTITY, 'exact previously observed official CHB RECORDS documentary identity; no filename-roster substitution')
    cases = {f'chb{i:02d}' for i in range(1,25)}
    io.need(type(docs['chb_summaries']) is dict and cases-{'chb24'} <= set(docs['chb_summaries']) <= cases
            and type(docs['chb_case_indices']) is dict and set(docs['chb_case_indices']) == cases, 'complete CHB case metadata')
    for case, aid in docs['chb_summaries'].items():
        doc(aid); io.need(by_asset[aid]['path'].endswith(case+'-summary.txt'), 'summary case binding')
    for case, aid in docs['chb_case_indices'].items():
        doc(aid); io.need(by_asset[aid]['path'].endswith(case+'-index.html'), 'case listing binding')
    io.need(type(docs['siena_summaries']) is dict and len(docs['siena_summaries']) == 14, 'all Siena subject summaries')
    for subject, aid in docs['siena_summaries'].items():
        io.need(type(subject) is str and re.fullmatch(r'PN\d{2}',subject), 'original Siena subject')
        doc(aid); io.need(by_asset[aid]['path'].endswith(subject+'/Seizures-list-'+subject+'.txt'), 'exact Siena summary subject')
    for key in ('common_reference','grouping','record_time'):
        ids = docs[key]; io.need(type(ids) is list and ids and len(ids) == len(set(ids)), 'explicit unresolved documentary evidence roster')
        for aid in ids: doc(aid)
    whitelists = selection['whitelists']
    io.need(type(whitelists) is dict and set(whitelists) == set(docs['siena_summaries']), 'whole Siena release whitelist')
    for subject, w in whitelists.items():
        io.fields(w, ['patient','summary_sha256','eeg_labels','evidence_sha256','authority_status'])
        io.need(w['patient'] == subject and w['authority_status'] == 'unissued', 'whitelist declaration does not adjudicate')
        sc.pin(w['summary_sha256']); sc.pin(w['evidence_sha256'])
        io.need(w['summary_sha256'] == by_asset[docs['siena_summaries'][subject]]['sha256'], 'whitelist original summary identity')
        io.need(w['evidence_sha256'] in {by_asset[x]['sha256'] for x in used}, 'whitelist evidence is an observed selected document')
        sc.edge_mapping(w['eeg_labels'], 'Siena')
    whitelist_pin = sc.digest({'schema':'siena_release_EEG_whitelists_v1','subjects':[whitelists[x] for x in sorted(whitelists)]})
    records = selection['records']; io.need(type(records) is list and len(records) == 727, 'all source-record bindings')
    seen = set(); published = {'CHB':set(),'Siena':set()}; raw_ids = set(); prepared_ids = set(); people = {}; inverse_people = {}
    refs = {r['recording_id']:r for r in reference['records']}
    for record in records:
        io.fields(record, ['recording_id','publisher_path','original_asset','prepared_asset','summary_asset','clock_record'])
        rid = record['recording_id']; io.need(rid in rows and rid not in seen, 'unique complete source binding'); seen.add(rid)
        row = rows[rid]; cohort = row['cohort']; path = record['publisher_path']; relative(path)
        pattern = r'chb(?:0[1-9]|1[0-9]|2[0-4])/[^/]+\.edf' if cohort == 'CHB' else r'PN\d{2}/[^/]+\.edf'
        io.need(re.fullmatch(pattern,path) and path not in published[cohort], 'unique cohort original EDF name'); published[cohort].add(path)
        for key, capture, identifiers in [('original_asset','edf_header',raw_ids),('prepared_asset','none',prepared_ids)]:
            aid = asset_id(record[key]); io.need(aid in by_asset and aid not in identifiers and by_asset[aid]['capture'] == capture, 'unique complete original/prepared asset')
            identifiers.add(aid); used.add(aid)
        original, prepared = by_asset[record['original_asset']], by_asset[record['prepared_asset']]
        io.need(original['path'] == path and prepared['path'] == row['signal']['file'] and
                prepared['bytes'] == row['signal']['bytes'] and prepared['sha256'] == row['signal']['sha256'], 'exact original path and prepared signal binding')
        gid = group(path,cohort); pid = row['patient_id']
        io.need((gid not in people or people[gid] == pid) and (pid not in inverse_people or inverse_people[pid] == gid), 'one opaque ID per declared biological group; chb21 remains chb01')
        people[gid] = pid; inverse_people[pid] = gid
        subject = path.split('/')[0]
        if cohort == 'CHB':
            io.need(record['clock_record'] is None and record['summary_asset'] == docs['chb_summaries'].get(subject), 'original CHB summary selection')
        else:
            io.need(subject in whitelists and record['summary_asset'] == docs['siena_summaries'][subject], 'original Siena summary binding')
            sc.validate_clock_record(record['clock_record'])
            io.need(refs[rid]['release_whitelist_sha256'] == whitelist_pin and refs[rid]['release_eeg_labels'] == whitelists[subject]['eeg_labels'], 'same whole-release whitelist identity and electrode list')
            common = refs[rid]['common_reference']
            if common['claim'] == 'common_reference':
                io.need(common['evidence_sha256'] in {by_asset[x]['sha256'] for x in docs['common_reference']}, 'reference claim cites selected original documentary bytes')
            resolution = record['clock_record']['resolution']
            if resolution['status'] == 'documented_selection':
                io.need(resolution['evidence_sha256'] in {by_asset[x]['sha256'] for x in docs['record_time']}, 'clock decision cites observed selected time evidence, without adjudicating it')
    io.need(seen == set(rows) and len(raw_ids) == len(prepared_ids) == 727 and raw_ids.isdisjoint(prepared_ids), 'complete distinct original/prepared membership')
    io.need(len(people) == 37 and len({p.split('/')[0] for p in published['CHB']}) == 24 and
            {p.split('/')[0] for p in published['Siena']} == set(whitelists), 'full 24-case/23-person plus14-person scope')
    io.need(used == set(by_asset), 'no omitted or unclassified source assets')
    return selection

def asset_requirements(selection):
    validate_selection(selection)
    return sorted([dict(x) for x in selection['assets']], key=lambda x:x['asset_id'])

def validate_consumer_binding(selection, panel_raw, reference_raw, source_targets_raw, profile_pin):
    validate_selection(selection)
    io.need(type(panel_raw) is bytes and panel_raw == io.encoded(selection['panel']) and
            type(reference_raw) is bytes and reference_raw == io.encoded(selection['reference']) and
            type(source_targets_raw) is bytes and source_targets_raw == io.encoded(selection['source_targets']) and
            profile_pin == sc.profile_sha256(selection['panel']['scientific_profile']), 'same original canonical full consumer inputs')
    return True

def validate_phase_binding(selection, case, reference, logical_job):
    from case_contract import validate_case, project_row
    validate_selection(selection); validate_case(case); io.fields(logical_job, ['job_id','plan_sha256']); sc.pin(logical_job['plan_sha256'])
    from job_plan import job_plan
    plan = job_plan(io.encoded(selection['panel']))
    io.need(logical_job['plan_sha256'] == sha(io.encoded(plan)), 'exact full source job plan')
    jobs = [x for x in plan['jobs'] if x['job_id'] == logical_job['job_id']]
    io.need(len(jobs) == 1 and jobs[0]['arm'] == case['arm'], 'exact source-owner logical job')
    from prepare_case import make_cases
    fit, predict = make_cases(io.encoded(selection['panel']), io.encoded(selection['source_targets']), case['arm'], jobs[0]['held_source_patient'])
    expected = fit if case['phase'] == 'fit' else predict
    io.need(same(case,expected), 'exact full phase source/query membership and training labels')
    if case['arm'] == 'timing': io.need(reference is None, 'timing has no physical source reference')
    else:
        if type(reference) is bytes:
            raw = reference; reference = io.strict(raw)
            io.need(raw == io.encoded(reference), 'canonical original projected reference bytes')
        full = {r['recording_id']:r for r in selection['panel']['records']}
        phase = case['train'] if case['phase'] == 'fit' else case['query']
        selected = [full[r['recording_id']] for r in phase]
        io.need(same(reference,sc.project_reference(selection['reference'],selected)), 'exact original phase reference projection')
    return True

def input_evidence_binding(selection, record, header_sha256):
    """Bind observed original/header and the whole selected document corpus.

    This is a deterministic join identity, not a publisher-origin certificate.
    """
    assets = {a['asset_id']:a for a in selection['assets']}
    original = assets[record['original_asset']]
    corpus = {a['asset_id']:{'bytes':a['bytes'],'sha256':a['sha256']} for a in selection['assets'] if a['capture'] == 'whole_metadata'}
    return sc.digest({'publisher_path':record['publisher_path'], 'original_source':{'bytes':original['bytes'],'sha256':original['sha256']},
                      'header_sha256':header_sha256, 'document_roles':selection['documents'],'document_corpus':corpus})

def validate_observations(selection, observations):
    """Validate complete owned observations; no authentic adjudication is returned."""
    validate_selection(selection); assets = {a['asset_id']:a for a in selection['assets']}
    io.need(type(observations) is dict and set(observations) == set(assets), 'complete original observation roster')
    for aid, a in assets.items():
        o = observations[aid]
        io.fields(o, ['asset_id','bytes','sha256','captured_bytes','captured_sha256','before_identity','after_identity'])
        io.need(o['asset_id'] == aid and o['bytes'] == a['bytes'] and o['sha256'] == a['sha256'] and
                type(o['captured_bytes']) is bytes and sha(o['captured_bytes']) == o['captured_sha256'], 'original file/retained prefix identity')
        io.need(type(o['before_identity']) is tuple and len(o['before_identity']) >= 5 and o['before_identity'] == o['after_identity'], 'stable original file observation')
        if a['capture'] == 'none': io.need(o['captured_bytes'] == b'', 'no samples retained as metadata')
        elif a['capture'] == 'whole_metadata': io.need(len(o['captured_bytes']) == a['bytes'] and o['captured_sha256'] == a['sha256'], 'complete original documentary bytes')
        else: io.need(256 < len(o['captured_bytes']) <= 131328, 'complete bounded original EDF header')
    body = lambda aid: observations[aid]['captured_bytes']
    docs = selection['documents']; rows = {r['recording_id']:r for r in selection['panel']['records']}
    refs = {r['recording_id']:r for r in selection['reference']['records']}; records = {r['recording_id']:r for r in selection['records']}
    for cohort, key in [('CHB','chb_records'),('Siena','siena_records')]:
        names = annotation.roster(body(docs[key]),cohort)
        io.need(set(names) == {r['publisher_path'] for rid,r in records.items() if rows[rid]['cohort'] == cohort}, 'observed published membership exactly equals selected full release')
    source_labels = annotation.chb_annotations(body(docs['chb_records']),body(docs['chb_positives']),
        {c:body(a) for c,a in docs['chb_summaries'].items()}, {c:body(a) for c,a in docs['chb_case_indices'].items()},body(docs['chb_correction_companion']))
    gold = {r['recording_id']:r['events'] for r in selection['source_targets']['records']}
    headers = {}; labels = {}; original_labels = {}; clocks = {}; status = {}; discrepancies = []; duplicate_hashes = {}
    profile = selection['panel']['scientific_profile']
    for rid, record in records.items():
        row = rows[rid]; ref = refs[rid]; cohort = row['cohort']; original = assets[record['original_asset']]
        h = inspect_header(body(record['original_asset']), original['bytes'], cohort, ref['release_eeg_labels']); headers[rid] = h
        selected = h['selected_channels']
        io.need(ref['input_evidence_sha256'] == input_evidence_binding(selection,record,observations[record['original_asset']]['captured_sha256']), 'physical declaration binds observed original/header/document evidence')
        io.need(h['duration_seconds'] == row['duration_seconds'] and h['sample_rate_hz'] == ref['sample_rate_hz'] and
                [x['label'] for x in selected] == ref['channel_labels'] and [x['source_index'] for x in selected] == ref['source_channel_indices'] and
                [x['scale_to_microvolts'] for x in selected] == ref['calibration']['scale_to_microvolts'] and
                [x['offset_microvolts'] for x in selected] == ref['calibration']['offset_microvolts'], 'actual original header equals declared physical montage/calibration')
        duplicate_hashes.setdefault(original['sha256'],[]).append(rid)
        if cohort == 'CHB':
            events = source_labels[record['publisher_path']]; interval_list(events,row['duration_seconds'])
            io.need(events == gold[rid], 'actual original CHB annotation derivation equals selected training labels')
            original_labels[rid] = events; labels[rid] = events; status[rid] = 'source_parser'
        else:
            events, summary_clock = annotation.siena_original(record['publisher_path'],body(record['summary_asset']))
            interval_list(events,row['duration_seconds']); c = record['clock_record']; sc.validate_clock_record(c)
            io.need(c['path'] == record['publisher_path'] and c['source_sha256'] == original['sha256'] and
                    c['header_sha256'] == observations[record['original_asset']]['captured_sha256'] and
                    c['annotation_sha256'] == assets[record['summary_asset']]['sha256'] and c['source_events'] == events and
                    c['duration_seconds'] == h['duration_seconds'] and c['header_clock'] == h['registration_clock'] and
                    c['summary_clock'] == summary_clock, 'same original parser/header/summary clock evidence')
            original_labels[rid] = events; clocks[rid] = c
            if c['discrepancy']: discrepancies.append(rid)
            if profile['label_profile'] == 'C1_source_parser': labels[rid] = events; status[rid] = 'source_parser'
            else:
                candidate = c['C2_candidate']; labels[rid] = candidate['events']; status[rid] = candidate['status']
    io.need(sum(len(original_labels[r]) for r in original_labels if rows[r]['cohort'] == 'Siena') == 47, 'all original 47 Siena intervals')
    return {'schema':'neural012_source_observation_validation_v1','validation_status':'observed_consistency_only',
            'panel_sha256':sha(io.encoded(selection['panel'])),'scientific_profile_sha256':sc.profile_sha256(profile),
            'headers':headers,'labels':labels,'original_labels':original_labels,'clock_records':clocks,'label_status':status,
            'record_rows':records,'discrepancies':sorted(discrepancies),'duplicate_original_content_groups':sorted(sorted(v) for v in duplicate_hashes.values() if len(v)>1),
            'records':727,'people':37,'unresolved':list(HOLDS),'authentic_qualification':False,'projection_sample_equality_checked':False}

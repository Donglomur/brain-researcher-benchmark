"""Pinned metadata intake and complete source/ROI/split reconciliation."""
import csv
import hashlib
import io
from collections import Counter
from urllib.parse import urlsplit
from owner.io import Artifact, ContractError, capture, decode
from .algorithm import CONTEXT, COUNTS, SPLITS, number, split_mice, text_id

PINS = {
 'source_provenance': (3171, 'b982512cd9884dd4155315b822757c49dde84fe718de227b1049fd429ad05800'),
 'source_roster': (15010418, 'dbdf5abd501ff4bb46cee790e2bc2c1ad32ba15db2dd35bb6ba1dd1dc529fd65'),
 'provider_manifest': (2455839, '8cb641fb26da107334b99d9521e12add1b33015316cb80d5df4559987315222a'),
 'experiment_metadata': (656768, '7cc11662572df3e2711bcd056c0e7ec07da03d7cacb86e24ec833a06e464dcf8'),
 'roi_metadata': (4284681, '539f64843962625151a4b14f576b24682bb9f1f695e81c4c640300825f59f97c'),
}
HOST = 'visual-behavior-ophys-data.s3.us-west-2.amazonaws.com'
PREFIX = '/visual-behavior-ophys/behavior_ophys_experiments/'
SOURCE_SCHEMA = 'neural063_source_selection_v2'


def bounded_metadata(ctx, name):
    ref = ctx.input_ref(name, roles={name})
    if name in PINS and (ref.bytes, ref.sha256) != PINS[name]:
        raise ContractError('selected metadata pin changed: ' + name)
    return capture(ref.path, 30_000_000, descriptor=ref, meter=ctx.store.meter)


def csv_records(body):
    reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ContractError('unique CSV columns required')
    rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ContractError('ragged CSV row')
    return rows


def locator(row):
    parsed = urlsplit(row['url'])
    if (parsed.scheme != 'https' or parsed.netloc != HOST or not parsed.path.startswith(PREFIX)
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or parsed.path != PREFIX + 'behavior_ophys_experiment_' + text_id(row['ophys_experiment_id']) + '.nwb'):
        raise ContractError('wrong versioned provider object location')
    if not isinstance(row['version_id'], str) or not row['version_id']:
        raise ContractError('version identity absent')
    digest = row['blake2b_512']
    if not isinstance(digest, str) or len(digest) != 128 or any(c not in '0123456789abcdef' for c in digest):
        raise ContractError('BLAKE2b-512 provider identity required')
    return row['url'], row['version_id'], digest


def context_value(key, value):
    if key == 'passive':
        if value in (True, 'True', 'true'): return True
        if value in (False, 'False', 'false'): return False
        raise ContractError('invalid passive context')
    if key == 'imaging_depth':
        return number(float(value))
    if key == 'session_number':
        if str(value) not in tuple(str(i) for i in range(1, 7)):
            raise ContractError('invalid session number')
        return int(value)
    if not isinstance(value, str) or not value:
        raise ContractError('invalid categorical context')
    return value


def reconcile(roster, manifest, exp_csv, roi_csv):
    rows = roster.get('experiments')
    if not isinstance(rows, list) or len(rows) != 1936 or roster.get('manifest_sha256') != PINS['provider_manifest'][1]:
        raise ContractError('fixed full source roster/provider binding required')
    provider = manifest.get('data_files')
    if not isinstance(provider, dict):
        raise ContractError('provider data_files dictionary schema required')
    exp = {text_id(r['ophys_experiment_id']): r for r in exp_csv}
    if len(exp) != len(exp_csv) or len(exp) != 1936:
        raise ContractError('full unique experiment metadata required')
    expected_rois, seen_roi = {}, set()
    for r in roi_csv:
        eid, rid, cid = (text_id(r[k]) for k in ('ophys_experiment_id','cell_roi_id','cell_specimen_id'))
        if (eid,rid) in seen_roi:
            raise ContractError('duplicate published ROI row')
        seen_roi.add((eid,rid)); expected_rois.setdefault(eid, {})[rid] = cid
    if len(roi_csv) != 133066 or set(expected_rois) != set(exp):
        raise ContractError('full published ROI metadata panel required')
    normalized, seen_exp, source_objects = [], set(), set()
    cre, sessions, containers, lineages = {}, {}, {}, {}
    for row in rows:
        eid = text_id(row['ophys_experiment_id']); mouse = text_id(row['mouse_id'])
        sid, container = text_id(row['ophys_session_id']), text_id(row['ophys_container_id'])
        if eid in seen_exp or eid not in exp:
            raise ContractError('duplicate/foreign source experiment')
        seen_exp.add(eid)
        metadata = exp[eid]
        for key in ('mouse_id','ophys_session_id','ophys_container_id','file_id'):
            if text_id(row[key]) != text_id(metadata[key]):
                raise ContractError('source experiment hierarchy/provider metadata mismatch')
        context = {k: context_value(k, row[k]) for k in CONTEXT}
        if context != {k: context_value(k, metadata[k]) for k in CONTEXT}:
            raise ContractError('published context mismatch')
        for k in ('project_code','session_type'):
            if row[k] != metadata[k]: raise ContractError('all-context identity mismatch')
        if cre.setdefault(mouse, context['cre_line']) != context['cre_line']:
            raise ContractError('mouse crosses Cre groups')
        for mapping, child in ((sessions,sid),(containers,container)):
            if mapping.setdefault(child, mouse) != mouse:
                raise ContractError('session/container crosses biological mouse')
        rois = {text_id(r['cell_roi_id']): text_id(r['cell_specimen_id']) for r in row['rois']}
        if len(rois) != len(row['rois']) or rois != expected_rois[eid]:
            raise ContractError('all published ROI-lineage tuples must match')
        for cid in rois.values():
            if lineages.setdefault(cid, mouse) != mouse:
                raise ContractError('registered lineage crosses biological mouse')
        loc = locator(row)
        if loc in source_objects: raise ContractError('source object alias across experiments')
        source_objects.add(loc)
        item = provider.get(text_id(row['file_id']))
        if not isinstance(item, dict) or (item.get('url'), item.get('version_id'), item.get('file_hash')) != loc:
            raise ContractError('roster URL/version/BLAKE2b differs from exact provider identity')
        if row.get('bytes') is not None:
            raise ContractError('frozen original roster byte field unexpectedly populated')
        normalized.append({'ophys_experiment_id': eid,'mouse_id': mouse,'ophys_session_id':sid,
                           'ophys_container_id':container,'file_id':text_id(row['file_id']),
                           'context':context,'project_code':row['project_code'],'session_type':row['session_type'],
                           'split':row['split'],'url':loc[0],'version_id':loc[1],'blake2b_512':loc[2],
                           'rois':[{'cell_roi_id':r,'cell_specimen_id':c} for r,c in sorted(rois.items())]})
    assignments = split_mice(cre)
    frozen_assignments = {text_id(k):v for k,v in roster['mouse_assignments'].items()}
    if assignments != frozen_assignments or Counter(assignments.values()) != SPLITS:
        raise ContractError('fixed Cre-stratified mouse hash split changed')
    if any(r['split'] != assignments[r['mouse_id']] for r in normalized):
        raise ContractError('experiment split does not follow mouse')
    if len(cre) != 107 or len(sessions) != 703 or len(containers) != 326 or len(lineages) != 50476:
        raise ContractError('complete hierarchy/lineage census mismatch')
    if Counter(r['split'] for r in normalized) != {'fit':1374,'validation':272,'query':290}:
        raise ContractError('fixed experiment split counts changed')
    if Counter(assignments[m] for m in sessions.values()) != {'fit':473,'validation':97,'query':133}:
        raise ContractError('fixed session split counts changed')
    if len(set(r['blake2b_512'] for r in normalized)) != 1936:
        raise ContractError('duplicate complete source body identity across experiments')
    return {'schema':SOURCE_SCHEMA,'source_counts':COUNTS,'experiments':sorted(normalized,key=lambda r:r['ophys_experiment_id']),
            'mouse_assignments':assignments,'containers':326,'registered_lineages':50476,
            'raw_source_bytes':None,'event_count':None}


def selection(ctx):
    bodies = {name: bounded_metadata(ctx,name) for name in PINS}
    provenance = decode(bodies['source_provenance'])
    manifest_pin = provenance.get('source_manifest', {})
    if (manifest_pin.get('bytes'),manifest_pin.get('sha256')) != PINS['provider_manifest']:
        raise ContractError('source provenance manifest identity changed')
    if provenance.get('official_sdk_commit') != 'a56bd8ea7613a812334602b64746cdd30c325a96':
        raise ContractError('captured official source version changed')
    result = reconcile(decode(bodies['source_roster']),decode(bodies['provider_manifest']),
                       csv_records(bodies['experiment_metadata']),csv_records(bodies['roi_metadata']))
    result['source_inputs'] = {k:ctx.inputs[k].object() for k in ctx.inputs}
    result['reuse_sources'] = ctx.parameters.get('reuse_sources', {})
    if not set(result['reuse_sources']) <= {r['ophys_experiment_id'] for r in result['experiments']}:
        raise ContractError('reuse source contains foreign experiment')
    for value in result['reuse_sources'].values():
        ref = Artifact.parse(value)
        if ref.role != 'native_source' or ref.visibility != 'operator':
            raise ContractError('reuse is an explicitly bound operator native source only')
    return result

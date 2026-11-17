"""Complete Kilosort4 preparation contracts; pure metadata, no input/body I/O.

The two public functions validate/compile descriptions, never establish authentic
admission or launch science. The controller separately authenticates every receipt,
namespace, source/environment member and finite reservation before native dispatch.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import re

CANONICAL = "PAPER-paper-method-006"
SCHEMA = "kilosort4_preparation_metadata_v1"
SIMULATION_SHA = "e235f0cb6a54c34abd053b1835e63216c040b9524f6547e994f4ae3ae5f4aef7"
SIMULATION_PIN = {"path": "kilosort/simulation.py", "bytes": 60034, "sha256": SIMULATION_SHA}
WAVEFORM_ROOTS = (
    "671c7ea7-6726-4fbe-adeb-f89c2c8e489b", "eacc49a9-f3a1-49f1-b87f-0972f90ee837",
    "0c828385-6dd6-4842-a702-c5075f5f5e81", "32d27583-56aa-4510-bc03-669036edad20",
    "58c4bf97-ec3b-45b4-9db4-d5d9515d5b00", "cea755db-4eee-4138-bdd6-fc23a572f5a1",
    "68775ca0-b056-48d5-b6ae-a4c2a76ae48f", "d57df551-6dcb-4242-9c72-b806cff5613a",
    "cde63527-7f5a-4cc3-8ac2-215d82e7da26", "fc14c0d6-51cf-48ba-b326-56ed5a9420c3",
    "4ddb8a95-788b-48d0-8a0a-66c7c796da96",
)
HYBRID_ROOTS = ("3f6e25ae-c007-4dc3-aa77-450fd5705046", "fe380793-8035-414e-b000-09bfe5ece92a", "4ddb8a95-788b-48d0-8a0a-66c7c796da96")
SIMULATIONS = ("no_drift", "medium_drift", "high_drift", "fast_drift", "step_drift", "step_aligned")
DIAGNOSTICS = ("F1", "F2", "ED3_real", "linear_probe", "tetrode")
ROLES = frozenset(("common_observation", "constructor_metadata", "common_numeric_resource", "protected_truth", "protected_analysis", "author_source", "transport"))
ASSET_IDS = (44718640, 44718625, 44729887, 44729878, 44729602, 44729869, 44729857, 44729884, 44729881, 44732935)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


class InvalidMetadata(ValueError):
    pass


def _integer(v, name, minimum=0):
    if type(v) is not int or v < minimum:
        raise InvalidMetadata(f"{name}: integer >= {minimum} required")
    return v


def _text(v, name):
    if not isinstance(v, str) or not v or len(v) > 4096 or any(ord(c) < 32 for c in v):
        raise InvalidMetadata(f"{name}: nonempty bounded text required")
    return v


def _rational(v, name, positive=False):
    if not isinstance(v, list) or len(v) != 2:
        raise InvalidMetadata(f"{name}: exact [numerator,denominator] required")
    if type(v[0]) is not int or (positive and v[0] <= 0):
        raise InvalidMetadata(name + ': integer numerator with requested sign required')
    _integer(v[1], name + '.denominator', 1)
    return Fraction(*v)


def _pin(v, name):
    if not isinstance(v, dict) or set(v) != {"path", "bytes", "sha256"}:
        raise InvalidMetadata(f"{name}: exact path/bytes/sha256 pin required")
    _text(v['path'], name + '.path')
    _integer(v['bytes'], name + '.bytes')
    if not isinstance(v['sha256'], str) or SHA_RE.fullmatch(v['sha256']) is None:
        raise InvalidMetadata(f"{name}: lowercase SHA256 required")
    return deepcopy(v)


def _rows(v, name, maximum=100000):
    if not isinstance(v, list) or len(v) > maximum:
        raise InvalidMetadata(f"{name}: bounded list required")
    if any(not isinstance(row, dict) for row in v):
        raise InvalidMetadata(f"{name}: objects required")
    return v


def _unique(rows, name, key='id'):
    ids = [_text(r.get(key), name + '.' + key) for r in rows]
    if len(ids) != len(set(ids)):
        raise InvalidMetadata(f"{name}: duplicate identities")
    return {r[key]: r for r in rows}


def _gap(out, code, category, reason, scope):
    row = {"id": code, "category": category, "reason": reason, "scope": scope}
    if row not in out:
        out.append(row)


def _proof(row, key, gaps, scope):
    """Validate a receipt descriptor, never treat the descriptor as proof of its body."""
    p = row.get(key)
    if p is None:
        _gap(gaps, 'evidence:' + scope + ':' + key, 'missing-source-evidence', 'Missing authenticated receipt descriptor: ' + key, scope)
        return None
    return _pin(p, scope + '.' + key)


def validate_view(view):
    """Validate one complete signal-view descriptor without touching any payload."""
    if not isinstance(view, dict):
        raise InvalidMetadata('view must be an object')
    for key in ('id', 'root_id', 'source_version', 'format', 'dtype', 'units'):
        _text(view.get(key), 'view.' + key)
    if view.get('byte_order') not in ('little', 'big', 'not-applicable'):
        raise InvalidMetadata('view.byte_order')
    n = _integer(view.get('n_samples'), 'view.n_samples', 1)
    c = _integer(view.get('n_channels'), 'view.n_channels', 1)
    if c > 32768 or n > 2**63-1:
        raise InvalidMetadata('native descriptor extent exceeds finite admission bounds')
    fs = _rational(view.get('sample_frequency'), 'view.sample_frequency', True)
    origin = _rational(view.get('time_origin'), 'view.time_origin')
    if _rational(view.get('duration'), 'view.duration', True) != Fraction(n, 1) / fs:
        raise InvalidMetadata('view duration does not equal complete sample extent / frequency')
    _rational(view.get('scale'), 'view.scale', True)
    _pin(view.get('signal_pin'), 'view.signal_pin')
    _pin(view.get('channel_geometry_pin'), 'view.channel_geometry_pin')
    channels = view.get('neural_channels')
    sync = view.get('sync_channels')
    if not isinstance(channels, list) or not isinstance(sync, list) or not channels:
        raise InvalidMetadata('view channel partition required')
    for x in channels + sync:
        _integer(x, 'channel')
    if set(channels) & set(sync) or len(set(channels + sync)) != c or set(channels + sync) != set(range(c)):
        raise InvalidMetadata('every stored channel must appear once in neural/sync partition')
    transform = view.get('transform')
    if not isinstance(transform, dict) or transform.get('kind') not in ('identity', 'injection', 'stride2'):
        raise InvalidMetadata('view.transform explicit identity, injection or stride2 required')
    if transform['kind'] != 'identity':
        _text(transform.get('parent_view'), 'view.transform.parent_view')
        _pin(transform.get('source_definition'), 'view.transform.source_definition')
    if view.get('complete_original_support') is not True:
        raise InvalidMetadata('view must retain complete original support; excerpts are not queries')
    # This key is content identity only after the controller verifies the referenced bodies.
    identity = {'signal': view['signal_pin'], 'geometry': view['channel_geometry_pin'], 'frequency': view['sample_frequency'], 'origin': view['time_origin'], 'transform': transform, 'n_samples': n, 'n_channels': c, 'scale': view['scale']}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_unit_roles(rows, kind):
    """Source-class role join; physical order is deliberately irrelevant."""
    units = _rows(rows, 'units', 100000)
    _unique(units, 'units')
    target, background = [], []
    for u in units:
        role = u.get('evaluation_role')
        source_class = u.get('source_class')
        if role == 'positive_single_unit' and source_class in ('injected_single', 'designated_single', 'biophysical_single'):
            target.append(u['id'])
        elif role == 'construction_background' and source_class == 'multi_unit_generator':
            background.append(u['id'])
        else:
            raise InvalidMetadata('unit source-class/evaluation-role mismatch')
        _pin(u.get('source_role_receipt'), 'unit.source_role_receipt')
    if kind == 'hybrid' and (len(target) != 100 or background or any(u['source_class'] != 'injected_single' for u in units)):
        raise InvalidMetadata('hybrid must retain exactly100 injected positive units; natural units remain unlabeled')
    if kind == 'synthetic' and (len(target) != 600 or len(background) != 600 or any(u['source_class'] not in ('designated_single','multi_unit_generator') for u in units)):
        raise InvalidMetadata('synthetic must retain600 designated single targets AND600 background generators')
    if kind == 'biophysical' and (not target or background or any(u['source_class'] != 'biophysical_single' for u in units)):
        raise InvalidMetadata('complete admitted biophysical single-unit roster required; do not assume caption250')
    if kind not in ('hybrid', 'synthetic', 'biophysical'):
        raise InvalidMetadata('unknown truth-supported case kind')
    return {'positive_ids': target, 'background_ids': background, 'positive_count': len(target), 'background_count': len(background)}


def _inventory(metadata, gaps):
    """Complete source membership and lineage, not merely reported counts."""
    source = metadata.get('construction', {})
    if not isinstance(source, dict):
        raise InvalidMetadata('construction must be object')
    drift = _unique(_rows(source.get('drift_recordings', []), 'drift_recordings', 512), 'drift_recordings')
    wave = _unique(_rows(source.get('waveform_recordings', []), 'waveform_recordings', 11), 'waveform_recordings')
    trajectories = _unique(_rows(source.get('waveform_trajectories', []), 'waveform_trajectories', 597), 'waveform_trajectories')
    isi = _unique(_rows(source.get('isi_donors', []), 'isi_donors', 1497), 'isi_donors')
    for name, have, expected in [('drift_recordings', len(drift),512),('waveform_recordings',len(wave),11),('waveform_trajectories',len(trajectories),597),('isi_donors',len(isi),1497)]:
        if have != expected:
            _gap(gaps, 'membership:' + name, 'missing-source-definition', f'Complete original membership required: {have}/{expected}; no denominator reduction', name)
    if wave and set(wave) != set(WAVEFORM_ROOTS):
        raise InvalidMetadata('waveform recording roster differs from explicit original11 IDs')
    if not set(wave).issubset(drift):
        _gap(gaps, 'membership:waveform-drift-join', 'missing-source-evidence', 'All11 waveform roots must join the original512 drift study', 'source-lineage')
    boundary = source.get('starting_boundary')
    if boundary not in ('original_processed_IBL', 'regenerated_upstream_pyKilosort'):
        _gap(gaps, 'boundary:IBL', 'missing-source-definition', 'Freeze authentic original processed/raw boundary; downstream reproduction does not imply upstream sorting replay', 'G02/G03')
    for name, rows in [('drift_recordings',drift),('waveform_recordings',wave)]:
        for row in rows.values():
            _proof(row, 'source_membership_receipt', gaps, name + '/' + row['id'])
            _proof(row, 'original_input_pin', gaps, name + '/' + row['id'])
            _proof(row, 'processing_lineage_receipt', gaps, name + '/' + row['id'])
    for name, rows in [('waveform_trajectories', trajectories),('isi_donors',isi)]:
        for row in rows.values():
            if row.get('recording_id') not in wave:
                raise InvalidMetadata(name + ': donor must join one original waveform source recording')
            _text(row.get('source_unit_id'), name + '.source_unit_id')
            _proof(row, 'selection_receipt', gaps, name + '/' + row['id'])
            _proof(row, 'payload_pin', gaps, name + '/' + row['id'])
    if boundary == 'regenerated_upstream_pyKilosort':
        _proof(source, 'upstream_source_environment', gaps, 'G02/G03')
        _proof(source, 'upstream_complete_graph', gaps, 'G02/G03')
    return {'drift_recordings': list(drift), 'waveform_recordings': list(wave), 'waveform_trajectories': list(trajectories), 'isi_donors': list(isi), 'starting_boundary': boundary}


def prepare_manifest(metadata):
    """Return a full-scope preparation description with explicit missing gates.

    A metadata-consistent response still has execution_admitted=False. The outer
    controller must authenticate receipt bodies/issuer and actual payload facts;
    placing True in metadata cannot close those gates.
    """
    gaps = []
    try:
        if not isinstance(metadata, dict) or metadata.get('schema') != SCHEMA or metadata.get('canonical_id') != CANONICAL:
            raise InvalidMetadata('wrong preparation schema/canonical ID')
        if any(k in metadata for k in ('scores','truth_values','events','model_weights')):
            raise InvalidMetadata('preparation accepts descriptors, not numerical payloads')
        # Caller must size-limit the serialized document before parsing it. This
        # second bound limits post-parse traversal and output amplification.
        nbytes = len(json.dumps(metadata, allow_nan=False, separators=(',', ':')).encode())
        if nbytes > 16 * 1024 * 1024:
            raise InvalidMetadata('metadata exceeds16MiB description bound')
        assets = _unique(_rows(metadata.get('assets',[]), 'assets',10000), 'assets')
        for a in assets.values():
            if a.get('role') not in ROLES:
                raise InvalidMetadata('unknown asset role')
            _pin(a.get('pin'), 'asset.pin')
            _text(a.get('source_version'), 'asset.source_version')
            _proof(a, 'source_identity_receipt', gaps, 'asset/' + a['id'])
            if a.get('role') == 'common_numeric_resource':
                if a.get('access_arms') != ['A','B']:
                    raise InvalidMetadata('numeric resources must have identical A/B access')
                _proof(a, 'provenance_receipt', gaps, 'asset/' + a['id'])
            if a.get('role') == 'author_source' and a.get('access_arms') != ['B']:
                raise InvalidMetadata('selected author code is B-only')
            if a.get('role') in ('protected_truth','protected_analysis') and a.get('I_candidate_access') is not False:
                raise InvalidMetadata('I candidate cannot receive truth/analysis roles')
        declared = metadata.get('janelia_objects', [])
        if not isinstance(declared,list) or any(type(x) is not int for x in declared):
            raise InvalidMetadata('janelia_objects must contain integer publisher file IDs')
        if len(declared) != len(set(declared)):
            raise InvalidMetadata('duplicate Janelia objects')
        if set(declared) != set(ASSET_IDS):
            _gap(gaps,'source:Janelia-ten','missing-source-evidence','All ten original source objects and later full integrity/member roles remain mandatory','G01')
        _proof(metadata, 'historical_janelia_doi_join', gaps, '25006970-to-25298815v1')
        construction = _inventory(metadata,gaps)
        views = _unique(_rows(metadata.get('views',[]),'views',10000),'views')
        identities = {k:validate_view(v) for k,v in views.items()}
        for v in views.values():
            for key in ('native_admission_receipt','integrity_receipt','source_identity_receipt'):
                _proof(v,key,gaps,'view/' + v['id'])
            t = v['transform']
            if t['kind'] != 'identity' and t['parent_view'] not in views:
                raise InvalidMetadata('transformed view lacks original parent view')
            if t['kind'] == 'stride2':
                parent = views[t['parent_view']]
                if v['sample_frequency'] != [32000,1] or parent['sample_frequency'] != [32000,1]:
                    raise InvalidMetadata('biophysical normal/twice sorting clocks must be32000Hz')
                if v['n_samples'] != (parent['n_samples']+1)//2:
                    raise InvalidMetadata('stride2 full view must retain every second sample from index0')
                if t.get('truth_time_scale') != [1,2] or t.get('truth_rounding') != 'none':
                    raise InvalidMetadata('twice-speed truth must retain exact half-sample positions; no rounding')
                _proof(t,'odd_sample_policy_receipt',gaps,'stride2/' + v['id'])
        cases = _unique(_rows(metadata.get('cases',[]),'cases',11),'cases')
        support = []
        kinds = Counter()
        sim_names=[]; hybrid_roots=[]; bio_modes=[]
        for case in cases.values():
            kind = case.get('kind');kinds[kind]+=1
            if case.get('view_id') not in views:
                raise InvalidMetadata('case lacks complete view')
            v=views[case['view_id']]
            roles=validate_unit_roles(case.get('units'),kind)
            _proof(case,'complete_roster_receipt',gaps,'case/'+case['id'])
            _proof(case,'truth_clock_receipt',gaps,'case/'+case['id'])
            if kind=='synthetic':
                sim_names.append(case.get('condition'))
                if v['duration'] != [2700,1]:
                    raise InvalidMetadata('all six synthetic cases require full45minutes')
                _proof(case,'publication_configuration_receipt',gaps,'case/'+case['id'])
            elif kind=='hybrid':
                hybrid_roots.append(case.get('original_recording_id'))
                if v['transform']['kind'] != 'injection':
                    raise InvalidMetadata('hybrid must preserve distinct injected and raw-background views')
                if case.get('original_recording_id') != views[v['transform']['parent_view']]['root_id']:
                    raise InvalidMetadata('hybrid archive-to-original-background join mismatch')
            else:
                mode=case.get('condition');bio_modes.append(mode)
                if mode not in ('normal','twice_speed') or v['transform']['kind'] != ('identity' if mode=='normal' else 'stride2'):
                    raise InvalidMetadata('biophysical condition/transform mismatch')
                _proof(case,'immutable_dandi_assets_receipt',gaps,'case/'+case['id'])
            support.append({'id':case['id'],'kind':kind,'condition':case.get('condition'),'view_id':case['view_id'],'content_identity':identities[case['view_id']],**roles})
        if kinds != Counter({'hybrid':3,'synthetic':6,'biophysical':2}) or set(sim_names)!=set(SIMULATIONS) or set(hybrid_roots)!=set(HYBRID_ROOTS) or set(bio_modes)!={'normal','twice_speed'}:
            _gap(gaps,'case:core11','missing-source-evidence','Exactly three original hybrids, six original full simulations and both paired biophysical views required','I-core')
        if len(sim_names)!=len(set(sim_names)) or len(hybrid_roots)!=len(set(hybrid_roots)) or len(bio_modes)!=len(set(bio_modes)):
            raise InvalidMetadata('repeated condition cannot replace missing original case')
        steps={c.get('condition'):c for c in cases.values() if c.get('condition') in ('step_drift','step_aligned')}
        if len(steps)==2:
            left,right=steps['step_drift'],steps['step_aligned']
            for key in ('waveform_identity_pin','spike_draw_pin','norm_pin','drift_pin','whitening_pin'):
                _pin(left.get(key),'step.'+key);_pin(right.get(key),'aligned.'+key)
                if left[key] != right[key]:
                    raise InvalidMetadata('step/aligned must share '+key+'; geometry is the differing branch')
            if views[left['view_id']]['channel_geometry_pin']==views[right['view_id']]['channel_geometry_pin']:
                raise InvalidMetadata('step/aligned probe geometry distinction lost')
        diagnostics=_rows(metadata.get('diagnostics',[]),'diagnostics',10000)
        covered=set()
        for d in diagnostics:
            if d.get('obligation') not in DIAGNOSTICS or d.get('view_id') not in views:
                raise InvalidMetadata('unknown diagnostic or missing view')
            covered.add(d['obligation']);_proof(d,'original_support_receipt',gaps,'diagnostic/'+d['obligation'])
        if covered != set(DIAGNOSTICS):
            _gap(gaps,'diagnostics:roots','missing-source-evidence','Fig1/Fig2/ED3real/linear/tetrode full roots and any additional source-selected example/PC roots remain mandatory','I-diagnostics')
        _proof(metadata,'complete_diagnostic_roster_receipt',gaps,'all-original-I-diagnostics')
        query_views = {x['view_id'] for x in support} | {d['view_id'] for d in diagnostics}
        content_groups={}
        for vid in sorted(query_views):content_groups.setdefault(identities[vid],[]).append(vid)
        # Dedup is merely proposed: physical identity and transform receipts still
        # require controller authentication, including absent extra example roots.
        _gap(gaps,'admission:authentic-body','future-qualification','Metadata consistency never authenticates payload/header/truth/source or receipt bodies; owner admission required','all')
        _gap(gaps,'admission:physical-isolation','future-qualification','A/B and R/I packets, fresh workers, no scores/state feedback and finite resources require actual qualification','all')
        return {'schema':'kilosort4_prepared_manifest_v1','status':'required-unscorable' if gaps else 'metadata-consistent','canonical_id':CANONICAL,'execution_admitted':False,'actual_input_operations':0,'gaps':gaps,'result':{'construction':construction,'cases':support,'views':deepcopy(list(views.values())),'assets':deepcopy(list(assets.values())),'diagnostics':deepcopy(diagnostics),'proposed_content_groups':content_groups,'J_I':None,'J_I_metadata_lower_bound':len(content_groups),'all_original_support_required':True,'no_independence_assumption':True}}
    except (InvalidMetadata,TypeError,ValueError,KeyError,OverflowError) as exc:
        return {'schema':'kilosort4_prepared_manifest_v1','status':'invalid-input','canonical_id':CANONICAL,'execution_admitted':False,'actual_input_operations':0,'gaps':[{'id':'invalid-metadata','category':'schema','reason':str(exc),'scope':'request'}],'result':None}


# These are exact available source entry points, not reconstructed publication
# callers. Unknown producer branches cannot be filled by an arbitrary callback.
SOURCE_RECIPES = {
 'waveform_preprocess_source': {'function':'preprocess_wfs_sts','line':15,'inputs':['waveform_archive','y_chan','x_chan','y_chan_up','x_chan_up'],'parameters':['ups','device'],'outputs':['wfs','wfs_x','contaminations','sts','cls'],'differences':['sourceups10 versus paperups100','source nsts>50 strict per-bin selection versus prose minimum wording','actual597/1497 lineage not authenticated'],'source_failure_conditions':['pickled object-array admission','empty trains, unsupported rank or zero normalization undefined'],'families':['G03']},
 'synthetic_source': {'function':'create_simulation','line':365,'inputs':['st','cl','wfs','wfs_x','contaminations','whiten_mat'],'parameters':['filename','n_sim','n_noise','n_batches','batch_size','tsig','tpad','n_chan_bin','drift','drift_range','drift_seed','fast','step','ups'],'outputs':['st_sim','cl_sim','amp_sim','wf_sim','cb_sim','wfid_sim','drift_sim_ups'],'differences':['source defaults100/1000 andups10 versus paper600/600 andups100','source computes clipped20X but writesX; paper200X/int16','noise_next=noise_init literal assignment','source output extent follows last retained event, not full duration proof'],'source_failure_conditions':['whiten_mat conversion beforeNone guard','BinaryRWFile unsupported n_samples keyword after full signal allocation','source source-unit loops may leave zero templates after emptyISI'],'families':['G05']},
 'hybrid_waveforms_source': {'function':'waveforms_from_recording','line':452,'inputs':['filename_bg','chan_map'],'parameters':['NT','n_chan_bin','nt','twav_min'],'outputs':['wfs','cinds','chan0'],'differences':['native reads background/kilosort4 products, not authenticated historicalpyKilosort lineage'],'source_failure_conditions':['source globals ntw/tw/ptw retained','quality-array label alignment must be admitted','zero per-unit waveform count normalization undefined'],'families':['G03','G04']},
 'hybrid_source': {'function':'hybrid_simulation','line':625,'inputs':['filename_bg','wfs','cinds','chan0'],'parameters':['sim_name','n_batches_sim'],'outputs':['data','st_sim','cl_sim','ci_sim','wf_sim','cb_sim'],'differences':['source hardcoded probe and outputpaths retained','background and injected views remain distinct','native100 injected units, full source duration caller unknown'],'source_failure_conditions':['10000 random/spike buffers can overflow','BinaryRWFile unsupportedn_samples','source hardcoded probe must be mounted exactly','injection-array int16 arithmetic can overflow before laterclipping'],'families':['G04']},
}
MISSING_PRODUCERS = (
 ('drift512_original','G02','Exact512 membership, processed/raw input boundary, originalpyKilosort outputs/version, nine-position drift statistic source/percentile policy and complete invocation'),
 ('waveforms11_original','G03','Exact11 raw extraction producers;597waveform1497ISI selection/whitening/source-unit lineage; capturedKS4 consumer is not historicalpyKilosort proof'),
 ('synthetic_paper','G05','Complete600/600,ups100,200X/clippedint16 publication caller; originalRNG/seeds/condition parameters and reviewed writer/noise/extent semantics'),
 ('hybrid_paper','G04','Original three archive/root/full-duration joins; waveform/source sorter provenance, injection capacity/arithmetic/writer and exact historical invocation'),
 ('biophysical_admission','G10','Immutable DANDI000028 version/files/nativegeometry and normal/twice-speed clock/odd-index transform source'),
 ('real_and_other_probes','G09/G11','Fig1 locator7666892↔25232962/1, Fig2/ED3real exact files; complete linear/tetrode immutable versions/session roots and preprocessors'),
 ('historical_comparators','G06/G07/G08','All per-panel versions/wrappers/grids/ablations and exact supporting constructors; eleven-name union must not be guessed into historical matrix'),
 ('all_figure_producers','G21','All71 panel/GUI constructors including windows, embeddings, bins, norms/T2P, runtime methodology,34Methods/Table1 and reporting obligations'),
 ('older_methods_supplement','G06/G10/G21','SUP01–13 original Kilosort2/2.5/3 source, initialization/optimizer/recursion/settings withEQ01/EQ02/OPT01 unresolved; never substituteKS4'),
)


def constructor_plan(metadata):
    """Compile exact available native source recipes, retain all missing branches.

    No supplied callback/executable can mark an unknown historical constructor
    complete. A new reviewed source profile and implementation are needed.
    """
    prepared = prepare_manifest(metadata)
    recipes=[]
    for operation,spec in SOURCE_RECIPES.items():
        recipes.append({'operation':operation,'status':'source-adapter-present-unqualified','source_pin':deepcopy(SIMULATION_PIN),'module':'kilosort.simulation','function':spec['function'],'source_line':spec['line'],'native_bridge':'preparation/native_bridge.py','bridge_entrypoint':'run_constructor(request)','fixed_argv':['/environment/python3','-I','/opt/k4bench/preparation/native_bridge.py','/run/request.json'],'source_members':{'path':'NATIVE_SOURCE_MEMBERS.json','sha256':'b4639a6b1d723b38b52ef4ea4d378dbb07717e374176051fea6ae392894fb66c','meaning':'all17 directly/imported core Python source members, reverified before native import'},'settings':{'policy':'all effective parameters below are mandatory; no implicit defaults','source_global_constants':{'NT':60000,'fs':30000,'nt':61,'twav_min':20,'tw':121,'ntw':50,'ptw':91},'publication_override_admission':'unresolved'},'output_roles':{x:'protected_constructor_output' for x in spec['outputs']},'resource_requirements':['positive finite input/source authentication reads','full native RAM/GPU/CPU/wall/scratch/output quotas','implicit native sidecars and all side-effect outputs','complete serializations and terminal receipt reserve'],'gaps':spec['differences']+spec['source_failure_conditions'],'input_roles':{x:('common_numeric_resource' if x in ('wfs','wfs_x','contaminations','whiten_mat','waveform_archive') else 'constructor_metadata' if x in ('chan_map','y_chan','x_chan','y_chan_up','x_chan_up') else 'protected_truth' if x in ('st','cl','cinds','chan0') else 'common_observation') for x in spec['inputs']},'inputs':spec['inputs'],'parameters':spec['parameters'],'outputs':spec['outputs'],'source_differences':spec['differences'],'preserved_source_failure_conditions':spec['source_failure_conditions'],'graph_families':spec['families'],'required_before_dispatch':['authentic input/full-support/clock/role admission','exact source family plus pinned native environment','authenticated complete literal invocation andRNGstate','outer controller authority and physical isolation','finite full-allocation/read/write/CPU/GPU/time/scratch/log reservation','complete native output and failure retention'],'execution_admitted':False})
    gaps=[{'id':'producer:'+name,'category':'missing-scientific-definition-and-concrete-producer','scope':family,'reason':why} for name,family,why in MISSING_PRODUCERS]
    gaps += deepcopy(prepared['gaps'])
    return {'schema':'kilosort4_constructor_plan_v1','canonical_id':CANONICAL,'status':'invalid-input' if prepared['status']=='invalid-input' else 'required-unscorable','execution_admitted':False,'software_complete':False,'prepared_manifest':prepared,'source_recipes':recipes,'gaps':gaps,'complete_obligations':{'main_figures':5,'extended_data_figures':7,'panel_GUI':71,'methods_sections':34,'supplement_methods':13,'source_drift_roots':512,'waveform_roots':11,'waveform_trajectories':597,'isi_donors':1497,'hybrid_cases':3,'synthetic_cases':6,'biophysical_views':2},'resource_formulae':{'one_full_signal_float32':'4*T_alloc*385;T_alloc source-derived, not assumed2700*30000','optional_second_MUA_signal':'onlygenerate_spikes n_batches_sim is explicitly non-None;create_simulation doesnotpassit','one_hybrid_injection_int16':'2*NT*n_batches_sim*385','noise':'initial plus each batch: NT*96*4 real and12 FFTgroup intermediates, unwhitening andblend','all_retained':'original+decoded+generated+source+truth+failurelogs+outputs+peak scratch; immutable reuse only'}}

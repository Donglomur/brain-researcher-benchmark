"""Pure operator-private support planning; no files, fits, targets or scoring.

plan() admits the frozen canonical metadata and a complete supplied projection.
It does NOT authenticate that projection against original/G1 mapping bytes.
A separately selected trusted preparation/runtime must establish that custody.
"""
import collections
import hashlib
import itertools
import json

CANONICAL_SHA256 = '27a86a0d3065c06f9d2b7b509bc0ee3b0775cf3b58b810a917c4aba37d7f2e66'
SEEDS = (2026110700, 2026110701, 2026110702, 2026110703, 2026110704)
DOMAIN = 'neural094-pairwise-region-unit-rank-v1'


class Refused(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Refused(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def exact(obj, fields, name):
    need(type(obj) is dict and set(obj) == set(fields), name)


def _pairs(rows):
    out = {}
    for key, value in rows:
        need(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def strict(raw):
    def bad(value):
        raise Refused('nonstandard JSON constant: ' + value)
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Refused('invalid JSON') from error


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('ascii')


def _fingerprint(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _validated_catalog(obj):
    """Internal generic seam for tiny invented fixtures; not an admission API."""
    need(type(obj) is dict, 'catalog object')
    labels, sessions, mice = obj['labels'], obj['sessions'], obj['mice']
    need(type(labels) is list and len(labels) >= 2, 'full literal-label roster')
    raw = []
    totals = [0, 0]
    for label in labels:
        exact(label, ('raw_label', 'qc2_count', 'qc3_count'), 'label fields')
        name = label['raw_label']
        need(type(name) is str, 'literal label string')
        try:
            name.encode('utf-8')
        except UnicodeError as error:
            raise Refused('invalid Unicode label') from error
        need(integer(label['qc2_count']) and integer(label['qc3_count']), 'label counts')
        need(label['qc2_count'] + label['qc3_count'] > 0, 'observed-label support')
        totals[0] += label['qc2_count']; totals[1] += label['qc3_count']
        raw.append(name)
    need(raw == sorted(set(raw)), 'ordered unique literal labels; no stripping')
    need(type(sessions) is list and len(sessions) > 0, 'full session roster')
    expected_mice = []
    names = []
    for ordinal, session in enumerate(sessions, 1):
        exact(session, ('ordinal', 'session', 'mouse', 'unit_count', 'source_cluster_rows', 'channel_count'), 'session fields')
        need(type(session['ordinal']) is int and session['ordinal'] == ordinal, 'ordered ordinal')
        need(type(session['session']) is str and session['session'] != '' and type(session['mouse']) is str and session['mouse'] != '', 'source identity')
        need(all(integer(session[k], 1) for k in ('unit_count', 'source_cluster_rows', 'channel_count')), 'session extents')
        need(session['unit_count'] <= session['source_cluster_rows'], 'retained source rows')
        names.append(session['session'])
        if session['mouse'] not in expected_mice:
            expected_mice.append(session['mouse'])
    need(len(names) == len(set(names)) and type(mice) is list and mice == expected_mice, 'full ordered mice/session identities')
    need(type(obj['fixed_seeds']) is list and all(type(s) is int for s in obj['fixed_seeds']) and tuple(obj['fixed_seeds']) == SEEDS, 'five frozen unit-selection seeds')
    t = obj['totals']
    expected = {'sessions':len(sessions), 'mice':len(mice), 'labels':len(labels), 'unordered_pairs':len(labels)*(len(labels)-1)//2, 'unit_count':sum(s['unit_count'] for s in sessions), 'qc2_count':totals[0], 'qc3_count':totals[1], 'source_cluster_rows':sum(s['source_cluster_rows'] for s in sessions), 'channel_count':sum(s['channel_count'] for s in sessions)}
    need(type(t) is dict and set(t) == set(expected) and all(type(t[k]) is int and t[k] == v for k,v in expected.items()), 'complete canonical totals')
    need(t['unit_count'] == sum(totals), 'complete QC inventory')
    return obj


def plan(canonical_bytes, inventory):
    """Only production entry: frozen metadata + full operator-projected inventory.

    inventory = [{'ordinal':1, 'units':[{'unit':0,'source_qc_code':2,
                    'raw_label':'literal'}, ...]}, ... all39].
    Extra activity, target, choice, reward, coordinate or execution fields refuse.
    Source authentication is a mandatory future caller duty, not a JSON flag.
    """
    need(type(canonical_bytes) is bytes and hashlib.sha256(canonical_bytes).hexdigest() == CANONICAL_SHA256, 'frozen canonical metadata pin')
    catalog = strict(canonical_bytes)
    need(catalog['schema'] == 'neural094_pairwise_canonical_inventory_v1' and catalog['task'] == 'NEURAL-094' and catalog['original_whole_population_task_unchanged'] is True, 'canonical scientific scope')
    return _compile(_validated_catalog(catalog), inventory, CANONICAL_SHA256)


def _compile(catalog, inventory, canonical_sha='invented-fixture-only'):
    """Internal pure construction; callers must use plan for canonical metadata."""
    _validated_catalog(catalog)
    need(type(inventory) is list and len(inventory) == len(catalog['sessions']), 'complete session inventory')
    names = tuple(x['raw_label'] for x in catalog['labels'])
    indices = {name:i for i,name in enumerate(names)}
    global_qc = [[0,0] for _ in names]
    groups = []
    for ordinal, (expected, row) in enumerate(zip(catalog['sessions'], inventory), 1):
        exact(row, ('ordinal', 'units'), 'projected session fields')
        need(type(row['ordinal']) is int and row['ordinal'] == ordinal, 'complete inventory ordinal')
        units = row['units']
        need(type(units) is list and len(units) == expected['unit_count'], 'complete retained unit roster including silent units')
        current = [[] for _ in names]
        for alias, unit in enumerate(units):
            exact(unit, ('unit', 'source_qc_code', 'raw_label'), 'metadata-only projected unit')
            need(type(unit['unit']) is int and unit['unit'] == alias, 'dense unique original unit aliases')
            qc, label = unit['source_qc_code'], unit['raw_label']
            need(type(qc) is int and qc in (2,3), 'QC2 or QC3 inventory')
            need(type(label) is str and label in indices, 'canonical literal label')
            index = indices[label]
            current[index].append((alias,qc))
            global_qc[index][qc-2] += 1
        groups.append(tuple(tuple(x) for x in current))
    expected_qc = [[x['qc2_count'],x['qc3_count']] for x in catalog['labels']]
    need(global_qc == expected_qc, 'all literal-label QC counts and33997 inventory accounting')
    return _Plan(catalog, tuple(groups), canonical_sha)


class _Plan:
    """Immutable input snapshots; cached ranks contain only operator metadata."""
    def __init__(self, catalog, groups, canonical_sha):
        self._labels = tuple(x['raw_label'] for x in catalog['labels'])
        self._sessions = tuple((x['ordinal'], x['session'], x['mouse'], x['unit_count']) for x in catalog['sessions'])
        self._mice = tuple(catalog['mice'])
        self._groups = groups
        self._pairs = tuple(itertools.combinations(range(len(self._labels)),2))
        self._canonical_sha = canonical_sha
        self._rank_cache = {}

    def summary(self):
        supported = sum(bool(self._groups[s][a]) and bool(self._groups[s][b]) for a,b in self._pairs for s in range(len(self._sessions)))
        return {'schema':'neural094_pairwise_support_plan_summary_v1', 'component_status':'source_component_not_a_complete_benchmark', 'execution_selected':False, 'scientific_qualification':False, 'inventory_source_authenticated':False, 'trusted_full_mapping_and_trial_admission_required':True, 'canonical_metadata_sha256':self._canonical_sha, 'literal_labels':len(self._labels), 'unordered_pairs':len(self._pairs), 'sessions':len(self._sessions), 'mice':len(self._mice), 'recording_unit_rows_accounted':sum(x[3] for x in self._sessions), 'pair_session_cells':len(self._pairs)*len(self._sessions), 'structurally_supported_pair_session_cells':supported, 'unavailable_pair_session_cells':len(self._pairs)*len(self._sessions)-supported, 'fixed_unit_selection_seeds':list(SEEDS), 'regional_candidate_fit_infer_jobs':supported*len(SEEDS)*2, 'matched_regional_reference_jobs':supported*len(SEEDS)*2, 'shared_trusted_context_session_jobs':len(self._sessions), 'fit_infer_jobs_are_counts_not_compute_or_execution_admission':True, 'all_inventory_used_across_five_subsets_claim':False}

    def _pair(self, index):
        need(integer(index) and index < len(self._pairs), 'canonical pair index')
        return self._pairs[index]

    def pair(self, index):
        a,b = self._pair(index)
        rows, mask = [], []
        for s, (ordinal,session,mouse,_) in enumerate(self._sessions):
            left, right = self._groups[s][a], self._groups[s][b]
            nleft,nright = len(left),len(right)
            k = min(nleft,nright)
            status = 'supported_pending_execution' if k else 'unavailable_both_regions' if not (nleft or nright) else 'unavailable_left_region' if not nleft else 'unavailable_right_region'
            mask.append(k>0)
            rows.append({'ordinal':ordinal, 'session':session, 'mouse':mouse, 'left_QC2_QC3':[sum(q==2 for _,q in left),sum(q==3 for _,q in left)], 'right_QC2_QC3':[sum(q==2 for _,q in right),sum(q==3 for _,q in right)], 'K':k, 'structural_status':status, 'execution_status':'not_run' if k else 'not_applicable', 'same_original_trials_window_context_wheel_required':True})
        mouse_rows = []
        for mouse in self._mice:
            ordinals = [r['ordinal'] for r in rows if r['mouse']==mouse and r['K']>0]
            mouse_rows.append({'mouse':mouse, 'structurally_supported':bool(ordinals), 'planned_session_ordinals':ordinals, 'n_sessions':len(ordinals), 'execution_status':'not_run' if ordinals else 'structurally_unavailable'})
        ks = collections.Counter(r['K'] for r in rows)
        positive = collections.Counter(r['K'] for r in rows if r['K']>0)
        return {'schema':'neural094_pairwise_support_row_v1', 'pair_index':index, 'left_literal_label':self._labels[a], 'right_literal_label':self._labels[b], 'orientation':'right_log_loss_minus_left_log_loss; positive_favors_left_descriptive_only', 'structural_status':'supported_pending_execution' if any(mask) else 'structurally_unavailable_all_sessions', 'session_roster':rows, 'session_support_mask':mask, 'n_session':sum(mask), 'mouse_roster':mouse_rows, 'mouse_support_mask':[r['structurally_supported'] for r in mouse_rows], 'n_mouse':sum(r['structurally_supported'] for r in mouse_rows), 'K_histogram_all_sessions':[[k,ks[k]] for k in sorted(ks)], 'K_histogram_supported_sessions':[[k,positive[k]] for k in sorted(positive)], 'fixed_seeds':list(SEEDS), 'execution_failures_may_change_support_denominator':False, 'aggregate_status':'not_run' if any(mask) else 'structurally_unavailable', 'score_or_positive_effect_reward':None}

    def iter_pairs(self):
        for i in range(len(self._pairs)):
            yield self.pair(i)

    def _rank(self, session_index, label_index, seed):
        key = session_index,label_index,seed
        if key not in self._rank_cache:
            ordinal, session, _, _ = self._sessions[session_index]
            label = self._labels[label_index]
            def ranked(unit):
                alias,qc = unit
                # QC is deliberately absent from the ranking key; no activity,
                # outcome, counterpart region, K or pair index enters the rank.
                digest = hashlib.sha256(_encoded([DOMAIN,self._canonical_sha,ordinal,session,label,seed,alias])).digest()
                return digest,alias
            self._rank_cache[key] = tuple(sorted(self._groups[session_index][label_index],key=ranked))
        return self._rank_cache[key]

    def select(self, pair_index, session_ordinal, seed):
        a,b = self._pair(pair_index)
        need(integer(session_ordinal,1) and session_ordinal <= len(self._sessions), 'session ordinal')
        need(type(seed) is int and seed in SEEDS, 'one of five frozen seeds')
        s = session_ordinal-1
        k = min(len(self._groups[s][a]),len(self._groups[s][b]))
        if not k:
            return {'pair_index':pair_index,'session_ordinal':session_ordinal,'seed':seed,'K':0,'status':'structurally_unavailable','left':None,'right':None,'execution_selected':False}
        sides=[]
        for i in (a,b):
            full = self._groups[s][i]
            ranked = self._rank(s,i,seed)
            subset = tuple(sorted(ranked[:k]))
            aliases = [alias for alias,qc in subset]
            sides.append({'literal_label':self._labels[i], 'original_session_local_unit_aliases':aliases, 'selected_count':k, 'unselected_inventory_count':len(full)-k, 'full_inventory_count':len(full), 'selected_QC2_QC3':[sum(q==2 for _,q in subset),sum(q==3 for _,q in subset)], 'inventory_QC2_QC3':[sum(q==2 for _,q in full),sum(q==3 for _,q in full)], 'whole_region_inventory_selected':len(full)==k, 'full_region_rank_sha256':_fingerprint([alias for alias,qc in ranked]), 'selected_membership_sha256':_fingerprint(aliases)})
        return {'schema':'neural094_pairwise_selected_units_v1','pair_index':pair_index,'session_ordinal':session_ordinal,'seed':seed,'K':k,'status':'metadata_subset_defined_not_executed','left':sides[0],'right':sides[1],'same_K':True,'operator_private_original_aliases_not_a_candidate_packet':True,'new_dense_candidate_alias_projection_required':True,'execution_selected':False,'inventory_source_authenticated':False}
